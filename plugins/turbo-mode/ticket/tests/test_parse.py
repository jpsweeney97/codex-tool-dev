"""Tests for target ticket parsing and legacy cutover parsing."""

from __future__ import annotations

import textwrap

import pytest
from scripts.ticket_parse import (
    date_from_ticket_id,
    extract_fenced_yaml,
    extract_sections,
    extract_title,
    normalize_status,
    parse_legacy_ticket_for_cutover,
    parse_ticket,
    parse_yaml_block,
)

from tests.support.builders import make_gen1_ticket, make_gen2_ticket, make_gen4_ticket, make_ticket


class TestExtractFencedYaml:
    def test_standard_fenced_block(self):
        text = "# Title\n\n```yaml\nid: T-01\nstatus: open\n```\n\n## Body"
        assert extract_fenced_yaml(text) == "id: T-01\nstatus: open\n"

    def test_no_fenced_block(self):
        assert extract_fenced_yaml("# Just markdown\nNo yaml here.") is None


class TestParseYamlBlock:
    def test_valid_yaml(self):
        assert parse_yaml_block("id: T-01\nstatus: open\n") == {"id": "T-01", "status": "open"}

    def test_date_normalization(self):
        result = parse_yaml_block("date: 2026-03-02\n")
        assert result is not None
        assert result["date"] == "2026-03-02"

    def test_malformed_yaml(self):
        with pytest.warns(UserWarning, match="YAML parse error"):
            assert parse_yaml_block("key: [unclosed") is None


class TestExtractSections:
    def test_basic_sections(self):
        body = textwrap.dedent("""\
            ## Problem
            Something is broken.

            ## Approach
            Fix it.
        """)
        sections = extract_sections(body)
        assert sections["Problem"] == "Something is broken."
        assert sections["Approach"] == "Fix it."

    def test_nested_headings_ignored(self):
        body = "## Problem\nMain text.\n\n### Details\nSub text."
        assert "### Details" in extract_sections(body)["Problem"]


class TestExtractTitle:
    def test_extracts_legacy_h1_title(self):
        text = "# T-20260302-01: Fix auth bug\n\n```yaml\nid: T-20260302-01\n```"
        assert extract_title(text, "T-20260302-01") == "Fix auth bug"


class TestNormalizeStatus:
    def test_target_statuses_unchanged(self):
        for status in ("open", "in_progress", "done", "wontfix"):
            assert normalize_status(status) == (status, None)

    def test_legacy_deferred_maps_to_open_for_cutover(self):
        status, defer_info = normalize_status("deferred")
        assert status == "open"
        assert defer_info is not None


class TestDateFromTicketId:
    def test_target_id_date(self):
        assert date_from_ticket_id("T-20260302-01") == "2026-03-02"

    def test_invalid_id_rejected(self):
        with pytest.raises(ValueError, match="invalid target ticket id"):
            date_from_ticket_id("T-003")


class TestParseTicket:
    def test_target_ticket(self, tmp_tickets):
        path = make_ticket(tmp_tickets, "ignored.md", priority="normal")

        ticket = parse_ticket(path)

        assert ticket is not None
        assert ticket.id == "T-20260302-01"
        assert ticket.title == "Test ticket"
        assert ticket.date == "2026-03-02"
        assert ticket.status == "open"
        assert ticket.priority == "normal"
        assert ticket.generation == 10
        assert ticket.source == {}
        assert "Problem" in ticket.sections

    def test_legacy_ticket_is_not_normal_ticket(self, tmp_tickets):
        path = make_gen1_ticket(tmp_tickets)

        with pytest.warns(UserWarning, match="fenced YAML"):
            assert parse_ticket(path) is None

    def test_nonexistent_file(self, tmp_tickets):
        with pytest.warns(UserWarning, match="Cannot read"):
            assert parse_ticket(tmp_tickets / "nonexistent.md") is None


class TestLegacyCutoverParser:
    def test_gen1_ticket_can_be_parsed_for_cutover(self, tmp_tickets):
        path = make_gen1_ticket(tmp_tickets)

        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.id == "handoff-chain-viz"
        assert ticket.generation == 1
        assert ticket.priority == "medium"

    def test_gen2_section_renames_remain_diagnostic(self, tmp_tickets):
        path = make_gen2_ticket(tmp_tickets)

        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert "Problem" in ticket.sections

    def test_gen4_deferred_mapping_remains_diagnostic(self, tmp_tickets):
        path = make_gen4_ticket(tmp_tickets)

        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.status == "open"
        assert ticket.defer is not None
        assert ticket.source["type"] == "handoff"
