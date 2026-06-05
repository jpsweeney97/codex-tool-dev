"""Engine-owned autonomous Ticket write gateway."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.ticket_autonomy_config import WORKSPACE_RELATIVE_PATH, ensure_ticket_workspace
from scripts.ticket_autonomy_ids import make_event_id, sha256_fingerprint
from scripts.ticket_autonomy_runtime import (
    AutonomyDecision,
    CandidateMutation,
    CandidateTarget,
    EngineAction,
    EngineDispatch,
    RuntimeDecisionKind,
    map_candidate_to_engine,
)
from scripts.ticket_change_history import ChangeHistoryEntry
from scripts.ticket_dedup import (
    target_fingerprint as compute_target_fingerprint,
)
from scripts.ticket_dedup import (
    target_recovery_fingerprint,
)
from scripts.ticket_engine_core import (
    EngineResponse,
    _execute_close,
    _execute_create,
    _execute_reopen,
    _execute_update,
    _plan_create,
    normalize_target_response,
    preview_target_write,
)
from scripts.ticket_id import allocate_id, build_filename
from scripts.ticket_mutation_identity import make_candidate_mutation_identity
from scripts.ticket_read import InvalidTicketState, find_ticket_by_id
from scripts.ticket_turn_batch import (
    PENDING_SUMMARY_SCHEMA,
    CurrentRecoveryFingerprints,
    PendingSummaryStore,
    VerifiedRepoContext,
    acquire_process_lock,
    event_payload_fingerprint,
    project_mutation_recovery,
    release_process_lock,
)


@dataclass(frozen=True, slots=True)
class GatewayMutation:
    """Gateway-owned target candidate mutation request."""

    action: str
    ticket_id: str | None
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    tickets_dir: Path
    expected_ticket_fingerprint: str | None
    evidence_summary: str


@dataclass(frozen=True, slots=True)
class CreateAllocation:
    """Retained target ID/path allocation for one create candidate."""

    ticket_id: str
    ticket_path: Path


@dataclass(frozen=True, slots=True)
class ExpectedWriteFacts:
    """Recovery facts known before the ticket file write starts."""

    expected_post_write_fingerprint: str
    change_history_entry: dict[str, object]


@dataclass(frozen=True, slots=True)
class RetainedCreateAttempt:
    """Retained allocation plus exact expected create write facts."""

    allocation: CreateAllocation
    expected_write_facts: ExpectedWriteFacts


def _policy_blocked(message: str, *, data: dict[str, object] | None = None) -> EngineResponse:
    return EngineResponse(
        state="blocked",
        message=message,
        error_code="gateway_required",
        data=data or {},
    )


def _invalid_state(
    message: str,
    *,
    ticket_id: str | None = None,
    error_code: str = "invalid_state",
    data: dict[str, object] | None = None,
) -> EngineResponse:
    return EngineResponse(
        state="invalid_state",
        message=message,
        ticket_id=ticket_id,
        error_code=error_code,
        data=data or {},
    )


def _now_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_z(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _pause_reason(project_root: Path) -> str:
    path = project_root / WORKSPACE_RELATIVE_PATH / "pause.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "workspace_paused"
    if isinstance(data, dict) and isinstance(data.get("reason"), str):
        return data["reason"]
    return "workspace_paused"


def _workspace_is_paused(project_root: Path) -> bool:
    return (project_root / WORKSPACE_RELATIVE_PATH / "pause.json").is_file()


def _mutation_fingerprint(mutation: GatewayMutation) -> str:
    return sha256_fingerprint(
        {
            "ticket_id": mutation.ticket_id,
            "action": mutation.action,
            "target": {
                "fields": list(mutation.target.fields),
                "sections": list(mutation.target.sections),
            },
            "proposed_change": dict(mutation.proposed_change),
            "expected_ticket_fingerprint": mutation.expected_ticket_fingerprint,
            "evidence_summary": mutation.evidence_summary,
        }
    )


def _gateway_lock_path(project_root: Path, mutation: GatewayMutation) -> Path:
    if mutation.action == "create":
        key = sha256_fingerprint(
            {
                "lock": "create_allocation",
                "tickets_dir": str(mutation.tickets_dir.resolve()),
            }
        )
    elif mutation.ticket_id:
        key = sha256_fingerprint({"ticket_id": mutation.ticket_id})
    else:
        key = _mutation_fingerprint(mutation)
    filename = f"gateway-write-{key.removeprefix('sha256:')}.lock"
    return project_root / WORKSPACE_RELATIVE_PATH / filename


def _acquire_gateway_write_lock(
    project_root: Path,
    mutation: GatewayMutation,
    *,
    timeout_seconds: float = 2.0,
) -> Path | None:
    workspace = ensure_ticket_workspace(project_root)
    lock_path = _gateway_lock_path(project_root, mutation)
    if lock_path.parent != workspace:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    if not acquire_process_lock(lock_path, timeout_seconds=timeout_seconds):
        return None
    return lock_path


def _release_gateway_write_lock(lock_path: Path | None) -> None:
    release_process_lock(lock_path)


def build_engine_dispatch(mutation: GatewayMutation) -> EngineDispatch:
    """Build deterministic engine dispatch for a gateway target mutation."""
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        target=mutation.target,
        proposed_change=dict(mutation.proposed_change),
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
        evidence_summary=mutation.evidence_summary,
    )
    current_ticket_status: str | None = None
    if mutation.action != "create" and mutation.ticket_id is not None:
        ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id)
        if ticket is not None:
            current_ticket_status = ticket.status
    return map_candidate_to_engine(
        candidate,
        current_ticket_status=current_ticket_status,
    )


def _canonical_target(target: CandidateTarget) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (tuple(sorted(target.fields)), tuple(sorted(target.sections)))


def _decision_error(
    *,
    thread_id: str,
    turn_id: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    if mutation.action == "correct":
        if decision.kind != RuntimeDecisionKind.APPLY_CORRECTION:
            return "decision_mismatch"
    elif decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        return "autonomous_decision_required"
    if decision.mutation_id is None:
        return "mutation_id_required"
    if decision.candidate.ticket_id != mutation.ticket_id:
        return "ticket_mismatch"
    if decision.candidate.action != mutation.action:
        return "action_mismatch"
    if _canonical_target(decision.candidate.target) != _canonical_target(mutation.target):
        return "target_mismatch"
    if dict(decision.candidate.proposed_change) != dict(mutation.proposed_change):
        return "mutation_fingerprint_mismatch"
    if decision.candidate.expected_ticket_fingerprint != mutation.expected_ticket_fingerprint:
        return "expected_ticket_fingerprint_mismatch"
    if decision.candidate.evidence_summary != mutation.evidence_summary:
        return "evidence_summary_mismatch"
    if mutation.action != "create" and mutation.expected_ticket_fingerprint is None:
        return "expected_ticket_fingerprint_required"
    identity = make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        ticket_id=decision.candidate.ticket_id,
        action=decision.candidate.action,
        target=decision.candidate.target,
        proposed_change=decision.candidate.proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
        evidence_summary=decision.candidate.evidence_summary,
    )
    if decision.mutation_id != identity.mutation_id:
        return "mutation_id_mismatch"
    return None


def _validate_expected_ticket_fingerprint(mutation: GatewayMutation) -> EngineResponse | None:
    if mutation.action == "create":
        return None
    if not mutation.ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {mutation.action}",
            error_code="need_fields",
        )
    if mutation.expected_ticket_fingerprint is None:
        return _policy_blocked(f"{mutation.action} requires expected_ticket_fingerprint")
    try:
        ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id)
    except InvalidTicketState as exc:
        return _invalid_state(
            "Ticket state is not target-normalized.",
            ticket_id=mutation.ticket_id,
            data={"reason": str(exc)},
        )
    if ticket is None:
        return _invalid_state(
            message=f"No ticket matching {mutation.ticket_id}",
            ticket_id=mutation.ticket_id,
            error_code="not_found",
        )
    current = compute_target_fingerprint(Path(ticket.path))
    if current != mutation.expected_ticket_fingerprint:
        return _invalid_state(
            message="Stale fingerprint - ticket was modified since validation.",
            ticket_id=mutation.ticket_id,
            error_code="stale_plan",
        )
    return None


def _current_recovery_fingerprints(mutation: GatewayMutation) -> CurrentRecoveryFingerprints:
    if mutation.action == "create" or not mutation.ticket_id:
        return CurrentRecoveryFingerprints(None, None)
    try:
        ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id)
    except InvalidTicketState:
        return CurrentRecoveryFingerprints(None, None)
    if ticket is None:
        return CurrentRecoveryFingerprints(None, None)
    path = Path(ticket.path)
    return CurrentRecoveryFingerprints(
        pre_write_fingerprint=compute_target_fingerprint(path),
        post_write_fingerprint=target_recovery_fingerprint(path),
    )


def _expected_pre_write_fingerprint(
    *,
    mutation: GatewayMutation,
    decision: AutonomyDecision | None,
) -> str | None:
    del decision
    return mutation.expected_ticket_fingerprint


def _change_history_entry_details(entry: ChangeHistoryEntry) -> dict[str, object]:
    return {
        "timestamp": entry.timestamp,
        "actor": entry.actor,
        "reason": entry.reason,
        "corrects": entry.corrects,
    }


def _expected_write_facts_from_details(
    details: Mapping[str, object],
) -> ExpectedWriteFacts | None:
    expected_post = details.get("expected_post_write_fingerprint")
    raw_history = details.get("change_history_entry")
    if not isinstance(expected_post, str) or not expected_post:
        return None
    if not isinstance(raw_history, Mapping):
        return None
    timestamp = raw_history.get("timestamp")
    actor = raw_history.get("actor")
    reason = raw_history.get("reason")
    corrects = raw_history.get("corrects")
    if (
        not isinstance(timestamp, str)
        or not timestamp
        or not isinstance(actor, str)
        or not actor
        or not isinstance(reason, str)
        or not reason
        or (corrects is not None and not isinstance(corrects, str))
    ):
        return None
    return ExpectedWriteFacts(
        expected_post_write_fingerprint=expected_post,
        change_history_entry={
            "timestamp": timestamp,
            "actor": actor,
            "reason": reason,
            "corrects": corrects,
        },
    )


def _change_history_entry_from_expected_facts(
    facts: ExpectedWriteFacts,
) -> ChangeHistoryEntry:
    history = facts.change_history_entry
    return ChangeHistoryEntry(
        timestamp=str(history["timestamp"]),
        actor=str(history["actor"]),
        reason=str(history["reason"]),
        corrects=(str(history["corrects"]) if history.get("corrects") is not None else None),
    )


def _create_allocation_details(
    allocation: CreateAllocation,
    *,
    project_root: Path,
) -> dict[str, object]:
    return {
        "allocated_ticket_id": allocation.ticket_id,
        "allocated_ticket_path": str(allocation.ticket_path.relative_to(project_root)),
        "expected_pre_write_fact": "allocated_target_path_unused",
    }


def _create_allocation_from_details(
    details: Mapping[str, object],
    *,
    project_root: Path,
) -> CreateAllocation | None:
    raw = details.get("create_allocation")
    if not isinstance(raw, Mapping):
        return None
    ticket_id = raw.get("allocated_ticket_id")
    ticket_path = raw.get("allocated_ticket_path")
    pre_fact = raw.get("expected_pre_write_fact")
    if (
        not isinstance(ticket_id, str)
        or not isinstance(ticket_path, str)
        or pre_fact != "allocated_target_path_unused"
    ):
        return None
    path = project_root / ticket_path
    if path.parent != project_root / "docs" / "tickets":
        return None
    if path.name != f"{ticket_id}.md":
        return None
    return CreateAllocation(ticket_id=ticket_id, ticket_path=path)


def _allocate_create_target(
    mutation: GatewayMutation,
) -> tuple[CreateAllocation | None, EngineResponse | None]:
    title = mutation.proposed_change.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, _policy_blocked("create requires title before allocation")
    ticket_id = allocate_id(mutation.tickets_dir, datetime.now(UTC).date())
    try:
        filename = build_filename(ticket_id, title)
    except ValueError as exc:
        return None, _invalid_state(str(exc), error_code="invalid_state")
    ticket_path = mutation.tickets_dir / filename
    if ticket_path.exists():
        return None, _invalid_state(
            message="Create allocation path is already used.",
            ticket_id=ticket_id,
            error_code="create_allocation_conflict",
        )
    return CreateAllocation(ticket_id=ticket_id, ticket_path=ticket_path), None


def _fingerprint_details(
    *,
    mutation: GatewayMutation,
    project_root: Path,
    expected_write_facts: ExpectedWriteFacts,
    create_allocation: CreateAllocation | None = None,
) -> dict[str, object]:
    details: dict[str, object] = {
        "target": {
            "fields": list(mutation.target.fields),
            "sections": list(mutation.target.sections),
        },
        "evidence_summary": mutation.evidence_summary,
        "expected_post_write_fingerprint": (
            expected_write_facts.expected_post_write_fingerprint
        ),
        "change_history_entry": expected_write_facts.change_history_entry,
    }
    if mutation.action == "create":
        if create_allocation is not None:
            details["create_allocation"] = _create_allocation_details(
                create_allocation,
                project_root=project_root,
            )
        return details
    expected_pre = mutation.expected_ticket_fingerprint
    if expected_pre is not None:
        details["expected_pre_write_fingerprint"] = expected_pre
    return details


def _base_event(
    *,
    event_type: str,
    status: str,
    action: str,
    ticket_id: str | None,
    mutation_id: str | None,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    reason: str,
    details: Mapping[str, object],
    timestamp: str | None = None,
) -> dict[str, object]:
    without_id = {
        "schema": PENDING_SUMMARY_SCHEMA,
        "thread_id": thread_id,
        "turn_id": turn_id,
        "event_type": event_type,
        "status": status,
        "action": action,
        "ticket_id": ticket_id,
        "mutation_id": mutation_id,
        "repo_context": repo_context.as_event_payload(),
        "reason": reason,
        "details": dict(details),
    }
    payload_fingerprint = event_payload_fingerprint(without_id)
    event_id = make_event_id(
        schema=PENDING_SUMMARY_SCHEMA,
        event_type=event_type,
        thread_id=thread_id,
        turn_id=turn_id,
        mutation_id=mutation_id,
        status=status,
        action=action,
        ticket_id=ticket_id,
        payload_fingerprint=payload_fingerprint,
    )
    return {"event_id": event_id, "timestamp": timestamp or _now_z(), **without_id}


def _append_event_or_block(
    pending_summary: PendingSummaryStore,
    event: Mapping[str, object],
) -> EngineResponse | None:
    result = pending_summary.append_event(event)
    if result.state in {"appended", "already_recorded"}:
        return None
    return _policy_blocked(
        "Pending-summary bookkeeping failed; automatic ticket mutation paused.",
        data={"pause_reason": result.pause_reason or "pending_summary_unhealthy"},
    )


def _append_gateway_event(
    *,
    pending_summary: PendingSummaryStore,
    event_type: str,
    status: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    reason: str,
    details: Mapping[str, object],
    timestamp: str | None = None,
) -> EngineResponse | None:
    event = _base_event(
        event_type=event_type,
        status=status,
        action=mutation.action,
        ticket_id=mutation.ticket_id,
        mutation_id=decision.mutation_id,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason=reason,
        details=details,
        timestamp=timestamp,
    )
    return _append_event_or_block(pending_summary, event)


def _retained_create_attempt_event(
    *,
    pending_summary: PendingSummaryStore,
    thread_id: str,
    mutation_id: str,
) -> Mapping[str, object] | None:
    for event in reversed(pending_summary.read_events()):
        if event.get("thread_id") != thread_id or event.get("mutation_id") != mutation_id:
            continue
        if event.get("event_type") != "mutation_attempt":
            continue
        return event
    return None


def _retained_create_attempt(
    *,
    pending_summary: PendingSummaryStore,
    thread_id: str,
    mutation_id: str,
    project_root: Path,
) -> RetainedCreateAttempt | None:
    event = _retained_create_attempt_event(
        pending_summary=pending_summary,
        thread_id=thread_id,
        mutation_id=mutation_id,
    )
    if event is None:
        return None
    details = event.get("details")
    if not isinstance(details, Mapping):
        return None
    allocation = _create_allocation_from_details(details, project_root=project_root)
    expected_write_facts = _expected_write_facts_from_details(details)
    if allocation is None or expected_write_facts is None:
        return None
    return RetainedCreateAttempt(
        allocation=allocation,
        expected_write_facts=expected_write_facts,
    )


def _create_recovery_event(
    *,
    reference: Mapping[str, object],
    status: str,
    ticket_id: str,
    reason: str,
    details: Mapping[str, object],
) -> dict[str, object]:
    without_id = {
        "schema": PENDING_SUMMARY_SCHEMA,
        "thread_id": reference["thread_id"],
        "turn_id": reference["turn_id"],
        "event_type": "mutation_status",
        "status": status,
        "action": reference["action"],
        "ticket_id": ticket_id,
        "mutation_id": reference["mutation_id"],
        "repo_context": reference["repo_context"],
        "reason": reason,
        "details": dict(details),
    }
    payload_fingerprint = event_payload_fingerprint(without_id)
    event_id = make_event_id(
        schema=PENDING_SUMMARY_SCHEMA,
        event_type="mutation_status",
        thread_id=str(reference["thread_id"]),
        turn_id=str(reference["turn_id"]),
        mutation_id=str(reference["mutation_id"]),
        status=status,
        action=str(reference["action"]),
        ticket_id=ticket_id,
        payload_fingerprint=payload_fingerprint,
    )
    return {"event_id": event_id, "timestamp": _now_z(), **without_id}


def _existing_mutation_recovery_response(
    *,
    pending_summary: PendingSummaryStore,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
    thread_id: str,
    project_root: Path,
) -> EngineResponse | None:
    if decision.mutation_id is None:
        return _policy_blocked("Decision validation failed: mutation_id_required")
    existing_state = pending_summary.derive_mutation_state(
        thread_id=thread_id,
        mutation_id=decision.mutation_id,
    )
    if existing_state == "no_attempt":
        return None

    if mutation.action == "create" and existing_state == "attempt_recorded":
        retained = _retained_create_attempt(
            pending_summary=pending_summary,
            thread_id=thread_id,
            mutation_id=decision.mutation_id,
            project_root=project_root,
        )
        reference = _retained_create_attempt_event(
            pending_summary=pending_summary,
            thread_id=thread_id,
            mutation_id=decision.mutation_id,
        )
        if retained is None or reference is None:
            return _policy_blocked(
                "Create recovery failed: retained expected write facts missing",
                data={"recovery_state": "create_allocation_missing"},
            )
        if not retained.allocation.ticket_path.is_file():
            return None
        current_post = target_recovery_fingerprint(retained.allocation.ticket_path)
        if current_post != retained.expected_write_facts.expected_post_write_fingerprint:
            return _policy_blocked(
                "Create recovery failed: retained post-write fingerprint mismatch",
                data={"recovery_state": "create_post_write_mismatch"},
            )
        for event in (
            _create_recovery_event(
                reference=reference,
                status="ticket_written",
                ticket_id=retained.allocation.ticket_id,
                reason="Autonomous Ticket file written.",
                details={"post_write_fingerprint": current_post or "unknown"},
            ),
            _create_recovery_event(
                reference=reference,
                status="applied",
                ticket_id=retained.allocation.ticket_id,
                reason="Autonomous Ticket mutation applied.",
                details={},
            ),
        ):
            append_error = _append_event_or_block(pending_summary, event)
            if append_error is not None:
                return append_error
        return _policy_blocked(
            "Approval already used or recovery required: append_missing_ticket_written",
            data={
                "recovery_state": "append_missing_ticket_written",
                "recovery_reason": None,
                "events_appended": 2,
            },
        )

    projection = project_mutation_recovery(
        store=pending_summary,
        thread_id=thread_id,
        mutation_id=decision.mutation_id,
        current_ticket_fingerprints=_current_recovery_fingerprints(mutation),
    )
    if projection.state == "retry_with_same_mutation":
        return None

    for event in projection.events_to_append:
        append_error = _append_event_or_block(pending_summary, event)
        if append_error is not None:
            return append_error

    return _policy_blocked(
        f"Approval already used or recovery required: {projection.state}",
        data={
            "recovery_state": projection.state,
            "recovery_reason": projection.reason,
            "events_appended": len(projection.events_to_append),
        },
    )


_CREATE_SECTION_MAP = {
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


def _create_fields_for_engine(mutation: GatewayMutation) -> tuple[dict[str, object], str | None]:
    fields = {
        key: value
        for key, value in mutation.proposed_change.items()
        if key in mutation.target.fields
    }
    for heading in mutation.target.sections:
        engine_key = _CREATE_SECTION_MAP.get(heading)
        if engine_key is None:
            return {}, f"Unsupported create target section: {heading}"
        fields[engine_key] = mutation.proposed_change[heading]
    return fields, None


def _execute_dispatch(
    *,
    dispatch: EngineDispatch,
    mutation: GatewayMutation,
    thread_id: str,
    change_history_entry: ChangeHistoryEntry,
    create_allocation: CreateAllocation | None = None,
) -> EngineResponse:
    if dispatch.state != "ok" or dispatch.action is None:
        return _policy_blocked(dispatch.reason or "gateway dispatch failed")
    target_sections = dispatch.sections or {}
    if dispatch.action == EngineAction.CREATE:
        fields, create_error = _create_fields_for_engine(mutation)
        if create_error is not None:
            return _policy_blocked(create_error)
        return _execute_create(
            fields,
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            reserved_ticket_id=(
                create_allocation.ticket_id if create_allocation is not None else None
            ),
        )
    if dispatch.action == EngineAction.UPDATE:
        return _execute_update(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
    if dispatch.action == EngineAction.CLOSE:
        return _execute_close(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
    if dispatch.action == EngineAction.REOPEN:
        return _execute_reopen(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
    return _policy_blocked(f"Unsupported dispatch action: {dispatch.action!r}")


def _change_history_reason(action: str) -> str:
    if action == "create":
        return "Created ticket from candidate evidence."
    if action in {"done", "wontfix"}:
        return f"Closed ticket as {action} from candidate evidence."
    if action == "reopen":
        return "Reopened ticket from candidate evidence."
    if action == "correct":
        return "Corrected ticket from candidate evidence."
    return "Updated ticket from candidate evidence."


def _mutation_attempt_timestamp(
    pending_summary: PendingSummaryStore,
    *,
    thread_id: str,
    mutation_id: str,
) -> str | None:
    for event in pending_summary.read_events():
        if event.get("thread_id") != thread_id or event.get("mutation_id") != mutation_id:
            continue
        if event.get("event_type") != "mutation_attempt":
            continue
        timestamp = event.get("timestamp")
        if isinstance(timestamp, str) and _parse_z(timestamp) is not None:
            return timestamp
    return None


def _change_history_entry(action: str, *, timestamp: str | None = None) -> ChangeHistoryEntry:
    return ChangeHistoryEntry(
        timestamp=timestamp or _now_z(),
        actor="codex",
        reason=_change_history_reason(action),
    )


def _validate_autonomous_create_dedup(
    mutation: GatewayMutation,
    *,
    thread_id: str,
) -> EngineResponse | None:
    if mutation.action != "create":
        return None
    fields, create_error = _create_fields_for_engine(mutation)
    if create_error is not None:
        return _policy_blocked(create_error)
    fields.setdefault("priority", "normal")
    plan_response = _plan_create(fields, thread_id, "agent", mutation.tickets_dir)
    if plan_response.state == "ok":
        return None
    if plan_response.state == "duplicate_candidate":
        return plan_response
    return plan_response


def apply_ingest_create(
    *,
    fields: Mapping[str, object],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
) -> EngineResponse:
    """Create a ticket for ingest without exposing the old public stage pipeline."""
    normalized_fields = dict(fields)
    normalized_fields.setdefault("priority", "normal")
    try:
        plan_response = _plan_create(normalized_fields, session_id, request_origin, tickets_dir)
    except InvalidTicketState as exc:
        return _invalid_state(
            "Ticket state is not target-normalized.",
            data={"reason": str(exc)},
        )
    if plan_response.state != "ok":
        return normalize_target_response(plan_response)
    return normalize_target_response(
        _execute_create(
            normalized_fields,
            session_id,
            request_origin,
            tickets_dir,
            change_history_entry=ChangeHistoryEntry(
                timestamp=_now_z(),
                actor="codex",
                reason="Created ticket from ingest envelope.",
            ),
        )
    )


def _response_ok(response: EngineResponse) -> bool:
    return response.state == "ok"


def apply_autonomous_mutation(
    *,
    project_root: Path,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
    pending_summary: PendingSummaryStore,
) -> EngineResponse:
    """Apply one autonomous mutation through the gateway."""
    decision_error = _decision_error(
        thread_id=thread_id,
        turn_id=turn_id,
        mutation=mutation,
        decision=decision,
    )
    if decision_error is not None:
        return normalize_target_response(
            _policy_blocked(f"Decision validation failed: {decision_error}")
        )
    try:
        lock_path = _acquire_gateway_write_lock(project_root, mutation)
    except RuntimeError as exc:
        return normalize_target_response(_policy_blocked(f"Gateway write lock failed: {exc}"))
    if lock_path is None:
        return normalize_target_response(
            _policy_blocked(
                "Gateway write lock failed: lock_timeout",
                data={"pause_reason": "lock_timeout"},
            )
        )
    try:
        return normalize_target_response(
            _apply_autonomous_mutation_locked(
                project_root=project_root,
                thread_id=thread_id,
                turn_id=turn_id,
                repo_context=repo_context,
                mutation=mutation,
                decision=decision,
                pending_summary=pending_summary,
            )
        )
    finally:
        _release_gateway_write_lock(lock_path)


def _apply_autonomous_mutation_locked(
    *,
    project_root: Path,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
    pending_summary: PendingSummaryStore,
) -> EngineResponse:
    existing_state = pending_summary.derive_mutation_state(
        thread_id=thread_id,
        mutation_id=decision.mutation_id,
    )
    if existing_state != "no_attempt":
        recovery_response = _existing_mutation_recovery_response(
            pending_summary=pending_summary,
            mutation=mutation,
            decision=decision,
            thread_id=thread_id,
            project_root=project_root,
        )
        if recovery_response is not None:
            return recovery_response
    change_history_timestamp = (
        _mutation_attempt_timestamp(
            pending_summary,
            thread_id=thread_id,
            mutation_id=decision.mutation_id,
        )
        if existing_state != "no_attempt"
        else None
    )

    target_error = _validate_expected_ticket_fingerprint(mutation)
    if target_error is not None:
        return target_error

    create_allocation: CreateAllocation | None = None
    retained_create_attempt: RetainedCreateAttempt | None = None
    if mutation.action == "create":
        if existing_state == "no_attempt":
            create_error = _validate_autonomous_create_dedup(mutation, thread_id=thread_id)
            if create_error is not None:
                return create_error
            create_allocation, create_allocation_error = _allocate_create_target(mutation)
            if create_allocation_error is not None:
                return create_allocation_error
        else:
            retained_create_attempt = _retained_create_attempt(
                pending_summary=pending_summary,
                thread_id=thread_id,
                mutation_id=decision.mutation_id or "",
                project_root=project_root,
            )
            if retained_create_attempt is None:
                return _policy_blocked(
                    "Create recovery failed: retained expected write facts missing",
                    data={"recovery_state": "create_allocation_missing"},
                )
            create_allocation = retained_create_attempt.allocation

    if _workspace_is_paused(project_root):
        return _policy_blocked(
            "Ticket automation paused for this workspace.",
            data={"pause_reason": _pause_reason(project_root)},
        )

    dispatch = build_engine_dispatch(mutation)
    attempt_timestamp = change_history_timestamp or _now_z()
    if retained_create_attempt is not None:
        change_history_entry = _change_history_entry_from_expected_facts(
            retained_create_attempt.expected_write_facts
        )
    else:
        change_history_entry = _change_history_entry(
            mutation.action,
            timestamp=attempt_timestamp,
        )
    if dispatch.state != "ok" or dispatch.action is None:
        return _policy_blocked(dispatch.reason or "gateway dispatch failed")

    if mutation.action == "create":
        if create_allocation is None:
            return _policy_blocked(
                "Create recovery failed: retained expected write facts missing",
                data={"recovery_state": "create_allocation_missing"},
            )
    preview = preview_target_write(
        action=dispatch.action.value,
        ticket_id=mutation.ticket_id,
        fields=dict(dispatch.fields),
        target_sections=dispatch.sections or {},
        session_id=thread_id,
        request_origin="agent",
        tickets_dir=mutation.tickets_dir,
        change_history_entry=change_history_entry,
        reserved_ticket_id=(
            create_allocation.ticket_id if create_allocation is not None else None
        ),
    )
    if isinstance(preview, EngineResponse):
        return preview

    if retained_create_attempt is not None:
        retained_fingerprint = (
            retained_create_attempt.expected_write_facts.expected_post_write_fingerprint
        )
        if retained_fingerprint != preview.post_write_fingerprint:
            return _policy_blocked(
                "Create recovery failed: retained expected write facts changed",
                data={"recovery_state": "create_expected_write_facts_mismatch"},
            )
        expected_write_facts = retained_create_attempt.expected_write_facts
    else:
        expected_write_facts = ExpectedWriteFacts(
            expected_post_write_fingerprint=preview.post_write_fingerprint,
            change_history_entry=_change_history_entry_details(change_history_entry),
        )

    attempt_details = _fingerprint_details(
        mutation=mutation,
        project_root=project_root,
        expected_write_facts=expected_write_facts,
        create_allocation=create_allocation,
    )

    attempt_error = _append_gateway_event(
        pending_summary=pending_summary,
        event_type="mutation_attempt",
        status="pending",
        mutation=mutation,
        decision=decision,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason=(
            "Apply autonomous Ticket mutation."
            if decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
            else "Apply user-triggered autonomous Ticket correction."
        ),
        details=attempt_details,
        timestamp=attempt_timestamp,
    )
    if attempt_error is not None:
        return attempt_error

    if _workspace_is_paused(project_root):
        return _policy_blocked(
            "Ticket automation paused for this workspace.",
            data={"pause_reason": _pause_reason(project_root)},
        )

    response = _execute_dispatch(
        dispatch=dispatch,
        mutation=mutation,
        thread_id=thread_id,
        change_history_entry=change_history_entry,
        create_allocation=create_allocation,
    )
    if not _response_ok(response):
        _append_gateway_event(
            pending_summary=pending_summary,
            event_type="mutation_status",
            status="failed",
            mutation=mutation,
            decision=decision,
            thread_id=thread_id,
            turn_id=turn_id,
            repo_context=repo_context,
            reason="Autonomous Ticket mutation failed.",
            details={"error_code": response.error_code or "internal_error"},
        )
        return response

    ticket_path_raw = response.data.get("ticket_path")
    if not isinstance(ticket_path_raw, str):
        failed_error = _append_gateway_event(
            pending_summary=pending_summary,
            event_type="mutation_status",
            status="failed",
            mutation=mutation,
            decision=decision,
            thread_id=thread_id,
            turn_id=turn_id,
            repo_context=repo_context,
            reason="Autonomous Ticket mutation returned no ticket path.",
            details={"error_code": "ticket_path_missing"},
        )
        if failed_error is not None:
            return failed_error
        return _policy_blocked(
            "Autonomous Ticket mutation failed: ticket_path_missing",
            data={"error_code": "ticket_path_missing"},
        )

    post_write_fingerprint = target_recovery_fingerprint(Path(ticket_path_raw)) or "unknown"

    ticket_written_error = _append_gateway_event(
        pending_summary=pending_summary,
        event_type="mutation_status",
        status="ticket_written",
        mutation=mutation,
        decision=decision,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason="Autonomous Ticket file written.",
        details={"post_write_fingerprint": post_write_fingerprint},
    )
    if ticket_written_error is not None:
        return ticket_written_error

    applied_error = _append_gateway_event(
        pending_summary=pending_summary,
        event_type="mutation_status",
        status="applied",
        mutation=mutation,
        decision=decision,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason="Autonomous Ticket mutation applied.",
        details={},
    )
    if applied_error is not None:
        return applied_error

    return response
