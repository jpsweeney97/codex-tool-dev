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
from scripts.ticket_payloads import TicketPayloadPathError, clean_stale_payloads  # noqa: E402
from scripts.ticket_runtime_readiness import activate_runtime  # noqa: E402
from scripts.ticket_triage import DoctorInputError, ticket_doctor  # noqa: E402
from scripts.ticket_ux import attach_recovery_hint  # noqa: E402


def _response(
    state: str,
    data: dict[str, Any],
    message: str = "",
    *,
    error_code: str | None = None,
) -> dict[str, Any]:
    response = {"state": state, "message": message, "data": data}
    if error_code is not None:
        response["error_code"] = error_code
    return response


def _resolve_tickets_dir(raw_tickets_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    tickets_dir, _project_root, error = _resolve_tickets_context(raw_tickets_dir)
    return tickets_dir, error


def _resolve_tickets_context(
    raw_tickets_dir: Path,
) -> tuple[Path | None, Path | None, dict[str, Any] | None]:
    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        return (
            None,
            None,
            _response(
                "policy_blocked",
                {},
                "Cannot find project root (no .git or .codex marker in ancestors)",
            ),
        )
    tickets_dir, path_error = resolve_tickets_dir(raw_tickets_dir, project_root=project_root)
    if path_error is not None or tickets_dir is None:
        return (
            None,
            None,
            _response(
                "policy_blocked",
                {},
                path_error or "tickets_dir validation failed",
            ),
        )
    return tickets_dir, project_root, None


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


def clean_stale_payloads_payload(
    project_root: Path,
    *,
    confirm_clean_stale_payloads: bool = False,
) -> tuple[dict[str, Any], int]:
    """Delete stale prepare payloads only after explicit confirmation."""
    data: dict[str, Any] = {
        "mode": "clean-stale-payloads",
        "requires_confirmation": not confirm_clean_stale_payloads,
    }
    if not confirm_clean_stale_payloads:
        return _response(
            "policy_blocked",
            data,
            "stale payload cleanup requires --confirm-clean-stale-payloads",
        ), 1

    try:
        deleted = clean_stale_payloads(project_root)
    except TicketPayloadPathError as exc:
        return _response(
            "policy_blocked",
            {"mode": "clean-stale-payloads", "error_code": "policy_blocked"},
            str(exc),
        ), 1
    except OSError as exc:
        return _response(
            "error",
            {"mode": "clean-stale-payloads", "error_code": "io_error"},
            f"stale payload cleanup failed: {exc}",
        ), 1
    return _response(
        "ok",
        {
            "mode": "clean-stale-payloads",
            "deleted_count": len(deleted),
            "deleted": [str(item.path) for item in deleted],
        },
        "Deleted stale Ticket prepare payloads.",
    ), 0


def activate_runtime_payload(
    *,
    project_root: Path,
    tickets_dir: Path,
    marketplace_path: Path,
) -> tuple[dict[str, Any], int]:
    result = activate_runtime(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )
    if result.error_code is not None:
        response = _response(
            "policy_blocked",
            {"mode": "activate-runtime", "proof": result.proof},
            result.message,
            error_code=result.error_code,
        )
        try:
            response = attach_recovery_hint(response, result.error_code)
        except ValueError as exc:
            response["data"]["recovery_hint_error"] = str(exc)
        return response, 1
    return _response("ok", {"mode": "activate-runtime", "proof": result.proof}, result.message), 0


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

    clean_p = subparsers.add_parser("clean-stale-payloads")
    clean_p.add_argument("tickets_dir", type=Path)
    clean_p.add_argument("--confirm-clean-stale-payloads", action="store_true")

    activate_p = subparsers.add_parser("activate-runtime")
    activate_p.add_argument("tickets_dir", type=Path)
    activate_p.add_argument("--marketplace-path", type=Path, required=True)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        return 1

    if args.subcommand == "repair-audit" and args.fix:
        parser.error("audit repair mutation requires --confirm-repair, not --fix")

    tickets_dir, project_root, error = _resolve_tickets_context(args.tickets_dir)
    if error is not None or tickets_dir is None or project_root is None:
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
                json.dumps(_response("escalate", {"error_code": "invalid_doctor_root"}, str(exc)))
            )
            return 1
        response = _response("ok", payload)
        if response["data"]["report"]["payloads"]["stale_count"] > 0:
            response = attach_recovery_hint(response, "cleanup_stale_preview")
        print(json.dumps(response))
        return 0

    if args.subcommand == "repair-audit":
        response, exit_code = repair_audit_payload(
            tickets_dir,
            confirm_repair=args.confirm_repair,
        )
        print(json.dumps(response))
        return exit_code

    if args.subcommand == "clean-stale-payloads":
        response, exit_code = clean_stale_payloads_payload(
            project_root,
            confirm_clean_stale_payloads=args.confirm_clean_stale_payloads,
        )
        print(json.dumps(response))
        return exit_code

    if args.subcommand == "activate-runtime":
        response, exit_code = activate_runtime_payload(
            project_root=project_root,
            tickets_dir=tickets_dir,
            marketplace_path=args.marketplace_path,
        )
        print(json.dumps(response))
        return exit_code

    parser.print_usage(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
