"""Storage authority for handoff discovery and selection decisions.

This module owns handoff discovery, candidate classification, active-selection
ordering, history deduplication, and legacy-active policy checks. Storage path
arithmetic lives in ``storage_layout.py`` and chain-state lifecycle behavior
lives in ``chain_state.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from turbo_mode_handoff_runtime import storage_layout as _storage_layout
from turbo_mode_handoff_runtime.storage_inspection import (
    fs_status as _fs_status,
)
from turbo_mode_handoff_runtime.storage_inspection import (
    git_visibility as _git_visibility,
)
from turbo_mode_handoff_runtime.storage_inspection import (
    is_relative_to as _is_relative_to,
)
from turbo_mode_handoff_runtime.storage_primitives import (
    read_json_object as _read_json_object_primitive,
)
from turbo_mode_handoff_runtime.storage_primitives import (
    registry_key as _registry_key,
)
from turbo_mode_handoff_runtime.storage_primitives import (
    sha256_regular_file_or_none as _content_sha256,
)


class StorageLocation(StrEnum):
    PRIMARY_ACTIVE = "primary_active"
    PRIMARY_ARCHIVE = "primary_archive"
    PRIMARY_STATE = "primary_state"
    LEGACY_ACTIVE = "legacy_active"
    LEGACY_ARCHIVE = "legacy_archive"
    LEGACY_STATE = "legacy_state"
    STATE_LIKE_RESIDUE = "state_like_residue"
    PREVIOUS_PRIMARY_HIDDEN_ARCHIVE = "previous_primary_hidden_archive"
    UNKNOWN = "unknown"


class SelectionEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED_POLICY_CONFLICT = "blocked-policy-conflict"
    BLOCKED_TRACKED_SOURCE = "blocked-tracked-source"
    INVALID = "invalid"
    SKIPPED = "skipped"
    NOT_ACTIVE_SELECTION_INPUT = "not-active-selection-input"
    NOT_EXPLICIT_PATH_INPUT = "not-explicit-path-input"
    NOT_HISTORY_SEARCH_INPUT = "not-history-search-input"
    NOT_STATE_BRIDGE_INPUT = "not-state-bridge-input"


FILENAME_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2})_.+\.md$")
LEGACY_ACTIVE_OPT_IN_MANIFEST = (
    Path("docs") / "superpowers" / "plans" / "2026-05-13-handoff-storage-legacy-active-opt-ins.md"
)


@dataclass(frozen=True)
class HandoffCandidate:
    path: Path
    storage_location: StorageLocation
    artifact_class: str
    selection_eligibility: SelectionEligibility
    source_git_visibility: str
    source_fs_status: str
    filename_timestamp: str | None = None
    content_sha256: str | None = None
    document_profile: str | None = None
    skip_reason: str | None = None


@dataclass(frozen=True)
class HandoffInventory:
    project_root: Path
    scan_mode: str
    candidates: list[HandoffCandidate]


def discover_handoff_inventory(
    project_root: Path,
    *,
    scan_mode: str,
    explicit_path: Path | None = None,
) -> HandoffInventory:
    """Discover Handoff markdown candidates for a read-only scan mode."""
    layout = _storage_layout.get_storage_layout(project_root)
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
    elif scan_mode == "explicit-path":
        if explicit_path is None:
            raise ValueError(
                "discover_handoff_inventory failed: explicit path is required. Got: None"
            )
        candidates.append(
            _candidate_for_path(
                project_root=layout.project_root,
                path=explicit_path,
                location=_location_for_path(layout, explicit_path),
                scan_mode=scan_mode,
            )
        )
        return HandoffInventory(
            project_root=layout.project_root,
            scan_mode=scan_mode,
            candidates=candidates,
        )
    elif scan_mode == "state-bridge":
        roots = (
            (layout.primary_state_dir, StorageLocation.PRIMARY_STATE),
            (layout.legacy_state_dir, StorageLocation.LEGACY_STATE),
        )
    else:
        raise ValueError(
            f"discover_handoff_inventory failed: unsupported scan mode. Got: {scan_mode!r:.100}"
        )

    for root, location in roots:
        if scan_mode == "state-bridge":
            candidates.extend(
                _discover_state_files(
                    project_root=layout.project_root,
                    root=root,
                    location=location,
                    scan_mode=scan_mode,
                )
            )
        else:
            candidates.extend(
                _discover_markdown(
                    project_root=layout.project_root,
                    root=root,
                    location=location,
                    scan_mode=scan_mode,
                )
            )
    candidates = _dedup_candidates_by_path(candidates)
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


def eligible_history_candidates(inventory: HandoffInventory) -> list[HandoffCandidate]:
    """Return history-search candidates after same-content source-tier dedup."""
    candidates = [
        candidate
        for candidate in inventory.candidates
        if candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
    ]
    ordered = sorted(candidates, key=lambda candidate: _absolute_path_key(candidate.path))
    ordered = sorted(
        ordered,
        key=lambda candidate: _history_source_precedence(candidate.storage_location),
        reverse=True,
    )
    winners: dict[str, HandoffCandidate] = {}
    passthrough: list[HandoffCandidate] = []
    for candidate in ordered:
        if candidate.content_sha256 is None:
            passthrough.append(candidate)
            continue
        winners.setdefault(candidate.content_sha256, candidate)
    return list(winners.values()) + passthrough


def _dedup_candidates_by_path(candidates: list[HandoffCandidate]) -> list[HandoffCandidate]:
    winners: dict[Path, HandoffCandidate] = {}
    for candidate in candidates:
        current = winners.get(candidate.path)
        if current is None or _candidate_specificity(candidate) > _candidate_specificity(current):
            winners[candidate.path] = candidate
    return list(winners.values())


def _candidate_specificity(candidate: HandoffCandidate) -> int:
    location_specificity = {
        StorageLocation.PRIMARY_STATE: 60,
        StorageLocation.LEGACY_STATE: 60,
        StorageLocation.STATE_LIKE_RESIDUE: 60,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE: 50,
        StorageLocation.PRIMARY_ARCHIVE: 45,
        StorageLocation.LEGACY_ARCHIVE: 45,
        StorageLocation.PRIMARY_ACTIVE: 30,
        StorageLocation.LEGACY_ACTIVE: 30,
        StorageLocation.UNKNOWN: 0,
    }[candidate.storage_location]
    eligibility_bonus = 1 if candidate.selection_eligibility != SelectionEligibility.SKIPPED else 0
    return location_specificity + eligibility_bonus


def _discover_markdown(
    *,
    project_root: Path,
    root: Path,
    location: StorageLocation,
    scan_mode: str,
) -> list[HandoffCandidate]:
    if not root.exists() or not root.is_dir():
        return []
    # rglob (not flat glob) is intentional: `root` may be an active dir whose
    # archive/.archive/.session-state are nested subdirs (see storage_layout).
    # rglob deliberately over-discovers; _skip_reason then filters nested_file /
    # state_directory entries and the candidate classifier assigns the correct
    # StorageLocation. A flat glob here would change the discovered set, so it
    # must not be swapped naively. Watch trigger: revisit only if /load latency
    # is reported or per-project handoff counts exceed ~500 (then split active
    # vs archive into separate targeted scans rather than flatten this one).
    return [
        _candidate_for_path(
            project_root=project_root,
            path=path,
            location=location,
            scan_mode=scan_mode,
        )
        for path in sorted(root.rglob("*.md"))
    ]


def _discover_state_files(
    *,
    project_root: Path,
    root: Path,
    location: StorageLocation,
    scan_mode: str,
) -> list[HandoffCandidate]:
    if not root.exists() or not root.is_dir():
        return []
    return [
        _state_candidate_for_path(
            project_root=project_root,
            root=root,
            path=path,
            location=location,
            scan_mode=scan_mode,
        )
        for path in sorted(root.iterdir())
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
    content_sha256 = _content_sha256(path)
    document_profile = _document_profile(path, location=location, scan_mode=scan_mode)
    skip_reason = _skip_reason(root_for_location(project_root, location), path)
    if skip_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="skipped-handoff-artifact",
            selection_eligibility=SelectionEligibility.SKIPPED,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            filename_timestamp=filename_timestamp,
            content_sha256=content_sha256,
            document_profile=document_profile,
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
            content_sha256=content_sha256,
            document_profile=document_profile,
            skip_reason=invalid_reason,
        )
    artifact_class = _artifact_class(location=location, path=path, git_visibility=git_visibility)
    if (
        scan_mode == "active-selection"
        and location == StorageLocation.LEGACY_ACTIVE
        and content_sha256 is not None
    ):
        consumed_status = _consumed_legacy_active_status(project_root, path, content_sha256)
        if consumed_status == "consumed":
            return HandoffCandidate(
                path=path.resolve(),
                storage_location=location,
                artifact_class="consumed-legacy-active",
                selection_eligibility=SelectionEligibility.NOT_ACTIVE_SELECTION_INPUT,
                source_git_visibility=git_visibility,
                source_fs_status=fs_status,
                filename_timestamp=filename_timestamp,
                content_sha256=content_sha256,
                document_profile=document_profile,
                skip_reason="legacy active source already consumed",
            )
        if consumed_status.startswith("registry-unreadable"):
            detail = consumed_status.partition(": ")[2]
            skip_reason = "consumed legacy active registry unreadable"
            if detail:
                skip_reason = f"{skip_reason}: {detail}"
            return HandoffCandidate(
                path=path.resolve(),
                storage_location=location,
                artifact_class="consumed-legacy-active-registry-unreadable",
                selection_eligibility=SelectionEligibility.BLOCKED_POLICY_CONFLICT,
                source_git_visibility=git_visibility,
                source_fs_status=fs_status,
                filename_timestamp=filename_timestamp,
                content_sha256=content_sha256,
                document_profile=document_profile,
                skip_reason=skip_reason,
            )
    if (
        location == StorageLocation.LEGACY_ACTIVE
        and content_sha256 is not None
        and _reviewed_legacy_active_opt_in_matches(project_root, path, content_sha256)
    ):
        artifact_class = "reviewed-runtime-migration-opt-in"
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
        content_sha256=content_sha256,
        document_profile=document_profile,
        skip_reason=reason,
    )


def _state_candidate_for_path(
    *,
    project_root: Path,
    root: Path,
    path: Path,
    location: StorageLocation,
    scan_mode: str,
) -> HandoffCandidate:
    git_visibility = _git_visibility(project_root, path)
    fs_status = _fs_status(path)
    skip_reason = _state_skip_reason(root, path)
    if skip_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="skipped-state-artifact",
            selection_eligibility=SelectionEligibility.SKIPPED,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            content_sha256=_content_sha256(path),
            document_profile="state",
            skip_reason=skip_reason,
        )
    if location == StorageLocation.PRIMARY_STATE:
        artifact_class = "primary-state-artifact"
    elif location == StorageLocation.LEGACY_STATE:
        artifact_class = "legacy-state-artifact"
    else:
        artifact_class = "unknown-state-artifact"
    return HandoffCandidate(
        path=path.resolve(),
        storage_location=location,
        artifact_class=artifact_class,
        selection_eligibility=SelectionEligibility.ELIGIBLE,
        source_git_visibility=git_visibility,
        source_fs_status=fs_status,
        content_sha256=_content_sha256(path),
        document_profile="state",
        skip_reason=None,
    )


def root_for_location(project_root: Path, location: StorageLocation) -> Path:
    layout = _storage_layout.get_storage_layout(project_root)
    if location == StorageLocation.PRIMARY_ACTIVE:
        return layout.primary_active_dir
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return layout.primary_archive_dir
    if location == StorageLocation.PRIMARY_STATE:
        return layout.primary_state_dir
    if location == StorageLocation.LEGACY_ACTIVE:
        return layout.legacy_active_dir
    if location == StorageLocation.LEGACY_ARCHIVE:
        return layout.legacy_archive_dir
    if location == StorageLocation.LEGACY_STATE:
        return layout.legacy_state_dir
    if location == StorageLocation.STATE_LIKE_RESIDUE:
        return layout.legacy_active_dir
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return layout.previous_primary_hidden_archive_dir
    return layout.project_root


def _location_for_path(layout: _storage_layout.StorageLayout, path: Path) -> StorageLocation:
    resolved = path.resolve()
    roots = (
        (layout.primary_state_dir, StorageLocation.PRIMARY_STATE),
        (
            layout.previous_primary_hidden_archive_dir,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        ),
        (layout.primary_archive_dir, StorageLocation.PRIMARY_ARCHIVE),
        (layout.primary_active_dir, StorageLocation.PRIMARY_ACTIVE),
        (layout.legacy_state_dir, StorageLocation.LEGACY_STATE),
        (layout.legacy_archive_dir, StorageLocation.LEGACY_ARCHIVE),
        (layout.legacy_active_dir, StorageLocation.LEGACY_ACTIVE),
    )
    for root, location in roots:
        if _is_relative_to(resolved, root.resolve()):
            return location
    return StorageLocation.UNKNOWN


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
    if location == StorageLocation.PRIMARY_STATE:
        return "primary-state-artifact"
    if location == StorageLocation.LEGACY_STATE:
        return "legacy-state-artifact"
    if location == StorageLocation.STATE_LIKE_RESIDUE:
        return "state-like-residue"
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
    if scan_mode == "explicit-path":
        if location == StorageLocation.UNKNOWN:
            return (
                SelectionEligibility.NOT_EXPLICIT_PATH_INPUT,
                "explicit path is outside supported handoff storage roots",
            )
        if location == StorageLocation.PRIMARY_ACTIVE and git_visibility == "tracked-conflict":
            return (
                SelectionEligibility.BLOCKED_TRACKED_SOURCE,
                "tracked primary runtime source must not be moved or suppressed",
            )
        if location in {
            StorageLocation.PRIMARY_ACTIVE,
            StorageLocation.PRIMARY_ARCHIVE,
            StorageLocation.LEGACY_ACTIVE,
            StorageLocation.LEGACY_ARCHIVE,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        }:
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.NOT_EXPLICIT_PATH_INPUT,
            "storage location is not explicit-path handoff input",
        )
    if scan_mode == "state-bridge":
        if location in {StorageLocation.PRIMARY_STATE, StorageLocation.LEGACY_STATE}:
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.NOT_STATE_BRIDGE_INPUT,
            "storage location is not state-bridge input",
        )
    if scan_mode == "history-search":
        if location in {
            StorageLocation.PRIMARY_ACTIVE,
            StorageLocation.PRIMARY_ARCHIVE,
            StorageLocation.LEGACY_ACTIVE,
            StorageLocation.LEGACY_ARCHIVE,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        }:
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
        if artifact_class == "reviewed-runtime-migration-opt-in":
            return SelectionEligibility.ELIGIBLE, None
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


def _skip_reason(root: Path, path: Path) -> str | None:
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
    return None


def _state_skip_reason(root: Path, path: Path) -> str | None:
    if path.name.startswith("."):
        return "hidden_basename"
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "path_escape"
    if path.is_symlink():
        return "symlink"
    if path.parent != root or len(relative.parts) != 1:
        return "nested_file"
    if not path.name.startswith("handoff-") or path.suffix not in {"", ".json"}:
        return "not_state_artifact"
    return None


def _invalid_reason(*, path: Path, location: StorageLocation, scan_mode: str) -> str | None:
    if location == StorageLocation.UNKNOWN:
        return None
    if location in {StorageLocation.PRIMARY_STATE, StorageLocation.LEGACY_STATE}:
        return None
    if scan_mode == "active-selection" and _filename_timestamp(path) is None:
        return "invalid_filename_timestamp"
    if scan_mode in {"history-search", "explicit-path"} and _archive_history_location(location):
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


def _history_source_precedence(location: StorageLocation) -> int:
    if location == StorageLocation.PRIMARY_ACTIVE:
        return 5
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return 4
    if location == StorageLocation.LEGACY_ACTIVE:
        return 3
    if location == StorageLocation.LEGACY_ARCHIVE:
        return 2
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return 1
    return 0


def _absolute_path_key(path: Path) -> str:
    return str(path.resolve())


def _document_profile(path: Path, *, location: StorageLocation, scan_mode: str) -> str | None:
    if location in {StorageLocation.PRIMARY_STATE, StorageLocation.LEGACY_STATE}:
        return "state"
    if _looks_like_current_contract(path):
        return "current_contract"
    if scan_mode in {"history-search", "explicit-path"} and _archive_history_location(location):
        return "historical_archive"
    return None


def _reviewed_legacy_active_opt_in_matches(
    project_root: Path,
    path: Path,
    content_sha256: str,
) -> bool:
    manifest = project_root / LEGACY_ACTIVE_OPT_IN_MANIFEST
    for row in _read_markdown_table(manifest):
        if _row_cell(row, "project_relative_path") != path.relative_to(project_root).as_posix():
            continue
        if _row_cell(row, "raw_byte_sha256") != content_sha256:
            continue
        if _row_cell(row, "source_root") != "project_root":
            continue
        if _row_cell(row, "storage_location") != StorageLocation.LEGACY_ACTIVE:
            continue
        if not _row_cell(row, "reviewer") or not _row_cell(row, "reason"):
            continue
        return True
    return False


def _consumed_legacy_active_status(
    project_root: Path,
    path: Path,
    content_sha256: str,
) -> str:
    registry_path = (
        _storage_layout.get_storage_layout(project_root).primary_state_dir
        / "consumed-legacy-active.json"
    )
    try:
        payload = _read_json_object_primitive(registry_path, missing={"entries": []})
    except (OSError, ValueError) as exc:
        return f"registry-unreadable: {exc!r}"
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return "registry-unreadable: ValueError('entries field is not a list')"
    expected = {
        "source_root": "project_root",
        "project_relative_source_path": path.relative_to(project_root).as_posix(),
        "storage_location": StorageLocation.LEGACY_ACTIVE,
        "source_content_sha256": content_sha256,
    }
    for entry in entries:
        if isinstance(entry, dict) and _registry_key(entry) == expected:
            return "consumed"
    return "not-consumed"


def _read_markdown_table(path: Path) -> list[dict[str, str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_clean_table_cell(cell) for cell in stripped.strip("|").split("|")]
        if headers is None:
            headers = cells
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def _clean_table_cell(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == "`" and stripped[-1] == "`":
        return stripped[1:-1]
    return stripped


def _row_cell(row: dict[str, str], key: str) -> str:
    return row.get(key, "").strip()
