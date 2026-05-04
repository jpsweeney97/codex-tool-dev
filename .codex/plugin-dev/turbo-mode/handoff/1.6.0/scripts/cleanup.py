#!/usr/bin/env python3
"""
cleanup.py - Handoff plugin SessionStart hook script.

Responsibilities:
- Prune state files older than 24 hours

Does NOT touch handoff files — those are git-tracked in docs/handoffs/
and managed manually. Does NOT auto-inject or prompt for handoffs.

Exit Codes:
    0  - Success (always exits 0 to avoid blocking session start)
"""

import subprocess
import sys
import time
from pathlib import Path

try:
    from scripts.project_paths import get_state_dir
except ModuleNotFoundError:  # Direct execution (python3 scripts/cleanup.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.project_paths import get_state_dir  # type: ignore[no-redef]


def _trash(path: Path) -> bool:
    """Attempt to move a file to trash. Returns True on success, False on failure.

    Failures are silent by design — this runs during SessionStart cleanup where
    blocking the session is worse than skipping a deletion.
    """
    try:
        subprocess.run(["trash", str(path)], capture_output=True, timeout=5, check=True)
        return True
    except FileNotFoundError:
        return False  # trash binary not installed — skip deletion
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False  # PermissionError, trash failure, or timeout — skip


def prune_old_state_files(max_age_hours: int = 24, *, state_dir: Path | None = None) -> list[Path]:
    """Delete state files older than max_age_hours. Returns list of deleted files."""
    if state_dir is None:
        state_dir = get_state_dir()
    if not state_dir.exists():
        return []

    deleted = []
    cutoff = time.time() - (max_age_hours * 60 * 60)

    for state_file in state_dir.glob("handoff-*"):
        try:
            if state_file.stat().st_mtime < cutoff:
                if _trash(state_file):
                    deleted.append(state_file)
        except OSError:
            pass  # Handles stat() TOCTOU: file removed between glob() and stat()

    return deleted


def main() -> int:
    """Main entry point for SessionStart hook.

    Silently prunes old state files. Does not touch handoff files
    (those are git-tracked in docs/handoffs/ — manual cleanup only).

    Returns:
        0 on best-effort completion. A SessionStart hook must never block
        session start. Only BaseException subclasses (e.g., KeyboardInterrupt,
        SystemExit) propagate — these indicate process-level termination.
    """
    try:
        prune_old_state_files(max_age_hours=24)
    except Exception:
        pass  # Never block session start — cleanup is best-effort

    return 0


if __name__ == "__main__":
    sys.exit(main())
