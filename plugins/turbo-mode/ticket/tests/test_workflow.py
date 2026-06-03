"""Tests for the deprecated generic workflow shim."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ticket_workflow import run_recovery, run_workflow


def _payload_file(tmp_path: Path) -> Path:
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps({"action": "create"}), encoding="utf-8")
    return path


def test_workflow_prepare_is_unavailable(tmp_path: Path) -> None:
    response = run_workflow("prepare", _payload_file(tmp_path))

    assert response == {
        "state": "unavailable",
        "message": "Deprecated Ticket workflow is unavailable: workflow/prepare.",
        "data": {"surface": "workflow/prepare"},
        "error_code": "deprecated_workflow",
    }


def test_workflow_execute_is_unavailable(tmp_path: Path) -> None:
    response = run_workflow("execute", _payload_file(tmp_path))

    assert response["state"] == "unavailable"
    assert response["error_code"] == "deprecated_workflow"


def test_workflow_recover_is_unavailable(tmp_path: Path) -> None:
    response = run_recovery(_payload_file(tmp_path), "create_anyway")

    assert response["state"] == "unavailable"
    assert response["data"]["surface"] == "workflow/recover"


def test_workflow_unknown_subcommand_escalates(tmp_path: Path) -> None:
    response = run_workflow("preview", _payload_file(tmp_path))

    assert response["state"] == "escalate"
    assert response["error_code"] == "intent_mismatch"
