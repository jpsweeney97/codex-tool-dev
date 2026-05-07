from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import queue
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .manifests import build_manifest
from .models import PluginSpec, RefreshError, fail

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
EXPECTED_RESPONSE_IDS = frozenset({0, 1, 2, 3, 4, 5})
REAL_CODEX_HOME = Path("/Users/jp/.codex")
APP_SERVER_RESPONSE_SCHEMA_VERSION = ACCEPTED_RESPONSE_SCHEMA_VERSION
PLUGIN_VERSIONS = {"handoff": "1.6.0", "ticket": "1.4.0"}


@dataclass(frozen=True)
class BindingCandidate:
    category: str
    name: str
    supported: bool
    selected: bool = False
    evidence: str | None = None
    observed_value: str | None = None


@dataclass(frozen=True)
class AppServerLaunchAuthority:
    requested_codex_home: str
    resolved_config_path: str
    resolved_plugin_cache_root: str
    resolved_local_only_root: str
    binding_mechanism_name: str
    binding_mechanism_value: str
    child_environment_delta: dict[str, str]
    child_cwd: str
    executable_path: str | None
    executable_sha256: str | None
    executable_hash_unavailable_reason: str | None
    codex_version: str
    initialize_server_info: dict[str, Any]
    initialize_capabilities: dict[str, Any]
    initialize_result: dict[str, Any]
    accepted_response_schema_version: str
    candidate_mechanisms_checked: tuple[BindingCandidate, ...]
    plugin_read_sources: dict[str, str]
    skill_paths: tuple[str, ...]
    hook_paths: tuple[str, ...]


@dataclass(frozen=True)
class AppServerPreInstallTargetAuthority:
    requested_codex_home: str
    install_destination_root: str
    resolved_plugin_cache_root: str
    binding_mechanism_name: str
    binding_mechanism_value: str
    launch_authority_sha256: str
    marketplace_path: str
    remote_marketplace_name: str | None
    no_real_home_paths: bool
    pre_install_cache_manifest_sha256: dict[str, str]


@dataclass(frozen=True)
class _InstallAuthorityPaths:
    repo_root: Path
    codex_home: Path
    marketplace_path: Path


@dataclass(frozen=True)
class AppServerInstallAuthority:
    requested_codex_home: str
    launch_authority_sha256: str
    pre_install_target_authority_sha256: str
    install_request_sha256: dict[str, str]
    install_response_sha256: dict[str, str]
    same_child_post_install_corroboration_sha256: str
    fresh_child_post_install_corroboration_sha256: str
    installed_destination_paths: dict[str, str]
    accepted_install_response_schema_by_plugin: dict[str, str]
    pre_install_cache_manifest_sha256: dict[str, str]
    post_install_cache_manifest_sha256: dict[str, str]
    cache_manifest_delta_sha256: dict[str, str]


@dataclass(frozen=True)
class CodexRuntimeIdentity:
    codex_version: str
    executable_path: str | None
    executable_sha256: str | None
    executable_hash_unavailable_reason: str | None
    server_info: dict[str, Any]
    initialize_capabilities: dict[str, Any]
    initialize_result: dict[str, Any] = field(default_factory=dict)
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


class InventoryCollectionError(RefreshError):
    """Raised when inventory collection fails after collecting partial transcript."""

    def __init__(self, operation: str, reason: str, got: object, transcript: list[dict[str, Any]]):
        super().__init__(f"{operation} failed: {reason}. Got: {got!r:.100}")
        self.transcript = tuple(transcript)


def serialize_authority_record(record: object) -> Any:
    if dataclasses.is_dataclass(record):
        return {
            key: serialize_authority_record(value)
            for key, value in dataclasses.asdict(record).items()
        }
    if isinstance(record, Path):
        return str(record)
    if isinstance(record, tuple):
        return [serialize_authority_record(value) for value in record]
    if isinstance(record, list):
        return [serialize_authority_record(value) for value in record]
    if isinstance(record, dict):
        return {
            str(key): serialize_authority_record(value)
            for key, value in record.items()
        }
    return record


def authority_digest(record: object) -> str:
    payload = json.dumps(
        serialize_authority_record(record),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json_artifact(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_text(
        json.dumps(serialize_authority_record(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def rewrite_ticket_hook_manifest(*, ticket_plugin_root: Path) -> Path:
    hooks_path = ticket_plugin_root / "hooks" / "hooks.json"
    try:
        payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("rewrite Ticket hook manifest", str(exc), str(hooks_path))
    try:
        hook = payload["hooks"]["PreToolUse"][0]["hooks"][0]
    except (KeyError, IndexError, TypeError) as exc:
        fail("rewrite Ticket hook manifest", f"unexpected hook structure: {exc}", str(hooks_path))
    if not isinstance(hook, dict):
        fail("rewrite Ticket hook manifest", "hook entry is not an object", hook)
    current_command = hook.get("command")
    if not isinstance(current_command, str):
        fail(
            "rewrite Ticket hook manifest",
            "unexpected Ticket hook command",
            current_command,
        )
    current_script_path = _parse_ticket_guard_command(
        current_command,
        operation="rewrite Ticket hook manifest",
    )
    expected_current_paths = {
        ticket_plugin_root / "hooks" / "ticket_engine_guard.py",
        REAL_CODEX_HOME
        / "plugins"
        / "cache"
        / "turbo-mode"
        / "ticket"
        / PLUGIN_VERSIONS["ticket"]
        / "hooks"
        / "ticket_engine_guard.py",
    }
    if current_script_path not in expected_current_paths:
        fail(
            "rewrite Ticket hook manifest",
            "unexpected Ticket hook command",
            current_command,
        )
    hook["command"] = _ticket_guard_command(ticket_plugin_root)
    hooks_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return hooks_path


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
    codex_executable = (
        resolve_codex_executable() if roundtrip is None or identity_collector is None else None
    )
    active_roundtrip = roundtrip or (
        lambda active_requests: app_server_roundtrip(
            active_requests,
            executable=codex_executable,
            env_overrides={"CODEX_HOME": str(paths.codex_home)},
            cwd=scratch_cwd,
        )
    )
    transcript: tuple[dict[str, Any], ...] = ()
    try:
        transcript = tuple(active_roundtrip(requests))
        identity_base = (
            identity_collector()
            if identity_collector is not None
            else collect_codex_runtime_identity(executable=codex_executable)
        )
        responses = response_by_id(transcript)
        initialize = responses.get(0)
        if initialize is None:
            fail("inventory contract", "initialize response missing", sorted(responses))
        initialize_result = response_result(initialize)
        identity = CodexRuntimeIdentity(
            codex_version=identity_base.codex_version,
            executable_path=identity_base.executable_path,
            executable_sha256=identity_base.executable_sha256,
            executable_hash_unavailable_reason=identity_base.executable_hash_unavailable_reason,
            server_info=_dict_result_field(initialize, "serverInfo"),
            initialize_capabilities=_dict_result_field(initialize, "capabilities"),
            initialize_result=initialize_result,
        )
        inventory = validate_readonly_inventory_contract(
            transcript,
            paths=paths,
            identity=identity,
            request_methods=tuple(request.get("method", "") for request in requests),
        )
    except InventoryCollectionError:
        raise
    except RefreshError as exc:
        raise InventoryCollectionError(
            "inventory contract",
            str(exc),
            "partial transcript",
            list(transcript),
        ) from exc
    return inventory, transcript


def resolve_codex_executable() -> str:
    executable = shutil.which("codex")
    if executable is None:
        fail("resolve codex executable", "codex executable not found on PATH", "codex")
    return executable


def collect_codex_runtime_identity(*, executable: str | None = None) -> CodexRuntimeIdentity:
    active_executable = executable or resolve_codex_executable()
    try:
        completed = subprocess.run(
            [active_executable, "--version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        fail("collect codex runtime identity", "codex --version timed out", exc.timeout)
    if completed.returncode != 0:
        fail(
            "collect codex runtime identity",
            completed.stderr.strip() or completed.stdout.strip() or "codex --version failed",
            completed.returncode,
        )
    executable_sha256: str | None = None
    unavailable_reason: str | None = None
    path = Path(active_executable)
    try:
        executable_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        unavailable_reason = str(exc)
    return CodexRuntimeIdentity(
        codex_version=completed.stdout.strip(),
        executable_path=active_executable,
        executable_sha256=executable_sha256,
        executable_hash_unavailable_reason=unavailable_reason,
        server_info={},
        initialize_capabilities={},
    )


def app_server_roundtrip(
    requests: list[dict[str, Any]],
    *,
    executable: str | None = None,
    env_overrides: dict[str, str] | None = None,
    cwd: Path | None = None,
    after_response: Callable[
        [dict[str, Any], dict[str, Any], list[dict[str, Any]]], None
    ]
    | None = None,
) -> list[dict[str, Any]]:
    active_executable = executable or resolve_codex_executable()
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.Popen(
        [active_executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None
    output: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []
    transcript: list[dict[str, Any]] = []

    def read_stdout() -> None:
        try:
            for line in proc.stdout:
                output.put(line)
        finally:
            output.put(None)

    def read_stderr() -> None:
        for line in proc.stderr:
            stderr_lines.append(line)

    stdout_reader = threading.Thread(target=read_stdout, daemon=True)
    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    stdout_reader.start()
    stderr_reader.start()
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
                    raise InventoryCollectionError(
                        "app-server request",
                        "stdout closed before response",
                        request,
                        transcript,
                    )
                try:
                    response = json.loads(response_line)
                except json.JSONDecodeError:
                    transcript.append({"direction": "recv-raw", "body": response_line.rstrip("\n")})
                    continue
                transcript.append({"direction": "recv", "body": response})
                if response.get("id") == request["id"]:
                    if "error" in response:
                        raise InventoryCollectionError(
                            "app-server request",
                            "response returned error",
                            response,
                            transcript,
                        )
                    if after_response is not None:
                        after_response(request, response, transcript)
                    break
            else:
                raise InventoryCollectionError(
                    "app-server request",
                    "timed out waiting for response",
                    request,
                    transcript,
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
        if proc.returncode not in (0, -15, None) and stderr:
            transcript.append({"direction": "stderr", "body": stderr})
    return transcript


def collect_app_server_launch_authority(
    paths: Any,
    *,
    scratch_cwd: Path | None = None,
    roundtrip=None,
    identity_collector=None,
    app_server_help_text: str | None = None,
    codex_help_text: str | None = None,
    executable: str | None = None,
) -> tuple[AppServerLaunchAuthority, tuple[dict[str, Any], ...]]:
    active_executable = executable or resolve_codex_executable()
    active_scratch_cwd = scratch_cwd or Path(
        tempfile.mkdtemp(prefix="turbo-mode-refresh-authority-")
    )
    active_scratch_cwd.mkdir(parents=True, exist_ok=True)
    active_app_server_help = app_server_help_text or capture_help_text(
        [active_executable, "app-server", "--help"]
    )
    active_codex_help = codex_help_text or (
        capture_help_text([active_executable, "--help"])
        + "\n"
        + capture_help_text([active_executable, "exec", "--help"])
    )
    env_overrides = explicit_home_binding_env(
        requested_codex_home=paths.codex_home,
        codex_help_text=active_codex_help,
    )
    requests = build_readonly_inventory_requests(paths, scratch_cwd=active_scratch_cwd)
    active_roundtrip = roundtrip or app_server_roundtrip
    transcript = tuple(
        active_roundtrip(
            requests=requests,
            executable=active_executable,
            env_overrides=env_overrides,
            cwd=active_scratch_cwd,
        )
    )
    identity_base = (
        identity_collector()
        if identity_collector is not None
        else collect_codex_runtime_identity(executable=active_executable)
    )
    responses = response_by_id(transcript)
    initialize = responses.get(0)
    if initialize is None:
        fail("app-server authority", "initialize response missing", sorted(responses))
    initialize_result = response_result(initialize)
    requested_codex_home = str(paths.codex_home)
    actual_codex_home = initialize_result.get("codexHome")
    if actual_codex_home != requested_codex_home:
        fail(
            "app-server authority",
            "requested Codex home binding mismatch",
            actual_codex_home,
        )
    identity = CodexRuntimeIdentity(
        codex_version=identity_base.codex_version,
        executable_path=identity_base.executable_path,
        executable_sha256=identity_base.executable_sha256,
        executable_hash_unavailable_reason=identity_base.executable_hash_unavailable_reason,
        server_info=_dict_result_field(initialize, "serverInfo"),
        initialize_capabilities=_dict_result_field(initialize, "capabilities"),
        initialize_result=initialize_result,
    )
    inventory = validate_readonly_inventory_contract(
        transcript,
        paths=paths,
        identity=identity,
        request_methods=tuple(request.get("method", "") for request in requests),
    )
    candidates = discover_binding_candidates(
        app_server_help_text=active_app_server_help,
        codex_help_text=active_codex_help,
        initialize_result=initialize_result,
        requested_codex_home=paths.codex_home,
    )
    skill_paths = observed_skill_paths(responses[4])
    hook_paths = observed_hook_paths(responses[5])
    if paths.codex_home != REAL_CODEX_HOME:
        real_home_prefix = f"{REAL_CODEX_HOME}/"
        for path_value in (
            *inventory.plugin_read_sources.values(),
            *skill_paths,
            *hook_paths,
        ):
            if isinstance(path_value, str) and path_value.startswith(real_home_prefix):
                fail(
                    "app-server authority",
                    "isolated authority resolved live Codex home path",
                    path_value,
                )
    return (
        AppServerLaunchAuthority(
            requested_codex_home=requested_codex_home,
            resolved_config_path=str(paths.codex_home / "config.toml"),
            resolved_plugin_cache_root=str(paths.codex_home / "plugins/cache/turbo-mode"),
            resolved_local_only_root=str(paths.local_only_root),
            binding_mechanism_name="env:CODEX_HOME",
            binding_mechanism_value=requested_codex_home,
            child_environment_delta=env_overrides,
            child_cwd=str(active_scratch_cwd),
            executable_path=identity.executable_path,
            executable_sha256=identity.executable_sha256,
            executable_hash_unavailable_reason=identity.executable_hash_unavailable_reason,
            codex_version=identity.codex_version,
            initialize_server_info=identity.server_info,
            initialize_capabilities=identity.initialize_capabilities,
            initialize_result=identity.initialize_result,
            accepted_response_schema_version=APP_SERVER_RESPONSE_SCHEMA_VERSION,
            candidate_mechanisms_checked=candidates,
            plugin_read_sources=inventory.plugin_read_sources,
            skill_paths=skill_paths,
            hook_paths=hook_paths,
        ),
        transcript,
    )


def build_pre_install_target_authority(
    *,
    launch_authority: AppServerLaunchAuthority,
    marketplace_path: Path,
    remote_marketplace_name: str | None,
    allow_real_codex_home: bool = False,
) -> AppServerPreInstallTargetAuthority:
    requested_codex_home = Path(launch_authority.requested_codex_home)
    install_destination_root = requested_codex_home / "plugins/cache/turbo-mode"
    if not allow_real_codex_home and install_destination_root.is_relative_to(REAL_CODEX_HOME):
        fail(
            "pre-install target authority",
            "isolated install destination resolved under live Codex home",
            str(install_destination_root),
        )
    return AppServerPreInstallTargetAuthority(
        requested_codex_home=str(requested_codex_home),
        install_destination_root=str(install_destination_root),
        resolved_plugin_cache_root=launch_authority.resolved_plugin_cache_root,
        binding_mechanism_name=launch_authority.binding_mechanism_name,
        binding_mechanism_value=launch_authority.binding_mechanism_value,
        launch_authority_sha256=authority_digest(launch_authority),
        marketplace_path=str(marketplace_path),
        remote_marketplace_name=remote_marketplace_name,
        no_real_home_paths=not str(install_destination_root).startswith(f"{REAL_CODEX_HOME}/"),
        pre_install_cache_manifest_sha256=cache_manifest_sha256_by_plugin(
            install_destination_root=install_destination_root
        ),
    )


def build_install_requests(
    *,
    pre_install_authority: AppServerPreInstallTargetAuthority | None,
    expected_requested_codex_home: Path,
    expected_launch_authority_sha256: str,
    expected_marketplace_path: Path,
) -> list[dict[str, Any]]:
    if pre_install_authority is None:
        fail("build install requests", "pre-install target authority missing", None)
    if pre_install_authority.launch_authority_sha256 != expected_launch_authority_sha256:
        fail(
            "build install requests",
            "pre-install target authority stale",
            pre_install_authority.launch_authority_sha256,
        )
    if pre_install_authority.requested_codex_home != str(expected_requested_codex_home):
        fail(
            "build install requests",
            "pre-install target authority home mismatch",
            pre_install_authority.requested_codex_home,
        )
    if pre_install_authority.marketplace_path != str(expected_marketplace_path):
        fail(
            "build install requests",
            "pre-install target authority marketplace mismatch",
            pre_install_authority.marketplace_path,
        )
    install_destination_root = Path(pre_install_authority.install_destination_root)
    expected_root = expected_requested_codex_home / "plugins/cache/turbo-mode"
    if install_destination_root != expected_root:
        fail(
            "build install requests",
            "pre-install target authority install root mismatch",
            str(install_destination_root),
        )
    if str(install_destination_root).startswith(f"{REAL_CODEX_HOME}/") and (
        expected_requested_codex_home != REAL_CODEX_HOME
    ):
        fail(
            "build install requests",
            "pre-install target authority points at live Codex home",
            str(install_destination_root),
        )
    return [
        {
            "id": 1,
            "method": "plugin/install",
            "params": {
                "marketplacePath": str(expected_marketplace_path),
                "pluginName": "handoff",
                "remoteMarketplaceName": pre_install_authority.remote_marketplace_name,
            },
        },
        {
            "id": 2,
            "method": "plugin/install",
            "params": {
                "marketplacePath": str(expected_marketplace_path),
                "pluginName": "ticket",
                "remoteMarketplaceName": pre_install_authority.remote_marketplace_name,
            },
        },
    ]


def validate_install_responses(
    *,
    transcript: tuple[dict[str, Any], ...],
    launch_authority: AppServerLaunchAuthority,
    pre_install_authority: AppServerPreInstallTargetAuthority,
    install_requests: tuple[dict[str, Any], ...],
    same_child_post_install_transcript: tuple[dict[str, Any], ...] | None = None,
    fresh_child_post_install_transcript: tuple[dict[str, Any], ...] | None = None,
) -> AppServerInstallAuthority:
    _validate_install_authority_link(
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
    )
    responses = _install_response_by_id(transcript)
    request_by_id = {
        int(request["id"]): request
        for request in install_requests
        if isinstance(request.get("id"), int)
    }
    installed_destination_paths: dict[str, str] = {}
    accepted_schema_by_plugin: dict[str, str] = {}
    request_digests: dict[str, str] = {}
    response_digests: dict[str, str] = {}
    pre_manifest_digests = dict(pre_install_authority.pre_install_cache_manifest_sha256)
    post_manifest_digests: dict[str, str] = {}
    cache_delta_digests: dict[str, str] = {}
    same_child_corroboration_sha256 = _validate_post_install_corroboration(
        transcript=same_child_post_install_transcript,
        label="same-child",
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
    )
    fresh_child_corroboration_sha256 = _validate_post_install_corroboration(
        transcript=fresh_child_post_install_transcript,
        label="fresh-child",
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
    )
    for request_id, plugin_name in ((1, "handoff"), (2, "ticket")):
        request = request_by_id.get(request_id)
        if request is None:
            fail("validate install responses", "missing install request", request_id)
        _validate_install_request(
            request=request,
            plugin_name=plugin_name,
            pre_install_authority=pre_install_authority,
        )
        response = responses.get(request_id)
        if response is None:
            fail("validate install responses", "missing install response", request_id)
        result = response_result(response)
        _validate_sparse_install_response(result)
        version = PLUGIN_VERSIONS[plugin_name]
        expected_path = Path(pre_install_authority.install_destination_root) / plugin_name / version
        if not expected_path.exists():
            fail(
                "validate install responses",
                "post-install cache path missing",
                str(expected_path),
            )
        request_digests[plugin_name] = authority_digest(request)
        response_digests[plugin_name] = authority_digest(result)
        installed_destination_paths[plugin_name] = str(expected_path)
        accepted_schema_by_plugin[plugin_name] = "sparse-success-auth-v1"
        post_manifest_digests[plugin_name] = cache_manifest_sha256(
            plugin_name=plugin_name,
            installed_path=expected_path,
        )
        cache_delta_digests[plugin_name] = cache_manifest_delta_sha256(
            plugin_name=plugin_name,
            installed_path=expected_path,
            pre_install_manifest_sha256=pre_manifest_digests[plugin_name],
            post_install_manifest_sha256=post_manifest_digests[plugin_name],
        )
    return AppServerInstallAuthority(
        requested_codex_home=launch_authority.requested_codex_home,
        launch_authority_sha256=authority_digest(launch_authority),
        pre_install_target_authority_sha256=authority_digest(pre_install_authority),
        install_request_sha256=request_digests,
        install_response_sha256=response_digests,
        same_child_post_install_corroboration_sha256=same_child_corroboration_sha256,
        fresh_child_post_install_corroboration_sha256=fresh_child_corroboration_sha256,
        installed_destination_paths=installed_destination_paths,
        accepted_install_response_schema_by_plugin=accepted_schema_by_plugin,
        pre_install_cache_manifest_sha256=pre_manifest_digests,
        post_install_cache_manifest_sha256=post_manifest_digests,
        cache_manifest_delta_sha256=cache_delta_digests,
    )


def _validate_sparse_install_response(result: dict[str, Any]) -> None:
    auth_policy = result.get("authPolicy")
    if not isinstance(auth_policy, str):
        fail(
            "validate install responses",
            "install response missing accepted success/auth schema",
            result,
        )
    apps_needing_auth = result.get("appsNeedingAuth", [])
    if not isinstance(apps_needing_auth, list):
        fail(
            "validate install responses",
            "install response appsNeedingAuth is not a list",
            result,
        )


def _install_response_by_id(transcript: tuple[dict[str, Any], ...]) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {}
    for item in transcript:
        if item.get("direction") != "recv":
            continue
        body = item.get("body")
        if not isinstance(body, dict):
            fail("validate install responses", "malformed install response stream", item)
        response_id = body.get("id")
        if response_id not in {1, 2}:
            continue
        if response_id in responses:
            fail("validate install responses", "duplicate install response id", response_id)
        responses[response_id] = body
    return responses


def _validate_post_install_corroboration(
    *,
    transcript: tuple[dict[str, Any], ...] | None,
    label: str,
    launch_authority: AppServerLaunchAuthority,
    pre_install_authority: AppServerPreInstallTargetAuthority,
) -> str:
    if transcript is None:
        fail(
            "validate install responses",
            "post-install corroboration missing",
            label,
        )
    paths = _install_authority_paths(
        pre_install_authority=pre_install_authority,
    )
    identity = CodexRuntimeIdentity(
        codex_version=launch_authority.codex_version,
        executable_path=launch_authority.executable_path,
        executable_sha256=launch_authority.executable_sha256,
        executable_hash_unavailable_reason=launch_authority.executable_hash_unavailable_reason,
        server_info=launch_authority.initialize_server_info,
        initialize_capabilities=launch_authority.initialize_capabilities,
        initialize_result=launch_authority.initialize_result,
    )
    validate_readonly_inventory_contract(
        transcript,
        paths=paths,
        identity=identity,
        request_methods=("post-install-corroboration", label),
    )
    if paths.codex_home != REAL_CODEX_HOME and json_contains(transcript, f"{REAL_CODEX_HOME}/"):
        fail(
            "validate install responses",
            "post-install corroboration resolved live Codex home path",
            label,
        )
    return transcript_sha256(transcript)


def _install_authority_paths(
    *,
    pre_install_authority: AppServerPreInstallTargetAuthority,
) -> _InstallAuthorityPaths:
    marketplace_path = Path(pre_install_authority.marketplace_path)
    try:
        repo_root = marketplace_path.parents[2]
    except IndexError:
        fail(
            "validate install responses",
            "marketplace path cannot resolve repo root",
            str(marketplace_path),
        )
    return _InstallAuthorityPaths(
        repo_root=repo_root,
        codex_home=Path(pre_install_authority.requested_codex_home),
        marketplace_path=marketplace_path,
    )


def _ticket_guard_command(plugin_root: Path) -> str:
    return f"python3 {plugin_root}/hooks/ticket_engine_guard.py"


def _parse_ticket_guard_command(command: str, *, operation: str) -> Path:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        fail(operation, f"unexpected Ticket hook command: {exc}", command)
    if len(argv) != 2 or argv[0] != "python3":
        fail(operation, "unexpected Ticket hook command", command)
    script_path = Path(argv[1])
    if not script_path.is_absolute():
        fail(operation, "unexpected Ticket hook command", command)
    if tuple(script_path.parts[-2:]) != ("hooks", "ticket_engine_guard.py"):
        fail(operation, "unexpected Ticket hook command", command)
    return script_path


def _validate_install_authority_link(
    *,
    launch_authority: AppServerLaunchAuthority,
    pre_install_authority: AppServerPreInstallTargetAuthority,
) -> None:
    launch_digest = authority_digest(launch_authority)
    if pre_install_authority.launch_authority_sha256 != launch_digest:
        fail(
            "validate install responses",
            "pre-install target authority stale",
            pre_install_authority.launch_authority_sha256,
        )
    if pre_install_authority.requested_codex_home != launch_authority.requested_codex_home:
        fail(
            "validate install responses",
            "pre-install target authority home mismatch",
            pre_install_authority.requested_codex_home,
        )
    expected_install_root = Path(launch_authority.requested_codex_home) / "plugins/cache/turbo-mode"
    if pre_install_authority.install_destination_root != str(expected_install_root):
        fail(
            "validate install responses",
            "pre-install target authority install root mismatch",
            pre_install_authority.install_destination_root,
        )
    if pre_install_authority.resolved_plugin_cache_root != str(expected_install_root):
        fail(
            "validate install responses",
            "pre-install target authority plugin cache root mismatch",
            pre_install_authority.resolved_plugin_cache_root,
        )
    if not pre_install_authority.no_real_home_paths and (
        Path(launch_authority.requested_codex_home) != REAL_CODEX_HOME
    ):
        fail(
            "validate install responses",
            "pre-install target authority allows live Codex home paths",
            pre_install_authority.no_real_home_paths,
        )
    expected_plugins = set(PLUGIN_VERSIONS)
    observed_plugins = set(pre_install_authority.pre_install_cache_manifest_sha256)
    if observed_plugins != expected_plugins:
        fail(
            "validate install responses",
            "pre-install cache manifest proof mismatch",
            sorted(observed_plugins),
        )


def _validate_install_request(
    *,
    request: dict[str, Any],
    plugin_name: str,
    pre_install_authority: AppServerPreInstallTargetAuthority,
) -> None:
    if request.get("method") != "plugin/install":
        fail("validate install responses", "install request method mismatch", request)
    params = request.get("params")
    if not isinstance(params, dict):
        fail("validate install responses", "install request params missing", request)
    if params.get("pluginName") != plugin_name:
        fail("validate install responses", "install request plugin mismatch", params)
    if params.get("marketplacePath") != pre_install_authority.marketplace_path:
        fail("validate install responses", "install request marketplace mismatch", params)
    if params.get("remoteMarketplaceName") != pre_install_authority.remote_marketplace_name:
        fail("validate install responses", "install request remote marketplace mismatch", params)


def cache_manifest_sha256_by_plugin(*, install_destination_root: Path) -> dict[str, str]:
    return {
        plugin_name: cache_manifest_sha256(
            plugin_name=plugin_name,
            installed_path=install_destination_root / plugin_name / version,
        )
        for plugin_name, version in PLUGIN_VERSIONS.items()
    }


def cache_manifest_sha256(*, plugin_name: str, installed_path: Path) -> str:
    manifest = installed_cache_manifest(plugin_name=plugin_name, installed_path=installed_path)
    return authority_digest(manifest)


def cache_manifest_delta_sha256(
    *,
    plugin_name: str,
    installed_path: Path,
    pre_install_manifest_sha256: str,
    post_install_manifest_sha256: str,
) -> str:
    return authority_digest(
        {
            "pluginName": plugin_name,
            "installedPath": str(installed_path),
            "preInstallManifestSha256": pre_install_manifest_sha256,
            "postInstallManifestSha256": post_install_manifest_sha256,
        }
    )


def installed_cache_manifest(
    *,
    plugin_name: str,
    installed_path: Path,
) -> dict[str, Any]:
    if not installed_path.exists():
        return {}
    spec = PluginSpec(
        name=plugin_name,
        version=PLUGIN_VERSIONS[plugin_name],
        source_root=installed_path,
        cache_root=installed_path,
    )
    return build_manifest(spec, root_kind="cache")


def capture_help_text(argv: list[str]) -> str:
    completed = subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        fail(
            "capture help text",
            completed.stderr.strip() or completed.stdout.strip() or "help command failed",
            argv,
        )
    return completed.stdout


def explicit_home_binding_env(
    *,
    requested_codex_home: Path,
    codex_help_text: str,
) -> dict[str, str]:
    if "CODEX_HOME" not in codex_help_text:
        fail(
            "app-server authority",
            "no explicit Codex home binding mechanism discovered",
            "CODEX_HOME",
        )
    return {"CODEX_HOME": str(requested_codex_home)}


def discover_binding_candidates(
    *,
    app_server_help_text: str,
    codex_help_text: str,
    initialize_result: dict[str, Any],
    requested_codex_home: Path,
) -> tuple[BindingCandidate, ...]:
    has_config_flag = "--config" in app_server_help_text or "-c, --config" in app_server_help_text
    has_parent_config_flag = "--config" in codex_help_text or "-c, --config" in codex_help_text
    has_code_home = "CODEX_HOME" in codex_help_text
    has_config_path_option = (
        "config-path" in app_server_help_text or "config-path" in codex_help_text
    )
    observed_codex_home = initialize_result.get("codexHome")
    return (
        BindingCandidate(
            category="app-server-cli-flag",
            name="app-server --config",
            supported=has_config_flag,
            evidence="app-server-help",
        ),
        BindingCandidate(
            category="parent-cli-flag",
            name="codex --config",
            supported=has_parent_config_flag,
            evidence="codex-help",
        ),
        BindingCandidate(
            category="environment-variable",
            name="CODEX_HOME",
            supported=has_code_home,
            selected=True,
            evidence="codex-help",
            observed_value=str(requested_codex_home),
        ),
        BindingCandidate(
            category="config-path-option",
            name="explicit-config-path",
            supported=has_config_path_option,
            evidence="help-scan",
        ),
        BindingCandidate(
            category="protocol-field",
            name="initialize.result.codexHome",
            supported=isinstance(observed_codex_home, str),
            evidence="initialize-result",
            observed_value=str(observed_codex_home) if observed_codex_home is not None else None,
        ),
    )


def observed_skill_paths(response: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        path
        for path in (
            skill_record_path(record) for record in skill_records_by_name(response).values()
        )
        if path is not None
    )


def observed_hook_paths(response: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(path)
        for hook in hook_records(response)
        for path in (hook.get("sourcePath"), hook.get("command"))
        if isinstance(path, str)
    )


def response_by_id(transcript: tuple[dict[str, Any], ...]) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {}
    for item in transcript:
        direction = item.get("direction")
        if direction == "recv-raw":
            fail("inventory contract", "malformed app-server response stream", item.get("body"))
        if direction != "recv":
            continue
        body = item.get("body")
        if not isinstance(body, dict):
            fail("inventory contract", "app-server response is not an object", body)
        response_id = body.get("id")
        if response_id is None:
            if isinstance(body.get("method"), str):
                continue
            fail("inventory contract", "app-server response missing id", body)
        if not isinstance(response_id, int):
            fail("inventory contract", "app-server response id is not an integer", response_id)
        if response_id not in EXPECTED_RESPONSE_IDS:
            fail("inventory contract", "unexpected app-server response id", response_id)
        if response_id in responses:
            fail("inventory contract", "duplicate app-server response id", response_id)
        if "error" in body:
            fail("inventory contract", "app-server response returned error", body)
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
    plugin_list = validate_plugin_list_response(responses[3], paths)
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
    source_path = plugin_read_source_path(response)
    if source_path != expected:
        fail(
            "inventory contract",
            f"plugin/read missing source path for {plugin}",
            source_path,
        )
    return source_path


def validate_plugin_list_response(response: dict[str, Any], paths: Any) -> list[str]:
    if json_contains(response, "/plugin-dev/"):
        fail("inventory contract", "plugin/list contains plugin-dev path", response)
    plugin_ids = plugin_list_ids(response, paths)
    expected = {"handoff@turbo-mode", "ticket@turbo-mode"}
    missing = sorted(expected - plugin_ids)
    if missing:
        fail("inventory contract", "plugin/list missing Turbo Mode plugins", missing)
    return ["handoff@turbo-mode", "ticket@turbo-mode"]


def validate_skills_response(response: dict[str, Any], paths: Any) -> list[str]:
    expected = EXPECTED_HANDOFF_SKILLS + EXPECTED_TICKET_SKILLS
    if json_contains(response, "/plugin-dev/"):
        fail("inventory contract", "skills/list contains plugin-dev path", response)
    skills = skill_records_by_name(response)
    missing = sorted(skill for skill in expected if skill not in skills)
    if missing:
        fail("inventory contract", "skills/list missing Turbo Mode skills", missing)
    for skill in expected:
        record = skills[skill]
        actual_path = skill_record_path(record)
        plugin = skill.split(":", 1)[0]
        version = "1.4.0" if skill.startswith("ticket:") else "1.6.0"
        cache_prefix = str(paths.codex_home / f"plugins/cache/turbo-mode/{plugin}/{version}/skills")
        if actual_path is None or not actual_path.startswith(cache_prefix + "/"):
            fail(
                "inventory contract",
                f"skills/list missing installed-cache skill path for {skill}",
                actual_path,
            )
    return sorted(expected)


def validate_hooks_response(response: dict[str, Any], paths: Any) -> dict[str, str]:
    ticket_hooks = [
        item for item in hook_records(response) if item.get("pluginId") == "ticket@turbo-mode"
    ]
    if len(ticket_hooks) != 1:
        fail("inventory contract", "expected exactly one Ticket hook", len(ticket_hooks))
    hook = ticket_hooks[0]
    if hook.get("eventName") != "preToolUse" or hook.get("matcher") != "Bash":
        fail("inventory contract", "Ticket hook event or matcher mismatch", hook)
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
        for item in hook_records(response)
        if item.get("pluginId") == "handoff@turbo-mode"
    ]
    if hooks:
        fail("inventory contract", "expected no Handoff hooks", hooks)
    return []


def plugin_read_source_path(response: dict[str, Any]) -> str | None:
    result = response_result(response)
    source = result.get("source")
    if isinstance(source, dict) and isinstance(source.get("path"), str):
        return source["path"]
    plugin = result.get("plugin")
    if not isinstance(plugin, dict):
        return None
    summary = plugin.get("summary")
    if not isinstance(summary, dict):
        return None
    summary_source = summary.get("source")
    if isinstance(summary_source, dict) and isinstance(summary_source.get("path"), str):
        return summary_source["path"]
    return None


def plugin_list_ids(response: dict[str, Any], paths: Any) -> set[str]:
    result = response_result(response)
    plugins = result.get("plugins")
    if isinstance(plugins, list):
        return plugin_ids_from_records(plugins)

    marketplace_path = str(paths.marketplace_path)
    ids: set[str] = set()
    marketplaces = result.get("marketplaces")
    if not isinstance(marketplaces, list):
        return ids
    for marketplace in marketplaces:
        if not isinstance(marketplace, dict):
            continue
        if marketplace.get("name") != "turbo-mode" or marketplace.get("path") != marketplace_path:
            continue
        marketplace_plugins = marketplace.get("plugins")
        if not isinstance(marketplace_plugins, list):
            continue
        ids.update(plugin_ids_from_records(marketplace_plugins))
    return ids


def plugin_ids_from_records(records: list[Any]) -> set[str]:
    ids: set[str] = set()
    for plugin in records:
        if isinstance(plugin, str):
            ids.add(plugin)
        elif isinstance(plugin, dict) and isinstance(plugin.get("id"), str):
            ids.add(plugin["id"])
    return ids


def skill_records_by_name(response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = response_result(response)
    records = collect_named_records(result.get("skills"))
    data = result.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                records.update(collect_named_records(item.get("skills")))
    return records


def collect_named_records(value: Any) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not isinstance(value, list):
        return records
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            records[item["name"]] = item
    return records


def skill_record_path(record: dict[str, Any]) -> str | None:
    for key in ("path", "sourcePath"):
        value = record.get(key)
        if isinstance(value, str):
            return value
    return None


def hook_records(response: dict[str, Any]) -> list[dict[str, Any]]:
    result = response_result(response)
    hooks = collect_hook_records(result.get("hooks"))
    data = result.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                hooks.extend(collect_hook_records(item.get("hooks")))
    return hooks


def collect_hook_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def response_result(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        fail("inventory contract", "response result is not an object", response)
    return result


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
