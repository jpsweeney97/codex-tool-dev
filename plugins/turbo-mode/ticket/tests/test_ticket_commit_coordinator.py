"""Tests for ticket-only commit disposition coordination."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.ticket_commit_coordinator import record_ticket_commit_disposition

from tests.support.builders import make_ticket


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", ".gitignore", "docs/tickets")
    _git(
        repo,
        "-c",
        "user.name=Ticket Test",
        "-c",
        "user.email=ticket-test@example.invalid",
        "commit",
        "-m",
        message,
    )


def _init_ticket_repo(tmp_path: Path, *, branch: str = "feature/work") -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-b", "main")
    (tmp_path / ".gitignore").write_text(
        ".codex/ticket-workspace/\n.codex/ticket.local.md\n",
        encoding="utf-8",
    )
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    _commit(tmp_path, "initial tickets")
    if branch != "main":
        _git(tmp_path, "switch", "-c", branch)
    return tmp_path, ticket


def _staged_paths(repo: Path) -> list[str]:
    output = _git(repo, "diff", "--cached", "--name-only").stdout
    return [line for line in output.splitlines() if line]


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _subject(repo: Path) -> str:
    return _git(repo, "log", "-1", "--pretty=%s").stdout.strip()


def _one_sentence(reason: str | None) -> None:
    assert reason is not None
    assert "\n" not in reason
    assert reason.endswith(".")


def test_current_branch_ticket_only_commit_stages_only_touched_ticket_paths(
    tmp_path: Path,
) -> None:
    repo, ticket = _init_ticket_repo(tmp_path)
    ticket.write_text(
        ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )
    (repo / "notes.txt").write_text("user work\n", encoding="utf-8")
    pending = repo / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    pending.parent.mkdir(parents=True)
    pending.write_text("", encoding="utf-8")

    result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )

    assert result.disposition == "commit_recorded"
    assert result.commit_hash == _head(repo)
    assert _subject(repo) == "tickets: update project state"
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.splitlines() == [
        "docs/tickets/one.md"
    ]
    assert _staged_paths(repo) == []
    assert _git(repo, "status", "--short", "--", "notes.txt").stdout == "?? notes.txt\n"


def test_unrelated_staged_index_defers_and_leaves_index_unchanged(tmp_path: Path) -> None:
    repo, ticket = _init_ticket_repo(tmp_path)
    head_before = _head(repo)
    (repo / "notes.txt").write_text("user work\n", encoding="utf-8")
    _git(repo, "add", "notes.txt")
    ticket.write_text(
        ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )
    staged_before = _staged_paths(repo)

    result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )

    assert result.disposition == "commit_deferred"
    _one_sentence(result.reason)
    assert _head(repo) == head_before
    assert _staged_paths(repo) == staged_before


def test_same_ticket_overlap_defers_without_touching_index_or_worktree(tmp_path: Path) -> None:
    repo, ticket = _init_ticket_repo(tmp_path)
    ticket.write_text(
        ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )
    _git(repo, "add", "docs/tickets/one.md")
    ticket.write_text(ticket.read_text(encoding="utf-8") + "\nUser note.\n", encoding="utf-8")
    staged_before = _staged_paths(repo)
    text_before = ticket.read_text(encoding="utf-8")

    result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )

    assert result.disposition == "commit_deferred"
    _one_sentence(result.reason)
    assert _staged_paths(repo) == staged_before
    assert ticket.read_text(encoding="utf-8") == text_before


def test_unrelated_backlog_commits_only_on_clean_main(tmp_path: Path) -> None:
    repo, ticket = _init_ticket_repo(tmp_path, branch="main")
    ticket.write_text(
        ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )

    result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="unrelated_backlog",
        create_ticket_only_commit=True,
    )

    assert result.disposition == "commit_recorded"
    assert result.commit_hash == _head(repo)
    assert _subject(repo) == "tickets: capture follow-up work"


def test_unrelated_backlog_defers_on_dirty_worktree_or_non_main_branch(tmp_path: Path) -> None:
    dirty_repo, dirty_ticket = _init_ticket_repo(tmp_path / "dirty", branch="main")
    dirty_ticket.write_text(
        dirty_ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )
    (dirty_repo / "notes.txt").write_text("user work\n", encoding="utf-8")

    dirty = record_ticket_commit_disposition(
        project_root=dirty_repo,
        touched_ticket_paths=(dirty_ticket,),
        ticket_change_scope="unrelated_backlog",
        create_ticket_only_commit=True,
    )

    feature_repo, feature_ticket = _init_ticket_repo(tmp_path / "feature")
    feature_ticket.write_text(
        feature_ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )
    feature = record_ticket_commit_disposition(
        project_root=feature_repo,
        touched_ticket_paths=(feature_ticket,),
        ticket_change_scope="unrelated_backlog",
        create_ticket_only_commit=True,
    )

    assert dirty.disposition == "commit_deferred"
    assert feature.disposition == "commit_deferred"
    _one_sentence(dirty.reason)
    _one_sentence(feature.reason)


def test_detached_head_defers_ticket_only_commit(tmp_path: Path) -> None:
    repo, ticket = _init_ticket_repo(tmp_path)
    _git(repo, "checkout", "--detach", "HEAD")
    ticket.write_text(
        ticket.read_text(encoding="utf-8").replace("priority: high", "priority: low"),
        encoding="utf-8",
    )

    result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )

    assert result.disposition == "commit_deferred"
    _one_sentence(result.reason)


def test_bundled_disposition_requires_related_commit_identifier(tmp_path: Path) -> None:
    repo, ticket = _init_ticket_repo(tmp_path)

    bundled = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=False,
        related_commit="abc123",
    )
    missing = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=False,
    )

    assert bundled.disposition == "commit_bundled_with_work"
    assert bundled.commit_hash == "abc123"
    assert missing.disposition == "commit_deferred"
    _one_sentence(missing.reason)


def test_pending_summary_and_invalid_ticket_paths_are_never_staged(tmp_path: Path) -> None:
    repo, ticket = _init_ticket_repo(tmp_path)
    pending = repo / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    pending.parent.mkdir(parents=True)
    pending.write_text("{}\n", encoding="utf-8")
    invalid = repo / "docs" / "tickets" / "invalid.md"
    invalid.write_text("not a ticket\n", encoding="utf-8")

    pending_result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(pending,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )
    invalid_result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(invalid,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )
    valid_result = record_ticket_commit_disposition(
        project_root=repo,
        touched_ticket_paths=(ticket,),
        ticket_change_scope="current_branch",
        create_ticket_only_commit=True,
    )

    assert pending_result.disposition == "commit_deferred"
    assert invalid_result.disposition == "commit_deferred"
    assert valid_result.disposition == "commit_deferred"
    assert _staged_paths(repo) == []
