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
    EngineAction,
    EngineDispatch,
    RuntimeDecisionKind,
    map_candidate_to_engine,
)
from scripts.ticket_change_history import (
    ChangeHistoryEntry,
    ChangeHistoryLabel,
)
from scripts.ticket_dedup import target_fingerprint as compute_target_fingerprint
from scripts.ticket_engine_core import (
    EngineResponse,
    _execute_close,
    _execute_create,
    _execute_reopen,
    _execute_update,
    _plan_create,
)
from scripts.ticket_mutation_identity import make_candidate_mutation_identity
from scripts.ticket_read import find_ticket_by_id
from scripts.ticket_turn_batch import (
    PENDING_SUMMARY_SCHEMA,
    PendingSummaryStore,
    VerifiedRepoContext,
    acquire_process_lock,
    event_payload_fingerprint,
    project_mutation_recovery,
    release_process_lock,
)


@dataclass(frozen=True, slots=True)
class GatewayMutation:
    """Gateway-owned mutation request."""

    action: str
    ticket_id: str | None
    fields: Mapping[str, object]
    tickets_dir: Path
    target_fingerprint: str | None


def _policy_blocked(message: str, *, data: dict[str, object] | None = None) -> EngineResponse:
    return EngineResponse(
        state="policy_blocked",
        message=message,
        error_code="gateway_required",
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
            "proposed_change": dict(mutation.fields),
        }
    )


def _gateway_lock_path(project_root: Path, mutation: GatewayMutation) -> Path:
    key = _mutation_fingerprint(mutation)
    if mutation.action != "create" and mutation.ticket_id:
        key = sha256_fingerprint({"ticket_id": mutation.ticket_id})
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
    """Build deterministic engine dispatch for a gateway mutation."""
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        proposed_change=dict(mutation.fields),
        evidence=(),
    )
    return map_candidate_to_engine(candidate)


def _candidate_evidence_payload(candidate: CandidateMutation) -> list[dict[str, str]]:
    return [
        {"kind": evidence.kind, "ref": evidence.ref, "freshness": evidence.freshness}
        for evidence in candidate.evidence
    ]


def _decision_error(
    *,
    thread_id: str,
    turn_id: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    if decision.kind == RuntimeDecisionKind.APPLY_CORRECTION:
        if mutation.action != "correction" or decision.candidate.action != "correction":
            return "decision_mismatch"
    elif decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        return "autonomous_decision_required"
    if decision.mutation_id is None:
        return "mutation_id_required"
    if decision.candidate.ticket_id != mutation.ticket_id:
        return "ticket_mismatch"
    if decision.candidate.action != mutation.action:
        return "action_mismatch"
    if dict(decision.candidate.proposed_change) != dict(mutation.fields):
        return "mutation_fingerprint_mismatch"
    if mutation.action != "create" and mutation.target_fingerprint is None:
        return "target_fingerprint_required"
    identity = make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        ticket_id=decision.candidate.ticket_id,
        action=decision.candidate.action,
        proposed_change=decision.candidate.proposed_change,
        target_fingerprint=mutation.target_fingerprint,
        evidence=_candidate_evidence_payload(decision.candidate),
    )
    if decision.mutation_id != identity.mutation_id:
        return "mutation_id_mismatch"
    return None


def _validate_target_fingerprint(mutation: GatewayMutation) -> EngineResponse | None:
    if mutation.action == "create":
        return None
    if not mutation.ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {mutation.action}",
            error_code="need_fields",
        )
    if mutation.target_fingerprint is None:
        return _policy_blocked(f"{mutation.action} requires target_fingerprint")
    ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id, include_closed=True)
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {mutation.ticket_id}",
            ticket_id=mutation.ticket_id,
            error_code="not_found",
        )
    current = compute_target_fingerprint(Path(ticket.path))
    if current != mutation.target_fingerprint:
        return EngineResponse(
            state="preflight_failed",
            message="Stale fingerprint - ticket was modified since validation.",
            ticket_id=mutation.ticket_id,
            error_code="stale_plan",
        )
    return None


def _current_ticket_fingerprint(mutation: GatewayMutation) -> str | None:
    if mutation.action == "create" or not mutation.ticket_id:
        return None
    ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id, include_closed=True)
    if ticket is None:
        return None
    return compute_target_fingerprint(Path(ticket.path))


def _expected_pre_write_fingerprint(
    *,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    del decision
    return mutation.target_fingerprint


def _fingerprint_details(
    *,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> dict[str, object]:
    expected_pre = _expected_pre_write_fingerprint(mutation=mutation, decision=decision)
    return {"expected_pre_write_fingerprint": expected_pre} if expected_pre is not None else {}


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
    return {"event_id": event_id, "timestamp": _now_z(), **without_id}


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
    )
    return _append_event_or_block(pending_summary, event)


def _existing_mutation_recovery_response(
    *,
    pending_summary: PendingSummaryStore,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
    thread_id: str,
) -> EngineResponse | None:
    if decision.mutation_id is None:
        return _policy_blocked("Decision validation failed: mutation_id_required")
    existing_state = pending_summary.derive_mutation_state(
        thread_id=thread_id,
        mutation_id=decision.mutation_id,
    )
    if existing_state == "no_attempt":
        return None

    projection = project_mutation_recovery(
        store=pending_summary,
        thread_id=thread_id,
        mutation_id=decision.mutation_id,
        current_ticket_fingerprint=_current_ticket_fingerprint(mutation),
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


def _execute_dispatch(
    *,
    dispatch: EngineDispatch,
    mutation: GatewayMutation,
    thread_id: str,
    change_history_entry: ChangeHistoryEntry,
) -> EngineResponse:
    if dispatch.state != "ok" or dispatch.action is None:
        return _policy_blocked(dispatch.reason or "gateway dispatch failed")
    if dispatch.action == EngineAction.CREATE:
        return _execute_create(
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
        )
    if dispatch.action == EngineAction.UPDATE:
        return _execute_update(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
        )
    if dispatch.action == EngineAction.CLOSE:
        return _execute_close(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
        )
    if dispatch.action == EngineAction.REOPEN:
        return _execute_reopen(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
        )
    return _policy_blocked(f"Unsupported dispatch action: {dispatch.action!r}")


def _change_history_label(action: str) -> ChangeHistoryLabel:
    if action == "create":
        return ChangeHistoryLabel.AUTO_CREATE
    if action == "blocker_edit":
        return ChangeHistoryLabel.AUTO_BLOCKER
    if action in {"done", "wontfix"}:
        return ChangeHistoryLabel.AUTO_CLOSE
    if action == "reopen":
        return ChangeHistoryLabel.AUTO_REOPEN
    if action == "correction":
        return ChangeHistoryLabel.CORRECTION
    return ChangeHistoryLabel.AUTO_UPDATE


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
        label=_change_history_label(action),
        reason=f"Automatic Ticket {action} applied.",
    )


def _validate_autonomous_create_dedup(
    mutation: GatewayMutation,
    *,
    thread_id: str,
) -> EngineResponse | None:
    if mutation.action != "create":
        return None
    fields = dict(mutation.fields)
    fields.setdefault("priority", "medium")
    plan_response = _plan_create(fields, thread_id, "agent", mutation.tickets_dir)
    if plan_response.state == "ok":
        return None
    if plan_response.state == "duplicate_candidate":
        return plan_response
    return plan_response


def _response_ok(response: EngineResponse) -> bool:
    return response.state in {
        "ok_create",
        "ok_update",
        "ok_close",
        "ok_close_archived",
        "ok_reopen",
    }


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
        return _policy_blocked(f"Decision validation failed: {decision_error}")
    try:
        lock_path = _acquire_gateway_write_lock(project_root, mutation)
    except RuntimeError as exc:
        return _policy_blocked(f"Gateway write lock failed: {exc}")
    if lock_path is None:
        return _policy_blocked(
            "Gateway write lock failed: lock_timeout",
            data={"pause_reason": "lock_timeout"},
        )
    try:
        return _apply_autonomous_mutation_locked(
            project_root=project_root,
            thread_id=thread_id,
            turn_id=turn_id,
            repo_context=repo_context,
            mutation=mutation,
            decision=decision,
            pending_summary=pending_summary,
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

    target_error = _validate_target_fingerprint(mutation)
    if target_error is not None:
        return target_error

    create_error = _validate_autonomous_create_dedup(mutation, thread_id=thread_id)
    if create_error is not None:
        return create_error

    if _workspace_is_paused(project_root):
        return _policy_blocked(
            "Ticket automation paused for this workspace.",
            data={"pause_reason": _pause_reason(project_root)},
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
        details={
            "decision": decision.kind.value,
            "current_mode": "agent_primary",
            "evidence_kind": "runtime_context",
            **_fingerprint_details(mutation=mutation, decision=decision),
        },
    )
    if attempt_error is not None:
        return attempt_error

    if _workspace_is_paused(project_root):
        return _policy_blocked(
            "Ticket automation paused for this workspace.",
            data={"pause_reason": _pause_reason(project_root)},
        )

    dispatch = build_engine_dispatch(mutation)
    response = _execute_dispatch(
        dispatch=dispatch,
        mutation=mutation,
        thread_id=thread_id,
        change_history_entry=_change_history_entry(
            mutation.action,
            timestamp=change_history_timestamp,
        ),
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

    post_write_fingerprint = compute_target_fingerprint(Path(ticket_path_raw)) or "unknown"

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
