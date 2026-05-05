from __future__ import annotations

from pathlib import Path

import pytest
from refresh.manifests import build_manifest, diff_manifests, scan_generated_residue
from refresh.models import DiffKind, PluginSpec, RefreshError
from refresh.paths import canonical_key


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
