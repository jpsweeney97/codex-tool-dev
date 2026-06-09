#!/usr/bin/env python3
"""Publish the Turbo Mode release mirror from the canonical plugin source.

Direction of truth: canonical plugin sources live at
``~/.agents/plugins/<name>/`` (Claude format, ``.claude-plugin/plugin.json``)
and serve both Claude Code and Codex directly. ``plugins/turbo-mode/<name>``
in this repo is a GitHub release mirror only, updated by this tool at
explicit publish time. See ``~/.agents/AGENTS.md`` "Plugin Layout And
Delivery" for the full delivery contract.

Default mode is a non-mutating plan-and-check: it prints the copy plan,
reports per-plugin drift between canonical source and mirror, and exits 1
when the mirror is not in sync. ``--publish`` replaces each mirror tree
atomically (staging copy, backup, swap; backup restored on failure), then
re-checks. The tool never deletes a mirror plugin directory: a mirror
plugin with no canonical counterpart is reported for manual removal with
``trash``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

sys.dont_write_bytecode = True

MIRROR_PARENT_REL = Path("plugins/turbo-mode")
CANONICAL_PLUGIN_PARENT_REL = Path("plugins")
MANIFEST_REL = Path(".claude-plugin/plugin.json")
LEGACY_MANIFEST_REL = Path(".codex-plugin/plugin.json")
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
)
EXCLUDED_FILE_NAMES = frozenset({".DS_Store"})
EXCLUDED_FILE_SUFFIXES = (".pyc",)


class PublishReleaseMirrorError(Exception):
    """Raised when the release mirror publish cannot proceed safely."""


@dataclass(frozen=True)
class MirrorPlanItem:
    """One canonical-source to release-mirror copy operation."""

    plugin: str
    source_root: Path
    mirror_root: Path


@dataclass(frozen=True)
class MirrorPlan:
    """Resolved release mirror publish paths."""

    repo_root: Path
    agents_home: Path
    mirror_parent: Path
    items: tuple[MirrorPlanItem, ...]


def build_mirror_plan(*, repo_root: Path, agents_home: Path) -> MirrorPlan:
    """Build the publish plan without mutating the mirror."""

    resolved_repo_root = repo_root.resolve(strict=False)
    resolved_agents_home = agents_home.expanduser().resolve(strict=False)
    mirror_parent = resolved_repo_root / MIRROR_PARENT_REL
    items: list[MirrorPlanItem] = []
    for plugin, source_root in discover_canonical_plugins(resolved_agents_home):
        items.append(
            MirrorPlanItem(
                plugin=plugin,
                source_root=source_root,
                mirror_root=mirror_parent / plugin,
            )
        )
    return MirrorPlan(
        repo_root=resolved_repo_root,
        agents_home=resolved_agents_home,
        mirror_parent=mirror_parent,
        items=tuple(items),
    )


def discover_canonical_plugins(agents_home: Path) -> tuple[tuple[str, Path], ...]:
    """Discover canonical plugin source roots from their Claude-format manifests."""

    source_parent = agents_home / CANONICAL_PLUGIN_PARENT_REL
    if not source_parent.is_dir():
        fail("discover canonical plugins", "missing canonical plugin parent", source_parent)

    discovered: list[tuple[str, Path]] = []
    seen_names: dict[str, Path] = {}
    for candidate in sorted(source_parent.iterdir(), key=lambda path: path.name):
        if not candidate.is_dir():
            continue
        manifest_path = candidate / MANIFEST_REL
        if not manifest_path.is_file():
            continue
        manifest = read_plugin_manifest(manifest_path)
        plugin_name = manifest.get("name")
        if not isinstance(plugin_name, str) or not plugin_name.strip():
            fail("discover canonical plugins", "missing plugin name", manifest_path)
        plugin = plugin_name.strip()
        validate_plugin_name(plugin, manifest_path)
        if plugin in seen_names:
            fail(
                "discover canonical plugins",
                f"duplicate plugin name also found at {seen_names[plugin]}",
                manifest_path,
            )
        seen_names[plugin] = manifest_path
        discovered.append((plugin, candidate))

    if not discovered:
        fail("discover canonical plugins", "no plugin manifests found", source_parent)
    return tuple(sorted(discovered, key=lambda item: item[0]))


def read_plugin_manifest(manifest_path: Path) -> dict[str, Any]:
    """Read a plugin manifest from a canonical plugin source root."""

    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail("read plugin manifest", str(exc), manifest_path)
    except json.JSONDecodeError as exc:
        fail("read plugin manifest", str(exc), manifest_path)
    if not isinstance(loaded, dict):
        fail("read plugin manifest", "manifest must be a JSON object", manifest_path)
    return loaded


def validate_plugin_name(plugin: str, manifest_path: Path) -> None:
    """Reject manifest names that cannot be used as mirror directories."""

    if plugin in {".", ".."} or "/" in plugin or "\\" in plugin:
        fail("discover canonical plugins", "invalid plugin name", manifest_path)


def collect_tree_files(root: Path) -> dict[Path, Path]:
    """Collect non-residue files under a root keyed by relative path."""

    files: dict[Path, Path] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if is_generated_residue(rel):
            continue
        if path.is_file():
            files[rel] = path
    return files


def compare_plugin_trees(source_root: Path, mirror_root: Path) -> tuple[str, ...]:
    """Return human-readable differences between source and mirror trees."""

    source_files = collect_tree_files(source_root)
    mirror_files = collect_tree_files(mirror_root) if mirror_root.is_dir() else {}
    differences: list[str] = []
    for rel in sorted(set(source_files) | set(mirror_files), key=str):
        if rel not in mirror_files:
            differences.append(f"missing in mirror: {rel}")
        elif rel not in source_files:
            differences.append(f"stale in mirror: {rel}")
        elif source_files[rel].read_bytes() != mirror_files[rel].read_bytes():
            differences.append(f"content differs: {rel}")
    return tuple(differences)


def find_stale_mirror_plugins(plan: MirrorPlan) -> tuple[Path, ...]:
    """Find mirror plugin dirs whose canonical counterpart no longer exists."""

    if not plan.mirror_parent.is_dir():
        return ()
    canonical = {item.plugin for item in plan.items}
    stale: list[Path] = []
    for candidate in sorted(plan.mirror_parent.iterdir(), key=lambda path: path.name):
        if not candidate.is_dir() or candidate.name in canonical:
            continue
        has_manifest = (candidate / MANIFEST_REL).is_file() or (
            candidate / LEGACY_MANIFEST_REL
        ).is_file()
        if has_manifest:
            stale.append(candidate)
    return tuple(stale)


def check_mirror(plan: MirrorPlan) -> int:
    """Report per-plugin mirror status; return 1 when out of sync."""

    fail_code = 0
    for item in plan.items:
        if not item.mirror_root.is_dir():
            print(f"MISSING-MIRROR: {item.plugin} (run: {cli_name()} --publish)")
            fail_code = 1
            continue
        differences = compare_plugin_trees(item.source_root, item.mirror_root)
        if differences:
            print(f"DRIFT: {item.plugin} (run: {cli_name()} --publish)")
            for difference in differences:
                print(f"  {difference}")
            fail_code = 1
        else:
            print(f"IN-SYNC: {item.plugin}")
    for stale in find_stale_mirror_plugins(plan):
        print(f"STALE-MIRROR-PLUGIN: {stale} (no canonical counterpart; remove with trash)")
        fail_code = 1
    return fail_code


def publish_mirror(plan: MirrorPlan) -> dict[str, Any]:
    """Copy canonical plugin trees into the release mirror."""

    published: list[dict[str, str]] = []
    for item in plan.items:
        copy_plugin_tree(source_root=item.source_root, target_root=item.mirror_root)
        published.append(
            {
                "plugin": item.plugin,
                "source": str(item.source_root),
                "mirror": str(item.mirror_root),
            }
        )
    return {"published": published}


def copy_plugin_tree(*, source_root: Path, target_root: Path) -> None:
    """Copy one plugin tree to its mirror target atomically."""

    if not source_root.is_dir():
        fail("publish release mirror", "missing source root", source_root)
    reject_unexpected_symlinks(source_root)
    target_parent = target_root.parent
    target_parent.mkdir(parents=True, exist_ok=True)
    if target_root.exists() and not target_root.is_dir():
        fail("publish release mirror", "target exists and is not a directory", target_root)

    token = uuid.uuid4().hex
    staging_root = target_parent / f".{target_root.name}.publish-{token}.tmp"
    backup_root = target_parent / f".{target_root.name}.publish-{token}.backup"
    target_moved_to_backup = False
    remove_backup = False
    try:
        shutil.copytree(
            source_root,
            staging_root,
            ignore=build_ignore_callable(source_root),
        )
        if target_root.exists():
            target_root.rename(backup_root)
            target_moved_to_backup = True
        staging_root.rename(target_root)
        remove_backup = target_moved_to_backup
    except OSError as exc:
        restore_exc: OSError | None = None
        if target_moved_to_backup and backup_root.exists() and not target_root.exists():
            try:
                backup_root.rename(target_root)
            except OSError as caught_restore_exc:
                restore_exc = caught_restore_exc
        if restore_exc is not None:
            fail(
                "publish release mirror",
                (
                    f"{exc}; rollback restore failed: {restore_exc}; "
                    f"backup preserved at {backup_root}"
                ),
                target_root,
            )
        fail("publish release mirror", str(exc), target_root)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        if remove_backup and backup_root.exists():
            shutil.rmtree(backup_root)


def reject_unexpected_symlinks(root: Path) -> None:
    """Reject symlinks so copy cannot follow content outside the source tree."""

    for path in root.rglob("*"):
        if is_generated_residue(path.relative_to(root)):
            continue
        if path.is_symlink():
            fail("publish release mirror", "symlinks are not allowed", path)


def build_ignore_callable(source_root: Path) -> Callable[[str, list[str]], set[str]]:
    """Build a copytree ignore callback for generated local residue."""

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        directory_path = Path(directory)
        for name in names:
            rel = (directory_path / name).relative_to(source_root)
            if is_generated_residue(rel):
                ignored.add(name)
        return ignored

    return ignore


def is_generated_residue(rel: Path) -> bool:
    """Return whether a relative path is local generated residue."""

    return (
        bool(set(rel.parts) & EXCLUDED_DIR_NAMES)
        or rel.name in EXCLUDED_FILE_NAMES
        or rel.name.endswith(EXCLUDED_FILE_SUFFIXES)
    )


def print_plan(plan: MirrorPlan) -> None:
    """Print planned publish operations."""

    print("planned publish operations (canonical -> mirror):")
    for item in plan.items:
        print(f"- {item.plugin}: {item.source_root} -> {item.mirror_root}")


def cli_name() -> str:
    """Return the invocation name used in repair hints."""

    return Path(sys.argv[0]).name or "publish_release_mirror.py"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Check or publish the Turbo Mode release mirror from the canonical "
            "plugin source in ~/.agents/plugins. Default mode is a non-mutating "
            "plan-and-check that exits 1 on drift."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--agents-home", type=Path, default=Path.home() / ".agents")
    parser.add_argument("--publish", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the release mirror publish helper."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = build_mirror_plan(repo_root=args.repo_root, agents_home=args.agents_home)
        print_plan(plan)
        if args.publish:
            summary = publish_mirror(plan)
            print("publish completed:")
            print(json.dumps(summary, indent=2))
        return check_mirror(plan)
    except (PublishReleaseMirrorError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def fail(operation: str, reason: str, got: object) -> NoReturn:
    """Raise a repo-standard failure message."""

    raise PublishReleaseMirrorError(f"{operation} failed: {reason}. Got: {got!r:.100}")


if __name__ == "__main__":
    raise SystemExit(main())
