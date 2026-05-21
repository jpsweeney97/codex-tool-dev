from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_engine_runner import run
from scripts.ticket_runtime_readiness import RUNTIME_PROOF_PATH_ENV

from tests.support.builders import write_autonomy_config


def _write_payload(root: Path, payload: dict[str, object]) -> str:
    payload_path = root / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return str(payload_path)


def test_agent_execute_with_user_hook_origin_reaches_runtime_readiness_gate(
    tmp_tickets: Path,
    capsys,
    monkeypatch,
) -> None:
    write_autonomy_config(
        tmp_tickets,
        "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
    )
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    problem = "Runner should reach the runtime readiness gate."
    payload_file = _write_payload(
        project_root,
        {
            "action": "create",
            "fields": {
                "title": "Runtime gate",
                "problem": problem,
                "priority": "medium",
            },
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp(problem, []),
            "autonomy_config": {
                "mode": "auto_audit",
                "max_creates": 5,
                "warnings": [],
            },
        },
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "runtime_readiness_required"


def test_agent_execute_with_missing_runtime_proof_env_reports_proof_missing(
    tmp_tickets: Path,
    capsys,
    monkeypatch,
) -> None:
    write_autonomy_config(
        tmp_tickets,
        "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n",
    )
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
                "priority": "medium",
            },
            "session_id": "runner-session",
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_dedup_fp(problem, []),
            "autonomy_config": {
                "mode": "auto_audit",
                "max_creates": 5,
                "warnings": [],
            },
        },
    )

    exit_code = run("agent", ["execute", payload_file], prog="ticket_engine_agent.py")

    assert exit_code == 1
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "runtime_readiness_required"
    assert response["data"]["runtime_readiness"]["error_code"] == "proof_missing"
    assert str(missing_proof) in response["data"]["runtime_readiness"]["message"]


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


def test_runner_unexpected_exception_returns_json_engine_response(
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
            "fields": {"title": "Boom", "problem": "Runner raises", "priority": "medium"},
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
    assert response["error_code"] == "io_error"
    assert "boom" in response["message"]
