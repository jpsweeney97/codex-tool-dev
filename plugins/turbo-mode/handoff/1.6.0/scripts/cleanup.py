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

def _load_bootstrap_by_path() -> None:
    import importlib.util

    bootstrap_path = Path(__file__).resolve().parent / "_bootstrap.py"
    cached = sys.modules.get("scripts._bootstrap")
    if cached is not None:
        cached_file = getattr(cached, "__file__", None)
        try:
            cached_path = Path(cached_file).resolve() if cached_file is not None else None
        except (OSError, TypeError):
            cached_path = None
        if cached_path == bootstrap_path:
            ensure = getattr(cached, "ensure_plugin_scripts_package", None)
            if callable(ensure):
                ensure()
                return
        sys.modules.pop("scripts._bootstrap", None)
    spec = importlib.util.spec_from_file_location("scripts._bootstrap", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            "handoff bootstrap failed: missing or unloadable _bootstrap.py. "
            f"Got: {str(bootstrap_path)!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)


_load_bootstrap_by_path()
del _load_bootstrap_by_path

from scripts.session_state import prune_old_state_files


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


if __name__ == "__main__":
    sys.exit(main())
