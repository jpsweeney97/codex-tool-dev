"""User-facing ticket UX helpers.

This module contains pure formatting and guidance helpers. It does not mutate
ticket files and does not bypass the ticket engine or guard hook.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


STATE_LABELS = {
    "ok": "Ready",
    "ok_create": "Ticket created",
    "ok_update": "Ticket updated",
    "ok_close": "Ticket closed",
    "ok_close_archived": "Ticket closed and archived",
    "ok_reopen": "Ticket reopened",
    "need_fields": "More information needed",
    "duplicate_candidate": "Potential duplicate found",
    "preflight_failed": "Preflight check failed",
    "policy_blocked": "Blocked by ticket policy",
    "invalid_transition": "Status change is not allowed",
    "dependency_blocked": "Blocking tickets are unresolved",
    "not_found": "Ticket not found",
    "escalate": "Manual review required",
    "target_fingerprint": "Ticket changed since preview",
    "dedup_override": "Create anyway",
    "dependency_override": "Ignore blockers for this operation",
}


def humanize_state(value: str) -> str:
    """Return a user-facing label for an engine state or internal term."""
    return STATE_LABELS.get(value, value.replace("_", " ").capitalize())


def ticket_identity(ticket: Any) -> dict[str, str]:
    """Return the stable user-facing identity for a parsed ticket."""
    path = Path(ticket.path)
    return {
        "id": str(ticket.id),
        "title": str(ticket.title),
        "path": str(path),
        "filename": path.name,
    }


def close_readiness(ticket: Any, tickets_dir: Path, *, resolution: str = "done") -> dict[str, Any]:
    """Report whether a ticket can close with the requested resolution."""
    from scripts.ticket_engine_core import engine_close_readiness

    response = engine_close_readiness(ticket, tickets_dir, resolution=resolution)
    data = dict(response.data or {})
    data.setdefault("ready", response.state == "ok")
    data.setdefault("error_code", response.error_code)
    data.setdefault("message", response.message)
    return data
