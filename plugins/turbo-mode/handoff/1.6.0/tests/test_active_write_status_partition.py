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
