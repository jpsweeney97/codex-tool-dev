from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from turbo_mode_handoff_runtime.plugin_siblings import find_sibling_plugin_root


def _make_plugin(root: Path, name: str) -> None:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        f'{{"name":"{name}","version":"0.1.0"}}',
        encoding="utf-8",
    )


def test_finds_ticket_root_in_plugin_dev_layout(tmp_path: Path) -> None:
    handoff_root = tmp_path / "plugin-dev" / "turbo-mode" / "handoff" / "1.6.0"
    ticket_root = tmp_path / "plugin-dev" / "turbo-mode" / "ticket" / "1.4.0"
    _make_plugin(handoff_root, "handoff")
    _make_plugin(ticket_root, "ticket")
    assert find_sibling_plugin_root(handoff_root, "ticket") == ticket_root


def test_rejects_multiple_ticket_versions(tmp_path: Path) -> None:
    handoff_root = tmp_path / "cache" / "turbo-mode" / "handoff" / "1.6.0"
    _make_plugin(handoff_root, "handoff")
    _make_plugin(tmp_path / "cache" / "turbo-mode" / "ticket" / "1.4.0", "ticket")
    _make_plugin(tmp_path / "cache" / "turbo-mode" / "ticket" / "1.5.0", "ticket")
    with pytest.raises(RuntimeError, match="Expected exactly one installed ticket version"):
        find_sibling_plugin_root(handoff_root, "ticket")


def test_cli_field_output(tmp_path: Path) -> None:
    handoff_root = tmp_path / "plugin-dev" / "turbo-mode" / "handoff" / "1.6.0"
    ticket_root = tmp_path / "plugin-dev" / "turbo-mode" / "ticket" / "1.4.0"
    _make_plugin(handoff_root, "handoff")
    _make_plugin(ticket_root, "ticket")
    script = Path(__file__).parent.parent / "scripts" / "plugin_siblings.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--plugin-root",
            str(handoff_root),
            "--sibling",
            "ticket",
            "--field",
            "plugin_root",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(ticket_root)
