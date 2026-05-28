"""Tests for strict local Ticket automation config."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.ticket_autonomy_config import (
    AutomationMode,
    LocalConfigState,
    SetupChoice,
    _clear_workspace_pause_for_tests,
    ensure_ticket_workspace,
    is_workspace_paused,
    mode_snapshot_key,
    pause_workspace_automation,
    read_local_config,
    read_mode_snapshot,
    resolve_thread_mode,
    resume_workspace_automation,
    write_local_config,
    write_local_config_from_setup_choice,
    write_mode_snapshot,
    write_workspace_pause,
)


def _declare_workspace_ignored(project_root: Path) -> None:
    (project_root / ".gitignore").write_text(
        ".codex/ticket-workspace/\n.codex/ticket.local.md\n",
        encoding="utf-8",
    )


def test_missing_config_requires_setup(tmp_path: Path) -> None:
    result = read_local_config(tmp_path)

    assert result.state == LocalConfigState.SETUP_REQUIRED
    assert result.mode is None
    assert result.reason == "missing_config"
    assert result.path == tmp_path / ".codex" / "ticket.local.md"


@pytest.mark.parametrize("mode", list(AutomationMode))
def test_valid_strict_json_config(tmp_path: Path, mode: AutomationMode) -> None:
    write_local_config(tmp_path, mode)

    result = read_local_config(tmp_path)

    assert result.state == LocalConfigState.VALID
    assert result.mode == mode
    assert result.reason is None
    assert result.path.read_text(encoding="utf-8") == (
        f'{{"schema":"codex.ticket.local.v1","mode":"{mode.value}"}}\n'
    )


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("[]\n", "invalid_shape"),
        (
            '{"schema":"codex.ticket.local.v1","mode":"agent_primary","extra":true}\n',
            "invalid_keys",
        ),
        ('{"schema":"wrong","mode":"agent_primary"}\n', "invalid_schema"),
        ('{"schema":"codex.ticket.local.v1","mode":"suggest"}\n', "invalid_mode"),
        ('{"schema":"codex.ticket.local.v1","mode":"auto_audit"}\n', "invalid_mode"),
        ('{"schema":"codex.ticket.local.v1","mode":"auto_silent"}\n', "invalid_mode"),
        ("---\nautonomy_mode: auto_audit\n---\n", "invalid_json"),
        (
            '```json\n{"schema":"codex.ticket.local.v1","mode":"agent_primary"}\n```\n',
            "invalid_json",
        ),
        ('{"schema":"codex.ticket.local.v1","mode":"agent_primary"} // comment\n', "invalid_json"),
    ],
)
def test_invalid_config_requires_setup(tmp_path: Path, text: str, reason: str) -> None:
    path = tmp_path / ".codex" / "ticket.local.md"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")

    result = read_local_config(tmp_path)

    assert result.state == LocalConfigState.SETUP_REQUIRED
    assert result.mode is None
    assert result.reason == reason


def test_guided_setup_choice_writes_strict_json(tmp_path: Path) -> None:
    automatic = write_local_config_from_setup_choice(tmp_path, SetupChoice.AUTOMATIC)
    assert automatic.read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"agent_primary"}\n'
    )

    ask_first = write_local_config_from_setup_choice(tmp_path, SetupChoice.ASK_FIRST)
    assert ask_first.read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"discussion_only"}\n'
    )


def test_preview_is_manual_only_config_mode(tmp_path: Path) -> None:
    path = write_local_config(tmp_path, AutomationMode.PREVIEW)

    assert path.read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"preview"}\n'
    )
    assert read_local_config(tmp_path).mode == AutomationMode.PREVIEW


def test_workspace_requires_ignore_rule(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not ignored"):
        ensure_ticket_workspace(tmp_path)


def test_ensure_ticket_workspace_writes_local_guidance(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)

    workspace = ensure_ticket_workspace(tmp_path)

    assert workspace == tmp_path / ".codex" / "ticket-workspace"
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == (
        "# Ticket Automation Workspace State\n\n"
        "Files in this directory are local Ticket automation bookkeeping.\n"
        "Do not stage, commit, push, publish, or treat them as project history.\n"
        "Project truth remains in `docs/tickets/` ticket files and committed "
        "`## Change History` entries.\n"
    )


def test_workspace_pause_and_test_clear(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)

    pause_path = write_workspace_pause(tmp_path, reason="user_requested")

    assert pause_path == tmp_path / ".codex" / "ticket-workspace" / "pause.json"
    assert is_workspace_paused(tmp_path) is True

    _clear_workspace_pause_for_tests(tmp_path)

    assert is_workspace_paused(tmp_path) is False


def test_pause_workspace_rewrites_config_to_discussion_only(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)

    pause_workspace_automation(tmp_path, reason="user_requested")

    assert is_workspace_paused(tmp_path) is True
    assert read_local_config(tmp_path).mode == AutomationMode.DISCUSSION_ONLY


def test_mode_snapshots_are_thread_and_project_scoped(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)

    resolved = resolve_thread_mode(tmp_path, "thread-1")

    assert resolved.state == LocalConfigState.VALID
    assert resolved.mode == AutomationMode.AGENT_PRIMARY
    assert resolved.source == "config"

    write_local_config(tmp_path, AutomationMode.DISCUSSION_ONLY)
    second = resolve_thread_mode(tmp_path, "thread-1")
    other_thread = resolve_thread_mode(tmp_path, "thread-2")

    assert second.mode == AutomationMode.AGENT_PRIMARY
    assert second.source == "snapshot"
    assert other_thread.mode == AutomationMode.DISCUSSION_ONLY
    assert other_thread.source == "config"
    assert mode_snapshot_key(tmp_path, "thread-1") != mode_snapshot_key(tmp_path, "thread-2")


def test_missing_thread_id_is_invalid_for_runtime_resolution(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)

    resolved = resolve_thread_mode(tmp_path, "")

    assert resolved.state == LocalConfigState.SETUP_REQUIRED
    assert resolved.mode is None
    assert resolved.reason == "thread_id_required"


def test_pause_overrides_existing_snapshot(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)
    write_mode_snapshot(tmp_path, "thread-1", AutomationMode.AGENT_PRIMARY)
    write_workspace_pause(tmp_path, reason="repair")

    resolved = resolve_thread_mode(tmp_path, "thread-1")

    assert resolved.state == LocalConfigState.SETUP_REQUIRED
    assert resolved.mode is None
    assert resolved.reason == "workspace_paused"


def test_resume_requires_setup_choice_and_invalidates_snapshots(tmp_path: Path) -> None:
    _declare_workspace_ignored(tmp_path)
    snapshot = write_mode_snapshot(tmp_path, "thread-1", AutomationMode.AGENT_PRIMARY)
    write_workspace_pause(tmp_path, reason="repair")

    config_path = resume_workspace_automation(tmp_path, choice=SetupChoice.ASK_FIRST)

    assert is_workspace_paused(tmp_path) is False
    assert config_path.read_text(encoding="utf-8") == (
        '{"schema":"codex.ticket.local.v1","mode":"discussion_only"}\n'
    )
    assert not snapshot.path.exists()
    assert read_mode_snapshot(tmp_path, "thread-1") is None
