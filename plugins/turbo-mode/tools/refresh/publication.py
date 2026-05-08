from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import RefreshError, fail


@dataclass(frozen=True)
class PublicationReplayPaths:
    candidate: Path
    final: Path
    metadata: Path
    redaction: Path
    redaction_final: Path
    published: Path
    failed: Path


@dataclass(frozen=True)
class PublicationReplayResult:
    candidate_summary_path: str
    final_summary_path: str
    metadata_summary_path: str
    redaction_summary_path: str
    redaction_final_summary_path: str
    published_summary_path: str
    published_summary_sha256: str


def publish_and_replay_commit_safe_summary(
    *,
    operation: str,
    paths: PublicationReplayPaths,
    build_candidate_payload: Callable[[], dict[str, Any]],
    build_final_payload: Callable[[str, str], dict[str, Any]],
    validate_payload: Callable[[dict[str, Any]], None],
    run_candidate_validation: Callable[[PublicationReplayPaths], None],
    run_final_validation: Callable[[PublicationReplayPaths], None],
) -> PublicationReplayResult:
    reject_summary_path_state(
        published=paths.published,
        failed=paths.failed,
        operation=operation,
    )
    candidate_payload = build_candidate_payload()
    validate_payload(candidate_payload)
    write_json_0600_exclusive(paths.candidate, candidate_payload)
    run_candidate_validation(paths)

    final_payload = build_final_payload(
        sha256_file(paths.metadata),
        sha256_file(paths.redaction),
    )
    validate_payload(final_payload)
    write_json_0600_exclusive(paths.final, final_payload)
    publish_json_0600_crash_safe(
        source_payload_path=paths.final,
        final_path=paths.published,
        operation=operation,
    )
    try:
        run_final_validation(paths)
    except BaseException as exc:
        demoted_path = demote_published_summary_0600_crash_safe(
            published=paths.published,
            failed=paths.failed,
            operation=operation,
        )
        try:
            setattr(exc, "demoted_summary_path", str(demoted_path))
        except (AttributeError, TypeError):
            pass
        raise

    return PublicationReplayResult(
        candidate_summary_path=str(paths.candidate),
        final_summary_path=str(paths.final),
        metadata_summary_path=str(paths.metadata),
        redaction_summary_path=str(paths.redaction),
        redaction_final_summary_path=str(paths.redaction_final),
        published_summary_path=str(paths.published),
        published_summary_sha256=sha256_file(paths.published),
    )


def reject_summary_path_state(
    *,
    published: Path,
    failed: Path,
    operation: str,
) -> None:
    published_exists = published.exists()
    failed_exists = failed.exists()
    if published_exists and failed_exists:
        fail(
            operation,
            "published and failed summary paths coexist",
            {"published": str(published), "failed": str(failed)},
        )
    if published_exists:
        fail(operation, "published summary already exists", str(published))
    if failed_exists:
        fail(operation, "failed summary already exists", str(failed))


def write_json_0600_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)
    _fsync_dir(path.parent)


def publish_json_0600_crash_safe(
    *,
    source_payload_path: Path,
    final_path: Path,
    operation: str,
) -> None:
    if final_path.exists():
        fail(operation, "published summary already exists", str(final_path))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.parent / f".{final_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_bytes_0600_exclusive(temp_path, source_payload_path.read_bytes())
        _rename_no_overwrite(temp_path, final_path, operation=operation)
        _fsync_dir(final_path.parent)
    except BaseException:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        raise


def demote_published_summary_0600_crash_safe(
    *,
    published: Path,
    failed: Path,
    operation: str,
) -> Path:
    if failed.exists():
        fail(operation, "failed summary already exists", str(failed))
    if not published.exists():
        fail(operation, "published summary missing before demotion", str(published))
    _rename_no_overwrite(published, failed, operation=operation)
    _fsync_dir(failed.parent)
    return failed


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_bytes_0600_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def _rename_no_overwrite(source: Path, target: Path, *, operation: str) -> None:
    if source.parent != target.parent:
        fail(
            operation,
            "crash-safe rename requires same directory",
            f"{source!s} -> {target!s}",
        )
    if target.exists():
        fail(operation, "rename target already exists", str(target))
    if not source.exists():
        fail(operation, "rename source missing", str(source))
    if sys.platform == "darwin":
        _rename_no_overwrite_darwin(source, target, operation=operation)
    elif sys.platform.startswith("linux"):
        _rename_no_overwrite_linux(source, target, operation=operation)
    else:
        raise RefreshError(
            "crash-safe rename failed: unsupported platform. "
            f"Got: {sys.platform!r:.100}"
        )
    if source.exists() or not target.exists():
        fail(
            operation,
            "crash-safe rename final path validation failed",
            {
                "source_exists": source.exists(),
                "target_exists": target.exists(),
            },
        )


def _rename_no_overwrite_darwin(source: Path, target: Path, *, operation: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renamex_np = getattr(libc, "renamex_np", None)
    if renamex_np is None:
        fail(operation, "renamex_np unavailable", f"{source!s} -> {target!s}")
    renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    renamex_np.restype = ctypes.c_int
    rename_excl = 0x00000004
    result = renamex_np(os.fsencode(source), os.fsencode(target), rename_excl)
    if result != 0:
        err = ctypes.get_errno()
        raise RefreshError(
            "crash-safe rename failed: renamex_np exited non-zero. "
            f"Got: errno={err!r:.100}"
        )


def _rename_no_overwrite_linux(source: Path, target: Path, *, operation: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        fail(operation, "renameat2 unavailable", f"{source!s} -> {target!s}")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    result = renameat2(
        at_fdcwd,
        os.fsencode(source),
        at_fdcwd,
        os.fsencode(target),
        rename_noreplace,
    )
    if result != 0:
        err = ctypes.get_errno()
        raise RefreshError(
            "crash-safe rename failed: renameat2 exited non-zero. "
            f"Got: errno={err!r:.100}"
        )


def _fsync_dir(path: Path) -> None:
    dir_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
