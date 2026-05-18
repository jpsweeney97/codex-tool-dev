from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.ticket_parse import extract_fenced_yaml, parse_ticket, parse_yaml_block
from scripts.ticket_render import render_ticket
from scripts.ticket_update import run_update


def _payload_file(project_root: Path, payload: dict) -> Path:
    path = project_root / ".codex" / "ticket-update-payload.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _payload(tickets_dir: Path, update: dict, *, ticket_id: str = "T-20260518-01") -> dict:
    return {
        "tickets_dir": str(tickets_dir),
        "ticket_id": ticket_id,
        "session_id": "session-update",
        "hook_injected": True,
        "hook_request_origin": "user",
        "update": update,
    }


def _read_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _frontmatter(path: Path) -> dict:
    yaml_text = extract_fenced_yaml(path.read_text(encoding="utf-8"))
    assert yaml_text is not None
    data = parse_yaml_block(yaml_text)
    assert data is not None
    return data


def _make_refinement_ticket(
    tickets_dir: Path,
    *,
    status: str = "open",
    problem: str = "Needs refinement",
    next_action: str = "Needs refinement",
    acceptance_criteria: list[str] | None = None,
) -> Path:
    path = tickets_dir / "2026-05-18-refine-ticket.md"
    path.write_text(
        render_ticket(
            id="T-20260518-01",
            title="Refine captured hook preview",
            date="2026-05-18",
            status=status,
            priority="medium",
            source={"type": "ad-hoc", "ref": "", "session": "test-session"},
            tags=["bug", "needs-refinement"],
            problem=problem,
            capture_confidence="low",
            capture_source="conversation",
            refinement_status="needs_refinement",
            component="ticket",
            related_paths=["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
            next_action=next_action,
            acceptance_criteria=acceptance_criteria or ["Needs refinement"],
        ),
        encoding="utf-8",
    )
    return path


def test_prepare_previews_refinement_clear_before_execute(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "problem": "The hook guard preview hides whether a refinement ticket is ready.",
                "next_action": "Show the refinement-clear decision in the update preview.",
                "acceptance_criteria": [
                    "Preview reports when needs-refinement will be cleared.",
                    "Execution removes refinement metadata only after concrete fields exist.",
                ],
            },
        ),
    )

    response = run_update("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    assert response["message"].endswith("Refinement: will clear needs-refinement")
    assert response["data"]["preview"]["refinement"] == "will clear needs-refinement"
    parsed = parse_ticket(next(tmp_tickets.glob("*.md")))
    assert parsed is not None
    assert parsed.refinement_status == "needs_refinement"
    assert "needs-refinement" in parsed.tags


def test_execute_clears_refinement_status_and_tag_for_concrete_refinement(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "problem": "The hook guard preview hides whether a refinement ticket is ready.",
                "next_action": "Show the refinement-clear decision in the update preview.",
                "acceptance_criteria": [
                    "Preview reports when needs-refinement will be cleared.",
                    "Execution removes refinement metadata only after concrete fields exist.",
                ],
            },
        ),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    parsed = parse_ticket(ticket_path)
    assert parsed is not None
    assert parsed.refinement_status == ""
    assert "needs-refinement" not in parsed.tags
    assert parsed.sections["Problem"] == (
        "The hook guard preview hides whether a refinement ticket is ready."
    )
    assert parsed.sections["Next Action"] == (
        "Show the refinement-clear decision in the update preview."
    )
    assert "Needs refinement" not in parsed.sections["Acceptance Criteria"]
    assert "Preview reports when needs-refinement will be cleared." in parsed.sections[
        "Acceptance Criteria"
    ]


def test_successful_update_execute_deletes_ticket_tmp_payload(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = project_root / ".codex" / "ticket-tmp" / "update.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(
        json.dumps(_payload(tmp_tickets, {"priority": "high"})),
        encoding="utf-8",
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    assert execute["data"]["payload_deleted"] is True
    assert not payload_path.exists()


def test_failed_update_execute_preserves_ticket_tmp_payload(
    tmp_tickets: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = project_root / ".codex" / "ticket-tmp" / "update.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(json.dumps({"tickets_dir": str(tmp_tickets)}), encoding="utf-8")

    execute = run_update("execute", payload_path)

    assert execute["state"] in {"preflight_failed", "policy_blocked", "escalate"}
    assert payload_path.exists()


def test_priority_and_tags_only_keep_refinement_status(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"priority": "high", "tags": ["bug", "needs-refinement"]}),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    assert prepare["data"]["preview"]["refinement"] == "unchanged"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    parsed = parse_ticket(ticket_path)
    assert parsed is not None
    assert parsed.priority == "high"
    assert parsed.refinement_status == "needs_refinement"
    assert "needs-refinement" in parsed.tags


def test_tag_update_preserves_needs_refinement_tag_when_status_remains(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"tags": ["bug"]}),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    assert prepare["data"]["preview"]["refinement"] == "unchanged"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    parsed = parse_ticket(ticket_path)
    assert parsed is not None
    assert parsed.refinement_status == "needs_refinement"
    assert parsed.tags == ["bug", "needs-refinement"]


def test_acceptance_criteria_only_does_not_clear_refinement_status(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(
        tmp_tickets,
        problem="The existing problem statement is already concrete.",
        next_action="Add the missing regression coverage.",
    )
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "acceptance_criteria": [
                    "Regression coverage proves acceptance-criteria-only updates keep refinement.",
                ],
            },
        ),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    assert prepare["data"]["preview"]["refinement"] == "unchanged"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    parsed = parse_ticket(ticket_path)
    assert parsed is not None
    assert parsed.refinement_status == "needs_refinement"
    assert "needs-refinement" in parsed.tags


def test_concrete_criteria_with_placeholder_problem_does_not_clear_refinement_status(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "problem": "Needs refinement",
                "next_action": "Add regression coverage for refinement clearing.",
                "acceptance_criteria": [
                    "Regression coverage proves placeholder problem keeps refinement.",
                ],
            },
        ),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    assert prepare["data"]["preview"]["refinement"] == "unchanged"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    parsed = parse_ticket(ticket_path)
    assert parsed is not None
    assert parsed.refinement_status == "needs_refinement"
    assert "needs-refinement" in parsed.tags


def test_arbitrary_body_section_fields_are_rejected(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "approach": "Replace an arbitrary body section.",
                "verification": "pytest hidden",
            },
        ),
    )

    response = run_update("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "unsupported_update_fields"
    assert response["data"]["unsupported_fields"] == ["approach", "verification"]


def test_lifecycle_status_uses_existing_transition_policy(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets, status="open")
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"status": "done"}),
    )

    response = run_update("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert response["error_code"] == "invalid_transition"
    assert response["data"]["precondition_code"] == "missing_acceptance_criteria"


def test_execute_without_prepare_returns_stale_plan(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"priority": "high"}),
    )

    response = run_update("execute", payload_path)

    assert response["state"] == "preflight_failed"
    assert response["error_code"] == "stale_plan"


def test_execute_rejects_mutated_update_as_stale_plan(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"priority": "high"}),
    )
    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    payload = _read_payload(payload_path)
    payload["update"]["priority"] = "low"
    _write_payload(payload_path, payload)

    response = run_update("execute", payload_path)

    assert response["state"] == "preflight_failed"
    assert response["error_code"] == "stale_plan"


def test_execute_rejects_mutated_fields_as_stale_plan(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"priority": "high"}),
    )
    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    payload = _read_payload(payload_path)
    payload["fields"]["priority"] = "low"
    _write_payload(payload_path, payload)

    response = run_update("execute", payload_path)

    assert response["state"] == "preflight_failed"
    assert response["error_code"] == "stale_plan"


def test_execute_rejects_mutated_action_and_classify_intent_as_stale_plan(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(
        tmp_tickets,
        problem="The ticket has a concrete problem.",
        next_action="The ticket has a concrete next action.",
        acceptance_criteria=["The ticket has concrete acceptance criteria."],
    )
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"priority": "high"}),
    )
    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    payload = _read_payload(payload_path)
    payload["action"] = "close"
    payload["classify_intent"] = "close"
    _write_payload(payload_path, payload)

    response = run_update("execute", payload_path)

    assert response["state"] == "preflight_failed"
    assert response["error_code"] == "stale_plan"


def test_execute_rejects_mutated_preview_as_stale_plan(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, {"priority": "high"}),
    )
    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    payload = _read_payload(payload_path)
    payload["update_prepare"]["preview"]["refinement"] = "tampered"
    _write_payload(payload_path, payload)

    response = run_update("execute", payload_path)

    assert response["state"] == "preflight_failed"
    assert response["error_code"] == "stale_plan"


def test_reopen_terminal_ticket_uses_engine_reopen_path(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(tmp_tickets, status="done")
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "status": "open",
                "reopen_reason": "Regression reproduced after closure.",
            },
        ),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    assert prepare["data"]["preview"]["action"] == "reopen"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_reopen"
    parsed = parse_ticket(ticket_path)
    assert parsed is not None
    assert parsed.status == "open"
    assert "Regression reproduced after closure." in ticket_path.read_text(encoding="utf-8")


def test_close_payload_rejects_mixed_refinement_fields(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets, status="in_progress")
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "status": "done",
                "problem": "This field must not be dropped by close mapping.",
            },
        ),
    )

    response = run_update("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "unsupported_update_fields"
    assert response["data"]["unsupported_fields"] == ["problem"]


def test_reopen_payload_rejects_mixed_metadata_fields(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets, status="done")
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "status": "open",
                "reopen_reason": "Regression reproduced after closure.",
                "priority": "high",
            },
        ),
    )

    response = run_update("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "unsupported_update_fields"
    assert response["data"]["unsupported_fields"] == ["priority"]


def test_metadata_dependency_update_writes_scoped_frontmatter(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    ticket_path = _make_refinement_ticket(tmp_tickets)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            {
                "component": "ticket",
                "related_paths": ["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
                "blocked_by": ["T-20260518-02"],
                "blocks": ["T-20260518-03"],
            },
        ),
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    data = _frontmatter(ticket_path)
    assert data["component"] == "ticket"
    assert data["related_paths"] == ["plugins/turbo-mode/ticket/scripts/ticket_update.py"]
    assert data["blocked_by"] == ["T-20260518-02"]
    assert data["blocks"] == ["T-20260518-03"]
