from __future__ import annotations

from pathlib import Path

from turbo_mode_handoff_runtime.storage_layout import get_storage_layout


def test_storage_layout_uses_codex_handoffs_as_primary(tmp_path: Path) -> None:
    layout = get_storage_layout(tmp_path)

    assert layout.primary_active_dir == tmp_path / ".codex" / "handoffs"
    assert layout.primary_archive_dir == tmp_path / ".codex" / "handoffs" / "archive"
    assert layout.primary_state_dir == tmp_path / ".codex" / "handoffs" / ".session-state"
    assert layout.legacy_active_dir == tmp_path / "docs" / "handoffs"
    assert layout.legacy_archive_dir == tmp_path / "docs" / "handoffs" / "archive"
    assert (
        layout.previous_primary_hidden_archive_dir == tmp_path / ".codex" / "handoffs" / ".archive"
    )
