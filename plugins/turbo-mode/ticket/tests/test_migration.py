"""Diagnostic legacy migration tests."""

from __future__ import annotations

import textwrap

from scripts.ticket_cutover_inventory import inspect_legacy_ticket_for_cutover
from scripts.ticket_parse import parse_legacy_ticket_for_cutover, parse_ticket

from tests.support.builders import (
    make_gen1_ticket,
    make_gen2_ticket,
    make_gen3_ticket,
    make_gen4_ticket,
    make_ticket,
)


class TestLegacyDiagnosticParser:
    def test_golden_gen1(self, tmp_tickets) -> None:
        path = make_gen1_ticket(tmp_tickets)
        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.generation == 1
        assert ticket.id == "handoff-chain-viz"
        assert ticket.priority == "medium"
        assert ticket.source == {"type": "legacy", "ref": "", "session": ""}
        assert ticket.frontmatter.get("plugin") == "handoff"
        assert ticket.frontmatter.get("related") == ["handoff-search", "handoff-quality-hook"]
        assert "Problem" in ticket.sections
        assert "Summary" not in ticket.sections

    def test_golden_gen2(self, tmp_tickets) -> None:
        path = make_gen2_ticket(tmp_tickets)
        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.generation == 2
        assert ticket.id == "T-A"
        assert ticket.priority == "high"
        assert ticket.blocks == ["T-B"]
        assert ticket.frontmatter.get("branch") == "feature/analytics-refactor"
        assert "Problem" in ticket.sections
        assert "Rationale" in ticket.sections
        assert "Design" in ticket.sections
        assert "Context" in ticket.sections
        assert "Risks" not in ticket.sections

    def test_golden_gen3(self, tmp_tickets) -> None:
        path = make_gen3_ticket(tmp_tickets)
        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.generation == 3
        assert ticket.id == "T-003"
        assert ticket.status == "in_progress"
        assert ticket.frontmatter.get("branch") == "fix/session-counting"
        assert "Problem" in ticket.sections
        assert "Prior Investigation" in ticket.sections
        assert "Summary" not in ticket.sections
        assert "Findings" not in ticket.sections
        assert "Verification" in ticket.sections

    def test_golden_gen4(self, tmp_tickets) -> None:
        path = make_gen4_ticket(tmp_tickets)
        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.generation == 4
        assert ticket.id == "T-20260301-01"
        assert ticket.status == "open"
        assert ticket.defer is not None
        assert ticket.source["type"] == "handoff"
        assert ticket.source["session"] == "xyz-123"
        assert ticket.source["ref"] == "session-xyz"
        assert "Approach" in ticket.sections
        assert "Proposed Approach" not in ticket.sections
        assert "Source" in ticket.sections
        assert "Acceptance Criteria" in ticket.sections

    def test_gen4_default_source_type(self, tmp_tickets) -> None:
        content = textwrap.dedent(
            """\
            # T-20260301-02: Missing source_type

            ```yaml
            id: T-20260301-02
            date: "2026-03-01"
            status: deferred
            priority: medium
            provenance:
              created_by: defer.py
              session_id: abc-456
            tags: []
            blocked_by: []
            blocks: []
            ```

            ## Problem
            Test for default source_type path.
            """
        )
        path = tmp_tickets / "2026-03-01-no-source-type.md"
        path.write_text(content, encoding="utf-8")
        ticket = parse_legacy_ticket_for_cutover(path)

        assert ticket is not None
        assert ticket.generation == 4
        assert ticket.source["type"] == "defer"


class TestNormalParserBoundary:
    def test_normal_parser_rejects_legacy_ticket(self, tmp_tickets) -> None:
        path = make_gen1_ticket(tmp_tickets)

        assert parse_ticket(path) is None

    def test_normal_parser_accepts_target_ticket(self, tmp_tickets) -> None:
        path = make_ticket(tmp_tickets, "ignored.md", id="T-20260310-01")

        ticket = parse_ticket(path)

        assert ticket is not None
        assert ticket.generation == 10


class TestCutoverInventoryBoundary:
    def test_legacy_gen1_can_be_inventoried(self, tmp_tickets) -> None:
        path = make_gen1_ticket(tmp_tickets)

        inventory = inspect_legacy_ticket_for_cutover(path)

        assert inventory.current_id == "handoff-chain-viz"
        assert inventory.metadata_container == "fenced_yaml"
        assert inventory.proposed_target_path.name == "T-20260115-01.md"

    def test_legacy_gen4_can_be_inventoried(self, tmp_tickets) -> None:
        path = make_gen4_ticket(tmp_tickets)

        inventory = inspect_legacy_ticket_for_cutover(path)

        assert inventory.current_id == "T-20260301-01"
        assert inventory.proposed_target_path.name == "T-20260301-01.md"
        assert inventory.status_mapping_needed == "deferred->open"
        assert inventory.priority_mapping_needed == "medium->normal"
