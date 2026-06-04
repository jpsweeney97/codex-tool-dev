"""Tests for blocker resolution with target tickets."""

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
        """Open blocker in ticket_map is reported as unresolved."""
        ticket_map = {"T-20260301-01": FakeTicket("T-20260301-01", "open")}
        missing, unresolved = _classify_blockers(["T-20260301-01"], ticket_map)
        assert missing == []
        assert unresolved == ["T-20260301-01"]


class TestPreflightCloseWithBlocker:
    """Integration test: close action with target blocker references."""

    def test_preflight_close_with_done_blocker(self, tmp_tickets):
        """Terminal blocker in the target active directory is resolved."""
        make_ticket(
            tmp_tickets,
            "T-20260301-01.md",
            id="T-20260301-01",
            status="done",
            title="Blocker task",
        )

        make_ticket(
            tmp_tickets,
            "T-20260310-01.md",
            id="T-20260310-01",
            status="blocked",
            blocked_by=["T-20260301-01"],
            blocked_on="Waiting for terminal blocker confirmation.",
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
        assert resp.state != "dependency_blocked", (
            f"Terminal blocker should not cause dependency_blocked, "
            f"got state={resp.state!r}, message={resp.message!r}"
        )

    def test_nonterminal_blocker_is_unresolved(self, tmp_tickets):
        """Non-terminal blocker is unresolved, not missing."""
        make_ticket(
            tmp_tickets,
            "T-20260301-99.md",
            id="T-20260301-99",
            status="open",
            title="Not actually done",
        )

        make_ticket(
            tmp_tickets,
            "T-20260310-01.md",
            id="T-20260310-01",
            status="blocked",
            blocked_by=["T-20260301-99"],
            blocked_on="Waiting for non-terminal blocker.",
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
