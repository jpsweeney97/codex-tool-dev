from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import scripts.load_transactions as load_transactions
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_legacy_active_opt_in(project_root: Path, source: Path) -> Path:
    rel_path = source.relative_to(project_root).as_posix()
    manifest = (
        project_root
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-05-13-handoff-storage-legacy-active-opt-ins.md"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "| project_relative_path | raw_byte_sha256 | source_root | storage_location | "
        "reviewer | reason |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| `{rel_path}` | `{_sha256(source)}` | `project_root` | "
        "`legacy_active` | `test-reviewer` | reviewed runtime migration input |\n",
        encoding="utf-8",
    )
    return manifest


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


def test_load_retry_recovers_primary_archive_after_state_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _handoff(
        tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_12-00_archived.md"
    )
    before = archive.read_text(encoding="utf-8")
    state_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-retry.json"
    original_write_resume_state = load_transactions.write_resume_state

    def fail_write_resume_state(*args: object, **kwargs: object) -> Path:
        raise RuntimeError("state write failed")

    monkeypatch.setattr(load_transactions, "write_resume_state", fail_write_resume_state)
    with pytest.raises(RuntimeError, match="state write failed"):
        load_transactions.load_handoff(
            tmp_path,
            project_name="demo",
            explicit_path=archive,
            resume_token="retry",
        )

    assert archive.read_text(encoding="utf-8") == before
    assert not state_path.exists()

    monkeypatch.setattr(load_transactions, "write_resume_state", original_write_resume_state)

    result = load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert result.source_path == archive
    assert result.archive_path == archive
    assert result.state_path == state_path
    assert json.loads(state_path.read_text(encoding="utf-8"))["archive_path"] == str(archive)
    assert list_load_recovery_records(tmp_path) == []


def test_explicit_legacy_archive_load_copies_to_primary_archive_and_reuses_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_legacy.md"
    )
    copy_destinations: list[Path] = []

    def copy_spy(source: Path, destination: Path) -> Path:
        copy_destinations.append(destination)
        return load_transactions.shutil.copyfile(source, destination)

    monkeypatch.setattr(load_transactions.shutil, "copy2", copy_spy)

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
    assert len(copy_destinations) == 1
    assert copy_destinations[0].parent == first.archive_path.parent
    assert copy_destinations[0] != first.archive_path
    assert not copy_destinations[0].exists()


def test_legacy_archive_state_write_failure_does_not_record_copied_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_legacy.md"
    )
    archive = tmp_path / ".codex" / "handoffs" / "archive" / legacy.name

    def fail_write_resume_state(*args: object, **kwargs: object) -> Path:
        raise RuntimeError("state write failed")

    monkeypatch.setattr(load_transactions, "write_resume_state", fail_write_resume_state)

    with pytest.raises(RuntimeError, match="state write failed"):
        load_transactions.load_handoff(
            tmp_path,
            project_name="demo",
            explicit_path=legacy,
            resume_token="retry",
        )

    assert archive.exists()
    assert not (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "copied-legacy-archives.json"
    ).exists()


def test_load_retry_recovers_legacy_archive_after_copied_registry_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_legacy.md"
    )
    legacy_hash = _sha256(legacy)
    archive = tmp_path / ".codex" / "handoffs" / "archive" / legacy.name
    state_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-retry.json"
    original_record = load_transactions._record_copied_legacy_archive

    def fail_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("copied registry failed")

    monkeypatch.setattr(load_transactions, "_record_copied_legacy_archive", fail_record)
    with pytest.raises(RuntimeError, match="copied registry failed"):
        load_transactions.load_handoff(
            tmp_path,
            project_name="demo",
            explicit_path=legacy,
            resume_token="retry",
        )

    assert legacy.exists()
    assert archive.exists()
    assert state_path.exists()
    assert not (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "copied-legacy-archives.json"
    ).exists()

    monkeypatch.setattr(load_transactions, "_record_copied_legacy_archive", original_record)

    result = load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert result.source_path == legacy
    assert result.archive_path == archive
    assert result.state_path == state_path
    registry = json.loads(
        (
            tmp_path
            / ".codex"
            / "handoffs"
            / ".session-state"
            / "copied-legacy-archives.json"
        ).read_text(encoding="utf-8")
    )
    assert len(registry["entries"]) == 1
    assert registry["entries"][0]["project_relative_source_path"] == legacy.relative_to(
        tmp_path
    ).as_posix()
    assert registry["entries"][0]["source_content_sha256"] == legacy_hash
    assert registry["entries"][0]["copied_primary_archive_path"] == str(archive)
    assert list_load_recovery_records(tmp_path) == []


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


def test_legacy_active_load_copies_to_primary_archive_writes_state_and_consumes_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-00_legacy.md")
    legacy_hash = _sha256(legacy)
    _write_legacy_active_opt_in(tmp_path, legacy)
    copy_destinations: list[Path] = []

    def copy_spy(source: Path, destination: Path) -> Path:
        copy_destinations.append(destination)
        return load_transactions.shutil.copyfile(source, destination)

    monkeypatch.setattr(load_transactions.shutil, "copy2", copy_spy)

    result = load_handoff(tmp_path, project_name="demo", resume_token="legacy")

    archive_path = tmp_path / ".codex" / "handoffs" / "archive" / legacy.name
    assert legacy.exists()
    assert result.source_path == legacy
    assert result.archive_path == archive_path
    assert archive_path.read_bytes() == legacy.read_bytes()
    state = json.loads(Path(result.state_path).read_text(encoding="utf-8"))
    assert state["archive_path"] == str(archive_path)

    registry = json.loads(
        (
            tmp_path
            / ".codex"
            / "handoffs"
            / ".session-state"
            / "consumed-legacy-active.json"
        ).read_text(encoding="utf-8")
    )
    assert len(registry["entries"]) == 1
    entry = registry["entries"][0]
    assert entry["source_root"] == "project_root"
    assert entry["project_relative_source_path"] == legacy.relative_to(tmp_path).as_posix()
    assert entry["storage_location"] == "legacy_active"
    assert entry["source_content_sha256"] == legacy_hash
    assert entry["copied_primary_archive_path"] == str(archive_path)
    assert entry["operation"] == "legacy-load"
    assert len(copy_destinations) == 1
    assert copy_destinations[0].parent == archive_path.parent
    assert copy_destinations[0] != archive_path
    assert not copy_destinations[0].exists()

    with pytest.raises(LoadTransactionError, match="no active handoff candidates"):
        load_handoff(tmp_path, project_name="demo", resume_token="legacy-again")


def test_explicit_consumed_legacy_active_load_reuses_primary_archive(
    tmp_path: Path,
) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-00_legacy.md")
    _write_legacy_active_opt_in(tmp_path, legacy)

    first = load_handoff(tmp_path, project_name="demo", resume_token="one")
    second = load_handoff(
        tmp_path,
        project_name="demo",
        explicit_path=legacy,
        resume_token="two",
    )

    assert second.archive_path == first.archive_path
    second_state = json.loads(Path(second.state_path).read_text(encoding="utf-8"))
    assert second_state["archive_path"] == str(first.archive_path)
    archives = sorted((tmp_path / ".codex" / "handoffs" / "archive").glob("*.md"))
    assert archives == [first.archive_path]

    registry = json.loads(
        (
            tmp_path
            / ".codex"
            / "handoffs"
            / ".session-state"
            / "consumed-legacy-active.json"
        ).read_text(encoding="utf-8")
    )
    assert len(registry["entries"]) == 1


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
    lock = tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "load.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("busy", encoding="utf-8")

    with pytest.raises(LoadTransactionError, match="lock is already held"):
        load_handoff(tmp_path, project_name="demo")

    assert source.exists()
    assert not (tmp_path / ".codex" / "handoffs" / "archive").exists()


def test_load_lock_metadata_exists_during_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_locked.md")
    observed: dict[str, Any] = {}

    def inspect_lock(
        project_root: Path,
        *,
        candidate: object,
        project_name: str | None,
        resume_token: str | None,
        transaction_id: str,
    ) -> load_transactions.LoadResult:
        lock = (
            tmp_path
            / ".codex"
            / "handoffs"
            / ".session-state"
            / "locks"
            / "load.lock"
        )
        observed["lock_exists"] = lock.exists()
        observed["metadata"] = json.loads(lock.read_text(encoding="utf-8"))
        raise RuntimeError("stop after lock inspection")

    monkeypatch.setattr(load_transactions, "_load_handoff_locked", inspect_lock)

    with pytest.raises(RuntimeError, match="stop after lock inspection"):
        load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="lock")

    assert observed["lock_exists"] is True
    assert observed["metadata"]["project"] == "demo"
    assert observed["metadata"]["operation"] == "load"
    assert observed["metadata"]["transaction_id"]
    assert observed["metadata"]["transaction_id"] == observed["metadata"]["lock_id"]
    assert observed["metadata"]["pid"] > 0
    assert observed["metadata"]["hostname"]
    assert observed["metadata"]["created_at"]
    assert observed["metadata"]["timeout_seconds"] == 1800
    assert not (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "load.lock"
    ).exists()


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


def test_read_only_recovery_inventory_reports_archive_after_state_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_pending.md")
    archive = tmp_path / ".codex" / "handoffs" / "archive" / source.name

    def fail_write_resume_state(*args: object, **kwargs: object) -> Path:
        raise RuntimeError("state write failed")

    monkeypatch.setattr(load_transactions, "write_resume_state", fail_write_resume_state)

    with pytest.raises(RuntimeError, match="state write failed"):
        load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="token")

    assert not source.exists()
    assert archive.exists()
    records = list_load_recovery_records(tmp_path)
    assert len(records) == 1
    assert records[0]["status"] == "pending"
    assert records[0]["source_path"] == str(source)
    assert records[0]["archive_path"] == str(archive)
    assert records[0]["state_path"] == str(
        tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token.json"
    )
    assert not Path(str(records[0]["state_path"])).exists()


def test_load_retry_recovers_primary_active_after_state_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_recover.md")
    archive = tmp_path / ".codex" / "handoffs" / "archive" / source.name
    original_write_resume_state = load_transactions.write_resume_state

    def fail_write_resume_state(*args: object, **kwargs: object) -> Path:
        raise RuntimeError("state write failed")

    monkeypatch.setattr(load_transactions, "write_resume_state", fail_write_resume_state)
    with pytest.raises(RuntimeError, match="state write failed"):
        load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="retry")

    monkeypatch.setattr(load_transactions, "write_resume_state", original_write_resume_state)

    result = load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert result.source_path == source
    assert result.archive_path == archive
    assert result.state_path == (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-retry.json"
    )
    assert result.state_path.exists()
    recovered_state = json.loads(result.state_path.read_text(encoding="utf-8"))
    assert recovered_state["archive_path"] == str(archive)

    transaction = json.loads(Path(result.transaction_path).read_text(encoding="utf-8"))
    assert transaction["status"] == "completed"
    assert list_load_recovery_records(tmp_path) == []


def test_load_retry_recovers_legacy_active_after_consumed_registry_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-00_legacy.md")
    legacy_hash = _sha256(legacy)
    _write_legacy_active_opt_in(tmp_path, legacy)
    archive = tmp_path / ".codex" / "handoffs" / "archive" / legacy.name
    state_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-retry.json"
    original_consume = load_transactions._consume_legacy_active

    def fail_consume(*args: object, **kwargs: object) -> None:
        raise RuntimeError("consumed registry failed")

    monkeypatch.setattr(load_transactions, "_consume_legacy_active", fail_consume)
    with pytest.raises(RuntimeError, match="consumed registry failed"):
        load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert legacy.exists()
    assert archive.exists()
    assert state_path.exists()
    assert not (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "consumed-legacy-active.json"
    ).exists()

    monkeypatch.setattr(load_transactions, "_consume_legacy_active", original_consume)

    result = load_transactions.load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert result.source_path == legacy
    assert result.archive_path == archive
    assert result.state_path == state_path
    registry = json.loads(
        (
            tmp_path
            / ".codex"
            / "handoffs"
            / ".session-state"
            / "consumed-legacy-active.json"
        ).read_text(encoding="utf-8")
    )
    assert len(registry["entries"]) == 1
    assert registry["entries"][0]["project_relative_source_path"] == legacy.relative_to(
        tmp_path
    ).as_posix()
    assert registry["entries"][0]["source_content_sha256"] == legacy_hash
    assert registry["entries"][0]["copied_primary_archive_path"] == str(archive)
    assert list_load_recovery_records(tmp_path) == []
