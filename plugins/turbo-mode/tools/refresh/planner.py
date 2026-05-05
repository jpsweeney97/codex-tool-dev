from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by live Python 3.9 smoke
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised by direct Python 3.9 smoke
        tomllib = None

from .app_server_inventory import AppServerInventoryCheck, collect_readonly_runtime_inventory
from .classifier import classify_diff_path
from .manifests import build_manifest, diff_manifests, scan_generated_residue
from .models import (
    CoverageState,
    CoverageStatus,
    DiffEntry,
    FilesystemState,
    ManifestEntry,
    MutationMode,
    PathClassification,
    PlanAxes,
    PluginSpec,
    PreflightState,
    RefreshError,
    ResidueIssue,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
    fail,
)
from .state_machine import derive_terminal_plan_status

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


InventoryCollector = Callable[
    [RefreshPaths],
    tuple[AppServerInventoryCheck, tuple[dict[str, Any], ...]],
]


@dataclass(frozen=True)
class RuntimeConfigCheck:
    state: RuntimeConfigState
    marketplace_state: str
    plugin_hooks_state: str
    plugin_enablement_state: dict[str, str]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RefreshPlanResult:
    mode: str
    paths: RefreshPaths
    residue_issues: tuple[ResidueIssue, ...]
    diffs: tuple[DiffEntry, ...]
    diff_classification: tuple[PathClassification, ...]
    runtime_config: RuntimeConfigCheck | None
    axes: PlanAxes
    terminal_status: TerminalPlanStatus
    future_external_command: str | None = None
    mutation_command_available: bool = False
    requires_plan: str | None = None
    app_server_inventory: AppServerInventoryCheck | None = None
    app_server_transcript: tuple[dict[str, Any], ...] = ()
    app_server_inventory_status: str = "not-requested"
    app_server_inventory_failure_reason: str | None = None


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


def plan_refresh(
    *,
    repo_root: Path,
    codex_home: Path,
    mode: str,
    inventory_check: bool = False,
    inventory_collector: InventoryCollector | None = None,
) -> RefreshPlanResult:
    paths = build_paths(
        repo_root=repo_root,
        codex_home=codex_home,
    )
    if mode not in {"dry-run", "plan-refresh"}:
        fail("plan refresh", "mode must be dry-run or plan-refresh", mode)
    specs = build_plugin_specs(repo_root=paths.repo_root, codex_home=paths.codex_home)
    preflight_reasons: list[str] = []
    try:
        residue_issues = tuple(scan_generated_residue(specs))
    except RefreshError as exc:
        residue_issues = ()
        preflight_reasons.append(str(exc))

    for spec in specs:
        if not spec.source_root.exists():
            preflight_reasons.append(f"missing source root: {spec.source_root}")
        if not spec.cache_root.exists():
            preflight_reasons.append(f"missing cache root: {spec.cache_root}")
    if residue_issues:
        preflight_reasons.append("generated residue present")

    runtime_config: RuntimeConfigCheck | None = None
    diffs: list[DiffEntry] = []
    classifications: list[PathClassification] = []
    manifest_collected = False

    if not _has_manifest_blocking_reasons(preflight_reasons):
        try:
            for spec in specs:
                source_manifest = build_manifest(spec, root_kind="source")
                cache_manifest = build_manifest(spec, root_kind="cache")
                spec_diffs = diff_manifests(source_manifest, cache_manifest)
                diffs.extend(spec_diffs)
                classifications.extend(
                    _classify_diff_for_spec(spec, diff) for diff in spec_diffs
                )
            manifest_collected = True
        except RefreshError as exc:
            preflight_reasons.append(str(exc))

    try:
        validate_repo_marketplace(paths.marketplace_path)
        runtime_config = read_runtime_config_state(
            paths.config_path,
            expected_marketplace_source=paths.repo_root,
        )
    except RefreshError as exc:
        preflight_reasons.append(str(exc))

    app_server_inventory: AppServerInventoryCheck | None = None
    app_server_transcript: tuple[dict[str, Any], ...] = ()
    inventory_status = "not-requested"
    inventory_failure_reason: str | None = None
    if inventory_check:
        if runtime_config is None:
            inventory_status = "requested-blocked"
            inventory_failure_reason = "runtime config preflight unavailable"
        else:
            try:
                collector = inventory_collector or collect_readonly_runtime_inventory
                app_server_inventory, app_server_transcript = collector(paths)
                inventory_status = "collected"
            except RefreshError as exc:
                inventory_status = "requested-failed"
                inventory_failure_reason = str(exc)
                preflight_reasons.append(str(exc))

    axes = _derive_axes(
        diffs=diffs,
        classifications=classifications,
        runtime_config=runtime_config,
        app_server_inventory=app_server_inventory,
        preflight_reasons=tuple(preflight_reasons),
        manifest_collected=manifest_collected,
    )
    terminal_status = derive_terminal_plan_status(axes)
    future_external_command = (
        select_future_external_command(axes) if mode == "plan-refresh" else None
    )
    return RefreshPlanResult(
        mode=mode,
        paths=paths,
        residue_issues=residue_issues,
        diffs=tuple(diffs),
        diff_classification=tuple(classifications),
        runtime_config=runtime_config,
        axes=axes,
        terminal_status=terminal_status,
        future_external_command=future_external_command,
        mutation_command_available=False,
        requires_plan="future-mutation-plan" if future_external_command is not None else None,
        app_server_inventory=app_server_inventory,
        app_server_transcript=app_server_transcript,
        app_server_inventory_status=inventory_status,
        app_server_inventory_failure_reason=inventory_failure_reason,
    )


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
        data = _loads_config_toml(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
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
    if hooks_state == "absent-unproven":
        return RuntimeConfigCheck(
            state=RuntimeConfigState.UNCHECKED,
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
    return RuntimeConfigCheck(
        state=RuntimeConfigState.ALIGNED,
        marketplace_state=marketplace_state,
        plugin_hooks_state=hooks_state,
        plugin_enablement_state=plugin_state,
        reasons=reasons,
    )


def _loads_config_toml(text: str) -> dict[str, Any]:
    if tomllib is not None:
        return tomllib.loads(text)
    return _loads_minimal_config_toml(text)


def _loads_minimal_config_toml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current = data
    current_path: tuple[str, ...] = ()
    explicit_tables: set[tuple[str, ...]] = set()
    assigned_keys: set[tuple[str, ...]] = set()
    in_multiline_array = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if in_multiline_array:
            if line == "]":
                in_multiline_array = False
            continue
        if line.startswith("[") and line.endswith("]"):
            current = data
            current_path = tuple(_split_toml_dotted_key(line[1:-1], line_number=line_number))
            if current_path in explicit_tables:
                raise ValueError(f"duplicate table on line {line_number}")
            explicit_tables.add(current_path)
            if current_path in assigned_keys:
                raise ValueError(f"table conflicts with scalar on line {line_number}")
            for key in current_path:
                child = current.setdefault(key, {})
                if not isinstance(child, dict):
                    raise ValueError(f"section conflicts with scalar on line {line_number}")
                current = child
            continue
        if "=" not in line:
            raise ValueError(f"expected key/value on line {line_number}")
        key_text, value_text = line.split("=", 1)
        keys = _split_toml_dotted_key(key_text.strip(), line_number=line_number)
        target = current
        for key in keys[:-1]:
            child = target.setdefault(key, {})
            if not isinstance(child, dict):
                raise ValueError(f"key conflicts with scalar on line {line_number}")
            target = child
        raw_value = value_text.strip()
        full_key = current_path + tuple(keys)
        if full_key in assigned_keys:
            raise ValueError(f"duplicate key on line {line_number}")
        if isinstance(target.get(keys[-1]), dict):
            raise ValueError(f"key conflicts with table on line {line_number}")
        assigned_keys.add(full_key)
        target[keys[-1]] = _parse_minimal_toml_value(
            raw_value,
            line_number=line_number,
        )
        in_multiline_array = _starts_multiline_array(raw_value)
    return data


def _starts_multiline_array(text: str) -> bool:
    return text.startswith("[") and not text.endswith("]")


def _split_toml_dotted_key(text: str, *, line_number: int) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and in_quote:
            current.append(char)
            escaped = True
            continue
        if char == '"':
            current.append(char)
            in_quote = not in_quote
            continue
        if char == "." and not in_quote:
            parts.append(_parse_minimal_toml_key("".join(current), line_number=line_number))
            current = []
            continue
        current.append(char)
    if in_quote:
        raise ValueError(f"unterminated quoted key on line {line_number}")
    parts.append(_parse_minimal_toml_key("".join(current), line_number=line_number))
    return parts


def _parse_minimal_toml_key(text: str, *, line_number: int) -> str:
    key = text.strip()
    if not key:
        raise ValueError(f"empty key on line {line_number}")
    if key.startswith('"') and key.endswith('"'):
        try:
            parsed = json.loads(key)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid quoted key on line {line_number}") from exc
        if not isinstance(parsed, str):
            raise ValueError(f"quoted key is not a string on line {line_number}")
        return parsed
    return key


def _parse_minimal_toml_value(text: str, *, line_number: int) -> str | bool:
    if text == "true":
        return True
    if text == "false":
        return False
    if text.startswith('"') and text.endswith('"'):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid string value on line {line_number}") from exc
        if isinstance(parsed, str):
            return parsed
    return text


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
        if "enabled" not in entry:
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


def _classify_diff_for_spec(spec: PluginSpec, diff: DiffEntry) -> PathClassification:
    source_text = _read_text_for_entry(spec.source_root, diff.source)
    cache_text = _read_text_for_entry(spec.cache_root, diff.cache)
    executable = bool(
        (diff.source and diff.source.executable)
        or (diff.cache and diff.cache.executable)
    )
    return classify_diff_path(
        diff.canonical_path,
        kind=diff.kind,
        source_text=source_text,
        cache_text=cache_text,
        executable=executable,
    )


def _read_text_for_entry(root: Path, entry: ManifestEntry | None) -> str:
    if entry is None:
        return ""
    prefix = "/".join(entry.canonical_path.split("/")[:2])
    rel = entry.canonical_path.removeprefix(prefix + "/")
    path = root / rel
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""
    except FileNotFoundError:
        return ""


def _has_manifest_blocking_reasons(preflight_reasons: list[str]) -> bool:
    return any(
        reason.startswith("missing source root:")
        or reason.startswith("missing cache root:")
        or "generated residue present" in reason
        or "scan generated residue failed" in reason
        for reason in preflight_reasons
    )


def _derive_axes(
    *,
    diffs: list[DiffEntry],
    classifications: list[PathClassification],
    runtime_config: RuntimeConfigCheck | None,
    app_server_inventory: AppServerInventoryCheck | None,
    preflight_reasons: tuple[str, ...],
    manifest_collected: bool,
) -> PlanAxes:
    filesystem_state = (
        FilesystemState.DRIFT
        if diffs
        else FilesystemState.NO_DRIFT
        if manifest_collected
        else FilesystemState.UNKNOWN
    )
    coverage_state = (
        _aggregate_coverage_state(filesystem_state, classifications)
        if manifest_collected
        else CoverageState.UNKNOWN
    )
    selected_mutation_mode = (
        _select_mutation_mode(filesystem_state, classifications)
        if manifest_collected
        else SelectedMutationMode.UNKNOWN
    )
    runtime_config_state = (
        runtime_config.state if runtime_config is not None else RuntimeConfigState.UNKNOWN
    )
    if runtime_config_state == RuntimeConfigState.ALIGNED:
        runtime_config_state = (
            RuntimeConfigState.ALIGNED
            if app_server_inventory is not None
            and app_server_inventory.state == "aligned"
            else RuntimeConfigState.UNCHECKED
        )
    elif runtime_config_state == RuntimeConfigState.UNCHECKED:
        runtime_config_state = RuntimeConfigState.UNKNOWN
    if runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH:
        selected_mutation_mode = SelectedMutationMode.GUARDED_REFRESH
    return PlanAxes(
        filesystem_state=filesystem_state,
        coverage_state=coverage_state,
        runtime_config_state=runtime_config_state,
        preflight_state=PreflightState.BLOCKED if preflight_reasons else PreflightState.PASSED,
        selected_mutation_mode=selected_mutation_mode,
        reasons=preflight_reasons + (runtime_config.reasons if runtime_config is not None else ()),
    )


def _aggregate_coverage_state(
    filesystem_state: FilesystemState,
    classifications: list[PathClassification],
) -> CoverageState:
    if filesystem_state == FilesystemState.NO_DRIFT:
        return CoverageState.NOT_APPLICABLE
    if any(item.coverage_status == CoverageStatus.COVERAGE_GAP for item in classifications):
        return CoverageState.COVERAGE_GAP
    return CoverageState.COVERED


def _select_mutation_mode(
    filesystem_state: FilesystemState,
    classifications: list[PathClassification],
) -> SelectedMutationMode:
    if filesystem_state == FilesystemState.NO_DRIFT:
        return SelectedMutationMode.NONE
    if any(item.mutation_mode == MutationMode.BLOCKED for item in classifications):
        return SelectedMutationMode.NONE
    if any(item.mutation_mode == MutationMode.GUARDED for item in classifications):
        return SelectedMutationMode.GUARDED_REFRESH
    return SelectedMutationMode.REFRESH


def select_future_external_command(axes: PlanAxes) -> str | None:
    if not future_external_command_allowed(axes):
        return None
    if axes.runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH:
        return (
            "python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py "
            "--guarded-refresh --smoke standard"
        )
    if (
        axes.filesystem_state == FilesystemState.DRIFT
        and axes.selected_mutation_mode == SelectedMutationMode.REFRESH
    ):
        return (
            "python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py "
            "--refresh --smoke light"
        )
    if (
        axes.filesystem_state == FilesystemState.DRIFT
        and axes.selected_mutation_mode == SelectedMutationMode.GUARDED_REFRESH
    ):
        return (
            "python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py "
            "--guarded-refresh --smoke standard"
        )
    return None


def future_external_command_allowed(axes: PlanAxes) -> bool:
    if axes.preflight_state != PreflightState.PASSED:
        return False
    if axes.runtime_config_state == RuntimeConfigState.UNCHECKED:
        return (
            axes.filesystem_state == FilesystemState.DRIFT
            and axes.coverage_state == CoverageState.COVERED
            and axes.selected_mutation_mode
            in {
                SelectedMutationMode.REFRESH,
                SelectedMutationMode.GUARDED_REFRESH,
            }
        )
    if axes.runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH:
        return axes.coverage_state in {
            CoverageState.COVERED,
            CoverageState.NOT_APPLICABLE,
        }
    return False
