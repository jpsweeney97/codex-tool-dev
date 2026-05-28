"""Tests for runtime-first autonomy enforcement in the engine core."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.ticket_autonomy_config import AutomationMode, write_local_config
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_dedup import target_fingerprint as compute_target_fp
from scripts.ticket_engine_core import (
    AutonomyConfig,
    engine_execute,
    engine_preflight,
    read_autonomy_config,
)

from tests.support.builders import make_ticket


def _preflight(tickets_dir: Path, **overrides: object):
    defaults: dict[str, object] = {
        "ticket_id": None,
        "action": "create",
        "session_id": "test-session",
        "request_origin": "user",
        "classify_confidence": 0.95,
        "classify_intent": "create",
        "dedup_fingerprint": "abc",
        "target_fingerprint": None,
        "tickets_dir": tickets_dir,
    }
    defaults.update(overrides)
    return engine_preflight(**defaults)


def test_read_autonomy_config_missing_records_setup_required(tmp_tickets: Path) -> None:
    config = read_autonomy_config(tmp_tickets)

    assert config.mode == AutomationMode.DISCUSSION_ONLY
    assert config.warnings == ("missing_config",)


def test_read_autonomy_config_uses_strict_json(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)

    config = read_autonomy_config(tmp_tickets)

    assert config.mode == AutomationMode.AGENT_PRIMARY
    assert config.warnings == ()
    assert config.to_dict() == {"mode": "agent_primary", "warnings": []}


def test_agent_preflight_requires_setup_when_config_missing(tmp_tickets: Path) -> None:
    resp = _preflight(tmp_tickets, request_origin="agent", hook_injected=True)

    assert resp.state == "policy_blocked"
    assert resp.error_code == "setup_required"
    assert resp.data["autonomy_config"]["mode"] == "discussion_only"
    assert resp.data["autonomy_config"]["warnings"] == ["missing_config"]


@pytest.mark.parametrize("mode", list(AutomationMode))
def test_agent_preflight_requires_gateway_for_configured_modes(
    tmp_tickets: Path,
    mode: AutomationMode,
) -> None:
    write_local_config(tmp_tickets.parent.parent, mode)

    resp = _preflight(tmp_tickets, request_origin="agent", hook_injected=True)

    assert resp.state == "policy_blocked"
    assert resp.error_code == "gateway_required"
    assert resp.data["autonomy_config"]["mode"] == mode.value


def test_user_preflight_is_not_blocked_by_missing_automation_config(tmp_tickets: Path) -> None:
    resp = _preflight(tmp_tickets, request_origin="user")

    assert resp.state == "ok"
    assert resp.data["autonomy_config"]["mode"] == "discussion_only"
    assert resp.data["autonomy_config"]["warnings"] == ["missing_config"]


def test_agent_reopen_policy_still_fails_before_gateway(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)

    resp = _preflight(
        tmp_tickets,
        request_origin="agent",
        hook_injected=True,
        action="reopen",
        classify_intent="reopen",
        ticket_id="T-20260302-01",
    )

    assert resp.state == "policy_blocked"
    assert resp.error_code == "policy_blocked"
    assert "reopen" in resp.message.lower()


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("dedup_override", "dedup_override"),
        ("dependency_override", "dependency_override"),
    ],
)
def test_agent_overrides_still_fail_before_gateway(
    tmp_tickets: Path,
    field: str,
    message: str,
) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    kwargs: dict[str, object] = {field: True}
    if field == "dependency_override":
        make_ticket(tmp_tickets, "2026-03-02-test.md")
        kwargs.update(
            {
                "action": "close",
                "classify_intent": "close",
                "ticket_id": "T-20260302-01",
            }
        )

    resp = _preflight(tmp_tickets, request_origin="agent", hook_injected=True, **kwargs)

    assert resp.state == "policy_blocked"
    assert resp.error_code == "policy_blocked"
    assert message in resp.message


def test_low_level_agent_execute_requires_gateway_before_write(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    problem = "Agent execute must wait for a gateway decision."

    resp = engine_execute(
        action="create",
        ticket_id=None,
        fields={"title": "Gateway required", "problem": problem, "priority": "medium"},
        session_id="execute-session",
        request_origin="agent",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        autonomy_config=AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY),
        hook_injected=True,
        hook_request_origin="agent",
        classify_intent="create",
        classify_confidence=0.95,
        dedup_fingerprint=compute_dedup_fp(problem, []),
    )

    assert resp.state == "policy_blocked"
    assert resp.error_code == "gateway_required"
    assert list(tmp_tickets.glob("*.md")) == []
    assert not (tmp_tickets / ".audit").exists()


def test_direct_agent_execute_requires_gateway_before_runtime_proof(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    problem = "Direct execute must wait for runtime-first gateway approval."

    resp = engine_execute(
        action="create",
        ticket_id=None,
        fields={"title": "Gateway required", "problem": problem, "priority": "medium"},
        session_id="execute-session",
        request_origin="agent",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        autonomy_config=AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY),
        hook_injected=True,
        hook_request_origin="user",
        classify_intent="create",
        classify_confidence=0.95,
        dedup_fingerprint=compute_dedup_fp(problem, []),
        runtime_execute_surface="direct_execute",
    )

    assert resp.state == "policy_blocked"
    assert resp.error_code == "gateway_required"
    assert "runtime_readiness" not in resp.data


def test_agent_update_requires_gateway_before_write(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    ticket_path = make_ticket(tmp_tickets, "2026-03-02-test.md")

    resp = engine_execute(
        action="update",
        ticket_id="T-20260302-01",
        fields={"priority": "low"},
        session_id="execute-session",
        request_origin="agent",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        autonomy_config=AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY),
        hook_injected=True,
        hook_request_origin="agent",
        classify_intent="update",
        classify_confidence=0.95,
        target_fingerprint=compute_target_fp(ticket_path),
    )

    assert resp.state == "policy_blocked"
    assert resp.error_code == "gateway_required"
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
