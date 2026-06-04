"""Tests for target ticket read module."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.ticket_read import (
    InvalidTicketState,
    _ticket_to_dict,
    filter_tickets,
    find_ticket_by_id,
    fuzzy_match_id,
    list_tickets,
    query_tickets_payload,
)

from tests.support.builders import make_gen1_ticket, make_ticket


class TestListTickets:
    def test_empty_directory(self, tmp_tickets):
        assert list_tickets(tmp_tickets) == []

    def test_lists_all_target_tickets(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", priority="normal")
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-02", priority="low")

        tickets = list_tickets(tmp_tickets)

        assert [ticket.id for ticket in tickets] == ["T-20260302-02", "T-20260302-01"]

    def test_invalid_active_ticket_fails_explicitly(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        bad = tmp_tickets / "bad.md"
        bad.write_text("# Not a ticket\nNo yaml.", encoding="utf-8")

        with pytest.raises(InvalidTicketState):
            list_tickets(tmp_tickets)

    def test_legacy_active_ticket_fails_explicitly(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        make_gen1_ticket(tmp_tickets)

        with pytest.raises(InvalidTicketState):
            list_tickets(tmp_tickets)

    def test_null_optional_frontmatter_list_fails_explicitly(self, tmp_tickets):
        ticket = tmp_tickets / "T-20260302-01.md"
        ticket.write_text(
            "---\n"
            "id: T-20260302-01\n"
            "title: Test ticket\n"
            "status: open\n"
            "priority: normal\n"
            "tags: null\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
            "\n"
            "## Problem\n"
            "Test problem.\n"
            "\n"
            "## Next Action\n"
            "Test next action.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n",
            encoding="utf-8",
        )

        with pytest.raises(InvalidTicketState):
            list_tickets(tmp_tickets)

    def test_markdown_h1_inside_code_fence_lists_as_valid_ticket(self, tmp_tickets):
        ticket = tmp_tickets / "T-20260302-01.md"
        ticket.write_text(
            "---\n"
            "id: T-20260302-01\n"
            "title: Test ticket\n"
            "status: open\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
            "\n"
            "## Problem\n"
            "Preserve this Markdown example:\n"
            "```markdown\n"
            "# Example heading\n"
            "```\n"
            "\n"
            "## Next Action\n"
            "Continue work on this ticket.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Test fixture normalized to target schema.\n",
            encoding="utf-8",
        )

        tickets = list_tickets(tmp_tickets)

        assert [ticket.id for ticket in tickets] == ["T-20260302-01"]

    def test_closed_tickets_subdir_is_not_scanned(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir()
        make_ticket(closed_dir, "ignored.md", id="T-20260301-01", status="done")

        tickets = list_tickets(tmp_tickets)

        assert [ticket.id for ticket in tickets] == ["T-20260302-01"]

    def test_validated_ticket_that_fails_to_parse_raises(self, tmp_tickets, monkeypatch):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        import scripts.ticket_read as ticket_read

        monkeypatch.setattr(ticket_read, "parse_ticket", lambda _path: None)

        with pytest.raises(InvalidTicketState):
            list_tickets(tmp_tickets)


class TestFindTicketById:
    def test_exact_match(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")

        ticket = find_ticket_by_id(tmp_tickets, "T-20260302-01")

        assert ticket is not None
        assert ticket.id == "T-20260302-01"

    def test_not_found(self, tmp_tickets):
        assert find_ticket_by_id(tmp_tickets, "T-99999999-99") is None


class TestFilterTickets:
    def test_filter_by_status(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-02", status="done")
        filtered = filter_tickets(list_tickets(tmp_tickets), status="open")
        assert [ticket.id for ticket in filtered] == ["T-20260302-01"]

    def test_filter_by_priority_and_tag(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", priority="high", tags=["auth"])
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-02", priority="low", tags=["ui"])
        tickets = list_tickets(tmp_tickets)

        assert [ticket.id for ticket in filter_tickets(tickets, priority="high")] == [
            "T-20260302-01"
        ]
        assert [ticket.id for ticket in filter_tickets(tickets, tag="auth")] == ["T-20260302-01"]


class TestFuzzyMatchId:
    def test_prefix_match(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        assert [ticket.id for ticket in fuzzy_match_id(list_tickets(tmp_tickets), "T-2026030")] == [
            "T-20260302-01"
        ]

    def test_multiple_matches(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-02")
        assert len(fuzzy_match_id(list_tickets(tmp_tickets), "T-20260302")) == 2


def test_list_includes_display_sort_key_and_identity(tmp_tickets: Path) -> None:
    make_ticket(
        tmp_tickets,
        "ignored.md",
        id="T-20260503-10",
        status="open",
        priority="high",
        tags=["release"],
        title="High priority open work",
    )
    payload = [_ticket_to_dict(ticket) for ticket in list_tickets(tmp_tickets)]

    assert payload[0]["id"] == "T-20260503-10"
    assert payload[0]["display"]["identity"]["filename"] == "T-20260503-10.md"
    assert payload[0]["display"]["status_label"] == "Open"


def test_display_sort_key_uses_target_status_rank(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "ignored.md", id="T-20260503-10", status="idea")
    make_ticket(tmp_tickets, "ignored.md", id="T-20260503-11", status="open")
    make_ticket(
        tmp_tickets,
        "ignored.md",
        id="T-20260503-12",
        status="blocked",
        blocked_on="Waiting for upstream work.",
    )
    make_ticket(tmp_tickets, "ignored.md", id="T-20260503-13", status="done")
    make_ticket(tmp_tickets, "ignored.md", id="T-20260503-14", status="wontfix")

    payload_by_status = {
        item["status"]: item
        for item in (
            _ticket_to_dict(ticket)
            for ticket in list_tickets(tmp_tickets)
        )
    }

    assert payload_by_status["idea"]["display"]["sort_key"].startswith("0-idea")
    assert payload_by_status["open"]["display"]["sort_key"].startswith("1-open")
    assert payload_by_status["blocked"]["display"]["sort_key"].startswith("2-blocked")
    assert payload_by_status["done"]["display"]["sort_key"].startswith("8-done")
    assert payload_by_status["wontfix"]["display"]["sort_key"].startswith("9-wontfix")


def test_query_marks_ambiguous_prefix_matches(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "ignored.md", id="T-20260503-11", title="First match")
    make_ticket(tmp_tickets, "ignored.md", id="T-20260503-12", title="Second match")

    response = query_tickets_payload(list_tickets(tmp_tickets), "T-20260503")

    assert response["match"]["kind"] == "ambiguous_prefix"
    assert response["match"]["candidate_count"] == 2


READ_SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_read.py"


class TestReadCLI:
    def test_list_subcommand_returns_json(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_tickets)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert data["data"]["tickets"][0]["title"] == "Test ticket"

    def test_list_invalid_state_returns_json(self, tmp_tickets):
        bad = tmp_tickets / "bad.md"
        bad.write_text("# Not a ticket\nNo yaml.", encoding="utf-8")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_tickets)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["state"] == "invalid_state"

    def test_query_subcommand_fuzzy_match(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", title="Fix auth bug")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "query", str(tmp_tickets), "T-20260302"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert data["data"]["tickets"][0]["title"] == "Fix auth bug"

    def test_list_nonexistent_dir_returns_empty(self, tmp_path):
        (tmp_path / ".git").mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_path / "nope")],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["data"]["tickets"] == []
