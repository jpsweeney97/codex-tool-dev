from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.lib.fsutil import copy_with_backup, copytree_with_backup
from scripts.lib.manifest import InstallManifest


def promote_skill(src_dir: Path, dest_root: Path, manifest: InstallManifest) -> None:
    if not src_dir.is_dir():
        raise ValueError(f"promote_skill failed: src_dir is not a directory. Got: {str(src_dir)!r}")
    name = src_dir.name
    dest_dir = dest_root / name
    copytree_with_backup(src_dir, dest_dir)
    manifest.record(f"skill:{name}", {"src": str(src_dir), "dest": str(dest_dir)})


def promote_agent(src_file: Path, dest_root: Path, manifest: InstallManifest) -> None:
    if not src_file.exists():
        raise ValueError(f"promote_agent failed: missing agent file. Got: {str(src_file)!r}")
    dest_file = dest_root / src_file.name
    copy_with_backup(src_file, dest_file)
    manifest.record(f"agent:{src_file.stem}", {"src": str(src_file), "dest": str(dest_file)})


def _deterministic_automation_id(template_file: Path) -> str:
    # Stable id derived from template content path (not runtime state).
    # Length chosen to keep paths manageable.
    h = hashlib.sha256(str(template_file).encode("utf-8")).hexdigest()
    return h[:16]


def promote_automation_template(
    src_template: Path, dest_root: Path, manifest: InstallManifest
) -> None:
    if not src_template.exists():
        raise ValueError(
            f"promote_automation_template failed: missing template file. Got: {str(src_template)!r}"
        )

    automation_id = _deterministic_automation_id(src_template)
    dest_dir = dest_root / automation_id
    dest_file = dest_dir / "automation.toml"

    # Template is already TOML; for v1 we copy it verbatim.
    # Future: support variable substitution, environment expansion, etc.
    copy_with_backup(src_template, dest_file)
    manifest.record(
        f"automation:{src_template.stem}",
        {"src": str(src_template), "dest": str(dest_file), "id": automation_id},
    )
