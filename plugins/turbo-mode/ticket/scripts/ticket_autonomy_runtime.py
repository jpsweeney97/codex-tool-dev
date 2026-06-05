"""Runtime autonomy decisions for Ticket candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from scripts.ticket_mutation_identity import (
    CandidateMutationIdentity,
    make_candidate_mutation_identity,
)
from scripts.ticket_target_schema import validate_target_section_name


class RuntimeDecisionKind(StrEnum):
    """Runtime-first decision kinds."""

    APPLY_AUTONOMOUSLY = "apply_autonomously"
    APPLY_CORRECTION = "apply_correction"
    REQUIRE_USER_DISCUSSION = "require_user_discussion"
    SKIP_DUE_TO_CONFLICT = "skip_due_to_conflict"
    DEFER_UNTIL_RETRY_CONDITION = "defer_until_retry_condition"
    TICKET_UPDATE_BLOCKED = "ticket_update_blocked"


class EngineAction(StrEnum):
    """Engine dispatch actions used by the autonomous gateway."""

    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    REOPEN = "reopen"


@dataclass(frozen=True, slots=True)
class CandidateTarget:
    """User-visible fields and sections a candidate intends to change."""

    fields: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateMutation:
    """A proposed target Ticket mutation candidate."""

    ticket_id: str | None
    action: str
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    expected_ticket_fingerprint: str | None
    evidence_summary: str


@dataclass(frozen=True, slots=True)
class AutonomyIntent:
    """Batch of Ticket mutation candidates from one turn context."""

    action_kind: str
    candidates: tuple[CandidateMutation, ...]
    source_context: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EngineDispatch:
    """Gateway-local dispatch projection for a candidate."""

    state: str
    action: EngineAction | None
    fields: dict[str, object]
    reason: str | None = None
    sections: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class AutonomyDecision:
    """Runtime decision for one candidate."""

    candidate: CandidateMutation
    kind: RuntimeDecisionKind
    mutation_id: str | None
    engine_dispatch: EngineDispatch | None
    reason: str | None
    pending_summary_status: str


_TARGET_FRONTMATTER_FIELDS = frozenset(
    {"title", "status", "priority", "tags", "related_paths", "blocked_by"}
)
_ALLOWED_ACTIONS = frozenset({"create", "update", "done", "wontfix", "reopen", "correct"})
_ALLOWED_CANDIDATE_KEYS = frozenset(
    {
        "action",
        "ticket_id",
        "target",
        "proposed_change",
        "expected_ticket_fingerprint",
        "evidence_summary",
    }
)
_FORBIDDEN_TARGET_SECTIONS = frozenset({"Change History"})
_HARD_DISCUSSION_ACTIONS = frozenset({"archive", "delete", "history_repair"})
_METADATA_ACTIONS = frozenset({"create", "update", "correct"})
_LIFECYCLE_ACTIONS = frozenset({"done", "reopen"})
_UNSAFE_CORRECTION_KEYS = frozenset(
    {
        "delete",
        "archive",
        "history_repair",
        "rewrite_change_history",
        "remove_history_entries",
        "git_history_edit",
    }
)
_CORRECTION_CONTEXT_MAX_AGE = timedelta(days=14)


def _string_tuple(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list | tuple):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item.strip() != item:
            return None
        result.append(item)
    return tuple(result)


def _target_from_mapping(value: object) -> CandidateTarget | None:
    if not isinstance(value, Mapping):
        return None
    if set(value) != {"fields", "sections"}:
        return None
    fields = _string_tuple(value.get("fields"))
    sections = _string_tuple(value.get("sections"))
    if fields is None or sections is None:
        return None
    return CandidateTarget(fields=fields, sections=sections)


def _line_shaped(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and "\n" not in value
        and "\r" not in value
    )


def _target_keys(target: CandidateTarget) -> set[str]:
    return set(target.fields) | set(target.sections)


def _duplicate_names(values: tuple[str, ...]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _candidate_shape_errors(candidate: CandidateMutation) -> list[str]:
    errors: list[str] = []
    if candidate.action not in _ALLOWED_ACTIONS:
        errors.append(f"action must be one of {sorted(_ALLOWED_ACTIONS)!r}")
    if candidate.action == "create":
        if candidate.ticket_id is not None:
            errors.append("ticket_id must be null for create")
        if candidate.expected_ticket_fingerprint is not None:
            errors.append("expected_ticket_fingerprint must be null for create")
    else:
        if not isinstance(candidate.ticket_id, str) or not candidate.ticket_id:
            errors.append(f"ticket_id is required for {candidate.action}")
        if (
            not isinstance(candidate.expected_ticket_fingerprint, str)
            or not candidate.expected_ticket_fingerprint
        ):
            errors.append("expected_ticket_fingerprint is required for non-create writes")
    invalid_fields = sorted(
        field for field in candidate.target.fields if field not in _TARGET_FRONTMATTER_FIELDS
    )
    if invalid_fields:
        errors.append(f"target.fields contains invalid frontmatter fields: {invalid_fields!r}")
    duplicate_fields = _duplicate_names(candidate.target.fields)
    if duplicate_fields:
        errors.append(f"target.fields contains duplicate names: {duplicate_fields!r}")
    duplicate_sections = _duplicate_names(candidate.target.sections)
    if duplicate_sections:
        errors.append(f"target.sections contains duplicate names: {duplicate_sections!r}")
    invalid_sections = sorted(
        section
        for section in candidate.target.sections
        if not validate_target_section_name(section)
    )
    if invalid_sections:
        errors.append(f"target.sections contains invalid section names: {invalid_sections!r}")
    overlapping_names = sorted(set(candidate.target.fields) & set(candidate.target.sections))
    if overlapping_names:
        errors.append(
            "target names cannot appear in both fields and sections: "
            f"{overlapping_names!r}"
        )
    forbidden_sections = sorted(set(candidate.target.sections) & _FORBIDDEN_TARGET_SECTIONS)
    if forbidden_sections:
        errors.append(f"target.sections cannot name kernel-owned sections: {forbidden_sections!r}")
    expected_keys = _target_keys(candidate.target)
    if not expected_keys:
        errors.append("target must name at least one field or section")
    actual_keys = set(candidate.proposed_change)
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        errors.append(
            "proposed_change keys must exactly match target fields and sections; "
            f"missing {missing!r}; extra {extra!r}"
        )
    if not _line_shaped(candidate.evidence_summary):
        errors.append("evidence_summary must be a non-empty single line")
    return errors


def candidate_mapping_errors(item: Mapping[str, object]) -> list[str]:
    unknown = sorted(set(item) - _ALLOWED_CANDIDATE_KEYS)
    if unknown:
        return [f"unknown candidate keys: {unknown!r}"]
    missing = sorted(_ALLOWED_CANDIDATE_KEYS - set(item))
    if missing:
        return [f"missing candidate keys: {missing!r}"]
    errors: list[str] = []
    action = item.get("action")
    ticket_id = item.get("ticket_id")
    expected_ticket_fingerprint = item.get("expected_ticket_fingerprint")
    evidence_summary = item.get("evidence_summary")
    if not isinstance(action, str):
        errors.append("action must be a string")
    if ticket_id is not None and not isinstance(ticket_id, str):
        errors.append("ticket_id must be a string or null")
    if expected_ticket_fingerprint is not None and not isinstance(
        expected_ticket_fingerprint,
        str,
    ):
        errors.append("expected_ticket_fingerprint must be a string or null")
    if not isinstance(evidence_summary, str):
        errors.append("evidence_summary must be a string")
    if errors:
        return errors
    target = _target_from_mapping(item.get("target"))
    if target is None:
        return ["target must contain exactly fields and sections lists"]
    proposed_change = item.get("proposed_change")
    if not isinstance(proposed_change, Mapping):
        return ["proposed_change must be an object"]
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )
    return _candidate_shape_errors(candidate)


def candidate_mutation_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    if candidate_mapping_errors(item):
        return None
    target = _target_from_mapping(item["target"])
    if target is None:
        return None
    proposed_change = item["proposed_change"]
    if not isinstance(proposed_change, Mapping):
        return None
    ticket_id = item["ticket_id"]
    action = item["action"]
    expected_ticket_fingerprint = item["expected_ticket_fingerprint"]
    evidence_summary = item["evidence_summary"]
    if not isinstance(action, str) or not isinstance(evidence_summary, str):
        return None
    if ticket_id is not None and not isinstance(ticket_id, str):
        return None
    if expected_ticket_fingerprint is not None and not isinstance(
        expected_ticket_fingerprint,
        str,
    ):
        return None
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def _target_shape_valid(candidate: CandidateMutation) -> bool:
    return not _candidate_shape_errors(candidate)


def _close_target_is_valid(
    candidate: CandidateMutation,
    resolution: str,
    *,
    current_ticket_status: str | None = None,
) -> bool:
    target_fields = set(candidate.target.fields)
    target_sections = set(candidate.target.sections)
    open_close = target_fields == {"status"} and not target_sections
    blocked_close_cleanup = (
        target_fields == {"status", "blocked_by"}
        and target_sections == {"Blocked On"}
        and candidate.proposed_change.get("blocked_by") == []
        and candidate.proposed_change.get("Blocked On") is None
    )
    if candidate.proposed_change.get("status") != resolution:
        return False
    if current_ticket_status == "blocked":
        return blocked_close_cleanup
    return open_close or blocked_close_cleanup


def _nonempty_target_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _blocked_to_open_target_is_valid(
    candidate: CandidateMutation,
    *,
    current_ticket_status: str | None = None,
) -> bool:
    if current_ticket_status != "blocked" or candidate.proposed_change.get("status") != "open":
        return True
    return (
        set(candidate.target.fields) == {"status", "blocked_by"}
        and set(candidate.target.sections) == {"Blocked On", "Next Action"}
        and candidate.proposed_change.get("blocked_by") == []
        and candidate.proposed_change.get("Blocked On") is None
        and _nonempty_target_text(candidate.proposed_change.get("Next Action"))
    )


def _reopen_target_is_valid(candidate: CandidateMutation) -> bool:
    target_status = candidate.proposed_change.get("status")
    target_fields = set(candidate.target.fields)
    target_sections = set(candidate.target.sections)
    if target_status == "open":
        return target_fields == {"status"} and not target_sections
    if target_status == "blocked":
        return (
            target_fields == {"status", "blocked_by"}
            and target_sections == {"Blocked On"}
            and isinstance(candidate.proposed_change.get("blocked_by"), list)
            and _nonempty_target_text(candidate.proposed_change.get("Blocked On"))
        )
    return False


def map_candidate_to_engine(
    candidate: CandidateMutation,
    *,
    gateway_approved: bool = True,
    current_ticket_status: str | None = None,
) -> EngineDispatch:
    """Map one target-shaped candidate to deterministic engine dispatch."""
    if not _target_shape_valid(candidate):
        return EngineDispatch("policy_blocked", None, {}, reason="target_closure_failed")
    fields = {
        key: value
        for key, value in candidate.proposed_change.items()
        if key in candidate.target.fields
    }
    sections = {
        key: value
        for key, value in candidate.proposed_change.items()
        if key in candidate.target.sections
    }
    if candidate.action == "done":
        if not _close_target_is_valid(
            candidate,
            "done",
            current_ticket_status=current_ticket_status,
        ):
            return EngineDispatch(
                "policy_blocked",
                None,
                {},
                reason="close_target_not_allowlisted",
            )
        return EngineDispatch(
            "ok",
            EngineAction.CLOSE,
            {"resolution": "done"},
            sections=sections,
        )
    if candidate.action == "wontfix":
        if not _close_target_is_valid(
            candidate,
            "wontfix",
            current_ticket_status=current_ticket_status,
        ):
            return EngineDispatch(
                "policy_blocked",
                None,
                {},
                reason="close_target_not_allowlisted",
            )
        return EngineDispatch(
            "ok",
            EngineAction.CLOSE,
            {"resolution": "wontfix"},
            sections=sections,
        )
    if candidate.action == "reopen":
        if not gateway_approved:
            return EngineDispatch("policy_blocked", None, {}, reason="gateway_required")
        if fields.get("status") not in {"open", "blocked"}:
            return EngineDispatch("policy_blocked", None, {}, reason="reopen_status_required")
        if not _reopen_target_is_valid(candidate):
            return EngineDispatch(
                "policy_blocked",
                None,
                {},
                reason="reopen_target_not_allowlisted",
            )
        return EngineDispatch("ok", EngineAction.REOPEN, fields, sections=sections)
    if candidate.action == "correct":
        if fields.get("status") in {"done", "wontfix"}:
            if not _close_target_is_valid(
                candidate,
                str(fields["status"]),
                current_ticket_status=current_ticket_status,
            ):
                return EngineDispatch(
                    "policy_blocked",
                    None,
                    {},
                    reason="close_target_not_allowlisted",
                )
            return EngineDispatch(
                "ok",
                EngineAction.CLOSE,
                {"resolution": fields["status"]},
                sections=sections,
            )
        if fields.get("status") in {"open", "blocked"}:
            if current_ticket_status in {"done", "wontfix"}:
                if not _reopen_target_is_valid(candidate):
                    return EngineDispatch(
                        "policy_blocked",
                        None,
                        {},
                        reason="reopen_target_not_allowlisted",
                    )
                return EngineDispatch("ok", EngineAction.REOPEN, fields, sections=sections)
            if not _blocked_to_open_target_is_valid(
                candidate,
                current_ticket_status=current_ticket_status,
            ):
                return EngineDispatch(
                    "policy_blocked",
                    None,
                    {},
                    reason="blocked_to_open_target_not_allowlisted",
                )
            return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
        return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
    if candidate.action == "update":
        if not _blocked_to_open_target_is_valid(
            candidate,
            current_ticket_status=current_ticket_status,
        ):
            return EngineDispatch(
                "policy_blocked",
                None,
                {},
                reason="blocked_to_open_target_not_allowlisted",
            )
        return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
    if candidate.action == "create":
        return EngineDispatch("ok", EngineAction.CREATE, fields, sections=sections)
    return EngineDispatch("policy_blocked", None, {}, reason="unsupported_action")


def _requires_discussion(candidate: CandidateMutation) -> bool:
    return bool(candidate.proposed_change.get("requires_discussion"))


def _unsafe_correction(candidate: CandidateMutation) -> bool:
    return bool(_UNSAFE_CORRECTION_KEYS & set(candidate.proposed_change))


def _parse_z(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


def _canonical_target_key(target: CandidateTarget) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (tuple(sorted(target.fields)), tuple(sorted(target.sections)))


def _canonical_context_target(value: object) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    if not isinstance(value, Mapping):
        return None
    fields = value.get("fields")
    sections = value.get("sections")
    if not isinstance(fields, list) or not isinstance(sections, list):
        return None
    if not all(isinstance(field, str) for field in fields):
        return None
    if not all(isinstance(section, str) for section in sections):
        return None
    return (tuple(sorted(fields)), tuple(sorted(sections)))


def _correction_detail_available(
    candidate: CandidateMutation,
    source_context: Mapping[str, object],
    *,
    now: datetime,
    max_age: timedelta = _CORRECTION_CONTEXT_MAX_AGE,
) -> bool:
    contexts = source_context.get("recent_correction_context")
    if not isinstance(contexts, Mapping) or candidate.ticket_id is None:
        return False
    context = contexts.get(candidate.ticket_id)
    if not isinstance(context, Mapping):
        return False
    if context.get("correction_ready") is not True:
        return False
    if context.get("correction_detail_retained") is not True:
        return False
    if not isinstance(context.get("source_mutation_id"), str):
        return False
    retained_at = _parse_z(context.get("retained_at"))
    if retained_at is None:
        return False
    if retained_at < now - max_age:
        return False
    if context.get("expected_ticket_fingerprint") != candidate.expected_ticket_fingerprint:
        return False
    proposed_change = context.get("proposed_change")
    if not isinstance(proposed_change, Mapping):
        return False
    if dict(proposed_change) != dict(candidate.proposed_change):
        return False
    return _canonical_context_target(context.get("target")) == _canonical_target_key(
        candidate.target
    )


def _identity_for_candidate(
    *,
    candidate: CandidateMutation,
    thread_id: str,
    turn_id: str,
) -> CandidateMutationIdentity:
    return make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        target=candidate.target,
        proposed_change=candidate.proposed_change,
        expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
        evidence_summary=candidate.evidence_summary,
    )


def _decision(
    candidate: CandidateMutation,
    kind: RuntimeDecisionKind,
    *,
    reason: str,
    pending_summary_status: str,
    mutation_id: str | None = None,
    engine_dispatch: EngineDispatch | None = None,
) -> AutonomyDecision:
    return AutonomyDecision(
        candidate=candidate,
        kind=kind,
        mutation_id=mutation_id,
        engine_dispatch=engine_dispatch,
        reason=reason,
        pending_summary_status=pending_summary_status,
    )


def _fanout_key(action: str) -> str:
    if action in _METADATA_ACTIONS:
        return "metadata"
    if action in _LIFECYCLE_ACTIONS:
        return "lifecycle"
    return action


def _fanout_cap(action: str, source_context: Mapping[str, object]) -> int:
    key = _fanout_key(action)
    if key == "metadata":
        return 5
    if key == "lifecycle":
        return 2 if source_context.get("explicit_linked_batch") else 1
    if action == "wontfix":
        return 5 if source_context.get("shared_decision_evidence") else 0
    return 1


def evaluate_autonomy_intent(
    intent: AutonomyIntent,
    *,
    current_mode: str,
    thread_id: str,
    turn_id: str,
    now: datetime | None = None,
) -> tuple[AutonomyDecision, ...]:
    """Evaluate candidate mutations against runtime-first hard rules.

    Args:
        intent: Candidate batch from the current turn.
        current_mode: Thread-scoped automation mode.
        thread_id: Current Codex thread identifier.
        turn_id: Current turn identifier.
        now: Reserved call-site timestamp for deterministic tests.

    Returns:
        One decision per candidate, preserving candidate order.
    """
    runtime_now = now or datetime.now(UTC)
    applied_counts: dict[str, int] = defaultdict(int)
    decisions: list[AutonomyDecision] = []

    for candidate in intent.candidates:
        if candidate.action in _HARD_DISCUSSION_ACTIONS or _requires_discussion(candidate):
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="discussion_required",
                    pending_summary_status="discussion_required",
                )
            )
            continue
        if current_mode == "discussion_only":
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="discussion_only",
                    pending_summary_status="discussion_required",
                )
            )
            continue
        if current_mode != "agent_primary":
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="unsupported_mode",
                    pending_summary_status="discussion_required",
                )
            )
            continue
        if candidate.action == "correct":
            shape_errors = _candidate_shape_errors(candidate)
            if shape_errors:
                decisions.append(
                    _decision(
                        candidate,
                        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                        reason="target_closure_failed",
                        pending_summary_status="discussion_required",
                    )
                )
                continue
            if _unsafe_correction(candidate):
                decisions.append(
                    _decision(
                        candidate,
                        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                        reason="unsafe_correction",
                        pending_summary_status="discussion_required",
                    )
                )
                continue
            if not _correction_detail_available(
                candidate,
                intent.source_context,
                now=runtime_now,
            ):
                decisions.append(
                    _decision(
                        candidate,
                        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                        reason="correction_detail_missing",
                        pending_summary_status="discussion_required",
                    )
                )
                continue

        if candidate.action != "create" and candidate.expected_ticket_fingerprint is None:
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.TICKET_UPDATE_BLOCKED,
                    reason="expected_ticket_fingerprint_required",
                    pending_summary_status="ticket_update_blocked",
                    mutation_id=None,
                )
            )
            continue

        fanout_key = _fanout_key(candidate.action)
        if applied_counts[fanout_key] >= _fanout_cap(candidate.action, intent.source_context):
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="fanout_cap_exceeded",
                    pending_summary_status="discussion_required",
                )
            )
            continue

        dispatch = map_candidate_to_engine(candidate)
        if dispatch.state != "ok":
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason=dispatch.reason or "policy_blocked",
                    pending_summary_status="discussion_required",
                    engine_dispatch=dispatch,
                )
            )
            continue
        identity = _identity_for_candidate(
            candidate=candidate,
            thread_id=thread_id,
            turn_id=turn_id,
        )
        applied_counts[fanout_key] += 1
        decisions.append(
            _decision(
                candidate,
                RuntimeDecisionKind.APPLY_CORRECTION
                if candidate.action == "correct"
                else RuntimeDecisionKind.APPLY_AUTONOMOUSLY,
                reason=(
                    "correction_detail_retained"
                    if candidate.action == "correct"
                    else "authorized"
                ),
                pending_summary_status="pending",
                mutation_id=identity.mutation_id,
                engine_dispatch=dispatch,
            )
        )

    return tuple(decisions)
