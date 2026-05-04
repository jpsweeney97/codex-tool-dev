from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ticket_parse import parse_ticket
from scripts.ticket_ux import close_readiness, humanize_state, ticket_identity
from tests.support.builders import make_gen1_ticket, make_ticket


def test_ticket_identity_uses_content_id_before_filename(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "2026-05-03-readable-slug.md",
        id="T-20260503-07",
        title="Readable slug is not identity",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    identity = ticket_identity(ticket)

    assert identity == {
        "id": "T-20260503-07",
        "title": "Readable slug is not identity",
        "path": str(path),
        "filename": "2026-05-03-readable-slug.md",
    }


def test_humanize_state_replaces_internal_terms() -> None:
    assert humanize_state("duplicate_candidate") == "Potential duplicate found"
    assert humanize_state("policy_blocked") == "Blocked by ticket policy"
    assert humanize_state("target_fingerprint") == "Ticket changed since preview"


def test_close_readiness_reports_missing_acceptance_criteria(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "2026-05-03-no-criteria.md",
        id="T-20260503-08",
        extra_sections="\n",
    )
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", "")
    path.write_text(text, encoding="utf-8")
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "invalid_transition"
    assert result["missing"] == ["acceptance_criteria"]
    assert result["allowed_actions"] == [
        "add acceptance criteria",
        "close as wontfix",
        "keep current status",
    ]


def test_close_readiness_allows_wontfix_without_acceptance_criteria(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "2026-05-03-wontfix.md", id="T-20260503-09")
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", "")
    path.write_text(text, encoding="utf-8")
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="wontfix")

    assert result["ready"] is True
    assert result["missing"] == []
    assert result["allowed_actions"] == ["close as wontfix"]


@pytest.mark.parametrize("status", ["done", "wontfix"])
def test_close_readiness_rejects_terminal_tickets(tmp_tickets: Path, status: str) -> None:
    path = make_ticket(
        tmp_tickets,
        f"2026-05-03-terminal-{status}.md",
        id=f"T-20260503-{10 if status == 'done' else 11}",
        status=status,
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "invalid_transition"
    assert result["status"] == status
    assert result["allowed_actions"] == ["reopen before closing", "keep current status"]


def test_close_readiness_rejects_legacy_tickets(tmp_tickets: Path) -> None:
    path = make_gen1_ticket(tmp_tickets, "legacy.md")
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "policy_blocked"
    assert result["allowed_actions"] == ["migrate ticket before close", "keep current status"]


def test_close_readiness_reports_open_blocker(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "blocker.md", id="T-20260503-12", status="open")
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-13",
        status="in_progress",
        blocked_by=["T-20260503-12"],
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "dependency_blocked"
    assert result["blocking_ids"] == ["T-20260503-12"]
    assert result["missing_blockers"] == []
    assert result["unresolved_blockers"] == ["T-20260503-12"]
    assert result["allowed_actions"] == ["resolve blockers", "close as wontfix", "keep current status"]


def test_close_readiness_reports_missing_blocker_reference(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "missing-blocker.md",
        id="T-20260503-14",
        status="in_progress",
        blocked_by=["T-20260503-99"],
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "dependency_blocked"
    assert result["blocking_ids"] == ["T-20260503-99"]
    assert result["missing_blockers"] == ["T-20260503-99"]
    assert result["unresolved_blockers"] == []


def test_close_readiness_error_code_matches_close_policy_for_terminal_ticket(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(tmp_tickets, "terminal-parity.md", id="T-20260503-15", status="done")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-15",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_missing_acceptance_criteria(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(tmp_tickets, "missing-ac-parity.md", id="T-20260503-16", status="in_progress")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", ""), encoding="utf-8")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-16",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_blocked_ticket(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    make_ticket(tmp_tickets, "blocker-parity.md", id="T-20260503-17", status="open")
    path = make_ticket(
        tmp_tickets,
        "blocked-parity.md",
        id="T-20260503-18",
        status="in_progress",
        blocked_by=["T-20260503-17"],
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-18",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_legacy_ticket(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_gen1_ticket(tmp_tickets, "legacy-parity.md")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        ticket.id,
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_invalid_resolution(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(tmp_tickets, "invalid-resolution-parity.md", id="T-20260503-19", status="in_progress")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="blocked")
    close_response = _execute_close(
        "T-20260503-19",
        {"resolution": "blocked"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_ready_matches_close_policy_for_successful_close(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(tmp_tickets, "success-parity.md", id="T-20260503-20", status="in_progress")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-20",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["ready"] is True
    assert close_response.state == "ok_close"
