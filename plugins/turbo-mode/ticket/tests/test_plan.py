"""Tests for engine_plan stage."""
from __future__ import annotations

from scripts.ticket_engine_core import engine_plan
from tests.support.builders import make_ticket


class TestEnginePlan:
    def test_create_with_all_fields(self, tmp_tickets):
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": ["handler.py"],
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

    def test_create_invalid_key_file_paths_rejected(self, tmp_tickets):
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": "handler.py",
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "need_fields"
        assert resp.error_code == "need_fields"
        assert "key_file_paths" in resp.message

    def test_dedup_detection(self, tmp_tickets):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).date()
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
                "key_file_paths": ["test.py"],  # Must match conftest's Key Files table
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
                "key_file_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # Old ticket outside 24h window — no dedup match.
        assert resp.state == "ok"

    def test_dedup_uses_created_at_over_date(self, tmp_tickets):
        """Dedup uses created_at for precise window check (P0-3).

        A ticket with a recent created_at but old date should still be
        within the 24h dedup window. created_at has second-level precision
        and is immune to git checkout/clone mtime resets.
        """
        from datetime import datetime, timedelta, timezone

        # created_at = 1 hour ago (within 24h window).
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        created_at = recent.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Date is 2 days ago — would be outside window with date-only logic.
        old_date = "2026-02-28"
        make_ticket(
            tmp_tickets,
            f"{old_date}-midnight.md",
            id="T-20260228-01",
            date=old_date,
            created_at=created_at,
            problem="Auth times out.",
            title="Midnight edge case",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": ["test.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # created_at puts it within window — duplicate detected.
        assert resp.state == "duplicate_candidate"

    def test_dedup_skips_old_created_at(self, tmp_tickets):
        """Tickets with old created_at are excluded even with recent date."""
        from datetime import datetime, timedelta, timezone

        # created_at = 3 days ago (outside 24h window).
        old = datetime.now(timezone.utc) - timedelta(days=3)
        created_at = old.strftime("%Y-%m-%dT%H:%M:%SZ")
        make_ticket(
            tmp_tickets,
            "2026-03-07-stale.md",
            id="T-20260307-01",
            date="2026-03-07",
            created_at=created_at,
            problem="Auth times out.",
            title="Stale ticket",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": ["test.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # Old created_at puts ticket outside window — no dedup match.
        assert resp.state == "ok"

    def test_dedup_end_of_day_fallback_catches_near_midnight(self, tmp_tickets):
        """Legacy tickets without created_at use end-of-day fallback.

        A ticket dated today (without created_at) should always be in the
        24h window because its date is treated as 23:59:59 UTC.
        """
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        make_ticket(
            tmp_tickets,
            f"{today}-legacy.md",
            id="T-20260307-01",
            date=today,
            # No created_at — exercises fallback path.
            problem="Auth times out.",
            title="Legacy ticket",
        )
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": ["test.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # End-of-day fallback puts today's ticket within window.
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
                "key_file_paths": ["test.py"],
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

    def test_plan_create_dedup_includes_archived_tickets(self, tmp_tickets):
        """Dedup scan must include closed-tickets/ to detect archived duplicates.

        Before fix: list_tickets(tickets_dir) misses closed-tickets/ subdir,
        so an archived ticket with identical problem text is not detected.
        After fix: _list_tickets_with_closed scans closed-tickets/ too.
        """
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")
        today_compact = today_str.replace("-", "")
        created_at = today.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Create an archived ticket in closed-tickets/ with known problem text.
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir(parents=True, exist_ok=True)
        make_ticket(
            closed_dir,
            f"{today_str}-archived.md",
            id=f"T-{today_compact}-01",
            date=today_str,
            created_at=created_at,
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
                "key_file_paths": ["test.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate", (
            f"Archived ticket with same problem should be detected as duplicate, "
            f"got state={resp.state!r}"
        )
