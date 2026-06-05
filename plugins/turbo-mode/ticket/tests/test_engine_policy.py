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
from scripts.ticket_parse import parse_legacy_ticket_for_cutover, parse_ticket
from scripts.ticket_target_schema import validate_target_ticket_file

from tests.support.builders import make_gen1_ticket, make_ticket


def test_update_invalid_transition_returns_structured_policy_data(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "done.md", id="T-20260503-21", status="done")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-21",
        ticket,
        {"status": "open"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "done"
    assert response.data["requested_status"] == "open"
    assert response.data["valid_recovery_statuses"] == []
    assert response.data["requires_reopen"] is True
    assert response.data["precondition_code"] == "none"
    assert response.data["precondition_detail"] is None


def test_close_terminal_invalid_transition_returns_structured_policy_data(
    tmp_tickets: Path,
) -> None:
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


def test_close_policy_rejects_idea_as_terminal_source(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "idea.md", id="T-20260503-31", status="idea")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_close_policy(
        "T-20260503-31",
        ticket,
        {"resolution": "wontfix"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "idea"
    assert response.data["valid_recovery_statuses"] == []
    assert "promote idea to open first" in response.message


def test_close_missing_acceptance_criteria_returns_precondition_detail(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "no-ac.md", id="T-20260503-23", status="open")
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", ""), encoding="utf-8"
    )
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
    assert response.data["current_status"] == "open"
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
        status="blocked",
        blocked_by=["T-20260503-24"],
        blocked_on="Waiting for blocker resolution.",
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
    assert response.data["current_status"] == "blocked"
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


def test_update_blocked_transition_requires_visible_blocker(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "open.md", id="T-20260503-29", status="open")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-29",
        ticket,
        {"status": "blocked"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "open"
    assert response.data["requested_status"] == "blocked"
    assert response.data["precondition_code"] == "blocked_on_required"
    assert response.data["precondition_detail"] == {"missing": ["blocked_on"]}


def test_update_allows_blocked_to_open_with_blocker_cleanup(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-30",
        status="blocked",
        blocked_by=["T-20260503-31"],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-30",
        ticket,
        {"status": "open", "blocked_by": [], "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is None


def test_update_allows_blocked_to_open_without_blocked_by_field_when_already_empty(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-33",
        status="blocked",
        blocked_by=[],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-33",
        ticket,
        {"status": "open", "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is None


def test_update_rejects_blocked_to_open_without_blocked_on_even_when_blocked_by_empty(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-35",
        status="blocked",
        blocked_by=[],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-35",
        ticket,
        {"status": "open", "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["precondition_code"] == "blocker_cleanup_required"
    assert response.data["precondition_detail"] == {
        "required": ["blocked_by: []", "blocked_on: null"]
    }


def test_update_rejects_blocked_to_open_with_leftover_blocked_on(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-36",
        status="blocked",
        blocked_by=[],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-36",
        ticket,
        {
            "status": "open",
            "blocked_on": "Still waiting for the upstream fix.",
            "next_action": "Continue.",
        },
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["precondition_code"] == "blocker_cleanup_required"
    assert response.data["precondition_detail"] == {
        "required": ["blocked_by: []", "blocked_on: null"]
    }


def test_update_rejects_blocked_to_open_without_clearing_existing_blocked_by(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-34",
        status="blocked",
        blocked_by=["T-20260503-31"],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-34",
        ticket,
        {"status": "open", "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["precondition_code"] == "blocker_cleanup_required"


def test_update_rejects_blocked_to_done_with_close_action_hint(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-32",
        status="blocked",
        blocked_by=["T-20260503-31"],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-32",
        ticket,
        {"status": "done"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["valid_recovery_statuses"] == ["open"]
    assert "use close action" in response.message


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


def test_close_runtime_rejects_legacy_ticket_outside_cutover_reader(tmp_tickets: Path) -> None:
    path = make_gen1_ticket(tmp_tickets, "legacy-close.md")
    assert parse_ticket(path) is None
    legacy_ticket = parse_legacy_ticket_for_cutover(path)
    assert legacy_ticket is not None

    response = _execute_close(
        legacy_ticket.id,
        {"resolution": "done"},
        "session",
        "user",
        tmp_tickets,
    )

    assert response.state == "invalid_state"
    assert response.error_code == "invalid_state"
    assert response.ticket_id == legacy_ticket.id
    assert response.data["reason"]


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
    execute = _execute_reopen(
        "T-20260503-28", {"reopen_reason": "Need more work"}, "session", "user", tmp_tickets
    )

    assert policy is not None
    assert policy.state == execute.state
    assert policy.error_code == execute.error_code
