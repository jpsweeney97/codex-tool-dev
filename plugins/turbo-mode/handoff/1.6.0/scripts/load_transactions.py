"""Mutating load transaction primitives for Handoff storage."""

from __future__ import annotations

import json
import os
import shutil
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.session_state import allocate_archive_path, write_resume_state
from scripts.storage_authority import (
    HandoffCandidate,
    SelectionEligibility,
    StorageLocation,
    discover_handoff_inventory,
    eligible_active_candidates,
    get_storage_layout,
)


class LoadTransactionError(RuntimeError):
    pass


class TrackedRuntimeSourceError(LoadTransactionError):
    pass


@dataclass(frozen=True)
class LoadResult:
    transaction_id: str
    transaction_path: str
    source_path: Path
    archive_path: Path
    state_path: Path
    storage_location: StorageLocation


def load_handoff(
    project_root: Path,
    *,
    project_name: str | None = None,
    explicit_path: Path | None = None,
    resume_token: str | None = None,
) -> LoadResult:
    """Load a primary handoff source into archive/state under a transaction record."""
    layout = get_storage_layout(project_root)
    transaction_id = uuid.uuid4().hex
    project = project_name or layout.project_root.name
    lock_path = layout.primary_state_dir / "locks" / "load.lock"
    _acquire_lock(
        lock_path,
        project=project,
        operation="load",
        transaction_id=transaction_id,
    )
    try:
        recovered = _recover_pending_load(layout)
        if recovered is not None:
            return recovered
        candidate = _select_candidate(layout.project_root, explicit_path=explicit_path)
        _ensure_loadable(candidate)
        return _load_handoff_locked(
            layout.project_root,
            candidate=candidate,
            project_name=project_name,
            resume_token=resume_token,
            transaction_id=transaction_id,
        )
    finally:
        _release_lock(lock_path)


def _load_handoff_locked(
    project_root: Path,
    *,
    candidate: HandoffCandidate,
    project_name: str | None,
    resume_token: str | None,
    transaction_id: str,
) -> LoadResult:
    layout = get_storage_layout(project_root)
    transaction_path = layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
    project = project_name or layout.project_root.name
    state_token = resume_token or uuid.uuid4().hex
    intended_state_path = layout.primary_state_dir / f"handoff-{project}-{state_token}.json"
    _write_transaction(
        transaction_path,
        transaction_id=transaction_id,
        status="pending",
        candidate=candidate,
        archive_path=None,
        state_path=intended_state_path,
        project=project,
        resume_token=state_token,
    )

    if candidate.storage_location == StorageLocation.PRIMARY_ACTIVE:
        layout.primary_archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = allocate_archive_path(candidate.path, layout.primary_archive_dir)
        candidate.path.replace(archive_path)
    elif candidate.storage_location == StorageLocation.PRIMARY_ARCHIVE:
        archive_path = candidate.path
    elif candidate.storage_location in {
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }:
        archive_path = _copy_legacy_archive(
            layout,
            candidate,
            transaction_id=transaction_id,
        )
    elif candidate.storage_location == StorageLocation.LEGACY_ACTIVE:
        archive_path = _copy_legacy_active(layout, candidate)
    else:
        raise LoadTransactionError(
            "load-handoff failed: storage location not implemented. "
            f"Got: {candidate.storage_location!r:.100}"
        )
    _write_transaction(
        transaction_path,
        transaction_id=transaction_id,
        status="pending",
        candidate=candidate,
        archive_path=archive_path,
        state_path=intended_state_path,
        project=project,
        resume_token=state_token,
    )

    state_path = write_resume_state(
        layout.primary_state_dir,
        project,
        str(archive_path),
        state_token,
    )
    _write_transaction(
        transaction_path,
        transaction_id=transaction_id,
        status="pending",
        candidate=candidate,
        archive_path=archive_path,
        state_path=state_path,
        project=project,
        resume_token=state_token,
    )
    if candidate.storage_location == StorageLocation.LEGACY_ACTIVE:
        _consume_legacy_active(
            layout,
            candidate,
            copied_archive_path=archive_path,
            transaction_id=transaction_id,
        )
    _write_transaction(
        transaction_path,
        transaction_id=transaction_id,
        status="completed",
        candidate=candidate,
        archive_path=archive_path,
        state_path=state_path,
        project=project,
        resume_token=state_token,
    )
    return LoadResult(
        transaction_id=transaction_id,
        transaction_path=str(transaction_path),
        source_path=candidate.path,
        archive_path=archive_path,
        state_path=state_path,
        storage_location=candidate.storage_location,
    )


def list_load_recovery_records(project_root: Path) -> list[dict[str, object]]:
    """Return pending load transaction records without mutating recovery state."""
    layout = get_storage_layout(project_root)
    transactions_dir = layout.primary_state_dir / "transactions"
    if not transactions_dir.exists():
        return []
    records: list[dict[str, object]] = []
    for path in sorted(transactions_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "completed":
            records.append(data)
    return records


def _recover_pending_load(layout) -> LoadResult | None:
    transactions_dir = layout.primary_state_dir / "transactions"
    if not transactions_dir.exists():
        return None
    for transaction_path in sorted(transactions_dir.glob("*.json")):
        try:
            record = json.loads(transaction_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("operation") != "load" or record.get("status") != "pending":
            continue
        if record.get("storage_location") != StorageLocation.PRIMARY_ACTIVE:
            continue
        return _recover_primary_active_load(layout, transaction_path, record)
    return None


def _recover_primary_active_load(
    layout,
    transaction_path: Path,
    record: dict[str, object],
) -> LoadResult:
    transaction_id = str(record.get("transaction_id", ""))
    source_path = Path(str(record.get("source_path", "")))
    archive_path = Path(str(record.get("archive_path", "")))
    state_path = Path(str(record.get("state_path", "")))
    project = str(record.get("project", ""))
    resume_token = str(record.get("resume_token", ""))
    if not transaction_id or not project or not resume_token:
        raise LoadTransactionError(
            "load-handoff failed: pending transaction lacks recovery metadata. "
            f"Got: {str(transaction_path)!r:.100}"
        )
    if not archive_path.exists():
        raise LoadTransactionError(
            "load-handoff failed: pending transaction archive is missing. "
            f"Got: {str(archive_path)!r:.100}"
        )
    if not state_path.exists():
        written_state = write_resume_state(
            layout.primary_state_dir,
            project,
            str(archive_path),
            resume_token,
        )
        if written_state != state_path:
            raise LoadTransactionError(
                "load-handoff failed: recovered state path mismatch. "
                f"Got: {str(written_state)!r:.100}"
            )
    record["status"] = "completed"
    record["state_path"] = str(state_path)
    record["updated_at"] = datetime.now(UTC).isoformat()
    _write_json_atomic(transaction_path, record)
    return LoadResult(
        transaction_id=transaction_id,
        transaction_path=str(transaction_path),
        source_path=source_path,
        archive_path=archive_path,
        state_path=state_path,
        storage_location=StorageLocation.PRIMARY_ACTIVE,
    )


def _acquire_lock(
    path: Path,
    *,
    project: str,
    operation: str,
    transaction_id: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise LoadTransactionError(
            f"load-handoff failed: project load lock is already held. Got: {str(path)!r:.100}"
        ) from exc
    metadata = {
        "project": project,
        "operation": operation,
        "transaction_id": transaction_id,
        "lock_id": transaction_id,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(UTC).isoformat(),
        "timeout_seconds": 1800,
    }
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


def _release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    for directory in (path.parent, path.parent.parent):
        try:
            directory.rmdir()
        except OSError:
            pass


def _select_candidate(project_root: Path, *, explicit_path: Path | None) -> HandoffCandidate:
    if explicit_path is not None:
        inventory = discover_handoff_inventory(
            project_root,
            scan_mode="explicit-path",
            explicit_path=explicit_path,
        )
        return inventory.candidates[0]
    inventory = discover_handoff_inventory(project_root, scan_mode="active-selection")
    candidates = eligible_active_candidates(inventory)
    if not candidates:
        raise LoadTransactionError("load-handoff failed: no active handoff candidates. Got: []")
    return candidates[0]


def _ensure_loadable(candidate: HandoffCandidate) -> None:
    if candidate.selection_eligibility == SelectionEligibility.BLOCKED_TRACKED_SOURCE:
        raise TrackedRuntimeSourceError(
            "load-handoff failed: tracked runtime source cannot be moved. "
            f"Got: {str(candidate.path)!r:.100}"
        )
    if candidate.selection_eligibility != SelectionEligibility.ELIGIBLE:
        raise LoadTransactionError(
            "load-handoff failed: candidate is not eligible. "
            f"Got: {candidate.selection_eligibility!r:.100}"
        )
    if candidate.storage_location == StorageLocation.PRIMARY_ACTIVE:
        if candidate.source_git_visibility == "tracked-conflict":
            raise TrackedRuntimeSourceError(
                "load-handoff failed: tracked runtime source cannot be moved. "
                f"Got: {str(candidate.path)!r:.100}"
            )
        return
    if candidate.storage_location == StorageLocation.PRIMARY_ARCHIVE:
        return
    if candidate.storage_location in {
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }:
        return
    if candidate.storage_location == StorageLocation.LEGACY_ACTIVE:
        if candidate.artifact_class != "reviewed-runtime-migration-opt-in":
            raise LoadTransactionError(
                "load-handoff failed: legacy active source lacks accepted runtime provenance. "
                f"Got: {candidate.artifact_class!r:.100}"
            )
        return
    raise LoadTransactionError(
        "load-handoff failed: unsupported storage location. "
        f"Got: {candidate.storage_location!r:.100}"
    )


def _copy_legacy_archive(
    layout,
    candidate: HandoffCandidate,
    *,
    transaction_id: str,
) -> Path:
    registry_path = layout.primary_state_dir / "copied-legacy-archives.json"
    registry = _read_registry(registry_path)
    key = _legacy_archive_key(layout.project_root, candidate)
    for entry in registry["entries"]:
        if _registry_key(entry) != key:
            continue
        copied_path = Path(str(entry["copied_primary_archive_path"]))
        if copied_path.exists() and _sha256_file(copied_path) == candidate.content_sha256:
            return copied_path
        raise LoadTransactionError(
            "load-handoff failed: copied legacy archive registry entry is stale. "
            f"Got: {str(copied_path)!r:.100}"
        )

    layout.primary_archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = allocate_archive_path(candidate.path, layout.primary_archive_dir)
    copied_hash = _copy_to_archive_atomic(
        candidate.path,
        archive_path,
        expected_hash=candidate.content_sha256,
    )
    registry["entries"].append({
        **key,
        "source_absolute_path": str(candidate.path),
        "copied_primary_archive_path": str(archive_path),
        "copied_content_sha256": copied_hash,
        "operation": "legacy-archive-load",
        "transaction_id": transaction_id,
        "copied_at": datetime.now(UTC).isoformat(),
    })
    _write_json_atomic(registry_path, registry)
    return archive_path


def _copy_legacy_active(layout, candidate: HandoffCandidate) -> Path:
    consumed_archive_path = _verified_consumed_legacy_active_archive(layout, candidate)
    if consumed_archive_path is not None:
        return consumed_archive_path
    layout.primary_archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = allocate_archive_path(candidate.path, layout.primary_archive_dir)
    _copy_to_archive_atomic(candidate.path, archive_path, expected_hash=candidate.content_sha256)
    return archive_path


def _copy_to_archive_atomic(
    source_path: Path,
    archive_path: Path,
    *,
    expected_hash: str | None,
) -> str:
    temp_path = archive_path.with_name(f".{archive_path.name}.{uuid.uuid4().hex}.tmp")
    shutil.copy2(source_path, temp_path)
    copied_hash = _sha256_file(temp_path)
    if expected_hash is not None and copied_hash != expected_hash:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise LoadTransactionError(
            "load-handoff failed: copied archive hash mismatch. "
            f"Got: {str(archive_path)!r:.100}"
        )
    os.replace(temp_path, archive_path)
    return copied_hash


def _verified_consumed_legacy_active_archive(
    layout,
    candidate: HandoffCandidate,
) -> Path | None:
    registry_path = layout.primary_state_dir / "consumed-legacy-active.json"
    registry = _read_registry(registry_path)
    key = _legacy_active_key(layout.project_root, candidate)
    for entry in registry["entries"]:
        if _registry_key(entry) != key:
            continue
        copied_path = Path(str(entry["copied_primary_archive_path"]))
        copied_hash = str(entry.get("copied_content_sha256", ""))
        if (
            copied_path.exists()
            and copied_hash == (candidate.content_sha256 or "")
            and _sha256_file(copied_path) == copied_hash
        ):
            return copied_path
        raise LoadTransactionError(
            "load-handoff failed: consumed legacy active registry entry is stale. "
            f"Got: {str(copied_path)!r:.100}"
        )
    return None


def _consume_legacy_active(
    layout,
    candidate: HandoffCandidate,
    *,
    copied_archive_path: Path,
    transaction_id: str,
) -> None:
    registry_path = layout.primary_state_dir / "consumed-legacy-active.json"
    registry = _read_registry(registry_path)
    key = _legacy_active_key(layout.project_root, candidate)
    copied_hash = _sha256_file(copied_archive_path)
    for entry in registry["entries"]:
        if _registry_key(entry) != key:
            continue
        if (
            Path(str(entry["copied_primary_archive_path"])).exists()
            and str(entry["copied_primary_archive_path"]) == str(copied_archive_path)
            and str(entry.get("copied_content_sha256", "")) == copied_hash
        ):
            return
        raise LoadTransactionError(
            "load-handoff failed: consumed legacy active registry entry is stale. "
            f"Got: {entry.get('copied_primary_archive_path')!r:.100}"
        )
    registry["entries"].append({
        **key,
        "source_absolute_path": str(candidate.path),
        "source_resolved_path": str(candidate.path.resolve()),
        "copied_primary_archive_path": str(copied_archive_path),
        "copied_content_sha256": copied_hash,
        "operation": "legacy-load",
        "transaction_id": transaction_id,
        "consumed_at": datetime.now(UTC).isoformat(),
    })
    _write_json_atomic(registry_path, registry)


def _read_registry(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"entries": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise LoadTransactionError(
            f"load-handoff failed: invalid copied legacy archive registry. Got: {str(path)!r:.100}"
        )
    return data


def _legacy_archive_key(project_root: Path, candidate: HandoffCandidate) -> dict[str, str]:
    return {
        "source_root": str(project_root),
        "project_relative_source_path": candidate.path.relative_to(project_root).as_posix(),
        "storage_location": candidate.storage_location,
        "source_content_sha256": candidate.content_sha256 or "",
    }


def _legacy_active_key(project_root: Path, candidate: HandoffCandidate) -> dict[str, str]:
    return {
        "source_root": "project_root",
        "project_relative_source_path": candidate.path.relative_to(project_root).as_posix(),
        "storage_location": candidate.storage_location,
        "source_content_sha256": candidate.content_sha256 or "",
    }


def _registry_key(entry: dict[str, object]) -> dict[str, str]:
    return {
        "source_root": str(entry.get("source_root", "")),
        "project_relative_source_path": str(entry.get("project_relative_source_path", "")),
        "storage_location": str(entry.get("storage_location", "")),
        "source_content_sha256": str(entry.get("source_content_sha256", "")),
    }


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _write_transaction(
    path: Path,
    *,
    transaction_id: str,
    status: str,
    candidate: HandoffCandidate,
    archive_path: Path | None,
    state_path: Path | None,
    project: str,
    resume_token: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "transaction_id": transaction_id,
        "operation": "load",
        "status": status,
        "project": project,
        "resume_token": resume_token,
        "source_path": str(candidate.path),
        "storage_location": candidate.storage_location,
        "source_git_visibility": candidate.source_git_visibility,
        "source_fs_status": candidate.source_fs_status,
        "source_content_sha256": candidate.content_sha256,
        "archive_path": str(archive_path) if archive_path is not None else None,
        "state_path": str(state_path) if state_path is not None else None,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _write_json_atomic(path, payload)
