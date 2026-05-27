"""End-to-end tests for runtime-first apply-turn orchestration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ticket_autonomy import build_repo_context
from scripts.ticket_autonomy_config import AutomationMode, write_local_config

from tests.support.builders import make_ticket

SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_autonomy.py"


def _init_ticket_project(project_root: Path) -> Path:
    subprocess.run(["git", "init"], cwd=project_root, capture_output=True, text=True, check=True)
    (project_root / ".gitignore").write_text(
        ".codex/ticket-workspace/\n.codex/ticket.local.md\n",
        encoding="utf-8",
    )
    tickets_dir = project_root / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    return tickets_dir


def _run_autonomy(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _write_context(project_root: Path, payload: dict[str, object]) -> Path:
    path = project_root / "turn-context.json"
    base: dict[str, object] = {
        "schema": "codex.ticket.turn_context.v1",
        "operation": "apply_ticket_mutations",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "user_request": "Update the ticket after verification.",
        "assistant_work_summary": "Implemented and verified the requested change.",
        "git": dict(build_repo_context(project_root).as_event_payload()),
    }
    base.update(payload)
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


def _apply_turn(project_root: Path, context: Path, *, turn_id: str = "turn-1"):
    return _run_autonomy(
        project_root,
        "apply-turn",
        "--project-root",
        str(project_root),
        "--turn-id",
        turn_id,
        "--context-file",
        str(context),
    )


def _events(project_root: Path) -> list[dict[str, object]]:
    path = project_root / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_agent_primary_apply_turn_applies_update_through_gateway(tmp_path: Path) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "reason": "Verification passed.",
                    "evidence": [{"kind": "current_thread_reason", "ref": "tests passed"}],
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "applied"
    assert payload["changed"] is True
    assert "Applied" in payload["ticket_updates"]
    assert "priority: low" in ticket.read_text(encoding="utf-8")
    events = _events(tmp_path)
    assert [event["status"] for event in events[:4]] == [
        "pending",
        "approval_consumed",
        "ticket_written",
        "applied",
    ]
    assert all(event["thread_id"] == "thread-1" for event in events)
    expected_repo_context = build_repo_context(tmp_path).as_event_payload()
    assert all(event["repo_context"] == expected_repo_context for event in events)


def test_preview_and_discussion_modes_do_not_write_tickets(tmp_path: Path) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "evidence": [{"kind": "current_thread_reason", "ref": "tests passed"}],
                }
            ]
        },
    )
    before = ticket.read_text(encoding="utf-8")

    write_local_config(tmp_path, AutomationMode.PREVIEW)
    preview = _apply_turn(tmp_path, context)
    assert preview.returncode == 0
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["state"] == "preview"
    assert "Skipped" in preview_payload["ticket_updates"]
    assert ticket.read_text(encoding="utf-8") == before
    assert "preview_only" not in {event["status"] for event in _events(tmp_path)}

    other_context = _write_context(
        tmp_path,
        {
            "thread_id": "thread-2",
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "evidence": [{"kind": "current_thread_reason", "ref": "tests passed"}],
                }
            ],
        },
    )
    write_local_config(tmp_path, AutomationMode.DISCUSSION_ONLY)
    discussion = _apply_turn(tmp_path, other_context)
    assert discussion.returncode == 0
    discussion_payload = json.loads(discussion.stdout)
    assert discussion_payload["state"] == "discussion_required"
    assert discussion_payload["discussion_question"]
    assert ticket.read_text(encoding="utf-8") == before


def test_conflicting_candidate_is_skipped_without_blocking_plausible_candidate(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    first = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    second = make_ticket(tickets_dir, "two.md", id="T-20260527-02")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "conflict_reason": "Current thread contradicts this ticket.",
                    "evidence": [{"kind": "conflicting", "ref": "summary"}],
                },
                {
                    "ticket_id": "T-20260527-02",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "evidence": [{"kind": "current_thread_reason", "ref": "tests passed"}],
                },
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "applied"
    assert "Skipped" in payload["ticket_updates"]
    assert "priority: high" in first.read_text(encoding="utf-8")
    assert "priority: low" in second.read_text(encoding="utf-8")


def test_repo_context_mismatch_fails_closed_before_ledger_or_write(tmp_path: Path) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    bad_git = dict(build_repo_context(tmp_path).as_event_payload())
    bad_git["repo_fingerprint"] = "wrong"
    context = _write_context(
        tmp_path,
        {
            "git": bad_git,
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "evidence": [{"kind": "current_thread_reason", "ref": "tests passed"}],
                }
            ],
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["state"] == "paused"
    assert payload["pause_reason"] == "repo_context_mismatch"
    assert _events(tmp_path) == []
    assert "priority: high" in ticket.read_text(encoding="utf-8")


def test_pause_operation_short_circuits_before_candidate_discovery(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(tmp_path, {"operation": "pause_automation"})

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    assert json.loads(result.stdout)["state"] == "paused"
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()
    assert (tmp_path / ".codex" / "ticket.local.md").read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"discussion_only"}\n'
    )
    assert _events(tmp_path) == []
