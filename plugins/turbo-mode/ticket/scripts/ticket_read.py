"""Shared read module for ticket query and list operations.

Used by ticket-ops (query/list commands) and ticket-triage.
Read-only — never modifies ticket files.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_parse import ParsedTicket, parse_ticket  # noqa: E402
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir  # noqa: E402
from scripts.ticket_target_schema import validate_target_ticket_file  # noqa: E402


class InvalidTicketState(ValueError):
    """Raised when an active ticket record is not target-normalized."""


def list_tickets(tickets_dir: Path) -> list[ParsedTicket]:
    """List all target-normalized tickets in the tickets directory.

    Scans docs/tickets/*.md (top level only; any closed-tickets/ subdirectory
    is intentionally not scanned). Invalid active files fail explicitly.
    Returns tickets sorted by date (newest first), then by ID.
    """
    tickets: list[ParsedTicket] = []

    if not tickets_dir.is_dir():
        return tickets

    # Scan active tickets.
    for ticket_file in tickets_dir.glob("*.md"):
        validation = validate_target_ticket_file(ticket_file)
        if not validation.ok:
            raise InvalidTicketState(validation.error)
        ticket = parse_ticket(ticket_file)
        if ticket is None:
            raise InvalidTicketState(
                "list tickets failed: a validated ticket did not parse. "
                f"Got: {str(ticket_file)!r:.100}"
            )
        tickets.append(ticket)

    # Sort: newest date first, then by ID.
    tickets.sort(key=lambda t: (t.date, t.id), reverse=True)
    return tickets


def find_ticket_by_id(
    tickets_dir: Path,
    ticket_id: str,
) -> ParsedTicket | None:
    """Find a ticket by exact ID. Returns None if not found.

    Scans active ticket files and matches on the `id` field.
    """
    all_tickets = list_tickets(tickets_dir)
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


def split_refinement_tickets(tickets: list[ParsedTicket]) -> dict[str, list[ParsedTicket]]:
    """Return target ticket groups for list payloads.

    Target tickets do not persist refinement metadata, so normal reads classify
    every valid target ticket as ready.
    """
    return {
        "needs_refinement": [],
        "ready": list(tickets),
    }


def _ticket_to_dict(ticket: ParsedTicket) -> dict:
    """Convert ParsedTicket to JSON-serializable dict."""
    from scripts.ticket_ux import humanize_state, ticket_identity

    priority_rank = {"high": "0", "normal": "1", "low": "2"}.get(ticket.priority, "9")
    status_rank = {
        "idea": "0",
        "open": "1",
        "blocked": "2",
        "done": "8",
        "wontfix": "9",
    }.get(ticket.status, "7")
    return {
        "id": ticket.id,
        "title": ticket.title,
        "date": ticket.date,
        "status": ticket.status,
        "priority": ticket.priority,
        "tags": ticket.tags,
        "blocked_by": ticket.blocked_by,
        "path": str(ticket.path),
        "related_paths": ticket.related_paths,
        "display": {
            "identity": ticket_identity(ticket),
            "status_label": humanize_state(ticket.status),
            "priority_label": humanize_state(ticket.priority),
            "sort_key": f"{status_rank}-{ticket.status}-{priority_rank}",
        },
    }


def query_tickets_payload(tickets: list[ParsedTicket], search_term: str) -> dict:
    """Return query payload with explicit ambiguity metadata."""
    matches = fuzzy_match_id(tickets, search_term)
    match_kind = "none"
    if len(matches) == 1:
        match_kind = "exact" if matches[0].id == search_term else "prefix"
    elif len(matches) > 1:
        match_kind = "ambiguous_prefix"

    payload = [_ticket_to_dict(ticket) for ticket in matches]
    for item in payload:
        item.setdefault("display", {})["match"] = {
            "query": search_term,
            "kind": match_kind,
            "candidate_count": len(matches),
        }
    return {
        "match": {
            "query": search_term,
            "kind": match_kind,
            "candidate_count": len(matches),
        },
        "tickets": payload,
    }


def list_tickets_payload(tickets: list[ParsedTicket]) -> dict:
    """Return list payload while grouping refinement placeholders separately."""
    groups = split_refinement_tickets(tickets)
    return {
        "tickets": [_ticket_to_dict(ticket) for ticket in tickets],
        "ticket_groups": {
            "ready": [_ticket_to_dict(ticket) for ticket in groups["ready"]],
            "needs_refinement": [_ticket_to_dict(ticket) for ticket in groups["needs_refinement"]],
        },
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

    query_p = subparsers.add_parser("query")
    query_p.add_argument("tickets_dir", type=Path)
    query_p.add_argument("search_term")

    check_p = subparsers.add_parser("check")
    check_p.add_argument("tickets_dir", type=Path)
    check_p.add_argument("ticket_id")
    check_p.add_argument("--resolution", default="done", choices=("done", "wontfix"))

    args = parser.parse_args()

    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        print(
            json.dumps(
                {
                    "state": "policy_blocked",
                    "message": "Cannot find project root (no .git or .codex marker in ancestors)",
                    "error_code": "policy_blocked",
                }
            )
        )
        sys.exit(1)
    tickets_dir, path_error = resolve_tickets_dir(args.tickets_dir, project_root=project_root)
    if path_error is not None or tickets_dir is None:
        print(
            json.dumps(
                {
                    "state": "policy_blocked",
                    "message": path_error or "tickets_dir validation failed",
                    "error_code": "policy_blocked",
                }
            )
        )
        sys.exit(1)

    if args.subcommand == "list":
        try:
            tickets = list_tickets(tickets_dir)
        except InvalidTicketState as exc:
            print(
                json.dumps(
                    {
                        "state": "invalid_state",
                        "message": str(exc),
                        "error_code": "invalid_state",
                    }
                )
            )
            sys.exit(1)
        tickets = filter_tickets(
            tickets,
            status=args.status,
            priority=args.priority,
            tag=args.tag,
        )
        print(
            json.dumps(
                {
                    "state": "ok",
                    "data": list_tickets_payload(tickets),
                }
            )
        )

    elif args.subcommand == "query":
        try:
            all_tickets = list_tickets(tickets_dir)
        except InvalidTicketState as exc:
            print(
                json.dumps(
                    {
                        "state": "invalid_state",
                        "message": str(exc),
                        "error_code": "invalid_state",
                    }
                )
            )
            sys.exit(1)
        payload = query_tickets_payload(all_tickets, args.search_term)
        print(
            json.dumps(
                {
                    "state": "ok",
                    "data": payload,
                }
            )
        )

    elif args.subcommand == "check":
        from scripts.ticket_ux import close_readiness

        try:
            ticket = find_ticket_by_id(tickets_dir, args.ticket_id)
        except InvalidTicketState as exc:
            print(
                json.dumps(
                    {
                        "state": "invalid_state",
                        "message": str(exc),
                        "error_code": "invalid_state",
                    }
                )
            )
            sys.exit(1)
        if ticket is None:
            print(
                json.dumps(
                    {
                        "state": "not_found",
                        "message": f"Ticket {args.ticket_id} not found",
                        "error_code": "not_found",
                        "data": {"tickets": []},
                    }
                )
            )
            sys.exit(1)
        print(
            json.dumps(
                {
                    "state": "ok",
                    "data": {
                        "ticket": _ticket_to_dict(ticket),
                        "close_readiness": close_readiness(
                            ticket,
                            tickets_dir,
                            resolution=args.resolution,
                        ),
                    },
                }
            )
        )


if __name__ == "__main__":
    main()
