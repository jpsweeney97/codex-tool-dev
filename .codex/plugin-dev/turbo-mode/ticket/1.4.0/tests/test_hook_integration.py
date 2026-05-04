"""Integration tests — hook subprocess → engine subprocess → audit trail.

Exercises the full production flow: the PreToolUse hook validates and injects
trust fields into a payload file, then the user entrypoint subprocess reads
that payload and runs the engine, which writes an audit trail.

Both the hook and entrypoint are invoked via subprocess.run with
sys.executable, matching how Codex invokes them in production.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PLUGIN_ROOT = str(Path(__file__).parent.parent)
HOOK_SCRIPT = str(Path(__file__).parent.parent / "hooks" / "ticket_engine_guard.py")
USER_ENTRYPOINT = str(Path(__file__).parent.parent / "scripts" / "ticket_engine_user.py")
AGENT_ENTRYPOINT = str(Path(__file__).parent.parent / "scripts" / "ticket_engine_agent.py")


def run_hook(
    command: str,
    session_id: str = "integration-sess",
    cwd: str = "/",
    *,
    agent_id: str | None = None,
    agent_type: str | None = None,
) -> dict:
    """Run the hook with a Bash command and return parsed output."""
    hook_input = {
        "session_id": session_id,
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": cwd,
        "permission_mode": "default",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_use_id": "toolu_integration",
    }
    if agent_id is not None:
        hook_input["agent_id"] = agent_id
    if agent_type is not None:
        hook_input["agent_type"] = agent_type
    env = {**os.environ, "CODEX_PLUGIN_ROOT": PLUGIN_ROOT}
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(hook_input),
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert result.returncode == 0, f"Hook crashed: {result.stderr}"
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


class TestFullCreateFlow:
    """Full flow: hook → user entrypoint → create → audit trail."""

    def test_full_create_flow(self, tmp_path: Path) -> None:
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        # Marker needed for discover_project_root() in entrypoint.
        (tmp_path / ".git").mkdir(exist_ok=True)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        problem = "Testing the full hook-engine-audit flow."
        # Create payload file with create action and required fields.
        payload = {
            "action": "create",
            "fields": {
                "title": "Integration test ticket",
                "problem": problem,
                "priority": "medium",
            },
            "tickets_dir": str(tickets_dir),
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_fp(problem, []),
        }
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        # Step 1: Run hook — verify allow + payload injected.
        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute {payload_file}"
        hook_output = run_hook(command, session_id="integration-sess", cwd=str(tmp_path))
        assert hook_output != {}, "Hook should return a decision for ticket_engine commands"
        decision = hook_output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

        # Verify hook injected trust fields into the payload file.
        injected = json.loads(payload_file.read_text(encoding="utf-8"))
        assert injected["hook_injected"] is True
        assert injected["session_id"] == "integration-sess"
        assert injected["hook_request_origin"] == "user"

        # Step 2: Run user entrypoint subprocess — verify ok_create.
        result = subprocess.run(
            [sys.executable, USER_ENTRYPOINT, "execute", str(payload_file)],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=10,
        )
        assert result.returncode == 0, f"Entrypoint failed: {result.stderr}"
        resp = json.loads(result.stdout)
        assert resp["state"] == "ok_create"

        # Step 3: Read audit file — verify 2 entries (attempt_started + ok_create).
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_file = tickets_dir / ".audit" / date_dir / "integration-sess.jsonl"
        assert audit_file.exists(), f"Audit file not found at {audit_file}"

        lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        assert len(lines) == 2
        assert lines[0]["action"] == "attempt_started"
        assert lines[1]["action"] == "create"
        assert lines[1]["result"] == "ok_create"

        # Step 4: Verify session_id in audit matches what hook injected.
        assert lines[0]["session_id"] == "integration-sess"
        assert lines[1]["session_id"] == "integration-sess"


class TestHookDenyPreventsExecution:
    """Denied commands don't reach the engine."""

    def test_hook_deny_prevents_execution(self, tmp_path: Path) -> None:
        payload = {"action": "create"}
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        # Command with extra args after payload path triggers deny.
        command = (
            f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute "
            f"{payload_file} --verbose"
        )
        hook_output = run_hook(command, cwd=str(tmp_path))

        # Verify deny.
        decision = hook_output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"

        # Verify payload NOT modified (no hook_injected field).
        raw = json.loads(payload_file.read_text(encoding="utf-8"))
        assert "hook_injected" not in raw


class TestHookSessionIdPropagatesToAudit:
    """Session ID propagates end-to-end: hook → payload → engine → audit."""

    def test_hook_session_id_propagates_to_audit(self, tmp_path: Path) -> None:
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        # Marker needed for discover_project_root() in entrypoint.
        (tmp_path / ".git").mkdir(exist_ok=True)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        unique_session = "unique-sess-xyz"
        problem = "Verify session_id flows through entire pipeline."
        payload = {
            "action": "create",
            "fields": {
                "title": "Session propagation test",
                "problem": problem,
                "priority": "low",
            },
            "tickets_dir": str(tickets_dir),
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_fp(problem, []),
        }
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        # Step 1: Run hook with specific session_id.
        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute {payload_file}"
        hook_output = run_hook(command, session_id=unique_session, cwd=str(tmp_path))
        assert hook_output["hookSpecificOutput"]["permissionDecision"] == "allow"

        # Step 2: Run entrypoint.
        result = subprocess.run(
            [sys.executable, USER_ENTRYPOINT, "execute", str(payload_file)],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=10,
        )
        assert result.returncode == 0, f"Entrypoint failed: {result.stderr}"

        # Step 3: Verify audit file exists at path with that session_id.
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_file = tickets_dir / ".audit" / date_dir / f"{unique_session}.jsonl"
        assert audit_file.exists(), f"Audit file not found at {audit_file}"

        # Step 4: Verify session_id in audit entries matches.
        lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        assert len(lines) >= 2
        for entry in lines:
            assert entry["session_id"] == unique_session


class TestPatch1Integration:
    """End-to-end: hook → entrypoint → engine with full staged payload."""

    def test_canonical_create_flow_with_staged_payload(self, tmp_path: Path) -> None:
        """Full trust path: hook injects trust fields, entrypoint validates,
        engine checks structural prerequisites."""
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        # Marker needed for discover_project_root() in entrypoint.
        (tmp_path / ".git").mkdir(exist_ok=True)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        problem = "Integration test problem for Patch 1"
        fp = compute_fp(problem, [])
        payload = {
            "action": "create",
            "fields": {
                "title": "Patch 1 Integration Test",
                "problem": problem,
                "priority": "medium",
            },
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": fp,
            "tickets_dir": str(tickets_dir),
        }
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        # Hook injection
        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute {payload_file}"
        hook_output = run_hook(command, session_id="integration-session", cwd=str(tmp_path))
        assert hook_output != {}, "Hook should return a decision for ticket_engine commands"
        assert hook_output["hookSpecificOutput"]["permissionDecision"] == "allow"

        # Verify payload was injected with trust triple
        injected = json.loads(payload_file.read_text(encoding="utf-8"))
        assert injected["hook_injected"] is True
        assert injected["hook_request_origin"] == "user"
        assert injected["session_id"] == "integration-session"

    def test_bypass_attempt_blocked_end_to_end(self, tmp_path: Path) -> None:
        """Leading-space bypass attempt is caught by prefilter."""
        payload = {"action": "create"}
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        # Leading space before python3 — shlex prefilter should catch this
        command = f" python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute {payload_file}"
        hook_output = run_hook(command, cwd=str(tmp_path))
        assert hook_output != {}, "Hook should return a decision"
        assert hook_output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestOriginMismatchIntegration:
    def test_agent_hook_origin_rejects_user_entrypoint(self, tmp_path: Path) -> None:
        # Marker needed for discover_project_root() in entrypoint.
        (tmp_path / ".git").mkdir(exist_ok=True)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps({
            "action": "create",
            "fields": {"title": "Mismatch", "problem": "Mismatch", "priority": "low"},
            "tickets_dir": str(tickets_dir),
        }), encoding="utf-8")

        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute {payload_file}"
        hook_output = run_hook(
            command,
            cwd=str(tmp_path),
            agent_id="agent-123",
            agent_type="reviewer",
        )
        assert hook_output["hookSpecificOutput"]["permissionDecision"] == "allow"

        result = subprocess.run(
            [sys.executable, USER_ENTRYPOINT, "execute", str(payload_file)],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=10,
        )
        assert result.returncode == 1
        resp = json.loads(result.stdout)
        assert resp["error_code"] == "origin_mismatch"

    def test_user_hook_origin_rejects_agent_entrypoint(self, tmp_path: Path) -> None:
        # Marker needed for discover_project_root() in entrypoint.
        (tmp_path / ".git").mkdir(exist_ok=True)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps({
            "action": "create",
            "fields": {"title": "Mismatch", "problem": "Mismatch", "priority": "low"},
            "tickets_dir": str(tickets_dir),
        }), encoding="utf-8")

        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_agent.py execute {payload_file}"
        hook_output = run_hook(command, cwd=str(tmp_path))
        assert hook_output["hookSpecificOutput"]["permissionDecision"] == "allow"

        result = subprocess.run(
            [sys.executable, AGENT_ENTRYPOINT, "execute", str(payload_file)],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=10,
        )
        assert result.returncode == 1
        resp = json.loads(result.stdout)
        assert resp["error_code"] == "origin_mismatch"
