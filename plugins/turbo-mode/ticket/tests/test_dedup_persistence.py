"""Tests for dedup persistence (C-002) and dedup_override binding (C-008)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scripts.ticket_engine_core import _execute_create, engine_preflight
from scripts.ticket_parse import parse_ticket
from tests.support.builders import make_ticket


class TestKeyFilePathsPersistence:
    """C-002: key_file_paths persisted in YAML frontmatter on create."""

    def test_created_ticket_persists_key_file_paths(self, tmp_tickets):
        """key_file_paths should appear in YAML frontmatter, sorted."""
        resp = _execute_create(
            fields={
                "title": "Fix auth timeout",
                "problem": "Auth handler times out",
                "key_file_paths": ["handler.py", "auth/config.py"],
                "key_files": [
                    {"file": "handler.py", "role": "Timeout logic", "look_for": "timeout"},
                    {"file": "auth/config.py", "role": "Config", "look_for": "timeout_ms"},
                ],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok_create"

        ticket = parse_ticket(Path(resp.data["ticket_path"]))
        assert ticket is not None
        assert ticket.frontmatter.get("key_file_paths") == ["auth/config.py", "handler.py"]

    def test_created_ticket_without_key_file_paths_has_no_field(self, tmp_tickets):
        """No key_file_paths in fields => no key_file_paths in YAML."""
        resp = _execute_create(
            fields={
                "title": "Simple fix",
                "problem": "Something is broken",
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok_create"

        ticket = parse_ticket(Path(resp.data["ticket_path"]))
        assert ticket is not None
        assert "key_file_paths" not in ticket.frontmatter

    def test_created_ticket_empty_key_file_paths_not_persisted(self, tmp_tickets):
        """Empty key_file_paths list should not be persisted."""
        resp = _execute_create(
            fields={
                "title": "Simple fix",
                "problem": "Something is broken",
                "key_file_paths": [],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok_create"

        ticket = parse_ticket(Path(resp.data["ticket_path"]))
        assert ticket is not None
        assert "key_file_paths" not in ticket.frontmatter


class TestDedupPrefersPersistedField:
    """C-002: dedup scan reads persisted key_file_paths over regex extraction."""

    def test_dedup_reads_persisted_key_file_paths(self, tmp_tickets):
        """Dedup scan uses persisted key_file_paths from YAML, not regex."""
        from scripts.ticket_engine_core import engine_plan

        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")
        today_compact = today_str.replace("-", "")
        created_at = today.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Create a ticket with key_file_paths persisted in YAML.
        make_ticket(
            tmp_tickets,
            f"{today_str}-auth.md",
            id=f"T-{today_compact}-01",
            date=today_str,
            created_at=created_at,
            problem="Auth times out.",
            title="Fix auth bug",
            extra_yaml='key_file_paths: [handler.py, auth/config.py]\n        ',
        )

        # Try to create a duplicate with matching key_file_paths.
        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug again",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": ["auth/config.py", "handler.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "duplicate_candidate"

    def test_dedup_falls_back_to_regex_without_persisted_field(self, tmp_tickets):
        """Pre-existing tickets without key_file_paths YAML still work via regex."""
        from scripts.ticket_engine_core import engine_plan

        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")
        today_compact = today_str.replace("-", "")
        created_at = today.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Ticket WITHOUT key_file_paths in YAML — has Key Files markdown table.
        make_ticket(
            tmp_tickets,
            f"{today_str}-auth.md",
            id=f"T-{today_compact}-01",
            date=today_str,
            created_at=created_at,
            problem="Auth times out.",
            title="Fix auth bug",
            # Default make_ticket has Key Files table with "test.py".
        )

        resp = engine_plan(
            intent="create",
            fields={
                "title": "Fix auth bug again",
                "problem": "Auth times out.",
                "priority": "high",
                "key_file_paths": ["test.py"],
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        # Regex fallback extracts "test.py" from Key Files table.
        assert resp.state == "duplicate_candidate"


class TestDedupOverrideBinding:
    """C-008: dedup_override requires duplicate_of identifying the candidate."""

    def test_dedup_override_without_duplicate_of_rejected(self, tmp_tickets):
        """dedup_override=True without duplicate_of -> need_fields."""
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            dedup_override=True,
            # No duplicate_of
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "need_fields"
        assert "duplicate_of" in str(resp.data.get("missing_fields", []))

    def test_dedup_override_with_duplicate_of_passes(self, tmp_tickets):
        """dedup_override=True with duplicate_of -> passes dedup check."""
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            dedup_override=True,
            duplicate_of="T-20260302-01",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert "dedup" in resp.data["checks_passed"]

    def test_execute_dedup_override_requires_duplicate_of(self, tmp_tickets):
        """C-008 defense-in-depth: execute-stage binding check works independently."""
        from scripts.ticket_engine_core import engine_execute

        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Test ticket",
                "problem": "Test problem",
            },
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.9,
            dedup_fingerprint="646884cf25d6e17cda6f80764f9ad25ef35cb7b75e5adbed249b8b5a874a583b",
            dedup_override=True,
            dependency_override=False,
            duplicate_of=None,  # Missing — should be rejected
        )
        assert resp.state == "need_fields"
        assert "duplicate_of" in str(resp.data.get("missing_fields", []))

    def test_dedup_override_false_without_duplicate_of_passes(self, tmp_tickets):
        """No override + no duplicate -> normal flow, no binding check."""
        resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc123",
            target_fingerprint=None,
            dedup_override=False,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
