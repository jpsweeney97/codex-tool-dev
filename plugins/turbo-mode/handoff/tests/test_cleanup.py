"""Tests for cleanup.py - state-file cleanup helper."""

from unittest.mock import patch

from turbo_mode_handoff_runtime.cleanup import main


class TestMain:
    """Tests for main entry point."""

    def test_always_returns_zero(self, capsys) -> None:
        """main() must return 0 even when internals raise."""
        with patch(
            "turbo_mode_handoff_runtime.cleanup.prune_old_state_files",
            side_effect=RuntimeError("unexpected"),
        ):
            assert main() == 0
        captured = capsys.readouterr()
        assert "state cleanup warning: ttl prune failed: unexpected" in captured.err

    def test_calls_prune_state_files_only(self) -> None:
        """main() calls prune_old_state_files once. No handoff pruning."""
        with patch("turbo_mode_handoff_runtime.cleanup.prune_old_state_files") as mock_state:
            result = main()
        assert result == 0
        mock_state.assert_called_once_with(max_age_hours=24)
