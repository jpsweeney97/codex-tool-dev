"""Pending-summary turn batch validation."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from scripts.ticket_autonomy_config import ensure_ticket_workspace
from scripts.ticket_autonomy_ids import canonical_json, sha256_fingerprint

PENDING_SUMMARY_SCHEMA = "codex.ticket.pending_summary.v1"

_REPO_CONTEXT_KEYS = frozenset(
    {
        "repo_root",
        "worktree_root",
        "repo_fingerprint",
        "branch",
        "head",
    }
)
_EVENT_KEYS = frozenset(
    {
        "schema",
        "event_id",
        "timestamp",
        "thread_id",
        "turn_id",
        "event_type",
        "status",
        "action",
        "ticket_id",
        "mutation_id",
        "repo_context",
        "reason",
        "details",
    }
)
_EVENT_STATUSES = {
    "mutation_attempt": {
        "pending",
        "skipped",
        "discussion_required",
        "deferred",
        "failed",
    },
    "mutation_status": {
        "approval_consumed",
        "ticket_written",
        "applied",
        "failed",
        "corrected",
        "inactive",
    },
    "summary_receipt": {"summarized", "failed"},
    "compaction_receipt": {"compacted", "failed"},
    "automation_pause": {"paused"},
}
_ACTIONS = frozenset(
    {
        "create",
        "update",
        "reprioritize",
        "blocker_edit",
        "stale_cleanup",
        "refine",
        "done",
        "wontfix",
        "reopen",
        "archive",
        "delete",
        "history_repair",
        "correction",
        "summarize",
        "compact",
        "pause_automation",
    }
)
_DECISIONS = frozenset(
    {
        "apply_autonomously",
        "require_user_discussion",
        "skip_due_to_conflict",
        "defer_until_retry_condition",
        "preview_only",
    }
)
_MODES = frozenset({"discussion_only", "preview", "agent_primary"})
_EVIDENCE_KINDS = frozenset(
    {
        "runtime_context",
        "code_inspection",
        "test_output",
        "user_request",
        "none",
    }
)
_PAUSE_REASONS = frozenset(
    {
        "user_requested",
        "pending_summary_unhealthy",
        "setup_required",
        "lock_timeout",
        "conflicting_event",
        "repair",
    }
)
_COMMIT_DISPOSITIONS = frozenset(
    {
        "commit_recorded",
        "commit_bundled_with_work",
        "commit_deferred",
    }
)


@dataclass(frozen=True, slots=True)
class VerifiedRepoContext:
    """Already-verified live repository context for event payloads."""

    repo_root: Path
    worktree_root: Path
    repo_fingerprint: str
    branch: str | None
    head: str | None

    def as_event_payload(self) -> Mapping[str, object]:
        """Return the exact pending-summary repo_context payload."""
        return {
            "repo_root": _path_text(self.repo_root),
            "worktree_root": _path_text(self.worktree_root),
            "repo_fingerprint": self.repo_fingerprint,
            "branch": self.branch,
            "head": self.head,
        }


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validation result for pending-summary shapes."""

    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AppendResult:
    """Result from append-only pending-summary bookkeeping."""

    state: Literal["appended", "already_recorded", "paused"]
    event_id: str
    pause_reason: str | None = None


def _path_text(path: Path) -> str:
    return str(path).replace("\\", "/")


def _ok() -> ValidationResult:
    return ValidationResult(True)


def _invalid(error: str) -> ValidationResult:
    return ValidationResult(False, error)


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _exact_keys(value: Mapping[str, object], expected: frozenset[str]) -> ValidationResult:
    actual = set(value)
    missing = sorted(expected - actual)
    if missing:
        return _invalid(f"missing required field: {missing[0]}")
    unknown = sorted(actual - expected)
    if unknown:
        return _invalid(f"unknown field: {unknown[0]}")
    return _ok()


def validate_repo_context(repo_context: Mapping[str, object]) -> ValidationResult:
    """Validate pending-summary repository context shape.

    Args:
        repo_context: Candidate `repo_context` event payload.

    Returns:
        Validation result. This proves shape only, not live repo identity.
    """
    if not isinstance(repo_context, Mapping):
        return _invalid("repo_context must be an object")
    key_result = _exact_keys(repo_context, _REPO_CONTEXT_KEYS)
    if not key_result.ok:
        return key_result

    repo_root = repo_context["repo_root"]
    worktree_root = repo_context["worktree_root"]
    for key, value in (("repo_root", repo_root), ("worktree_root", worktree_root)):
        if not _nonempty_string(value):
            return _invalid(f"{key} must be a non-empty string")
        if "\\" in value:
            return _invalid(f"{key} must use / path separators")
    if repo_root != worktree_root:
        return _invalid("worktree_root must match repo_root for this verified context")
    if not _nonempty_string(repo_context["repo_fingerprint"]):
        return _invalid("repo_fingerprint must be a non-empty string")

    branch = repo_context["branch"]
    head = repo_context["head"]
    if branch is None and head is None:
        return _ok()
    if not _nonempty_string(branch):
        return _invalid("branch must be present when git metadata is available")
    if not _nonempty_string(head):
        return _invalid("head must be present when git metadata is available")
    return _ok()


def _validate_optional_string(event: Mapping[str, object], key: str) -> ValidationResult:
    value = event[key]
    if value is not None and not _nonempty_string(value):
        return _invalid(f"{key} must be a non-empty string or null")
    return _ok()


def _validate_finite_details(details: Mapping[str, object]) -> ValidationResult:
    finite_checks = (
        ("decision", _DECISIONS),
        ("current_mode", _MODES),
        ("evidence_kind", _EVIDENCE_KINDS),
        ("pause_reason", _PAUSE_REASONS),
        ("commit_disposition", _COMMIT_DISPOSITIONS),
    )
    for key, allowed in finite_checks:
        if key in details and details[key] not in allowed:
            return _invalid(f"{key} is not supported")
    return _ok()


def _require_detail(details: Mapping[str, object], key: str) -> ValidationResult:
    if not _nonempty_string(details.get(key)):
        return _invalid(f"details.{key} is required")
    return _ok()


def _validate_details(
    *,
    event_type: str,
    status: str,
    action: str,
    details: Mapping[str, object],
) -> ValidationResult:
    finite = _validate_finite_details(details)
    if not finite.ok:
        return finite

    decision = details.get("decision")
    if event_type == "mutation_attempt":
        if decision not in _DECISIONS:
            return _invalid("details.decision is required")
        if decision == "apply_autonomously" and not isinstance(details.get("approval"), Mapping):
            return _invalid("details.approval is required")
        if decision == "preview_only" and status != "skipped":
            return _invalid("preview_only decisions must use skipped status")

    required_by_status = {
        "approval_consumed": "approval_id",
        "ticket_written": "post_write_fingerprint",
        "discussion_required": "question",
        "deferred": "retry_condition",
        "failed": "error_code",
        "paused": "pause_reason",
    }
    required = required_by_status.get(status)
    if required is not None:
        result = _require_detail(details, required)
        if not result.ok:
            return result

    if status == "applied" and action in _ACTIONS:
        result = _require_detail(details, "commit_disposition")
        if not result.ok:
            return result
        if details["commit_disposition"] not in _COMMIT_DISPOSITIONS:
            return _invalid("commit_disposition is not supported")

    return _ok()


def validate_pending_summary_event(event: Mapping[str, object]) -> ValidationResult:
    """Validate one pending-summary event.

    Args:
        event: Candidate pending-summary event.

    Returns:
        Validation result. This proves deterministic shape and finite values.
    """
    if not isinstance(event, Mapping):
        return _invalid("event must be an object")
    key_result = _exact_keys(event, _EVENT_KEYS)
    if not key_result.ok:
        return key_result

    if event["schema"] != PENDING_SUMMARY_SCHEMA:
        return _invalid("schema is unsupported")
    for key in ("event_id", "timestamp", "thread_id", "turn_id"):
        if not _nonempty_string(event[key]):
            return _invalid(f"{key} must be a non-empty string")

    event_type = event["event_type"]
    if event_type not in _EVENT_STATUSES:
        return _invalid("event_type is not supported")
    status = event["status"]
    if not isinstance(status, str) or status not in _EVENT_STATUSES[event_type]:
        return _invalid("status is not supported for event_type")

    action = event["action"]
    if action not in _ACTIONS:
        return _invalid("action is not supported")

    for key in ("ticket_id", "mutation_id"):
        optional = _validate_optional_string(event, key)
        if not optional.ok:
            return optional

    repo_context = event["repo_context"]
    if not isinstance(repo_context, Mapping):
        return _invalid("repo_context must be an object")
    repo_result = validate_repo_context(repo_context)
    if not repo_result.ok:
        return repo_result

    reason = event["reason"]
    if not _nonempty_string(reason) or "\n" in reason or "\r" in reason or len(reason) > 200:
        return _invalid("reason must be one short line")

    details = event["details"]
    if not isinstance(details, Mapping):
        return _invalid("details must be an object")

    return _validate_details(
        event_type=event_type,
        status=status,
        action=action,
        details=details,
    )


def event_payload_fingerprint(
    event_without_event_id_and_timestamp: Mapping[str, object],
) -> str:
    """Fingerprint an event payload before `event_id` and `timestamp` are added.

    Args:
        event_without_event_id_and_timestamp: Event payload without ID/timestamp.

    Returns:
        Canonical SHA-256 fingerprint.

    Raises:
        ValueError: If ID or timestamp fields are already present.
    """
    forbidden = {"event_id", "timestamp"} & set(event_without_event_id_and_timestamp)
    if forbidden:
        field = sorted(forbidden)[0]
        raise ValueError(
            "event payload fingerprint failed: event_id and timestamp must be absent. "
            f"Got: {field!r:.100}"
        )
    return sha256_fingerprint(event_without_event_id_and_timestamp)


def _event_id(event: Mapping[str, object]) -> str:
    value = event.get("event_id")
    return value if isinstance(value, str) else ""


def _event_signature(event: Mapping[str, object]) -> str:
    comparable = {key: value for key, value in event.items() if key != "timestamp"}
    return canonical_json(comparable)


class PendingSummaryStore:
    """Append-only local pending-summary event store."""

    def __init__(self, project_root: Path, *, lock_timeout_seconds: float = 2.0) -> None:
        """Create a project-local pending-summary store.

        Args:
            project_root: Project root that owns `.codex/ticket-workspace/`.
            lock_timeout_seconds: Maximum time to wait for the append lock.
        """
        self.project_root = project_root
        self.lock_timeout_seconds = lock_timeout_seconds
        self.workspace = project_root / ".codex" / "ticket-workspace"
        self.log_path = self.workspace / "ticket.pending-summary.jsonl"
        self.lock_path = self.workspace / "ticket.pending-summary.lock"

    def append_event(self, event: Mapping[str, object]) -> AppendResult:
        """Append one valid event, preserving idempotency by `event_id`.

        Args:
            event: Pending-summary event to append.

        Returns:
            Append result. Expected bookkeeping failures return `paused`.
        """
        event_id = _event_id(event)
        validation = validate_pending_summary_event(event)
        if not validation.ok:
            return AppendResult("paused", event_id, "invalid_event")

        ensure_ticket_workspace(self.project_root)
        if not self._acquire_lock():
            return AppendResult("paused", event_id, "lock_timeout")

        try:
            existing = self._read_events_or_none()
            if existing is None:
                return AppendResult("paused", event_id, "pending_summary_unhealthy")

            new_signature = _event_signature(event)
            for existing_event in existing:
                if existing_event.get("event_id") != event_id:
                    continue
                if _event_signature(existing_event) == new_signature:
                    return AppendResult("already_recorded", event_id)
                return AppendResult("paused", event_id, "conflicting_event")

            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(canonical_json(dict(event)) + "\n")
            return AppendResult("appended", event_id)
        finally:
            self._release_lock()

    def read_events(self) -> tuple[dict[str, object], ...]:
        """Read valid pending-summary events from the local JSONL log."""
        events = self._read_events_or_none()
        return events if events is not None else ()

    def derive_mutation_state(self, *, thread_id: str, mutation_id: str) -> str:
        """Derive recovery state from recorded events only.

        Args:
            thread_id: Thread that scopes the mutation.
            mutation_id: Mutation ID to inspect.

        Returns:
            Display-ready recovery state.
        """
        rank = {
            "no_attempt": 0,
            "attempt_recorded": 1,
            "approval_consumed": 2,
            "ticket_written": 3,
            "status_recorded": 4,
            "summary_recorded": 5,
        }
        state = "no_attempt"
        for event in self.read_events():
            if event.get("thread_id") != thread_id or event.get("mutation_id") != mutation_id:
                continue
            event_type = event.get("event_type")
            status = event.get("status")
            candidate = None
            if event_type == "mutation_attempt":
                candidate = "attempt_recorded"
            elif status == "approval_consumed":
                candidate = "approval_consumed"
            elif status == "ticket_written":
                candidate = "ticket_written"
            elif status in {"applied", "failed", "corrected", "inactive"}:
                candidate = "status_recorded"
            elif event_type == "summary_receipt" and status == "summarized":
                candidate = "summary_recorded"
            if candidate is not None and rank[candidate] > rank[state]:
                state = candidate
        return state

    def _acquire_lock(self) -> bool:
        deadline = time.monotonic() + max(self.lock_timeout_seconds, 0.0)
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                try:
                    os.write(fd, f"{os.getpid()}\n".encode())
                finally:
                    os.close(fd)
                return True
            except FileExistsError:
                if self.lock_timeout_seconds <= 0 or time.monotonic() >= deadline:
                    return False
                time.sleep(min(0.05, max(deadline - time.monotonic(), 0.0)))

    def _release_lock(self) -> None:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass

    def _read_events_or_none(self) -> tuple[dict[str, object], ...] | None:
        if not self.log_path.is_file():
            return ()
        events: list[dict[str, object]] = []
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for line in lines:
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed, dict):
                return None
            if not validate_pending_summary_event(parsed).ok:
                return None
            events.append(parsed)
        return tuple(events)
