#!/usr/bin/env python3
"""Read-only ticket review wrapper around triage dashboard and audit reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_paths import discover_project_root, resolve_tickets_dir  # noqa: E402
from scripts.ticket_triage import triage_audit_report, triage_dashboard  # noqa: E402


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


def review_payload(tickets_dir: Path) -> dict[str, Any]:
    """Return read-only backlog review data from the triage dashboard."""
    dashboard = triage_dashboard(tickets_dir)
    return {
        "backend": "ticket_triage.dashboard",
        **dashboard,
    }


def audit_payload(tickets_dir: Path, *, days: int = 7) -> dict[str, Any]:
    """Return read-only audit summary data from ticket triage."""
    return {
        "backend": "ticket_triage.audit",
        "audit": triage_audit_report(tickets_dir, days=days),
    }


def hygiene_candidates_from_review(payload: dict[str, Any]) -> dict[str, Any]:
    """Build discussion-gated hygiene candidates from read-only review data."""
    findings: list[dict[str, Any]] = []
    stale = payload.get("stale", [])
    if isinstance(stale, list):
        for item in stale:
            if not isinstance(item, dict):
                continue
            ticket_id = item.get("id")
            if not isinstance(ticket_id, str) or not ticket_id:
                continue
            findings.append(
                {
                    "ticket_id": ticket_id,
                    "action": "stale_cleanup",
                    "reason": "Ticket review found a stale active ticket.",
                }
            )
    return {"state": "ok", "review_hygiene_findings": findings}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ticket review operations")
    subparsers = parser.add_subparsers(dest="subcommand")

    review_p = subparsers.add_parser("review")
    review_p.add_argument("tickets_dir", type=Path)

    audit_p = subparsers.add_parser("audit")
    audit_p.add_argument("tickets_dir", type=Path)
    audit_p.add_argument("--days", type=int, default=7)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        return 1

    tickets_dir, error = _resolve_tickets_dir(args.tickets_dir)
    if error is not None or tickets_dir is None:
        print(json.dumps(error))
        return 1

    if args.subcommand == "review":
        print(json.dumps(_response("ok", review_payload(tickets_dir))))
        return 0

    if args.subcommand == "audit":
        print(json.dumps(_response("ok", audit_payload(tickets_dir, days=args.days))))
        return 0

    parser.print_usage(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
