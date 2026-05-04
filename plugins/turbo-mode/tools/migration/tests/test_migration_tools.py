from __future__ import annotations

import inspect
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cache_refresh_wrapper
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


def test_cache_refresh_dry_run_rejects_stale_path_probe_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    evidence = repo / "evidence"
    evidence.mkdir(parents=True)
    config = tmp_path / "config.toml"
    config.write_text("[marketplaces]\n", encoding="utf-8")
    marketplace = repo / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": "handoff",
                        "source": {"source": "local", "path": "./plugins/turbo-mode/handoff/1.6.0"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    },
                    {
                        "name": "ticket",
                        "source": {"source": "local", "path": "./plugins/turbo-mode/ticket/1.4.0"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    cache_roots = [tmp_path / "cache/handoff/1.6.0", tmp_path / "cache/ticket/1.4.0"]
    for cache_root in cache_roots:
        cache_root.mkdir(parents=True)
    metadata = {
        "run_id": "new-run",
        "mode": "path-probe-execute",
        "tool_path": cache_refresh_wrapper.PATH_PROBE_TOOL_PATH,
        "tool_sha256": "current-tool",
        "repo_head": "HEAD",
        "plan_sha256": "plan",
        "cache_roots": [str(path) for path in cache_roots],
        "source_roots": [str(tmp_path / "source-h"), str(tmp_path / "source-t")],
        "config_path": str(config),
        "marketplace_path": str(marketplace),
    }
    (evidence / "path-probe-execute.summary.json").write_text(
        json.dumps(
            {
                "run_metadata": {**metadata, "run_id": "old-run"},
                "expected_versioned_installed_path": str(tmp_path / "cache/path-probe/9.9.9"),
                "local_segment_present": False,
            }
        ),
        encoding="utf-8",
    )
    for name, mode in (
        ("runtime-preflight.summary.json", "runtime-preflight"),
        ("path-probe-fault-test.summary.json", "path-probe-fault-test"),
        ("path-probe-dry-run.summary.json", "path-probe-dry-run"),
    ):
        tool_path = (
            cache_refresh_wrapper.PATH_PROBE_TOOL_PATH
            if mode.startswith("path-probe")
            else cache_refresh_wrapper.RUNTIME_PREFLIGHT_TOOL_PATH
        )
        (evidence / name).write_text(
            json.dumps(
                {
                    "run_metadata": {
                        **metadata,
                        "run_id": "new-run",
                        "mode": mode,
                        "tool_path": tool_path,
                    }
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(cache_refresh_wrapper, "EVIDENCE_ROOT", evidence)
    monkeypatch.setattr(cache_refresh_wrapper, "CONFIG_PATH", config)
    monkeypatch.setattr(cache_refresh_wrapper, "MARKETPLACE_PATH", marketplace)
    monkeypatch.setattr(cache_refresh_wrapper, "CACHE_ROOTS", cache_roots)
    monkeypatch.setattr(
        cache_refresh_wrapper, "SOURCE_ROOTS", [tmp_path / "source-h", tmp_path / "source-t"]
    )
    monkeypatch.setattr(
        cache_refresh_wrapper, "LOCK_PATH_TEMPLATE", str(tmp_path / "lock-{run_id}")
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "local_only_root",
        lambda run_id, phase: tmp_path / "local" / run_id / phase,
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "base_run_metadata",
        lambda *, run_id, mode, tool_path: {
            **metadata,
            "run_id": run_id,
            "mode": mode,
            "tool_path": tool_path,
            "tool_sha256": "current-tool",
            "repo_head": "HEAD",
            "plan_sha256": "plan",
            "cache_roots": [str(path) for path in cache_roots],
            "source_roots": [str(tmp_path / "source-h"), str(tmp_path / "source-t")],
            "config_path": str(config),
            "marketplace_path": str(marketplace),
        },
    )

    with pytest.raises(migration_common.MigrationError, match="stale run_id"):
        cache_refresh_wrapper.dry_run("new-run")


def test_cache_refresh_execute_acquires_lock_and_disarms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    config = tmp_path / "config.toml"
    config.write_text("[features]\nplugin_hooks = true\n", encoding="utf-8")
    lock_path = tmp_path / "migration.lock"
    source_roots = [tmp_path / "source/handoff", tmp_path / "source/ticket"]
    cache_roots = [tmp_path / "cache/handoff", tmp_path / "cache/ticket"]
    for root in source_roots + cache_roots:
        root.mkdir(parents=True)
        (root / ".codex-plugin").mkdir()
        (root / ".codex-plugin/plugin.json").write_text(root.name, encoding="utf-8")
    monkeypatch.setattr(cache_refresh_wrapper, "CONFIG_PATH", config)
    monkeypatch.setattr(cache_refresh_wrapper, "CACHE_ROOTS", cache_roots)
    monkeypatch.setattr(cache_refresh_wrapper, "SOURCE_ROOTS", source_roots)
    monkeypatch.setattr(cache_refresh_wrapper, "MARKETPLACE_PATH", tmp_path / "marketplace.json")
    monkeypatch.setattr(cache_refresh_wrapper, "LOCK_PATH_TEMPLATE", str(lock_path))
    monkeypatch.setattr(cache_refresh_wrapper, "EVIDENCE_ROOT", tmp_path / "evidence")
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "local_only_root",
        lambda run_id, phase: tmp_path / "local" / run_id / phase,
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "base_run_metadata",
        lambda *, run_id, mode, tool_path: {
            "run_id": run_id,
            "mode": mode,
            "tool_path": tool_path,
            "tool_sha256": "tool",
            "repo_head": "HEAD",
            "plan_sha256": "plan",
            "cache_roots": [str(path) for path in cache_roots],
            "source_roots": [str(path) for path in source_roots],
            "config_path": str(config),
            "marketplace_path": str(tmp_path / "marketplace.json"),
        },
    )
    monkeypatch.setattr(
        cache_refresh_wrapper, "verify_dry_run_prerequisites", lambda run_id, metadata: None
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "capture_process_check",
        lambda *args, **kwargs: events.append("process-check"),
    )
    monkeypatch.setattr(
        cache_refresh_wrapper, "set_plugin_hooks", lambda enabled: events.append(f"hooks-{enabled}")
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "register_repo_marketplace",
        lambda evidence_root: events.append("marketplace"),
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "install_and_inventory",
        lambda run_id, evidence_root, metadata: events.append("inventory"),
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "run_source_cache_gate",
        lambda *args, **kwargs: events.append("equality"),
    )
    monkeypatch.setattr(
        cache_refresh_wrapper, "run_installed_smoke", lambda *args, **kwargs: events.append("smoke")
    )
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "write_manifest_snapshot",
        lambda *args, **kwargs: events.append("snapshot"),
    )

    cache_refresh_wrapper.execute("run")

    assert not lock_path.exists()
    assert events == [
        "process-check",
        "hooks-False",
        "process-check",
        "snapshot",
        "snapshot",
        "marketplace",
        "inventory",
        "equality",
        "smoke",
        "equality",
    ]
    summary = json.loads(
        (tmp_path / "evidence/cache-refresh-execute.summary.json").read_text(encoding="utf-8")
    )
    assert summary["result"] == "CACHE_REFRESH_DISARMED"


def test_app_server_roundtrip_does_not_use_blocking_stdout_readline() -> None:
    source = inspect.getsource(cache_refresh_wrapper.app_server_roundtrip)

    assert ".stdout.readline()" not in source
    assert "Queue" in source or "Thread" in source


def test_inventory_contract_rejects_missing_ticket_hook() -> None:
    transcript = [
        {
            "direction": "recv",
            "body": {
                "id": 3,
                "result": {
                    "source": {
                        "path": (
                            "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/"
                            "handoff/1.6.0"
                        )
                    }
                },
            },
        },
        {
            "direction": "recv",
            "body": {
                "id": 4,
                "result": {
                    "source": {
                        "path": (
                            "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/"
                            "ticket/1.4.0"
                        )
                    }
                },
            },
        },
        {
            "direction": "recv",
            "body": {"id": 5, "result": {"plugins": ["handoff@turbo-mode", "ticket@turbo-mode"]}},
        },
        {
            "direction": "recv",
            "body": {
                "id": 6,
                "result": {
                    "skills": [
                        {
                            "name": skill,
                            "sourcePath": (
                                "/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/"
                                f"skills/{skill.removeprefix('handoff:')}/SKILL.md"
                            ),
                        }
                        for skill in cache_refresh_wrapper.REQUIRED_HANDOFF_SKILLS
                    ]
                },
            },
        },
        {"direction": "recv", "body": {"id": 7, "result": {"hooks": []}}},
    ]

    with pytest.raises(migration_common.MigrationError, match="Ticket Bash preToolUse hook"):
        cache_refresh_wrapper.validate_inventory_contract(transcript)


def test_rollback_verifies_restored_config_and_cache_manifests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "/before"\n',
        encoding="utf-8",
    )
    config_backup = tmp_path / "config.before.toml"
    config_backup.write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
    cache_root = tmp_path / "cache/handoff"
    cache_root.mkdir(parents=True)
    (cache_root / "file.txt").write_text("before", encoding="utf-8")
    backup_root = tmp_path / "backup"
    backup_root.mkdir()
    failed_root = tmp_path / "failed"
    monkeypatch.setattr(cache_refresh_wrapper, "CONFIG_PATH", config)
    monkeypatch.setattr(cache_refresh_wrapper, "CACHE_ROOTS", [cache_root])
    monkeypatch.setattr(cache_refresh_wrapper, "EVIDENCE_ROOT", tmp_path / "evidence")
    monkeypatch.setattr(
        cache_refresh_wrapper,
        "restore_cache_roots",
        lambda backup_root, failed_root: (cache_root / "file.txt").write_text(
            "corrupt", encoding="utf-8"
        ),
    )
    metadata = {"run_id": "run", "mode": "cache-refresh-execute"}
    pre_manifests = {
        str(cache_root): {"file.txt": migration_common.sha256_file(cache_root / "file.txt")}
    }

    with pytest.raises(migration_common.MigrationError, match="restored cache manifest"):
        cache_refresh_wrapper.rollback(
            metadata=metadata,
            evidence_root=tmp_path / "local",
            config_backup=config_backup,
            backup_root=backup_root,
            failed_root=failed_root,
            reason="test",
            pre_cache_manifests=pre_manifests,
            prior_marketplace_stanza={"source_type": "local", "source": "/before"},
        )
