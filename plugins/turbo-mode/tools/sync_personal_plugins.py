#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

PLUGIN_SOURCE_RELS: dict[str, Path] = {
    "handoff": Path("plugins/turbo-mode/handoff/1.7.0"),
    "ticket": Path("plugins/turbo-mode/ticket/1.4.0"),
}
PERSONAL_PLUGIN_TARGET_RELS: dict[str, Path] = {
    "handoff": Path("plugins/handoff"),
    "ticket": Path("plugins/ticket"),
}
PERSONAL_MARKETPLACE_RELATIVE_PATHS: dict[str, str] = {
    "handoff": "./.codex/plugins/handoff",
    "ticket": "./.codex/plugins/ticket",
}
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


class SyncPersonalPluginsError(Exception):
    """Raised when personal plugin sync cannot proceed safely."""


@dataclass(frozen=True)
class SyncPlanItem:
    """One repo-source to personal-plugin copy operation."""

    plugin: str
    source_root: Path
    target_root: Path


@dataclass(frozen=True)
class SyncPlan:
    """Resolved personal plugin sync paths."""

    repo_root: Path
    codex_home: Path
    agents_home: Path
    marketplace_path: Path
    items: tuple[SyncPlanItem, ...]


def build_sync_plan(
    *,
    repo_root: Path,
    codex_home: Path,
    agents_home: Path | None = None,
) -> SyncPlan:
    """Build the copy plan without mutating local plugin state."""

    resolved_repo_root = repo_root.resolve(strict=False)
    resolved_codex_home = codex_home.expanduser().resolve(strict=False)
    resolved_agents_home = (
        agents_home.expanduser().resolve(strict=False)
        if agents_home is not None
        else (Path.home() / ".agents").resolve(strict=False)
    )
    items: list[SyncPlanItem] = []
    for plugin, source_rel in PLUGIN_SOURCE_RELS.items():
        source_root = resolved_repo_root / source_rel
        target_root = resolved_codex_home / PERSONAL_PLUGIN_TARGET_RELS[plugin]
        if not source_root.is_dir():
            fail("build personal plugin sync plan", "missing source root", source_root)
        items.append(
            SyncPlanItem(
                plugin=plugin,
                source_root=source_root,
                target_root=target_root,
            )
        )
    return SyncPlan(
        repo_root=resolved_repo_root,
        codex_home=resolved_codex_home,
        agents_home=resolved_agents_home,
        marketplace_path=resolved_agents_home / "plugins/marketplace.json",
        items=tuple(items),
    )


def build_personal_marketplace_payload() -> dict[str, Any]:
    """Return the intended personal marketplace descriptor."""

    return {
        "name": "turbo-mode",
        "interface": {
            "displayName": "Turbo Mode",
        },
        "plugins": [
            {
                "name": plugin,
                "source": {
                    "source": "local",
                    "path": PERSONAL_MARKETPLACE_RELATIVE_PATHS[plugin],
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
            for plugin in PLUGIN_SOURCE_RELS
        ],
    }


def sync_personal_plugins(plan: SyncPlan) -> dict[str, Any]:
    """Copy repo plugin source trees into the configured personal plugin roots."""

    copied: list[dict[str, str]] = []
    for item in plan.items:
        copy_plugin_tree(source_root=item.source_root, target_root=item.target_root)
        copied.append(
            {
                "plugin": item.plugin,
                "source": str(item.source_root),
                "target": str(item.target_root),
            }
        )
    return {"copied": copied}


def copy_plugin_tree(*, source_root: Path, target_root: Path) -> None:
    """Copy one plugin tree to its personal plugin target."""

    if not source_root.is_dir():
        fail("copy personal plugin", "missing source root", source_root)
    reject_unexpected_symlinks(source_root)
    target_parent = target_root.parent
    target_parent.mkdir(parents=True, exist_ok=True)
    if target_root.exists() and not target_root.is_dir():
        fail("copy personal plugin", "target exists and is not a directory", target_root)

    token = uuid.uuid4().hex
    staging_root = target_parent / f".{target_root.name}.sync-{token}.tmp"
    backup_root = target_parent / f".{target_root.name}.sync-{token}.backup"
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
                "copy personal plugin",
                (
                    f"{exc}; rollback restore failed: {restore_exc}; "
                    f"backup preserved at {backup_root}"
                ),
                target_root,
            )
        fail("copy personal plugin", str(exc), target_root)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        if remove_backup and backup_root.exists():
            shutil.rmtree(backup_root)


def write_personal_marketplace(*, marketplace_path: Path) -> None:
    """Write the personal marketplace descriptor to an explicit destination."""

    payload = build_personal_marketplace_payload()
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = marketplace_path.with_name(f".{marketplace_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(marketplace_path)
    except OSError as exc:
        fail("write personal marketplace", str(exc), marketplace_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def reject_unexpected_symlinks(root: Path) -> None:
    """Reject symlinks so copy cannot follow content outside the source tree."""

    for path in root.rglob("*"):
        if is_generated_residue(path.relative_to(root)):
            continue
        if path.is_symlink():
            fail("copy personal plugin", "symlinks are not allowed", path)


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


def print_plan(plan: SyncPlan) -> None:
    """Print planned operations and personal marketplace JSON."""

    print("planned copy operations:")
    for item in plan.items:
        print(f"- {item.plugin}: {item.source_root} -> {item.target_root}")
    print(f"personal marketplace path: {plan.marketplace_path}")
    print("personal marketplace JSON:")
    print(json.dumps(build_personal_marketplace_payload(), indent=2))


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Plan or sync Turbo Mode repo source into personal Codex plugin directories."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--agents-home", type=Path, default=Path.home() / ".agents")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--write-personal-marketplace", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the personal plugin sync helper."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = build_sync_plan(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            agents_home=args.agents_home,
        )
        print_plan(plan)
        if args.sync:
            summary = sync_personal_plugins(plan)
            print("sync completed:")
            print(json.dumps(summary, indent=2))
        if args.write_personal_marketplace:
            write_personal_marketplace(marketplace_path=plan.marketplace_path)
            print(f"personal marketplace written: {plan.marketplace_path}")
    except (SyncPersonalPluginsError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def fail(operation: str, reason: str, got: object) -> None:
    """Raise a repo-standard failure message."""

    raise SyncPersonalPluginsError(f"{operation} failed: {reason}. Got: {got!r:.100}")


if __name__ == "__main__":
    raise SystemExit(main())
