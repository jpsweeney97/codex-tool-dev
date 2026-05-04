"""Tests for autonomy config parsing and enforcement."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp, target_fingerprint as compute_target_fp
from scripts.ticket_engine_core import (
    AutonomyConfig,
    engine_execute,
    engine_preflight,
    read_autonomy_config,
)
from tests.support.builders import make_ticket, write_autonomy_config


@pytest.fixture
def autonomy_env(tmp_path: Path):
    """Set up directory structure for autonomy config tests.

    Creates:
        tmp_path/.codex/          (project root marker)
        tmp_path/docs/tickets/     (tickets_dir)

    Returns (tickets_dir, config_path) tuple.
    """
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    config_path = codex_dir / "ticket.local.md"
    return tickets_dir, config_path


class TestAutonomyConfig:
    """Test AutonomyConfig dataclass and read_autonomy_config() parsing."""

    def test_default_when_no_config_file(self, autonomy_env):
        """Missing .codex/ticket.local.md → default suggest/5/no warnings."""
        tickets_dir, _ = autonomy_env
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "suggest"
        assert config.max_creates == 5
        assert config.warnings == ()

    def test_valid_auto_audit_config(self, autonomy_env):
        """Valid auto_audit config with custom max_creates."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text(
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 10\n---\n"
        )
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "auto_audit"
        assert config.max_creates == 10
        assert config.warnings == ()

    def test_valid_auto_silent_config(self, autonomy_env):
        """Valid auto_silent config."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\nautonomy_mode: auto_silent\n---\n")
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "auto_silent"
        assert config.max_creates == 5  # default

    def test_malformed_yaml_warns_and_defaults(self, autonomy_env):
        """Malformed YAML → suggest + warning (NOT silent swallow)."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\n: [invalid yaml\n---\n")
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "suggest"
        assert len(config.warnings) == 1
        assert "failed to parse" in config.warnings[0].lower()

    def test_unknown_mode_warns_and_defaults(self, autonomy_env):
        """Unknown autonomy_mode → suggest + warning."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\nautonomy_mode: yolo\n---\n")
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "suggest"
        assert len(config.warnings) == 1
        assert "yolo" in config.warnings[0]

    def test_non_dict_frontmatter_warns(self, autonomy_env):
        """YAML list instead of dict → suggest + warning."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\n- item1\n- item2\n---\n")
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "suggest"
        assert len(config.warnings) == 1
        assert "not a dict" in config.warnings[0].lower()

    def test_missing_mode_field_defaults_suggest(self, autonomy_env):
        """No autonomy_mode field → suggest (implicit default)."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\nsome_other_field: value\n---\n")
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "suggest"
        assert config.warnings == ()

    def test_non_int_max_creates_warns(self, autonomy_env):
        """Non-integer max_creates → default 5 + warning."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text(
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: lots\n---\n"
        )
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "auto_audit"
        assert config.max_creates == 5
        assert len(config.warnings) == 1
        assert "max_creates" in config.warnings[0].lower()

    def test_zero_max_creates_disables_agent_creates(self, autonomy_env):
        """max_creates=0 means disable all agent creates (not invalid)."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text(
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 0\n---\n"
        )
        config = read_autonomy_config(tickets_dir)
        assert config.max_creates == 0
        assert config.warnings == ()

    def test_negative_max_creates_warns(self, autonomy_env):
        """Negative max_creates → default 5 + warning."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text(
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: -1\n---\n"
        )
        config = read_autonomy_config(tickets_dir)
        assert config.max_creates == 5
        assert len(config.warnings) == 1

    def test_no_frontmatter_delimiters_warns(self, autonomy_env):
        """File exists but no --- delimiters → suggest + warning."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text("autonomy_mode: auto_audit\n")
        config = read_autonomy_config(tickets_dir)
        assert config.mode == "suggest"
        assert len(config.warnings) == 1
        assert "no valid frontmatter" in config.warnings[0].lower()

    def test_to_dict_from_dict_round_trip(self):
        """AutonomyConfig serialization round-trips correctly."""
        original = AutonomyConfig(mode="auto_audit", max_creates=10, warnings=("w1",))
        restored = AutonomyConfig.from_dict(original.to_dict())
        assert restored.mode == original.mode
        assert restored.max_creates == original.max_creates
        assert restored.warnings == original.warnings

    def test_discovers_project_root_via_git_directory_marker(self, tmp_path: Path):
        """Config lookup reuses marker-based root discovery, not a .codex-only walk."""
        (tmp_path / ".git").mkdir(exist_ok=True)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "ticket.local.md").write_text(
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 7\n---\n",
            encoding="utf-8",
        )
        tickets_dir = tmp_path / "nested" / "docs" / "tickets"
        tickets_dir.mkdir(parents=True)

        config = read_autonomy_config(tickets_dir)
        assert config.mode == "auto_audit"
        assert config.max_creates == 7

    def test_discovers_project_root_via_git_worktree_file_marker(self, tmp_path: Path):
        """A .git file marker is also a valid project root for config lookup."""
        (tmp_path / ".git").write_text("gitdir: /tmp/worktrees/example\n", encoding="utf-8")
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "ticket.local.md").write_text(
            "---\nautonomy_mode: auto_silent\n---\n",
            encoding="utf-8",
        )
        tickets_dir = tmp_path / "nested" / "docs" / "tickets"
        tickets_dir.mkdir(parents=True)

        config = read_autonomy_config(tickets_dir)
        assert config.mode == "auto_silent"
        assert config.max_creates == 5


class TestAutonomyPreflight:
    """Test autonomy enforcement in engine_preflight."""

    @pytest.fixture
    def auto_audit_env(self, autonomy_env):
        """Set up auto_audit config and return tickets_dir."""
        tickets_dir, config_path = autonomy_env
        config_path.write_text(
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 3\n---\n"
        )
        return tickets_dir

    def _preflight(self, tickets_dir, **overrides):
        """Helper: call engine_preflight with sensible defaults."""
        defaults = dict(
            ticket_id=None,
            action="create",
            session_id="test-session",
            request_origin="user",
            classify_confidence=0.95,
            classify_intent="create",
            dedup_fingerprint="abc",
            target_fingerprint=None,
            tickets_dir=tickets_dir,
        )
        defaults.update(overrides)
        return engine_preflight(**defaults)

    def test_agent_suggest_mode_blocked(self, autonomy_env):
        tickets_dir, _ = autonomy_env
        resp = self._preflight(tickets_dir, request_origin="agent", hook_injected=True)
        assert resp.state == "policy_blocked"
        assert "suggest" in resp.message.lower()

    def test_agent_auto_audit_allowed(self, auto_audit_env):
        resp = self._preflight(auto_audit_env, request_origin="agent", hook_injected=True)
        assert resp.state == "ok"
        assert "autonomy_config" in resp.data

    def test_agent_auto_audit_includes_notification(self, auto_audit_env):
        resp = self._preflight(auto_audit_env, request_origin="agent", hook_injected=True)
        assert resp.state == "ok"
        assert "notification" in resp.data

    def test_agent_auto_silent_blocked_v1(self, autonomy_env):
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\nautonomy_mode: auto_silent\n---\n")
        resp = self._preflight(tickets_dir, request_origin="agent", hook_injected=True)
        assert resp.state == "policy_blocked"
        assert "auto_silent" in resp.message.lower() or "v1.0" in resp.message.lower()

    def test_agent_reopen_user_only(self, auto_audit_env):
        resp = self._preflight(
            auto_audit_env, request_origin="agent", hook_injected=True,
            action="reopen", classify_intent="reopen", ticket_id="T-20260302-01",
        )
        assert resp.state == "policy_blocked"
        assert "user-only" in resp.message.lower() or "reopen" in resp.message.lower()

    def test_agent_dedup_override_rejected(self, auto_audit_env):
        resp = self._preflight(
            auto_audit_env, request_origin="agent", hook_injected=True, dedup_override=True,
        )
        assert resp.state == "policy_blocked"
        assert "dedup_override" in resp.message.lower()

    def test_agent_dependency_override_rejected(self, auto_audit_env):
        resp = self._preflight(
            auto_audit_env, request_origin="agent", hook_injected=True,
            action="close", classify_intent="close", ticket_id="T-20260302-01",
            dependency_override=True,
        )
        assert resp.state == "policy_blocked"
        assert "dependency_override" in resp.message.lower()

    def test_agent_no_hook_injected_passes_through(self, auto_audit_env):
        """C-006: hook_injected=False on preflight must not block; preflight is non-execute."""
        resp = self._preflight(auto_audit_env, request_origin="agent", hook_injected=False)
        assert resp.state == "ok"

    def test_agent_auto_audit_session_cap_reached(self, auto_audit_env):
        import json
        from datetime import datetime, timezone
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = auto_audit_env / ".audit" / date_dir
        audit_dir.mkdir(parents=True)
        audit_file = audit_dir / "test-session.jsonl"
        for i in range(3):
            entry = {"action": "attempt_started", "intent": "create", "request_origin": "agent", "session_id": "test-session"}
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        resp = self._preflight(auto_audit_env, request_origin="agent", hook_injected=True)
        assert resp.state == "policy_blocked"
        assert "cap" in resp.message.lower() or "3/3" in resp.message

    def test_agent_auto_audit_update_no_cap_check(self, auto_audit_env):
        make_ticket(auto_audit_env, "2026-03-02-test.md")
        resp = self._preflight(
            auto_audit_env, request_origin="agent", hook_injected=True,
            action="update", classify_intent="update", ticket_id="T-20260302-01",
        )
        assert resp.state == "ok"

    def test_user_always_passes_autonomy(self, autonomy_env):
        tickets_dir, config_path = autonomy_env
        config_path.write_text("---\nautonomy_mode: auto_silent\n---\n")
        resp = self._preflight(tickets_dir, request_origin="user")
        assert resp.state == "ok"

    def test_preflight_response_includes_autonomy_config(self, autonomy_env):
        tickets_dir, _ = autonomy_env
        resp = self._preflight(tickets_dir, request_origin="user")
        assert resp.state == "ok"
        assert "autonomy_config" in resp.data
        assert resp.data["autonomy_config"]["mode"] == "suggest"

    def test_agent_audit_unavailable_blocks_create(self, auto_audit_env):
        """AUDIT_UNAVAILABLE from count → policy_blocked in preflight."""
        import os
        import sys
        if sys.platform == "win32":
            pytest.skip("chmod not effective on Windows")
        import json
        from datetime import datetime, timezone
        # Create an audit file, then make it unreadable.
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = auto_audit_env / ".audit" / date_dir
        audit_dir.mkdir(parents=True)
        audit_file = audit_dir / "test-session.jsonl"
        audit_file.write_text(
            json.dumps({"action": "create", "result": "ok_create"}) + "\n"
        )
        try:
            os.chmod(audit_file, 0o000)
            resp = self._preflight(
                auto_audit_env, request_origin="agent", hook_injected=True,
            )
            assert resp.state == "policy_blocked"
            assert "audit" in resp.message.lower()
        finally:
            os.chmod(audit_file, 0o644)

    def test_agent_update_allowed_under_auto_audit(self, auto_audit_env):
        """Agent update succeeds under auto_audit (no session cap for updates)."""
        make_ticket(auto_audit_env, "2026-03-02-test.md")
        resp = self._preflight(
            auto_audit_env, request_origin="agent", hook_injected=True,
            action="update", classify_intent="update", ticket_id="T-20260302-01",
        )
        assert resp.state == "ok"

    def test_agent_close_allowed_under_auto_audit(self, auto_audit_env):
        """Agent close succeeds under auto_audit."""
        make_ticket(auto_audit_env, "2026-03-02-test.md")
        resp = self._preflight(
            auto_audit_env, request_origin="agent", hook_injected=True,
            action="close", classify_intent="close", ticket_id="T-20260302-01",
        )
        assert resp.state == "ok"


class TestAutonomyExecute:
    """Test autonomy defense-in-depth in engine_execute."""

    def test_execute_agent_suggest_blocked(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_execute_agent_unknown_mode_self_heals_to_suggest(self, tmp_tickets):
        write_autonomy_config(tmp_tickets, "---\nautonomy_mode: yolo\n---\n")
        config = read_autonomy_config(tmp_tickets)
        assert config.mode == "suggest"
        assert any("yolo" in w for w in config.warnings)
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_execute_agent_none_config_blocked(self, tmp_tickets):
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_agent_execute_uses_live_config_not_payload_snapshot(self, tmp_tickets):
        write_autonomy_config(tmp_tickets, "---\nautonomy_mode: suggest\n---\n")
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
            hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
        )
        assert resp.state == "policy_blocked"
        assert "changed since preflight" in resp.message.lower()

    def test_agent_execute_blocks_when_snapshot_and_live_config_diverge_to_more_restrictive(self, tmp_tickets):
        write_autonomy_config(tmp_tickets, "---\nautonomy_mode: suggest\n---\n")
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
            hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
        )
        assert resp.state == "policy_blocked"
        assert "changed since preflight" in resp.message.lower()

    def test_agent_execute_blocks_when_snapshot_and_live_config_diverge_to_less_restrictive(self, tmp_tickets):
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets,
            autonomy_config=AutonomyConfig(mode="suggest"),
            hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
        )
        assert resp.state == "policy_blocked"
        assert "changed since preflight" in resp.message.lower()

    def test_agent_execute_fail_closed_on_malformed_live_config(self, tmp_tickets):
        write_autonomy_config(tmp_tickets, "---\n: [invalid yaml\n---\n")
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_execute_agent_reopen_blocked(self, tmp_tickets):
        make_ticket(tmp_tickets, "t.md", id="T-20260302-01", status="done")
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="reopen", ticket_id="T-20260302-01", fields={},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="reopen",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_execute_agent_dedup_override_blocked(self, tmp_tickets):
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=True, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_agent_execute_no_snapshot_now_rejected(self, tmp_tickets):
        """Agent without autonomy_config snapshot is now rejected (structural prerequisite)."""
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            # autonomy_config intentionally omitted (None)
        )
        assert resp.state == "policy_blocked"
        assert "autonomy_config" in resp.message.lower()

    def test_agent_execute_with_snapshot_succeeds(self, tmp_tickets):
        """Agent with matching autonomy_config snapshot succeeds."""
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "ok_create"

    def test_execute_agent_auto_audit_cap_reached(self, tmp_tickets):
        import json
        from datetime import datetime, timezone
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 2\n---\n",
        )
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / date_dir
        audit_dir.mkdir(parents=True)
        audit_file = audit_dir / "sess.jsonl"
        for _ in range(2):
            entry = {"action": "create", "result": "ok_create", "session_id": "sess"}
            with open(audit_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "policy_blocked"

    def test_frozen_prevents_post_construction_mutation(self, tmp_tickets):
        """Frozen dataclass prevents field mutation after construction."""
        config = AutonomyConfig(mode="auto_audit")
        with pytest.raises(AttributeError):
            config.mode = "suggest"  # type: ignore[misc]

    def test_post_init_heals_invalid_max_creates(self, tmp_tickets):
        """Invalid max_creates type self-heals to default 5 with warning."""
        config = AutonomyConfig(mode="auto_audit", max_creates="5")  # type: ignore[arg-type]
        assert config.max_creates == 5
        assert any("Invalid max_creates" in w for w in config.warnings)
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Problem", []),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "ok_create"

    def test_execute_agent_update_auto_audit_allowed(self, tmp_tickets):
        """Agent update under auto_audit succeeds (no session cap for updates)."""
        make_ticket(tmp_tickets, "2026-03-02-test.md")
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="update", ticket_id="T-20260302-01",
            fields={"priority": "high"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="update",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "ok_update"

    def test_execute_agent_close_auto_audit_allowed(self, tmp_tickets):
        """Agent close under auto_audit succeeds."""
        make_ticket(tmp_tickets, "2026-03-02-test.md", status="in_progress")
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        resp = engine_execute(
            action="close", ticket_id="T-20260302-01",
            fields={"resolution": "done"},
            session_id="sess", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tmp_tickets, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="close",
            classify_confidence=0.95,
            target_fingerprint=compute_target_fp(next(tmp_tickets.glob("*.md"))),
            autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
        )
        assert resp.state == "ok_close"

    def test_execute_agent_audit_write_failure_blocks(self, tmp_tickets):
        """If audit trail can't be written, agent mutation is blocked (fail-closed)."""
        import os
        import sys as _sys
        if _sys.platform == "win32":
            pytest.skip("chmod not effective on Windows")
        write_autonomy_config(
            tmp_tickets,
            "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
        )
        audit_dir = tmp_tickets / ".audit"
        audit_dir.mkdir(parents=True)
        try:
            os.chmod(audit_dir, 0o444)
            resp = engine_execute(
                action="create", ticket_id=None,
                fields={"title": "Test", "problem": "Problem"},
                session_id="sess", request_origin="agent",
                dedup_override=False, dependency_override=False,
                tickets_dir=tmp_tickets, hook_injected=True,
                hook_request_origin="agent",
                classify_intent="create",
                classify_confidence=0.95,
                dedup_fingerprint=compute_dedup_fp("Problem", []),
                autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
            )
            assert resp.state == "policy_blocked"
            assert "audit" in resp.message.lower()
        finally:
            os.chmod(audit_dir, 0o755)
