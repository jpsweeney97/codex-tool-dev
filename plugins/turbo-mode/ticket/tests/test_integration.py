"""Integration tests — full engine pipeline end-to-end."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_dedup import target_fingerprint as compute_target_fp
from scripts.ticket_engine_core import (
    engine_classify,
    engine_execute,
    engine_plan,
    engine_preflight,
)
from scripts.ticket_parse import parse_ticket

from tests.support.builders import make_ticket


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
            "priority": "normal",
            "related_paths": [],
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
        assert execute_resp.state == "ok"
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
                "priority": "normal",
                "related_paths": [],
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
        assert execute_resp.state == "ok"
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
        """Create -> update to blocked -> close."""
        make_ticket(tmp_tickets, "2026-03-02-test.md", id="T-20260302-01", status="open")

        # Update to blocked.
        update_resp = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"status": "blocked", "blocked_on": "Waiting for upstream work."},
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
        assert update_resp.state == "ok"

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
        assert close_resp.state == "ok"

    def test_dedup_then_override(self, tmp_tickets):
        """Create duplicate detected -> override -> create succeeds."""
        # Use dynamic date so ticket stays within 24h dedup window.
        today = datetime.now(UTC).date().isoformat()
        today_compact = today.replace("-", "")
        make_ticket(
            tmp_tickets,
            f"{today}-existing.md",
            id=f"T-{today_compact}-01",
            date=today,
            problem="Auth times out.",
            related_paths=["test.py"],
        )

        fields = {
            "title": "Same auth bug",
            "problem": "Auth times out.",
            "priority": "high",
            "related_paths": ["test.py"],
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
            dedup_fingerprint=compute_dedup_fp(fields["problem"], fields.get("related_paths", [])),
        )
        assert execute_resp.state == "ok"

    def test_create_with_related_paths_only_produces_valid_ticket_without_key_files_section(
        self, tmp_tickets
    ):
        fields = {
            "title": "Paths only create",
            "problem": "Only dedup file paths are available for this ticket.",
            "priority": "normal",
            "related_paths": ["src/auth/token.py", "src/middleware/session.py"],
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
        assert execute_resp.state == "ok"

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
                "priority": "normal",
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
        assert resp.state == "ok"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])
        assert ticket_path.exists()

        # Update status to blocked.
        resp = engine_execute(
            action="update",
            ticket_id=ticket_id,
            fields={"status": "blocked", "blocked_on": "Waiting for upstream work."},
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
        assert resp.state == "ok"

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
        assert resp.state == "ok"

        # Reopen.
        resp = engine_execute(
            action="reopen",
            ticket_id=ticket_id,
            fields={"status": "open"},
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
        assert resp.state == "ok"

        # Verify final state.
        content = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in content
        assert "Reopen History" not in content

    def test_full_lifecycle_preserves_canonical_yaml_shape(self, tmp_tickets):
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Serializer lifecycle",
                "problem": "All mutation paths should share one YAML renderer.",
                "priority": "normal",
                "tags": ["test"],
                "blocked_by": [],
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
            dedup_fingerprint=compute_dedup_fp(
                "All mutation paths should share one YAML renderer.", []
            ),
        )
        assert resp.state == "ok"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])
        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert ticket.frontmatter == {
            "id": ticket_id,
            "title": "Serializer lifecycle",
            "status": "open",
            "priority": "normal",
            "tags": ["test"],
            "related_paths": [],
            "blocked_by": [],
        }

        resp = engine_execute(
            action="update",
            ticket_id=ticket_id,
            fields={"status": "blocked", "blocked_on": "Waiting for upstream work."},
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
        assert resp.state == "ok"
        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert ticket.status == "blocked"

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
        assert resp.state == "ok"
        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert ticket.status == "wontfix"

        resp = engine_execute(
            action="reopen",
            ticket_id=ticket_id,
            fields={"status": "open"},
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
        assert resp.state == "ok"
        content = ticket_path.read_text(encoding="utf-8")
        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert ticket.status == "open"
        assert "## Reopen History" not in content

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
