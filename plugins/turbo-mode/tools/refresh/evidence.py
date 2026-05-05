from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .app_server_inventory import transcript_bytes
from .planner import RefreshPlanResult

SCHEMA_VERSION = "turbo-mode-refresh-plan-03"


def evidence_payload(result: RefreshPlanResult, *, run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": result.mode,
        "repo_root": str(result.paths.repo_root),
        "codex_home": str(result.paths.codex_home),
        "marketplace_path": str(result.paths.marketplace_path),
        "config_path": str(result.paths.config_path),
        "local_only_evidence_root": str(result.paths.local_only_root / run_id),
        "residue_issues": _json_safe(result.residue_issues),
        "diffs": _json_safe(result.diffs),
        "diff_classification": _json_safe(result.diff_classification),
        "runtime_config": _json_safe(result.runtime_config),
        "app_server_inventory": _json_safe(result.app_server_inventory),
        "app_server_inventory_status": result.app_server_inventory_status,
        "app_server_inventory_failure_reason": result.app_server_inventory_failure_reason,
        "axes": _json_safe(result.axes),
        "terminal_plan_status": result.terminal_status.value,
        "future_external_command": result.future_external_command,
        "mutation_command_available": result.mutation_command_available,
        "requires_plan": result.requires_plan,
        "omission_reasons": _omission_reasons(result),
    }


def write_local_evidence(result: RefreshPlanResult, *, run_id: str) -> Path:
    safe_run_id = validate_run_id(run_id)
    ensure_private_evidence_root(result.paths.local_only_root)
    run_dir = result.paths.local_only_root / safe_run_id
    try:
        os.mkdir(run_dir, 0o700)
    except FileExistsError as exc:
        raise FileExistsError(
            "create evidence run directory failed: run directory already exists. "
            f"Got: {str(run_dir)!r:.100}"
        ) from exc
    path = run_dir / f"{result.mode}.summary.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if result.app_server_transcript:
        transcript_path = run_dir / "app-server-readonly-inventory.transcript.json"
        transcript_fd = os.open(transcript_path, flags, 0o600)
        with os.fdopen(transcript_fd, "wb") as handle:
            handle.write(transcript_bytes(result.app_server_transcript))
        os.chmod(transcript_path, 0o600)
    payload = evidence_payload(result, run_id=safe_run_id)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)
    return path


def ensure_private_evidence_root(root: Path) -> None:
    reject_symlinks_in_path(root)
    if root.exists():
        if not root.is_dir():
            raise NotADirectoryError(
                "validate evidence root failed: root is not a directory. "
                f"Got: {str(root)!r:.100}"
            )
        mode = stat.S_IMODE(root.stat().st_mode)
        if mode != 0o700:
            raise PermissionError(
                "validate evidence root failed: evidence root permissions must be 0700. "
                f"Got: {oct(mode)!r:.100}"
            )
        return
    root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    reject_symlinks_in_path(root)


def reject_symlinks_in_path(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            path_stat = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(path_stat.st_mode):
            raise ValueError(
                "validate evidence path failed: symlinks are not allowed. "
                f"Got: {str(current)!r:.100}"
            )


def validate_run_id(run_id: str) -> str:
    if not run_id or "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
        raise ValueError(
            "validate run id failed: run id must be one path segment. "
            f"Got: {run_id!r:.100}"
        )
    if ".." in run_id:
        raise ValueError(
            "validate run id failed: traversal marker is not allowed. "
            f"Got: {run_id!r:.100}"
        )
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in run_id):
        raise ValueError(
            "validate run id failed: unsupported character. "
            f"Got: {run_id!r:.100}"
        )
    return run_id


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _omission_reasons(result: RefreshPlanResult) -> dict[str, str]:
    return {
        "app_server_inventory": result.app_server_inventory_status,
        "process_gate": "outside-plan-03",
        "post_refresh_cache_manifest": "outside-plan-03",
        "smoke_summary": "outside-plan-03",
        "commit_safe_summary": "outside-plan-03",
    }
