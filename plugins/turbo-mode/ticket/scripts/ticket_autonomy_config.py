"""Strict local Ticket automation config and workspace state."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

LOCAL_CONFIG_SCHEMA = "codex.ticket.local.v1"
MODE_SNAPSHOT_SCHEMA = "codex.ticket.mode-snapshot.v1"
LOCAL_CONFIG_RELATIVE_PATH = Path(".codex") / "ticket.local.md"
WORKSPACE_RELATIVE_PATH = Path(".codex") / "ticket-workspace"
PAUSE_FILENAME = "pause.json"
SNAPSHOTS_DIRNAME = "mode-snapshots"

WORKSPACE_AGENTS_TEXT = """# Ticket Automation Workspace State

Files in this directory are local Ticket automation bookkeeping.
Do not stage, commit, push, publish, or treat them as project history.
Project truth remains in `docs/tickets/` ticket files and committed `## Change History` entries.
"""


class AutomationMode(StrEnum):
    """Runtime-first automation modes for local Ticket setup."""

    DISCUSSION_ONLY = "discussion_only"
    PREVIEW = "preview"
    AGENT_PRIMARY = "agent_primary"


class LocalConfigState(StrEnum):
    """Strict local config resolution state."""

    VALID = "valid"
    SETUP_REQUIRED = "setup_required"


class SetupChoice(StrEnum):
    """Host-facing setup choices that can write local config."""

    AUTOMATIC = "automatic"
    ASK_FIRST = "ask_first"


@dataclass(frozen=True, slots=True)
class LocalConfigResult:
    """Strict local config read result."""

    state: LocalConfigState
    mode: AutomationMode | None
    path: Path
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ModeSnapshot:
    """Per-project, per-thread mode snapshot."""

    project_root: Path
    thread_id: str
    mode: AutomationMode
    path: Path


@dataclass(frozen=True, slots=True)
class ResolvedMode:
    """Effective automation mode resolution result for a thread."""

    state: LocalConfigState
    mode: AutomationMode | None
    source: Literal["snapshot", "config", "setup_required"]
    path: Path | None
    reason: str | None = None


def _local_config_path(project_root: Path) -> Path:
    return project_root / LOCAL_CONFIG_RELATIVE_PATH


def _workspace_path(project_root: Path) -> Path:
    return project_root / WORKSPACE_RELATIVE_PATH


def _pause_path(project_root: Path) -> Path:
    return _workspace_path(project_root) / PAUSE_FILENAME


def _snapshot_dir(project_root: Path) -> Path:
    return _workspace_path(project_root) / SNAPSHOTS_DIRNAME


def _canonical_json(data: dict[str, str]) -> str:
    return json.dumps(data, separators=(",", ":"))


def _normalized_project_root(project_root: Path) -> str:
    return str(project_root.resolve(strict=False))


def _parse_mode(value: Any) -> AutomationMode | None:
    if not isinstance(value, str):
        return None
    try:
        return AutomationMode(value)
    except ValueError:
        return None


def read_local_config(project_root: Path) -> LocalConfigResult:
    """Read strict project-local automation config.

    Args:
        project_root: Project root containing `.codex/ticket.local.md`.

    Returns:
        A config result. Invalid or missing config returns `setup_required`.
    """
    path = _local_config_path(project_root)
    if not path.is_file():
        return LocalConfigResult(LocalConfigState.SETUP_REQUIRED, None, path, "missing_config")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LocalConfigResult(LocalConfigState.SETUP_REQUIRED, None, path, "invalid_json")

    if not isinstance(data, dict):
        return LocalConfigResult(LocalConfigState.SETUP_REQUIRED, None, path, "invalid_shape")
    if set(data) != {"schema", "mode"}:
        return LocalConfigResult(LocalConfigState.SETUP_REQUIRED, None, path, "invalid_keys")
    if data.get("schema") != LOCAL_CONFIG_SCHEMA:
        return LocalConfigResult(LocalConfigState.SETUP_REQUIRED, None, path, "invalid_schema")

    mode = _parse_mode(data.get("mode"))
    if mode is None:
        return LocalConfigResult(LocalConfigState.SETUP_REQUIRED, None, path, "invalid_mode")

    return LocalConfigResult(LocalConfigState.VALID, mode, path)


def write_local_config(project_root: Path, mode: AutomationMode) -> Path:
    """Rewrite project-local automation config as compact strict JSON.

    Args:
        project_root: Project root that owns the local config.
        mode: Runtime-first automation mode to write.

    Returns:
        Path to the written config file.
    """
    path = _local_config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json({"schema": LOCAL_CONFIG_SCHEMA, "mode": mode.value})
    path.write_text(f"{payload}\n", encoding="utf-8")
    return path


def write_local_config_from_setup_choice(project_root: Path, choice: SetupChoice) -> Path:
    """Rewrite local config from a guided setup choice.

    Args:
        project_root: Project root that owns the local config.
        choice: Host-facing setup choice.

    Returns:
        Path to the written config file.
    """
    if choice == SetupChoice.AUTOMATIC:
        return write_local_config(project_root, AutomationMode.AGENT_PRIMARY)
    if choice == SetupChoice.ASK_FIRST:
        return write_local_config(project_root, AutomationMode.DISCUSSION_ONLY)
    raise ValueError(f"write setup choice failed: unknown setup choice. Got: {choice!r:.100}")


def _workspace_ignore_is_declared(project_root: Path) -> bool:
    relative = WORKSPACE_RELATIVE_PATH.as_posix() + "/"
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, ValueError):
        result = None
    if result is not None and result.returncode == 0:
        return True
    if result is not None and result.returncode == 1:
        return False

    gitignore = project_root / ".gitignore"
    if not gitignore.is_file():
        return False
    try:
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    accepted = {
        ".codex/ticket-workspace",
        ".codex/ticket-workspace/",
        ".codex/ticket-workspace/**",
    }
    return any(line.strip() in accepted for line in lines if not line.strip().startswith("#"))


def ensure_ticket_workspace(project_root: Path) -> Path:
    """Create the local Ticket automation workspace after ignore verification.

    Args:
        project_root: Project root that owns `.codex/ticket-workspace/`.

    Returns:
        Path to the workspace directory.

    Raises:
        RuntimeError: If the workspace path is not ignored by git.
    """
    if not _workspace_ignore_is_declared(project_root):
        raise RuntimeError(
            "ensure ticket workspace failed: .codex/ticket-workspace/ is not ignored. "
            f"Got: {str(project_root)!r:.100}"
        )

    workspace = _workspace_path(project_root)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text(WORKSPACE_AGENTS_TEXT, encoding="utf-8")
    _snapshot_dir(project_root).mkdir(parents=True, exist_ok=True)
    return workspace


def mode_snapshot_key(project_root: Path, thread_id: str) -> str:
    """Build a deterministic local snapshot key for a project and thread.

    Args:
        project_root: Project root that scopes the snapshot directory.
        thread_id: Current Codex thread identifier.

    Returns:
        First 32 lowercase hex characters of the SHA-256 key.
    """
    if not thread_id.strip():
        raise ValueError(
            "mode snapshot key failed: thread_id is required. "
            f"Got: {thread_id!r:.100}"
        )
    payload = _canonical_json(
        {
            "project_root": _normalized_project_root(project_root),
            "thread_id": thread_id,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _snapshot_path(project_root: Path, thread_id: str) -> Path:
    return _snapshot_dir(project_root) / f"{mode_snapshot_key(project_root, thread_id)}.json"


def read_mode_snapshot(project_root: Path, thread_id: str) -> ModeSnapshot | None:
    """Read and validate a local mode snapshot.

    Args:
        project_root: Project root that scopes the snapshot directory.
        thread_id: Current Codex thread identifier.

    Returns:
        The valid snapshot, or `None` when missing, malformed, or stale.
    """
    if not thread_id.strip():
        return None
    path = _snapshot_path(project_root, thread_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if set(data) != {"schema", "project_root", "thread_id", "mode"}:
        return None
    if data.get("schema") != MODE_SNAPSHOT_SCHEMA:
        return None
    if data.get("project_root") != _normalized_project_root(project_root):
        return None
    if data.get("thread_id") != thread_id:
        return None
    mode = _parse_mode(data.get("mode"))
    if mode is None:
        return None
    return ModeSnapshot(project_root.resolve(strict=False), thread_id, mode, path)


def write_mode_snapshot(project_root: Path, thread_id: str, mode: AutomationMode) -> ModeSnapshot:
    """Write a local mode snapshot for the project/thread pair.

    Args:
        project_root: Project root that scopes the snapshot directory.
        thread_id: Current Codex thread identifier.
        mode: Automation mode to freeze for the thread.

    Returns:
        The written snapshot metadata.
    """
    ensure_ticket_workspace(project_root)
    path = _snapshot_path(project_root, thread_id)
    payload = _canonical_json(
        {
            "schema": MODE_SNAPSHOT_SCHEMA,
            "project_root": _normalized_project_root(project_root),
            "thread_id": thread_id,
            "mode": mode.value,
        }
    )
    path.write_text(f"{payload}\n", encoding="utf-8")
    return ModeSnapshot(project_root.resolve(strict=False), thread_id, mode, path)


def is_workspace_paused(project_root: Path) -> bool:
    """Return whether project-local Ticket automation is paused."""
    return _pause_path(project_root).is_file()


def resolve_thread_mode(project_root: Path, thread_id: str) -> ResolvedMode:
    """Resolve the effective automation mode for one project/thread pair.

    Args:
        project_root: Project root that owns local config and workspace state.
        thread_id: Current Codex thread identifier.

    Returns:
        Snapshot-backed, config-backed, or setup-required resolution.
    """
    pause_path = _pause_path(project_root)
    if pause_path.is_file():
        return ResolvedMode(
            LocalConfigState.SETUP_REQUIRED,
            None,
            "setup_required",
            pause_path,
            "workspace_paused",
        )
    if not thread_id.strip():
        return ResolvedMode(
            LocalConfigState.SETUP_REQUIRED,
            None,
            "setup_required",
            None,
            "thread_id_required",
        )

    snapshot = read_mode_snapshot(project_root, thread_id)
    if snapshot is not None:
        return ResolvedMode(LocalConfigState.VALID, snapshot.mode, "snapshot", snapshot.path)

    config = read_local_config(project_root)
    if config.state != LocalConfigState.VALID or config.mode is None:
        return ResolvedMode(
            LocalConfigState.SETUP_REQUIRED,
            None,
            "setup_required",
            config.path,
            config.reason,
        )

    snapshot = write_mode_snapshot(project_root, thread_id, config.mode)
    return ResolvedMode(LocalConfigState.VALID, snapshot.mode, "config", config.path)


def write_workspace_pause(project_root: Path, *, reason: str) -> Path:
    """Write the workspace-wide automation pause marker.

    Args:
        project_root: Project root that owns workspace state.
        reason: Short machine-readable pause reason.

    Returns:
        Path to the pause marker.
    """
    ensure_ticket_workspace(project_root)
    path = _pause_path(project_root)
    payload = _canonical_json(
        {
            "schema": "codex.ticket.workspace-pause.v1",
            "reason": reason,
            "paused_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    path.write_text(f"{payload}\n", encoding="utf-8")
    return path


def pause_workspace_automation(project_root: Path, *, reason: str) -> Path:
    """Pause automation and rewrite local config to discussion-only mode.

    Args:
        project_root: Project root that owns workspace state.
        reason: Short machine-readable pause reason.

    Returns:
        Path to the pause marker.
    """
    pause_path = write_workspace_pause(project_root, reason=reason)
    write_local_config(project_root, AutomationMode.DISCUSSION_ONLY)
    return pause_path


def _clear_workspace_pause_for_tests(project_root: Path) -> None:
    try:
        _pause_path(project_root).unlink()
    except FileNotFoundError:
        pass


def _invalidate_mode_snapshots(project_root: Path) -> None:
    snapshot_dir = _snapshot_dir(project_root)
    if not snapshot_dir.is_dir():
        return
    for path in snapshot_dir.glob("*.json"):
        if path.is_file():
            path.unlink()


def resume_workspace_automation(project_root: Path, *, choice: SetupChoice) -> Path:
    """Resume automation through an explicit setup-choice rewrite.

    Args:
        project_root: Project root that owns workspace state.
        choice: Host-facing setup choice used to rewrite strict config.

    Returns:
        Path to the rewritten config file.
    """
    ensure_ticket_workspace(project_root)
    _invalidate_mode_snapshots(project_root)
    _clear_workspace_pause_for_tests(project_root)
    return write_local_config_from_setup_choice(project_root, choice)
