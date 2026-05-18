"""Tests for ticket_parse.py — fenced-YAML parsing and section extraction."""
from __future__ import annotations

import textwrap

import pytest

# Import path: tests run from packages/plugins/ticket/
from scripts.ticket_parse import (
    detect_generation,
    extract_fenced_yaml,
    extract_sections,
    extract_title,
    normalize_status,
    parse_ticket,
    parse_yaml_block,
)
from tests.support.builders import make_gen1_ticket, make_gen2_ticket, make_gen3_ticket, make_gen4_ticket, make_ticket


# --- extract_fenced_yaml ---


class TestExtractFencedYaml:
    def test_standard_fenced_block(self):
        text = "# Title\n\n```yaml\nid: T-01\nstatus: open\n```\n\n## Body"
        assert extract_fenced_yaml(text) == "id: T-01\nstatus: open\n"

    def test_yml_variant(self):
        text = "```yml\nid: T-01\n```"
        assert extract_fenced_yaml(text) == "id: T-01\n"

    def test_no_fenced_block(self):
        assert extract_fenced_yaml("# Just markdown\nNo yaml here.") is None

    def test_multiple_blocks_returns_first(self):
        text = "```yaml\nfirst: true\n```\n\n```yaml\nsecond: true\n```"
        assert extract_fenced_yaml(text) == "first: true\n"

    def test_non_yaml_fenced_block_ignored(self):
        text = "```python\nprint('hi')\n```\n```yaml\nid: T-01\n```"
        assert extract_fenced_yaml(text) == "id: T-01\n"


# --- parse_yaml_block ---


class TestParseYamlBlock:
    def test_valid_yaml(self):
        result = parse_yaml_block("id: T-01\nstatus: open\n")
        assert result == {"id": "T-01", "status": "open"}

    def test_date_normalization(self):
        """PyYAML converts unquoted dates to datetime.date — we normalize back."""
        result = parse_yaml_block("date: 2026-03-02\n")
        assert result["date"] == "2026-03-02"
        assert isinstance(result["date"], str)

    def test_empty_string(self):
        assert parse_yaml_block("") is None

    def test_malformed_yaml(self):
        with pytest.warns(UserWarning, match="YAML parse error"):
            result = parse_yaml_block("key: [unclosed")
        assert result is None

    def test_non_dict_yaml(self):
        with pytest.warns(UserWarning, match="expected dict"):
            result = parse_yaml_block("- item1\n- item2\n")
        assert result is None


# --- extract_sections ---


class TestExtractSections:
    def test_basic_sections(self):
        body = textwrap.dedent("""\
            ## Problem
            Something is broken.

            ## Approach
            Fix it.

            ## Acceptance Criteria
            - [ ] Fixed
        """)
        sections = extract_sections(body)
        assert "Problem" in sections
        assert "Something is broken." in sections["Problem"]
        assert "Approach" in sections
        assert "Acceptance Criteria" in sections

    def test_empty_body(self):
        assert extract_sections("") == {}

    def test_content_before_first_heading(self):
        body = "Some preamble text.\n\n## Problem\nThe issue."
        sections = extract_sections(body)
        assert "Problem" in sections
        # Preamble is discarded (not a named section)

    def test_nested_headings_ignored(self):
        """### subheadings are part of the parent ## section."""
        body = "## Problem\nMain text.\n\n### Details\nSub text."
        sections = extract_sections(body)
        assert "Problem" in sections
        assert "### Details" in sections["Problem"]
        assert "Sub text." in sections["Problem"]


class TestExtractTitle:
    def test_extracts_title_from_v10_heading(self):
        text = "# T-20260302-01: Fix auth bug\n\n```yaml\nid: T-20260302-01\n```"
        assert extract_title(text, "T-20260302-01") == "Fix auth bug"

    def test_extracts_plain_title_heading(self):
        text = "# Fix auth bug\n\n```yaml\nid: T-20260302-01\n```"
        assert extract_title(text, "T-20260302-01") == "Fix auth bug"

    def test_missing_h1_returns_empty_string(self):
        text = "```yaml\nid: T-20260302-01\n```"
        assert extract_title(text, "T-20260302-01") == ""


# --- detect_generation ---


class TestDetectGeneration:
    def test_gen1_slug_id(self):
        assert detect_generation({"id": "handoff-chain-viz"}) == 1

    def test_gen2_letter_id(self):
        assert detect_generation({"id": "T-A"}) == 2
        assert detect_generation({"id": "T-F"}) == 2

    def test_gen3_numeric_id(self):
        assert detect_generation({"id": "T-003"}) == 3
        assert detect_generation({"id": "T-100"}) == 3

    def test_gen4_date_id_with_provenance(self):
        assert detect_generation({"id": "T-20260301-01", "provenance": {}}) == 4

    def test_v10_date_id_with_source(self):
        assert detect_generation({"id": "T-20260302-01", "source": {}}) == 10

    def test_v10_with_contract_version(self):
        assert detect_generation({"id": "T-20260302-01", "contract_version": "1.0"}) == 10

    def test_non_string_id_coerced(self):
        """YAML `id: 123` produces int — must not crash regex matchers."""
        assert detect_generation({"id": 123}) == 1
        assert detect_generation({"id": 42, "provenance": {}}) == 1


# --- normalize_status ---


class TestNormalizeStatus:
    def test_canonical_statuses_unchanged(self):
        for s in ("open", "in_progress", "blocked", "done", "wontfix"):
            assert normalize_status(s) == (s, None)

    def test_planning_maps_to_open(self):
        assert normalize_status("planning") == ("open", None)

    def test_implementing_maps_to_in_progress(self):
        assert normalize_status("implementing") == ("in_progress", None)

    def test_complete_maps_to_done(self):
        assert normalize_status("complete") == ("done", None)

    def test_closed_maps_to_done(self):
        assert normalize_status("closed") == ("done", None)

    def test_deferred_maps_to_open_with_defer(self):
        status, defer_info = normalize_status("deferred")
        assert status == "open"
        assert defer_info is not None
        assert defer_info["active"] is True

    def test_unknown_status_preserved(self):
        """Unknown statuses pass through — mutation paths fail closed."""
        assert normalize_status("banana") == ("banana", None)


# --- parse_ticket ---


class TestParseTicket:
    def test_v10_ticket(self, tmp_tickets):

        path = make_ticket(tmp_tickets, "2026-03-02-test.md")
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.id == "T-20260302-01"
        assert ticket.title == "Test ticket"
        assert ticket.status == "open"
        assert ticket.priority == "high"
        assert ticket.generation == 10
        assert "Problem" in ticket.sections

    def test_gen1_ticket(self, tmp_tickets):

        path = make_gen1_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.id == "handoff-chain-viz"
        assert ticket.title == "Visualize handoff chains"
        assert ticket.generation == 1
        # Field defaults applied
        assert ticket.source == {"type": "legacy", "ref": "", "session": ""}
        assert ticket.priority == "medium"

    def test_gen2_ticket(self, tmp_tickets):

        path = make_gen2_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.id == "T-A"
        assert ticket.generation == 2
        # Summary → Problem rename
        assert "Problem" in ticket.sections

    def test_gen3_ticket(self, tmp_tickets):

        path = make_gen3_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.id == "T-003"
        assert ticket.generation == 3
        # Findings → Prior Investigation rename
        assert "Prior Investigation" in ticket.sections

    def test_gen4_ticket(self, tmp_tickets):

        path = make_gen4_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.id == "T-20260301-01"
        assert ticket.generation == 4
        # Status normalization: deferred → open
        assert ticket.status == "open"
        assert ticket.defer is not None
        assert ticket.defer["active"] is True
        # Provenance → source mapping
        assert ticket.source["type"] == "handoff"
        # Proposed Approach → Approach rename
        assert "Approach" in ticket.sections

    def test_nonexistent_file(self, tmp_tickets):
        path = tmp_tickets / "nonexistent.md"
        with pytest.warns(UserWarning, match="Cannot read"):
            assert parse_ticket(path) is None

    def test_no_yaml_block(self, tmp_tickets):
        path = tmp_tickets / "no-yaml.md"
        path.write_text("# Just a title\nNo yaml.", encoding="utf-8")
        with pytest.warns(UserWarning, match="No fenced YAML"):
            assert parse_ticket(path) is None

    def test_missing_required_fields(self, tmp_tickets):
        path = tmp_tickets / "bad.md"
        path.write_text("# Bad\n\n```yaml\npriority: high\n```\n", encoding="utf-8")
        with pytest.warns(UserWarning, match="missing required"):
            assert parse_ticket(path) is None

    def test_non_string_id_coerced(self, tmp_tickets):
        """YAML `id: 123` should parse without crashing."""
        path = tmp_tickets / "numeric-id.md"
        path.write_text(
            '# Test\n\n```yaml\nid: 123\ndate: "2026-03-02"\nstatus: open\n```\n',
            encoding="utf-8",
        )
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.id == "123"
        assert ticket.title == "Test"
        assert ticket.generation == 1  # Slug fallback

    def test_mutable_defaults_isolated(self, tmp_tickets):
        """Parsing two legacy tickets must not share mutable default state."""

        path1 = make_gen1_ticket(tmp_tickets, "gen1-a.md")
        path2 = make_gen1_ticket(tmp_tickets, "gen1-b.md")
        t1 = parse_ticket(path1)
        t2 = parse_ticket(path2)
        assert t1 is not None and t2 is not None
        # Mutating t1's defaults must not affect t2.
        assert t1.source is not t2.source
        assert t1.tags is not t2.tags
