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


from turbo_mode_handoff_runtime.session_state import prune_old_state_files


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
    except Exception as exc:
        print(
            f"state cleanup warning: ttl prune failed: {exc}. Got: {24!r:.100}",
            file=sys.stderr,
        )

    return 0
