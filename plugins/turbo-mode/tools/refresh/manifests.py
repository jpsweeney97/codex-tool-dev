from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from .models import DiffEntry, DiffKind, ManifestEntry, PluginSpec, ResidueIssue, fail
from .paths import canonical_key

GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv"}
GENERATED_FILES = {".DS_Store"}
GENERATED_PATH_FRAGMENTS = {".codex/ticket-tmp"}


def has_shebang(path: Path) -> bool:
    return path.read_bytes().startswith(b"#!")


def is_executable_mode(path: Path) -> bool:
    return bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def reject_symlink_or_escape(path: Path, *, root: Path, root_kind: str) -> None:
    try:
        path.lstat()
    except OSError as exc:
        fail("inspect manifest path", str(exc), {"root_kind": root_kind, "path": str(path)})
    if path.is_symlink():
        fail(
            "inspect manifest path",
            "symlinks are not allowed",
            {"root_kind": root_kind, "path": str(path)},
        )
    try:
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
    except OSError as exc:
        fail("inspect manifest path", str(exc), {"root_kind": root_kind, "path": str(path)})
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        fail(
            "inspect manifest path",
            "path escapes root",
            {"root_kind": root_kind, "path": str(path)},
        )


def scan_generated_residue(specs: list[PluginSpec]) -> list[ResidueIssue]:
    issues: list[ResidueIssue] = []
    for spec in specs:
        for root_kind, root in (("source", spec.source_root), ("cache", spec.cache_root)):
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                try:
                    path_stat = path.lstat()
                except OSError as exc:
                    fail(
                        "scan generated residue",
                        str(exc),
                        {"root_kind": root_kind, "path": str(path)},
                    )
                if path.is_symlink():
                    continue
                if stat.S_ISDIR(path_stat.st_mode) and any(path.iterdir()):
                    continue
                rel = path.relative_to(root)
                if _is_generated_residue(rel):
                    issues.append(
                        ResidueIssue(
                            root_kind=root_kind,
                            plugin=spec.name,
                            path=rel.as_posix(),
                            reason="generated-residue",
                        )
                    )
    return issues


def build_manifest(spec: PluginSpec, *, root_kind: str) -> dict[str, ManifestEntry]:
    root = _root_for_kind(spec, root_kind)
    if not root.exists():
        return {}
    residue_issues = scan_generated_residue([spec])
    for issue in residue_issues:
        if issue.root_kind == root_kind:
            fail("build manifest", "generated residue present", issue.path)

    manifest: dict[str, ManifestEntry] = {}
    for path in sorted(root.rglob("*")):
        reject_symlink_or_escape(path, root=root, root_kind=root_kind)
        if not path.is_file():
            continue
        content = path.read_bytes()
        file_stat = path.stat()
        key = canonical_key(spec, path, root=root)
        manifest[key] = ManifestEntry(
            canonical_path=key,
            sha256=hashlib.sha256(content).hexdigest(),
            size=len(content),
            mode=stat.S_IMODE(file_stat.st_mode),
            executable=is_executable_mode(path),
            has_shebang=content.startswith(b"#!"),
        )
    return manifest


def diff_manifests(
    source: dict[str, ManifestEntry],
    cache: dict[str, ManifestEntry],
) -> list[DiffEntry]:
    diffs: list[DiffEntry] = []
    for canonical_path in sorted(set(source) | set(cache)):
        source_entry = source.get(canonical_path)
        cache_entry = cache.get(canonical_path)
        if source_entry is None:
            diffs.append(
                DiffEntry(
                    canonical_path=canonical_path,
                    kind=DiffKind.REMOVED,
                    source=None,
                    cache=cache_entry,
                )
            )
        elif cache_entry is None:
            diffs.append(
                DiffEntry(
                    canonical_path=canonical_path,
                    kind=DiffKind.ADDED,
                    source=source_entry,
                    cache=None,
                )
            )
        elif _manifest_entries_differ(source_entry, cache_entry):
            diffs.append(
                DiffEntry(
                    canonical_path=canonical_path,
                    kind=DiffKind.CHANGED,
                    source=source_entry,
                    cache=cache_entry,
                )
            )
    return diffs


def _root_for_kind(spec: PluginSpec, root_kind: str) -> Path:
    if root_kind == "source":
        return spec.source_root
    if root_kind == "cache":
        return spec.cache_root
    fail("select manifest root", "root kind must be source or cache", root_kind)


def _is_generated_residue(rel: Path) -> bool:
    rel_posix = rel.as_posix()
    return (
        rel.name in GENERATED_FILES
        or bool(set(rel.parts) & GENERATED_DIRS)
        or any(fragment in rel_posix for fragment in GENERATED_PATH_FRAGMENTS)
    )


def _manifest_entries_differ(source: ManifestEntry, cache: ManifestEntry) -> bool:
    return (
        source.sha256 != cache.sha256
        or source.mode != cache.mode
        or source.executable != cache.executable
        or source.has_shebang != cache.has_shebang
    )
