"""Shared filesystem primitives for Handoff storage scripts.

This module is intentionally stdlib-only and must not import local Handoff
modules. Import direction is scripts.* modules -> storage_primitives only.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


_CLAIM_TIMEOUT_SECONDS = 60
_LOCK_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True)
class LockPolicy:
    """Caller-specific diagnostics for a shared lock implementation."""

    operation_label: str
    lock_kind: str
    error_factory: Callable[[str], Exception]


@dataclass(frozen=True)
class DeleteResult:
    action: str
    mechanism: str | None
    path: str
    error: str | None = None


def parse_created_at(value: str | None) -> datetime:
    """Parse an ISO timestamp as UTC, treating missing timezone as UTC."""
    if value is None:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """Write a JSON object through a sibling temp file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def read_json_object(
    path: Path,
    *,
    missing: dict[str, object] | None = None,
) -> dict[str, object]:
    """Read a JSON object from disk, optionally returning a missing-file default."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if missing is not None:
            return dict(missing)
        raise
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"read-json-object failed: JSON object unreadable. Got: {str(path)!r:.100}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"read-json-object failed: JSON object malformed. Got: {str(path)!r:.100}"
        )
    return payload


def write_text_atomic_exclusive(
    path: Path,
    payload: str,
    *,
    max_attempts: int = 100,
) -> Path:
    """Write text through a sibling temp file and publish via exclusive hard link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    suffix = path.suffix
    for attempt in range(max_attempts):
        retry_suffix = "" if attempt == 0 else f"-{attempt:02d}"
        candidate = path.with_name(f"{stem}{retry_suffix}{suffix}")
        temp_path = candidate.with_name(f".{candidate.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(payload, encoding="utf-8")
            try:
                os.link(temp_path, candidate)
            except FileExistsError:
                continue
            return candidate
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
    raise FileExistsError(
        f"write-text-atomic-exclusive failed: collision budget exhausted. Got: {str(path)!r:.100}"
    )


def safe_delete(path: Path) -> DeleteResult:
    """Delete one file by preferring trash, then unlink, then reporting failure.

    Returns a DeleteResult with action in {"deleted", "already_absent", "failed"}.
    Never raises for trash or unlink errors; callers inspect ``action`` to decide
    whether to enter their own recovery flow. ``mechanism`` records which delete
    path was attempted on success or partial-attempt; ``error`` carries the last
    underlying exception string on failure so callers can surface it in
    operator-actionable messages.
    """
    if not path.exists():
        return DeleteResult(action="already_absent", mechanism=None, path=str(path))
    try:
        subprocess.run(
            ["trash", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return DeleteResult(action="deleted", mechanism="trash", path=str(path))
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as trash_exc:
        try:
            path.unlink()
        except FileNotFoundError:
            return DeleteResult(action="already_absent", mechanism=None, path=str(path))
        except OSError as unlink_exc:
            return DeleteResult(
                action="failed",
                mechanism="unlink",
                path=str(path),
                error=f"trash: {trash_exc!r}; unlink: {unlink_exc!r}",
            )
        return DeleteResult(action="deleted", mechanism="unlink", path=str(path))


def sha256_file(path: Path) -> str:
    """Return the SHA256 digest for a readable file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file_or_none(path: Path) -> str | None:
    """Return the SHA256 digest for a readable file, or None on read failure."""
    try:
        return sha256_file(path)
    except OSError:
        return None


def sha256_regular_file_or_none(path: Path) -> str | None:
    """Return the SHA256 digest for a regular file, or None otherwise."""
    try:
        if not path.is_file():
            return None
        return sha256_file(path)
    except OSError:
        return None


def acquire_lock(
    path: Path,
    *,
    project: str,
    operation: str,
    transaction_id: str,
    policy: LockPolicy,
) -> None:
    """Acquire a project lock, recovering stale same-host locks when safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if _try_recover_stale_lock(path, now=datetime.now(UTC), policy=policy):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                raise _held_error(path, policy) from exc
        else:
            raise _held_error(path, policy)
    metadata = {
        "project": project,
        "operation": operation,
        "transaction_id": transaction_id,
        "lock_id": transaction_id,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(UTC).isoformat(),
        "timeout_seconds": _LOCK_TIMEOUT_SECONDS,
    }
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    lock_check = json.loads(path.read_text(encoding="utf-8"))
    if lock_check.get("lock_id") != transaction_id:
        raise _held_error(path, policy)


def release_lock(path: Path) -> None:
    """Release a lock file and prune only the immediate locks directory."""
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    try:
        path.parent.rmdir()
    except OSError:
        pass


def _held_error(path: Path, policy: LockPolicy) -> Exception:
    return policy.error_factory(
        f"{policy.operation_label} failed: {policy.lock_kind} is already held. "
        f"Got: {str(path)!r:.100}"
    )


def _write_claim_metadata(claim_fd: int) -> None:
    payload = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(UTC).isoformat(),
        "timeout_seconds": _CLAIM_TIMEOUT_SECONDS,
    }
    try:
        os.write(claim_fd, json.dumps(payload).encode("utf-8"))
        os.fsync(claim_fd)
    finally:
        os.close(claim_fd)


def _try_recover_stale_lock(path: Path, *, now: datetime, policy: LockPolicy) -> bool:
    claim_path = path.with_name(path.name + ".recovery")
    try:
        claim_fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        claim_age_hint = _claim_age_hint(claim_path, now=now)
        raise policy.error_factory(
            f"{policy.operation_label} failed: recovery claim file present{claim_age_hint}; "
            f"if no process is actively recovering this lock, run `trash {claim_path}` and retry. "
            f"Got: {str(claim_path)!r:.100}"
        )
    try:
        _write_claim_metadata(claim_fd)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return True
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise policy.error_factory(
                f"{policy.operation_label} failed: lock metadata unreadable; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            ) from exc
        if not isinstance(payload, dict):
            raise _malformed_error(path, policy)
        created_at = payload.get("created_at")
        timeout = payload.get("timeout_seconds")
        hostname = payload.get("hostname")
        if (
            not isinstance(created_at, str)
            or not isinstance(timeout, (int, float))
            or not isinstance(hostname, str)
        ):
            raise _malformed_error(path, policy)
        try:
            created = parse_created_at(created_at)
        except ValueError as exc:
            raise _malformed_error(path, policy) from exc
        if (now - created).total_seconds() <= timeout:
            return False
        if hostname != socket.gethostname():
            raise policy.error_factory(
                f"{policy.operation_label} failed: stale lock from another host; manual operator review required. "
                f"Got: {(hostname, str(path))!r:.100}"
            )
        os.unlink(path)
        return True
    finally:
        try:
            os.unlink(claim_path)
        except FileNotFoundError:
            pass


def _claim_age_hint(claim_path: Path, *, now: datetime) -> str:
    try:
        claim_payload = json.loads(claim_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return " (claim metadata unreadable)"
    if not isinstance(claim_payload, dict):
        return ""
    c_pid = claim_payload.get("pid")
    c_host = claim_payload.get("hostname")
    c_created = claim_payload.get("created_at")
    c_timeout = claim_payload.get("timeout_seconds")
    if not isinstance(c_created, str):
        return ""
    try:
        age = (now - parse_created_at(c_created)).total_seconds()
    except ValueError:
        return ""
    if isinstance(c_timeout, (int, float)) and age > c_timeout:
        return f" (likely stale: pid={c_pid!r} host={c_host!r} age={age:.0f}s)"
    return f" (live recoverer: pid={c_pid!r} host={c_host!r})"


def _malformed_error(path: Path, policy: LockPolicy) -> Exception:
    return policy.error_factory(
        f"{policy.operation_label} failed: lock metadata malformed; manual operator review required. "
        f"Got: {str(path)!r:.100}"
    )
