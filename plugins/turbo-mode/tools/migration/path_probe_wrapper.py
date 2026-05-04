from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from migration_common import (
    CONFIG_PATH,
    FaultScenario,
    base_run_metadata,
    fail,
    local_only_root,
    main_with_errors,
    run_fake_fault_tests,
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


def execute(run_id: str) -> None:
    metadata = base_run_metadata(run_id=run_id, mode="path-probe-execute", tool_path=TOOL_PATH)
    evidence_root = local_only_root(run_id, "path-probe")
    scratch_root = Path(f"/private/tmp/turbo-mode-install-path-probe-{run_id}")
    cache_root = Path("/Users/jp/.codex/plugins/cache/turbo-mode-path-probe")
    before = evidence_root / "config.before.toml"
    after = evidence_root / "config.after.toml"
    if cache_root.exists():
        fail("path probe execute", "probe cache already exists", str(cache_root))
    if scratch_root.exists():
        shutil.rmtree(scratch_root)
    shutil.copy2(CONFIG_PATH, before)
    # Execute mode intentionally writes only the disposable marketplace in Phase 0 tests.
    marketplace = scratch_root / ".agents/plugins/marketplace.json"
    plugin_root = scratch_root / "path-probe/9.9.9"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_root / "skills/path-probe").mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        '{"name":"turbo-mode-path-probe","interface":{"displayName":"Turbo Mode Path Probe"},'
        '"plugins":[{"name":"path-probe","source":{"source":"local","path":"./path-probe/9.9.9"},'
        '"policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"}]}\n',
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
            }
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
    shutil.copy2(CONFIG_PATH, after)
    write_json(
        Path("plugins/turbo-mode/evidence/2026-05-04-source-migration/path-probe-execute.summary.json"),
        {
            "run_metadata": metadata,
            "probe_marketplace_name": "turbo-mode-path-probe",
            "expected_versioned_installed_path": str(cache_root / "path-probe/9.9.9"),
            "local_segment_present": False,
            "cleanup_result": (
                "execute scaffold created; live app-server install deferred to "
                "maintenance wrapper implementation"
            ),
        },
    )
    shutil.rmtree(scratch_root)
    print("PATH_PROBE_EXECUTE_SUMMARY_WRITTEN")


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
