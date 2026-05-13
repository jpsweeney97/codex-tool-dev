from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from scripts.load_transactions import (
    LoadTransactionError,
    TrackedRuntimeSourceError,
    list_load_recovery_records,
    load_handoff,
)


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)


def _handoff(path: Path, title: str = "Test") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"title: {title}\n"
        "date: 2026-05-13\n"
        'created_at: "2026-05-13T16:00:00Z"\n'
        f"session_id: {title.lower()}-session\n"
        "project: demo\n"
        "type: handoff\n"
        "---\n\n"
        "## Goal\n\n"
        "Load transaction test.\n",
        encoding="utf-8",
    )
    return path


def test_primary_active_load_archives_source_and_writes_primary_state(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_load.md")

    result = load_handoff(tmp_path, project_name="demo", resume_token="token-a")

    archive_path = tmp_path / ".codex" / "handoffs" / "archive" / source.name
    state_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token-a.json"
    assert result.archive_path == archive_path
    assert result.state_path == state_path
    assert not source.exists()
    assert archive_path.read_text(encoding="utf-8").startswith("---\n")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["archive_path"] == str(archive_path)

    transaction = json.loads(Path(result.transaction_path).read_text(encoding="utf-8"))
    assert transaction["status"] == "completed"
    assert transaction["source_path"] == str(source)
    assert transaction["archive_path"] == str(archive_path)
    assert transaction["state_path"] == str(state_path)


def test_explicit_primary_archive_load_writes_state_without_moving_archive(tmp_path: Path) -> None:
    archive = _handoff(
        tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_12-00_archived.md"
    )
    before = archive.read_text(encoding="utf-8")

    result = load_handoff(
        tmp_path,
        project_name="demo",
        explicit_path=archive,
        resume_token="token-b",
    )

    assert result.archive_path == archive
    assert archive.read_text(encoding="utf-8") == before
    state = json.loads(Path(result.state_path).read_text(encoding="utf-8"))
    assert state["archive_path"] == str(archive)


def test_explicit_legacy_archive_load_copies_to_primary_archive_and_reuses_registry(
    tmp_path: Path,
) -> None:
    legacy = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_legacy.md"
    )

    first = load_handoff(tmp_path, project_name="demo", explicit_path=legacy, resume_token="one")
    second = load_handoff(tmp_path, project_name="demo", explicit_path=legacy, resume_token="two")

    assert legacy.exists()
    assert first.archive_path == second.archive_path
    assert first.archive_path == tmp_path / ".codex" / "handoffs" / "archive" / legacy.name
    first_state = json.loads(Path(first.state_path).read_text(encoding="utf-8"))
    second_state = json.loads(Path(second.state_path).read_text(encoding="utf-8"))
    assert first_state["archive_path"] == str(first.archive_path)
    assert second_state["archive_path"] == str(first.archive_path)

    registry_path = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "copied-legacy-archives.json"
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert len(registry["entries"]) == 1
    assert registry["entries"][0]["storage_location"] == "legacy_archive"
    assert registry["entries"][0]["copied_primary_archive_path"] == str(first.archive_path)


def test_explicit_previous_primary_hidden_archive_uses_copy_registry(tmp_path: Path) -> None:
    hidden = _handoff(
        tmp_path / ".codex" / "handoffs" / ".archive" / "2026-05-13_12-00_hidden.md"
    )

    result = load_handoff(
        tmp_path,
        project_name="demo",
        explicit_path=hidden,
        resume_token="hidden",
    )

    assert hidden.exists()
    assert result.archive_path == tmp_path / ".codex" / "handoffs" / "archive" / hidden.name
    registry = json.loads(
        (
            tmp_path
            / ".codex"
            / "handoffs"
            / ".session-state"
            / "copied-legacy-archives.json"
        ).read_text(encoding="utf-8")
    )
    assert registry["entries"][0]["storage_location"] == "previous_primary_hidden_archive"


def test_tracked_primary_active_load_fails_before_mutation(tmp_path: Path) -> None:
    _git_init(tmp_path)
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_tracked.md")
    subprocess.run(["git", "add", str(source.relative_to(tmp_path))], cwd=tmp_path, check=True)
    before = source.read_text(encoding="utf-8")

    with pytest.raises(TrackedRuntimeSourceError):
        load_handoff(tmp_path, project_name="demo", explicit_path=source)

    assert source.exists()
    assert source.read_text(encoding="utf-8") == before
    assert not (tmp_path / ".codex" / "handoffs" / "archive").exists()
    assert not (tmp_path / ".codex" / "handoffs" / ".session-state").exists()


def test_load_lock_blocks_concurrent_attempt_before_mutation(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_locked.md")
    lock = tmp_path / ".codex" / "handoffs" / ".session-state" / "load.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("busy", encoding="utf-8")

    with pytest.raises(LoadTransactionError, match="lock is already held"):
        load_handoff(tmp_path, project_name="demo")

    assert source.exists()
    assert not (tmp_path / ".codex" / "handoffs" / "archive").exists()


def test_read_only_recovery_inventory_reports_pending_transactions(tmp_path: Path) -> None:
    transactions = tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions"
    transactions.mkdir(parents=True)
    pending = transactions / "pending.json"
    completed = transactions / "completed.json"
    pending.write_text('{"transaction_id": "a", "status": "pending"}', encoding="utf-8")
    completed.write_text('{"transaction_id": "b", "status": "completed"}', encoding="utf-8")

    records = list_load_recovery_records(tmp_path)

    assert records == [{"transaction_id": "a", "status": "pending"}]
    assert pending.exists()
    assert completed.exists()
