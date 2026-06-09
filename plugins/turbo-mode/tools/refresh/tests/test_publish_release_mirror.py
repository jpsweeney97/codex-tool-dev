from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import publish_release_mirror as publish_module
import pytest
from publish_release_mirror import (
    PublishReleaseMirrorError,
    build_mirror_plan,
    main,
    publish_mirror,
    reject_unexpected_symlinks,
)


def seed_canonical_plugin(agents_home: Path, plugin: str, version: str) -> Path:
    source_root = agents_home / "plugins" / plugin
    source_root.mkdir(parents=True)
    (source_root / ".claude-plugin").mkdir()
    (source_root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": plugin, "version": version}),
        encoding="utf-8",
    )
    (source_root / "README.md").write_text(f"{plugin} source\n", encoding="utf-8")
    return source_root


def seed_canonical_plugins(agents_home: Path) -> None:
    seed_canonical_plugin(agents_home, "handoff", "3.0.0")
    seed_canonical_plugin(agents_home, "review-family", "0.2.0")
    (agents_home / "plugins/marketplace.json").write_text("{}\n", encoding="utf-8")


def cli_args(repo_root: Path, agents_home: Path, *extra: str) -> list[str]:
    return [
        "--repo-root",
        str(repo_root),
        "--agents-home",
        str(agents_home),
        *extra,
    ]


def test_plan_discovers_canonical_plugins_and_mirror_targets(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)

    plan = build_mirror_plan(repo_root=repo_root, agents_home=agents_home)

    assert [(item.plugin, item.source_root, item.mirror_root) for item in plan.items] == [
        (
            "handoff",
            agents_home / "plugins/handoff",
            repo_root / "plugins/turbo-mode/handoff",
        ),
        (
            "review-family",
            agents_home / "plugins/review-family",
            repo_root / "plugins/turbo-mode/review-family",
        ),
    ]


def test_plan_skips_canonical_dirs_without_claude_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)
    legacy_only = agents_home / "plugins/legacy-only"
    legacy_only.mkdir()
    (legacy_only / ".codex-plugin").mkdir()
    (legacy_only / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "legacy-only", "version": "0.0.1"}),
        encoding="utf-8",
    )

    plan = build_mirror_plan(repo_root=repo_root, agents_home=agents_home)

    assert [item.plugin for item in plan.items] == ["handoff", "review-family"]


def test_default_cli_is_non_mutating_and_reports_missing_mirror(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)

    exit_code = main(cli_args(repo_root, agents_home))

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "planned publish operations" in output
    assert "MISSING-MIRROR: handoff" in output
    assert "MISSING-MIRROR: review-family" in output
    assert not (repo_root / "plugins/turbo-mode/handoff").exists()


def test_publish_copies_excludes_residue_and_replaces_stale_mirror(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)
    handoff = agents_home / "plugins/handoff"
    (handoff / ".DS_Store").write_bytes(b"finder")
    (handoff / "module").mkdir()
    (handoff / "module/__pycache__").mkdir()
    (handoff / "module/__pycache__/example.cpython-313.pyc").write_bytes(b"pyc")
    stale = repo_root / "plugins/turbo-mode/handoff/.codex-plugin/plugin.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    exit_code = main(cli_args(repo_root, agents_home, "--publish"))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "publish completed:" in output
    assert "IN-SYNC: handoff" in output
    assert "IN-SYNC: review-family" in output
    mirror = repo_root / "plugins/turbo-mode/handoff"
    assert (mirror / "README.md").read_text(encoding="utf-8") == "handoff source\n"
    assert (mirror / ".claude-plugin/plugin.json").is_file()
    assert not (mirror / ".codex-plugin").exists()
    assert not (mirror / ".DS_Store").exists()
    assert not (mirror / "module/__pycache__").exists()


def test_check_reports_drift_after_mirror_edit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)
    assert main(cli_args(repo_root, agents_home, "--publish")) == 0
    capsys.readouterr()
    mirror_readme = repo_root / "plugins/turbo-mode/handoff/README.md"
    mirror_readme.write_text("edited in mirror\n", encoding="utf-8")

    exit_code = main(cli_args(repo_root, agents_home))

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "DRIFT: handoff" in output
    assert "content differs: README.md" in output
    assert "IN-SYNC: review-family" in output


def test_check_reports_stale_mirror_plugin_without_deleting_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)
    assert main(cli_args(repo_root, agents_home, "--publish")) == 0
    capsys.readouterr()
    retired = repo_root / "plugins/turbo-mode/retired-plugin"
    (retired / ".codex-plugin").mkdir(parents=True)
    (retired / ".codex-plugin/plugin.json").write_text("{}", encoding="utf-8")
    tools_dir = repo_root / "plugins/turbo-mode/tools"
    tools_dir.mkdir()
    (tools_dir / "helper.py").write_text("# helper\n", encoding="utf-8")

    exit_code = main(cli_args(repo_root, agents_home))

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "STALE-MIRROR-PLUGIN" in output
    assert "retired-plugin" in output
    assert "tools" not in [line.split()[-1] for line in output.splitlines() if "STALE" in line]
    assert retired.is_dir()

    publish_exit = main(cli_args(repo_root, agents_home, "--publish"))
    capsys.readouterr()
    assert publish_exit == 1
    assert retired.is_dir()


def test_reject_unexpected_symlinks_rejects_file_symlink(tmp_path: Path) -> None:
    agents_home = tmp_path / "home/.agents"
    source_root = seed_canonical_plugin(agents_home, "handoff", "3.0.0")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (source_root / "outside-link.txt").symlink_to(outside)

    with pytest.raises(PublishReleaseMirrorError, match="symlinks are not allowed"):
        reject_unexpected_symlinks(source_root)


def test_publish_preserves_backup_when_replacement_and_restore_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    source_root = seed_canonical_plugin(agents_home, "handoff", "3.0.0")
    target_root = repo_root / "plugins/turbo-mode/handoff"
    target_root.mkdir(parents=True)
    (target_root / "old.txt").write_text("old mirror\n", encoding="utf-8")
    monkeypatch.setattr(publish_module.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    staging_root = target_root.parent / ".handoff.publish-fixed.tmp"
    backup_root = target_root.parent / ".handoff.publish-fixed.backup"
    original_rename = Path.rename

    def fail_after_backup(self: Path, target: Path | str) -> Path:
        target_path = Path(target)
        if self == staging_root and target_path == target_root:
            raise OSError("simulated replacement failure")
        if self == backup_root and target_path == target_root:
            raise OSError("simulated rollback restore failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_after_backup)

    with pytest.raises(PublishReleaseMirrorError) as exc_info:
        publish_module.copy_plugin_tree(source_root=source_root, target_root=target_root)

    message = str(exc_info.value)
    assert "simulated replacement failure" in message
    assert str(backup_root) in message
    assert backup_root.is_dir()
    assert (backup_root / "old.txt").read_text(encoding="utf-8") == "old mirror\n"
    assert not staging_root.exists()
    assert not target_root.exists()


def test_publish_mirror_returns_summary(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agents_home = tmp_path / "home/.agents"
    seed_canonical_plugins(agents_home)

    summary = publish_mirror(build_mirror_plan(repo_root=repo_root, agents_home=agents_home))

    assert summary["published"] == [
        {
            "plugin": "handoff",
            "source": str(agents_home / "plugins/handoff"),
            "mirror": str(repo_root / "plugins/turbo-mode/handoff"),
        },
        {
            "plugin": "review-family",
            "source": str(agents_home / "plugins/review-family"),
            "mirror": str(repo_root / "plugins/turbo-mode/review-family"),
        },
    ]
