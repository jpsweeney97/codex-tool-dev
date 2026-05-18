from __future__ import annotations

from pathlib import Path

from scripts.ticket_parse import parse_ticket
from scripts.ticket_read import _ticket_to_dict
from scripts.ticket_render import render_ticket
from scripts.ticket_ux import close_readiness
from scripts.ticket_validate import validate_fields

from scripts import ticket_read
from tests.support.builders import make_gen1_ticket, make_ticket


def test_capture_ticket_renders_required_sections_and_metadata(tmp_path: Path) -> None:
    text = render_ticket(
        id="T-20260518-01",
        title="Capture follow-up for hook guard preview",
        date="2026-05-18",
        status="open",
        priority="medium",
        source={"type": "capture", "ref": "", "session": "session-1"},
        tags=["bug", "needs-refinement"],
        problem="The hook guard preview needs a user-friendly capture path.",
        captured_request="Create a follow-up for improving the hook guard preview.",
        next_action="Clarify the expected preview behavior for hook guard failures.",
        capture_confidence="low",
        capture_source="conversation",
        refinement_status="needs_refinement",
        component="ticket",
        related_paths=["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
        acceptance_criteria=["Needs refinement"],
    )

    assert "capture_confidence: low" in text
    assert "capture_source: conversation" in text
    assert "refinement_status: needs_refinement" in text
    assert "component: ticket" in text
    assert "related_paths: [plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py]" in text
    assert "## Captured Request\nCreate a follow-up for improving the hook guard preview." in text
    assert "## Problem\nThe hook guard preview needs a user-friendly capture path." in text
    assert "## Next Action\nClarify the expected preview behavior for hook guard failures." in text
    assert "## Acceptance Criteria\n- [ ] Needs refinement" in text

    path = tmp_path / "ticket.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_ticket(path)
    assert parsed is not None
    assert parsed.capture_confidence == "low"
    assert parsed.capture_source == "conversation"
    assert parsed.refinement_status == "needs_refinement"
    assert parsed.component == "ticket"
    assert parsed.related_paths == ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"]


def test_ticket_to_dict_includes_capture_metadata(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "capture-metadata.md",
        id="T-20260518-02",
        extra_yaml=(
            "capture_confidence: medium\n"
            "        capture_source: conversation\n"
            "        refinement_status: needs_refinement\n"
            "        component: ticket\n"
            "        related_paths: [plugins/turbo-mode/ticket/scripts/ticket_read.py]\n"
            "        "
        ),
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    payload = _ticket_to_dict(ticket)

    assert payload["capture"] == {
        "confidence": "medium",
        "source": "conversation",
        "refinement_status": "needs_refinement",
        "component": "ticket",
        "related_paths": ["plugins/turbo-mode/ticket/scripts/ticket_read.py"],
    }


def test_legacy_tickets_default_capture_metadata(tmp_tickets: Path) -> None:
    ticket = parse_ticket(make_gen1_ticket(tmp_tickets, "legacy-capture-defaults.md"))
    assert ticket is not None

    assert ticket.capture_confidence == ""
    assert ticket.capture_source == ""
    assert ticket.refinement_status == ""
    assert ticket.component == ""
    assert ticket.related_paths == []


def test_split_refinement_tickets_groups_by_refinement_status(
    tmp_tickets: Path,
) -> None:
    needs_path = make_ticket(
        tmp_tickets,
        "needs-refinement.md",
        id="T-20260518-03",
        extra_yaml="refinement_status: needs_refinement\n        ",
    )
    ready_path = make_ticket(tmp_tickets, "ready.md", id="T-20260518-04")
    needs_ticket = parse_ticket(needs_path)
    ready_ticket = parse_ticket(ready_path)
    assert needs_ticket is not None
    assert ready_ticket is not None

    grouped = ticket_read.split_refinement_tickets([needs_ticket, ready_ticket])

    assert grouped["needs_refinement"] == [needs_ticket]
    assert grouped["ready"] == [ready_ticket]


def test_needs_refinement_acceptance_criteria_requires_refinement_status() -> None:
    errors = validate_fields(
        {
            "title": "Incomplete ticket",
            "problem": "The captured issue is still vague.",
            "acceptance_criteria": ["Needs refinement"],
        }
    )
    assert (
        "acceptance_criteria Needs refinement requires refinement_status=needs_refinement"
    ) in errors


def test_needs_refinement_tag_requires_refinement_status() -> None:
    errors = validate_fields({"tags": ["needs-refinement"]})
    assert "tag needs-refinement requires refinement_status=needs_refinement" in errors


def test_capture_metadata_rejects_invalid_values() -> None:
    errors = validate_fields(
        {
            "capture_confidence": "certain",
            "capture_source": 123,
            "refinement_status": "rough",
            "component": ["ticket"],
            "related_paths": "plugins/turbo-mode/ticket",
        }
    )
    assert "capture_confidence must be one of ['high', 'low', 'medium'], got 'certain'" in errors
    assert "capture_source must be a string, got int" in errors
    assert "refinement_status must be 'needs_refinement', got 'rough'" in errors
    assert "component must be a string, got list" in errors
    assert "related_paths must be a list, got str" in errors


def test_close_readiness_rejects_needs_refinement_until_ac_is_concrete(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "needs-refinement-close.md",
        id="T-20260518-05",
        status="in_progress",
        extra_yaml="refinement_status: needs_refinement\n        ",
    )
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("- [ ] Issue resolved", "- [ ] Needs refinement"),
        encoding="utf-8",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "invalid_transition"
    assert result["missing"] == ["acceptance_criteria"]
    assert result["message"] == (
        "Transition to 'done' requires concrete acceptance criteria; ticket still needs refinement"
    )

    path.write_text(
        path.read_text(encoding="utf-8")
        .replace("refinement_status: needs_refinement\n", "")
        .replace("- [ ] Needs refinement", "- [ ] Hook guard preview has concrete AC"),
        encoding="utf-8",
    )
    refined_ticket = parse_ticket(path)
    assert refined_ticket is not None

    refined_result = close_readiness(refined_ticket, tmp_tickets, resolution="done")

    assert refined_result["ready"] is True
