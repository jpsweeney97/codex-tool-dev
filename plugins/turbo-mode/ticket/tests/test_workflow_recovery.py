"""Recovery checks for the deprecated workflow shim."""

from __future__ import annotations

from pathlib import Path

from scripts.ticket_workflow import run_recovery


def test_recovery_path_is_unavailable(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")

    response = run_recovery(payload, "create_anyway")

    assert response == {
        "state": "unavailable",
        "message": "Deprecated Ticket workflow is unavailable: workflow/recover.",
        "data": {"surface": "workflow/recover"},
        "error_code": "deprecated_workflow",
    }
