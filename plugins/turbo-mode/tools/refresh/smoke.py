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
    raw_root: Path
    handoff_plugin: Path
    archived_handoff_path: Path | None = None
    session_state_path: Path | None = None


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
        "raw_stdout_sha256": {result.label: result.stdout_sha256 for result in results},
        "raw_stderr_sha256": {result.label: result.stderr_sha256 for result in results},
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
    raw_root = smoke_root / "raw"
    for path in (
        local_only_run_root,
        smoke_root,
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
        raw_root=raw_root,
        handoff_plugin=codex_home / "plugins/cache/turbo-mode/handoff/1.7.0",
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
    handoff_archive_dir = state.smoke_repo / ".codex/handoffs/archive"
    handoff_state_dir = state.smoke_repo / ".codex/handoffs/.session-state"
    return (
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
                str(handoff_archive_dir),
                "--field",
                "archived_path",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} archive --source {_handoff_source_path(state)} "
                f"--archive-dir {handoff_archive_dir} "
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
                str(handoff_state_dir),
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
                f"--state-dir {handoff_state_dir} "
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
                str(handoff_state_dir),
                "--project",
                "smoke-repo",
                "--field",
                "archive_path",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} read-state "
                f"--state-dir {handoff_state_dir} "
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
                str(handoff_state_dir),
                "--state-path",
                "{session_state_path}",
            ),
            command_string=(
                "PYTHONDONTWRITEBYTECODE=1 python3 "
                f"{handoff_script} clear-state "
                f"--state-dir {handoff_state_dir} "
                "--state-path {session_state_path}"
            ),
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            after=_assert_state_cleared,
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
    return state.smoke_repo / ".codex/handoffs/2026-05-06_00-00_smoke.md"


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
    if state.session_state_path is not None and state.session_state_path.exists():
        stderr = _read_stderr(result).decode("utf-8", errors="replace")
        if "state cleanup warning:" in stderr:
            return
        fail(
            "run handoff clear-state smoke",
            "state file still exists",
            str(state.session_state_path),
        )


def _format_sequence(values: Sequence[str], state: _SmokeState) -> tuple[str, ...]:
    return tuple(_format_text(value, state) for value in values)


def _format_text(value: str, state: _SmokeState) -> str:
    archived = str(state.archived_handoff_path or "{archived_handoff_path}")
    session_state_path = (
        _require_session_state_path(state)
        if "{session_state_path}" in value
        else "{session_state_path}"
    )
    return value.format(
        archived_handoff_path=archived,
        session_state_path=session_state_path,
    )


def _require_session_state_path(state: _SmokeState) -> str:
    if state.session_state_path is None:
        fail("build smoke command", "session state path is not available yet", None)
    return str(state.session_state_path)


def _single_line_from_stdout(result: SmokeResult) -> Path:
    text = _read_stdout(result).decode("utf-8", errors="replace").strip()
    if "\n" in text or not text:
        fail("parse smoke stdout", "expected one path line", text)
    return Path(text)


def _read_stdout(result: SmokeResult) -> bytes:
    return Path(result.stdout_path).read_bytes()


def _read_stderr(result: SmokeResult) -> bytes:
    return Path(result.stderr_path).read_bytes()


def _write_private_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
    os.chmod(path, 0o600)
