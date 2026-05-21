from __future__ import annotations

import json
from pathlib import Path

from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_engine_runner import run

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
