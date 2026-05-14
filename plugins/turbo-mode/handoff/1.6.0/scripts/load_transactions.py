"""Mutating load transaction primitives for Handoff storage."""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import uuid
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.session_state import allocate_archive_path, write_resume_state
    from scripts.storage_authority import (
        HandoffCandidate,
        SelectionEligibility,
        StorageLocation,
        discover_handoff_inventory,
        eligible_active_candidates,
        get_storage_layout,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.session_state import (  # type: ignore[no-redef]
        allocate_archive_path,
        write_resume_state,
    )
    from scripts.storage_authority import (  # type: ignore[no-redef]
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
        recovered = _recover_pending_load(layout, project=project)
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
        archive_path = _copy_legacy_archive(layout, candidate)
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
    if candidate.storage_location in {
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }:
        _record_copied_legacy_archive(
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
        except (OSError, json.JSONDecodeError) as exc:
            records.append({
                "transaction_path": str(path),
                "status": "unreadable",
                "operation": "load",
                "error": f"pending transaction record unreadable: {path}",
            })
            continue
        if data.get("operation") == "load" and data.get("status") == "pending":
            records.append(data)
    return records


def _load_result_payload(result: LoadResult) -> dict[str, object]:
    return {
        "transaction_id": result.transaction_id,
        "transaction_path": result.transaction_path,
        "source_path": str(result.source_path),
        "archive_path": str(result.archive_path),
        "state_path": str(result.state_path),
        "storage_location": result.storage_location,
    }


def _emit(payload: dict[str, object], field: str | None) -> int:
    if field is None:
        json.dump(payload, sys.stdout, indent=2)
        print()
        return 0
    value = payload.get(field)
    if value is None:
        return 1
    print(value)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Run handoff load transactions")
    subparsers = parser.add_subparsers(dest="command", required=True)

    load_parser = subparsers.add_parser("load")
    load_parser.add_argument("--project-root", type=Path, required=True)
    load_parser.add_argument("--project", default=None)
    load_parser.add_argument("--explicit-path", type=Path, default=None)
    load_parser.add_argument("--resume-token", default=None)
    load_parser.add_argument(
        "--field",
        choices=(
            "transaction_id",
            "transaction_path",
            "source_path",
            "archive_path",
            "state_path",
            "storage_location",
        ),
        default=None,
    )

    args = parser.parse_args(argv)
    if args.command == "load":
        try:
            result = load_handoff(
                args.project_root.resolve(),
                project_name=args.project,
                explicit_path=args.explicit_path,
                resume_token=args.resume_token,
            )
        except LoadTransactionError as exc:
            print(exc, file=sys.stderr)
            return 1
        return _emit(_load_result_payload(result), args.field)
    return 1


def _recover_pending_load(layout, *, project: str) -> LoadResult | None:
    transactions_dir = layout.primary_state_dir / "transactions"
    if not transactions_dir.exists():
        return None
    for transaction_path in sorted(transactions_dir.glob("*.json")):
        try:
            record = json.loads(transaction_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LoadTransactionError(
                "load-handoff failed: pending transaction record unreadable; manual operator review required. "
                f"Got: {str(transaction_path)!r:.100}"
            ) from exc
        if record.get("operation") != "load" or record.get("status") != "pending":
            continue
        if record.get("project") != project:
            continue
        if record.get("storage_location") not in {
            StorageLocation.PRIMARY_ACTIVE,
            StorageLocation.PRIMARY_ARCHIVE,
            StorageLocation.LEGACY_ACTIVE,
            StorageLocation.LEGACY_ARCHIVE,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        }:
            continue
        recovered = _recover_load_transaction(layout, transaction_path, record)
        if recovered is not None:
            return recovered
    return None


def _recover_load_transaction(
    layout,
    transaction_path: Path,
    record: dict[str, object],
) -> LoadResult | None:
    transaction_id = str(record.get("transaction_id", ""))
    source_path = Path(str(record.get("source_path", "")))
    project = str(record.get("project", ""))
    resume_token = str(record.get("resume_token", ""))
    state_path_value = str(record.get("state_path") or "")
    if not transaction_id or not project or not resume_token or not state_path_value:
        raise LoadTransactionError(
            "load-handoff failed: pending transaction lacks recovery metadata. "
            f"Got: {str(transaction_path)!r:.100}"
        )
    state_path = Path(state_path_value)
    archive_path = _resolve_pending_archive_path(layout, transaction_path, record)
    if archive_path is None:
        return None
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
    storage_location = StorageLocation(str(record.get("storage_location", "")))
    if storage_location == StorageLocation.LEGACY_ACTIVE:
        _recover_consumed_legacy_active(layout, record, archive_path=archive_path)
    if storage_location in {
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }:
        _recover_copied_legacy_archive(layout, record, archive_path=archive_path)
    record["status"] = "completed"
    record["archive_path"] = str(archive_path)
    record["state_path"] = str(state_path)
    record["updated_at"] = datetime.now(UTC).isoformat()
    _write_json_atomic(transaction_path, record)
    return LoadResult(
        transaction_id=transaction_id,
        transaction_path=str(transaction_path),
        source_path=source_path,
        archive_path=archive_path,
        state_path=state_path,
        storage_location=storage_location,
    )


def _resolve_pending_archive_path(
    layout,
    transaction_path: Path,
    record: dict[str, object],
) -> Path | None:
    storage_location = StorageLocation(str(record.get("storage_location", "")))
    source_path = Path(str(record.get("source_path", "")))
    source_hash = str(record.get("source_content_sha256") or "")
    archive_value = record.get("archive_path")
    if archive_value:
        archive_path = Path(str(archive_value))
        if not archive_path.exists():
            raise LoadTransactionError(
                "load-handoff failed: pending transaction archive is missing. "
                f"Got: {str(archive_path)!r:.100}"
            )
        if storage_location == StorageLocation.PRIMARY_ACTIVE and source_hash:
            if _sha256_file(archive_path) != source_hash:
                raise LoadTransactionError(
                    "load-handoff failed: pending primary active archive hash mismatch. "
                    f"Got: {str(archive_path)!r:.100}"
                )
        return archive_path
    if storage_location == StorageLocation.PRIMARY_ARCHIVE:
        if source_path.exists():
            record["archive_path"] = str(source_path)
            record["updated_at"] = datetime.now(UTC).isoformat()
            _write_json_atomic(transaction_path, record)
            return source_path
        raise LoadTransactionError(
            "load-handoff failed: pending primary archive source is missing. "
            f"Got: {str(source_path)!r:.100}"
        )
    if storage_location == StorageLocation.PRIMARY_ACTIVE:
        if source_path.exists():
            _abandon_pending_load_for_retry(
                transaction_path,
                record,
                retry_reason="primary-active-replace-not-started",
            )
            return None
        return _adopt_primary_active_archive_by_hash(layout, transaction_path, record)
    if storage_location == StorageLocation.LEGACY_ACTIVE:
        archive_path = _registry_archive_for_pending_legacy_active(layout, record)
        if archive_path is None:
            _abandon_pending_load_for_retry(
                transaction_path,
                record,
                retry_reason="legacy-active-copy-not-recorded",
            )
            return None
        return archive_path
    if storage_location in {
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }:
        archive_path = _registry_archive_for_pending_legacy_archive(layout, record)
        if archive_path is None:
            _abandon_pending_load_for_retry(
                transaction_path,
                record,
                retry_reason="legacy-archive-copy-not-recorded",
            )
            return None
        return archive_path
    raise LoadTransactionError(
        "load-handoff failed: unsupported pending transaction storage location. "
        f"Got: {storage_location!r:.100}"
    )


def _adopt_primary_active_archive_by_hash(
    layout,
    transaction_path: Path,
    record: dict[str, object],
) -> Path:
    source_hash = str(record.get("source_content_sha256") or "")
    if not source_hash:
        raise LoadTransactionError(
            "load-handoff failed: pending primary active transaction lacks source hash. "
            f"Got: {str(transaction_path)!r:.100}"
        )
    if not layout.primary_archive_dir.exists():
        raise LoadTransactionError(
            "load-handoff failed: pending primary active archive is unrecoverable; "
            "source was moved but no archive directory exists. "
            f"Got: {str(transaction_path)!r:.100}"
        )
    matches = [
        path
        for path in sorted(layout.primary_archive_dir.glob("*.md"))
        if path.is_file() and _sha256_file(path) == source_hash
    ]
    if len(matches) == 1:
        archive_path = matches[0]
        record["archive_path"] = str(archive_path)
        record["updated_at"] = datetime.now(UTC).isoformat()
        _write_json_atomic(transaction_path, record)
        return archive_path
    if not matches:
        raise LoadTransactionError(
            "load-handoff failed: pending primary active archive is unrecoverable; "
            "source was moved but no archive matched recorded source hash. "
            f"Got: {str(transaction_path)!r:.100}"
        )
    raise LoadTransactionError(
        "load-handoff failed: pending primary active archive is ambiguous. "
        f"Got: {[str(path) for path in matches]!r:.1000}"
    )


def _abandon_pending_load_for_retry(
    transaction_path: Path,
    record: dict[str, object],
    *,
    retry_reason: str,
) -> None:
    now = datetime.now(UTC).isoformat()
    record["status"] = "abandoned"
    record["retry_reason"] = retry_reason
    record["abandoned_by"] = "load-recovery"
    record["abandoned_at"] = now
    record["updated_at"] = now
    _write_json_atomic(transaction_path, record)


def _registry_archive_for_pending_legacy_active(
    layout,
    record: dict[str, object],
) -> Path | None:
    return _lookup_pending_legacy_archive(
        layout,
        record,
        registry_path=layout.primary_state_dir / "consumed-legacy-active.json",
        source_root_value="project_root",
    )


def _registry_archive_for_pending_legacy_archive(
    layout,
    record: dict[str, object],
) -> Path | None:
    return _lookup_pending_legacy_archive(
        layout,
        record,
        registry_path=layout.primary_state_dir / "copied-legacy-archives.json",
        source_root_value=str(layout.project_root),
    )


def _lookup_pending_legacy_archive(
    layout,
    record: dict[str, object],
    *,
    registry_path: Path,
    source_root_value: str,
) -> Path | None:
    if not registry_path.exists():
        return None
    source_path = Path(str(record.get("source_path", "")))
    source_hash = str(record.get("source_content_sha256") or "")
    if not source_hash:
        return None
    try:
        relative = source_path.relative_to(layout.project_root).as_posix()
    except ValueError:
        return None
    registry = _read_registry(registry_path)
    target_key = {
        "source_root": source_root_value,
        "project_relative_source_path": relative,
        "storage_location": str(record.get("storage_location", "")),
        "source_content_sha256": source_hash,
    }
    for entry in registry["entries"]:
        if _registry_key(entry) != target_key:
            continue
        archive_path = Path(str(entry.get("copied_primary_archive_path", "")))
        if not archive_path.exists():
            return None
        if _sha256_file(archive_path) != source_hash:
            return None
        return archive_path
    return None


def _recover_consumed_legacy_active(
    layout,
    record: dict[str, object],
    *,
    archive_path: Path,
) -> None:
    source_path = Path(str(record.get("source_path", "")))
    source_hash = str(record.get("source_content_sha256", ""))
    copied_hash = _sha256_file(archive_path)
    if copied_hash != source_hash:
        raise LoadTransactionError(
            "load-handoff failed: recovered legacy active archive hash mismatch. "
            f"Got: {str(archive_path)!r:.100}"
        )
    registry_path = layout.primary_state_dir / "consumed-legacy-active.json"
    registry = _read_registry(registry_path)
    key = {
        "source_root": "project_root",
        "project_relative_source_path": source_path.relative_to(layout.project_root).as_posix(),
        "storage_location": StorageLocation.LEGACY_ACTIVE,
        "source_content_sha256": source_hash,
    }
    for entry in registry["entries"]:
        if _registry_key(entry) != key:
            continue
        if (
            Path(str(entry["copied_primary_archive_path"])).exists()
            and str(entry["copied_primary_archive_path"]) == str(archive_path)
            and str(entry.get("copied_content_sha256", "")) == copied_hash
        ):
            return
        raise LoadTransactionError(
            "load-handoff failed: consumed legacy active registry entry is stale. "
            f"Got: {entry.get('copied_primary_archive_path')!r:.100}"
        )
    registry["entries"].append({
        **key,
        "source_absolute_path": str(source_path),
        "source_resolved_path": str(source_path.resolve()),
        "copied_primary_archive_path": str(archive_path),
        "copied_content_sha256": copied_hash,
        "operation": "legacy-load",
        "transaction_id": str(record.get("transaction_id", "")),
        "consumed_at": datetime.now(UTC).isoformat(),
    })
    _write_json_atomic(registry_path, registry)


def _recover_copied_legacy_archive(
    layout,
    record: dict[str, object],
    *,
    archive_path: Path,
) -> None:
    source_path = Path(str(record.get("source_path", "")))
    source_hash = str(record.get("source_content_sha256", ""))
    copied_hash = _sha256_file(archive_path)
    if copied_hash != source_hash:
        raise LoadTransactionError(
            "load-handoff failed: recovered legacy archive hash mismatch. "
            f"Got: {str(archive_path)!r:.100}"
        )
    storage_location = StorageLocation(str(record.get("storage_location", "")))
    registry_path = layout.primary_state_dir / "copied-legacy-archives.json"
    registry = _read_registry(registry_path)
    key = {
        "source_root": str(layout.project_root),
        "project_relative_source_path": source_path.relative_to(layout.project_root).as_posix(),
        "storage_location": storage_location,
        "source_content_sha256": source_hash,
    }
    for entry in registry["entries"]:
        if _registry_key(entry) != key:
            continue
        if (
            Path(str(entry["copied_primary_archive_path"])).exists()
            and str(entry["copied_primary_archive_path"]) == str(archive_path)
            and str(entry.get("copied_content_sha256", "")) == copied_hash
        ):
            return
        raise LoadTransactionError(
            "load-handoff failed: copied legacy archive registry entry is stale. "
            f"Got: {entry.get('copied_primary_archive_path')!r:.100}"
        )
    registry["entries"].append({
        **key,
        "source_absolute_path": str(source_path),
        "copied_primary_archive_path": str(archive_path),
        "copied_content_sha256": copied_hash,
        "operation": "legacy-archive-load",
        "transaction_id": str(record.get("transaction_id", "")),
        "copied_at": datetime.now(UTC).isoformat(),
    })
    _write_json_atomic(registry_path, registry)


def _parse_created_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


_CLAIM_TIMEOUT_SECONDS = 60


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


def _try_recover_stale_lock(path: Path, *, now: datetime) -> bool:
    claim_path = path.with_name(path.name + ".recovery")
    try:
        claim_fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        claim_age_hint = ""
        try:
            claim_payload = json.loads(claim_path.read_text(encoding="utf-8"))
            if isinstance(claim_payload, dict):
                c_pid = claim_payload.get("pid")
                c_host = claim_payload.get("hostname")
                c_created = claim_payload.get("created_at")
                c_timeout = claim_payload.get("timeout_seconds")
                if isinstance(c_created, str):
                    try:
                        age = (now - _parse_created_at(c_created)).total_seconds()
                        if isinstance(c_timeout, (int, float)) and age > c_timeout:
                            claim_age_hint = f" (likely stale: pid={c_pid!r} host={c_host!r} age={age:.0f}s)"
                        else:
                            claim_age_hint = f" (live recoverer: pid={c_pid!r} host={c_host!r})"
                    except ValueError:
                        pass
        except (OSError, json.JSONDecodeError, ValueError):
            claim_age_hint = " (claim metadata unreadable)"
        raise LoadTransactionError(
            f"load-handoff failed: recovery claim file present{claim_age_hint}; "
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
            raise LoadTransactionError(
                "load-handoff failed: lock metadata unreadable; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            ) from exc
        if not isinstance(payload, dict):
            raise LoadTransactionError(
                "load-handoff failed: lock metadata malformed; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            )
        created_at = payload.get("created_at")
        timeout = payload.get("timeout_seconds")
        hostname = payload.get("hostname")
        if not isinstance(created_at, str) or not isinstance(timeout, (int, float)) or not isinstance(hostname, str):
            raise LoadTransactionError(
                "load-handoff failed: lock metadata malformed; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            )
        try:
            created = _parse_created_at(created_at)
        except ValueError as exc:
            raise LoadTransactionError(
                "load-handoff failed: lock metadata malformed; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            ) from exc
        if (now - created).total_seconds() <= timeout:
            return False
        if hostname != socket.gethostname():
            raise LoadTransactionError(
                "load-handoff failed: stale lock from another host; manual operator review required. "
                f"Got: {(hostname, str(path))!r:.100}"
            )
        os.unlink(path)
        return True
    finally:
        try:
            os.unlink(claim_path)
        except FileNotFoundError:
            pass


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
    except FileExistsError:
        if _try_recover_stale_lock(path, now=datetime.now(UTC)):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc2:
                raise LoadTransactionError(
                    f"load-handoff failed: project load lock is already held. Got: {str(path)!r:.100}"
                ) from exc2
        else:
            raise LoadTransactionError(
                f"load-handoff failed: project load lock is already held. Got: {str(path)!r:.100}"
            )
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
    lock_check = json.loads(path.read_text(encoding="utf-8"))
    if lock_check.get("lock_id") != transaction_id:
        raise LoadTransactionError(
            f"load-handoff failed: project load lock is already held. Got: {str(path)!r:.100}"
        )


def _release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    for directory in (path.parent,):
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
    _copy_to_archive_atomic(
        candidate.path,
        archive_path,
        expected_hash=candidate.content_sha256,
    )
    return archive_path


def _record_copied_legacy_archive(
    layout,
    candidate: HandoffCandidate,
    *,
    copied_archive_path: Path,
    transaction_id: str,
) -> None:
    registry_path = layout.primary_state_dir / "copied-legacy-archives.json"
    registry = _read_registry(registry_path)
    key = _legacy_archive_key(layout.project_root, candidate)
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
            "load-handoff failed: copied legacy archive registry entry is stale. "
            f"Got: {entry.get('copied_primary_archive_path')!r:.100}"
        )
    registry["entries"].append({
        **key,
        "source_absolute_path": str(candidate.path),
        "copied_primary_archive_path": str(copied_archive_path),
        "copied_content_sha256": copied_hash,
        "operation": "legacy-archive-load",
        "transaction_id": transaction_id,
        "copied_at": datetime.now(UTC).isoformat(),
    })
    _write_json_atomic(registry_path, registry)


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


if __name__ == "__main__":
    raise SystemExit(main())
