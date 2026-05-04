from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.support.builders import make_ticket
from tests.support.workflow import PLUGIN_ROOT, authorized_recovery_payload, payload_file, trusted_args_ticket_payload, trusted_payload


def test_recovery_cli_set_field_preserves_quoted_json_value(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "tags"}],
        validation_errors=["tags must contain only strings"],
        ticket_id="T-20260503-66",
    )
    payload_path = payload_file(tmp_path, payload)

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
            "recover",
            str(payload_path),
            "set_field",
            "tags",
            '["ux", "ticket"]',
        ],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    output = json.loads(completed.stdout)
    hydrated = json.loads(payload_path.read_text(encoding="utf-8"))
    assert output["state"] == "ok"
    assert hydrated["fields"]["tags"] == ["ux", "ticket"]


def test_cli_ready_to_execute_returns_0(tmp_tickets: Path, tmp_path: Path) -> None:
    project_root = tmp_tickets.parent.parent
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "CLI ready",
            "problem": "Prepare should return ready_to_execute via CLI.",
            "priority": "medium",
        },
    ))

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
            "prepare",
            str(payload_path),
        ],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    output = json.loads(completed.stdout)
    assert output["state"] == "ready_to_execute"


def test_cli_need_fields_returns_2(tmp_tickets: Path, tmp_path: Path) -> None:
    project_root = tmp_tickets.parent.parent
    make_ticket(tmp_tickets, "cli-reopen.md", id="T-20260503-67", status="done")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload("reopen", "T-20260503-67", {}))

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
            "prepare",
            str(payload_path),
        ],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2, completed.stdout + completed.stderr
    output = json.loads(completed.stdout)
    assert output["state"] == "need_fields"


def test_cli_other_errors_return_1(tmp_tickets: Path, tmp_path: Path) -> None:
    project_root = tmp_tickets.parent.parent
    payload_path = tmp_path / "bad.json"
    payload_path.write_text("{bad-json", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
            "prepare",
            str(payload_path),
        ],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    output = json.loads(completed.stdout)
    assert output["state"] == "escalate"
