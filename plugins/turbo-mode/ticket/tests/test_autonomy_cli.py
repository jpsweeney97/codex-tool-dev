"""Tests for the host-facing Ticket autonomy CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.ticket_autonomy import build_repo_context
from scripts.ticket_turn_batch import PendingSummaryStore

from tests.test_turn_batch import valid_status_event

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


def _init_ticket_project(project_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=project_root, capture_output=True, text=True, check=True)
    (project_root / ".gitignore").write_text(
        ".codex/ticket-workspace/\n.codex/ticket.local.md\n",
        encoding="utf-8",
    )


def _write_context(project_root: Path, **overrides: object) -> Path:
    context: dict[str, object] = {
        "schema": "codex.ticket.turn_context.v1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "git": dict(build_repo_context(project_root).as_event_payload()),
    }
    context.update(overrides)
    path = project_root / "turn-context.json"
    path.write_text(json.dumps(context), encoding="utf-8")
    return path


def _git_status(project_root: Path, *paths: str) -> str:
    result = subprocess.run(
        ["git", "status", "--short", "--", *paths],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _git_check_ignored(project_root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", path],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


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


def test_pause_writes_pause_marker_and_discussion_only_config_without_touching_tickets(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    ticket = _write_ticket(tmp_path, "example.md", "# Example\n\n## Problem\nText.\n")
    before_ticket = ticket.read_text(encoding="utf-8")

    result = _run_autonomy(
        tmp_path,
        "pause",
        "--project-root",
        str(tmp_path),
        "--reason",
        "user_requested",
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "state": "paused",
        "pause_reason": "user_requested",
        "message": "Ticket automation paused for this workspace.",
        "ticket_updates": None,
        "discussion_question": None,
    }
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()
    assert (tmp_path / ".codex" / "ticket.local.md").read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"discussion_only"}\n'
    )
    assert _git_check_ignored(tmp_path, ".codex/ticket.local.md")
    assert _git_check_ignored(tmp_path, ".codex/ticket-workspace/pause.json")
    assert _git_status(tmp_path, ".codex/ticket.local.md", ".codex/ticket-workspace") == ""
    assert ticket.read_text(encoding="utf-8") == before_ticket


def test_recover_returns_parseable_json(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)

    result = _run_autonomy(
        tmp_path,
        "recover",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "ok"
    assert payload["turn_id"] == "turn-1"


def test_recover_compacts_old_correction_ready_detail(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)
    store = PendingSummaryStore(tmp_path)
    old_timestamp = (datetime.now(UTC) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert (
        store.append_event(
            valid_status_event(
                "failed",
                event_id="evt_old_correction",
                timestamp=old_timestamp,
                thread_id="thread-1",
                mutation_id="mut-old",
                error_code="policy_blocked",
                correction_ready=True,
                correction_detail="full correction detail",
            )
        ).state
        == "appended"
    )

    result = _run_autonomy(
        tmp_path,
        "recover",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "ok"
    assert payload["compaction_state"] == "appended"
    event = PendingSummaryStore(tmp_path).read_events()[0]
    assert "correction_detail" not in event["details"]
    assert event["details"]["correction_detail_compacted"] is True


def test_apply_turn_rejects_invalid_context(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)

    for overrides in [
        {"thread_id": ""},
        {"turn_id": ""},
        {"turn_id": "other-turn"},
    ]:
        context = _write_context(tmp_path, **overrides)
        result = _run_autonomy(
            tmp_path,
            "apply-turn",
            "--project-root",
            str(tmp_path),
            "--turn-id",
            "turn-1",
            "--context-file",
            str(context),
        )

        assert result.returncode == 2
        assert json.loads(result.stdout)["state"] == "invalid_context"


def test_apply_turn_missing_config_requires_setup_choices(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)
    context = _write_context(tmp_path)

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
    )

    assert result.returncode == 3
    assert json.loads(result.stdout) == {
        "state": "setup_required",
        "reason": "missing_config",
        "setup_choices": ["automatic", "ask_first"],
        "ticket_updates": None,
        "discussion_question": None,
    }


def test_apply_turn_setup_choice_automatic_writes_config_snapshot_and_continues(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    context = _write_context(tmp_path, candidate_changes=[{"action": "update"}])

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
        "--setup-choice",
        "automatic",
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "state": "no_change",
        "changed": False,
        "ticket_updates": None,
        "discussion_question": None,
    }
    assert (tmp_path / ".codex" / "ticket.local.md").read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"agent_primary"}\n'
    )
    snapshots = sorted((tmp_path / ".codex" / "ticket-workspace" / "mode-snapshots").glob("*.json"))
    assert len(snapshots) == 1
    assert '"mode":"agent_primary"' in snapshots[0].read_text(encoding="utf-8")
    assert _git_check_ignored(tmp_path, ".codex/ticket.local.md")
    assert _git_check_ignored(tmp_path, snapshots[0].relative_to(tmp_path).as_posix())
    assert _git_status(tmp_path, ".codex/ticket.local.md", ".codex/ticket-workspace") == ""


def test_apply_turn_setup_choice_ask_first_writes_discussion_snapshot(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    context = _write_context(tmp_path, candidate_changes=[{"action": "update"}])

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
        "--setup-choice",
        "ask_first",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_only"
    assert payload["changed"] is False
    assert (tmp_path / ".codex" / "ticket.local.md").read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"discussion_only"}\n'
    )
    snapshots = sorted((tmp_path / ".codex" / "ticket-workspace" / "mode-snapshots").glob("*.json"))
    assert len(snapshots) == 1
    assert '"mode":"discussion_only"' in snapshots[0].read_text(encoding="utf-8")
    assert _git_status(tmp_path, ".codex/ticket.local.md", ".codex/ticket-workspace") == ""


def test_apply_turn_rejects_preview_setup_choice(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)
    context = _write_context(tmp_path)

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
        "--setup-choice",
        "preview",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["state"] == "invalid_args"


def test_apply_turn_uses_thread_mode_snapshot_over_later_config_edits(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)
    context = _write_context(tmp_path, candidate_changes=[{"action": "update"}])

    first = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
        "--setup-choice",
        "automatic",
    )
    assert first.returncode == 0

    (tmp_path / ".codex" / "ticket.local.md").write_text(
        '{"schema":"codex.ticket.local.v1","mode":"discussion_only"}\n',
        encoding="utf-8",
    )
    second = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
    )

    assert second.returncode == 0
    assert json.loads(second.stdout) == {
        "state": "no_change",
        "changed": False,
        "ticket_updates": None,
        "discussion_question": None,
    }


def test_apply_turn_pause_marker_returns_paused_output(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)
    context = _write_context(tmp_path)
    pause = _run_autonomy(
        tmp_path,
        "pause",
        "--project-root",
        str(tmp_path),
        "--reason",
        "pending_summary_unhealthy",
    )
    assert pause.returncode == 0

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
    )

    assert result.returncode == 3
    assert json.loads(result.stdout) == {
        "state": "paused",
        "pause_reason": "pending_summary_unhealthy",
        "message": "Ticket automation paused because pending-summary bookkeeping needs cleanup.",
        "ticket_updates": None,
        "discussion_question": None,
    }


def test_host_cli_has_no_raw_clear_pause_or_ledger_commands(tmp_path: Path) -> None:
    for command in ["clear-pause", "append-event", "consume-approval", "mark-summarized"]:
        result = _run_autonomy(tmp_path, command, "--project-root", str(tmp_path))

        assert result.returncode == 2
        assert json.loads(result.stdout)["state"] == "invalid_args"


def test_doctor_ledger_dry_run_and_confirm_repair_return_json(tmp_path: Path) -> None:
    _init_ticket_project(tmp_path)

    dry_run = _run_autonomy(
        tmp_path,
        "doctor-ledger",
        "--project-root",
        str(tmp_path),
        "--dry-run",
    )
    repair = _run_autonomy(
        tmp_path,
        "doctor-ledger",
        "--project-root",
        str(tmp_path),
        "--confirm-repair",
    )

    assert dry_run.returncode == 0
    assert json.loads(dry_run.stdout)["state"] == "ok"
    assert repair.returncode == 0
    assert json.loads(repair.stdout)["state"] == "ok"
