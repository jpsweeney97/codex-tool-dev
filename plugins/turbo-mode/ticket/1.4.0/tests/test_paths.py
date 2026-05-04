"""Tests for marker-based project-root resolution and tickets_dir resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

import scripts.ticket_paths as ticket_paths
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir


class TestDiscoverProjectRoot:
    """Marker-based project root discovery."""

    def test_finds_git_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir(exist_ok=True)
        nested = tmp_path / "src" / "pkg"
        nested.mkdir(parents=True)
        root = discover_project_root(nested)
        assert root == tmp_path

    def test_finds_codex_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".codex").mkdir()
        nested = tmp_path / "src" / "deep" / "pkg"
        nested.mkdir(parents=True)
        root = discover_project_root(nested)
        assert root == tmp_path

    def test_finds_git_file_worktree(self, tmp_path: Path) -> None:
        """A .git file (worktree) is also a valid marker."""
        (tmp_path / ".git").write_text("gitdir: /some/other/.git/worktrees/x")
        nested = tmp_path / "src"
        nested.mkdir()
        root = discover_project_root(nested)
        assert root == tmp_path

    def test_prefers_nearest_ancestor(self, tmp_path: Path) -> None:
        """If multiple ancestors have markers, choose nearest."""
        (tmp_path / ".git").mkdir(exist_ok=True)
        inner = tmp_path / "subproject"
        inner.mkdir()
        (inner / ".codex").mkdir()
        deep = inner / "src"
        deep.mkdir()
        root = discover_project_root(deep)
        assert root == inner

    def test_returns_none_without_markers(self, tmp_path: Path) -> None:
        nested = tmp_path / "no" / "markers" / "here"
        nested.mkdir(parents=True)
        root = discover_project_root(nested)
        assert root is None

    def test_cwd_itself_is_root(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir(exist_ok=True)
        root = discover_project_root(tmp_path)
        assert root == tmp_path

    def test_resolves_symlink_before_marker_lookup(self, tmp_path: Path) -> None:
        """Symlinked start paths resolve to the canonical project root."""
        (tmp_path / ".git").mkdir(exist_ok=True)
        real_nested = tmp_path / "real" / "src"
        real_nested.mkdir(parents=True)
        symlink_root = tmp_path.parent / f"{tmp_path.name}-link"
        symlink_root.symlink_to(tmp_path, target_is_directory=True)
        symlink_nested = symlink_root / "real" / "src"

        root = discover_project_root(symlink_nested)
        assert root == tmp_path.resolve()


class TestResolveTicketsDir:
    def test_default_path_used_when_none(self, tmp_path: Path) -> None:
        resolved, err = resolve_tickets_dir(None, project_root=tmp_path)
        assert err is None
        assert resolved == (tmp_path / "docs" / "tickets").resolve()

    def test_rejects_path_outside_project_root(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside-tickets"
        resolved, err = resolve_tickets_dir(str(outside), project_root=tmp_path)
        assert resolved is None
        assert err is not None
        assert "escapes project root" in err

    def test_rejects_non_string_type(self, tmp_path: Path) -> None:
        resolved, err = resolve_tickets_dir(123, project_root=tmp_path)
        assert resolved is None
        assert err is not None
        assert "expected string path" in err

    def test_resolution_error_returns_validation_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_resolve(_: Path) -> Path:
            raise OSError("permission denied")

        monkeypatch.setattr(ticket_paths.Path, "resolve", fail_resolve)
        resolved, err = resolve_tickets_dir("docs/tickets", project_root=tmp_path)
        assert resolved is None
        assert err is not None
        assert "resolution failed" in err
