# Turbo Mode Refresh 02 Non-Mutating CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the non-mutating Turbo Mode installed-refresh CLI for `--dry-run` and `--plan-refresh`.

**Architecture:** Plan 02 wraps the Plan 01 pure core with a thin orchestration layer, local-only evidence writing, and a command-line entrypoint. It must consume `build_manifest`, `diff_manifests`, `scan_generated_residue`, `classify_diff_path`, and `derive_terminal_plan_status`; it must not reinterpret classifier outcomes or implement installed-cache mutation.

**Tech Stack:** Python 3.11, stdlib `argparse` / `json` / `tomllib`, existing `refresh` package modules, `pytest`, `ruff`.

---

## Scope

Plan 02 implements:

- `python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --dry-run`
- `python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --plan-refresh`
- local-only evidence under `/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/`
- read-only repo marketplace validation
- read-only global config validation, including marketplace registration, plugin hooks, and explicit enablement for `handoff@turbo-mode` and `ticket@turbo-mode`
- source/cache manifest diffing
- path classification using Plan 01 classifier APIs
- aggregate state-axis derivation using Plan 01 state-machine APIs
- future-only external-shell command advice, explicitly marked non-executable in Plan 02

Plan 02 does not implement:

- executable `--refresh`
- executable `--guarded-refresh`
- app-server inventory
- process gates
- locks
- recovery
- global config mutation
- installed-cache mutation
- commit-safe evidence under `plugins/turbo-mode/evidence/refresh/`

The CLI may define `--refresh` and `--guarded-refresh` as rejected arguments only if the implementation exits before reading or writing mutable runtime state and reports that mutation modes are outside Plan 02. `--plan-refresh` must not call its advisory output `selected_command`; future mutation command text must be exposed as `future_external_command` with `mutation_command_available = false` and `requires_plan = "future-mutation-plan"`.

Future mutation advice must use one shared eligibility predicate. Advice is forbidden when `preflight_state` is blocked, when coverage is a gap or unknown, when runtime/config state is unknown or unrepairable, or when the only available evidence is a malformed/missing/disabled local config. The only Plan 02 advice lanes are:

- inventory-missing covered filesystem drift with `runtime_config_state = UNCHECKED` and `coverage_state = COVERED`;
- repairable runtime/config mismatch with no coverage gap (`coverage_state = COVERED` for drift or `NOT_APPLICABLE` for no-drift).

Global config alignment requires all three local config surfaces to validate: `[marketplaces.turbo-mode]`, `[features].plugin_hooks`, and `[plugins."handoff@turbo-mode"].enabled` plus `[plugins."ticket@turbo-mode"].enabled`. Disabled, missing, or non-boolean plugin enablement is not runtime inventory, but it is enough local config evidence to block Plan 02 advice and prevent `filesystem-no-drift` from looking enabled.

Because Plan 02 does not collect app-server inventory, it must never emit `no-drift` or use local config alignment as runtime alignment. Matching source/cache manifests with readable local config produce `filesystem-no-drift`; drift with covered filesystem classification can produce future-only mode advice, but its terminal status remains blocked until an inventory-capable plan proves runtime alignment.

## Current Base

- Current implementation base: local `main` after Plan 01 merge, `1bc24df`.
- Existing pure core package: `plugins/turbo-mode/tools/refresh/`.
- Existing Plan 01 handoff rule: Plan 02 consumes core APIs and persists separate axes before deriving terminal status.
- Existing design spec: `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`.

## File Structure

Create:

- `plugins/turbo-mode/tools/refresh/planner.py`
  - Builds plugin specs from repo root and Codex home.
  - Validates source roots, cache roots, repo marketplace metadata, and global config in read-only mode.
  - Builds manifests, diffs them, classifies paths, aggregates axes, and derives terminal status.
  - Preserves source/cache facts even when config, marketplace, residue, or manifest gates produce a higher-priority blocked terminal status.
  - Derives future-only `--plan-refresh` command advice from preserved local facts without claiming the command is executable in Plan 02.

- `plugins/turbo-mode/tools/refresh/evidence.py`
  - Creates local-only run directories with `0700`.
  - Rejects symlinked evidence paths and evidence roots with broader permissions.
  - Creates each run directory exclusively instead of following or reusing an existing path.
  - Writes evidence JSON files with `0600`.
  - Converts dataclasses/enums/paths to JSON-safe structures.
  - Records explicit omission reasons for evidence classes outside Plan 02.

- `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
  - Script entrypoint matching the design spec path.
  - Sets `sys.dont_write_bytecode = True` before importing local `refresh.*` modules.
  - Parses `--dry-run`, `--plan-refresh`, `--repo-root`, `--codex-home`, `--run-id`, and `--json`.
  - Calls planner and evidence writer.
  - Prints a human-readable summary by default and JSON when requested.

Modify:

- `plugins/turbo-mode/tools/refresh/__init__.py`
  - Export no new public symbols unless tests need package-level import stability. Prefer direct module imports.

Create tests:

- `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- `plugins/turbo-mode/tools/refresh/tests/test_evidence.py`
- `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

Do not modify:

- `plugins/turbo-mode/tools/migration/migration_common.py`
- `plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py`
- installed cache roots under `/Users/jp/.codex/plugins/cache/turbo-mode/`
- `/Users/jp/.codex/config.toml`

Do not accept `--local-only-root` in Plan 02. Tests that need isolation must pass a temporary `--codex-home`; the evidence root is always derived as `<codex_home>/local-only/turbo-mode-refresh`.

---

### Task 0: Live Residue Decision Before Implementation

**Files:**

- No source edits expected.

- [ ] **Step 1: Run the live source residue gate**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
```

Expected in the current checkout before cleanup:

```text
plugins/turbo-mode/handoff/1.6.0/.pytest_cache
plugins/turbo-mode/handoff/1.6.0/.venv
```

- [ ] **Step 2: Stop or clean with explicit approval**

If the residue is present, stop before implementing Plan 02 unless the operator explicitly approves moving those residue paths to Trash. Do not treat a live `--dry-run` stop on this residue as a soft pass.

If cleanup is approved, use `trash` only:

```bash
trash plugins/turbo-mode/handoff/1.6.0/.pytest_cache
trash plugins/turbo-mode/handoff/1.6.0/.venv
```

- [ ] **Step 3: Re-run the residue gate**

Run the Step 1 `find` command again.

Expected after approved cleanup: prints nothing.

---

### Task 1: Add Read-Only Planning Models And Path Context

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/planner.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`

- [ ] **Step 1: Write the failing tests for plugin spec construction**

Create `plugins/turbo-mode/tools/refresh/tests/test_planner.py` with:

```python
from __future__ import annotations

from pathlib import Path

from refresh.planner import build_paths, build_plugin_specs


def test_build_plugin_specs_uses_repo_source_and_codex_cache_roots(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"

    specs = build_plugin_specs(repo_root=repo_root, codex_home=codex_home)

    assert [(spec.name, spec.version) for spec in specs] == [
        ("handoff", "1.6.0"),
        ("ticket", "1.4.0"),
    ]
    assert specs[0].source_root == repo_root / "plugins/turbo-mode/handoff/1.6.0"
    assert specs[0].cache_root == codex_home / "plugins/cache/turbo-mode/handoff/1.6.0"
    assert specs[1].source_root == repo_root / "plugins/turbo-mode/ticket/1.4.0"
    assert specs[1].cache_root == codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"


def test_build_paths_normalizes_relative_repo_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    codex_home = tmp_path / ".codex"
    monkeypatch.chdir(tmp_path)

    paths = build_paths(repo_root=Path("repo"), codex_home=codex_home)

    assert paths.repo_root == repo_root.resolve(strict=True)
    assert paths.marketplace_path == repo_root / ".agents/plugins/marketplace.json"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_planner.py -q
```

Expected: fail because `refresh.planner` does not exist.

- [ ] **Step 3: Implement the planning context**

Create `plugins/turbo-mode/tools/refresh/planner.py` with the initial context helpers:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_planner.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/turbo-mode/tools/refresh/planner.py plugins/turbo-mode/tools/refresh/tests/test_planner.py
git commit -m "feat: add turbo-mode refresh planning context"
```

---

### Task 2: Add Read-Only Marketplace And Config Validation

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/planner.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`

- [ ] **Step 1: Add failing tests for repo marketplace validation**

Append to `test_planner.py`:

```python
import json

import pytest
from refresh.models import RefreshError
from refresh.planner import validate_repo_marketplace


def write_marketplace(path: Path, *, ticket_path: str = "./plugins/turbo-mode/ticket/1.4.0") -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "name": "turbo-mode",
                "plugins": [
                    {
                        "name": "handoff",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/handoff/1.6.0",
                        },
                    },
                    {
                        "name": "ticket",
                        "source": {"source": "local", "path": ticket_path},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_validate_repo_marketplace_accepts_expected_local_plugins(tmp_path: Path) -> None:
    marketplace = tmp_path / "repo/.agents/plugins/marketplace.json"
    write_marketplace(marketplace)

    result = validate_repo_marketplace(marketplace)

    assert result == {
        "handoff": "./plugins/turbo-mode/handoff/1.6.0",
        "ticket": "./plugins/turbo-mode/ticket/1.4.0",
    }


def test_validate_repo_marketplace_rejects_wrong_ticket_source(tmp_path: Path) -> None:
    marketplace = tmp_path / "repo/.agents/plugins/marketplace.json"
    write_marketplace(marketplace, ticket_path="./wrong")

    with pytest.raises(RefreshError, match="ticket source path mismatch"):
        validate_repo_marketplace(marketplace)
```

- [ ] **Step 2: Add failing tests for config state classification**

Append to `test_planner.py`. Integrate imports into the existing module import block so the final file is ruff-stable; the import lines below show required symbols, not a literal mid-file import block.

```python
from refresh.models import RuntimeConfigState
from refresh.planner import read_runtime_config_state


def test_read_runtime_config_state_aligned_when_marketplace_and_hooks_true(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/repo"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.ALIGNED
    assert state.plugin_hooks_state == "true"
    assert state.marketplace_state == "aligned"
    assert state.plugin_enablement_state == {
        "handoff@turbo-mode": "enabled",
        "ticket@turbo-mode": "enabled",
    }


def test_read_runtime_config_state_absent_hooks_is_unchecked(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/repo"\n'
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.UNCHECKED
    assert state.plugin_hooks_state == "absent-unproven"


def test_read_runtime_config_state_conflicting_marketplace_is_repairable(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/other"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.REPAIRABLE_MISMATCH
    assert state.marketplace_state == "conflicting-source"


def test_read_runtime_config_state_disabled_hooks_is_unrepairable(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/repo"\n'
        "[features]\nplugin_hooks = false\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.UNREPAIRABLE_MISMATCH
    assert state.plugin_hooks_state == "false"


def test_read_runtime_config_state_malformed_toml_blocks_preflight(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[features\n", encoding="utf-8")

    with pytest.raises(RefreshError, match="parse config failed"):
        read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))


def test_read_runtime_config_state_disabled_plugin_is_unrepairable(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/repo"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = false\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.UNREPAIRABLE_MISMATCH
    assert state.plugin_enablement_state["ticket@turbo-mode"] == "disabled"


def test_read_runtime_config_state_missing_plugin_enablement_is_unknown(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/repo"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.UNKNOWN
    assert state.plugin_enablement_state["ticket@turbo-mode"] == "missing"


def test_read_runtime_config_state_non_boolean_plugin_enablement_is_unrepairable(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/repo"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = "yes"\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=Path("/repo"))

    assert state.state == RuntimeConfigState.UNREPAIRABLE_MISMATCH
    assert state.plugin_enablement_state["ticket@turbo-mode"] == "malformed"


def test_read_runtime_config_state_normalizes_config_source_path(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    config = tmp_path / "config.toml"
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo}/."\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )

    state = read_runtime_config_state(config, expected_marketplace_source=repo)

    assert state.state == RuntimeConfigState.ALIGNED
    assert state.marketplace_state == "aligned"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_planner.py -q
```

Expected: fail because validation helpers do not exist.

- [ ] **Step 4: Implement validation helpers**

Add to `planner.py`:

```python
import json
import tomllib
from typing import Any

from .models import RefreshError, RuntimeConfigState, fail

EXPECTED_MARKETPLACE_SOURCES = {
    "handoff": "./plugins/turbo-mode/handoff/1.6.0",
    "ticket": "./plugins/turbo-mode/ticket/1.4.0",
}
EXPECTED_CONFIG_PLUGINS = ("handoff@turbo-mode", "ticket@turbo-mode")


@dataclass(frozen=True)
class RuntimeConfigCheck:
    state: RuntimeConfigState
    marketplace_state: str
    plugin_hooks_state: str
    plugin_enablement_state: dict[str, str]
    reasons: tuple[str, ...] = ()


def validate_repo_marketplace(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
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
    except Exception as exc:
        raise RefreshError(f"parse config failed: {exc}. Got: {str(config_path)!r:.100}") from exc
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_planner.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/tools/refresh/planner.py plugins/turbo-mode/tools/refresh/tests/test_planner.py
git commit -m "feat: validate turbo-mode refresh config state"
```

---

### Task 3: Aggregate Manifest Diff, Classification, And Plan Axes

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/planner.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`

- [ ] **Step 1: Add failing aggregate tests**

Append to `test_planner.py`:

```python
from refresh.models import (
    CoverageState,
    FilesystemState,
    PathOutcome,
    PreflightState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.planner import plan_refresh


def write_plugin_pair(
    repo_root: Path,
    codex_home: Path,
    *,
    plugin: str,
    version: str,
    rel: str,
    source_text: str,
    cache_text: str,
) -> None:
    source = repo_root / f"plugins/turbo-mode/{plugin}/{version}" / rel
    cache = codex_home / f"plugins/cache/turbo-mode/{plugin}/{version}" / rel
    source.parent.mkdir(parents=True, exist_ok=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    cache.write_text(cache_text, encoding="utf-8")


def ensure_complete_plugin_roots(repo_root: Path, codex_home: Path) -> None:
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="README.md",
        source_text="handoff same\n",
        cache_text="handoff same\n",
    )
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="ticket",
        version="1.4.0",
        rel="README.md",
        source_text="ticket same\n",
        cache_text="ticket same\n",
    )


def write_aligned_config(codex_home: Path, repo_root: Path) -> None:
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )


def write_valid_marketplace(repo_root: Path) -> None:
    write_marketplace(repo_root / ".agents/plugins/marketplace.json")


def test_plan_refresh_no_drift_with_aligned_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.axes.filesystem_state == FilesystemState.NO_DRIFT
    assert result.axes.coverage_state == CoverageState.NOT_APPLICABLE
    assert result.axes.preflight_state == PreflightState.PASSED
    assert result.axes.runtime_config_state == RuntimeConfigState.UNCHECKED
    assert result.terminal_status == TerminalPlanStatus.FILESYSTEM_NO_DRIFT
    assert result.diff_classification == ()


def test_plan_refresh_normalizes_relative_repo_root_for_config_comparison(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root.resolve(strict=False))
    ensure_complete_plugin_roots(repo_root, codex_home)
    monkeypatch.chdir(tmp_path)

    result = plan_refresh(repo_root=Path("repo"), codex_home=codex_home, mode="dry-run")

    assert result.paths.repo_root == repo_root.resolve(strict=True)
    assert result.terminal_status == TerminalPlanStatus.FILESYSTEM_NO_DRIFT


def test_plan_refresh_fast_safe_drift_allows_refresh(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="scripts/search.py",
        source_text="print('new')\n",
        cache_text="print('old')\n",
    )

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.axes.filesystem_state == FilesystemState.DRIFT
    assert result.axes.coverage_state == CoverageState.COVERED
    assert result.axes.runtime_config_state == RuntimeConfigState.UNCHECKED
    assert result.axes.selected_mutation_mode == SelectedMutationMode.REFRESH
    assert result.terminal_status == TerminalPlanStatus.BLOCKED_PREFLIGHT
    assert [item.outcome for item in result.diff_classification] == [
        PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE
    ]


def test_plan_refresh_guarded_drift_requires_guarded_refresh(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="ticket",
        version="1.4.0",
        rel="scripts/ticket_engine_core.py",
        source_text="print('new')\n",
        cache_text="print('old')\n",
    )

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.axes.selected_mutation_mode == SelectedMutationMode.GUARDED_REFRESH
    assert result.axes.runtime_config_state == RuntimeConfigState.UNCHECKED
    assert result.terminal_status == TerminalPlanStatus.BLOCKED_PREFLIGHT


def test_plan_refresh_residue_blocks_preflight(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    residue = repo_root / "plugins/turbo-mode/handoff/1.6.0/scripts/__pycache__/x.pyc"
    residue.parent.mkdir(parents=True)
    residue.write_bytes(b"compiled")

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.axes.preflight_state == PreflightState.BLOCKED
    assert result.terminal_status == TerminalPlanStatus.BLOCKED_PREFLIGHT
    assert result.residue_issues[0].reason == "generated-residue"


def test_plan_refresh_rejects_invalid_mode(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)

    with pytest.raises(RefreshError, match="mode must be dry-run or plan-refresh"):
        plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="refresh")


def test_plan_refresh_preserves_diff_facts_when_config_blocks(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("[features]\nplugin_hooks = true\n", encoding="utf-8")
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="scripts/search.py",
        source_text="print('new')\n",
        cache_text="print('old')\n",
    )

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.terminal_status == TerminalPlanStatus.BLOCKED_PREFLIGHT
    assert result.axes.filesystem_state == FilesystemState.DRIFT
    assert result.axes.coverage_state == CoverageState.COVERED
    assert [item.canonical_path for item in result.diff_classification] == [
        "handoff/1.6.0/scripts/search.py"
    ]


def test_plan_refresh_added_command_bearing_doc_is_coverage_gap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    source_doc = repo_root / "plugins/turbo-mode/ticket/1.4.0/skills/ticket/references/new.md"
    source_doc.parent.mkdir(parents=True, exist_ok=True)
    source_doc.write_text("```bash\npython3 scripts/ticket_read.py list\n```\n", encoding="utf-8")

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.terminal_status == TerminalPlanStatus.COVERAGE_GAP_BLOCKED
    assert result.diff_classification[0].canonical_path == (
        "ticket/1.4.0/skills/ticket/references/new.md"
    )
    assert result.diff_classification[0].outcome == PathOutcome.COVERAGE_GAP_FAIL
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_planner.py -q
```

Expected: fail because `plan_refresh` and result models do not exist.

- [ ] **Step 3: Implement aggregate planner**

Add to `planner.py`:

```python
from .classifier import classify_diff_path
from .manifests import build_manifest, diff_manifests, scan_generated_residue
from .models import (
    CoverageState,
    CoverageStatus,
    DiffEntry,
    FilesystemState,
    MutationMode,
    PathClassification,
    PlanAxes,
    PreflightState,
    RefreshError,
    ResidueIssue,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
    fail,
)
from .state_machine import derive_terminal_plan_status


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


def plan_refresh(
    *,
    repo_root: Path,
    codex_home: Path,
    mode: str,
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
                classifications.extend(_classify_diff_for_spec(spec, diff) for diff in spec_diffs)
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

    axes = _derive_axes(
        diffs=diffs,
        classifications=classifications,
        runtime_config=runtime_config,
        preflight_reasons=tuple(preflight_reasons),
        manifest_collected=manifest_collected,
    )
    terminal_status = derive_terminal_plan_status(axes)
    future_external_command = (
        select_future_external_command(axes)
        if mode == "plan-refresh"
        else None
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
    )


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


def _read_text_for_entry(root: Path, entry: object | None) -> str:
    if entry is None:
        return ""
    canonical_path = getattr(entry, "canonical_path")
    prefix = "/".join(canonical_path.split("/")[:2])
    rel = canonical_path.removeprefix(prefix + "/")
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
```

Add axis derivation and future command advice:

```python
def _derive_axes(
    *,
    diffs: list[DiffEntry],
    classifications: list[PathClassification],
    runtime_config: RuntimeConfigCheck | None,
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
        runtime_config_state = RuntimeConfigState.UNCHECKED
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
        return "python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --refresh --smoke light"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_planner.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/turbo-mode/tools/refresh/planner.py plugins/turbo-mode/tools/refresh/tests/test_planner.py
git commit -m "feat: derive turbo-mode refresh dry-run status"
```

---

### Task 4: Write Local-Only Evidence Safely

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/evidence.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_evidence.py`

- [ ] **Step 1: Write failing evidence tests**

Create `plugins/turbo-mode/tools/refresh/tests/test_evidence.py` with:

```python
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from refresh.evidence import evidence_payload, write_local_evidence
from refresh.models import (
    CoverageState,
    FilesystemState,
    PlanAxes,
    PreflightState,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.planner import RefreshPaths, RefreshPlanResult


def empty_result(tmp_path: Path) -> RefreshPlanResult:
    paths = RefreshPaths(
        repo_root=tmp_path / "repo",
        codex_home=tmp_path / ".codex",
        marketplace_path=tmp_path / "repo/.agents/plugins/marketplace.json",
        config_path=tmp_path / ".codex/config.toml",
        local_only_root=tmp_path / ".codex/local-only/turbo-mode-refresh",
    )
    axes = PlanAxes(
        filesystem_state=FilesystemState.NO_DRIFT,
        coverage_state=CoverageState.NOT_APPLICABLE,
        runtime_config_state=RuntimeConfigState.UNCHECKED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.NONE,
    )
    return RefreshPlanResult(
        mode="dry-run",
        paths=paths,
        residue_issues=(),
        diffs=(),
        diff_classification=(),
        runtime_config=None,
        axes=axes,
        terminal_status=TerminalPlanStatus.FILESYSTEM_NO_DRIFT,
    )


def test_evidence_payload_serializes_axes_and_terminal_status(tmp_path: Path) -> None:
    payload = evidence_payload(empty_result(tmp_path), run_id="run-1")

    assert payload["schema_version"] == "turbo-mode-refresh-plan-02"
    assert payload["run_id"] == "run-1"
    assert payload["mode"] == "dry-run"
    assert payload["terminal_plan_status"] == "filesystem-no-drift"
    assert payload["axes"]["filesystem_state"] == "no-drift"


def test_write_local_evidence_uses_private_permissions(tmp_path: Path) -> None:
    result = empty_result(tmp_path)

    evidence_path = write_local_evidence(result, run_id="run-1")

    run_dir_mode = stat.S_IMODE(evidence_path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(evidence_path.stat().st_mode)
    assert run_dir_mode == 0o700
    assert file_mode == 0o600
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["run_id"] == "run-1"


def test_write_local_evidence_rejects_unsafe_run_id(tmp_path: Path) -> None:
    result = empty_result(tmp_path)

    with pytest.raises(ValueError, match="one path segment"):
        write_local_evidence(result, run_id="../escape")


def test_write_local_evidence_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    first = write_local_evidence(result, run_id="run-1")

    with pytest.raises(FileExistsError):
        write_local_evidence(result, run_id="run-1")

    assert json.loads(first.read_text(encoding="utf-8"))["run_id"] == "run-1"


def test_write_local_evidence_rejects_symlinked_run_directory(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    evidence_root = result.paths.local_only_root
    evidence_root.mkdir(parents=True, mode=0o700)
    (evidence_root / "run-1").symlink_to(target, target_is_directory=True)

    with pytest.raises(FileExistsError, match="run directory already exists"):
        write_local_evidence(result, run_id="run-1")


def test_write_local_evidence_rejects_broad_existing_root(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    result.paths.local_only_root.mkdir(parents=True)
    os.chmod(result.paths.local_only_root, 0o755)

    with pytest.raises(PermissionError, match="evidence root permissions"):
        write_local_evidence(result, run_id="run-1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_evidence.py -q
```

Expected: fail because `refresh.evidence` does not exist.

- [ ] **Step 3: Implement evidence writer**

Create `plugins/turbo-mode/tools/refresh/evidence.py`:

```python
from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .planner import RefreshPlanResult

SCHEMA_VERSION = "turbo-mode-refresh-plan-02"


def evidence_payload(result: RefreshPlanResult, *, run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": result.mode,
        "repo_root": str(result.paths.repo_root),
        "codex_home": str(result.paths.codex_home),
        "marketplace_path": str(result.paths.marketplace_path),
        "config_path": str(result.paths.config_path),
        "local_only_evidence_root": str(result.paths.local_only_root / run_id),
        "residue_issues": _json_safe(result.residue_issues),
        "diffs": _json_safe(result.diffs),
        "diff_classification": _json_safe(result.diff_classification),
        "runtime_config": _json_safe(result.runtime_config),
        "axes": _json_safe(result.axes),
        "terminal_plan_status": result.terminal_status.value,
        "future_external_command": result.future_external_command,
        "mutation_command_available": result.mutation_command_available,
        "requires_plan": result.requires_plan,
        "omission_reasons": _omission_reasons(result),
    }


def write_local_evidence(result: RefreshPlanResult, *, run_id: str) -> Path:
    safe_run_id = validate_run_id(run_id)
    ensure_private_evidence_root(result.paths.local_only_root)
    run_dir = result.paths.local_only_root / safe_run_id
    try:
        os.mkdir(run_dir, 0o700)
    except FileExistsError as exc:
        raise FileExistsError(
            "create evidence run directory failed: run directory already exists. "
            f"Got: {str(run_dir)!r:.100}"
        ) from exc
    path = run_dir / f"{result.mode}.summary.json"
    payload = evidence_payload(result, run_id=safe_run_id)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)
    return path


def ensure_private_evidence_root(root: Path) -> None:
    reject_symlinks_in_path(root)
    if root.exists():
        if not root.is_dir():
            raise NotADirectoryError(
                "validate evidence root failed: root is not a directory. "
                f"Got: {str(root)!r:.100}"
            )
        mode = stat.S_IMODE(root.stat().st_mode)
        if mode != 0o700:
            raise PermissionError(
                "validate evidence root failed: evidence root permissions must be 0700. "
                f"Got: {oct(mode)!r:.100}"
            )
        return
    root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    reject_symlinks_in_path(root)


def reject_symlinks_in_path(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            path_stat = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(path_stat.st_mode):
            raise ValueError(
                "validate evidence path failed: symlinks are not allowed. "
                f"Got: {str(current)!r:.100}"
            )


def validate_run_id(run_id: str) -> str:
    if not run_id or "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
        raise ValueError(
            "validate run id failed: run id must be one path segment. "
            f"Got: {run_id!r:.100}"
        )
    if ".." in run_id:
        raise ValueError(
            "validate run id failed: traversal marker is not allowed. "
            f"Got: {run_id!r:.100}"
        )
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in run_id):
        raise ValueError(
            "validate run id failed: unsupported character. "
            f"Got: {run_id!r:.100}"
        )
    return run_id


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _omission_reasons(result: RefreshPlanResult) -> dict[str, str]:
    return {
        "app_server_inventory": "outside-plan-02",
        "process_gate": "outside-plan-02",
        "post_refresh_cache_manifest": "outside-plan-02",
        "smoke_summary": "outside-plan-02",
        "commit_safe_summary": "outside-plan-02",
    }
```

- [ ] **Step 4: Run evidence tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_evidence.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/turbo-mode/tools/refresh/evidence.py plugins/turbo-mode/tools/refresh/tests/test_evidence.py
git commit -m "feat: write turbo-mode refresh local evidence"
```

---

### Task 5: Add CLI For `--dry-run` And `--plan-refresh`

**Files:**

- Create: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `plugins/turbo-mode/tools/refresh/tests/test_cli.py` with:

```python
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
TOOL = REPO_ROOT / "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"


def write_marketplace(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "name": "turbo-mode",
                "plugins": [
                    {
                        "name": "handoff",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/handoff/1.6.0",
                        },
                    },
                    {
                        "name": "ticket",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/ticket/1.4.0",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def write_valid_marketplace(repo_root: Path) -> None:
    write_marketplace(repo_root / ".agents/plugins/marketplace.json")


def write_aligned_config(codex_home: Path, repo_root: Path) -> None:
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )


def write_plugin_pair(
    repo_root: Path,
    codex_home: Path,
    *,
    plugin: str,
    version: str,
    rel: str,
    source_text: str,
    cache_text: str,
) -> None:
    source = repo_root / f"plugins/turbo-mode/{plugin}/{version}" / rel
    cache = codex_home / f"plugins/cache/turbo-mode/{plugin}/{version}" / rel
    source.parent.mkdir(parents=True, exist_ok=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    cache.write_text(cache_text, encoding="utf-8")


def ensure_complete_plugin_roots(repo_root: Path, codex_home: Path) -> None:
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="README.md",
        source_text="handoff same\n",
        cache_text="handoff same\n",
    )
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="ticket",
        version="1.4.0",
        rel="README.md",
        source_text="ticket same\n",
        cache_text="ticket same\n",
    )


def run_tool(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def tree_snapshot(root: Path) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for path in sorted([root, *root.rglob("*")]):
        rel = "." if path == root else path.relative_to(root).as_posix()
        path_stat = path.lstat()
        mode = oct(stat.S_IMODE(path_stat.st_mode))
        if stat.S_ISDIR(path_stat.st_mode):
            entries[rel] = {"kind": "dir", "mode": mode}
        elif stat.S_ISLNK(path_stat.st_mode):
            entries[rel] = {
                "kind": "symlink",
                "mode": mode,
                "target": os.readlink(path),
            }
        elif stat.S_ISREG(path_stat.st_mode):
            entries[rel] = {
                "kind": "file",
                "mode": mode,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        else:
            entries[rel] = {"kind": "other", "mode": mode}
    return entries


def path_snapshot(path: Path) -> dict[str, str]:
    path_stat = path.lstat()
    mode = oct(stat.S_IMODE(path_stat.st_mode))
    if stat.S_ISLNK(path_stat.st_mode):
        return {"kind": "symlink", "mode": mode, "target": os.readlink(path)}
    if stat.S_ISREG(path_stat.st_mode):
        return {
            "kind": "file",
            "mode": mode,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return {"kind": "other", "mode": mode}


def test_cli_dry_run_outputs_json_and_writes_evidence(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)

    completed = run_tool(
        [
            "--dry-run",
            "--json",
            "--run-id",
            "run-1",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["terminal_plan_status"] == "filesystem-no-drift"
    assert payload["runtime_config"]["plugin_enablement_state"] == {
        "handoff@turbo-mode": "enabled",
        "ticket@turbo-mode": "enabled",
    }
    assert (codex_home / "local-only/turbo-mode-refresh/run-1/dry-run.summary.json").is_file()


def test_cli_plan_refresh_emits_future_command_advice_for_fast_safe_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="scripts/search.py",
        source_text="print('new')\n",
        cache_text="print('old')\n",
    )

    completed = run_tool(
        [
            "--plan-refresh",
            "--json",
            "--run-id",
            "run-2",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["terminal_plan_status"] == "blocked-preflight"
    assert payload["axes"]["filesystem_state"] == "drift"
    assert payload["axes"]["runtime_config_state"] == "unchecked"
    assert payload["mutation_command_available"] is False
    assert payload["requires_plan"] == "future-mutation-plan"
    assert payload["future_external_command"].endswith("--refresh --smoke light")


def test_cli_bare_invocation_does_not_write_bytecode(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    refresh_root = REPO_ROOT / "plugins/turbo-mode/tools/refresh"
    assert not list(refresh_root.rglob("__pycache__"))
    assert not list(refresh_root.rglob("*.pyc"))
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
    }

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "bare-no-bytecode",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ],
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert not list(refresh_root.rglob("__pycache__"))
    assert not list(refresh_root.rglob("*.pyc"))


def test_cli_evidence_path_errors_report_without_traceback(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    evidence_root = codex_home / "local-only/turbo-mode-refresh"
    evidence_root.mkdir(parents=True)
    evidence_root.chmod(0o755)

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "bad-evidence-root",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 1
    assert "validate evidence root failed" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_mutation_modes_in_plan_02() -> None:
    completed = run_tool(["--refresh"])

    assert completed.returncode == 2
    assert "outside Plan 02" in completed.stderr


def test_cli_rejects_exact_future_command_shapes_with_plan_02_message() -> None:
    refresh = run_tool(["--refresh", "--smoke", "light"])
    guarded = run_tool(["--guarded-refresh", "--smoke", "standard"])

    assert refresh.returncode == 2
    assert guarded.returncode == 2
    assert "outside Plan 02" in refresh.stderr
    assert "outside Plan 02" in guarded.stderr
    assert "unrecognized arguments" not in refresh.stderr
    assert "unrecognized arguments" not in guarded.stderr
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py -q
```

Expected: fail because the CLI script does not exist.

- [ ] **Step 3: Implement CLI entrypoint**

Create `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.evidence import evidence_payload, write_local_evidence
from refresh.models import RefreshError
from refresh.planner import plan_refresh


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess Turbo Mode installed-cache drift without mutation."
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--plan-refresh", action="store_true")
    modes.add_argument("--refresh", action="store_true")
    modes.add_argument("--guarded-refresh", action="store_true")
    parser.add_argument("--smoke", choices=("light", "standard"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--run-id")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh or args.guarded_refresh:
        parser.error("--refresh and --guarded-refresh are outside Plan 02")
    if args.smoke is not None:
        parser.error("--smoke is only accepted with rejected future command shapes")
    mode = "plan-refresh" if args.plan_refresh else "dry-run"
    run_id = args.run_id or uuid.uuid4().hex
    try:
        result = plan_refresh(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            mode=mode,
        )
        evidence_path = write_local_evidence(result, run_id=run_id)
    except (RefreshError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = evidence_payload(result, run_id=run_id)
    payload["evidence_path"] = str(evidence_path)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode: {mode}")
        print(f"terminal_plan_status: {result.terminal_status.value}")
        print(f"evidence_path: {evidence_path}")
        print(f"mutation_command_available: {str(result.mutation_command_available).lower()}")
        if result.future_external_command is not None:
            print(f"future_external_command: {result.future_external_command}")
            print(f"requires_plan: {result.requires_plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh/tests/test_cli.py
git commit -m "feat: add turbo-mode refresh dry-run cli"
```

---

### Task 6: Add Plan 02 Regression Gates

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

- [ ] **Step 1: Add regressions for future command advice stop conditions**

Append to `test_planner.py`:

```python
def test_plan_refresh_emits_no_future_command_for_coverage_gap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel=".codex-plugin/plugin.json",
        source_text='{"name":"new"}\n',
        cache_text='{"name":"old"}\n',
    )

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.terminal_status == TerminalPlanStatus.COVERAGE_GAP_BLOCKED
    assert result.future_external_command is None
    assert result.mutation_command_available is False


def test_plan_refresh_repairable_runtime_mismatch_emits_future_guarded_advice(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/other"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )
    ensure_complete_plugin_roots(repo_root, codex_home)

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.terminal_status == TerminalPlanStatus.REPAIRABLE_RUNTIME_CONFIG_MISMATCH
    assert result.mutation_command_available is False
    assert result.requires_plan == "future-mutation-plan"
    assert result.future_external_command is not None
    assert "--guarded-refresh --smoke standard" in result.future_external_command


def test_plan_refresh_unrepairable_config_suppresses_future_advice_for_covered_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = false\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="scripts/search.py",
        source_text="print('new')\n",
        cache_text="print('old')\n",
    )

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.axes.runtime_config_state == RuntimeConfigState.UNREPAIRABLE_MISMATCH
    assert result.axes.coverage_state == CoverageState.COVERED
    assert result.future_external_command is None
    assert result.requires_plan is None


def test_plan_refresh_unknown_config_suppresses_future_advice_for_covered_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="scripts/search.py",
        source_text="print('new')\n",
        cache_text="print('old')\n",
    )

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.axes.runtime_config_state == RuntimeConfigState.UNKNOWN
    assert result.axes.coverage_state == CoverageState.COVERED
    assert result.future_external_command is None
    assert result.requires_plan is None


def test_plan_refresh_disabled_plugin_enablement_blocks_filesystem_no_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = false\n',
        encoding="utf-8",
    )
    ensure_complete_plugin_roots(repo_root, codex_home)

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.axes.runtime_config_state == RuntimeConfigState.UNREPAIRABLE_MISMATCH
    assert result.terminal_status == TerminalPlanStatus.UNREPAIRABLE_RUNTIME_CONFIG_MISMATCH
    assert result.future_external_command is None
    assert result.runtime_config is not None
    assert result.runtime_config.plugin_enablement_state["ticket@turbo-mode"] == "disabled"


def test_plan_refresh_missing_plugin_enablement_blocks_filesystem_no_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )
    ensure_complete_plugin_roots(repo_root, codex_home)

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.axes.runtime_config_state == RuntimeConfigState.UNKNOWN
    assert result.terminal_status == TerminalPlanStatus.BLOCKED_PREFLIGHT
    assert result.future_external_command is None
    assert result.runtime_config is not None
    assert result.runtime_config.plugin_enablement_state["ticket@turbo-mode"] == "missing"


def test_plan_refresh_repairable_mismatch_suppresses_future_advice_for_coverage_gap(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/other"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )
    ensure_complete_plugin_roots(repo_root, codex_home)
    source_doc = repo_root / "plugins/turbo-mode/ticket/1.4.0/skills/ticket/references/new.md"
    source_doc.parent.mkdir(parents=True, exist_ok=True)
    source_doc.write_text("```bash\npython3 scripts/ticket_read.py list\n```\n", encoding="utf-8")

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="plan-refresh")

    assert result.axes.runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH
    assert result.axes.coverage_state == CoverageState.COVERAGE_GAP
    assert result.future_external_command is None
    assert result.requires_plan is None


def test_plan_refresh_manifest_symlink_failure_becomes_blocked_result(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    link = repo_root / "plugins/turbo-mode/handoff/1.6.0/skills"
    link.symlink_to(outside)

    result = plan_refresh(repo_root=repo_root, codex_home=codex_home, mode="dry-run")

    assert result.terminal_status == TerminalPlanStatus.BLOCKED_PREFLIGHT
    assert any("symlinks are not allowed" in reason for reason in result.axes.reasons)
```

- [ ] **Step 2: Add CLI regression for no installed-cache or config mutation**

Append to `test_cli.py`. Integrate any new imports at module top; do not paste duplicate import blocks in the middle of the file.

```python
def test_cli_dry_run_does_not_modify_cache_tree_or_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.6.0",
        rel="README.md",
        source_text="source drift\n",
        cache_text="cache original\n",
    )
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="ticket",
        version="1.4.0",
        rel="scripts/ticket_engine_core.py",
        source_text="print('source')\n",
        cache_text="print('cache')\n",
    )
    cache_root = codex_home / "plugins/cache/turbo-mode"
    config = codex_home / "config.toml"
    before_cache = tree_snapshot(cache_root)
    before_config = path_snapshot(config)

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "run-3",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    assert tree_snapshot(cache_root) == before_cache
    assert path_snapshot(config) == before_config
```

- [ ] **Step 3: Run full refresh package tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: all refresh tests pass.

- [ ] **Step 4: Run ruff**

Run:

```bash
uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py
```

Expected: no issues.

- [ ] **Step 5: Run residue gate**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
```

Expected: prints nothing.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py
git commit -m "test: cover turbo-mode refresh non-mutating plan gates"
```

---

### Task 7: Run Live Non-Mutating Smoke From The Real Checkout

**Files:**

- No source edits expected.

- [ ] **Step 1: Confirm working tree before smoke**

Run:

```bash
git status --short --branch
```

Expected: on the Plan 02 branch with a clean working tree after Task 6 commit.

- [ ] **Step 2: Capture pre-smoke mutable-surface manifests**

Run:

```bash
set -euo pipefail
mkdir -p /private/tmp/codex-tool-dev-refresh-plan-02
python3 - <<'PY' > /private/tmp/codex-tool-dev-refresh-plan-02/cache-before.json
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

roots = [
    Path("/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0"),
    Path("/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0"),
]
rows: list[dict[str, str]] = []
for root in roots:
    for path in sorted([root, *root.rglob("*")]):
        path_stat = path.lstat()
        row = {
            "path": f"{root.name}/{path.relative_to(root).as_posix() if path != root else '.'}",
            "mode": oct(stat.S_IMODE(path_stat.st_mode)),
        }
        if stat.S_ISDIR(path_stat.st_mode):
            row["kind"] = "dir"
        elif stat.S_ISLNK(path_stat.st_mode):
            row["kind"] = "symlink"
            row["target"] = os.readlink(path)
        elif stat.S_ISREG(path_stat.st_mode):
            row["kind"] = "file"
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            row["kind"] = "other"
        rows.append(row)
print(json.dumps(rows, indent=2, sort_keys=True))
PY
python3 - <<'PY' > /private/tmp/codex-tool-dev-refresh-plan-02/config-before.json
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

path = Path("/Users/jp/.codex/config.toml")
path_stat = path.lstat()
print(json.dumps({
    "kind": "file",
    "mode": oct(stat.S_IMODE(path_stat.st_mode)),
    "path": str(path),
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
}, indent=2, sort_keys=True))
PY
```

Expected:

- cache manifest file exists and is non-empty;
- config manifest file exists and is non-empty;
- cache manifest records file content hashes, file modes, directory entries, symlink entries, and symlink targets;
- config manifest records file content hash and mode;
- these files are local smoke evidence only and must not be committed.

- [ ] **Step 3: Run real `--dry-run` without JSON**

Run:

```bash
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --dry-run
```

Expected:

- command exits 0 or exits 1 only for a real read-only preflight condition;
- it writes one local-only evidence file under `/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/dry-run.summary.json`;
- it does not create `__pycache__` or `*.pyc` in the repo even without `PYTHONDONTWRITEBYTECODE`;
- it does not write installed cache files;
- it does not write `/Users/jp/.codex/config.toml`;
- it does not start app-server.

- [ ] **Step 4: Run real `--plan-refresh --json`**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --plan-refresh --json
```

Expected:

- JSON includes `schema_version = "turbo-mode-refresh-plan-02"`;
- JSON includes all state axes;
- JSON includes `terminal_plan_status`;
- JSON includes `future_external_command` only when `preflight_state = passed` and local filesystem/config facts identify an explicitly allowed future mutation lane;
- JSON includes `mutation_command_available = false` for every Plan 02 result;
- JSON includes `requires_plan = "future-mutation-plan"` when `future_external_command` is present;
- JSON includes `future_external_command = null` for coverage-gap, unknown config, unrepairable config, root/preflight failure, and `filesystem-no-drift` statuses.

- [ ] **Step 5: Compare post-smoke mutable-surface manifests**

Run:

```bash
set -euo pipefail
python3 - <<'PY' > /private/tmp/codex-tool-dev-refresh-plan-02/cache-after.json
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

roots = [
    Path("/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0"),
    Path("/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0"),
]
rows: list[dict[str, str]] = []
for root in roots:
    for path in sorted([root, *root.rglob("*")]):
        path_stat = path.lstat()
        row = {
            "path": f"{root.name}/{path.relative_to(root).as_posix() if path != root else '.'}",
            "mode": oct(stat.S_IMODE(path_stat.st_mode)),
        }
        if stat.S_ISDIR(path_stat.st_mode):
            row["kind"] = "dir"
        elif stat.S_ISLNK(path_stat.st_mode):
            row["kind"] = "symlink"
            row["target"] = os.readlink(path)
        elif stat.S_ISREG(path_stat.st_mode):
            row["kind"] = "file"
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            row["kind"] = "other"
        rows.append(row)
print(json.dumps(rows, indent=2, sort_keys=True))
PY
python3 - <<'PY' > /private/tmp/codex-tool-dev-refresh-plan-02/config-after.json
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

path = Path("/Users/jp/.codex/config.toml")
path_stat = path.lstat()
print(json.dumps({
    "kind": "file",
    "mode": oct(stat.S_IMODE(path_stat.st_mode)),
    "path": str(path),
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
}, indent=2, sort_keys=True))
PY
cmp /private/tmp/codex-tool-dev-refresh-plan-02/cache-before.json \
  /private/tmp/codex-tool-dev-refresh-plan-02/cache-after.json
cmp /private/tmp/codex-tool-dev-refresh-plan-02/config-before.json \
  /private/tmp/codex-tool-dev-refresh-plan-02/config-after.json
```

Expected:

- both `cmp` commands exit 0;
- any difference is a hard failure of the non-mutating contract, even if `git status` is clean.

- [ ] **Step 6: Confirm no repo residue**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
git status --short --branch
```

Expected:

- full plugin-root residue command prints nothing;
- git status remains clean.

If real `--dry-run` or `--plan-refresh` stops on a real preflight condition, do not weaken the preflight. Record the exact terminal status and decide whether the condition belongs in Plan 02 implementation or a later runtime/config lane.

---

## Final Verification Gate

Run:

```bash
set -euo pipefail
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py
test -s /private/tmp/codex-tool-dev-refresh-plan-02/cache-before.json
test -s /private/tmp/codex-tool-dev-refresh-plan-02/cache-after.json
test -s /private/tmp/codex-tool-dev-refresh-plan-02/config-before.json
test -s /private/tmp/codex-tool-dev-refresh-plan-02/config-after.json
cmp /private/tmp/codex-tool-dev-refresh-plan-02/cache-before.json \
  /private/tmp/codex-tool-dev-refresh-plan-02/cache-after.json
cmp /private/tmp/codex-tool-dev-refresh-plan-02/config-before.json \
  /private/tmp/codex-tool-dev-refresh-plan-02/config-after.json
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
git status --short --branch
```

Expected:

- all refresh tests pass;
- ruff reports no issues;
- pre/post installed-cache and config evidence files exist;
- installed-cache and `/Users/jp/.codex/config.toml` pre/post metadata manifests are identical;
- full plugin-root residue scan prints nothing;
- working tree is clean after final commit;
- no command writes installed cache roots;
- no command writes `/Users/jp/.codex/config.toml`;
- no command starts app-server.

## Hard Stop Conditions

Stop implementation and ask for review if any of these occur:

- The planner needs app-server inventory to prove runtime identity, installed registration, post-refresh state, hook inventory, or any claim beyond local source/cache/config filesystem state.
- The implementation needs to mutate installed cache, global config, marketplace metadata, or process state.
- `--plan-refresh` would need to expose an executable mutation command instead of future-only command advice marked with `mutation_command_available = false`.
- A classifier result seems wrong and would require changing `classifier.py` policy rather than consuming it.
- Local-only evidence needs raw process listings, app-server transcripts, or sensitivity scanning beyond the Plan 02 summary payload.
- Real checkout smoke exposes config-state ambiguity that is not represented by the existing `RuntimeConfigState` axis.

## Hand-Off To Plan 03

Plan 03 may add read-only app-server inventory if the runtime identity and schema-capture contract is ready. Mutation plans must remain separate until process gates, locks, rollback/recovery, app-server install, smoke execution, and commit-safe evidence validation have their own implementation plan.
