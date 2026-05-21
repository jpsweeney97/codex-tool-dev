from __future__ import annotations

import json
import queue
from pathlib import Path

import pytest
import refresh.app_server_turn_driver as driver_module
from refresh.app_server_turn_driver import (
    TranscriptSummary,
    analyze_transcript,
    build_probe_command,
    build_probe_prompt,
    build_thread_start_request,
    build_turn_start_request,
    prepare_preflight_layout,
    transcript_summary_to_dict,
    write_transcript_jsonl,
)
from refresh.models import RefreshError


class _StringWriter:
    def __init__(self) -> None:
        self.chunks: list[str] = []

    def write(self, chunk: str) -> int:
        self.chunks.append(chunk)
        return len(chunk)

    def flush(self) -> None:
        return None


class _Proc:
    def __init__(self, *, stdin: _StringWriter | None) -> None:
        self.stdin = stdin


def test_build_probe_command_targets_installed_ticket_engine_agent(tmp_path: Path) -> None:
    installed_ticket_root = tmp_path / "installed-ticket"
    payload_path = tmp_path / "contained" / "payload.json"

    command = build_probe_command(
        installed_ticket_root=installed_ticket_root,
        payload_path=payload_path,
    )

    assert command == (
        f"uv run python -B {installed_ticket_root}/scripts/ticket_engine_agent.py "
        f"execute {payload_path}"
    )


def test_build_thread_start_request_pins_ephemeral_contained_thread(contained_root: Path) -> None:
    request = build_thread_start_request(contained_root=contained_root)

    assert request["id"] == 1
    assert request["method"] == "thread/start"
    assert request["params"]["approvalPolicy"] == "never"
    assert request["params"]["cwd"] == str(contained_root)
    assert request["params"]["ephemeral"] is True
    assert request["params"]["runtimeWorkspaceRoots"] == [str(contained_root)]


def test_build_turn_start_request_pins_workspace_write_and_exact_prompt(
    contained_root: Path,
) -> None:
    command = (
        "uv run python -B /tmp/installed-ticket/scripts/ticket_engine_agent.py "
        "execute /tmp/payload.json"
    )
    request = build_turn_start_request(
        thread_id="thread-123",
        contained_root=contained_root,
        prompt_text=build_probe_prompt(command),
    )

    assert request["id"] == 2
    assert request["method"] == "turn/start"
    assert request["params"]["threadId"] == "thread-123"
    assert request["params"]["approvalPolicy"] == "never"
    assert request["params"]["runtimeWorkspaceRoots"] == [str(contained_root)]
    assert request["params"]["sandboxPolicy"] == {
        "type": "workspaceWrite",
        "writableRoots": [str(contained_root)],
    }
    assert request["params"]["input"] == [{"type": "text", "text": build_probe_prompt(command)}]


def test_prepare_preflight_layout_writes_payload_and_contained_ticket_root(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "repo"
    contained_root = project_root / ".codex/ticket-runtime-smoke-preflight/contained"
    installed_ticket_root = tmp_path / "installed-ticket"
    out_path = (
        project_root
        / ".codex"
        / "ticket-runtime-smoke-preflight"
        / "app-server-driver-preflight.jsonl"
    )

    layout = prepare_preflight_layout(
        project_root=project_root,
        contained_root=contained_root,
        installed_ticket_root=installed_ticket_root,
        out_path=out_path,
    )

    assert layout.payload_path == contained_root / "payload.json"
    assert layout.tickets_dir == contained_root / "docs" / "tickets"
    assert layout.out_path == out_path
    assert json.loads(layout.payload_path.read_text(encoding="utf-8")) == {
        "tickets_dir": str(layout.tickets_dir),
    }
    assert layout.probe_command == (
        f"uv run python -B {installed_ticket_root}/scripts/ticket_engine_agent.py "
        f"execute {layout.payload_path}"
    )
    assert str(layout.payload_path).startswith(
        str(project_root / ".codex/ticket-runtime-smoke-preflight")
    )


def test_write_transcript_jsonl_uses_send_recv_rows(tmp_path: Path) -> None:
    out_path = tmp_path / "transcript.jsonl"
    transcript = [
        {"direction": "send", "body": {"id": 0, "method": "initialize"}},
        {"direction": "recv", "body": {"id": 0, "result": {"ok": True}}},
    ]

    write_transcript_jsonl(out_path, transcript)

    assert out_path.read_text(encoding="utf-8").splitlines() == [
        '{"body":{"id":0,"method":"initialize"},"direction":"send"}',
        '{"body":{"id":0,"result":{"ok":true}},"direction":"recv"}',
    ]


def test_write_transcript_jsonl_preserves_stderr_rows(tmp_path: Path) -> None:
    out_path = tmp_path / "transcript.jsonl"
    transcript = [
        {"direction": "stderr", "body": "driver diagnostic"},
    ]

    write_transcript_jsonl(out_path, transcript)

    assert out_path.read_text(encoding="utf-8").splitlines() == [
        '{"body":"driver diagnostic","direction":"stderr"}',
    ]


def test_read_next_message_rejects_malformed_json() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []
    output.put("not-json\n")

    with pytest.raises(RefreshError, match="malformed JSON response"):
        driver_module._read_next_message(output=output, transcript=transcript, timeout=1.0)

    assert transcript == [{"direction": "recv-raw", "body": "not-json"}]


def test_send_and_record_rejects_app_server_error_response(tmp_path: Path) -> None:
    output: queue.Queue[str | None] = queue.Queue()
    output.put('{"id":7,"error":{"message":"blocked"}}\n')
    transcript: list[dict[str, object]] = []
    proc = _Proc(stdin=_StringWriter())

    with pytest.raises(RefreshError, match="response returned error"):
        driver_module._send_and_record(
            proc=proc,
            output=output,
            request={"id": 7, "method": "plugin/read"},
            transcript=transcript,
        )


def test_send_and_record_rejects_response_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []
    proc = _Proc(stdin=_StringWriter())
    monkeypatch.setattr(driver_module, "REQUEST_TIMEOUT_SECONDS", 0.001)

    with pytest.raises(RefreshError, match="timed out waiting for response"):
        driver_module._send_and_record(
            proc=proc,
            output=output,
            request={"id": 8, "method": "plugin/read"},
            transcript=transcript,
        )


def test_drain_until_turn_completed_requires_exact_turn_id() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []

    with pytest.raises(RefreshError, match="turn id missing"):
        driver_module._drain_until_turn_completed(
            output=output,
            transcript=transcript,
            turn_id="",
        )


def test_analyze_transcript_reports_gate_b_success_shape(
    tmp_path: Path,
    contained_root: Path,
) -> None:
    installed_ticket_root = tmp_path / "installed-ticket"
    payload_path = contained_root / "payload.json"
    probe_command = build_probe_command(
        installed_ticket_root=installed_ticket_root,
        payload_path=payload_path,
    )
    transcript = [
        {"direction": "send", "body": {"id": 0, "method": "initialize"}},
        {"direction": "send", "body": {"method": "initialized"}},
        {
            "direction": "send",
            "body": {
                "id": 1,
                "method": "thread/start",
                "params": {"ephemeral": True},
            },
        },
        {"direction": "recv", "body": {"id": 1, "result": {"thread": {"id": "thread-1"}}}},
        {
            "direction": "send",
            "body": {"id": 2, "method": "turn/start", "params": {"threadId": "thread-1"}},
        },
        {
            "direction": "recv",
            "body": {
                "method": "hook/completed",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "run": {
                        "eventName": "preToolUse",
                        "status": "completed",
                        "sourcePath": str(
                            installed_ticket_root / "hooks" / "ticket_engine_guard.py"
                        ),
                        "entries": [],
                    },
                },
            },
        },
        {
            "direction": "recv",
            "body": {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-1",
                    "turn": {
                        "id": "turn-1",
                        "status": "completed",
                        "items": [
                            {
                                "id": "cmd-1",
                                "type": "commandExecution",
                                "status": "completed",
                                "command": probe_command,
                                "cwd": str(contained_root),
                            }
                        ],
                    },
                },
            },
        },
    ]

    summary = analyze_transcript(
        transcript,
        probe_command=probe_command,
        installed_ticket_root=installed_ticket_root,
    )

    assert summary.passed is True
    assert summary.command_execution_count == 1
    assert summary.ticket_hook_completed_count == 1
    assert summary.approval_request_methods == ()
    assert summary.turn_id == "turn-1"


def test_analyze_transcript_rejects_approval_requests(
    tmp_path: Path,
    contained_root: Path,
) -> None:
    installed_ticket_root = tmp_path / "installed-ticket"
    payload_path = contained_root / "payload.json"
    probe_command = build_probe_command(
        installed_ticket_root=installed_ticket_root,
        payload_path=payload_path,
    )
    transcript = [
        {"direction": "send", "body": {"id": 0, "method": "initialize"}},
        {"direction": "send", "body": {"method": "initialized"}},
        {
            "direction": "recv",
            "body": {
                "method": "item/commandExecution/requestApproval",
                "params": {"threadId": "thread-1"},
            },
        },
    ]

    summary = analyze_transcript(
        transcript,
        probe_command=probe_command,
        installed_ticket_root=installed_ticket_root,
    )

    assert summary.passed is False
    assert summary.approval_request_methods == ("item/commandExecution/requestApproval",)


def test_analyze_transcript_accepts_live_item_started_and_failed_hook_shape(
    tmp_path: Path,
    contained_root: Path,
) -> None:
    installed_ticket_root = tmp_path / "installed-ticket"
    payload_path = contained_root / "payload.json"
    probe_command = build_probe_command(
        installed_ticket_root=installed_ticket_root,
        payload_path=payload_path,
    )
    transcript = [
        {"direction": "send", "body": {"id": 0, "method": "initialize"}},
        {"direction": "send", "body": {"method": "initialized"}},
        {
            "direction": "send",
            "body": {
                "id": 1,
                "method": "thread/start",
                "params": {"ephemeral": True},
            },
        },
        {"direction": "recv", "body": {"id": 1, "result": {"thread": {"id": "thread-1"}}}},
        {
            "direction": "send",
            "body": {"id": 2, "method": "turn/start", "params": {"threadId": "thread-1"}},
        },
        {
            "direction": "recv",
            "body": {
                "method": "hook/completed",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "run": {
                        "eventName": "preToolUse",
                        "status": "failed",
                        "sourcePath": str(installed_ticket_root / "hooks" / "hooks.json"),
                        "entries": [
                            {
                                "kind": "error",
                                "text": (
                                    "PreToolUse hook returned unsupported "
                                    "permissionDecision:allow"
                                ),
                            }
                        ],
                    },
                },
            },
        },
        {
            "direction": "recv",
            "body": {
                "method": "item/started",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "item": {
                        "id": "cmd-1",
                        "type": "commandExecution",
                        "status": "inProgress",
                        "command": f"/bin/bash -c '{probe_command}'",
                        "cwd": str(contained_root),
                    },
                },
            },
        },
        {
            "direction": "recv",
            "body": {
                "method": "item/completed",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "item": {
                        "id": "cmd-1",
                        "type": "commandExecution",
                        "status": "completed",
                        "command": f"/bin/bash -c '{probe_command}'",
                        "cwd": str(contained_root),
                    },
                },
            },
        },
    ]

    summary = analyze_transcript(
        transcript,
        probe_command=probe_command,
        installed_ticket_root=installed_ticket_root,
    )

    assert summary.command_execution_count == 1
    assert summary.ticket_hook_completed_count == 1
    assert summary.probe_command_seen is True


def test_send_and_record_retries_after_empty_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyStdin:
        def write(self, _chunk: str) -> None:
            return None

        def flush(self) -> None:
            return None

    class DummyProc:
        stdin = DummyStdin()

    transcript: list[dict[str, object]] = []
    polls = iter([None, {"id": 0, "result": {"ok": True}}])

    monkeypatch.setattr(
        driver_module,
        "_read_next_message",
        lambda **_kwargs: next(polls),
    )

    response = driver_module._send_and_record(
        proc=DummyProc(),
        output=queue.Queue(),
        request={"id": 0, "method": "initialize", "params": {}},
        transcript=transcript,
    )

    assert response == {"id": 0, "result": {"ok": True}}


def test_send_and_record_rejects_dead_app_server_with_stderr() -> None:
    class DeadProc:
        stdin = _StringWriter()
        returncode = 2

        def poll(self) -> int:
            return self.returncode

    output: queue.Queue[str | None] = queue.Queue()
    output.put(None)
    transcript: list[dict[str, object]] = []

    with pytest.raises(RefreshError, match="app-server exited with code 2: fatal stderr"):
        driver_module._send_and_record(
            proc=DeadProc(),
            output=output,
            request={"id": 0, "method": "initialize"},
            transcript=transcript,
            stderr_lines=["fatal stderr"],
            reader_errors=[],
        )


def test_send_and_record_rejects_reader_exception() -> None:
    class LiveProc:
        stdin = _StringWriter()

        def poll(self) -> None:
            return None

    output: queue.Queue[str | None] = queue.Queue()
    output.put(None)
    transcript: list[dict[str, object]] = []

    with pytest.raises(RefreshError, match="reader failed: stdout reader failed"):
        driver_module._send_and_record(
            proc=LiveProc(),
            output=output,
            request={"id": 0, "method": "initialize"},
            transcript=transcript,
            stderr_lines=[],
            reader_errors=["stdout reader failed: RuntimeError('broken')"],
        )


def test_transcript_summary_passed_is_derived_from_failure_reasons() -> None:
    summary = TranscriptSummary(
        request_methods=(),
        approval_request_methods=(),
        command_execution_count=0,
        ticket_hook_completed_count=0,
        turn_id=None,
        probe_command_seen=False,
        thread_start_ephemeral=False,
        failure_reasons=("approval_requested",),
    )

    assert summary.passed is False
    assert transcript_summary_to_dict(summary)["passed"] is False


@pytest.mark.parametrize(
    ("mutator", "expected_reason"),
    [
        (
            lambda transcript, _probe, _root: transcript[1]["body"].update(
                {"method": "not-initialized"}
            ),
            "request_sequence_mismatch",
        ),
        (
            lambda transcript, _probe, _root: transcript[2]["body"]["params"].update(
                {"ephemeral": False}
            ),
            "thread_start_missing_ephemeral",
        ),
        (
            lambda transcript, _probe, _root: transcript[6]["body"]["params"]["turn"]["items"].append(
                {
                    "id": "cmd-2",
                    "type": "commandExecution",
                    "status": "completed",
                    "command": "echo extra",
                }
            ),
            "command_execution_count_mismatch",
        ),
        (
            lambda transcript, _probe, _root: transcript.pop(5),
            "ticket_hook_count_mismatch",
        ),
        (
            lambda transcript, _probe, _root: transcript[6]["body"]["params"]["turn"]["items"][0].update(
                {"command": "echo different"}
            ),
            "probe_command_missing",
        ),
        (
            lambda transcript, _probe, _root: transcript.append(
                {
                    "direction": "recv",
                    "body": {
                        "method": "item/commandExecution/requestApproval",
                        "params": {"threadId": "thread-1"},
                    },
                }
            ),
            "approval_requested",
        ),
    ],
)
def test_analyze_transcript_reports_each_failure_reason(
    tmp_path: Path,
    contained_root: Path,
    mutator,
    expected_reason: str,
) -> None:
    installed_ticket_root = tmp_path / "installed-ticket"
    payload_path = contained_root / "payload.json"
    probe_command = build_probe_command(
        installed_ticket_root=installed_ticket_root,
        payload_path=payload_path,
    )
    transcript = _passing_transcript(
        installed_ticket_root=installed_ticket_root,
        contained_root=contained_root,
        probe_command=probe_command,
    )
    mutator(transcript, probe_command, installed_ticket_root)

    summary = analyze_transcript(
        transcript,
        probe_command=probe_command,
        installed_ticket_root=installed_ticket_root,
    )

    assert expected_reason in summary.failure_reasons
    assert summary.passed is False


def _passing_transcript(
    *,
    installed_ticket_root: Path,
    contained_root: Path,
    probe_command: str,
) -> list[dict[str, object]]:
    return [
        {"direction": "send", "body": {"id": 0, "method": "initialize"}},
        {"direction": "send", "body": {"method": "initialized"}},
        {
            "direction": "send",
            "body": {
                "id": 1,
                "method": "thread/start",
                "params": {"ephemeral": True},
            },
        },
        {"direction": "recv", "body": {"id": 1, "result": {"thread": {"id": "thread-1"}}}},
        {
            "direction": "send",
            "body": {"id": 2, "method": "turn/start", "params": {"threadId": "thread-1"}},
        },
        {
            "direction": "recv",
            "body": {
                "method": "hook/completed",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "run": {
                        "eventName": "preToolUse",
                        "status": "completed",
                        "sourcePath": str(
                            installed_ticket_root / "hooks" / "ticket_engine_guard.py"
                        ),
                        "entries": [],
                    },
                },
            },
        },
        {
            "direction": "recv",
            "body": {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-1",
                    "turn": {
                        "id": "turn-1",
                        "status": "completed",
                        "items": [
                            {
                                "id": "cmd-1",
                                "type": "commandExecution",
                                "status": "completed",
                                "command": probe_command,
                                "cwd": str(contained_root),
                            }
                        ],
                    },
                },
            },
        },
    ]


@pytest.fixture
def contained_root(tmp_path: Path) -> Path:
    path = tmp_path / "contained"
    path.mkdir(parents=True, exist_ok=True)
    return path
