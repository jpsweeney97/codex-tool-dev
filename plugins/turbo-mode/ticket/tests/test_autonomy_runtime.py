"""Tests for runtime-first autonomy decisions."""

from __future__ import annotations

from datetime import UTC, datetime

from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    EngineAction,
    EvidenceLink,
    RuntimeDecisionKind,
    TicketChangeScope,
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
    ticket_change_scope: TicketChangeScope = "current_branch",
) -> CandidateMutation:
    change = {"field": "value"} if proposed_change is None else proposed_change
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=change,
        evidence=evidence or _evidence("current_thread_reason"),
        conflict_reason=conflict_reason,
        ticket_change_scope=ticket_change_scope,
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
        assert decision.approval is not None


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


def test_approval_envelope_binds_decision_context_and_expires_within_ten_minutes() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate)[0]

    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.approval is not None
    approval = decision.approval
    assert approval["thread_id"] == "thread-1"
    assert approval["ticket_id"] == candidate.ticket_id
    assert approval["mutation_id"] == decision.mutation_id
    assert approval["current_mode"] == "agent_primary"
    assert approval["decision"] == "apply_autonomously"
    assert approval["ticket_state_fingerprint"] == f"state-{candidate.ticket_id}"
    assert approval["mutation_fingerprint"]
    assert approval["evidence_fingerprint"]
    assert approval["approval_id"].startswith("appr_")
    assert approval["created_at"] == "2026-05-27T12:00:00Z"
    assert approval["expires_at"] == "2026-05-27T12:10:00Z"


def test_ticket_change_scope_binds_mutation_identity_and_approval_fingerprint() -> None:
    current_branch = _decisions(
        _candidate("update", ticket_change_scope="current_branch"),
    )[0]
    unrelated_backlog = _decisions(
        _candidate("update", ticket_change_scope="unrelated_backlog"),
    )[0]

    assert current_branch.mutation_id != unrelated_backlog.mutation_id
    assert current_branch.approval is not None
    assert unrelated_backlog.approval is not None
    assert (
        current_branch.approval["mutation_fingerprint"]
        != unrelated_backlog.approval["mutation_fingerprint"]
    )


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
