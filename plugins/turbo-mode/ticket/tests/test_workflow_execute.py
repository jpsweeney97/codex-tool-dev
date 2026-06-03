"""Execute-specific checks for the deprecated workflow shim."""

from __future__ import annotations

from pathlib import Path

from scripts.ticket_workflow import run_workflow


def test_execute_path_does_not_mutate_payload_or_ticket_files(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text('{"action":"create"}', encoding="utf-8")
    before = payload.read_text(encoding="utf-8")

    response = run_workflow("execute", payload)

    assert response["state"] == "unavailable"
    assert payload.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.md"))
