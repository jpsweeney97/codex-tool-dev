from __future__ import annotations

from pathlib import Path

import pytest
from refresh.classifier import classify_diff_path
from refresh.manifests import build_manifest, diff_manifests, scan_generated_residue
from refresh.models import (
    CoverageState,
    CoverageStatus,
    DiffKind,
    FilesystemState,
    MutationMode,
    PlanAxes,
    PluginSpec,
    PreflightState,
    RefreshError,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.paths import canonical_key
from refresh.state_machine import derive_terminal_plan_status


def plugin_spec(tmp_path: Path) -> PluginSpec:
    return PluginSpec(
        name="handoff",
        version="1.6.0",
        source_root=tmp_path / "source",
        cache_root=tmp_path / "cache",
    )


def test_canonical_key_uses_plugin_version_and_posix_relative_path(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    path = spec.source_root / "skills" / "search" / "SKILL.md"
    assert canonical_key(spec, path, root=spec.source_root) == (
        "handoff/1.6.0/skills/search/SKILL.md"
    )


def test_generated_residue_is_reported_before_manifest_diff(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    residue = spec.source_root / "scripts" / "__pycache__" / "x.pyc"
    residue.parent.mkdir(parents=True)
    residue.write_bytes(b"compiled")

    issues = scan_generated_residue([spec])

    assert [(issue.plugin, issue.path, issue.reason) for issue in issues] == [
        ("handoff", "scripts/__pycache__/x.pyc", "generated-residue")
    ]


def test_manifest_rejects_generated_residue(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    residue = spec.cache_root / ".pytest_cache" / "README.md"
    residue.parent.mkdir(parents=True)
    residue.write_text("cache", encoding="utf-8")

    with pytest.raises(RefreshError):
        build_manifest(spec, root_kind="cache")


def test_manifest_rejects_file_symlink_before_hashing(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = spec.source_root / "README.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)

    with pytest.raises(RefreshError):
        build_manifest(spec, root_kind="source")


def test_manifest_rejects_directory_symlink_before_hashing(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "SKILL.md").write_text("external", encoding="utf-8")
    link = spec.source_root / "skills"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(RefreshError):
        build_manifest(spec, root_kind="source")


def test_directory_symlink_rejection_wins_before_external_residue_scan(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    outside_residue = tmp_path / "outside" / ".pytest_cache" / "README.md"
    outside_residue.parent.mkdir(parents=True)
    outside_residue.write_text("external cache", encoding="utf-8")
    link = spec.source_root / "skills"
    link.parent.mkdir(parents=True)
    link.symlink_to(tmp_path / "outside", target_is_directory=True)

    with pytest.raises(RefreshError, match="symlinks are not allowed"):
        build_manifest(spec, root_kind="source")


def test_residue_scan_does_not_descend_from_directory_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = plugin_spec(tmp_path)
    outside_file = tmp_path / "outside" / "README.md"
    outside_file.parent.mkdir(parents=True)
    outside_file.write_text("external", encoding="utf-8")
    link = spec.source_root / "skills"
    link.parent.mkdir(parents=True)
    link.symlink_to(tmp_path / "outside", target_is_directory=True)
    original_rglob = Path.rglob

    def fail_on_symlink_rglob(self: Path, pattern: str) -> object:
        if self.is_symlink():
            raise AssertionError(f"descended from symlink path: {self}")
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", fail_on_symlink_rglob)

    assert scan_generated_residue([spec]) == []


def test_diff_manifests_reports_added_removed_and_changed(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    source_only = spec.source_root / "README.md"
    cache_only = spec.cache_root / "CHANGELOG.md"
    changed_source = spec.source_root / "skills" / "search" / "SKILL.md"
    changed_cache = spec.cache_root / "skills" / "search" / "SKILL.md"
    source_only.parent.mkdir(parents=True)
    cache_only.parent.mkdir(parents=True)
    changed_source.parent.mkdir(parents=True)
    changed_cache.parent.mkdir(parents=True)
    source_only.write_text("source", encoding="utf-8")
    cache_only.write_text("cache", encoding="utf-8")
    changed_source.write_text("new", encoding="utf-8")
    changed_cache.write_text("old", encoding="utf-8")

    diffs = diff_manifests(
        build_manifest(spec, root_kind="source"),
        build_manifest(spec, root_kind="cache"),
    )

    assert [(diff.canonical_path, diff.kind) for diff in diffs] == [
        ("handoff/1.6.0/CHANGELOG.md", DiffKind.REMOVED),
        ("handoff/1.6.0/README.md", DiffKind.ADDED),
        ("handoff/1.6.0/skills/search/SKILL.md", DiffKind.CHANGED),
    ]


def test_diff_manifests_reports_executable_metadata_drift(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    source_path = spec.source_root / "scripts" / "search.py"
    cache_path = spec.cache_root / "scripts" / "search.py"
    source_path.parent.mkdir(parents=True)
    cache_path.parent.mkdir(parents=True)
    source_path.write_text("print('same')\n", encoding="utf-8")
    cache_path.write_text("print('same')\n", encoding="utf-8")
    source_path.chmod(0o755)
    cache_path.chmod(0o644)

    diffs = diff_manifests(
        build_manifest(spec, root_kind="source"),
        build_manifest(spec, root_kind="cache"),
    )

    assert [(diff.canonical_path, diff.kind) for diff in diffs] == [
        ("handoff/1.6.0/scripts/search.py", DiffKind.CHANGED)
    ]


def test_fixture_backed_diff_classification_and_aggregate_state(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    _write_pair(spec, "README.md", source_text="same\n", cache_text="same\n")
    _write_pair(
        spec,
        "scripts/search.py",
        source_text="print('fast new')\n",
        cache_text="print('fast old')\n",
    )
    _write_pair(
        spec,
        "scripts/defer.py",
        source_text="print('guarded new')\n",
        cache_text="print('guarded old')\n",
    )
    _write_pair(
        spec,
        "scripts/distill.py",
        source_text="print('gap new')\n",
        cache_text="print('gap old')\n",
    )
    _write_pair(
        spec,
        "notes/operator.md",
        source_text="note new\n",
        cache_text="note old\n",
    )
    residue = spec.source_root / "scripts" / "__pycache__" / "x.pyc"
    residue.parent.mkdir(parents=True, exist_ok=True)
    residue.write_bytes(b"compiled")

    residue_issues = scan_generated_residue([spec])

    assert [(issue.plugin, issue.path, issue.reason) for issue in residue_issues] == [
        ("handoff", "scripts/__pycache__/x.pyc", "generated-residue")
    ]
    residue.unlink()
    residue.parent.rmdir()

    diffs = diff_manifests(
        build_manifest(spec, root_kind="source"),
        build_manifest(spec, root_kind="cache"),
    )

    assert [(diff.canonical_path, diff.kind) for diff in diffs] == [
        ("handoff/1.6.0/notes/operator.md", DiffKind.CHANGED),
        ("handoff/1.6.0/scripts/defer.py", DiffKind.CHANGED),
        ("handoff/1.6.0/scripts/distill.py", DiffKind.CHANGED),
        ("handoff/1.6.0/scripts/search.py", DiffKind.CHANGED),
    ]

    classifications = [
        classify_diff_path(
            diff.canonical_path,
            kind=diff.kind,
            source_text=(spec.source_root / _relative_path(diff.canonical_path)).read_text(
                encoding="utf-8"
            ),
            cache_text=(spec.cache_root / _relative_path(diff.canonical_path)).read_text(
                encoding="utf-8"
            ),
            executable=bool(diff.source and diff.source.executable),
        )
        for diff in diffs
    ]
    classification_by_path = {
        classification.canonical_path: classification for classification in classifications
    }

    assert (
        classification_by_path["handoff/1.6.0/scripts/search.py"].mutation_mode
        == MutationMode.FAST
    )
    assert (
        classification_by_path["handoff/1.6.0/scripts/search.py"].coverage_status.value
        == CoverageStatus.COVERED.value
    )
    assert (
        classification_by_path["handoff/1.6.0/scripts/defer.py"].mutation_mode
        == MutationMode.GUARDED
    )
    assert (
        classification_by_path["handoff/1.6.0/scripts/distill.py"].coverage_status.value
        == CoverageStatus.COVERAGE_GAP.value
    )
    assert (
        classification_by_path["handoff/1.6.0/scripts/distill.py"].mutation_mode
        == MutationMode.BLOCKED
    )
    assert (
        classification_by_path["handoff/1.6.0/notes/operator.md"].mutation_mode
        == MutationMode.GUARDED
    )

    axes = PlanAxes(
        filesystem_state=FilesystemState.DRIFT,
        coverage_state=CoverageState.COVERAGE_GAP,
        runtime_config_state=RuntimeConfigState.ALIGNED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
    )

    assert derive_terminal_plan_status(axes) == TerminalPlanStatus.COVERAGE_GAP_BLOCKED


def _write_pair(
    spec: PluginSpec,
    relative: str,
    *,
    source_text: str,
    cache_text: str,
) -> None:
    source = spec.source_root / relative
    cache = spec.cache_root / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    cache.write_text(cache_text, encoding="utf-8")


def _relative_path(canonical_path: str) -> Path:
    return Path(*Path(canonical_path).parts[2:])
