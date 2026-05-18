"""Integration tests: config → preflight → execute → audit trail."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_engine_core import (
    AutonomyConfig,
    engine_count_session_creates,
    engine_execute,
    engine_preflight,
)


@pytest.fixture
def integration_env(tmp_path: Path):
    """Full integration environment: .codex config + tickets dir."""
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    config_path = codex_dir / "ticket.local.md"
    return tickets_dir, config_path


class TestAutonomyIntegration:
    """End-to-end: config → preflight → execute → audit."""

    def test_suggest_mode_blocks_agent_create(self, integration_env):
        """Full flow: default suggest mode → preflight blocks → no execute."""
        tickets_dir, _ = integration_env
        resp = engine_preflight(
            ticket_id=None, action="create", session_id="int-session",
            request_origin="agent", classify_confidence=0.95, classify_intent="create",
            dedup_fingerprint="fp1", target_fingerprint=None,
            tickets_dir=tickets_dir, hook_injected=True,
        )
        assert resp.state == "policy_blocked"
        assert resp.data["autonomy_config"]["mode"] == "suggest"

    def test_auto_audit_full_create_flow(self, integration_env):
        """Full flow: auto_audit → preflight ok → execute creates → audit recorded."""
        tickets_dir, config_path = integration_env
        config_path.write_text("---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n")

        pf_resp = engine_preflight(
            ticket_id=None, action="create", session_id="int-session",
            request_origin="agent", classify_confidence=0.95, classify_intent="create",
            dedup_fingerprint="fp1", target_fingerprint=None,
            tickets_dir=tickets_dir, hook_injected=True,
        )
        assert pf_resp.state == "ok"
        config_snapshot = pf_resp.data["autonomy_config"]
        assert "notification" in pf_resp.data

        config = AutonomyConfig.from_dict(config_snapshot)
        ex_resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Auto-created", "problem": "Agent found an issue"},
            session_id="int-session", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tickets_dir, autonomy_config=config, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Agent found an issue", []),
        )
        assert ex_resp.state == "ok_create"

        count = engine_count_session_creates("int-session", tickets_dir)
        assert count == 1

    def test_auto_audit_session_cap_enforced(self, integration_env):
        """Full flow: auto_audit cap reached → preflight blocks."""
        tickets_dir, config_path = integration_env
        config_path.write_text("---\nautonomy_mode: auto_audit\nmax_creates_per_session: 2\n---\n")

        for i in range(2):
            problem = f"Issue {i}"
            config = AutonomyConfig(mode="auto_audit", max_creates=2)
            engine_execute(
                action="create", ticket_id=None,
                fields={"title": f"Ticket {i}", "problem": problem},
                session_id="cap-session", request_origin="agent",
                dedup_override=False, dependency_override=False,
                tickets_dir=tickets_dir, autonomy_config=config, hook_injected=True,
                hook_request_origin="agent",
                classify_intent="create",
                classify_confidence=0.95,
                dedup_fingerprint=compute_dedup_fp(problem, []),
            )

        resp = engine_preflight(
            ticket_id=None, action="create", session_id="cap-session",
            request_origin="agent", classify_confidence=0.95, classify_intent="create",
            dedup_fingerprint="fp3", target_fingerprint=None,
            tickets_dir=tickets_dir, hook_injected=True,
        )
        assert resp.state == "policy_blocked"
        assert "cap" in resp.message.lower() or "2/2" in resp.message

    def test_user_unaffected_by_autonomy_config(self, integration_env):
        """User operations pass regardless of autonomy config."""
        tickets_dir, config_path = integration_env
        config_path.write_text("---\nautonomy_mode: auto_silent\n---\n")

        resp = engine_preflight(
            ticket_id=None, action="create", session_id="user-session",
            request_origin="user", classify_confidence=0.95, classify_intent="create",
            dedup_fingerprint="fp1", target_fingerprint=None,
            tickets_dir=tickets_dir,
        )
        assert resp.state == "ok"

        ex_resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "User ticket", "problem": "User issue"},
            session_id="user-session", request_origin="user",
            dedup_override=False, dependency_override=False,
            tickets_dir=tickets_dir,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("User issue", []),
        )
        assert ex_resp.state == "ok_create"

    def test_execute_blocks_when_autonomy_policy_changes_after_preflight(self, integration_env):
        """Agent execute re-reads live config and blocks if policy changed."""
        tickets_dir, config_path = integration_env
        config_path.write_text("---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n")

        pf_resp = engine_preflight(
            ticket_id=None, action="create", session_id="toctou-session",
            request_origin="agent", classify_confidence=0.95, classify_intent="create",
            dedup_fingerprint="fp1", target_fingerprint=None,
            tickets_dir=tickets_dir, hook_injected=True,
        )
        assert pf_resp.state == "ok"
        snapshot = AutonomyConfig.from_dict(pf_resp.data["autonomy_config"])
        assert snapshot.mode == "auto_audit"

        # Config changes between preflight and execute.
        config_path.write_text("---\nautonomy_mode: suggest\n---\n")

        ex_resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "TOCTOU test", "problem": "Testing snapshot"},
            session_id="toctou-session", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tickets_dir, autonomy_config=snapshot, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Testing snapshot", []),
        )
        assert ex_resp.state == "policy_blocked"
        assert "changed since preflight" in ex_resp.message.lower()

    def test_policy_changed_with_malformed_live_config_includes_warnings(self, integration_env):
        """Policy-changed response includes live_warnings when config is malformed."""
        tickets_dir, config_path = integration_env
        config_path.write_text("---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n")

        pf_resp = engine_preflight(
            ticket_id=None, action="create", session_id="warn-session",
            request_origin="agent", classify_confidence=0.95, classify_intent="create",
            dedup_fingerprint="fp1", target_fingerprint=None,
            tickets_dir=tickets_dir, hook_injected=True,
        )
        assert pf_resp.state == "ok"
        snapshot = AutonomyConfig.from_dict(pf_resp.data["autonomy_config"])
        assert snapshot.mode == "auto_audit"

        # Config becomes malformed between preflight and execute.
        config_path.write_text("---\nautonomy_mode: BOGUS_MODE\n---\n")

        ex_resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Warning test", "problem": "Config degraded"},
            session_id="warn-session", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tickets_dir, autonomy_config=snapshot, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Config degraded", []),
        )
        assert ex_resp.state == "policy_blocked"
        assert "changed since preflight" in ex_resp.message.lower()
        assert ex_resp.data["live_mode"] == "suggest"
        assert "live_warnings" in ex_resp.data
        assert any("BOGUS_MODE" in w for w in ex_resp.data["live_warnings"])

    def test_defense_in_depth_mode_block_with_malformed_config_includes_warnings(self, integration_env):
        """Defense-in-depth mode block includes live_mode and live_warnings when config is malformed."""
        tickets_dir, config_path = integration_env
        # Malformed config: self-heals to mode="suggest", max_creates=5.
        config_path.write_text("---\nautonomy_mode: BOGUS_MODE\n---\n")

        # Snapshot matches effective policy (suggest, 5) — fingerprints match,
        # policy-changed check passes, mode block fires.
        snapshot = AutonomyConfig(mode="suggest")

        ex_resp = engine_execute(
            action="create", ticket_id=None,
            fields={"title": "Mode block test", "problem": "Degraded config mode block"},
            session_id="dind-session", request_origin="agent",
            dedup_override=False, dependency_override=False,
            tickets_dir=tickets_dir, autonomy_config=snapshot, hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Degraded config mode block", []),
        )
        assert ex_resp.state == "policy_blocked"
        assert "defense-in-depth" in ex_resp.message.lower()
        assert ex_resp.data["live_mode"] == "suggest"
        assert "live_warnings" in ex_resp.data
        assert any("BOGUS_MODE" in w for w in ex_resp.data["live_warnings"])
