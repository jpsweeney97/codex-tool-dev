from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import PluginSpec

TOOL_RELATIVE_PATH = "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"
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


def build_plugin_specs(*, repo_root: Path, codex_home: Path) -> list[PluginSpec]:
    return [
        PluginSpec(
            name="handoff",
            version="1.6.0",
            source_root=repo_root / "plugins/turbo-mode/handoff/1.6.0",
            cache_root=codex_home / "plugins/cache/turbo-mode/handoff/1.6.0",
        ),
        PluginSpec(
            name="ticket",
            version="1.4.0",
            source_root=repo_root / "plugins/turbo-mode/ticket/1.4.0",
            cache_root=codex_home / "plugins/cache/turbo-mode/ticket/1.4.0",
        ),
    ]
