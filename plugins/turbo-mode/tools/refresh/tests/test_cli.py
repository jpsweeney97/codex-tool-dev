from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

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


def write_valid_marketplace(repo_root: Path) -> None:
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


def write_aligned_config(codex_home: Path, repo_root: Path) -> None:
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."review-family@turbo-mode"]\nenabled = true\n',
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
    source = repo_root / f"plugins/turbo-mode/{plugin}" / rel
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
        version="1.7.0",
        rel="README.md",
        source_text="handoff same\n",
        cache_text="handoff same\n",
    )
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="review-family",
        version="0.1.0",
        rel="README.md",
        source_text="review-family same\n",
        cache_text="review-family same\n",
    )


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


def setup_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    write_valid_marketplace(repo_root)
    write_aligned_config(codex_home, repo_root)
    ensure_complete_plugin_roots(repo_root, codex_home)
    return repo_root, codex_home


def test_load_cli_module_does_not_write_tools_bytecode() -> None:
    tools_root = REPO_ROOT / "plugins/turbo-mode/tools"
    assert not list(tools_root.rglob("__pycache__"))
    assert not list(tools_root.rglob("*.pyc"))

    load_cli_module()

    assert not list(tools_root.rglob("__pycache__"))
    assert not list(tools_root.rglob("*.pyc"))


def test_cli_dry_run_outputs_json_and_writes_evidence(tmp_path: Path) -> None:
    repo_root, codex_home = setup_repo(tmp_path)

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
        "review-family@turbo-mode": "enabled",
    }
    assert (codex_home / "local-only/turbo-mode-refresh/run-1/dry-run.summary.json").is_file()


def test_cli_plan_refresh_emits_dev_refresh_advice_for_fast_safe_drift(
    tmp_path: Path,
) -> None:
    repo_root, codex_home = setup_repo(tmp_path)
    write_plugin_pair(
        repo_root,
        codex_home,
        plugin="handoff",
        version="1.7.0",
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
    assert payload["dev_refresh_command"] == "npm run turbo:sync-personal-plugins"


def test_cli_require_terminal_status_mismatch_returns_error(tmp_path: Path) -> None:
    repo_root, codex_home = setup_repo(tmp_path)

    completed = run_tool(
        [
            "--dry-run",
            "--run-id",
            "run-status",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--require-terminal-status",
            "guarded-refresh-required",
        ]
    )

    assert completed.returncode == 1
    assert "required terminal status mismatch" in completed.stderr


def test_cli_rejects_smoke_without_mutation_mode(tmp_path: Path) -> None:
    repo_root, codex_home = setup_repo(tmp_path)

    completed = run_tool(
        [
            "--dry-run",
            "--smoke",
            "standard",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    )

    assert completed.returncode == 2
    assert "--smoke is only accepted with mutation modes" in completed.stderr


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
        result = {"source": {"path": f"{repo}/plugins/turbo-mode/{plugin}"}}
    elif method == "plugin/list":
        result = {"plugins": ["handoff@turbo-mode", "review-family@turbo-mode"]}
    elif method == "skills/list":
        result = {
            "skills": [
                skill("handoff:distill", "handoff", "1.7.0", "distill"),
                skill("handoff:load", "handoff", "1.7.0", "load"),
                skill("handoff:quicksave", "handoff", "1.7.0", "quicksave"),
                skill("handoff:save", "handoff", "1.7.0", "save"),
                skill("handoff:search", "handoff", "1.7.0", "search"),
                skill("handoff:summary", "handoff", "1.7.0", "summary"),
                skill(
                    "review-family:implementation-review",
                    "review-family",
                    "0.1.0",
                    "implementation-review",
                ),
                skill(
                    "review-family:review-reviewer",
                    "review-family",
                    "0.1.0",
                    "review-reviewer",
                ),
                skill(
                    "review-family:scrutinize",
                    "review-family",
                    "0.1.0",
                    "scrutinize",
                ),
                skill(
                    "review-family:scrutinize-skill",
                    "review-family",
                    "0.1.0",
                    "scrutinize-skill",
                ),
                skill(
                    "review-family:system-design-review",
                    "review-family",
                    "0.1.0",
                    "system-design-review",
                ),
            ]
        }
    elif method == "hooks/list":
        result = {"hooks": []}
    else:
        result = {}
    print(json.dumps({"id": request_id, "result": result}), flush=True)
""",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    return codex


def test_cli_inventory_check_collects_runtime_inventory(tmp_path: Path) -> None:
    repo_root, codex_home = setup_repo(tmp_path)
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
