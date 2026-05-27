"""Engine-owned autonomous Ticket write gateway."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.ticket_autonomy_config import WORKSPACE_RELATIVE_PATH
from scripts.ticket_autonomy_ids import make_event_id
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
    append_change_history_entry,
)
from scripts.ticket_dedup import target_fingerprint as compute_target_fingerprint
from scripts.ticket_engine_core import (
    EngineResponse,
    _execute_close,
    _execute_create,
    _execute_reopen,
    _execute_update,
)
from scripts.ticket_read import find_ticket_by_id
from scripts.ticket_turn_batch import (
    PENDING_SUMMARY_SCHEMA,
    PendingSummaryStore,
    VerifiedRepoContext,
    event_payload_fingerprint,
    project_mutation_recovery,
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


def build_engine_dispatch(mutation: GatewayMutation) -> EngineDispatch:
    """Build deterministic engine dispatch for a gateway mutation."""
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        proposed_change=dict(mutation.fields),
        evidence=(),
    )
    return map_candidate_to_engine(candidate)


def _approval_error(
    *,
    thread_id: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    approval = decision.approval
    if decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY or approval is None:
        return "approval_required"
    if decision.mutation_id is None:
        return "mutation_id_required"
    if approval.get("thread_id") != thread_id:
        return "thread_mismatch"
    if approval.get("ticket_id") != mutation.ticket_id:
        return "ticket_mismatch"
    if approval.get("mutation_id") != decision.mutation_id:
        return "mutation_mismatch"
    if approval.get("decision") != RuntimeDecisionKind.APPLY_AUTONOMOUSLY.value:
        return "decision_mismatch"
    expires_at = _parse_z(approval.get("expires_at"))
    if expires_at is None or expires_at <= datetime.now(UTC):
        return "approval_expired"
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
            message="Stale fingerprint - ticket was modified since approval.",
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
    if mutation.target_fingerprint:
        return mutation.target_fingerprint
    approval = decision.approval
    if isinstance(approval, Mapping):
        value = approval.get("ticket_state_fingerprint")
        if isinstance(value, str) and value and value != "unknown":
            return value
    return None


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
        return _policy_blocked("Approval validation failed: mutation_id_required")
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
) -> EngineResponse:
    if dispatch.state != "ok" or dispatch.action is None:
        return _policy_blocked(dispatch.reason or "gateway dispatch failed")
    if dispatch.action == EngineAction.CREATE:
        return _execute_create(dict(dispatch.fields), thread_id, "agent", mutation.tickets_dir)
    if dispatch.action == EngineAction.UPDATE:
        return _execute_update(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
        )
    if dispatch.action == EngineAction.CLOSE:
        return _execute_close(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
        )
    if dispatch.action == EngineAction.REOPEN:
        return _execute_reopen(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
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


def _write_change_history_entry(ticket_path: Path, *, action: str) -> None:
    text = ticket_path.read_text(encoding="utf-8")
    entry = ChangeHistoryEntry(
        timestamp=_now_z(),
        label=_change_history_label(action),
        reason=f"Automatic Ticket {action} applied.",
    )
    ticket_path.write_text(append_change_history_entry(text, entry), encoding="utf-8")


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
    """Apply one approved autonomous mutation through the gateway."""
    approval_error = _approval_error(thread_id=thread_id, mutation=mutation, decision=decision)
    if approval_error is not None:
        return _policy_blocked(f"Approval validation failed: {approval_error}")
    if decision.mutation_id is None or decision.approval is None:
        return _policy_blocked("Approval validation failed: approval_required")
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

    target_error = _validate_target_fingerprint(mutation)
    if target_error is not None:
        return target_error

    attempt_error = _append_gateway_event(
        pending_summary=pending_summary,
        event_type="mutation_attempt",
        status="pending",
        mutation=mutation,
        decision=decision,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason="Apply approved autonomous Ticket mutation.",
        details={
            "decision": RuntimeDecisionKind.APPLY_AUTONOMOUSLY.value,
            "current_mode": str(decision.approval.get("current_mode", "agent_primary")),
            "approval": decision.approval,
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

    consumed_error = _append_gateway_event(
        pending_summary=pending_summary,
        event_type="mutation_status",
        status="approval_consumed",
        mutation=mutation,
        decision=decision,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason="Autonomous approval consumed.",
        details={
            "approval_id": str(decision.approval["approval_id"]),
            **_fingerprint_details(mutation=mutation, decision=decision),
        },
    )
    if consumed_error is not None:
        return consumed_error

    dispatch = build_engine_dispatch(mutation)
    response = _execute_dispatch(dispatch=dispatch, mutation=mutation, thread_id=thread_id)
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
    if isinstance(ticket_path_raw, str):
        _write_change_history_entry(Path(ticket_path_raw), action=mutation.action)
        post_write_fingerprint = compute_target_fingerprint(Path(ticket_path_raw)) or "unknown"
    else:
        post_write_fingerprint = "unknown"

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
        details={
            "commit_disposition": "commit_deferred",
            "commit_reason": "Commit coordinator not yet run for this source slice.",
        },
    )
    if applied_error is not None:
        return applied_error

    return response
