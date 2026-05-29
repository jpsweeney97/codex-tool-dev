from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import sync_personal_plugins as sync_module
from sync_personal_plugins import (
    SyncPersonalPluginsError,
    build_personal_marketplace_payload,
    build_sync_plan,
    main,
    reject_unexpected_symlinks,
    sync_personal_plugins,
)


def seed_plugin_source(repo_root: Path, plugin: str, version: str) -> Path:
    source_root = repo_root / "plugins/turbo-mode" / plugin
    source_root.mkdir(parents=True)
    (source_root / ".codex-plugin").mkdir()
    (source_root / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": plugin, "version": version}),
        encoding="utf-8",
    )
    (source_root / "README.md").write_text(f"{plugin} source\n", encoding="utf-8")
    return source_root


def seed_turbo_mode_sources(repo_root: Path) -> None:
    seed_plugin_source(repo_root, "handoff", "1.7.0")
    seed_plugin_source(repo_root, "review-family", "0.1.0")
    seed_plugin_source(repo_root, "ticket", "1.4.0")


def test_personal_marketplace_payload_uses_home_relative_plugin_paths() -> None:
    items = (
        sync_module.SyncPlanItem(
            plugin="handoff",
            source_root=Path("/repo/plugins/turbo-mode/handoff"),
            target_root=Path("/home/.codex/plugins/handoff"),
        ),
        sync_module.SyncPlanItem(
            plugin="ticket",
            source_root=Path("/repo/plugins/turbo-mode/ticket"),
            target_root=Path("/home/.codex/plugins/ticket"),
        ),
        sync_module.SyncPlanItem(
            plugin="review-family",
            source_root=Path("/repo/plugins/turbo-mode/review-family"),
            target_root=Path("/home/.codex/plugins/review-family"),
        ),
    )

    payload = build_personal_marketplace_payload(items)

    assert payload["name"] == "turbo-mode"
    plugins = {plugin["name"]: plugin for plugin in payload["plugins"]}
    assert plugins["handoff"]["source"] == {
        "source": "local",
        "path": "./.codex/plugins/handoff",
    }
    assert plugins["ticket"]["source"] == {
        "source": "local",
        "path": "./.codex/plugins/ticket",
    }
    assert plugins["review-family"]["source"] == {
        "source": "local",
        "path": "./.codex/plugins/review-family",
    }


def test_sync_plan_reports_repo_sources_and_personal_targets(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "home/.codex"
    seed_turbo_mode_sources(repo_root)

    plan = build_sync_plan(repo_root=repo_root, codex_home=codex_home)

    assert [(item.plugin, item.source_root, item.target_root) for item in plan.items] == [
        (
            "handoff",
            repo_root / "plugins/turbo-mode/handoff",
            codex_home / "plugins/handoff",
        ),
        (
            "review-family",
            repo_root / "plugins/turbo-mode/review-family",
            codex_home / "plugins/review-family",
        ),
        (
            "ticket",
            repo_root / "plugins/turbo-mode/ticket",
            codex_home / "plugins/ticket",
        ),
    ]


def test_sync_plan_discovers_new_configured_plugin_roots(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "home/.codex"
    seed_turbo_mode_sources(repo_root)
    seed_plugin_source(repo_root, "review-helper", "0.1.0")
    (repo_root / "plugins/turbo-mode/tools").mkdir(parents=True)

    plan = build_sync_plan(repo_root=repo_root, codex_home=codex_home)
    payload = build_personal_marketplace_payload(plan.items)

    assert [item.plugin for item in plan.items] == [
        "handoff",
        "review-family",
        "review-helper",
        "ticket",
    ]
    assert {
        plugin["name"]: plugin["source"]["path"] for plugin in payload["plugins"]
    } == {
        "handoff": "./.codex/plugins/handoff",
        "review-family": "./.codex/plugins/review-family",
        "review-helper": "./.codex/plugins/review-helper",
        "ticket": "./.codex/plugins/ticket",
    }


def test_sync_copies_sources_and_excludes_generated_residue(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "home/.codex"
    seed_turbo_mode_sources(repo_root)
    handoff = repo_root / "plugins/turbo-mode/handoff"
    (handoff / ".pytest_cache").mkdir()
    (handoff / ".pytest_cache/CACHEDIR.TAG").write_text("cache\n", encoding="utf-8")
    (handoff / "module").mkdir()
    (handoff / "module/__pycache__").mkdir()
    (handoff / "module/__pycache__/example.cpython-313.pyc").write_bytes(b"pyc")
    (handoff / ".DS_Store").write_bytes(b"finder")
    (handoff / ".ruff_cache").mkdir()
    (handoff / ".ruff_cache/state").write_text("ruff\n", encoding="utf-8")
    (handoff / ".mypy_cache").mkdir()
    (handoff / ".mypy_cache/state").write_text("mypy\n", encoding="utf-8")
    (handoff / ".venv").mkdir()
    (handoff / ".venv/pyvenv.cfg").write_text("venv\n", encoding="utf-8")
    (handoff / "loose.pyc").write_bytes(b"pyc")

    summary = sync_personal_plugins(
        build_sync_plan(repo_root=repo_root, codex_home=codex_home)
    )

    assert summary["copied"] == [
        {
            "plugin": "handoff",
            "source": str(repo_root / "plugins/turbo-mode/handoff"),
            "target": str(codex_home / "plugins/handoff"),
        },
        {
            "plugin": "review-family",
            "source": str(repo_root / "plugins/turbo-mode/review-family"),
            "target": str(codex_home / "plugins/review-family"),
        },
        {
            "plugin": "ticket",
            "source": str(repo_root / "plugins/turbo-mode/ticket"),
            "target": str(codex_home / "plugins/ticket"),
        },
    ]
    assert (codex_home / "plugins/handoff/README.md").read_text(encoding="utf-8") == (
        "handoff source\n"
    )
    assert not (codex_home / "plugins/handoff/.pytest_cache").exists()
    assert not (codex_home / "plugins/handoff/module/__pycache__").exists()
    assert not (codex_home / "plugins/handoff/.DS_Store").exists()
    assert not (codex_home / "plugins/handoff/.ruff_cache").exists()
    assert not (codex_home / "plugins/handoff/.mypy_cache").exists()
    assert not (codex_home / "plugins/handoff/.venv").exists()
    assert not (codex_home / "plugins/handoff/loose.pyc").exists()


def test_reject_unexpected_symlinks_rejects_file_symlink(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_root = seed_plugin_source(repo_root, "handoff", "1.7.0")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (source_root / "outside-link.txt").symlink_to(outside)

    with pytest.raises(SyncPersonalPluginsError, match="symlinks are not allowed"):
        reject_unexpected_symlinks(source_root)


def test_reject_unexpected_symlinks_rejects_directory_symlink(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_root = seed_plugin_source(repo_root, "handoff", "1.7.0")
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    (source_root / "outside-dir-link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(SyncPersonalPluginsError, match="symlinks are not allowed"):
        reject_unexpected_symlinks(source_root)


def test_default_cli_is_non_mutating_and_prints_plan_and_marketplace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "home/.codex"
    agents_home = tmp_path / "home/.agents"
    seed_turbo_mode_sources(repo_root)

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--agents-home",
            str(agents_home),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "planned copy operations:" in output
    assert "personal marketplace JSON:" in output
    assert "./.codex/plugins/handoff" in output
    assert "./.codex/plugins/review-family" in output
    assert not (codex_home / "plugins/handoff").exists()
    assert not (codex_home / "plugins/review-family").exists()
    assert not (agents_home / "plugins/marketplace.json").exists()


def test_cli_sync_copies_into_temp_codex_home_and_replaces_stale_target(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "home/.codex"
    agents_home = tmp_path / "home/.agents"
    seed_turbo_mode_sources(repo_root)
    stale = codex_home / "plugins/handoff/stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale\n", encoding="utf-8")

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--agents-home",
            str(agents_home),
            "--sync",
        ]
    )

    assert exit_code == 0
    assert (codex_home / "plugins/handoff/README.md").exists()
    assert (codex_home / "plugins/review-family/README.md").exists()
    assert (codex_home / "plugins/ticket/README.md").exists()
    assert not stale.exists()
    assert not (agents_home / "plugins/marketplace.json").exists()


def test_copy_preserves_backup_when_replacement_and_restore_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    source_root = seed_plugin_source(repo_root, "handoff", "1.7.0")
    target_root = tmp_path / "home/.codex/plugins/handoff"
    target_root.mkdir(parents=True)
    (target_root / "old.txt").write_text("old target\n", encoding="utf-8")
    monkeypatch.setattr(sync_module.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    staging_root = target_root.parent / ".handoff.sync-fixed.tmp"
    backup_root = target_root.parent / ".handoff.sync-fixed.backup"
    original_rename = Path.rename

    def fail_after_backup(self: Path, target: Path | str) -> Path:
        target_path = Path(target)
        if self == staging_root and target_path == target_root:
            raise OSError("simulated replacement failure")
        if self == backup_root and target_path == target_root:
            raise OSError("simulated rollback restore failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_after_backup)

    with pytest.raises(sync_module.SyncPersonalPluginsError) as exc_info:
        sync_module.copy_plugin_tree(source_root=source_root, target_root=target_root)

    message = str(exc_info.value)
    assert "simulated replacement failure" in message
    assert str(backup_root) in message
    assert backup_root.is_dir()
    assert (backup_root / "old.txt").read_text(encoding="utf-8") == "old target\n"
    assert not staging_root.exists()
    assert not target_root.exists()


def test_cli_writes_personal_marketplace_only_with_explicit_flag(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "home/.codex"
    agents_home = tmp_path / "home/.agents"
    seed_turbo_mode_sources(repo_root)

    main(
        [
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--agents-home",
            str(agents_home),
        ]
    )
    assert not (agents_home / "plugins/marketplace.json").exists()

    exit_code = main(
        [
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--agents-home",
            str(agents_home),
            "--write-personal-marketplace",
        ]
    )

    assert exit_code == 0
    marketplace = json.loads(
        (agents_home / "plugins/marketplace.json").read_text(encoding="utf-8")
    )
    plugins = {plugin["name"]: plugin for plugin in marketplace["plugins"]}
    assert plugins["handoff"]["source"]["path"] == "./.codex/plugins/handoff"
    assert plugins["review-family"]["source"]["path"] == (
        "./.codex/plugins/review-family"
    )
    assert plugins["ticket"]["source"]["path"] == "./.codex/plugins/ticket"
