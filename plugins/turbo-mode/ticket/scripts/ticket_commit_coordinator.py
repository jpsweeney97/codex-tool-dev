"""Ticket-only commit disposition coordinator."""

from __future__ import annotations

import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from scripts.ticket_parse import parse_ticket
from scripts.ticket_turn_batch import PendingSummaryStore

CommitDisposition = Literal[
    "commit_recorded",
    "commit_bundled_with_work",
    "commit_deferred",
]
TicketChangeScope = Literal["current_branch", "unrelated_backlog"]


@dataclass(frozen=True, slots=True)
class CommitDispositionRecord:
    """Result of ticket commit disposition handling."""

    disposition: CommitDisposition
    commit_hash: str | None = None
    reason: str | None = None


def _deferred(reason: str) -> CommitDispositionRecord:
    clean = reason.strip().replace("\n", " ")
    if not clean.endswith("."):
        clean = f"{clean}."
    return CommitDispositionRecord("commit_deferred", reason=clean)


def _git(
    project_root: Path,
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=check,
    )


def _git_lines(project_root: Path, *args: str) -> list[str] | None:
    result = _git(project_root, *args)
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line]


def _relative_ticket_path(project_root: Path, path: Path) -> str | None:
    root = project_root.resolve(strict=False)
    resolved = path.resolve(strict=False)
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return None
    if rel.parts[:2] != ("docs", "tickets"):
        return None
    if rel.suffix != ".md":
        return None
    return rel.as_posix()


def _branch(project_root: Path) -> str | None:
    result = _git(project_root, "symbolic-ref", "--short", "-q", "HEAD")
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def _staged_paths(project_root: Path) -> list[str] | None:
    return _git_lines(project_root, "diff", "--cached", "--name-only")


def _status_paths(project_root: Path) -> list[str] | None:
    result = _git(project_root, "status", "--porcelain=v1", "--untracked-files=all")
    if result.returncode != 0:
        return None
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        paths.append(line[3:])
    return paths


def _validate_ticket_paths(paths: tuple[Path, ...]) -> str | None:
    for path in paths:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = parse_ticket(path)
        if parsed is None:
            return f"Ticket parse validation failed for {path.name}"
    return None


def _pending_summary_is_healthy(project_root: Path) -> bool:
    store = PendingSummaryStore(project_root)
    return store._read_events_or_none() is not None


def _diff_check(project_root: Path, *args: str) -> bool:
    result = _git(project_root, "diff", "--check", *args)
    return result.returncode == 0


def _unstage(project_root: Path, rel_paths: tuple[str, ...]) -> None:
    if rel_paths:
        _git(project_root, "restore", "--staged", "--", *rel_paths)


def _commit_message(scope: TicketChangeScope) -> str:
    if scope == "unrelated_backlog":
        return "tickets: capture follow-up work"
    return "tickets: update project state"


def record_ticket_commit_disposition(
    *,
    project_root: Path,
    touched_ticket_paths: tuple[Path, ...],
    ticket_change_scope: TicketChangeScope,
    create_ticket_only_commit: bool,
    related_commit: str | None = None,
) -> CommitDispositionRecord:
    """Record or create the commit disposition for autonomous ticket writes.

    Args:
        project_root: Git worktree root.
        touched_ticket_paths: Ticket files written by automation.
        ticket_change_scope: Whether the ticket write belongs to this branch.
        create_ticket_only_commit: Whether to create a standalone ticket commit.
        related_commit: Existing containing commit identifier, when available.

    Returns:
        Commit disposition record. Unsafe cases return `commit_deferred`.
    """
    project_root = project_root.resolve(strict=False)
    if not create_ticket_only_commit:
        if related_commit:
            return CommitDispositionRecord("commit_bundled_with_work", commit_hash=related_commit)
        return _deferred("Containing work commit was not supplied")

    rel_paths: list[str] = []
    for path in touched_ticket_paths:
        rel = _relative_ticket_path(project_root, path)
        if rel is None:
            return _deferred("Only docs/tickets markdown files may be committed")
        rel_paths.append(rel)
    if not rel_paths:
        return _deferred("No ticket paths were supplied")
    rel_tuple = tuple(dict.fromkeys(rel_paths))
    path_tuple = tuple(project_root / rel for rel in rel_tuple)

    staged_before = _staged_paths(project_root)
    if staged_before is None:
        return _deferred("Git index inspection failed")
    if staged_before:
        return _deferred("Git index already contains staged changes")

    branch = _branch(project_root)
    if branch is None:
        return _deferred("Git branch is detached or unknown")
    if ticket_change_scope == "unrelated_backlog" and branch != "main":
        return _deferred("Unrelated backlog ticket commits require main")

    status_before = _status_paths(project_root)
    if status_before is None:
        return _deferred("Git worktree inspection failed")
    if ticket_change_scope == "unrelated_backlog":
        unrelated_dirty = sorted(path for path in status_before if path not in rel_tuple)
        if unrelated_dirty:
            return _deferred("Unrelated dirty worktree blocks backlog ticket commit")

    validation_error = _validate_ticket_paths(path_tuple)
    if validation_error is not None:
        return _deferred(validation_error)
    if not _pending_summary_is_healthy(project_root):
        return _deferred("Pending-summary log validation failed")
    if not _diff_check(project_root, "--", *rel_tuple):
        return _deferred("Ticket diff whitespace validation failed")

    add = _git(project_root, "add", "--", *rel_tuple)
    if add.returncode != 0:
        return _deferred("Git staging failed")

    staged_after = _staged_paths(project_root)
    if staged_after is None:
        _unstage(project_root, rel_tuple)
        return _deferred("Git index inspection failed")
    if not staged_after:
        return _deferred("No ticket changes were available to commit")
    if any(path not in rel_tuple for path in staged_after):
        _unstage(project_root, rel_tuple)
        return _deferred("Git staging included paths outside the ticket-owned set")
    if not _diff_check(project_root, "--cached", "--", *rel_tuple):
        _unstage(project_root, rel_tuple)
        return _deferred("Staged ticket diff whitespace validation failed")

    commit = _git(
        project_root,
        "-c",
        "user.name=Ticket Automation",
        "-c",
        "user.email=ticket-automation@example.invalid",
        "commit",
        "-m",
        _commit_message(ticket_change_scope),
    )
    if commit.returncode != 0:
        _unstage(project_root, rel_tuple)
        return _deferred("Ticket-only commit failed")

    head = _git(project_root, "rev-parse", "HEAD")
    if head.returncode != 0:
        return _deferred("Recorded commit hash could not be read")
    return CommitDispositionRecord("commit_recorded", commit_hash=head.stdout.strip())
