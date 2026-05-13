"""Active handoff writer reservation primitives."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from scripts.storage_authority import get_storage_layout
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.storage_authority import get_storage_layout  # type: ignore[no-redef]


class ActiveWriteError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActiveWriteReservation:
    schema_version: int
    project: str
    operation: str
    run_id: str
    transaction_id: str
    transaction_path: Path
    idempotency_key: str
    allocated_active_path: Path
    state_snapshot_id: str
    state_snapshot_hash: str
    state_snapshot_paths: list[str]
    resumed_from_path: str | None
    resumed_from_hash: str | None
    bound_slug: str
    slug_source: str
    operation_state_path: Path
    lease_id: str
    lease_acquired_at: str
    lease_expires_at: str
    transaction_watermark: str
    status: str
    created_at: str
    updated_at: str

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the reservation."""
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "operation": self.operation,
            "run_id": self.run_id,
            "transaction_id": self.transaction_id,
            "transaction_path": str(self.transaction_path),
            "idempotency_key": self.idempotency_key,
            "allocated_active_path": str(self.allocated_active_path),
            "state_snapshot_id": self.state_snapshot_id,
            "state_snapshot_hash": self.state_snapshot_hash,
            "state_snapshot_paths": self.state_snapshot_paths,
            "resumed_from_path": self.resumed_from_path,
            "resumed_from_hash": self.resumed_from_hash,
            "bound_slug": self.bound_slug,
            "slug_source": self.slug_source,
            "operation_state_path": str(self.operation_state_path),
            "lease_id": self.lease_id,
            "lease_acquired_at": self.lease_acquired_at,
            "lease_expires_at": self.lease_expires_at,
            "transaction_watermark": self.transaction_watermark,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def begin_active_write(
    project_root: Path,
    *,
    project_name: str | None,
    operation: str,
    slug: str,
    run_id: str | None = None,
    created_at: str | None = None,
    lease_seconds: int = 1800,
) -> ActiveWriteReservation:
    """Reserve an active handoff write before final content generation."""
    if operation not in {"save", "summary", "quicksave"}:
        raise ActiveWriteError(
            f"begin-active-write failed: unsupported operation. Got: {operation!r:.100}"
        )
    if not slug:
        raise ActiveWriteError("begin-active-write failed: slug must be non-empty. Got: ''")

    layout = get_storage_layout(project_root)
    project = project_name or layout.project_root.name
    transaction_id = uuid.uuid4().hex
    lock_path = layout.primary_state_dir / "locks" / "active-write.lock"
    _acquire_lock(lock_path, project=project, operation=operation, transaction_id=transaction_id)
    try:
        (
            state_snapshot_id,
            state_snapshot_hash,
            state_snapshot_paths,
            resumed_path,
            resumed_hash,
        ) = _state_snapshot(
            layout.primary_state_dir,
            project,
        )
        transaction_watermark = _transaction_watermark(layout.primary_state_dir)
        timestamp = _parse_created_at(created_at)
        active_path = _allocate_active_path(layout.primary_active_dir, slug, timestamp)
        active_run_id = run_id or uuid.uuid4().hex
        lease_id = uuid.uuid4().hex
        now = datetime.now(UTC)
        acquired_at = now.isoformat()
        expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
        transaction_path = (
            layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
        )
        operation_state_path = (
            layout.primary_state_dir
            / "active-writes"
            / project
            / f"{active_run_id}.json"
        )
        idempotency_key = _stable_hash([
            project,
            operation,
            active_run_id,
            state_snapshot_hash,
            resumed_path or "",
            resumed_hash or "",
            slug,
            str(active_path),
        ])
        reservation = ActiveWriteReservation(
            schema_version=1,
            project=project,
            operation=operation,
            run_id=active_run_id,
            transaction_id=transaction_id,
            transaction_path=transaction_path,
            idempotency_key=idempotency_key,
            allocated_active_path=active_path,
            state_snapshot_id=state_snapshot_id,
            state_snapshot_hash=state_snapshot_hash,
            state_snapshot_paths=state_snapshot_paths,
            resumed_from_path=resumed_path,
            resumed_from_hash=resumed_hash,
            bound_slug=slug,
            slug_source="caller",
            operation_state_path=operation_state_path,
            lease_id=lease_id,
            lease_acquired_at=acquired_at,
            lease_expires_at=expires_at,
            transaction_watermark=transaction_watermark,
            status="begun",
            created_at=acquired_at,
            updated_at=acquired_at,
        )
        _write_json_atomic(operation_state_path, reservation.to_payload())
        _write_json_atomic(
            transaction_path,
            {
                **reservation.to_payload(),
                "status": "pending_before_write",
            },
        )
        return reservation
    finally:
        _release_lock(lock_path)


def write_active_handoff(
    project_root: Path,
    *,
    operation_state_path: Path,
    content: str,
    content_sha256: str,
) -> dict[str, object]:
    """Write reserved active handoff content and mark the transaction committed."""
    layout = get_storage_layout(project_root)
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    project = str(state.get("project", layout.project_root.name))
    operation = str(state.get("operation", ""))
    transaction_id = str(state.get("transaction_id", ""))
    lock_path = layout.primary_state_dir / "locks" / "active-write.lock"
    _acquire_lock(lock_path, project=project, operation=operation, transaction_id=transaction_id)
    try:
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if expected_hash != content_sha256:
            raise ActiveWriteError(
                "write-active-handoff failed: content hash mismatch. "
                f"Got: {content_sha256!r:.100}"
            )
        active_path = Path(str(state["allocated_active_path"]))
        if active_path.exists():
            existing_hash = _sha256_path(active_path)
            if existing_hash != content_sha256:
                if state.get("status") != "committed":
                    state["status"] = "content_mismatch"
                    state["updated_at"] = datetime.now(UTC).isoformat()
                    _write_json_atomic(operation_state_path, state)
                raise ActiveWriteError(
                    "write-active-handoff failed: active output content mismatch. "
                    f"Got: {str(active_path)!r:.100}"
                )
        else:
            active_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = active_path.with_name(f".{active_path.name}.{uuid.uuid4().hex}.tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_hash = _sha256_path(temp_path)
            if temp_hash != content_sha256:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
                raise ActiveWriteError(
                    "write-active-handoff failed: written content hash mismatch. "
                    f"Got: {str(temp_path)!r:.100}"
                )
            os.replace(temp_path, active_path)
        updated_at = datetime.now(UTC).isoformat()
        cleanup_action, cleanup_path = _clear_snapshotted_primary_state(state)
        state.update({
            "status": "committed",
            "active_path": str(active_path),
            "content_hash": content_sha256,
            "output_sha256": content_sha256,
            "state_cleanup_action": cleanup_action,
            "state_cleanup_path": cleanup_path,
            "updated_at": updated_at,
        })
        _write_json_atomic(operation_state_path, state)
        transaction_path = Path(str(state["transaction_path"]))
        transaction = {
            **state,
            "status": "completed",
            "active_path": str(active_path),
        }
        _write_json_atomic(transaction_path, transaction)
        return transaction
    finally:
        _release_lock(lock_path)


def list_active_writes(
    project_root: Path,
    *,
    project_name: str,
    operation: str | None = None,
) -> list[dict[str, object]]:
    """Return persisted active-write operation-state records without mutation."""
    layout = get_storage_layout(project_root)
    active_writes_dir = layout.primary_state_dir / "active-writes" / project_name
    if not active_writes_dir.exists():
        return []
    records: list[dict[str, object]] = []
    for path in sorted(active_writes_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if operation is not None and record.get("operation") != operation:
            continue
        records.append(record)
    return records


def abandon_active_write(
    project_root: Path,
    *,
    operation_state_path: Path,
    reason: str,
) -> dict[str, object]:
    """Mark one active-write operation abandoned without deleting active output."""
    layout = get_storage_layout(project_root)
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    project = str(state.get("project", layout.project_root.name))
    operation = str(state.get("operation", ""))
    transaction_id = str(state.get("transaction_id", ""))
    lock_path = layout.primary_state_dir / "locks" / "active-write.lock"
    _acquire_lock(lock_path, project=project, operation=operation, transaction_id=transaction_id)
    try:
        updated_at = datetime.now(UTC).isoformat()
        active_path = Path(str(state.get("active_path") or state["allocated_active_path"]))
        state.update({
            "status": "abandoned",
            "active_path": str(active_path),
            "active_path_exists": active_path.exists(),
            "active_path_sha256": _sha256_path(active_path) if active_path.exists() else None,
            "abandon_reason": reason,
            "updated_at": updated_at,
        })
        _write_json_atomic(operation_state_path, state)
        transaction_path = Path(str(state["transaction_path"]))
        transaction = {
            **state,
            "status": "abandoned",
        }
        _write_json_atomic(transaction_path, transaction)
        return transaction
    finally:
        _release_lock(lock_path)


def recover_active_write_transaction(
    project_root: Path,
    *,
    operation_state_path: Path,
) -> dict[str, object]:
    """Recover a verifiable active-write transaction without regenerating content."""
    layout = get_storage_layout(project_root)
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    project = str(state.get("project", layout.project_root.name))
    operation = str(state.get("operation", ""))
    transaction_id = str(state.get("transaction_id", ""))
    lock_path = layout.primary_state_dir / "locks" / "active-write.lock"
    _acquire_lock(lock_path, project=project, operation=operation, transaction_id=transaction_id)
    try:
        if state.get("status") == "committed":
            return state
        if state.get("status") == "abandoned":
            return state
        active_path = Path(str(state.get("active_path") or state["allocated_active_path"]))
        content_hash = str(state.get("content_hash") or state.get("output_sha256") or "")
        if not content_hash:
            return state
        if not active_path.exists():
            state["status"] = "pending_before_write"
            state["updated_at"] = datetime.now(UTC).isoformat()
            _write_json_atomic(operation_state_path, state)
            return state
        if _sha256_path(active_path) != content_hash:
            state["status"] = "content_mismatch"
            state["updated_at"] = datetime.now(UTC).isoformat()
            _write_json_atomic(operation_state_path, state)
            raise ActiveWriteError(
                "active-write-transaction-recover failed: active output content mismatch. "
                f"Got: {str(active_path)!r:.100}"
            )
        updated_at = datetime.now(UTC).isoformat()
        cleanup_action, cleanup_path = _clear_snapshotted_primary_state(state)
        state.update({
            "status": "committed",
            "active_path": str(active_path),
            "content_hash": content_hash,
            "output_sha256": content_hash,
            "state_cleanup_action": cleanup_action,
            "state_cleanup_path": cleanup_path,
            "updated_at": updated_at,
        })
        _write_json_atomic(operation_state_path, state)
        transaction_path = Path(str(state["transaction_path"]))
        transaction = {
            **state,
            "status": "completed",
            "active_path": str(active_path),
        }
        _write_json_atomic(transaction_path, transaction)
        return state
    finally:
        _release_lock(lock_path)


def _allocate_active_path(active_dir: Path, slug: str, created_at: datetime) -> Path:
    active_dir.mkdir(parents=True, exist_ok=True)
    prefix = created_at.strftime("%Y-%m-%d_%H-%M")
    candidate = active_dir / f"{prefix}_{slug}.md"
    if not candidate.exists():
        return candidate
    for index in range(1, 100):
        candidate = active_dir / f"{prefix}_{slug}-{index:02d}.md"
        if not candidate.exists():
            return candidate
    raise ActiveWriteError(
        f"allocate-active-path failed: collision budget exhausted. Got: {slug!r:.100}"
    )


def _state_snapshot(
    state_dir: Path,
    project: str,
) -> tuple[str, str, list[str], str | None, str | None]:
    states = sorted(state_dir.glob(f"handoff-{project}-*.json"))
    if not states:
        return "no-state", _stable_hash(["no-state"]), [], None, None
    payload_parts: list[str] = []
    state_paths: list[str] = []
    resumed_path: str | None = None
    for path in states:
        data = path.read_text(encoding="utf-8")
        payload_parts.extend([path.name, data])
        state_paths.append(str(path))
        if resumed_path is None:
            try:
                resumed_path = str(json.loads(data).get("archive_path", ""))
            except json.JSONDecodeError:
                resumed_path = None
    resumed_hash = _sha256_path(Path(resumed_path)) if resumed_path else None
    return "primary-state", _stable_hash(payload_parts), state_paths, resumed_path, resumed_hash


def _clear_snapshotted_primary_state(state: dict[str, object]) -> tuple[str, str | None]:
    paths = [Path(str(path)) for path in state.get("state_snapshot_paths", [])]
    if not paths:
        return "none", None
    if len(paths) > 1:
        raise ActiveWriteError(
            f"write-active-handoff failed: ambiguous state cleanup. Got: {len(paths)!r:.100}"
        )
    path = paths[0]
    if not path.exists():
        return "already-cleared-primary-state", str(path)
    try:
        subprocess.run(["trash", str(path)], capture_output=True, text=True, timeout=5, check=True)
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as exc:
        raise ActiveWriteError(
            "write-active-handoff failed: state cleanup failed. "
            f"Got: {str(path)!r:.100}"
        ) from exc
    return "cleared-primary-state", str(path)


def _transaction_watermark(state_dir: Path) -> str:
    transactions_dir = state_dir / "transactions"
    if not transactions_dir.exists():
        return _stable_hash(["no-transactions"])
    parts: list[str] = []
    for path in sorted(transactions_dir.glob("*.json")):
        parts.extend([path.name, path.read_text(encoding="utf-8")])
    return _stable_hash(parts or ["no-transactions"])


def _parse_created_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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
        raise ActiveWriteError(
            "begin-active-write failed: project active-write lock is already held. "
            f"Got: {str(path)!r:.100}"
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


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _stable_hash(parts: list[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _sha256_path(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
