"""Shared path utilities for handoff plugin scripts.

Provides project root detection and handoffs directory resolution.
"""

from __future__ import annotations

import subprocess
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

from scripts.storage_authority import get_storage_layout


def get_project_root() -> tuple[Path, str]:
    """Get project root directory from git, falling back to cwd.

    Returns:
        (project_root, source) where source is "git" or "cwd".
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()), "git"

        print(
            f"Warning: git rev-parse failed (returncode={result.returncode}). Falling back to cwd.",
            file=sys.stderr,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(
            f"Warning: git project detection failed ({type(exc).__name__}). Falling back to cwd.",
            file=sys.stderr,
        )
    return Path.cwd(), "cwd"


def get_project_name() -> tuple[str, str]:
    """Get project name from git root directory, falling back to cwd.

    Returns:
        (project_name, source) where source is "git" or "cwd".
    """
    root, source = get_project_root()
    return root.name, source


def get_handoffs_dir() -> Path:
    """Get primary handoffs directory: <project_root>/.codex/handoffs/."""
    root, _ = get_project_root()
    return get_storage_layout(root).primary_active_dir


def get_archive_dir() -> Path:
    """Return the archive directory for the current project's handoffs."""
    root, _ = get_project_root()
    return get_storage_layout(root).primary_archive_dir


def get_state_dir() -> Path:
    """Get session state directory: <project_root>/.codex/handoffs/.session-state/

    State files are ephemeral bridge objects (24h TTL) linking resume to save
    via the chain protocol. The plugin writes filesystem artifacts only and
    does not add gitignore rules; tracking is host-repository policy.
    """
    root, _ = get_project_root()
    return get_storage_layout(root).primary_state_dir


def get_legacy_handoffs_dir() -> Path:
    """Get legacy handoffs directory: <project_root>/docs/handoffs/

    Used by search, triage, and load for fallback discovery of
    pre-migration handoff files.
    """
    root, _ = get_project_root()
    return get_storage_layout(root).legacy_active_dir
