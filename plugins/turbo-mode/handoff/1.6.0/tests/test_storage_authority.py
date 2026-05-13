from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from scripts.storage_authority import (
    SelectionEligibility,
    StorageLocation,
    chain_state_recovery_inventory,
    discover_handoff_inventory,
    eligible_active_candidates,
    eligible_history_candidates,
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


def _invalid_handoff(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## Goal\n\nMissing required frontmatter.\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_legacy_active_opt_in(
    project_root: Path,
    source: Path,
    *,
    sha256: str | None = None,
) -> Path:
    rel_path = source.relative_to(project_root).as_posix()
    manifest = (
        project_root
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-05-13-handoff-storage-legacy-active-opt-ins.md"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "| project_relative_path | raw_byte_sha256 | source_root | storage_location | "
        "reviewer | reason |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"| `{rel_path}` | `{sha256 or _sha256(source)}` | `project_root` | "
        "`legacy_active` | `test-reviewer` | reviewed runtime migration input |\n",
        encoding="utf-8",
    )
    return manifest


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


def test_active_selection_accepts_exact_reviewed_legacy_active_opt_in(tmp_path: Path) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-01_legacy.md", "Legacy")
    _write_legacy_active_opt_in(tmp_path, legacy)

    inventory = discover_handoff_inventory(tmp_path, scan_mode="active-selection")

    candidate = next(candidate for candidate in inventory.candidates if candidate.path == legacy)
    assert candidate.storage_location == StorageLocation.LEGACY_ACTIVE
    assert candidate.artifact_class == "reviewed-runtime-migration-opt-in"
    assert candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
    assert eligible_active_candidates(inventory) == [candidate]


def test_active_selection_blocks_legacy_active_opt_in_hash_mismatch(tmp_path: Path) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-01_legacy.md", "Legacy")
    _write_legacy_active_opt_in(tmp_path, legacy, sha256="0" * 64)

    inventory = discover_handoff_inventory(tmp_path, scan_mode="active-selection")

    candidate = next(candidate for candidate in inventory.candidates if candidate.path == legacy)
    assert candidate.artifact_class == "policy-conflict-artifact"
    assert candidate.selection_eligibility == SelectionEligibility.BLOCKED_POLICY_CONFLICT
    assert eligible_active_candidates(inventory) == []


def test_active_selection_suppresses_consumed_legacy_active_by_stable_hash(
    tmp_path: Path,
) -> None:
    legacy = _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-01_legacy.md", "Legacy")
    _write_legacy_active_opt_in(tmp_path, legacy)
    consumed = tmp_path / ".codex" / "handoffs" / ".session-state" / "consumed-legacy-active.json"
    consumed.parent.mkdir(parents=True, exist_ok=True)
    consumed.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "source_root": "project_root",
                        "project_relative_source_path": legacy.relative_to(tmp_path).as_posix(),
                        "storage_location": "legacy_active",
                        "source_content_sha256": _sha256(legacy),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    suppressed = discover_handoff_inventory(tmp_path, scan_mode="active-selection")
    suppressed_candidate = next(
        candidate for candidate in suppressed.candidates if candidate.path == legacy
    )
    assert suppressed_candidate.artifact_class == "consumed-legacy-active"
    assert (
        suppressed_candidate.selection_eligibility
        == SelectionEligibility.NOT_ACTIVE_SELECTION_INPUT
    )
    assert eligible_active_candidates(suppressed) == []

    legacy.write_text(legacy.read_text(encoding="utf-8") + "\nChanged bytes.\n", encoding="utf-8")
    changed = discover_handoff_inventory(tmp_path, scan_mode="active-selection")
    changed_candidate = next(
        candidate for candidate in changed.candidates if candidate.path == legacy
    )
    assert changed_candidate.artifact_class == "policy-conflict-artifact"
    assert changed_candidate.selection_eligibility == SelectionEligibility.BLOCKED_POLICY_CONFLICT


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


def test_active_selection_orders_by_filename_timestamp_then_lexical_path(tmp_path: Path) -> None:
    older = _handoff(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_10-00_older.md",
        "Older",
    )
    later_b = _handoff(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_b.md",
        "Later B",
    )
    later_a = _handoff(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_a.md",
        "Later A",
    )

    inventory = discover_handoff_inventory(tmp_path, scan_mode="active-selection")

    assert [candidate.path for candidate in eligible_active_candidates(inventory)] == [
        later_a,
        later_b,
        older,
    ]


def test_active_selection_reports_invalid_hidden_nested_and_state_diagnostics(
    tmp_path: Path,
) -> None:
    invalid = _invalid_handoff(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_invalid.md"
    )
    hidden = _handoff(tmp_path / ".codex" / "handoffs" / ".hidden.md")
    nested = _handoff(tmp_path / ".codex" / "handoffs" / "nested" / "2026-05-13_12-00_nested.md")
    state_doc = _handoff(
        tmp_path / ".codex" / "handoffs" / ".session-state" / "2026-05-13_12-00_state.md"
    )

    inventory = discover_handoff_inventory(tmp_path, scan_mode="active-selection")
    by_path = {candidate.path: candidate for candidate in inventory.candidates}

    assert by_path[invalid].selection_eligibility == SelectionEligibility.INVALID
    assert by_path[invalid].skip_reason == "invalid_document"
    assert by_path[hidden].selection_eligibility == SelectionEligibility.SKIPPED
    assert by_path[hidden].skip_reason == "hidden_basename"
    assert by_path[nested].selection_eligibility == SelectionEligibility.SKIPPED
    assert by_path[nested].skip_reason == "nested_file"
    assert by_path[state_doc].selection_eligibility == SelectionEligibility.SKIPPED
    assert by_path[state_doc].skip_reason == "state_directory"


def test_history_search_keeps_no_frontmatter_archives_as_historical_profile(
    tmp_path: Path,
) -> None:
    archive = tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_12-00_old.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("## Older Handoff\n\nNo current frontmatter.\n", encoding="utf-8")

    inventory = discover_handoff_inventory(tmp_path, scan_mode="history-search")
    candidate = next(candidate for candidate in inventory.candidates if candidate.path == archive)

    assert candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
    assert candidate.document_profile == "historical_archive"


def test_history_search_dedups_duplicate_hashes_by_source_tier_then_path(
    tmp_path: Path,
) -> None:
    primary_active = _handoff(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_same.md",
        "Same",
    )
    _handoff(
        tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_12-00_same.md",
        "Same",
    )
    _handoff(tmp_path / "docs" / "handoffs" / "2026-05-13_12-00_same.md", "Same")
    _handoff(
        tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_same.md",
        "Same",
    )
    _handoff(
        tmp_path / ".codex" / "handoffs" / ".archive" / "2026-05-13_12-00_same.md",
        "Same",
    )

    inventory = discover_handoff_inventory(tmp_path, scan_mode="history-search")

    assert [candidate.path for candidate in eligible_history_candidates(inventory)] == [
        primary_active,
    ]


def test_explicit_path_classifies_supported_storage_locations(tmp_path: Path) -> None:
    paths = {
        StorageLocation.PRIMARY_ACTIVE: _handoff(
            tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md"
        ),
        StorageLocation.PRIMARY_ARCHIVE: _handoff(
            tmp_path / ".codex" / "handoffs" / "archive" / "2026-05-13_12-00_primary.md"
        ),
        StorageLocation.LEGACY_ACTIVE: _handoff(
            tmp_path / "docs" / "handoffs" / "2026-05-13_12-00_legacy.md"
        ),
        StorageLocation.LEGACY_ARCHIVE: _handoff(
            tmp_path / "docs" / "handoffs" / "archive" / "2026-05-13_12-00_legacy.md"
        ),
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE: _handoff(
            tmp_path / ".codex" / "handoffs" / ".archive" / "2026-05-13_12-00_hidden.md"
        ),
    }

    for location, path in paths.items():
        inventory = discover_handoff_inventory(
            tmp_path,
            scan_mode="explicit-path",
            explicit_path=path,
        )
        candidate = inventory.candidates[0]
        assert candidate.storage_location == location
        assert candidate.selection_eligibility == SelectionEligibility.ELIGIBLE


def test_state_bridge_reports_primary_and_legacy_state_without_mutation(
    tmp_path: Path,
) -> None:
    primary = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token.json"
    legacy = tmp_path / "docs" / "handoffs" / ".session-state" / "handoff-demo"
    primary.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text('{"project": "demo"}', encoding="utf-8")
    legacy.write_text("/tmp/archive.md", encoding="utf-8")

    inventory = discover_handoff_inventory(tmp_path, scan_mode="state-bridge")
    by_path = {candidate.path: candidate for candidate in inventory.candidates}

    assert by_path[primary].storage_location == StorageLocation.PRIMARY_STATE
    assert by_path[primary].artifact_class == "primary-state-artifact"
    assert by_path[primary].selection_eligibility == SelectionEligibility.ELIGIBLE
    assert by_path[legacy].storage_location == StorageLocation.LEGACY_STATE
    assert by_path[legacy].artifact_class == "legacy-state-artifact"
    assert by_path[legacy].selection_eligibility == SelectionEligibility.ELIGIBLE


def test_chain_state_recovery_inventory_reports_token_mismatch_as_invalid(
    tmp_path: Path,
) -> None:
    state = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token-a.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps({
            "state_path": str(state),
            "project": "demo",
            "resume_token": "different-token",
            "archive_path": "/tmp/archive.md",
            "created_at": "2026-05-13T16:00:00Z",
        }),
        encoding="utf-8",
    )

    inventory = chain_state_recovery_inventory(tmp_path, project_name="demo")

    candidate = inventory["candidates"][0]
    assert candidate["project_relative_state_path"] == (
        ".codex/handoffs/.session-state/handoff-demo-token-a.json"
    )
    assert candidate["detected_format"] == "tokenized-json"
    assert candidate["validation_status"] == "invalid"
    assert candidate["validation_error"] == "payload resume token does not match filename token"
