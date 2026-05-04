"""Ticket triage — read-only analysis of ticket health and audit activity."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_paths import discover_project_root, resolve_tickets_dir

_TERMINAL_STATUSES = frozenset({"done", "wontfix"})

# Ticket ID patterns for id_ref matching.
_TICKET_ID_PATTERNS = [
    re.compile(r"T-\d{8}-\d{2,}"),  # v1.0: T-YYYYMMDD-NN
    re.compile(r"T-\d{3}"),          # Gen 3: T-NNN
    re.compile(r"T-[A-F]"),          # Gen 2: T-X
]


def triage_dashboard(tickets_dir: Path) -> dict[str, Any]:
    """Generate a triage dashboard with ticket counts and alerts.

    Filters to non-terminal statuses (excludes done/wontfix).
    list_tickets(include_closed=False) returns all tickets in the active
    directory regardless of status field — filtering by status is our job.
    Returns dict with: counts, total, stale, blocked_chains, size_warnings.
    """
    from scripts.ticket_read import list_tickets

    all_tickets = list_tickets(tickets_dir, include_closed=False)
    # Filter to actionable tickets (non-terminal status).
    tickets = [t for t in all_tickets if t.status not in _TERMINAL_STATUSES]
    ticket_map = {t.id: t for t in tickets}

    counts: dict[str, int] = {"open": 0, "in_progress": 0, "blocked": 0}
    stale: list[dict[str, str]] = []
    blocked_chains: list[dict[str, Any]] = []
    size_warnings: list[dict[str, str]] = []

    for ticket in tickets:
        if ticket.status in counts:
            counts[ticket.status] += 1

        if _is_stale(ticket):
            stale.append({
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status,
                "date": ticket.date,
            })

        if ticket.status == "blocked" and ticket.blocked_by:
            root_blockers = _find_root_blockers(ticket, ticket_map)
            blocked_chains.append({
                "id": ticket.id,
                "title": ticket.title,
                "root_blockers": root_blockers,
            })

        warning = _check_doc_size(ticket)
        if warning:
            size_warnings.append({"id": ticket.id, "title": ticket.title, "warning": warning})

    return {
        "counts": counts,
        "total": len(tickets),
        "stale": stale,
        "blocked_chains": blocked_chains,
        "size_warnings": size_warnings,
    }


def _is_stale(ticket: Any, cutoff_days: int = 7) -> bool:
    """Check if ticket is stale (open/in_progress >7 days by ticket date).

    Returns True for unparseable dates (fail toward visibility).
    """
    if ticket.status not in ("open", "in_progress"):
        return False
    try:
        ticket_date = datetime.strptime(ticket.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ticket_date).days > cutoff_days
    except ValueError:
        return True


def _find_root_blockers(ticket: Any, ticket_map: dict[str, Any]) -> list[str]:
    """Follow blocked_by chains to find root blockers."""
    visited: set[str] = set()
    roots: list[str] = []

    def _walk(tid: str) -> None:
        if tid in visited:
            return
        visited.add(tid)
        t = ticket_map.get(tid)
        if t is None or not t.blocked_by:
            roots.append(tid)
            return
        for bid in t.blocked_by:
            _walk(bid)

    for bid in ticket.blocked_by:
        _walk(bid)
    return roots


def _check_doc_size(ticket: Any) -> str | None:
    """Check ticket document size, return warning string if large or unreadable."""
    try:
        size = Path(ticket.path).stat().st_size
    except OSError:
        return "error: file unreadable"
    if size >= 32768:
        return f"strong_warn: {size // 1024}KB (>32KB)"
    if size >= 16384:
        return f"warn: {size // 1024}KB (>16KB)"
    return None


def triage_audit_report(tickets_dir: Path, days: int = 7) -> dict[str, Any]:
    """Summarize recent autonomous actions from audit trail.

    Reads .audit/YYYY-MM-DD/<session_id>.jsonl files within the lookback window.
    Returns dict with: total_entries, by_action, by_result, sessions,
    skipped_lines, read_errors.
    """
    audit_base = tickets_dir / ".audit"
    if not audit_base.is_dir():
        return {"total_entries": 0, "by_action": {}, "by_result": {}, "sessions": 0,
                "skipped_lines": 0, "read_errors": 0}

    now = datetime.now(timezone.utc)
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    entries: list[dict[str, Any]] = []
    session_ids: set[str] = set()
    skipped_lines = 0
    read_errors = 0

    for date_dir in sorted(audit_base.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dir_date < cutoff:
            continue
        for jsonl_file in date_dir.glob("*.jsonl"):
            session_ids.add(jsonl_file.stem)
            try:
                for line in jsonl_file.read_text(encoding="utf-8").strip().split("\n"):
                    if not line.strip():
                        continue
                    try:
                        entries.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        skipped_lines += 1
            except OSError:
                read_errors += 1

    by_action: dict[str, int] = {}
    by_result: dict[str, int] = {}
    for entry in entries:
        action = entry.get("action", "unknown")
        by_action[action] = by_action.get(action, 0) + 1
        result = entry.get("result")
        if result is not None:
            by_result[str(result)] = by_result.get(str(result), 0) + 1

    return {
        "total_entries": len(entries),
        "by_action": by_action,
        "by_result": by_result,
        "sessions": len(session_ids),
        "skipped_lines": skipped_lines,
        "read_errors": read_errors,
    }


def triage_orphan_detection(
    tickets_dir: Path,
    handoffs_dir: Path,
) -> dict[str, Any]:
    """Detect orphaned handoff items not linked to any ticket.

    Three matching strategies (ported from handoff triage.py):
    1. uid_match: handoff text contains ticket's source.session
    2. id_ref: handoff text contains a ticket ID
    3. manual_review: no deterministic match
    """
    from scripts.ticket_read import list_tickets

    tickets = list_tickets(tickets_dir, include_closed=True)
    ticket_ids = {t.id for t in tickets}
    session_map: dict[str, str] = {}  # session_id -> ticket_id
    for t in tickets:
        sid = t.source.get("session", "")
        if sid:
            session_map[sid] = t.id

    matched: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []
    read_errors: list[str] = []

    if not handoffs_dir.is_dir():
        return {"matched": matched, "orphaned": orphaned, "total_items": 0, "read_errors": read_errors}

    for hf in sorted(handoffs_dir.glob("*.md")):
        try:
            text = hf.read_text(encoding="utf-8")
        except OSError:
            read_errors.append(hf.name)
            continue

        item: dict[str, str] = {"file": hf.name, "path": str(hf)}
        match_found = False

        # Strategy 1: uid_match -- session ID in handoff text.
        for sid, tid in session_map.items():
            if sid in text:
                matched.append({"match_type": "uid_match", "matched_ticket": tid, "item": item})
                match_found = True
                break

        if match_found:
            continue

        # Strategy 2: id_ref -- ticket ID referenced in handoff text.
        for pattern in _TICKET_ID_PATTERNS:
            refs = pattern.findall(text)
            for ref in refs:
                if ref in ticket_ids:
                    matched.append({"match_type": "id_ref", "matched_ticket": ref, "item": item})
                    match_found = True
                    break
            if match_found:
                break

        if match_found:
            continue

        # Strategy 3: manual_review -- no deterministic match.
        orphaned.append({"match_type": "manual_review", "matched_ticket": None, "item": item})

    return {
        "matched": matched,
        "orphaned": orphaned,
        "total_items": len(matched) + len(orphaned),
        "read_errors": read_errors,
    }


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Ticket triage operations")
    subparsers = parser.add_subparsers(dest="subcommand")

    dash_p = subparsers.add_parser("dashboard")
    dash_p.add_argument("tickets_dir", type=Path)

    audit_p = subparsers.add_parser("audit")
    audit_p.add_argument("tickets_dir", type=Path)
    audit_p.add_argument("--days", type=int, default=7)

    args = parser.parse_args()

    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        print(json.dumps({
            "state": "policy_blocked",
            "message": "Cannot find project root (no .git or .codex marker in ancestors)",
            "error_code": "policy_blocked",
        }))
        sys.exit(1)
    tickets_dir, path_error = resolve_tickets_dir(args.tickets_dir, project_root=project_root)
    if path_error is not None or tickets_dir is None:
        print(json.dumps({
            "state": "policy_blocked",
            "message": path_error or "tickets_dir validation failed",
            "error_code": "policy_blocked",
        }))
        sys.exit(1)

    if args.subcommand == "dashboard":
        result = triage_dashboard(tickets_dir)
        print(json.dumps({"state": "ok", "data": result}))

    elif args.subcommand == "audit":
        result = triage_audit_report(tickets_dir, days=args.days)
        print(json.dumps({"state": "ok", "data": result}))


if __name__ == "__main__":
    main()
