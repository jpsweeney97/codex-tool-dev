"""Filesystem and git inspection helpers for handoff storage artifacts."""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_relative_to(path: Path, root: Path) -> bool:
    """Return whether ``path`` is at or below ``root``."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def fs_status(path: Path) -> str:
    """Classify the current filesystem status for ``path``."""
    if path.is_symlink():
        return "symlink"
    if not path.exists():
        return "missing"
    if path.is_file():
        return "regular-file"
    if path.is_dir():
        return "directory"
    return "non-regular"


def git_visibility(project_root: Path, path: Path) -> str:
    """Classify git visibility for ``path`` within ``project_root``."""
    if not _inside_git_worktree(project_root):
        return "not-git-repo"
    project = project_root.resolve()
    resolved = path.resolve()
    if not is_relative_to(resolved, project):
        return "outside-project"
    rel = resolved.relative_to(project).as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode == 0:
        return "tracked-conflict"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", rel],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if ignored.returncode == 0:
        return "ignored"
    return "untracked"


def _inside_git_worktree(project_root: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"
