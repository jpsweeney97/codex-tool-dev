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
    CandidateTarget,
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

from tests.support.builders import make_legacy_ticket_for_cutover, make_ticket
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


def _target(
    *,
    fields: tuple[str, ...] = ("priority",),
    sections: tuple[str, ...] = (),
) -> CandidateTarget:
    return CandidateTarget(fields=fields, sections=sections)


def _decision_for(
    *,
    ticket_id: str | None,
    action: str = "update",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = "ticket-fp",
    evidence_summary: str = "Current turn justifies this ticket change.",
    fields: dict[str, object] | None = None,
    target_fp: str | None = None,
    turn_id: str = "turn-1",
):
    if proposed_change is None and fields is not None:
        proposed_change = fields
    if target_fp is not None:
        expected_ticket_fingerprint = target_fp
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target or _target(),
        proposed_change=proposed_change or {"priority": "low"},
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind=action,
            candidates=(candidate,),
            source_context={},
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
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    fields: dict[str, object] | None = None,
) -> GatewayMutation:
    if proposed_change is None and fields is not None:
        proposed_change = fields
    expected = target_fingerprint(ticket_path)
    return GatewayMutation(
        action=action,
        ticket_id=ticket_id,
        target=target or _target(),
        proposed_change=proposed_change or {"priority": "low"},
        tickets_dir=tickets_dir,
        expected_ticket_fingerprint=expected,
        evidence_summary="Current turn justifies this ticket change.",
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


def test_gateway_does_not_import_commit_coordination() -> None:
    source = Path(gateway.__file__).read_text(encoding="utf-8")

    assert "ticket_commit_coordinator" not in source
    assert "record_ticket_commit_disposition" not in source
    assert "CommitDispositionRecord" not in source


def test_gateway_rejects_non_autonomous_or_mismatched_decisions(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
    )
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
                target=_target(),
                proposed_change={"priority": "low"},
                expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
                evidence_summary="Current turn justifies this ticket change.",
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
                target=_target(),
                proposed_change={"priority": "normal"},
                expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
                evidence_summary="Current turn justifies this ticket change.",
            ),
        ),
        pending_summary=store,
    )
    mismatched_target_fingerprint = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=replace(mutation, expected_ticket_fingerprint="different-ticket-state"),
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
    assert mismatched_target_fingerprint.error_code == "gateway_required"
    assert "expected_ticket_fingerprint_mismatch" in mismatched_target_fingerprint.message
    assert forged_mutation_id.error_code == "gateway_required"
    assert "mutation_id_mismatch" in forged_mutation_id.message
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
    assert _events(project_root) == []


def test_gateway_autonomous_create_writes_ticket_without_target_fingerprint(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    target = CandidateTarget(
        fields=("title", "priority", "related_paths"),
        sections=("Problem",),
    )
    proposed_change = {
        "title": "Add retry to publisher",
        "priority": "high",
        "related_paths": ["publisher.py"],
        "Problem": "Publisher drops messages on transient broker errors.",
    }
    candidate = CandidateMutation(
        ticket_id=None,
        action="create",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
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
    mutation = GatewayMutation(
        action="create",
        ticket_id=None,
        target=target,
        proposed_change=proposed_change,
        tickets_dir=tmp_tickets,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
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

    assert response.state == "ok"
    created = list(tmp_tickets.glob("*.md"))
    assert len(created) == 1
    ticket_text = created[0].read_text(encoding="utf-8")
    assert "Add retry to publisher" in ticket_text
    assert "| codex | Created ticket from candidate evidence." in ticket_text
    # A freshly created ticket carries exactly one Change History entry — no
    # fabricated render-time placeholder ahead of the real gateway entry.
    history_section = ticket_text.split("## Change History", 1)[1].split("\n## ", 1)[0]
    history_entries = [line for line in history_section.splitlines() if line.startswith("- ")]
    assert len(history_entries) == 1, history_entries
    assert "Rendered target ticket." not in ticket_text
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
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
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

    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "priority: low" in text
    assert "## Change History" in text
    assert "| codex | Updated ticket from candidate evidence." in text
    events = _events(project_root)
    assert [event["status"] for event in events] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert all(event["thread_id"] == "thread-1" for event in events)
    expected_repo_context = _repo_context(project_root).as_event_payload()
    assert all(event["repo_context"] == expected_repo_context for event in events)
    assert events[-1]["details"] == {}
    assert "commit_disposition" not in response.data
    assert "commit_hash" not in response.data
    assert "commit_reason" not in response.data

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


def test_gateway_applies_exact_target_section_update(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    target = CandidateTarget(fields=("priority",), sections=("Next Action",))
    proposed_change = {
        "priority": "low",
        "Next Action": "Finish the target candidate migration.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
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

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "priority: low" in text
    assert "## Next Action\nFinish the target candidate migration." in text
    assert "| codex | Updated ticket from candidate evidence." in text


def test_gateway_removes_exact_optional_target_section(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    assert "## Verification" in ticket_path.read_text(encoding="utf-8")
    target = CandidateTarget(fields=(), sections=("Verification",))
    proposed_change = {"Verification": None}
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
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

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "## Verification" not in text
    assert "## Approach" in text
    assert "## Key Files" in text
    assert "| codex | Updated ticket from candidate evidence." in text


def test_gateway_updates_blocked_ticket_to_open_with_target_section_cleanup(
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
    target = CandidateTarget(
        fields=("status", "blocked_by"),
        sections=("Blocked On", "Next Action"),
    )
    proposed_change = {
        "status": "open",
        "blocked_by": [],
        "Blocked On": None,
        "Next Action": "Continue the candidate-contract migration.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
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

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "status: open" in text
    assert "blocked_by: []" in text
    assert "## Blocked On" not in text
    assert "## Next Action\nContinue the candidate-contract migration." in text
    assert "| codex | Updated ticket from candidate evidence." in text


def test_gateway_rejects_blocked_to_open_without_next_action(
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
    before_text = ticket_path.read_text(encoding="utf-8")
    target = CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",))
    proposed_change = {
        "status": "open",
        "blocked_by": [],
        "Blocked On": None,
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
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

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "blocked"
    assert response.error_code == "gateway_required"
    assert "blocked_to_open_target_not_allowlisted" in response.message
    assert text == before_text


def test_gateway_rejects_status_only_close_for_blocked_ticket(
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
    before_text = ticket_path.read_text(encoding="utf-8")
    target = CandidateTarget(fields=("status",), sections=())
    proposed_change = {"status": "done"}
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="done",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="done",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
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

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "blocked"
    assert "close_target_not_allowlisted" in response.message
    assert text == before_text


def test_gateway_create_accepts_every_source_supported_target_section(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    target = CandidateTarget(
        fields=("title", "status", "priority", "blocked_by"),
        sections=(
            "Problem",
            "Next Action",
            "Blocked On",
            "Captured Request",
            "Context",
            "Prior Investigation",
            "Approach",
            "Decisions Made",
            "Acceptance Criteria",
            "Verification",
            "Key Files",
            "Related",
        ),
    )
    proposed_change = {
        "title": "Add retry to publisher",
        "status": "blocked",
        "priority": "high",
        "blocked_by": ["T-20260605-02"],
        "Problem": "Publisher drops transient broker messages.",
        "Next Action": "Add retry around broker publish.",
        "Blocked On": "Waiting for T-20260605-02 to expose broker retry policy.",
        "Captured Request": "Track the publisher retry follow-up.",
        "Context": "Broker publishes sometimes fail transiently.",
        "Prior Investigation": "Logs show retryable broker timeouts.",
        "Approach": "Wrap publish in bounded retry.",
        "Decisions Made": "Use bounded retry instead of unbounded replay.",
        "Acceptance Criteria": [
            "Publisher retries transient broker failures.",
            "Permanent broker failures still surface clearly.",
        ],
        "Verification": "uv run pytest plugins/turbo-mode/ticket/tests/test_publish.py -q",
        "Key Files": [
            {
                "file": "plugins/turbo-mode/ticket/scripts/publisher.py",
                "role": "Publisher",
                "look_for": "retry around broker publish",
            }
        ],
        "Related": "T-20260605-02",
    }
    mutation = GatewayMutation(
        action="create",
        ticket_id=None,
        target=target,
        proposed_change=proposed_change,
        tickets_dir=tmp_tickets,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
    )
    decision = _decision_for(
        ticket_id=None,
        action="create",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
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

    assert response.state == "ok"
    ticket_path = Path(str(response.data["ticket_path"]))
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: blocked" in text
    assert "blocked_by: [T-20260605-02]" in text
    assert "## Blocked On\nWaiting for T-20260605-02 to expose broker retry policy." in text
    assert "## Captured Request\nTrack the publisher retry follow-up." in text
    assert "## Context\nBroker publishes sometimes fail transiently." in text
    assert "## Prior Investigation\nLogs show retryable broker timeouts." in text
    assert "## Approach\nWrap publish in bounded retry." in text
    assert "## Decisions Made\nUse bounded retry instead of unbounded replay." in text
    assert "## Acceptance Criteria\n- [ ] Publisher retries transient broker failures." in text
    assert "## Verification\n```bash\nuv run pytest" in text
    assert (
        "| plugins/turbo-mode/ticket/scripts/publisher.py | Publisher | "
        "retry around broker publish |"
    ) in text
    assert "## Related\nT-20260605-02" in text


def test_gateway_replay_after_summary_recorded_does_not_rewrite_ticket(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
    )
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
    assert first.state == "ok"
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

    assert replay.state == "blocked"
    assert replay.data["recovery_state"] == "healthy"
    assert ticket_path.read_text(encoding="utf-8") == before_text
    assert _events(project_root) == before_events
    assert before_text.count("Updated ticket from candidate evidence.") == 1


def test_gateway_retry_uses_original_attempt_timestamp_for_change_history_dedupe(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    original_entry = "- 2026-05-27T12:00:00Z | codex | Updated ticket from candidate evidence."
    ticket_text = ticket_path.read_text(encoding="utf-8").rstrip()
    ticket_path.write_text(
        f"{ticket_text}\n\n## Change History\n{original_entry}\n",
        encoding="utf-8",
    )
    mutation = _mutation(tmp_tickets, ticket_path)
    pre = mutation.expected_ticket_fingerprint or ""
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

    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "priority: low" in text
    assert text.count(original_entry) == 1


def test_gateway_write_lock_clears_dead_pid_lock_and_proceeds(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
    )
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

    assert response.state == "ok"
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
    second_mutation = _mutation(tmp_tickets, ticket_path, fields={"priority": "normal"})
    first_decision = _decision_for(
        ticket_id="T-20260527-01",
        fields={"priority": "low"},
        target_fp=pre,
        turn_id="turn-first",
    )
    second_decision = _decision_for(
        ticket_id="T-20260527-01",
        fields={"priority": "normal"},
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
            dispatch_priorities.append(dict(mutation.proposed_change).get("priority"))
        try:
            if dict(mutation.proposed_change).get("priority") != "low":
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
                "ok",
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
    assert responses["first"].state == "ok"
    assert responses["second"].state == "invalid_state"
    assert responses["second"].error_code == "stale_plan"
    assert dispatch_priorities == ["low"]
    assert max_active_dispatches == 1


def test_gateway_autonomous_create_stops_at_duplicate_candidate(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    today = datetime.now(UTC).strftime("%Y%m%d")
    make_ticket(
        tmp_tickets,
        "existing.md",
        id=f"T-{today}-01",
        title="Fix auth bug",
        problem="Auth times out.",
    )
    target = CandidateTarget(fields=("title", "priority"), sections=("Problem",))
    proposed_change = {
        "title": "Fix auth bug",
        "priority": "high",
        "Problem": "Auth times out.",
    }
    candidate = CandidateMutation(
        ticket_id=None,
        action="create",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the duplicate auth fix.",
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
    mutation = GatewayMutation(
        action="create",
        ticket_id=None,
        target=target,
        proposed_change=proposed_change,
        tickets_dir=tmp_tickets,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the duplicate auth fix.",
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

    assert response.state == "blocked"
    assert response.error_code == "duplicate_candidate"
    assert len(list(tmp_tickets.glob("*.md"))) == 1


def test_gateway_returns_invalid_state_for_non_normalized_active_ticket(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    make_legacy_ticket_for_cutover(
        tmp_tickets,
        "legacy-active.md",
        id="legacy-ticket",
    )
    target_fp = "sha256:legacy-ticket-state"
    mutation = GatewayMutation(
        action="update",
        ticket_id="legacy-ticket",
        target=_target(),
        proposed_change={"priority": "low"},
        tickets_dir=tmp_tickets,
        expected_ticket_fingerprint=target_fp,
        evidence_summary="Current turn justifies this ticket change.",
    )
    decision = _decision_for(ticket_id="legacy-ticket", target_fp=target_fp)

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "invalid_state"
    assert response.error_code == "invalid_state"
    assert response.ticket_id == "legacy-ticket"
    assert _events(project_root) == []


def test_gateway_recovers_missing_write_events_without_rewriting_ticket(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    pre = mutation.expected_ticket_fingerprint or ""
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
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
    )

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
    assert blocked.state == "blocked"
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
    assert paused.state == "blocked"
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
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
    )
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

    assert response.state == "blocked"
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
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target_fp=mutation.expected_ticket_fingerprint or "",
    )

    monkeypatch.setattr(
        gateway,
        "_execute_dispatch",
        lambda **_kwargs: EngineResponse("ok", "Updated without path", data={}),
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

    assert response.state == "blocked"
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
        GatewayMutation(
            action="done",
            ticket_id="T-1",
            target=CandidateTarget(fields=("status",), sections=()),
            proposed_change={"status": "done"},
            tickets_dir=tmp_tickets,
            expected_ticket_fingerprint="fp",
            evidence_summary="Current turn justifies closing the ticket.",
        ),
    )
    wontfix = build_engine_dispatch(
        GatewayMutation(
            action="wontfix",
            ticket_id="T-1",
            target=CandidateTarget(fields=("status",), sections=()),
            proposed_change={"status": "wontfix"},
            tickets_dir=tmp_tickets,
            expected_ticket_fingerprint="fp",
            evidence_summary="Current turn justifies closing the ticket.",
        ),
    )
    update = build_engine_dispatch(
        GatewayMutation(
            action="update",
            ticket_id="T-1",
            target=_target(),
            proposed_change={"priority": "low"},
            tickets_dir=tmp_tickets,
            expected_ticket_fingerprint="fp",
            evidence_summary="Current turn justifies updating the ticket.",
        ),
    )
    reopen = build_engine_dispatch(
        GatewayMutation(
            action="reopen",
            ticket_id="T-1",
            target=CandidateTarget(fields=("status",), sections=()),
            proposed_change={"status": "open"},
            tickets_dir=tmp_tickets,
            expected_ticket_fingerprint="fp",
            evidence_summary="Current turn justifies reopening the ticket.",
        ),
    )
    archive = build_engine_dispatch(
        GatewayMutation(
            action="done",
            ticket_id="T-1",
            target=CandidateTarget(fields=("status",), sections=()),
            proposed_change={"status": "done", "archive": True},
            tickets_dir=tmp_tickets,
            expected_ticket_fingerprint="fp",
            evidence_summary="Current turn justifies closing the ticket.",
        ),
    )

    assert done.action.value == "close"
    assert done.fields == {"resolution": "done"}
    assert wontfix.action.value == "close"
    assert wontfix.fields == {"resolution": "wontfix"}
    assert update.action.value == "update"
    assert update.fields == {"priority": "low"}
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
