"""Integration tests for hook subprocess to engine subprocess flow.

Exercises the full production flow: the PreToolUse hook validates and injects
trust fields into a payload file, then the user entrypoint subprocess reads
that payload and runs the engine.

Both the hook and entrypoint are invoked via subprocess.run with
sys.executable, matching how Codex invokes them in production.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
    normalize: bool = True,
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
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 0, f"Hook crashed: {result.stderr}"
    if not result.stdout.strip():
        raw: dict = {}
    else:
        raw = json.loads(result.stdout)
    return _normalize_hook_output(raw) if normalize else raw


def _normalize_hook_output(raw: dict) -> dict:
    if "hookSpecificOutput" in raw:
        return raw
    if raw == {}:
        return {}
    entries = raw.get("entries", [])
    if not entries:
        return {}
    first = entries[0]
    kind = first.get("kind", "")
    text = first.get("text", "")
    decision = "allow" if kind in {"feedback", "context"} else "deny"
    return {
        "hookSpecificOutput": {
            "permissionDecision": decision,
            "permissionDecisionReason": text,
        },
        "_raw": raw,
    }


class TestFullCreateFlow:
    """Full flow: hook to user entrypoint to create without future audit writes."""

    def test_hook_raw_allow_contract_uses_feedback_entries(self, tmp_path: Path) -> None:
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps({"action": "create"}), encoding="utf-8")

        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py plan {payload_file}"
        hook_output = run_hook(command, cwd=str(tmp_path), normalize=False)

        assert hook_output["entries"][0]["kind"] == "feedback"
        assert "validated" in hook_output["entries"][0]["text"]

    def test_hook_raw_deny_contract_uses_stop_entries(self, tmp_path: Path) -> None:
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps({"action": "create"}), encoding="utf-8")

        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py plan {payload_file} | cat"
        hook_output = run_hook(command, cwd=str(tmp_path), normalize=False)

        assert hook_output["entries"][0]["kind"] == "stop"
        assert {entry["kind"] for entry in hook_output["entries"]} == {"stop"}
        assert not any(entry["kind"] == "feedback" for entry in hook_output["entries"])
        assert "metacharacters" in hook_output["entries"][0]["text"].lower()

    def test_full_create_flow(self, tmp_path: Path) -> None:
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        # Marker needed for discover_project_root() in entrypoint.
        (tmp_path / ".git").mkdir(exist_ok=True)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        problem = "Testing the full hook-engine flow."
        # Create payload file with create action and required fields.
        payload = {
            "action": "create",
            "fields": {
                "title": "Integration test ticket",
                "problem": problem,
                "priority": "normal",
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

        # Step 2: Run user entrypoint subprocess — verify ok.
        result = subprocess.run(
            [sys.executable, USER_ENTRYPOINT, "execute", str(payload_file)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=10,
        )
        assert result.returncode == 0, f"Entrypoint failed: {result.stderr}"
        resp = json.loads(result.stdout)
        assert resp["state"] == "ok"

        # Step 3: Verify the ticket exists and future runtime does not create `.audit`.
        ticket_path = Path(resp["data"]["ticket_path"])
        assert ticket_path.exists()
        assert not (tickets_dir / ".audit").exists()


class TestHookDenyPreventsExecution:
    """Denied commands don't reach the engine."""

    def test_hook_deny_prevents_execution(self, tmp_path: Path) -> None:
        payload = {"action": "create"}
        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        # Command with extra args after payload path triggers deny.
        command = (
            f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_user.py execute {payload_file} --verbose"
        )
        hook_output = run_hook(command, cwd=str(tmp_path))

        # Verify deny.
        decision = hook_output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"

        # Verify payload NOT modified (no hook_injected field).
        raw = json.loads(payload_file.read_text(encoding="utf-8"))
        assert "hook_injected" not in raw


class TestHookSessionIdPropagatesToPayload:
    """Session ID propagates from hook into the engine payload."""

    def test_hook_session_id_propagates_to_payload_without_audit_write(
        self, tmp_path: Path
    ) -> None:
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
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=10,
        )
        assert result.returncode == 0, f"Entrypoint failed: {result.stderr}"

        # Step 3: Verify session_id remains in the payload and no future audit file is written.
        injected = json.loads(payload_file.read_text(encoding="utf-8"))
        assert injected["session_id"] == unique_session
        assert not (tickets_dir / ".audit").exists()


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
                "priority": "normal",
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
        payload_file.write_text(
            json.dumps(
                {
                    "action": "create",
                    "fields": {"title": "Mismatch", "problem": "Mismatch", "priority": "low"},
                    "tickets_dir": str(tickets_dir),
                }
            ),
            encoding="utf-8",
        )

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
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=10,
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
        payload_file.write_text(
            json.dumps(
                {
                    "action": "create",
                    "fields": {"title": "Mismatch", "problem": "Mismatch", "priority": "low"},
                    "tickets_dir": str(tickets_dir),
                }
            ),
            encoding="utf-8",
        )

        command = f"python3 {PLUGIN_ROOT}/scripts/ticket_engine_agent.py execute {payload_file}"
        hook_output = run_hook(command, cwd=str(tmp_path))
        assert hook_output["hookSpecificOutput"]["permissionDecision"] == "allow"

        result = subprocess.run(
            [sys.executable, AGENT_ENTRYPOINT, "execute", str(payload_file)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=10,
        )
        assert result.returncode == 1
        resp = json.loads(result.stdout)
        assert resp["state"] == "policy_blocked"
        assert "classify_intent" in resp["message"]
