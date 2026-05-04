"""Tests for the ticket_engine_guard PreToolUse hook.

Tests invoke the hook via subprocess.run with JSON on stdin,
using sys.executable as the Python interpreter.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "ticket_engine_guard.py"


def run_hook(
    hook_input: dict,
    *,
    plugin_root: str | None = None,
) -> dict:
    """Send hook input JSON via stdin and return parsed output.

    Sets CODEX_PLUGIN_ROOT so the allowlist pattern matches the test paths.
    """
    env = {}
    if plugin_root is not None:
        env["CODEX_PLUGIN_ROOT"] = plugin_root

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        timeout=10,
        env={**dict(__import__("os").environ), **env} if env else None,
    )
    assert result.returncode == 0, f"Hook exited with {result.returncode}: {result.stderr}"
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def make_hook_input(
    command: str,
    *,
    plugin_root: str = "/fake/plugin",
    session_id: str = "test-session-123",
    tool_name: str = "Bash",
    cwd: str = "/",
) -> dict:
    """Build a hook stdin JSON payload."""
    return {
        "session_id": session_id,
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": cwd,
        "permission_mode": "default",
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"command": command},
        "tool_use_id": "toolu_01ABC123",
    }


def make_payload_file(tmp_path: Path, data: dict | None = None) -> Path:
    """Create a JSON payload file for testing."""
    payload = data if data is not None else {"action": "test"}
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def load_guard_module() -> ModuleType:
    """Load the hook module for direct unit tests of helper functions."""
    spec = importlib.util.spec_from_file_location("ticket_engine_guard", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decision(output: dict) -> str:
    """Extract permissionDecision from hook output."""
    return output["hookSpecificOutput"]["permissionDecision"]


def _reason(output: dict) -> str:
    """Extract permissionDecisionReason from hook output."""
    return output["hookSpecificOutput"]["permissionDecisionReason"]


# ---------------------------------------------------------------------------
# Allowlist tests
# ---------------------------------------------------------------------------


class TestAllowlist:
    """Tests for command allowlist matching."""

    def test_allows_user_entrypoint(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        scripts_dir = Path(plugin_root) / "scripts"
        scripts_dir.mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "allow"

    def test_allows_agent_entrypoint(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        scripts_dir = Path(plugin_root) / "scripts"
        scripts_dir.mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_agent.py classify {payload_file}",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "allow"

    def test_allows_user_entrypoint_with_dash_b(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 -B {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "allow"

    def test_allows_agent_entrypoint_with_dash_b(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 -B {plugin_root}/scripts/ticket_engine_agent.py classify {payload_file}",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "allow"

    def test_direct_core_import_passes_through(self) -> None:
        """python3 -c one-liners don't match _is_ticket_invocation — pass through.

        The 4-branch gate only matches `python3 <root>/scripts/ticket_*.py ...`
        invocations. `python3 -c '...'` is not a ticket script invocation, so it
        passes through as empty JSON (branch 4). The old substring gate denied
        this, but that was overly broad — the hook's contract is to gate ticket
        script execution, not all python invocations mentioning ticket internals.
        """
        inp = make_hook_input(
            "python3 -c 'from scripts.ticket_engine_core import engine_plan'",
            plugin_root="/fake/plugin",
        )
        output = run_hook(inp, plugin_root="/fake/plugin")
        assert output == {}

    def test_blocks_ticket_engine_with_extra_args(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        scripts_dir = Path(plugin_root) / "scripts"
        scripts_dir.mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file} --verbose",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "Extra arguments" in _reason(output)

    def test_allows_stderr_redirect_suffix(self, tmp_path: Path) -> None:
        """2>&1 is a diagnostic suffix, not injection — should be stripped and allowed."""
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        scripts_dir = Path(plugin_root) / "scripts"
        scripts_dir.mkdir(parents=True)
        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload_file} 2>&1",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "allow"

    def test_blocks_stderr_redirect_with_pipe_chained(self, tmp_path: Path) -> None:
        """2>&1 followed by a pipe is still injection and must be blocked."""
        plugin_root = str(tmp_path / "plugin")
        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan /tmp/p.json 2>&1 | cat",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "metacharacters" in _reason(output).lower()

    def test_blocks_ticket_engine_with_pipe(self, tmp_path: Path) -> None:
        plugin_root = str(tmp_path / "plugin")
        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan /tmp/p.json | cat",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "metacharacters" in _reason(output).lower()

    def test_blocks_ticket_engine_with_semicolon(self, tmp_path: Path) -> None:
        plugin_root = str(tmp_path / "plugin")
        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan /tmp/p.json; rm -rf /",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "metacharacters" in _reason(output).lower()

    def test_passthrough_non_ticket_command(self) -> None:
        inp = make_hook_input("ls -la /tmp")
        output = run_hook(inp)
        assert output == {}

    def test_passthrough_non_bash_tool(self) -> None:
        inp = make_hook_input("anything", plugin_root="/fake/plugin")
        inp["tool_name"] = "Write"
        output = run_hook(inp)
        assert output == {}

    def test_allows_all_valid_subcommands(self, tmp_path: Path) -> None:
        plugin_root = str(tmp_path / "plugin")
        scripts_dir = Path(plugin_root) / "scripts"
        scripts_dir.mkdir(parents=True)

        for subcommand in ("classify", "plan", "preflight", "execute"):
            payload_file = make_payload_file(tmp_path, {"action": subcommand})
            inp = make_hook_input(
                f"python3 {plugin_root}/scripts/ticket_engine_user.py {subcommand} {payload_file}",
                plugin_root=plugin_root,
            )
            output = run_hook(inp, plugin_root=plugin_root)
            assert _decision(output) == "allow", f"Failed for subcommand: {subcommand}"

    def test_blocks_unknown_subcommand(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path)
        plugin_root = str(tmp_path / "plugin")
        scripts_dir = Path(plugin_root) / "scripts"
        scripts_dir.mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py destroy {payload_file}",
            plugin_root=plugin_root,
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "Unknown subcommand" in _reason(output)


# ---------------------------------------------------------------------------
# Payload injection tests
# ---------------------------------------------------------------------------


class TestPayloadInjection:
    """Tests for trust field injection into payload files."""

    def test_injects_session_id(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "plan"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
            plugin_root=plugin_root,
            session_id="sess-abc-789",
        )
        inp["session_id"] = "sess-abc-789"
        run_hook(inp, plugin_root=plugin_root)

        result = json.loads(payload_file.read_text(encoding="utf-8"))
        assert result["session_id"] == "sess-abc-789"

    def test_injects_hook_injected_true(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "plan"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
            plugin_root=plugin_root,
        )
        run_hook(inp, plugin_root=plugin_root)

        result = json.loads(payload_file.read_text(encoding="utf-8"))
        assert result["hook_injected"] is True

    def test_injects_hook_request_origin_user(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "classify"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload_file}",
            plugin_root=plugin_root,
        )
        run_hook(inp, plugin_root=plugin_root)

        result = json.loads(payload_file.read_text(encoding="utf-8"))
        assert result["hook_request_origin"] == "user"

    def test_injects_hook_request_origin_agent(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "execute"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_agent.py execute {payload_file}",
            plugin_root=plugin_root,
        )
        run_hook(inp, plugin_root=plugin_root)

        result = json.loads(payload_file.read_text(encoding="utf-8"))
        assert result["hook_request_origin"] == "user"

    def test_injects_agent_origin_when_agent_id_present(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "classify"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload_file}",
            plugin_root=plugin_root,
        )
        inp["agent_id"] = "agent-123"
        run_hook(inp, plugin_root=plugin_root)

        result = json.loads(payload_file.read_text(encoding="utf-8"))
        assert result["hook_request_origin"] == "agent"

    def test_agent_type_without_agent_id_remains_user_origin(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "classify"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload_file}",
            plugin_root=plugin_root,
        )
        inp["agent_type"] = "Explore"
        run_hook(inp, plugin_root=plugin_root)

        result = json.loads(payload_file.read_text(encoding="utf-8"))
        assert result["hook_request_origin"] == "user"


def test_hook_allows_ticket_workflow_prepare_and_injects_payload(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_workflow.py prepare {payload}",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
    injected = json.loads(payload.read_text(encoding="utf-8"))
    assert injected["hook_injected"] is True
    assert injected["hook_request_origin"] == "user"


def test_hook_workflow_valid_agent_id_injects_agent_origin(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_workflow.py prepare {payload}",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )
    event["agent_id"] = "agent-123"

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
    injected = json.loads(payload.read_text(encoding="utf-8"))
    assert injected["hook_request_origin"] == "agent"


@pytest.mark.parametrize("agent_id", ["", None, 42])
def test_hook_workflow_malformed_agent_id_denied(tmp_path: Path, agent_id: object) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_workflow.py prepare {payload}",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )
    event["agent_id"] = agent_id

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Malformed agent_id" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_allows_ticket_workflow_recover_and_injects_payload(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","duplicate_of":"T-20260503-01","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_workflow.py recover {payload} create_anyway",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_hook_allows_ticket_workflow_recover_set_field_with_quoted_json(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        (
            f"python3 -B {plugin_root}/scripts/ticket_workflow.py "
            f"recover {payload} set_field tags '[\"ux\", \"ticket\"]'"
        ),
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_hook_denies_ticket_workflow_recover_set_field_shell_metacharacter_json(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        (
            f"python3 -B {plugin_root}/scripts/ticket_workflow.py "
            f"recover {payload} set_field note '{{\"note\":\"x>y\"}}'"
        ),
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "metacharacters" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()


def test_hook_allows_ticket_triage_doctor_with_expected_roots(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    event = make_hook_input(
        (
            f"python3 -B {plugin_root}/scripts/ticket_triage.py doctor {tickets_dir} "
            f"--plugin-root {plugin_root} --cache-root {plugin_root}"
        ),
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.parametrize("doctor_args", [
    "docs/tickets --plugin-root / --cache-root /",
    "docs/tickets --plugin-root /Users/jp --cache-root /Users/jp",
    "docs/tickets --cache-root /tmp/cache --plugin-root /tmp/plugin",
])
def test_hook_denies_ticket_triage_doctor_arbitrary_roots(tmp_path: Path, doctor_args: str) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_triage.py doctor {doctor_args}",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "doctor" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()


@pytest.mark.parametrize("command_template", [
    "/usr/bin/python3 {root}/scripts/ticket_workflow.py prepare {payload}",
    "python3.11 {root}/scripts/ticket_workflow.py prepare {payload}",
    "env python3 {root}/scripts/ticket_workflow.py prepare {payload}",
    "python3 -u {root}/scripts/ticket_workflow.py prepare {payload}",
    "python3 -X dev {root}/scripts/ticket_workflow.py prepare {payload}",
    "python3 -m pdb {root}/scripts/ticket_workflow.py prepare {payload}",
    "python3 -B -B {root}/scripts/ticket_workflow.py prepare {payload}",
    "python3 {root}/scripts/../scripts/ticket_workflow.py prepare {payload}",
    "python3 -B {root}/scripts/ticket_workflow.py prepare '{space_payload}'",
])
def test_hook_denies_noncanonical_ticket_workflow_command_shapes(
    tmp_path: Path,
    command_template: str,
) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    space_payload = tmp_path / "payload with spaces.json"
    space_payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        command_template.format(
            root=plugin_root,
            payload=payload,
            space_payload=space_payload,
        ),
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_denies_ticket_workflow_recover_without_action(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","duplicate_of":"T-20260503-01","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_workflow.py recover {payload}",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "requires a recovery action" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_denies_ticket_workflow_recover_set_field_missing_json_value(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_workflow.py recover {payload} set_field tags",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "expects 2 argument(s), got 1" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_denies_ticket_workflow_recover_set_field_extra_argument(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create","fields":{}}', encoding="utf-8")
    event = make_hook_input(
        (
            f"python3 -B {plugin_root}/scripts/ticket_workflow.py "
            f"recover {payload} set_field tags '[\"ux\"]' extra"
        ),
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "expects 2 argument(s), got 3" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_preserves_existing_payload_fields(tmp_path: Path) -> None:
    payload_file = make_payload_file(tmp_path, {
        "action": "plan",
        "ticket_id": "T-20260303-01",
        "custom_field": [1, 2, 3],
    })
    plugin_root = str(tmp_path / "plugin")
    (Path(plugin_root) / "scripts").mkdir(parents=True)

    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
        plugin_root=plugin_root,
    )
    run_hook(inp, plugin_root=plugin_root)

    result = json.loads(payload_file.read_text(encoding="utf-8"))
    assert result["action"] == "plan"
    assert result["ticket_id"] == "T-20260303-01"
    assert result["custom_field"] == [1, 2, 3]
    assert result["hook_injected"] is True


def test_atomic_write(tmp_path: Path) -> None:
    """After injection, file is valid JSON."""
    payload_file = make_payload_file(tmp_path, {"action": "preflight"})
    plugin_root = str(tmp_path / "plugin")
    (Path(plugin_root) / "scripts").mkdir(parents=True)

    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py preflight {payload_file}",
        plugin_root=plugin_root,
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "allow"

    result = json.loads(payload_file.read_text(encoding="utf-8"))
    assert isinstance(result, dict)
    assert result["hook_injected"] is True


def test_empty_session_id_denied_before_injection(tmp_path: Path) -> None:
    payload_file = make_payload_file(tmp_path, {"action": "plan"})
    plugin_root = str(tmp_path / "plugin")
    (Path(plugin_root) / "scripts").mkdir(parents=True)

    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
        plugin_root=plugin_root,
        session_id="",
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "deny"
    assert "Malformed session_id" in _reason(output)

    result = json.loads(payload_file.read_text(encoding="utf-8"))
    assert "hook_injected" not in result
    assert "hook_request_origin" not in result


def test_deny_on_unreadable_payload(tmp_path: Path) -> None:
    plugin_root = str(tmp_path / "plugin")
    (Path(plugin_root) / "scripts").mkdir(parents=True)
    nonexistent = tmp_path / "nonexistent.json"

    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {nonexistent}",
        plugin_root=plugin_root,
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "deny"
    assert "unreadable" in _reason(output).lower()


def test_deny_on_invalid_json_payload(tmp_path: Path) -> None:
    plugin_root = str(tmp_path / "plugin")
    (Path(plugin_root) / "scripts").mkdir(parents=True)
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json {{{", encoding="utf-8")

    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {bad_file}",
        plugin_root=plugin_root,
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "deny"
    assert "invalid json" in _reason(output).lower()


def test_deny_on_non_dict_payload(tmp_path: Path) -> None:
    """Rejects JSON arrays and other non-object payloads."""
    plugin_root = str(tmp_path / "plugin")
    (Path(plugin_root) / "scripts").mkdir(parents=True)
    array_file = tmp_path / "array.json"
    array_file.write_text("[1, 2, 3]", encoding="utf-8")

    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {array_file}",
        plugin_root=plugin_root,
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "deny"


def test_blocks_newline_injection(tmp_path: Path) -> None:
    """Blocks commands containing newlines (command injection vector)."""
    plugin_root = str(tmp_path / "plugin")
    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py plan /tmp/p.json\nrm -rf /",
        plugin_root=plugin_root,
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "deny"
    assert "metacharacters" in _reason(output).lower()


class TestPayloadPathBoundaries:
    def test_allows_payload_inside_workspace_root(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "plan"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
            plugin_root=plugin_root,
            cwd=str(tmp_path),
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "allow"

    def test_denies_relative_payload_path_for_engine_invocation(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "plan"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file.name}",
            plugin_root=plugin_root,
            cwd=str(tmp_path),
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "absolute" in _reason(output).lower()

    def test_denies_relative_payload_path_for_workflow_invocation(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "create", "fields": {}})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        inp = make_hook_input(
            f"python3 -B {plugin_root}/scripts/ticket_workflow.py prepare {payload_file.name}",
            plugin_root=plugin_root,
            cwd=str(tmp_path),
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "absolute" in _reason(output).lower()

    def test_denies_payload_outside_workspace_root(self, tmp_path: Path) -> None:
        payload_file = make_payload_file(tmp_path, {"action": "plan"})
        plugin_root = str(tmp_path / "plugin")
        (Path(plugin_root) / "scripts").mkdir(parents=True)

        outside_root = tmp_path / "workspace"
        outside_root.mkdir()

        inp = make_hook_input(
            f"python3 {plugin_root}/scripts/ticket_engine_user.py plan {payload_file}",
            plugin_root=plugin_root,
            cwd=str(outside_root),
        )
        output = run_hook(inp, plugin_root=plugin_root)
        assert _decision(output) == "deny"
        assert "outside workspace root" in _reason(output).lower()

    def test_payload_path_resolution_oserror_returns_deny_reason(self, monkeypatch: pytest.MonkeyPatch) -> None:
        guard = load_guard_module()

        def fail_resolve(_: Path) -> Path:
            raise OSError("permission denied")

        monkeypatch.setattr(guard.Path, "resolve", fail_resolve)
        resolved, err = guard._resolve_payload_path("/tmp/payload.json", "/tmp")
        assert resolved is None
        assert err is not None
        assert "resolution failed" in err.lower()


FAKE_ROOT = "/fake/plugin"


class TestReadAllowlist:
    def test_read_list_allowed(self):
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_read.py list /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"

    def test_read_query_allowed(self):
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_read.py query /tmp/tickets T-20260302",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"

    def test_read_no_payload_injection(self):
        """Read commands should pass through without modifying any files."""
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_read.py list /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"
        assert "validated (read-only)" in decision.get("permissionDecisionReason", "")

    def test_read_list_allowed_with_dash_b(self):
        result = run_hook(
            make_hook_input(
                f"python3 -B {FAKE_ROOT}/scripts/ticket_read.py list /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"


class TestTriageAllowlist:
    def test_triage_dashboard_allowed(self):
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_triage.py dashboard /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"

    def test_triage_dashboard_allowed_with_dash_b(self):
        result = run_hook(
            make_hook_input(
                f"python3 -B {FAKE_ROOT}/scripts/ticket_triage.py dashboard /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"

    def test_triage_audit_allowed(self):
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_triage.py audit /tmp/tickets --days 30",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"

    def test_triage_no_payload_injection(self):
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_triage.py dashboard /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert "validated (read-only)" in decision.get("permissionDecisionReason", "")


class TestAuditAllowlist:
    def test_audit_allowed_for_user(self):
        """ticket_audit.py is allowed for user invocations."""
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_audit.py repair /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"
        assert "audit" in decision.get("permissionDecisionReason", "").lower()

    def test_audit_denied_for_agent(self):
        """ticket_audit.py is denied for agent invocations."""
        hook_input = make_hook_input(
            f"python3 {FAKE_ROOT}/scripts/ticket_audit.py repair /tmp/tickets",
        )
        hook_input["agent_id"] = "subagent-123"
        result = run_hook(hook_input, plugin_root=FAKE_ROOT)
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"
        assert "user-only" in decision.get("permissionDecisionReason", "").lower()

    def test_audit_allowed_for_user_with_dash_b(self):
        result = run_hook(
            make_hook_input(
                f"python3 -B {FAKE_ROOT}/scripts/ticket_audit.py repair /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"
        assert "audit" in decision.get("permissionDecisionReason", "").lower()

    def test_audit_denied_for_agent_with_dash_b(self):
        hook_input = make_hook_input(
            f"python3 -B {FAKE_ROOT}/scripts/ticket_audit.py repair /tmp/tickets",
        )
        hook_input["agent_id"] = "subagent-123"
        result = run_hook(hook_input, plugin_root=FAKE_ROOT)
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"
        assert "user-only" in decision.get("permissionDecisionReason", "").lower()

    def test_audit_no_payload_injection(self):
        """Audit commands should pass through without modifying payload files."""
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_audit.py check /tmp/tickets",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "allow"
        assert "validated (user-only)" in decision.get("permissionDecisionReason", "")


class TestExecutionShapeMatching:
    def test_cat_ticket_file_passes_through(self):
        """Non-python commands on ticket files pass through (empty JSON)."""
        result = run_hook(
            make_hook_input(
                f"cat {FAKE_ROOT}/scripts/ticket_triage.py",
            ),
            plugin_root=FAKE_ROOT,
        )
        # cat is not a python invocation — passes through as empty dict
        assert result == {}

    def test_rg_ticket_file_passes_through(self):
        """rg/grep on ticket files pass through."""
        result = run_hook(
            make_hook_input(
                f"rg ticket_engine {FAKE_ROOT}/scripts/ticket_engine_core.py",
            ),
            plugin_root=FAKE_ROOT,
        )
        assert result == {}

    def test_unknown_ticket_script_denied(self):
        """Python invocation of an unrecognized ticket script is denied."""
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/ticket_evil.py attack",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_python_without_3_denied(self):
        """python (not python3) invocation of engine script is denied, not bypassed."""
        result = run_hook(
            make_hook_input(
                f"python {FAKE_ROOT}/scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_relative_path_engine_invocation_denied(self):
        """Relative path engine invocation is denied, not bypassed."""
        result = run_hook(
            make_hook_input(
                "python3 scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_path_traversal_engine_invocation_denied(self):
        """Path traversal in engine invocation is denied, not bypassed."""
        result = run_hook(
            make_hook_input(
                f"python3 {FAKE_ROOT}/scripts/../scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_absolute_python_path_denied(self):
        """/usr/bin/python3 engine invocation is denied, not bypassed."""
        result = run_hook(
            make_hook_input(
                f"/usr/bin/python3 {FAKE_ROOT}/scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_versioned_python_denied(self):
        """python3.11 engine invocation is denied, not bypassed."""
        result = run_hook(
            make_hook_input(
                f"python3.11 {FAKE_ROOT}/scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_env_python3_denied(self):
        """`env python3` engine invocation is denied, not bypassed."""
        result = run_hook(
            make_hook_input(
                f"env python3 {FAKE_ROOT}/scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_env_with_var_python3_denied(self):
        """`env VAR=value python3` engine invocation is denied."""
        result = run_hook(
            make_hook_input(
                f"env PYTHONPATH=. python3 {FAKE_ROOT}/scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"

    def test_inline_env_var_python3_denied(self):
        """`PYTHONPATH=. python3` (bare env assignment) engine invocation is denied."""
        result = run_hook(
            make_hook_input(
                f"PYTHONPATH=. python3 {FAKE_ROOT}/scripts/ticket_engine_user.py plan payload.json",
            ),
            plugin_root=FAKE_ROOT,
        )
        decision = result.get("hookSpecificOutput", {})
        assert decision.get("permissionDecision") == "deny"


# ---------------------------------------------------------------------------
# Candidate detection tests (shlex-based)
# ---------------------------------------------------------------------------


class TestCandidateDetection:
    """Tests for shlex-based ticket command candidate detection."""

    # --- Leading-space bypass (F-001) ---
    def test_leading_space_denied(self, tmp_path: Path) -> None:
        """Leading space must not bypass hook — detected as candidate, denied as non-canonical."""
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f" python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_leading_tabs_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"\tpython3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    # --- env launcher variants (detected as candidate → denied as non-canonical) ---
    def test_env_python3_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"/usr/bin/env python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_env_with_var_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"env PYTHONPATH=. python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_env_unset_then_python_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = (
            f"env -u PYTHONPATH python3 "
            f"{plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        )
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_env_split_string_python_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = (
            f'env -S "python3 {plugin_root}/scripts/ticket_engine_user.py '
            f'classify {payload}"'
        )
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_lowercase_env_assignment_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"myvar=value python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    # --- Versioned python (detected as candidate → denied as non-canonical) ---
    def test_versioned_python_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3.12 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_absolute_python_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"/usr/bin/python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_dash_b_canonical_python_allowed(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 -B {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    @pytest.mark.parametrize("python_prefix", ["-BB", "-B -u", "-u -B"])
    def test_noncanonical_dash_b_flag_combinations_denied(
        self, tmp_path: Path, python_prefix: str
    ) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = (
            f"python3 {python_prefix} "
            f"{plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        )
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_absolute_python_with_dash_b_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"/usr/bin/python3 -B {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_env_python3_with_dash_b_denied(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"env python3 -B {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    # --- Non-ticket commands pass through ---
    def test_non_ticket_python_passes_through(self, tmp_path: Path) -> None:
        """Python invocations that don't target ticket scripts pass through."""
        result = run_hook(make_hook_input("python3 setup.py install", cwd=str(tmp_path)))
        assert result == {} or result.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    def test_grep_for_ticket_script_name_passes_through(self, tmp_path: Path) -> None:
        """Non-python commands mentioning ticket script basenames pass through."""
        result = run_hook(make_hook_input("rg ticket_engine_user.py README.md", cwd=str(tmp_path)))
        assert result == {} or result.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    # --- Malformed quoting with ticket basename → deny ---
    def test_malformed_quoting_with_ticket_basename_denied(self, tmp_path: Path) -> None:
        """shlex.split failure + ticket basename in raw string → deny."""
        plugin_root = str(Path(__file__).parent.parent)
        cmd = f"python3 '{plugin_root}/scripts/ticket_engine_user.py classify"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_malformed_quoting_with_unknown_ticket_script_denied(self, tmp_path: Path) -> None:
        """Broad ticket_*.py fallback still denies malformed quoted commands."""
        plugin_root = str(Path(__file__).parent.parent)
        cmd = f"python3 '{plugin_root}/scripts/ticket_rogue.py classify"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    # --- Malformed quoting without ticket basename → pass through ---
    def test_malformed_quoting_without_ticket_basename_passes(self, tmp_path: Path) -> None:
        cmd = "python3 'some_other_script.py"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result == {} or result.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    @pytest.mark.parametrize("python_prefix", ["-u", "-X dev", "-m pdb"])
    def test_python_flags_before_script_denied(self, tmp_path: Path, python_prefix: str) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = (
            f"python3 {python_prefix} "
            f"{plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        )
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    # --- Canonical form still allowed ---
    def test_canonical_user_still_allowed(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_canonical_agent_still_allowed(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_agent.py classify {payload}"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_canonical_with_2_and_1_still_allowed(self, tmp_path: Path) -> None:
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_user.py execute {payload} 2>&1"
        result = run_hook(make_hook_input(cmd, cwd=str(tmp_path)))
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"


# ---------------------------------------------------------------------------
# Agent ID origin helper tests
# ---------------------------------------------------------------------------


class TestAgentIdOriginHelper:
    """Tests for explicit agent_id handling in all hook branches."""

    # --- Engine branch: empty string agent_id should deny ---
    def test_engine_empty_agent_id_denied(self, tmp_path: Path) -> None:
        """Present-but-empty agent_id on engine command -> deny as malformed."""
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = ""  # Present but empty.
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_engine_non_string_agent_id_denied(self, tmp_path: Path) -> None:
        """Non-string agent_id (e.g., int) on engine command -> deny."""
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = 42
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_engine_none_agent_id_denied(self, tmp_path: Path) -> None:
        """Present-but-null agent_id on engine command -> deny as malformed."""
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = None
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_engine_missing_agent_id_is_user(self, tmp_path: Path) -> None:
        """Missing agent_id key -> user origin, allowed."""
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_user.py classify {payload}"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        assert "agent_id" not in hook_input  # Confirm missing.
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
        # Verify injected origin is "user".
        injected = json.loads(payload.read_text(encoding="utf-8"))
        assert injected["hook_request_origin"] == "user"

    def test_engine_valid_agent_id_is_agent(self, tmp_path: Path) -> None:
        """Non-empty string agent_id -> agent origin."""
        plugin_root = str(Path(__file__).parent.parent)
        payload = make_payload_file(tmp_path)
        cmd = f"python3 {plugin_root}/scripts/ticket_engine_agent.py classify {payload}"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = "agent-123"
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
        injected = json.loads(payload.read_text(encoding="utf-8"))
        assert injected["hook_request_origin"] == "agent"

    # --- Audit branch: empty/non-string agent_id should deny ---
    def test_audit_empty_agent_id_denied(self, tmp_path: Path) -> None:
        """Present-but-empty agent_id on audit command -> deny."""
        plugin_root = str(Path(__file__).parent.parent)
        cmd = f"python3 {plugin_root}/scripts/ticket_audit.py list /tmp/payload.json"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = ""
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_audit_non_string_agent_id_denied(self, tmp_path: Path) -> None:
        """Non-string agent_id on audit command -> deny."""
        plugin_root = str(Path(__file__).parent.parent)
        cmd = f"python3 {plugin_root}/scripts/ticket_audit.py list /tmp/payload.json"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = 0
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_audit_valid_agent_id_denied(self, tmp_path: Path) -> None:
        """Valid agent_id on audit command -> deny (audit is user-only)."""
        plugin_root = str(Path(__file__).parent.parent)
        cmd = f"python3 {plugin_root}/scripts/ticket_audit.py list /tmp/payload.json"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        hook_input["agent_id"] = "agent-456"
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_audit_missing_agent_id_allowed(self, tmp_path: Path) -> None:
        """Missing agent_id on audit command -> user -> allowed."""
        plugin_root = str(Path(__file__).parent.parent)
        cmd = f"python3 {plugin_root}/scripts/ticket_audit.py list /tmp/payload.json"
        hook_input = make_hook_input(cmd, cwd=str(tmp_path))
        assert "agent_id" not in hook_input
        result = run_hook(hook_input)
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
