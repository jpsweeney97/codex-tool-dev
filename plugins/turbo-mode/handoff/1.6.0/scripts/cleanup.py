#!/usr/bin/env python3
"""
cleanup.py - Handoff state-file cleanup helper.

This entry point is hook-compatible, but Handoff 1.6.0 does not wire
plugin-bundled command hooks into the installed plugin manifest.

Responsibilities:
- Prune state files older than 24 hours

Does NOT touch handoff files. The plugin writes filesystem artifacts only;
whether docs/handoffs/ is tracked or ignored is host-repository policy.
The plugin does not add gitignore rules, stage files, or auto-commit files.

Exit Codes:
    0  - Success (always exits 0 to avoid blocking the caller)
"""

import sys
from pathlib import Path

try:
    from scripts.session_state import prune_old_state_files
except ModuleNotFoundError:  # Direct execution (python3 scripts/cleanup.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.session_state import prune_old_state_files  # type: ignore[no-redef]


def main() -> int:
    """Main entry point for state-file cleanup.

    Silently prunes old state files. Does not touch handoff files.

    Returns:
        0 on best-effort completion. Cleanup must never block the caller. Only
        BaseException subclasses (e.g., KeyboardInterrupt, SystemExit)
        propagate — these indicate process-level termination.
    """
    try:
        prune_old_state_files(max_age_hours=24)
    except Exception:
        pass  # Never block session start — cleanup is best-effort

    return 0


if __name__ == "__main__":
    sys.exit(main())
