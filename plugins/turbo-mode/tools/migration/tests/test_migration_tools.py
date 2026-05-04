from __future__ import annotations

import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import copy_ticket_source
import migration_common
import validate_redaction
import validate_run_metadata


def test_safe_archive_extraction_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tgz"
    with tarfile.open(archive, "w:gz") as tar:
        data = b"bad"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    with pytest.raises(migration_common.MigrationError):
        migration_common.extract_safe(archive, tmp_path / "out")


def test_ticket_allowlist_rejects_unknown_file(tmp_path: Path) -> None:
    source = tmp_path / "ticket"
    for rel in copy_ticket_source.ALLOWLIST:
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rel, encoding="utf-8")
    unknown = source / "notes/private.md"
    unknown.parent.mkdir(parents=True)
    unknown.write_text("private", encoding="utf-8")

    with pytest.raises(migration_common.MigrationError):
        copy_ticket_source.classify_source(source)


def test_ticket_copy_is_deterministic(tmp_path: Path) -> None:
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
    assert copied_paths == [
        "a.txt",
        "dir/b.txt",
    ]


def test_redaction_rejects_plugin_dev_and_secret() -> None:
    issues = validate_redaction.validate_text(
        "evidence.json",
        "/Users/jp/.codex/plugins/plugin-dev/turbo-mode\n"
        "token = ghp_abcdefghijklmnopqrstuvwxyz123456\n",
    )

    assert any("forbidden local path" in issue for issue in issues)
    assert any("secret-like token" in issue for issue in issues)


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


def test_fault_harness_cleans_all_scenarios(tmp_path: Path) -> None:
    result = migration_common.run_fake_fault_tests(
        tmp_path,
        [
            migration_common.FaultScenario("one", ("a/b.txt",)),
            migration_common.FaultScenario("two", ("c.txt",)),
        ],
    )

    assert result["count"] == 2
    assert all(item["cleanup_verified"] for item in result["scenarios"])
