"""Tests for the engine-owned autonomous write gateway."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import scripts.ticket_engine_gateway as gateway
from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    EvidenceLink,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
)
from scripts.ticket_dedup import target_fingerprint
from scripts.ticket_engine_core import EngineResponse, engine_execute
from scripts.ticket_engine_gateway import (
    GatewayMutation,
    apply_autonomous_mutation,
    build_engine_dispatch,
)
from scripts.ticket_turn_batch import PendingSummaryStore, VerifiedRepoContext

from tests.support.builders import make_ticket
from tests.test_turn_batch import valid_attempt_event, valid_status_event


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
):
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=fields or {"priority": "low"},
        evidence=(EvidenceLink("current_thread_reason", "test"),),
    )
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind=action,
            candidates=(candidate,),
            source_context={"ticket_state_fingerprints": {ticket_id: target_fp}},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime.now(UTC),
    )[0]


def _mutation(
    tickets_dir: Path,
    ticket_path: Path,
    *,
    ticket_id: str = "T-20260527-01",
    action: str = "update",
    fields: dict[str, object] | None = None,
) -> GatewayMutation:
    return GatewayMutation(
        action=action,
        ticket_id=ticket_id,
        fields=fields or {"priority": "low"},
        tickets_dir=tickets_dir,
        target_fingerprint=target_fingerprint(ticket_path),
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
    approval = details.get("approval")
    if isinstance(approval, dict):
        details["approval"] = {**approval, "ticket_state_fingerprint": pre}
    return {**event, "details": details}


def test_gateway_rejects_missing_mismatched_reused_and_expired_approvals(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    store = PendingSummaryStore(project_root)

    missing = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision.__class__(
            decision.candidate,
            RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
            None,
            None,
            None,
            "discussion_required",
            "discussion_required",
        ),
        pending_summary=store,
    )
    forged_approval = dict(decision.approval or {})
    forged_approval["ticket_id"] = "T-20260527-99"
    forged = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision.__class__(
            decision.candidate,
            decision.kind,
            decision.mutation_id,
            forged_approval,
            decision.engine_dispatch,
            decision.reason,
            decision.pending_summary_status,
        ),
        pending_summary=store,
    )
    expired_approval = dict(decision.approval or {})
    expired_approval["expires_at"] = "2000-01-01T00:00:00Z"
    expired = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision.__class__(
            decision.candidate,
            decision.kind,
            decision.mutation_id,
            expired_approval,
            decision.engine_dispatch,
            decision.reason,
            decision.pending_summary_status,
        ),
        pending_summary=store,
    )

    assert missing.error_code == "gateway_required"
    assert forged.error_code == "gateway_required"
    assert expired.error_code == "gateway_required"


def test_gateway_rejects_approval_when_live_mutation_fingerprint_differs(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    forged_approval = dict(decision.approval or {})
    forged_approval["mutation_fingerprint"] = "sha256:not-the-live-mutation"
    forged = decision.__class__(
        decision.candidate,
        decision.kind,
        decision.mutation_id,
        forged_approval,
        decision.engine_dispatch,
        decision.reason,
        decision.pending_summary_status,
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=forged,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "policy_blocked"
    assert "mutation_fingerprint_mismatch" in response.message
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
    pending_summary_path = (
        project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    )
    assert not pending_summary_path.exists()


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
        "approval_consumed",
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
    assert (
        store.append_event(
            _event_with_recovery_fingerprints(
                valid_status_event(
                    "approval_consumed",
                    event_id="evt_approval_recover",
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
        "approval_consumed",
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


def test_gateway_rechecks_pause_after_approval_consumption_before_dispatch(
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
    assert [event["status"] for event in _events(project_root)] == [
        "pending",
        "approval_consumed",
    ]


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
        "approval_consumed",
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
