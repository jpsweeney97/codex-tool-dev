"""Tests for the deprecated focused-update workflow shim."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ticket_update import autonomy_candidate_from_update_payload, run_update

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ticket_update.py"


def _payload_file(tmp_path: Path) -> Path:
    path = tmp_path / "update.json"
    path.write_text(json.dumps({"ticket_id": "T-20260518-01", "update": {}}), encoding="utf-8")
    return path


def test_update_prepare_is_unavailable(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = run_update("prepare", payload)

    assert response == {
        "state": "unavailable",
        "message": "Deprecated Ticket update workflow is unavailable: update/prepare.",
        "data": {"surface": "update/prepare"},
        "error_code": "deprecated_workflow",
    }


def test_update_execute_is_unavailable(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = run_update("execute", payload)

    assert response["state"] == "unavailable"
    assert response["error_code"] == "deprecated_workflow"
    assert response["data"]["surface"] == "update/execute"


def test_update_unknown_subcommand_escalates(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = run_update("preview", payload)

    assert response["state"] == "escalate"
    assert response["error_code"] == "intent_mismatch"


def test_update_adapter_returns_discussion_candidate(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = autonomy_candidate_from_update_payload(payload)

    assert response["state"] == "discussion_required"
    assert response["data"]["possible_candidates"][0]["action"] == "update"


def test_update_cli_exits_nonzero_with_structured_unavailable(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "prepare", str(payload)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    response = json.loads(result.stdout)
    assert response["state"] == "unavailable"
    assert response["error_code"] == "deprecated_workflow"
