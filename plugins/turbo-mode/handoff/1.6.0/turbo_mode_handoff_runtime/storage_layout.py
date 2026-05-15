"""Storage layout paths for Handoff runtime state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageLayout:
    project_root: Path
    primary_active_dir: Path
    primary_archive_dir: Path
    primary_state_dir: Path
    legacy_active_dir: Path
    legacy_archive_dir: Path
    legacy_state_dir: Path
    previous_primary_hidden_archive_dir: Path


def get_storage_layout(project_root: Path) -> StorageLayout:
    """Return the post-cutover Handoff storage layout for a project root."""
    root = project_root.resolve()
    primary = root / ".codex" / "handoffs"
    legacy = root / "docs" / "handoffs"
    return StorageLayout(
        project_root=root,
        primary_active_dir=primary,
        primary_archive_dir=primary / "archive",
        primary_state_dir=primary / ".session-state",
        legacy_active_dir=legacy,
        legacy_archive_dir=legacy / "archive",
        legacy_state_dir=legacy / ".session-state",
        previous_primary_hidden_archive_dir=primary / ".archive",
    )
