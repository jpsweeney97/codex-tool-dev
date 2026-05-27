"""Tests for pending-summary turn batch validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.ticket_autonomy_ids import sha256_fingerprint
from scripts.ticket_turn_batch import (
    PENDING_SUMMARY_SCHEMA,
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
        "approval": {"approval_id": "appr_123", "decision": "apply_autonomously"},
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
        "reason": "Apply approved ticket update",
        "details": details,
    }
    data.update(overrides)
    return data


def valid_status_event(status: str, **detail_overrides: object) -> dict[str, object]:
    details_by_status: dict[str, dict[str, object]] = {
        "approval_consumed": {"approval_id": "appr_123"},
        "ticket_written": {"post_write_fingerprint": "post-fp"},
        "applied": {"commit_disposition": "commit_deferred"},
        "discussion_required": {"question": "Which ticket should be updated?"},
        "deferred": {"retry_condition": "branch is clean"},
        "failed": {"error_code": "policy_blocked"},
    }
    details = details_by_status.get(status, {}).copy()
    details.update(detail_overrides)
    return valid_attempt_event(
        event_type="mutation_status",
        status=status,
        details=details,
    )


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
        ("mutation_status", "approval_consumed"),
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
        ("details", {"commit_disposition": "unknown"}, "commit_disposition"),
    ],
)
def test_finite_values(field: str, value: object, expected: str) -> None:
    assert_invalid(valid_attempt_event(**{field: value}), expected)


def test_preview_records_use_skipped_status_with_preview_only_decision() -> None:
    preview = valid_attempt_event(
        status="skipped",
        details={"decision": "preview_only", "current_mode": "preview"},
    )
    invalid_status = valid_attempt_event(status="preview_only")

    assert validate_pending_summary_event(preview).ok is True
    assert_invalid(invalid_status, "status")


def test_reason_is_one_short_line() -> None:
    assert_invalid(valid_attempt_event(reason="line one\nline two"), "reason")
    assert_invalid(valid_attempt_event(reason="x" * 201), "reason")


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (
            without_detail(valid_attempt_event(), "approval"),
            "approval",
        ),
        (valid_status_event("approval_consumed", approval_id=""), "approval_id"),
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
        (valid_status_event("applied", commit_disposition=""), "commit_disposition"),
    ],
)
def test_status_details_requirements(event: dict[str, object], expected: str) -> None:
    assert_invalid(event, expected)


def test_event_payload_fingerprint_excludes_event_id_and_timestamp() -> None:
    event = valid_attempt_event()
    payload = {key: value for key, value in event.items() if key not in {"event_id", "timestamp"}}

    assert event_payload_fingerprint(payload) == sha256_fingerprint(payload)

    with pytest.raises(ValueError, match="event payload fingerprint failed"):
        event_payload_fingerprint(event)
