from scripts.ticket_autonomy_runtime import CandidateTarget
from scripts.ticket_mutation_identity import (
    candidate_mutation_payload,
    make_candidate_mutation_identity,
)


def _identity(
    *,
    expected_ticket_fingerprint: str | None = "ticket-state-a",
    evidence_summary: str = "Priority changed after this turn.",
):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def test_expected_fingerprint_binds_mutation_identity() -> None:
    first = _identity(expected_ticket_fingerprint="ticket-state-a")
    second = _identity(expected_ticket_fingerprint="ticket-state-b")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_evidence_summary_binds_mutation_identity() -> None:
    first = _identity(evidence_summary="Priority changed after this turn.")
    second = _identity(evidence_summary="Priority changed after user review.")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_candidate_payload_uses_target_contract_keys() -> None:
    payload = candidate_mutation_payload(
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority",), sections=("Next Action",)),
        proposed_change={
            "priority": "high",
            "Next Action": "Finish the migration.",
        },
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )

    assert payload == {
        "ticket_id": "T-20260527-01",
        "action": "update",
        "target": {"fields": ["priority"], "sections": ["Next Action"]},
        "proposed_change": {
            "priority": "high",
            "Next Action": "Finish the migration.",
        },
        "expected_ticket_fingerprint": "ticket-state-a",
        "evidence_summary": "Priority changed after this turn.",
    }


def test_candidate_identity_canonicalizes_target_order() -> None:
    first = make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(
            fields=("priority", "tags"),
            sections=("Context", "Next Action"),
        ),
        proposed_change={
            "priority": "high",
            "tags": ["ticket"],
            "Context": "Important context.",
            "Next Action": "Finish the migration.",
        },
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )
    second = make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(
            fields=("tags", "priority"),
            sections=("Next Action", "Context"),
        ),
        proposed_change={
            "Next Action": "Finish the migration.",
            "Context": "Important context.",
            "tags": ["ticket"],
            "priority": "high",
        },
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )

    assert first.mutation_fingerprint == second.mutation_fingerprint
    assert first.mutation_id == second.mutation_id


def test_identity_is_deterministic_for_identical_inputs() -> None:
    first = _identity(expected_ticket_fingerprint="ticket-state-a")
    second = _identity(expected_ticket_fingerprint="ticket-state-a")

    assert first.mutation_id == second.mutation_id
    assert first.mutation_fingerprint == second.mutation_fingerprint
    assert first.evidence_fingerprint == second.evidence_fingerprint
