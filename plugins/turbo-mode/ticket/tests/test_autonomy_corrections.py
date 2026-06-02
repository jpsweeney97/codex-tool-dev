"""Tests for user-triggered autonomous correction flow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    EvidenceLink,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
)
from scripts.ticket_dedup import target_fingerprint
from scripts.ticket_engine_gateway import GatewayMutation, apply_autonomous_mutation
from scripts.ticket_parse import parse_ticket
from scripts.ticket_turn_batch import PendingSummaryStore, VerifiedRepoContext

from tests.support.builders import make_ticket


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


def _correction_decision(candidate: CandidateMutation, *, ticket_path: Path | None = None):
    source_context: dict[str, object] = {}
    if ticket_path is not None and candidate.ticket_id is not None:
        source_context["ticket_state_fingerprints"] = {
            candidate.ticket_id: target_fingerprint(ticket_path)
        }
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="correct_ticket_mutation",
            candidates=(candidate,),
            source_context=source_context,
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime.now(UTC),
    )[0]


def _apply_correction(
    *,
    project_root: Path,
    tickets_dir: Path,
    ticket_path: Path,
    candidate: CandidateMutation,
):
    decision = _correction_decision(candidate, ticket_path=ticket_path)
    mutation = GatewayMutation(
        action="correction",
        ticket_id=candidate.ticket_id,
        fields=dict(candidate.proposed_change),
        tickets_dir=tickets_dir,
        target_fingerprint=target_fingerprint(ticket_path),
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
    return decision, response


def _events(project_root: Path) -> list[dict[str, object]]:
    path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_user_triggered_update_correction_applies_without_new_approval(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correction",
        proposed_change={"priority": "high"},
        evidence=(EvidenceLink("correction_detail", "prior mutation set priority too low"),),
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok_update"
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
    assert "correction" in ticket_path.read_text(encoding="utf-8")
    events = _events(project_root)
    assert [event["status"] for event in events] == ["pending", "ticket_written", "applied"]
    assert events[0]["details"]["decision"] == RuntimeDecisionKind.APPLY_CORRECTION.value
    assert "approval" not in events[0]["details"]


def test_wrongly_created_ticket_is_corrected_with_wontfix_not_deleted(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "wrong.md", id="T-20260527-01", status="open")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correction",
        proposed_change={"resolution": "wontfix"},
        evidence=(EvidenceLink("correction_detail", "ticket was created for the wrong item"),),
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    parsed = parse_ticket(ticket_path)
    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok_close"
    assert ticket_path.exists()
    assert parsed is not None
    assert parsed.status == "wontfix"
    assert "correction" in ticket_path.read_text(encoding="utf-8")


def test_unsafe_correction_requests_require_discussion() -> None:
    unsafe_keys = (
        {"delete": True},
        {"archive": True},
        {"history_repair": True},
        {"rewrite_change_history": True},
        {"remove_history_entries": ["old"]},
        {"git_history_edit": "reset"},
    )

    decisions = [
        _correction_decision(
            CandidateMutation(
                ticket_id="T-20260527-01",
                action="correction",
                proposed_change=payload,
                evidence=(EvidenceLink("correction_detail", "unsafe correction"),),
            )
        )
        for payload in unsafe_keys
    ]

    assert {decision.kind for decision in decisions} == {
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    }


def test_expired_correction_detail_requires_discussion_when_state_is_not_obvious() -> None:
    decision = _correction_decision(
        CandidateMutation(
            ticket_id="T-20260527-01",
            action="correction",
            proposed_change={"priority": "high"},
            evidence=(EvidenceLink("ticket_state", "current ticket still exists"),),
        )
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"
