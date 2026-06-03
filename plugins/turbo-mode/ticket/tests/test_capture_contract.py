from __future__ import annotations

from pathlib import Path

from scripts.ticket_parse import parse_ticket
from scripts.ticket_read import _ticket_to_dict
from scripts.ticket_render import render_ticket
from scripts.ticket_ux import close_readiness
from scripts.ticket_validate import validate_fields

from scripts import ticket_read
from tests.support.builders import make_gen1_ticket, make_ticket


def test_capture_ticket_renders_target_sections_without_capture_metadata(tmp_path: Path) -> None:
    text = render_ticket(
        id="T-20260518-01",
        title="Capture follow-up for hook guard",
        status="open",
        priority="normal",
        tags=["bug"],
        problem="The hook guard needs a user-friendly capture path.",
        captured_request="Create a follow-up for improving the hook guard.",
        next_action="Clarify the expected guard behavior.",
        related_paths=["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
        acceptance_criteria=["Guard behavior is documented"],
        change_history_entry="- 2026-06-02T00:00:00Z | codex | Created target ticket.",
    )

    assert "capture_confidence:" not in text
    assert "capture_source:" not in text
    assert "refinement_status:" not in text
    assert "component:" not in text
    assert "related_paths: [plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py]" in text
    assert "## Captured Request\nCreate a follow-up for improving the hook guard." in text
    assert "## Problem\nThe hook guard needs a user-friendly capture path." in text
    assert "## Next Action\nClarify the expected guard behavior." in text
    assert "## Acceptance Criteria\n- [ ] Guard behavior is documented" in text

    path = tmp_path / "T-20260518-01.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_ticket(path)
    assert parsed is not None
    assert parsed.related_paths == ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"]


def test_ticket_to_dict_uses_target_identity_and_paths(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "T-20260518-02.md",
        id="T-20260518-02",
        related_paths=["plugins/turbo-mode/ticket/scripts/ticket_read.py"],
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    payload = _ticket_to_dict(ticket)

    assert payload["related_paths"] == ["plugins/turbo-mode/ticket/scripts/ticket_read.py"]
    assert "capture" not in payload
    assert payload["display"]["identity"]["filename"] == "T-20260518-02.md"


def test_legacy_tickets_are_rejected_by_normal_parser(tmp_tickets: Path) -> None:
    ticket = parse_ticket(make_gen1_ticket(tmp_tickets, "legacy-capture-defaults.md"))
    assert ticket is None


def test_split_refinement_tickets_classifies_target_tickets_as_ready(
    tmp_tickets: Path,
) -> None:
    first_path = make_ticket(tmp_tickets, "T-20260518-03.md", id="T-20260518-03")
    second_path = make_ticket(tmp_tickets, "T-20260518-04.md", id="T-20260518-04")
    first_ticket = parse_ticket(first_path)
    second_ticket = parse_ticket(second_path)
    assert first_ticket is not None
    assert second_ticket is not None

    grouped = ticket_read.split_refinement_tickets([first_ticket, second_ticket])

    assert grouped["needs_refinement"] == []
    assert grouped["ready"] == [first_ticket, second_ticket]


def test_needs_refinement_acceptance_criteria_rejected_as_non_concrete() -> None:
    errors = validate_fields(
        {
            "title": "Incomplete ticket",
            "problem": "The captured issue is still vague.",
            "acceptance_criteria": ["Needs refinement"],
        }
    )
    assert "acceptance_criteria must be concrete; got Needs refinement" in errors


def test_needs_refinement_tag_is_not_a_target_tag() -> None:
    errors = validate_fields({"tags": ["needs-refinement"]})
    assert "tag needs-refinement is not a target tag" in errors


def test_capture_metadata_rejected_as_deprecated_write_fields() -> None:
    errors = validate_fields(
        {
            "capture_confidence": "certain",
            "capture_source": 123,
            "refinement_status": "rough",
            "component": ["ticket"],
            "related_paths": "plugins/turbo-mode/ticket",
        }
    )
    assert "capture_confidence is not a target write field" in errors
    assert "capture_source is not a target write field" in errors
    assert "refinement_status is not a target write field" in errors
    assert "component is not a target write field" in errors
    assert "related_paths must be a list, got str" in errors


def test_close_readiness_rejects_placeholder_ac_until_concrete(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "T-20260518-05.md",
        id="T-20260518-05",
        status="in_progress",
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
        path.read_text(encoding="utf-8").replace(
            "- [ ] Needs refinement",
            "- [ ] Hook guard behavior has concrete AC",
        ),
        encoding="utf-8",
    )
    refined_ticket = parse_ticket(path)
    assert refined_ticket is not None

    refined_result = close_readiness(refined_ticket, tmp_tickets, resolution="done")

    assert refined_result["ready"] is True
