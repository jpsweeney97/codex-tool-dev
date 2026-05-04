from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import tomllib
from pathlib import Path
from typing import Any

from migration_common import (
    CACHE_ROOTS,
    CONFIG_PATH,
    EVIDENCE_ROOT,
    MARKETPLACE_PATH,
    REPO_ROOT,
    SOURCE_ROOTS,
    FaultScenario,
    atomic_lock,
    base_run_metadata,
    fail,
    file_manifest,
    local_only_root,
    main_with_errors,
    read_json_bytes,
    release_lock,
    run_fake_fault_tests,
    sha256_file,
    write_json,
    write_sha256sums,
)

TOOL_PATH = "plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py"
PATH_PROBE_TOOL_PATH = "plugins/turbo-mode/tools/migration/path_probe_wrapper.py"
LOCK_PATH_TEMPLATE = "/private/tmp/turbo-mode-source-migration-{run_id}.lock"
PROCESS_BLOCKERS = (
    "ticket_engine_guard.py",
    "ticket_workflow.py",
    "ticket_",
    "codex app-server",
    "Codex",
    "codex exec",
)
EXPECTED_PLUGINS = {
    "handoff": "./plugins/turbo-mode/handoff/1.6.0",
    "ticket": "./plugins/turbo-mode/ticket/1.4.0",
}
PERSONAL_MARKETPLACE_PATH = Path("/Users/jp/.agents/plugins/marketplace.json")
REQUIRED_PREFLIGHT_SUMMARIES = {
    "runtime-preflight.summary.json": "runtime-preflight",
    "path-probe-fault-test.summary.json": "path-probe-fault-test",
    "path-probe-dry-run.summary.json": "path-probe-dry-run",
    "path-probe-execute.summary.json": "path-probe-execute",
}
RUNTIME_PREFLIGHT_TOOL_PATH = "plugins/turbo-mode/tools/migration/migration_common.py"
REQUEST_TIMEOUT_SECONDS = 30.0
REQUIRED_HANDOFF_SKILLS = {
    "handoff:quicksave",
    "handoff:save",
    "handoff:summary",
    "handoff:load",
    "handoff:search",
    "handoff:defer",
    "handoff:triage",
    "handoff:distill",
}
REQUIRED_INSTALLED_SMOKE_STEPS = (
    "handoff-search",
    "handoff-defer",
    "handoff-triage",
    "handoff-session-state-write",
    "handoff-session-state-read",
    "handoff-session-state-clear",
    "ticket-create-prepare",
    "ticket-create-execute",
    "ticket-scalar-acceptance-rejected",
    "ticket-update-priority-prepare",
    "ticket-update-priority-execute",
    "ticket-update-status-prepare",
    "ticket-update-status-execute",
    "ticket-close-prepare",
    "ticket-close-execute",
    "ticket-reopen-prepare",
    "ticket-reopen-execute",
    "ticket-noncanonical-denied",
    "ticket-read-list",
    "ticket-read-query",
    "ticket-triage-dashboard",
    "ticket-audit-repair-dry-run",
)

FAULTS = [
    FaultScenario("registration-failure-after-config-backup", ("config.before.toml",)),
    FaultScenario(
        "one-cache-replaced-second-install-failing",
        ("cache/handoff/backup", "cache/ticket/new"),
    ),
    FaultScenario("source-cache-equality-mismatch", ("cache/handoff/file", "source/handoff/file")),
    FaultScenario("app-server-child-crash", ("app-server.pid",)),
    FaultScenario("installed-smoke-failure", ("smoke/output.json",)),
    FaultScenario("plugin-hooks-disable-restore", ("config.before.toml", "config.disabled.toml")),
    FaultScenario("sigint", ("lock", "config.before.toml")),
    FaultScenario("sigterm", ("lock", "config.before.toml")),
]


def fault_test(run_id: str) -> None:
    metadata = base_run_metadata(
        run_id=run_id,
        mode="cache-refresh-fault-test",
        tool_path=TOOL_PATH,
    )
    root = Path(f"/private/tmp/turbo-mode-cache-refresh-faults-{run_id}")
    result = run_fake_fault_tests(root, FAULTS)
    write_json(
        Path(
            "plugins/turbo-mode/evidence/2026-05-04-source-migration/cache-refresh-fault-test.summary.json"
        ),
        {"run_metadata": metadata, **result, "result": "CACHE_REFRESH_FAULT_TESTS_PASSED"},
    )
    print("CACHE_REFRESH_FAULT_TESTS_PASSED")


def dry_run(run_id: str) -> None:
    metadata = base_run_metadata(run_id=run_id, mode="cache-refresh-dry-run", tool_path=TOOL_PATH)
    readiness = verify_dry_run_prerequisites(run_id, metadata)
    evidence_root = local_only_root(run_id, "cache-refresh")
    backup_root = evidence_root / "cache-backup"
    write_json(
        Path(
            "plugins/turbo-mode/evidence/2026-05-04-source-migration/cache-refresh-dry-run.summary.json"
        ),
        {
            "run_metadata": metadata,
            "local_only_evidence_root": str(evidence_root),
            "backup_root": str(backup_root),
            "readiness": readiness,
            "planned_restore_order": [
                "terminate app-server child",
                "quarantine partial cache roots",
                "restore Handoff and Ticket cache roots from backup",
                "restore prior config.toml",
                "verify restored cache manifests",
                "verify restored marketplace stanza",
            ],
            "result": "DRY_RUN_COMPLETE_EXTERNAL_EXECUTE_REQUIRED",
        },
    )
    print("DRY_RUN_COMPLETE_EXTERNAL_EXECUTE_REQUIRED")


def read_json_path(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail("read json evidence", "file missing", str(path))
    return read_json_bytes(path.read_bytes(), source=str(path))


def validate_repo_marketplace() -> dict[str, str]:
    data = read_json_path(MARKETPLACE_PATH)
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        fail("validate repo marketplace", "plugins is not a list", str(MARKETPLACE_PATH))
    found: dict[str, str] = {}
    for plugin in plugins:
        if not isinstance(plugin, dict):
            continue
        name = plugin.get("name")
        source = plugin.get("source")
        policy = plugin.get("policy")
        if (
            not isinstance(name, str)
            or not isinstance(source, dict)
            or not isinstance(policy, dict)
        ):
            continue
        found[name] = str(source.get("path"))
        if source.get("source") != "local":
            fail("validate repo marketplace", f"{name} source is not local", source)
        if (
            policy.get("installation") != "AVAILABLE"
            or policy.get("authentication") != "ON_INSTALL"
        ):
            fail("validate repo marketplace", f"{name} policy is not installable", policy)
        if plugin.get("category") != "Productivity":
            fail(
                "validate repo marketplace",
                f"{name} category is not Productivity",
                plugin.get("category"),
            )
    if found != EXPECTED_PLUGINS:
        fail("validate repo marketplace", "plugin source paths mismatch", found)
    return found


def validate_config_parseable() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        fail("cache refresh dry run", "config file missing", str(CONFIG_PATH))
    try:
        return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        fail("cache refresh dry run", f"config TOML parse failed: {exc}", str(CONFIG_PATH))


def expected_metadata_for(run_id: str, mode: str, tool_path: str) -> dict[str, Any]:
    if tool_path.startswith("manual-shell:"):
        metadata = base_run_metadata(run_id=run_id, mode=mode, tool_path=TOOL_PATH)
        metadata["tool_path"] = tool_path
        metadata["tool_sha256"] = None
        return metadata
    return base_run_metadata(run_id=run_id, mode=mode, tool_path=tool_path)


def validate_summary_metadata(
    path: Path, *, run_id: str, mode: str, tool_path: str
) -> dict[str, Any]:
    summary = read_json_path(path)
    metadata = summary.get("run_metadata")
    if not isinstance(metadata, dict):
        fail("validate evidence metadata", "run_metadata missing", str(path))
    expected = expected_metadata_for(run_id, mode, tool_path)
    for key in (
        "run_id",
        "plan_sha256",
        "repo_head",
        "source_roots",
        "cache_roots",
        "config_path",
        "marketplace_path",
    ):
        if metadata.get(key) != expected.get(key):
            fail(
                "validate evidence metadata",
                f"stale {key}",
                {"path": str(path), "actual": metadata.get(key), "expected": expected.get(key)},
            )
    if metadata.get("mode") != mode:
        fail(
            "validate evidence metadata",
            "mode mismatch",
            {"path": str(path), "actual": metadata.get("mode"), "expected": mode},
        )
    if metadata.get("tool_path") != tool_path:
        fail(
            "validate evidence metadata",
            "tool_path mismatch",
            {"path": str(path), "actual": metadata.get("tool_path"), "expected": tool_path},
        )
    if expected.get("tool_sha256") is not None and metadata.get("tool_sha256") != expected.get(
        "tool_sha256"
    ):
        fail(
            "validate evidence metadata",
            "tool_sha256 mismatch",
            {
                "path": str(path),
                "actual": metadata.get("tool_sha256"),
                "expected": expected.get("tool_sha256"),
            },
        )
    return summary


def verify_dry_run_prerequisites(run_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    validate_config_parseable()
    marketplace_plugins = validate_repo_marketplace()
    missing_cache = [str(path) for path in CACHE_ROOTS if not path.exists()]
    if missing_cache:
        fail("cache refresh dry run", "active cache roots missing", missing_cache)
    lock_path = Path(LOCK_PATH_TEMPLATE.format(run_id=run_id))
    if lock_path.exists():
        fail("cache refresh dry run", "prior lock exists", str(lock_path))
    summaries: dict[str, dict[str, Any]] = {}
    for filename, mode in REQUIRED_PREFLIGHT_SUMMARIES.items():
        tool_path = (
            PATH_PROBE_TOOL_PATH if mode.startswith("path-probe") else RUNTIME_PREFLIGHT_TOOL_PATH
        )
        summaries[filename] = validate_summary_metadata(
            EVIDENCE_ROOT / filename,
            run_id=run_id,
            mode=mode,
            tool_path=tool_path,
        )
    execute_summary = summaries["path-probe-execute.summary.json"]
    if execute_summary.get("local_segment_present") is not False:
        fail(
            "cache refresh dry run",
            "path probe did not reject local cache segment",
            execute_summary,
        )
    installed_path = str(execute_summary.get("expected_versioned_installed_path", ""))
    if "/path-probe/9.9.9" not in installed_path:
        fail(
            "cache refresh dry run", "path probe did not prove versioned cache root", installed_path
        )
    return {
        "config_parseable": True,
        "marketplace_plugins": marketplace_plugins,
        "cache_roots": [str(path) for path in CACHE_ROOTS],
        "lock_absent": str(lock_path),
        "validated_summaries": sorted(REQUIRED_PREFLIGHT_SUMMARIES),
        "tool_sha256": metadata["tool_sha256"],
    }


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
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []

    def read_stdout() -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        finally:
            output.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        for request in requests:
            proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            proc.stdin.flush()
            transcript.append({"direction": "send", "body": request})
            if "id" not in request:
                continue
            deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    response_line = output.get(timeout=min(0.1, remaining))
                except queue.Empty:
                    continue
                if response_line is None:
                    fail("app-server request", "stdout closed before response", request)
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
        reader.join(timeout=1)
    return transcript


def capture_process_check(evidence_root: Path, metadata: dict[str, Any], label: str) -> None:
    completed = subprocess.run(
        ["ps", "-axo", "pid,command"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail(
            "process check",
            completed.stderr.strip() or completed.stdout.strip(),
            "ps -axo pid,command",
        )
    raw_path = evidence_root / f"process-{label}.txt"
    raw_path.write_text(completed.stdout, encoding="utf-8")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    current_pid = str(os.getpid())
    blockers = [
        line
        for line in lines
        if current_pid not in line and any(marker in line for marker in PROCESS_BLOCKERS)
    ]
    write_json(
        EVIDENCE_ROOT / f"process-check-{label}.summary.json",
        {
            "run_metadata": metadata,
            "raw_process_sha256": sha256_file(raw_path),
            "blocked_process_count": len(blockers),
            "blocked_markers": sorted(
                {marker for marker in PROCESS_BLOCKERS for line in blockers if marker in line}
            ),
        },
    )
    if blockers:
        fail(
            "process check",
            "hook-capable Codex process present",
            {"count": len(blockers), "label": label},
        )


def set_plugin_hooks(enabled: bool) -> None:
    original = CONFIG_PATH.read_text(encoding="utf-8")
    lines = original.splitlines()
    output: list[str] = []
    in_features = False
    saw_features = False
    wrote_key = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_features and not wrote_key:
                output.append(f"plugin_hooks = {str(enabled).lower()}")
                wrote_key = True
            in_features = stripped == "[features]"
            saw_features = saw_features or in_features
            output.append(line)
            continue
        if in_features and stripped.startswith("plugin_hooks"):
            output.append(f"plugin_hooks = {str(enabled).lower()}")
            wrote_key = True
        else:
            output.append(line)
    if in_features and not wrote_key:
        output.append(f"plugin_hooks = {str(enabled).lower()}")
        wrote_key = True
    if not saw_features:
        if output and output[-1].strip():
            output.append("")
        output.extend(["[features]", f"plugin_hooks = {str(enabled).lower()}"])
    CONFIG_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")


def write_manifest_snapshot(root: Path, output: Path, metadata: dict[str, Any]) -> dict[str, str]:
    manifest = file_manifest(root)
    write_sha256sums(output, manifest, metadata=metadata)
    return manifest


def backup_cache_roots(backup_root: Path) -> None:
    if backup_root.exists():
        shutil.rmtree(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)
    for cache_root in CACHE_ROOTS:
        destination = backup_root / cache_root.name
        shutil.copytree(cache_root, destination)


def restore_cache_roots(backup_root: Path, failed_root: Path) -> None:
    failed_root.mkdir(parents=True, exist_ok=True)
    for cache_root in CACHE_ROOTS:
        if cache_root.exists():
            destination = failed_root / cache_root.name
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(cache_root), str(destination))
        backup = backup_root / cache_root.name
        if backup.exists():
            shutil.copytree(backup, cache_root)


def quarantine_cache_roots(quarantine_root: Path) -> None:
    if quarantine_root.exists():
        shutil.rmtree(quarantine_root)
    quarantine_root.mkdir(parents=True, exist_ok=True)
    for cache_root in CACHE_ROOTS:
        if cache_root.exists():
            shutil.move(str(cache_root), str(quarantine_root / cache_root.name))


def quarantine_personal_marketplace(evidence_root: Path) -> Path | None:
    if not PERSONAL_MARKETPLACE_PATH.exists():
        return None
    backup = evidence_root / "personal-marketplace.before.json"
    if backup.exists():
        backup.unlink()
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(PERSONAL_MARKETPLACE_PATH), str(backup))
    return backup


def restore_personal_marketplace(backup: Path | None) -> str:
    if backup is None:
        return "not_present"
    if not backup.exists():
        return "backup_missing"
    PERSONAL_MARKETPLACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PERSONAL_MARKETPLACE_PATH.exists():
        fail(
            "personal marketplace restore",
            "destination already exists",
            str(PERSONAL_MARKETPLACE_PATH),
        )
    shutil.move(str(backup), str(PERSONAL_MARKETPLACE_PATH))
    return "restored"


def register_repo_marketplace(evidence_root: Path) -> None:
    existing = current_marketplace_stanza()
    if existing.get("source_type") == "local" and existing.get("source") == str(REPO_ROOT):
        (evidence_root / "marketplace-add.stdout.txt").write_text(
            "turbo-mode marketplace already registered\n",
            encoding="utf-8",
        )
        (evidence_root / "marketplace-add.stderr.txt").write_text("", encoding="utf-8")
        return
    if existing:
        completed = subprocess.run(
            ["codex", "plugin", "marketplace", "remove", "turbo-mode"],
            text=True,
            capture_output=True,
            check=False,
        )
        (evidence_root / "marketplace-remove.stdout.txt").write_text(
            completed.stdout,
            encoding="utf-8",
        )
        (evidence_root / "marketplace-remove.stderr.txt").write_text(
            completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            fail(
                "remove existing marketplace",
                completed.stderr.strip() or completed.stdout.strip(),
                existing,
            )
    completed = subprocess.run(
        ["codex", "plugin", "marketplace", "add", str(REPO_ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    (evidence_root / "marketplace-add.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (evidence_root / "marketplace-add.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        fail(
            "register marketplace",
            completed.stderr.strip() or completed.stdout.strip(),
            str(REPO_ROOT),
        )
    config = validate_config_parseable()
    turbo = config.get("marketplaces", {}).get("turbo-mode", {})
    if turbo.get("source_type") != "local" or turbo.get("source") != str(REPO_ROOT):
        fail("register marketplace", "turbo-mode marketplace stanza mismatch", turbo)


def install_and_inventory(run_id: str, evidence_root: Path, metadata: dict[str, Any]) -> None:
    scratch = Path(f"/private/tmp/turbo-mode-source-migration-smoke-{run_id}")
    scratch.mkdir(parents=True, exist_ok=True)
    requests: list[dict[str, object]] = [
        {
            "id": 0,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "turbo-mode-source-migration", "version": "0"},
                "capabilities": {"experimentalApi": True},
            },
        },
        {"method": "initialized"},
        {
            "id": 1,
            "method": "plugin/install",
            "params": {
                "marketplacePath": str(MARKETPLACE_PATH),
                "pluginName": "handoff",
                "remoteMarketplaceName": None,
            },
        },
        {
            "id": 2,
            "method": "plugin/install",
            "params": {
                "marketplacePath": str(MARKETPLACE_PATH),
                "pluginName": "ticket",
                "remoteMarketplaceName": None,
            },
        },
        {
            "id": 3,
            "method": "plugin/read",
            "params": {
                "marketplacePath": str(MARKETPLACE_PATH),
                "pluginName": "handoff",
                "remoteMarketplaceName": None,
            },
        },
        {
            "id": 4,
            "method": "plugin/read",
            "params": {
                "marketplacePath": str(MARKETPLACE_PATH),
                "pluginName": "ticket",
                "remoteMarketplaceName": None,
            },
        },
        {
            "id": 5,
            "method": "plugin/list",
            "params": {"marketplacePath": str(MARKETPLACE_PATH), "remoteMarketplaceName": None},
        },
        {"id": 6, "method": "skills/list", "params": {"cwds": [str(scratch)]}},
        {"id": 7, "method": "hooks/list", "params": {"cwds": [str(scratch)]}},
    ]
    transcript = app_server_roundtrip(requests)
    transcript_path = evidence_root / "app-server-install-inventory.transcript.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    inventory = validate_inventory_contract(transcript)
    write_json(
        EVIDENCE_ROOT / "hook-inventory.summary.json",
        {
            "run_metadata": metadata,
            "raw_transcript_sha256": sha256_file(transcript_path),
            "requests": [request.get("method") for request in requests],
            "inventory": inventory,
            "result": "APP_SERVER_INSTALL_AND_INVENTORY_COMPLETE",
        },
    )


def response_by_id(transcript: list[dict[str, object]]) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {}
    for item in transcript:
        if item.get("direction") != "recv":
            continue
        body = item.get("body")
        if not isinstance(body, dict):
            continue
        response_id = body.get("id")
        if isinstance(response_id, int):
            responses[response_id] = body
    return responses


def walk_json(value: object) -> list[object]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(walk_json(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(walk_json(child))
    return items


def json_contains(value: object, needle: str) -> bool:
    return needle in json.dumps(value, sort_keys=True)


def validate_plugin_read_response(response: dict[str, Any], plugin: str) -> str:
    expected = str(REPO_ROOT / EXPECTED_PLUGINS[plugin].removeprefix("./"))
    if json_contains(response, "/plugin-dev/"):
        fail("inventory contract", "plugin/read contains plugin-dev path", plugin)
    if not json_contains(response, expected):
        fail(
            "inventory contract", f"plugin/read missing repo source metadata for {plugin}", expected
        )
    return expected


def validate_plugin_list_response(response: dict[str, Any]) -> list[str]:
    serialized = json.dumps(response, sort_keys=True)
    missing = [
        f"{name}@turbo-mode" for name in EXPECTED_PLUGINS if f"{name}@turbo-mode" not in serialized
    ]
    if missing:
        fail("inventory contract", "plugin/list missing Turbo Mode plugins", missing)
    if "/plugin-dev/" in serialized:
        fail("inventory contract", "plugin/list contains plugin-dev path", response)
    return sorted(EXPECTED_PLUGINS)


def validate_skills_response(response: dict[str, Any]) -> list[str]:
    serialized = json.dumps(response, sort_keys=True)
    missing = sorted(skill for skill in REQUIRED_HANDOFF_SKILLS if skill not in serialized)
    if missing:
        fail("inventory contract", "skills/list missing Handoff skills", missing)
    cache_prefix = "/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/skills/"
    if cache_prefix not in serialized:
        fail(
            "inventory contract", "skills/list missing installed-cache Handoff paths", cache_prefix
        )
    if "/plugin-dev/" in serialized:
        fail("inventory contract", "skills/list contains plugin-dev path", cache_prefix)
    return sorted(REQUIRED_HANDOFF_SKILLS)


def validate_hooks_response(response: dict[str, Any]) -> dict[str, Any]:
    hooks = [
        item
        for item in walk_json(response)
        if isinstance(item, dict)
        and item.get("pluginId") == "ticket@turbo-mode"
        and item.get("eventName") == "preToolUse"
        and item.get("matcher") == "Bash"
    ]
    if len(hooks) != 1:
        fail("inventory contract", "expected exactly one Ticket Bash preToolUse hook", len(hooks))
    hook = hooks[0]
    command = str(hook.get("command", ""))
    source_path = str(hook.get("sourcePath", ""))
    expected_prefix = "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/"
    expected_suffix = "/hooks/ticket_engine_guard.py"
    expected_source = "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
    if not command.startswith(expected_prefix) or not command.endswith(expected_suffix):
        fail("inventory contract", "Ticket hook command mismatch", command)
    if source_path != expected_source:
        fail("inventory contract", "Ticket hook sourcePath mismatch", source_path)
    if "/plugin-dev/" in command or "/plugin-dev/" in source_path:
        fail("inventory contract", "Ticket hook contains plugin-dev path", hook)
    return {"command": command, "sourcePath": source_path}


def validate_inventory_contract(transcript: list[dict[str, object]]) -> dict[str, Any]:
    responses = response_by_id(transcript)
    required = {3, 4, 5, 6, 7}
    missing = sorted(required - set(responses))
    if missing:
        fail("inventory contract", "missing app-server responses", missing)
    return {
        "plugin_read_sources": {
            "handoff": validate_plugin_read_response(responses[3], "handoff"),
            "ticket": validate_plugin_read_response(responses[4], "ticket"),
        },
        "plugin_list": validate_plugin_list_response(responses[5]),
        "handoff_skills": validate_skills_response(responses[6]),
        "ticket_hook": validate_hooks_response(responses[7]),
    }


def assert_forbidden_ticket_paths_absent() -> None:
    forbidden = ("docs/tickets", "docs/tickets/.audit", "docs/superpowers/plans")
    present: list[str] = []
    for root in (SOURCE_ROOTS[1], CACHE_ROOTS[1]):
        for rel in forbidden:
            path = root / rel
            if path.exists():
                present.append(str(path))
    if present:
        fail("source cache equality", "forbidden Ticket paths present", present)


def assert_no_residue() -> None:
    residue: list[str] = []
    for root in [REPO_ROOT / "plugins/turbo-mode", *CACHE_ROOTS]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                path.name
                in {
                    ".DS_Store",
                    "__pycache__",
                    ".pytest_cache",
                    ".ruff_cache",
                    ".mypy_cache",
                    ".venv",
                }
                or ".codex/ticket-tmp" in path.as_posix()
            ):
                residue.append(str(path))
    if residue:
        fail("source cache residue", "generated residue present", sorted(residue))


def run_source_cache_gate(run_id: str, metadata: dict[str, Any], label: str) -> None:
    assert_forbidden_ticket_paths_absent()
    assert_no_residue()
    results: dict[str, Any] = {}
    for name, source, cache in (
        ("handoff", SOURCE_ROOTS[0], CACHE_ROOTS[0]),
        ("ticket", SOURCE_ROOTS[1], CACHE_ROOTS[1]),
    ):
        source_manifest = file_manifest(source)
        cache_manifest = file_manifest(cache)
        missing = sorted(set(source_manifest) - set(cache_manifest))
        extra = sorted(set(cache_manifest) - set(source_manifest))
        changed = sorted(
            path
            for path in set(source_manifest) & set(cache_manifest)
            if source_manifest[path] != cache_manifest[path]
        )
        results[name] = {
            "source_file_count": len(source_manifest),
            "cache_file_count": len(cache_manifest),
            "missing_in_cache": missing,
            "extra_in_cache": extra,
            "hash_mismatch": changed,
        }
        if missing or extra or changed:
            fail("source cache equality", f"{name} mismatch", results[name])
    write_json(
        EVIDENCE_ROOT / f"{label}-source-cache-equality.summary.json",
        {
            "run_metadata": metadata,
            "run_id": run_id,
            "plugins": results,
            "result": "SOURCE_CACHE_EQUALITY_PASSED",
        },
    )


def run_installed_smoke(run_id: str, evidence_root: Path, metadata: dict[str, Any]) -> None:
    smoke_root = Path(f"/private/tmp/turbo-mode-source-migration-smoke-{run_id}")
    smoke_root.mkdir(parents=True, exist_ok=True)
    (smoke_root / ".codex").mkdir(exist_ok=True)
    (smoke_root / "payloads").mkdir(exist_ok=True)
    (smoke_root / "docs/tickets").mkdir(parents=True, exist_ok=True)
    handoff_dir = smoke_root / "docs/handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    phrase = f"turbo-mode-smoke-{run_id}"
    (handoff_dir / "2026-05-04_00-00_smoke.md").write_text(
        "---\n"
        "date: 2026-05-04\n"
        'time: "00:00"\n'
        'created_at: "2026-05-04T00:00:00Z"\n'
        "session_id: 00000000-0000-4000-8000-000000000000\n"
        "project: smoke\n"
        "title: Smoke\n"
        "type: checkpoint\n"
        "files: []\n"
        "---\n\n"
        f"## Goal\n\n{phrase}\n",
        encoding="utf-8",
    )
    results: list[dict[str, Any]] = []
    handoff_root = CACHE_ROOTS[0]
    ticket_root = CACHE_ROOTS[1]

    append_smoke_result(
        results,
        run_smoke_command(
            "handoff-search",
            ["python3", "-B", str(handoff_root / "scripts/search.py"), phrase],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
        ),
    )
    append_smoke_result(
        results,
        run_smoke_command(
            "handoff-defer",
            [
                "python3",
                "-B",
                str(handoff_root / "scripts/defer.py"),
                "--tickets-dir",
                "docs/tickets",
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
            input_text=json.dumps(
                [
                    {
                        "summary": f"Deferred smoke {run_id}",
                        "problem": "Exercise installed Handoff defer envelope emission.",
                        "priority": "medium",
                    }
                ]
            ),
            expected_states={"ok"},
        ),
    )
    if not list((smoke_root / "docs/tickets/.envelopes").glob("*.json")):
        fail("installed smoke", "Handoff defer did not emit an envelope", str(smoke_root))
    append_smoke_result(
        results,
        run_smoke_command(
            "handoff-triage",
            [
                "python3",
                "-B",
                str(handoff_root / "scripts/triage.py"),
                "--tickets-dir",
                "docs/tickets",
                "--handoffs-dir",
                "docs/handoffs",
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
        ),
    )

    state_dir = smoke_root / "docs/handoffs/.session-state"
    archived = smoke_root / "docs/handoffs/archive/smoke.md"
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("smoke", encoding="utf-8")
    write_state = run_smoke_command(
        "handoff-session-state-write",
        [
            "python3",
            "-B",
            str(handoff_root / "scripts/session_state.py"),
            "write-state",
            "--state-dir",
            str(state_dir),
            "--project",
            "smoke",
            "--archive-path",
            str(archived),
            "--field",
            "state_path",
        ],
        smoke_root=smoke_root,
        evidence_root=evidence_root,
    )
    append_smoke_result(results, write_state)
    state_path = write_state["stdout"].strip()
    append_smoke_result(
        results,
        run_smoke_command(
            "handoff-session-state-read",
            [
                "python3",
                "-B",
                str(handoff_root / "scripts/session_state.py"),
                "read-state",
                "--state-dir",
                str(state_dir),
                "--project",
                "smoke",
                "--field",
                "archive_path",
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
        ),
    )
    append_smoke_result(
        results,
        run_smoke_command(
            "handoff-session-state-clear",
            [
                "python3",
                "-B",
                str(handoff_root / "scripts/session_state.py"),
                "clear-state",
                "--state-dir",
                str(state_dir),
                "--state-path",
                state_path,
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
        ),
    )

    create_payload = write_smoke_payload(
        smoke_root,
        "ticket-create",
        trusted_ticket_payload(
            run_id,
            "create",
            {
                "title": f"Installed smoke {run_id}",
                "problem": "Exercise installed Ticket create workflow.",
                "priority": "medium",
                "acceptance_criteria": ["Smoke passes"],
            },
        ),
    )
    append_smoke_result(
        results,
        run_workflow_smoke_step(
            "ticket-create-prepare",
            ticket_root,
            "prepare",
            create_payload,
            smoke_root,
            evidence_root,
        ),
    )
    create_execute = run_workflow_smoke_step(
        "ticket-create-execute", ticket_root, "execute", create_payload, smoke_root, evidence_root
    )
    append_smoke_result(results, create_execute)
    ticket_id = create_execute["json"].get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        fail("installed smoke", "Ticket create did not return a ticket_id", create_execute["json"])

    scalar_payload = write_smoke_payload(
        smoke_root,
        "ticket-scalar-acceptance",
        trusted_ticket_payload(
            run_id,
            "create",
            {
                "title": f"Scalar acceptance {run_id}",
                "problem": "Exercise scalar acceptance rejection.",
                "priority": "medium",
                "acceptance_criteria": "not-a-list",
            },
        ),
    )
    append_smoke_result(
        results,
        run_workflow_smoke_step(
            "ticket-scalar-acceptance-rejected",
            ticket_root,
            "prepare",
            scalar_payload,
            smoke_root,
            evidence_root,
            expected_returncodes={2},
            expected_states={"need_fields"},
        ),
    )
    for label, action, fields in (
        ("ticket-update-priority", "update", {"priority": "high"}),
        ("ticket-update-status", "update", {"status": "in_progress"}),
        ("ticket-close", "close", {"resolution": "done"}),
        ("ticket-reopen", "reopen", {"reopen_reason": "Need more work"}),
    ):
        payload = write_smoke_payload(
            smoke_root,
            label,
            trusted_ticket_payload(run_id, action, fields, ticket_id=ticket_id),
        )
        append_smoke_result(
            results,
            run_workflow_smoke_step(
                f"{label}-prepare", ticket_root, "prepare", payload, smoke_root, evidence_root
            ),
        )
        append_smoke_result(
            results,
            run_workflow_smoke_step(
                f"{label}-execute", ticket_root, "execute", payload, smoke_root, evidence_root
            ),
        )

    append_smoke_result(
        results,
        run_noncanonical_hook_smoke(ticket_root, create_payload, smoke_root, evidence_root),
    )
    append_smoke_result(
        results,
        run_smoke_command(
            "ticket-read-list",
            ["python3", "-B", str(ticket_root / "scripts/ticket_read.py"), "list", "docs/tickets"],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
            expected_states={"ok"},
        ),
    )
    append_smoke_result(
        results,
        run_smoke_command(
            "ticket-read-query",
            [
                "python3",
                "-B",
                str(ticket_root / "scripts/ticket_read.py"),
                "query",
                "docs/tickets",
                ticket_id,
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
            expected_states={"ok"},
        ),
    )
    append_smoke_result(
        results,
        run_smoke_command(
            "ticket-triage-dashboard",
            [
                "python3",
                "-B",
                str(ticket_root / "scripts/ticket_triage.py"),
                "dashboard",
                "docs/tickets",
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
        ),
    )
    append_smoke_result(
        results,
        run_smoke_command(
            "ticket-audit-repair-dry-run",
            [
                "python3",
                "-B",
                str(ticket_root / "scripts/ticket_audit.py"),
                "repair",
                "docs/tickets",
                "--dry-run",
            ],
            smoke_root=smoke_root,
            evidence_root=evidence_root,
            expected_states={"ok"},
        ),
    )
    observed = {result["label"] for result in results}
    missing = sorted(set(REQUIRED_INSTALLED_SMOKE_STEPS) - observed)
    if missing:
        fail("installed smoke", "required smoke steps missing", missing)
    write_json(
        EVIDENCE_ROOT / "installed-smoke.summary.json",
        {
            "run_metadata": metadata,
            "smoke_root": str(smoke_root),
            "steps": redact_smoke_results(results),
            "result": "INSTALLED_SMOKE_PASSED",
        },
    )


def trusted_ticket_payload(
    run_id: str,
    action: str,
    fields: dict[str, Any],
    *,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": action,
        "args": {},
        "request_origin": "user",
        "hook_injected": True,
        "hook_request_origin": "user",
        "session_id": f"installed-smoke-{run_id}-{action}",
        "fields": fields,
    }
    if ticket_id is not None:
        payload["args"]["ticket_id"] = ticket_id
    return payload


def write_smoke_payload(smoke_root: Path, label: str, payload: dict[str, Any]) -> Path:
    path = smoke_root / "payloads" / f"{label}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def append_smoke_result(results: list[dict[str, Any]], result: dict[str, Any]) -> None:
    results.append(result)


def run_workflow_smoke_step(
    label: str,
    ticket_root: Path,
    subcommand: str,
    payload_path: Path,
    smoke_root: Path,
    evidence_root: Path,
    *,
    expected_returncodes: set[int] | None = None,
    expected_states: set[str] | None = None,
) -> dict[str, Any]:
    return run_smoke_command(
        label,
        [
            "python3",
            "-B",
            str(ticket_root / "scripts/ticket_workflow.py"),
            subcommand,
            str(payload_path),
        ],
        smoke_root=smoke_root,
        evidence_root=evidence_root,
        expected_returncodes=expected_returncodes,
        expected_states=expected_states
        or {"ready_to_execute", "ok_create", "ok_update", "ok_close", "ok_reopen"},
    )


def run_smoke_command(
    label: str,
    command: list[str],
    *,
    smoke_root: Path,
    evidence_root: Path,
    input_text: str | None = None,
    expected_returncodes: set[int] | None = None,
    expected_states: set[str] | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=smoke_root,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    stdout_path = write_smoke_output(evidence_root, label, completed.stdout, "stdout")
    stderr_path = write_smoke_output(evidence_root, label, completed.stderr, "stderr")
    allowed = expected_returncodes or {0}
    if completed.returncode not in allowed:
        fail("installed smoke", completed.stderr.strip() or completed.stdout.strip(), command)
    parsed: dict[str, Any] | None = None
    if completed.stdout.strip().startswith("{"):
        parsed = read_json_bytes(completed.stdout.encode("utf-8"), source=f"{label} stdout")
        parsed_state = parsed.get("state", parsed.get("status"))
        if expected_states is not None and parsed_state not in expected_states:
            fail("installed smoke", f"{label} returned unexpected state", parsed)
    return {
        "label": label,
        "command": command[:3],
        "returncode": completed.returncode,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "state": parsed.get("state", parsed.get("status")) if parsed else None,
        "json": parsed or {},
        "stdout": completed.stdout,
    }


def run_noncanonical_hook_smoke(
    ticket_root: Path,
    payload_path: Path,
    smoke_root: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    before_payload = sha256_file(payload_path)
    before_tickets = file_manifest(smoke_root / "docs/tickets")
    before_audit = file_manifest(smoke_root / "docs/tickets/.audit")
    event = {
        "session_id": "installed-smoke-noncanonical",
        "transcript_path": str(evidence_root / "noncanonical-transcript.jsonl"),
        "cwd": str(smoke_root),
        "permission_mode": "default",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                f"/usr/bin/python3 -B {ticket_root}/scripts/ticket_workflow.py "
                f"prepare {payload_path}"
            )
        },
        "tool_use_id": "toolu_installed_smoke",
    }
    result = run_smoke_command(
        "ticket-noncanonical-denied",
        ["python3", "-B", str(ticket_root / "hooks/ticket_engine_guard.py")],
        smoke_root=smoke_root,
        evidence_root=evidence_root,
        input_text=json.dumps(event),
    )
    output = result["json"]
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    if decision != "deny":
        fail("installed smoke", "noncanonical Ticket command was not denied", output)
    if sha256_file(payload_path) != before_payload:
        fail("installed smoke", "noncanonical denial mutated payload", str(payload_path))
    if file_manifest(smoke_root / "docs/tickets") != before_tickets:
        fail("installed smoke", "noncanonical denial mutated tickets", str(smoke_root))
    if file_manifest(smoke_root / "docs/tickets/.audit") != before_audit:
        fail("installed smoke", "noncanonical denial mutated audit", str(smoke_root))
    return result


def redact_smoke_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": result["label"],
            "command": result["command"],
            "returncode": result["returncode"],
            "stdout_sha256": result["stdout_sha256"],
            "stderr_sha256": result["stderr_sha256"],
            "state": result["state"],
        }
        for result in results
    ]


def write_smoke_output(evidence_root: Path, label: str, content: str, stream: str) -> Path:
    path = evidence_root / f"smoke-{label}.{stream}.txt"
    path.write_text(content, encoding="utf-8")
    return path


def rollback(
    *,
    metadata: dict[str, Any],
    evidence_root: Path,
    config_backup: Path,
    backup_root: Path,
    failed_root: Path,
    reason: str,
    pre_cache_manifests: dict[str, dict[str, str]],
    prior_marketplace_stanza: dict[str, Any],
    personal_marketplace_backup: Path | None = None,
) -> None:
    cache_restore_result = "skipped_pre_cache_mutation"
    if pre_cache_manifests:
        restore_cache_roots(backup_root, failed_root)
        cache_restore_result = "restored"
    if config_backup.exists():
        shutil.copy2(config_backup, CONFIG_PATH)
    personal_marketplace_restore = restore_personal_marketplace(personal_marketplace_backup)
    verify_rollback_restored(pre_cache_manifests, prior_marketplace_stanza)
    write_json(
        evidence_root / "ROLLBACK_COMPLETE.json",
        {
            "run_metadata": metadata,
            "cache_restore": cache_restore_result,
            "personal_marketplace_restore": personal_marketplace_restore,
            "reason": reason,
            "result": "ROLLBACK_COMPLETE",
        },
    )
    write_json(
        EVIDENCE_ROOT / "cache-refresh-rollback.summary.json",
        {
            "run_metadata": metadata,
            "rollback_local_only_sha256": sha256_file(evidence_root / "ROLLBACK_COMPLETE.json"),
            "result": "ROLLBACK_COMPLETE",
        },
    )


def current_marketplace_stanza() -> dict[str, Any]:
    config = validate_config_parseable()
    marketplaces = config.get("marketplaces", {})
    if not isinstance(marketplaces, dict):
        return {}
    turbo = marketplaces.get("turbo-mode", {})
    if not isinstance(turbo, dict):
        return {}
    return dict(turbo)


def verify_rollback_restored(
    pre_cache_manifests: dict[str, dict[str, str]],
    prior_marketplace_stanza: dict[str, Any],
) -> None:
    if pre_cache_manifests:
        for cache_root in CACHE_ROOTS:
            actual = file_manifest(cache_root)
            expected = pre_cache_manifests.get(str(cache_root))
            if actual != expected:
                fail(
                    "rollback verification",
                    "restored cache manifest mismatch",
                    {"cache_root": str(cache_root), "expected": expected, "actual": actual},
                )
    if prior_marketplace_stanza:
        actual_stanza = current_marketplace_stanza()
        if actual_stanza != prior_marketplace_stanza:
            fail(
                "rollback verification",
                "restored marketplace stanza mismatch",
                {"expected": prior_marketplace_stanza, "actual": actual_stanza},
            )


def execute(run_id: str) -> None:
    metadata = base_run_metadata(
        run_id=run_id,
        mode="cache-refresh-execute",
        tool_path=TOOL_PATH,
    )
    verify_dry_run_prerequisites(run_id, metadata)
    evidence_root = local_only_root(run_id, "cache-refresh")
    evidence_root.mkdir(parents=True, exist_ok=True)
    backup_root = evidence_root / "cache-backup"
    failed_root = evidence_root / "failed-cache"
    config_backup = evidence_root / "config.before.toml"
    lock_path = Path(LOCK_PATH_TEMPLATE.format(run_id=run_id))
    lock_fd = atomic_lock(lock_path)
    disarmed = False
    pre_cache_manifests: dict[str, dict[str, str]] = {}
    prior_marketplace_stanza: dict[str, Any] = {}
    personal_marketplace_backup: Path | None = None
    write_json(
        EVIDENCE_ROOT / "cache-refresh-execute.start.summary.json",
        {
            "run_metadata": metadata,
            "lock_path": str(lock_path),
            "result": "CACHE_REFRESH_EXECUTE_STARTED",
        },
    )
    try:
        capture_process_check(evidence_root, metadata, "before-hooks-disable")
        prior_marketplace_stanza = current_marketplace_stanza()
        shutil.copy2(CONFIG_PATH, config_backup)
        set_plugin_hooks(False)
        shutil.copy2(CONFIG_PATH, evidence_root / "config.hooks-disabled.toml")
        capture_process_check(evidence_root, metadata, "before-cache-mutation")
        backup_cache_roots(backup_root)
        for cache_root in CACHE_ROOTS:
            pre_cache_manifests[str(cache_root)] = write_manifest_snapshot(
                cache_root,
                evidence_root / f"{cache_root.parent.name}-{cache_root.name}.before.SHA256SUMS",
                metadata,
            )
        quarantine_cache_roots(evidence_root / "preinstall-cache")
        personal_marketplace_backup = quarantine_personal_marketplace(evidence_root)
        shutil.copy2(config_backup, CONFIG_PATH)
        register_repo_marketplace(evidence_root)
        install_and_inventory(run_id, evidence_root, metadata)
        run_source_cache_gate(run_id, metadata, "pre-smoke")
        run_installed_smoke(run_id, evidence_root, metadata)
        run_source_cache_gate(run_id, metadata, "post-smoke")
        write_json(
            EVIDENCE_ROOT / "cache-refresh-execute.summary.json",
            {
                "run_metadata": metadata,
                "local_only_evidence_root": str(evidence_root),
                "backup_root": str(backup_root),
                "result": "CACHE_REFRESH_DISARMED",
            },
        )
        disarmed = True
        print("CACHE_REFRESH_DISARMED")
    except Exception as exc:
        if not disarmed:
            rollback(
                metadata=metadata,
                evidence_root=evidence_root,
                config_backup=config_backup,
                backup_root=backup_root,
                failed_root=failed_root,
                reason=str(exc),
                pre_cache_manifests=pre_cache_manifests,
                prior_marketplace_stanza=prior_marketplace_stanza,
                personal_marketplace_backup=personal_marketplace_backup,
            )
        raise
    finally:
        release_lock(lock_fd, lock_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh active Turbo Mode cache under rollback.")
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
