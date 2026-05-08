from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
TOOL = REPO_ROOT / "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"


def load_cli_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "refresh_installed_turbo_mode_under_test",
        TOOL,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def write_plan05_seed_sources(repo_root: Path) -> None:
    fixture = (
        REPO_ROOT
        / "plugins/turbo-mode/tools/refresh/tests/fixtures/"
        "handoff_state_helper_doc_migration.json"
    )
    data = json.loads(fixture.read_text(encoding="utf-8"))
    for rel, record in data.items():
        source = repo_root / f"plugins/turbo-mode/{rel}"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(record["source_text"], encoding="utf-8")
    ticket = repo_root / "plugins/turbo-mode/ticket/1.4.0/README.md"
    ticket.parent.mkdir(parents=True, exist_ok=True)
    ticket.write_text("ticket source\n", encoding="utf-8")
    ticket_hook = repo_root / "plugins/turbo-mode/ticket/1.4.0/hooks/hooks.json"
    ticket_hook.parent.mkdir(parents=True, exist_ok=True)
    ticket_hook.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "python3 /Users/jp/.codex/plugins/cache/turbo-mode/"
                                        "ticket/1.4.0/hooks/ticket_engine_guard.py"
                                    ),
                                    "timeout": 10,
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    ticket_guard = repo_root / "plugins/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py"
    ticket_guard.write_text("#!/usr/bin/env python3\nprint('guard')\n", encoding="utf-8")


def commit_all(repo_root: Path) -> None:
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo_root, check=True)


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


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


def setup_plan05_seed_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    init_git_repo(repo_root)
    write_valid_marketplace(repo_root)
    write_plan05_seed_sources(repo_root)
    write_refresh_tooling_sources(repo_root)
    commit_all(repo_root)
    source_commit = git_output(repo_root, "rev-parse", "HEAD")
    source_tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    return repo_root, source_commit, source_tree


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


def assert_text_not_present(paths: list[Path], needle: str) -> None:
    for path in paths:
        assert needle not in path.read_text(encoding="utf-8")


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


def test_cli_record_summary_validators_do_not_write_bytecode(tmp_path: Path) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    refresh_root = REPO_ROOT / "plugins/turbo-mode/tools/refresh"
    assert not list(refresh_root.rglob("__pycache__"))
    assert not list(refresh_root.rglob("*.pyc"))
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
    }

    completed = run_system_python_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "record-no-bytecode",
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
    assert "--refresh is outside non-mutating refresh planning" in completed.stderr


def test_cli_rejects_refresh_future_command_shape_with_plan_neutral_message() -> None:
    refresh = run_tool(["--refresh", "--smoke", "light"])

    assert refresh.returncode == 2
    assert "--refresh is outside non-mutating refresh planning" in refresh.stderr
    assert "unrecognized arguments" not in refresh.stderr


def test_cli_guarded_refresh_requires_source_identity_before_planning(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()

    completed = run_tool(
        [
            "--guarded-refresh",
            "--isolated-rehearsal",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 2
    assert "--source-implementation-commit is required" in completed.stderr
    assert not (codex_home / "local-only").exists()


def test_cli_guarded_refresh_rejects_any_existing_run_state_marker_before_planning(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    marker_dir = codex_home / "local-only/turbo-mode-refresh/run-state"
    marker_dir.mkdir(parents=True)
    marker = marker_dir / "stale.marker.json"
    marker.write_text("{}\n", encoding="utf-8")

    completed = run_tool(
        [
            "--guarded-refresh",
            "--isolated-rehearsal",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--source-implementation-commit",
            "source",
            "--source-implementation-tree",
            "tree",
        ]
    )

    assert completed.returncode == 1
    assert "active run-state marker exists" in completed.stderr


def test_cli_recover_conflicts_with_guarded_refresh() -> None:
    completed = run_tool(["--guarded-refresh", "--recover", "run-1"])

    assert completed.returncode == 2
    assert "not allowed with argument" in completed.stderr


def test_cli_certify_retained_run_conflicts_with_mutation_modes() -> None:
    completed = run_tool(["--certify-retained-run", "run-1", "--guarded-refresh"])

    assert completed.returncode == 2
    assert "not allowed with argument" in completed.stderr


def test_cli_certify_retained_run_refuses_missing_local_only_run_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()

    completed = run_tool(
        [
            "--certify-retained-run",
            "run-1",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 1
    assert "retained run root is missing" in completed.stderr
    assert not (codex_home / "plugins/cache/turbo-mode").exists()


def test_cli_recover_requires_source_identity_before_writes(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()

    completed = run_tool(
        [
            "--recover",
            "run-1",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 2
    assert "--source-implementation-commit is required for --recover" in completed.stderr
    assert not codex_home.exists()


def test_cli_isolated_rehearsal_requires_guarded_refresh(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)

    completed = run_tool(
        [
            "--dry-run",
            "--isolated-rehearsal",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 2
    assert "--isolated-rehearsal requires --guarded-refresh" in completed.stderr


def test_cli_guarded_refresh_rejects_real_home_no_record_summary_before_writes() -> None:
    completed = run_tool(
        [
            "--guarded-refresh",
            "--no-record-summary",
            "--codex-home",
            "/Users/jp/.codex",
        ]
    )

    assert completed.returncode == 2
    assert "--no-record-summary is not allowed for real guarded refresh" in completed.stderr


def test_cli_guarded_refresh_rejects_real_home_without_rehearsal_proof_before_writes() -> None:
    completed = run_tool(
        [
            "--guarded-refresh",
            "--record-summary",
            "--run-id",
            "plan06-live-guarded-refresh-20260507-204500",
            "--codex-home",
            "/Users/jp/.codex",
        ]
    )

    assert completed.returncode == 2
    assert "--rehearsal-proof is required for real guarded refresh" in completed.stderr


def test_cli_guarded_refresh_rejects_real_home_isolated_rehearsal_before_writes() -> None:
    completed = run_tool(
        [
            "--guarded-refresh",
            "--isolated-rehearsal",
            "--codex-home",
            "/Users/jp/.codex",
        ]
    )

    assert completed.returncode == 2
    assert "--isolated-rehearsal requires --codex-home outside /Users/jp/.codex" in (
        completed.stderr
    )


def test_cli_guarded_refresh_rejects_thin_real_home_rehearsal_proof_before_legacy_block(
    tmp_path: Path,
) -> None:
    proof = tmp_path / "proof.json"
    proof.write_text("{}\n", encoding="utf-8")
    proof_sha256 = hashlib.sha256(proof.read_bytes()).hexdigest()
    proof.with_name(f"{proof.name}.sha256").write_text(
        f"{proof_sha256}  {proof}\n",
        encoding="utf-8",
    )

    completed = run_tool(
        [
            "--guarded-refresh",
            "--record-summary",
            "--run-id",
            "plan06-live-guarded-refresh-20260507-204500",
            "--codex-home",
            "/Users/jp/.codex",
            "--rehearsal-proof",
            str(proof),
            "--rehearsal-proof-sha256",
            proof_sha256,
            "--source-implementation-commit",
            "source",
            "--source-implementation-tree",
            "tree",
        ]
    )

    assert completed.returncode == 1
    assert "missing rehearsal proof field" in completed.stderr
    assert "real guarded refresh blocked" not in completed.stderr


def test_cli_guarded_refresh_captures_real_home_rehearsal_proof_before_marker_check(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    proof_path = tmp_path / "rehearsal-proof.json"
    proof_path.write_text("{}\n", encoding="utf-8")
    calls: list[str] = []
    capture_roots: list[Path] = []

    def fake_validate_rehearsal_proof_bundle(**_kwargs: object) -> object:
        calls.append("validate")
        return object()

    def fake_capture_rehearsal_proof_bundle(
        _validated: object,
        *,
        live_run_root: Path,
    ) -> object:
        calls.append("capture")
        capture_roots.append(live_run_root)
        return type(
            "Capture",
            (),
            {"capture_manifest_path": str(tmp_path / "capture-manifest.json")},
        )()

    def fake_ensure_no_active_run_state_markers(_local_only_root: Path) -> None:
        calls.append("marker-check")

    def fake_plan_refresh(**_kwargs: object) -> object:
        calls.append("plan-refresh")
        raise cli.RefreshError("stop after real-home proof capture")

    monkeypatch.setattr(
        cli,
        "validate_rehearsal_proof_bundle",
        fake_validate_rehearsal_proof_bundle,
    )
    monkeypatch.setattr(
        cli,
        "capture_rehearsal_proof_bundle",
        fake_capture_rehearsal_proof_bundle,
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "ensure_no_active_run_state_markers",
        fake_ensure_no_active_run_state_markers,
    )
    monkeypatch.setattr(cli, "plan_refresh", fake_plan_refresh)

    args = parser.parse_args(
        [
            "--guarded-refresh",
            "--record-summary",
            "--run-id",
            "plan06-live-guarded-refresh-20260507-205500",
            "--codex-home",
            "/Users/jp/.codex",
            "--rehearsal-proof",
            str(proof_path),
            "--rehearsal-proof-sha256",
            "proof-sha",
            "--source-implementation-commit",
            "source",
            "--source-implementation-tree",
            "tree",
        ]
    )

    assert cli.guarded_refresh_main(args, parser) == 1
    captured = capsys.readouterr()

    assert calls == ["validate", "capture", "marker-check", "plan-refresh"]
    assert capture_roots == [
        Path(
            "/Users/jp/.codex/local-only/turbo-mode-refresh/"
            "plan06-live-guarded-refresh-20260507-205500"
        )
    ]
    assert "rehearsal proof capture complete" in captured.err
    assert "validation and capture are not complete" not in captured.err


def test_cli_guarded_refresh_real_home_runs_orchestration_after_proof_capture(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    proof_path = tmp_path / "rehearsal-proof.json"
    proof_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "validate_rehearsal_proof_bundle",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        cli,
        "capture_rehearsal_proof_bundle",
        lambda _validated, *, live_run_root: type(
            "Capture",
            (),
            {"capture_manifest_path": str(live_run_root / "capture-manifest.json")},
        )(),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "ensure_no_active_run_state_markers",
        lambda _local_only_root: None,
    )
    calls: list[str] = []

    paths = type(
        "Paths",
        (),
        {
            "repo_root": tmp_path / "repo",
            "codex_home": Path("/Users/jp/.codex"),
            "local_only_root": tmp_path / "local-only",
        },
    )()
    terminal_status = type("TerminalStatus", (), {"value": "guarded-refresh-required"})()
    runtime_config = type("RuntimeConfig", (), {"plugin_hooks_state": "true"})()

    def fake_plan_refresh(**_kwargs: object) -> object:
        calls.append("plan-refresh")
        return type(
            "PlanRefresh",
            (),
            {
                "terminal_status": terminal_status,
                "paths": paths,
                "runtime_config": runtime_config,
            },
        )()

    proof_path = tmp_path / "source-execution-identity.proof.json"
    proof_path.write_text("{}\n", encoding="utf-8")

    def fake_verify_source_execution_identity(**_kwargs: object) -> object:
        calls.append("verify-source-execution")
        return type(
            "Proof",
            (),
            {
                "proof_path": str(proof_path),
                "execution_head": "source",
                "execution_tree": "tree",
                "changed_paths": [],
            },
        )()

    def fake_run_guarded_refresh_orchestration(ctx: object, **kwargs: object) -> object:
        calls.append("orchestrate")
        assert ctx.run_id == "plan06-live-guarded-refresh-20260508-101500"
        assert ctx.codex_home == Path("/Users/jp/.codex")
        assert ctx.local_only_run_root == (
            tmp_path
            / "local-only"
            / "plan06-live-guarded-refresh-20260508-101500"
        )
        assert kwargs["isolated_rehearsal"] is False
        return type(
            "Orchestration",
            (),
            {
                "final_status": "MUTATION_COMPLETE_CERTIFIED",
                "final_status_path": str(tmp_path / "final-status.json"),
                "rehearsal_proof_path": None,
                "rehearsal_proof_sha256": None,
                "rehearsal_proof_sha256_path": None,
            },
        )()

    monkeypatch.setattr(cli, "plan_refresh", fake_plan_refresh)
    monkeypatch.setattr(
        cli,
        "verify_source_execution_identity",
        fake_verify_source_execution_identity,
    )
    monkeypatch.setattr(
        cli,
        "run_guarded_refresh_orchestration",
        fake_run_guarded_refresh_orchestration,
    )

    args = parser.parse_args(
        [
            "--guarded-refresh",
            "--record-summary",
            "--json",
            "--run-id",
            "plan06-live-guarded-refresh-20260508-101500",
            "--codex-home",
            "/Users/jp/.codex",
            "--rehearsal-proof",
            str(proof_path),
            "--rehearsal-proof-sha256",
            "proof-sha",
            "--source-implementation-commit",
            "source",
            "--source-implementation-tree",
            "tree",
        ]
    )

    assert cli.guarded_refresh_main(args, parser) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["final_status"] == "MUTATION_COMPLETE_CERTIFIED"
    assert "rehearsal proof capture complete" in captured.err
    assert "real guarded refresh blocked" not in captured.err
    assert calls == ["plan-refresh", "verify-source-execution", "orchestrate"]


def test_cli_guarded_refresh_rejects_path_shaped_real_home_run_id_before_capture(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    proof_path = tmp_path / "rehearsal-proof.json"
    proof_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "validate_rehearsal_proof_bundle",
        lambda **_kwargs: pytest.fail("rehearsal proof validation should not run"),
    )
    monkeypatch.setattr(
        cli,
        "capture_rehearsal_proof_bundle",
        lambda *_args, **_kwargs: pytest.fail("rehearsal proof capture should not run"),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "ensure_no_active_run_state_markers",
        lambda *_args, **_kwargs: pytest.fail("marker check should not run"),
    )

    args = parser.parse_args(
        [
            "--guarded-refresh",
            "--record-summary",
            "--run-id",
            "../escape",
            "--codex-home",
            "/Users/jp/.codex",
            "--rehearsal-proof",
            str(proof_path),
            "--rehearsal-proof-sha256",
            "proof-sha",
            "--source-implementation-commit",
            "source",
            "--source-implementation-tree",
            "tree",
        ]
    )

    assert cli.guarded_refresh_main(args, parser) == 1
    captured = capsys.readouterr()

    assert "validate run id failed: run id must be one path segment" in captured.err


def test_cli_generate_guarded_refresh_approval_candidate_writes_static_runbook(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    repo_root, _fixture_codex_home = setup_record_summary_repo(tmp_path)
    source_commit = git_output(repo_root, "rev-parse", "HEAD")
    source_tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    codex_home = tmp_path / ".codex"
    proof_path = tmp_path / "rehearsal-proof.json"
    proof_path.write_text('{"proof": true}\n', encoding="utf-8")
    proof_sha256 = hashlib.sha256(proof_path.read_bytes()).hexdigest()

    monkeypatch.setattr(
        cli,
        "validate_rehearsal_proof_bundle",
        lambda **_kwargs: object(),
    )

    args = parser.parse_args(
        [
            "--generate-guarded-refresh-approval",
            "--json",
            "--run-id",
            "plan06-live-guarded-refresh-20260508-120000",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--rehearsal-proof",
            str(proof_path),
            "--rehearsal-proof-sha256",
            proof_sha256,
            "--source-implementation-commit",
            source_commit,
            "--source-implementation-tree",
            source_tree,
        ]
    )

    assert cli.generate_guarded_refresh_approval_main(args, parser) == 0
    approval_dir = (
        codex_home
        / "local-only/turbo-mode-refresh/approvals/"
        "plan06-live-guarded-refresh-20260508-120000"
    )
    approval = json.loads(
        (approval_dir / "guarded-refresh-approval.json").read_text(encoding="utf-8")
    )

    assert approval["approval_status"] == "blocked-before-operator-approval"
    assert approval["source_implementation_commit"] == source_commit
    assert approval["execution_head"] == source_commit
    assert approval["source_execution_identity_match"] is True
    assert approval["approved_changed_paths"] == []
    assert (approval_dir / "approved-source-to-execution-changed-paths.txt").read_text(
        encoding="utf-8"
    ) == ""
    assert approval["python_bin"] == sys.executable

    completed = subprocess.run(
        [
            str(approval_dir / "guarded-refresh-runbook.sh"),
            "--static-preflight-only",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (
        "guarded refresh static preflight passed for "
        "plan06-live-guarded-refresh-20260508-120000"
    ) in completed.stdout
    assert "approval_status=blocked-before-operator-approval" in completed.stdout


def test_cli_generate_guarded_refresh_approval_rejects_disallowed_delta_before_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    repo_root, _fixture_codex_home = setup_record_summary_repo(tmp_path)
    source_commit = git_output(repo_root, "rev-parse", "HEAD")
    source_tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    codex_home = tmp_path / ".codex"
    proof_path = tmp_path / "rehearsal-proof.json"
    proof_path.write_text('{"proof": true}\n', encoding="utf-8")
    proof_sha256 = hashlib.sha256(proof_path.read_bytes()).hexdigest()
    tool_path = repo_root / "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"
    tool_path.write_text("print('changed')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "disallowed delta"], cwd=repo_root, check=True)

    monkeypatch.setattr(
        cli,
        "validate_rehearsal_proof_bundle",
        lambda **_kwargs: object(),
    )

    args = parser.parse_args(
        [
            "--generate-guarded-refresh-approval",
            "--run-id",
            "plan06-live-guarded-refresh-20260508-121500",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--rehearsal-proof",
            str(proof_path),
            "--rehearsal-proof-sha256",
            proof_sha256,
            "--source-implementation-commit",
            source_commit,
            "--source-implementation-tree",
            source_tree,
        ]
    )

    assert cli.generate_guarded_refresh_approval_main(args, parser) == 1
    approval_dir = (
        codex_home
        / "local-only/turbo-mode-refresh/approvals/"
        "plan06-live-guarded-refresh-20260508-121500"
    )
    assert not approval_dir.exists()


def test_cli_seed_isolated_rehearsal_home_rejects_real_home_before_writes(
    tmp_path: Path,
) -> None:
    repo_root, source_commit, source_tree = setup_plan05_seed_repo(tmp_path)

    completed = run_tool(
        [
            "--seed-isolated-rehearsal-home",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            "/Users/jp/.codex",
            "--source-implementation-commit",
            source_commit,
            "--source-implementation-tree",
            source_tree,
        ]
    )

    assert completed.returncode == 2
    assert "--seed-isolated-rehearsal-home requires --codex-home outside /Users/jp/.codex" in (
        completed.stderr
    )


def test_cli_seed_isolated_rehearsal_home_requires_source_identity_before_writes(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()

    completed = run_tool(
        [
            "--seed-isolated-rehearsal-home",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 2
    assert "--source-implementation-commit is required for --seed-isolated-rehearsal-home" in (
        completed.stderr
    )
    assert not codex_home.exists()


def test_cli_seed_isolated_rehearsal_home_creates_plan05_drift_and_manifest(
    tmp_path: Path,
) -> None:
    repo_root, source_commit, source_tree = setup_plan05_seed_repo(tmp_path)
    codex_home = tmp_path / "isolated-home"
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
            "--seed-isolated-rehearsal-home",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--run-id",
            "seed-run",
            "--source-implementation-commit",
            source_commit,
            "--source-implementation-tree",
            source_tree,
            "--json",
        ],
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["terminal_plan_status"] == "guarded-refresh-required"
    seed_manifest = Path(payload["seed_manifest_path"])
    assert seed_manifest.is_file()
    assert codex_home in seed_manifest.parents
    manifest = json.loads(seed_manifest.read_text(encoding="utf-8"))
    assert manifest["canonical_drift_paths"] == [
        "handoff/1.6.0/skills/load/SKILL.md",
        "handoff/1.6.0/skills/quicksave/SKILL.md",
        "handoff/1.6.0/skills/save/SKILL.md",
        "handoff/1.6.0/skills/summary/SKILL.md",
        "handoff/1.6.0/tests/test_session_state.py",
        "handoff/1.6.0/tests/test_skill_docs.py",
    ]
    assert manifest["no_real_home_paths"] is True
    assert not any("/Users/jp/.codex" in path for path in manifest["generated_paths"])
    hook_manifest = json.loads(
        (codex_home / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json").read_text(
            encoding="utf-8"
        )
    )
    hook_command = hook_manifest["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert hook_command == (
        f"python3 {codex_home}/plugins/cache/turbo-mode/ticket/1.4.0/"
        "hooks/ticket_engine_guard.py"
    )

    dry_run = run_tool(
        [
            "--dry-run",
            "--inventory-check",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ],
        env=env,
    )

    assert dry_run.returncode == 0, dry_run.stderr
    dry_run_payload = json.loads(
        Path(payload["post_seed_dry_run_path"]).read_text(encoding="utf-8")
    )
    assert dry_run_payload["terminal_plan_status"] == "guarded-refresh-required"


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
    assert candidate_payload["schema_version"] == "turbo-mode-refresh-commit-safe-plan-06"
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
    assert_text_not_present(
        [candidate, final, published, metadata, redaction, final_scan],
        "outside-plan-04",
    )
    assert_text_not_present(
        [candidate, final, published, metadata, redaction, final_scan],
        "plan-04-cli",
    )
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


def test_cli_record_summary_rejects_wrong_terminal_status_before_writes(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)

    completed = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--require-terminal-status",
            "guarded-refresh-required",
            "--run-id",
            "wrong-terminal-status",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 1
    assert "required terminal status mismatch" in completed.stderr
    assert not (codex_home / "local-only/turbo-mode-refresh/wrong-terminal-status").exists()
    assert not (
        repo_root / "plugins/turbo-mode/evidence/refresh/wrong-terminal-status.summary.json"
    ).exists()


def test_cli_record_summary_writes_when_terminal_status_matches(tmp_path: Path) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)

    completed = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--require-terminal-status",
            "filesystem-no-drift",
            "--run-id",
            "matching-terminal-status",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        codex_home
        / "local-only/turbo-mode-refresh/matching-terminal-status/commit-safe.final.summary.json"
    ).is_file()
    assert (
        repo_root / "plugins/turbo-mode/evidence/refresh/matching-terminal-status.summary.json"
    ).is_file()


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


@pytest.mark.parametrize(
    "dirty_path",
    [
        "plugins/turbo-mode/handoff/1.6.0/README.md",
        "plugins/turbo-mode/ticket/1.4.0/README.md",
    ],
)
def test_cli_record_summary_fails_when_plugin_source_surfaces_are_dirty(
    tmp_path: Path,
    dirty_path: str,
) -> None:
    repo_root, codex_home = setup_record_summary_repo(tmp_path)
    (repo_root / dirty_path).write_text("dirty\n", encoding="utf-8")

    completed = run_tool(
        [
            "--dry-run",
            "--record-summary",
            "--run-id",
            "dirty-plugin-source",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 1
    assert "relevant dirty state" in completed.stderr
    assert not (codex_home / "local-only/turbo-mode-refresh/dirty-plugin-source").exists()


def test_cli_refresh_modes_use_plan_neutral_error_wording(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)

    completed = run_tool(
        [
            "--refresh",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 2
    assert "outside non-mutating refresh planning" in completed.stderr
    assert "outside Plan 04" not in completed.stderr


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
