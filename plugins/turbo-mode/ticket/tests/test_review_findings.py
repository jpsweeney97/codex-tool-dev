"""Regression tests for architectural review findings (2026-03-08).

Each test reproduces the exact scenario described in the finding and verifies
the fix resolves it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from scripts.ticket_autonomy_config import AutomationMode, write_local_config
from scripts.ticket_dedup import (
    dedup_fingerprint as compute_dedup_fp,
)
from scripts.ticket_dedup import (
    target_fingerprint as compute_target_fp,
)
from scripts.ticket_engine_core import (
    AutonomyConfig,
    engine_count_session_creates,
    engine_execute,
    engine_plan,
)
from scripts.ticket_parse import parse_ticket
from scripts.ticket_review import hygiene_candidates_from_review, review_payload
from scripts.ticket_validate import validate_fields

from tests.support.builders import make_ticket

# ---------------------------------------------------------------------------
# F1: Close/reopen stays in active target ticket records
# ---------------------------------------------------------------------------


class TestF1ReopenUnarchive:
    """Target records no longer archive closed tickets to closed-tickets/."""

    def test_close_then_reopen_updates_active_ticket_in_place(self, tmp_tickets: Path) -> None:
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Reopen test", "problem": "Will remain active"},
            session_id="f1-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Will remain active", []),
        )
        assert resp.state == "ok"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])

        fp = compute_target_fp(ticket_path)
        close_resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
            fields={"resolution": "wontfix"},
            session_id="f1-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            target_fingerprint=fp,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
        )
        assert close_resp.state == "ok"
        closed_path = Path(close_resp.data["ticket_path"])
        assert closed_path == ticket_path
        assert closed_path.parent == tmp_tickets
        assert closed_path.exists()
        closed_ticket = parse_ticket(closed_path)
        assert closed_ticket is not None
        assert closed_ticket.status == "wontfix"

        reopen_fp = compute_target_fp(closed_path)
        reopen_resp = engine_execute(
            action="reopen",
            ticket_id=ticket_id,
            fields={"reopen_reason": "Need more work"},
            session_id="f1-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            target_fingerprint=reopen_fp,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="reopen",
            classify_confidence=0.95,
        )
        assert reopen_resp.state == "ok"
        reopened_path = Path(reopen_resp.data["ticket_path"])

        assert reopened_path.parent == tmp_tickets
        assert reopened_path.exists()
        assert reopened_path == ticket_path

        ticket = parse_ticket(reopened_path)
        assert ticket is not None
        assert ticket.status == "open"

    def test_close_archive_field_is_rejected(self, tmp_tickets: Path) -> None:
        """archive is removed from the target write vocabulary."""
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Archive rejected", "problem": "Archive flag should fail"},
            session_id="f1-archive-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Archive flag should fail", []),
        )
        assert resp.state == "ok"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])

        fp = compute_target_fp(ticket_path)
        close_resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
            fields={"resolution": "wontfix", "archive": True},
            session_id="f1-archive-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            target_fingerprint=fp,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="close",
            classify_confidence=0.95,
        )
        assert close_resp.state == "need_fields"
        assert close_resp.data["validation_errors"] == ["archive is not a target write field"]


# ---------------------------------------------------------------------------
# F2: Pipeline plan -> execute for non-create must provide target_fingerprint
# ---------------------------------------------------------------------------


class TestF2PlanFingerprint:
    """Repro: plan(update) -> preflight -> execute(update) must not policy_block."""

    def test_plan_returns_target_fingerprint_for_update_via_ticket_id_param(
        self, tmp_tickets: Path
    ) -> None:
        """ticket_id passed as top-level param (real entrypoint path)."""
        make_ticket(tmp_tickets, "2026-03-02-fp-test.md", id="T-20260302-01")
        resp = engine_plan(
            intent="update",
            fields={},
            session_id="f2-sess",
            request_origin="user",
            tickets_dir=tmp_tickets,
            ticket_id="T-20260302-01",
        )
        assert resp.state == "ok"
        assert resp.data["target_fingerprint"] is not None

    def test_plan_falls_back_to_fields_ticket_id(self, tmp_tickets: Path) -> None:
        """ticket_id in fields still works (backward compat)."""
        make_ticket(tmp_tickets, "2026-03-02-fp-test2.md", id="T-20260302-02")
        resp = engine_plan(
            intent="update",
            fields={"ticket_id": "T-20260302-02"},
            session_id="f2-sess",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert resp.data["target_fingerprint"] is not None

    def test_plan_returns_none_fingerprint_when_no_ticket_id(self, tmp_tickets: Path) -> None:
        resp = engine_plan(
            intent="update",
            fields={},
            session_id="f2-sess",
            request_origin="user",
            tickets_dir=tmp_tickets,
        )
        assert resp.state == "ok"
        assert resp.data["target_fingerprint"] is None

    def test_full_update_pipeline_via_entrypoint(self, tmp_tickets: Path) -> None:
        """Documented payload schema: ticket_id at top level, not in fields."""
        make_ticket(tmp_tickets, "2026-03-02-pipeline.md", id="T-20260302-03")

        # Plan with top-level ticket_id (matches pipeline-guide.md schema).
        plan_resp = engine_plan(
            intent="update",
            fields={"priority": "high"},
            session_id="f2-sess",
            request_origin="user",
            tickets_dir=tmp_tickets,
            ticket_id="T-20260302-03",
        )
        assert plan_resp.state == "ok"
        fp = plan_resp.data["target_fingerprint"]
        assert fp is not None

        exec_resp = engine_execute(
            action="update",
            ticket_id="T-20260302-03",
            fields={"priority": "high"},
            session_id="f2-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            target_fingerprint=fp,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
        )
        assert exec_resp.state == "ok"

    def test_plan_via_entrypoint_payload(self, tmp_tickets: Path) -> None:
        """PlanInput.from_payload extracts top-level ticket_id."""
        from scripts.ticket_stage_models import PlanInput

        payload = {
            "action": "update",
            "ticket_id": "T-20260302-04",
            "session_id": "f2-sess",
            "fields": {"priority": "high"},
        }
        inp = PlanInput.from_payload(payload)
        assert inp.ticket_id == "T-20260302-04"

    def test_plan_via_cli_returns_target_fingerprint(self, tmp_tickets: Path) -> None:
        """Documented update payload through CLI produces non-null target_fingerprint."""
        import tempfile

        make_ticket(tmp_tickets, "2026-03-02-cli.md", id="T-20260302-05")
        project_root = tmp_tickets.parents[1]

        # Write payload matching pipeline-guide.md schema.
        payload = {
            "action": "update",
            "ticket_id": "T-20260302-05",
            "args": {"ticket_id": "T-20260302-05"},
            "session_id": "",
            "request_origin": "user",
            "fields": {"priority": "high"},
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            dir=str(project_root),
        ) as f:
            json.dump(payload, f)
            payload_path = f.name

        user_script = Path(__file__).parent.parent / "scripts" / "ticket_engine_user.py"
        result = subprocess.run(
            [sys.executable, str(user_script), "plan", payload_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        Path(payload_path).unlink()
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert data["data"]["target_fingerprint"] is not None


# ---------------------------------------------------------------------------
# F3a: Future creates must not write active audit counters
# ---------------------------------------------------------------------------


class TestF3aOriginFilter:
    """Historical audit counting remains readable, but future writes do not add entries."""

    def test_user_create_does_not_write_future_audit_count(self, tmp_tickets: Path) -> None:
        session_id = "f3a-sess"
        engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "User ticket", "problem": "User created"},
            session_id=session_id,
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("User created", []),
        )

        assert engine_count_session_creates(session_id, tmp_tickets, request_origin="agent") == 0
        assert engine_count_session_creates(session_id, tmp_tickets, request_origin="user") == 0


# ---------------------------------------------------------------------------
# F3b: Agent writes fail before legacy audit paths
# ---------------------------------------------------------------------------


class TestF3bAuditResultFailClose:
    """Runtime-first gateway blocks agent writes before any legacy audit append."""

    def test_agent_create_requires_gateway_before_audit_append(self, tmp_tickets: Path) -> None:
        write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
        config = AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY)

        def patched_audit_append(*args, **kwargs):
            raise AssertionError("_audit_append should not run for future agent writes")

        with patch("scripts.ticket_engine_core._audit_append", side_effect=patched_audit_append):
            resp = engine_execute(
                action="create",
                ticket_id=None,
                fields={"title": "Agent ticket", "problem": "Agent issue"},
                session_id="f3b-sess",
                request_origin="agent",
                dedup_override=False,
                dependency_override=False,
                tickets_dir=tmp_tickets,
                autonomy_config=config,
                hook_injected=True,
                hook_request_origin="agent",
                classify_intent="create",
                classify_confidence=0.95,
                dedup_fingerprint=compute_dedup_fp("Agent issue", []),
            )
        assert resp.state == "policy_blocked"
        assert resp.error_code == "gateway_required"
        assert engine_count_session_creates("f3b-sess", tmp_tickets, request_origin="agent") == 0

    def test_agent_preflight_requires_gateway_not_legacy_cap(self, tmp_tickets: Path) -> None:
        write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
        from scripts.ticket_engine_core import engine_preflight

        preflight_resp = engine_preflight(
            ticket_id=None,
            action="create",
            session_id="f3b-cap-sess",
            request_origin="agent",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint=compute_dedup_fp("Second issue", []),
            target_fingerprint=None,
            fields={"title": "Second agent ticket", "problem": "Second issue"},
            duplicate_of=None,
            dedup_override=False,
            dependency_override=False,
            hook_injected=True,
            tickets_dir=tmp_tickets,
        )
        assert preflight_resp.state == "policy_blocked"
        assert preflight_resp.error_code == "gateway_required"

    def test_user_create_succeeds_despite_result_audit_failure(self, tmp_tickets: Path) -> None:
        """User creates should not be blocked by result audit failures."""
        call_count = 0

        def patched_audit_append(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True
            return False

        with patch("scripts.ticket_engine_core._audit_append", side_effect=patched_audit_append):
            resp = engine_execute(
                action="create",
                ticket_id=None,
                fields={"title": "User ticket", "problem": "User issue"},
                session_id="f3b-user-sess",
                request_origin="user",
                dedup_override=False,
                dependency_override=False,
                tickets_dir=tmp_tickets,
                hook_injected=True,
                hook_request_origin="user",
                classify_intent="create",
                classify_confidence=0.95,
                dedup_fingerprint=compute_dedup_fp("User issue", []),
            )
        assert resp.state == "ok"
        assert call_count == 0


# ---------------------------------------------------------------------------
# F4: Read-only CLIs must use discovered project root, not cwd
# ---------------------------------------------------------------------------

READ_SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_read.py"
TRIAGE_SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_triage.py"
AUDIT_SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_audit.py"


class TestF4ProjectRootDiscovery:
    """Repro: from <repo>/sub/dir, absolute tickets_dir should work."""

    def test_read_from_subdirectory_finds_project_root(self, tmp_tickets: Path) -> None:
        project_root = tmp_tickets.parents[1]
        subdir = project_root / "sub" / "dir"
        subdir.mkdir(parents=True)

        make_ticket(tmp_tickets, "2026-03-02-subdir.md", id="T-20260302-01")

        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tmp_tickets)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(subdir),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["data"]["tickets"]) == 1

    def test_triage_from_subdirectory_finds_project_root(self, tmp_tickets: Path) -> None:
        project_root = tmp_tickets.parents[1]
        subdir = project_root / "sub" / "dir"
        subdir.mkdir(parents=True)

        result = subprocess.run(
            [sys.executable, str(TRIAGE_SCRIPT), "dashboard", str(tmp_tickets)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(subdir),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ok"

    def test_read_no_project_root_returns_policy_blocked(self, tmp_path: Path) -> None:
        """Without .git or .codex marker, CLIs should fail cleanly."""
        # Create a dir with no project root markers.
        isolated = tmp_path / "no_markers"
        isolated.mkdir()
        tickets = isolated / "docs" / "tickets"
        tickets.mkdir(parents=True)

        result = subprocess.run(
            [sys.executable, str(READ_SCRIPT), "list", str(tickets)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(isolated),
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["state"] == "policy_blocked"
        assert "project root" in data["message"].lower()


# ---------------------------------------------------------------------------
# F5: source is not a target write field
# ---------------------------------------------------------------------------


class TestF5SourceValidation:
    """source metadata is no longer written into target ticket frontmatter."""

    def test_source_without_type_returns_deprecated_field_error(self) -> None:
        errors = validate_fields({"source": {"ref": "x"}})
        assert errors == ["source is not a target write field"]

    def test_source_with_all_required_keys_is_still_deprecated(self) -> None:
        errors = validate_fields({"source": {"type": "ad-hoc", "ref": "x", "session": ""}})
        assert errors == ["source is not a target write field"]

    def test_create_with_bad_source_returns_need_fields(self, tmp_tickets: Path) -> None:
        """Engine should catch bad source before render_ticket crashes."""
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Bad source",
                "problem": "Missing type",
                "source": {"ref": "x"},
            },
            session_id="f5-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Missing type", []),
        )
        # Should get a structured error, not an unhandled KeyError.
        assert resp.state == "need_fields"
        assert "source" in resp.message.lower() or "type" in resp.message.lower()


def test_review_payload_remains_read_only_and_exports_hygiene_candidates(
    tmp_tickets: Path,
) -> None:
    ticket_path = make_ticket(
        tmp_tickets,
        "stale.md",
        id="T-20260501-01",
        date="2026-05-01",
        status="open",
    )
    before = ticket_path.read_text(encoding="utf-8")

    payload = review_payload(tmp_tickets)
    candidates = hygiene_candidates_from_review(payload)

    assert ticket_path.read_text(encoding="utf-8") == before
    assert payload["stale"][0]["id"] == "T-20260501-01"
    assert candidates["review_hygiene_findings"][0]["ticket_id"] == "T-20260501-01"
    assert candidates["review_hygiene_findings"][0]["action"] == "stale_cleanup"
    assert "approval" not in candidates["review_hygiene_findings"][0]
