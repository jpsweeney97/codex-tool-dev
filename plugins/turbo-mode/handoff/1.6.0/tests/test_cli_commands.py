from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PLUGIN_ROOT = Path(__file__).parent.parent


def _run_shell(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/zsh", "-lc", command],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)


def _residue_snapshot(root: Path) -> set[str]:
    snapshot: set[str] = set()
    for pattern in [".venv", ".pytest_cache", ".DS_Store", "scripts/__pycache__", "hooks/__pycache__"]:
        for match in root.glob(pattern):
            snapshot.add(str(match.relative_to(root)))
    return snapshot


def test_search_command_runs_from_normal_repo_cwd(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    before = _residue_snapshot(PLUGIN_ROOT)
    handoffs = tmp_path / "docs" / "handoffs"
    handoffs.mkdir(parents=True)
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff-1.6.0"
    command = (
        f'PLUGIN_ROOT="{PLUGIN_ROOT}" '
        f'PROJECT_ROOT="{tmp_path}" '
        f'PYTHONDONTWRITEBYTECODE=1 '
        f'UV_PROJECT_ENVIRONMENT="{runtime_env}" '
        f'uv run --project "{PLUGIN_ROOT}/pyproject.toml" '
        f'python "{PLUGIN_ROOT}/scripts/search.py" nonexistent_query_xyz'
    )
    result = _run_shell(command, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["query"] == "nonexistent_query_xyz"
    assert _residue_snapshot(PLUGIN_ROOT) == before


def test_triage_command_runs_from_normal_repo_cwd(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    before = _residue_snapshot(PLUGIN_ROOT)
    tickets = tmp_path / "docs" / "tickets"
    tickets.mkdir(parents=True)
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff-1.6.0"
    command = (
        f'PLUGIN_ROOT="{PLUGIN_ROOT}" '
        f'PROJECT_ROOT="{tmp_path}" '
        f'PYTHONDONTWRITEBYTECODE=1 '
        f'UV_PROJECT_ENVIRONMENT="{runtime_env}" '
        f'uv run --project "{PLUGIN_ROOT}/pyproject.toml" '
        f'python "{PLUGIN_ROOT}/scripts/triage.py" --tickets-dir "{tickets}"'
    )
    result = _run_shell(command, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "open_tickets" in payload
    assert _residue_snapshot(PLUGIN_ROOT) == before


def test_distill_command_runs_from_normal_repo_cwd(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    before = _residue_snapshot(PLUGIN_ROOT)
    handoff_dir = tmp_path / "docs" / "handoffs"
    handoff_dir.mkdir(parents=True)
    handoff = handoff_dir / "2026-05-02_00-00_test.md"
    handoff.write_text(
        "---\n"
        'title: "Test"\n'
        "date: 2026-05-02\n"
        "type: handoff\n"
        "session_id: sess-1\n"
        "---\n\n"
        "## Decisions\n\n"
        "### Choice\n\n"
        "**Choice:** Use a probe.\n\n"
        "**Driver:** Need runtime proof.\n",
        encoding="utf-8",
    )
    learnings = tmp_path / "docs" / "learnings" / "learnings.md"
    learnings.parent.mkdir(parents=True)
    learnings.write_text("# Learnings\n", encoding="utf-8")
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff-1.6.0"
    command = (
        f'PLUGIN_ROOT="{PLUGIN_ROOT}" '
        f'PROJECT_ROOT="{tmp_path}" '
        f'PYTHONDONTWRITEBYTECODE=1 '
        f'UV_PROJECT_ENVIRONMENT="{runtime_env}" '
        f'uv run --project "{PLUGIN_ROOT}/pyproject.toml" '
        f'python "{PLUGIN_ROOT}/scripts/distill.py" "{handoff}" --learnings "{learnings}"'
    )
    result = _run_shell(command, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["handoff_path"] == str(handoff)
    assert _residue_snapshot(PLUGIN_ROOT) == before


def test_defer_pipeline_matches_ticket_guard_contract(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    before = _residue_snapshot(PLUGIN_ROOT)
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff-1.6.0"
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    candidates_json = json.dumps(
        [
            {
                "summary": "Verify defer ticket boundary",
                "problem": (
                    "Prove that defer emits an envelope and Ticket ingest accepts "
                    "the guard-compatible command form."
                ),
                "source_text": "Deferred follow-up for release gate verification.",
                "proposed_approach": "Emit one envelope and ingest it through the guarded Ticket entrypoint.",
                "acceptance_criteria": ["One ticket file exists", "Envelope moved to .processed"],
                "priority": "medium",
                "source_type": "ad-hoc",
                "source_ref": "test",
                "effort": "S",
            }
        ],
        indent=2,
    )
    emit_command = f'''PLUGIN_ROOT="{PLUGIN_ROOT}"
PROJECT_ROOT="{tmp_path}"
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT="{runtime_env}" \\
uv run --project "{PLUGIN_ROOT}/pyproject.toml" python "{PLUGIN_ROOT}/scripts/defer.py" --tickets-dir "{tickets_dir}" <<'JSON'
{candidates_json}
JSON
'''
    emit_result = _run_shell(emit_command, tmp_path)
    assert emit_result.returncode == 0, emit_result.stderr
    emitted = json.loads(emit_result.stdout)
    assert emitted["status"] in {"ok", "partial_success"}, emitted
    envelope_path = emitted["envelopes"][0]

    payload_path = tmp_path / ".codex" / "ticket-tmp" / "payload-ingest.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(
        json.dumps({"envelope_path": envelope_path, "tickets_dir": "docs/tickets"}, indent=2),
        encoding="utf-8",
    )

    resolver = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            f"{PLUGIN_ROOT}/pyproject.toml",
            "python",
            f"{PLUGIN_ROOT}/scripts/plugin_siblings.py",
            "--plugin-root",
            str(PLUGIN_ROOT),
            "--sibling",
            "ticket",
            "--field",
            "plugin_root",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env={
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_PROJECT_ENVIRONMENT": str(runtime_env),
        },
        check=True,
    )
    ticket_root = resolver.stdout.strip()
    literal_command = (
        f"python3 {ticket_root}/scripts/ticket_engine_user.py "
        f"ingest {payload_path}"
    )

    guard_result = subprocess.run(
        ["python3", f"{ticket_root}/hooks/ticket_engine_guard.py"],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": literal_command},
                "cwd": str(tmp_path),
                "session_id": "defer-test-session",
            }
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    guard_payload = json.loads(guard_result.stdout)
    assert guard_payload["hookSpecificOutput"]["permissionDecision"] == "allow", guard_payload

    injected = json.loads(payload_path.read_text(encoding="utf-8"))
    assert injected["hook_injected"] is True
    assert injected["hook_request_origin"] == "user"
    assert injected["session_id"] == "defer-test-session"

    ingest_result = subprocess.run(
        [
            "python3",
            f"{ticket_root}/scripts/ticket_engine_user.py",
            "ingest",
            str(payload_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert ingest_result.returncode == 0, ingest_result.stdout + ingest_result.stderr
    assert list((tmp_path / "docs" / "tickets").glob("*.md"))
    assert list((tmp_path / "docs" / "tickets" / ".envelopes" / ".processed").glob("*.json"))
    assert _residue_snapshot(PLUGIN_ROOT) == before
    assert runtime_env.exists()
