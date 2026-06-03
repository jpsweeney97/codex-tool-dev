from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.ticket_autonomy_config import AutomationMode, write_local_config
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_dedup import target_fingerprint as compute_target_fp
from scripts.ticket_engine_runner import run
from scripts.ticket_runtime_readiness import (
    RUNTIME_ACTIVATION_BOOTSTRAP_ENV,
    RUNTIME_PROOF_PATH_ENV,
)

from tests.support.builders import (
    make_legacy_ticket_for_cutover,
    make_ticket,
    write_autonomy_config,
)


def _write_payload(root: Path, payload: dict[str, object]) -> str:
    payload_path = root / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return str(payload_path)


def _write_ingest_envelope(tickets_dir: Path) -> Path:
    envelopes_dir = tickets_dir / ".envelopes"
    envelopes_dir.mkdir(parents=True, exist_ok=True)
    envelope_path = envelopes_dir / "2026-06-03T120000Z-agent-ingest.json"
    envelope_path.write_text(
        json.dumps(
            {
                "envelope_version": "1.0",
                "title": "Agent ingest should use gateway",
                "problem": "Agent ingest must not create tickets directly.",
                "source": {"type": "handoff", "ref": "session-abc", "session": "abc-123"},
                "emitted_at": "2026-06-03T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return envelope_path


def _agent_create_payload(problem: str, hook_origin: str | None = "user") -> dict[str, object]:
    payload: dict[str, object] = {
        "action": "create",
        "fields": {
            "title": "Runtime gate",
            "problem": problem,
            "priority": "normal",
        },
        "session_id": "runner-session",
        "hook_injected": True,
        "classify_intent": "create",
        "classify_confidence": 0.95,
        "dedup_fingerprint": compute_dedup_fp(problem, []),
        "autonomy_config": {
            "mode": "agent_primary",
            "warnings": [],
        },
    }
    if hook_origin is not None:
        payload["hook_request_origin"] = hook_origin
    return payload


def _snapshot_ticket_files(tickets_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(tickets_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(tickets_dir.glob("*.md"))
    }


def _write_old_mode_config(tickets_dir: Path, mode: str) -> None:
    write_autonomy_config(
        tickets_dir,
        f"---\nautonomy_mode: {mode}\nmax_creates_per_session: 5\n---\n",
    )


def _old_mode_agent_execute_payload(
    tickets_dir: Path,
    *,
    action: str,
    mode: str,
) -> dict[str, object]:
    session_id = f"runner-{mode}-{action}"
    if action == "create":
        problem = f"Old {mode} direct create must require the gateway."
        return {
            "action": "create",
            "fields": {
                "title": "Gateway required",
                "problem": problem,
                "priority": "normal",
            },
            "session_id": session_id,
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp(problem, []),
            "autonomy_config": {"mode": mode, "max_creates": 5, "warnings": []},
        }

    status = "done" if action == "reopen" else "open"
    ticket_path = make_ticket(
        tickets_dir,
        f"2026-03-02-{action}-{mode}.md",
        id="T-20260302-01",
        status=status,
    )
    fields_by_action: dict[str, dict[str, object]] = {
        "update": {"priority": "low"},
        "close": {"resolution": "done"},
        "reopen": {"reopen_reason": "Need another pass."},
    }
    return {
        "action": action,
        "ticket_id": "T-20260302-01",
        "fields": fields_by_action[action],
        "session_id": session_id,
        "hook_injected": True,
        "hook_request_origin": "user",
        "classify_intent": action,
        "classify_confidence": 0.95,
        "target_fingerprint": compute_target_fp(ticket_path),
        "autonomy_config": {"mode": mode, "max_creates": 5, "warnings": []},
    }


@pytest.mark.parametrize("action", ["create", "update", "close", "reopen"])
@pytest.mark.parametrize("mode", ["auto_audit", "auto_silent", "suggest"])
def test_agent_execute_old_autonomy_modes_require_gateway_decision(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    mode: str,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _write_old_mode_config(tmp_tickets, mode)
    payload = _old_mode_agent_execute_payload(tmp_tickets, action=action, mode=mode)
    before = _snapshot_ticket_files(tmp_tickets)
    payload_file = _write_payload(
        project_root,
        payload,
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "gateway_required"
    assert _snapshot_ticket_files(tmp_tickets) == before
    assert not (tmp_tickets / ".audit").exists()


def test_agent_execute_with_unknown_hook_origin_rejects_before_runtime_gate(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_file = _write_payload(
        project_root,
        _agent_create_payload(
            "Unknown hook origins must not use the direct execute bypass.",
            "cli",
        ),
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "escalate"
    assert response["error_code"] == "origin_mismatch"


@pytest.mark.parametrize("subcommand", ["plan", "preflight", "ingest"])
def test_agent_user_hook_origin_bypass_is_execute_only(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
    subcommand: str,
) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_file = _write_payload(
        project_root,
        _agent_create_payload("Only execute may carry user hook provenance for agent entrypoints."),
    )

    exit_code = run("agent", [subcommand, payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["error_code"] == "origin_mismatch"


def test_agent_execute_with_agent_hook_origin_requires_gateway_before_runtime_gate(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    project_root = tmp_tickets.parent.parent
    missing_proof = project_root / ".codex" / "agent-hook-runtime-proof.json"
    monkeypatch.chdir(project_root)
    monkeypatch.setenv(RUNTIME_PROOF_PATH_ENV, str(missing_proof))
    payload_file = _write_payload(
        project_root,
        _agent_create_payload(
            "Matching agent hook provenance should use the normal runtime gate.",
            "agent",
        ),
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "gateway_required"
    assert "runtime_readiness" not in response.get("data", {})


def test_agent_ingest_with_agent_hook_origin_requires_gateway(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    envelope_path = _write_ingest_envelope(tmp_tickets)
    payload_file = _write_payload(
        project_root,
        {
            "envelope_path": str(envelope_path),
            "tickets_dir": str(tmp_tickets),
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "agent",
        },
    )

    exit_code = run("agent", ["ingest", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "blocked"
    assert response["error_code"] == "gateway_required"
    assert list(tmp_tickets.glob("*.md")) == []
    assert envelope_path.exists()
    assert not (tmp_tickets / ".envelopes" / ".processed").exists()


def test_user_ingest_with_non_normalized_ticket_returns_invalid_state(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    make_legacy_ticket_for_cutover(
        tmp_tickets,
        "legacy-active.md",
        id="legacy-ticket",
    )
    envelope_path = _write_ingest_envelope(tmp_tickets)
    payload_file = _write_payload(
        project_root,
        {
            "envelope_path": str(envelope_path),
            "tickets_dir": str(tmp_tickets),
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        },
    )

    exit_code = run("user", ["ingest", payload_file], prog="ticket_engine_user.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "invalid_state"
    assert response["error_code"] == "invalid_state"
    assert response["data"]["ingest_outcome"] == "blocked"
    assert list(tmp_tickets.glob("*.md")) == [tmp_tickets / "legacy-active.md"]
    assert envelope_path.exists()
    assert not (tmp_tickets / ".envelopes" / ".processed").exists()


def test_agent_execute_with_missing_runtime_proof_env_still_requires_gateway_first(
    tmp_tickets: Path,
    capsys,
    monkeypatch,
) -> None:
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    project_root = tmp_tickets.parent.parent
    missing_proof = project_root / ".codex" / "missing-runtime-proof.json"
    monkeypatch.chdir(project_root)
    monkeypatch.setenv(RUNTIME_PROOF_PATH_ENV, str(missing_proof))
    problem = "Runner should use the configured runtime proof path."
    payload_file = _write_payload(
        project_root,
        {
            "action": "create",
            "fields": {
                "title": "Runtime gate",
                "problem": problem,
                "priority": "normal",
            },
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp(problem, []),
            "autonomy_config": {
                "mode": "agent_primary",
                "warnings": [],
            },
        },
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "gateway_required"
    assert "runtime_readiness" not in response.get("data", {})


def test_runner_passes_activation_bootstrap_only_with_execute_proof_env(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    proof_path = (
        project_root
        / ".codex"
        / "ticket-runtime-smoke"
        / "run-1"
        / "activated-ticket-runtime-proof.json"
    )
    monkeypatch.chdir(project_root)
    monkeypatch.setenv(RUNTIME_PROOF_PATH_ENV, str(proof_path))
    monkeypatch.setenv(RUNTIME_ACTIVATION_BOOTSTRAP_ENV, "1")
    captured: dict[str, object] = {}

    def _dispatch_stage(
        *_args,
        runtime_proof_path=None,
        allow_activation_bootstrap=False,
        **_kwargs,
    ):
        captured["runtime_proof_path"] = runtime_proof_path
        captured["allow_activation_bootstrap"] = allow_activation_bootstrap
        from scripts.ticket_engine_core import EngineResponse

        return EngineResponse(state="ok", message="ok")

    monkeypatch.setattr("scripts.ticket_engine_runner.dispatch_stage", _dispatch_stage)
    payload_file = _write_payload(
        project_root,
        {
            "action": "create",
            "fields": {"title": "Runtime gate", "problem": "bootstrap", "priority": "normal"},
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp("bootstrap", []),
            "autonomy_config": {"mode": "agent_primary", "warnings": []},
        },
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["state"] == "ok"
    assert captured["runtime_proof_path"] == proof_path
    assert captured["allow_activation_bootstrap"] is True


@pytest.mark.parametrize("subcommand", ["classify", "plan", "preflight", "ingest"])
def test_runtime_proof_env_is_ignored_outside_execute(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
    subcommand: str,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    monkeypatch.setenv(RUNTIME_PROOF_PATH_ENV, str(project_root / ".codex" / "proof.json"))
    captured: dict[str, object] = {}

    def _dispatch_stage(*_args, runtime_proof_path=None, **_kwargs):
        captured["runtime_proof_path"] = runtime_proof_path
        from scripts.ticket_engine_core import EngineResponse

        return EngineResponse(state="ok", message="ok")

    monkeypatch.setattr("scripts.ticket_engine_runner.dispatch_stage", _dispatch_stage)
    payload_file = _write_payload(
        project_root,
        {
            "action": "create",
            "args": {},
            "fields": {},
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "envelope_path": str(tmp_tickets / ".envelopes" / "incoming.json"),
        },
    )

    exit_code = run("user", [subcommand, payload_file], prog="ticket_engine_user.py")

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["state"] == "ok"
    assert captured["runtime_proof_path"] is None


def test_runner_unexpected_exception_returns_internal_error_response(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_file = _write_payload(
        project_root,
        {
            "action": "create",
            "fields": {"title": "Boom", "problem": "Runner raises", "priority": "normal"},
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp("Runner raises", []),
        },
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("scripts.ticket_engine_runner.dispatch_stage", _raise)

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "escalate"
    assert response["error_code"] == "internal_error"
    assert "boom" in response["message"]


def test_runner_oserror_returns_io_error_response(
    tmp_tickets: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_file = _write_payload(
        project_root,
        {
            "action": "create",
            "fields": {"title": "Boom", "problem": "Runner raises", "priority": "normal"},
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp("Runner raises", []),
        },
    )

    def _raise(*_args, **_kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr("scripts.ticket_engine_runner.dispatch_stage", _raise)

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "escalate"
    assert response["error_code"] == "io_error"
    assert "disk unavailable" in response["message"]
