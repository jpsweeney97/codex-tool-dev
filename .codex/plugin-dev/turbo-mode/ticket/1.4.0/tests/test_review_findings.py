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

from scripts.ticket_dedup import (
    dedup_fingerprint as compute_dedup_fp,
    target_fingerprint as compute_target_fp,
)
from scripts.ticket_engine_core import (
    AutonomyConfig,
    engine_count_session_creates,
    engine_execute,
    engine_plan,
)
from scripts.ticket_read import find_ticket_by_id
from scripts.ticket_validate import validate_fields
from tests.support.builders import make_ticket, write_autonomy_config


# ---------------------------------------------------------------------------
# F1: Reopening an archived ticket must move it back to active directory
# ---------------------------------------------------------------------------

class TestF1ReopenUnarchive:
    """Repro: create -> close(archive=True) -> reopen should move ticket back."""

    def test_reopen_archived_ticket_moves_to_active_dir(self, tmp_tickets: Path) -> None:
        # Create and close with archive.
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Archive test", "problem": "Will be archived"},
            session_id="f1-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Will be archived", []),
        )
        assert resp.state == "ok_create"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])

        fp = compute_target_fp(ticket_path)
        close_resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
            fields={"resolution": "wontfix", "archive": True},
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
        assert close_resp.state == "ok_close_archived"
        archived_path = Path(close_resp.data["ticket_path"])
        assert archived_path.parent.name == "closed-tickets"
        assert archived_path.exists()
        assert not ticket_path.exists()

        # Reopen: should move back to active directory.
        reopen_fp = compute_target_fp(archived_path)
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
        assert reopen_resp.state == "ok_reopen"
        reopened_path = Path(reopen_resp.data["ticket_path"])

        # Ticket must be in active directory, not closed-tickets/.
        assert reopened_path.parent == tmp_tickets
        assert reopened_path.exists()
        assert not archived_path.exists()

        # Status must be open.
        ticket = find_ticket_by_id(tmp_tickets, ticket_id, include_closed=False)
        assert ticket is not None
        assert ticket.status == "open"


    def test_reopen_rename_failure_preserves_closed_status(self, tmp_tickets: Path) -> None:
        """If un-archive rename fails, ticket stays closed with original status."""
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Rename fail", "problem": "Will fail rename"},
            session_id="f1-rename-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Will fail rename", []),
        )
        assert resp.state == "ok_create"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])

        fp = compute_target_fp(ticket_path)
        close_resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
            fields={"resolution": "wontfix", "archive": True},
            session_id="f1-rename-sess",
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
        assert close_resp.state == "ok_close_archived"
        archived_path = Path(close_resp.data["ticket_path"])
        original_text = archived_path.read_text(encoding="utf-8")

        # Force rename to fail.
        reopen_fp = compute_target_fp(archived_path)
        real_rename = Path.rename
        def failing_rename(self_path: Path, target: Path) -> Path:
            if self_path == archived_path:
                raise OSError("simulated rename failure")
            return real_rename(self_path, target)

        with patch.object(Path, "rename", failing_rename):
            reopen_resp = engine_execute(
                action="reopen",
                ticket_id=ticket_id,
                fields={"reopen_reason": "Should fail"},
                session_id="f1-rename-sess",
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

        assert reopen_resp.state == "escalate"
        assert reopen_resp.error_code == "io_error"
        # Ticket must still be in closed-tickets/ with original content (not status: open).
        assert archived_path.exists()
        assert archived_path.read_text(encoding="utf-8") == original_text
        assert "wontfix" in original_text  # original closed status preserved

    def test_reopen_write_failure_after_rename_rolls_back(self, tmp_tickets: Path) -> None:
        """If write_text fails after un-archive rename, ticket is moved back."""
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Write fail", "problem": "Will fail write"},
            session_id="f1-write-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Will fail write", []),
        )
        assert resp.state == "ok_create"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])

        fp = compute_target_fp(ticket_path)
        close_resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
            fields={"resolution": "wontfix", "archive": True},
            session_id="f1-write-sess",
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
        assert close_resp.state == "ok_close_archived"
        archived_path = Path(close_resp.data["ticket_path"])
        original_text = archived_path.read_text(encoding="utf-8")

        # Force write_text to fail on the post-rename destination.
        reopen_fp = compute_target_fp(archived_path)
        active_dst = tmp_tickets / archived_path.name
        real_write_text = Path.write_text
        def failing_write(self_path: Path, data: str, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> None:
            if self_path == active_dst:
                raise OSError("simulated write failure")
            real_write_text(self_path, data, encoding=encoding, errors=errors, newline=newline)

        with patch.object(Path, "write_text", failing_write):
            reopen_resp = engine_execute(
                action="reopen",
                ticket_id=ticket_id,
                fields={"reopen_reason": "Should fail write"},
                session_id="f1-write-sess",
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

        assert reopen_resp.state == "escalate"
        assert reopen_resp.error_code == "io_error"
        # Ticket must be rolled back to closed-tickets/ with original content.
        assert archived_path.exists()
        assert archived_path.read_text(encoding="utf-8") == original_text
        assert not active_dst.exists()

    def test_reopen_write_and_rollback_both_fail_reports_inconsistency(self, tmp_tickets: Path) -> None:
        """If write fails and rollback rename also fails, message warns about inconsistent state."""
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Double fault", "problem": "Both will fail"},
            session_id="f1-dbl-sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Both will fail", []),
        )
        assert resp.state == "ok_create"
        ticket_id = resp.ticket_id
        ticket_path = Path(resp.data["ticket_path"])

        fp = compute_target_fp(ticket_path)
        close_resp = engine_execute(
            action="close",
            ticket_id=ticket_id,
            fields={"resolution": "wontfix", "archive": True},
            session_id="f1-dbl-sess",
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
        assert close_resp.state == "ok_close_archived"
        archived_path = Path(close_resp.data["ticket_path"])

        reopen_fp = compute_target_fp(archived_path)
        active_dst = tmp_tickets / archived_path.name
        real_write_text = Path.write_text
        real_rename = Path.rename
        rename_call_count = 0

        def failing_write(self_path: Path, data: str, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> None:
            if self_path == active_dst:
                raise OSError("simulated write failure")
            real_write_text(self_path, data, encoding=encoding, errors=errors, newline=newline)

        def failing_rollback_rename(self_path: Path, target: Path) -> Path:
            nonlocal rename_call_count
            rename_call_count += 1
            # First rename (un-archive) succeeds; second (rollback) fails.
            if rename_call_count >= 2:
                raise OSError("simulated rollback failure")
            return real_rename(self_path, target)

        with patch.object(Path, "write_text", failing_write), \
             patch.object(Path, "rename", failing_rollback_rename):
            reopen_resp = engine_execute(
                action="reopen",
                ticket_id=ticket_id,
                fields={"reopen_reason": "Should double-fault"},
                session_id="f1-dbl-sess",
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

        assert reopen_resp.state == "escalate"
        assert reopen_resp.error_code == "io_error"
        assert "ROLLBACK ALSO FAILED" in reopen_resp.message


# ---------------------------------------------------------------------------
# F2: Pipeline plan -> execute for non-create must provide target_fingerprint
# ---------------------------------------------------------------------------

class TestF2PlanFingerprint:
    """Repro: plan(update) -> preflight -> execute(update) must not policy_block."""

    def test_plan_returns_target_fingerprint_for_update_via_ticket_id_param(self, tmp_tickets: Path) -> None:
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
            fields={"priority": "critical"},
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
            fields={"priority": "critical"},
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
        assert exec_resp.state == "ok_update"

    def test_plan_via_entrypoint_payload(self, tmp_tickets: Path) -> None:
        """PlanInput.from_payload extracts top-level ticket_id."""
        from scripts.ticket_stage_models import PlanInput

        payload = {
            "action": "update",
            "ticket_id": "T-20260302-04",
            "session_id": "f2-sess",
            "fields": {"priority": "critical"},
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
            "fields": {"priority": "critical"},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=str(project_root),
        ) as f:
            json.dump(payload, f)
            payload_path = f.name

        user_script = Path(__file__).parent.parent / "scripts" / "ticket_engine_user.py"
        result = subprocess.run(
            [sys.executable, str(user_script), "plan", payload_path],
            capture_output=True, text=True, timeout=10, cwd=str(project_root),
        )
        Path(payload_path).unlink()
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["state"] == "ok"
        assert data["data"]["target_fingerprint"] is not None


# ---------------------------------------------------------------------------
# F3a: Agent create-cap must not count user creates
# ---------------------------------------------------------------------------

class TestF3aOriginFilter:
    """Repro: user create should not consume agent budget."""

    def test_user_creates_do_not_count_toward_agent_cap(self, tmp_tickets: Path) -> None:
        session_id = "f3a-sess"
        # Create as user.
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
        # Agent count should be 0.
        assert engine_count_session_creates(session_id, tmp_tickets, request_origin="agent") == 0
        # User count should be 1.
        assert engine_count_session_creates(session_id, tmp_tickets, request_origin="user") == 1


# ---------------------------------------------------------------------------
# F3b: Failed result audit write must escalate for agents
# ---------------------------------------------------------------------------

class TestF3bAuditResultFailClose:
    """Repro: agent create succeeds but result audit write fails."""

    def test_agent_create_escalates_on_result_audit_failure(self, tmp_tickets: Path) -> None:
        import scripts.ticket_engine_core as core_mod

        write_autonomy_config(tmp_tickets, "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n")
        config = AutonomyConfig(mode="auto_audit", max_creates=5)

        # attempt_started writes to disk, result entry fails.
        real_audit_append = core_mod._audit_append
        call_count = 0

        def patched_audit_append(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return real_audit_append(*args, **kwargs)
            return False  # result entry fails

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
        assert resp.state == "escalate"
        assert "audit" in resp.message.lower()

    def test_cap_sealed_after_result_audit_failure(self, tmp_tickets: Path) -> None:
        """After result-audit failure, attempt_started seals the count."""
        import scripts.ticket_engine_core as core_mod

        write_autonomy_config(tmp_tickets, "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 1\n---\n")
        config = AutonomyConfig(mode="auto_audit", max_creates=1)

        # First create: attempt_started writes to disk, result fails.
        real_audit_append = core_mod._audit_append
        call_count = 0

        def patched_audit_append(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return real_audit_append(*args, **kwargs)  # attempt_started writes to disk
            return False  # result entry fails

        with patch("scripts.ticket_engine_core._audit_append", side_effect=patched_audit_append):
            engine_execute(
                action="create",
                ticket_id=None,
                fields={"title": "First agent ticket", "problem": "First issue"},
                session_id="f3b-cap-sess",
                request_origin="agent",
                dedup_override=False,
                dependency_override=False,
                tickets_dir=tmp_tickets,
                autonomy_config=config,
                hook_injected=True,
                hook_request_origin="agent",
                classify_intent="create",
                classify_confidence=0.95,
                dedup_fingerprint=compute_dedup_fp("First issue", []),
            )

        # Count must be 1 (from attempt_started), sealing the cap.
        count = engine_count_session_creates("f3b-cap-sess", tmp_tickets, request_origin="agent")
        assert count == 1

        # Second create attempt: must be blocked by cap.
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
        assert "cap" in preflight_resp.message.lower() or "1/1" in preflight_resp.message

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
        assert resp.state == "ok_create"


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
            capture_output=True, text=True, timeout=10, cwd=str(subdir),
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
            capture_output=True, text=True, timeout=10, cwd=str(subdir),
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
            capture_output=True, text=True, timeout=10, cwd=str(isolated),
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["state"] == "policy_blocked"
        assert "project root" in data["message"].lower()


# ---------------------------------------------------------------------------
# F5: source dict without "type" key must return validation error, not crash
# ---------------------------------------------------------------------------

class TestF5SourceValidation:
    """Repro: source={"ref":"x"} should fail validation, not KeyError."""

    def test_source_without_type_returns_validation_error(self) -> None:
        errors = validate_fields({"source": {"ref": "x"}})
        assert any("type" in e for e in errors)

    def test_source_with_all_required_keys_passes(self) -> None:
        errors = validate_fields({"source": {"type": "ad-hoc", "ref": "x", "session": ""}})
        assert not errors

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
