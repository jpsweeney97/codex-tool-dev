"""Tests for engine_execute stage — dispatch, create, update, close, reopen, trust, validation."""
from __future__ import annotations

from pathlib import Path

import pytest

import scripts.ticket_engine_core as ticket_engine_core
from scripts.ticket_engine_core import (
    AutonomyConfig,
    engine_execute,
    engine_preflight,
)
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp, target_fingerprint as compute_target_fp
from scripts.ticket_parse import extract_fenced_yaml
from tests.support.builders import expected_canonical_yaml, make_ticket, write_autonomy_config

class TestEngineExecute:
    def test_invalid_transition_terminal_via_update(self, tmp_tickets):
        """done -> in_progress via update is invalid (must reopen first)."""

        make_ticket(tmp_tickets, "2026-03-02-done.md", id="T-20260302-01", status="done")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "in_progress"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert "reopen" in resp.message.lower()

    def test_invalid_transition_wontfix_via_update(self, tmp_tickets):
        """wontfix -> open via update is invalid (must reopen)."""

        make_ticket(tmp_tickets, "2026-03-02-wontfix.md", id="T-20260302-01", status="wontfix")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "open"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"

    def test_transition_to_blocked_requires_blocked_by(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open", blocked_by=[])
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "blocked"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert "blocked_by" in resp.message.lower()

    def test_blocked_ticket_cannot_reopen_with_missing_blocker_reference(self, tmp_tickets):

        make_ticket(
            tmp_tickets,
            "2026-03-02-test.md",
            id="T-20260302-01",
            status="blocked",
            blocked_by=["T-MISSING-01"],
        )
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "open"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert "missing blocker" in resp.message.lower()

    def test_agent_override_rejected(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01")
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Test", "problem": "Test", "priority": "medium"},
            session_id="test-session",
            request_origin="agent",
            dedup_override=True,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Test", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"
        assert "agent" in resp.message.lower() or "override" in resp.message.lower()

    def test_error_code_on_all_error_returns(self, tmp_tickets):
        """All error EngineResponse returns include error_code."""
        # Test update need_fields.
        resp = engine_execute(
            action="update",
            ticket_id=None,
            fields={},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint="dummy-fp",
        )
        assert resp.state == "need_fields"
        assert resp.error_code == "need_fields"

        # Test update not_found.
        resp = engine_execute(
            action="update",
            ticket_id="T-99999999-99",
            fields={},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint="dummy-fp",
        )
        assert resp.state == "not_found"
        assert resp.error_code == "not_found"

    def test_create_ticket(self, tmp_tickets):
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Fix auth bug",
                "problem": "Auth times out for large payloads.",
                "priority": "high",
                "effort": "S",
                "source": {"type": "ad-hoc", "ref": "", "session": "test-session"},
                "tags": ["auth"],
                "approach": "Make timeout configurable.",
                "acceptance_criteria": ["Timeout configurable", "Default remains 30s"],
                "verification": "uv run pytest tests/test_auth.py",
                "key_files": [{"file": "handler.py:45", "role": "Timeout", "look_for": "hardcoded"}],
            },
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Auth times out for large payloads.", []),
        )
        assert resp.state == "ok_create"
        assert resp.ticket_id is not None
        assert resp.ticket_id.startswith("T-")
        assert resp.data["ticket_path"] is not None
        # Verify file was created.
        ticket_path = Path(resp.data["ticket_path"])
        assert ticket_path.exists()
        content = ticket_path.read_text(encoding="utf-8")
        assert "Fix auth bug" in content
        assert "## Problem" in content

    def test_create_uses_canonical_yaml_shape(self, tmp_tickets):
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Canonical create",
                "problem": "Create should use the same serializer as mutations.",
                "priority": "high",
                "effort": "S",
                "source": {"type": "ad-hoc", "ref": "", "session": "test-session"},
                "tags": ["auth", "api"],
            },
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Create should use the same serializer as mutations.", []),
        )
        assert resp.state == "ok_create"
        ticket_path = Path(resp.data["ticket_path"])
        ticket_yaml = extract_fenced_yaml(ticket_path.read_text(encoding="utf-8"))
        # Extract dynamic created_at from actual output for comparison.
        import re as _re
        _ca_match = _re.search(r'created_at: "([^"]+)"', ticket_yaml or "")
        _created_at = _ca_match.group(1) if _ca_match else ""
        assert _created_at, "created_at should be present in newly created tickets"
        assert ticket_yaml == expected_canonical_yaml(
            ticket_id=resp.ticket_id,
            date=ticket_path.name[:10],
            created_at=_created_at,
            status="open",
            priority="high",
            effort="S",
            source_type="ad-hoc",
            source_ref="",
            session="test-session",
            tags=["auth", "api"],
            blocked_by=[],
            blocks=[],
        )

    def test_execute_create_blocks_duplicate_without_override(self, tmp_tickets):
        fields = {
            "title": "Duplicate target",
            "problem": "Duplicate me",
            "priority": "medium",
        }
        fp = compute_dedup_fp(fields["problem"], fields.get("key_file_paths", []))
        first = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert first.state == "ok_create"

        second = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert second.state == "duplicate_candidate"
        assert second.error_code == "duplicate_candidate"

    def test_execute_create_duplicate_allowed_with_override(self, tmp_tickets):
        fields = {
            "title": "Duplicate override target",
            "problem": "Duplicate with override",
            "priority": "medium",
        }
        fp = compute_dedup_fp(fields["problem"], fields.get("key_file_paths", []))
        first = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert first.state == "ok_create"

        second = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="test-session",
            request_origin="user",
            dedup_override=True,
            duplicate_of=first.ticket_id,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert second.state == "ok_create"

    def test_execute_create_retries_on_file_exists(
        self, tmp_tickets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_write = ticket_engine_core._write_text_exclusive
        attempts: list[Path] = []

        def flaky_write(ticket_path: Path, content: str) -> None:
            attempts.append(ticket_path)
            if len(attempts) == 1:
                real_write(ticket_path, content)
                raise FileExistsError("simulated collision")
            real_write(ticket_path, content)

        monkeypatch.setattr(ticket_engine_core, "_write_text_exclusive", flaky_write)

        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Retry on collision",
                "problem": "Exclusive create should retry instead of overwriting.",
                "priority": "medium",
            },
            session_id="retry-session",
            request_origin="user",
            dedup_override=True,
            duplicate_of="T-00000000-00",
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Exclusive create should retry instead of overwriting.", []),
        )

        assert resp.state == "ok_create"
        assert len(attempts) == 2
        assert attempts[0].exists()
        assert attempts[1].exists()
        assert attempts[1] != attempts[0]
        assert Path(resp.data["ticket_path"]) == attempts[1]

    def test_execute_create_fails_after_retry_budget_exhausted(
        self, tmp_tickets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts: list[Path] = []

        def always_exists(ticket_path: Path, content: str) -> None:
            attempts.append(ticket_path)
            raise FileExistsError("still colliding")

        monkeypatch.setattr(ticket_engine_core, "_write_text_exclusive", always_exists)

        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Retry exhaustion",
                "problem": "Create should fail after the exclusive-write retry budget.",
                "priority": "medium",
            },
            session_id="retry-session",
            request_origin="user",
            dedup_override=True,
            duplicate_of="T-00000000-00",
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Create should fail after the exclusive-write retry budget.", []),
        )

        assert resp.state == "escalate"
        assert resp.error_code == "io_error"
        assert "retry budget" in resp.message.lower()
        assert len(attempts) == 3

    def test_execute_create_write_oserror_returns_escalate_with_io_error(
        self, tmp_tickets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def oserror_write(ticket_path: Path, content: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(ticket_engine_core, "_write_text_exclusive", oserror_write)

        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Write failure",
                "problem": "Create should return io_error on OSError.",
                "priority": "medium",
            },
            session_id="oserror-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Create should return io_error on OSError.", []),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "io_error"
        assert "create failed" in resp.message.lower()

    def test_write_text_exclusive_unlinks_partial_file_on_fsync_failure(
        self, tmp_tickets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ticket_path = tmp_tickets / "partial-write.md"

        def fail_fsync(fd: int) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(ticket_engine_core.os, "fsync", fail_fsync)

        with pytest.raises(OSError, match="disk full"):
            ticket_engine_core._write_text_exclusive(ticket_path, "partial content")

        assert not ticket_path.exists()

    def test_execute_create_propagates_plan_errors(self, tmp_tickets):
        """Defense-in-depth should return plan-stage validation failures."""
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Missing problem"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("", []),
        )
        assert resp.state == "need_fields"
        assert resp.error_code == "need_fields"

    def test_update_ticket(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "in_progress"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        content = (tmp_tickets / "2026-03-02-test.md").read_text(encoding="utf-8")
        assert "status: in_progress" in content
        assert 'date: "2026-03-02"' in content

    def test_update_rejects_section_field_problem_and_leaves_file_unchanged(self, tmp_tickets):

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"problem": "New problem text"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "intent_mismatch"
        assert "section fields not supported" in resp.message.lower()
        assert ticket_path.read_text(encoding="utf-8") == before

    def test_update_rejects_mixed_frontmatter_and_section_fields_atomically(self, tmp_tickets):

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"priority": "critical", "approach": "Different approach"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "intent_mismatch"
        assert "section fields not supported" in resp.message.lower()
        after = ticket_path.read_text(encoding="utf-8")
        assert after == before
        assert "priority: critical" not in after

    def test_update_rejects_unknown_field_and_leaves_file_unchanged(self, tmp_tickets):

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"custom": {"bad": "value"}},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "intent_mismatch"
        assert "unknown fields: custom" in resp.message.lower()
        assert ticket_path.read_text(encoding="utf-8") == before

    def test_update_ignores_matching_fields_ticket_id(self, tmp_tickets):

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"ticket_id": "T-20260302-01", "priority": "critical"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        content = ticket_path.read_text(encoding="utf-8")
        assert "priority: critical" in content
        assert "ticket_id:" not in content

    def test_update_rejects_mismatched_fields_ticket_id(self, tmp_tickets):

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"ticket_id": "T-99999999-99"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "intent_mismatch"
        assert "fields.ticket_id must match" in resp.message.lower()
        assert ticket_path.read_text(encoding="utf-8") == before

    def test_update_preserves_field_order(self, tmp_tickets):
        """Canonical renderer emits fields in defined order, not alphabetical."""

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"priority": "critical"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        content = (tmp_tickets / "2026-03-02-test.md").read_text(encoding="utf-8")
        id_pos = content.index("id: T-20260302-01")
        status_pos = content.index("status: open")
        assert id_pos < status_pos

    def test_update_preserves_full_field_order(self, tmp_tickets):
        """Verify all canonical field positions."""

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open",
                     priority="medium", effort="S")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"tags": ["bug"]},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        content = (tmp_tickets / "2026-03-02-test.md").read_text(encoding="utf-8")
        id_pos = content.index("id:")
        status_pos = content.index("status:")
        priority_pos = content.index("priority:")
        effort_pos = content.index("effort:")
        tags_pos = content.index("tags:")
        assert id_pos < status_pos < priority_pos < effort_pos < tags_pos

    def test_canonical_renderer_none_skipped(self, tmp_tickets):
        """Fields set to None are omitted, not rendered as 'key: None'."""

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"effort": None},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        content = (tmp_tickets / "2026-03-02-test.md").read_text(encoding="utf-8")
        assert "effort: None" not in content

    def test_canonical_renderer_list_format(self, tmp_tickets):
        """Lists render as YAML flow sequences, not Python repr."""

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"tags": ["bug", "urgent"]},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        content = (tmp_tickets / "2026-03-02-test.md").read_text(encoding="utf-8")
        assert "tags: [bug, urgent]" in content
        assert "['bug'" not in content

    def test_canonical_renderer_quotes_embedded_double_quote(self, tmp_tickets):
        """Embedded quotes in list items remain valid YAML after update."""
        from scripts.ticket_read import list_tickets

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"tags": ['bad"tag']},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 1
        assert 'bad"tag' in tickets[0].tags

    def test_canonical_renderer_quotes_integer_date(self, tmp_tickets):
        """Integer date values are coerced to string and quoted to prevent type drift."""
        from scripts.ticket_read import list_tickets

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"date": 20260305},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 1
        assert isinstance(tickets[0].date, str)

    def test_canonical_renderer_quotes_colon_strings(self, tmp_tickets):
        """Strings with colon separators remain parseable YAML."""
        from scripts.ticket_read import list_tickets

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"effort": "S: small"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 1
        assert tickets[0].effort == "S: small"

    def test_canonical_renderer_preserves_hash_in_string(self, tmp_tickets):
        """Strings containing # are preserved and not parsed as comments."""
        from scripts.ticket_read import list_tickets

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"effort": "M # note"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        tickets = list_tickets(tmp_tickets)
        assert len(tickets) == 1
        assert tickets[0].effort == "M # note"

    def test_close_ticket(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="in_progress")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close"

    def test_close_with_archive(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="in_progress")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done", "archive": True},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close_archived"
        assert not (tmp_tickets / "2026-03-02-test.md").exists()
        assert (tmp_tickets / "closed-tickets" / "2026-03-02-test.md").exists()

    def test_close_archive_collision_suffixes(self, tmp_tickets):
        """Archiving with an existing file in closed-tickets/ uses -2 suffix."""

        # Create and archive ticket A.
        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="in_progress")
        resp_a = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done", "archive": True},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp_a.state == "ok_close_archived"
        assert (tmp_tickets / "closed-tickets" / "2026-03-02-test.md").exists()

        # Create ticket B with same filename (A no longer blocks the name).
        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-02", status="in_progress")
        resp_b = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done", "archive": True},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp_b.state == "ok_close_archived"
        # Both files exist — B got the -2 suffix.
        assert (tmp_tickets / "closed-tickets" / "2026-03-02-test.md").exists()
        assert (tmp_tickets / "closed-tickets" / "2026-03-02-test-2.md").exists()

    def test_close_with_open_blockers_rejected_without_override(self, tmp_tickets):

        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-20260302-01"],
        )
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "dependency_blocked"
        assert resp.error_code == "dependency_blocked"

    def test_execute_close_reports_missing_blockers(self, tmp_tickets):

        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-MISSING-01"],
        )
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "dependency_blocked"
        assert resp.data["missing_blockers"] == ["T-MISSING-01"]
        assert resp.data["unresolved_blockers"] == []

    def test_close_with_open_blockers_and_override_succeeds(self, tmp_tickets):

        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-20260302-01"],
        )
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=True,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close"

    def test_close_reports_missing_and_unresolved_blockers_together(self, tmp_tickets):

        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-20260302-01", "T-MISSING-01"],
        )
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "dependency_blocked"
        assert resp.data["unresolved_blockers"] == ["T-20260302-01"]
        assert resp.data["missing_blockers"] == ["T-MISSING-01"]

    def test_execute_close_allows_missing_blockers_with_dependency_override(self, tmp_tickets):

        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-MISSING-01"],
        )
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=True,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close"

    def test_close_wontfix_with_open_blockers_succeeds(self, tmp_tickets):

        make_ticket(tmp_tickets, "blocker.md", id="T-20260302-01", status="open")
        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-20260302-01"],
        )
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "wontfix"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close"

    def test_close_wontfix_ignores_missing_blockers(self, tmp_tickets):

        make_ticket(
            tmp_tickets,
            "target.md",
            id="T-20260302-02",
            status="in_progress",
            blocked_by=["T-MISSING-01"],
        )
        preflight = engine_preflight(
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
        assert preflight.state == "ok"
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "wontfix"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close"

    def test_close_archive_rename_oserror_returns_escalate(
        self, tmp_tickets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="in_progress")
        ticket_path = tmp_tickets / "2026-03-02-test.md"
        real_rename = Path.rename

        def fail_rename(self: Path, target: Path) -> None:
            if self == ticket_path:
                raise OSError("disk error")
            real_rename(self, target)

        monkeypatch.setattr(ticket_engine_core.Path, "rename", fail_rename)
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done", "archive": True},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "io_error"
        assert "archive rename failed" in resp.message

    def test_close_archive_collision_suffix_exhausted_returns_escalate(
        self, tmp_tickets: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="in_progress")
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir()
        archived_stub = (
            "# Archived ticket\n\n"
            "```yaml\n"
            "id: T-20260301-99\n"
            "date: \"2026-03-01\"\n"
            "status: done\n"
            "priority: medium\n"
            "source: {type: ad-hoc, ref: \"\", session: \"test\"}\n"
            "contract_version: \"1.0\"\n"
            "```\n"
        )
        (closed_dir / "2026-03-02-test.md").write_text(archived_stub, encoding="utf-8")
        (closed_dir / "2026-03-02-test-2.md").write_text(archived_stub, encoding="utf-8")
        monkeypatch.setattr(ticket_engine_core, "_MAX_ARCHIVE_COLLISION_SUFFIX", 1)
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done", "archive": True},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "io_error"
        assert "collision resolution failed" in resp.message

    def test_close_from_open_succeeds(self, tmp_tickets):
        """Close directly validates with action='close', not 'update'."""

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close"

    def test_close_with_invalid_resolution_rejected(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "in_progress"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        # Schema validation now catches invalid resolutions before transition check.
        assert resp.state == "need_fields"
        assert resp.error_code == "need_fields"
        assert "resolution" in resp.message

    def test_close_terminal_ticket_rejected(self, tmp_tickets):
        """Closing an already-done ticket is invalid — must reopen first."""

        make_ticket(tmp_tickets, "2026-03-02-done.md", id="T-20260302-01", status="done")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "wontfix"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert resp.error_code == "invalid_transition"

    def test_close_wontfix_to_done_rejected(self, tmp_tickets):
        """wontfix -> done via close is invalid — terminal state."""

        make_ticket(tmp_tickets, "2026-03-02-wf.md", id="T-20260302-01", status="wontfix")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"

    def test_close_checks_acceptance_criteria(self, tmp_tickets):
        """Close to 'done' from in_progress requires acceptance criteria."""
        import textwrap

        # Create ticket WITHOUT acceptance criteria section.
        content = textwrap.dedent("""\
            # T-20260302-01: No AC ticket

            ```yaml
            id: T-20260302-01
            date: "2026-03-02"
            status: in_progress
            priority: high
            effort: S
            source:
              type: ad-hoc
              ref: ""
              session: "test"
            tags: []
            blocked_by: []
            blocks: []
            contract_version: "1.0"
            ```

            ## Problem
            Test problem without acceptance criteria.
        """)
        (tmp_tickets / "2026-03-02-test.md").write_text(content, encoding="utf-8")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert "acceptance" in resp.message.lower() or "criteria" in resp.message.lower()

    def test_close_from_open_checks_acceptance_criteria(self, tmp_tickets):
        """Close to 'done' from open requires AC — bypass path for P0-1."""
        import textwrap

        content = textwrap.dedent("""\
            # T-20260302-01: Open no AC ticket

            ```yaml
            id: T-20260302-01
            date: "2026-03-02"
            status: open
            priority: high
            effort: S
            source:
              type: ad-hoc
              ref: ""
              session: "test"
            tags: []
            blocked_by: []
            blocks: []
            contract_version: "1.0"
            ```

            ## Problem
            Test problem without acceptance criteria.
        """)
        (tmp_tickets / "2026-03-02-open-no-ac.md").write_text(content, encoding="utf-8")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert "acceptance" in resp.message.lower() or "criteria" in resp.message.lower()

    def test_close_from_blocked_checks_acceptance_criteria(self, tmp_tickets):
        """Close to 'done' from blocked requires AC — bypass path for P0-1."""
        import textwrap

        content = textwrap.dedent("""\
            # T-20260302-01: Blocked no AC ticket

            ```yaml
            id: T-20260302-01
            date: "2026-03-02"
            status: blocked
            priority: high
            effort: S
            source:
              type: ad-hoc
              ref: ""
              session: "test"
            tags: []
            blocked_by: ["T-OTHER-01"]
            blocks: []
            contract_version: "1.0"
            ```

            ## Problem
            Test problem without acceptance criteria.
        """)
        (tmp_tickets / "2026-03-02-blocked-no-ac.md").write_text(content, encoding="utf-8")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=True,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "invalid_transition"
        assert "acceptance" in resp.message.lower() or "criteria" in resp.message.lower()

    def test_close_from_open_succeeds_with_acceptance_criteria(self, tmp_tickets):
        """Close to 'done' from open succeeds when AC present — positive path."""

        make_ticket(tmp_tickets, "2026-03-02-open-with-ac.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_close", f"Expected ok_close but got {resp.state}: {resp.message}"

    def test_update_rejects_unknown_fields_before_serialization(self, tmp_tickets):
        """Unsupported update fields fail validation before YAML serialization."""

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"custom": {"bad": object()}},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "intent_mismatch"
        assert "unknown fields: custom" in resp.message.lower()

    def test_reopen_ticket(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="done")
        resp = engine_execute(
            action="reopen",
            ticket_id="T-20260302-01",
            fields={"reopen_reason": "Bug reoccurred after merge"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="reopen",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_reopen"
        content = (tmp_tickets / "2026-03-02-test.md").read_text(encoding="utf-8")
        assert "status: open" in content
        assert "Reopen History" in content

    def test_reopen_rejects_invalid_fields_before_write(self, tmp_tickets):

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="done")
        resp = engine_execute(
            action="reopen",
            ticket_id="T-20260302-01",
            fields={"reopen_reason": "Bug reoccurred after merge", "status": "pending"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="reopen",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(ticket_path),
        )
        assert resp.error_code == "need_fields"
        assert "status" in resp.message
        content = ticket_path.read_text(encoding="utf-8")
        assert "status: done" in content

    def test_execute_stale_target_fingerprint_rejected(self, tmp_tickets):
        from scripts.ticket_dedup import target_fingerprint

        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        stale_fp = target_fingerprint(ticket_path)
        ticket_path.write_text(ticket_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "in_progress"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            target_fingerprint=stale_fp,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
        )
        assert resp.state == "preflight_failed"
        assert resp.error_code == "stale_plan"



class TestTransportValidation:
    """Test hook_injected transport-layer validation."""

    def test_agent_without_hook_injected_rejected(self, tmp_tickets):
        """Agent without hook_injected → policy_blocked (transport validation)."""
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "policy_blocked"

    def test_user_without_hook_injected_rejected(self, tmp_tickets):
        """User mutations without hook_injected → policy_blocked."""
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "policy_blocked"

    def test_user_with_hook_injected_but_no_origin_rejected(self, tmp_tickets):
        """User with hook_injected but no hook_request_origin → policy_blocked."""
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
        )
        assert resp.state == "policy_blocked"

    def test_user_with_full_triple_succeeds(self, tmp_tickets):
        """User mutations with full trust triple proceed normally."""
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
        )
        assert resp.state == "ok_create"


class TestExecuteTrustTripleEngine:
    """engine_execute() requires full trust triple for all origins."""

    def test_user_execute_without_hook_injected_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=False,
            hook_request_origin="user",
        )
        assert resp.state == "policy_blocked"

    def test_user_execute_without_hook_request_origin_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            # hook_request_origin not passed (defaults to None)
        )
        assert resp.state == "policy_blocked"

    def test_user_execute_with_mismatched_hook_origin_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="agent",
        )
        assert resp.error_code == "origin_mismatch"

    def test_user_execute_with_full_triple_succeeds(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
        )
        assert resp.state == "ok_create"

    def test_agent_execute_with_mismatched_hook_origin_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
        )
        assert resp.error_code == "origin_mismatch"

    def test_execute_with_empty_session_id_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
        )
        assert resp.state == "policy_blocked"
        assert "session_id empty" in resp.message

    def test_execute_with_unknown_request_origin_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session", request_origin="",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "origin_mismatch"


class TestYamlScalarEdgeCases:
    @pytest.mark.parametrize("reserved", ["true", "yes", "null"])
    def test_reserved_scalar_round_trip_preserved(self, tmp_tickets, reserved: str):
        from scripts.ticket_read import list_tickets

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"effort": reserved},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        tickets = list_tickets(tmp_tickets)
        assert tickets[0].effort == reserved

    def test_empty_string_round_trip_preserved(self, tmp_tickets):
        from scripts.ticket_read import list_tickets

        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open", effort="M")
        resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"effort": ""},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
        )
        assert resp.state == "ok_update"
        tickets = list_tickets(tmp_tickets)
        assert tickets[0].effort == ""


class TestExecuteStructuralPrerequisites:
    """engine_execute() requires prior-stage artifacts."""

    def test_missing_classify_intent_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            # classify_intent missing
        )
        assert resp.state == "policy_blocked"

    def test_mismatched_classify_intent_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="update",  # Doesn't match action="create"
            classify_confidence=0.95,
        )
        assert resp.error_code == "intent_mismatch"

    def test_missing_classify_confidence_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create",
            # classify_confidence missing (defaults to None)
        )
        assert resp.state == "policy_blocked"

    def test_low_confidence_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.3,  # Below 0.5 threshold
        )
        assert resp.state == "preflight_failed"

    def test_exact_user_confidence_threshold_accepted(self, tmp_tickets):
        fp = compute_dedup_fp("P", [])
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.5,
            dedup_fingerprint=fp,
        )
        assert resp.state == "ok_create"

    def test_missing_dedup_fingerprint_for_create_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            # dedup_fingerprint missing
        )
        assert resp.state == "policy_blocked"

    def test_mismatched_dedup_fingerprint_rejected(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint="wrong-fingerprint",
        )
        assert resp.error_code == "stale_plan"

    def test_correct_dedup_fingerprint_accepted(self, tmp_tickets):
        fp = compute_dedup_fp("P", [])
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert resp.state == "ok_create"

    def test_missing_target_fingerprint_for_update_rejected(self, tmp_tickets):
        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        resp = engine_execute(
            action="update", ticket_id="T-20260302-01",
            fields={"status": "in_progress"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
            # target_fingerprint missing (None)
        )
        assert resp.state == "policy_blocked"

    def test_agent_missing_autonomy_config_rejected(self, tmp_tickets):
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("P", []),
            # autonomy_config=None (missing snapshot)
        )
        assert resp.state == "policy_blocked"


class TestExecuteFieldValidation:
    """engine_execute rejects invalid field types/values before writing."""

    def test_create_invalid_priority_rejected(self, tmp_tickets):
        fp = compute_dedup_fp("Problem", [])
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "Problem", "priority": "urgent"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create", classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert resp.error_code == "need_fields"
        assert "priority" in resp.message

    def test_create_invalid_key_file_paths_rejected_before_fingerprint_recompute(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "Problem", "key_file_paths": "src/main.py"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create", classify_confidence=0.95,
            dedup_fingerprint="placeholder",
        )
        assert resp.error_code == "need_fields"
        assert "key_file_paths" in resp.message

    def test_create_scalar_tags_rejected(self, tmp_tickets):
        fp = compute_dedup_fp("Problem", [])
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "T", "problem": "Problem", "tags": "bug"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="create", classify_confidence=0.95,
            dedup_fingerprint=fp,
        )
        assert resp.error_code == "need_fields"
        assert "tags" in resp.message

    def test_update_scalar_blocked_by_rejected(self, tmp_tickets):

        tp = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")
        tfp = compute_target_fp(tp)
        resp = engine_execute(
            action="update", ticket_id="T-20260302-01",
            fields={"blocked_by": "T-20260302-02"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="update", classify_confidence=0.95,
            target_fingerprint=tfp,
        )
        assert resp.error_code == "need_fields"
        assert "blocked_by" in resp.message

    def test_close_invalid_resolution_rejected(self, tmp_tickets):

        tp = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="in_progress")
        tfp = compute_target_fp(tp)
        resp = engine_execute(
            action="close", ticket_id="T-20260302-01",
            fields={"resolution": "cancelled"},
            session_id="sess", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True, hook_request_origin="user",
            classify_intent="close", classify_confidence=0.95,
            target_fingerprint=tfp,
        )
        assert resp.error_code == "need_fields"
        assert "resolution" in resp.message


class TestContractVersionEnforcement:
    """C-004: contract_version is engine-owned; callers cannot set it."""

    def test_update_rejects_caller_contract_version(self, tmp_tickets):
        """Update with contract_version in fields should be rejected as unknown field."""
        from scripts.ticket_engine_core import _execute_update

        make_ticket(tmp_tickets, "2026-03-10-cv.md",
                    id="T-20260310-01", title="Test ticket")

        resp = _execute_update(
            ticket_id="T-20260310-01",
            fields={"priority": "high", "contract_version": "0.9"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "escalate"
        assert "contract_version" in resp.message

    def test_update_stamps_contract_version(self, tmp_tickets):
        """Valid update should stamp contract_version='1.0' on the file."""
        from scripts.ticket_engine_core import _execute_update
        from scripts.ticket_parse import parse_ticket

        make_ticket(tmp_tickets, "2026-03-10-cv-stamp.md",
                    id="T-20260310-01", title="Test ticket",
                    contract_version="0.8")

        resp = _execute_update(
            ticket_id="T-20260310-01",
            fields={"priority": "low"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok_update"

        ticket = parse_ticket(tmp_tickets / "2026-03-10-cv-stamp.md")
        assert ticket is not None
        assert ticket.frontmatter.get("contract_version") == "1.0", (
            f"contract_version should be forced to 1.0, got {ticket.frontmatter.get('contract_version')!r}"
        )

    def test_close_stamps_contract_version(self, tmp_tickets):
        """Close should stamp contract_version='1.0'."""
        from scripts.ticket_engine_core import _execute_close
        from scripts.ticket_parse import parse_ticket

        make_ticket(tmp_tickets, "2026-03-10-cv2.md",
                    id="T-20260310-02", title="Test ticket",
                    status="in_progress", contract_version="0.8")

        resp = _execute_close(
            ticket_id="T-20260310-02",
            fields={"resolution": "done"},
            session_id="test-session",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )

        assert resp.state in ("ok_close", "ok_close_archived")
        ticket = parse_ticket(Path(resp.data["ticket_path"]))
        assert ticket is not None
        assert ticket.frontmatter.get("contract_version") == "1.0"

    def test_contract_version_not_in_update_keys(self):
        """contract_version should not be in _UPDATE_FRONTMATTER_KEYS."""
        from scripts.ticket_engine_core import _UPDATE_FRONTMATTER_KEYS
        assert "contract_version" not in _UPDATE_FRONTMATTER_KEYS
