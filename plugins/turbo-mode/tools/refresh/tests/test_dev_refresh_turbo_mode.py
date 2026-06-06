from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from dev_refresh_turbo_mode import (
    build_dev_install_requests,
    load_marketplace_plugin_names,
    load_marketplace_plugin_specs,
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
                            "path": "./plugins/turbo-mode/handoff",
                        },
                    },
                    {
                        "name": "review-family",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/review-family",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def seed_source_marketplace(repo_root: Path) -> None:
    handoff_root = repo_root / "plugins/turbo-mode/handoff"
    review_root = repo_root / "plugins/turbo-mode/review-family"
    handoff_root.mkdir(parents=True)
    review_root.mkdir(parents=True)
    (handoff_root / ".codex-plugin").mkdir()
    (handoff_root / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "handoff", "version": "1.7.0"}),
        encoding="utf-8",
    )
    (handoff_root / "README.md").write_text("handoff source\n", encoding="utf-8")
    (handoff_root / "hooks").mkdir()
    (handoff_root / "hooks/hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (review_root / ".codex-plugin").mkdir()
    (review_root / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "review-family", "version": "0.1.0"}),
        encoding="utf-8",
    )
    (review_root / "README.md").write_text("review-family source\n", encoding="utf-8")


def test_build_dev_install_requests_refreshes_entire_marketplace(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_marketplace(repo_root)

    plugin_names = load_marketplace_plugin_names(repo_root / ".agents/plugins/marketplace.json")
    requests = build_dev_install_requests(
        marketplace_path=repo_root / ".agents/plugins/marketplace.json",
        plugin_names=plugin_names,
    )

    assert plugin_names == ("handoff", "review-family")
    assert [request.get("method") for request in requests] == [
        "initialize",
        "initialized",
        "plugin/install",
        "plugin/install",
    ]
    assert [request["params"]["pluginName"] for request in requests if request.get("id")] == [
        "handoff",
        "review-family",
    ]


def test_marketplace_specs_use_plugin_manifest_version_for_cache_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    write_marketplace(repo_root)
    seed_source_marketplace(repo_root)
    handoff_manifest = (
        repo_root
        / "plugins/turbo-mode/handoff/.codex-plugin/plugin.json"
    )
    handoff_manifest.write_text(
        json.dumps({"name": "handoff", "version": "1.7.0"}),
        encoding="utf-8",
    )

    specs = load_marketplace_plugin_specs(
        repo_root / ".agents/plugins/marketplace.json",
        repo_root,
        codex_home,
    )

    handoff_spec = next(spec for spec in specs if spec.name == "handoff")
    assert handoff_spec.source_root == repo_root / "plugins/turbo-mode/handoff"
    assert handoff_spec.version == "1.7.0"
    assert handoff_spec.cache_root == codex_home / "plugins/cache/turbo-mode/handoff/1.7.0"


def test_run_dev_refresh_installs_marketplace_and_writes_proof(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    write_marketplace(repo_root)
    seed_source_marketplace(repo_root)

    def fake_roundtrip(
        requests: list[dict[str, object]],
        *,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> list[dict[str, object]]:
        assert env_overrides == {"CODEX_HOME": str(codex_home)}
        assert cwd is not None
        for plugin_name, version in (("handoff", "1.7.0"), ("review-family", "0.1.0")):
            source = repo_root / f"plugins/turbo-mode/{plugin_name}"
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
                "handoff": str(repo_root / "plugins/turbo-mode/handoff"),
                "review-family": str(repo_root / "plugins/turbo-mode/review-family"),
            },
            skills=("handoff:save", "review-family:implementation-review"),
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
    assert summary["plugins"] == ["handoff", "review-family"]
    assert summary["source_cache_diff_count"] == 0
    assert summary["runtime_inventory_state"] == "aligned"
    assert summary["guarded_refresh_used"] is False
    assert summary["summary_path"].endswith("unit-dev-refresh/dev-refresh.summary.json")
    assert Path(summary["summary_path"]).exists()


def test_run_dev_refresh_rejects_source_cache_drift_after_install(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    write_marketplace(repo_root)
    seed_source_marketplace(repo_root)

    def fake_roundtrip(
        _requests: list[dict[str, object]],
        *,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> list[dict[str, object]]:
        assert env_overrides == {"CODEX_HOME": str(codex_home)}
        assert cwd is not None
        for plugin_name, version in (("handoff", "1.7.0"), ("review-family", "0.1.0")):
            source = repo_root / f"plugins/turbo-mode/{plugin_name}"
            cache = codex_home / f"plugins/cache/turbo-mode/{plugin_name}/{version}"
            shutil.copytree(source, cache, dirs_exist_ok=True)
        (codex_home / "plugins/cache/turbo-mode/handoff/1.7.0/README.md").write_text(
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
    seed_source_marketplace(repo_root)
    residue = repo_root / "plugins/turbo-mode/handoff/.pytest_cache/.gitignore"
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
        for plugin_name, version in (("handoff", "1.7.0"), ("review-family", "0.1.0")):
            source = repo_root / f"plugins/turbo-mode/{plugin_name}"
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


def test_package_alias_points_at_personal_plugin_sync_lane() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert "turbo:dev-refresh" not in scripts
    assert (
        "plugins/turbo-mode/tools/sync_personal_plugins.py"
        in scripts["turbo:plan-personal-plugins"]
    )
    assert "--sync" not in scripts["turbo:plan-personal-plugins"]
    assert (
        "plugins/turbo-mode/tools/sync_personal_plugins.py --sync"
        in scripts["turbo:sync-personal-plugins"]
    )
    assert "dev_refresh_turbo_mode.py" not in scripts["turbo:sync-personal-plugins"]
    assert "refresh_installed_turbo_mode.py" not in scripts["turbo:sync-personal-plugins"]
    assert "--guarded-refresh" not in scripts["turbo:sync-personal-plugins"]


def test_dev_refresh_lane_does_not_import_planner() -> None:
    source = (REPO_ROOT / "plugins/turbo-mode/tools/dev_refresh_turbo_mode.py").read_text(
        encoding="utf-8"
    )

    assert "from refresh.planner" not in source
