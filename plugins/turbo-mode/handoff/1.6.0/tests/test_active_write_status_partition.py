from __future__ import annotations

from typing import get_args

import turbo_mode_handoff_runtime.active_writes as active_writes

# Source-grounded expected vocabularies (see plan "Source-Grounded Status
# Vocabulary"). Every member has a verified source site in active_writes.py:
# a write site, except the synthetic read-path "unreadable" record
# (constructed in _unreadable_active_write_record, never persisted).
EXPECTED_OPERATION_STATE_STATUSES = {
    "begun",
    "pending_before_write",
    "content-generated",
    "content_mismatch",
    "write-pending",
    "cleanup_failed",
    "committed",
    "abandoned",
    "reservation_expired",
    "reservation_conflict",
    "unreadable",
}
EXPECTED_TRANSACTION_STATUSES = {
    "pending_before_write",
    "content-generated",
    "content_mismatch",
    "write-pending",
    "cleanup_failed",
    "completed",
    "abandoned",
    "reservation_expired",
    "reservation_conflict",
}


def test_operation_state_status_alias_matches_source_vocabulary() -> None:
    members = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    assert members == EXPECTED_OPERATION_STATE_STATUSES


def test_transaction_status_alias_matches_source_vocabulary() -> None:
    members = set(get_args(active_writes.ActiveWriteTransactionStatus))
    assert members == EXPECTED_TRANSACTION_STATUSES


def test_discriminating_invariant_committed_is_operation_state_only() -> None:
    op = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    tx = set(get_args(active_writes.ActiveWriteTransactionStatus))
    assert "committed" in op and "committed" not in tx
    assert "completed" in tx and "completed" not in op
    assert {"begun", "unreadable"} <= op
    assert not ({"begun", "unreadable"} & tx)


def test_shared_statuses_are_exactly_the_documented_overlap() -> None:
    op = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    tx = set(get_args(active_writes.ActiveWriteTransactionStatus))
    assert op & tx == {
        "pending_before_write",
        "content-generated",
        "content_mismatch",
        "write-pending",
        "cleanup_failed",
        "abandoned",
        "reservation_expired",
        "reservation_conflict",
    }


# Source-grounded from session_state.py:51-53 (write-transaction terminal
# {committed, abandoned, reservation_expired} ∪ load-transaction terminal
# {completed, abandoned}). This is a TTL-prune ALLOW-LIST: a subset-only
# check would let a future edit silently drop a required terminal (e.g.
# 'completed') and still pass, disabling pruning for it. Pin it EXACTLY.
EXPECTED_TERMINAL_TRANSACTION_STATUSES = {
    "committed",
    "completed",
    "abandoned",
    "reservation_expired",
}


def test_terminal_transaction_statuses_align_with_partition() -> None:
    """session_state.TERMINAL_TRANSACTION_STATUSES is the cross-domain
    TTL-prune terminal allow-list. It is pinned EXACTLY (completeness, not
    just 'no unknowns' — dropping a required terminal silently disables its
    pruning), and its partition linkage is documented. Enforced in the test
    layer to avoid a session_state -> active_writes module-level import
    (documented layering trap, ARCHITECTURE.md:18)."""
    import turbo_mode_handoff_runtime.session_state as session_state

    terminal = set(session_state.TERMINAL_TRANSACTION_STATUSES)
    op = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    tx = set(get_args(active_writes.ActiveWriteTransactionStatus))

    # Exact pin: catches BOTH unknown additions AND silent omissions.
    assert terminal == EXPECTED_TERMINAL_TRANSACTION_STATUSES, (
        f"TERMINAL_TRANSACTION_STATUSES drifted from the source-grounded "
        f"allow-list: missing={EXPECTED_TERMINAL_TRANSACTION_STATUSES - terminal} "
        f"unexpected={terminal - EXPECTED_TERMINAL_TRANSACTION_STATUSES}"
    )
    # Partition linkage (diagnostic specificity + documents WHY each member
    # is allowed): every member is a known status in some domain; every
    # non-'committed' member is a valid transaction status ('committed' is
    # the op-only cross-domain member).
    assert terminal <= (op | tx), f"unknown terminal status(es): {terminal - (op | tx)}"
    assert (terminal - {"committed"}) <= tx, (
        f"non-'committed' terminals not in transaction alias: "
        f"{(terminal - {'committed'}) - tx}"
    )
