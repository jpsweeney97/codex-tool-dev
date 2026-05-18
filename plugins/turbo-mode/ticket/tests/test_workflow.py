from __future__ import annotations

import json
from pathlib import Path

from scripts.ticket_workflow import run_workflow
from tests.support.builders import make_ticket
from tests.support.workflow import (
    assert_preview_schema,
    now_iso,
    payload_file,
    trusted_args_ticket_payload,
    trusted_payload,
)


def test_prepare_malformed_json_returns_structured_error(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    bad_payload = tmp_path / "payload.json"
    bad_payload.write_text("{not-json", encoding="utf-8")

    response = run_workflow("prepare", bad_payload)

    assert response["state"] == "escalate"
    assert response["error_code"] == "parse_error"
    assert response["message"].startswith("Cannot read payload:")


def test_prepare_payload_path_with_spaces_does_not_emit_invalid_commands(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    payload_path = tmp_path / "payload with spaces.json"
    payload_path.write_text(json.dumps(trusted_payload(
        "create",
        {
            "title": "Workflow create",
            "problem": "Need a preview without invalid next commands.",
            "priority": "medium",
        },
    )), encoding="utf-8")

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    assert response["data"]["preview"]["next_command"] is None


def test_prepare_hydrates_payload_through_shared_dispatch(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "Hydrated create",
            "problem": "Workflow should hydrate classify, plan, and preflight outputs.",
            "priority": "medium",
        },
    ))

    response = run_workflow("prepare", payload_path)
    hydrated = json.loads(payload_path.read_text(encoding="utf-8"))

    assert response["state"] == "ready_to_execute"
    assert hydrated["classify_intent"] == "create"
    assert hydrated["classify_confidence"] == 0.95
    assert isinstance(hydrated["dedup_fingerprint"], str)
    assert "checks_passed" in hydrated
    assert_preview_schema(response["data"]["preview"], action="create", payload_path=payload_path)


def test_prepare_does_not_write_ticket_files(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    before_paths = sorted(str(path) for path in tmp_tickets.glob("*.md"))
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "No writes",
            "problem": "Prepare must stay read-only.",
            "priority": "medium",
        },
    ))

    response = run_workflow("prepare", payload_path)
    after_paths = sorted(str(path) for path in tmp_tickets.glob("*.md"))

    assert response["state"] == "ready_to_execute"
    assert before_paths == after_paths


def test_prepare_update_returns_unified_preview_schema(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "update.md", id="T-20260503-30", status="open")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "update",
        "T-20260503-30",
        {"status": "in_progress"},
    ))

    response = run_workflow("prepare", payload_path)
    hydrated = json.loads(payload_path.read_text(encoding="utf-8"))

    assert response["state"] == "ready_to_execute"
    assert hydrated["ticket_id"] == "T-20260503-30"
    assert isinstance(hydrated["target_fingerprint"], str)
    assert_preview_schema(response["data"]["preview"], action="update", payload_path=payload_path)


def test_prepare_close_returns_unified_preview_schema(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "close.md", id="T-20260503-31", status="in_progress")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "close",
        "T-20260503-31",
        {"resolution": "done"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    assert_preview_schema(response["data"]["preview"], action="close", payload_path=payload_path)


def test_prepare_reopen_returns_unified_preview_schema(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "reopen.md", id="T-20260503-32", status="done")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "reopen",
        "T-20260503-32",
        {"reopen_reason": "Need more work"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    assert_preview_schema(response["data"]["preview"], action="reopen", payload_path=payload_path)


def test_prepare_duplicate_create_stops_at_duplicate_candidate(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(
        tmp_tickets,
        "existing.md",
        id="T-20260503-33",
        date=now_iso()[:10],
        created_at=now_iso(),
        problem="Duplicate workflow problem",
    )
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "Duplicate create",
            "problem": "Duplicate workflow problem",
            "priority": "medium",
            "key_file_paths": ["test.py"],
        },
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "duplicate_candidate"
    assert response["data"]["preview"]["will_write"] is False


def test_prepare_blocked_close_is_not_ready(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "blocker.md", id="T-20260503-34", status="open")
    make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-35",
        status="in_progress",
        blocked_by=["T-20260503-34"],
    )
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "close",
        "T-20260503-35",
        {"resolution": "done"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "dependency_blocked"
    assert response["data"]["preview"]["will_write"] is False


def test_prepare_terminal_invalid_transition_is_not_ready(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "terminal.md", id="T-20260503-36", status="done")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "update",
        "T-20260503-36",
        {"status": "in_progress"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert response["data"]["preview"]["will_write"] is False


def test_prepare_nonterminal_invalid_transition_is_not_ready(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "nonterminal.md", id="T-20260503-37", status="open")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "update",
        "T-20260503-37",
        {"status": "done"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert response["data"]["preview"]["will_write"] is False


def test_prepare_close_without_acceptance_criteria_is_not_ready(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    path = make_ticket(tmp_tickets, "no-ac.md", id="T-20260503-38", status="in_progress")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", ""), encoding="utf-8")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "close",
        "T-20260503-38",
        {"resolution": "done"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert response["data"]["preview"]["will_write"] is False


def test_prepare_close_malformed_ticket_yaml_is_not_ready(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    path = make_ticket(tmp_tickets, "bad-yaml.md", id="T-20260503-39", status="in_progress")
    path.write_text("# broken\n```yaml\nid: [\n```\n", encoding="utf-8")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "close",
        "T-20260503-39",
        {"resolution": "done"},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "not_found"
    assert response["error_code"] == "not_found"


def test_prepare_reopen_without_reason_is_not_ready(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "done-reopen.md", id="T-20260503-40", status="done")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload(
        "reopen",
        "T-20260503-40",
        {},
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["data"]["preview"]["will_write"] is False
