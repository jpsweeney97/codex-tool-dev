from __future__ import annotations

import json
from pathlib import Path

from scripts.ticket_workflow import run_recovery, run_workflow
from tests.support.builders import make_ticket, write_autonomy_config
from tests.support.workflow import now_iso, payload_file, trusted_args_ticket_payload, trusted_payload


def test_execute_uses_executeinput_and_autonomy_config_from_shared_dispatch(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "Workflow execute",
            "problem": "Execute should still use the shared runner boundary.",
            "priority": "medium",
        },
    ))

    prepare = run_workflow("prepare", payload_path)
    execute = run_workflow("execute", payload_path)

    assert prepare["state"] == "ready_to_execute"
    assert execute["state"] == "ok_create"
    assert len(list(tmp_tickets.glob("*.md"))) == 1


def test_execute_stale_target_fingerprint_offers_rerun_prepare(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    ticket = make_ticket(tmp_tickets, "stale.md", id="T-20260503-63", status="open")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "update",
        "T-20260503-63",
        {"status": "in_progress"},
    ))

    prepare = run_workflow("prepare", payload_path)
    ticket.write_text(ticket.read_text(encoding="utf-8") + "\n<!-- changed -->\n", encoding="utf-8")
    execute = run_workflow("execute", payload_path)

    assert prepare["state"] == "ready_to_execute"
    assert execute["state"] == "preflight_failed"
    assert execute["error_code"] == "stale_plan"
    assert execute["data"]["recovery_options"][0]["recover_command"].endswith(" prepare " + str(payload_path))


def test_prepare_after_user_create_anyway_reaches_ready_to_execute(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(
        tmp_tickets,
        "existing.md",
        id="T-20260503-64",
        date=now_iso()[:10],
        created_at=now_iso(),
        problem="Create anyway duplicate",
    )
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "Create anyway",
            "problem": "Create anyway duplicate",
            "priority": "medium",
            "key_file_paths": ["test.py"],
        },
    ))

    first_prepare = run_workflow("prepare", payload_path)
    recover = run_recovery(payload_path, "create_anyway")
    second_prepare = run_workflow("prepare", payload_path)

    assert first_prepare["state"] == "duplicate_candidate"
    assert recover["state"] == "ok"
    assert second_prepare["state"] == "ready_to_execute"


def test_agent_create_anyway_recovery_remains_policy_blocked(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(
        tmp_tickets,
        "existing-agent.md",
        id="T-20260503-65",
        date=now_iso()[:10],
        created_at=now_iso(),
        problem="Agent duplicate",
    )
    write_autonomy_config(
        tmp_tickets,
        "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
    )
    payload = trusted_payload(
        "create",
        {
            "title": "Agent create anyway",
            "problem": "Agent duplicate",
            "priority": "medium",
            "key_file_paths": ["test.py"],
        },
    )
    payload["request_origin"] = "agent"
    payload["hook_request_origin"] = "agent"
    payload_path = payload_file(tmp_path, payload)

    first_prepare = run_workflow("prepare", payload_path)
    recover = run_recovery(payload_path, "create_anyway")
    second_prepare = run_workflow("prepare", payload_path)

    assert first_prepare["state"] == "duplicate_candidate"
    assert recover["state"] == "ok"
    assert second_prepare["state"] == "policy_blocked"
