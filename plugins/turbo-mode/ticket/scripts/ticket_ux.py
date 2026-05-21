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

RECOVERY_HINTS: dict[str, dict[str, str]] = {
    "stale_plan": {
        "summary": "The saved preview is no longer current.",
        "next_step": "Rerun the preview, review the updated result, then confirm again.",
    },
    "trust_setup": {
        "summary": "Ticket setup needs attention before this write can continue.",
        "next_step": (
            "Stop without writing. Run ticket-doctor diagnostics or verify the plugin "
            "hook setup before retrying."
        ),
    },
    "retry_preview": {
        "summary": "The saved preview state is no longer usable.",
        "next_step": "Rerun the preview and confirm again before writing.",
    },
    "cleanup_stale_preview": {
        "summary": "Old abandoned Ticket preview state can be cleaned up after review.",
        "next_step": "Use ticket-doctor stale cleanup after reviewing the reported items.",
    },
    "policy_blocked": {
        "summary": "This write is blocked by Ticket policy.",
        "next_step": "Keep the ticket unchanged and adjust the request or policy before retrying.",
    },
    "preflight_failed": {
        "summary": "Ticket checks did not pass.",
        "next_step": "Review the preview or check details, update the request, then rerun preview.",
    },
    "host_policy_blocked": {
        "summary": "The host refused the contained Ticket runtime activation turn.",
        "next_step": "Retry activation on a host that allows the pinned workspaceWrite policy.",
    },
    "deterministic_driver_unavailable": {
        "summary": "Ticket could not capture a deterministic runtime activation transcript.",
        "next_step": "Repair the app-server command-driving path before retrying activation.",
    },
    "hook_contract_blocked": {
        "summary": "The installed Ticket hook contract is still blocking runtime activation.",
        "next_step": "Refresh or repair the installed Ticket runtime before retrying activation.",
    },
    "engine_gate_required": {
        "summary": (
            "Ticket runtime activation cannot finish until the direct-execute "
            "engine gate is present."
        ),
        "next_step": (
            "Update to a build with the direct-execute runtime gate, then rerun activation."
        ),
    },
    "runtime_readiness_required": {
        "summary": "Ticket runtime activation is required before this direct execute can continue.",
        "next_step": (
            "Run the explicit activate-runtime flow or refresh the installed Ticket runtime "
            "before retrying."
        ),
    },
}

INTERNAL_RECOVERY_TERMS = (
    "hook_injected",
    "hook_request_origin",
    "request_origin",
    "origin_mismatch",
    "verified hook provenance",
    "payload",
    "payload path",
    "payload_file",
    "envelope_path",
    "processed_path",
    "incoming_envelope_path",
    "ticket_path",
    "envelope_move_error",
    "PAYLOAD_PATH",
    "canonical command",
    "python3 -B",
    "uv run python -B",
)

INTERNAL_RECOVERY_PATH_PATTERNS = (
    r"(?<![A-Za-z0-9_.-])/(?:Users|home|workspace|workspaces|private|tmp|var)/",
    r"[A-Za-z]:\\",
)


def recovery_hint(code: str) -> dict[str, str]:
    """Return a transcript-safe recovery hint for a known recovery code."""
    try:
        hint = RECOVERY_HINTS[code]
    except KeyError as exc:
        raise ValueError(f"unknown recovery hint code: {code!r}") from exc
    return {"code": code, **hint}


def attach_recovery_hint(response: dict[str, Any], code: str) -> dict[str, Any]:
    """Return response with a transcript-safe recovery hint in data."""
    updated = dict(response)
    data = dict(updated.get("data") or {})
    data["recovery_hint"] = recovery_hint(code)
    updated["data"] = data
    return updated


def attach_engine_recovery_hint(response: Any, code: str) -> Any:
    """Attach a transcript-safe recovery hint to an EngineResponse-like object."""
    data = dict(getattr(response, "data", {}) or {})
    data["recovery_hint"] = recovery_hint(code)
    response.data = data
    return response


def recovery_hint_code_for_response(response: dict[str, Any]) -> str | None:
    """Choose the default user-facing recovery code for a response dict."""
    data = response.get("data")
    if isinstance(data, dict) and "recovery_hint" in data:
        return None
    if response.get("error_code") == "stale_plan":
        return "stale_plan"
    if response.get("error_code") == "parse_error":
        return "retry_preview"
    if response.get("error_code") == "origin_mismatch":
        return "trust_setup"
    if response.get("error_code") == "host_policy_blocked":
        return "host_policy_blocked"
    if response.get("error_code") == "deterministic_driver_unavailable":
        return "deterministic_driver_unavailable"
    if response.get("error_code") == "hook_contract_blocked":
        return "hook_contract_blocked"
    if response.get("error_code") == "engine_gate_required":
        return "engine_gate_required"
    if response.get("error_code") == "runtime_readiness_required":
        return "runtime_readiness_required"
    if response.get("state") == "policy_blocked":
        return "policy_blocked"
    if response.get("state") == "preflight_failed":
        return "preflight_failed"
    return None


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
