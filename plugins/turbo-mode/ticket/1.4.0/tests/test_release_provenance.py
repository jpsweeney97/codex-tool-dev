"""Release provenance checks for installed Ticket runtime surfaces."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"


def test_guard_hook_manifest_command_is_cache_local() -> None:
    """The composed Turbo Mode gate must not execute Ticket hooks from plugin-dev."""
    payload = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for entries in payload["hooks"].values()
        for entry in entries
        for hook in entry["hooks"]
    ]

    assert commands == [
        "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py"
    ]
    assert all("/plugin-dev/" not in command for command in commands)


def test_user_entrypoint_with_dash_b_does_not_create_cache_pycache(tmp_path: Path) -> None:
    """The documented python3 -B entrypoint contract must not write bytecode residue."""
    package_root = tmp_path / "ticket"
    shutil.copytree(PLUGIN_ROOT / "scripts", package_root / "scripts")
    env = os.environ.copy()
    env.pop("PYTHONDONTWRITEBYTECODE", None)

    result = subprocess.run(
        [sys.executable, "-B", str(package_root / "scripts" / "ticket_engine_user.py")],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )

    assert result.returncode != 0
    assert not list((package_root / "scripts").glob("__pycache__"))
