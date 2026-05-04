"""Tests for the triage analysis script."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.support.builders import make_ticket


class TestDashboard:
    """Test triage_dashboard counts and alerts."""

    @pytest.fixture
    def populated_tickets(self, tmp_tickets):
        """Create a mix of tickets for dashboard testing."""
        make_ticket(tmp_tickets, "t1.md", id="T-20260302-01", status="open")
        make_ticket(tmp_tickets, "t2.md", id="T-20260302-02", status="in_progress")
        make_ticket(tmp_tickets, "t3.md", id="T-20260302-03", status="blocked",
                    blocked_by=["T-20260302-01"])
        make_ticket(tmp_tickets, "t4.md", id="T-20260302-04", status="done")
        return tmp_tickets

    def test_status_counts(self, populated_tickets):
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(populated_tickets)
        assert result["counts"]["open"] == 1
        assert result["counts"]["in_progress"] == 1
        assert result["counts"]["blocked"] == 1
        assert result["total"] == 3  # open + in_progress + blocked (done excluded)

    def test_empty_directory(self, tmp_tickets):
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert result["total"] == 0
        assert result["stale"] == []


class TestStaleDetection:
    """Test stale ticket detection."""

    def test_stale_ticket_detected(self, tmp_tickets):
        """Ticket older than 7 days in open status -> stale."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        make_ticket(tmp_tickets, "old.md", id="T-20260220-01", date=old_date, status="open")
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert len(result["stale"]) == 1
        assert result["stale"][0]["id"] == "T-20260220-01"
        assert result["stale"][0]["title"] == "Test ticket"

    def test_recent_ticket_not_stale(self, tmp_tickets):
        """Ticket from today -> not stale."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        make_ticket(tmp_tickets, "new.md", id="T-20260302-01", date=today, status="open")
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert result["stale"] == []

    def test_done_ticket_not_stale(self, tmp_tickets):
        """Done tickets are never stale (regardless of age)."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        make_ticket(tmp_tickets, "done.md", id="T-20260201-01", date=old_date, status="done")
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert result["stale"] == []


class TestBlockedChain:
    """Test blocked chain analysis."""

    def test_root_blocker_found(self, tmp_tickets):
        """Follow blocked_by chain to find root blocker."""
        make_ticket(tmp_tickets, "root.md", id="T-20260302-01", status="open")
        make_ticket(tmp_tickets, "mid.md", id="T-20260302-02", status="blocked",
                    blocked_by=["T-20260302-01"])
        make_ticket(tmp_tickets, "leaf.md", id="T-20260302-03", status="blocked",
                    blocked_by=["T-20260302-02"])
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        chains = {c["id"]: c for c in result["blocked_chains"]}
        assert "T-20260302-03" in chains
        assert "T-20260302-01" in chains["T-20260302-03"]["root_blockers"]
        assert chains["T-20260302-03"]["title"] == "Test ticket"

    def test_missing_blocker_is_root(self, tmp_tickets):
        """Blocker not found in ticket map -> treated as root."""
        make_ticket(tmp_tickets, "blocked.md", id="T-20260302-01", status="blocked",
                    blocked_by=["T-MISSING-01"])
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert result["blocked_chains"][0]["root_blockers"] == ["T-MISSING-01"]

    def test_circular_dependency_no_infinite_loop(self, tmp_tickets):
        """Circular blocked_by chain -> visited set prevents infinite loop."""
        make_ticket(tmp_tickets, "a.md", id="T-20260302-01", status="blocked",
                    blocked_by=["T-20260302-02"])
        make_ticket(tmp_tickets, "b.md", id="T-20260302-02", status="blocked",
                    blocked_by=["T-20260302-01"])
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        chains = {c["id"]: c for c in result["blocked_chains"]}
        assert len(chains) == 2


class TestDocSize:
    """Test document size warnings."""

    def test_large_doc_strong_warning(self, tmp_tickets):
        """Ticket >32KB -> strong_warn."""
        path = make_ticket(tmp_tickets, "big.md", id="T-20260302-01")
        with open(path, "a") as f:
            f.write("x" * 33000)
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert len(result["size_warnings"]) == 1
        assert "strong_warn" in result["size_warnings"][0]["warning"]
        assert result["size_warnings"][0]["title"] == "Test ticket"

    def test_medium_doc_warning(self, tmp_tickets):
        """Ticket >16KB but <32KB -> warn."""
        path = make_ticket(tmp_tickets, "med.md", id="T-20260302-01")
        with open(path, "a") as f:
            f.write("x" * 17000)
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert len(result["size_warnings"]) == 1
        assert "warn" in result["size_warnings"][0]["warning"]
        assert "strong" not in result["size_warnings"][0]["warning"]

    def test_normal_doc_no_warning(self, tmp_tickets):
        """Normal-sized ticket -> no warning."""
        make_ticket(tmp_tickets, "normal.md", id="T-20260302-01")
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert result["size_warnings"] == []


class TestAuditReport:
    """Test audit trail report generation."""

    @pytest.fixture
    def audit_env(self, tmp_tickets):
        """Create audit trail with sample entries."""
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / date_dir
        audit_dir.mkdir(parents=True)

        # Session 1: 2 creates, 1 update.
        s1_file = audit_dir / "session-1.jsonl"
        entries = [
            {"action": "create", "result": "ok_create", "session_id": "session-1"},
            {"action": "create", "result": "ok_create", "session_id": "session-1"},
            {"action": "update", "result": "ok_update", "session_id": "session-1"},
        ]
        s1_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        # Session 2: 1 blocked attempt.
        s2_file = audit_dir / "session-2.jsonl"
        s2_file.write_text(json.dumps(
            {"action": "create", "result": "policy_blocked", "session_id": "session-2"}
        ) + "\n")

        return tmp_tickets

    def test_total_entries_counted(self, audit_env):
        from scripts.ticket_triage import triage_audit_report
        result = triage_audit_report(audit_env)
        assert result["total_entries"] == 4

    def test_by_action_aggregation(self, audit_env):
        from scripts.ticket_triage import triage_audit_report
        result = triage_audit_report(audit_env)
        assert result["by_action"]["create"] == 3
        assert result["by_action"]["update"] == 1

    def test_by_result_aggregation(self, audit_env):
        from scripts.ticket_triage import triage_audit_report
        result = triage_audit_report(audit_env)
        assert result["by_result"]["ok_create"] == 2
        assert result["by_result"]["policy_blocked"] == 1

    def test_session_count(self, audit_env):
        from scripts.ticket_triage import triage_audit_report
        result = triage_audit_report(audit_env)
        assert result["sessions"] == 2

    def test_no_audit_dir_returns_empty(self, tmp_tickets):
        from scripts.ticket_triage import triage_audit_report
        result = triage_audit_report(tmp_tickets)
        assert result["total_entries"] == 0
        assert result["sessions"] == 0

    def test_boundary_day_included(self, tmp_tickets):
        """Audit directory exactly N days old is included, not excluded."""
        from scripts.ticket_triage import triage_audit_report

        # Create an audit entry exactly 7 days ago (at midnight).
        boundary_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / boundary_date
        audit_dir.mkdir(parents=True)
        s_file = audit_dir / "boundary-session.jsonl"
        s_file.write_text(
            json.dumps({"action": "create", "result": "ok_create", "session_id": "boundary-session"}) + "\n"
        )

        result = triage_audit_report(tmp_tickets, days=7)
        assert result["total_entries"] == 1, "Boundary day should be included in the lookback window"

    def test_skipped_lines_counted(self, tmp_tickets):
        """Corrupt JSONL lines are counted in skipped_lines."""
        from scripts.ticket_triage import triage_audit_report
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / date_dir
        audit_dir.mkdir(parents=True)
        s_file = audit_dir / "corrupt-session.jsonl"
        s_file.write_text(
            json.dumps({"action": "create", "result": "ok_create"}) + "\n"
            + "NOT VALID JSON\n"
            + json.dumps({"action": "update", "result": "ok_update"}) + "\n"
        )
        result = triage_audit_report(tmp_tickets)
        assert result["total_entries"] == 2
        assert result["skipped_lines"] == 1

    def test_read_errors_counted(self, tmp_tickets):
        """Unreadable audit files are counted in read_errors."""
        import os
        import sys
        if sys.platform == "win32":
            pytest.skip("chmod not effective on Windows")
        from scripts.ticket_triage import triage_audit_report
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / date_dir
        audit_dir.mkdir(parents=True)
        s_file = audit_dir / "unreadable-session.jsonl"
        s_file.write_text(json.dumps({"action": "create"}) + "\n")
        try:
            os.chmod(s_file, 0o000)
            result = triage_audit_report(tmp_tickets)
            assert result["read_errors"] == 1
        finally:
            os.chmod(s_file, 0o644)


class TestStaleEdgeCases:
    """Test _is_stale edge case behavior."""

    def test_corrupt_date_is_stale(self, tmp_tickets):
        """Tickets with unparseable dates are marked stale (fail toward visibility)."""
        make_ticket(tmp_tickets, "bad-date.md", date="not-a-date", status="open")
        from scripts.ticket_triage import triage_dashboard
        result = triage_dashboard(tmp_tickets)
        assert len(result["stale"]) == 1

    def test_unreadable_file_shows_size_warning(self, tmp_tickets):
        """Missing/unreadable ticket files get a size warning."""
        make_ticket(tmp_tickets, "test.md", status="open")
        # Corrupt the path so stat fails.
        from scripts.ticket_triage import _check_doc_size
        from types import SimpleNamespace
        fake_ticket = SimpleNamespace(path="/nonexistent/path.md")
        assert _check_doc_size(fake_ticket) == "error: file unreadable"


class TestOrphanDetection:
    """Test handoff orphan detection with three matching strategies."""

    @pytest.fixture
    def orphan_env(self, tmp_path):
        """Set up tickets and handoffs directories."""
        tickets_dir = tmp_path / "docs" / "tickets"
        tickets_dir.mkdir(parents=True)
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        return tickets_dir, handoffs_dir

    def test_uid_match_by_session(self, orphan_env):
        """Handoff matching ticket's source.session -> uid_match."""
        tickets_dir, handoffs_dir = orphan_env
        make_ticket(tickets_dir, "t1.md", id="T-20260302-01", session="session-abc")
        (handoffs_dir / "handoff-1.md").write_text(
            "# Handoff\nSession session-abc produced this work.\n"
        )
        from scripts.ticket_triage import triage_orphan_detection
        result = triage_orphan_detection(tickets_dir, handoffs_dir)
        assert len(result["matched"]) == 1
        assert result["matched"][0]["match_type"] == "uid_match"
        assert result["matched"][0]["matched_ticket"] == "T-20260302-01"

    def test_id_ref_match(self, orphan_env):
        """Handoff mentioning ticket ID -> id_ref match."""
        tickets_dir, handoffs_dir = orphan_env
        make_ticket(tickets_dir, "t1.md", id="T-20260302-01")
        (handoffs_dir / "handoff-1.md").write_text(
            "# Handoff\nRelated to T-20260302-01.\n"
        )
        from scripts.ticket_triage import triage_orphan_detection
        result = triage_orphan_detection(tickets_dir, handoffs_dir)
        assert len(result["matched"]) == 1
        assert result["matched"][0]["match_type"] == "id_ref"

    def test_manual_review_fallback(self, orphan_env):
        """Handoff with no matching ticket -> manual_review."""
        tickets_dir, handoffs_dir = orphan_env
        (handoffs_dir / "handoff-1.md").write_text(
            "# Handoff\nSome unrelated work.\n"
        )
        from scripts.ticket_triage import triage_orphan_detection
        result = triage_orphan_detection(tickets_dir, handoffs_dir)
        assert len(result["orphaned"]) == 1
        assert result["orphaned"][0]["match_type"] == "manual_review"

    def test_no_handoffs_dir(self, tmp_tickets):
        """Missing handoffs directory -> empty results."""
        from scripts.ticket_triage import triage_orphan_detection
        result = triage_orphan_detection(tmp_tickets, Path("/nonexistent"))
        assert result["total_items"] == 0

    def test_uid_match_takes_priority_over_id_ref(self, orphan_env):
        """uid_match is checked before id_ref -- first match wins."""
        tickets_dir, handoffs_dir = orphan_env
        make_ticket(tickets_dir, "t1.md", id="T-20260302-01", session="session-xyz")
        (handoffs_dir / "handoff-1.md").write_text(
            "# Handoff\nSession session-xyz about T-20260302-01.\n"
        )
        from scripts.ticket_triage import triage_orphan_detection
        result = triage_orphan_detection(tickets_dir, handoffs_dir)
        assert len(result["matched"]) == 1
        assert result["matched"][0]["match_type"] == "uid_match"


TRIAGE_SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_triage.py"


class TestTriageCLI:
    def test_dashboard_subcommand_returns_json(self, tmp_tickets):
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT), "dashboard", str(tmp_tickets)],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert "counts" in data["data"]

    def test_audit_subcommand_returns_json(self, tmp_tickets):
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT), "audit", str(tmp_tickets)],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert "total_entries" in data["data"]

    def test_audit_with_days_arg(self, tmp_tickets):
        project_root = tmp_tickets.parent.parent
        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT), "audit", str(tmp_tickets), "--days", "30"],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"

    def test_unknown_subcommand_exits_2(self, tmp_tickets):
        """argparse exits 2 for invalid subcommand choice, not 1."""
        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT), "bogus", str(tmp_tickets)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2

    def test_missing_args_exits_1(self):
        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 1

    def test_dashboard_rejects_path_outside_project_root(self, tmp_path):
        (tmp_path / ".git").mkdir(exist_ok=True)
        outside = tmp_path.parent / "outside-tickets"
        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT), "dashboard", str(outside)],
            capture_output=True, text=True, timeout=10, cwd=str(tmp_path),
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["state"] == "policy_blocked"
