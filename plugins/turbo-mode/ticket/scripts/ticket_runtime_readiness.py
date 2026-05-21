from __future__ import annotations

import hashlib
import json
import os
import queue
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, TypeAlias

REQUEST_TIMEOUT_SECONDS = 30.0
RUNTIME_PROOF_PATH_ENV = "TICKET_RUNTIME_PROOF_PATH"
RUNTIME_ACTIVATION_BOOTSTRAP_ENV = "TICKET_RUNTIME_ACTIVATION_BOOTSTRAP"
_POST_DIRECT_AUTONOMY_CONFIG = "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n"

RuntimeReadinessErrorCode: TypeAlias = Literal[
    "proof_missing",
    "proof_invalid",
    "stale_proof",
    "nonce_mismatch",
    "invalid_scope",
    "executing_root_mismatch",
    "plugin_manifest_path_mismatch",
    "raw_evidence_missing",
    "plugin_manifest_hash_mismatch",
    "hook_manifest_path_mismatch",
    "hook_manifest_hash_mismatch",
    "guard_script_path_mismatch",
    "guard_script_hash_mismatch",
    "inventory_transcript_hash_mismatch",
    "hook_transcript_hash_mismatch",
    "post_activation_transcript_hash_mismatch",
    "payload_hash_mismatch",
    "engine_stdout_hash_mismatch",
]

RuntimeActivationDriverErrorCode: TypeAlias = Literal[
    "host_policy_blocked",
    "deterministic_driver_unavailable",
    "hook_contract_blocked",
    "engine_gate_required",
    "runtime_readiness_required",
]

RuntimeActivationBuildErrorCode: TypeAlias = (
    RuntimeActivationDriverErrorCode | RuntimeReadinessErrorCode
)


@dataclass(frozen=True)
class ReadinessSuccess:
    message: str
    passed: Literal[True] = True
    error_code: None = None

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError(
                f"ReadinessSuccess validation failed: message is required. Got: {self!r:.100}"
            )
        if self.passed is not True or self.error_code is not None:
            raise ValueError(
                "ReadinessSuccess validation failed: success must have passed=True and "
                f"error_code=None. Got: {self!r:.100}"
            )


@dataclass(frozen=True)
class ReadinessFailure:
    error_code: RuntimeReadinessErrorCode
    message: str
    passed: Literal[False] = False

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError(
                f"ReadinessFailure validation failed: message is required. Got: {self!r:.100}"
            )
        if self.passed is not False or not self.error_code:
            raise ValueError(
                "ReadinessFailure validation failed: failure must have passed=False and "
                f"a non-empty error_code. Got: {self!r:.100}"
            )


@dataclass(frozen=True)
class ActivationSuccess:
    proof: dict[str, Any]
    message: str
    error_code: None = None

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError(
                f"ActivationSuccess validation failed: message is required. Got: {self!r:.100}"
            )
        if self.error_code is not None or not isinstance(self.proof, dict):
            raise ValueError(
                "ActivationSuccess validation failed: success requires proof and "
                f"error_code=None. Got: {self!r:.100}"
            )


@dataclass(frozen=True)
class ActivationFailure:
    error_code: RuntimeActivationBuildErrorCode
    message: str
    proof: None = None

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError(
                f"ActivationFailure validation failed: message is required. Got: {self!r:.100}"
            )
        if not self.error_code or self.proof is not None:
            raise ValueError(
                "ActivationFailure validation failed: failure requires non-empty error_code "
                "and proof=None. "
                f"Got: {self!r:.100}"
            )


RuntimeReadinessVerification: TypeAlias = ReadinessSuccess | ReadinessFailure
RuntimeActivationBuildResult: TypeAlias = ActivationSuccess | ActivationFailure


class RuntimeActivationError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        if not error_code:
            raise ValueError(
                "RuntimeActivationError validation failed: error_code is required. "
                f"Got: {error_code!r:.100}"
            )
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_deepcopy(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe deep copy for proof payloads.

    Runtime proof dataclasses are frozen only at the outer object; proof dicts
    remain mutable so callers can serialize and inspect them normally.
    """
    copied = json.loads(json.dumps(payload))
    if not isinstance(copied, dict):
        raise ValueError(f"JSON copy failed: expected object. Got: {type(copied).__name__!r:.100}")
    return copied


def _ticket_python_command(script_path: Path, *args: Path | str) -> str:
    parts = ["uv", "run", "python", "-B", str(script_path), *(str(arg) for arg in args)]
    return shlex.join(parts)


def _write_post_direct_autonomy_config(post_root: Path) -> dict[str, Any]:
    config_root = post_root / ".codex"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "ticket.local.md").write_text(
        _POST_DIRECT_AUTONOMY_CONFIG,
        encoding="utf-8",
    )
    return {"mode": "auto_audit", "max_creates": 5, "warnings": []}


def verify_installed_ticket_runtime_readiness_for_execute(
    *,
    project_root: Path,
    proof_path: Path | None = None,
    allow_activation_bootstrap: bool = False,
) -> RuntimeReadinessVerification:
    resolved_project_root = project_root.resolve(strict=False)
    active_proof_path = proof_path or (
        resolved_project_root / ".codex" / "ticket-runtime-proof.json"
    )
    if not active_proof_path.is_file():
        return _reject("proof_missing", f"Runtime proof missing at {active_proof_path}")

    try:
        proof = json.loads(active_proof_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _reject("proof_invalid", f"Cannot read runtime proof: {exc}")
    if not isinstance(proof, dict):
        return _reject("proof_invalid", "Runtime proof must be a JSON object")

    if proof.get("schema_version") != "installed_ticket_runtime_readiness-v1":
        return _reject("proof_invalid", "Unexpected runtime proof schema_version")
    status = proof.get("status")
    bootstrap_allowed = (
        allow_activation_bootstrap
        and proof_path is not None
        and active_proof_path.name == "activated-ticket-runtime-proof.json"
    )
    if bootstrap_allowed:
        if status != "activation_in_progress":
            return _reject(
                "proof_invalid",
                "Runtime activation bootstrap requires a temporary activation_in_progress proof",
            )
    elif status != "activated":
        return _reject("proof_invalid", "Runtime proof is not activated")

    evidence_project_root = resolved_project_root
    proof_project_root = proof.get("project_root")
    if proof_path is not None and isinstance(proof_project_root, str) and proof_project_root:
        evidence_project_root = Path(proof_project_root).resolve(strict=False)

    expires_at = _parse_utc_timestamp(proof.get("expires_at"))
    if expires_at is None:
        return _reject("proof_invalid", "Runtime proof expires_at is invalid")
    if expires_at <= datetime.now(UTC):
        return _reject("stale_proof", "Runtime proof expired")

    try:
        return _verify_runtime_readiness_proof_fields(
            proof=proof,
            evidence_project_root=evidence_project_root,
            allow_pending_post_activation=bootstrap_allowed,
        )
    except KeyError as exc:
        return _reject(
            "proof_invalid",
            f"Missing or invalid runtime proof field: {_key_error_field(exc)}",
        )


def _verify_runtime_readiness_proof_fields(
    *,
    proof: dict[str, Any],
    evidence_project_root: Path,
    allow_pending_post_activation: bool = False,
) -> RuntimeReadinessVerification:
    if proof.get("run_nonce") != _get_nested_str(proof, "hook_membrane_proof", "nonce"):
        return _reject("nonce_mismatch", "Runtime proof nonce mismatch")

    scope = _get_nested_list(proof, "activation_scope", "gated_execute_surfaces")
    if scope != ["direct_execute"]:
        return _reject("invalid_scope", "Runtime proof scope must be direct_execute only")
    post_smokes = _get_nested_dict(proof, "post_activation_gated_smokes")
    required_surfaces = _get_nested_list(proof, "post_activation_gated_smokes", "required_surfaces")
    if required_surfaces != ["direct_execute"]:
        return _reject(
            "invalid_scope",
            "Runtime proof post-activation scope must be direct_execute only",
        )
    surface_results = _get_nested_dict(proof, "post_activation_gated_smokes", "surface_results")
    if set(surface_results) != {"direct_execute"}:
        return _reject("invalid_scope", "Runtime proof contains unsupported execute surfaces")
    direct_execute_result = _get_nested_dict(
        proof, "post_activation_gated_smokes", "surface_results", "direct_execute"
    )
    post_smoke_status = post_smokes.get("status")
    if allow_pending_post_activation:
        if post_smoke_status != "pending":
            return _reject(
                "proof_invalid",
                "Runtime activation bootstrap proof must have pending post-activation smoke",
            )
    else:
        if post_smoke_status != "passed":
            return _reject("proof_invalid", "Runtime proof post-activation smoke has not passed")
        if direct_execute_result.get("engine_state") != "ok_create":
            return _reject(
                "proof_invalid",
                "Runtime proof direct_execute smoke did not create a ticket",
            )
        if direct_execute_result.get("runtime_readiness_required") is not True:
            return _reject(
                "proof_invalid",
                "Runtime proof direct_execute smoke did not traverse runtime readiness",
            )
        if direct_execute_result.get("execute_surface") != "direct_execute":
            return _reject("proof_invalid", "Runtime proof direct_execute surface mismatch")

    runtime_identity = _get_nested_dict(proof, "runtime_identity")
    executable_sha256 = runtime_identity.get("executable_sha256")
    if not isinstance(executable_sha256, str) or not executable_sha256:
        hash_reason = runtime_identity.get("executable_hash_unavailable_reason")
        message = "Runtime proof executable_sha256 is required"
        if isinstance(hash_reason, str) and hash_reason:
            message = f"{message}: {hash_reason}"
        return _reject("proof_invalid", message)

    executing_root = Path(__file__).resolve().parents[1]
    installed_root = Path(_get_nested_str(proof, "ticket_plugin", "installed_cache_root")).resolve(
        strict=False
    )
    if executing_root != installed_root:
        return _reject(
            "executing_root_mismatch",
            f"Executing root {executing_root} does not match proof installed root {installed_root}",
        )

    plugin_manifest_path = Path(_get_nested_str(proof, "ticket_plugin", "plugin_manifest_path"))
    expected_plugin_manifest_path = installed_root / ".codex-plugin" / "plugin.json"
    if plugin_manifest_path != expected_plugin_manifest_path:
        return _reject("plugin_manifest_path_mismatch", "Plugin manifest path mismatch")
    if not plugin_manifest_path.is_file():
        return _reject("raw_evidence_missing", f"Plugin manifest missing at {plugin_manifest_path}")
    if sha256_file(plugin_manifest_path) != _get_nested_str(
        proof, "ticket_plugin", "plugin_manifest_sha256"
    ):
        return _reject("plugin_manifest_hash_mismatch", "Plugin manifest hash mismatch")

    hook_manifest_path = Path(_get_nested_str(proof, "inventory", "hook", "hook_manifest_path"))
    expected_hook_manifest_path = installed_root / "hooks" / "hooks.json"
    if hook_manifest_path != expected_hook_manifest_path:
        return _reject("hook_manifest_path_mismatch", "Hook manifest path mismatch")
    if not hook_manifest_path.is_file():
        return _reject("raw_evidence_missing", f"Hook manifest missing at {hook_manifest_path}")
    if sha256_file(hook_manifest_path) != _get_nested_str(
        proof, "inventory", "hook", "hook_manifest_sha256"
    ):
        return _reject("hook_manifest_hash_mismatch", "Hook manifest hash mismatch")

    guard_script_path = Path(_get_nested_str(proof, "inventory", "hook", "guard_script_path"))
    expected_guard_script_path = installed_root / "hooks" / "ticket_engine_guard.py"
    if guard_script_path != expected_guard_script_path:
        return _reject("guard_script_path_mismatch", "Guard script path mismatch")
    if not guard_script_path.is_file():
        return _reject("raw_evidence_missing", f"Guard script missing at {guard_script_path}")
    if sha256_file(guard_script_path) != _get_nested_str(
        proof, "inventory", "hook", "guard_script_sha256"
    ):
        return _reject("guard_script_hash_mismatch", "Guard script hash mismatch")

    try:
        run_dir = evidence_project_root / proof["raw_evidence"]["run_dir"]
        inventory_transcript = run_dir / proof["raw_evidence"]["app_server_inventory_transcript"]
        hook_events = run_dir / proof["raw_evidence"]["hook_membrane_events"]
        post_events = run_dir / proof["raw_evidence"]["post_activation_events"]
        payload_before = run_dir / proof["raw_evidence"]["payload_before"]
        engine_stdout = run_dir / proof["raw_evidence"]["engine_stdout"]
    except KeyError as exc:
        return _reject("proof_invalid", f"Missing raw_evidence field: {exc}")

    for path in (
        inventory_transcript,
        hook_events,
        post_events,
        payload_before,
        engine_stdout,
    ):
        if not path.is_file():
            return _reject("raw_evidence_missing", f"Raw evidence missing at {path}")
    if not allow_pending_post_activation and post_events.stat().st_size == 0:
        return _reject("raw_evidence_missing", f"Post-activation transcript empty at {post_events}")

    if sha256_file(inventory_transcript) != _get_nested_str(
        proof, "inventory", "transcript_sha256"
    ):
        return _reject("inventory_transcript_hash_mismatch", "Inventory transcript hash mismatch")
    if sha256_file(hook_events) != _get_nested_str(
        proof, "hook_membrane_proof", "raw_events_sha256"
    ):
        return _reject("hook_transcript_hash_mismatch", "Hook membrane transcript hash mismatch")
    if sha256_file(post_events) != _get_nested_str(
        proof,
        "post_activation_gated_smokes",
        "surface_results",
        "direct_execute",
        "raw_events_sha256",
    ):
        return _reject(
            "post_activation_transcript_hash_mismatch", "Post-activation transcript hash mismatch"
        )
    if not allow_pending_post_activation:
        ticket_path = Path(
            _get_nested_str(
                proof,
                "post_activation_gated_smokes",
                "surface_results",
                "direct_execute",
                "ticket_path",
            )
        )
        if not ticket_path.is_file():
            return _reject(
                "raw_evidence_missing",
                f"Post-activation ticket missing at {ticket_path}",
            )
        if sha256_file(ticket_path) != _get_nested_str(
            proof,
            "post_activation_gated_smokes",
            "surface_results",
            "direct_execute",
            "ticket_sha256",
        ):
            return _reject(
                "post_activation_transcript_hash_mismatch",
                "Post-activation ticket hash mismatch",
            )
    if sha256_file(payload_before) != _get_nested_str(
        proof, "hook_membrane_proof", "payload_sha256"
    ):
        return _reject("payload_hash_mismatch", "Payload hash mismatch")
    if sha256_file(engine_stdout) != _get_nested_str(
        proof, "hook_membrane_proof", "engine_stdout_sha256"
    ):
        return _reject("engine_stdout_hash_mismatch", "Engine stdout hash mismatch")

    return ReadinessSuccess(
        message="Runtime readiness proof verified for direct_execute",
    )


def _key_error_field(exc: KeyError) -> str:
    return str(exc.args[0]) if exc.args else str(exc)


def _reject(error_code: RuntimeReadinessErrorCode, message: str) -> RuntimeReadinessVerification:
    return ReadinessFailure(error_code=error_code, message=message)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, tmp_path_raw = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp_path), str(path))
    except OSError:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        print(
            f"runtime activation cleanup failed: {exc}. Got: {str(path)!r:.100}",
            file=sys.stderr,
        )


def _parse_utc_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _get_nested_str(mapping: dict[str, Any], *path: str) -> str:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(path))
        value = value[key]
    if not isinstance(value, str):
        raise KeyError(".".join(path))
    return value


def _get_nested_list(mapping: dict[str, Any], *path: str) -> list[Any]:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(path))
        value = value[key]
    if not isinstance(value, list):
        raise KeyError(".".join(path))
    return value


def _get_nested_dict(mapping: dict[str, Any], *path: str) -> dict[str, Any]:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(path))
        value = value[key]
    if not isinstance(value, dict):
        raise KeyError(".".join(path))
    return value


def build_activation_candidate(
    *,
    project_root: Path,
    tickets_dir: Path,
    marketplace_path: Path,
    executable: str | None = None,
    now: datetime | None = None,
) -> RuntimeActivationBuildResult:
    resolved_project_root = project_root.resolve(strict=False)
    resolved_tickets_dir = tickets_dir.resolve(strict=False)
    active_now = now or datetime.now(UTC)
    run_nonce = "ticket-runtime-" + active_now.strftime("%Y%m%dT%H%M%SZ-") + secrets.token_hex(8)
    run_dir = resolved_project_root / ".codex" / "ticket-runtime-smoke" / run_nonce
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        inventory_result = collect_installed_runtime_inventory(
            project_root=resolved_project_root,
            marketplace_path=marketplace_path.resolve(strict=False),
            run_dir=run_dir,
            executable=executable,
        )
        smoke_result = run_activation_smoke(
            project_root=resolved_project_root,
            tickets_dir=resolved_tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=Path(
                inventory_result["inventory"]["installed_runtime_root"]
            ).resolve(strict=False),
            executable=executable,
        )
    except RuntimeActivationError as exc:
        return ActivationFailure(
            error_code=exc.error_code,
            message=exc.message,
        )

    proof = {
        "schema_version": "installed_ticket_runtime_readiness-v1",
        "status": "activation_in_progress",
        "created_at": active_now.isoformat().replace("+00:00", "Z"),
        "expires_at": (active_now + timedelta(hours=24)).isoformat().replace("+00:00", "Z"),
        "run_nonce": run_nonce,
        "project_root": str(resolved_project_root),
        "ticket_plugin": {
            **inventory_result["ticket_plugin"],
            "installed_cache_root": inventory_result["inventory"]["installed_runtime_root"],
            "plugin_manifest_path": inventory_result["inventory"]["plugin_manifest_path"],
            "plugin_manifest_sha256": inventory_result["inventory"]["plugin_manifest_sha256"],
        },
        "runtime_identity": inventory_result["runtime_identity"],
        "inventory": inventory_result["inventory"],
        "hook_membrane_proof": smoke_result["hook_membrane_proof"],
        "pre_activation_gated_smokes": smoke_result.get(
            "pre_activation_gated_smokes",
            {
                "status": "pending",
                "required_surfaces": ["direct_execute"],
                "surface_results": {},
            },
        ),
        "agentcontrol_hook_traversal_smoke": {
            "status": "not_captured",
            "reason": "no_concrete_harness_named",
        },
        "post_activation_gated_smokes": smoke_result.get(
            "post_activation_gated_smokes",
            {
                "status": "pending",
                "required_surfaces": ["direct_execute"],
                "surface_results": {},
            },
        ),
        "activation_scope": {
            "gated_execute_surfaces": ["direct_execute"],
            "certified_entrypoints": ["ticket_engine_agent.py"],
            "certified_policy_lane": "ticket_engine_agent.py execute + autonomy_mode=auto_audit",
            "excluded_mutation_paths": [
                "ingest_dispatch",
                "activation_smoke_bootstrap",
                "ticket_capture.py",
                "ticket_update.py",
                "ticket_workflow.py",
            ],
            "autonomy_mode": "auto_audit",
            "caller_identity_proven": False,
            "hook_request_origin_contract": "provenance_metadata_only_currently_user",
        },
        "raw_evidence": {
            "run_dir": str(run_dir.relative_to(resolved_project_root)),
            "app_server_inventory_transcript": str(
                inventory_result["raw_inventory_transcript"].relative_to(run_dir)
            ),
            **smoke_result["raw_evidence"],
        },
    }
    return ActivationSuccess(
        proof=proof,
        message="Candidate activation proof built",
    )


def activate_runtime(
    *,
    project_root: Path,
    tickets_dir: Path,
    marketplace_path: Path,
    executable: str | None = None,
    now: datetime | None = None,
) -> RuntimeActivationBuildResult:
    candidate = build_activation_candidate(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
        executable=executable,
        now=now,
    )
    if candidate.error_code is not None or candidate.proof is None:
        return candidate

    resolved_project_root = project_root.resolve(strict=False)
    proof = _json_deepcopy(candidate.proof)
    run_dir = resolved_project_root / _get_nested_str(proof, "raw_evidence", "run_dir")
    temp_proof_path = run_dir / "activated-ticket-runtime-proof.json"

    try:
        _write_json(temp_proof_path, proof)

        prior_proof_override = os.environ.get(RUNTIME_PROOF_PATH_ENV)
        prior_bootstrap_override = os.environ.get(RUNTIME_ACTIVATION_BOOTSTRAP_ENV)
        try:
            os.environ[RUNTIME_PROOF_PATH_ENV] = str(temp_proof_path)
            os.environ[RUNTIME_ACTIVATION_BOOTSTRAP_ENV] = "1"
            post_smoke = run_post_activation_direct_execute_smoke(
                project_root=resolved_project_root,
                tickets_dir=tickets_dir.resolve(strict=False),
                run_dir=run_dir,
                installed_ticket_root=Path(
                    _get_nested_str(proof, "ticket_plugin", "installed_cache_root")
                ).resolve(strict=False),
                proof_path=temp_proof_path,
                executable=executable,
            )
        except RuntimeActivationError as exc:
            return ActivationFailure(
                error_code=exc.error_code,
                message=exc.message,
            )
        finally:
            if prior_proof_override is None:
                os.environ.pop(RUNTIME_PROOF_PATH_ENV, None)
            else:
                os.environ[RUNTIME_PROOF_PATH_ENV] = prior_proof_override
            if prior_bootstrap_override is None:
                os.environ.pop(RUNTIME_ACTIVATION_BOOTSTRAP_ENV, None)
            else:
                os.environ[RUNTIME_ACTIVATION_BOOTSTRAP_ENV] = prior_bootstrap_override

        proof["status"] = "activated"
        proof["post_activation_gated_smokes"] = post_smoke["post_activation_gated_smokes"]
        _write_json(temp_proof_path, proof)

        try:
            verification = verify_installed_ticket_runtime_readiness_for_execute(
                project_root=resolved_project_root,
                proof_path=temp_proof_path,
            )
        except OSError as exc:
            return ActivationFailure(
                error_code="deterministic_driver_unavailable",
                message=(
                    f"runtime proof verification failed: {exc}. Got: {str(temp_proof_path)!r:.100}"
                ),
            )
        if not verification.passed:
            return ActivationFailure(
                error_code=verification.error_code,
                message=verification.message,
            )

        final_proof_path = resolved_project_root / ".codex" / "ticket-runtime-proof.json"
        final_proof_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(final_proof_path, proof)
        return ActivationSuccess(
            proof=proof,
            message="Installed Ticket runtime proof activated",
        )
    except OSError as exc:
        return ActivationFailure(
            error_code="deterministic_driver_unavailable",
            message=f"runtime proof activation failed: {exc}. Got: {str(temp_proof_path)!r:.100}",
        )
    finally:
        _unlink_if_exists(temp_proof_path)


def collect_installed_runtime_inventory(
    *,
    project_root: Path,
    marketplace_path: Path,
    run_dir: Path,
    executable: str | None = None,
) -> dict[str, Any]:
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    transcript = _app_server_roundtrip(
        requests=[
            {
                "id": 0,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "ticket-runtime-readiness", "version": "0"},
                    "capabilities": {"experimentalApi": True},
                },
            },
            {"method": "initialized"},
            {
                "id": 1,
                "method": "plugin/read",
                "params": {
                    "marketplacePath": str(marketplace_path),
                    "pluginName": "ticket",
                    "remoteMarketplaceName": None,
                },
            },
            {
                "id": 2,
                "method": "plugin/list",
                "params": {"marketplacePath": str(marketplace_path), "remoteMarketplaceName": None},
            },
            {"id": 3, "method": "skills/list", "params": {"cwds": [str(project_root)]}},
            {"id": 4, "method": "hooks/list", "params": {"cwds": [str(project_root)]}},
        ],
        executable=executable,
        cwd=project_root,
    )
    transcript_path = raw_dir / "app-server-inventory-transcript.jsonl"
    _write_transcript_jsonl(transcript_path, transcript)

    responses = _responses_by_id(transcript)
    _response_result(responses, 0)
    plugin_read = _response_result(responses, 1)
    hooks_result = _response_result(responses, 4)

    ticket_hook = _find_ticket_hook(hooks_result)
    installed_runtime_root = Path(ticket_hook["sourcePath"]).resolve(strict=False).parents[1]
    plugin_manifest_path = installed_runtime_root / ".codex-plugin" / "plugin.json"
    if not plugin_manifest_path.is_file():
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Installed Ticket plugin manifest missing at {plugin_manifest_path}",
        )
    executable_sha256, hash_unavailable_reason = _resolve_executable_sha256_with_reason(executable)
    runtime_identity = {
        "codex_version": _capture_codex_version(executable),
        "executable_path": _resolve_codex_executable(executable),
        "executable_sha256": executable_sha256,
        "executable_hash_unavailable_reason": hash_unavailable_reason,
        "accepted_response_schema_version": "ticket-app-server-readiness-v1",
        "parser_version": "installed-ticket-runtime-readiness-v1",
    }
    return {
        "ticket_plugin": {
            "plugin_id": "ticket@turbo-mode",
            "name": "ticket",
            "version": plugin_read.get("plugin", {}).get("summary", {}).get("version", "1.4.0"),
        },
        "runtime_identity": runtime_identity,
        "inventory": {
            "request_methods": [
                "initialize",
                "initialized",
                "plugin/read",
                "plugin/list",
                "skills/list",
                "hooks/list",
            ],
            "marketplace_path": str(marketplace_path),
            "cwd": str(project_root),
            "transcript_sha256": sha256_file(transcript_path),
            "plugin_read_source_path": _plugin_read_source_path(plugin_read),
            "installed_runtime_root": str(installed_runtime_root),
            "plugin_manifest_path": str(plugin_manifest_path),
            "plugin_manifest_sha256": sha256_file(plugin_manifest_path),
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "hook_manifest_path": ticket_hook["sourcePath"],
                "hook_manifest_sha256": sha256_file(Path(ticket_hook["sourcePath"])),
                "guard_command": ticket_hook["command"],
                "guard_script_path": str(
                    installed_runtime_root / "hooks" / "ticket_engine_guard.py"
                ),
                "guard_script_sha256": sha256_file(
                    installed_runtime_root / "hooks" / "ticket_engine_guard.py"
                ),
            },
        },
        "raw_inventory_transcript": transcript_path,
    }


def run_activation_smoke(
    *,
    project_root: Path,
    tickets_dir: Path,
    run_dir: Path,
    installed_ticket_root: Path,
    executable: str | None = None,
) -> dict[str, Any]:
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    smoke_tickets_dir = run_dir / "docs" / "tickets"
    smoke_tickets_dir.mkdir(parents=True, exist_ok=True)
    payload_path = run_dir / "payload.json"
    payload = {"tickets_dir": str(smoke_tickets_dir)}
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload_before_path = raw_dir / "payload-before.json"
    payload_before_path.write_text(payload_path.read_text(encoding="utf-8"), encoding="utf-8")
    command = _ticket_python_command(
        installed_ticket_root / "scripts" / "ticket_engine_activation_smoke.py",
        "execute",
        payload_path,
    )
    prompt = (
        "Run exactly one Bash command and nothing else.\n"
        f"Command: {command}\n"
        "Do not inspect files, do not explain, do not ask for approval, "
        "and do not run any other command."
    )
    transcript = _run_app_server_turn(
        project_root=project_root,
        contained_root=run_dir,
        prompt_text=prompt,
        executable=executable,
    )
    hook_events_path = raw_dir / "hook-membrane-events.jsonl"
    _write_transcript_jsonl(hook_events_path, transcript)

    hook_runs = _hook_completed_runs(
        transcript,
        source_path=installed_ticket_root / "hooks" / "hooks.json",
    )
    if len(hook_runs) != 1:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Expected exactly one Ticket hook completion, saw {len(hook_runs)}",
        )
    hook_run = hook_runs[0]
    if any(
        "unsupported permissionDecision" in str(entry.get("text", ""))
        for entry in hook_run.get("entries", [])
    ):
        raise RuntimeActivationError(
            "hook_contract_blocked",
            "Installed Ticket hook still emits unsupported output",
        )

    command_items = _command_execution_items(transcript)
    if len(command_items) != 1:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Expected exactly one command execution item, saw {len(command_items)}",
        )
    command_item = command_items[0]
    if command not in str(command_item.get("command", "")):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Activation smoke command did not traverse the expected command execution path",
        )

    payload_after_path = raw_dir / "payload-after.json"
    payload_after_path.write_text(payload_path.read_text(encoding="utf-8"), encoding="utf-8")
    engine_stdout_text = _command_output_text(transcript)
    engine_stdout_path = raw_dir / "engine-stdout.json"
    engine_stdout_path.write_text(engine_stdout_text, encoding="utf-8")
    if not engine_stdout_text.strip():
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Activation smoke did not emit engine output",
        )
    try:
        engine_response = json.loads(engine_stdout_text)
    except json.JSONDecodeError as exc:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Activation smoke returned invalid engine output: {exc}",
        ) from exc
    if not isinstance(engine_response, dict):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Activation smoke returned non-object engine output",
        )

    app_server_stderr_path = raw_dir / "app-server-stderr.txt"
    app_server_stderr_path.write_text(_stderr_text(transcript), encoding="utf-8")
    pre_activation_gate = run_pre_activation_direct_execute_gate_smoke(
        project_root=project_root,
        run_dir=run_dir,
        installed_ticket_root=installed_ticket_root,
        executable=executable,
    )
    post_events_path = raw_dir / "post-activation-gated-events.jsonl"
    post_events_path.write_text("", encoding="utf-8")

    return {
        "run_nonce": run_dir.name,
        "hook_membrane_proof": {
            "runner": "app_server_turn",
            "status": "passed",
            "command": command,
            "payload_path": str(payload_path),
            "nonce": run_dir.name,
            "payload_sha256": sha256_file(payload_before_path),
            "raw_events_sha256": sha256_file(hook_events_path),
            "engine_stdout_sha256": sha256_file(engine_stdout_path),
        },
        "post_activation_gated_smokes": {
            "status": "pending",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "raw_events_sha256": sha256_file(post_events_path),
                }
            },
        },
        "pre_activation_gated_smokes": pre_activation_gate["pre_activation_gated_smokes"],
        "raw_evidence": {
            "hook_membrane_events": str(hook_events_path.relative_to(run_dir)),
            "pre_activation_events": pre_activation_gate["raw_evidence"]["pre_activation_events"],
            "post_activation_events": str(post_events_path.relative_to(run_dir)),
            "payload_before": str(payload_before_path.relative_to(run_dir)),
            "payload_after": str(payload_after_path.relative_to(run_dir)),
            "engine_stdout": str(engine_stdout_path.relative_to(run_dir)),
            "app_server_stderr": str(app_server_stderr_path.relative_to(run_dir)),
        },
    }


def run_pre_activation_direct_execute_gate_smoke(
    *,
    project_root: Path,
    run_dir: Path,
    installed_ticket_root: Path,
    executable: str | None = None,
) -> dict[str, Any]:
    from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fingerprint

    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pre_root = run_dir / "pre-direct"
    pre_tickets_dir = pre_root / "docs" / "tickets"
    pre_tickets_dir.mkdir(parents=True, exist_ok=True)
    payload_path = pre_root / "pre-direct-payload.json"
    problem = "Runtime activation pre-gate direct execute smoke."
    autonomy_config = _write_post_direct_autonomy_config(pre_root)
    payload = {
        "action": "create",
        "fields": {
            "title": "Runtime activation pre-gate smoke",
            "problem": problem,
            "priority": "medium",
        },
        "session_id": f"{run_dir.name}-pre-direct",
        "classify_intent": "create",
        "classify_confidence": 0.95,
        "dedup_fingerprint": compute_dedup_fingerprint(problem, []),
        "tickets_dir": str(pre_tickets_dir),
        "autonomy_config": autonomy_config,
    }
    _write_json(payload_path, payload)
    command = _ticket_python_command(
        installed_ticket_root / "scripts" / "ticket_engine_agent.py",
        "execute",
        payload_path,
    )
    prompt = (
        "Run exactly one Bash command and nothing else.\n"
        f"Command: {command}\n"
        "Do not inspect files, do not explain, do not ask for approval, "
        "and do not run any other command."
    )

    prior_override = os.environ.get(RUNTIME_PROOF_PATH_ENV)
    os.environ.pop(RUNTIME_PROOF_PATH_ENV, None)
    try:
        transcript = _run_app_server_turn(
            project_root=project_root,
            contained_root=run_dir,
            prompt_text=prompt,
            executable=executable,
        )
    finally:
        if prior_override is not None:
            os.environ[RUNTIME_PROOF_PATH_ENV] = prior_override

    pre_events_path = raw_dir / "pre-activation-gated-events.jsonl"
    _write_transcript_jsonl(pre_events_path, transcript)
    command_items = _command_execution_items(transcript)
    if len(command_items) != 1:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Expected exactly one pre-activation command execution item, saw {len(command_items)}",
        )
    command_item = command_items[0]
    if command not in str(command_item.get("command", "")):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Pre-activation direct execute smoke did not traverse the expected command path",
        )

    engine_stdout_text = _command_output_text(transcript)
    if not engine_stdout_text.strip():
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Pre-activation direct execute smoke did not emit engine output",
        )
    try:
        engine_response = json.loads(engine_stdout_text)
    except json.JSONDecodeError as exc:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Pre-activation direct execute smoke returned invalid engine output: {exc}",
        ) from exc
    if not isinstance(engine_response, dict):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Pre-activation direct execute smoke returned non-object engine output",
        )

    if (
        engine_response.get("state") != "policy_blocked"
        or engine_response.get("error_code") != "runtime_readiness_required"
    ):
        raise RuntimeActivationError(
            "engine_gate_required",
            "Pre-activation direct execute did not block with runtime_readiness_required",
        )

    return {
        "pre_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": command,
                    "execute_surface": "direct_execute",
                    "engine_state": "policy_blocked",
                    "error_code": "runtime_readiness_required",
                    "raw_events_sha256": sha256_file(pre_events_path),
                }
            },
        },
        "raw_evidence": {
            "pre_activation_events": str(pre_events_path.relative_to(run_dir)),
        },
    }


def run_post_activation_direct_execute_smoke(
    *,
    project_root: Path,
    tickets_dir: Path,
    run_dir: Path,
    installed_ticket_root: Path,
    proof_path: Path,
    executable: str | None = None,
) -> dict[str, Any]:
    from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fingerprint

    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    post_root = run_dir / "post-direct"
    post_tickets_dir = post_root / "docs" / "tickets"
    post_tickets_dir.mkdir(parents=True, exist_ok=True)
    payload_path = post_root / "post-direct-payload.json"
    problem = "Runtime activation direct execute smoke."
    autonomy_config = _write_post_direct_autonomy_config(post_root)
    payload = {
        "action": "create",
        "fields": {
            "title": "Runtime activation smoke",
            "problem": problem,
            "priority": "medium",
        },
        "session_id": f"{run_dir.name}-post-direct",
        "classify_intent": "create",
        "classify_confidence": 0.95,
        "dedup_fingerprint": compute_dedup_fingerprint(problem, []),
        "tickets_dir": str(post_tickets_dir),
        "autonomy_config": autonomy_config,
    }
    _write_json(payload_path, payload)
    command = _ticket_python_command(
        installed_ticket_root / "scripts" / "ticket_engine_agent.py",
        "execute",
        payload_path,
    )
    prompt = (
        "Run exactly one Bash command and nothing else.\n"
        f"Command: {command}\n"
        "Do not inspect files, do not explain, do not ask for approval, "
        "and do not run any other command."
    )

    prior_override = os.environ.get(RUNTIME_PROOF_PATH_ENV)
    os.environ[RUNTIME_PROOF_PATH_ENV] = str(proof_path)
    try:
        transcript = _run_app_server_turn(
            project_root=project_root,
            contained_root=run_dir,
            prompt_text=prompt,
            executable=executable,
        )
    finally:
        if prior_override is None:
            os.environ.pop(RUNTIME_PROOF_PATH_ENV, None)
        else:
            os.environ[RUNTIME_PROOF_PATH_ENV] = prior_override

    post_events_path = raw_dir / "post-activation-gated-events.jsonl"
    _write_transcript_jsonl(post_events_path, transcript)

    command_items = _command_execution_items(transcript)
    if len(command_items) != 1:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Expected exactly one command execution item, saw {len(command_items)}",
        )
    command_item = command_items[0]
    if command not in str(command_item.get("command", "")):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Direct execute smoke did not traverse the expected command execution path",
        )

    engine_stdout_text = _command_output_text(transcript)
    if not engine_stdout_text.strip():
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Direct execute smoke did not emit engine output",
        )
    try:
        engine_response = json.loads(engine_stdout_text)
    except json.JSONDecodeError as exc:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Direct execute smoke returned invalid engine output: {exc}",
        ) from exc
    if not isinstance(engine_response, dict):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Direct execute smoke returned non-object engine output",
        )
    if engine_response.get("state") != "ok_create":
        raise RuntimeActivationError(
            "runtime_readiness_required",
            "Direct execute smoke did not reach an activated runtime-ready create result",
        )

    ticket_path_raw = (
        engine_response.get("data", {}).get("ticket_path")
        if isinstance(engine_response.get("data"), dict)
        else None
    )
    if not isinstance(ticket_path_raw, str) or not ticket_path_raw:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Direct execute smoke did not report a created ticket path",
        )
    ticket_path = Path(ticket_path_raw)
    if not ticket_path.is_file():
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Direct execute smoke ticket missing at {ticket_path}",
        )

    return {
        "post_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": command,
                    "execute_surface": "direct_execute",
                    "runtime_readiness_required": True,
                    "engine_state": "ok_create",
                    "raw_events_sha256": sha256_file(post_events_path),
                    "ticket_path": str(ticket_path),
                    "ticket_sha256": sha256_file(ticket_path),
                }
            },
        }
    }


def _resolve_codex_executable(executable: str | None) -> str:
    active = executable or shutil.which("codex")
    if active is None:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable", "codex executable not found"
        )
    return active


def _resolve_executable_sha256(executable: str | None) -> str | None:
    digest, _reason = _resolve_executable_sha256_with_reason(executable)
    return digest


def _resolve_executable_sha256_with_reason(executable: str | None) -> tuple[str | None, str | None]:
    path = Path(_resolve_codex_executable(executable))
    try:
        return sha256_file(path), None
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _capture_codex_version(executable: str | None) -> str:
    active = _resolve_codex_executable(executable)
    try:
        completed = subprocess.run(
            [active, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"codex --version timed out after {exc.timeout}s",
        ) from exc
    except OSError as exc:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"codex --version failed: {exc}. Got: {active!r:.100}",
        ) from exc
    if completed.returncode != 0:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            completed.stderr.strip() or completed.stdout.strip() or "codex --version failed",
        )
    return completed.stdout.strip()


def _app_server_roundtrip(
    *,
    requests: list[dict[str, Any]],
    cwd: Path,
    executable: str | None = None,
) -> list[dict[str, Any]]:
    active_executable = _resolve_codex_executable(executable)
    proc = subprocess.Popen(
        [active_executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(cwd),
        env=os.environ.copy(),
    )
    if proc.stdin is None or proc.stdout is None or proc.stderr is None:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "app-server stdio pipe unavailable",
        )
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
    completed = False
    try:
        for request in requests:
            _send_request(proc=proc, request=request, transcript=transcript)
            if "id" not in request:
                continue
            _wait_for_response(
                output=output,
                transcript=transcript,
                expected_id=int(request["id"]),
                proc=proc,
                stderr_lines=stderr_lines,
                reader_errors=reader_errors,
            )
        completed = True
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
        if completed:
            _raise_if_reader_errors(reader_errors)
    return transcript


def _run_app_server_turn(
    *,
    project_root: Path,
    contained_root: Path,
    prompt_text: str,
    executable: str | None = None,
) -> list[dict[str, Any]]:
    active_executable = _resolve_codex_executable(executable)
    proc = subprocess.Popen(
        [active_executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(project_root),
        env=os.environ.copy(),
    )
    if proc.stdin is None or proc.stdout is None or proc.stderr is None:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "app-server stdio pipe unavailable",
        )
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
    completed = False
    try:
        _send_request(
            proc=proc,
            request={
                "id": 0,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "ticket-runtime-readiness", "version": "0"},
                    "capabilities": {"experimentalApi": True},
                },
            },
            transcript=transcript,
        )
        _wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=0,
            proc=proc,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        _send_request(proc=proc, request={"method": "initialized"}, transcript=transcript)
        _send_request(
            proc=proc,
            request={
                "id": 1,
                "method": "thread/start",
                "params": {
                    "approvalPolicy": "never",
                    "cwd": str(contained_root),
                    "ephemeral": True,
                    "runtimeWorkspaceRoots": [str(contained_root)],
                },
            },
            transcript=transcript,
        )
        thread_response = _wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=1,
            proc=proc,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        thread_id = str(_response_result_by_body(thread_response).get("thread", {}).get("id", ""))
        if not thread_id:
            raise RuntimeActivationError(
                "deterministic_driver_unavailable", "thread/start missing thread id"
            )
        _send_request(
            proc=proc,
            request={
                "id": 2,
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
            },
            transcript=transcript,
        )
        turn_response = _wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=2,
            proc=proc,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        turn_id = str(_response_result_by_body(turn_response).get("turn", {}).get("id", ""))
        if not turn_id:
            raise RuntimeActivationError(
                "deterministic_driver_unavailable", "turn/start missing turn id"
            )
        _drain_until_turn_completed(
            output=output,
            transcript=transcript,
            turn_id=turn_id,
            proc=proc,
            stderr_lines=stderr_lines,
            reader_errors=reader_errors,
        )
        completed = True
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
        if completed:
            _raise_if_reader_errors(reader_errors)
    return transcript


def _send_request(
    *,
    proc: subprocess.Popen[str],
    request: dict[str, Any],
    transcript: list[dict[str, Any]],
) -> None:
    if proc.stdin is None:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "app-server stdin pipe unavailable",
        )
    proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    transcript.append({"direction": "send", "body": request})


def _wait_for_response(
    *,
    output: queue.Queue[str | None],
    transcript: list[dict[str, Any]],
    expected_id: int,
    proc: subprocess.Popen[str] | None = None,
    stderr_lines: list[str] | None = None,
    reader_errors: list[str] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        message = _read_message(
            output=output, transcript=transcript, timeout=deadline - time.monotonic()
        )
        if message is None:
            _raise_if_app_server_unavailable(
                proc=proc,
                stderr_lines=stderr_lines,
                reader_errors=reader_errors,
            )
            continue
        if message.get("id") != expected_id:
            continue
        if "error" in message:
            raise RuntimeActivationError(
                "deterministic_driver_unavailable",
                f"app-server returned error for request {expected_id}",
            )
        return message
    raise RuntimeActivationError(
        "deterministic_driver_unavailable",
        f"Timed out waiting for app-server response {expected_id}",
    )


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
        raise RuntimeActivationError(
            "deterministic_driver_unavailable", "turn/start missing turn id"
        )
    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        message = _read_message(
            output=output, transcript=transcript, timeout=deadline - time.monotonic()
        )
        if message is None:
            _raise_if_app_server_unavailable(
                proc=proc,
                stderr_lines=stderr_lines,
                reader_errors=reader_errors,
            )
            continue
        if message.get("method") != "turn/completed":
            continue
        params = message.get("params", {})
        if not isinstance(params, dict):
            continue
        turn = params.get("turn", {})
        if not isinstance(turn, dict):
            continue
        if turn.get("id") == turn_id:
            return
    raise RuntimeActivationError(
        "deterministic_driver_unavailable",
        "Timed out waiting for turn/completed",
    )


def _read_message(
    *,
    output: queue.Queue[str | None],
    transcript: list[dict[str, Any]],
    timeout: float,
) -> dict[str, Any] | None:
    try:
        raw = output.get(timeout=max(0.01, min(0.1, max(0.0, timeout))))
    except queue.Empty:
        return None
    if raw is None:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "app-server stdout closed unexpectedly",
        )
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        transcript.append({"direction": "recv-raw", "body": raw.rstrip("\n")})
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Malformed app-server JSON response: {exc}",
        ) from exc
    transcript.append({"direction": "recv", "body": message})
    return message


def _raise_if_app_server_unavailable(
    *,
    proc: subprocess.Popen[str] | None,
    stderr_lines: list[str] | None,
    reader_errors: list[str] | None,
) -> None:
    if reader_errors:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"app-server reader failed: {reader_errors[0]}",
        )
    if proc is None:
        return
    poll = getattr(proc, "poll", None)
    if poll is None or poll() is None:
        return
    stderr = "".join(stderr_lines or ()).strip()
    message = f"app-server exited with code {proc.returncode}"
    if stderr:
        message = f"{message}: {stderr}"
    raise RuntimeActivationError("deterministic_driver_unavailable", message)


def _raise_if_reader_errors(reader_errors: list[str]) -> None:
    if reader_errors:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"app-server reader failed: {reader_errors[0]}",
        )


def _write_transcript_jsonl(path: Path, transcript: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in transcript
        ),
        encoding="utf-8",
    )


def _responses_by_id(transcript: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {}
    for row in transcript:
        body = row.get("body")
        if row.get("direction") != "recv" or not isinstance(body, dict):
            continue
        response_id = body.get("id")
        if isinstance(response_id, int):
            responses[response_id] = body
    return responses


def _response_result(responses: dict[int, dict[str, Any]], response_id: int) -> dict[str, Any]:
    body = responses.get(response_id)
    if not isinstance(body, dict):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Missing app-server response {response_id}",
        )
    return _response_result_by_body(body)


def _response_result_by_body(body: dict[str, Any]) -> dict[str, Any]:
    result = body.get("result")
    if not isinstance(result, dict):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "App-server response result was not an object",
        )
    return result


def _plugin_read_source_path(result: dict[str, Any]) -> str:
    source = result.get("source")
    if isinstance(source, dict) and isinstance(source.get("path"), str):
        return source["path"]
    plugin = result.get("plugin")
    if isinstance(plugin, dict):
        summary = plugin.get("summary")
        if isinstance(summary, dict):
            summary_source = summary.get("source")
            if isinstance(summary_source, dict) and isinstance(summary_source.get("path"), str):
                return summary_source["path"]
    raise RuntimeActivationError(
        "deterministic_driver_unavailable",
        "plugin/read missing Ticket source path",
    )


def _find_ticket_hook(result: dict[str, Any]) -> dict[str, str]:
    hooks: list[dict[str, Any]] = []
    direct_hooks = result.get("hooks")
    if isinstance(direct_hooks, list):
        hooks.extend(item for item in direct_hooks if isinstance(item, dict))
    data = result.get("data")
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            item_hooks = item.get("hooks")
            if isinstance(item_hooks, list):
                hooks.extend(hook for hook in item_hooks if isinstance(hook, dict))
    ticket_hooks = [hook for hook in hooks if hook.get("pluginId") == "ticket@turbo-mode"]
    if len(ticket_hooks) != 1:
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            f"Expected exactly one Ticket hook, saw {len(ticket_hooks)}",
        )
    hook = ticket_hooks[0]
    if hook.get("eventName") != "preToolUse" or hook.get("matcher") != "Bash":
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Ticket hook event or matcher mismatch",
        )
    command = hook.get("command")
    source_path = hook.get("sourcePath")
    if not isinstance(command, str) or not isinstance(source_path, str):
        raise RuntimeActivationError(
            "deterministic_driver_unavailable",
            "Ticket hook record missing command/sourcePath",
        )
    return {"command": command, "sourcePath": source_path}


def _hook_completed_runs(
    transcript: list[dict[str, Any]],
    *,
    source_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    expected_source = str(source_path) if source_path is not None else None
    for row in transcript:
        body = row.get("body")
        if row.get("direction") != "recv" or not isinstance(body, dict):
            continue
        if body.get("method") != "hook/completed":
            continue
        params = body.get("params", {})
        if isinstance(params, dict) and isinstance(params.get("run"), dict):
            run = params["run"]
            if run.get("eventName") != "preToolUse":
                continue
            if expected_source is not None and run.get("sourcePath") != expected_source:
                continue
            runs.append(run)
    return runs


def _command_execution_items(transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for row in transcript:
        body = row.get("body")
        if row.get("direction") != "recv" or not isinstance(body, dict):
            continue
        params = body.get("params")
        if not isinstance(params, dict):
            continue
        item = params.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "commandExecution":
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            items[item_id] = item
    return list(items.values())


def _command_output_deltas(transcript: list[dict[str, Any]]) -> list[str]:
    deltas: list[str] = []
    for row in transcript:
        body = row.get("body")
        if row.get("direction") != "recv" or not isinstance(body, dict):
            continue
        if body.get("method") != "item/commandExecution/outputDelta":
            continue
        params = body.get("params", {})
        if isinstance(params, dict) and isinstance(params.get("delta"), str):
            deltas.append(params["delta"])
    return deltas


def _command_output_text(transcript: list[dict[str, Any]]) -> str:
    delta_text = "".join(_command_output_deltas(transcript))
    if delta_text.strip():
        return delta_text
    for item in reversed(_command_execution_items(transcript)):
        aggregated_output = item.get("aggregatedOutput")
        if isinstance(aggregated_output, str) and aggregated_output.strip():
            return aggregated_output
    return ""


def _stderr_text(transcript: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in transcript:
        if row.get("direction") == "stderr" and isinstance(row.get("body"), str):
            parts.append(row["body"])
    return "\n".join(parts).strip()
