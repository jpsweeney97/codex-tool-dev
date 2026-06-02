"""Runtime autonomy decisions for Ticket candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from scripts.ticket_autonomy_ids import (
    make_approval_id,
    make_mutation_id,
    sha256_fingerprint,
)


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


TicketChangeScope = Literal["current_branch", "unrelated_backlog"]


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    """Evidence that connects a turn candidate to a ticket."""

    kind: str
    ref: str
    freshness: Literal["fresh", "stale"] = "fresh"


@dataclass(frozen=True, slots=True)
class CandidateMutation:
    """A proposed Ticket mutation candidate."""

    ticket_id: str | None
    action: str
    proposed_change: Mapping[str, object]
    evidence: tuple[EvidenceLink, ...]
    conflict_reason: str | None = None
    ticket_change_scope: TicketChangeScope = "current_branch"


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


@dataclass(frozen=True, slots=True)
class AutonomyDecision:
    """Runtime decision for one candidate."""

    candidate: CandidateMutation
    kind: RuntimeDecisionKind
    mutation_id: str | None
    approval: dict[str, object] | None
    engine_dispatch: EngineDispatch | None
    reason: str | None
    pending_summary_status: str


_HARD_DISCUSSION_ACTIONS = frozenset({"archive", "delete", "history_repair"})
_METADATA_ACTIONS = frozenset({"create", "update", "reprioritize", "stale_cleanup", "correction"})
_BLOCKER_REFINEMENT_ACTIONS = frozenset({"blocker_edit", "refine"})
_LIFECYCLE_ACTIONS = frozenset({"done", "reopen"})
_UPDATE_ACTIONS = frozenset({"update", "reprioritize", "stale_cleanup", "correction"}) | (
    _BLOCKER_REFINEMENT_ACTIONS
)
_CLOSE_FIELDS = frozenset({"resolution"})
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


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _evidence_payload(candidate: CandidateMutation) -> list[dict[str, str]]:
    return [
        {"kind": evidence.kind, "ref": evidence.ref, "freshness": evidence.freshness}
        for evidence in candidate.evidence
    ]


def _fresh_evidence(candidate: CandidateMutation) -> tuple[EvidenceLink, ...]:
    return tuple(evidence for evidence in candidate.evidence if evidence.freshness == "fresh")


def _has_evidence_kind(candidate: CandidateMutation, *kinds: str) -> bool:
    allowed = set(kinds)
    return any(
        evidence.kind in allowed and evidence.freshness == "fresh"
        for evidence in candidate.evidence
    )


def _ticket_state_fingerprint(
    candidate: CandidateMutation,
    source_context: Mapping[str, object],
) -> str:
    fingerprints = source_context.get("ticket_state_fingerprints")
    if isinstance(fingerprints, Mapping) and isinstance(candidate.ticket_id, str):
        value = fingerprints.get(candidate.ticket_id)
        if isinstance(value, str) and value:
            return value
    value = candidate.proposed_change.get("ticket_state_fingerprint")
    if isinstance(value, str) and value:
        return value
    return "unknown"


def _candidate_payload(candidate: CandidateMutation) -> dict[str, object]:
    return {
        "ticket_id": candidate.ticket_id,
        "action": candidate.action,
        "proposed_change": dict(candidate.proposed_change),
        "ticket_change_scope": candidate.ticket_change_scope,
    }


def _make_approval(
    *,
    candidate: CandidateMutation,
    decision_kind: RuntimeDecisionKind,
    mutation_id: str,
    mutation_fingerprint: str,
    evidence_fingerprint: str,
    ticket_state_fingerprint: str,
    current_mode: str,
    thread_id: str,
    now: datetime,
) -> dict[str, object]:
    ticket_id = candidate.ticket_id or "__new_ticket__"
    approval_id = make_approval_id(
        schema="codex.ticket.approval.v1",
        thread_id=thread_id,
        ticket_id=ticket_id,
        mutation_id=mutation_id,
        mutation_fingerprint=mutation_fingerprint,
        ticket_state_fingerprint=ticket_state_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        current_mode=current_mode,
        decision=decision_kind.value,
    )
    return {
        "schema": "codex.ticket.approval.v1",
        "approval_id": approval_id,
        "thread_id": thread_id,
        "ticket_id": candidate.ticket_id,
        "mutation_id": mutation_id,
        "current_mode": current_mode,
        "decision": decision_kind.value,
        "ticket_state_fingerprint": ticket_state_fingerprint,
        "mutation_fingerprint": mutation_fingerprint,
        "evidence_fingerprint": evidence_fingerprint,
        "created_at": _iso_z(now),
        "expires_at": _iso_z(now + timedelta(minutes=10)),
    }


def _decision(
    candidate: CandidateMutation,
    kind: RuntimeDecisionKind,
    *,
    reason: str,
    pending_summary_status: str,
    mutation_id: str | None = None,
    approval: dict[str, object] | None = None,
    engine_dispatch: EngineDispatch | None = None,
) -> AutonomyDecision:
    return AutonomyDecision(
        candidate=candidate,
        kind=kind,
        mutation_id=mutation_id,
        approval=approval,
        engine_dispatch=engine_dispatch,
        reason=reason,
        pending_summary_status=pending_summary_status,
    )


def _candidate_has_conflict(candidate: CandidateMutation) -> bool:
    return candidate.conflict_reason is not None or any(
        evidence.kind == "conflicting" for evidence in candidate.evidence
    )


def _requires_discussion(candidate: CandidateMutation) -> bool:
    return bool(candidate.proposed_change.get("requires_discussion"))


def _close_fields_are_allowlisted(candidate: CandidateMutation, resolution: str) -> bool:
    if "archive" in candidate.proposed_change:
        return False
    unknown = set(candidate.proposed_change) - _CLOSE_FIELDS
    if unknown:
        return False
    proposed_resolution = candidate.proposed_change.get("resolution")
    return proposed_resolution in {None, resolution}


def _evidence_floor_met(candidate: CandidateMutation, source_context: Mapping[str, object]) -> bool:
    if not _fresh_evidence(candidate):
        return False
    if candidate.action == "wontfix":
        return bool(source_context.get("shared_decision_evidence")) or _has_evidence_kind(
            candidate,
            "user_decision",
            "product_decision",
        )
    if candidate.action in {"done", "reopen"}:
        return _has_evidence_kind(candidate, "ticket_state") and _has_evidence_kind(
            candidate,
            "current_thread_reason",
        )
    if candidate.action in _BLOCKER_REFINEMENT_ACTIONS:
        if _has_evidence_kind(candidate, "explicit_ticket"):
            return True
        return _has_evidence_kind(candidate, "file_path") and _has_evidence_kind(
            candidate,
            "current_thread_reason",
        )
    return True


def _fanout_key(action: str) -> str:
    if action in _METADATA_ACTIONS:
        return "metadata"
    if action in _BLOCKER_REFINEMENT_ACTIONS:
        return "blocker_refinement"
    if action in _LIFECYCLE_ACTIONS:
        return "lifecycle"
    return action


def _fanout_cap(action: str, source_context: Mapping[str, object]) -> int:
    key = _fanout_key(action)
    if key == "metadata":
        return 5
    if key == "blocker_refinement":
        return 3
    if key == "lifecycle":
        return 2 if source_context.get("explicit_linked_batch") else 1
    if action == "wontfix":
        return 5 if source_context.get("shared_decision_evidence") else 0
    return 1


def map_candidate_to_engine(
    candidate: CandidateMutation,
    *,
    gateway_approved: bool = True,
) -> EngineDispatch:
    """Map one Ticket-facing candidate to deterministic engine dispatch.

    Args:
        candidate: Candidate to dispatch.
        gateway_approved: Whether the call is through the autonomous gateway.

    Returns:
        Dispatch projection. Policy-blocked results do not authorize writes.
    """
    fields = dict(candidate.proposed_change)
    if candidate.action == "done":
        if not _close_fields_are_allowlisted(candidate, "done"):
            return EngineDispatch("policy_blocked", None, {}, "close_fields_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "done"})
    if candidate.action == "wontfix":
        if not _close_fields_are_allowlisted(candidate, "wontfix"):
            return EngineDispatch("policy_blocked", None, {}, "close_fields_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "wontfix"})
    if candidate.action == "reopen":
        if not gateway_approved:
            return EngineDispatch("policy_blocked", None, {}, "gateway_required")
        reopen_reason = fields.get("reopen_reason")
        if not isinstance(reopen_reason, str) or not reopen_reason.strip():
            return EngineDispatch("policy_blocked", None, {}, "reopen_reason_required")
        if set(fields) != {"reopen_reason"}:
            return EngineDispatch("policy_blocked", None, {}, "reopen_fields_not_allowlisted")
        return EngineDispatch("ok", EngineAction.REOPEN, {"reopen_reason": reopen_reason})
    if candidate.action == "correction" and fields.get("resolution") in {"done", "wontfix"}:
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": fields["resolution"]})
    if candidate.action in _UPDATE_ACTIONS:
        return EngineDispatch("ok", EngineAction.UPDATE, fields)
    if candidate.action == "create":
        return EngineDispatch("ok", EngineAction.CREATE, fields)
    return EngineDispatch("policy_blocked", None, {}, "unsupported_action")


def _unsafe_correction(candidate: CandidateMutation) -> bool:
    return bool(_UNSAFE_CORRECTION_KEYS & set(candidate.proposed_change))


def _correction_detail_available(candidate: CandidateMutation) -> bool:
    return _has_evidence_kind(candidate, "correction_detail")


def _mutation_id_for_candidate(
    *,
    candidate: CandidateMutation,
    thread_id: str,
    turn_id: str,
) -> tuple[str, str, str]:
    mutation_fingerprint = sha256_fingerprint(_candidate_payload(candidate))
    evidence_fingerprint = sha256_fingerprint(_evidence_payload(candidate))
    mutation_id = make_mutation_id(
        schema="codex.ticket.mutation.v1",
        thread_id=thread_id,
        turn_id=turn_id,
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    return mutation_id, mutation_fingerprint, evidence_fingerprint


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
        now: Approval creation time. Defaults to current UTC time.

    Returns:
        One decision per candidate, preserving candidate order.
    """
    decision_time = now or datetime.now(UTC)
    applied_counts: dict[str, int] = defaultdict(int)
    decisions: list[AutonomyDecision] = []

    for candidate in intent.candidates:
        if _candidate_has_conflict(candidate):
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.SKIP_DUE_TO_CONFLICT,
                    reason=candidate.conflict_reason or "conflicting_evidence",
                    pending_summary_status="skipped",
                )
            )
            continue
        if candidate.action == "correction":
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
            if not _correction_detail_available(candidate):
                decisions.append(
                    _decision(
                        candidate,
                        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                        reason="correction_detail_missing",
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
            mutation_id, _mutation_fingerprint, _evidence_fingerprint = (
                _mutation_id_for_candidate(
                    candidate=candidate,
                    thread_id=thread_id,
                    turn_id=turn_id,
                )
            )
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.APPLY_CORRECTION,
                    reason="correction_detail_retained",
                    pending_summary_status="pending",
                    mutation_id=mutation_id,
                    approval=None,
                    engine_dispatch=dispatch,
                )
            )
            continue
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
        if candidate.action in {"done", "wontfix"} and not _close_fields_are_allowlisted(
            candidate,
            candidate.action,
        ):
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="close_fields_not_allowlisted",
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
        if not _evidence_floor_met(candidate, intent.source_context):
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="evidence_floor_not_met",
                    pending_summary_status="discussion_required",
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

        mutation_id, mutation_fingerprint, evidence_fingerprint = _mutation_id_for_candidate(
            candidate=candidate,
            thread_id=thread_id,
            turn_id=turn_id,
        )
        ticket_state_fingerprint = _ticket_state_fingerprint(candidate, intent.source_context)
        approval = _make_approval(
            candidate=candidate,
            decision_kind=RuntimeDecisionKind.APPLY_AUTONOMOUSLY,
            mutation_id=mutation_id,
            mutation_fingerprint=mutation_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            ticket_state_fingerprint=ticket_state_fingerprint,
            current_mode=current_mode,
            thread_id=thread_id,
            now=decision_time,
        )
        applied_counts[fanout_key] += 1
        decisions.append(
            _decision(
                candidate,
                RuntimeDecisionKind.APPLY_AUTONOMOUSLY,
                reason="approved",
                pending_summary_status="pending",
                mutation_id=mutation_id,
                approval=approval,
                engine_dispatch=dispatch,
            )
        )

    return tuple(decisions)
