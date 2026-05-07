from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import RefreshError, fail

LOCK_OWNER_SCHEMA_VERSION = "turbo-mode-refresh-lock-owner-v1"
RUN_STATE_SCHEMA_VERSION = "turbo-mode-refresh-run-state-v1"
PHASE_ONLY_ALLOWED = frozenset(
    {
        "marker-started",
        "before-snapshot-process-checked",
        "after-hook-disable-process-checked",
        "before-install-process-checked",
        "post-mutation-process-checked",
        "post-recovery-process-checked",
    }
)
SNAPSHOT_METADATA_FIELDS = (
    "snapshot_path_map",
    "snapshot_manifest_digest",
    "original_config_sha256",
    "pre_refresh_cache_manifest_sha256",
    "recovery_eligibility",
)


@dataclass(frozen=True, kw_only=True)
class LockOwner:
    run_id: str
    mode: str
    source_implementation_commit: str
    execution_head: str
    tool_sha256: str
    pid: int
    parent_pid: int
    observed_process_start: str
    raw_owner_process_row_sha256: str
    acquisition_timestamp: str
    command_line_sequence: tuple[str, ...]
    schema_version: str = LOCK_OWNER_SCHEMA_VERSION


@dataclass(frozen=True, kw_only=True)
class RunState:
    run_id: str
    mode: str
    source_implementation_commit: str
    source_implementation_tree: str
    execution_head: str
    execution_tree: str
    tool_sha256: str
    phase: str
    schema_version: str = RUN_STATE_SCHEMA_VERSION
    original_run_owner_sha256: str | None = None
    recovery_owner_sha256: str | None = None
    pre_snapshot_app_server_launch_authority_sha256: str | None = None
    pre_install_app_server_target_authority_sha256: str | None = None
    plugin_hooks_start_state: str | None = None
    original_config_sha256: str | None = None
    expected_intermediate_config_sha256: str | None = None
    hook_disabled_config_sha256: str | None = None
    pre_refresh_cache_manifest_sha256: dict[str, str] = field(default_factory=dict)
    post_install_cache_manifest_sha256: dict[str, str] = field(default_factory=dict)
    snapshot_path_map: dict[str, str] = field(default_factory=dict)
    snapshot_manifest_digest: str | None = None
    process_summary_sha256: dict[str, str] = field(default_factory=dict)
    app_server_child_pid_map: dict[str, int] = field(default_factory=dict)
    smoke_summary_sha256: str | None = None
    evidence_summary_sha256: str | None = None
    recovery_eligibility: str | None = None
    final_status: str | None = None


@contextmanager
def acquire_refresh_lock(
    *,
    local_only_root: Path,
    run_id: str,
    mode: str,
    source_implementation_commit: str,
    execution_head: str,
    tool_sha256: str,
) -> Iterator[LockOwner]:
    ensure_local_only_root(local_only_root)
    lock_path = local_only_root / "refresh.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RefreshError(
                "acquire refresh lock failed: refresh lock is already held. "
                f"Got: {str(lock_path)!r:.100}"
            ) from exc
        owner_record = _collect_owner_process_row(os.getpid())
        owner_record = replace(
            owner_record,
            run_id=run_id,
            mode=mode,
            source_implementation_commit=source_implementation_commit,
            execution_head=execution_head,
            tool_sha256=tool_sha256,
            acquisition_timestamp=_utc_now(),
        )
        owner_path = _owner_path(local_only_root, run_id)
        write_owner_file(owner_path, owner_record)
        yield owner_record
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def write_initial_run_state(local_only_root: Path, state: RunState) -> Path:
    path = _marker_path(local_only_root, state.run_id)
    if path.exists():
        raise FileExistsError(
            "write initial run state failed: marker already exists. "
            f"Got: {str(path)!r:.100}"
        )
    return _write_run_state(path, state)


def replace_run_state(local_only_root: Path, state: RunState) -> Path:
    return _write_run_state(_marker_path(local_only_root, state.run_id), state)


def update_run_state_phase(local_only_root: Path, run_id: str, phase: str) -> None:
    if phase not in PHASE_ONLY_ALLOWED:
        raise RefreshError(
            "update run state phase failed: "
            "phase-only update cannot produce recovery-critical fields. "
            f"Got: {phase!r:.100}",
        )
    state = read_run_state(local_only_root, run_id)
    replace_run_state(local_only_root, replace(state, phase=phase))


def read_run_state(local_only_root: Path, run_id: str) -> RunState:
    path = _marker_path(local_only_root, run_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("read run state", str(exc), str(path))
    return _run_state_from_payload(payload)


def clear_run_state(local_only_root: Path, run_id: str) -> None:
    path = _marker_path(local_only_root, run_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def preserve_original_owner_for_recovery(
    local_only_root: Path,
    run_id: str,
    owner_path: Path,
) -> dict[str, str]:
    destination_dir = local_only_root / run_id / "recovery"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_dir.chmod(0o700)
    destination = destination_dir / "original-owner.json"
    data = owner_path.read_bytes()
    _write_private_bytes(destination, data)
    return {
        "preserved_owner_path": str(destination),
        "preserved_owner_sha256": hashlib.sha256(data).hexdigest(),
    }


def write_owner_file(path: Path, owner: LockOwner) -> None:
    _write_private_json(path, _json_safe(owner))


def collect_owner_identity(
    *,
    pid: int,
    run_id: str,
    mode: str,
    source_implementation_commit: str,
    execution_head: str,
    tool_sha256: str,
) -> LockOwner:
    raw_row = _raw_owner_row(pid)
    return _owner_from_raw_row(
        raw_row,
        run_id=run_id,
        mode=mode,
        source_implementation_commit=source_implementation_commit,
        execution_head=execution_head,
        tool_sha256=tool_sha256,
    )


def validate_recovery_owner_identity(stale_owner: LockOwner, current_owner: LockOwner) -> None:
    if stale_owner.pid != current_owner.pid:
        fail(
            "validate recovery owner",
            "owner PID mismatch",
            {"stale": stale_owner.pid, "current": current_owner.pid},
        )
    if stale_owner.observed_process_start != current_owner.observed_process_start:
        fail(
            "validate recovery owner",
            "PID reuse detected",
            {
                "pid": stale_owner.pid,
                "stale_lstart": stale_owner.observed_process_start,
                "current_lstart": current_owner.observed_process_start,
            },
        )


def validate_recovery_run_state(state: RunState, *, expected_run_id: str) -> None:
    if state.run_id != expected_run_id:
        fail(
            "validate recovery marker",
            "run id mismatch",
            {"expected": expected_run_id, "actual": state.run_id},
        )
    _require_snapshot_marker(state, operation="validate recovery marker")


def validate_hook_disable_allowed(state: RunState) -> None:
    _require_launch_authority(state, operation="validate hook disable")
    _require_snapshot_marker(state, operation="validate hook disable")


def validate_cache_install_allowed(state: RunState) -> None:
    _require_launch_authority(state, operation="validate cache install")
    _require_snapshot_marker(state, operation="validate cache install")


def validate_smoke_allowed(state: RunState) -> None:
    _require_launch_authority(state, operation="validate smoke")


def ensure_local_only_root(local_only_root: Path) -> None:
    local_only_root.mkdir(parents=True, exist_ok=True)
    os.chmod(local_only_root, 0o700)
    run_state_dir = local_only_root / "run-state"
    run_state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(run_state_dir, 0o700)


def _collect_owner_process_row(pid: int) -> LockOwner:
    raw_row = _raw_owner_row(pid)
    return _owner_from_raw_row(
        raw_row,
        run_id="",
        mode="",
        source_implementation_commit="",
        execution_head="",
        tool_sha256="",
    )


def _raw_owner_row(pid: int) -> str:
    completed = subprocess.run(
        ["ps", "-ww", "-o", "pid=,ppid=,lstart=,command=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        fail("collect lock owner identity", "owner process row missing or ambiguous", rows)
    return rows[0]


def _owner_from_raw_row(
    row: str,
    *,
    run_id: str,
    mode: str,
    source_implementation_commit: str,
    execution_head: str,
    tool_sha256: str,
) -> LockOwner:
    match = re.match(r"^\s*(\d+)\s+(\d+)\s+(.{24})\s+(.+)$", row)
    if match is None:
        fail("collect lock owner identity", "owner process row unparsable", row)
    try:
        pid = int(match.group(1))
        ppid = int(match.group(2))
    except ValueError:
        fail("collect lock owner identity", "owner process PID unparsable", row)
    observed_process_start = match.group(3)
    command = match.group(4)
    try:
        command_line_sequence = tuple(shlex.split(command))
    except ValueError:
        fail("collect lock owner identity", "owner command unparsable", row)
    return LockOwner(
        run_id=run_id,
        mode=mode,
        source_implementation_commit=source_implementation_commit,
        execution_head=execution_head,
        tool_sha256=tool_sha256,
        pid=pid,
        parent_pid=ppid,
        observed_process_start=observed_process_start,
        raw_owner_process_row_sha256=hashlib.sha256(row.encode("utf-8")).hexdigest(),
        acquisition_timestamp=_utc_now(),
        command_line_sequence=command_line_sequence,
    )


def _owner_path(local_only_root: Path, run_id: str) -> Path:
    ensure_local_only_root(local_only_root)
    return local_only_root / "run-state" / f"{run_id}.owner.json"


def _marker_path(local_only_root: Path, run_id: str) -> Path:
    ensure_local_only_root(local_only_root)
    return local_only_root / "run-state" / f"{run_id}.marker.json"


def _write_run_state(path: Path, state: RunState) -> Path:
    _write_private_json(path, _json_safe(state))
    return path


def _write_private_json(path: Path, payload: object) -> None:
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    _write_private_bytes(path, data)


def _write_private_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.chmod(path, 0o600)


def _run_state_from_payload(payload: object) -> RunState:
    if not isinstance(payload, dict):
        fail("read run state", "payload is not an object", payload)
    kwargs: dict[str, Any] = {}
    field_names = {field.name for field in dataclasses.fields(RunState)}
    for key, value in payload.items():
        if key in field_names:
            kwargs[key] = value
    return RunState(**kwargs)


def _require_launch_authority(state: RunState, *, operation: str) -> None:
    if not state.pre_snapshot_app_server_launch_authority_sha256:
        fail(
            operation,
            "pre-snapshot app-server launch authority is required",
            state.phase,
        )


def _require_snapshot_marker(state: RunState, *, operation: str) -> None:
    missing = [
        field_name
        for field_name in SNAPSHOT_METADATA_FIELDS
        if not getattr(state, field_name)
    ]
    if missing:
        fail(operation, "snapshot marker metadata is required", missing)


def _json_safe(value: object) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            key: _json_safe(inner_value)
            for key, inner_value in dataclasses.asdict(value).items()
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_safe(inner_value) for inner_value in value]
    if isinstance(value, list):
        return [_json_safe(inner_value) for inner_value in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(inner_value) for key, inner_value in value.items()}
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
