"""End-to-end tests for runtime-first apply-turn orchestration."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.ticket_autonomy import build_repo_context
from scripts.ticket_autonomy_config import AutomationMode, write_local_config
from scripts.ticket_dedup import target_fingerprint
from scripts.ticket_turn_batch import PendingSummaryStore

from tests.support.builders import make_ticket
from tests.test_turn_batch import valid_status_event

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


def _append_retained_correction_context(
    project_root: Path,
    ticket_path: Path,
    *,
    target: dict[str, list[str]] | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = None,
    timestamp: str | None = None,
    compacted: bool = False,
) -> None:
    details: dict[str, object] = {
        "correction_ready": True,
        "target": target or {"fields": ["priority"], "sections": []},
        "proposed_change": proposed_change or {"priority": "high"},
        "expected_ticket_fingerprint": (
            expected_ticket_fingerprint or target_fingerprint(ticket_path) or ""
        ),
    }
    if compacted:
        details["correction_detail_compacted"] = True
    else:
        details["correction_detail_retained"] = True
        details["correction_detail"] = "Prior automatic mutation wrote the wrong priority."
    event = valid_status_event(
        "failed",
        event_id="evt_prior_correction",
        timestamp=timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        thread_id="thread-1",
        mutation_id="mut-prior-correction",
        ticket_id="T-20260527-01",
        error_code="policy_blocked",
        **details,
    )
    assert PendingSummaryStore(project_root).append_event(event).state == "appended"


def _priority_update_candidate(
    ticket_path: Path | None,
    *,
    ticket_id: str = "T-20260527-01",
    priority: str = "low",
    evidence_summary: str = "Verification passed.",
) -> dict[str, object]:
    return {
        "ticket_id": ticket_id,
        "action": "update",
        "target": {"fields": ["priority"], "sections": []},
        "proposed_change": {"priority": priority},
        "expected_ticket_fingerprint": (
            target_fingerprint(ticket_path) if ticket_path is not None else None
        ),
        "evidence_summary": evidence_summary,
    }


def test_agent_primary_apply_turn_applies_update_through_gateway(tmp_path: Path) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                _priority_update_candidate(ticket),
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
    assert events[2]["status"] == "applied"
    assert events[2]["details"] == {}
    assert payload["ticket_updates"] == {"Applied": ["T-20260527-01"]}
    assert "commit_dispositions" not in payload
    assert all(event["thread_id"] == "thread-1" for event in events)
    expected_repo_context = json.loads(context.read_text(encoding="utf-8"))["git"]
    assert all(event["repo_context"] == expected_repo_context for event in events)


def test_agent_primary_apply_turn_applies_target_correction_from_retained_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(tmp_path, ticket)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
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
    assert " | codex | Corrected ticket from candidate evidence." in text
    events = _events(tmp_path)
    mutation_events = [event for event in events if event["event_type"] != "summary_receipt"]
    assert [event["status"] for event in mutation_events[-3:]] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert "decision" not in mutation_events[-3]["details"]
    assert "evidence_kind" not in mutation_events[-3]["details"]


def test_agent_primary_apply_turn_blocks_correction_with_compacted_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(tmp_path, ticket, compacted=True)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_agent_primary_apply_turn_blocks_correction_with_expired_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    old_timestamp = (datetime.now(UTC) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _append_retained_correction_context(tmp_path, ticket, timestamp=old_timestamp)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_agent_primary_apply_turn_blocks_correction_with_unmatched_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(
        tmp_path,
        ticket,
        expected_ticket_fingerprint="different-fingerprint",
    )
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_agent_primary_apply_turn_blocks_correction_with_proposed_change_mismatch(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(
        tmp_path,
        ticket,
        proposed_change={"priority": "normal"},
    )
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_invalid_preview_config_and_discussion_mode_do_not_write_tickets(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                _priority_update_candidate(ticket),
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
                _priority_update_candidate(ticket),
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


def test_apply_turn_reports_adapter_authorization_residue_as_invalid_candidate(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    candidate = _priority_update_candidate(
        ticket,
        evidence_summary="Adapter proposed a scoped update.",
    )
    candidate.update(
        {
            "authorization": {"token": "forged"},
            "mutation_id": "forged",
        }
    )
    context = _write_context(
        tmp_path,
        {
            "update_candidates": [candidate]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "invalid_candidate"
    assert payload["invalid_candidates"] == [
        {
            "key": "update_candidates",
            "index": 0,
            "errors": ["unknown candidate keys: ['authorization', 'mutation_id']"],
        }
    ]
    assert "priority: high" in ticket.read_text(encoding="utf-8")
    assert _events(tmp_path) == []


def test_explicit_conflict_reason_candidate_is_invalid_candidate(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    first = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    second = make_ticket(tickets_dir, "two.md", id="T-20260527-02")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    conflicting = _priority_update_candidate(
        first,
        ticket_id="T-20260527-01",
        evidence_summary="Current thread contradicts this ticket.",
    )
    conflicting["conflict_reason"] = "Current thread contradicts this ticket."
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                conflicting,
                _priority_update_candidate(second, ticket_id="T-20260527-02"),
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "invalid_candidate"
    assert payload["invalid_candidates"] == [
        {
            "key": "candidate_mutations",
            "index": 0,
            "errors": ["unknown candidate keys: ['conflict_reason']"],
        }
    ]
    assert "priority: high" in first.read_text(encoding="utf-8")
    assert "priority: high" in second.read_text(encoding="utf-8")
    assert _events(tmp_path) == []


def test_null_expected_fingerprint_invalidates_batch_without_private_event(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                _priority_update_candidate(ticket),
                _priority_update_candidate(None, ticket_id="T-20260527-02"),
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "invalid_candidate"
    assert payload["changed"] is False
    assert payload["invalid_candidates"] == [
        {
            "key": "candidate_mutations",
            "index": 1,
            "errors": ["expected_ticket_fingerprint is required for non-create writes"],
        }
    ]
    assert payload["discussion_question"] == (
        "Fix the explicit Ticket candidate payload before automatic ticket mutation."
    )
    assert "mutation_id" not in payload
    assert "event_id" not in payload
    assert "fingerprints" not in payload
    assert "priority: high" in ticket.read_text(encoding="utf-8")
    assert _events(tmp_path) == []


def test_null_expected_fingerprint_only_reports_invalid_candidate_without_private_event(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                _priority_update_candidate(None, ticket_id="T-20260527-02"),
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "invalid_candidate"
    assert payload["changed"] is False
    assert payload["invalid_candidates"] == [
        {
            "key": "candidate_mutations",
            "index": 0,
            "errors": ["expected_ticket_fingerprint is required for non-create writes"],
        }
    ]
    assert payload["discussion_question"] == (
        "Fix the explicit Ticket candidate payload before automatic ticket mutation."
    )
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
                _priority_update_candidate(ticket),
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
