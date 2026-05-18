"""Shared path validation helpers for ticket scripts."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_PROJECT_ROOT_MARKERS = (".codex", ".git")


def discover_project_root(start: Path) -> Path | None:
    """Walk ancestors from start to find nearest project root.

    A project root is the nearest ancestor (including start itself) that
    contains a .codex/ directory, a .git/ directory, or a .git file
    (git worktree marker).

    The search starts from start.resolve(), so symlinked paths are
    canonicalized before marker detection. The returned root is therefore
    the resolved filesystem path, not the original symlink spelling.

    Returns None if no marker is found (caller should reject, not fallback).
    """
    current = start.resolve()
    while True:
        for marker in _PROJECT_ROOT_MARKERS:
            if (current / marker).exists():
                return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def resolve_tickets_dir(
    raw_tickets_dir: Any,
    *,
    project_root: Path,
) -> tuple[Path | None, str | None]:
    """Resolve and validate tickets_dir against project root."""
    value = "docs/tickets" if raw_tickets_dir is None else raw_tickets_dir
    if not isinstance(value, (str, os.PathLike)):
        return (
            None,
            f"tickets_dir validation failed: expected string path. Got: {value!r:.100}",
        )

    try:
        root = project_root.resolve()
        candidate = Path(value)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    except OSError as exc:
        return (
            None,
            f"tickets_dir resolution failed: {exc}. Got: {str(value)!r:.100}",
        )

    try:
        resolved.relative_to(root)
    except ValueError:
        return (
            None,
            f"tickets_dir validation failed: path escapes project root {str(root)!r}. Got: {str(value)!r:.100}",
        )
    return resolved, None
