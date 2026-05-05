from __future__ import annotations

import json
from pathlib import Path

import pytest
from refresh.models import RefreshError, RuntimeConfigState
from refresh.planner import (
    build_paths,
    build_plugin_specs,
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
