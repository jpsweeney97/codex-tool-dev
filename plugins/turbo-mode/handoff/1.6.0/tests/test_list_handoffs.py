from __future__ import annotations

import json
from pathlib import Path

from scripts.list_handoffs import main as list_main


def _handoff(path: Path, title: str, branch: str = "main") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"title: {title}\n"
        "date: 2026-02-28\n"
        'created_at: "2026-02-28T00:00:00Z"\n'
        f"session_id: {title.lower().replace(' ', '-')}\n"
        "project: test-project\n"
        "type: handoff\n"
        f"branch: {branch}\n"
        "---\n\n"
        "## Goal\n\n"
        "Test.\n",
        encoding="utf-8",
    )
    return path


def test_lists_active_handoffs_in_storage_authority_order(tmp_path: Path) -> None:
    active = tmp_path / ".codex" / "handoffs"
    older = _handoff(active / "2026-02-28_10-00_old.md", "Old")
    newer = _handoff(active / "2026-02-28_11-00_new.md", "New")

    output = list_main(["--project-root", str(tmp_path)])
    payload = json.loads(output)

    assert payload["total"] == 2
    assert [item["path"] for item in payload["handoffs"]] == [str(newer), str(older)]
    assert payload["handoffs"][0]["storage_location"] == "primary_active"
    assert payload["handoffs"][0]["branch"] == "main"


def test_legacy_archive_is_not_active_list_input(tmp_path: Path) -> None:
    legacy_archive = tmp_path / "docs" / "handoffs" / "archive"
    _handoff(legacy_archive / "2026-02-28_11-00_old.md", "Old Archive")

    output = list_main(["--project-root", str(tmp_path)])
    payload = json.loads(output)

    assert payload["total"] == 0
    assert payload["handoffs"] == []
