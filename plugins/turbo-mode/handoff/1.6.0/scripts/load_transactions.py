"""Mutating load transaction primitives for Handoff storage."""

from __future__ import annotations

import json
import os
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
    candidate = _select_candidate(layout.project_root, explicit_path=explicit_path)
    _ensure_loadable(candidate)
    lock_path = layout.primary_state_dir / "load.lock"
    _acquire_lock(lock_path)
    try:
        return _load_handoff_locked(
            layout.project_root,
            candidate=candidate,
            project_name=project_name,
            resume_token=resume_token,
        )
    finally:
        _release_lock(lock_path)


def _load_handoff_locked(
    project_root: Path,
    *,
    candidate: HandoffCandidate,
    project_name: str | None,
    resume_token: str | None,
) -> LoadResult:
    layout = get_storage_layout(project_root)
    transaction_id = uuid.uuid4().hex
    transaction_path = layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
    project = project_name or layout.project_root.name
    _write_transaction(
        transaction_path,
        transaction_id=transaction_id,
        status="pending",
        candidate=candidate,
        archive_path=None,
        state_path=None,
    )

    if candidate.storage_location == StorageLocation.PRIMARY_ACTIVE:
        layout.primary_archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = allocate_archive_path(candidate.path, layout.primary_archive_dir)
        candidate.path.replace(archive_path)
    elif candidate.storage_location == StorageLocation.PRIMARY_ARCHIVE:
        archive_path = candidate.path
    else:
        raise LoadTransactionError(
            "load-handoff failed: storage location not implemented. "
            f"Got: {candidate.storage_location!r:.100}"
        )

    state_path = write_resume_state(
        layout.primary_state_dir,
        project,
        str(archive_path),
        resume_token,
    )
    _write_transaction(
        transaction_path,
        transaction_id=transaction_id,
        status="completed",
        candidate=candidate,
        archive_path=archive_path,
        state_path=state_path,
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


def _acquire_lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise LoadTransactionError(
            f"load-handoff failed: project load lock is already held. Got: {str(path)!r:.100}"
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")


def _release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


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
    raise LoadTransactionError(
        "load-handoff failed: unsupported storage location. "
        f"Got: {candidate.storage_location!r:.100}"
    )


def _write_transaction(
    path: Path,
    *,
    transaction_id: str,
    status: str,
    candidate: HandoffCandidate,
    archive_path: Path | None,
    state_path: Path | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "transaction_id": transaction_id,
        "operation": "load",
        "status": status,
        "source_path": str(candidate.path),
        "storage_location": candidate.storage_location,
        "source_git_visibility": candidate.source_git_visibility,
        "source_fs_status": candidate.source_fs_status,
        "source_content_sha256": candidate.content_sha256,
        "archive_path": str(archive_path) if archive_path is not None else None,
        "state_path": str(state_path) if state_path is not None else None,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)
