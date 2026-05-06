from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
TOOL = REPO_ROOT / "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"


def write_marketplace(path: Path) -> None:
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


def write_valid_marketplace(repo_root: Path) -> None:
    write_marketplace(repo_root / ".agents/plugins/marketplace.json")


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


def init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)


def write_refresh_tooling_sources(repo_root: Path) -> None:
    for rel in (
        "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
        "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
        "plugins/turbo-mode/tools/refresh_validate_redaction.py",
        "plugins/turbo-mode/tools/refresh/__init__.py",
    ):
        target = repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        source = REPO_ROOT / rel
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def commit_all(repo_root: Path) -> None:
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo_root, check=True)


def setup_record_summary_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    init_git_repo(repo_root)
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    write_refresh_tooling_sources(repo_root)
    commit_all(repo_root)
    return repo_root, codex_home


def run_tool(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def run_system_python_tool(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(TOOL), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def write_fake_codex(bin_dir: Path) -> Path:
    codex = bin_dir / "codex"
    codex.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

repo = os.environ["FAKE_REPO_ROOT"]
codex_home = os.environ["FAKE_CODEX_HOME"]

def skill(name, plugin, version, rel):
    return {
        "name": name,
        "sourcePath": (
            f"{codex_home}/plugins/cache/turbo-mode/{plugin}/{version}"
            f"/skills/{rel}/SKILL.md"
        ),
    }

if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.test")
    raise SystemExit(0)

if sys.argv[1:] != ["app-server", "--listen", "stdio://"]:
    print("unexpected argv", sys.argv[1:], file=sys.stderr)
    raise SystemExit(2)

for line in sys.stdin:
    request = json.loads(line)
    request_id = request.get("id")
    if request_id is None:
        continue
    method = request.get("method")
    if method == "initialize":
        result = {
            "serverInfo": {"name": "codex-app-server", "version": "0.test"},
            "capabilities": {"experimentalApi": True},
        }
    elif method == "plugin/read":
        plugin = request["params"]["pluginName"]
        version = "1.6.0" if plugin == "handoff" else "1.4.0"
        result = {"source": {"path": f"{repo}/plugins/turbo-mode/{plugin}/{version}"}}
    elif method == "plugin/list":
        result = {"plugins": ["handoff@turbo-mode", "ticket@turbo-mode"]}
    elif method == "skills/list":
        result = {
            "skills": [
                skill("handoff:defer", "handoff", "1.6.0", "defer"),
                skill("handoff:distill", "handoff", "1.6.0", "distill"),
                skill("handoff:load", "handoff", "1.6.0", "load"),
                skill("handoff:quicksave", "handoff", "1.6.0", "quicksave"),
                skill("handoff:save", "handoff", "1.6.0", "save"),
                skill("handoff:search", "handoff", "1.6.0", "search"),
                skill("handoff:summary", "handoff", "1.6.0", "summary"),
                skill("handoff:triage", "handoff", "1.6.0", "triage"),
                skill("ticket:ticket", "ticket", "1.4.0", "ticket"),
                skill("ticket:ticket-triage", "ticket", "1.4.0", "ticket-triage"),
            ]
        }
    elif method == "hooks/list":
        ticket_cache = f"{codex_home}/plugins/cache/turbo-mode/ticket/1.4.0"
        result = {
            "hooks": [
                {
                    "pluginId": "ticket@turbo-mode",
                    "eventName": "preToolUse",
                    "matcher": "Bash",
                    "command": f"python3 {ticket_cache}/hooks/ticket_engine_guard.py",
                    "sourcePath": f"{ticket_cache}/hooks/hooks.json",
                }
            ]
        }
    else:
        result = {}
    print(json.dumps({"id": request_id, "result": result}), flush=True)
""",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    return codex


def tree_snapshot(root: Path) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for path in sorted([root, *root.rglob("*")]):
        rel = "." if path == root else path.relative_to(root).as_posix()
        path_stat = path.lstat()
        mode = oct(stat.S_IMODE(path_stat.st_mode))
        if stat.S_ISDIR(path_stat.st_mode):
            entries[rel] = {"kind": "dir", "mode": mode}
        elif stat.S_ISLNK(path_stat.st_mode):
            entries[rel] = {
                "kind": "symlink",
                "mode": mode,
                "target": os.readlink(path),
            }
        elif stat.S_ISREG(path_stat.st_mode):
            entries[rel] = {
                "kind": "file",
                "mode": mode,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        else:
            entries[rel] = {"kind": "other", "mode": mode}
    return entries


def path_snapshot(path: Path) -> dict[str, str]:
    path_stat = path.lstat()
    mode = oct(stat.S_IMODE(path_stat.st_mode))
    if stat.S_ISLNK(path_stat.st_mode):
        return {"kind": "symlink", "mode": mode, "target": os.readlink(path)}
    if stat.S_ISREG(path_stat.st_mode):
        return {
            "kind": "file",
            "mode": mode,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return {"kind": "other", "mode": mode}


def test_cli_dry_run_outputs_json_and_writes_evidence(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)

    completed = run_tool(
        [
            "--dry-run",
            "--json",
            "--run-id",
            "run-1",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["terminal_plan_status"] == "filesystem-no-drift"
    assert payload["runtime_config"]["plugin_enablement_state"] == {
        "handoff@turbo-mode": "enabled",
        "ticket@turbo-mode": "enabled",
    }
    assert (codex_home / "local-only/turbo-mode-refresh/run-1/dry-run.summary.json").is_file()


def test_cli_inventory_check_collects_runtime_inventory(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_codex(bin_dir)
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_REPO_ROOT": str(repo_root),
        "FAKE_CODEX_HOME": str(codex_home),
    }

    completed = run_tool(
        [
            "--dry-run",
            "--inventory-check",
            "--json",
            "--run-id",
            "run-inventory",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ],
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["terminal_plan_status"] == "no-drift"
    assert payload["app_server_inventory"]["state"] == "aligned"
    transcript = codex_home / (
        "local-only/turbo-mode-refresh/run-inventory/"
        "app-server-readonly-inventory.transcript.json"
    )
    assert transcript.is_file()


def test_cli_plan_refresh_emits_future_command_advice_for_fast_safe_drift(
    tmp_path: Path,
) -> None:
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

    completed = run_tool(
        [
            "--plan-refresh",
            "--json",
            "--run-id",
            "run-2",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["terminal_plan_status"] == "blocked-preflight"
    assert payload["axes"]["filesystem_state"] == "drift"
    assert payload["axes"]["runtime_config_state"] == "unchecked"
    assert payload["mutation_command_available"] is False
    assert payload["requires_plan"] == "future-mutation-plan"
    assert payload["future_external_command"].endswith("--refresh --smoke light")


def test_cli_bare_invocation_does_not_write_bytecode(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    refresh_root = REPO_ROOT / "plugins/turbo-mode/tools/refresh"
    assert not list(refresh_root.rglob("__pycache__"))
    assert not list(refresh_root.rglob("*.pyc"))
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
    }

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "bare-no-bytecode",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ],
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert not list(refresh_root.rglob("__pycache__"))
    assert not list(refresh_root.rglob("*.pyc"))


def test_cli_system_python_no_user_site_does_not_require_tomli(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}

    completed = run_system_python_tool(
        [
            "--dry-run",
            "--run-id",
            "no-user-site",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ],
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert "filesystem-no-drift" in completed.stdout
    assert "Traceback" not in completed.stderr


def test_cli_evidence_path_errors_report_without_traceback(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    evidence_root = codex_home / "local-only/turbo-mode-refresh"
    evidence_root.mkdir(parents=True)
    evidence_root.chmod(0o755)

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "bad-evidence-root",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 1
    assert "validate evidence root failed" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_mutation_modes_in_plan_02() -> None:
    completed = run_tool(["--refresh"])

    assert completed.returncode == 2
    assert "outside Plan 04" in completed.stderr


def test_cli_rejects_exact_future_command_shapes_with_plan_02_message() -> None:
    refresh = run_tool(["--refresh", "--smoke", "light"])
    guarded = run_tool(["--guarded-refresh", "--smoke", "standard"])

    assert refresh.returncode == 2
    assert guarded.returncode == 2
    assert "outside Plan 04" in refresh.stderr
    assert "outside Plan 04" in guarded.stderr
    assert "unrecognized arguments" not in refresh.stderr
    assert "unrecognized arguments" not in guarded.stderr


def test_cli_dry_run_does_not_modify_cache_tree_or_config(tmp_path: Path) -> None:
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
        rel="README.md",
        source_text="source drift\n",
        cache_text="cache original\n",
    )
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="ticket",
        version="1.4.0",
        rel="scripts/ticket_engine_core.py",
        source_text="print('source')\n",
        cache_text="print('cache')\n",
    )
    cache_root = codex_home / "plugins/cache/turbo-mode"
    config = codex_home / "config.toml"
    before_cache = tree_snapshot(cache_root)
    before_config = path_snapshot(config)

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "run-3",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    assert tree_snapshot(cache_root) == before_cache
    assert path_snapshot(config) == before_config


def test_cli_record_summary_publishes_after_candidate_and_final_validation(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    published = repo_root / "plugins/turbo-mode/evidence/refresh/run-1.summary.json"

    completed = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--json",
            "--run-id",
            "run-1",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--summary-output",
            str(published),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    run_root = codex_home / "local-only/turbo-mode-refresh/run-1"
    candidate = run_root / "commit-safe.candidate.summary.json"
    final = run_root / "commit-safe.final.summary.json"
    metadata = run_root / "metadata-validation.summary.json"
    redaction = run_root / "redaction.summary.json"
    final_scan = run_root / "redaction-final-scan.summary.json"
    assert candidate.is_file()
    assert final.is_file()
    assert metadata.is_file()
    assert redaction.is_file()
    assert final_scan.is_file()
    assert published.is_file()
    candidate_payload = json.loads(candidate.read_text(encoding="utf-8"))
    final_payload = json.loads(final.read_text(encoding="utf-8"))
    published_payload = json.loads(published.read_text(encoding="utf-8"))
    assert candidate_payload["schema_version"] == "turbo-mode-refresh-commit-safe-plan-04"
    assert candidate_payload["mode"] == "dry-run"
    assert candidate_payload["metadata_validation_summary_sha256"] is None
    assert candidate_payload["redaction_validation_summary_sha256"] is None
    assert final_payload["metadata_validation_summary_sha256"] == hashlib.sha256(
        metadata.read_bytes()
    ).hexdigest()
    assert final_payload["redaction_validation_summary_sha256"] == hashlib.sha256(
        redaction.read_bytes()
    ).hexdigest()
    assert published_payload == final_payload
    assert "app_server_transcript" not in candidate_payload
    assert "app_server_inventory_failure_reason" not in candidate_payload
    assert candidate_payload["omission_reasons"]["raw_app_server_transcript"] == "local-only"
    assert payload["published_summary_path"] == str(published)


def test_cli_record_summary_plan_refresh_writes_plan_refresh_candidate(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)

    completed = run_tool(
        [
            "--plan-refresh",
            "--record-summary",
            "--run-id",
            "run-plan",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    candidate = (
        codex_home
        / "local-only/turbo-mode-refresh/run-plan/commit-safe.candidate.summary.json"
    )
    summary = json.loads(candidate.read_text(encoding="utf-8"))
    assert summary["mode"] == "plan-refresh"
    assert (
        repo_root / "plugins/turbo-mode/evidence/refresh/run-plan.summary.json"
    ).is_file()


def test_cli_record_summary_inventory_check_projects_methods_without_transcript(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_codex(bin_dir)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_REPO_ROOT": str(repo_root),
        "FAKE_CODEX_HOME": str(codex_home),
    }

    completed = run_tool(
        [
            "--dry-run",
            "--inventory-check",
            "--record-summary",
            "--run-id",
            "run-inventory",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ],
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    candidate = (
        codex_home
        / "local-only/turbo-mode-refresh/run-inventory/commit-safe.candidate.summary.json"
    )
    summary = json.loads(candidate.read_text(encoding="utf-8"))
    dumped = json.dumps(summary)
    assert summary["app_server_inventory_status"] == "collected"
    assert summary["app_server_request_methods"] == [
        "initialize",
        "initialized",
        "plugin/read",
        "plugin/read",
        "plugin/list",
        "skills/list",
        "hooks/list",
    ]
    assert "app_server_transcript" not in summary
    assert "secret" not in dumped


def test_cli_record_summary_fails_before_candidate_when_relevant_dirty(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    (repo_root / "plugins/turbo-mode/tools/refresh/__init__.py").write_text(
        "# dirty\n",
        encoding="utf-8",
    )

    completed = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "dirty",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 1
    assert "relevant dirty state" in completed.stderr
    assert not (codex_home / "local-only/turbo-mode-refresh/dirty").exists()
    assert not (repo_root / "plugins/turbo-mode/evidence/refresh/dirty.summary.json").exists()


def test_cli_record_summary_allows_unrelated_dirty_path(tmp_path: Path) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    docs = repo_root / "docs/note.md"
    docs.parent.mkdir()
    docs.write_text("dirty\n", encoding="utf-8")

    completed = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "unrelated",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr


def test_cli_record_summary_rejects_existing_run_and_bad_summary_output(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    evidence_root = codex_home / "local-only/turbo-mode-refresh"
    evidence_root.mkdir(parents=True, mode=0o700)
    os.chmod(evidence_root, 0o700)
    existing = evidence_root / "existing"
    existing.mkdir(mode=0o700)

    reused = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "existing",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )
    assert reused.returncode == 1
    assert "run directory already exists" in reused.stderr

    escaped = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "escape",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--summary-output",
            str(tmp_path / "outside.summary.json"),
        ]
    )
    assert escaped.returncode == 1
    assert "path must stay under evidence root" in escaped.stderr


def test_cli_record_summary_rejects_existing_summary_output_and_symlink_parent(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    evidence_root = repo_root / "plugins/turbo-mode/evidence/refresh"
    evidence_root.mkdir(parents=True)
    existing = evidence_root / "exists.summary.json"
    existing.write_text("{}\n", encoding="utf-8")

    rejected_existing = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "exists",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--summary-output",
            str(existing),
        ]
    )
    assert rejected_existing.returncode == 1
    assert "output path already exists" in rejected_existing.stderr

    trash = tmp_path / "symlink-target"
    trash.mkdir()
    symlink_parent = evidence_root / "link"
    symlink_parent.symlink_to(trash, target_is_directory=True)
    rejected_symlink = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "symlink",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--summary-output",
            str(symlink_parent / "run.summary.json"),
        ]
    )
    assert rejected_symlink.returncode == 1
    assert "path must stay under evidence root" in rejected_symlink.stderr or (
        "symlink parent" in rejected_symlink.stderr
    )
