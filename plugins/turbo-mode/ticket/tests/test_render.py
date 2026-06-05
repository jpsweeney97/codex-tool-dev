"""Tests for target ticket Markdown rendering."""

from __future__ import annotations

import pytest
from scripts.ticket_parse import parse_ticket
from scripts.ticket_render import render_ticket

_HISTORY = "- 2026-06-02T00:00:00Z | codex | Created target ticket."


class TestRenderTicket:
    def test_basic_ticket(self, tmp_path):
        result = render_ticket(
            id="T-20260302-01",
            title="Fix authentication timeout",
            status="open",
            priority="high",
            tags=["auth", "api"],
            related_paths=["handler.py"],
            problem="Auth handler times out for payloads >10MB.",
            next_action="Make timeout configurable per route.",
            acceptance_criteria=["Timeout configurable per route", "Default remains 30s"],
            verification="uv run pytest tests/test_auth.py",
            key_files=[
                {"file": "handler.py:45", "role": "Timeout logic", "look_for": "hardcoded timeout"},
            ],
            change_history_entry="- 2026-06-02T00:00:00Z | codex | Created target ticket.",
        )
        assert result.startswith("---\n")
        assert "\n---\n\n## Problem\n" in result
        assert "# T-20260302-01:" not in result
        assert "```yaml" not in result
        assert "id: T-20260302-01" in result
        assert 'title: "Fix authentication timeout"' in result
        assert "priority: high" in result
        assert "related_paths: [handler.py]" in result
        assert "## Next Action" in result
        assert "## Change History" in result
        assert "contract_version:" not in result

        ticket_file = tmp_path / "T-20260302-01.md"
        ticket_file.write_text(result, encoding="utf-8")
        ticket = parse_ticket(ticket_file)
        assert ticket is not None
        assert ticket.title == "Fix authentication timeout"

    def test_minimal_ticket_defaults_target_sections(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Minimal ticket",
            status="open",
            priority="normal",
            problem="Something needs fixing.",
            change_history_entry=_HISTORY,
        )
        assert "## Problem\nSomething needs fixing." in result
        assert "## Next Action\nContinue work on this ticket." in result
        assert "## Change History" in result
        assert "priority: normal" in result
        assert "date:" not in result
        assert "source:" not in result

    def test_optional_sections_included(self):
        result = render_ticket(
            id="T-20260302-01",
            title="With extras",
            status="open",
            priority="high",
            problem="Issue.",
            context="Found during refactor.",
            prior_investigation="Checked handler.py; timeout hardcoded.",
            decisions_made="Configurable timeout over fixed increase.",
            related="T-20260301-03 (API config refactor)",
            change_history_entry=_HISTORY,
        )
        assert "## Context" in result
        assert "## Prior Investigation" in result
        assert "## Decisions Made" in result
        assert "## Related" in result

    def test_blocked_by_is_forward_edge_only(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Blocked ticket",
            status="open",
            priority="high",
            problem="Waiting on dependency.",
            blocked_by=["T-20260302-02"],
            blocks=["T-20260302-03"],
            change_history_entry=_HISTORY,
        )
        assert "blocked_by: [T-20260302-02]" in result
        assert "blocks:" not in result

    def test_blocked_on_section_renders_between_next_action_and_change_history(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Blocked ticket",
            status="blocked",
            priority="high",
            problem="Waiting on dependency.",
            next_action="Resume once the dependency is resolved.",
            blocked_on="Waiting for deployment credentials from the user.",
            change_history_entry=_HISTORY,
        )

        assert "## Blocked On\nWaiting for deployment credentials from the user." in result
        assert result.index("## Next Action") < result.index("## Blocked On")
        assert result.index("## Blocked On") < result.index("## Change History")

    def test_empty_blocked_on_does_not_render_section(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Open ticket",
            status="open",
            priority="normal",
            problem="No blocker.",
            blocked_on="",
            change_history_entry=_HISTORY,
        )

        assert "## Blocked On" not in result

    def test_defer_field_not_persisted(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Deferred ticket",
            status="open",
            priority="low",
            problem="Can wait.",
            defer={"active": True, "reason": "Waiting for v2 API", "deferred_at": "2026-03-02"},
            change_history_entry=_HISTORY,
        )
        assert "defer:" not in result


def test_render_ticket_docstring_documents_blocked_on_order():
    doc = " ".join((render_ticket.__doc__ or "").split())

    assert "Problem -> Next Action -> Blocked On -> Change History" in doc


def test_render_ticket_yaml_injection_tags(tmp_path):
    """Tags containing YAML-special characters render as valid target YAML."""
    result = render_ticket(
        id="T-20260303-02",
        title="Test tag injection",
        status="open",
        priority="normal",
        tags=["tag: with colon", "tag\nwith\nnewline"],
        problem="Problem text.",
        change_history_entry=_HISTORY,
    )
    ticket_file = tmp_path / "T-20260303-02.md"
    ticket_file.write_text(result, encoding="utf-8")
    ticket = parse_ticket(ticket_file)
    assert ticket is not None
    assert "tag: with colon" in ticket.tags
    assert "tag\nwith\nnewline" in ticket.tags


def test_render_ticket_rejects_scalar_acceptance_criteria():
    with pytest.raises(ValueError, match="acceptance_criteria"):
        render_ticket(
            id="T-20260303-03",
            title="Reject scalar acceptance criteria",
            status="open",
            priority="normal",
            problem="Problem text.",
            acceptance_criteria="one criterion",  # type: ignore[arg-type]
            change_history_entry=_HISTORY,
        )
