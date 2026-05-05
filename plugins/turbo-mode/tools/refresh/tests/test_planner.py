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
