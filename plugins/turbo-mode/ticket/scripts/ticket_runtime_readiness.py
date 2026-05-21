from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeReadinessVerification:
    passed: bool
    error_code: str | None
    message: str


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_installed_ticket_runtime_readiness_for_execute(
    *,
    project_root: Path,
    proof_path: Path | None = None,
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

    if proof.get("schema_version") != "installed_ticket_runtime_readiness-v1":
        return _reject("proof_invalid", "Unexpected runtime proof schema_version")
    if proof.get("status") != "activated":
        return _reject("proof_invalid", "Runtime proof is not activated")

    expires_at = _parse_utc_timestamp(proof.get("expires_at"))
    if expires_at is None:
        return _reject("proof_invalid", "Runtime proof expires_at is invalid")
    if expires_at <= datetime.now(UTC):
        return _reject("stale_proof", "Runtime proof expired")

    if proof.get("run_nonce") != _get_nested_str(proof, "hook_membrane_proof", "nonce"):
        return _reject("nonce_mismatch", "Runtime proof nonce mismatch")

    scope = _get_nested_list(proof, "activation_scope", "gated_execute_surfaces")
    if scope != ["direct_execute"]:
        return _reject("invalid_scope", "Runtime proof scope must be direct_execute only")
    surface_results = _get_nested_dict(proof, "post_activation_gated_smokes", "surface_results")
    if any(key != "direct_execute" for key in surface_results):
        return _reject("invalid_scope", "Runtime proof contains unsupported execute surfaces")

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
        run_dir = resolved_project_root / proof["raw_evidence"]["run_dir"]
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

    if sha256_file(inventory_transcript) != _get_nested_str(proof, "inventory", "transcript_sha256"):
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
        return _reject("post_activation_transcript_hash_mismatch", "Post-activation transcript hash mismatch")
    if sha256_file(payload_before) != _get_nested_str(
        proof, "hook_membrane_proof", "payload_sha256"
    ):
        return _reject("payload_hash_mismatch", "Payload hash mismatch")
    if sha256_file(engine_stdout) != _get_nested_str(
        proof, "hook_membrane_proof", "engine_stdout_sha256"
    ):
        return _reject("engine_stdout_hash_mismatch", "Engine stdout hash mismatch")

    return RuntimeReadinessVerification(
        passed=True,
        error_code=None,
        message="Runtime readiness proof verified for direct_execute",
    )


def _reject(error_code: str, message: str) -> RuntimeReadinessVerification:
    return RuntimeReadinessVerification(passed=False, error_code=error_code, message=message)


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
