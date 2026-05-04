from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import tomllib
from pathlib import Path

from migration_common import (
    CONFIG_PATH,
    FaultScenario,
    atomic_lock,
    base_run_metadata,
    fail,
    local_only_root,
    main_with_errors,
    release_lock,
    run_fake_fault_tests,
    sha256_file,
    write_json,
)

TOOL_PATH = "plugins/turbo-mode/tools/migration/path_probe_wrapper.py"

FAULTS = [
    FaultScenario("after-scratch-marketplace", ("scratch/.agents/plugins/marketplace.json",)),
    FaultScenario("after-disposable-cache", ("cache/path-probe/9.9.9/.codex-plugin/plugin.json",)),
    FaultScenario("after-config-mutation", ("config.toml", "config.toml.bak")),
    FaultScenario("after-app-server-spawn-bookkeeping", ("app-server.pid",)),
    FaultScenario("after-install-before-read", ("cache/path-probe/9.9.9/installed",)),
    FaultScenario("sigint", ("lock", "config.toml.bak")),
    FaultScenario("sigterm", ("lock", "config.toml.bak")),
]


def fault_test(run_id: str) -> None:
    metadata = base_run_metadata(run_id=run_id, mode="path-probe-fault-test", tool_path=TOOL_PATH)
    root = Path(f"/private/tmp/turbo-mode-path-probe-faults-{run_id}")
    result = run_fake_fault_tests(root, FAULTS)
    write_json(
        Path("plugins/turbo-mode/evidence/2026-05-04-source-migration/path-probe-fault-test.summary.json"),
        {"run_metadata": metadata, **result, "result": "PATH_PROBE_FAULT_TESTS_PASSED"},
    )
    print("PATH_PROBE_FAULT_TESTS_PASSED")


def dry_run(run_id: str) -> None:
    metadata = base_run_metadata(run_id=run_id, mode="path-probe-dry-run", tool_path=TOOL_PATH)
    evidence_root = local_only_root(run_id, "path-probe")
    if not CONFIG_PATH.is_file():
        fail("path probe dry run", "config file missing", str(CONFIG_PATH))
    planned_root = Path(f"/private/tmp/turbo-mode-install-path-probe-{run_id}")
    summary = {
        "run_metadata": metadata,
        "local_only_evidence_root": str(evidence_root),
        "planned_probe_root": str(planned_root),
        "planned_cleanup_order": [
            "plugin/uninstall best-effort",
            "terminate app-server child",
            "remove disposable cache",
            "restore config backup",
            "remove scratch marketplace",
        ],
        "result": "PATH_PROBE_DRY_RUN_COMPLETE",
    }
    write_json(
        Path("plugins/turbo-mode/evidence/2026-05-04-source-migration/path-probe-dry-run.summary.json"),
        summary,
    )
    print("PATH_PROBE_DRY_RUN_COMPLETE")


def app_server_roundtrip(requests: list[dict[str, object]]) -> list[dict[str, object]]:
    proc = subprocess.Popen(
        ["codex", "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    transcript: list[dict[str, object]] = []
    try:
        for request in requests:
            proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            proc.stdin.flush()
            transcript.append({"direction": "send", "body": request})
            if "id" not in request:
                continue
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                response_line = proc.stdout.readline()
                if not response_line:
                    time.sleep(0.05)
                    continue
                try:
                    response = json.loads(response_line)
                except json.JSONDecodeError:
                    transcript.append({"direction": "recv-raw", "body": response_line.rstrip("\n")})
                    continue
                transcript.append({"direction": "recv", "body": response})
                if response.get("id") == request["id"]:
                    if "error" in response:
                        fail("app-server request", "response returned error", response)
                    break
            else:
                fail("app-server request", "timed out waiting for response", request)
    finally:
        proc.terminate()
        try:
            _stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _stdout, stderr = proc.communicate(timeout=5)
        transcript.append({"direction": "stderr", "body": stderr})
    return transcript


def assert_no_probe_config() -> None:
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if "path-probe@turbo-mode-path-probe" in config.get("plugins", {}):
        fail("path probe execute", "probe plugin config already exists", str(CONFIG_PATH))
    if "turbo-mode-path-probe" in config.get("marketplaces", {}):
        fail("path probe execute", "probe marketplace config already exists", str(CONFIG_PATH))


def restore_config(backup: Path) -> None:
    shutil.copy2(backup, CONFIG_PATH)


def trash_if_exists(path: Path) -> None:
    if not path.exists():
        return
    completed = subprocess.run(["trash", str(path)], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        fail("trash path", completed.stderr.strip() or completed.stdout.strip(), str(path))


def execute(run_id: str) -> None:
    metadata = base_run_metadata(run_id=run_id, mode="path-probe-execute", tool_path=TOOL_PATH)
    evidence_root = local_only_root(run_id, "path-probe")
    scratch_root = Path(f"/private/tmp/turbo-mode-install-path-probe-{run_id}")
    cache_root = Path("/Users/jp/.codex/plugins/cache/turbo-mode-path-probe")
    lock_path = Path(f"/private/tmp/turbo-mode-path-probe-{run_id}.lock")
    before = evidence_root / "config.before.toml"
    after = evidence_root / "config.after.toml"
    lock_fd = atomic_lock(lock_path)
    if cache_root.exists():
        fail("path probe execute", "probe cache already exists", str(cache_root))
    try:
        assert_no_probe_config()
        if scratch_root.exists():
            shutil.rmtree(scratch_root)
        shutil.copy2(CONFIG_PATH, before)
        marketplace = scratch_root / ".agents/plugins/marketplace.json"
        plugin_root = scratch_root / "path-probe/9.9.9"
        marketplace.parent.mkdir(parents=True, exist_ok=True)
        (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
        (plugin_root / "skills/path-probe").mkdir(parents=True, exist_ok=True)
        marketplace.write_text(
            json.dumps(
                {
                    "name": "turbo-mode-path-probe",
                    "interface": {"displayName": "Turbo Mode Path Probe"},
                    "plugins": [
                        {
                            "name": "path-probe",
                            "source": {"source": "local", "path": "./path-probe/9.9.9"},
                            "policy": {
                                "installation": "AVAILABLE",
                                "authentication": "ON_INSTALL",
                            },
                            "category": "Productivity",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (plugin_root / ".codex-plugin/plugin.json").write_text(
            json.dumps(
                {
                    "name": "path-probe",
                    "version": "9.9.9",
                    "description": "Disposable local plugin install-path probe",
                    "skills": "./skills/",
                    "interface": {
                        "displayName": "Path Probe",
                        "shortDescription": "Disposable local plugin install-path probe",
                        "developerName": "JP",
                        "category": "Productivity",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (plugin_root / "skills/path-probe/SKILL.md").write_text(
            "---\n"
            "name: path-probe\n"
            "description: Disposable local plugin install-path probe.\n"
            "---\n\n"
            "# Path Probe\n\n"
            "This disposable skill exists only to validate local plugin install path behavior.\n",
            encoding="utf-8",
        )
        requests: list[dict[str, object]] = [
            {
                "id": 0,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "turbo-mode-path-probe", "version": "0"},
                    "capabilities": {"experimentalApi": True},
                },
            },
            {"method": "initialized"},
            {
                "id": 1,
                "method": "plugin/install",
                "params": {
                    "marketplacePath": str(marketplace),
                    "pluginName": "path-probe",
                    "remoteMarketplaceName": None,
                },
            },
            {
                "id": 2,
                "method": "plugin/read",
                "params": {
                    "marketplacePath": str(marketplace),
                    "pluginName": "path-probe",
                    "remoteMarketplaceName": None,
                },
            },
        ]
        transcript = app_server_roundtrip(requests)
        (evidence_root / "transcript.json").write_text(
            json.dumps(transcript, indent=2),
            encoding="utf-8",
        )
        expected_installed = cache_root / "path-probe/9.9.9/.codex-plugin/plugin.json"
        local_segment = cache_root / "path-probe/local"
        if not expected_installed.is_file():
            fail(
                "path probe execute",
                "expected installed manifest missing",
                str(expected_installed),
            )
        if local_segment.exists():
            fail("path probe execute", "unexpected local cache segment exists", str(local_segment))
        restore_config(before)
        trash_if_exists(cache_root)
        shutil.copy2(CONFIG_PATH, after)
        assert_no_probe_config()
        if cache_root.exists():
            fail("path probe cleanup", "probe cache remains after cleanup", str(cache_root))
        write_json(
            Path(
                "plugins/turbo-mode/evidence/2026-05-04-source-migration/"
                "path-probe-execute.summary.json"
            ),
            {
                "run_metadata": metadata,
                "raw_transcript_sha256": sha256_file(evidence_root / "transcript.json"),
                "probe_marketplace_name": "turbo-mode-path-probe",
                "expected_versioned_installed_path": str(expected_installed.parent.parent),
                "local_segment_present": False,
                "config_digest_before": sha256_file(before),
                "config_digest_after": sha256_file(after),
                "cleanup_result": "probe cache and config entries absent after cleanup",
            },
        )
        print("PATH_PROBE_EXECUTE_COMPLETE")
    finally:
        if scratch_root.exists():
            shutil.rmtree(scratch_root)
        config_changed = (
            before.exists()
            and CONFIG_PATH.exists()
            and sha256_file(CONFIG_PATH) != sha256_file(before)
        )
        if config_changed:
            restore_config(before)
        release_lock(lock_fd, lock_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run disposable local install-path probe.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fault-test", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.fault_test:
        fault_test(args.run_id)
    elif args.dry_run:
        dry_run(args.run_id)
    else:
        execute(args.run_id)


if __name__ == "__main__":
    main_with_errors(main)
