"""Import bootstrap for direct Handoff script execution."""

from __future__ import annotations

import sys
import types
from pathlib import Path


def plugin_script_dir() -> Path:
    """Return this plugin's script directory."""
    return Path(__file__).resolve().parent


def plugin_root() -> Path:
    """Return this plugin root."""
    return plugin_script_dir().parent


def ensure_plugin_scripts_package() -> None:
    """Ensure imports from scripts.* resolve to this plugin's scripts directory first."""
    script_dir = str(plugin_script_dir())
    plugin_parent = str(plugin_root())
    if plugin_parent not in sys.path:
        sys.path.insert(0, plugin_parent)
    scripts_pkg = sys.modules.get("scripts")
    if scripts_pkg is None or not hasattr(scripts_pkg, "__path__"):
        scripts_pkg = types.ModuleType("scripts")
        scripts_pkg.__path__ = [script_dir]  # type: ignore[attr-defined]
        sys.modules["scripts"] = scripts_pkg
        return
    package_path = list(scripts_pkg.__path__)  # type: ignore[attr-defined]
    package_path = [entry for entry in package_path if entry != script_dir]
    package_path.insert(0, script_dir)
    scripts_pkg.__path__ = package_path  # type: ignore[attr-defined]


ensure_plugin_scripts_package()
