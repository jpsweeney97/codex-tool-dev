"""Tests for pending-summary turn batch validation."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.ticket_autonomy_ids import sha256_fingerprint
from scripts.ticket_turn_batch import (
    PENDING_SUMMARY_SCHEMA,
    PendingSummaryStore,
    VerifiedRepoContext,
    event_payload_fingerprint,
    validate_pending_summary_event,
    validate_repo_context,
)


def valid_repo_context(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "repo_root": "/repo",
        "worktree_root": "/repo",
        "repo_fingerprint": "repo-fp",
        "branch": "feature/ticket-runtime",
        "head": "abc123",
    }
    data.update(overrides)
    return data


def valid_attempt_event(**overrides: object) -> dict[str, object]:
    details: dict[str, object] = {
        "decision": "apply_autonomously",
        "current_mode": "agent_primary",
        "evidence_kind": "runtime_context",
    }
    details.update(overrides.pop("details", {}))
    data: dict[str, object] = {
        "schema": PENDING_SUMMARY_SCHEMA,
        "event_id": "evt_123",
        "timestamp": "2026-05-27T12:00:00Z",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "event_type": "mutation_attempt",
        "status": "pending",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "mutation_id": "mut_123",
        "repo_context": valid_repo_context(),
        "reason": "Apply autonomous Ticket mutation.",
        "details": details,
    }
    data.update(overrides)
    return data


def valid_status_event(status: str, **detail_overrides: object) -> dict[str, object]:
    details_by_status: dict[str, dict[str, object]] = {
        "ticket_written": {"post_write_fingerprint": "post-fp"},
        "applied": {},
        "discussion_required": {"question": "Which ticket should be updated?"},
        "deferred": {"retry_condition": "branch is clean"},
        "failed": {"error_code": "policy_blocked"},
    }
    event_overrides: dict[str, object] = {}
    for key in (
        "event_id",
        "timestamp",
        "thread_id",
        "turn_id",
        "ticket_id",
        "mutation_id",
        "repo_context",
        "reason",
        "action",
    ):
        if key in detail_overrides:
            event_overrides[key] = detail_overrides.pop(key)
    details = details_by_status.get(status, {}).copy()
    details.update(detail_overrides)
    return valid_attempt_event(
        event_type="mutation_status",
        status=status,
        details=details,
        **event_overrides,
    )


def project_root_with_ignored_workspace(tmp_path: Path) -> Path:
    (tmp_path / ".gitignore").write_text(
        ".codex/ticket-workspace/\n.codex/ticket.local.md\n",
        encoding="utf-8",
    )
    return tmp_path


def assert_invalid(event: dict[str, object], expected: str) -> None:
    result = validate_pending_summary_event(event)
    assert result.ok is False
    assert result.error is not None
    assert expected in result.error


def without_detail(event: dict[str, object], key: str) -> dict[str, object]:
    details = dict(event["details"])
    details.pop(key, None)
    return {**event, "details": details}


def test_pending_summary_envelope_requires_strict_fields() -> None:
    event = valid_attempt_event()
    assert validate_pending_summary_event(event).ok is True

    for key in event:
        invalid = dict(event)
        invalid.pop(key)
        assert_invalid(invalid, key)

    invalid = dict(event)
    invalid["extra"] = True
    assert_invalid(invalid, "unknown")


def test_pending_summary_event_requires_thread_id_from_turn_context() -> None:
    assert_invalid(valid_attempt_event(thread_id=""), "thread_id")
    assert validate_pending_summary_event(valid_attempt_event(thread_id="thread-1")).ok is True


def test_repo_context_requires_exact_normalized_fields() -> None:
    assert validate_repo_context(valid_repo_context()).ok is True
    assert validate_repo_context(valid_repo_context(branch=None, head="abc123")).ok is True
    assert validate_pending_summary_event(
        valid_attempt_event(repo_context=valid_repo_context(branch=None, head="abc123"))
    ).ok is True

    missing = valid_repo_context()
    missing.pop("head")
    assert validate_repo_context(missing).ok is False

    unknown = valid_repo_context(extra=True)
    assert validate_repo_context(unknown).ok is False

    backslash = valid_repo_context(repo_root="C:\\repo")
    assert validate_repo_context(backslash).ok is False

    partial_git = valid_repo_context(branch="main", head=None)
    assert validate_repo_context(partial_git).ok is False

    mismatched_worktree = valid_repo_context(worktree_root="/other")
    assert validate_repo_context(mismatched_worktree).ok is False


def test_verified_repo_context_exports_exact_event_payload() -> None:
    context = VerifiedRepoContext(
        repo_root=Path("/repo"),
        worktree_root=Path("/repo"),
        repo_fingerprint="repo-fp",
        branch="feature/ticket-runtime",
        head="abc123",
    )

    assert context.as_event_payload() == valid_repo_context()
    assert validate_pending_summary_event(
        valid_attempt_event(repo_context=context.as_event_payload())
    ).ok
    assert_invalid(valid_attempt_event(repo_context=None), "repo_context")


@pytest.mark.parametrize(
    ("event_type", "status"),
    [
        ("mutation_attempt", "pending"),
        ("mutation_attempt", "skipped"),
        ("mutation_attempt", "discussion_required"),
        ("mutation_attempt", "deferred"),
        ("mutation_attempt", "failed"),
        ("mutation_status", "ticket_written"),
        ("mutation_status", "applied"),
        ("summary_receipt", "summarized"),
        ("compaction_receipt", "compacted"),
        ("automation_pause", "paused"),
    ],
)
def test_valid_event_status_matrix(event_type: str, status: str) -> None:
    if event_type == "mutation_attempt":
        details: dict[str, object]
        details = {"decision": "skip_due_to_conflict"} if status == "skipped" else {}
        if status == "discussion_required":
            details = {"decision": "require_user_discussion", "question": "Clarify target."}
        if status == "deferred":
            details = {
                "decision": "defer_until_retry_condition",
                "retry_condition": "clean branch",
            }
        if status == "failed":
            details = {"decision": "skip_due_to_conflict", "error_code": "policy_blocked"}
        event = valid_attempt_event(event_type=event_type, status=status, details=details)
    elif event_type == "automation_pause":
        event = valid_attempt_event(
            event_type=event_type,
            status=status,
            action="pause_automation",
            details={"pause_reason": "user_requested"},
        )
    else:
        event = valid_status_event(status)
        event["event_type"] = event_type

    assert validate_pending_summary_event(event).ok is True


@pytest.mark.parametrize(
    ("event_type", "status"),
    [
        ("mutation_attempt", "ticket_written"),
        ("mutation_status", "pending"),
        ("summary_receipt", "applied"),
        ("compaction_receipt", "summarized"),
        ("automation_pause", "failed"),
    ],
)
def test_invalid_event_status_matrix(event_type: str, status: str) -> None:
    assert_invalid(valid_attempt_event(event_type=event_type, status=status), "status")


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("action", "unknown_action", "action"),
        ("details", {"decision": "unknown"}, "decision"),
        ("details", {"current_mode": "unknown"}, "current_mode"),
        ("details", {"evidence_kind": "unknown"}, "evidence_kind"),
        ("details", {"pause_reason": "unknown"}, "pause_reason"),
    ],
)
def test_finite_values(field: str, value: object, expected: str) -> None:
    assert_invalid(valid_attempt_event(**{field: value}), expected)


def test_preview_only_decision_is_not_a_supported_pending_summary_decision() -> None:
    event = valid_attempt_event(
        status="skipped",
        details={"decision": "preview_only", "current_mode": "preview"},
    )

    assert_invalid(event, "decision")


def test_approval_consumed_status_is_not_supported() -> None:
    event = valid_status_event("ticket_written")
    event["status"] = "approval_consumed"
    event["details"] = {"approval_id": "old-approval"}

    assert_invalid(event, "status")


def test_reason_is_one_short_line() -> None:
    assert_invalid(valid_attempt_event(reason="line one\nline two"), "reason")
    assert_invalid(valid_attempt_event(reason="x" * 201), "reason")


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (valid_status_event("ticket_written", post_write_fingerprint=""), "post_write_fingerprint"),
        (
            valid_attempt_event(
                status="discussion_required",
                details={"decision": "require_user_discussion", "question": ""},
            ),
            "question",
        ),
        (
            valid_attempt_event(
                status="deferred",
                details={
                    "decision": "defer_until_retry_condition",
                    "retry_condition": "",
                },
            ),
            "retry_condition",
        ),
        (valid_status_event("failed", error_code=""), "error_code"),
    ],
)
def test_status_details_requirements(event: dict[str, object], expected: str) -> None:
    assert_invalid(event, expected)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("commit_disposition", "commit_deferred"),
        ("commit_hash", "abc123"),
        ("commit_reason", "Containing work commit was not supplied."),
        ("ticket_change_scope", "current_branch"),
    ],
)
def test_git_branch_bookkeeping_details_are_not_supported(
    key: str,
    value: object,
) -> None:
    event = valid_status_event("applied", **{key: value})

    assert_invalid(event, key)


def test_event_payload_fingerprint_excludes_event_id_and_timestamp() -> None:
    event = valid_attempt_event()
    payload = {key: value for key, value in event.items() if key not in {"event_id", "timestamp"}}

    assert event_payload_fingerprint(payload) == sha256_fingerprint(payload)

    with pytest.raises(ValueError, match="event payload fingerprint failed"):
        event_payload_fingerprint(event)


def test_pending_summary_jsonl_receives_one_json_object_per_line(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    first = valid_attempt_event(event_id="evt_1", mutation_id="mut_1")
    second = valid_attempt_event(event_id="evt_2", mutation_id="mut_2")

    first_result = store.append_event(first)
    second_result = store.append_event(second)

    assert first_result.state == "appended"
    assert second_result.state == "appended"
    log_path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [line.startswith('{"') for line in lines] == [True, True]
    assert [event["event_id"] for event in store.read_events()] == ["evt_1", "evt_2"]


def test_append_event_returns_already_recorded_for_same_non_timestamp_content(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    first = valid_attempt_event(event_id="evt_same", timestamp="2026-05-27T12:00:00Z")
    duplicate = valid_attempt_event(event_id="evt_same", timestamp="2026-05-27T12:05:00Z")

    assert store.append_event(first).state == "appended"
    result = store.append_event(duplicate)

    assert result.state == "already_recorded"
    assert len(store.read_events()) == 1


def test_append_event_pauses_for_conflicting_event_id(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    first = valid_attempt_event(event_id="evt_conflict", mutation_id="mut_1")
    conflicting = valid_attempt_event(event_id="evt_conflict", mutation_id="mut_2")

    assert store.append_event(first).state == "appended"
    result = store.append_event(conflicting)

    assert result.state == "paused"
    assert result.pause_reason == "conflicting_event"
    assert len(store.read_events()) == 1


def test_append_event_lock_timeout_pauses_without_writing(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root, lock_timeout_seconds=0)
    lock_path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("held\n", encoding="utf-8")

    result = store.append_event(valid_attempt_event())

    assert result.state == "paused"
    assert result.pause_reason == "lock_timeout"
    assert store.read_events() == ()


def test_append_event_clears_dead_pid_lock_and_writes(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root, lock_timeout_seconds=0)
    lock_path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("999999999\n", encoding="utf-8")

    result = store.append_event(valid_attempt_event())

    assert result.state == "appended"
    assert len(store.read_events()) == 1
    assert not lock_path.exists()


def test_append_event_live_or_malformed_lock_fails_closed(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root, lock_timeout_seconds=0)
    lock_path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.lock"
    lock_path.parent.mkdir(parents=True)

    lock_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    live_result = store.append_event(valid_attempt_event(event_id="evt_live"))
    assert live_result.state == "paused"
    assert live_result.pause_reason == "lock_timeout"
    assert lock_path.exists()

    lock_path.write_text("not-a-pid\n", encoding="utf-8")
    malformed_result = store.append_event(valid_attempt_event(event_id="evt_malformed"))
    assert malformed_result.state == "paused"
    assert malformed_result.pause_reason == "lock_timeout"
    assert lock_path.exists()
    assert store.read_events() == ()


def test_append_event_pauses_when_existing_jsonl_is_unhealthy(tmp_path: Path) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    log_path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("{not json}\n", encoding="utf-8")
    store = PendingSummaryStore(project_root)

    result = store.append_event(valid_attempt_event())

    assert result.state == "paused"
    assert result.pause_reason == "pending_summary_unhealthy"


def _correction_ready_event(index: int, timestamp: str) -> dict[str, object]:
    return valid_status_event(
        "failed",
        event_id=f"evt_correction_{index}",
        timestamp=timestamp,
        thread_id="thread-1",
        mutation_id=f"mut_correction_{index}",
        error_code="policy_blocked",
        correction_ready=True,
        correction_detail=f"full correction detail {index}",
    )


def test_compaction_keeps_recent_correction_detail_under_age_and_count_limits(
    tmp_path: Path,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent_base = now - timedelta(days=1)

    assert store.append_event(_correction_ready_event(0, old_timestamp)).state == "appended"
    for index in range(1, 506):
        timestamp = (recent_base + timedelta(seconds=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert store.append_event(_correction_ready_event(index, timestamp)).state == "appended"

    result = store.compact_correction_ready_events(now=now)

    assert result.state == "appended"
    events = store.read_events()
    detailed = [
        event
        for event in events
        if isinstance(event["details"], dict) and "correction_detail" in event["details"]
    ]
    compacted = [
        event
        for event in events
        if isinstance(event["details"], dict)
        and event["details"].get("correction_detail_compacted") is True
    ]
    old = next(event for event in events if event["event_id"] == "evt_correction_0")
    newest = next(event for event in events if event["event_id"] == "evt_correction_505")

    assert len(detailed) == 500
    assert len(compacted) == 6
    assert "correction_detail" not in old["details"]
    assert newest["details"]["correction_detail"] == "full correction detail 505"


def test_compaction_validates_temp_jsonl_before_replacing_active_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = project_root_with_ignored_workspace(tmp_path)
    store = PendingSummaryStore(project_root)
    now = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert store.append_event(_correction_ready_event(0, old_timestamp)).state == "appended"
    before = store.log_path.read_text(encoding="utf-8")

    monkeypatch.setattr(store, "_validate_compacted_events", lambda _events: False)
    result = store.compact_correction_ready_events(now=now)

    assert result.state == "paused"
    assert result.pause_reason == "invalid_compaction"
    assert store.log_path.read_text(encoding="utf-8") == before
