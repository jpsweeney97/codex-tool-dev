from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PluginSpec, RefreshError, RuntimeConfigState, fail

TOOL_RELATIVE_PATH = "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"
MARKETPLACE_RELATIVE_PATH = ".agents/plugins/marketplace.json"
EXPECTED_MARKETPLACE_SOURCES = {
    "handoff": "./plugins/turbo-mode/handoff/1.6.0",
    "ticket": "./plugins/turbo-mode/ticket/1.4.0",
}
EXPECTED_CONFIG_PLUGINS = ("handoff@turbo-mode", "ticket@turbo-mode")


@dataclass(frozen=True)
class RefreshPaths:
    repo_root: Path
    codex_home: Path
    marketplace_path: Path
    config_path: Path
    local_only_root: Path


@dataclass(frozen=True)
class RuntimeConfigCheck:
    state: RuntimeConfigState
    marketplace_state: str
    plugin_hooks_state: str
    plugin_enablement_state: dict[str, str]
    reasons: tuple[str, ...] = ()


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


def validate_repo_marketplace(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("parse repo marketplace", str(exc), str(path))
    if not isinstance(data, dict):
        fail("parse repo marketplace", "top-level value is not an object", str(path))
    if data.get("name") != "turbo-mode":
        fail("validate repo marketplace", "marketplace name mismatch", data.get("name"))
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        fail("validate repo marketplace", "plugins is not a list", data.get("plugins"))
    found: dict[str, str] = {}
    for plugin in plugins:
        if not isinstance(plugin, dict):
            fail("validate repo marketplace", "plugin entry is not an object", plugin)
        name = plugin.get("name")
        source = plugin.get("source")
        if name in EXPECTED_MARKETPLACE_SOURCES:
            if not isinstance(source, dict):
                fail("validate repo marketplace", f"{name} source is not an object", plugin)
            if source.get("source") != "local":
                fail("validate repo marketplace", f"{name} source type mismatch", source)
            found[name] = str(source.get("path"))
    for name, expected in EXPECTED_MARKETPLACE_SOURCES.items():
        actual = found.get(name)
        if actual != expected:
            fail("validate repo marketplace", f"{name} source path mismatch", actual)
    return found


def read_runtime_config_state(
    config_path: Path,
    *,
    expected_marketplace_source: Path,
) -> RuntimeConfigCheck:
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RefreshError(
            f"parse config failed: {exc}. Got: {str(config_path)!r:.100}"
        ) from exc
    if not isinstance(data, dict):
        fail("parse config", "top-level value is not an object", str(config_path))

    marketplace_state, marketplace_reason = _marketplace_config_state(
        data,
        expected_marketplace_source=expected_marketplace_source,
    )
    hooks_state, hooks_reason = _plugin_hooks_state(data)
    plugin_state, plugin_reasons = _plugin_enablement_state(data)
    reasons = tuple(
        reason
        for reason in (marketplace_reason, hooks_reason, *plugin_reasons)
        if reason
    )

    if hooks_state == "malformed":
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if hooks_state == "false":
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if any(state == "malformed" for state in plugin_state.values()):
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if any(state == "disabled" for state in plugin_state.values()):
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if any(state == "missing" for state in plugin_state.values()):
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNKNOWN,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if marketplace_state == "missing":
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if marketplace_state == "conflicting-source":
        return RuntimeConfigCheck(
            state=RuntimeConfigState.REPAIRABLE_MISMATCH,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    if hooks_state == "absent-unproven":
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNCHECKED,
            marketplace_state=marketplace_state,
            plugin_hooks_state=hooks_state,
            plugin_enablement_state=plugin_state,
            reasons=reasons,
        )
    return RuntimeConfigCheck(
        state=RuntimeConfigState.ALIGNED,
        marketplace_state=marketplace_state,
        plugin_hooks_state=hooks_state,
        plugin_enablement_state=plugin_state,
        reasons=reasons,
    )


def _marketplace_config_state(
    data: dict[str, Any],
    *,
    expected_marketplace_source: Path,
) -> tuple[str, str | None]:
    marketplaces = data.get("marketplaces")
    if not isinstance(marketplaces, dict):
        return "missing", "marketplaces section missing"
    turbo = marketplaces.get("turbo-mode")
    if not isinstance(turbo, dict):
        return "missing", "turbo-mode marketplace missing"
    if turbo.get("source_type") != "local":
        return "conflicting-source", "turbo-mode marketplace source_type is not local"
    actual_source = turbo.get("source")
    if not isinstance(actual_source, str):
        return "conflicting-source", "turbo-mode marketplace source is not a string"
    actual_path = Path(actual_source).expanduser().resolve(strict=False)
    expected_path = expected_marketplace_source.expanduser().resolve(strict=False)
    if actual_path != expected_path:
        return "conflicting-source", "turbo-mode marketplace source mismatch"
    return "aligned", None


def _plugin_hooks_state(data: dict[str, Any]) -> tuple[str, str | None]:
    features = data.get("features")
    if features is None:
        return "absent-unproven", "features.plugin_hooks absent"
    if not isinstance(features, dict):
        return "malformed", "features section is not an object"
    if "plugin_hooks" not in features:
        return "absent-unproven", "features.plugin_hooks absent"
    value = features["plugin_hooks"]
    if value is True:
        return "true", None
    if value is False:
        return "false", "features.plugin_hooks disabled"
    return "malformed", "features.plugin_hooks is not boolean"


def _plugin_enablement_state(data: dict[str, Any]) -> tuple[dict[str, str], tuple[str, ...]]:
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return (
            {name: "missing" for name in EXPECTED_CONFIG_PLUGINS},
            ("plugins section missing",),
        )
    states: dict[str, str] = {}
    reasons: list[str] = []
    for name in EXPECTED_CONFIG_PLUGINS:
        entry = plugins.get(name)
        if not isinstance(entry, dict):
            states[name] = "missing"
            reasons.append(f"plugins.{name}.enabled missing")
            continue
        enabled = entry.get("enabled")
        if enabled is True:
            states[name] = "enabled"
        elif enabled is False:
            states[name] = "disabled"
            reasons.append(f"plugins.{name}.enabled disabled")
        else:
            states[name] = "malformed"
            reasons.append(f"plugins.{name}.enabled is not boolean")
    return states, tuple(reasons)
