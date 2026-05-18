"""Migration golden tests — one per legacy generation.

Each test creates a legacy ticket, parses it, and verifies field mapping,
section renames, and status normalization against expected output.
"""
from __future__ import annotations

import textwrap


from scripts.ticket_parse import parse_ticket
from tests.support.builders import make_gen1_ticket, make_gen2_ticket, make_gen3_ticket, make_gen4_ticket, make_ticket


class TestGen1Migration:
    def test_golden_gen1(self, tmp_tickets):

        path = make_gen1_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.generation == 1
        assert ticket.id == "handoff-chain-viz"
        # Field defaults applied for all missing fields.
        assert ticket.priority == "medium"
        assert ticket.source == {"type": "legacy", "ref": "", "session": ""}
        assert ticket.effort == ""
        assert ticket.tags == []
        assert ticket.blocked_by == []
        assert ticket.blocks == []
        # Gen 1 has `plugin` and `related` fields — preserved in frontmatter.
        assert ticket.frontmatter.get("plugin") == "handoff"
        assert ticket.frontmatter.get("related") == ["handoff-search", "handoff-quality-hook"]
        # Section rename: Summary → Problem.
        assert "Problem" in ticket.sections
        assert "Summary" not in ticket.sections


class TestGen2Migration:
    def test_golden_gen2(self, tmp_tickets):

        path = make_gen2_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.generation == 2
        assert ticket.id == "T-A"
        # Existing fields preserved.
        assert ticket.priority == "high"
        assert ticket.blocked_by == []
        assert ticket.blocks == ["T-B"]
        # Gen 2 has free-text effort and branch — preserved in frontmatter.
        assert ticket.frontmatter.get("effort") == "S (1-2 sessions)"
        assert ticket.frontmatter.get("branch") == "feature/analytics-refactor"
        # Section rename: Summary → Problem.
        assert "Problem" in ticket.sections
        # Preserved sections (non-standard names kept).
        assert "Rationale" in ticket.sections
        assert "Design" in ticket.sections
        # Risks → Context rename.
        assert "Context" in ticket.sections
        assert "Risks" not in ticket.sections


class TestGen3Migration:
    def test_golden_gen3(self, tmp_tickets):

        path = make_gen3_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.generation == 3
        assert ticket.id == "T-003"
        assert ticket.status == "in_progress"
        # Gen 3 has branch field — preserved in frontmatter.
        assert ticket.frontmatter.get("branch") == "fix/session-counting"
        # Section renames: Summary → Problem, Findings → Prior Investigation.
        assert "Problem" in ticket.sections
        assert "Prior Investigation" in ticket.sections
        assert "Summary" not in ticket.sections
        assert "Findings" not in ticket.sections
        # Preserved sections.
        assert "Prerequisites" in ticket.sections
        assert "References" in ticket.sections
        assert "Verification" in ticket.sections


class TestGen4Migration:
    def test_golden_gen4(self, tmp_tickets):

        path = make_gen4_ticket(tmp_tickets)
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.generation == 4
        assert ticket.id == "T-20260301-01"
        # Status normalization: deferred → open.
        assert ticket.status == "open"
        assert ticket.defer is not None
        assert ticket.defer["active"] is True
        # Field mapping: provenance → source.
        assert ticket.source["type"] == "handoff"
        assert ticket.source["session"] == "xyz-123"
        # source_ref mapped to source.ref (plan fix: verify actual value, not just existence).
        assert ticket.source["ref"] == "session-xyz"
        # Section rename: Proposed Approach → Approach.
        assert "Approach" in ticket.sections
        assert "Proposed Approach" not in ticket.sections
        # Source section preserved (unrecognized → kept).
        assert "Source" in ticket.sections
        # Acceptance Criteria section preserved.
        assert "Acceptance Criteria" in ticket.sections

    def test_gen4_default_source_type(self, tmp_tickets):
        """Gen 4 ticket without source_type gets default source.type='defer'."""
        content = textwrap.dedent("""\
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
        """)
        path = tmp_tickets / "2026-03-01-no-source-type.md"
        path.write_text(content, encoding="utf-8")
        ticket = parse_ticket(path)
        assert ticket is not None
        assert ticket.generation == 4
        # Default source_type is "defer" per design doc.
        assert ticket.source["type"] == "defer"


class TestLegacyWriteGate:
    """C-001: legacy tickets (generation < 10) are read-only."""

    def test_update_rejects_legacy_gen1_ticket(self, tmp_tickets):
        """Update on a Gen 1 ticket should be policy_blocked."""
        from scripts.ticket_engine_core import _execute_update

        make_gen1_ticket(tmp_tickets)
        resp = _execute_update(
            ticket_id="handoff-chain-viz",
            fields={"priority": "high"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "policy_blocked"
        assert "legacy" in resp.message.lower() or "generation" in resp.message.lower()

    def test_close_rejects_legacy_gen3_ticket(self, tmp_tickets):
        """Close on a Gen 3 ticket should be policy_blocked."""
        from scripts.ticket_engine_core import _execute_close

        make_gen3_ticket(tmp_tickets)
        resp = _execute_close(
            ticket_id="T-003",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "policy_blocked"

    def test_reopen_rejects_legacy_gen4_ticket(self, tmp_tickets):
        """C-001 edge case: reopen on a Gen 4 ticket should be policy_blocked."""
        from scripts.ticket_engine_core import _execute_reopen

        make_gen4_ticket(tmp_tickets)
        resp = _execute_reopen(
            ticket_id="T-20260301-01",
            fields={"reopen_reason": "needs more work"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "policy_blocked"

    def test_update_allows_v10_ticket(self, tmp_tickets):
        """Regression: v1.0 tickets (generation=10) should be updatable."""
        from scripts.ticket_engine_core import _execute_update

        make_ticket(tmp_tickets, "2026-03-10-normal.md",
                    id="T-20260310-01", title="Normal ticket")
        resp = _execute_update(
            ticket_id="T-20260310-01",
            fields={"priority": "high"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state != "policy_blocked"
