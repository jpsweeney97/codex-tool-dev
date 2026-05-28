"""Deterministic IDs and fingerprints for runtime-first Ticket autonomy."""

from __future__ import annotations

import hashlib
import json
import math


def _value_error(operation: str, reason: str, value: object) -> ValueError:
    return ValueError(f"{operation} failed: {reason}. Got: {value!r:.100}")


def _normalize_for_json(value: object, *, operation: str) -> object:
    if value is None or isinstance(value, bool | int | str):
        if isinstance(value, str):
            return value.replace("\\", "/")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _value_error(operation, "non-finite float is unsupported", value)
        return value
    if isinstance(value, list | tuple):
        return [_normalize_for_json(item, operation=operation) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _value_error(operation, "object keys must be strings", value)
            normalized[key] = _normalize_for_json(item, operation=operation)
        return normalized
    raise _value_error(operation, "unsupported canonical input", value)


def canonical_json(value: object) -> str:
    """Render a JSON-compatible value in canonical form.

    Args:
        value: JSON-compatible value to normalize and serialize.

    Returns:
        Sorted-key, compact-separator JSON with ASCII escapes.

    Raises:
        ValueError: If the value cannot be represented canonically.
    """
    operation = "canonical json"
    normalized = _normalize_for_json(value, operation=operation)
    try:
        return json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    except (TypeError, ValueError) as exc:
        raise _value_error(operation, str(exc), value) from exc


def sha256_fingerprint(value: object) -> str:
    """Hash a canonical JSON value with SHA-256.

    Args:
        value: JSON-compatible value to canonicalize before hashing.

    Returns:
        Lowercase 64-character SHA-256 hex digest.
    """
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _short_prefixed_id(prefix: str, payload: dict[str, object]) -> str:
    digest = sha256_fingerprint(payload)[:32]
    return f"{prefix}_{digest}"


def make_mutation_id(
    *,
    schema: str,
    thread_id: str,
    turn_id: str,
    action: str,
    ticket_id: str | None,
    mutation_fingerprint: str,
    evidence_fingerprint: str,
) -> str:
    """Build a deterministic mutation ID.

    Args:
        schema: Mutation schema identifier.
        thread_id: Codex thread identifier.
        turn_id: Turn identifier within the thread.
        action: Ticket mutation action.
        ticket_id: Target ticket ID, or `None` for create previews.
        mutation_fingerprint: Canonical mutation payload fingerprint.
        evidence_fingerprint: Evidence payload fingerprint.

    Returns:
        `mut_` plus the first 32 hex characters of the payload digest.
    """
    return _short_prefixed_id(
        "mut",
        {
            "schema": schema,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "action": action,
            "ticket_id": ticket_id,
            "mutation_fingerprint": mutation_fingerprint,
            "evidence_fingerprint": evidence_fingerprint,
        },
    )


def make_event_id(
    *,
    schema: str,
    event_type: str,
    thread_id: str,
    turn_id: str,
    mutation_id: str | None,
    status: str,
    action: str,
    ticket_id: str | None,
    payload_fingerprint: str,
) -> str:
    """Build a deterministic pending-summary event ID.

    Args:
        schema: Event schema identifier.
        event_type: Event type.
        thread_id: Codex thread identifier.
        turn_id: Turn identifier within the thread.
        mutation_id: Related mutation ID, when present.
        status: Event status.
        action: Ticket action.
        ticket_id: Target ticket ID, when present.
        payload_fingerprint: Event payload fingerprint excluding ID/timestamp.

    Returns:
        `evt_` plus the first 32 hex characters of the payload digest.
    """
    return _short_prefixed_id(
        "evt",
        {
            "schema": schema,
            "event_type": event_type,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "mutation_id": mutation_id,
            "status": status,
            "action": action,
            "ticket_id": ticket_id,
            "payload_fingerprint": payload_fingerprint,
        },
    )


def make_approval_id(
    *,
    schema: str,
    thread_id: str,
    ticket_id: str,
    mutation_id: str,
    mutation_fingerprint: str,
    ticket_state_fingerprint: str,
    evidence_fingerprint: str,
    current_mode: str,
    decision: str,
) -> str:
    """Build a deterministic approval ID.

    Args:
        schema: Approval schema identifier.
        thread_id: Codex thread identifier.
        ticket_id: Target ticket ID.
        mutation_id: Related mutation ID.
        mutation_fingerprint: Canonical mutation payload fingerprint.
        ticket_state_fingerprint: Ticket state fingerprint at approval time.
        evidence_fingerprint: Evidence payload fingerprint.
        current_mode: Thread-scoped automation mode.
        decision: Approval decision kind.

    Returns:
        `appr_` plus the first 32 hex characters of the payload digest.
    """
    return _short_prefixed_id(
        "appr",
        {
            "schema": schema,
            "thread_id": thread_id,
            "ticket_id": ticket_id,
            "mutation_id": mutation_id,
            "mutation_fingerprint": mutation_fingerprint,
            "ticket_state_fingerprint": ticket_state_fingerprint,
            "evidence_fingerprint": evidence_fingerprint,
            "current_mode": current_mode,
            "decision": decision,
        },
    )
