"""Active handoff writer reservation primitives."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from scripts.storage_authority import (
        ChainStateDiagnosticError,
        continue_chain_state,
        get_storage_layout,
        read_chain_state,
    )
    from scripts.storage_primitives import (
        LockPolicy,
        acquire_lock as _acquire_lock_with_policy,
        parse_created_at as _parse_created_at,
        release_lock as _release_lock,
        sha256_file_or_none as _sha256_path,
        write_json_atomic as _write_json_atomic,
    )
except ModuleNotFoundError:
    import types

    _script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(_script_dir.parent))
    scripts_pkg = sys.modules.get("scripts")
    if scripts_pkg is None or not hasattr(scripts_pkg, "__path__"):
        scripts_pkg = types.ModuleType("scripts")
        scripts_pkg.__path__ = [str(_script_dir)]  # type: ignore[attr-defined]
        sys.modules["scripts"] = scripts_pkg
    else:
        package_path = list(scripts_pkg.__path__)  # type: ignore[attr-defined]
        if str(_script_dir) not in package_path:
            package_path.insert(0, str(_script_dir))
            scripts_pkg.__path__ = package_path  # type: ignore[attr-defined]

    from scripts.storage_authority import (  # type: ignore[no-redef]
        ChainStateDiagnosticError,
        continue_chain_state,
        get_storage_layout,
        read_chain_state,
    )
    from scripts.storage_primitives import (  # type: ignore[no-redef]
        LockPolicy,
        acquire_lock as _acquire_lock_with_policy,
        parse_created_at as _parse_created_at,
        release_lock as _release_lock,
        sha256_file_or_none as _sha256_path,
        write_json_atomic as _write_json_atomic,
    )


class ActiveWriteError(RuntimeError):
    pass


DEFAULT_SLUGS = {
    "save": "handoff",
    "summary": "summary",
    "quicksave": "checkpoint",
}


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
    recovery_commands: dict[str, object]
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
            "recovery_commands": self.recovery_commands,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def begin_active_write(
    project_root: Path,
    *,
    project_name: str | None,
    operation: str,
    slug: str | None = None,
    run_id: str | None = None,
    created_at: str | None = None,
    lease_seconds: int = 1800,
) -> ActiveWriteReservation:
    """Reserve an active handoff write before final content generation."""
    if operation not in {"save", "summary", "quicksave"}:
        raise ActiveWriteError(
            f"begin-active-write failed: unsupported operation. Got: {operation!r:.100}"
        )
    bound_slug, slug_source = _bind_slug(operation, slug)

    layout = get_storage_layout(project_root)
    project = project_name or layout.project_root.name
    active_run_id = run_id or uuid.uuid4().hex
    operation_state_path = (
        layout.primary_state_dir
        / "active-writes"
        / project
        / f"{active_run_id}.json"
    )
    if run_id is not None and operation_state_path.exists():
        return _existing_reservation(
            operation_state_path,
            operation=operation,
            slug=slug,
        )
    transaction_id = uuid.uuid4().hex
    lock_path = layout.primary_state_dir / "locks" / "active-write.lock"
    _acquire_lock(lock_path, project=project, operation=operation, transaction_id=transaction_id)
    try:
        _continue_legacy_chain_state_if_unambiguous(layout.project_root, project=project)
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
        now = datetime.now(UTC)
        _ensure_no_compatible_reservation(
            layout.primary_state_dir,
            project=project,
            operation=operation,
            state_snapshot_hash=state_snapshot_hash,
        )
        transaction_watermark = _transaction_watermark(layout.primary_state_dir)
        timestamp = _parse_created_at(created_at)
        active_path = _allocate_active_path(
            layout.project_root,
            layout.primary_active_dir,
            operation,
            bound_slug,
            timestamp,
        )
        lease_id = uuid.uuid4().hex
        acquired_at = now.isoformat()
        expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
        transaction_path = (
            layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
        )
        idempotency_key = _stable_hash([
            project,
            operation,
            active_run_id,
            state_snapshot_hash,
            resumed_path or "",
            resumed_hash or "",
            bound_slug,
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
            bound_slug=bound_slug,
            slug_source=slug_source,
            operation_state_path=operation_state_path,
            lease_id=lease_id,
            lease_acquired_at=acquired_at,
            lease_expires_at=expires_at,
            transaction_watermark=transaction_watermark,
            recovery_commands=_recovery_commands(layout.project_root, operation_state_path),
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


def _continue_legacy_chain_state_if_unambiguous(project_root: Path, *, project: str) -> None:
    try:
        chain_state = read_chain_state(project_root, project_name=project)
    except ChainStateDiagnosticError as exc:
        raise _chain_state_active_write_error(exc) from exc
    if chain_state.get("status") != "legacy-bridge-required":
        return
    candidate = chain_state.get("state")
    if not isinstance(candidate, dict):
        raise ActiveWriteError(
            "begin-active-write failed: legacy chain-state candidate was invalid. Got: None"
        )
    try:
        continue_chain_state(
            project_root,
            project_name=project,
            state_path=str(candidate["project_relative_state_path"]),
            expected_payload_sha256=str(candidate["payload_sha256"]),
        )
    except ChainStateDiagnosticError as exc:
        raise _chain_state_active_write_error(exc) from exc


def _chain_state_active_write_error(exc: ChainStateDiagnosticError) -> ActiveWriteError:
    error = exc.payload.get("error", {})
    code = error.get("code") if isinstance(error, dict) else "unknown"
    return ActiveWriteError(
        "begin-active-write failed: chain-state recovery required. "
        f"Got: {code!r:.100}"
    )


def _existing_reservation(
    operation_state_path: Path,
    *,
    operation: str,
    slug: str | None,
) -> ActiveWriteReservation:
    payload = json.loads(operation_state_path.read_text(encoding="utf-8"))
    if payload.get("operation") != operation:
        raise ActiveWriteError(
            "begin-active-write failed: run id belongs to another operation. "
            f"Got: {payload.get('operation')!r:.100}"
        )
    if slug is not None and payload.get("bound_slug") != slug:
        raise ActiveWriteError(
            "begin-active-write failed: run id is already bound to another slug. "
            f"Got: {payload.get('bound_slug')!r:.100}"
        )
    return _reservation_from_payload(payload)


def _bind_slug(operation: str, slug: str | None) -> tuple[str, str]:
    if slug is None:
        return DEFAULT_SLUGS[operation], "helper-default"
    if not slug:
        raise ActiveWriteError("begin-active-write failed: slug must be non-empty. Got: ''")
    _ensure_slug_segment("begin-active-write", slug)
    return slug, "caller-predeclared"


def _ensure_slug_segment(operation: str, slug: str) -> None:
    if "/" in slug or "\\" in slug or slug in {".", ".."}:
        raise ActiveWriteError(
            f"{operation} failed: slug must be a filename segment. Got: {slug!r:.100}"
        )


def _reservation_from_payload(payload: dict[str, object]) -> ActiveWriteReservation:
    return ActiveWriteReservation(
        schema_version=int(payload["schema_version"]),
        project=str(payload["project"]),
        operation=str(payload["operation"]),
        run_id=str(payload["run_id"]),
        transaction_id=str(payload["transaction_id"]),
        transaction_path=Path(str(payload["transaction_path"])),
        idempotency_key=str(payload["idempotency_key"]),
        allocated_active_path=Path(str(payload["allocated_active_path"])),
        state_snapshot_id=str(payload["state_snapshot_id"]),
        state_snapshot_hash=str(payload["state_snapshot_hash"]),
        state_snapshot_paths=[str(path) for path in payload.get("state_snapshot_paths", [])],
        resumed_from_path=(
            str(payload["resumed_from_path"])
            if payload.get("resumed_from_path") is not None
            else None
        ),
        resumed_from_hash=(
            str(payload["resumed_from_hash"])
            if payload.get("resumed_from_hash") is not None
            else None
        ),
        bound_slug=str(payload["bound_slug"]),
        slug_source=str(payload["slug_source"]),
        operation_state_path=Path(str(payload["operation_state_path"])),
        lease_id=str(payload["lease_id"]),
        lease_acquired_at=str(payload["lease_acquired_at"]),
        lease_expires_at=str(payload["lease_expires_at"]),
        transaction_watermark=str(payload["transaction_watermark"]),
        recovery_commands=dict(payload.get("recovery_commands", {})),
        status=str(payload["status"]),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
    )


def _ensure_no_compatible_reservation(
    state_dir: Path,
    *,
    project: str,
    operation: str,
    state_snapshot_hash: str,
) -> None:
    active_writes_dir = state_dir / "active-writes" / project
    if not active_writes_dir.exists():
        return
    now = datetime.now(UTC)
    for path in sorted(active_writes_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ActiveWriteError(
                "begin-active-write failed: active-write record unreadable; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            ) from exc
        if record.get("operation") != operation:
            continue
        if record.get("state_snapshot_hash") != state_snapshot_hash:
            continue
        if record.get("status") in {"committed", "abandoned", "reservation_expired"}:
            continue
        if _auto_expire_pre_output_reservation(record, path, now=now):
            continue
        raise ActiveWriteError(
            "begin-active-write failed: active write already reserved. "
            f"Got: {str(path)!r:.100}"
        )


def _auto_expire_pre_output_reservation(
    record: dict[str, object],
    operation_state_path: Path,
    *,
    now: datetime,
) -> bool:
    if record.get("status") != "begun":
        return False
    if record.get("content_hash") or record.get("output_sha256"):
        return False
    expires_at = str(record.get("lease_expires_at") or "")
    transaction_path_value = record.get("transaction_path")
    if not expires_at or not transaction_path_value:
        return False
    try:
        expires = _parse_created_at(expires_at)
    except ValueError:
        return False
    if expires >= now:
        return False
    updated = {**record, "status": "reservation_expired", "updated_at": now.isoformat()}
    _write_json_atomic(operation_state_path, updated)
    _write_json_atomic(Path(str(transaction_path_value)), {**updated, "status": "reservation_expired"})
    return True


def _recovery_commands(project_root: Path, operation_state_path: Path) -> dict[str, object]:
    operation_state = str(operation_state_path)
    return {
        "continue": {
            "command": "active-write-transaction-recover",
            "args": {
                "project_root": str(project_root),
                "operation_state_path": operation_state,
            },
        },
        "retry_write": {
            "command": "write-active-handoff",
            "args": {
                "project_root": str(project_root),
                "operation_state_path": operation_state,
                "content_file": "<content-file>",
                "content_sha256": "<sha256>",
            },
        },
        "abandon": {
            "command": "abandon-active-write",
            "args": {
                "project_root": str(project_root),
                "operation_state_path": operation_state,
                "reason": "<reason>",
            },
        },
    }


def allocate_active_path(
    project_root: Path,
    *,
    operation: str,
    slug: str,
    created_at: str | None = None,
) -> Path:
    """Allocate a collision-safe primary active handoff path."""
    if operation not in DEFAULT_SLUGS:
        raise ActiveWriteError(
            f"allocate-active-path failed: unsupported operation. Got: {operation!r:.100}"
        )
    _ensure_slug_segment("allocate-active-path", slug)
    layout = get_storage_layout(project_root)
    timestamp = _parse_created_at(created_at)
    return _allocate_active_path(
        layout.project_root,
        layout.primary_active_dir,
        operation,
        slug,
        timestamp,
    )


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
        _ensure_reservation_is_fresh(state, operation_state_path)
        _ensure_state_snapshot_is_current(layout.primary_state_dir, state, operation_state_path)
        _ensure_transaction_watermark_is_current(
            layout.primary_state_dir,
            state,
            operation_state_path,
        )
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if expected_hash != content_sha256:
            raise ActiveWriteError(
                "write-active-handoff failed: content hash mismatch. "
                f"Got: {content_sha256!r:.100}"
            )
        active_path = Path(str(state["allocated_active_path"]))
        transaction_path = Path(str(state["transaction_path"]))
        if state.get("status") != "committed":
            generated_at = datetime.now(UTC).isoformat()
            state.update({
                "status": "content-generated",
                "content_hash": content_sha256,
                "output_sha256": content_sha256,
                "updated_at": generated_at,
            })
            _write_json_atomic(operation_state_path, state)
            _write_json_atomic(
                transaction_path,
                {
                    **state,
                    "status": "content-generated",
                },
            )
        temp_active_path: str | None = None
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
            try:
                active_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = active_path.with_name(f".{active_path.name}.{uuid.uuid4().hex}.tmp")
                temp_active_path = str(temp_path)
                temp_path.write_text(content, encoding="utf-8")
            except OSError as exc:
                raise ActiveWriteError(
                    "write-active-handoff failed: active output write failed. "
                    f"Got: {str(active_path)!r:.100}"
                ) from exc
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
        state.update({
            "status": "write-pending",
            "active_path": str(active_path),
            "temp_active_path": temp_active_path,
            "content_hash": content_sha256,
            "output_sha256": content_sha256,
            "updated_at": updated_at,
        })
        _write_json_atomic(operation_state_path, state)
        _write_json_atomic(
            transaction_path,
            {
                **state,
                "status": "write-pending",
                "active_path": str(active_path),
            },
        )
        try:
            cleanup_action, cleanup_path = _clear_snapshotted_primary_state(state)
        except ActiveWriteError:
            failed_at = datetime.now(UTC).isoformat()
            state.update({
                "status": "cleanup_failed",
                "state_cleanup_action": "cleanup_failed",
                "state_cleanup_path": _first_state_cleanup_path(state),
                "updated_at": failed_at,
            })
            _write_json_atomic(operation_state_path, state)
            _write_json_atomic(
                transaction_path,
                {
                    **state,
                    "status": "cleanup_failed",
                    "active_path": str(active_path),
                },
            )
            raise
        state.update({
            "status": "committed",
            "state_cleanup_action": cleanup_action,
            "state_cleanup_path": cleanup_path,
            "updated_at": datetime.now(UTC).isoformat(),
        })
        _write_json_atomic(operation_state_path, state)
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
            "active_path_sha256": _sha256_path(active_path),
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
        recovered_from_status = str(state.get("status", ""))
        active_path = Path(str(state.get("active_path") or state["allocated_active_path"]))
        content_hash = str(state.get("content_hash") or state.get("output_sha256") or "")
        if not content_hash:
            return state
        if not active_path.exists():
            state["status"] = "pending_before_write"
            state["updated_at"] = datetime.now(UTC).isoformat()
            _write_json_atomic(operation_state_path, state)
            transaction_path = Path(str(state["transaction_path"]))
            _write_json_atomic(
                transaction_path,
                {
                    **state,
                    "status": "pending_before_write",
                    "active_path": str(active_path),
                },
            )
            return state
        if _sha256_path(active_path) != content_hash:
            state["status"] = "content_mismatch"
            state["updated_at"] = datetime.now(UTC).isoformat()
            _write_json_atomic(operation_state_path, state)
            transaction_path = Path(str(state["transaction_path"]))
            _write_json_atomic(
                transaction_path,
                {
                    **state,
                    "status": "content_mismatch",
                    "active_path": str(active_path),
                },
            )
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
            "recovered_from_status": recovered_from_status,
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


def _allocate_active_path(
    project_root: Path,
    active_dir: Path,
    operation: str,
    slug: str,
    created_at: datetime,
) -> Path:
    try:
        active_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ActiveWriteError(
            "allocate-active-path failed: parent path conflict. "
            f"Got: {str(active_dir)!r:.100}"
        ) from exc
    prefix = created_at.strftime("%Y-%m-%d_%H-%M")
    stem = f"{operation}-{slug}"
    candidate = active_dir / f"{prefix}_{stem}.md"
    if not _active_path_occupied(project_root, candidate):
        return candidate
    for index in range(1, 100):
        candidate = active_dir / f"{prefix}_{stem}-{index:02d}.md"
        if not _active_path_occupied(project_root, candidate):
            return candidate
    raise ActiveWriteError(
        f"allocate-active-path failed: collision budget exhausted. Got: {slug!r:.100}"
    )


def _active_path_occupied(project_root: Path, path: Path) -> bool:
    return path.exists() or path.is_symlink() or _git_tracks_path(project_root, path)


def _git_tracks_path(project_root: Path, path: Path) -> bool:
    project = project_root.resolve()
    try:
        rel = path.resolve().relative_to(project).as_posix()
    except ValueError:
        return False
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", rel],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return tracked.returncode == 0


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


def _ensure_reservation_is_fresh(
    state: dict[str, object],
    operation_state_path: Path,
) -> None:
    if state.get("status") in {"committed", "abandoned"}:
        return
    expires_at = str(state.get("lease_expires_at", ""))
    if not expires_at:
        return
    expires = _parse_created_at(expires_at)
    if expires >= datetime.now(UTC):
        return
    updated_at = datetime.now(UTC).isoformat()
    state.update({
        "status": "reservation_expired",
        "updated_at": updated_at,
    })
    _write_json_atomic(operation_state_path, state)
    transaction_path = Path(str(state["transaction_path"]))
    _write_json_atomic(
        transaction_path,
        {
            **state,
            "status": "reservation_expired",
        },
    )
    raise ActiveWriteError(
        "write-active-handoff failed: reservation expired. "
        f"Got: {expires_at!r:.100}"
    )


def _ensure_state_snapshot_is_current(
    state_dir: Path,
    state: dict[str, object],
    operation_state_path: Path,
) -> None:
    if state.get("status") in {"committed", "abandoned"}:
        return
    snapshot_id, snapshot_hash, _, _, _ = _state_snapshot(
        state_dir,
        str(state.get("project", "")),
    )
    if (
        snapshot_id == str(state.get("state_snapshot_id", ""))
        and snapshot_hash == str(state.get("state_snapshot_hash", ""))
    ):
        return
    updated_at = datetime.now(UTC).isoformat()
    state.update({
        "status": "reservation_conflict",
        "conflict_reason": "state_snapshot_changed",
        "current_state_snapshot_id": snapshot_id,
        "current_state_snapshot_hash": snapshot_hash,
        "updated_at": updated_at,
    })
    _write_json_atomic(operation_state_path, state)
    transaction_path = Path(str(state["transaction_path"]))
    _write_json_atomic(
        transaction_path,
        {
            **state,
            "status": "reservation_conflict",
        },
    )
    raise ActiveWriteError(
        "write-active-handoff failed: state snapshot changed. "
        f"Got: {snapshot_hash!r:.100}"
    )


def _first_state_cleanup_path(state: dict[str, object]) -> str | None:
    paths = [str(path) for path in state.get("state_snapshot_paths", [])]
    if not paths:
        return None
    return paths[0]


def _ensure_transaction_watermark_is_current(
    state_dir: Path,
    state: dict[str, object],
    operation_state_path: Path,
) -> None:
    if state.get("status") in {"committed", "abandoned"}:
        return
    transaction_path = Path(str(state["transaction_path"]))
    watermark = _transaction_watermark(state_dir, exclude_path=transaction_path)
    if watermark == str(state.get("transaction_watermark", "")):
        return
    updated_at = datetime.now(UTC).isoformat()
    state.update({
        "status": "reservation_conflict",
        "conflict_reason": "transaction_watermark_changed",
        "current_transaction_watermark": watermark,
        "updated_at": updated_at,
    })
    _write_json_atomic(operation_state_path, state)
    _write_json_atomic(
        transaction_path,
        {
            **state,
            "status": "reservation_conflict",
        },
    )
    raise ActiveWriteError(
        "write-active-handoff failed: transaction watermark changed. "
        f"Got: {watermark!r:.100}"
    )


def _transaction_watermark(state_dir: Path, *, exclude_path: Path | None = None) -> str:
    transactions_dir = state_dir / "transactions"
    if not transactions_dir.exists():
        return _stable_hash(["no-transactions"])
    parts: list[str] = []
    for path in sorted(transactions_dir.glob("*.json")):
        if exclude_path is not None and path == exclude_path:
            continue
        parts.extend([path.name, path.read_text(encoding="utf-8")])
    return _stable_hash(parts or ["no-transactions"])


_ACTIVE_WRITE_LOCK_POLICY = LockPolicy(
    operation_label="begin-active-write",
    lock_kind="project active-write lock",
    error_factory=ActiveWriteError,
)


def _acquire_lock(
    path: Path,
    *,
    project: str,
    operation: str,
    transaction_id: str,
) -> None:
    _acquire_lock_with_policy(
        path,
        project=project,
        operation=operation,
        transaction_id=transaction_id,
        policy=_ACTIVE_WRITE_LOCK_POLICY,
    )


def _stable_hash(parts: list[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()
