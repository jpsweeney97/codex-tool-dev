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
    assert "outside Plan 02" in completed.stderr


def test_cli_rejects_exact_future_command_shapes_with_plan_02_message() -> None:
    refresh = run_tool(["--refresh", "--smoke", "light"])
    guarded = run_tool(["--guarded-refresh", "--smoke", "standard"])

    assert refresh.returncode == 2
    assert guarded.returncode == 2
    assert "outside Plan 02" in refresh.stderr
    assert "outside Plan 02" in guarded.stderr
    assert "unrecognized arguments" not in refresh.stderr
    assert "unrecognized arguments" not in guarded.stderr
