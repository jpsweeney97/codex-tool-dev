from __future__ import annotations

import subprocess
from pathlib import Path

from turbo_mode_handoff_runtime.storage_inspection import fs_status, git_visibility, is_relative_to


def test_is_relative_to_returns_true_for_children_and_false_for_siblings(tmp_path: Path) -> None:
    child = tmp_path / "child" / "artifact.md"
    sibling = tmp_path.parent / "sibling" / "artifact.md"

    assert is_relative_to(child, tmp_path)
    assert not is_relative_to(sibling, tmp_path)


def test_fs_status_covers_missing_file_directory_and_symlink(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"
    regular = tmp_path / "regular.md"
    regular.write_text("body", encoding="utf-8")
    directory = tmp_path / "dir"
    directory.mkdir()
    symlink = tmp_path / "regular-link.md"
    symlink.symlink_to(regular)

    assert fs_status(missing) == "missing"
    assert fs_status(regular) == "regular-file"
    assert fs_status(directory) == "directory"
    assert fs_status(symlink) == "symlink"


def test_git_visibility_reports_not_git_repo_outside_worktree(tmp_path: Path) -> None:
    handoff = tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text("---\ntitle: Primary\n---\n", encoding="utf-8")

    assert git_visibility(tmp_path, handoff) == "not-git-repo"


def test_git_visibility_reports_tracked_conflict(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    handoff = tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text("---\ntitle: Primary\n---\n", encoding="utf-8")
    subprocess.run(["git", "add", str(handoff.relative_to(tmp_path))], cwd=tmp_path, check=True)

    assert git_visibility(tmp_path, handoff) == "tracked-conflict"
