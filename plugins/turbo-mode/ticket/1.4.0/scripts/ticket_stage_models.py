"""Stage-boundary input models for the ticket engine pipeline.

Frozen dataclasses with from_payload() constructors that validate shape and
presence at the dispatch boundary. Business rule validation (allowed field
values, status transitions, etc.) remains in the engine and ticket_validate.py.

Import direction: this module imports only stdlib. Entrypoints and engine
import from it. It must not import EngineResponse, AutonomyConfig, or any
ticket module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PayloadError(Exception):
    """Raised when payload validation fails during stage-input construction.

    code: "need_fields" (missing required data) or "parse_error" (wrong type/shape)
    state: recommended EngineResponse state — "need_fields" or "escalate"
    """

    def __init__(self, message: str, *, code: str, state: str) -> None:
        super().__init__(message)
        self.code = code
        self.state = state


# --- Extraction helpers ---


def _get_str(payload: dict[str, Any], key: str, *, default: str) -> str:
    """Get a string field with a default. Raises PayloadError if present but wrong type."""
    value = payload.get(key, default)
    if not isinstance(value, str):
        raise PayloadError(
            f"{key} must be a string, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return value


def _get_dict(payload: dict[str, Any], key: str, *, default: dict[str, Any] | None) -> dict[str, Any]:
    """Get a dict field with a default. Raises PayloadError if present but wrong type."""
    if key not in payload:
        if default is not None:
            return dict(default)  # Defensive copy.
        raise PayloadError(
            f"missing required field: {key}",
            code="need_fields",
            state="need_fields",
        )
    value = payload[key]
    if not isinstance(value, dict):
        raise PayloadError(
            f"{key} must be a dict, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return value


def _get_bool(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    """Get a bool field with a default. Raises PayloadError if present but wrong type."""
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise PayloadError(
            f"{key} must be a bool, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return value


def _get_float(payload: dict[str, Any], key: str, *, default: float) -> float:
    """Get a numeric field with a default. Accepts int or float."""
    value = payload.get(key, default)
    if not isinstance(value, (int, float)):
        raise PayloadError(
            f"{key} must be a number, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return float(value)


def _get_optional_str(payload: dict[str, Any], key: str) -> str | None:
    """Get an optional string field. Returns None if absent."""
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise PayloadError(
            f"{key} must be a string or null, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return value


def _get_optional_float(payload: dict[str, Any], key: str) -> float | None:
    """Get an optional numeric field. Returns None if absent."""
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise PayloadError(
            f"{key} must be a number or null, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return float(value)


def _get_optional_dict(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    """Get an optional dict field. Returns None if absent."""
    value = payload.get(key)
    if value is not None and not isinstance(value, dict):
        raise PayloadError(
            f"{key} must be a dict or null, got {type(value).__name__}",
            code="parse_error",
            state="escalate",
        )
    return value


# --- Stage input models ---


@dataclass(frozen=True)
class ClassifyInput:
    """Input model for the classify stage."""

    action: str
    args: dict[str, Any]
    session_id: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ClassifyInput:
        return cls(
            action=_get_str(payload, "action", default=""),
            args=_get_dict(payload, "args", default={}),
            session_id=_get_str(payload, "session_id", default=""),
        )


@dataclass(frozen=True)
class PlanInput:
    """Input model for the plan stage."""

    intent: str
    fields: dict[str, Any]
    session_id: str
    ticket_id: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PlanInput:
        # Lazy fallback: only validate "action" type when "intent" is absent.
        # Eager evaluation of _get_str for the default would reject a
        # non-string "action" even when a valid "intent" is present.
        if "intent" in payload:
            intent = _get_str(payload, "intent", default="")
        else:
            intent = _get_str(payload, "action", default="")
        return cls(
            intent=intent,
            fields=_get_dict(payload, "fields", default={}),
            session_id=_get_str(payload, "session_id", default=""),
            ticket_id=_get_optional_str(payload, "ticket_id"),
        )


@dataclass(frozen=True)
class PreflightInput:
    """Input model for the preflight stage."""

    action: str
    ticket_id: str | None
    session_id: str
    classify_confidence: float
    classify_intent: str
    dedup_fingerprint: str | None
    target_fingerprint: str | None
    fields: dict[str, Any] | None
    duplicate_of: str | None
    dedup_override: bool
    dependency_override: bool
    hook_injected: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PreflightInput:
        return cls(
            action=_get_str(payload, "action", default=""),
            ticket_id=_get_optional_str(payload, "ticket_id"),
            session_id=_get_str(payload, "session_id", default=""),
            classify_confidence=_get_float(payload, "classify_confidence", default=0.0),
            classify_intent=_get_str(payload, "classify_intent", default=""),
            dedup_fingerprint=_get_optional_str(payload, "dedup_fingerprint"),
            target_fingerprint=_get_optional_str(payload, "target_fingerprint"),
            fields=_get_optional_dict(payload, "fields"),
            duplicate_of=_get_optional_str(payload, "duplicate_of"),
            dedup_override=_get_bool(payload, "dedup_override", default=False),
            dependency_override=_get_bool(payload, "dependency_override", default=False),
            hook_injected=_get_bool(payload, "hook_injected", default=False),
        )


@dataclass(frozen=True)
class ExecuteInput:
    """Input model for the execute stage."""

    action: str
    ticket_id: str | None
    fields: dict[str, Any]
    session_id: str
    dedup_override: bool
    dependency_override: bool
    target_fingerprint: str | None
    autonomy_config_data: dict[str, Any] | None
    hook_injected: bool
    hook_request_origin: str | None
    classify_intent: str | None
    classify_confidence: float | None
    dedup_fingerprint: str | None
    duplicate_of: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ExecuteInput:
        return cls(
            action=_get_str(payload, "action", default=""),
            ticket_id=_get_optional_str(payload, "ticket_id"),
            fields=_get_dict(payload, "fields", default={}),
            session_id=_get_str(payload, "session_id", default=""),
            dedup_override=_get_bool(payload, "dedup_override", default=False),
            dependency_override=_get_bool(payload, "dependency_override", default=False),
            target_fingerprint=_get_optional_str(payload, "target_fingerprint"),
            # Tolerant extraction: coerce non-dict to None (preserves pre-A-002
            # behavior where isinstance(config_data, dict) silently ignored
            # non-dict values instead of raising).
            autonomy_config_data=(
                payload.get("autonomy_config")
                if isinstance(payload.get("autonomy_config"), dict)
                else None
            ),
            hook_injected=_get_bool(payload, "hook_injected", default=False),
            hook_request_origin=_get_optional_str(payload, "hook_request_origin"),
            classify_intent=_get_optional_str(payload, "classify_intent"),
            classify_confidence=_get_optional_float(payload, "classify_confidence"),
            dedup_fingerprint=_get_optional_str(payload, "dedup_fingerprint"),
            duplicate_of=_get_optional_str(payload, "duplicate_of"),
        )


@dataclass(frozen=True)
class IngestInput:
    """Input model for the ingest stage.

    Receives an envelope path. The ingest handler reads, validates, maps,
    and runs the full engine pipeline internally.
    """

    envelope_path: str
    session_id: str
    hook_injected: bool
    hook_request_origin: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> IngestInput:
        envelope_path = _get_str(payload, "envelope_path", default="")
        if not envelope_path:
            raise PayloadError(
                "envelope_path is required",
                code="need_fields",
                state="need_fields",
            )
        return cls(
            envelope_path=envelope_path,
            session_id=_get_str(payload, "session_id", default=""),
            hook_injected=_get_bool(payload, "hook_injected", default=False),
            hook_request_origin=_get_optional_str(payload, "hook_request_origin"),
        )
