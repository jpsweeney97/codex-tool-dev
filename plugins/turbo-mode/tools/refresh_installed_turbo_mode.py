#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.evidence import evidence_payload, write_local_evidence  # noqa: E402
from refresh.models import RefreshError  # noqa: E402
from refresh.planner import plan_refresh  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess Turbo Mode installed-cache drift without mutation."
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--plan-refresh", action="store_true")
    modes.add_argument("--refresh", action="store_true")
    modes.add_argument("--guarded-refresh", action="store_true")
    parser.add_argument("--smoke", choices=("light", "standard"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--run-id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--inventory-check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh or args.guarded_refresh:
        parser.error("--refresh and --guarded-refresh are outside Plan 03")
    if args.smoke is not None:
        parser.error("--smoke is only accepted with rejected future command shapes")
    mode = "plan-refresh" if args.plan_refresh else "dry-run"
    run_id = args.run_id or uuid.uuid4().hex
    try:
        result = plan_refresh(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            mode=mode,
            inventory_check=args.inventory_check,
        )
        evidence_path = write_local_evidence(result, run_id=run_id)
    except (RefreshError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = evidence_payload(result, run_id=run_id)
    payload["evidence_path"] = str(evidence_path)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode: {mode}")
        print(f"terminal_plan_status: {result.terminal_status.value}")
        print(f"evidence_path: {evidence_path}")
        print(f"app_server_inventory_status: {result.app_server_inventory_status}")
        if result.app_server_inventory_failure_reason is not None:
            print(
                "app_server_inventory_failure_reason: "
                f"{result.app_server_inventory_failure_reason}"
            )
        if result.app_server_inventory is not None:
            print(f"app_server_inventory: {result.app_server_inventory.state}")
        print(f"mutation_command_available: {str(result.mutation_command_available).lower()}")
        if result.future_external_command is not None:
            print(f"future_external_command: {result.future_external_command}")
            print(f"requires_plan: {result.requires_plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
