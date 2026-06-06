from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent


def _run_shell(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    if shutil.which("zsh") is None:
        pytest.skip("zsh not available")
    return subprocess.run(
        ["/bin/zsh", "-lc", command],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)


def _residue_snapshot(root: Path) -> set[str]:
    snapshot: set[str] = set()
    for pattern in [
        ".venv",
        ".pytest_cache",
        ".DS_Store",
        "scripts/__pycache__",
        "hooks/__pycache__",
    ]:
        for match in root.glob(pattern):
            snapshot.add(str(match.relative_to(root)))
    return snapshot


def test_search_command_runs_from_normal_repo_cwd(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    before = _residue_snapshot(PLUGIN_ROOT)
    handoffs = tmp_path / "docs" / "handoffs"
    handoffs.mkdir(parents=True)
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff"
    command = (
        f'PLUGIN_ROOT="{PLUGIN_ROOT}" '
        f'PROJECT_ROOT="{tmp_path}" '
        f"PYTHONDONTWRITEBYTECODE=1 "
        f'UV_PROJECT_ENVIRONMENT="{runtime_env}" '
        f'uv run --project "{PLUGIN_ROOT}/pyproject.toml" '
        f'python "{PLUGIN_ROOT}/scripts/search.py" nonexistent_query_xyz'
    )
    result = _run_shell(command, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["query"] == "nonexistent_query_xyz"
    assert _residue_snapshot(PLUGIN_ROOT) == before


def test_distill_command_runs_from_normal_repo_cwd(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    before = _residue_snapshot(PLUGIN_ROOT)
    handoff_dir = tmp_path / "docs" / "handoffs"
    handoff_dir.mkdir(parents=True)
    handoff = handoff_dir / "2026-05-02_00-00_test.md"
    handoff.write_text(
        "---\n"
        'title: "Test"\n'
        "date: 2026-05-02\n"
        "type: handoff\n"
        "session_id: sess-1\n"
        "---\n\n"
        "## Decisions\n\n"
        "### Choice\n\n"
        "**Choice:** Use a probe.\n\n"
        "**Driver:** Need runtime proof.\n",
        encoding="utf-8",
    )
    learnings = tmp_path / "docs" / "learnings" / "learnings.md"
    learnings.parent.mkdir(parents=True)
    learnings.write_text("# Learnings\n", encoding="utf-8")
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff"
    command = (
        f'PLUGIN_ROOT="{PLUGIN_ROOT}" '
        f'PROJECT_ROOT="{tmp_path}" '
        f"PYTHONDONTWRITEBYTECODE=1 "
        f'UV_PROJECT_ENVIRONMENT="{runtime_env}" '
        f'uv run --project "{PLUGIN_ROOT}/pyproject.toml" '
        f'python "{PLUGIN_ROOT}/scripts/distill.py" "{handoff}" --learnings "{learnings}"'
    )
    result = _run_shell(command, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["handoff_path"] == str(handoff)
    assert _residue_snapshot(PLUGIN_ROOT) == before
