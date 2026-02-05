from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def backup_path(dest: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return dest.with_name(f"{dest.name}.bak-{stamp}")


def copy_with_backup(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        backup = backup_path(dest)
        shutil.copy2(dest, backup)
    shutil.copy2(src, dest)


def copytree_with_backup(src_dir: Path, dest_dir: Path) -> None:
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    if dest_dir.exists():
        backup = backup_path(dest_dir)
        shutil.copytree(dest_dir, backup, dirs_exist_ok=True)
    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)

