from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from dev_refresh_turbo_mode import (
    build_dev_install_requests,
    load_marketplace_plugin_names,
    run_dev_refresh,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


def write_marketplace(repo_root: Path) -> None:
    marketplace = repo_root / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
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


def seed_source_marketplace(repo_root: Path, *, ticket_hook_command: str | None = None) -> None:
    handoff_root = repo_root / "plugins/turbo-mode/handoff/1.6.0"
    ticket_root = repo_root / "plugins/turbo-mode/ticket/1.4.0"
    handoff_root.mkdir(parents=True)
    ticket_root.mkdir(parents=True)
    (handoff_root / "README.md").write_text("handoff source\n", encoding="utf-8")
    (handoff_root / "hooks").mkdir()
    (handoff_root / "hooks/hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (ticket_root / "README.md").write_text("ticket source\n", encoding="utf-8")
    (ticket_root / "hooks").mkdir()
    (ticket_root / "hooks/ticket_engine_guard.py").write_text(
        "#!/usr/bin/env python3\nprint('guard')\n",
        encoding="utf-8",
    )
    command = ticket_hook_command or (
        "python3 /Users/jp/.codex/plugins/cache/turbo-mode/"
        "ticket/1.4.0/hooks/ticket_engine_guard.py"
    )
    (ticket_root / "hooks/hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": command,
                                    "timeout": 10,
                                }
                            ],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_dev_install_requests_refreshes_entire_marketplace(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_marketplace(repo_root)

    plugin_names = load_marketplace_plugin_names(repo_root / ".agents/plugins/marketplace.json")
    requests = build_dev_install_requests(
        marketplace_path=repo_root / ".agents/plugins/marketplace.json",
        plugin_names=plugin_names,
    )

    assert plugin_names == ("handoff", "ticket")
    assert [request.get("method") for request in requests] == [
        "initialize",
        "initialized",
        "plugin/install",
        "plugin/install",
    ]
    assert [request["params"]["pluginName"] for request in requests if request.get("id")] == [
        "handoff",
        "ticket",
    ]


def test_run_dev_refresh_installs_marketplace_and_writes_proof(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    write_marketplace(repo_root)
    seed_source_marketplace(
        repo_root,
        ticket_hook_command=(
            f"python3 {codex_home}/plugins/cache/turbo-mode/ticket/1.4.0/"
            "hooks/ticket_engine_guard.py"
        ),
    )

    def fake_roundtrip(
        requests: list[dict[str, object]],
        *,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> list[dict[str, object]]:
        assert env_overrides == {"CODEX_HOME": str(codex_home)}
        assert cwd is not None
        for plugin_name, version in (("handoff", "1.6.0"), ("ticket", "1.4.0")):
            source = repo_root / f"plugins/turbo-mode/{plugin_name}/{version}"
            cache = codex_home / f"plugins/cache/turbo-mode/{plugin_name}/{version}"
            shutil.copytree(source, cache, dirs_exist_ok=True)
        return [
            {"direction": "recv", "body": {"method": "codex/log", "params": {"message": "ready"}}},
            {"direction": "recv", "body": {"id": 0, "result": {"codexHome": str(codex_home)}}},
            {"direction": "recv", "body": {"id": 1, "result": {"authPolicy": "ON_INSTALL"}}},
            {"direction": "recv", "body": {"id": 2, "result": {"authPolicy": "ON_INSTALL"}}},
        ]

    def fake_inventory_collector(
        _paths: object,
    ) -> tuple[SimpleNamespace, tuple[dict[str, object], ...]]:
        inventory = SimpleNamespace(
            state="aligned",
            plugin_read_sources={
                "handoff": str(repo_root / "plugins/turbo-mode/handoff/1.6.0"),
                "ticket": str(repo_root / "plugins/turbo-mode/ticket/1.4.0"),
            },
            skills=("handoff:save", "ticket:ticket"),
            ticket_hook={
                "sourcePath": str(
                    codex_home
                    / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
                )
            },
            handoff_hooks=(),
            transcript_sha256="inventory-sha",
        )
        return inventory, ({"direction": "recv", "body": {"id": 0}},)

    summary = run_dev_refresh(
        repo_root=repo_root,
        codex_home=codex_home,
        run_id="unit-dev-refresh",
        verify=True,
        roundtrip=fake_roundtrip,
        inventory_collector=fake_inventory_collector,
    )

    assert summary["lane"] == "dev-refresh"
    assert summary["plugins"] == ["handoff", "ticket"]
    assert summary["source_cache_diff_count"] == 0
    assert summary["runtime_inventory_state"] == "aligned"
    assert summary["guarded_refresh_used"] is False
    assert summary["summary_path"].endswith("unit-dev-refresh/dev-refresh.summary.json")
    assert Path(summary["summary_path"]).exists()
    hooks = json.loads(
        (
            codex_home
            / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
        ).read_text(encoding="utf-8")
    )
    command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert command == (
        f"python3 {codex_home}/plugins/cache/turbo-mode/ticket/1.4.0/"
        "hooks/ticket_engine_guard.py"
    )


def test_run_dev_refresh_rejects_source_cache_drift_after_install(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    write_marketplace(repo_root)
    seed_source_marketplace(
        repo_root,
        ticket_hook_command=(
            f"python3 {codex_home}/plugins/cache/turbo-mode/ticket/1.4.0/"
            "hooks/ticket_engine_guard.py"
        ),
    )

    def fake_roundtrip(
        _requests: list[dict[str, object]],
        *,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> list[dict[str, object]]:
        assert env_overrides == {"CODEX_HOME": str(codex_home)}
        assert cwd is not None
        for plugin_name, version in (("handoff", "1.6.0"), ("ticket", "1.4.0")):
            source = repo_root / f"plugins/turbo-mode/{plugin_name}/{version}"
            cache = codex_home / f"plugins/cache/turbo-mode/{plugin_name}/{version}"
            shutil.copytree(source, cache, dirs_exist_ok=True)
        (codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/README.md").write_text(
            "stale cache\n",
            encoding="utf-8",
        )
        return [
            {"direction": "recv", "body": {"id": 0, "result": {"codexHome": str(codex_home)}}},
            {"direction": "recv", "body": {"id": 1, "result": {"authPolicy": "ON_INSTALL"}}},
            {"direction": "recv", "body": {"id": 2, "result": {"authPolicy": "ON_INSTALL"}}},
        ]

    with pytest.raises(Exception, match="source/cache drift remains after dev refresh"):
        run_dev_refresh(
            repo_root=repo_root,
            codex_home=codex_home,
            run_id="unit-dev-refresh-drift",
            verify=False,
            roundtrip=fake_roundtrip,
        )


def test_run_dev_refresh_ignores_generated_residue_in_dev_manifest(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    write_marketplace(repo_root)
    seed_source_marketplace(
        repo_root,
        ticket_hook_command=(
            f"python3 {codex_home}/plugins/cache/turbo-mode/ticket/1.4.0/"
            "hooks/ticket_engine_guard.py"
        ),
    )
    residue = repo_root / "plugins/turbo-mode/handoff/1.6.0/.pytest_cache/.gitignore"
    residue.parent.mkdir()
    residue.write_text("*\n", encoding="utf-8")

    def fake_roundtrip(
        _requests: list[dict[str, object]],
        *,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> list[dict[str, object]]:
        assert env_overrides == {"CODEX_HOME": str(codex_home)}
        assert cwd is not None
        for plugin_name, version in (("handoff", "1.6.0"), ("ticket", "1.4.0")):
            source = repo_root / f"plugins/turbo-mode/{plugin_name}/{version}"
            cache = codex_home / f"plugins/cache/turbo-mode/{plugin_name}/{version}"
            shutil.copytree(source, cache, dirs_exist_ok=True)
        return [
            {"direction": "recv", "body": {"id": 0, "result": {"codexHome": str(codex_home)}}},
            {"direction": "recv", "body": {"id": 1, "result": {"authPolicy": "ON_INSTALL"}}},
            {"direction": "recv", "body": {"id": 2, "result": {"authPolicy": "ON_INSTALL"}}},
        ]

    summary = run_dev_refresh(
        repo_root=repo_root,
        codex_home=codex_home,
        run_id="unit-dev-refresh-residue",
        verify=False,
        roundtrip=fake_roundtrip,
    )

    assert summary["source_cache_diff_count"] == 0
    assert {
        "root_kind": "source",
        "plugin": "handoff",
        "path": ".pytest_cache/.gitignore",
        "reason": "generated-residue-ignored",
    } in summary["generated_residue_ignored"]
    assert {
        "root_kind": "cache",
        "plugin": "handoff",
        "path": ".pytest_cache/.gitignore",
        "reason": "generated-residue-ignored",
    } in summary["generated_residue_ignored"]


def test_package_alias_points_at_dev_refresh_lane() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    script = package["scripts"]["turbo:dev-refresh"]

    assert "plugins/turbo-mode/tools/dev_refresh_turbo_mode.py --verify --json" in script
    assert "refresh_installed_turbo_mode.py" not in script
    assert "--guarded-refresh" not in script
