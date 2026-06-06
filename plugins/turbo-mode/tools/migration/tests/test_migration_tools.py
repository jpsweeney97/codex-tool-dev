from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import migration_common
import validate_redaction
import validate_run_metadata
import validate_staged_content


def test_active_migration_roots_match_current_plugin_contract() -> None:
    source_roots = "\n".join(str(path) for path in migration_common.SOURCE_ROOTS)
    cache_roots = "\n".join(str(path) for path in migration_common.CACHE_ROOTS)

    assert "plugins/turbo-mode/handoff" in source_roots
    assert "plugins/turbo-mode/review-family" in source_roots
    assert "handoff/1.7.0" in cache_roots
    assert "review-family/0.1.0" in cache_roots


def test_safe_archive_extraction_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tgz"
    with tarfile.open(archive, "w:gz") as tar:
        data = b"bad"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    with pytest.raises(migration_common.MigrationError):
        migration_common.extract_safe(archive, tmp_path / "out")


def test_exact_copy_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    manifest: dict[str, str] = {}
    for rel in ("a.txt", "dir/b.txt"):
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rel, encoding="utf-8")
        manifest[rel] = migration_common.sha256_file(path)

    copied = migration_common.copy_exact_files(source, output, manifest)

    assert copied == manifest
    copied_paths = sorted(
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    )
    assert copied_paths == ["a.txt", "dir/b.txt"]


def test_redaction_rejects_plugin_dev_and_secret() -> None:
    issues = validate_redaction.validate_text(
        "evidence.json",
        "/Users/jp/.codex/plugins/plugin-dev/turbo-mode\n"
        "token = ghp_abcdefghijklmnopqrstuvwxyz123456\n",
    )

    assert any("forbidden local path" in issue for issue in issues)
    assert any("secret-like token" in issue for issue in issues)


def test_redaction_allows_local_path_fixtures_in_source_tests() -> None:
    issues = validate_redaction.validate_text(
        "plugins/turbo-mode/review-family/tests/test_docs.py",
        '"/Users/jp/.agents/plugins/marketplace.json" '
        '"/Users/jp/.codex/plugins/cache/" '
        '"/Users/jp/Projects/myproject"\n',
    )

    assert issues == []


def test_validate_metadata_detects_stale_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = tmp_path / "plan.md"
    plan.write_text("plan", encoding="utf-8")
    evidence = Path("evidence")
    (repo / evidence).mkdir()
    summary = repo / evidence / "summary.json"
    metadata = {
        "run_id": "old",
        "generated_at_utc": "2026-05-04T00:00:00+00:00",
        "plan_path": str(plan),
        "plan_sha256": migration_common.sha256_file(plan),
        "repo_root": str(repo),
        "repo_head": "HEAD",
        "migration_base_head": migration_common.MIGRATION_BASE_HEAD,
        "migration_base_ref": migration_common.MIGRATION_BASE_REF,
        "migration_base_kind": migration_common.MIGRATION_BASE_KIND,
        "tool_path": "manual-shell:test",
        "tool_sha256": "abc",
        "mode": "test",
        "source_roots": [str(path) for path in migration_common.SOURCE_ROOTS],
        "cache_roots": [str(path) for path in migration_common.CACHE_ROOTS],
        "config_path": str(migration_common.CONFIG_PATH),
        "marketplace_path": str(migration_common.MARKETPLACE_PATH),
    }
    summary.write_text(json.dumps({"run_metadata": metadata}), encoding="utf-8")
    monkeypatch.setattr(validate_run_metadata, "repo_head", lambda repo_root: "HEAD")

    args = type(
        "Args",
        (),
        {
            "run_id": "new",
            "plan": plan,
            "repo_root": repo,
            "evidence_root": evidence,
            "source": "worktree",
            "scan_all": True,
            "require": [],
        },
    )()

    with pytest.raises(migration_common.MigrationError):
        validate_run_metadata.run_validation(args)


def test_staged_content_cli_parses_local_only_output_as_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed_args: dict[str, object] = {}

    def fake_run_validation(args: object) -> None:
        parsed_args["local_only_output"] = getattr(args, "local_only_output")

    monkeypatch.setattr(validate_staged_content, "run_validation", fake_run_validation)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_staged_content.py",
            "--run-id",
            "run",
            "--repo-root",
            str(tmp_path),
            "--expected-staged-root",
            "plugins/turbo-mode/handoff",
            "--source-manifest",
            "manifest.txt",
            "--marketplace",
            ".agents/plugins/marketplace.json",
            "--tool-root",
            "plugins/turbo-mode/tools/migration",
            "--local-only-output",
            str(tmp_path / "local/summary.json"),
        ],
    )

    validate_staged_content.main()

    assert parsed_args["local_only_output"] == tmp_path / "local/summary.json"


def test_validate_staged_content_rejects_empty_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validate_staged_content, "staged_names", lambda repo_root: [])
    args = type(
        "Args",
        (),
        {
            "repo_root": tmp_path,
            "expected_staged_root": "plugins/turbo-mode/handoff",
            "expected_staged_file": [],
        },
    )()

    with pytest.raises(migration_common.MigrationError, match="staged index is empty"):
        validate_staged_content.run_validation(args)


def test_validate_marketplace_accepts_current_two_plugin_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    marketplace = repo / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(validate_staged_content.EXPECTED_MARKETPLACE, indent=2),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", str(marketplace.relative_to(repo))], cwd=repo, check=True)

    validate_staged_content.validate_marketplace(
        str(repo),
        ".agents/plugins/marketplace.json",
    )


def test_fake_fault_tests_cleanup_scenarios(tmp_path: Path) -> None:
    result = migration_common.run_fake_fault_tests(
        tmp_path / "faults",
        [
            migration_common.FaultScenario("one", ("a/b.txt",)),
            migration_common.FaultScenario("two", ("c.txt",)),
        ],
    )

    assert result == {
        "count": 2,
        "scenarios": [
            {"scenario": "one", "cleanup_verified": True},
            {"scenario": "two", "cleanup_verified": True},
        ],
    }
