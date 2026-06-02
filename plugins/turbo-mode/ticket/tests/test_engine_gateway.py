"""Tests for the engine-owned autonomous write gateway."""

from __future__ import annotations

import ast
import json
import os
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import scripts.ticket_engine_gateway as gateway
from scripts.ticket_autonomy_runtime import (
    AutonomyDecision,
    AutonomyIntent,
    CandidateMutation,
    EvidenceLink,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
)
from scripts.ticket_commit_coordinator import TicketChangeScope
from scripts.ticket_dedup import target_fingerprint
from scripts.ticket_engine_core import EngineResponse, engine_execute
from scripts.ticket_engine_gateway import (
    GatewayMutation,
    apply_autonomous_mutation,
    build_engine_dispatch,
)
from scripts.ticket_turn_batch import PendingSummaryStore, VerifiedRepoContext

from tests.support.builders import make_ticket
from tests.test_turn_batch import valid_attempt_event


def _declare_ignored_workspace(project_root: Path) -> None:
    (project_root / ".gitignore").write_text(
        ".codex/ticket-workspace/\n.codex/ticket.local.md\n",
        encoding="utf-8",
    )


def _repo_context(project_root: Path) -> VerifiedRepoContext:
    return VerifiedRepoContext(
        repo_root=project_root,
        worktree_root=project_root,
        repo_fingerprint="repo-fp",
        branch="feature/ticket-runtime",
        head="abc123",
    )


def _decision_for(
    *,
    ticket_id: str,
    action: str = "update",
    fields: dict[str, object] | None = None,
    target_fp: str = "ticket-fp",
    ticket_change_scope: TicketChangeScope = "current_branch",
    turn_id: str = "turn-1",
):
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=fields or {"priority": "low"},
        evidence=(EvidenceLink("current_thread_reason", "test"),),
        ticket_change_scope=ticket_change_scope,
    )
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind=action,
            candidates=(candidate,),
            source_context={"ticket_state_fingerprints": {ticket_id: target_fp}},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id=turn_id,
        now=datetime.now(UTC),
    )[0]


def _mutation(
    tickets_dir: Path,
    ticket_path: Path,
    *,
    ticket_id: str = "T-20260527-01",
    action: str = "update",
    fields: dict[str, object] | None = None,
    ticket_change_scope: TicketChangeScope = "current_branch",
) -> GatewayMutation:
    return GatewayMutation(
        action=action,
        ticket_id=ticket_id,
        fields=fields or {"priority": "low"},
        tickets_dir=tickets_dir,
        target_fingerprint=target_fingerprint(ticket_path),
        ticket_change_scope=ticket_change_scope,
    )


def _events(project_root: Path) -> list[dict[str, object]]:
    path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _event_with_recovery_fingerprints(
    event: dict[str, object],
    *,
    pre: str,
    post: str,
) -> dict[str, object]:
    details = dict(event["details"])
    details["expected_pre_write_fingerprint"] = pre
    details["expected_post_write_fingerprint"] = post
    return {**event, "details": details}


def test_gateway_rejects_non_autonomous_or_mismatched_decisions(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    store = PendingSummaryStore(project_root)

    discussion = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(
            decision,
            kind=RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
            reason="discussion_required",
            pending_summary_status="discussion_required",
        ),
        pending_summary=store,
    )
    mismatched_ticket = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(
            decision,
            candidate=CandidateMutation(
                ticket_id="T-20260527-99",
                action="update",
                proposed_change={"priority": "low"},
                evidence=(EvidenceLink("current_thread_reason", "test"),),
            ),
        ),
        pending_summary=store,
    )
    mismatched_fields = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(
            decision,
            candidate=CandidateMutation(
                ticket_id="T-20260527-01",
                action="update",
                proposed_change={"priority": "normal"},
                evidence=(EvidenceLink("current_thread_reason", "test"),),
            ),
        ),
        pending_summary=store,
    )
    mismatched_scope = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=replace(mutation, ticket_change_scope="unrelated_backlog"),
        decision=decision,
        pending_summary=store,
    )
    mismatched_target_fingerprint = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=replace(mutation, target_fingerprint="different-ticket-state"),
        decision=decision,
        pending_summary=store,
    )
    forged_mutation_id = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(decision, mutation_id="mut_wrong"),
        pending_summary=store,
    )

    assert discussion.error_code == "gateway_required"
    assert "autonomous_decision_required" in discussion.message
    assert mismatched_ticket.error_code == "gateway_required"
    assert "ticket_mismatch" in mismatched_ticket.message
    assert mismatched_fields.error_code == "gateway_required"
    assert "mutation_fingerprint_mismatch" in mismatched_fields.message
    assert mismatched_scope.error_code == "gateway_required"
    assert "ticket_change_scope_mismatch" in mismatched_scope.message
    assert mismatched_target_fingerprint.error_code == "gateway_required"
    assert "mutation_id_mismatch" in mismatched_target_fingerprint.message
    assert forged_mutation_id.error_code == "gateway_required"
    assert "mutation_id_mismatch" in forged_mutation_id.message
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
    assert _events(project_root) == []


def test_gateway_autonomous_create_writes_ticket_without_target_fingerprint(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    fields = {
        "title": "Add retry to publisher",
        "problem": "Publisher drops messages on transient broker errors.",
        "priority": "high",
        "key_file_paths": ["publisher.py"],
    }
    candidate = CandidateMutation(
        ticket_id=None,
        action="create",
        proposed_change=fields,
        evidence=(EvidenceLink("current_thread_reason", "discussed this turn"),),
    )
    decision = evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="create",
            candidates=(candidate,),
            source_context={},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime.now(UTC),
    )[0]
    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.mutation_id is not None
    mutation = GatewayMutation("create", None, fields, tmp_tickets, None)

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "ok_create"
    created = list(tmp_tickets.glob("*.md"))
    assert len(created) == 1
    ticket_text = created[0].read_text(encoding="utf-8")
    assert "Add retry to publisher" in ticket_text
    assert "auto-create" in ticket_text
    events = _events(project_root)
    assert [event["status"] for event in events] == [
        "pending",
        "ticket_written",
        "applied",
    ]


def test_gateway_applies_update_records_events_and_writes_change_history(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "ok_update"
    text = ticket_path.read_text(encoding="utf-8")
    assert "priority: low" in text
    assert "## Change History" in text
    assert "auto-update" in text
    events = _events(project_root)
    assert [event["status"] for event in events] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert all(event["thread_id"] == "thread-1" for event in events)
    expected_repo_context = _repo_context(project_root).as_event_payload()
    assert all(event["repo_context"] == expected_repo_context for event in events)
    assert events[-1]["details"]["commit_disposition"] == "commit_deferred"
    assert response.data["commit_disposition"] == "commit_deferred"

    reused = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )
    assert reused.error_code == "gateway_required"


def test_gateway_replay_after_summary_recorded_does_not_rewrite_ticket(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    store = PendingSummaryStore(project_root)

    first = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )
    assert first.state == "ok_update"
    assert (
        store.append_event(
            valid_attempt_event(
                event_id="evt_summary_recorded",
                event_type="summary_receipt",
                status="summarized",
                action="summarize",
                ticket_id=None,
                mutation_id=decision.mutation_id,
                details={},
            )
        ).state
        == "appended"
    )
    before_text = ticket_path.read_text(encoding="utf-8")
    before_events = _events(project_root)

    replay = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert replay.state == "policy_blocked"
    assert replay.data["recovery_state"] == "healthy"
    assert ticket_path.read_text(encoding="utf-8") == before_text
    assert _events(project_root) == before_events
    assert before_text.count("auto-update") == 1


def test_gateway_retry_uses_original_attempt_timestamp_for_change_history_dedupe(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    original_entry = "- 2026-05-27T12:00:00Z | auto-update | Automatic Ticket update applied."
    ticket_text = ticket_path.read_text(encoding="utf-8").rstrip()
    ticket_path.write_text(
        f"{ticket_text}\n\n## Change History\n{original_entry}\n",
        encoding="utf-8",
    )
    mutation = _mutation(tmp_tickets, ticket_path)
    pre = mutation.target_fingerprint or ""
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=pre, turn_id="turn-retry")
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            valid_attempt_event(
                event_id="evt_original_attempt",
                timestamp="2026-05-27T12:00:00Z",
                thread_id="thread-1",
                mutation_id=decision.mutation_id,
                details={"expected_pre_write_fingerprint": pre},
            )
        ).state
        == "appended"
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-retry",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert response.state == "ok_update"
    text = ticket_path.read_text(encoding="utf-8")
    assert "priority: low" in text
    assert text.count(original_entry) == 1


def test_gateway_passes_ticket_change_scope_to_commit_disposition(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        ticket_change_scope="unrelated_backlog",
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.target_fingerprint or "",
        ticket_change_scope="unrelated_backlog",
    )
    captured: dict[str, object] = {}

    def fake_record_ticket_commit_disposition(**kwargs: object) -> gateway.CommitDispositionRecord:
        captured.update(kwargs)
        return gateway.CommitDispositionRecord(
            "commit_deferred",
            reason="Unrelated backlog ticket commits require main.",
        )

    monkeypatch.setattr(
        gateway,
        "record_ticket_commit_disposition",
        fake_record_ticket_commit_disposition,
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "ok_update"
    assert captured["ticket_change_scope"] == "unrelated_backlog"
    assert response.data["commit_disposition"] == "commit_deferred"
    assert response.data["commit_reason"] == "Unrelated backlog ticket commits require main."


def test_gateway_write_lock_clears_dead_pid_lock_and_proceeds(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    lock_path = gateway._gateway_lock_path(project_root, mutation)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("999999999\n", encoding="utf-8")

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "ok_update"
    assert not lock_path.exists()


def test_gateway_write_lock_keeps_live_or_malformed_locks_closed(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    lock_path = gateway._gateway_lock_path(project_root, mutation)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    assert gateway._acquire_gateway_write_lock(
        project_root,
        mutation,
        timeout_seconds=0,
    ) is None
    assert lock_path.exists()

    lock_path.write_text("not-a-pid\n", encoding="utf-8")
    assert gateway._acquire_gateway_write_lock(
        project_root,
        mutation,
        timeout_seconds=0,
    ) is None
    assert lock_path.exists()


def test_concurrent_same_ticket_gateway_calls_serialize_and_second_sees_stale_fingerprint(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    pre = target_fingerprint(ticket_path) or ""
    first_mutation = _mutation(tmp_tickets, ticket_path, fields={"priority": "low"})
    second_mutation = _mutation(tmp_tickets, ticket_path, fields={"priority": "medium"})
    first_decision = _decision_for(
        ticket_id="T-20260527-01",
        fields={"priority": "low"},
        target_fp=pre,
        turn_id="turn-first",
    )
    second_decision = _decision_for(
        ticket_id="T-20260527-01",
        fields={"priority": "medium"},
        target_fp=pre,
        turn_id="turn-second",
    )
    first_entered = threading.Event()
    release_first = threading.Event()
    active_lock = threading.Lock()
    active_dispatches = 0
    max_active_dispatches = 0
    dispatch_priorities: list[object] = []

    def fake_execute_dispatch(**kwargs: object) -> EngineResponse:
        nonlocal active_dispatches, max_active_dispatches
        mutation = kwargs["mutation"]
        assert isinstance(mutation, GatewayMutation)
        with active_lock:
            active_dispatches += 1
            max_active_dispatches = max(max_active_dispatches, active_dispatches)
            dispatch_priorities.append(dict(mutation.fields).get("priority"))
        try:
            if dict(mutation.fields).get("priority") != "low":
                raise AssertionError("second gateway call entered dispatch")
            first_entered.set()
            if not release_first.wait(timeout=5):
                raise AssertionError("first gateway call was not released")
            ticket_path.write_text(
                ticket_path.read_text(encoding="utf-8").replace(
                    "priority: high",
                    "priority: low",
                ),
                encoding="utf-8",
            )
            return EngineResponse(
                "ok_update",
                "Updated.",
                data={"ticket_path": str(ticket_path)},
            )
        finally:
            with active_lock:
                active_dispatches -= 1

    monkeypatch.setattr(gateway, "_execute_dispatch", fake_execute_dispatch)
    responses: dict[str, EngineResponse | BaseException] = {}

    def run_gateway(name: str, mutation: GatewayMutation, decision: AutonomyDecision) -> None:
        try:
            responses[name] = apply_autonomous_mutation(
                project_root=project_root,
                thread_id="thread-1",
                turn_id=f"turn-{name}",
                repo_context=_repo_context(project_root),
                mutation=mutation,
                decision=decision,
                pending_summary=PendingSummaryStore(project_root),
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertions below
            responses[name] = exc

    first_thread = threading.Thread(
        target=run_gateway,
        args=("first", first_mutation, first_decision),
    )
    second_thread = threading.Thread(
        target=run_gateway,
        args=("second", second_mutation, second_decision),
    )
    first_thread.start()
    assert first_entered.wait(timeout=5)
    second_thread.start()
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert isinstance(responses["first"], EngineResponse)
    assert isinstance(responses["second"], EngineResponse)
    assert responses["first"].state == "ok_update"
    assert responses["second"].state == "preflight_failed"
    assert responses["second"].error_code == "stale_plan"
    assert dispatch_priorities == ["low"]
    assert max_active_dispatches == 1


def test_gateway_autonomous_create_stops_at_duplicate_candidate(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    today = datetime.now(UTC).date().isoformat()
    make_ticket(
        tmp_tickets,
        "existing.md",
        id="T-20260527-01",
        date=today,
        title="Fix auth bug",
        problem="Auth times out.",
    )
    fields = {
        "title": "Fix auth bug",
        "problem": "Auth times out.",
        "priority": "high",
        "key_file_paths": ["test.py"],
    }
    candidate = CandidateMutation(
        ticket_id=None,
        action="create",
        proposed_change=fields,
        evidence=(EvidenceLink("current_thread_reason", "same issue"),),
    )
    decision = evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="create",
            candidates=(candidate,),
            source_context={},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime.now(UTC),
    )[0]
    mutation = GatewayMutation("create", None, fields, tmp_tickets, None)

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "duplicate_candidate"
    assert response.error_code == "duplicate_candidate"
    assert len(list(tmp_tickets.glob("*.md"))) == 1


def test_gateway_recovers_missing_write_events_without_rewriting_ticket(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    pre = mutation.target_fingerprint or ""
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=pre)

    ticket_path.write_text(
        ticket_path.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )
    post = target_fingerprint(ticket_path) or ""
    before = ticket_path.read_text(encoding="utf-8")
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            _event_with_recovery_fingerprints(
                valid_attempt_event(
                    event_id="evt_attempt_recover",
                    thread_id="thread-1",
                    mutation_id=decision.mutation_id,
                ),
                pre=pre,
                post=post,
            )
        ).state
        == "appended"
    )
    recovered = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert recovered.error_code == "gateway_required"
    assert recovered.data["recovery_state"] == "append_missing_ticket_written"
    assert ticket_path.read_text(encoding="utf-8") == before
    assert [event["status"] for event in _events(project_root)] == [
        "pending",
        "ticket_written",
        "applied",
    ]


def test_pending_summary_failure_and_pause_prevent_ticket_mutation(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    before = ticket_path.read_text(encoding="utf-8")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")

    lock_path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("locked\n", encoding="utf-8")
    blocked = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root, lock_timeout_seconds=0),
    )
    assert blocked.state == "policy_blocked"
    assert ticket_path.read_text(encoding="utf-8") == before
    lock_path.unlink()

    from scripts.ticket_autonomy_config import write_workspace_pause

    write_workspace_pause(project_root, reason="user_requested")
    paused = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )
    assert paused.state == "policy_blocked"
    assert paused.data["pause_reason"] == "user_requested"
    assert ticket_path.read_text(encoding="utf-8") == before
    assert _events(project_root) == []


def test_gateway_rechecks_pause_after_attempt_record_before_dispatch(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    before = ticket_path.read_text(encoding="utf-8")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    checks = iter([False, True])

    monkeypatch.setattr(gateway, "_workspace_is_paused", lambda _project_root: next(checks))

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "policy_blocked"
    assert response.data["pause_reason"] == "workspace_paused"
    assert ticket_path.read_text(encoding="utf-8") == before
    assert [event["status"] for event in _events(project_root)] == ["pending"]


def test_gateway_treats_success_without_ticket_path_as_failed_mutation(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    before = ticket_path.read_text(encoding="utf-8")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")

    monkeypatch.setattr(
        gateway,
        "_execute_dispatch",
        lambda **_kwargs: EngineResponse("ok_update", "Updated without path", data={}),
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "policy_blocked"
    assert "ticket_path_missing" in response.message
    assert ticket_path.read_text(encoding="utf-8") == before
    assert [event["status"] for event in _events(project_root)] == [
        "pending",
        "failed",
    ]


def test_gateway_dispatch_maps_ticket_actions_and_rejects_archive_smuggling(
    tmp_tickets: Path,
) -> None:
    done = build_engine_dispatch(
        GatewayMutation("done", "T-1", {}, tmp_tickets, "fp"),
    )
    wontfix = build_engine_dispatch(
        GatewayMutation("wontfix", "T-1", {}, tmp_tickets, "fp"),
    )
    update = build_engine_dispatch(
        GatewayMutation("blocker_edit", "T-1", {"blocks": []}, tmp_tickets, "fp"),
    )
    reopen = build_engine_dispatch(
        GatewayMutation("reopen", "T-1", {"reopen_reason": "Regression."}, tmp_tickets, "fp"),
    )
    archive = build_engine_dispatch(
        GatewayMutation("done", "T-1", {"archive": True}, tmp_tickets, "fp"),
    )

    assert done.action.value == "close"
    assert done.fields == {"resolution": "done"}
    assert wontfix.action.value == "close"
    assert wontfix.fields == {"resolution": "wontfix"}
    assert update.action.value == "update"
    assert reopen.action.value == "reopen"
    assert archive.state == "policy_blocked"


def test_direct_agent_execute_remains_gateway_required(tmp_tickets: Path) -> None:
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    response = engine_execute(
        action="update",
        ticket_id="T-20260527-01",
        fields={"priority": "low"},
        session_id="session",
        request_origin="agent",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        target_fingerprint=target_fingerprint(ticket_path),
        hook_injected=True,
        hook_request_origin="user",
        classify_intent="update",
        classify_confidence=1.0,
        runtime_execute_surface="direct_execute",
    )

    assert response.error_code == "gateway_required"
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")


def test_static_guard_keeps_autonomy_ticket_writes_named() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    allowed: dict[str, set[str]] = {
        "ticket_autonomy.py": {"_run_migrate_change_history"},
        "ticket_engine_gateway.py": {"_release_gateway_write_lock"},
    }
    checked = [
        plugin_root / "scripts" / "ticket_autonomy.py",
        plugin_root / "scripts" / "ticket_autonomy_runtime.py",
        plugin_root / "scripts" / "ticket_candidate_discovery.py",
        plugin_root / "scripts" / "ticket_engine_gateway.py",
    ]
    mutating_calls = {"write_text", "rename", "unlink"}

    violations: list[str] = []
    for path in checked:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in mutating_calls:
                continue
            parent = parents.get(node)
            function_name = ""
            while parent is not None:
                if isinstance(parent, ast.FunctionDef):
                    function_name = parent.name
                    break
                parent = parents.get(parent)
            if function_name not in allowed.get(path.name, set()):
                violations.append(f"{path.name}:{function_name}:{node.func.attr}")

    assert violations == []
