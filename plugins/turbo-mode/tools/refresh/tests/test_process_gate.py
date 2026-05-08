from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest
import refresh.process_gate as process_gate_module
from refresh.models import RefreshError
from refresh.process_gate import (
    ProcessGateFinding,
    ProcessRow,
    capture_process_gate,
    classify_processes,
    parse_ps_output,
)

REFRESH_PID = 4000
REFRESH_COMMAND = (
    "python3",
    "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
    "--guarded-refresh",
)


TICKET_GUARD_COMMAND = (
    "python3 "
    "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/"
    "ticket_engine_guard.py"
)
TICKET_HOOKS_CONSUMER_COMMAND = (
    "python3 -c "
    "open('/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json')"
)
REFRESH_COMMAND_TEXT = (
    "python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py "
    "--guarded-refresh"
)
AMBIGUOUS_WRAPPER_TEXT = f"{REFRESH_COMMAND_TEXT} && codex exec true"


def row(
    pid: int,
    command: str,
    *,
    ppid: int = 1,
    argv: tuple[str, ...] | None = None,
) -> ProcessRow:
    active_argv = argv if argv is not None else tuple(command.split())
    basename = Path(active_argv[0]).name if active_argv else None
    return ProcessRow(
        pid=pid,
        ppid=ppid,
        command=command,
        argv=active_argv,
        executable_basename=basename,
    )


def only_finding(process_row: ProcessRow) -> ProcessGateFinding:
    findings = classify_processes(
        [process_row],
        refresh_pid=REFRESH_PID,
        refresh_command=REFRESH_COMMAND,
        recorded_child_app_server_pids=frozenset({4100}),
    )
    assert len(findings) == 1
    return findings[0]


def assert_classification(process_row: ProcessRow, classification: str, *, blocking: bool) -> None:
    finding = only_finding(process_row)
    assert finding.classification == classification
    assert finding.blocking is blocking


def test_parse_ps_output_parses_pid_ppid_command_rows() -> None:
    rows = parse_ps_output(
        "  PID  PPID COMMAND\n"
        "  123     1 /Applications/Codex.app/Contents/MacOS/Codex\n"
        "  456   123 codex app-server --listen stdio://\n"
    )
    assert rows == (
        ProcessRow(
            pid=123,
            ppid=1,
            command="/Applications/Codex.app/Contents/MacOS/Codex",
            argv=("/Applications/Codex.app/Contents/MacOS/Codex",),
            executable_basename="Codex",
        ),
        ProcessRow(
            pid=456,
            ppid=123,
            command="codex app-server --listen stdio://",
            argv=("codex", "app-server", "--listen", "stdio://"),
            executable_basename="codex",
        ),
    )


def test_unparsable_ps_row_is_uncertain_high_risk() -> None:
    rows = parse_ps_output("not-a-process-row\n")

    assert rows == (
        ProcessRow(
            pid=-1,
            ppid=-1,
            command="not-a-process-row",
            argv=(),
            executable_basename=None,
        ),
    )
    assert_classification(rows[0], "uncertain-high-risk", blocking=True)


def test_capture_process_gate_wraps_ps_nonzero_as_refresh_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(2, ["ps"], stderr="ps failed")

    monkeypatch.setattr(process_gate_module.subprocess, "run", fake_run)

    with pytest.raises(RefreshError, match="ps exited non-zero"):
        capture_process_gate(
            label="preflight",
            local_only_run_root=tmp_path / "run",
            refresh_pid=REFRESH_PID,
            refresh_command=REFRESH_COMMAND,
            recorded_child_app_server_pids=frozenset(),
        )


def test_codex_desktop_is_blocking() -> None:
    assert_classification(
        row(100, "/Applications/Codex.app/Contents/MacOS/Codex"),
        "codex-desktop",
        blocking=True,
    )


def test_codex_cli_shapes_block_by_default() -> None:
    commands = [
        "codex",
        "codex exec echo ok",
        "codex resume",
        "codex login",
        "codex mcp",
        "codex plugin list",
    ]
    for index, command in enumerate(commands, start=1):
        assert_classification(row(100 + index, command), "codex-cli", blocking=True)


def test_unrelated_codex_app_server_blocks() -> None:
    assert_classification(
        row(200, "codex app-server --listen stdio://"),
        "codex-app-server",
        blocking=True,
    )


def test_installed_ticket_hook_runtime_blocks() -> None:
    assert_classification(
        row(300, TICKET_GUARD_COMMAND),
        "ticket-hook-runtime",
        blocking=True,
    )


def test_ticket_hook_path_consumer_blocks() -> None:
    assert_classification(
        row(
            301,
            TICKET_HOOKS_CONSUMER_COMMAND,
            argv=(
                "python3",
                "-c",
                "open('/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json')",
            ),
        ),
        "ticket-hook-path-consumer",
        blocking=True,
    )


def test_harmless_codex_substring_path_is_non_blocking() -> None:
    assert_classification(
        row(400, "python3 /tmp/codex-not-a-process/file.txt"),
        "non-blocking",
        blocking=False,
    )


def test_refresh_tool_pid_is_self_even_when_command_contains_codex() -> None:
    assert_classification(
        row(REFRESH_PID, "python3 /tmp/codex-not-a-process/refresh.py"),
        "self-refresh-tool",
        blocking=False,
    )


def test_recorded_direct_child_app_server_is_allowed() -> None:
    assert_classification(
        row(
            4100,
            "codex app-server --listen stdio://",
            ppid=REFRESH_PID,
            argv=("codex", "app-server", "--listen", "stdio://"),
        ),
        "allowed-child-app-server",
        blocking=False,
    )


def test_recorded_child_pid_without_exact_app_server_shape_blocks() -> None:
    assert_classification(
        row(
            4100,
            "codex app-server --listen tcp://127.0.0.1:0",
            ppid=REFRESH_PID,
            argv=("codex", "app-server", "--listen", "tcp://127.0.0.1:0"),
        ),
        "codex-app-server",
        blocking=True,
    )


def test_shell_wrapper_is_allowed_only_when_it_exactly_wraps_refresh_command() -> None:
    assert_classification(
        row(
            500,
            f"/bin/zsh -lc '{REFRESH_COMMAND_TEXT}'",
            argv=("/bin/zsh", "-lc", REFRESH_COMMAND_TEXT),
        ),
        "self-refresh-tool",
        blocking=False,
    )


def test_shell_wrapper_blocks_when_inner_command_is_ambiguous() -> None:
    assert_classification(
        row(
            501,
            f"/bin/zsh -lc '{AMBIGUOUS_WRAPPER_TEXT}'",
            argv=("/bin/zsh", "-lc", AMBIGUOUS_WRAPPER_TEXT),
        ),
        "uncertain-high-risk",
        blocking=True,
    )


def test_truncated_high_risk_rows_block_as_uncertain() -> None:
    markers = [
        "codex app-server --listen",
        "/Applications/Codex.app/Contents",
        "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_",
        "python3 ticket_workflow.py",
    ]
    for index, command in enumerate(markers, start=1):
        assert_classification(
            ProcessRow(
                pid=600 + index,
                ppid=1,
                command=command,
                argv=(),
                executable_basename=None,
            ),
            "uncertain-high-risk",
            blocking=True,
        )


def test_unparsable_codex_app_server_row_blocks_as_uncertain() -> None:
    assert_classification(
        ProcessRow(
            pid=-1,
            ppid=-1,
            command="??? codex app-server --listen stdio://",
            argv=(),
            executable_basename=None,
        ),
        "uncertain-high-risk",
        blocking=True,
    )


def test_non_child_codex_row_is_never_non_blocking() -> None:
    finding = only_finding(
        row(
            700,
            "codex app-server --listen stdio://",
            ppid=999,
            argv=("codex", "app-server", "--listen", "stdio://"),
        )
    )
    assert finding.blocking is True
    assert finding.classification != "non-blocking"


def test_capture_process_gate_writes_private_raw_listing_and_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    completed = subprocess.CompletedProcess(
        ["ps"],
        0,
        stdout=(
            "  PID  PPID COMMAND\n"
            f" {REFRESH_PID}  999 {REFRESH_COMMAND_TEXT}\n"
            " 9100    1 python3 /tmp/codex-not-a-process/file.txt\n"
        ),
        stderr="",
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command == ["ps", "-ww", "-axo", "pid,ppid,command"]
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is True
        return completed

    monkeypatch.setattr(process_gate_module.subprocess, "run", fake_run)
    summary = capture_process_gate(
        label="before-snapshot",
        local_only_run_root=tmp_path,
        refresh_pid=REFRESH_PID,
        refresh_command=REFRESH_COMMAND,
        recorded_child_app_server_pids=frozenset(),
    )
    raw_path = tmp_path / "process-before-snapshot.txt"
    summary_path = tmp_path / "process-before-snapshot.summary.json"
    assert stat.S_IMODE(raw_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(summary_path.stat().st_mode) == 0o600
    assert summary["blocked_process_count"] == 0
    assert summary["blocking_classifications"] == []
    assert summary["raw_process_sha256"]
    assert summary["exclusivity_status"] == "exclusive_window_observed_by_process_samples"
    assert json.loads(summary_path.read_text(encoding="utf-8")) == summary


def test_capture_process_gate_omits_exclusivity_status_when_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    completed = subprocess.CompletedProcess(
        ["ps"],
        0,
        stdout=(
            "  PID  PPID COMMAND\n"
            f" {REFRESH_PID}  999 {REFRESH_COMMAND_TEXT}\n"
            " 9200    1 codex exec echo unsafe\n"
        ),
        stderr="",
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return completed

    monkeypatch.setattr(process_gate_module.subprocess, "run", fake_run)
    summary = capture_process_gate(
        label="before-snapshot",
        local_only_run_root=tmp_path,
        refresh_pid=REFRESH_PID,
        refresh_command=REFRESH_COMMAND,
        recorded_child_app_server_pids=frozenset(),
    )
    assert summary["blocked_process_count"] == 1
    assert summary["blocking_classifications"] == ["codex-cli"]
    assert "exclusivity_status" not in summary
