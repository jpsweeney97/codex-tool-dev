"""Tests for engine_preflight stage."""
from __future__ import annotations

from scripts.ticket_engine_core import engine_preflight
from tests.support.builders import make_ticket


class TestEnginePreflight:
    def test_user_create_passes(self, tmp_tickets):
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert len(resp.data["checks_passed"]) > 0

    def test_unknown_origin_rejected(self, tmp_tickets):
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="unknown",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "escalate"

    def test_low_confidence_rejected(self, tmp_tickets):
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.1,
            classify_intent="create",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "preflight_failed"
        assert "confidence" in resp.message.lower()

    def test_exact_user_confidence_threshold_passes(self, tmp_tickets):
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.5,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert "confidence" in resp.data["checks_passed"]

    def test_agent_preflight_without_hook_injected_succeeds(self, tmp_tickets):
        """C-006: preflight must not block agents solely because hook_injected=False.

        In suggest mode agents are always policy_blocked (autonomy, not hook gate),
        but the block reason must not mention hook_injected.
        """
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="agent",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
            hook_injected=False,
        )
        # Blocked by suggest-mode autonomy policy — NOT by missing hook_injected
        assert resp.state == "policy_blocked"
        assert "hook_injected" not in resp.message.lower()

    def test_agent_reopen_user_only(self, tmp_tickets):
        """Agent reopen → policy_blocked (user-only in v1.0)."""
        resp = engine_preflight(
            ticket_id="T-20260302-01",
            action="reopen",
            session_id="test-session",
            request_origin="agent",
            classify_confidence=0.95,
            classify_intent="reopen",
            dedup_fingerprint=None,
            target_fingerprint=None,
            hook_injected=True,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "policy_blocked"

    def test_non_create_without_ticket_id_rejected(self, tmp_tickets):
        """Non-create actions require ticket_id."""
        resp = engine_preflight(
            ticket_id=None,
            action="update",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="update",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "need_fields"

    def test_intent_mismatch_escalates(self, tmp_tickets):
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="update",  # Mismatch!
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "escalate"
        assert "mismatch" in resp.message.lower()

    def test_stale_target_fingerprint(self, tmp_tickets):
        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01")
        resp = engine_preflight(
            ticket_id="T-20260302-01",
            action="update",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="update",
            dedup_fingerprint=None,
            target_fingerprint="stale-fingerprint",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "preflight_failed"
        assert "stale" in resp.message.lower() or "fingerprint" in resp.message.lower()

    def test_update_ticket_not_found(self, tmp_tickets):
        resp = engine_preflight(
            ticket_id="T-99999999-99",
            action="update",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="update",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "not_found"

    def test_close_with_open_blockers(self, tmp_tickets):
        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            blocked_by=["T-20260302-01"],
        )
        resp = engine_preflight(
            ticket_id="T-20260302-02",
            action="close",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="close",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "dependency_blocked"

    def test_close_wontfix_with_open_blockers_allowed(self, tmp_tickets):
        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            blocked_by=["T-20260302-01"],
        )
        resp = engine_preflight(
            ticket_id="T-20260302-02",
            action="close",
            fields={"resolution": "wontfix"},
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="close",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert "dependencies_not_required_for_wontfix" in resp.data["checks_passed"]

    def test_close_with_open_blockers_override(self, tmp_tickets):
        """dependency_override=True allows closing with open blockers."""
        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            blocked_by=["T-20260302-01"],
        )
        resp = engine_preflight(
            ticket_id="T-20260302-02",
            action="close",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="close",
            dedup_fingerprint=None,
            target_fingerprint=None,
            dependency_override=True,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert "dependencies_overridden" in resp.data["checks_passed"]

    def test_preflight_close_reports_missing_blockers(self, tmp_tickets):
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            blocked_by=["T-MISSING-01"],
        )
        resp = engine_preflight(
            ticket_id="T-20260302-02",
            action="close",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="close",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "dependency_blocked"
        assert resp.data["missing_blockers"] == ["T-MISSING-01"]
        assert resp.data["unresolved_blockers"] == []

    def test_dedup_blocks_without_override(self, tmp_tickets):
        """Preflight blocks create when duplicate detected and no override."""
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            duplicate_of="T-20260302-01",
            dedup_override=False,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate"
        assert resp.error_code == "duplicate_candidate"

    def test_dedup_passes_with_override(self, tmp_tickets):
        """Preflight allows create when duplicate detected but override=True."""
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            duplicate_of="T-20260302-01",
            dedup_override=True,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert "dedup" in resp.data["checks_passed"]

    def test_confidence_gate_no_policy_blocked_code(self, tmp_tickets):
        """Confidence gate returns error_code=preflight_failed, not policy_blocked."""
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.1,
            classify_intent="create",
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "preflight_failed"
        assert resp.error_code == "preflight_failed"
