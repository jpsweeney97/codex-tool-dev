"""Tests for ticket_read.py — shared read module for query and list."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ticket_read import (
    _ticket_to_dict,
    find_ticket_by_id,
    filter_tickets,
    fuzzy_match_id,
    list_tickets,
    query_tickets_payload,
)
from tests.support.builders import make_gen1_ticket, make_gen2_ticket, make_ticket


class TestListTickets:
    def test_empty_directory(self, tmp_tickets):
        tickets = list_tickets(tmp_tickets)
        assert tickets == []

    def test_nonexistent_directory(self, tmp_path):
        tickets = list_tickets(tmp_path / "nonexistent")
        assert tickets == []

    def test_lists_all_tickets(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-first.md", id="T-20260302-01")
        make_ticket(tmp_tickets, "2026-03-02-second.md", id="T-20260302-02")
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 2

    def test_skips_unparseable(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-good.md", id="T-20260302-01")
        bad = tmp_tickets / "bad.md"
        bad.write_text("# Not a ticket\nNo yaml.", encoding="utf-8")
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 1

    def test_includes_legacy(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-new.md", id="T-20260302-01")
        make_gen1_ticket(tmp_tickets)
        make_gen2_ticket(tmp_tickets)
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 3

    def test_includes_closed_tickets(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-open.md", id="T-20260302-01")
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir()
        make_ticket(closed_dir, "2026-03-01-done.md", id="T-20260301-01", status="done")
        tickets = list_tickets(tmp_tickets, include_closed=True)
        assert len(tickets) == 2


class TestFindTicketById:
    def test_exact_match(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01")
        ticket = find_ticket_by_id(tmp_tickets, "T-20260302-01")
        assert ticket is not None
        assert ticket.id == "T-20260302-01"

    def test_not_found(self, tmp_tickets):
        assert find_ticket_by_id(tmp_tickets, "T-99999999-99") is None

    def test_legacy_id(self, tmp_tickets):

        make_gen2_ticket(tmp_tickets)
        ticket = find_ticket_by_id(tmp_tickets, "T-A")
        assert ticket is not None
        assert ticket.id == "T-A"
        assert ticket.title == "Refactor analytics pipeline"


class TestFilterTickets:
    def test_filter_by_status(self, tmp_tickets):

        make_ticket(tmp_tickets, "open.md", id="T-20260302-01", status="open")
        make_ticket(tmp_tickets, "done.md", id="T-20260302-02", status="done")
        tickets = list_tickets(tmp_tickets)
        filtered = filter_tickets(tickets, status="open")
        assert len(filtered) == 1
        assert filtered[0].id == "T-20260302-01"

    def test_filter_by_priority(self, tmp_tickets):

        make_ticket(tmp_tickets, "high.md", id="T-20260302-01", priority="high")
        make_ticket(tmp_tickets, "low.md", id="T-20260302-02", priority="low")
        tickets = list_tickets(tmp_tickets)
        filtered = filter_tickets(tickets, priority="high")
        assert len(filtered) == 1

    def test_filter_by_tag(self, tmp_tickets):

        make_ticket(tmp_tickets, "auth.md", id="T-20260302-01", tags=["auth", "api"])
        make_ticket(tmp_tickets, "ui.md", id="T-20260302-02", tags=["ui"])
        tickets = list_tickets(tmp_tickets)
        filtered = filter_tickets(tickets, tag="auth")
        assert len(filtered) == 1

    def test_filter_multiple_criteria(self, tmp_tickets):

        make_ticket(tmp_tickets, "match.md", id="T-20260302-01", status="open", priority="high")
        make_ticket(tmp_tickets, "no-match.md", id="T-20260302-02", status="open", priority="low")
        tickets = list_tickets(tmp_tickets)
        filtered = filter_tickets(tickets, status="open", priority="high")
        assert len(filtered) == 1


class TestFuzzyMatchId:
    def test_prefix_match(self, tmp_tickets):

        make_ticket(tmp_tickets, "ticket.md", id="T-20260302-01")
        tickets = list_tickets(tmp_tickets)
        matches = fuzzy_match_id(tickets, "T-2026030")
        assert len(matches) == 1

    def test_no_match(self, tmp_tickets):

        make_ticket(tmp_tickets, "ticket.md", id="T-20260302-01")
        tickets = list_tickets(tmp_tickets)
        matches = fuzzy_match_id(tickets, "T-99999")
        assert len(matches) == 0

    def test_multiple_matches(self, tmp_tickets):

        make_ticket(tmp_tickets, "one.md", id="T-20260302-01")
        make_ticket(tmp_tickets, "two.md", id="T-20260302-02")
        tickets = list_tickets(tmp_tickets)
        matches = fuzzy_match_id(tickets, "T-20260302")
        assert len(matches) == 2


def test_list_includes_display_sort_key_and_identity(tmp_tickets: Path) -> None:
    make_ticket(
        tmp_tickets,
        "2026-05-03-critical-open.md",
        id="T-20260503-10",
        status="open",
        priority="critical",
        tags=["release"],
        title="Critical open work",
    )
    tickets = list_tickets(tmp_tickets)
    payload = [_ticket_to_dict(ticket) for ticket in tickets]

    assert payload[0]["id"] == "T-20260503-10"
    assert payload[0]["display"]["identity"]["filename"] == "2026-05-03-critical-open.md"
    assert payload[0]["display"]["status_label"] == "Open"
    assert payload[0]["display"]["sort_key"] == "1-open-0"


def test_query_marks_ambiguous_prefix_matches(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "a.md", id="T-20260503-11", title="First match")
    make_ticket(tmp_tickets, "b.md", id="T-20260503-12", title="Second match")

    all_tickets = list_tickets(tmp_tickets, include_closed=True)
    response = query_tickets_payload(all_tickets, "T-20260503")
    payload = response["tickets"]

    assert len(payload) == 2
    assert {item["id"] for item in payload} == {"T-20260503-11", "T-20260503-12"}
    assert response["match"]["query"] == "T-20260503"
    assert response["match"]["kind"] == "ambiguous_prefix"
    assert response["match"]["candidate_count"] == 2
    assert all(item["display"]["match"]["kind"] == "ambiguous_prefix" for item in payload)


READ_SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_read.py"


class TestReadCLI:
    def test_list_subcommand_returns_json(self, tmp_tickets):
        make_ticket(tmp_tickets, "2026-03-02-first.md", id="T-20260302-01", status="open")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_tickets)],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert len(data["data"]["tickets"]) == 1
        assert data["data"]["tickets"][0]["title"] == "Test ticket"

    def test_list_with_status_filter(self, tmp_tickets):
        make_ticket(tmp_tickets, "2026-03-02-open.md", id="T-20260302-01", status="open")
        make_ticket(tmp_tickets, "2026-03-02-blocked.md", id="T-20260302-02", status="blocked")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_tickets), "--status", "open"],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["data"]["tickets"]) == 1
        assert data["data"]["tickets"][0]["id"] == "T-20260302-01"

    def test_query_subcommand_fuzzy_match(self, tmp_tickets):
        make_ticket(tmp_tickets, "2026-03-02-auth-bug.md", id="T-20260302-01", title="Fix auth bug")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "query", str(tmp_tickets), "T-20260302"],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert len(data["data"]["tickets"]) >= 1
        assert data["data"]["tickets"][0]["title"] == "Fix auth bug"

    def test_unknown_subcommand_exits_2(self, tmp_tickets):
        """argparse exits 2 for invalid subcommand choice, not 1."""
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "bogus", str(tmp_tickets)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2

    def test_missing_args_exits_1(self):
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 1

    def test_list_nonexistent_dir_returns_empty(self, tmp_path):
        (tmp_path / ".git").mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_path / "nope")],
            capture_output=True, text=True, timeout=10, cwd=str(tmp_path),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["data"]["tickets"] == []

    def test_list_rejects_path_outside_project_root(self, tmp_path):
        (tmp_path / ".git").mkdir(exist_ok=True)
        outside = tmp_path.parent / "outside-tickets"
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(outside)],
            capture_output=True, text=True, timeout=10, cwd=str(tmp_path),
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["state"] == "policy_blocked"

    def test_query_accepts_absolute_path_inside_project_root(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-auth-bug.md", id="T-20260302-01", title="Fix auth bug")
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "query", str(tmp_tickets), "T-20260302-01"],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["data"]["tickets"][0]["title"] == "Fix auth bug"


def test_cli_check_returns_close_readiness(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "2026-05-03-check.md", id="T-20260503-13")
    project_root = tmp_tickets.parent.parent

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(READ_SCRIPT),
            "check",
            str(tmp_tickets),
            "T-20260503-13",
        ],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert output["state"] == "ok"
    assert output["data"]["ticket"]["id"] == "T-20260503-13"
    assert output["data"]["close_readiness"]["ready"] is True
