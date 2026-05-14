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
