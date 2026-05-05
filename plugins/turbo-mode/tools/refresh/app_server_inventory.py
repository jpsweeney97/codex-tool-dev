from __future__ import annotations

import hashlib
import json
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import fail

PARSER_VERSION = "refresh-app-server-inventory-1"
ACCEPTED_RESPONSE_SCHEMA_VERSION = "app-server-readonly-inventory-v1"
REQUEST_TIMEOUT_SECONDS = 30.0
EXPECTED_HANDOFF_SKILLS = (
    "handoff:defer",
    "handoff:distill",
    "handoff:load",
    "handoff:quicksave",
    "handoff:save",
    "handoff:search",
    "handoff:summary",
    "handoff:triage",
)
EXPECTED_TICKET_SKILLS = ("ticket:ticket", "ticket:ticket-triage")


@dataclass(frozen=True)
class CodexRuntimeIdentity:
    codex_version: str
    executable_path: str | None
    executable_sha256: str | None
    executable_hash_unavailable_reason: str | None
    server_info: dict[str, Any]
    initialize_capabilities: dict[str, Any]
    parser_version: str = PARSER_VERSION
    accepted_response_schema_version: str = ACCEPTED_RESPONSE_SCHEMA_VERSION


@dataclass(frozen=True)
class AppServerInventoryCheck:
    state: str
    identity: CodexRuntimeIdentity
    plugin_read_sources: dict[str, str]
    plugin_list: tuple[str, ...]
    skills: tuple[str, ...]
    ticket_hook: dict[str, str]
    handoff_hooks: tuple[dict[str, str], ...]
    request_methods: tuple[str, ...]
    transcript_sha256: str
    reasons: tuple[str, ...] = ()


def build_readonly_inventory_requests(paths: Any, *, scratch_cwd: Path) -> list[dict[str, Any]]:
    marketplace = str(paths.marketplace_path)
    return [
        {
            "id": 0,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "turbo-mode-installed-refresh", "version": "0"},
                "capabilities": {"experimentalApi": True},
            },
        },
        {"method": "initialized"},
        {
            "id": 1,
            "method": "plugin/read",
            "params": {
                "marketplacePath": marketplace,
                "pluginName": "handoff",
                "remoteMarketplaceName": None,
            },
        },
        {
            "id": 2,
            "method": "plugin/read",
            "params": {
                "marketplacePath": marketplace,
                "pluginName": "ticket",
                "remoteMarketplaceName": None,
            },
        },
        {
            "id": 3,
            "method": "plugin/list",
            "params": {"marketplacePath": marketplace, "remoteMarketplaceName": None},
        },
        {"id": 4, "method": "skills/list", "params": {"cwds": [str(scratch_cwd)]}},
        {"id": 5, "method": "hooks/list", "params": {"cwds": [str(scratch_cwd)]}},
    ]


def collect_readonly_runtime_inventory(
    paths: Any,
    *,
    scratch_cwd: Path | None = None,
    roundtrip=None,
    identity_collector=None,
) -> tuple[AppServerInventoryCheck, tuple[dict[str, Any], ...]]:
    if scratch_cwd is None:
        with tempfile.TemporaryDirectory(prefix="turbo-mode-refresh-inventory-") as tmpdir:
            return _collect_readonly_runtime_inventory(
                paths,
                scratch_cwd=Path(tmpdir),
                roundtrip=roundtrip,
                identity_collector=identity_collector,
            )
    return _collect_readonly_runtime_inventory(
        paths,
        scratch_cwd=scratch_cwd,
        roundtrip=roundtrip,
        identity_collector=identity_collector,
    )


def _collect_readonly_runtime_inventory(
    paths: Any,
    *,
    scratch_cwd: Path,
    roundtrip=None,
    identity_collector=None,
) -> tuple[AppServerInventoryCheck, tuple[dict[str, Any], ...]]:
    scratch_cwd.mkdir(parents=True, exist_ok=True)
    requests = build_readonly_inventory_requests(paths, scratch_cwd=scratch_cwd)
    active_roundtrip = roundtrip or app_server_roundtrip
    transcript = tuple(active_roundtrip(requests))
    active_identity_collector = identity_collector or collect_codex_runtime_identity
    identity_base = active_identity_collector()
    responses = response_by_id(transcript)
    initialize = responses.get(0)
    if initialize is None:
        fail("inventory contract", "initialize response missing", sorted(responses))
    identity = CodexRuntimeIdentity(
        codex_version=identity_base.codex_version,
        executable_path=identity_base.executable_path,
        executable_sha256=identity_base.executable_sha256,
        executable_hash_unavailable_reason=identity_base.executable_hash_unavailable_reason,
        server_info=_dict_result_field(initialize, "serverInfo"),
        initialize_capabilities=_dict_result_field(initialize, "capabilities"),
    )
    inventory = validate_readonly_inventory_contract(
        transcript,
        paths=paths,
        identity=identity,
        request_methods=tuple(request.get("method", "") for request in requests),
    )
    return inventory, transcript


def collect_codex_runtime_identity() -> CodexRuntimeIdentity:
    executable = shutil.which("codex")
    if executable is None:
        fail("collect codex runtime identity", "codex executable not found on PATH", "codex")
    completed = subprocess.run(
        [executable, "--version"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        fail(
            "collect codex runtime identity",
            completed.stderr.strip() or completed.stdout.strip() or "codex --version failed",
            completed.returncode,
        )
    executable_sha256: str | None = None
    unavailable_reason: str | None = None
    path = Path(executable)
    try:
        executable_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        unavailable_reason = str(exc)
    return CodexRuntimeIdentity(
        codex_version=completed.stdout.strip(),
        executable_path=executable,
        executable_sha256=executable_sha256,
        executable_hash_unavailable_reason=unavailable_reason,
        server_info={},
        initialize_capabilities={},
    )


def app_server_roundtrip(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proc = subprocess.Popen(
        ["codex", "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, Any]] = []

    def read_stdout() -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        finally:
            output.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        for request in requests:
            proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            proc.stdin.flush()
            transcript.append({"direction": "send", "body": request})
            if "id" not in request:
                continue
            deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    response_line = output.get(timeout=min(0.1, remaining))
                except queue.Empty:
                    continue
                if response_line is None:
                    fail("app-server request", "stdout closed before response", request)
                try:
                    response = json.loads(response_line)
                except json.JSONDecodeError:
                    transcript.append({"direction": "recv-raw", "body": response_line.rstrip("\n")})
                    continue
                transcript.append({"direction": "recv", "body": response})
                if response.get("id") == request["id"]:
                    if "error" in response:
                        fail("app-server request", "response returned error", response)
                    break
            else:
                fail("app-server request", "timed out waiting for response", request)
    finally:
        proc.terminate()
        try:
            _stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _stdout, stderr = proc.communicate(timeout=5)
        if proc.returncode not in (0, -15, None) and stderr:
            transcript.append({"direction": "stderr", "body": stderr.strip()})
    return transcript


def response_by_id(transcript: tuple[dict[str, Any], ...]) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {}
    for item in transcript:
        if item.get("direction") != "recv":
            continue
        body = item.get("body")
        if not isinstance(body, dict):
            continue
        response_id = body.get("id")
        if isinstance(response_id, int):
            responses[response_id] = body
    return responses


def validate_readonly_inventory_contract(
    transcript: tuple[dict[str, Any], ...],
    *,
    paths: Any,
    identity: CodexRuntimeIdentity,
    request_methods: tuple[str, ...],
) -> AppServerInventoryCheck:
    responses = response_by_id(transcript)
    missing = sorted({0, 1, 2, 3, 4, 5} - set(responses))
    if missing:
        fail("inventory contract", "missing app-server responses", missing)
    plugin_read_sources = {
        "handoff": validate_plugin_read_response(responses[1], paths, "handoff", "1.6.0"),
        "ticket": validate_plugin_read_response(responses[2], paths, "ticket", "1.4.0"),
    }
    plugin_list = validate_plugin_list_response(responses[3])
    skills = validate_skills_response(responses[4], paths)
    ticket_hook = validate_hooks_response(responses[5], paths)
    handoff_hooks = validate_no_handoff_hooks(responses[5])
    return AppServerInventoryCheck(
        state="aligned",
        identity=identity,
        plugin_read_sources=plugin_read_sources,
        plugin_list=tuple(plugin_list),
        skills=tuple(skills),
        ticket_hook=ticket_hook,
        handoff_hooks=tuple(handoff_hooks),
        request_methods=request_methods,
        transcript_sha256=transcript_sha256(transcript),
    )


def validate_plugin_read_response(
    response: dict[str, Any],
    paths: Any,
    plugin: str,
    version: str,
) -> str:
    expected = str(paths.repo_root / f"plugins/turbo-mode/{plugin}/{version}")
    if json_contains(response, "/plugin-dev/"):
        fail("inventory contract", "plugin/read contains plugin-dev path", plugin)
    if not json_contains(response, expected):
        fail(
            "inventory contract",
            f"plugin/read missing repo source metadata for {plugin}",
            expected,
        )
    return expected


def validate_plugin_list_response(response: dict[str, Any]) -> list[str]:
    serialized = json.dumps(response, sort_keys=True)
    missing = [
        plugin_id
        for plugin_id in ("handoff@turbo-mode", "ticket@turbo-mode")
        if plugin_id not in serialized
    ]
    if missing:
        fail("inventory contract", "plugin/list missing Turbo Mode plugins", missing)
    if "/plugin-dev/" in serialized:
        fail("inventory contract", "plugin/list contains plugin-dev path", response)
    return ["handoff@turbo-mode", "ticket@turbo-mode"]


def validate_skills_response(response: dict[str, Any], paths: Any) -> list[str]:
    serialized = json.dumps(response, sort_keys=True)
    expected = EXPECTED_HANDOFF_SKILLS + EXPECTED_TICKET_SKILLS
    missing = sorted(skill for skill in expected if skill not in serialized)
    if missing:
        fail("inventory contract", "skills/list missing Turbo Mode skills", missing)
    for plugin, version in (("handoff", "1.6.0"), ("ticket", "1.4.0")):
        cache_prefix = str(paths.codex_home / f"plugins/cache/turbo-mode/{plugin}/{version}/skills")
        if cache_prefix not in serialized:
            fail(
                "inventory contract",
                "skills/list missing installed-cache skill paths",
                cache_prefix,
            )
    if "/plugin-dev/" in serialized:
        fail("inventory contract", "skills/list contains plugin-dev path", response)
    return sorted(expected)


def validate_hooks_response(response: dict[str, Any], paths: Any) -> dict[str, str]:
    hooks = [
        item
        for item in walk_json(response)
        if isinstance(item, dict)
        and item.get("pluginId") == "ticket@turbo-mode"
        and item.get("eventName") == "preToolUse"
        and item.get("matcher") == "Bash"
    ]
    if len(hooks) != 1:
        fail("inventory contract", "expected exactly one Ticket Bash preToolUse hook", len(hooks))
    hook = hooks[0]
    command = str(hook.get("command", ""))
    source_path = str(hook.get("sourcePath", ""))
    expected_cache = paths.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"
    expected_command = f"python3 {expected_cache}/hooks/ticket_engine_guard.py"
    expected_source = f"{expected_cache}/hooks/hooks.json"
    if command != expected_command:
        fail("inventory contract", "Ticket hook command mismatch", command)
    if source_path != expected_source:
        fail("inventory contract", "Ticket hook sourcePath mismatch", source_path)
    if "/plugin-dev/" in command or "/plugin-dev/" in source_path:
        fail("inventory contract", "Ticket hook contains plugin-dev path", hook)
    return {"command": command, "sourcePath": source_path}


def validate_no_handoff_hooks(response: dict[str, Any]) -> list[dict[str, str]]:
    hooks = [
        item
        for item in walk_json(response)
        if isinstance(item, dict) and item.get("pluginId") == "handoff@turbo-mode"
    ]
    if hooks:
        fail("inventory contract", "expected no Handoff hooks", hooks)
    return []


def walk_json(value: object) -> list[object]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(walk_json(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(walk_json(child))
    return items


def json_contains(value: object, needle: str) -> bool:
    return needle in json.dumps(value, sort_keys=True)


def transcript_sha256(transcript: tuple[dict[str, Any], ...]) -> str:
    return hashlib.sha256(transcript_bytes(transcript)).hexdigest()


def transcript_bytes(transcript: tuple[dict[str, Any], ...]) -> bytes:
    return json.dumps(transcript, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _dict_result_field(response: dict[str, Any], key: str) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        fail("inventory contract", "response result is not an object", response)
    value = result.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        fail("inventory contract", f"{key} is not an object", value)
    return value
