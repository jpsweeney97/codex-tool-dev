"""Tests for runtime-first autonomy decisions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    CandidateTarget,
    EngineAction,
    RuntimeDecisionKind,
    candidate_mapping_errors,
    candidate_mutation_from_mapping,
    evaluate_autonomy_intent,
    map_candidate_to_engine,
)

NOW = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def _target(
    *,
    fields: tuple[str, ...] = ("priority",),
    sections: tuple[str, ...] = (),
) -> CandidateTarget:
    return CandidateTarget(fields=fields, sections=sections)


def _candidate(
    action: str,
    *,
    ticket_id: str | None = "T-20260527-01",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = "state-T-20260527-01",
    evidence_summary: str = "Current turn justifies this ticket change.",
) -> CandidateMutation:
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target or _target(),
        proposed_change={"priority": "low"} if proposed_change is None else proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def _intent(*candidates: CandidateMutation, **context: object) -> AutonomyIntent:
    source_context: dict[str, object] = {}
    source_context.update(context)
    return AutonomyIntent(
        action_kind=candidates[0].action if candidates else "update",
        candidates=tuple(candidates),
        source_context=source_context,
    )


def _decisions(*candidates: CandidateMutation, mode: str = "agent_primary", **context: object):
    return evaluate_autonomy_intent(
        _intent(*candidates, **context),
        current_mode=mode,
        thread_id="thread-1",
        turn_id="turn-1",
        now=NOW,
    )


def test_candidate_mapping_rejects_unknown_top_level_keys() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
            "legacy_reason": "old shape",
        }
    )

    assert errors == ["unknown candidate keys: ['legacy_reason']"]


def test_candidate_mapping_rejects_missing_top_level_keys() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
        }
    )

    assert errors == ["missing candidate keys: ['evidence_summary']"]


def test_candidate_mapping_rejects_conflict_reason_as_candidate_content() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
            "conflict_reason": "conflicting evidence",
        }
    )

    assert errors == ["unknown candidate keys: ['conflict_reason']"]


def test_candidate_mapping_requires_exact_target_closure() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": ["Next Action"]},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == [
        "proposed_change keys must exactly match target fields and sections; "
        "missing ['Next Action']; extra []"
    ]


@pytest.mark.parametrize("action", ("create", "update", "done", "wontfix", "reopen", "correct"))
def test_candidate_mapping_rejects_empty_target(action: str) -> None:
    ticket_id = None if action == "create" else "T-20260527-01"
    expected_ticket_fingerprint = None if action == "create" else "state-T-20260527-01"

    errors = candidate_mapping_errors(
        {
            "action": action,
            "ticket_id": ticket_id,
            "target": {"fields": [], "sections": []},
            "proposed_change": {},
            "expected_ticket_fingerprint": expected_ticket_fingerprint,
            "evidence_summary": "Current turn justifies this ticket change.",
        }
    )

    assert "target must name at least one field or section" in errors


def test_candidate_mapping_rejects_duplicate_target_names() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority", "priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == ["target.fields contains duplicate names: ['priority']"]


def test_candidate_mapping_rejects_field_section_overlap() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": ["priority"]},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == ["target names cannot appear in both fields and sections: ['priority']"]


def test_candidate_mapping_rejects_invalid_target_section_names() -> None:
    for section_name in ("Bad\nName", "Bad | Name", "### Bad"):
        errors = candidate_mapping_errors(
            {
                "action": "update",
                "ticket_id": "T-20260527-01",
                "target": {"fields": ["priority"], "sections": [section_name]},
                "proposed_change": {"priority": "high", section_name: "unsafe"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed after this turn.",
            }
        )

        assert errors == [f"target.sections contains invalid section names: {[section_name]!r}"]


def test_create_allows_null_ticket_id_and_null_expected_fingerprint() -> None:
    candidate = candidate_mutation_from_mapping(
        {
            "action": "create",
            "ticket_id": None,
            "target": {
                "fields": ["title", "priority"],
                "sections": ["Problem", "Next Action"],
            },
            "proposed_change": {
                "title": "Add retry to publisher",
                "priority": "high",
                "Problem": "Publisher drops transient broker messages.",
                "Next Action": "Add retry around broker publish.",
            },
            "expected_ticket_fingerprint": None,
            "evidence_summary": "The user asked to track the publisher retry follow-up.",
        }
    )

    assert candidate is not None
    assert candidate.ticket_id is None
    assert candidate.target.fields == ("title", "priority")
    assert candidate.target.sections == ("Problem", "Next Action")
    assert candidate.expected_ticket_fingerprint is None


def test_create_rejects_wrong_type_ticket_id_and_expected_fingerprint() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "create",
            "ticket_id": 123,
            "target": {"fields": ["title"], "sections": ["Problem", "Next Action"]},
            "proposed_change": {
                "title": "Add retry to publisher",
                "Problem": "Publisher drops transient broker messages.",
                "Next Action": "Add retry around broker publish.",
            },
            "expected_ticket_fingerprint": 123,
            "evidence_summary": "The user asked to track the publisher retry follow-up.",
        }
    )

    assert errors == [
        "ticket_id must be a string or null",
        "expected_ticket_fingerprint must be a string or null",
    ]


def test_candidate_mapping_rejects_wrong_type_action_and_evidence_summary() -> None:
    errors = candidate_mapping_errors(
        {
            "action": ["update"],
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": {"reason": "Priority changed."},
        }
    )

    assert errors == [
        "action must be a string",
        "evidence_summary must be a string",
    ]


def test_ordinary_candidates_apply_autonomously_with_agent_primary() -> None:
    candidates = [
        _candidate("update"),
        _candidate(
            "done",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "done"},
        ),
        _candidate(
            "wontfix",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "wontfix"},
        ),
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
        ),
    ]

    for candidate in candidates:
        decision = _decisions(candidate, shared_decision_evidence=True)[0]
        assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
        assert decision.mutation_id is not None
        assert decision.reason == "authorized"


def test_destructive_and_history_actions_require_user_discussion() -> None:
    decisions = _decisions(
        _candidate("delete"),
        _candidate("archive"),
        _candidate("history_repair"),
    )

    assert [decision.kind for decision in decisions] == [
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
    ]


def test_close_archive_or_extra_fields_cannot_be_smuggled_through_auto_close() -> None:
    candidates = [
        _candidate(
            "done",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "done", "archive": True},
        ),
        _candidate(
            "wontfix",
            target=_target(fields=("status", "priority"), sections=()),
            proposed_change={"status": "wontfix", "priority": "low"},
        ),
    ]

    decisions = _decisions(*candidates, shared_decision_evidence=True)

    assert [decision.kind for decision in decisions] == [
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
    ]


def test_discussion_only_does_not_authorize_writes() -> None:
    candidate = _candidate("update")

    discussion = _decisions(candidate, mode="discussion_only")[0]

    assert discussion.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert discussion.reason == "discussion_only"


def test_unsupported_preview_mode_requires_discussion_without_preview_decision() -> None:
    candidate = _candidate("update")

    decision = _decisions(candidate, mode="preview")[0]

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "unsupported_mode"
    assert decision.pending_summary_status == "discussion_required"


def test_fanout_caps_keep_above_cap_candidates_as_pending_summary_records() -> None:
    metadata = [_candidate("update", ticket_id=f"T-20260527-0{i}") for i in range(1, 7)]
    lifecycle = [
        _candidate(
            "done",
            ticket_id=f"T-20260527-2{i}",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "done"},
        )
        for i in range(1, 4)
    ]
    wontfix = [
        _candidate(
            "wontfix",
            ticket_id=f"T-20260527-3{i}",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "wontfix"},
        )
        for i in range(1, 3)
    ]

    metadata_decisions = _decisions(*metadata)
    lifecycle_decisions = _decisions(*lifecycle, explicit_linked_batch=True)
    wontfix_decisions = _decisions(*wontfix)

    assert [decision.kind for decision in metadata_decisions].count(
        RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    ) == 5
    assert metadata_decisions[-1].kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert metadata_decisions[-1].pending_summary_status == "discussion_required"
    assert [decision.kind for decision in lifecycle_decisions].count(
        RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    ) == 2
    assert lifecycle_decisions[-1].pending_summary_status == "discussion_required"
    assert all(
        decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
        for decision in wontfix_decisions
    )


def test_agent_primary_decision_uses_mutation_id() -> None:
    candidate = _candidate("update")

    decision = _decisions(candidate)[0]

    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.mutation_id is not None
    assert decision.mutation_id.startswith("mut_")
    assert decision.engine_dispatch is not None
    assert decision.engine_dispatch.state == "ok"
    assert decision.reason == "authorized"


def test_expected_fingerprint_binds_mutation_identity_for_non_create() -> None:
    first = _decisions(
        _candidate("update", expected_ticket_fingerprint="ticket-state-a"),
    )[0]
    second = _decisions(
        _candidate("update", expected_ticket_fingerprint="ticket-state-b"),
    )[0]

    assert first.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert second.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert first.mutation_id != second.mutation_id


def test_non_create_requires_expected_ticket_fingerprint() -> None:
    decision = _decisions(
        _candidate("update", expected_ticket_fingerprint=None),
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "expected_ticket_fingerprint_required"
    assert decision.pending_summary_status == "ticket_update_blocked"
    assert decision.mutation_id is None


def test_candidate_mutation_has_no_ticket_change_scope_field() -> None:
    candidate = _candidate("update")

    assert not hasattr(candidate, "ticket_change_scope")


def test_ticket_actions_map_to_engine_dispatch_exactly() -> None:
    done = map_candidate_to_engine(
        _candidate(
            "done",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "done"},
        ),
    )
    wontfix = map_candidate_to_engine(
        _candidate(
            "wontfix",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "wontfix"},
        ),
    )
    update = map_candidate_to_engine(_candidate("update", proposed_change={"priority": "low"}))
    reopen = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
            evidence_summary="Regression recurred.",
        ),
    )

    assert done.action == EngineAction.CLOSE
    assert done.fields == {"resolution": "done"}
    assert wontfix.action == EngineAction.CLOSE
    assert wontfix.fields == {"resolution": "wontfix"}
    assert update.action == EngineAction.UPDATE
    assert update.fields == {"priority": "low"}
    assert reopen.action == EngineAction.REOPEN
    assert reopen.fields == {"status": "open"}


def test_reopen_uses_evidence_summary_not_reopen_reason() -> None:
    rejected = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open", "reopen_reason": "Regression recurred."},
        )
    )
    accepted = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
            evidence_summary="Regression recurred.",
        )
    )

    assert rejected.state == "policy_blocked"
    assert rejected.reason == "target_closure_failed"
    assert accepted.action == EngineAction.REOPEN
    assert accepted.fields == {"status": "open"}


def test_direct_generic_agent_origin_reopen_is_policy_blocked_outside_gateway() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
        ),
        gateway_approved=False,
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "gateway_required"


def test_blocked_close_status_only_target_is_rejected() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "done",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "done"},
        ),
        current_ticket_status="blocked",
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "close_target_not_allowlisted"


def test_blocked_close_target_names_blocker_cleanup() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "done",
            target=_target(fields=("status", "blocked_by"), sections=("Blocked On",)),
            proposed_change={"status": "done", "blocked_by": [], "Blocked On": None},
        ),
        current_ticket_status="blocked",
    )

    assert dispatch.action == EngineAction.CLOSE
    assert dispatch.fields == {"resolution": "done"}
    assert dispatch.sections == {"Blocked On": None}


def test_correct_close_rejects_mixed_status_and_metadata_target() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status", "priority"), sections=()),
            proposed_change={"status": "done", "priority": "high"},
        )
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "close_target_not_allowlisted"


def test_correct_active_status_defaults_to_update_without_current_terminal_status() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status", "blocked_by"), sections=("Blocked On",)),
            proposed_change={
                "status": "blocked",
                "blocked_by": ["T-20260527-02"],
                "Blocked On": "Waiting for T-20260527-02.",
            },
        )
    )

    assert dispatch.action == EngineAction.UPDATE
    assert dispatch.fields == {
        "status": "blocked",
        "blocked_by": ["T-20260527-02"],
    }
    assert dispatch.sections == {"Blocked On": "Waiting for T-20260527-02."}


def test_correct_reopens_only_when_current_ticket_is_terminal() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
        ),
        current_ticket_status="done",
    )

    assert dispatch.action == EngineAction.REOPEN
    assert dispatch.fields == {"status": "open"}
