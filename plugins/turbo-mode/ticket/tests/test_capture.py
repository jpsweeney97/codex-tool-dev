"""Tests for the deprecated capture workflow shim."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ticket_capture import autonomy_candidate_from_capture_payload, run_capture

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ticket_capture.py"


def _payload_file(tmp_path: Path) -> Path:
    path = tmp_path / "capture.json"
    path.write_text(json.dumps({"capture": {"title": "Old capture"}}), encoding="utf-8")
    return path


def test_capture_prepare_is_unavailable(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = run_capture("prepare", payload)

    assert response == {
        "state": "unavailable",
        "message": "Deprecated Ticket capture workflow is unavailable: capture/prepare.",
        "data": {"surface": "capture/prepare"},
        "error_code": "deprecated_workflow",
    }


def test_capture_execute_is_unavailable(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = run_capture("execute", payload)

    assert response["state"] == "unavailable"
    assert response["error_code"] == "deprecated_workflow"
    assert response["data"]["surface"] == "capture/execute"


def test_capture_unknown_subcommand_escalates(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = run_capture("preview", payload)

    assert response["state"] == "escalate"
    assert response["error_code"] == "intent_mismatch"


def test_capture_adapter_returns_discussion_candidate(tmp_path: Path) -> None:
    payload = _payload_file(tmp_path)

    response = autonomy_candidate_from_capture_payload(payload)

    assert response["state"] == "discussion_required"
    assert response["data"]["possible_candidates"][0]["action"] == "create"


def test_capture_cli_exits_nonzero_with_structured_unavailable(tmp_path: Path) -> None:
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
