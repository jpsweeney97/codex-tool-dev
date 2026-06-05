"""Status vocabulary guardrails for target Ticket surfaces."""

from __future__ import annotations

import scripts.ticket_engine_core as ticket_engine_core
import scripts.ticket_read as ticket_read
import scripts.ticket_target_schema as target_schema
import scripts.ticket_triage as ticket_triage


def test_transition_table_covers_target_statuses() -> None:
    assert set(ticket_engine_core._VALID_TRANSITIONS) == set(target_schema.TARGET_STATUSES)


def test_read_sort_rank_covers_target_statuses() -> None:
    assert set(ticket_read.STATUS_SORT_RANK) == set(target_schema.TARGET_STATUSES)


def test_triage_counts_derive_from_active_target_statuses(tmp_tickets) -> None:
    result = ticket_triage.triage_dashboard(tmp_tickets)

    assert set(result["counts"]) == set(target_schema.TARGET_ACTIVE_STATUSES)
    assert tuple(result["counts"]) == target_schema.TARGET_ACTIVE_STATUSES


def test_terminal_status_constant_is_shared() -> None:
    assert ticket_engine_core._TERMINAL_STATUSES is target_schema.TARGET_TERMINAL_STATUSES
    assert ticket_triage._TERMINAL_STATUSES is target_schema.TARGET_TERMINAL_STATUSES
