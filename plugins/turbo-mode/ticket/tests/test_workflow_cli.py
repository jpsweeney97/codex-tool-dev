"""CLI checks for the deprecated workflow shim."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ticket_workflow.py"


def test_workflow_cli_exits_nonzero_with_structured_unavailable(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")

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
