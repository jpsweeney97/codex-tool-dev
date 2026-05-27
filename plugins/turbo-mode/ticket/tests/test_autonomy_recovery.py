"""Tests for pending-summary recovery projection."""

from __future__ import annotations

from pathlib import Path

from scripts.ticket_autonomy_ids import make_mutation_id
from scripts.ticket_turn_batch import PendingSummaryStore

from tests.test_turn_batch import (
    project_root_with_ignored_workspace,
    valid_attempt_event,
    valid_status_event,
)


def test_thread_scoped_mutation_ids_create_separate_recovery_state(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    common = {
        "schema": "codex.ticket.mutation.v1",
        "turn_id": "turn-1",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "mutation_fingerprint": "mutfp",
        "evidence_fingerprint": "evfp",
    }
    mutation_1 = make_mutation_id(thread_id="thread-1", **common)
    mutation_2 = make_mutation_id(thread_id="thread-2", **common)

    store.append_event(
        valid_attempt_event(event_id="evt_1", thread_id="thread-1", mutation_id=mutation_1)
    )
    store.append_event(
        valid_attempt_event(event_id="evt_2", thread_id="thread-2", mutation_id=mutation_2)
    )

    assert mutation_1 != mutation_2
    assert store.derive_mutation_state(thread_id="thread-1", mutation_id=mutation_1) == (
        "attempt_recorded"
    )
    assert store.derive_mutation_state(thread_id="thread-2", mutation_id=mutation_2) == (
        "attempt_recorded"
    )
    assert store.derive_mutation_state(thread_id="thread-1", mutation_id=mutation_2) == (
        "no_attempt"
    )


def test_recovery_derives_mutation_state_from_events(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    thread_id = "thread-1"
    mutation_id = "mut_recover"

    assert store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id) == (
        "no_attempt"
    )

    store.append_event(
        valid_attempt_event(event_id="evt_attempt", thread_id=thread_id, mutation_id=mutation_id)
    )
    assert store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id) == (
        "attempt_recorded"
    )

    store.append_event(
        valid_status_event(
            "approval_consumed",
            event_id="evt_approval",
            thread_id=thread_id,
            mutation_id=mutation_id,
        )
    )
    assert store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id) == (
        "approval_consumed"
    )

    store.append_event(
        valid_status_event(
            "ticket_written",
            event_id="evt_written",
            thread_id=thread_id,
            mutation_id=mutation_id,
        )
    )
    assert store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id) == (
        "ticket_written"
    )

    store.append_event(
        valid_status_event(
            "applied",
            event_id="evt_applied",
            thread_id=thread_id,
            mutation_id=mutation_id,
        )
    )
    assert store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id) == (
        "status_recorded"
    )

    store.append_event(
        valid_attempt_event(
            event_id="evt_summary",
            event_type="summary_receipt",
            status="summarized",
            thread_id=thread_id,
            mutation_id=mutation_id,
            details={},
        )
    )
    assert store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id) == (
        "summary_recorded"
    )
