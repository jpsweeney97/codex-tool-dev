from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import PluginSpec, fail

MARKETPLACE_RELATIVE_PATH = ".agents/plugins/marketplace.json"


@dataclass(frozen=True)
class RefreshPaths:
    repo_root: Path
    codex_home: Path
    marketplace_path: Path
    config_path: Path
    local_only_root: Path


def build_paths(
    *,
    repo_root: Path,
    codex_home: Path,
) -> RefreshPaths:
    normalized_repo_root = repo_root.expanduser().resolve(strict=True)
    normalized_codex_home = codex_home.expanduser().resolve(strict=False)
    return RefreshPaths(
        repo_root=normalized_repo_root,
        codex_home=normalized_codex_home,
        marketplace_path=normalized_repo_root / MARKETPLACE_RELATIVE_PATH,
        config_path=normalized_codex_home / "config.toml",
        local_only_root=normalized_codex_home / "local-only/turbo-mode-refresh",
    )


def canonical_key(spec: PluginSpec, path: Path, *, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        fail("canonicalize path", "path is outside root", {"path": str(path), "root": str(root)})
    return f"{spec.name}/{spec.version}/{rel.as_posix()}"
