from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .app_server_inventory import REAL_CODEX_HOME
from .models import fail

SMOKE_SCHEMA_VERSION = "turbo-mode-refresh-standard-smoke-v1"
SMOKE_TIER = "standard"
SESSION_ID = "plan06-smoke"


@dataclass(frozen=True)
class SmokeResult:
    label: str
    command_sequence: tuple[str, ...]
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    redacted_status: str
    stdout_path: str
    stderr_path: str


@dataclass(frozen=True)
class SmokeCommand:
    label: str
    argv: tuple[str, ...]
    command_string: str
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    stdin: bytes | Callable[[_SmokeState], bytes] | None = None
    before: Callable[[_SmokeState], None] | None = None
    after: Callable[[_SmokeState, SmokeResult], None] | None = None


@dataclass
class _SmokeState:
    local_only_run_root: Path
    codex_home: Path
    repo_root: Path
    smoke_root: Path
    smoke_repo: Path
    smoke_state: Path
    smoke_payloads: Path
    raw_root: Path
    handoff_plugin: Path
    ticket_plugin: Path
    archived_handoff_path: Path | None = None
    session_state_path: Path | None = None
    ticket_id: str | None = None


def run_standard_smoke(
    *,
    local_only_run_root: Path,
    codex_home: Path,
    repo_root: Path,
) -> dict[str, object]:
    state = _prepare_state(
        local_only_run_root=local_only_run_root,
        codex_home=codex_home,
        repo_root=repo_root,
    )
    commands = tuple(
        _build_smoke_plan(
            state=state,
            local_only_run_root=local_only_run_root,
            codex_home=codex_home,
            repo_root=repo_root,
        )
    )
    results: list[SmokeResult] = []
    for command in commands:
        result = _run_command(command, state=state)
        results.append(result)
        if result.exit_code != 0:
            break

    summary: dict[str, object] = {
        "schema_version": SMOKE_SCHEMA_VERSION,
        "selected_smoke_tier": SMOKE_TIER,
        "smoke_labels": [result.label for result in results],
        "results": [asdict(result) for result in results],
        "raw_stdout_sha256": {
            result.label: result.stdout_sha256 for result in results
        },
        "raw_stderr_sha256": {
            result.label: result.stderr_sha256 for result in results
        },
        "final_status": "passed"
        if results and all(result.exit_code == 0 for result in results)
        else "failed",
        "repo_root": str(repo_root),
        "codex_home": str(codex_home),
        "smoke_root": str(state.smoke_root),
    }
    _write_private_bytes(
        state.local_only_run_root / "standard-smoke.summary.json",
        json.dumps(summary, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return summary


def _prepare_state(
    *,
    local_only_run_root: Path,
    codex_home: Path,
    repo_root: Path,
) -> _SmokeState:
    if codex_home == REAL_CODEX_HOME and os.environ.get("ALLOW_REAL_CODEX_HOME_SMOKE") != "1":
        fail(
            "run standard smoke",
            "real Codex home plugin root requires explicit real-home run context",
            str(codex_home / "plugins/cache"),
        )
    smoke_root = local_only_run_root / "standard-smoke"
    smoke_repo = smoke_root / "repo"
    smoke_state = smoke_root / "state"
    smoke_payloads = smoke_repo / ".smoke-payloads"
    raw_root = smoke_root / "raw"
    for path in (
        local_only_run_root,
        smoke_root,
        smoke_repo / "docs/tickets",
        smoke_payloads,
        smoke_state,
        raw_root,
    ):
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    state = _SmokeState(
        local_only_run_root=local_only_run_root,
        codex_home=codex_home,
        repo_root=repo_root,
        smoke_root=smoke_root,
        smoke_repo=smoke_repo,
        smoke_state=smoke_state,
        smoke_payloads=smoke_payloads,
        raw_root=raw_root,
        handoff_plugin=codex_home / "plugins/cache/turbo-mode/handoff/1.6.0",
        ticket_plugin=codex_home / "plugins/cache/turbo-mode/ticket/1.4.0",
    )
    return state


def _build_smoke_plan(
    *,
    state: _SmokeState,
    local_only_run_root: Path,
    codex_home: Path,
    repo_root: Path,
) -> Sequence[SmokeCommand]:
    del local_only_run_root, codex_home, repo_root
    handoff_script = state.handoff_plugin / "scripts/session_state.py"
    defer_script = state.handoff_plugin / "scripts/defer.py"
    ticket_workflow = state.ticket_plugin / "scripts/ticket_workflow.py"
    ticket_read = state.ticket_plugin / "scripts/ticket_read.py"
    ticket_audit = state.ticket_plugin / "scripts/ticket_audit.py"
    commands: list[SmokeCommand] = [
        SmokeCommand(
            label="smoke-repo-git-init",
            argv=("git", "init"),
            command_string="git init",
            cwd=state.smoke_repo,
        ),
        SmokeCommand(
            label="handoff-session-state-archive",
            argv=(
                "python3",
                str(handoff_script),
                "archive",
                "--source",
                str(_handoff_source_path(state)),
                "--archive-dir",
                str(state.smoke_repo / "docs/handoffs/archive"),
                "--field",
                "archived_path",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} archive --source {_handoff_source_path(state)} "
                f"--archive-dir {state.smoke_repo / 'docs/handoffs/archive'} "
                "--field archived_path"
            ),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            before=_seed_handoff,
            after=_record_archived_handoff,
        ),
        SmokeCommand(
            label="handoff-session-state-write",
            argv=(
                "python3",
                str(handoff_script),
                "write-state",
                "--state-dir",
                str(state.smoke_repo / "docs/handoffs/.session-state"),
                "--project",
                "smoke-repo",
                "--archive-path",
                "{archived_handoff_path}",
                "--field",
                "state_path",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} write-state "
                f"--state-dir {state.smoke_repo / 'docs/handoffs/.session-state'} "
                "--project smoke-repo --archive-path {archived_handoff_path} "
                "--field state_path"
            ),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            after=_record_session_state,
        ),
        SmokeCommand(
            label="handoff-session-state-read",
            argv=(
                "python3",
                str(handoff_script),
                "read-state",
                "--state-dir",
                str(state.smoke_repo / "docs/handoffs/.session-state"),
                "--project",
                "smoke-repo",
                "--field",
                "archive_path",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} read-state "
                f"--state-dir {state.smoke_repo / 'docs/handoffs/.session-state'} "
                "--project smoke-repo --field archive_path"
            ),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            after=_assert_read_state_matches_archive,
        ),
        SmokeCommand(
            label="handoff-session-state-clear",
            argv=(
                "python3",
                str(handoff_script),
                "clear-state",
                "--state-dir",
                str(state.smoke_repo / "docs/handoffs/.session-state"),
                "--project",
                "smoke-repo",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} clear-state "
                f"--state-dir {state.smoke_repo / 'docs/handoffs/.session-state'} "
                "--project smoke-repo"
            ),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            after=_assert_state_cleared,
        ),
        SmokeCommand(
            label="handoff-defer",
            argv=("python3", str(defer_script), "--tickets-dir", "docs/tickets"),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{defer_script} --tickets-dir docs/tickets"
            ),
            cwd=state.smoke_repo,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            stdin=_defer_payload,
            after=_assert_defer_emitted_envelope,
        ),
    ]
    commands.extend(
        _ticket_workflow_pair(
            state,
            action="create",
            workflow_script=ticket_workflow,
            payload_name="ticket-create.json",
            payload_factory=_ticket_create_payload,
        )
    )
    commands.extend(
        [
            SmokeCommand(
                label="ticket-list-open",
                argv=(
                    "python3",
                    "-B",
                    str(ticket_read),
                    "list",
                    "docs/tickets",
                    "--status",
                    "open",
                ),
                command_string=(
                    f"python3 -B {ticket_read} list docs/tickets --status open"
                ),
                cwd=state.smoke_repo,
            ),
            SmokeCommand(
                label="ticket-query-created",
                argv=(
                    "python3",
                    "-B",
                    str(ticket_read),
                    "query",
                    "docs/tickets",
                    "{ticket_id}",
                ),
                command_string=(
                    f"python3 -B {ticket_read} query docs/tickets {{ticket_id}}"
                ),
                cwd=state.smoke_repo,
            ),
        ]
    )
    commands.extend(
        _ticket_workflow_pair(
            state,
            action="update",
            workflow_script=ticket_workflow,
            payload_name="ticket-update.json",
            payload_factory=_ticket_update_payload,
        )
    )
    commands.append(
        SmokeCommand(
            label="ticket-query-updated",
            argv=(
                "python3",
                "-B",
                str(ticket_read),
                "query",
                "docs/tickets",
                "{ticket_id}",
            ),
            command_string=f"python3 -B {ticket_read} query docs/tickets {{ticket_id}}",
            cwd=state.smoke_repo,
        )
    )
    commands.extend(
        _ticket_workflow_pair(
            state,
            action="close",
            workflow_script=ticket_workflow,
            payload_name="ticket-close.json",
            payload_factory=_ticket_close_payload,
        )
    )
    commands.extend(
        _ticket_workflow_pair(
            state,
            action="reopen",
            workflow_script=ticket_workflow,
            payload_name="ticket-reopen.json",
            payload_factory=_ticket_reopen_payload,
        )
    )
    commands.append(
        SmokeCommand(
            label="ticket-audit-repair-dry-run",
            argv=(
                "python3",
                "-B",
                str(ticket_audit),
                "repair",
                "docs/tickets",
                "--dry-run",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                f"{ticket_audit} repair docs/tickets --dry-run"
            ),
            cwd=state.smoke_repo,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
    )
    return tuple(commands)


def _ticket_workflow_pair(
    state: _SmokeState,
    *,
    action: str,
    workflow_script: Path,
    payload_name: str,
    payload_factory: Callable[[_SmokeState], dict[str, object]],
) -> Sequence[SmokeCommand]:
    prepare = _ticket_workflow_command(
        state,
        action=action,
        phase="prepare",
        workflow_script=workflow_script,
        payload_name=payload_name,
        payload_factory=payload_factory,
    )
    execute = _ticket_workflow_command(
        state,
        action=action,
        phase="execute",
        workflow_script=workflow_script,
        payload_name=payload_name,
        payload_factory=payload_factory,
    )
    return (
        _ticket_hook_command(state, target=prepare),
        prepare,
        _ticket_hook_command(state, target=execute),
        execute,
    )


def _ticket_workflow_command(
    state: _SmokeState,
    *,
    action: str,
    phase: str,
    workflow_script: Path,
    payload_name: str,
    payload_factory: Callable[[_SmokeState], dict[str, object]],
) -> SmokeCommand:
    payload_path = state.smoke_payloads / payload_name
    label = f"ticket-{action}-{phase}"
    after = _record_ticket_id if action == "create" and phase == "execute" else None
    return SmokeCommand(
        label=label,
        argv=("python3", "-B", str(workflow_script), phase, str(payload_path)),
        command_string=f"python3 -B {workflow_script} {phase} {payload_path}",
        cwd=state.smoke_repo,
        before=lambda active_state: _ensure_payload(
            payload_path,
            payload_factory(active_state),
        ),
        after=after,
    )


def _ticket_hook_command(state: _SmokeState, *, target: SmokeCommand) -> SmokeCommand:
    guard = state.ticket_plugin / "hooks/ticket_engine_guard.py"
    return SmokeCommand(
        label=f"ticket-hook-{target.label}",
        argv=("python3", str(guard)),
        command_string=f"CODEX_PLUGIN_ROOT={state.ticket_plugin} python3 {guard}",
        cwd=state.smoke_repo,
        env={"CODEX_PLUGIN_ROOT": str(state.ticket_plugin)},
        before=target.before,
        stdin=lambda active_state: _ticket_hook_input(target, active_state),
        after=lambda active_state, result: _assert_ticket_hook_allowed(
            active_state,
            target=target,
            result=result,
        ),
    )


def _run_command(command: SmokeCommand, *, state: _SmokeState) -> SmokeResult:
    if command.before is not None:
        command.before(state)
    argv = _format_sequence(command.argv, state)
    command_string = _format_text(command.command_string, state)
    command_env = {
        "CODEX_HOME": str(state.codex_home),
        "TURBO_MODE_SMOKE_LABEL": command.label,
        **dict(command.env or {}),
    }
    env = {
        **_minimal_subprocess_env(),
        **command_env,
    }
    cwd = command.cwd or state.smoke_repo
    _validate_smoke_command_authority(
        codex_home=state.codex_home,
        argv=argv,
        command_string=command_string,
        cwd=cwd,
        env=env,
    )
    stdin = command.stdin(state) if callable(command.stdin) else command.stdin
    completed = subprocess.run(
        list(argv),
        cwd=str(cwd),
        env=env,
        input=stdin,
        capture_output=True,
        check=False,
    )
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    stdout_path = state.raw_root / f"{command.label}.stdout.txt"
    stderr_path = state.raw_root / f"{command.label}.stderr.txt"
    _write_private_bytes(stdout_path, stdout)
    _write_private_bytes(stderr_path, stderr)
    result = SmokeResult(
        label=command.label,
        command_sequence=argv,
        exit_code=completed.returncode,
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        redacted_status="passed" if completed.returncode == 0 else "failed",
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )
    if completed.returncode == 0 and command.after is not None:
        command.after(state, result)
    return result


def _validate_smoke_command_authority(
    *,
    codex_home: Path,
    argv: Sequence[str],
    command_string: str,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    if codex_home == REAL_CODEX_HOME:
        return
    checked_values = [*argv, command_string, str(cwd), *env.values()]
    real_home_text = str(REAL_CODEX_HOME)
    for value in checked_values:
        if real_home_text in value:
            fail("validate smoke command", "live Codex home path in isolated smoke", value)


def _minimal_subprocess_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path_value = os.environ.get("PATH")
    if path_value is not None:
        env["PATH"] = os.pathsep.join(
            entry for entry in path_value.split(os.pathsep) if str(REAL_CODEX_HOME) not in entry
        )
    for key in ("LANG", "LC_ALL"):
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    return env


def _seed_handoff(state: _SmokeState) -> None:
    handoff_path = _handoff_source_path(state)
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(
        """---
date: 2026-05-06
time: "00:00"
created_at: "2026-05-06T00:00:00Z"
session_id: 00000000-0000-4000-8000-000000000006
project: smoke-repo
title: Smoke
type: summary
files: []
---

Smoke handoff.
""",
        encoding="utf-8",
    )


def _handoff_source_path(state: _SmokeState) -> Path:
    return state.smoke_repo / "docs/handoffs/2026-05-06_00-00_smoke.md"


def _record_archived_handoff(state: _SmokeState, result: SmokeResult) -> None:
    archive_path = _single_line_from_stdout(result)
    state.archived_handoff_path = archive_path
    if not archive_path.exists():
        fail("run handoff archive smoke", "archived handoff path missing", str(archive_path))
    if _handoff_source_path(state).exists():
        fail(
            "run handoff archive smoke",
            "source handoff was not moved",
            str(_handoff_source_path(state)),
        )


def _record_session_state(state: _SmokeState, result: SmokeResult) -> None:
    state_path = _single_line_from_stdout(result)
    state.session_state_path = state_path
    if not state_path.exists():
        fail("run handoff write-state smoke", "state path missing", str(state_path))


def _assert_read_state_matches_archive(state: _SmokeState, result: SmokeResult) -> None:
    if state.archived_handoff_path is None:
        fail("run handoff read-state smoke", "archive path not recorded", None)
    if _single_line_from_stdout(result) != state.archived_handoff_path:
        fail(
            "run handoff read-state smoke",
            "read-state archive path mismatch",
            _read_stdout(result).decode("utf-8", errors="replace").strip(),
        )


def _assert_state_cleared(state: _SmokeState, result: SmokeResult) -> None:
    del result
    if state.session_state_path is not None and state.session_state_path.exists():
        fail(
            "run handoff clear-state smoke",
            "state file still exists",
            str(state.session_state_path),
        )


def _defer_payload(state: _SmokeState) -> bytes:
    del state
    return (
        json.dumps(
            {
                "summary": "Smoke deferred task",
                "problem": "Verify installed defer command shape.",
                "source_type": "plan",
                "source_ref": "plan06-smoke",
                "session_id": SESSION_ID,
                "acceptance_criteria": [
                    "Installed defer command emits an envelope.",
                ],
                "priority": "low",
                "effort": "S",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _assert_defer_emitted_envelope(state: _SmokeState, result: SmokeResult) -> None:
    stdout = _read_stdout(result).decode("utf-8", errors="replace")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {}
    if payload.get("status") not in {"ok", None}:
        fail("run handoff defer smoke", "defer status was not ok", payload)
    envelope_root = state.smoke_repo / "docs/tickets/.envelopes"
    if not any(envelope_root.glob("*")):
        fail("run handoff defer smoke", "deferred envelope missing", str(envelope_root))


def _ticket_create_payload(state: _SmokeState) -> dict[str, object]:
    del state
    return {
        "action": "create",
        "fields": {
            "title": "Smoke ticket",
            "problem": "Verify installed Ticket command shape.",
            "priority": "low",
            "status": "open",
            "tags": ["smoke"],
            "acceptance_criteria": ["Smoke read/query can find this ticket."],
            "key_files": [],
        },
    }


def _ticket_update_payload(state: _SmokeState) -> dict[str, object]:
    return {
        "action": "update",
        "ticket_id": _require_ticket_id(state),
        "fields": {"tags": ["smoke", "updated"]},
    }


def _ticket_close_payload(state: _SmokeState) -> dict[str, object]:
    return {
        "action": "close",
        "ticket_id": _require_ticket_id(state),
        "fields": {"resolution": "done"},
    }


def _ticket_reopen_payload(state: _SmokeState) -> dict[str, object]:
    return {
        "action": "reopen",
        "ticket_id": _require_ticket_id(state),
        "fields": {"reopen_reason": "Plan 06 smoke verifies reopen lifecycle."},
    }


def _ticket_hook_input(target: SmokeCommand, state: _SmokeState) -> bytes:
    return (
        json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": _format_text(target.command_string, state)},
                "cwd": str(state.smoke_repo),
                "session_id": SESSION_ID,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _assert_ticket_hook_allowed(
    state: _SmokeState,
    *,
    target: SmokeCommand,
    result: SmokeResult,
) -> None:
    stdout = _read_stdout(result).decode("utf-8", errors="replace")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        fail("run Ticket hook smoke", f"hook output was not JSON: {exc}", stdout)
    decision = payload.get("hookSpecificOutput", {}).get("permissionDecision")
    if decision != "allow":
        fail("run Ticket hook smoke", "ticket hook did not allow command", payload)
    payload_path = Path(_format_sequence(target.argv, state)[-1])
    command_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    expected = {
        "hook_injected": True,
        "hook_request_origin": "user",
        "session_id": SESSION_ID,
    }
    for key, expected_value in expected.items():
        if command_payload.get(key) != expected_value:
            fail(
                "run Ticket hook smoke",
                f"ticket hook did not inject {key}",
                command_payload.get(key),
            )


def _record_ticket_id(state: _SmokeState, result: SmokeResult) -> None:
    stdout = _read_stdout(result).decode("utf-8", errors="replace")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        fail("run Ticket create smoke", f"create output was not JSON: {exc}", stdout)
    ticket_id = payload.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        fail("run Ticket create smoke", "missing ticket_id", payload)
    state.ticket_id = ticket_id
    ticket_files = list((state.smoke_repo / "docs/tickets").glob("*.md"))
    if len(ticket_files) != 1:
        fail(
            "run Ticket create smoke",
            "expected one ticket file",
            [str(path) for path in ticket_files],
        )


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    forbidden = {"session_id", "request_origin", "hook_injected", "hook_request_origin"}
    leaked = sorted(forbidden.intersection(payload))
    if leaked:
        fail("write smoke payload", "payload pre-seeded trust fields", leaked)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)


def _ensure_payload(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        return
    _write_payload(path, payload)


def _format_sequence(values: Sequence[str], state: _SmokeState) -> tuple[str, ...]:
    return tuple(_format_text(value, state) for value in values)


def _format_text(value: str, state: _SmokeState) -> str:
    archived = str(state.archived_handoff_path or "{archived_handoff_path}")
    return value.format(
        archived_handoff_path=archived,
        ticket_id=_require_ticket_id(state) if "{ticket_id}" in value else "{ticket_id}",
    )


def _require_ticket_id(state: _SmokeState) -> str:
    if state.ticket_id is None:
        fail("build smoke command", "ticket id is not available yet", None)
    return state.ticket_id


def _single_line_from_stdout(result: SmokeResult) -> Path:
    text = _read_stdout(result).decode("utf-8", errors="replace").strip()
    if "\n" in text or not text:
        fail("parse smoke stdout", "expected one path line", text)
    return Path(text)


def _read_stdout(result: SmokeResult) -> bytes:
    return Path(result.stdout_path).read_bytes()


def _write_private_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
    os.chmod(path, 0o600)
