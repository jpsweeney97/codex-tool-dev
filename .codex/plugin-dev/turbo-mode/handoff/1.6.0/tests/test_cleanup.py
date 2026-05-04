"""Tests for cleanup.py — SessionStart hook script."""

import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from scripts.cleanup import (
    _trash,
    main,
    prune_old_state_files,
)


class TestTrash:
    """Tests for _trash helper."""

    def test_success_returns_true(self, tmp_path: Path) -> None:
        target = tmp_path / "file.md"
        target.write_text("content")
        with patch("scripts.cleanup.subprocess.run") as mock_run:
            assert _trash(target) is True
            mock_run.assert_called_once_with(
                ["trash", str(target)],
                capture_output=True,
                timeout=5,
                check=True,
            )

    def test_binary_not_found_returns_false(self, tmp_path: Path) -> None:
        target = tmp_path / "file.md"
        with patch(
            "scripts.cleanup.subprocess.run", side_effect=FileNotFoundError
        ):
            assert _trash(target) is False

    def test_trash_failure_returns_false(self, tmp_path: Path) -> None:
        target = tmp_path / "file.md"
        with patch(
            "scripts.cleanup.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "trash"),
        ):
            assert _trash(target) is False

    def test_timeout_returns_false(self, tmp_path: Path) -> None:
        target = tmp_path / "file.md"
        with patch(
            "scripts.cleanup.subprocess.run",
            side_effect=subprocess.TimeoutExpired("trash", 5),
        ):
            assert _trash(target) is False

    def test_oserror_returns_false(self, tmp_path: Path) -> None:
        """R4: PermissionError (OSError subclass) must not escape _trash."""
        target = tmp_path / "file.md"
        with patch(
            "scripts.cleanup.subprocess.run",
            side_effect=PermissionError("not executable"),
        ):
            assert _trash(target) is False


class TestPruneOldStateFiles:
    """Tests for prune_old_state_files."""

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        assert prune_old_state_files(state_dir=tmp_path / "nope") == []

    def test_old_state_files_deleted(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "session-state"
        state_dir.mkdir()
        old = state_dir / "handoff-abc123"
        old.write_text("/some/archive/path")
        old_time = time.time() - (25 * 60 * 60)  # 25 hours ago
        os.utime(old, (old_time, old_time))
        with patch("scripts.cleanup._trash", return_value=True):
            result = prune_old_state_files(max_age_hours=24, state_dir=state_dir)
        assert result == [old]

    def test_failed_trash_not_in_deleted(self, tmp_path: Path) -> None:
        """C1 regression: state files not trashed must not appear in deleted list (B3)."""
        state_dir = tmp_path / "session-state"
        state_dir.mkdir()
        old = state_dir / "handoff-abc123"
        old.write_text("/some/archive/path")
        old_time = time.time() - (25 * 60 * 60)
        os.utime(old, (old_time, old_time))
        with patch("scripts.cleanup._trash", return_value=False):
            result = prune_old_state_files(max_age_hours=24, state_dir=state_dir)
        assert result == [], "State file should not be in deleted list when trash fails"

    def test_recent_state_files_not_deleted(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "session-state"
        state_dir.mkdir()
        recent = state_dir / "handoff-def456"
        recent.write_text("/some/archive/path")
        with patch("scripts.cleanup._trash") as mock_trash:
            result = prune_old_state_files(max_age_hours=24, state_dir=state_dir)
        assert result == []
        mock_trash.assert_not_called()

    def test_non_handoff_files_ignored(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "session-state"
        state_dir.mkdir()
        other = state_dir / "other-file"
        other.write_text("content")
        old_time = time.time() - (25 * 60 * 60)
        os.utime(other, (old_time, old_time))
        with patch("scripts.cleanup._trash") as mock_trash:
            result = prune_old_state_files(max_age_hours=24, state_dir=state_dir)
        assert result == []
        mock_trash.assert_not_called()

    def test_stat_oserror_skipped(self, tmp_path: Path) -> None:
        """T2: stat() failure on individual state files doesn't crash the function."""
        state_dir = tmp_path / "session-state"
        state_dir.mkdir()
        target = state_dir / "handoff-abc123"
        target.write_text("content")
        target_str = str(target)

        orig_stat = Path.stat
        hit = False

        def selective_stat(self_path: Path, *args: object, **kwargs: object) -> os.stat_result:
            nonlocal hit
            if str(self_path) == target_str:
                hit = True
                raise OSError("permission denied")
            return orig_stat(self_path, *args, **kwargs)

        with patch("scripts.cleanup.Path.stat", autospec=True, side_effect=selective_stat):
            result = prune_old_state_files(max_age_hours=24, state_dir=state_dir)
        assert hit is True, "Patch must exercise the target file's stat() path"
        assert result == []

    def test_default_state_dir_uses_project_local(self, tmp_path: Path) -> None:
        """T3: When state_dir is None, resolves to <project_root>/docs/handoffs/.session-state."""
        state_dir = tmp_path / "docs" / "handoffs" / ".session-state"
        state_dir.mkdir(parents=True)
        old = state_dir / "handoff-abc123"
        old.write_text("content")
        old_time = time.time() - (25 * 60 * 60)
        os.utime(old, (old_time, old_time))
        with (
            patch("scripts.cleanup.get_state_dir", return_value=state_dir),
            patch("scripts.cleanup._trash", return_value=True) as mock_trash,
        ):
            result = prune_old_state_files(max_age_hours=24)
        assert result == [old]
        mock_trash.assert_called_once_with(old)


class TestMain:
    """Tests for main entry point."""

    def test_always_returns_zero(self) -> None:
        """main() must return 0 even when internals raise."""
        with patch("scripts.cleanup.prune_old_state_files", side_effect=RuntimeError("unexpected")):
            assert main() == 0

    def test_calls_prune_state_files_only(self) -> None:
        """main() calls prune_old_state_files once. No handoff pruning."""
        with patch("scripts.cleanup.prune_old_state_files") as mock_state:
            result = main()
        assert result == 0
        mock_state.assert_called_once_with(max_age_hours=24)
