"""Tests for runtime-first autonomy decisions."""

from __future__ import annotations

from datetime import UTC, datetime

from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    EngineAction,
    EvidenceLink,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
    map_candidate_to_engine,
)

NOW = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def _evidence(*kinds: str) -> tuple[EvidenceLink, ...]:
    return tuple(EvidenceLink(kind=kind, ref=f"{kind}:ref") for kind in kinds)


def _candidate(
    action: str,
    *,
    ticket_id: str = "T-20260527-01",
    proposed_change: dict[str, object] | None = None,
    evidence: tuple[EvidenceLink, ...] | None = None,
    conflict_reason: str | None = None,
) -> CandidateMutation:
    change = {"field": "value"} if proposed_change is None else proposed_change
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=change,
        evidence=evidence or _evidence("current_thread_reason"),
        conflict_reason=conflict_reason,
    )


def _intent(*candidates: CandidateMutation, **context: object) -> AutonomyIntent:
    source_context: dict[str, object] = {
        "ticket_state_fingerprints": {
            candidate.ticket_id: f"state-{candidate.ticket_id}" for candidate in candidates
        },
    }
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


def test_ordinary_candidates_apply_autonomously_with_agent_primary_and_evidence() -> None:
    candidates = [
        _candidate("update", evidence=_evidence("current_thread_reason")),
        _candidate("blocker_edit", evidence=_evidence("explicit_ticket")),
        _candidate("refine", evidence=_evidence("explicit_ticket")),
        _candidate(
            "done",
            proposed_change={},
            evidence=_evidence("ticket_state", "current_thread_reason"),
        ),
        _candidate("wontfix", proposed_change={}, evidence=_evidence("user_decision")),
        _candidate(
            "reopen",
            proposed_change={"reopen_reason": "Regression recurred."},
            evidence=_evidence("ticket_state", "current_thread_reason"),
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
            proposed_change={"archive": True},
            evidence=_evidence("ticket_state", "current_thread_reason"),
        ),
        _candidate(
            "wontfix",
            proposed_change={"resolution": "wontfix", "extra": "field"},
            evidence=_evidence("user_decision"),
        ),
    ]

    decisions = _decisions(*candidates, shared_decision_evidence=True)

    assert [decision.kind for decision in decisions] == [
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
        RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
    ]


def test_discussion_only_does_not_authorize_writes() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    discussion = _decisions(candidate, mode="discussion_only")[0]

    assert discussion.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert discussion.reason == "discussion_only"


def test_unsupported_preview_mode_requires_discussion_without_preview_decision() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate, mode="preview")[0]

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "unsupported_mode"
    assert decision.pending_summary_status == "discussion_required"


def test_conflicting_candidates_are_skipped() -> None:
    decision = _decisions(
        _candidate(
            "update",
            evidence=_evidence("current_thread_reason"),
            conflict_reason="ticket contradicts current thread",
        )
    )[0]

    assert decision.kind == RuntimeDecisionKind.SKIP_DUE_TO_CONFLICT
    assert decision.pending_summary_status == "skipped"


def test_fanout_caps_keep_above_cap_candidates_as_pending_summary_records() -> None:
    metadata = [_candidate("update", ticket_id=f"T-20260527-0{i}") for i in range(1, 7)]
    blockers = [
        _candidate(
            "blocker_edit",
            ticket_id=f"T-20260527-1{i}",
            evidence=_evidence("explicit_ticket"),
        )
        for i in range(1, 5)
    ]
    lifecycle = [
        _candidate(
            "done",
            ticket_id=f"T-20260527-2{i}",
            proposed_change={},
            evidence=_evidence("ticket_state", "current_thread_reason"),
        )
        for i in range(1, 4)
    ]
    wontfix = [
        _candidate(
            "wontfix",
            ticket_id=f"T-20260527-3{i}",
            proposed_change={},
            evidence=_evidence("user_decision"),
        )
        for i in range(1, 3)
    ]

    metadata_decisions = _decisions(*metadata)
    blocker_decisions = _decisions(*blockers)
    lifecycle_decisions = _decisions(*lifecycle, explicit_linked_batch=True)
    wontfix_decisions = _decisions(*wontfix)

    assert [decision.kind for decision in metadata_decisions].count(
        RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    ) == 5
    assert metadata_decisions[-1].kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert metadata_decisions[-1].pending_summary_status == "discussion_required"
    assert [decision.kind for decision in blocker_decisions].count(
        RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    ) == 3
    assert blocker_decisions[-1].pending_summary_status == "discussion_required"
    assert [decision.kind for decision in lifecycle_decisions].count(
        RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    ) == 2
    assert lifecycle_decisions[-1].pending_summary_status == "discussion_required"
    assert all(
        decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
        for decision in wontfix_decisions
    )


def test_agent_primary_decision_uses_mutation_id() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate)[0]

    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.mutation_id is not None
    assert decision.mutation_id.startswith("mut_")
    assert decision.engine_dispatch is not None
    assert decision.engine_dispatch.state == "ok"
    assert decision.reason == "authorized"


def test_target_fingerprint_binds_mutation_identity_for_non_create() -> None:
    candidate = _candidate("update")
    first = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-a"},
    )[0]
    second = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-b"},
    )[0]

    assert first.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert second.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert first.mutation_id != second.mutation_id


def test_non_create_candidate_requires_target_fingerprint_for_identity() -> None:
    decision = _decisions(
        _candidate("update"),
        ticket_state_fingerprints={},
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "target_fingerprint_required"
    assert decision.pending_summary_status == "ticket_update_blocked"
    assert decision.mutation_id is None


def test_correction_target_fingerprint_binds_mutation_identity() -> None:
    candidate = _candidate(
        "correction",
        proposed_change={"resolution": "done"},
        evidence=_evidence("correction_detail"),
    )
    first = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-a"},
    )[0]
    second = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-b"},
    )[0]

    assert first.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert second.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert first.mutation_id != second.mutation_id


def test_correction_requires_target_fingerprint_for_identity() -> None:
    decision = _decisions(
        _candidate(
            "correction",
            proposed_change={"resolution": "done"},
            evidence=_evidence("correction_detail"),
        ),
        ticket_state_fingerprints={},
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "target_fingerprint_required"
    assert decision.pending_summary_status == "ticket_update_blocked"
    assert decision.mutation_id is None


def test_candidate_mutation_has_no_ticket_change_scope_field() -> None:
    candidate = _candidate("update")

    assert not hasattr(candidate, "ticket_change_scope")


def test_ticket_actions_map_to_engine_dispatch_exactly() -> None:
    done = map_candidate_to_engine(
        _candidate("done", proposed_change={}, evidence=_evidence("ticket_state")),
    )
    wontfix = map_candidate_to_engine(
        _candidate("wontfix", proposed_change={}, evidence=_evidence("user_decision")),
    )
    update = map_candidate_to_engine(_candidate("blocker_edit", proposed_change={"blocks": []}))
    reopen = map_candidate_to_engine(
        _candidate("reopen", proposed_change={"reopen_reason": "Regression recurred."}),
    )

    assert done.action == EngineAction.CLOSE
    assert done.fields == {"resolution": "done"}
    assert wontfix.action == EngineAction.CLOSE
    assert wontfix.fields == {"resolution": "wontfix"}
    assert update.action == EngineAction.UPDATE
    assert update.fields == {"blocks": []}
    assert reopen.action == EngineAction.REOPEN
    assert reopen.fields == {"reopen_reason": "Regression recurred."}


def test_direct_generic_agent_origin_reopen_is_policy_blocked_outside_gateway() -> None:
    dispatch = map_candidate_to_engine(
        _candidate("reopen", proposed_change={"reopen_reason": "Regression recurred."}),
        gateway_approved=False,
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "gateway_required"
