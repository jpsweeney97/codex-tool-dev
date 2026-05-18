"""Integration tests — full engine pipeline end-to-end."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp, target_fingerprint as compute_target_fp
from scripts.ticket_engine_core import (
    engine_classify,
    engine_execute,
    engine_plan,
    engine_preflight,
)
from scripts.ticket_parse import extract_fenced_yaml
from tests.support.builders import expected_canonical_yaml, make_ticket


class TestFullCreatePipeline:
    def test_user_create_end_to_end(self, tmp_tickets):
        """classify -> plan -> preflight -> execute for user create."""
        # Step 1: classify
        classify_resp = engine_classify(
            action="create",
            args={},
            session_id="integration-test",
            request_origin="user",
        )
        assert classify_resp.state == "ok"

        # Step 2: plan
        fields = {
            "title": "Integration test ticket",
            "problem": "This is an integration test.",
            "priority": "medium",
            "key_file_paths": [],
        }
        plan_resp = engine_plan(
            intent=classify_resp.data["intent"],
            fields=fields,
            session_id="integration-test",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert plan_resp.state == "ok"

        # Step 3: preflight
        preflight_resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="integration-test",
            request_origin="user",
            classify_confidence=classify_resp.data["confidence"],
            classify_intent=classify_resp.data["intent"],
            dedup_fingerprint=plan_resp.data["dedup_fingerprint"],
            target_fingerprint=plan_resp.data["target_fingerprint"],
            tickets_dir=tmp_tickets,
        )
        assert preflight_resp.state == "ok"

        # Step 4: execute
        execute_resp = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="integration-test",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent=classify_resp.data["intent"],
            classify_confidence=classify_resp.data["confidence"],
            dedup_fingerprint=plan_resp.data["dedup_fingerprint"],
        )
        assert execute_resp.state == "ok_create"
        assert Path(execute_resp.data["ticket_path"]).exists()

    def test_user_create_end_to_end_with_plain_classify_data_merge(self, tmp_tickets):
        """The skill can merge classify data directly without renaming fields."""
        payload = {
            "action": "create",
            "args": {},
            "session_id": "integration-plain-merge",
            "request_origin": "user",
            "fields": {
                "title": "Integration plain merge ticket",
                "problem": "This verifies classify aliases are emitted natively.",
                "priority": "medium",
                "key_file_paths": [],
            },
        }

        classify_resp = engine_classify(
            action=payload["action"],
            args=payload["args"],
            session_id=payload["session_id"],
            request_origin=payload["request_origin"],
        )
        assert classify_resp.state == "ok"
        payload.update(classify_resp.data)

        plan_resp = engine_plan(
            intent=payload["intent"],
            fields=payload["fields"],
            session_id=payload["session_id"],
            request_origin=payload["request_origin"],
            tickets_dir=tmp_tickets,
        )
        assert plan_resp.state == "ok"
        payload.update(plan_resp.data)

        preflight_resp = engine_preflight(
            ticket_id=payload.get("resolved_ticket_id"),
            action=payload["action"],
            session_id=payload["session_id"],
            request_origin=payload["request_origin"],
            classify_confidence=payload.get("classify_confidence", 0.0),
            classify_intent=payload.get("classify_intent", ""),
            dedup_fingerprint=payload.get("dedup_fingerprint"),
            target_fingerprint=payload.get("target_fingerprint"),
            tickets_dir=tmp_tickets,
        )
        assert preflight_resp.state == "ok"

        execute_resp = engine_execute(
            action=payload["action"],
            ticket_id=payload.get("resolved_ticket_id"),
            fields=payload["fields"],
            session_id=payload["session_id"],
            request_origin=payload["request_origin"],
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent=payload.get("classify_intent"),
            classify_confidence=payload.get("classify_confidence"),
            dedup_fingerprint=payload.get("dedup_fingerprint"),
        )
        assert execute_resp.state == "ok_create"
        assert Path(execute_resp.data["ticket_path"]).exists()

    def test_agent_blocked_phase1_fail_closed(self, tmp_tickets):
        """Agent create is hard-blocked by Phase 1 fail-closed policy."""
        classify_resp = engine_classify(
            action="create",
            args={},
            session_id="agent-test",
            request_origin="agent",
        )
        assert classify_resp.state == "ok"

        preflight_resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="agent-test",
            request_origin="agent",
            classify_confidence=classify_resp.data["confidence"],
            classify_intent=classify_resp.data["intent"],
            dedup_fingerprint=None,
            target_fingerprint=None,
            tickets_dir=tmp_tickets,
        )
        assert preflight_resp.state == "policy_blocked"

    def test_update_then_close_pipeline(self, tmp_tickets):
        """Create -> update to in_progress -> close."""
        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")

        # Update to in_progress.
        update_resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "in_progress"},
            session_id="test",
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
        assert update_resp.state == "ok_update"

        # Close.
        close_resp = engine_execute(
            action="close",
            ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="test",
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
        assert close_resp.state == "ok_close"

    def test_dedup_then_override(self, tmp_tickets):
        """Create duplicate detected -> override -> create succeeds."""
        # Use dynamic date so ticket stays within 24h dedup window.
        today = datetime.now(timezone.utc).date().isoformat()
        make_ticket(
            tmp_tickets,
            f"{today}-existing.md",
            id="T-20260302-01",
            date=today,
            problem="Auth times out.",
        )

        fields = {
            "title": "Same auth bug",
            "problem": "Auth times out.",
            "priority": "high",
            # make_ticket's Key Files table always includes "test.py".
            "key_file_paths": ["test.py"],
        }

        plan_resp = engine_plan(
            intent="create",
            fields=fields,
            session_id="test",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert plan_resp.state == "duplicate_candidate"

        # Override and create anyway with the same execute payload.
        execute_resp = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="test",
            request_origin="user",
            dedup_override=True,
            duplicate_of=plan_resp.data["duplicate_of"],
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp(fields["problem"], fields.get("key_file_paths", [])),
        )
        assert execute_resp.state == "ok_create"

    def test_create_with_key_file_paths_only_produces_valid_ticket_without_key_files_section(
        self, tmp_tickets
    ):
        fields = {
            "title": "Paths only create",
            "problem": "Only dedup file paths are available for this ticket.",
            "priority": "medium",
            "key_file_paths": ["src/auth/token.py", "src/middleware/session.py"],
        }

        plan_resp = engine_plan(
            intent="create",
            fields=fields,
            session_id="paths-only",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert plan_resp.state == "ok"
        assert plan_resp.data["dedup_fingerprint"]

        execute_resp = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="paths-only",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=plan_resp.data["dedup_fingerprint"],
        )
        assert execute_resp.state == "ok_create"

        ticket_path = Path(execute_resp.data["ticket_path"])
        assert ticket_path.exists()
        ticket_text = ticket_path.read_text(encoding="utf-8")
        assert "## Key Files" not in ticket_text


class TestEngineExecuteIntegration:
    """Integration tests exercising the full engine_execute dispatcher
    across multiple lifecycle operations."""

    def test_full_lifecycle_create_update_close_reopen(self, tmp_tickets):
        """Create -> update -> close -> reopen lifecycle."""
        # Create.
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Lifecycle test",
                "problem": "Integration test problem.",
                "priority": "medium",
                "source": {"type": "ad-hoc", "ref": "", "session": "test-session"},
                "tags": ["test"],
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
            dedup_fingerprint=compute_dedup_fp("Integration test problem.", []),
        )
        assert resp.state == "ok_create"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])
        assert ticket_path.exists()

        # Update status to in_progress.
        resp = engine_execute(
            action="update",
            ticket_id=ticket_id,
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

        # Close with wontfix (avoids acceptance criteria requirement).
        resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
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

        # Reopen.
        resp = engine_execute(
            action="reopen",
            ticket_id=ticket_id,
            fields={"reopen_reason": "Reconsidered — will fix after all"},
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

        # Verify final state.
        content = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in content
        assert "Reopen History" in content

    def test_full_lifecycle_preserves_canonical_yaml_shape(self, tmp_tickets):
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Serializer lifecycle",
                "problem": "All mutation paths should share one YAML renderer.",
                "priority": "medium",
                "effort": "S",
                "source": {"type": "ad-hoc", "ref": "", "session": "test-session"},
                "tags": ["test"],
                "blocked_by": [],
                "blocks": [],
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
            dedup_fingerprint=compute_dedup_fp("All mutation paths should share one YAML renderer.", []),
        )
        assert resp.state == "ok_create"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])
        ticket_date = ticket_path.name[:10]

        # Extract dynamic created_at from actual output.
        import re as _re
        _actual_yaml = extract_fenced_yaml(ticket_path.read_text(encoding="utf-8"))
        _ca_match = _re.search(r'created_at: "([^"]+)"', _actual_yaml or "")
        _created_at = _ca_match.group(1) if _ca_match else ""

        expected = expected_canonical_yaml(
            ticket_id=ticket_id,
            date=ticket_date,
            created_at=_created_at,
            status="open",
            priority="medium",
            effort="S",
            source_type="ad-hoc",
            source_ref="",
            session="test-session",
            tags=["test"],
            blocked_by=[],
            blocks=[],
        )
        assert _actual_yaml == expected

        resp = engine_execute(
            action="update",
            ticket_id=ticket_id,
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
        expected = expected.replace("status: open\n", "status: in_progress\n")
        assert extract_fenced_yaml(ticket_path.read_text(encoding="utf-8")) == expected

        resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
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
        expected = expected.replace("status: in_progress\n", "status: wontfix\n")
        assert extract_fenced_yaml(ticket_path.read_text(encoding="utf-8")) == expected

        resp = engine_execute(
            action="reopen",
            ticket_id=ticket_id,
            fields={"reopen_reason": "Follow-up work is required"},
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
        expected = expected.replace("status: wontfix\n", "status: open\n")
        content = ticket_path.read_text(encoding="utf-8")
        assert extract_fenced_yaml(content) == expected
        assert "## Reopen History" in content

    def test_unknown_action_escalates(self, tmp_tickets):
        """Dispatcher rejects unknown actions."""
        ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01")
        resp = engine_execute(
            action="merge",
            ticket_id="T-20260302-01",
            fields={},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="merge",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(ticket_path),
        )
        assert resp.state == "escalate"
        assert resp.error_code == "intent_mismatch"
