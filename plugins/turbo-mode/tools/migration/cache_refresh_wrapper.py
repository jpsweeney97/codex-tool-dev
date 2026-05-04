from __future__ import annotations

import argparse
from pathlib import Path

from migration_common import (
    CACHE_ROOTS,
    CONFIG_PATH,
    MARKETPLACE_PATH,
    FaultScenario,
    base_run_metadata,
    fail,
    local_only_root,
    main_with_errors,
    run_fake_fault_tests,
    write_json,
)

TOOL_PATH = "plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py"

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
        Path("plugins/turbo-mode/evidence/2026-05-04-source-migration/cache-refresh-fault-test.summary.json"),
        {"run_metadata": metadata, **result, "result": "CACHE_REFRESH_FAULT_TESTS_PASSED"},
    )
    print("CACHE_REFRESH_FAULT_TESTS_PASSED")


def dry_run(run_id: str) -> None:
    metadata = base_run_metadata(run_id=run_id, mode="cache-refresh-dry-run", tool_path=TOOL_PATH)
    if not CONFIG_PATH.is_file():
        fail("cache refresh dry run", "config file missing", str(CONFIG_PATH))
    if not MARKETPLACE_PATH.is_file():
        fail("cache refresh dry run", "repo marketplace missing", str(MARKETPLACE_PATH))
    missing_cache = [str(path) for path in CACHE_ROOTS if not path.exists()]
    if missing_cache:
        fail("cache refresh dry run", "active cache roots missing", missing_cache)
    evidence_root = local_only_root(run_id, "cache-refresh")
    backup_root = evidence_root / "cache-backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    write_json(
        Path("plugins/turbo-mode/evidence/2026-05-04-source-migration/cache-refresh-dry-run.summary.json"),
        {
            "run_metadata": metadata,
            "local_only_evidence_root": str(evidence_root),
            "backup_root": str(backup_root),
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


def execute(run_id: str) -> None:
    metadata = base_run_metadata(
        run_id=run_id,
        mode="cache-refresh-execute-blocked",
        tool_path=TOOL_PATH,
    )
    write_json(
        Path("plugins/turbo-mode/evidence/2026-05-04-source-migration/cache-refresh-execute.blocked.summary.json"),
        {
            "run_metadata": metadata,
            "blocked": True,
            "reason": (
                "execute mode requires an external no-concurrent-hook-consumer "
                "maintenance window"
            ),
        },
    )
    fail(
        "cache refresh execute",
        "external maintenance-window execution is required before active cache mutation",
        run_id,
    )


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
