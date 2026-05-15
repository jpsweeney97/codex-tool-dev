"""Tests for project_paths.py — shared path utilities."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from turbo_mode_handoff_runtime.project_paths import (
    get_archive_dir,
    get_handoffs_dir,
    get_legacy_handoffs_dir,
    get_project_name,
    get_project_root,
)


class TestGetProjectRoot:
    """Tests for get_project_root."""

    def test_returns_git_root_path(self) -> None:
        with patch("turbo_mode_handoff_runtime.project_paths.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "/Users/jp/Projects/myproject\n"
            root, source = get_project_root()
        assert root == Path("/Users/jp/Projects/myproject")
        assert source == "git"

    def test_falls_back_to_cwd(self) -> None:
        with patch("turbo_mode_handoff_runtime.project_paths.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            root, source = get_project_root()
        assert root == Path.cwd()
        assert source == "cwd"

    def test_git_not_found_falls_back_to_cwd(self) -> None:
        with patch("turbo_mode_handoff_runtime.project_paths.subprocess.run", side_effect=FileNotFoundError):
            root, source = get_project_root()
            assert root == Path.cwd()
            assert source == "cwd"

    def test_timeout_falls_back_to_cwd(self) -> None:
        with patch(
            "turbo_mode_handoff_runtime.project_paths.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            root, source = get_project_root()
            assert root == Path.cwd()
            assert source == "cwd"

    def test_oserror_falls_back_to_cwd(self) -> None:
        with patch("turbo_mode_handoff_runtime.project_paths.subprocess.run", side_effect=OSError("disk error")):
            root, source = get_project_root()
            assert root == Path.cwd()
            assert source == "cwd"

    def test_exception_logs_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("turbo_mode_handoff_runtime.project_paths.subprocess.run", side_effect=FileNotFoundError):
            get_project_root()
        assert "Warning: git project detection failed" in capsys.readouterr().err


class TestGetProjectName:
    """Tests for get_project_name — delegates to get_project_root."""

    def test_returns_basename_of_root(self) -> None:
        with patch(
            "turbo_mode_handoff_runtime.project_paths.get_project_root",
            return_value=(Path("/Users/jp/Projects/myproject"), "git"),
        ):
            name, source = get_project_name()
        assert name == "myproject"
        assert source == "git"

    def test_falls_back_to_cwd_name(self) -> None:
        with patch(
            "turbo_mode_handoff_runtime.project_paths.get_project_root",
            return_value=(Path.cwd(), "cwd"),
        ):
            name, source = get_project_name()
        assert name == Path.cwd().name
        assert source == "cwd"


class TestGetHandoffsDir:
    """Tests for get_handoffs_dir."""

    def test_returns_primary_codex_handoffs_path(self) -> None:
        with patch(
            "turbo_mode_handoff_runtime.project_paths.get_project_root",
            return_value=(Path("/Users/jp/Projects/myproject"), "git"),
        ):
            result = get_handoffs_dir()
        assert result == Path("/Users/jp/Projects/myproject") / ".codex" / "handoffs"


class TestGetArchiveDir:
    def test_returns_archive_subdir(self) -> None:
        result = get_archive_dir()
        assert result.name == "archive"
        assert result.parent.name == "handoffs"

    def test_is_child_of_handoffs_dir(self) -> None:
        archive = get_archive_dir()
        handoffs = get_handoffs_dir()
        assert archive.parent == handoffs


class TestGetLegacyHandoffsDir:
    """Tests for get_legacy_handoffs_dir — fallback path for pre-migration files."""

    def test_returns_docs_handoffs_path(self) -> None:
        with patch(
            "turbo_mode_handoff_runtime.project_paths.get_project_root",
            return_value=(Path("/Users/jp/Projects/myproject"), "git"),
        ):
            result = get_legacy_handoffs_dir()
        assert result == Path("/Users/jp/Projects/myproject") / "docs" / "handoffs"
