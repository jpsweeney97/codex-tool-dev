from __future__ import annotations

from pathlib import Path

from .models import PluginSpec, fail


def canonical_key(spec: PluginSpec, path: Path, *, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        fail("canonicalize path", "path is outside root", {"path": str(path), "root": str(root)})
    return f"{spec.name}/{spec.version}/{rel.as_posix()}"
