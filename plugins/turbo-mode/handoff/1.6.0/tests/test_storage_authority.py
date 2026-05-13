from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.storage_authority import (
    SelectionEligibility,
    StorageLocation,
    discover_handoff_inventory,
    get_storage_layout,
)


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)


def _handoff(path: Path, title: str = "Test") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "date: 2026-05-13\n"
        'time: "12:00"\n'
        'created_at: "2026-05-13T16:00:00Z"\n'
        "session_id: test-session\n"
        "project: demo\n"
        f'title: "{title}"\n'
        "type: summary\n"
        "---\n\n"
        "## Goal\n\n"
        "Test storage authority.\n",
        encoding="utf-8",
    )
    return path


def test_storage_layout_uses_codex_handoffs_as_primary(tmp_path: Path) -> None:
    layout = get_storage_layout(tmp_path)

    assert layout.primary_active_dir == tmp_path / ".codex" / "handoffs"
    assert layout.primary_archive_dir == tmp_path / ".codex" / "handoffs" / "archive"
    assert layout.primary_state_dir == tmp_path / ".codex" / "handoffs" / ".session-state"
    assert layout.legacy_active_dir == tmp_path / "docs" / "handoffs"
    assert layout.legacy_archive_dir == tmp_path / "docs" / "handoffs" / "archive"
    assert (
        layout.previous_primary_hidden_archive_dir
        == tmp_path / ".codex" / "handoffs" / ".archive"
    )


def test_active_selection_blocks_unproven_legacy_active_markdown(tmp_path: Path) -> None:
    _git_init(tmp_path)
    primary = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md", "Primary")
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-01_legacy.md", "Legacy")
    legacy_archive = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-02_archive.md",
        "Archive",
    )

    inventory = discover_handoff_inventory(tmp_path, scan_mode="active-selection")

    by_path = {candidate.path: candidate for candidate in inventory.candidates}
    assert by_path[primary].storage_location == StorageLocation.PRIMARY_ACTIVE
    assert by_path[primary].selection_eligibility == SelectionEligibility.ELIGIBLE
    assert by_path[legacy].storage_location == StorageLocation.LEGACY_ACTIVE
    assert by_path[legacy].artifact_class == "policy-conflict-artifact"
    assert by_path[legacy].selection_eligibility == SelectionEligibility.BLOCKED_POLICY_CONFLICT
    assert by_path[legacy_archive].storage_location == StorageLocation.LEGACY_ARCHIVE
    assert (
        by_path[legacy_archive].selection_eligibility
        == SelectionEligibility.NOT_ACTIVE_SELECTION_INPUT
    )


def test_history_search_includes_archive_tiers_but_not_state(tmp_path: Path) -> None:
    primary = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md", "Primary")
    primary_archive = _handoff(
        tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_11-00_primary-archive.md",
        "Primary Archive",
    )
    legacy_archive = _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_10-00_legacy-archive.md",
        "Legacy Archive",
    )
    previous_hidden = _handoff(
        tmp_path / ".codex" / "handoffs" / ".archive" / "2026-05-13_09-00_hidden.md",
        "Hidden Archive",
    )
    state = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")

    inventory = discover_handoff_inventory(tmp_path, scan_mode="history-search")
    paths = {
        candidate.path
        for candidate in inventory.candidates
        if candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
    }

    assert primary in paths
    assert primary_archive in paths
    assert legacy_archive in paths
    assert previous_hidden in paths
    assert state not in paths


def test_tracked_primary_active_source_is_blocked(tmp_path: Path) -> None:
    _git_init(tmp_path)
    primary = _handoff(tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md", "Primary")
    subprocess.run(["git", "add", str(primary.relative_to(tmp_path))], cwd=tmp_path, check=True)

    inventory = discover_handoff_inventory(tmp_path, scan_mode="active-selection")

    candidate = next(candidate for candidate in inventory.candidates if candidate.path == primary)
    assert candidate.source_git_visibility == "tracked-conflict"
    assert candidate.selection_eligibility == SelectionEligibility.BLOCKED_TRACKED_SOURCE
