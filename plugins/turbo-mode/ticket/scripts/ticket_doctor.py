#!/usr/bin/env python3
"""Explicit-only ticket maintenance wrapper for diagnostics and audit repair."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_audit import repair_audit_logs  # noqa: E402
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir  # noqa: E402
from scripts.ticket_triage import DoctorInputError, ticket_doctor  # noqa: E402


def _response(state: str, data: dict[str, Any], message: str = "") -> dict[str, Any]:
    return {"state": state, "message": message, "data": data}


def _resolve_tickets_dir(raw_tickets_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        return None, _response(
            "policy_blocked",
            {},
            "Cannot find project root (no .git or .codex marker in ancestors)",
        )
    tickets_dir, path_error = resolve_tickets_dir(raw_tickets_dir, project_root=project_root)
    if path_error is not None or tickets_dir is None:
        return None, _response("policy_blocked", {}, path_error or "tickets_dir validation failed")
    return tickets_dir, None


def diagnose_payload(
    tickets_dir: Path,
    *,
    plugin_root: Path,
    cache_root: Path,
    runtime_probe_output: Path | None = None,
) -> dict[str, Any]:
    """Return read-only ticket doctor diagnostics."""
    return {
        "mode": "diagnose",
        "read_only": True,
        "report": ticket_doctor(
            tickets_dir,
            plugin_root=plugin_root,
            cache_root=cache_root,
            runtime_probe_output=runtime_probe_output,
        ),
    }


def repair_audit_payload(
    tickets_dir: Path,
    *,
    confirm_repair: bool = False,
) -> tuple[dict[str, Any], int]:
    """Dry-run audit repair first and mutate only with explicit confirmation."""
    dry_run_response, dry_run_exit = repair_audit_logs(tickets_dir=tickets_dir, dry_run=True)
    data: dict[str, Any] = {
        "mode": "repair-audit",
        "dry_run": dry_run_response,
        "repair": None,
        "requires_confirmation": False,
    }
    if dry_run_exit != 0:
        return _response("error", data, dry_run_response["message"]), dry_run_exit

    corrupt_files = dry_run_response["data"]["corrupt_files"]
    if corrupt_files == 0:
        return _response("ok", data, dry_run_response["message"]), 0

    if not confirm_repair:
        data["requires_confirmation"] = True
        return _response(
            "ok",
            data,
            "Dry run found audit corruption; rerun with --confirm-repair to mutate.",
        ), 0

    repair_response, repair_exit = repair_audit_logs(tickets_dir=tickets_dir, dry_run=False)
    data["repair"] = repair_response
    state = "ok" if repair_exit == 0 else "error"
    return _response(state, data, repair_response["message"]), repair_exit


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Explicit Ticket doctor operations")
    subparsers = parser.add_subparsers(dest="subcommand")

    diagnose_p = subparsers.add_parser("diagnose")
    diagnose_p.add_argument("tickets_dir", type=Path)
    diagnose_p.add_argument("--plugin-root", type=Path, required=True)
    diagnose_p.add_argument("--cache-root", type=Path, required=True)
    diagnose_p.add_argument("--runtime-probe-output", type=Path, default=None)

    repair_p = subparsers.add_parser("repair-audit")
    repair_p.add_argument("tickets_dir", type=Path)
    repair_p.add_argument("--confirm-repair", action="store_true")
    repair_p.add_argument("--fix", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        return 1

    if args.subcommand == "repair-audit" and args.fix:
        parser.error("audit repair mutation requires --confirm-repair, not --fix")

    tickets_dir, error = _resolve_tickets_dir(args.tickets_dir)
    if error is not None or tickets_dir is None:
        print(json.dumps(error))
        return 1

    if args.subcommand == "diagnose":
        try:
            payload = diagnose_payload(
                tickets_dir,
                plugin_root=args.plugin_root,
                cache_root=args.cache_root,
                runtime_probe_output=args.runtime_probe_output,
            )
        except DoctorInputError as exc:
            print(
                json.dumps(
                    _response("escalate", {"error_code": "invalid_doctor_root"}, str(exc))
                )
            )
            return 1
        print(json.dumps(_response("ok", payload)))
        return 0

    if args.subcommand == "repair-audit":
        response, exit_code = repair_audit_payload(
            tickets_dir,
            confirm_repair=args.confirm_repair,
        )
        print(json.dumps(response))
        return exit_code

    parser.print_usage(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
