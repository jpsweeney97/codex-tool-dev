"""Read-only storage authority for Handoff runtime paths."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class StorageLocation(StrEnum):
    PRIMARY_ACTIVE = "primary_active"
    PRIMARY_ARCHIVE = "primary_archive"
    PRIMARY_STATE = "primary_state"
    LEGACY_ACTIVE = "legacy_active"
    LEGACY_ARCHIVE = "legacy_archive"
    LEGACY_STATE = "legacy_state"
    PREVIOUS_PRIMARY_HIDDEN_ARCHIVE = "previous_primary_hidden_archive"
    UNKNOWN = "unknown"


class SelectionEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED_POLICY_CONFLICT = "blocked-policy-conflict"
    BLOCKED_TRACKED_SOURCE = "blocked-tracked-source"
    INVALID = "invalid"
    SKIPPED = "skipped"
    NOT_ACTIVE_SELECTION_INPUT = "not-active-selection-input"
    NOT_HISTORY_SEARCH_INPUT = "not-history-search-input"


FILENAME_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2})_.+\.md$")


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


@dataclass(frozen=True)
class HandoffCandidate:
    path: Path
    storage_location: StorageLocation
    artifact_class: str
    selection_eligibility: SelectionEligibility
    source_git_visibility: str
    source_fs_status: str
    filename_timestamp: str | None = None
    skip_reason: str | None = None


@dataclass(frozen=True)
class HandoffInventory:
    project_root: Path
    scan_mode: str
    candidates: list[HandoffCandidate]


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


def discover_handoff_inventory(project_root: Path, *, scan_mode: str) -> HandoffInventory:
    """Discover Handoff markdown candidates for a read-only scan mode."""
    layout = get_storage_layout(project_root)
    candidates: list[HandoffCandidate] = []
    if scan_mode == "active-selection":
        roots = (
            (layout.primary_active_dir, StorageLocation.PRIMARY_ACTIVE),
            (layout.legacy_active_dir, StorageLocation.LEGACY_ACTIVE),
            (layout.legacy_archive_dir, StorageLocation.LEGACY_ARCHIVE),
        )
    elif scan_mode == "history-search":
        roots = (
            (layout.primary_active_dir, StorageLocation.PRIMARY_ACTIVE),
            (layout.primary_archive_dir, StorageLocation.PRIMARY_ARCHIVE),
            (layout.legacy_active_dir, StorageLocation.LEGACY_ACTIVE),
            (layout.legacy_archive_dir, StorageLocation.LEGACY_ARCHIVE),
            (
                layout.previous_primary_hidden_archive_dir,
                StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
            ),
        )
    else:
        raise ValueError(
            f"discover_handoff_inventory failed: unsupported scan mode. Got: {scan_mode!r:.100}"
        )

    for root, location in roots:
        candidates.extend(
            _discover_markdown(
                project_root=layout.project_root,
                root=root,
                location=location,
                scan_mode=scan_mode,
            )
        )
    candidates.sort(key=lambda candidate: str(candidate.path))
    return HandoffInventory(
        project_root=layout.project_root,
        scan_mode=scan_mode,
        candidates=candidates,
    )


def eligible_active_candidates(inventory: HandoffInventory) -> list[HandoffCandidate]:
    """Return active-selection candidates in implicit load/list/distill order."""
    candidates = [
        candidate
        for candidate in inventory.candidates
        if candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
        and candidate.filename_timestamp is not None
    ]
    ordered = sorted(candidates, key=lambda candidate: _absolute_path_key(candidate.path))
    ordered = sorted(
        ordered,
        key=lambda candidate: _source_precedence(candidate.storage_location),
        reverse=True,
    )
    return sorted(
        ordered,
        key=lambda candidate: candidate.filename_timestamp or "",
        reverse=True,
    )


def _discover_markdown(
    *,
    project_root: Path,
    root: Path,
    location: StorageLocation,
    scan_mode: str,
) -> list[HandoffCandidate]:
    if not root.exists() or not root.is_dir():
        return []
    return [
        _candidate_for_path(
            project_root=project_root,
            path=path,
            location=location,
            scan_mode=scan_mode,
        )
        for path in sorted(root.rglob("*.md"))
    ]


def _candidate_for_path(
    *,
    project_root: Path,
    path: Path,
    location: StorageLocation,
    scan_mode: str,
) -> HandoffCandidate:
    git_visibility = _git_visibility(project_root, path)
    fs_status = _fs_status(path)
    filename_timestamp = _filename_timestamp(path)
    skip_reason = _skip_reason(root_for_location(project_root, location), path, location)
    if skip_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="skipped-handoff-artifact",
            selection_eligibility=SelectionEligibility.SKIPPED,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            filename_timestamp=filename_timestamp,
            skip_reason=skip_reason,
        )
    invalid_reason = _invalid_reason(path=path, location=location, scan_mode=scan_mode)
    if invalid_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="invalid-handoff-artifact",
            selection_eligibility=SelectionEligibility.INVALID,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            filename_timestamp=filename_timestamp,
            skip_reason=invalid_reason,
        )
    artifact_class = _artifact_class(location=location, path=path, git_visibility=git_visibility)
    eligibility, reason = _eligibility(
        location=location,
        artifact_class=artifact_class,
        git_visibility=git_visibility,
        scan_mode=scan_mode,
    )
    return HandoffCandidate(
        path=path.resolve(),
        storage_location=location,
        artifact_class=artifact_class,
        selection_eligibility=eligibility,
        source_git_visibility=git_visibility,
        source_fs_status=fs_status,
        filename_timestamp=filename_timestamp,
        skip_reason=reason,
    )


def root_for_location(project_root: Path, location: StorageLocation) -> Path:
    layout = get_storage_layout(project_root)
    if location == StorageLocation.PRIMARY_ACTIVE:
        return layout.primary_active_dir
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return layout.primary_archive_dir
    if location == StorageLocation.LEGACY_ACTIVE:
        return layout.legacy_active_dir
    if location == StorageLocation.LEGACY_ARCHIVE:
        return layout.legacy_archive_dir
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return layout.previous_primary_hidden_archive_dir
    return layout.primary_active_dir


def _artifact_class(*, location: StorageLocation, path: Path, git_visibility: str) -> str:
    if location == StorageLocation.PRIMARY_ACTIVE and git_visibility == "tracked-conflict":
        return "tracked-primary-active-source"
    if location == StorageLocation.PRIMARY_ACTIVE:
        return "primary-active-handoff"
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return "primary-archive-handoff"
    if location == StorageLocation.LEGACY_ARCHIVE:
        return "legacy-operational-archive"
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return "previous-primary-hidden-archive"
    if location == StorageLocation.LEGACY_ACTIVE:
        if git_visibility in {"ignored", "untracked"} and _looks_like_current_contract(path):
            return "policy-conflict-artifact"
        if git_visibility == "tracked-conflict":
            return "tracked-durable-handoff-artifact"
        return "policy-conflict-artifact"
    return "unknown"


def _eligibility(
    *,
    location: StorageLocation,
    artifact_class: str,
    git_visibility: str,
    scan_mode: str,
) -> tuple[SelectionEligibility, str | None]:
    if scan_mode == "history-search":
        if location in {
            StorageLocation.PRIMARY_ACTIVE,
            StorageLocation.PRIMARY_ARCHIVE,
            StorageLocation.LEGACY_ARCHIVE,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        }:
            return SelectionEligibility.ELIGIBLE, None
        if (
            location == StorageLocation.LEGACY_ACTIVE
            and artifact_class != "policy-conflict-artifact"
        ):
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.BLOCKED_POLICY_CONFLICT,
            "legacy active markdown lacks accepted external origin proof",
        )
    if location == StorageLocation.PRIMARY_ACTIVE:
        if git_visibility == "tracked-conflict":
            return (
                SelectionEligibility.BLOCKED_TRACKED_SOURCE,
                "tracked primary runtime source must not be moved or suppressed",
            )
        return SelectionEligibility.ELIGIBLE, None
    if location == StorageLocation.LEGACY_ACTIVE:
        return (
            SelectionEligibility.BLOCKED_POLICY_CONFLICT,
            "legacy active markdown lacks accepted external origin proof",
        )
    return (
        SelectionEligibility.NOT_ACTIVE_SELECTION_INPUT,
        "storage location is not active-selection input",
    )


def _looks_like_current_contract(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---", 4)
    if end == -1:
        return False
    keys = set()
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            keys.add(line.split(":", 1)[0].strip())
    return {"project", "created_at", "session_id", "type"} <= keys


def _skip_reason(root: Path, path: Path, location: StorageLocation) -> str | None:
    if path.name.startswith("."):
        return "hidden_basename"
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "path_escape"
    if ".session-state" in relative.parts:
        return "state_directory"
    if path.is_symlink():
        return "symlink"
    if path.parent != root:
        return "nested_file"
    if location == StorageLocation.LEGACY_ARCHIVE:
        return None
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return None
    return None


def _invalid_reason(*, path: Path, location: StorageLocation, scan_mode: str) -> str | None:
    if scan_mode == "active-selection" and _filename_timestamp(path) is None:
        return "invalid_filename_timestamp"
    if scan_mode == "history-search" and _archive_history_location(location):
        return None
    if not _looks_like_current_contract(path):
        return "invalid_document"
    return None


def _archive_history_location(location: StorageLocation) -> bool:
    return location in {
        StorageLocation.PRIMARY_ARCHIVE,
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }


def _filename_timestamp(path: Path) -> str | None:
    match = FILENAME_TIMESTAMP_RE.match(path.name)
    if match is None:
        return None
    return match.group("timestamp")


def _source_precedence(location: StorageLocation) -> int:
    if location == StorageLocation.PRIMARY_ACTIVE:
        return 2
    if location == StorageLocation.LEGACY_ACTIVE:
        return 1
    return 0


def _absolute_path_key(path: Path) -> str:
    return str(path.resolve())


def _fs_status(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if not path.exists():
        return "missing"
    if path.is_file():
        return "regular-file"
    if path.is_dir():
        return "directory"
    return "non-regular"


def _git_visibility(project_root: Path, path: Path) -> str:
    if not _inside_git_worktree(project_root):
        return "not-git-repo"
    rel = path.resolve().relative_to(project_root.resolve()).as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode == 0:
        return "tracked-conflict"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", rel],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if ignored.returncode == 0:
        return "ignored"
    return "untracked"


def _inside_git_worktree(project_root: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"
