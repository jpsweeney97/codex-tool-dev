"""Tests for the host-facing Ticket autonomy CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "ticket_autonomy.py"


def _run_autonomy(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _write_ticket(project_root: Path, name: str, text: str) -> Path:
    path = project_root / "docs" / "tickets" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_migrate_change_history_dry_run_reports_candidates_without_changes(tmp_path: Path) -> None:
    ticket = _write_ticket(tmp_path, "example.md", "# Example\n\n## Problem\nText.\n")
    before = ticket.read_text(encoding="utf-8")

    result = _run_autonomy(
        tmp_path,
        "migrate-change-history",
        "--project-root",
        str(tmp_path),
        "--dry-run",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "state": "ok",
        "changed": False,
        "candidate_count": 1,
        "candidates": ["docs/tickets/example.md"],
    }
    assert ticket.read_text(encoding="utf-8") == before


def test_migrate_change_history_apply_inserts_missing_sections(tmp_path: Path) -> None:
    ticket = _write_ticket(tmp_path, "example.md", "# Example\n\n## Problem\nText.\n")

    result = _run_autonomy(
        tmp_path,
        "migrate-change-history",
        "--project-root",
        str(tmp_path),
        "--apply",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "state": "ok",
        "changed": True,
        "updated_count": 1,
        "updated": ["docs/tickets/example.md"],
    }
    assert "## Change History" in ticket.read_text(encoding="utf-8")


def test_migrate_change_history_requires_explicit_apply_or_dry_run(tmp_path: Path) -> None:
    result = _run_autonomy(
        tmp_path,
        "migrate-change-history",
        "--project-root",
        str(tmp_path),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "invalid_args"
