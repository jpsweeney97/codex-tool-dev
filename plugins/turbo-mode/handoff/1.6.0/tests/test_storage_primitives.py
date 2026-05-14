from __future__ import annotations

import json
import os
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import scripts.storage_primitives as storage_primitives
from scripts.storage_primitives import (
    LockPolicy,
    acquire_lock,
    parse_created_at,
    release_lock,
    sha256_file,
    sha256_file_or_none,
    sha256_regular_file_or_none,
    write_json_atomic,
)


class HelperLockError(RuntimeError):
    pass


POLICY = LockPolicy(
    operation_label="helper-op",
    lock_kind="helper lock",
    error_factory=HelperLockError,
)


def _lock_path(tmp_path: Path) -> Path:
    return tmp_path / ".session-state" / "locks" / "helper.lock"


def _valid_lock_metadata(
    *,
    created_at: datetime,
    hostname: str | None = None,
    timeout_seconds: int = 1800,
) -> dict[str, object]:
    return {
        "project": "demo",
        "operation": "helper",
        "transaction_id": "existing-lock",
        "lock_id": "existing-lock",
        "pid": os.getpid(),
        "hostname": hostname or socket.gethostname(),
        "created_at": created_at.isoformat(),
        "timeout_seconds": timeout_seconds,
    }


def test_parse_created_at_normalizes_zulu_and_naive_values() -> None:
    assert parse_created_at("2026-05-14T04:00:00Z") == datetime(
        2026, 5, 14, 4, 0, tzinfo=UTC
    )
    assert parse_created_at("2026-05-14T04:00:00") == datetime(
        2026, 5, 14, 4, 0, tzinfo=UTC
    )


def test_parse_created_at_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        parse_created_at("not-a-date")


def test_lock_policy_rejects_empty_labels() -> None:
    with pytest.raises(ValueError, match="operation label must be non-empty"):
        LockPolicy(operation_label="", lock_kind="helper lock", error_factory=HelperLockError)
    with pytest.raises(ValueError, match="lock kind must be non-empty"):
        LockPolicy(operation_label="helper-op", lock_kind="", error_factory=HelperLockError)


def test_delete_result_validates_cross_field_invariants(tmp_path: Path) -> None:
    path = str(tmp_path / "state.json")
    with pytest.raises(ValueError, match="failed delete requires mechanism and error"):
        storage_primitives.DeleteResult(action="failed", mechanism=None, path=path)
    with pytest.raises(ValueError, match="successful delete cannot carry error"):
        storage_primitives.DeleteResult(
            action="deleted",
            mechanism="trash",
            path=path,
            error="unexpected",
        )
    with pytest.raises(ValueError, match="already_absent action cannot carry mechanism"):
        storage_primitives.DeleteResult(
            action="already_absent",
            mechanism="unlink",
            path=path,
        )


def test_write_json_atomic_writes_json_and_creates_parent(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "payload.json"
    write_json_atomic(path, {"status": "ok", "count": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "ok", "count": 1}
    assert not list(path.parent.glob("*.tmp"))


def test_sha256_file_variants(tmp_path: Path) -> None:
    path = tmp_path / "payload.txt"
    path.write_text("abc", encoding="utf-8")
    assert (
        sha256_file(path)
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert sha256_file_or_none(path) == sha256_file(path)
    assert sha256_regular_file_or_none(path) == sha256_file(path)
    assert sha256_file_or_none(tmp_path / "missing.txt") is None
    assert sha256_regular_file_or_none(tmp_path / "missing.txt") is None
    assert sha256_regular_file_or_none(tmp_path) is None


def test_sha256_helpers_preserve_distinct_regular_file_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "payload.txt"
    path.write_text("abc", encoding="utf-8")
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    assert sha256_file_or_none(path) == sha256_file(path)
    assert sha256_regular_file_or_none(path) is None


def test_acquire_lock_writes_expected_metadata_shape(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    acquire_lock(
        lock,
        project="demo",
        operation="helper",
        transaction_id="new-lock",
        policy=POLICY,
    )
    metadata = json.loads(lock.read_text(encoding="utf-8"))
    assert set(metadata) == {
        "project",
        "operation",
        "transaction_id",
        "lock_id",
        "pid",
        "hostname",
        "created_at",
        "timeout_seconds",
    }
    assert metadata["project"] == "demo"
    assert metadata["operation"] == "helper"
    assert metadata["transaction_id"] == "new-lock"
    assert metadata["lock_id"] == "new-lock"
    assert isinstance(metadata["pid"], int)
    assert isinstance(metadata["hostname"], str)
    assert isinstance(metadata["created_at"], str)
    assert metadata["timeout_seconds"] == 1800
    release_lock(lock)


def test_acquire_lock_blocks_fresh_lock(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(_valid_lock_metadata(created_at=datetime.now(UTC))),
        encoding="utf-8",
    )
    with pytest.raises(
        HelperLockError, match="helper-op failed: helper lock is already held"
    ):
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert lock.exists()


def test_acquire_lock_uses_policy_error_on_readback_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = _lock_path(tmp_path)
    monkeypatch.setattr(
        storage_primitives.json,
        "loads",
        lambda _: {"lock_id": "other-lock"},
    )
    with pytest.raises(HelperLockError) as exc_info:
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert str(exc_info.value).startswith(
        f"helper-op failed: helper lock is already held. Got: {str(lock)!r:.100}"
    )


def test_acquire_lock_uses_policy_error_on_readback_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = _lock_path(tmp_path)
    original_read_text = Path.read_text

    def fail_lock_readback(self: Path, *args: object, **kwargs: object) -> str:
        if self == lock:
            raise FileNotFoundError("lock disappeared")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_lock_readback)

    with pytest.raises(HelperLockError) as exc_info:
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert isinstance(exc_info.value.__cause__, FileNotFoundError)
    assert str(exc_info.value).startswith(
        f"helper-op failed: helper lock is already held. Got: {str(lock)!r:.100}"
    )


def test_acquire_lock_recovers_stale_same_host_lock(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(
            _valid_lock_metadata(
                created_at=datetime.now(UTC) - timedelta(hours=2),
                timeout_seconds=1800,
            )
        ),
        encoding="utf-8",
    )
    acquire_lock(
        lock,
        project="demo",
        operation="helper",
        transaction_id="new-lock",
        policy=POLICY,
    )
    metadata = json.loads(lock.read_text(encoding="utf-8"))
    assert metadata["lock_id"] == "new-lock"
    release_lock(lock)
    assert not lock.exists()
    assert (tmp_path / ".session-state").exists()


def test_acquire_lock_fails_closed_on_foreign_host_stale_lock(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(
            _valid_lock_metadata(
                created_at=datetime.now(UTC) - timedelta(hours=2),
                hostname="different-host",
                timeout_seconds=1800,
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        HelperLockError, match="stale lock from another host"
    ) as exc_info:
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert "different-host" in str(exc_info.value)
    assert lock.exists()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(["not-a-dict"], id="non-dict"),
        pytest.param({"created_at": datetime.now(UTC).isoformat()}, id="missing-fields"),
        pytest.param(
            {
                "created_at": 12345,
                "timeout_seconds": "nope",
                "hostname": 42,
            },
            id="wrong-types",
        ),
    ],
)
def test_acquire_lock_fails_closed_on_malformed_metadata(
    tmp_path: Path,
    payload: object,
) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HelperLockError, match="lock metadata malformed"):
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert lock.exists()


def test_acquire_lock_fails_closed_on_existing_recovery_claim(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(_valid_lock_metadata(created_at=datetime.now(UTC) - timedelta(hours=2))),
        encoding="utf-8",
    )
    claim = lock.with_name(lock.name + ".recovery")
    claim.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "created_at": datetime.now(UTC).isoformat(),
                "timeout_seconds": 60,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(HelperLockError, match="recovery claim file present") as exc_info:
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert isinstance(exc_info.value.__cause__, FileExistsError)
    assert "trash" in str(exc_info.value)
    assert lock.exists()
    assert claim.exists()


def test_acquire_lock_existing_claim_invalid_created_at_has_no_age_hint(
    tmp_path: Path,
) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps(_valid_lock_metadata(created_at=datetime.now(UTC) - timedelta(hours=2))),
        encoding="utf-8",
    )
    claim = lock.with_name(lock.name + ".recovery")
    claim.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "created_at": "not-a-date",
                "timeout_seconds": 60,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(HelperLockError, match="recovery claim file present") as exc_info:
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    message = str(exc_info.value)
    assert "recovery claim file present; if no process" in message
    assert "claim metadata unreadable" not in message
    assert "live recoverer" not in message
    assert "likely stale" not in message
    assert lock.exists()
    assert claim.exists()


def test_acquire_lock_writes_claim_metadata_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("not-json", encoding="utf-8")
    captured_claim: dict[str, object] = {}
    original_unlink = storage_primitives.os.unlink

    def capture_claim_before_unlink(path: str | os.PathLike[str]) -> None:
        unlink_path = Path(path)
        if unlink_path.name.endswith(".recovery") and unlink_path.exists():
            captured_claim.update(json.loads(unlink_path.read_text(encoding="utf-8")))
        original_unlink(path)

    monkeypatch.setattr(storage_primitives.os, "unlink", capture_claim_before_unlink)
    with pytest.raises(HelperLockError, match="lock metadata unreadable"):
        acquire_lock(
            lock,
            project="demo",
            operation="helper",
            transaction_id="new-lock",
            policy=POLICY,
        )
    assert captured_claim["timeout_seconds"] == 60
    assert set(captured_claim) == {"pid", "hostname", "created_at", "timeout_seconds"}


def test_read_json_object_returns_default_for_missing_path(tmp_path: Path) -> None:
    assert storage_primitives.read_json_object(
        tmp_path / "missing.json",
        missing={"entries": []},
    ) == {"entries": []}


def test_read_json_object_rejects_unreadable_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object unreadable"):
        storage_primitives.read_json_object(path)


def test_read_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object malformed"):
        storage_primitives.read_json_object(path)


def test_write_text_atomic_exclusive_uses_suffix_without_replacing_existing(
    tmp_path: Path,
) -> None:
    first = tmp_path / "envelope.json"
    first.write_text("existing", encoding="utf-8")

    written = storage_primitives.write_text_atomic_exclusive(first, "new")

    assert written == tmp_path / "envelope-01.json"
    assert first.read_text(encoding="utf-8") == "existing"
    assert written.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob("*.tmp"))


def test_write_text_atomic_exclusive_cleans_temp_before_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "envelope.json"
    first_temp_path: Path | None = None
    call_count = 0
    original_link = storage_primitives.os.link

    def flaky_link(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal first_temp_path, call_count
        call_count += 1
        if call_count == 1:
            first_temp_path = Path(src)
            raise FileExistsError("simulated collision")
        assert first_temp_path is not None
        assert not first_temp_path.exists()
        original_link(src, dst)

    monkeypatch.setattr(storage_primitives.os, "link", flaky_link)

    written = storage_primitives.write_text_atomic_exclusive(target, "new")

    assert written == tmp_path / "envelope-01.json"
    assert written.read_text(encoding="utf-8") == "new"
    assert call_count == 2
    assert not list(tmp_path.glob("*.tmp"))


def test_write_text_atomic_exclusive_exhausts_collision_budget(tmp_path: Path) -> None:
    for index in range(100):
        suffix = "" if index == 0 else f"-{index:02d}"
        (tmp_path / f"envelope{suffix}.json").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="collision budget exhausted"):
        storage_primitives.write_text_atomic_exclusive(tmp_path / "envelope.json", "new")


def test_safe_delete_uses_trash_when_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> object:
        calls.append(args)
        return object()

    def forbid_unlink(self: Path, *args: object, **kwargs: object) -> None:
        raise AssertionError(f"unlink should not run after successful trash: {self}")

    monkeypatch.setattr(storage_primitives.subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "unlink", forbid_unlink)

    result = storage_primitives.safe_delete(path)

    assert result.action == "deleted"
    assert result.mechanism == "trash"
    assert result.path == str(path)
    assert calls == [["trash", str(path)]]
    assert path.exists()


def test_safe_delete_falls_back_to_unlink_when_trash_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    monkeypatch.setattr(storage_primitives.subprocess, "run", fail_trash)

    result = storage_primitives.safe_delete(path)

    assert result.action == "deleted"
    assert result.mechanism == "unlink"
    assert result.path == str(path)
    assert not path.exists()


def test_safe_delete_reports_already_absent(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    result = storage_primitives.safe_delete(path)

    assert result.action == "already_absent"
    assert result.mechanism is None
    assert result.path == str(path)


def test_safe_delete_returns_failed_when_trash_and_unlink_both_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    original_unlink = Path.unlink

    def fail_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == path:
            raise PermissionError("unlink denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(storage_primitives.subprocess, "run", fail_trash)
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    result = storage_primitives.safe_delete(path)

    assert result.action == "failed"
    assert result.mechanism == "unlink"
    assert result.path == str(path)
    assert result.error is not None
    assert "unlink" in result.error
    assert path.exists()


def test_release_lock_prunes_empty_locks_dir(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("{}", encoding="utf-8")

    release_lock(lock)

    assert not lock.exists()
    assert not lock.parent.exists()
    assert lock.parent.parent.exists()


def test_release_lock_preserves_locks_dir_with_sibling(tmp_path: Path) -> None:
    lock = _lock_path(tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("{}", encoding="utf-8")
    sibling = lock.with_name("sibling.lock")
    sibling.write_text("{}", encoding="utf-8")

    release_lock(lock)

    assert not lock.exists()
    assert sibling.exists()
    assert lock.parent.exists()
