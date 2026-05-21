from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refresh.app_server_inventory import REQUEST_TIMEOUT_SECONDS, resolve_codex_executable
from refresh.models import RefreshError, fail

INITIALIZE_REQUEST_ID = 0
THREAD_START_REQUEST_ID = 1
TURN_START_REQUEST_ID = 2
APPROVAL_REQUEST_METHODS = frozenset(
    {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "item/permissions/requestApproval",
    }
)


@dataclass(frozen=True)
class PreflightLayout:
    project_root: Path
    preflight_root: Path
    contained_root: Path
    tickets_dir: Path
    payload_path: Path
    out_path: Path
    installed_ticket_root: Path
    probe_command: str
    prompt_text: str


@dataclass(frozen=True)
class TranscriptSummary:
    request_methods: tuple[str, ...]
    approval_request_methods: tuple[str, ...]
    command_execution_count: int
    ticket_hook_completed_count: int
    turn_id: str | None
    probe_command_seen: bool
    thread_start_ephemeral: bool
    failure_reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


def build_probe_command(*, installed_ticket_root: Path, payload_path: Path) -> str:
    return (
        f"uv run python -B {installed_ticket_root}/scripts/ticket_engine_agent.py "
        f"execute {payload_path}"
    )


def build_probe_prompt(command: str) -> str:
    return (
        "Run exactly one Bash command and nothing else.\n"
        f"Command: {command}\n"
        "Do not inspect files, do not explain, do not ask for approval, "
        "and do not run any other command."
    )


def build_thread_start_request(*, contained_root: Path) -> dict[str, Any]:
    return {
        "id": THREAD_START_REQUEST_ID,
        "method": "thread/start",
        "params": {
            "approvalPolicy": "never",
            "cwd": str(contained_root),
            "ephemeral": True,
            "runtimeWorkspaceRoots": [str(contained_root)],
        },
    }


def build_turn_start_request(
    *,
    thread_id: str,
    contained_root: Path,
    prompt_text: str,
) -> dict[str, Any]:
    return {
        "id": TURN_START_REQUEST_ID,
        "method": "turn/start",
        "params": {
            "threadId": thread_id,
            "approvalPolicy": "never",
            "runtimeWorkspaceRoots": [str(contained_root)],
            "sandboxPolicy": {
                "type": "workspaceWrite",
                "writableRoots": [str(contained_root)],
            },
            "input": [{"type": "text", "text": prompt_text}],
        },
    }


def prepare_preflight_layout(
    *,
    project_root: Path,
    contained_root: Path,
    installed_ticket_root: Path,
    out_path: Path,
) -> PreflightLayout:
    resolved_project_root = project_root.resolve(strict=False)
    preflight_root = resolved_project_root / ".codex" / "ticket-runtime-smoke-preflight"
    resolved_contained_root = contained_root.resolve(strict=False)
    resolved_out_path = out_path.resolve(strict=False)
    _assert_under_root(
        candidate=resolved_contained_root,
        allowed_root=preflight_root,
        operation="prepare preflight layout",
    )
    _assert_under_root(
        candidate=resolved_out_path,
        allowed_root=preflight_root,
        operation="prepare preflight layout",
    )

    tickets_dir = resolved_contained_root / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    payload_path = resolved_contained_root / "payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tickets_dir": str(tickets_dir)}
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    probe_command = build_probe_command(
        installed_ticket_root=installed_ticket_root.resolve(strict=False),
        payload_path=payload_path,
    )
    prompt_text = build_probe_prompt(probe_command)
    return PreflightLayout(
        project_root=resolved_project_root,
        preflight_root=preflight_root,
        contained_root=resolved_contained_root,
        tickets_dir=tickets_dir,
        payload_path=payload_path,
        out_path=resolved_out_path,
        installed_ticket_root=installed_ticket_root.resolve(strict=False),
        probe_command=probe_command,
        prompt_text=prompt_text,
    )


def write_transcript_jsonl(out_path: Path, transcript: list[dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in transcript
        ),
        encoding="utf-8",
    )


def analyze_transcript(
    transcript: list[dict[str, Any]],
    *,
    probe_command: str,
    installed_ticket_root: Path,
) -> TranscriptSummary:
    request_methods: list[str] = []
    approval_request_methods: list[str] = []
    command_execution_count = 0
    ticket_hook_completed_count = 0
    turn_id: str | None = None
    probe_command_seen = False
    thread_start_ephemeral = False
    seen_command_execution_ids: set[str] = set()
    hook_source_paths = {
        str(installed_ticket_root / "hooks" / "ticket_engine_guard.py"),
        str(installed_ticket_root / "hooks" / "hooks.json"),
    }

    for row in transcript:
        body = row.get("body")
        if not isinstance(body, dict):
            continue
        if row.get("direction") == "send":
            method = body.get("method")
            if isinstance(method, str):
                request_methods.append(method)
                if method == "thread/start":
                    params = body.get("params", {})
                    if isinstance(params, dict):
                        thread_start_ephemeral = params.get("ephemeral") is True
        elif row.get("direction") == "recv":
            method = body.get("method")
            if isinstance(method, str) and method in APPROVAL_REQUEST_METHODS:
                approval_request_methods.append(method)
            if method == "hook/completed":
                params = body.get("params", {})
                if isinstance(params, dict):
                    if isinstance(params.get("turnId"), str):
                        turn_id = turn_id or params.get("turnId")
                    run = params.get("run", {})
                    if (
                        isinstance(run, dict)
                        and run.get("eventName") == "preToolUse"
                        and run.get("sourcePath") in hook_source_paths
                    ):
                        ticket_hook_completed_count += 1
            if method == "turn/completed":
                params = body.get("params", {})
                if isinstance(params, dict):
                    turn = params.get("turn", {})
                    if isinstance(turn, dict) and isinstance(turn.get("id"), str):
                        turn_id = turn["id"]
            item = _item_from_message(body)
            if item is not None:
                if item.get("type") == "commandExecution":
                    if _mark_command_execution_seen(item, seen_command_execution_ids):
                        command_execution_count += 1
                    command_text = item.get("command")
                    if isinstance(command_text, str) and probe_command in command_text:
                        probe_command_seen = True
                params = body.get("params", {})
                if isinstance(params, dict) and isinstance(params.get("turnId"), str):
                    turn_id = turn_id or params.get("turnId")
            for item in _turn_items_from_message(body):
                if item.get("type") != "commandExecution":
                    continue
                if _mark_command_execution_seen(item, seen_command_execution_ids):
                    command_execution_count += 1
                command_text = item.get("command")
                if isinstance(command_text, str) and probe_command in command_text:
                    probe_command_seen = True

    request_methods_tuple = tuple(request_methods)
    approval_request_methods_tuple = tuple(dict.fromkeys(approval_request_methods))
    failure_reasons: list[str] = []
    if request_methods_tuple != ("initialize", "initialized", "thread/start", "turn/start"):
        failure_reasons.append("request_sequence_mismatch")
    if not thread_start_ephemeral:
        failure_reasons.append("thread_start_missing_ephemeral")
    if command_execution_count != 1:
        failure_reasons.append("command_execution_count_mismatch")
    if ticket_hook_completed_count != 1:
        failure_reasons.append("ticket_hook_count_mismatch")
    if approval_request_methods_tuple:
        failure_reasons.append("approval_requested")
    if not probe_command_seen:
        failure_reasons.append("probe_command_missing")

    return TranscriptSummary(
        request_methods=request_methods_tuple,
        approval_request_methods=approval_request_methods_tuple,
        command_execution_count=command_execution_count,
        ticket_hook_completed_count=ticket_hook_completed_count,
        turn_id=turn_id,
        probe_command_seen=probe_command_seen,
        thread_start_ephemeral=thread_start_ephemeral,
        failure_reasons=tuple(failure_reasons),
    )


def run_driver(
    *,
    layout: PreflightLayout,
    executable: str | None = None,
) -> tuple[TranscriptSummary, list[dict[str, Any]]]:
    active_executable = executable or resolve_codex_executable()
    proc = subprocess.Popen(
        [active_executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(layout.project_root),
        env=os.environ.copy(),
    )
    if proc.stdin is None or proc.stdout is None or proc.stderr is None:
        fail("start app-server", "stdio pipe unavailable", active_executable)

    output: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []
    reader_errors: list[str] = []
    transcript: list[dict[str, Any]] = []

    def read_stdout() -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        except Exception as exc:
            reader_errors.append(f"stdout reader failed: {exc!r}")
        finally:
            output.put(None)

    def read_stderr() -> None:
        try:
            for line in proc.stderr:
                stderr_lines.append(line)
        except Exception as exc:
            reader_errors.append(f"stderr reader failed: {exc!r}")

    stdout_reader = threading.Thread(target=read_stdout, daemon=True)
    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    stdout_reader.start()
    stderr_reader.start()

    try:
        _send_and_record(
            proc=proc,
            output=output,
            request={
                "id": INITIALIZE_REQUEST_ID,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "ticket-runtime-turn-driver",
                        "version": "0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            },
            transcript=transcript,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        _send_and_record(
            proc=proc,
            output=output,
            request={"method": "initialized"},
            transcript=transcript,
            expect_response=False,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        thread_response = _send_and_record(
            proc=proc,
            output=output,
            request=build_thread_start_request(contained_root=layout.contained_root),
            transcript=transcript,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        thread_id = _thread_id_from_response(thread_response)
        turn_response = _send_and_record(
            proc=proc,
            output=output,
            request=build_turn_start_request(
                thread_id=thread_id,
                contained_root=layout.contained_root,
                prompt_text=layout.prompt_text,
            ),
            transcript=transcript,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        active_turn_id = _turn_id_from_response(turn_response)
        if active_turn_id is None:
            fail("parse turn/start response", "turn id missing", turn_response)
        _drain_until_turn_completed(
            output=output,
            transcript=transcript,
            turn_id=active_turn_id,
            proc=proc,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        stdout_reader.join(timeout=1)
        stderr_reader.join(timeout=1)
        stderr = "".join(stderr_lines).strip()
        if stderr:
            transcript.append({"direction": "stderr", "body": stderr})
        write_transcript_jsonl(layout.out_path, transcript)

    summary = analyze_transcript(
        transcript,
        probe_command=layout.probe_command,
        installed_ticket_root=layout.installed_ticket_root,
    )
    return summary, transcript


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Drive one contained app-server turn for Ticket runtime preflight"
    )
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--contained-root", type=Path, required=True)
    parser.add_argument("--installed-ticket-root", type=Path, required=True)
    parser.add_argument("--marketplace-path", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        layout = prepare_preflight_layout(
            project_root=args.project_root,
            contained_root=args.contained_root,
            installed_ticket_root=args.installed_ticket_root,
            out_path=args.out,
        )
        summary, _transcript = run_driver(layout=layout)
    except RefreshError as exc:
        print(
            json.dumps(
                {
                    "state": "deterministic_driver_unavailable",
                    "message": str(exc),
                    "out_path": str(args.out),
                }
            )
        )
        return 1

    print(
        json.dumps(
            {
                "state": "ok" if summary.passed else "deterministic_driver_unavailable",
                "summary": transcript_summary_to_dict(summary),
                "out_path": str(layout.out_path),
                "marketplace_path": str(args.marketplace_path),
                "payload_path": str(layout.payload_path),
                "probe_command": layout.probe_command,
            }
        )
    )
    return 0 if summary.passed else 1


def _assert_under_root(*, candidate: Path, allowed_root: Path, operation: str) -> None:
    try:
        candidate.relative_to(allowed_root)
    except ValueError:
        fail(operation, f"path escapes {allowed_root}", str(candidate))


def _send_and_record(
    *,
    proc: subprocess.Popen[str],
    output: queue.Queue[str | None],
    request: dict[str, Any],
    transcript: list[dict[str, Any]],
    expect_response: bool = True,
    stderr_lines: list[str] | None = None,
    reader_errors: list[str] | None = None,
) -> dict[str, Any] | None:
    if proc.stdin is None:
        fail("send app-server request", "stdin unavailable", request)
    proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    transcript.append({"direction": "send", "body": request})
    if not expect_response:
        return None
    request_id = request.get("id")
    if not isinstance(request_id, int):
        fail("send app-server request", "request id missing", request)
    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = _read_next_message(
            output=output,
            transcript=transcript,
            timeout=deadline - time.monotonic(),
        )
        if response is None:
            _fail_if_app_server_unavailable(
                proc=proc,
                stderr_lines=stderr_lines,
                reader_errors=reader_errors,
            )
            continue
        if response.get("id") != request_id:
            continue
        if "error" in response:
            fail("send app-server request", "response returned error", response)
        return response
    fail("send app-server request", "timed out waiting for response", request)


def _drain_until_turn_completed(
    *,
    output: queue.Queue[str | None],
    transcript: list[dict[str, Any]],
    turn_id: str,
    proc: subprocess.Popen[str] | None = None,
    stderr_lines: list[str] | None = None,
    reader_errors: list[str] | None = None,
) -> None:
    if not turn_id:
        fail("drain turn transcript", "turn id missing", turn_id)
    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = _read_next_message(
            output=output,
            transcript=transcript,
            timeout=deadline - time.monotonic(),
        )
        if response is None:
            _fail_if_app_server_unavailable(
                proc=proc,
                stderr_lines=stderr_lines,
                reader_errors=reader_errors,
            )
            continue
        if response.get("method") != "turn/completed":
            continue
        params = response.get("params", {})
        if not isinstance(params, dict):
            continue
        turn = params.get("turn", {})
        if not isinstance(turn, dict):
            continue
        observed_turn_id = turn.get("id")
        if observed_turn_id == turn_id:
            return
    fail("drain turn transcript", "timed out waiting for turn/completed", turn_id)


def _read_next_message(
    *,
    output: queue.Queue[str | None],
    transcript: list[dict[str, Any]],
    timeout: float,
) -> dict[str, Any] | None:
    remaining = max(0.0, timeout)
    if remaining == 0.0:
        return None
    try:
        raw_line = output.get(timeout=min(0.1, remaining))
    except queue.Empty:
        return None
    if raw_line is None:
        return None
    try:
        response = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        transcript.append({"direction": "recv-raw", "body": raw_line.rstrip("\n")})
        fail("read app-server response", f"malformed JSON response: {exc}", raw_line.rstrip("\n"))
    transcript.append({"direction": "recv", "body": response})
    return response


def transcript_summary_to_dict(summary: TranscriptSummary) -> dict[str, Any]:
    return {
        "passed": summary.passed,
        "request_methods": summary.request_methods,
        "approval_request_methods": summary.approval_request_methods,
        "command_execution_count": summary.command_execution_count,
        "ticket_hook_completed_count": summary.ticket_hook_completed_count,
        "turn_id": summary.turn_id,
        "probe_command_seen": summary.probe_command_seen,
        "thread_start_ephemeral": summary.thread_start_ephemeral,
        "failure_reasons": summary.failure_reasons,
    }


def _fail_if_app_server_unavailable(
    *,
    proc: subprocess.Popen[str] | None,
    stderr_lines: list[str] | None,
    reader_errors: list[str] | None,
) -> None:
    if reader_errors:
        fail("read app-server response", f"reader failed: {reader_errors[0]}", None)
    if proc is None:
        return
    poll = getattr(proc, "poll", None)
    if poll is None or poll() is None:
        return
    stderr = "".join(stderr_lines or ()).strip()
    reason = f"app-server exited with code {proc.returncode}"
    if stderr:
        reason = f"{reason}: {stderr}"
    fail("read app-server response", reason, None)


def _thread_id_from_response(response: dict[str, Any] | None) -> str:
    if not isinstance(response, dict):
        fail("parse thread/start response", "response missing", response)
    result = response.get("result", {})
    if not isinstance(result, dict):
        fail("parse thread/start response", "result missing", response)
    thread = result.get("thread", {})
    if not isinstance(thread, dict):
        fail("parse thread/start response", "thread missing", result)
    thread_id = thread.get("id")
    if not isinstance(thread_id, str) or not thread_id:
        fail("parse thread/start response", "thread id missing", thread)
    return thread_id


def _turn_id_from_response(response: dict[str, Any] | None) -> str | None:
    if not isinstance(response, dict):
        return None
    result = response.get("result", {})
    if not isinstance(result, dict):
        return None
    turn = result.get("turn", {})
    if not isinstance(turn, dict):
        return None
    turn_id = turn.get("id")
    return turn_id if isinstance(turn_id, str) and turn_id else None


def _turn_items_from_message(body: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    turn_candidates = []
    result = body.get("result")
    if isinstance(result, dict):
        turn_candidates.append(result.get("turn"))
    params = body.get("params")
    if isinstance(params, dict):
        turn_candidates.append(params.get("turn"))
    for turn in turn_candidates:
        if not isinstance(turn, dict):
            continue
        turn_items = turn.get("items", [])
        if not isinstance(turn_items, list):
            continue
        for item in turn_items:
            if isinstance(item, dict):
                items.append(item)
    return items


def _item_from_message(body: dict[str, Any]) -> dict[str, Any] | None:
    params = body.get("params")
    if not isinstance(params, dict):
        return None
    item = params.get("item")
    return item if isinstance(item, dict) else None


def _mark_command_execution_seen(item: dict[str, Any], seen_ids: set[str]) -> bool:
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id:
        return True
    if item_id in seen_ids:
        return False
    seen_ids.add(item_id)
    return True


if __name__ == "__main__":
    raise SystemExit(main())
