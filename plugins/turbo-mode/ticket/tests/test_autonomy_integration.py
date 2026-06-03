"""Integration tests for runtime-first autonomy boundaries."""

from __future__ import annotations

from pathlib import Path

from scripts.ticket_autonomy_config import AutomationMode, write_local_config
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_engine_core import AutonomyConfig, engine_execute, engine_preflight


def test_agent_configured_for_agent_primary_still_waits_for_gateway(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    problem = "Agent primary mode still requires gateway approval in this slice."

    preflight = engine_preflight(
        ticket_id=None,
        action="create",
        session_id="int-session",
        request_origin="agent",
        classify_confidence=0.95,
        classify_intent="create",
        dedup_fingerprint=compute_dedup_fp(problem, []),
        target_fingerprint=None,
        fields={"title": "Gateway required", "problem": problem, "priority": "normal"},
        tickets_dir=tmp_tickets,
        hook_injected=True,
    )
    execute = engine_execute(
        action="create",
        ticket_id=None,
        fields={"title": "Gateway required", "problem": problem, "priority": "normal"},
        session_id="int-session",
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

    assert preflight.state == "policy_blocked"
    assert preflight.error_code == "gateway_required"
    assert execute.state == "policy_blocked"
    assert execute.error_code == "gateway_required"
    assert list(tmp_tickets.glob("*.md")) == []
    assert not (tmp_tickets / ".audit").exists()


def test_user_create_is_unaffected_by_local_automation_mode(tmp_tickets: Path) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.DISCUSSION_ONLY)
    problem = "User writes continue through the existing engine path."

    preflight = engine_preflight(
        ticket_id=None,
        action="create",
        session_id="user-session",
        request_origin="user",
        classify_confidence=0.95,
        classify_intent="create",
        dedup_fingerprint=compute_dedup_fp(problem, []),
        target_fingerprint=None,
        fields={"title": "User ticket", "problem": problem, "priority": "normal"},
        tickets_dir=tmp_tickets,
    )
    execute = engine_execute(
        action="create",
        ticket_id=None,
        fields={"title": "User ticket", "problem": problem, "priority": "normal"},
        session_id="user-session",
        request_origin="user",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        hook_injected=True,
        hook_request_origin="user",
        classify_intent="create",
        classify_confidence=0.95,
        dedup_fingerprint=compute_dedup_fp(problem, []),
    )

    assert preflight.state == "ok"
    assert execute.state == "ok"
    assert len(list(tmp_tickets.glob("*.md"))) == 1
