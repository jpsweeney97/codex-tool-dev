"""Tests for pending-summary recovery projection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from scripts.ticket_autonomy_ids import make_mutation_id
from scripts.ticket_turn_batch import (
    PendingSummaryStore,
    project_mutation_recovery,
    validate_pending_summary_event,
)

from tests.test_turn_batch import (
    project_root_with_ignored_workspace,
    valid_attempt_event,
    valid_status_event,
)


def _event_with_bound_fingerprints(
    event: dict[str, object],
    *,
    pre: str = "pre-fp",
    post: str = "post-fp",
) -> dict[str, object]:
    details = dict(event["details"])
    details["expected_pre_write_fingerprint"] = pre
    details["expected_post_write_fingerprint"] = post
    approval = details.get("approval")
    if isinstance(approval, Mapping):
        details["approval"] = {
            **dict(approval),
            "ticket_state_fingerprint": pre,
        }
    return {**event, "details": details}


def _append_ok(store: PendingSummaryStore, event: dict[str, object]) -> None:
    result = store.append_event(event)
    assert result.state == "appended"


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


def test_attempt_recorded_retries_only_same_mutation_when_pre_write_matches(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="pre-fp",
    )
    other_thread = project_mutation_recovery(
        store=store,
        thread_id="thread-2",
        mutation_id="mut_recover",
        current_ticket_fingerprint="pre-fp",
    )
    stale = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="other-fp",
    )

    assert projection.state == "retry_with_same_mutation"
    assert projection.events_to_append == ()
    assert projection.expected_pre_write_fingerprint == "pre-fp"
    assert projection.expected_post_write_fingerprint == "post-fp"
    assert other_thread.state == "healthy"
    assert stale.state == "pause_for_reconciliation"


def test_approval_consumed_with_post_write_state_appends_missing_write_events(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_status_event(
                "approval_consumed",
                event_id="evt_approval",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="post-fp",
    )

    assert projection.state == "append_missing_ticket_written"
    assert [event["status"] for event in projection.events_to_append] == [
        "ticket_written",
        "applied",
    ]
    assert all(validate_pending_summary_event(event).ok for event in projection.events_to_append)
    assert projection.events_to_append[0]["details"]["post_write_fingerprint"] == "post-fp"
    assert projection.events_to_append[1]["details"]["commit_disposition"] == "commit_deferred"


def test_approval_consumed_with_pre_write_state_retries_same_mutation(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_status_event(
                "approval_consumed",
                event_id="evt_approval",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="pre-fp",
    )

    assert projection.state == "retry_with_same_mutation"
    assert projection.events_to_append == ()


def test_approval_consumed_with_unknown_ticket_state_pauses_for_reconciliation(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_status_event(
                "approval_consumed",
                event_id="evt_approval",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="other-fp",
    )

    assert projection.state == "pause_for_reconciliation"
    assert projection.reason == "ticket_state_mismatch"


def test_ticket_written_without_terminal_status_appends_outcome(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )
    _append_ok(
        store,
        _event_with_bound_fingerprints(
            valid_status_event(
                "approval_consumed",
                event_id="evt_approval",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
    )
    _append_ok(
        store,
        valid_status_event(
            "ticket_written",
            event_id="evt_written",
            thread_id="thread-1",
            mutation_id="mut_recover",
            post_write_fingerprint="post-fp",
        ),
    )

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="post-fp",
    )

    assert projection.state == "append_missing_terminal_status"
    assert [event["status"] for event in projection.events_to_append] == ["applied"]
    assert validate_pending_summary_event(projection.events_to_append[0]).ok


def test_status_recorded_without_summary_appends_recovery_summary_receipt(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    for event in (
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
        _event_with_bound_fingerprints(
            valid_status_event(
                "approval_consumed",
                event_id="evt_approval",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
        valid_status_event(
            "ticket_written",
            event_id="evt_written",
            thread_id="thread-1",
            mutation_id="mut_recover",
            post_write_fingerprint="post-fp",
        ),
        valid_status_event(
            "applied",
            event_id="evt_applied",
            thread_id="thread-1",
            mutation_id="mut_recover",
        ),
    ):
        _append_ok(store, event)

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="post-fp",
    )

    assert projection.state == "summary_ready"
    assert [event["event_type"] for event in projection.events_to_append] == ["summary_receipt"]
    assert projection.events_to_append[0]["mutation_id"] == "mut_recover"
    assert validate_pending_summary_event(projection.events_to_append[0]).ok


def test_summary_recorded_does_not_retry_mutation(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    for event in (
        _event_with_bound_fingerprints(
            valid_attempt_event(
                event_id="evt_attempt",
                thread_id="thread-1",
                mutation_id="mut_recover",
            )
        ),
        valid_status_event(
            "applied",
            event_id="evt_applied",
            thread_id="thread-1",
            mutation_id="mut_recover",
        ),
        valid_attempt_event(
            event_id="evt_summary",
            event_type="summary_receipt",
            status="summarized",
            action="summarize",
            ticket_id=None,
            thread_id="thread-1",
            mutation_id="mut_recover",
            details={},
        ),
    ):
        _append_ok(store, event)

    projection = project_mutation_recovery(
        store=store,
        thread_id="thread-1",
        mutation_id="mut_recover",
        current_ticket_fingerprint="post-fp",
    )

    assert projection.state == "healthy"
    assert projection.events_to_append == ()


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
