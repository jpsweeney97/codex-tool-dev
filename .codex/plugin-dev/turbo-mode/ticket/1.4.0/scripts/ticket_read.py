"""Shared read module for ticket query and list operations.

Used by ticket-ops (query/list commands) and ticket-triage.
Read-only — never modifies ticket files.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_paths import discover_project_root, resolve_tickets_dir
from scripts.ticket_parse import ParsedTicket, parse_ticket


def list_tickets(
    tickets_dir: Path,
    *,
    include_closed: bool = False,
) -> list[ParsedTicket]:
    """List all parseable tickets in the tickets directory.

    Scans docs/tickets/*.md. If include_closed=True, also scans
    docs/tickets/closed-tickets/*.md. Skips unparseable files silently.
    Returns tickets sorted by date (newest first), then by ID.
    """
    tickets: list[ParsedTicket] = []

    if not tickets_dir.is_dir():
        return tickets

    # Scan active tickets.
    for ticket_file in tickets_dir.glob("*.md"):
        ticket = parse_ticket(ticket_file)
        if ticket is not None:
            tickets.append(ticket)

    # Scan closed tickets if requested.
    if include_closed:
        closed_dir = tickets_dir / "closed-tickets"
        if closed_dir.is_dir():
            for ticket_file in closed_dir.glob("*.md"):
                ticket = parse_ticket(ticket_file)
                if ticket is not None:
                    tickets.append(ticket)

    # Sort: newest date first, then by ID.
    tickets.sort(key=lambda t: (t.date, t.id), reverse=True)
    return tickets


def find_ticket_by_id(
    tickets_dir: Path,
    ticket_id: str,
    *,
    include_closed: bool = True,
) -> ParsedTicket | None:
    """Find a ticket by exact ID. Returns None if not found.

    Scans all ticket files (including closed) and matches on the `id` field.
    """
    all_tickets = list_tickets(tickets_dir, include_closed=include_closed)
    for ticket in all_tickets:
        if ticket.id == ticket_id:
            return ticket
    return None


def filter_tickets(
    tickets: list[ParsedTicket],
    *,
    status: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
) -> list[ParsedTicket]:
    """Filter a list of tickets by criteria. All criteria are AND-combined."""
    result = tickets
    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    if tag is not None:
        result = [t for t in result if tag in t.tags]
    return result


def fuzzy_match_id(
    tickets: list[ParsedTicket],
    partial_id: str,
) -> list[ParsedTicket]:
    """Find tickets whose ID starts with the given prefix."""
    return [t for t in tickets if t.id.startswith(partial_id)]


def _ticket_to_dict(ticket: ParsedTicket) -> dict:
    """Convert ParsedTicket to JSON-serializable dict.
    """
    return {
        "id": ticket.id,
        "title": ticket.title,
        "date": ticket.date,
        "status": ticket.status,
        "priority": ticket.priority,
        "tags": ticket.tags,
        "blocked_by": ticket.blocked_by,
        "blocks": ticket.blocks,
        "path": str(ticket.path),
    }


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Ticket read operations")
    subparsers = parser.add_subparsers(dest="subcommand")

    list_p = subparsers.add_parser("list")
    list_p.add_argument("tickets_dir", type=Path)
    list_p.add_argument("--status", default=None)
    list_p.add_argument("--priority", default=None)
    list_p.add_argument("--tag", default=None)
    list_p.add_argument("--include-closed", action="store_true")

    query_p = subparsers.add_parser("query")
    query_p.add_argument("tickets_dir", type=Path)
    query_p.add_argument("search_term")

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

    if args.subcommand == "list":
        tickets = list_tickets(tickets_dir, include_closed=args.include_closed)
        tickets = filter_tickets(
            tickets, status=args.status, priority=args.priority, tag=args.tag,
        )
        print(json.dumps({
            "state": "ok",
            "data": {"tickets": [_ticket_to_dict(t) for t in tickets]},
        }))

    elif args.subcommand == "query":
        all_tickets = list_tickets(tickets_dir, include_closed=True)
        matches = fuzzy_match_id(all_tickets, args.search_term)
        print(json.dumps({
            "state": "ok",
            "data": {"tickets": [_ticket_to_dict(t) for t in matches]},
        }))


if __name__ == "__main__":
    main()
