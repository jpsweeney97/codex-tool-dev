"""Lifecycle helpers for project-local Ticket prepare payloads."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from stat import S_ISDIR, S_ISLNK, S_ISREG

DEFAULT_STALE_PAYLOAD_TTL = timedelta(hours=24)


class TicketPayloadPathError(ValueError):
    """Raised when a Ticket payload path escapes the project-local temp root."""


@dataclass(frozen=True)
class StalePayload:
    path: Path
    age_seconds: int
    size_bytes: int
    modified_at: str


def _same_file(first: os.stat_result, second: os.stat_result) -> bool:
    return first.st_dev == second.st_dev and first.st_ino == second.st_ino


def _validate_logical_temp_path(project_root: Path) -> Path:
    project = project_root.resolve()
    codex = project / ".codex"
    root = codex / "ticket-tmp"

    try:
        codex_stat = codex.lstat()
    except FileNotFoundError:
        return root
    except OSError as exc:
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: cannot inspect .codex directory. "
            f"Got: {str(codex)!r:.100}"
        ) from exc
    if S_ISLNK(codex_stat.st_mode):
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: .codex directory must not be "
            f"a symlink. Got: {str(codex)!r:.100}"
        )
    if not S_ISDIR(codex_stat.st_mode):
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: .codex must be a directory. "
            f"Got: {str(codex)!r:.100}"
        )
    return root


def _open_ticket_tmp_dir(project_root: Path) -> tuple[Path, int | None]:
    """Open the validated logical temp directory, returning None when absent."""
    root = resolved_ticket_tmp_dir(project_root)
    try:
        expected = root.lstat()
    except FileNotFoundError:
        return root, None

    flags = os.O_RDONLY
    for flag_name in ("O_DIRECTORY", "O_CLOEXEC", "O_NOFOLLOW"):
        flags |= getattr(os, flag_name, 0)
    try:
        fd = os.open(root, flags)
    except FileNotFoundError:
        return root, None
    except OSError as exc:
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: cannot open logical temp directory. "
            f"Got: {str(root)!r:.100}"
        ) from exc

    try:
        opened = os.fstat(fd)
        if not _same_file(expected, opened):
            raise TicketPayloadPathError(
                "ticket tmp directory containment failed: logical temp directory changed "
                f"after validation. Got: {str(root)!r:.100}"
            )
    except Exception:
        os.close(fd)
        raise
    return root, fd


def _payload_stat_from_dir(fd: int, root: Path, name: str) -> os.stat_result | None:
    try:
        payload_stat = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if S_ISLNK(payload_stat.st_mode):
        raise TicketPayloadPathError(
            "ticket payload cleanup failed: payload path must not be a symlink. "
            f"Got: {str(root / name)!r:.100}"
        )
    if not S_ISREG(payload_stat.st_mode):
        return None
    return payload_stat


def resolved_ticket_tmp_dir(project_root: Path) -> Path:
    """Return the logical temp directory, rejecting symlinked or invalid roots."""
    project = project_root.resolve()
    root = _validate_logical_temp_path(project)
    try:
        root_stat = root.lstat()
    except FileNotFoundError:
        return root
    except OSError as exc:
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: cannot inspect logical temp directory. "
            f"Got: {str(root)!r:.100}"
        ) from exc
    if S_ISLNK(root_stat.st_mode):
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: logical temp directory must not be "
            f"a symlink. Got: {str(root)!r:.100}"
        )
    if not S_ISDIR(root_stat.st_mode):
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: logical temp directory must be "
            f"a directory. Got: {str(root)!r:.100}"
        )
    try:
        root.resolve().relative_to(project)
    except ValueError as exc:
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: resolved temp directory "
            f"is outside project root. Got: {str(root.resolve())!r:.100}"
        ) from exc
    return root


def delete_consumed_payload(payload_path: Path, project_root: Path) -> bool:
    """Delete a consumed prepare payload only inside project_root/.codex/ticket-tmp."""
    root, fd = _open_ticket_tmp_dir(project_root)
    if fd is None:
        return False
    try:
        payload_path.relative_to(root)
    except ValueError:
        os.close(fd)
        return False
    if payload_path.parent != root:
        os.close(fd)
        return False
    try:
        payload_stat = _payload_stat_from_dir(fd, root, payload_path.name)
        if payload_stat is None:
            return False
        try:
            os.unlink(payload_path.name, dir_fd=fd)
        except FileNotFoundError:
            return False
        return True
    finally:
        os.close(fd)


def stale_payloads(
    project_root: Path,
    *,
    now: datetime | None = None,
    stale_after: timedelta = DEFAULT_STALE_PAYLOAD_TTL,
) -> list[StalePayload]:
    """Return stale JSON payloads under project_root/.codex/ticket-tmp."""
    current = now or datetime.now(UTC)
    root, fd = _open_ticket_tmp_dir(project_root)
    if fd is None:
        return []
    try:
        stale: list[StalePayload] = []
        for name in sorted(os.listdir(fd)):
            if not name.endswith(".json"):
                continue
            path_stat = _payload_stat_from_dir(fd, root, name)
            if path_stat is None:
                continue
            modified = datetime.fromtimestamp(path_stat.st_mtime, tz=UTC)
            age = current - modified
            if age <= stale_after:
                continue
            stale.append(
                StalePayload(
                    path=root / name,
                    age_seconds=int(age.total_seconds()),
                    size_bytes=path_stat.st_size,
                    modified_at=modified.isoformat(),
                )
            )
        return stale
    finally:
        os.close(fd)


def clean_stale_payloads(
    project_root: Path,
    *,
    now: datetime | None = None,
    stale_after: timedelta = DEFAULT_STALE_PAYLOAD_TTL,
) -> list[StalePayload]:
    """Delete stale JSON payloads under project_root/.codex/ticket-tmp and return deletions."""
    current = now or datetime.now(UTC)
    root, fd = _open_ticket_tmp_dir(project_root)
    if fd is None:
        return []
    try:
        deleted: list[StalePayload] = []
        for name in sorted(os.listdir(fd)):
            if not name.endswith(".json"):
                continue
            path_stat = _payload_stat_from_dir(fd, root, name)
            if path_stat is None:
                continue
            modified = datetime.fromtimestamp(path_stat.st_mtime, tz=UTC)
            age = current - modified
            if age <= stale_after:
                continue
            item = StalePayload(
                path=root / name,
                age_seconds=int(age.total_seconds()),
                size_bytes=path_stat.st_size,
                modified_at=modified.isoformat(),
            )
            if _payload_stat_from_dir(fd, root, name) is None:
                continue
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                continue
            deleted.append(item)
        return deleted
    finally:
        os.close(fd)
