"""Tests for blocker resolution with archived tickets (C-003)."""
from __future__ import annotations

from scripts.ticket_engine_core import _classify_blockers, engine_preflight
from tests.support.builders import make_ticket


class FakeTicket:
    """Minimal ticket stub for _classify_blockers unit tests."""

    def __init__(self, id: str, status: str):
        self.id = id
        self.status = status


class TestClassifyBlockers:
    """Unit tests for _classify_blockers — function is correct, these verify it."""

    def test_archived_done_blocker_is_resolved(self):
        """Done blocker in ticket_map is neither missing nor unresolved."""
        ticket_map = {"T-20260301-01": FakeTicket("T-20260301-01", "done")}
        missing, unresolved = _classify_blockers(["T-20260301-01"], ticket_map)
        assert missing == []
        assert unresolved == []

    def test_archived_wontfix_blocker_is_resolved(self):
        """Wontfix blocker in ticket_map is neither missing nor unresolved."""
        ticket_map = {"T-20260301-01": FakeTicket("T-20260301-01", "wontfix")}
        missing, unresolved = _classify_blockers(["T-20260301-01"], ticket_map)
        assert missing == []
        assert unresolved == []

    def test_truly_missing_blocker_still_detected(self):
        """ID not in ticket_map is reported as missing."""
        missing, unresolved = _classify_blockers(["T-NONEXISTENT-01"], {})
        assert missing == ["T-NONEXISTENT-01"]
        assert unresolved == []

    def test_unresolved_blocker_still_detected(self):
        """In-progress blocker in ticket_map is reported as unresolved."""
        ticket_map = {"T-20260301-01": FakeTicket("T-20260301-01", "in_progress")}
        missing, unresolved = _classify_blockers(["T-20260301-01"], ticket_map)
        assert missing == []
        assert unresolved == ["T-20260301-01"]


class TestPreflightCloseWithArchivedBlocker:
    """Integration test: close action with blocker in closed-tickets/."""

    def test_preflight_close_with_archived_blocker(self, tmp_tickets):
        """Blocker in closed-tickets/ (done) should not cause dependency_blocked.

        Before fix: list_tickets(tickets_dir) misses closed-tickets/ subdir,
        so the blocker appears "missing" and preflight returns dependency_blocked.
        After fix: _list_tickets_with_closed includes archived tickets.
        """
        # Create a done blocker in closed-tickets/ subdirectory.
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir(parents=True, exist_ok=True)
        make_ticket(
            closed_dir,
            "2026-03-01-blocker.md",
            id="T-20260301-01",
            status="done",
            title="Blocker task",
        )

        # Create a ticket blocked by the archived one.
        make_ticket(
            tmp_tickets,
            "2026-03-10-blocked.md",
            id="T-20260310-01",
            status="in_progress",
            blocked_by=["T-20260301-01"],
            title="Blocked task",
        )

        resp = engine_preflight(
            ticket_id="T-20260310-01",
            action="close",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="close",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
            hook_injected=True,
        )
        # After fix: blocker is found in closed-tickets/ and is terminal.
        assert resp.state != "dependency_blocked", (
            f"Archived done blocker should not cause dependency_blocked, "
            f"got state={resp.state!r}, message={resp.message!r}"
        )

    def test_closed_dir_nonterminal_blocker_is_unresolved(self, tmp_tickets):
        """Edge case: ticket in closed-tickets/ with non-terminal status is unresolved, not missing."""
        # A ticket physically in closed-tickets/ but with status=in_progress
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir(parents=True, exist_ok=True)
        make_ticket(
            closed_dir,
            "2026-03-01-nonterminal.md",
            id="T-20260301-99",
            status="in_progress",
            title="Not actually done",
        )

        # A ticket blocked by that non-terminal "closed" ticket
        make_ticket(
            tmp_tickets,
            "2026-03-10-blocked.md",
            id="T-20260310-01",
            status="blocked",
            blocked_by=["T-20260301-99"],
            title="Blocked task",
        )

        resp = engine_preflight(
            ticket_id="T-20260310-01",
            action="close",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="close",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
            hook_injected=True,
        )
        # Should be dependency_blocked (unresolved), NOT missing
        assert resp.state == "dependency_blocked"
        assert "T-20260301-99" in resp.message
        # Verify it's classified as unresolved, not missing
        assert resp.data["unresolved_blockers"] == ["T-20260301-99"]
        assert resp.data["missing_blockers"] == []
