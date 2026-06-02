from scripts.ticket_mutation_identity import make_candidate_mutation_identity


def _identity(
    *,
    target_fingerprint: str | None = "ticket-state-a",
    ticket_change_scope: str = "current_branch",
):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        proposed_change={"priority": "high"},
        ticket_change_scope=ticket_change_scope,
        target_fingerprint=target_fingerprint,
        evidence=(
            {"kind": "current_thread_reason", "ref": "test", "freshness": "fresh"},
        ),
    )


def test_target_fingerprint_binds_mutation_identity() -> None:
    first = _identity(target_fingerprint="ticket-state-a")
    second = _identity(target_fingerprint="ticket-state-b")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint
    assert first.evidence_fingerprint == second.evidence_fingerprint


def test_helper_hashes_missing_target_fingerprint_without_policy_decision() -> None:
    missing = _identity(target_fingerprint=None)
    present = _identity(target_fingerprint="ticket-state-a")

    assert missing.mutation_id != present.mutation_id
    assert missing.mutation_fingerprint != present.mutation_fingerprint


def test_ticket_change_scope_binds_identity_until_scope_slice() -> None:
    current_branch = _identity(ticket_change_scope="current_branch")
    unrelated_backlog = _identity(ticket_change_scope="unrelated_backlog")

    assert current_branch.mutation_id != unrelated_backlog.mutation_id
