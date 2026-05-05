from __future__ import annotations

import json
from pathlib import Path

import pytest
from refresh.models import (
    CoverageState,
    FilesystemState,
    PathOutcome,
    PreflightState,
    RefreshError,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.planner import (
    build_paths,
    build_plugin_specs,
    plan_refresh,
    read_runtime_config_state,
    validate_repo_marketplace,
)


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


def write_marketplace(
    path: Path,
    *,
    ticket_path: str = "./plugins/turbo-mode/ticket/1.4.0",
) -> None:
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
