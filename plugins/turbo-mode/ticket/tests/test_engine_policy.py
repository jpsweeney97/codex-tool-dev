from __future__ import annotations

from pathlib import Path

from scripts.ticket_engine_core import (
    _evaluate_close_policy,
    _evaluate_reopen_policy,
    _evaluate_update_policy,
    _execute_close,
    _execute_reopen,
    _execute_update,
)
from scripts.ticket_parse import parse_ticket
from tests.support.builders import make_gen1_ticket, make_ticket


def test_update_invalid_transition_returns_structured_policy_data(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "done.md", id="T-20260503-21", status="done")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-21",
        ticket,
        {"status": "in_progress"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "done"
    assert response.data["requested_status"] == "in_progress"
    assert response.data["valid_recovery_statuses"] == []
    assert response.data["requires_reopen"] is True
    assert response.data["precondition_code"] == "none"
    assert response.data["precondition_detail"] is None


def test_close_terminal_invalid_transition_returns_structured_policy_data(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "terminal.md", id="T-20260503-22", status="done")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_close_policy(
        "T-20260503-22",
        ticket,
        {"resolution": "done"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "done"
    assert response.data["requested_status"] == "done"
    assert response.data["valid_recovery_statuses"] == []
    assert response.data["requires_reopen"] is True
    assert response.data["precondition_code"] == "none"
    assert response.data["precondition_detail"] is None


def test_close_missing_acceptance_criteria_returns_precondition_detail(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "no-ac.md", id="T-20260503-23", status="in_progress")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", ""), encoding="utf-8")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_close_policy(
        "T-20260503-23",
        ticket,
        {"resolution": "done"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "in_progress"
    assert response.data["requested_status"] == "done"
    assert response.data["valid_recovery_statuses"] == ["done", "wontfix"]
    assert response.data["requires_reopen"] is False
    assert response.data["precondition_code"] == "missing_acceptance_criteria"
    assert response.data["precondition_detail"] == {"missing": ["acceptance_criteria"]}


def test_close_dependency_blocked_returns_blocker_detail(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "blocker.md", id="T-20260503-24", status="open")
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-25",
        status="in_progress",
        blocked_by=["T-20260503-24"],
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_close_policy(
        "T-20260503-25",
        ticket,
        {"resolution": "done"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "dependency_blocked"
    assert response.data["current_status"] == "in_progress"
    assert response.data["requested_status"] == "done"
    assert response.data["valid_recovery_statuses"] == ["done", "wontfix"]
    assert response.data["requires_reopen"] is False
    assert response.data["precondition_code"] == "dependency_blocked"
    assert response.data["precondition_detail"] == {
        "blocking_ids": ["T-20260503-24"],
        "unresolved_blockers": ["T-20260503-24"],
        "missing_blockers": [],
    }


def test_reopen_invalid_transition_returns_structured_policy_data(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "open.md", id="T-20260503-26", status="open")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_reopen_policy(
        "T-20260503-26",
        ticket,
        {"reopen_reason": "Need more work"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "open"
    assert response.data["requested_status"] == "open"
    assert response.data["valid_recovery_statuses"] == []
    assert response.data["requires_reopen"] is False
    assert response.data["precondition_code"] == "none"
    assert response.data["precondition_detail"] is None


def test_update_evaluator_matches_execute_rejection(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "terminal-update.md", id="T-20260503-27", status="done")
    ticket = parse_ticket(path)
    assert ticket is not None

    policy = _evaluate_update_policy("T-20260503-27", ticket, {"status": "open"}, tmp_tickets)
    execute = _execute_update("T-20260503-27", {"status": "open"}, "session", "user", tmp_tickets)

    assert policy is not None
    assert policy.state == execute.state
    assert policy.error_code == execute.error_code
    assert policy.data["current_status"] == "done"


def test_close_evaluator_matches_execute_rejection(tmp_tickets: Path) -> None:
    path = make_gen1_ticket(tmp_tickets, "legacy-close.md")
    ticket = parse_ticket(path)
    assert ticket is not None

    policy = _evaluate_close_policy(ticket.id, ticket, {"resolution": "done"}, tmp_tickets)
    execute = _execute_close(ticket.id, {"resolution": "done"}, "session", "user", tmp_tickets)

    assert policy is not None
    assert policy.state == execute.state
    assert policy.error_code == execute.error_code


def test_reopen_evaluator_matches_execute_rejection(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "open-reopen.md", id="T-20260503-28", status="open")
    ticket = parse_ticket(path)
    assert ticket is not None

    policy = _evaluate_reopen_policy(
        "T-20260503-28",
        ticket,
        {"reopen_reason": "Need more work"},
        tmp_tickets,
    )
    execute = _execute_reopen("T-20260503-28", {"reopen_reason": "Need more work"}, "session", "user", tmp_tickets)

    assert policy is not None
    assert policy.state == execute.state
    assert policy.error_code == execute.error_code
