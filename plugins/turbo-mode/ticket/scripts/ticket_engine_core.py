"""Ticket engine core — classify | plan | preflight | execute pipeline.

All mutation and policy-enforcement logic lives here. Entrypoints
(ticket_engine_user.py, ticket_engine_agent.py) set request_origin
and delegate to this module.

Subcommand contract: each function returns an EngineResponse with
{state, ticket_id, message, data}.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, TypeAlias

from scripts.ticket_autonomy_config import AutomationMode, LocalConfigState, read_local_config
from scripts.ticket_change_history import (
    ChangeHistoryEntry,
    append_change_history_entry,
    render_change_history_entry,
)
from scripts.ticket_dedup import target_recovery_fingerprint_for_text
from scripts.ticket_id import allocate_id, build_filename
from scripts.ticket_parse import ParsedTicket
from scripts.ticket_paths import discover_project_root
from scripts.ticket_render import render_ticket
from scripts.ticket_target_schema import (
    TARGET_ACTIVE_STATUSES,
    TARGET_TERMINAL_STATUSES,
    validate_target_section_name,
    validate_target_ticket_text,
)
from scripts.ticket_trust import collect_trust_triple_errors
from scripts.ticket_validate import validate_create_fields, validate_fields

# --- Helpers ---


_V10_GENERATION = 10  # v1.0 tickets have generation=10; legacy is 1-4.
_CONTRACT_VERSION = "1.0"  # Current contract version; stamped on every write.
RuntimeExecuteSurface: TypeAlias = Literal["direct_execute"]


def _check_legacy_gate(ticket: ParsedTicket) -> EngineResponse | None:
    """Reject writes to legacy-format tickets (generation < 10).

    Contract §8: Read-only for legacy formats. Conversion on update
    (with user confirmation). Until confirm-and-convert is implemented,
    all non-create writes to legacy tickets are rejected.

    Returns EngineResponse if blocked, None if allowed.
    """
    if ticket.generation < _V10_GENERATION:
        return EngineResponse(
            state="policy_blocked",
            message=(
                f"Legacy ticket (generation {ticket.generation}) is read-only. "
                f"Contract §8 requires conversion with user confirmation before mutation. "
                f"Use 'ticket migrate {ticket.id}' when available (v1.1)."
            ),
            ticket_id=ticket.id,
            error_code="policy_blocked",
        )
    return None


# --- Response envelope ---


@dataclass
class EngineResponse:
    """Common response envelope for all engine subcommands.

    state: machine state (15 total: 14 emittable + 1 reserved)
    error_code: machine-readable failure code, or None on success
    ticket_id: affected ticket ID or None
    message: human-readable description
    data: subcommand-specific output
    """

    state: str
    message: str
    error_code: str | None = None
    ticket_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    _OK_STATES: frozenset[str] = field(
        default=frozenset({"ok"}),
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.state in self._OK_STATES:
            if self.error_code is not None:
                raise ValueError(
                    f"error_code must be None for success state {self.state!r}, "
                    f"got {self.error_code!r}"
                )
        else:
            if self.error_code is None:
                raise ValueError(
                    f"error_code is required for non-success state {self.state!r}. "
                    f"Message: {self.message!r:.100}"
                )

    def to_dict(self) -> dict[str, Any]:
        d = {
            "state": self.state,
            "ticket_id": self.ticket_id,
            "message": self.message,
            "data": self.data,
        }
        if self.error_code is not None:
            d["error_code"] = self.error_code
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass(frozen=True, slots=True)
class TargetWritePreview:
    """Rendered target ticket write used for pre-write recovery facts."""

    ticket_path: Path
    rendered_text: str
    post_write_fingerprint: str


def _invalid_ticket_state_response(
    reason: object,
    *,
    ticket_id: str | None = None,
) -> EngineResponse:
    return EngineResponse(
        state="invalid_state",
        message="Ticket state is not target-normalized.",
        ticket_id=ticket_id,
        error_code="invalid_state",
        data={"reason": str(reason)},
    )


def _invalid_rendered_ticket_response(
    operation: str,
    ticket_path: Path,
    text: str,
    *,
    ticket_id: str | None = None,
    state: str = "invalid_state",
    error_code: str = "invalid_state",
) -> EngineResponse | None:
    """Return a mutation rejection response when rendered text fails validation."""
    validation = validate_target_ticket_text(ticket_path, text)
    if validation.ok:
        return None
    if state == "need_fields":
        message = (
            f"{operation} failed: proposed fields render an invalid target ticket: "
            f"{validation.error}. Got: {text!r:.100}"
        )
    else:
        message = (
            f"{operation} failed: rendered ticket is not target-normalized: "
            f"{validation.error}. Got: {text!r:.100}"
        )
    return EngineResponse(
        state=state,
        message=message,
        ticket_id=ticket_id or validation.ticket_id or None,
        error_code=error_code,
        data={"reason": validation.error},
    )


def _find_ticket_by_id_for_engine(
    tickets_dir: Path,
    ticket_id: str,
) -> tuple[ParsedTicket | None, EngineResponse | None]:
    from scripts.ticket_read import InvalidTicketState, find_ticket_by_id

    try:
        return find_ticket_by_id(tickets_dir, ticket_id), None
    except InvalidTicketState as exc:
        return None, _invalid_ticket_state_response(exc, ticket_id=ticket_id)


def _list_tickets_for_engine(
    tickets_dir: Path,
    *,
    ticket_id: str | None = None,
) -> tuple[list[ParsedTicket], EngineResponse | None]:
    from scripts.ticket_read import InvalidTicketState, list_tickets

    try:
        return list_tickets(tickets_dir), None
    except InvalidTicketState as exc:
        return [], _invalid_ticket_state_response(exc, ticket_id=ticket_id)


TARGET_RESULT_STATES = frozenset(
    {
        "ok",
        "blocked",
        "needs_discussion",
        "invalid_state",
        "no_change",
    }
)

_INVALID_STATE_ERROR_CODES = frozenset(
    {
        "invalid_state",
        "invalid_transition",
        "not_found",
        "stale_plan",
    }
)

_TARGET_STATE_BY_STATE = {
    "ok": "ok",
    "blocked": "blocked",
    "needs_discussion": "needs_discussion",
    "discussion_required": "needs_discussion",
    "invalid_state": "invalid_state",
    "no_change": "no_change",
    "policy_blocked": "blocked",
    "need_fields": "blocked",
    "duplicate_candidate": "blocked",
    "preflight_failed": "invalid_state",
    "invalid_transition": "invalid_state",
    "not_found": "invalid_state",
    "escalate": "blocked",
    "unavailable": "blocked",
}


def target_state_for_response(state: str, error_code: str | None = None) -> str:
    """Map diagnostic/stage response states to the target result envelope."""
    if state in TARGET_RESULT_STATES:
        return state
    if error_code in _INVALID_STATE_ERROR_CODES:
        return "invalid_state"
    return _TARGET_STATE_BY_STATE.get(state, "blocked")


def normalize_target_response(response: EngineResponse) -> EngineResponse:
    """Return a target-envelope response while preserving error detail."""
    target_state = target_state_for_response(response.state, response.error_code)
    if target_state == response.state:
        return response
    return EngineResponse(
        state=target_state,
        message=response.message,
        error_code=response.error_code,
        ticket_id=response.ticket_id,
        data=response.data,
    )


# Sentinel for audit read failures.
AUDIT_UNAVAILABLE = object()


@dataclass(frozen=True)
class AutonomyConfig:
    """Immutable runtime-first automation config snapshot."""

    mode: AutomationMode | str = AutomationMode.DISCUSSION_ONLY
    warnings: tuple[str, ...] = ()
    max_creates: int | None = None

    def __post_init__(self) -> None:
        extra_warnings: list[str] = []
        if not isinstance(self.mode, AutomationMode):
            try:
                object.__setattr__(self, "mode", AutomationMode(self.mode))
            except ValueError:
                extra_warnings.append(
                    f"Invalid mode {self.mode!r}, defaulted to 'discussion_only'"
                )
                object.__setattr__(self, "mode", AutomationMode.DISCUSSION_ONLY)
        if extra_warnings:
            object.__setattr__(self, "warnings", self.warnings + tuple(extra_warnings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyConfig:
        """Reconstruct from dict (snapshot deserialization).

        Validates through __post_init__ — invalid values are self-healed
        to safe defaults with warnings appended.
        """
        return cls(
            mode=data.get("mode", AutomationMode.DISCUSSION_ONLY),
            warnings=tuple(data.get("warnings", ())),
            max_creates=data.get("max_creates"),
        )


# --- Valid actions and origins ---

VALID_ACTIONS = frozenset({"create", "update", "close", "reopen"})
VALID_ORIGINS = frozenset({"user", "agent"})


# --- classify ---


def engine_classify(
    *,
    action: str,
    args: dict[str, Any],
    session_id: str,
    request_origin: str,
) -> EngineResponse:
    """Classify the caller's intent and validate the action.

    Input action (from first-token routing) is authoritative. Classify validates
    but does not remap. If classify's intent disagrees -> intent_mismatch -> escalate.

    Returns EngineResponse with state="ok" on success, or error state on failure.
    """
    # Fail closed on unknown origin.
    if request_origin not in VALID_ORIGINS:
        return EngineResponse(
            state="escalate",
            message=f"Cannot determine caller identity: request_origin={request_origin!r}",
            error_code="origin_mismatch",
        )

    # Validate action.
    if action not in VALID_ACTIONS:
        return EngineResponse(
            state="escalate",
            message=f"Unknown action: {action!r}. Valid: {', '.join(sorted(VALID_ACTIONS))}",
            error_code="intent_mismatch",
        )

    # Resolve ticket ID from args (for non-create actions).
    resolved_ticket_id = args.get("ticket_id") if action != "create" else None

    # Confidence: high for explicit invocations (first-token routing provides strong signal).
    # This is a provisional default — calibration on labeled corpus required pre-GA.
    confidence = 0.95

    return EngineResponse(
        state="ok",
        message=f"Classified as {action}",
        data={
            "intent": action,
            "confidence": confidence,
            "classify_intent": action,
            "classify_confidence": confidence,
            "resolved_ticket_id": resolved_ticket_id,
        },
    )


# --- plan ---

# Required fields for create.
_CREATE_REQUIRED = ("title", "problem")
_CREATE_STATUSES = frozenset(TARGET_ACTIVE_STATUSES)

# Dedup window.
_DEDUP_WINDOW_HOURS = 24


def _validate_create_status_shape(fields: dict[str, Any]) -> list[str]:
    status = fields.get("status", "open")
    blocked_on = fields.get("blocked_on")
    blocked_by = fields.get("blocked_by", [])
    errors: list[str] = []

    if not isinstance(status, str) or status not in _CREATE_STATUSES:
        errors.append(f"create status must be one of {sorted(_CREATE_STATUSES)}")
    if status == "blocked":
        if not isinstance(blocked_on, str) or not blocked_on.strip():
            errors.append("blocked create requires blocked_on")
    else:
        if blocked_on:
            errors.append("blocked_on is only valid for blocked create")
        if blocked_by:
            errors.append("blocked_by is only valid for blocked create")
    return errors


def engine_plan(
    *,
    intent: str,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    ticket_id: str | None = None,
) -> EngineResponse:
    """Plan stage: validate fields, check duplicates, compute fingerprints.

    For create: validates required fields, computes dedup fingerprint,
    scans for duplicates within 24h window.
    For other intents: resolves ticket and computes target_fingerprint
    for TOCTOU protection in execute.

    Args:
        ticket_id: Top-level ticket_id from payload (for update/close/reopen).
    """
    if intent == "create":
        return _plan_create(fields, session_id, request_origin, tickets_dir)

    # Non-create: resolve ticket and compute target_fingerprint.
    resolved_id = ticket_id or fields.get("ticket_id")
    computed_fp: str | None = None
    if resolved_id:
        from scripts.ticket_dedup import target_fingerprint as compute_fp

        ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, resolved_id)
        if invalid_state is not None:
            return invalid_state
        if ticket is not None:
            computed_fp = compute_fp(Path(ticket.path))

    return EngineResponse(
        state="ok",
        message=f"Plan pass-through for {intent}",
        data={
            "dedup_fingerprint": None,
            "target_fingerprint": computed_fp,
            "duplicate_of": None,
            "missing_fields": [],
            "action_plan": {"intent": intent},
        },
    )


def _plan_create(
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
) -> EngineResponse:
    """Plan stage for create: field validation + dedup."""
    from scripts.ticket_dedup import dedup_fingerprint

    # Check required fields.
    missing = [f for f in _CREATE_REQUIRED if not fields.get(f)]
    if missing:
        return EngineResponse(
            state="need_fields",
            message=f"Missing required fields: {', '.join(missing)}",
            error_code="need_fields",
            data={"missing_fields": missing},
        )

    create_shape_errors = _validate_create_status_shape(fields)
    if create_shape_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(create_shape_errors)}",
            error_code="need_fields",
            data={"missing_fields": [], "validation_errors": create_shape_errors},
        )

    validation_errors = validate_create_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            data={"missing_fields": [], "validation_errors": validation_errors},
        )

    # Compute dedup fingerprint.
    problem_text = fields["problem"]
    related_paths = fields.get("related_paths", [])
    fp = dedup_fingerprint(problem_text, related_paths)

    # Scan for duplicates within 24h window.
    duplicate_of = None
    dup_target_fp = None
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=_DEDUP_WINDOW_HOURS)

    existing, invalid_state = _list_tickets_for_engine(tickets_dir)
    if invalid_state is not None:
        return invalid_state
    for ticket in existing:
        # Check if ticket is within dedup window.
        # Primary: created_at (ISO 8601 UTC, second-level precision).
        # Fallback: date field (day-level) treated as end-of-day (23:59:59 UTC)
        # for maximum inclusivity — never misses a near-midnight duplicate.
        # No filesystem dependency (mtime) — immune to git checkout/clone.
        if ticket.created_at:
            try:
                ticket_time = datetime.strptime(ticket.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC
                )
            except (ValueError, TypeError):
                ticket_time = None
        else:
            ticket_time = None

        if ticket_time is None:
            try:
                day = datetime.strptime(ticket.date, "%Y-%m-%d").replace(tzinfo=UTC)
                # End-of-day: assume latest possible creation time on that date.
                ticket_time = day.replace(hour=23, minute=59, second=59)
            except (ValueError, TypeError):
                continue

        if ticket_time < cutoff:
            continue

        # Compute fingerprint for this ticket's problem text.
        ticket_problem = ticket.sections.get("Problem", "")
        existing_fp = dedup_fingerprint(ticket_problem, ticket.related_paths)
        if existing_fp == fp:
            from scripts.ticket_dedup import target_fingerprint

            duplicate_of = ticket.id
            dup_target_fp = target_fingerprint(Path(ticket.path))
            break

    if duplicate_of:
        return EngineResponse(
            state="duplicate_candidate",
            message=f"Potential duplicate of {duplicate_of}",
            ticket_id=duplicate_of,
            error_code="duplicate_candidate",
            data={
                "dedup_fingerprint": fp,
                "target_fingerprint": dup_target_fp,
                "duplicate_of": duplicate_of,
                "missing_fields": [],
                "action_plan": {"intent": "create", "duplicate_candidate": True},
            },
        )

    return EngineResponse(
        state="ok",
        message="Plan complete, no duplicates found",
        data={
            "dedup_fingerprint": fp,
            "target_fingerprint": None,
            "duplicate_of": None,
            "missing_fields": [],
            "action_plan": {"intent": "create"},
        },
    )


# --- preflight ---

# Confidence thresholds (provisional — calibrate pre-GA).
_T_BASE = 0.5
_ORIGIN_MODIFIER: dict[str, float] = {"user": 0.0, "agent": 0.15}

# Terminal statuses for dependency resolution.
_TERMINAL_STATUSES = TARGET_TERMINAL_STATUSES


def _read_autonomy_config_state(
    tickets_dir: Path,
) -> tuple[AutonomyConfig, LocalConfigState, str | None]:
    project_root = discover_project_root(tickets_dir)
    if project_root is None:
        return (
            AutonomyConfig(warnings=("project_root_not_found",)),
            LocalConfigState.SETUP_REQUIRED,
            "project_root_not_found",
        )

    result = read_local_config(project_root)
    if result.state == LocalConfigState.VALID and result.mode is not None:
        return AutonomyConfig(mode=result.mode), LocalConfigState.VALID, None

    reason = result.reason or "setup_required"
    return (
        AutonomyConfig(mode=AutomationMode.DISCUSSION_ONLY, warnings=(reason,)),
        LocalConfigState.SETUP_REQUIRED,
        reason,
    )


def read_autonomy_config(tickets_dir: Path) -> AutonomyConfig:
    """Read strict local automation config for legacy engine callers."""
    config, _state, _reason = _read_autonomy_config_state(tickets_dir)
    return config


def engine_preflight(
    *,
    ticket_id: str | None,
    action: str,
    session_id: str,
    request_origin: str,
    classify_confidence: float,
    classify_intent: str,
    dedup_fingerprint: str | None,
    target_fingerprint: str | None,
    fields: dict[str, Any] | None = None,
    duplicate_of: str | None = None,
    dedup_override: bool = False,
    dependency_override: bool = False,
    hook_injected: bool = False,
    tickets_dir: Path,
) -> EngineResponse:
    """Preflight: single enforcement point for all mutating operations.

    Checks in order: origin, action, autonomy policy, confidence, intent match,
    dedup, ticket existence, dependency integrity, TOCTOU fingerprint.
    """
    checks_passed: list[str] = []
    checks_failed: list[dict[str, str]] = []
    preflight_fields = fields or {}

    # --- Origin check ---
    if request_origin not in VALID_ORIGINS:
        return EngineResponse(
            state="escalate",
            message=f"Cannot determine caller identity: request_origin={request_origin!r}",
            error_code="origin_mismatch",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "origin", "reason": "unknown origin"}],
            },
        )
    checks_passed.append("origin")

    # --- Action validation (Codex finding 3: defense-in-depth) ---
    if action not in VALID_ACTIONS:
        return EngineResponse(
            state="escalate",
            message=f"Unknown action: {action!r}. Valid: {', '.join(sorted(VALID_ACTIONS))}",
            error_code="intent_mismatch",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "action", "reason": "unknown action"}],
            },
        )
    checks_passed.append("action")

    # --- Autonomy policy (Codex finding 5: agent checks before confidence) ---
    config, config_state, config_reason = _read_autonomy_config_state(tickets_dir)
    notification: str | None = None

    if request_origin == "agent":
        # Action exclusions: reopen is user-only in v1.0.
        if action == "reopen":
            return EngineResponse(
                state="policy_blocked",
                message="Reopen is user-only in v1.0",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [
                        {"check": "agent_action_exclusion", "reason": "reopen is user-only"}
                    ],
                    "autonomy_config": config.to_dict(),
                },
            )

        # Override rejection: agents cannot use dedup_override or dependency_override.
        if dedup_override:
            return EngineResponse(
                state="policy_blocked",
                message="Agents cannot use dedup_override",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [
                        {
                            "check": "agent_override_rejection",
                            "reason": "dedup_override not allowed for agents",
                        }
                    ],
                    "autonomy_config": config.to_dict(),
                },
            )
        if dependency_override:
            return EngineResponse(
                state="policy_blocked",
                message="Agents cannot use dependency_override",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [
                        {
                            "check": "agent_override_rejection",
                            "reason": "dependency_override not allowed for agents",
                        }
                    ],
                    "autonomy_config": config.to_dict(),
                },
            )

        if config_state != LocalConfigState.VALID:
            return EngineResponse(
                state="policy_blocked",
                message="Ticket automation setup is required before agent mutations can run.",
                error_code="setup_required",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [
                        {"check": "local_config", "reason": config_reason or "setup_required"}
                    ],
                    "autonomy_config": config.to_dict(),
                },
            )

        return EngineResponse(
            state="policy_blocked",
            message=(
                "Agent mutations require a runtime-first autonomy gateway decision before "
                "Ticket can write."
            ),
            error_code="gateway_required",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "runtime_gateway", "reason": "gateway_required"}],
                "autonomy_config": config.to_dict(),
            },
        )

    checks_passed.append("autonomy_policy")

    # --- Confidence gate ---
    modifier = _ORIGIN_MODIFIER.get(request_origin, 0.0)
    threshold = _T_BASE + modifier
    if classify_confidence < threshold:
        return EngineResponse(
            state="preflight_failed",
            error_code="preflight_failed",
            message=f"Low confidence classification: {classify_confidence:.2f} "
            f"(threshold: {threshold:.2f}). Rephrase or specify the operation.",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [
                    {"check": "confidence", "reason": f"below threshold {threshold}"}
                ],
            },
        )
    checks_passed.append("confidence")

    # --- Intent match ---
    if classify_intent != action:
        return EngineResponse(
            state="escalate",
            message=(
                f"Intent_mismatch: classify returned {classify_intent!r} but action is {action!r}"
            ),
            error_code="intent_mismatch",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "intent_match", "reason": "mismatch"}],
            },
        )
    checks_passed.append("intent_match")

    # --- Dedup enforcement (create action) ---
    if action == "create" and dedup_override and not duplicate_of:
        # C-008: dedup_override must be bound to a specific duplicate candidate.
        return EngineResponse(
            state="need_fields",
            message=(
                "dedup_override requires duplicate_of identifying the specific duplicate candidate"
            ),
            error_code="need_fields",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [
                    {"check": "dedup_binding", "reason": "dedup_override without duplicate_of"}
                ],
                "missing_fields": ["duplicate_of"],
            },
        )
    if action == "create" and duplicate_of and not dedup_override:
        return EngineResponse(
            state="duplicate_candidate",
            message=f"Duplicate of {duplicate_of} detected in plan stage. "
            "Pass dedup_override=True to proceed.",
            error_code="duplicate_candidate",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "dedup", "reason": f"duplicate_of={duplicate_of}"}],
            },
        )
    if action == "create":
        checks_passed.append("dedup")

    # --- Ticket ID required for non-create ---
    if action != "create" and not ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {action}",
            error_code="need_fields",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "ticket_id", "reason": "missing for non-create"}],
            },
        )

    # --- Ticket existence check (non-create) ---
    if action != "create" and ticket_id:
        ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
        if invalid_state is not None:
            return invalid_state
        if ticket is None:
            return EngineResponse(
                state="not_found",
                message=f"No ticket found matching {ticket_id}",
                ticket_id=ticket_id,
                error_code="not_found",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "ticket_exists", "reason": "not found"}],
                },
            )
        checks_passed.append("ticket_exists")

        # --- Dependency check (close action) ---
        if action == "close" and ticket.blocked_by:
            resolution = preflight_fields.get("resolution", "done")
            if resolution == "wontfix":
                checks_passed.append("dependencies_not_required_for_wontfix")
            else:
                all_tickets, invalid_state = _list_tickets_for_engine(
                    tickets_dir,
                    ticket_id=ticket_id,
                )
                if invalid_state is not None:
                    return invalid_state
                ticket_map = {t.id: t for t in all_tickets}
                missing, unresolved = _classify_blockers(ticket.blocked_by, ticket_map)
                if missing or unresolved:
                    if dependency_override:
                        checks_passed.append("dependencies_overridden")
                    else:
                        return EngineResponse(
                            state="dependency_blocked",
                            message=_format_blocker_message(
                                unresolved=unresolved,
                                missing=missing,
                                include_override=True,
                            ),
                            ticket_id=ticket_id,
                            error_code="dependency_blocked",
                            data={
                                "checks_passed": checks_passed,
                                "checks_failed": [
                                    {
                                        "check": "dependencies",
                                        "reason": f"unresolved={unresolved}, missing={missing}",
                                    }
                                ],
                                "blocking_ids": unresolved + missing,
                                "unresolved_blockers": unresolved,
                                "missing_blockers": missing,
                            },
                        )
                else:
                    checks_passed.append("dependencies")

        # --- TOCTOU fingerprint check ---
        if target_fingerprint is not None:
            from scripts.ticket_dedup import target_fingerprint as compute_fp

            current_fp = compute_fp(Path(ticket.path))
            if current_fp != target_fingerprint:
                return EngineResponse(
                    state="preflight_failed",
                    message="Stale fingerprint — ticket was modified since read. "
                    "Re-run to get a fresh plan.",
                    ticket_id=ticket_id,
                    error_code="stale_plan",
                    data={
                        "checks_passed": checks_passed,
                        "checks_failed": [{"check": "target_fingerprint", "reason": "stale"}],
                    },
                )
            checks_passed.append("target_fingerprint")

    response_data: dict[str, Any] = {
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "autonomy_config": config.to_dict(),
    }
    if notification:
        response_data["notification"] = notification
    return EngineResponse(
        state="ok",
        message="All preflight checks passed",
        data=response_data,
    )


# --- execute ---

# Supported YAML frontmatter fields for update.
_UPDATE_FRONTMATTER_KEYS = frozenset(
    {
        "status",
        "priority",
        "related_paths",
        "tags",
        "blocked_by",
    }
)
_UPDATE_FOCUSED_MODE = "focused_refinement"
_UPDATE_INTERNAL_FIELDS = frozenset({"_update_mode", "_clear_refinement_status"})
_UPDATE_FOCUSED_SECTION_FIELDS = frozenset(
    {"problem", "next_action", "acceptance_criteria", "blocked_on"}
)
_UPDATE_SECTION_FIELDS = frozenset(
    {
        "problem",
        "next_action",
        "blocked_on",
        "context",
        "prior_investigation",
        "approach",
        "decisions_made",
        "acceptance_criteria",
        "verification",
        "key_files",
        "related",
    }
)
_UPDATE_IGNORED_FIELDS = frozenset({"ticket_id", "id"})

# Valid status transitions for update action only.
# Close and reopen handle terminal state changes as separate actions.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "idea": {"open"},
    "open": {"blocked"},
    "blocked": {"open"},
    "done": set(),
    "wontfix": set(),
}

# Bounds archive collision search to avoid infinite loops in pathological trees.
_MAX_ARCHIVE_COLLISION_SUFFIX = 1000
_CREATE_WRITE_RETRY_LIMIT = 3
_CREATE_TARGET_SECTION_MAP = {
    "Problem": "problem",
    "Next Action": "next_action",
    "Blocked On": "blocked_on",
    "Captured Request": "captured_request",
    "Context": "context",
    "Prior Investigation": "prior_investigation",
    "Approach": "approach",
    "Decisions Made": "decisions_made",
    "Acceptance Criteria": "acceptance_criteria",
    "Verification": "verification",
    "Key Files": "key_files",
    "Related": "related",
}

# Transitions that require preconditions.
# Pair-keyed: specific (current, target) combinations.
_TRANSITION_PRECONDITIONS: dict[tuple[str, str], str] = {
    ("open", "blocked"): "blocked_on_required",
    ("blocked", "open"): "blocker_cleanup_required",
}
# Target-keyed: preconditions that apply regardless of current status.
_TARGET_PRECONDITIONS: dict[str, str] = {
    "done": "acceptance_criteria_required",
}


def _normalize_acceptance_criterion(line: str) -> str:
    """Return acceptance-criteria text without markdown checklist/bullet markers."""
    stripped = line.strip()
    stripped = re.sub(r"^- \[[ xX]\]\s*", "", stripped)
    stripped = re.sub(r"^[-*]\s*", "", stripped)
    return stripped.strip()


def _acceptance_criteria_is_only_needs_refinement(section: str) -> bool:
    """Return True when the AC section contains only the refinement placeholder."""
    criteria = [
        criterion
        for criterion in (_normalize_acceptance_criterion(line) for line in section.splitlines())
        if criterion
    ]
    return criteria == ["Needs refinement"]


def _ticket_still_needs_refinement(ticket: Any) -> bool:
    """Return True when the AC placeholder blocks done readiness."""
    return _acceptance_criteria_is_only_needs_refinement(
        ticket.sections.get("Acceptance Criteria", "")
    )


def _transition_policy_data(
    current: str,
    requested: str,
    *,
    valid_recovery_statuses: list[str],
    requires_reopen: bool,
    precondition_code: str = "none",
    precondition_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build machine-readable transition policy context for workflow recovery."""
    return {
        "current_status": current,
        "requested_status": requested,
        "valid_recovery_statuses": valid_recovery_statuses,
        "requires_reopen": requires_reopen,
        "precondition_code": precondition_code,
        "precondition_detail": precondition_detail,
    }


def _check_transition_preconditions_with_detail(
    current: str,
    target: str,
    ticket: Any,
    tickets_dir: Path,
    fields: dict[str, Any] | None = None,
) -> tuple[str | None, str, dict[str, Any] | None]:
    """Check transition preconditions and return message plus machine context."""
    _fields = fields or {}

    target_precondition = _TARGET_PRECONDITIONS.get(target)
    if target_precondition == "acceptance_criteria_required":
        ac = ticket.sections.get("Acceptance Criteria", "")
        if _ticket_still_needs_refinement(ticket):
            return (
                "Transition to 'done' requires concrete acceptance criteria; "
                "ticket still needs refinement",
                "missing_acceptance_criteria",
                {"missing": ["acceptance_criteria"]},
            )
        if not ac.strip():
            return (
                "Transition to 'done' requires acceptance criteria section",
                "missing_acceptance_criteria",
                {"missing": ["acceptance_criteria"]},
            )

    key = (current, target)
    precondition = _TRANSITION_PRECONDITIONS.get(key)
    if precondition is None:
        return (None, "none", None)

    if precondition == "blocked_on_required":
        blocked_on = _fields.get("blocked_on")
        if not isinstance(blocked_on, str) or not blocked_on.strip():
            return (
                "Transition to 'blocked' requires blocked_on",
                "blocked_on_required",
                {"missing": ["blocked_on"]},
            )
        return (None, "none", None)

    if precondition == "blocker_cleanup_required":
        blocked_by = _fields.get("blocked_by", ticket.blocked_by)
        blocked_on_present = "blocked_on" in _fields
        # Unblocking must explicitly clear both machine IDs and visible blocker prose.
        if blocked_by != [] or not blocked_on_present or _fields.get("blocked_on") is not None:
            return (
                "Transition to 'open' from blocked requires clearing blocked_by and Blocked On",
                "blocker_cleanup_required",
                {"required": ["blocked_by: []", "blocked_on: null"]},
            )
        return (None, "none", None)

    return (None, "none", None)


def _classify_update_fields(
    fields: dict[str, Any],
    ticket_id: str,
) -> tuple[dict[str, Any], list[str], list[str], bool]:
    """Split update payload keys into supported vs invalid categories."""
    frontmatter_updates: dict[str, Any] = {}
    section_fields: list[str] = []
    unknown_fields: list[str] = []
    ticket_id_mismatch = False

    for key, value in fields.items():
        if key in _UPDATE_INTERNAL_FIELDS:
            continue
        if key in _UPDATE_IGNORED_FIELDS:
            if key == "ticket_id" and value != ticket_id:
                ticket_id_mismatch = True
            continue
        if key in _UPDATE_FRONTMATTER_KEYS:
            frontmatter_updates[key] = value
        elif key in _UPDATE_SECTION_FIELDS:
            section_fields.append(key)
        else:
            unknown_fields.append(key)

    return (
        frontmatter_updates,
        sorted(section_fields),
        sorted(unknown_fields),
        ticket_id_mismatch,
    )


_UPDATE_SECTION_HEADINGS = {
    "problem": "Problem",
    "next_action": "Next Action",
    "blocked_on": "Blocked On",
    "acceptance_criteria": "Acceptance Criteria",
}
_TARGET_FRONTMATTER_BLOCK_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)


def _render_key_files_section_value(value: Any) -> str:
    if not isinstance(value, list):
        raise ValueError("Key Files target section requires a list of row objects")
    rows = ["| File | Role | Look For |", "|------|------|----------|"]
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Key Files target section requires row objects")
        rows.append(
            "| "
            + " | ".join(
                str(item.get(key, ""))
                for key in ("file", "role", "look_for")
            )
            + " |"
        )
    return "\n".join(rows)


def _render_target_section_value(heading: str, value: Any) -> str | None:
    if value is None:
        return None
    if heading == "Acceptance Criteria":
        return _render_update_section_value("acceptance_criteria", value)
    if heading == "Key Files":
        return _render_key_files_section_value(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"{heading} does not support structured target values")
    return str(value)


def _target_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Return canonical target frontmatter fields."""
    return {
        "id": frontmatter["id"],
        "title": frontmatter["title"],
        "status": frontmatter["status"],
        "priority": frontmatter["priority"],
        "tags": frontmatter.get("tags", []),
        "related_paths": frontmatter.get("related_paths", []),
        "blocked_by": frontmatter.get("blocked_by", []),
    }


def _replace_target_frontmatter_text(text: str, frontmatter: dict[str, Any]) -> str:
    """Replace only target YAML frontmatter, preserving body bytes."""
    from scripts.ticket_render import render_frontmatter

    frontmatter_text = render_frontmatter(_target_frontmatter(frontmatter)).rstrip("\n")
    replacement = f"---\n{frontmatter_text}\n---\n"
    updated, replacements = _TARGET_FRONTMATTER_BLOCK_RE.subn(replacement, text, count=1)
    if replacements != 1:
        raise ValueError(
            "target frontmatter replacement failed: frontmatter block not found. "
            f"Got: {text!r:.100}"
        )
    return updated


def _render_target_ticket_text(
    frontmatter: dict[str, Any],
    sections: dict[str, str | None],
    *,
    original_text: str | None = None,
    targeted_headings: tuple[str, ...] = (),
) -> str:
    """Render a target ticket while preserving untargeted body sections.

    For targeted headings on an existing ticket, `None` removes the section and
    an empty string keeps the section with an empty body. For new text, `None`
    omits optional sections and required sections coerce `None` to an empty
    body.
    """
    from scripts.ticket_target_schema import TARGET_SECTIONS_REQUIRED

    if original_text is not None:
        rendered_text = _replace_target_frontmatter_text(original_text, frontmatter)
        for heading in targeted_headings:
            if heading in sections and sections[heading] is None:
                rendered_text = _remove_section(rendered_text, heading)
            else:
                rendered_text = _replace_or_append_section(
                    rendered_text,
                    heading,
                    str(sections.get(heading, "")),
                )
        return rendered_text

    from scripts.ticket_render import render_frontmatter

    rendered = ["---", render_frontmatter(_target_frontmatter(frontmatter)).rstrip("\n"), "---", ""]
    emitted: set[str] = set()
    for heading in TARGET_SECTIONS_REQUIRED:
        body = sections.get(heading, "")
        if body is None:
            body = ""
        rendered.extend([f"## {heading}", body.strip(), ""])
        emitted.add(heading)
    for heading, body in sections.items():
        if heading in emitted or body is None:
            continue
        rendered.extend([f"## {heading}", body.strip(), ""])
    return "\n".join(rendered).rstrip() + "\n"


def _focused_section_fields_allowed(fields: dict[str, Any], section_fields: list[str]) -> bool:
    """Return True for focused refinement or status-specific blocker section writes."""
    if fields.get("_update_mode") == _UPDATE_FOCUSED_MODE and all(
        field in _UPDATE_FOCUSED_SECTION_FIELDS for field in section_fields
    ):
        return True
    if fields.get("status") in {"blocked", "open"}:
        return all(field in {"blocked_on", "next_action"} for field in section_fields)
    return False


def _render_update_section_value(key: str, value: Any) -> str | None:
    """Render focused section update values into markdown section content."""
    if value is None:
        return None
    if key == "acceptance_criteria":
        if not isinstance(value, list):
            return ""
        return "\n".join(f"- [ ] {criterion}" for criterion in value)
    return str(value)


def _replace_or_append_section(text: str, heading: str, content: str) -> str:
    """Replace a level-two section body, inserting/appending when missing."""
    replacement = f"## {heading}\n{content.rstrip()}\n\n"
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    updated, count = pattern.subn(replacement, text, count=1)
    if count:
        return updated
    if heading == "Blocked On":
        return _insert_section_before(text, replacement, before_heading="Change History")
    return text.rstrip() + "\n\n" + replacement


def _insert_section_before(text: str, replacement: str, *, before_heading: str) -> str:
    """Insert a missing section before another level-two heading when present."""
    before_match = re.search(rf"^## {re.escape(before_heading)}\n", text, re.MULTILINE)
    if before_match is None:
        return text.rstrip() + "\n\n" + replacement
    return (
        text[: before_match.start()].rstrip()
        + "\n\n"
        + replacement
        + text[before_match.start() :]
    )


def _remove_section(text: str, heading: str) -> str:
    """Remove the first matching level-two section and leave surrounding text intact."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    updated, _count = pattern.subn("", text, count=1)
    return updated.rstrip() + "\n"


def _is_valid_transition(current: str, target: str, action: str) -> bool:
    """Check if a status transition is valid per the contract."""
    if action == "close":
        return current in {"open", "blocked"} and target in ("done", "wontfix")
    if action == "reopen":
        return current in ("done", "wontfix") and target == "open"
    # Update: follow transition table.
    valid = _VALID_TRANSITIONS.get(current, set())
    return target in valid


def _classify_blockers(
    blocked_by: list[str],
    ticket_map: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Split blocker references into missing vs unresolved IDs."""
    missing: list[str] = []
    unresolved: list[str] = []
    for bid in blocked_by:
        blocker = ticket_map.get(bid)
        if blocker is None:
            missing.append(bid)
        elif blocker.status not in _TERMINAL_STATUSES:
            unresolved.append(bid)
    return missing, unresolved


def _format_blocker_message(
    *,
    unresolved: list[str],
    missing: list[str],
    include_override: bool,
) -> str:
    """Build a blocker message that distinguishes missing references."""
    parts: list[str] = []
    if unresolved:
        parts.append(f"Ticket has open blockers: {unresolved}.")
    if missing:
        parts.append(f"Ticket has missing blocker references: {missing}.")
    if include_override:
        parts.append(
            "Resolve blockers, remove stale references, or pass dependency_override: true."
        )
    else:
        parts.append(
            "Resolve open blockers and remove stale/missing blocker references "
            "before changing status."
        )
    return " ".join(parts)


def _autonomy_policy_fingerprint(config: AutonomyConfig) -> tuple[str]:
    """Return the policy-relevant autonomy fields."""
    return (config.mode.value,)


def _check_transition_preconditions(
    current: str,
    target: str,
    ticket: Any,
    tickets_dir: Path,
    fields: dict[str, Any] | None = None,
) -> str | None:
    """Check transition preconditions. Returns error message or None if OK."""
    message, _code, _detail = _check_transition_preconditions_with_detail(
        current,
        target,
        ticket,
        tickets_dir,
        fields=fields,
    )
    return message


def _sanitize_session_id(session_id: str) -> str:
    """Sanitize session_id for safe use as a filename component.

    Strips path separators and null bytes to prevent path traversal.
    Logs a warning to stderr if sanitization changes the value.
    """
    sanitized = session_id.replace("/", "_").replace("\\", "_").replace("\0", "_")
    if sanitized != session_id:
        print(f"WARNING: session_id sanitized: {session_id!r} -> {sanitized!r}", file=sys.stderr)
    return sanitized


def _audit_append(session_id: str, tickets_dir: Path, entry: dict[str, Any]) -> bool:
    """Historical no-op for future engine writes.

    Existing `.audit` readers and repair tools remain available for historical
    files, but runtime writes moved to Change History plus pending-summary
    bookkeeping.
    """
    del session_id, tickets_dir, entry
    return True


def engine_count_session_creates(
    session_id: str,
    tickets_dir: Path,
    request_origin: str = "agent",
) -> int | object:
    """Count successful or gap create actions in a session's audit files.

    Uses attempt_started entries (written before mutation, fail-closed) minus
    known-failed results to compute the count. This ensures:
    - Successful creates are counted.
    - Gap creates (result audit write failed) are conservatively counted.
    - Failed creates (execution error) are NOT counted.

    Falls back to counting unpaired success result entries for backward
    compatibility with audit files written before attempt_started carried the
    intent field.

    Args:
        request_origin: Only count creates from this origin. Defaults to
            "agent" so user creates don't consume the agent budget.

    Returns:
        int: count of creates (0 if no audit files exist)
        AUDIT_UNAVAILABLE: on permission error reading an audit file
    """
    safe_id = _sanitize_session_id(session_id)
    audit_base = tickets_dir / ".audit"
    if not audit_base.is_dir():
        return 0

    # Session-scoped pairing state: pending_create tracks whether the most
    # recent attempt_started (create) has been matched to a result. Carried
    # across date-directory boundaries so a create spanning midnight pairs
    # correctly (attempt_started on day N, result on day N+1).
    attempts = 0
    non_ok = 0
    legacy_success = 0
    pending_create = False

    def is_success_result(result: str) -> bool:
        return result == "ok" or result.startswith("ok_")

    for date_dir in sorted(audit_base.iterdir()):
        if not date_dir.is_dir():
            continue
        audit_file = date_dir / f"{safe_id}.jsonl"
        if not audit_file.exists():
            continue
        try:
            text = audit_file.read_text(encoding="utf-8")
        except OSError:
            return AUDIT_UNAVAILABLE

        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                print(
                    f"WARNING: corrupt audit line in {audit_file}: {line[:100]!r}", file=sys.stderr
                )
                continue
            if entry.get("request_origin") != request_origin:
                continue
            # New format: attempt_started with intent field.
            if entry.get("action") == "attempt_started" and entry.get("intent") == "create":
                pending_create = True
                attempts += 1
            # Create result entry — pair with preceding attempt_started if any.
            elif entry.get("action") == "create" and isinstance(entry.get("result"), str):
                if pending_create:
                    pending_create = False
                    if not is_success_result(entry["result"]):
                        non_ok += 1
                elif is_success_result(entry["result"]):
                    # Unpaired success: legacy format (no preceding attempt_started).
                    legacy_success += 1

    # New-format creates: attempts minus known failures (gap-safe).
    return max(0, attempts - non_ok) + legacy_success


def engine_execute(
    *,
    action: str,
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    dedup_override: bool,
    dependency_override: bool,
    tickets_dir: Path,
    target_fingerprint: str | None = None,
    autonomy_config: AutonomyConfig | None = None,
    hook_injected: bool = False,
    hook_request_origin: str | None = None,
    classify_intent: str | None = None,
    classify_confidence: float | None = None,
    dedup_fingerprint: str | None = None,
    duplicate_of: str | None = None,
    runtime_execute_surface: RuntimeExecuteSurface | None = None,
    runtime_proof_path: Path | None = None,
    allow_activation_bootstrap: bool = False,
) -> EngineResponse:
    """Execute the mutation: create, update, close, or reopen.

    Assumes preflight has already passed. Writes ticket files.
    Wraps dispatch with JSONL audit trail.

    Args:
        runtime_execute_surface: Execute surface under certification. Only
            `direct_execute` is defined, and only for agent-origin execute.
        runtime_proof_path: Optional proof path used by runtime activation tests
            and explicit activation bootstrap.
        allow_activation_bootstrap: Permits a temporary activation-in-progress
            proof for the direct_execute activation smoke.
    """
    if request_origin not in VALID_ORIGINS:
        return EngineResponse(
            state="escalate",
            message=f"Cannot determine caller identity: request_origin={request_origin!r}",
            error_code="origin_mismatch",
        )

    snapshot_config = autonomy_config
    if request_origin == "agent" and runtime_execute_surface == "direct_execute":
        config = snapshot_config or AutonomyConfig()
    elif request_origin == "agent":
        config = read_autonomy_config(tickets_dir)
        if snapshot_config is not None and _autonomy_policy_fingerprint(
            snapshot_config
        ) != _autonomy_policy_fingerprint(config):
            policy_changed_data: dict[str, Any] = {"live_mode": config.mode}
            if config.warnings:
                policy_changed_data["live_warnings"] = list(config.warnings)
            return EngineResponse(
                state="policy_blocked",
                message="Autonomy policy changed since preflight. Rerun from preflight.",
                error_code="policy_blocked",
                data=policy_changed_data,
            )
    else:
        config = snapshot_config or AutonomyConfig()

    # --- Transport-layer trust triple (defense-in-depth for all origins) ---
    # The direct_execute exception is intentionally asymmetric: agent execute may
    # carry user hook provenance on current hosts, but user execute with agent
    # provenance still rejects. This only relaxes provenance matching; the
    # runtime-readiness proof gate below still decides whether the write may run.
    allow_direct_execute_provenance_mismatch = (
        runtime_execute_surface == "direct_execute"
        and request_origin == "agent"
        and hook_request_origin == "user"
    )
    if (
        hook_request_origin is not None
        and hook_request_origin != request_origin
        and not allow_direct_execute_provenance_mismatch
    ):
        return EngineResponse(
            state="escalate",
            message=(
                f"origin_mismatch: request_origin={request_origin!r}, "
                f"hook_request_origin={hook_request_origin!r}"
            ),
            error_code="origin_mismatch",
        )
    trust_errors = collect_trust_triple_errors(
        hook_injected,
        hook_request_origin,
        session_id,
    )
    if trust_errors:
        return EngineResponse(
            state="policy_blocked",
            message=f"Execute requires verified hook provenance: {', '.join(trust_errors)}",
            error_code="policy_blocked",
        )

    # --- Structural stage prerequisites ---
    # classify_intent: must match action.
    if classify_intent is None:
        return EngineResponse(
            state="policy_blocked",
            message="Execute requires classify_intent (run classify stage first)",
            error_code="policy_blocked",
        )
    if classify_intent != action:
        return EngineResponse(
            state="escalate",
            message=f"intent_mismatch: classify_intent={classify_intent!r} but action={action!r}",
            error_code="intent_mismatch",
        )

    # classify_confidence: must be present and above threshold.
    if classify_confidence is None:
        return EngineResponse(
            state="policy_blocked",
            message="Execute requires classify_confidence (run classify stage first)",
            error_code="policy_blocked",
        )
    modifier = _ORIGIN_MODIFIER.get(request_origin, 0.0)
    threshold = _T_BASE + modifier
    if classify_confidence < threshold:
        return EngineResponse(
            state="preflight_failed",
            message=f"Low confidence: {classify_confidence:.2f} (threshold: {threshold:.2f})",
            error_code="preflight_failed",
        )

    # dedup_fingerprint: required for create, must match recomputed value.
    if action == "create":
        if dedup_fingerprint is None:
            return EngineResponse(
                state="policy_blocked",
                message="Create execute requires dedup_fingerprint (run plan stage first)",
                error_code="policy_blocked",
            )
        validation_errors = validate_fields(fields)
        if validation_errors:
            return EngineResponse(
                state="need_fields",
                message=f"Field validation failed: {'; '.join(validation_errors)}",
                error_code="need_fields",
                data={"validation_errors": validation_errors},
            )
        from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp

        expected_fp = compute_dedup_fp(
            fields.get("problem", ""),
            fields.get("related_paths", []),
        )
        if dedup_fingerprint != expected_fp:
            return EngineResponse(
                state="preflight_failed",
                message="dedup_fingerprint mismatch — create fields changed since plan",
                error_code="stale_plan",
            )

    # target_fingerprint: required for non-create actions.
    if action != "create" and target_fingerprint is None:
        return EngineResponse(
            state="policy_blocked",
            message=f"{action} execute requires target_fingerprint (run plan stage first)",
            error_code="policy_blocked",
        )

    if request_origin == "agent" and runtime_execute_surface == "direct_execute":
        return EngineResponse(
            state="policy_blocked",
            message=(
                "Direct agent execute requires a gateway-validated decision. "
                "Use the runtime-first autonomy gateway once it is available."
            ),
            error_code="gateway_required",
        )

    # autonomy_config: required for agent-origin (snapshot from preflight).
    if request_origin == "agent" and autonomy_config is None:
        return EngineResponse(
            state="policy_blocked",
            message="Agent execute requires autonomy_config snapshot (rerun from preflight)",
            error_code="policy_blocked",
        )

    # --- Autonomy defense-in-depth (self-contained allowlist) ---
    if request_origin == "agent":
        if action == "reopen":
            return EngineResponse(
                state="policy_blocked",
                message="Defense-in-depth: reopen is user-only in v1.0",
                error_code="policy_blocked",
            )
        if dedup_override:
            return EngineResponse(
                state="policy_blocked",
                message="Defense-in-depth: agents cannot use dedup_override",
                error_code="policy_blocked",
            )
        if dependency_override:
            return EngineResponse(
                state="policy_blocked",
                message="Defense-in-depth: agents cannot use dependency_override",
                error_code="policy_blocked",
            )
        dind_data: dict[str, Any] = {"live_mode": config.mode.value}
        if config.warnings:
            dind_data["live_warnings"] = list(config.warnings)
        return EngineResponse(
            state="policy_blocked",
            message="Defense-in-depth: agent mutations require the runtime-first gateway",
            error_code="gateway_required",
            data=dind_data,
        )

    # C-008: dedup_override must be bound to a specific duplicate candidate.
    if action == "create" and dedup_override and not duplicate_of:
        return EngineResponse(
            state="need_fields",
            message=(
                "dedup_override requires duplicate_of identifying the specific duplicate candidate"
            ),
            error_code="need_fields",
            data={"missing_fields": ["duplicate_of"]},
        )

    # Defense-in-depth dedup check for direct execute(create) calls.
    if action == "create":
        create_fields = dict(fields)
        create_fields.setdefault("priority", "normal")
        plan_resp = _plan_create(create_fields, session_id, request_origin, tickets_dir)
        if plan_resp.state not in {"ok", "duplicate_candidate"}:
            return plan_resp
        if plan_resp.state == "duplicate_candidate" and not dedup_override:
            duplicate_of = plan_resp.data.get("duplicate_of")
            return EngineResponse(
                state="duplicate_candidate",
                message=(
                    f"Duplicate of {duplicate_of} detected in execute stage. "
                    "Pass dedup_override=True to proceed."
                ),
                error_code="duplicate_candidate",
                ticket_id=duplicate_of if isinstance(duplicate_of, str) else None,
                data={
                    "duplicate_of": duplicate_of,
                    "dedup_fingerprint": plan_resp.data.get("dedup_fingerprint"),
                    "target_fingerprint": plan_resp.data.get("target_fingerprint"),
                },
            )

    # Optional stale-plan defense-in-depth for non-create actions.
    if action != "create" and target_fingerprint is not None:
        if not ticket_id:
            return EngineResponse(
                state="need_fields",
                message=f"ticket_id required for {action}",
                error_code="need_fields",
            )
        from scripts.ticket_dedup import target_fingerprint as compute_fp

        target_ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
        if invalid_state is not None:
            return invalid_state
        if target_ticket is None:
            return EngineResponse(
                state="not_found",
                message=f"No ticket matching {ticket_id}",
                ticket_id=ticket_id,
                error_code="not_found",
            )
        current_fp = compute_fp(Path(target_ticket.path))
        if current_fp != target_fingerprint:
            return EngineResponse(
                state="preflight_failed",
                message=(
                    "Stale fingerprint — ticket was modified since read. "
                    "Re-run to get a fresh plan."
                ),
                ticket_id=ticket_id,
                error_code="stale_plan",
            )

    # Dispatch
    if action == "create":
        return _execute_create(fields, session_id, request_origin, tickets_dir)
    if action == "update":
        return _execute_update(ticket_id, fields, session_id, request_origin, tickets_dir)
    if action == "close":
        return _execute_close(
            ticket_id,
            fields,
            session_id,
            request_origin,
            tickets_dir,
            dependency_override=dependency_override,
        )
    if action == "reopen":
        return _execute_reopen(ticket_id, fields, session_id, request_origin, tickets_dir)
    return EngineResponse(
        state="escalate",
        message=f"Unknown action: {action!r}",
        error_code="intent_mismatch",
    )


# --- Execute sub-functions ---


def _write_text_exclusive(ticket_path: Path, content: str) -> None:
    """Write a new ticket file exclusively and fsync before returning."""
    encoded = content.encode("utf-8")
    fd = os.open(ticket_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    write_succeeded = False
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError(
                    f"exclusive write failed: short write. Got: {str(ticket_path)!r:.100}"
                )
            view = view[written:]
        os.fsync(fd)
        write_succeeded = True
    finally:
        os.close(fd)
        if not write_succeeded:
            try:
                os.unlink(ticket_path)
            except OSError:
                pass


def preview_target_write(
    *,
    action: str,
    ticket_id: str | None,
    fields: Mapping[str, Any],
    target_sections: Mapping[str, object],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    change_history_entry: ChangeHistoryEntry,
    reserved_ticket_id: str | None = None,
) -> EngineResponse | TargetWritePreview:
    """Render the exact target write without writing a ticket file."""
    if action != "create":
        return EngineResponse(
            state="blocked",
            message=f"Preview failed: unsupported action {action!r}",
            error_code="preview_unsupported",
            ticket_id=ticket_id,
        )
    render_fields = dict(fields)
    for heading, value in target_sections.items():
        engine_key = _CREATE_TARGET_SECTION_MAP.get(heading)
        if engine_key is None:
            return EngineResponse(
                state="blocked",
                message=f"Preview failed: unsupported create target section {heading!r}",
                error_code="preview_unsupported",
                ticket_id=ticket_id,
            )
        render_fields[engine_key] = value
    missing = []
    if not render_fields.get("title"):
        missing.append("title")
    if not render_fields.get("problem"):
        missing.append("problem")
    if missing:
        return EngineResponse(
            state="need_fields",
            message=f"Missing required fields for create: {missing}",
            error_code="need_fields",
        )

    create_shape_errors = _validate_create_status_shape(render_fields)
    if create_shape_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(create_shape_errors)}",
            error_code="need_fields",
            data={"validation_errors": create_shape_errors},
        )

    validation_errors = validate_create_fields(render_fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            data={"validation_errors": validation_errors},
        )

    now = datetime.now(UTC)
    today = now.date()
    title = render_fields.get("title", "Untitled")
    status = render_fields.get("status", "open")
    rendered_history = render_change_history_entry(change_history_entry)

    allocated_ticket_id = reserved_ticket_id or allocate_id(tickets_dir, today)
    try:
        filename = build_filename(allocated_ticket_id, str(title))
    except ValueError as exc:
        return EngineResponse(
            state="invalid_state",
            message=str(exc),
            error_code="invalid_state",
        )
    ticket_path = tickets_dir / filename
    content = render_ticket(
        id=allocated_ticket_id,
        title=title,
        status=status,
        priority=render_fields.get("priority", "normal"),
        related_paths=render_fields.get("related_paths"),
        tags=render_fields.get("tags", []),
        blocked_by=render_fields.get("blocked_by", []),
        problem=render_fields.get("problem", ""),
        captured_request=render_fields.get("captured_request", ""),
        approach=render_fields.get("approach", ""),
        acceptance_criteria=render_fields.get("acceptance_criteria"),
        next_action=render_fields.get("next_action", ""),
        blocked_on=render_fields.get("blocked_on", ""),
        verification=render_fields.get("verification", ""),
        key_files=render_fields.get("key_files"),
        context=render_fields.get("context", ""),
        prior_investigation=render_fields.get("prior_investigation", ""),
        decisions_made=render_fields.get("decisions_made", ""),
        related=render_fields.get("related", ""),
        change_history_entry=rendered_history,
    )
    invalid_render = _invalid_rendered_ticket_response(
        "create",
        ticket_path,
        content,
        ticket_id=allocated_ticket_id,
    )
    if invalid_render is not None:
        return invalid_render
    return TargetWritePreview(
        ticket_path=ticket_path,
        rendered_text=content,
        post_write_fingerprint=target_recovery_fingerprint_for_text(content),
    )


def _execute_create(
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    reserved_ticket_id: str | None = None,
) -> EngineResponse:
    """Create a new ticket file with all required contract fields."""
    if change_history_entry is None:
        change_history_entry = ChangeHistoryEntry(
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            actor="codex",
            reason="Created ticket.",
        )
    tickets_dir.mkdir(parents=True, exist_ok=True)
    attempts = 1 if reserved_ticket_id is not None else _CREATE_WRITE_RETRY_LIMIT
    for _attempt in range(attempts):
        preview = preview_target_write(
            action="create",
            ticket_id=None,
            fields=fields,
            target_sections={},
            session_id=session_id,
            request_origin=request_origin,
            tickets_dir=tickets_dir,
            change_history_entry=change_history_entry,
            reserved_ticket_id=reserved_ticket_id,
        )
        if isinstance(preview, EngineResponse):
            return preview
        ticket_id = reserved_ticket_id or preview.ticket_path.stem
        try:
            _write_text_exclusive(preview.ticket_path, preview.rendered_text)
        except FileExistsError:
            if reserved_ticket_id is not None:
                return EngineResponse(
                    state="invalid_state",
                    message="Reserved create allocation path already exists.",
                    ticket_id=ticket_id,
                    error_code="create_allocation_conflict",
                )
            continue
        except OSError as exc:
            return EngineResponse(
                state="escalate",
                message=f"create failed: {exc}. Got: {str(preview.ticket_path)!r:.100}",
                error_code="io_error",
            )
        return EngineResponse(
            state="ok",
            message=f"Created {ticket_id} at {preview.ticket_path}",
            ticket_id=ticket_id,
            data={"ticket_path": str(preview.ticket_path), "changes": None},
        )

    return EngineResponse(
        state="escalate",
        message=(
            "create failed: exclusive write retry budget exhausted after "
            f"{_CREATE_WRITE_RETRY_LIMIT} attempts. Got: {fields.get('title')!r:.100}"
        ),
        error_code="io_error",
    )


def _evaluate_update_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Return the update-policy rejection response, or None when update may write."""
    legacy_block = _check_legacy_gate(ticket)
    if legacy_block is not None:
        return legacy_block

    validation_errors = validate_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"validation_errors": validation_errors},
        )

    new_status = fields.get("status")
    if new_status and new_status != ticket.status:
        valid_recovery_statuses = (
            []
            if ticket.status in _TERMINAL_STATUSES
            else sorted(_VALID_TRANSITIONS.get(ticket.status, set()))
        )
        requires_reopen = ticket.status in _TERMINAL_STATUSES
        if not _is_valid_transition(ticket.status, new_status, "update"):
            close_hint = (
                " (use close action)"
                if ticket.status in {"open", "blocked"} and new_status in _TERMINAL_STATUSES
                else ""
            )
            return EngineResponse(
                state="invalid_transition",
                message=f"Cannot transition from {ticket.status} to {new_status} via update"
                + close_hint
                + (" (use reopen action)" if requires_reopen else ""),
                ticket_id=ticket_id,
                error_code="invalid_transition",
                data=_transition_policy_data(
                    ticket.status,
                    new_status,
                    valid_recovery_statuses=valid_recovery_statuses,
                    requires_reopen=requires_reopen,
                ),
            )
        precondition_error, precondition_code, precondition_detail = (
            _check_transition_preconditions_with_detail(
                ticket.status,
                new_status,
                ticket,
                tickets_dir,
                fields=fields,
            )
        )
        if precondition_error:
            if precondition_code == "invalid_state":
                reason = (precondition_detail or {}).get("reason", precondition_error)
                return _invalid_ticket_state_response(reason, ticket_id=ticket_id)
            return EngineResponse(
                state="invalid_transition",
                message=precondition_error,
                ticket_id=ticket_id,
                error_code=(
                    "dependency_blocked"
                    if precondition_code == "dependency_blocked"
                    else "invalid_transition"
                ),
                data=_transition_policy_data(
                    ticket.status,
                    new_status,
                    valid_recovery_statuses=valid_recovery_statuses,
                    requires_reopen=requires_reopen,
                    precondition_code=precondition_code,
                    precondition_detail=precondition_detail,
                ),
            )

    (
        _frontmatter_updates,
        section_fields,
        unknown_fields,
        ticket_id_mismatch,
    ) = _classify_update_fields(fields, ticket_id)
    if ticket_id_mismatch:
        return EngineResponse(
            state="escalate",
            message=(
                "Update failed: fields.ticket_id must match top-level "
                f"ticket_id. Got: {fields.get('ticket_id')!r:.100}"
            ),
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )
    section_fields_rejected = section_fields and not _focused_section_fields_allowed(
        fields,
        section_fields,
    )
    if section_fields_rejected or unknown_fields:
        parts: list[str] = []
        if section_fields_rejected:
            parts.append(f"section fields not supported by update: {', '.join(section_fields)}")
        if unknown_fields:
            parts.append(f"unknown fields: {', '.join(unknown_fields)}")
        return EngineResponse(
            state="escalate",
            message=f"Update failed: {'; '.join(parts)}",
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )

    return None


def _execute_update(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    target_sections: Mapping[str, object] | None = None,
) -> EngineResponse:
    """Update an existing ticket's frontmatter fields."""
    if not ticket_id:
        return EngineResponse(
            state="need_fields", message="ticket_id required for update", error_code="need_fields"
        )

    ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
    if invalid_state is not None:
        return invalid_state
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )

    ticket_path = Path(ticket.path)
    original_text = ticket_path.read_text(encoding="utf-8")
    (
        frontmatter_updates,
        section_fields,
        unknown_fields,
        ticket_id_mismatch,
    ) = _classify_update_fields(fields, ticket_id)
    if ticket_id_mismatch:
        return EngineResponse(
            state="escalate",
            message=(
                "Update failed: fields.ticket_id must match top-level "
                f"ticket_id. Got: {fields.get('ticket_id')!r:.100}"
            ),
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )
    section_fields_rejected = section_fields and not _focused_section_fields_allowed(
        fields,
        section_fields,
    )
    if section_fields_rejected or unknown_fields:
        parts: list[str] = []
        if section_fields_rejected:
            parts.append(f"section fields not supported by update: {', '.join(section_fields)}")
        if unknown_fields:
            parts.append(f"unknown fields: {', '.join(unknown_fields)}")
        return EngineResponse(
            state="escalate",
            message=f"Update failed: {'; '.join(parts)}",
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )

    data = dict(ticket.frontmatter)
    sections = dict(ticket.sections)
    changes: dict[str, Any] = {"frontmatter": {}, "sections_changed": []}
    for key, value in frontmatter_updates.items():
        if key in data and data[key] != value:
            changes["frontmatter"][key] = [data[key], value]
        data[key] = value

    for key in section_fields:
        heading = _UPDATE_SECTION_HEADINGS[key]
        rendered = _render_update_section_value(key, fields[key])
        old_rendered = ticket.sections.get(heading, "")
        if rendered is None:
            if heading in ticket.sections:
                changes["sections_changed"].append(heading)
        elif old_rendered.strip() != rendered.strip():
            changes["sections_changed"].append(heading)
        sections[heading] = rendered

    policy_fields = dict(fields)
    if target_sections and "Blocked On" in target_sections:
        policy_fields["blocked_on"] = target_sections["Blocked On"]
    policy_error = _evaluate_update_policy(ticket_id, ticket, policy_fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    for heading, value in (target_sections or {}).items():
        if heading == "Change History" or not validate_target_section_name(heading):
            return EngineResponse(
                state="escalate",
                message=f"Update failed: invalid target section {heading!r}",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
        try:
            rendered = _render_target_section_value(heading, value)
        except ValueError as exc:
            return EngineResponse(
                state="need_fields",
                message=f"Update failed: {exc}",
                ticket_id=ticket_id,
                error_code="need_fields",
            )
        old_rendered = ticket.sections.get(heading, "")
        if rendered is None:
            if heading in ticket.sections:
                changes["sections_changed"].append(heading)
        elif old_rendered.strip() != rendered.strip():
            changes["sections_changed"].append(heading)
        sections[heading] = rendered

    targeted_headings = tuple(_UPDATE_SECTION_HEADINGS[key] for key in section_fields) + tuple(
        (target_sections or {}).keys()
    )
    new_text = _render_target_ticket_text(
        data,
        sections,
        original_text=original_text,
        targeted_headings=targeted_headings,
    )
    if change_history_entry is not None:
        new_text = append_change_history_entry(new_text, change_history_entry)
    invalid_render = _invalid_rendered_ticket_response(
        "update",
        ticket_path,
        new_text,
        ticket_id=ticket_id,
        state="need_fields",
        error_code="need_fields",
    )
    if invalid_render is not None:
        return invalid_render
    ticket_path.write_text(new_text, encoding="utf-8")

    return EngineResponse(
        state="ok",
        message=f"Updated {ticket_id}",
        ticket_id=ticket_id,
        data={"ticket_path": str(ticket_path), "changes": changes},
    )


def _evaluate_close_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
    *,
    dependency_override: bool = False,
) -> EngineResponse | None:
    """Return the close-policy rejection response, or None when close may write."""
    resolution = fields.get("resolution", "done")

    legacy_block = _check_legacy_gate(ticket)
    if legacy_block is not None:
        return legacy_block

    close_fields = dict(fields)
    close_fields["resolution"] = resolution
    validation_errors = validate_fields(close_fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"validation_errors": validation_errors},
        )

    if ticket.status == "idea":
        valid_recovery_statuses = []
    elif ticket.status in _TERMINAL_STATUSES:
        valid_recovery_statuses = []
    elif ticket.status not in {"open", "blocked"}:
        valid_recovery_statuses = ["open", "blocked"]
    else:
        valid_recovery_statuses = ["done", "wontfix"]
    requires_reopen = ticket.status in _TERMINAL_STATUSES

    if ticket.blocked_by and resolution != "wontfix":
        all_tickets, invalid_state = _list_tickets_for_engine(
            tickets_dir,
            ticket_id=ticket_id,
        )
        if invalid_state is not None:
            return invalid_state
        ticket_map = {item.id: item for item in all_tickets}
        missing, unresolved = _classify_blockers(ticket.blocked_by, ticket_map)
        if (missing or unresolved) and not dependency_override:
            blocker_detail = {
                "blocking_ids": unresolved + missing,
                "unresolved_blockers": unresolved,
                "missing_blockers": missing,
            }
            return EngineResponse(
                state="dependency_blocked",
                message=_format_blocker_message(
                    unresolved=unresolved,
                    missing=missing,
                    include_override=True,
                ),
                ticket_id=ticket_id,
                error_code="dependency_blocked",
                data={
                    **_transition_policy_data(
                        ticket.status,
                        resolution,
                        valid_recovery_statuses=valid_recovery_statuses,
                        requires_reopen=requires_reopen,
                        precondition_code="dependency_blocked",
                        precondition_detail=blocker_detail,
                    ),
                    **blocker_detail,
                },
            )

    if not _is_valid_transition(ticket.status, resolution, "close"):
        message = f"Cannot close with resolution {resolution!r} (must be 'done' or 'wontfix')"
        if ticket.status == "idea":
            message += "; promote idea to open first"
        elif requires_reopen:
            message += f" from terminal status {ticket.status!r}"
        elif ticket.status not in {"open", "blocked"}:
            message += (
                f"; status {ticket.status!r} is not closeable; migrate to open or blocked first"
            )
        return EngineResponse(
            state="invalid_transition",
            message=message,
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                resolution,
                valid_recovery_statuses=valid_recovery_statuses,
                requires_reopen=requires_reopen,
            ),
        )

    precondition_error, precondition_code, precondition_detail = (
        _check_transition_preconditions_with_detail(
            ticket.status,
            resolution,
            ticket,
            tickets_dir,
            fields=fields,
        )
    )
    if precondition_error:
        if precondition_code == "invalid_state":
            reason = (precondition_detail or {}).get("reason", precondition_error)
            return _invalid_ticket_state_response(reason, ticket_id=ticket_id)
        return EngineResponse(
            state="invalid_transition",
            message=precondition_error,
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                resolution,
                valid_recovery_statuses=valid_recovery_statuses,
                requires_reopen=requires_reopen,
                precondition_code=precondition_code,
                precondition_detail=precondition_detail,
            ),
        )

    return None


def _close_readiness_data(
    ticket: ParsedTicket,
    *,
    resolution: str,
    ready: bool,
    error_code: str | None = None,
    missing: list[str] | None = None,
    unresolved_blockers: list[str] | None = None,
    missing_blockers: list[str] | None = None,
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Build the read-only close-readiness payload."""
    unresolved = unresolved_blockers or []
    missing_refs = missing_blockers or []
    return {
        "ready": ready,
        "resolution": resolution,
        "status": ticket.status,
        "error_code": error_code,
        "missing": missing or [],
        "blocking_ids": unresolved + missing_refs,
        "unresolved_blockers": unresolved,
        "missing_blockers": missing_refs,
        "allowed_actions": allowed_actions
        or ([f"close as {resolution}"] if ready else ["keep current status"]),
    }


def _close_readiness_from_policy_error(
    ticket: ParsedTicket,
    *,
    resolution: str,
    policy_error: EngineResponse,
) -> dict[str, Any]:
    """Translate the shared close-policy response into read-only UX hints."""
    data = dict(policy_error.data or {})
    precondition_detail = data.get("precondition_detail")
    missing = (
        list(precondition_detail.get("missing", []))
        if isinstance(precondition_detail, dict)
        else []
    )
    if policy_error.error_code == "policy_blocked":
        allowed_actions = ["migrate ticket before close", "keep current status"]
    elif policy_error.error_code == "dependency_blocked":
        allowed_actions = ["resolve blockers", "close as wontfix", "keep current status"]
    elif policy_error.error_code == "need_fields":
        allowed_actions = ["choose done or wontfix", "keep current status"]
    elif ticket.status == "idea":
        allowed_actions = ["promote idea to open before closing", "keep current status"]
    elif ticket.status in _TERMINAL_STATUSES:
        allowed_actions = ["reopen before closing", "keep current status"]
    elif missing:
        allowed_actions = ["add acceptance criteria", "close as wontfix", "keep current status"]
    else:
        allowed_actions = ["choose done or wontfix", "keep current status"]
    readiness = _close_readiness_data(
        ticket,
        resolution=resolution,
        ready=False,
        error_code=policy_error.error_code,
        missing=missing,
        unresolved_blockers=data.get("unresolved_blockers", []),
        missing_blockers=data.get("missing_blockers", []),
        allowed_actions=allowed_actions,
    )
    if "validation_errors" in data:
        readiness["validation_errors"] = data["validation_errors"]
    return readiness


def engine_close_readiness(
    ticket: ParsedTicket,
    tickets_dir: Path,
    *,
    resolution: str = "done",
) -> EngineResponse:
    """Return whether the shared close-policy evaluator would allow this close."""
    fields = {"resolution": resolution}
    policy_error = _evaluate_close_policy(ticket.id, ticket, fields, tickets_dir)
    if policy_error is not None:
        return EngineResponse(
            state=policy_error.state,
            message=policy_error.message,
            ticket_id=ticket.id,
            error_code=policy_error.error_code,
            data=_close_readiness_from_policy_error(
                ticket,
                resolution=resolution,
                policy_error=policy_error,
            ),
        )

    return EngineResponse(
        state="ok",
        message=f"Ticket {ticket.id} is ready to close as {resolution}",
        ticket_id=ticket.id,
        data=_close_readiness_data(ticket, resolution=resolution, ready=True),
    )


def _evaluate_workflow_policy(
    action: str,
    ticket_id: str | None,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Apply read-only execute policy checks for workflow prepare."""
    if action == "create":
        return None
    if not ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {action}",
            error_code="need_fields",
            data={"missing_fields": ["ticket_id"]},
        )

    ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
    if invalid_state is not None:
        return invalid_state
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )
    if action == "update":
        return _evaluate_update_policy(ticket_id, ticket, fields, tickets_dir)
    if action == "close":
        return _evaluate_close_policy(ticket_id, ticket, fields, tickets_dir)
    if action == "reopen":
        return _evaluate_reopen_policy(ticket_id, ticket, fields, tickets_dir)
    return EngineResponse(
        state="escalate",
        message=f"Unknown workflow action: {action!r}",
        error_code="intent_mismatch",
    )


def _evaluate_reopen_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Return the reopen-policy rejection response, or None when reopen may write."""
    reopen_reason = fields.get("reopen_reason", "")
    if not reopen_reason:
        return EngineResponse(
            state="need_fields",
            message="reopen_reason required for reopen",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"missing_fields": ["reopen_reason"]},
        )

    legacy_block = _check_legacy_gate(ticket)
    if legacy_block is not None:
        return legacy_block

    validation_errors = validate_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"validation_errors": validation_errors},
        )

    if not _is_valid_transition(ticket.status, "open", "reopen"):
        return EngineResponse(
            state="invalid_transition",
            message=f"Cannot reopen ticket with status {ticket.status} (must be done or wontfix)",
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                "open",
                valid_recovery_statuses=[],
                requires_reopen=False,
            ),
        )

    return None


def _execute_close(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    dependency_override: bool = False,
    change_history_entry: ChangeHistoryEntry | None = None,
    target_sections: Mapping[str, object] | None = None,
) -> EngineResponse:
    """Close a ticket (set status to done or wontfix, optionally archive).

    Validates transitions with action='close', which allows done/wontfix
    from any non-terminal status.
    """
    if not ticket_id:
        return EngineResponse(
            state="need_fields", message="ticket_id required for close", error_code="need_fields"
        )

    resolution = fields.get("resolution", "done")

    ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
    if invalid_state is not None:
        return invalid_state
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )

    if target_sections:
        if set(target_sections) != {"Blocked On"} or target_sections["Blocked On"] is not None:
            return EngineResponse(
                state="escalate",
                message="Close failed: invalid target section cleanup",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )

    policy_error = _evaluate_close_policy(
        ticket_id,
        ticket,
        fields,
        tickets_dir,
        dependency_override=dependency_override,
    )
    if policy_error is not None:
        return policy_error

    ticket_path = Path(ticket.path)
    original_text = ticket_path.read_text(encoding="utf-8")
    data = dict(ticket.frontmatter)
    sections = dict(ticket.sections)
    old_status = data.get("status", "")
    data["status"] = resolution
    changes_blocked_by = None
    if old_status == "blocked":
        previous_blocked_by = data.get("blocked_by", [])
        if previous_blocked_by:
            changes_blocked_by = [previous_blocked_by, []]
        data["blocked_by"] = []
        sections["Blocked On"] = None

    targeted_headings = ("Blocked On",) if old_status == "blocked" else ()
    new_text = _render_target_ticket_text(
        data,
        sections,
        original_text=original_text,
        targeted_headings=targeted_headings,
    )
    if change_history_entry is not None:
        new_text = append_change_history_entry(new_text, change_history_entry)
    invalid_render = _invalid_rendered_ticket_response(
        "close",
        ticket_path,
        new_text,
        ticket_id=ticket_id,
    )
    if invalid_render is not None:
        return invalid_render
    ticket_path.write_text(new_text, encoding="utf-8")

    changes = {"frontmatter": {"status": [old_status, resolution]}, "sections_changed": []}
    if old_status == "blocked":
        changes["sections_changed"].append("Blocked On")
        if changes_blocked_by is not None:
            changes["frontmatter"]["blocked_by"] = changes_blocked_by

    return EngineResponse(
        state="ok",
        message=f"Closed {ticket_id} (status: {resolution})",
        ticket_id=ticket_id,
        data={"ticket_path": str(ticket_path), "changes": changes},
    )


def _execute_reopen(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
) -> EngineResponse:
    """Reopen a done/wontfix ticket."""
    if not ticket_id:
        return EngineResponse(
            state="need_fields", message="ticket_id required for reopen", error_code="need_fields"
        )

    reopen_reason = fields.get("reopen_reason", "")
    if not reopen_reason:
        return EngineResponse(
            state="need_fields",
            message="reopen_reason required for reopen",
            error_code="need_fields",
        )

    ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
    if invalid_state is not None:
        return invalid_state
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )

    policy_error = _evaluate_reopen_policy(ticket_id, ticket, fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    # Write status change.
    ticket_path = Path(ticket.path)
    original_text = ticket_path.read_text(encoding="utf-8")
    data = dict(ticket.frontmatter)
    sections = dict(ticket.sections)
    old_status = data.get("status", "")
    data["status"] = "open"
    new_text = _render_target_ticket_text(data, sections, original_text=original_text)

    # Append to Reopen History section (newest-last).
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    reopen_entry = f"\n\n## Reopen History\n- **{now}**: {reopen_reason} (by {request_origin})"

    if "## Reopen History" in new_text:
        rh_match = re.search(r"## Reopen History\n", new_text)
        if rh_match:
            next_heading = re.search(r"\n## ", new_text[rh_match.end() :])
            if next_heading:
                insert_pos = rh_match.end() + next_heading.start()
            else:
                insert_pos = len(new_text)
            entry = f"- **{now}**: {reopen_reason} (by {request_origin})\n"
            new_text = new_text[:insert_pos].rstrip() + "\n" + entry + new_text[insert_pos:]
    else:
        new_text += reopen_entry
    if change_history_entry is not None:
        new_text = append_change_history_entry(new_text, change_history_entry)
    invalid_render = _invalid_rendered_ticket_response(
        "reopen",
        ticket_path,
        new_text,
        ticket_id=ticket_id,
    )
    if invalid_render is not None:
        return invalid_render

    try:
        ticket_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        msg = f"reopen write failed: {exc}. Got: {str(ticket_path)!r:.100}"
        return EngineResponse(
            state="escalate",
            message=msg,
            ticket_id=ticket_id,
            error_code="io_error",
        )

    return EngineResponse(
        state="ok",
        message=f"Reopened {ticket_id}. Reason: {reopen_reason}",
        ticket_id=ticket_id,
        data={"ticket_path": str(ticket_path), "changes": {"status": [old_status, "open"]}},
    )
