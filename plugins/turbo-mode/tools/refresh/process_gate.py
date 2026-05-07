from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

EXCLUSIVE_WINDOW_STATUS = "exclusive_window_observed_by_process_samples"
PROCESS_GATE_SCHEMA_VERSION = "turbo-mode-refresh-process-gate-v1"
TICKET_HOOK_ROOT = "/plugins/cache/turbo-mode/ticket/1.4.0/hooks/"


@dataclass(frozen=True)
class ProcessRow:
    pid: int
    ppid: int
    command: str
    argv: Sequence[str]
    executable_basename: str | None


@dataclass(frozen=True)
class ProcessGateFinding:
    pid: int
    classification: str
    blocking: bool
    command_marker: str


def parse_ps_output(text: str) -> Sequence[ProcessRow]:
    rows: list[ProcessRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("PID ") or line.upper().startswith("PID\t"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            rows.append(_unparsable_row(line))
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            rows.append(_unparsable_row(line))
            continue
        command = parts[2]
        argv = _parse_argv(command)
        rows.append(
            ProcessRow(
                pid=pid,
                ppid=ppid,
                command=command,
                argv=argv,
                executable_basename=_executable_basename(argv),
            )
        )
    return tuple(rows)


def classify_processes(
    rows: Sequence[ProcessRow],
    *,
    refresh_pid: int,
    refresh_command: Sequence[str],
    recorded_child_app_server_pids: frozenset[int],
) -> Sequence[ProcessGateFinding]:
    return tuple(
        _classify_row(
            row,
            refresh_pid=refresh_pid,
            refresh_command=refresh_command,
            recorded_child_app_server_pids=recorded_child_app_server_pids,
        )
        for row in rows
    )


def capture_process_gate(
    *,
    label: str,
    local_only_run_root: Path,
    refresh_pid: int,
    refresh_command: Sequence[str],
    recorded_child_app_server_pids: frozenset[int],
) -> dict[str, object]:
    completed = subprocess.run(
        ["ps", "-ww", "-axo", "pid,ppid,command"],
        capture_output=True,
        text=True,
        check=True,
    )
    raw_listing = completed.stdout
    rows = parse_ps_output(raw_listing)
    findings = classify_processes(
        rows,
        refresh_pid=refresh_pid,
        refresh_command=refresh_command,
        recorded_child_app_server_pids=recorded_child_app_server_pids,
    )
    blockers = [finding for finding in findings if finding.blocking]
    summary: dict[str, object] = {
        "schema_version": PROCESS_GATE_SCHEMA_VERSION,
        "label": label,
        "blocked_process_count": len(blockers),
        "blocking_classifications": sorted(
            {finding.classification for finding in blockers}
        ),
        "raw_process_sha256": hashlib.sha256(raw_listing.encode("utf-8")).hexdigest(),
        "findings": [asdict(finding) for finding in findings],
    }
    if not blockers:
        summary["exclusivity_status"] = EXCLUSIVE_WINDOW_STATUS

    local_only_run_root.mkdir(parents=True, exist_ok=True)
    raw_path = local_only_run_root / f"process-{label}.txt"
    summary_path = local_only_run_root / f"process-{label}.summary.json"
    _write_private_bytes(raw_path, raw_listing.encode("utf-8"))
    _write_private_bytes(
        summary_path,
        json.dumps(summary, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return summary


def _classify_row(
    row: ProcessRow,
    *,
    refresh_pid: int,
    refresh_command: Sequence[str],
    recorded_child_app_server_pids: frozenset[int],
) -> ProcessGateFinding:
    if row.pid == refresh_pid:
        return _finding(row, "self-refresh-tool", False, "refresh-pid")
    if _is_recorded_child_app_server(
        row,
        refresh_pid=refresh_pid,
        recorded_child_app_server_pids=recorded_child_app_server_pids,
    ):
        return _finding(row, "allowed-child-app-server", False, "recorded-child")
    if _is_exact_shell_wrapper(row.argv, refresh_command):
        return _finding(row, "self-refresh-tool", False, "exact-shell-wrapper")
    if not row.argv and _contains_high_risk_marker(row.command):
        return _finding(row, "uncertain-high-risk", True, _first_high_risk_marker(row.command))
    if _is_ambiguous_shell_wrapper(row.argv):
        return _finding(row, "uncertain-high-risk", True, "shell-wrapper")
    if _is_codex_desktop(row):
        return _finding(row, "codex-desktop", True, "Codex")
    if _is_truncated_codex_app_server(row):
        return _finding(row, "uncertain-high-risk", True, "codex-app-server")
    if _is_codex_app_server(row.argv):
        return _finding(row, "codex-app-server", True, "codex app-server")
    if _is_codex_cli(row):
        return _finding(row, "codex-cli", True, "codex")
    if _is_ticket_hook_runtime(row):
        return _finding(row, "ticket-hook-runtime", True, "ticket-hook-runtime")
    if _is_ticket_hook_path_consumer(row):
        return _finding(row, "ticket-hook-path-consumer", True, "ticket-hook-path")
    return _finding(row, "non-blocking", False, "none")


def _unparsable_row(command: str) -> ProcessRow:
    return ProcessRow(pid=-1, ppid=-1, command=command, argv=(), executable_basename=None)


def _parse_argv(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return ()


def _executable_basename(argv: Sequence[str]) -> str | None:
    if not argv:
        return None
    return Path(argv[0]).name


def _finding(
    row: ProcessRow,
    classification: str,
    blocking: bool,
    marker: str,
) -> ProcessGateFinding:
    return ProcessGateFinding(
        pid=row.pid,
        classification=classification,
        blocking=blocking,
        command_marker=marker,
    )


def _is_recorded_child_app_server(
    row: ProcessRow,
    *,
    refresh_pid: int,
    recorded_child_app_server_pids: frozenset[int],
) -> bool:
    if row.pid not in recorded_child_app_server_pids or row.ppid != refresh_pid:
        return False
    return _is_codex_app_server(row.argv) and _argv_contains_listen_stdio(row.argv)


def _argv_contains_listen_stdio(argv: Sequence[str]) -> bool:
    for index, arg in enumerate(argv):
        if arg == "--listen" and index + 1 < len(argv) and argv[index + 1] == "stdio://":
            return True
        if arg == "--listen=stdio://":
            return True
    return False


def _is_exact_shell_wrapper(argv: Sequence[str], refresh_command: Sequence[str]) -> bool:
    if len(argv) < 3 or Path(argv[0]).name not in {"bash", "sh", "zsh"}:
        return False
    if argv[1] not in {"-c", "-lc"}:
        return False
    try:
        wrapped = tuple(shlex.split(argv[2]))
    except ValueError:
        return False
    return wrapped == tuple(refresh_command)


def _is_ambiguous_shell_wrapper(argv: Sequence[str]) -> bool:
    if len(argv) < 3 or Path(argv[0]).name not in {"bash", "sh", "zsh"}:
        return False
    if argv[1] not in {"-c", "-lc"}:
        return False
    return _contains_high_risk_marker(argv[2])


def _is_codex_desktop(row: ProcessRow) -> bool:
    basename = row.executable_basename
    return basename == "Codex" or "Codex.app/Contents/MacOS/Codex" in row.command


def _is_codex_app_server(argv: Sequence[str]) -> bool:
    if not argv or Path(argv[0]).name != "codex":
        return False
    return len(argv) > 1 and argv[1] == "app-server"


def _is_truncated_codex_app_server(row: ProcessRow) -> bool:
    if not _is_codex_app_server(row.argv):
        return False
    return any(
        arg == "--listen" and index + 1 == len(row.argv)
        for index, arg in enumerate(row.argv)
    )


def _is_codex_cli(row: ProcessRow) -> bool:
    if row.executable_basename == "codex":
        return True
    return bool(row.argv and Path(row.argv[0]).name == "codex")


def _is_ticket_hook_runtime(row: ProcessRow) -> bool:
    if not row.argv:
        return False
    command_text = " ".join(row.argv)
    return (
        "ticket_engine_guard.py" in command_text
        or "ticket_workflow.py" in command_text
    )


def _is_ticket_hook_path_consumer(row: ProcessRow) -> bool:
    return TICKET_HOOK_ROOT in row.command


def _contains_high_risk_marker(command: str) -> bool:
    return _first_high_risk_marker(command) != "none"


def _first_high_risk_marker(command: str) -> str:
    markers: list[tuple[str, str]] = [
        ("codex-app-server", r"\bcodex\s+app-server\b"),
        ("codex-cli", r"(^|[\s/])codex(\s|$)"),
        ("codex-desktop", r"Codex(\.app|/Contents/MacOS/Codex|\s|$)"),
        ("ticket-engine", r"ticket_engine_"),
        ("ticket-workflow", r"ticket_workflow\.py"),
        ("ticket-hook-path", re.escape(TICKET_HOOK_ROOT)),
    ]
    for marker, pattern in markers:
        if re.search(pattern, command):
            return marker
    return "none"


def _write_private_bytes(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.chmod(path, 0o600)
