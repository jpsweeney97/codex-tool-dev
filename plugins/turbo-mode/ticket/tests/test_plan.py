"""Tests for engine_plan stage."""

from __future__ import annotations

from datetime import UTC

from scripts.ticket_engine_core import engine_plan

from tests.support.builders import make_legacy_ticket_for_cutover, make_ticket


class TestEnginePlan:
    def test_create_with_all_fields(self, tmp_tickets):
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": ["handler.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert "dedup_fingerprint" in resp.data
        assert resp.data["missing_fields"] == []

    def test_create_missing_required_fields(self, tmp_tickets):
        resp = engine_plan(
            intent="create",
            fields={"title": "No problem section"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "need_fields"
        assert "problem" in resp.data["missing_fields"]

    def test_create_invalid_related_paths_rejected(self, tmp_tickets):
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": "handler.py",
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "need_fields"
        assert resp.error_code == "need_fields"
        assert "related_paths" in resp.message

    def test_dedup_detection(self, tmp_tickets):
        from datetime import datetime

        today = datetime.now(UTC).date()
        today_str = today.isoformat()
        today_compact = today_str.replace("-", "")
        make_ticket(
            tmp_tickets,
            f"{today_str}-auth.md",
            id=f"T-{today_compact}-01",
            date=today_str,
            problem="Auth times out.",
            title="Fix auth bug",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate"
        assert resp.data["duplicate_of"] is not None

    def test_no_dedup_outside_24h(self, tmp_tickets):
        make_ticket(
            tmp_tickets,
            "2026-02-28-old.md",
            id="T-20260228-01",
            date="2026-02-28",
            problem="Auth times out.",
            title="Old auth bug",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # Old ticket outside 24h window — no dedup match.
        assert resp.state == "ok"

    def test_dedup_uses_target_id_date(self, tmp_tickets):
        """Dedup uses the target ID date derived from T-YYYYMMDD-NN."""
        from datetime import datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        today_compact = today.replace("-", "")
        make_ticket(
            tmp_tickets,
            f"T-{today_compact}-01.md",
            id=f"T-{today_compact}-01",
            problem="Auth times out.",
            title="Target ID date ticket",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate"

    def test_dedup_skips_old_target_id_date(self, tmp_tickets):
        """Tickets with old target ID dates are excluded from dedup."""
        make_ticket(
            tmp_tickets,
            "T-20260307-01.md",
            id="T-20260307-01",
            problem="Auth times out.",
            title="Stale ticket",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"

    def test_dedup_target_id_date_uses_end_of_day_window(self, tmp_tickets):
        """A ticket ID dated today is always inside the 24h dedup window."""
        from datetime import datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        today_compact = today.replace("-", "")
        make_ticket(
            tmp_tickets,
            f"T-{today_compact}-02.md",
            id=f"T-{today_compact}-02",
            problem="Auth times out.",
            title="Target ticket",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate"

    def test_dedup_ignores_mtime_after_git_clone(self, tmp_tickets):
        """File mtime does NOT affect dedup — git clone safety (P0-3 review).

        After git clone, all files get current mtime. Old tickets must NOT
        be treated as recent just because mtime is now.
        """
        import os
        import time

        # Old ticket with old date, no created_at.
        old_date = "2026-01-15"
        path = make_ticket(
            tmp_tickets,
            f"{old_date}-cloned.md",
            id="T-20260115-01",
            date=old_date,
            problem="Auth times out.",
            title="Old cloned ticket",
        )
        # Simulate git clone: set mtime to NOW.
        now = time.time()
        os.utime(path, (now, now))
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # mtime is ignored — old date puts ticket outside window.
        assert resp.state == "ok"

    def test_non_create_skips_dedup(self, tmp_tickets):
        resp = engine_plan(
            intent="update",
            fields={"ticket_id": "T-20260302-01"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        # No dedup for non-create.
        assert resp.data.get("dedup_fingerprint") is None

    def test_non_create_invalid_active_ticket_returns_invalid_state(self, tmp_tickets):
        make_legacy_ticket_for_cutover(tmp_tickets, "legacy-active.md")

        resp = engine_plan(
            intent="update",
            fields={"ticket_id": "T-20260302-01"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )

        assert resp.state == "invalid_state"
        assert resp.error_code == "invalid_state"
        assert resp.data["reason"]

    def test_plan_create_dedup_includes_terminal_tickets(self, tmp_tickets):
        """Dedup scan includes terminal target tickets in docs/tickets/."""
        from datetime import datetime

        today = datetime.now(UTC)
        today_str = today.strftime("%Y-%m-%d")
        today_compact = today_str.replace("-", "")
        make_ticket(
            tmp_tickets,
            f"T-{today_compact}-03.md",
            id=f"T-{today_compact}-01",
            status="done",
            problem="Auth times out.",
            title="Fix auth bug",
        )

        # Plan create with same problem text should detect duplicate.
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "related_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate", (
            f"Terminal ticket with same problem should be detected as duplicate, "
            f"got state={resp.state!r}"
        )
