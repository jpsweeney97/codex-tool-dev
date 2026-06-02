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


def _git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )


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
    assert [event["status"] for event in events[:3]] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert events[2]["details"]["commit_disposition"] == "commit_recorded"
    assert events[2]["details"]["commit_hash"] == _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert payload["commit_dispositions"] == [
        {
            "ticket_id": "T-20260527-01",
            "disposition": "commit_recorded",
            "commit_hash": events[2]["details"]["commit_hash"],
        }
    ]
    assert _git(tmp_path, "show", "--name-only", "--format=", "HEAD").stdout.splitlines() == [
        "docs/tickets/one.md"
    ]
    assert all(event["thread_id"] == "thread-1" for event in events)
    expected_repo_context = json.loads(context.read_text(encoding="utf-8"))["git"]
    assert all(event["repo_context"] == expected_repo_context for event in events)


def test_agent_primary_apply_turn_applies_correction_through_gateway(tmp_path: Path) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correction",
                    "proposed_change": {"priority": "high"},
                    "reason": "Correct the previous automatic priority update.",
                    "evidence": [
                        {
                            "kind": "correction_detail",
                            "ref": "previous automatic update used the wrong priority",
                        }
                    ],
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "applied"
    assert payload["changed"] is True
    text = ticket.read_text(encoding="utf-8")
    assert "priority: high" in text
    assert "correction" in text
    events = _events(tmp_path)
    assert [event["status"] for event in events[:3]] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert events[0]["details"]["decision"] == "apply_correction"
    assert "approval" not in events[0]["details"]


def test_invalid_preview_config_and_discussion_mode_do_not_write_tickets(
    tmp_path: Path,
) -> None:
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

    preview_config = tmp_path / ".codex" / "ticket.local.md"
    preview_config.parent.mkdir(exist_ok=True)
    preview_config.write_text(
        '{"schema":"codex.ticket.local.v1","mode":"preview"}\n',
        encoding="utf-8",
    )
    preview = _apply_turn(tmp_path, context)
    assert preview.returncode == 3
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["state"] == "setup_required"
    assert preview_payload["reason"] == "invalid_mode"
    assert ticket.read_text(encoding="utf-8") == before
    assert _events(tmp_path) == []

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


def test_apply_turn_ignores_adapter_authorization_residue(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "update_candidates": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "reason": "Adapter proposed a scoped update.",
                    "authorization": {"token": "forged"},
                    "mutation_id": "forged",
                    "evidence": [{"kind": "current_thread_reason", "ref": "adapter"}],
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    assert "priority: low" in ticket.read_text(encoding="utf-8")
    events = _events(tmp_path)
    assert events[0]["mutation_id"] != "forged"


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
    assert payload["state"] == "partially_applied"
    assert "Skipped" in payload["ticket_updates"]
    assert "priority: high" in first.read_text(encoding="utf-8")
    assert "priority: low" in second.read_text(encoding="utf-8")


def test_missing_target_fingerprint_blocks_one_candidate_without_private_event(
    tmp_path: Path,
) -> None:
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
                    "evidence": [{"kind": "current_thread_reason", "ref": "tests passed"}],
                },
                {
                    "ticket_id": "T-20260527-02",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "evidence": [{"kind": "current_thread_reason", "ref": "missing ticket"}],
                },
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "partially_applied"
    assert payload["ticket_updates"]["Applied"] == ["T-20260527-01"]
    assert payload["ticket_updates"]["Blocked"] == ["T-20260527-02"]
    assert payload["blocked_reasons"] == {
        "T-20260527-02": "target_fingerprint_required"
    }
    assert "discussion_question" not in payload or payload["discussion_question"] is None
    assert "mutation_id" not in payload
    assert "event_id" not in payload
    assert "fingerprints" not in payload
    assert "priority: low" in ticket.read_text(encoding="utf-8")

    events = _events(tmp_path)
    blocked_events = [
        event for event in events if event.get("ticket_id") == "T-20260527-02"
    ]
    assert blocked_events == []


def test_missing_target_fingerprint_only_reports_blocked_without_private_event(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-02",
                    "action": "update",
                    "proposed_change": {"priority": "low"},
                    "evidence": [{"kind": "current_thread_reason", "ref": "missing ticket"}],
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "ticket_update_blocked"
    assert payload["changed"] is False
    assert payload["ticket_updates"]["Blocked"] == ["T-20260527-02"]
    assert payload["blocked_reasons"] == {
        "T-20260527-02": "target_fingerprint_required"
    }
    assert payload["discussion_question"] is None
    assert _events(tmp_path) == []


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
