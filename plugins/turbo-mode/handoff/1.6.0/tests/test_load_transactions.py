from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
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
    assert not (tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "load.lock").exists()


def test_load_lock_blocks_concurrent_attempt_before_mutation(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_locked.md")
    lock = tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "load.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps({
            "lock_id": "other-writer",
            "project": "demo",
            "operation": "load",
            "transaction_id": "other-writer",
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": datetime.now(UTC).isoformat(),
            "timeout_seconds": 1800,
        }),
        encoding="utf-8",
    )

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
    pending.write_text(
        '{"transaction_id": "a", "operation": "load", "status": "pending"}',
        encoding="utf-8",
    )
    completed.write_text(
        '{"transaction_id": "b", "operation": "load", "status": "completed"}',
        encoding="utf-8",
    )
    abandoned = transactions / "abandoned.json"
    abandoned.write_text(
        '{"transaction_id": "c", "operation": "load", "status": "abandoned"}',
        encoding="utf-8",
    )

    records = list_load_recovery_records(tmp_path)

    assert records == [
        {"transaction_id": "a", "operation": "load", "status": "pending"}
    ]
    assert pending.exists()
    assert completed.exists()


def test_load_transactions_cli_load_outputs_requested_field(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "load_transactions.py"
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_cli.md")
    archive = tmp_path / ".codex" / "handoffs" / "archive" / source.name

    result = subprocess.run(
        [
            "python",
            str(script),
            "load",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--resume-token",
            "cli",
            "--field",
            "archive_path",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(archive)
    assert archive.exists()
    state_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-cli.json"
    assert json.loads(state_path.read_text(encoding="utf-8"))["archive_path"] == str(archive)


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


def _seed_pending_load_transaction(
    tmp_path: Path,
    *,
    transaction_id: str,
    source_path: Path,
    storage_location: str,
    source_content_sha256: str,
    resume_token: str = "retry",
    project: str = "demo",
) -> Path:
    transactions_dir = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions"
    )
    transactions_dir.mkdir(parents=True, exist_ok=True)
    transaction_path = transactions_dir / f"{transaction_id}.json"
    state_path = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / f"handoff-{project}-{resume_token}.json"
    )
    payload = {
        "transaction_id": transaction_id,
        "operation": "load",
        "status": "pending",
        "project": project,
        "resume_token": resume_token,
        "source_path": str(source_path),
        "storage_location": storage_location,
        "source_git_visibility": "untracked",
        "source_fs_status": "present",
        "source_content_sha256": source_content_sha256,
        "archive_path": None,
        "state_path": str(state_path),
        "updated_at": "2026-05-13T12:00:00+00:00",
    }
    transaction_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return transaction_path


def test_load_retry_recovers_primary_archive_with_archive_path_none(
    tmp_path: Path,
) -> None:
    archive = _handoff(
        tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_12-00_archived.md"
    )
    transaction_path = _seed_pending_load_transaction(
        tmp_path,
        transaction_id="primary-archive-pending",
        source_path=archive,
        storage_location="primary_archive",
        source_content_sha256=_sha256(archive),
    )

    result = load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert result.archive_path == archive
    assert result.transaction_path == str(transaction_path)
    assert result.state_path.exists()
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    assert transaction["status"] == "completed"
    assert transaction["archive_path"] == str(archive)
    assert list_load_recovery_records(tmp_path) == []


def test_load_retry_abandons_primary_active_when_source_exists(
    tmp_path: Path,
) -> None:
    source = _handoff(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_abandon.md"
    )
    pending_path = _seed_pending_load_transaction(
        tmp_path,
        transaction_id="primary-active-abandon",
        source_path=source,
        storage_location="primary_active",
        source_content_sha256=_sha256(source),
        resume_token="abandoned-attempt",
    )

    result = load_handoff(tmp_path, project_name="demo", resume_token="retry")

    abandoned = json.loads(pending_path.read_text(encoding="utf-8"))
    assert abandoned["status"] == "abandoned"
    assert abandoned["retry_reason"] == "primary-active-replace-not-started"
    assert abandoned["abandoned_by"] == "load-recovery"

    archive = tmp_path / ".codex" / "handoffs" / "archive" / source.name
    assert result.archive_path == archive
    assert result.transaction_path != str(pending_path)
    assert not source.exists()
    completed = json.loads(Path(result.transaction_path).read_text(encoding="utf-8"))
    assert completed["status"] == "completed"
    assert list_load_recovery_records(tmp_path) == []


def test_load_retry_adopts_primary_active_archive_by_hash_when_source_gone(
    tmp_path: Path,
) -> None:
    intended_source = (
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_adopted.md"
    )
    archive_dir = tmp_path / ".codex" / "handoffs" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    adopted_archive = archive_dir / "2026-05-13_12-00_adopted.md"
    _handoff(adopted_archive, title="Adopted")
    source_hash = _sha256(adopted_archive)
    pending_path = _seed_pending_load_transaction(
        tmp_path,
        transaction_id="primary-active-adopt",
        source_path=intended_source,
        storage_location="primary_active",
        source_content_sha256=source_hash,
    )

    result = load_handoff(tmp_path, project_name="demo", resume_token="retry")

    assert result.archive_path == adopted_archive
    assert result.transaction_path == str(pending_path)
    completed = json.loads(pending_path.read_text(encoding="utf-8"))
    assert completed["status"] == "completed"
    assert completed["archive_path"] == str(adopted_archive)
    assert list_load_recovery_records(tmp_path) == []


def test_load_retry_raises_unrecoverable_for_primary_active_when_source_gone_and_no_match(
    tmp_path: Path,
) -> None:
    intended_source = (
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_missing.md"
    )
    pending_path = _seed_pending_load_transaction(
        tmp_path,
        transaction_id="primary-active-missing",
        source_path=intended_source,
        storage_location="primary_active",
        source_content_sha256="a" * 64,
    )

    with pytest.raises(LoadTransactionError, match="unrecoverable"):
        load_handoff(tmp_path, project_name="demo", resume_token="retry")

    record = json.loads(pending_path.read_text(encoding="utf-8"))
    assert record["status"] == "pending"


def test_load_retry_raises_ambiguous_for_primary_active_with_multiple_hash_matches(
    tmp_path: Path,
) -> None:
    intended_source = (
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_ambiguous.md"
    )
    archive_dir = tmp_path / ".codex" / "handoffs" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    first = _handoff(archive_dir / "2026-05-13_12-00_ambiguous.md", title="Ambiguous")
    second = archive_dir / "2026-05-13_12-00_ambiguous-01.md"
    second.write_bytes(first.read_bytes())
    source_hash = _sha256(first)
    _seed_pending_load_transaction(
        tmp_path,
        transaction_id="primary-active-ambiguous",
        source_path=intended_source,
        storage_location="primary_active",
        source_content_sha256=source_hash,
    )

    with pytest.raises(LoadTransactionError, match="ambiguous") as excinfo:
        load_handoff(tmp_path, project_name="demo", resume_token="retry")

    message = str(excinfo.value)
    assert str(first) in message
    assert str(second) in message


def test_load_retry_abandons_legacy_active_without_registry_entry(
    tmp_path: Path,
) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-00_legacy.md")
    _write_legacy_active_opt_in(tmp_path, legacy)
    pending_path = _seed_pending_load_transaction(
        tmp_path,
        transaction_id="legacy-active-abandon",
        source_path=legacy,
        storage_location="legacy_active",
        source_content_sha256=_sha256(legacy),
        resume_token="abandoned-attempt",
    )

    result = load_handoff(tmp_path, project_name="demo", resume_token="retry")

    abandoned = json.loads(pending_path.read_text(encoding="utf-8"))
    assert abandoned["status"] == "abandoned"
    assert abandoned["retry_reason"] == "legacy-active-copy-not-recorded"
    assert abandoned["abandoned_by"] == "load-recovery"

    archive = tmp_path / ".codex" / "handoffs" / "archive" / legacy.name
    assert result.archive_path == archive
    assert result.transaction_path != str(pending_path)
    completed = json.loads(Path(result.transaction_path).read_text(encoding="utf-8"))
    assert completed["status"] == "completed"
    registry_path = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "consumed-legacy-active.json"
    )
    assert registry_path.exists()
    assert list_load_recovery_records(tmp_path) == []


def test_load_retry_abandons_legacy_archive_without_registry_entry(
    tmp_path: Path,
) -> None:
    legacy_archive = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_legacy.md"
    )
    pending_path = _seed_pending_load_transaction(
        tmp_path,
        transaction_id="legacy-archive-abandon",
        source_path=legacy_archive,
        storage_location="legacy_archive",
        source_content_sha256=_sha256(legacy_archive),
        resume_token="abandoned-attempt",
    )

    result = load_handoff(
        tmp_path,
        project_name="demo",
        explicit_path=legacy_archive,
        resume_token="retry",
    )

    abandoned = json.loads(pending_path.read_text(encoding="utf-8"))
    assert abandoned["status"] == "abandoned"
    assert abandoned["retry_reason"] == "legacy-archive-copy-not-recorded"
    assert abandoned["abandoned_by"] == "load-recovery"

    archive = tmp_path / ".codex" / "handoffs" / "archive" / legacy_archive.name
    assert result.archive_path == archive
    assert result.transaction_path != str(pending_path)
    registry_path = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "copied-legacy-archives.json"
    )
    assert registry_path.exists()
    final_records = list_load_recovery_records(tmp_path)
    assert final_records == []


# ── Lock liveness tests ─────────────────────────────────────────────


def _load_lock_path(tmp_path: Path) -> Path:
    return tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "load.lock"


def _valid_load_lock_metadata(
    *,
    created_at: datetime | None = None,
    timeout_seconds: int = 1800,
    hostname: str | None = None,
) -> dict[str, object]:
    return {
        "project": "demo",
        "operation": "load",
        "transaction_id": "existing-lock",
        "lock_id": "existing-lock",
        "pid": os.getpid(),
        "hostname": hostname or socket.gethostname(),
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
        "timeout_seconds": timeout_seconds,
    }


def _stage_load_lock(tmp_path: Path, metadata: dict[str, object]) -> Path:
    lock = _load_lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(metadata), encoding="utf-8")
    return lock


def test_load_lock_blocks_within_timeout(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    lock = _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=datetime.now(UTC)))
    with pytest.raises(LoadTransactionError, match="lock is already held"):
        load_handoff(tmp_path, project_name="demo")
    assert lock.exists()


def test_load_lock_recovers_from_stale_lock_same_host_after_timeout(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    result = load_handoff(tmp_path, project_name="demo")
    lock = _load_lock_path(tmp_path)
    assert not lock.exists()
    assert result.transaction_id != "existing-lock"


def test_load_lock_fails_closed_on_unparseable_metadata(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    lock = _load_lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("not-json", encoding="utf-8")
    with pytest.raises(LoadTransactionError, match="lock metadata unreadable"):
        load_handoff(tmp_path, project_name="demo")
    assert lock.exists()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([1, 2, 3], id="non-dict"),
        pytest.param({"project": "demo"}, id="missing-created_at"),
        pytest.param(
            {"created_at": "2026-01-01T00:00:00Z", "hostname": socket.gethostname()},
            id="missing-timeout_seconds",
        ),
        pytest.param(
            {"created_at": "2026-01-01T00:00:00Z", "timeout_seconds": 1800},
            id="missing-hostname",
        ),
        pytest.param(
            {"created_at": 12345, "timeout_seconds": 1800, "hostname": socket.gethostname()},
            id="wrong-type-created_at",
        ),
        pytest.param(
            {"created_at": "2026-01-01T00:00:00Z", "timeout_seconds": "nope", "hostname": socket.gethostname()},
            id="wrong-type-timeout_seconds",
        ),
        pytest.param(
            {"created_at": "2026-01-01T00:00:00Z", "timeout_seconds": 1800, "hostname": 42},
            id="wrong-type-hostname",
        ),
        pytest.param(
            {"created_at": "not-a-date", "timeout_seconds": 1800, "hostname": socket.gethostname()},
            id="unparsable-created_at",
        ),
    ],
)
def test_load_lock_fails_closed_on_malformed_json_metadata(
    tmp_path: Path,
    payload: object,
) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    lock = _load_lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LoadTransactionError, match="lock metadata malformed"):
        load_handoff(tmp_path, project_name="demo")
    assert lock.exists()


def test_load_lock_fails_closed_on_foreign_host(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    lock = _stage_load_lock(
        tmp_path, _valid_load_lock_metadata(created_at=stale_time, hostname="different-host"),
    )
    with pytest.raises(LoadTransactionError, match="stale lock from another host"):
        load_handoff(tmp_path, project_name="demo")
    assert lock.exists()


def test_load_lock_records_new_owner_during_critical_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    lock = _load_lock_path(tmp_path)
    observed: dict[str, object] = {}

    def inspect_lock(
        project_root: Path,
        *,
        candidate: object,
        project_name: str | None,
        resume_token: str | None,
        transaction_id: str,
    ) -> load_transactions.LoadResult:
        if lock.exists():
            observed["metadata"] = json.loads(lock.read_text(encoding="utf-8"))
        observed["transaction_id"] = transaction_id
        raise RuntimeError("stop after lock inspection")

    monkeypatch.setattr(load_transactions, "_load_handoff_locked", inspect_lock)
    with pytest.raises(RuntimeError, match="stop after lock inspection"):
        load_handoff(tmp_path, project_name="demo")
    assert observed["metadata"]["lock_id"] == observed["transaction_id"]  # type: ignore[index]
    assert observed["metadata"]["lock_id"] != "existing-lock"  # type: ignore[index]


def test_load_lock_recovery_claim_present_fails_closed_with_live_hint(
    tmp_path: Path,
) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    lock = _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    claim_path = lock.with_name(lock.name + ".recovery")
    claim_path.write_text(
        json.dumps({
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": datetime.now(UTC).isoformat(),
            "timeout_seconds": 60,
        }),
        encoding="utf-8",
    )
    with pytest.raises(LoadTransactionError, match="recovery claim file present") as exc_info:
        load_handoff(tmp_path, project_name="demo")
    assert "(live recoverer:" in str(exc_info.value)
    assert "trash" in str(exc_info.value)
    assert lock.exists()
    assert claim_path.exists()


def test_load_lock_recovery_claim_present_fails_closed_with_stale_hint(
    tmp_path: Path,
) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    lock = _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    claim_path = lock.with_name(lock.name + ".recovery")
    stale_claim_time = datetime.now(UTC) - timedelta(minutes=5)
    claim_path.write_text(
        json.dumps({
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": stale_claim_time.isoformat(),
            "timeout_seconds": 60,
        }),
        encoding="utf-8",
    )
    with pytest.raises(LoadTransactionError, match="recovery claim file present") as exc_info:
        load_handoff(tmp_path, project_name="demo")
    assert "(likely stale:" in str(exc_info.value)
    assert "trash" in str(exc_info.value)
    assert lock.exists()
    assert claim_path.exists()


def test_load_lock_recovery_claim_unparseable_fails_closed(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    lock = _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    claim_path = lock.with_name(lock.name + ".recovery")
    claim_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(LoadTransactionError, match="recovery claim file present") as exc_info:
        load_handoff(tmp_path, project_name="demo")
    assert "(claim metadata unreadable)" in str(exc_info.value)
    assert "trash" in str(exc_info.value)
    assert lock.exists()
    assert claim_path.exists()


def test_load_lock_recovery_claim_malformed_fails_closed(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    lock = _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    claim_path = lock.with_name(lock.name + ".recovery")
    claim_path.write_text(
        json.dumps({"created_at": 12345, "timeout_seconds": "nope"}),
        encoding="utf-8",
    )
    with pytest.raises(LoadTransactionError, match="recovery claim file present"):
        load_handoff(tmp_path, project_name="demo")
    assert lock.exists()
    assert claim_path.exists()


def test_load_lock_recovery_claim_removed_then_operation_succeeds(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    lock = _stage_load_lock(tmp_path, _valid_load_lock_metadata(created_at=stale_time))
    claim_path = lock.with_name(lock.name + ".recovery")
    stale_claim_time = datetime.now(UTC) - timedelta(minutes=5)
    claim_path.write_text(
        json.dumps({
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": stale_claim_time.isoformat(),
            "timeout_seconds": 60,
        }),
        encoding="utf-8",
    )
    with pytest.raises(LoadTransactionError, match="recovery claim file present"):
        load_handoff(tmp_path, project_name="demo")
    claim_path.unlink()
    result = load_handoff(tmp_path, project_name="demo")
    assert not _load_lock_path(tmp_path).exists()
    assert result.transaction_id != "existing-lock"


def test_load_release_lock_preserves_session_state_dir(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_lock-test.md")
    result = load_handoff(tmp_path, project_name="demo")
    session_state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    assert session_state_dir.exists()
    assert not _load_lock_path(tmp_path).exists()


def test_recover_pending_load_filters_by_project(tmp_path: Path) -> None:
    source = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_filter-test.md")
    transactions_dir = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions"
    )
    transactions_dir.mkdir(parents=True, exist_ok=True)
    foreign_record = {
        "project": "other-project",
        "operation": "load",
        "status": "pending",
        "transaction_id": "foreign-tx",
        "storage_location": "primary_archive",
        "source_path": str(source),
        "archive_path": str(tmp_path / ".codex" / "handoffs" / "archive" / source.name),
    }
    foreign_path = transactions_dir / "foreign.json"
    foreign_path.write_text(json.dumps(foreign_record), encoding="utf-8")
    result = load_handoff(tmp_path, project_name="demo")
    assert result.transaction_id != "foreign-tx"
    foreign_after = json.loads(foreign_path.read_text(encoding="utf-8"))
    assert foreign_after["status"] == "pending"


def test_load_lock_live_contention_with_subprocess(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_contention-test.md")
    plugin_root = str(Path(__file__).resolve().parent.parent)

    lock_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "load.lock"
    lock_path_repr = repr(str(lock_path))

    ready_marker = tmp_path / "ready.marker"
    release_marker = tmp_path / "release.marker"
    ready_marker_repr = repr(str(ready_marker))
    release_marker_repr = repr(str(release_marker))

    code_a = f"""\
import sys, time
from pathlib import Path
from scripts.load_transactions import _acquire_lock, _release_lock
lock_path = Path({lock_path_repr})
ready = Path({ready_marker_repr})
release = Path({release_marker_repr})
lock_path.parent.mkdir(parents=True, exist_ok=True)
_acquire_lock(lock_path, project="demo", operation="load", transaction_id="A")
ready.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 30.0
while not release.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
if not release.exists():
    sys.exit(2)
_release_lock(lock_path)
"""

    code_b = f"""\
import sys
from pathlib import Path
from scripts.load_transactions import _acquire_lock
lock_path = Path({lock_path_repr})
try:
    _acquire_lock(lock_path, project="demo", operation="load", transaction_id="B")
except Exception as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
"""

    proc_a = subprocess.Popen(
        [sys.executable, "-c", code_a],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=plugin_root,
    )
    deadline = time.monotonic() + 30.0
    while not ready_marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready_marker.exists(), (
        f"Process A did not become ready. "
        f"stderr={proc_a.stderr.read().decode() if proc_a.stderr else 'N/A'}"
    )

    result_b = subprocess.run(
        [sys.executable, "-c", code_b],
        capture_output=True,
        text=True,
        cwd=plugin_root,
    )
    assert result_b.returncode != 0, f"Process B should have failed. stdout={result_b.stdout}"
    assert "lock is already held" in result_b.stderr, (
        f"Expected 'lock is already held' in stderr. stderr={result_b.stderr}"
    )

    release_marker.write_text("release", encoding="utf-8")
    exit_code = proc_a.wait(timeout=10)
    assert exit_code == 0, (
        f"Process A exited with {exit_code}. "
        f"stderr={proc_a.stderr.read().decode() if proc_a.stderr else 'N/A'}"
    )

    result_b2 = subprocess.run(
        [sys.executable, "-c", code_b],
        capture_output=True,
        text=True,
        cwd=plugin_root,
    )
    assert result_b2.returncode == 0, (
        f"Process B should succeed after A released. stderr={result_b2.stderr}"
    )


# ── Corruption fail-closed tests ────────────────────────────────────


def test_recover_pending_load_fails_closed_on_corrupt_transaction(tmp_path: Path) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_corrupt-test.md")
    transactions_dir = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions"
    )
    transactions_dir.mkdir(parents=True, exist_ok=True)
    corrupt = transactions_dir / "garbage.json"
    corrupt.write_text("not-json{{{", encoding="utf-8")
    with pytest.raises(LoadTransactionError, match="pending transaction record unreadable"):
        load_handoff(tmp_path, project_name="demo")


def test_recover_pending_load_fails_closed_on_corrupt_foreign_transaction(
    tmp_path: Path,
) -> None:
    _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_corrupt-foreign.md")
    transactions_dir = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions"
    )
    transactions_dir.mkdir(parents=True, exist_ok=True)
    corrupt = transactions_dir / "foreign-corrupt.json"
    corrupt.write_text("not-json{{{", encoding="utf-8")
    with pytest.raises(LoadTransactionError, match="pending transaction record unreadable"):
        load_handoff(tmp_path, project_name="demo")


def test_list_load_recovery_records_surfaces_corrupt_transaction(tmp_path: Path) -> None:
    transactions_dir = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions"
    )
    transactions_dir.mkdir(parents=True, exist_ok=True)
    corrupt = transactions_dir / "garbage.json"
    corrupt.write_text("not-json{{{", encoding="utf-8")
    records = list_load_recovery_records(tmp_path)
    assert len(records) == 1
    assert records[0]["status"] == "unreadable"
    assert records[0]["transaction_path"] == str(corrupt)
