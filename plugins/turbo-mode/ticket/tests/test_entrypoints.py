"""Tests for engine entrypoints — ticket_engine_user.py and ticket_engine_agent.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Path to scripts directory.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def run_entrypoint(script: str, subcommand: str, payload: dict, tmp_path: Path) -> dict:
    """Run an entrypoint script as a subprocess and return parsed JSON output."""
    # Ensure cwd has a project-root marker so discover_project_root() succeeds.
    git_marker = tmp_path / ".git"
    if not git_marker.exists():
        git_marker.mkdir()

    payload_file = tmp_path / "input.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), subcommand, str(payload_file)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode in (0, 1, 2), f"Unexpected exit code: {result.returncode}\nstderr: {result.stderr}"
    return json.loads(result.stdout)


class TestUserEntrypoint:
    def test_classify_create(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_user.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert output["state"] == "ok"
        assert output["data"]["intent"] == "create"

    def test_origin_is_user(self, tmp_path):
        """The user entrypoint always sets request_origin=user."""
        output = run_entrypoint(
            "ticket_engine_user.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "request_origin": "agent",  # Caller tries to override — ignored.
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        # Should succeed because origin is forced to "user".
        assert output["state"] == "ok"

    def test_user_entrypoint_rejects_hook_agent_origin(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_user.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "hook_request_origin": "agent",
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert output["error_code"] == "origin_mismatch"


class TestAgentEntrypoint:
    def test_classify_create(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert output["state"] == "ok"
        assert output["data"]["intent"] == "create"

    def test_origin_is_agent(self, tmp_path):
        """The agent entrypoint always sets request_origin=agent."""
        # Agent classify succeeds, but preflight would block in suggest mode.
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert output["state"] == "ok"

    def test_execute_blocked_phase1(self, tmp_path):
        """Agent execute is hard-blocked in Phase 1 (defense-in-depth)."""
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "execute",
            {
                "action": "create",
                "fields": {"title": "test", "problem": "test", "priority": "medium"},
                "session_id": "test",
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert output["state"] == "policy_blocked"

    def test_agent_entrypoint_rejects_hook_user_origin(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "hook_request_origin": "user",
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert output["error_code"] == "origin_mismatch"


class TestMalformedAutonomyConfig:
    """Malformed autonomy_config payloads must not crash entrypoints."""

    @pytest.mark.parametrize("bad_value", ["not-a-dict", ["a", "list"], 42, True])
    def test_user_execute_with_bad_autonomy_config(self, tmp_path, bad_value):
        """Non-dict autonomy_config is ignored, not deserialized."""
        output = run_entrypoint(
            "ticket_engine_user.py",
            "execute",
            {
                "action": "create",
                "fields": {"title": "test", "problem": "test"},
                "session_id": "test",
                "hook_injected": True,
                "hook_request_origin": "user",
                "autonomy_config": bad_value,
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        # Should produce a structured response, not crash.
        assert "state" in output

    @pytest.mark.parametrize("bad_value", ["not-a-dict", ["a", "list"], 42, True])
    def test_agent_execute_with_bad_autonomy_config(self, tmp_path, bad_value):
        """Non-dict autonomy_config is ignored, not deserialized."""
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "execute",
            {
                "action": "create",
                "fields": {"title": "test", "problem": "test"},
                "session_id": "test",
                "hook_injected": True,
                "hook_request_origin": "agent",
                "autonomy_config": bad_value,
                "tickets_dir": str(tmp_path),
            },
            tmp_path,
        )
        assert "state" in output


class TestEntrypointErrors:
    def test_missing_subcommand(self, tmp_path):
        payload_file = tmp_path / "input.json"
        payload_file.write_text("{}", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ticket_engine_user.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_invalid_json(self, tmp_path):
        payload_file = tmp_path / "input.json"
        payload_file.write_text("not json", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ticket_engine_user.py"), "classify", str(payload_file)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode != 0


class TestExecuteTrustTriple:
    """Execute requires the full trust triple at the entrypoint layer."""

    def test_user_execute_without_hook_rejected(self, tmp_path):
        """User execute without hook_injected is rejected."""
        payload = {
            "action": "create",
            "fields": {"title": "Test", "problem": "Problem", "priority": "medium"},
        }
        result = run_entrypoint("ticket_engine_user.py", "execute", payload, tmp_path)
        assert result.get("error_code") == "policy_blocked" or result.get("state") == "policy_blocked"

    def test_user_execute_without_session_id_rejected(self, tmp_path):
        """User execute with hook_injected but empty session_id is rejected."""
        payload = {
            "action": "create",
            "fields": {"title": "Test", "problem": "Problem", "priority": "medium"},
            "hook_injected": True,
            "hook_request_origin": "user",
            "session_id": "",
        }
        result = run_entrypoint("ticket_engine_user.py", "execute", payload, tmp_path)
        assert result.get("error_code") == "policy_blocked" or result.get("state") == "policy_blocked"

    def test_user_execute_without_hook_request_origin_rejected(self, tmp_path):
        """User execute with hook_injected but missing hook_request_origin is rejected."""
        payload = {
            "action": "create",
            "fields": {"title": "Test", "problem": "Problem", "priority": "medium"},
            "hook_injected": True,
            "session_id": "test-session",
            # hook_request_origin missing
        }
        result = run_entrypoint("ticket_engine_user.py", "execute", payload, tmp_path)
        assert result.get("error_code") in ("policy_blocked", "origin_mismatch") or result.get("state") == "policy_blocked"

    def test_agent_execute_without_hook_rejected(self, tmp_path):
        """Agent execute without hook_injected is rejected."""
        payload = {
            "action": "create",
            "fields": {"title": "Test", "problem": "Problem", "priority": "medium"},
        }
        result = run_entrypoint("ticket_engine_agent.py", "execute", payload, tmp_path)
        assert result.get("error_code") == "policy_blocked" or result.get("state") == "policy_blocked"

    def test_user_classify_without_hook_allowed(self, tmp_path):
        """Non-execute stages remain directly runnable without hook metadata."""
        payload = {"action": "create", "args": {}}
        result = run_entrypoint("ticket_engine_user.py", "classify", payload, tmp_path)
        assert result.get("state") == "ok"

    def test_user_plan_without_hook_allowed(self, tmp_path):
        """Plan stage works without hook metadata."""
        payload = {
            "action": "create",
            "intent": "create",
            "fields": {"title": "Test", "problem": "Problem", "priority": "medium"},
        }
        result = run_entrypoint("ticket_engine_user.py", "plan", payload, tmp_path)
        assert result.get("state") in ("ok", "duplicate_candidate")

    def test_user_execute_with_full_trust_triple_allowed(self, tmp_path):
        """User execute with complete trust triple succeeds."""
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        problem = "Problem"
        payload = {
            "action": "create",
            "fields": {"title": "Test", "problem": problem, "priority": "medium"},
            "hook_injected": True,
            "hook_request_origin": "user",
            "session_id": "test-session",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_fp(problem, []),
        }
        result = run_entrypoint("ticket_engine_user.py", "execute", payload, tmp_path)
        assert result.get("state") == "ok_create"


class TestEntrypointTicketsDirBoundaries:
    def test_user_rejects_tickets_dir_outside_project_root(self, tmp_path: Path):
        outside = tmp_path.parent / "outside-tickets"
        output = run_entrypoint(
            "ticket_engine_user.py",
            "execute",
            {
                "action": "create",
                "fields": {"title": "test", "problem": "test"},
                "session_id": "test",
                "hook_injected": True,
                "hook_request_origin": "user",
                "tickets_dir": str(outside),
            },
            tmp_path,
        )
        assert output["state"] == "policy_blocked"
        assert output["error_code"] == "policy_blocked"

    def test_user_allows_absolute_tickets_dir_inside_project_root(self, tmp_path: Path):
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        in_root = tmp_path / "docs" / "tickets"
        problem = "test"
        output = run_entrypoint(
            "ticket_engine_user.py",
            "execute",
            {
                "action": "create",
                "fields": {"title": "test", "problem": problem},
                "session_id": "test",
                "hook_injected": True,
                "hook_request_origin": "user",
                "tickets_dir": str(in_root),
                "classify_intent": "create",
                "classify_confidence": 0.95,
                "dedup_fingerprint": compute_fp(problem, []),
            },
            tmp_path,
        )
        assert output["state"] == "ok_create"

    def test_agent_rejects_tickets_dir_outside_project_root(self, tmp_path: Path):
        outside = tmp_path.parent / "outside-tickets"
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "execute",
            {
                "action": "create",
                "fields": {"title": "test", "problem": "test"},
                "session_id": "test",
                "hook_injected": True,
                "hook_request_origin": "agent",
                "tickets_dir": str(outside),
            },
            tmp_path,
        )
        assert output["state"] == "policy_blocked"
        assert output["error_code"] == "policy_blocked"

    def test_agent_allows_absolute_tickets_dir_inside_project_root(self, tmp_path: Path):
        in_root = tmp_path / "docs" / "tickets"
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "classify",
            {
                "action": "create",
                "args": {},
                "session_id": "test",
                "tickets_dir": str(in_root),
            },
            tmp_path,
        )
        assert output["state"] == "ok"


class TestPayloadValidation:
    """Entrypoints translate PayloadError into structured EngineResponse."""

    def test_classify_bad_args_type_returns_parse_error(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_user.py",
            "classify",
            {
                "action": "create",
                "args": "not a dict",
                "session_id": "test",
            },
            tmp_path,
        )
        assert output["state"] == "escalate"
        assert output["error_code"] == "parse_error"
        assert "classify" in output["message"].lower()

    def test_execute_bad_fields_type_returns_parse_error(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_user.py",
            "execute",
            {
                "action": "create",
                "fields": "not a dict",
                "session_id": "test",
                "hook_injected": True,
                "hook_request_origin": "user",
            },
            tmp_path,
        )
        assert output["state"] == "escalate"
        assert output["error_code"] == "parse_error"
        assert "execute" in output["message"].lower()

    def test_agent_entrypoint_also_validates(self, tmp_path):
        output = run_entrypoint(
            "ticket_engine_agent.py",
            "classify",
            {
                "action": "create",
                "args": 42,
                "session_id": "test",
            },
            tmp_path,
        )
        assert output["state"] == "escalate"
        assert output["error_code"] == "parse_error"


class TestEntrypointProjectRootDiscovery:
    """Entrypoints use marker-based project root instead of bare cwd."""

    def _run_without_marker(self, script: str, tmp_path: Path) -> dict:
        """Run entrypoint from a cwd that has no project-root markers."""
        # Do NOT create .git or .codex — intentionally bare.
        nested = tmp_path / "no" / "markers"
        nested.mkdir(parents=True)
        payload_file = nested / "input.json"
        payload_file.write_text(
            json.dumps({"action": "create", "args": {}, "session_id": "test"}),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script), "classify", str(payload_file)],
            capture_output=True,
            text=True,
            cwd=str(nested),
        )
        assert result.returncode in (0, 1, 2), f"Unexpected exit code: {result.returncode}\nstderr: {result.stderr}"
        return json.loads(result.stdout)

    def test_user_rejects_when_no_project_root(self, tmp_path: Path) -> None:
        output = self._run_without_marker("ticket_engine_user.py", tmp_path)
        assert output["state"] == "policy_blocked"
        assert "project root" in output["message"]

    def test_agent_rejects_when_no_project_root(self, tmp_path: Path) -> None:
        output = self._run_without_marker("ticket_engine_agent.py", tmp_path)
        assert output["state"] == "policy_blocked"
        assert "project root" in output["message"]

    def test_user_resolves_from_nested_cwd(self, tmp_path: Path) -> None:
        """When cwd is nested inside a project, tickets_dir resolves against root."""
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        (tmp_path / ".git").mkdir(exist_ok=True)
        nested = tmp_path / "src" / "deep"
        nested.mkdir(parents=True)

        problem = "nested cwd test"
        payload = {
            "action": "create",
            "fields": {"title": "Test", "problem": problem, "priority": "medium"},
            "hook_injected": True,
            "hook_request_origin": "user",
            "session_id": "test-session",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_fp(problem, []),
        }
        payload_file = nested / "input.json"
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ticket_engine_user.py"), "execute", str(payload_file)],
            capture_output=True,
            text=True,
            cwd=str(nested),
        )
        output = json.loads(result.stdout)
        assert output["state"] == "ok_create"
        # Ticket should be created under project root, not under nested cwd.
        tickets_in_root = tmp_path / "docs" / "tickets"
        assert tickets_in_root.exists(), f"Expected tickets at {tickets_in_root}, not under {nested}"
