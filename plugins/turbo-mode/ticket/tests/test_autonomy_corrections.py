"""Tests for user-triggered autonomous correction flow."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    CandidateTarget,
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


def _recent_correction_context(
    candidate: CandidateMutation,
    *,
    source_mutation_id: str = "mut-prior-correction",
    retained_at: str = "2026-06-05T12:00:00Z",
) -> dict[str, object]:
    assert candidate.ticket_id is not None
    assert candidate.expected_ticket_fingerprint is not None
    return {
        candidate.ticket_id: {
            "correction_ready": True,
            "correction_detail_retained": True,
            "source_mutation_id": source_mutation_id,
            "retained_at": retained_at,
            "expected_ticket_fingerprint": candidate.expected_ticket_fingerprint,
            "proposed_change": dict(candidate.proposed_change),
            "target": {
                "fields": list(candidate.target.fields),
                "sections": list(candidate.target.sections),
            },
        }
    }


def _correction_decision(
    candidate: CandidateMutation,
    *,
    ticket_path: Path | None = None,
    recent_correction_context: bool | Mapping[str, object] = True,
    now: datetime | None = None,
):
    source_context: dict[str, object] = {}
    if ticket_path is not None and candidate.ticket_id is not None:
        source_context["ticket_state_fingerprints"] = {
            candidate.ticket_id: target_fingerprint(ticket_path)
        }
    if isinstance(recent_correction_context, Mapping):
        source_context["recent_correction_context"] = dict(recent_correction_context)
    elif recent_correction_context and candidate.ticket_id is not None:
        source_context["recent_correction_context"] = _recent_correction_context(candidate)
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="correct_ticket_mutation",
            candidates=(candidate,),
            source_context=source_context,
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=now or datetime(2026, 6, 5, 12, 5, tzinfo=UTC),
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
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        target=candidate.target,
        proposed_change=dict(candidate.proposed_change),
        tickets_dir=tickets_dir,
        expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
        evidence_summary=candidate.evidence_summary,
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


def _priority_correction(ticket_path: Path) -> CandidateMutation:
    return CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )


def test_user_triggered_update_correction_applies_without_new_approval(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "priority: high" in text
    assert " | codex | Corrected ticket from candidate evidence." in text
    events = _events(project_root)
    assert [event["status"] for event in events] == ["pending", "ticket_written", "applied"]
    assert "rewrite_change_history" not in events[0]["details"]
    assert "decision" not in events[0]["details"]
    assert "current_mode" not in events[0]["details"]
    assert "evidence_kind" not in events[0]["details"]
    assert events[0]["details"]["target"] == {"fields": ["priority"], "sections": []}
    assert events[0]["details"]["evidence_summary"] == "Prior mutation set priority too low."
    assert "approval" not in events[0]["details"]


def test_wrongly_created_ticket_is_corrected_with_wontfix_not_deleted(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "wrong.md", id="T-20260527-01", status="open")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("status",), sections=()),
        proposed_change={"status": "wontfix"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation created a ticket for the wrong item.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    parsed = parse_ticket(ticket_path)
    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    assert ticket_path.exists()
    assert parsed is not None
    assert parsed.status == "wontfix"
    assert (
        " | codex | Corrected ticket from candidate evidence."
        in ticket_path.read_text(encoding="utf-8")
    )


def test_correction_without_recent_context_requires_discussion(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=False,
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_correction_context_must_match_target_and_expected_fingerprint(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)
    mismatched_context = {
        "recent_correction_context": {
            "T-20260527-01": {
                "correction_ready": True,
                "correction_detail_retained": True,
                "source_mutation_id": "mut-prior-correction",
                "retained_at": "2026-06-05T12:00:00Z",
                "expected_ticket_fingerprint": "different-fingerprint",
                "proposed_change": {"priority": "high"},
                "target": {"fields": ["priority"], "sections": []},
            }
        }
    }

    decision = evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="correct_ticket_mutation",
            candidates=(candidate,),
            source_context=mismatched_context,
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime(2026, 6, 5, 12, 5, tzinfo=UTC),
    )[0]

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_correction_context_must_match_proposed_change(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)
    mismatched_context = _recent_correction_context(candidate)
    assert isinstance(mismatched_context["T-20260527-01"], dict)
    mismatched_context["T-20260527-01"]["proposed_change"] = {"priority": "normal"}

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=mismatched_context,
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_correction_context_expired_requires_discussion(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=_recent_correction_context(
            candidate,
            retained_at="2026-05-01T12:00:00Z",
        ),
        now=datetime(2026, 6, 5, 12, 5, tzinfo=UTC),
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_correction_context_unparseable_retained_at_requires_discussion(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=_recent_correction_context(
            candidate,
            retained_at="not-a-timestamp",
        ),
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_compacted_correction_context_requires_discussion(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = _priority_correction(ticket_path)
    context = _recent_correction_context(candidate)
    assert isinstance(context["T-20260527-01"], dict)
    retained = context["T-20260527-01"]
    retained.pop("correction_detail_retained")
    retained["correction_detail_compacted"] = True

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=context,
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_reordered_equivalent_correction_target_context_is_authorized(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority", "status"), sections=()),
        proposed_change={"priority": "high", "status": "open"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )
    context = _recent_correction_context(candidate)
    assert isinstance(context["T-20260527-01"], dict)
    context["T-20260527-01"]["target"] = {
        "fields": ["status", "priority"],
        "sections": [],
    }

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=context,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION


def test_correction_cannot_target_change_history(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=(), sections=("Change History",)),
        proposed_change={"Change History": "caller-owned rewrite"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Attempted unsafe correction.",
    )

    decision = _correction_decision(candidate, ticket_path=ticket_path)

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "target_closure_failed"


def test_user_triggered_active_correction_to_blocked_uses_update_not_reopen(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", status="open")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",)),
        proposed_change={
            "status": "blocked",
            "blocked_by": ["T-20260527-02"],
            "Blocked On": "Waiting for T-20260527-02.",
        },
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation left the ticket open instead of blocked.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: blocked" in text
    assert "blocked_by: [T-20260527-02]" in text
    assert "## Blocked On\nWaiting for T-20260527-02." in text
    assert "## Reopen History" not in text
    assert " | codex | Corrected ticket from candidate evidence." in text


def test_user_triggered_active_correction_to_open_clears_blocker_without_reopen(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(
        tmp_tickets,
        "one.md",
        id="T-20260527-01",
        status="blocked",
        blocked_by=["T-20260527-02"],
        blocked_on="Waiting for T-20260527-02.",
    )
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(
            fields=("status", "blocked_by"),
            sections=("Blocked On", "Next Action"),
        ),
        proposed_change={
            "status": "open",
            "blocked_by": [],
            "Blocked On": None,
            "Next Action": "Continue the candidate-contract migration.",
        },
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation left a stale blocker on an open ticket.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: open" in text
    assert "blocked_by: []" in text
    assert "## Blocked On" not in text
    assert "## Next Action\nContinue the candidate-contract migration." in text
    assert "## Reopen History" not in text
    assert " | codex | Corrected ticket from candidate evidence." in text


def test_user_triggered_terminal_correction_to_open_uses_reopen_policy(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("status",), sections=()),
        proposed_change={"status": "open"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation closed the ticket by mistake.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: open" in text
    assert "## Reopen History" not in text
    assert " | codex | Corrected ticket from candidate evidence." in text
