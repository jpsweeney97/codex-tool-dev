from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .app_server_inventory import collect_readonly_runtime_inventory
from .evidence import SCHEMA_VERSION as LOCAL_ONLY_SCHEMA_VERSION
from .manifests import build_manifest
from .models import RefreshError
from .planner import (
    MARKETPLACE_RELATIVE_PATH,
    RefreshPaths,
    RefreshPlanResult,
    build_paths,
    build_plugin_specs,
    read_runtime_config_state,
)
from .validation import _json_safe, load_json_object

COMMIT_SAFE_SCHEMA_VERSION = "turbo-mode-refresh-commit-safe-plan-04"
DIRTY_STATE_POLICY = "fail-relevant-dirty-state"
RELEVANT_DIRTY_PATHS = (
    ".agents/plugins/marketplace.json",
    "plugins/turbo-mode/tools/refresh",
    "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
    "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
    "plugins/turbo-mode/tools/refresh_validate_redaction.py",
)

SAFE_REASON_CODES = {
    "source-root-missing",
    "cache-root-missing",
    "generated-residue-present",
    "manifest-build-failed",
    "runtime-config-parse-failed",
    "config-marketplaces-section-missing",
    "config-marketplace-missing",
    "config-marketplace-source-type-mismatch",
    "config-marketplace-source-not-string",
    "config-marketplace-source-mismatch",
    "config-plugin-hooks-absent",
    "config-features-section-malformed",
    "config-plugin-hooks-disabled",
    "config-plugin-hooks-malformed",
    "config-plugins-section-missing",
    "config-plugin-enabled-missing",
    "config-plugin-enabled-disabled",
    "config-plugin-enabled-malformed",
    "added-executable-path",
    "added-non-doc-path",
    "executable-doc-surface",
    "command-shape-changed",
    "projection-parser-warning",
    "semantic-policy-trigger",
    "coverage-gap-path",
    "guarded-only-path",
    "fast-safe-path",
    "unmatched-path",
    "runtime-config-preflight-unavailable",
    "app-server-stdout-closed",
    "app-server-returned-error",
    "app-server-timeout",
    "app-server-contract-invalid",
    "app-server-unavailable",
    "refresh-error",
    "unknown-reason",
}

INVENTORY_FAILURE_REASON_CODES = {
    None,
    "runtime-config-preflight-unavailable",
    "app-server-stdout-closed",
    "app-server-returned-error",
    "app-server-timeout",
    "app-server-contract-invalid",
    "app-server-unavailable",
    "refresh-error",
    "unknown-inventory-failure",
}

CURRENT_IDENTITY_UNAVAILABLE_REASONS = {
    None,
    "source-root-unavailable",
    "installed-cache-root-unavailable",
    "runtime-config-parse-failed",
    "path-not-found",
    "permission-denied",
    "unavailable",
    "hash-unavailable",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_payload(payload: Any) -> str:
    data = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(data).hexdigest()


def sha256_path_metadata(path: Path) -> str | None:
    if not path.exists():
        return None
    stat_result = path.stat()
    payload = {
        "path": path.as_posix(),
        "file_type": "file" if path.is_file() else "other",
        "mode": stat_result.st_mode,
        "size": stat_result.st_size,
        "sha256": sha256_file(path) if path.is_file() else None,
    }
    return sha256_payload(payload)


def digest_or_unavailable(payload_factory: Callable[[], Any]) -> tuple[str | None, str | None]:
    try:
        return sha256_payload(payload_factory()), None
    except (OSError, ValueError, RefreshError) as exc:
        return None, current_identity_unavailable_reason(exc)


def file_metadata_digest_or_unavailable(path: Path) -> tuple[str | None, str | None]:
    try:
        digest = sha256_path_metadata(path)
        if digest is None:
            return None, "path-not-found"
        return digest, None
    except (OSError, ValueError) as exc:
        return None, current_identity_unavailable_reason(exc)


def current_identity_unavailable_reason(exc: BaseException) -> str:
    text = str(exc)
    if "missing source root" in text:
        return "source-root-unavailable"
    if "missing cache root" in text:
        return "installed-cache-root-unavailable"
    if "parse config" in text:
        return "runtime-config-parse-failed"
    if isinstance(exc, FileNotFoundError):
        return "path-not-found"
    if isinstance(exc, PermissionError):
        return "permission-denied"
    return "unavailable"


def ensure_relevant_worktree_clean(repo_root: Path) -> dict[str, Any]:
    dirty_paths = relevant_dirty_paths(repo_root)
    if dirty_paths:
        raise ValueError(
            "prepare commit-safe summary failed: relevant dirty state. "
            f"Got: {dirty_paths!r:.100}"
        )
    return {
        "status": "clean-relevant-paths",
        "relevant_paths_checked": sorted(RELEVANT_DIRTY_PATHS),
        "post_commit_binding": False,
    }


def relevant_dirty_paths(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", *RELEVANT_DIRTY_PATHS],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    dirty: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        dirty.append(line[3:].strip())
    return dirty


def build_commit_safe_summary(
    result: RefreshPlanResult,
    *,
    run_id: str,
    local_summary_path: Path,
    repo_head: str,
    repo_tree: str,
    tool_path: Path,
    tool_sha256: str,
    dirty_state: dict[str, Any],
    metadata_validation_summary_sha256: str | None,
    redaction_validation_summary_sha256: str | None,
) -> dict[str, Any]:
    local_summary = load_json_object(local_summary_path)
    _validate_local_summary_identity(local_summary, result=result, run_id=run_id)
    projected = project_commit_safe_fields_from_local_summary(local_summary)
    return {
        "schema_version": COMMIT_SAFE_SCHEMA_VERSION,
        "run_id": run_id,
        "mode": result.mode,
        "source_local_summary_schema_version": LOCAL_ONLY_SCHEMA_VERSION,
        "repo_head": repo_head,
        "repo_tree": repo_tree,
        "tool_path": tool_path.as_posix(),
        "tool_sha256": tool_sha256,
        "dirty_state_policy": DIRTY_STATE_POLICY,
        "dirty_state": dirty_state,
        "current_run_identity": build_current_run_identity(
            result=result,
            run_id=run_id,
            local_summary=local_summary,
        ),
        "local_only_evidence_root": str(result.paths.local_only_root / run_id),
        "local_only_summary_sha256": sha256_file(local_summary_path),
        **projected,
        "metadata_validation_summary_sha256": metadata_validation_summary_sha256,
        "redaction_validation_summary_sha256": redaction_validation_summary_sha256,
        "omission_reasons": _commit_safe_omission_reasons(),
    }


def build_current_run_identity(
    *,
    result: RefreshPlanResult,
    run_id: str,
    local_summary: dict[str, Any],
) -> dict[str, Any]:
    inventory_collector = None
    if result.app_server_inventory is not None:
        def inventory_collector(_paths: RefreshPaths) -> Any:
            return result.app_server_inventory

    return build_current_run_identity_from_paths(
        repo_root=result.paths.repo_root,
        codex_home=result.paths.codex_home,
        run_id=run_id,
        local_summary=local_summary,
        inventory_collector=inventory_collector,
    )


def build_current_run_identity_from_paths(
    *,
    repo_root: Path,
    codex_home: Path,
    run_id: str,
    local_summary: dict[str, Any],
    inventory_collector: Callable[[RefreshPaths], Any] | None = None,
) -> dict[str, Any]:
    try:
        paths = build_paths(repo_root=repo_root, codex_home=codex_home)
    except FileNotFoundError:
        normalized_repo_root = repo_root.expanduser().resolve(strict=False)
        normalized_codex_home = codex_home.expanduser().resolve(strict=False)
        paths = RefreshPaths(
            repo_root=normalized_repo_root,
            codex_home=normalized_codex_home,
            marketplace_path=normalized_repo_root / MARKETPLACE_RELATIVE_PATH,
            config_path=normalized_codex_home / "config.toml",
            local_only_root=normalized_codex_home / "local-only/turbo-mode-refresh",
        )
    specs = build_plugin_specs(repo_root=paths.repo_root, codex_home=paths.codex_home)
    source_manifest_sha256, source_manifest_reason = digest_or_unavailable(
        lambda: [
            _manifest_or_missing_source(spec, root_kind="source")
            for spec in specs
        ]
    )
    cache_manifest_sha256, cache_manifest_reason = digest_or_unavailable(
        lambda: [_manifest_or_missing_source(spec, root_kind="cache") for spec in specs]
    )
    marketplace_sha256, marketplace_reason = file_metadata_digest_or_unavailable(
        paths.marketplace_path
    )
    config_sha256, config_reason = file_metadata_digest_or_unavailable(paths.config_path)
    runtime_config_sha256, runtime_config_reason = digest_or_unavailable(
        lambda: read_runtime_config_state(
            paths.config_path,
            expected_marketplace_source=paths.repo_root,
        )
    )
    status = str(local_summary.get("app_server_inventory_status"))
    runtime_identity = None
    inventory_summary = None
    if status == "collected":
        collector = inventory_collector or _collect_current_runtime_inventory
        current_inventory = collector(paths)
        inventory_summary = _inventory_replay_identity(current_inventory)
        runtime_identity = _runtime_identity_projection(current_inventory.identity)
    return {
        "local_summary_schema_version": local_summary.get("schema_version"),
        "local_summary_run_id": local_summary.get("run_id"),
        "local_summary_mode": local_summary.get("mode"),
        "source_manifest_sha256": source_manifest_sha256,
        "source_manifest_unavailable_reason": source_manifest_reason,
        "installed_cache_manifest_sha256": cache_manifest_sha256,
        "installed_cache_manifest_unavailable_reason": cache_manifest_reason,
        "repo_marketplace_sha256": marketplace_sha256,
        "repo_marketplace_unavailable_reason": marketplace_reason,
        "local_config_metadata_sha256": config_sha256,
        "local_config_metadata_unavailable_reason": config_reason,
        "runtime_config_projection_sha256": runtime_config_sha256,
        "runtime_config_projection_unavailable_reason": runtime_config_reason,
        "app_server_inventory_summary_sha256": (
            sha256_payload(inventory_summary) if inventory_summary is not None else None
        ),
        "app_server_inventory_freshness": _app_server_inventory_freshness(
            status=status,
            inventory_summary=inventory_summary,
        ),
        "runtime_identity": runtime_identity,
        "runtime_identity_freshness": _runtime_identity_freshness(
            status=status,
            runtime_identity=runtime_identity,
        ),
    }


def _collect_current_runtime_inventory(paths: RefreshPaths) -> Any:
    inventory, _raw_transcript = collect_readonly_runtime_inventory(paths)
    return inventory


def _manifest_or_missing_source(spec: Any, *, root_kind: str) -> dict[str, Any]:
    root = spec.source_root if root_kind == "source" else spec.cache_root
    if not root.exists():
        raise FileNotFoundError(f"missing {root_kind} root: {root}")
    return build_manifest(spec, root_kind=root_kind)


def project_commit_safe_fields_from_local_summary(
    local_summary: dict[str, Any],
) -> dict[str, Any]:
    inventory = local_summary.get("app_server_inventory") or {}
    identity = inventory.get("identity") if isinstance(inventory, dict) else None
    inventory_summary = (
        _inventory_replay_identity_from_local_summary(inventory)
        if isinstance(inventory, dict)
        else None
    )
    return {
        "terminal_plan_status": local_summary["terminal_plan_status"],
        "final_status": local_summary["terminal_plan_status"],
        "axes": _commit_safe_axes(_object_dict(local_summary["axes"])),
        "diff_classification": _commit_safe_diff_classification(
            [_object_dict(item) for item in list(local_summary["diff_classification"])]
        ),
        "runtime_config": _commit_safe_runtime_config(
            _object_dict_or_none(local_summary.get("runtime_config"))
        ),
        "app_server_inventory_status": local_summary["app_server_inventory_status"],
        "app_server_inventory_failure_reason_code": (
            _commit_safe_inventory_failure_reason_code(
                status=str(local_summary["app_server_inventory_status"]),
                raw_reason=local_summary.get("app_server_inventory_failure_reason"),
            )
        ),
        "app_server_inventory_summary_sha256": (
            sha256_payload(inventory_summary) if inventory_summary is not None else None
        ),
        "app_server_request_methods": list(inventory.get("request_methods") or [])
        if isinstance(inventory, dict)
        else [],
        **_runtime_identity_projection_from_local_summary(identity, flattened=True),
    }


def _validate_local_summary_identity(
    local_summary: dict[str, Any],
    *,
    result: RefreshPlanResult,
    run_id: str,
) -> None:
    expected = {
        "schema_version": LOCAL_ONLY_SCHEMA_VERSION,
        "run_id": run_id,
        "mode": result.mode,
    }
    actual = {key: local_summary.get(key) for key in expected}
    if actual != expected:
        raise ValueError(
            "validate local summary identity failed: summary does not match result. "
            f"Got: {actual!r:.100}"
        )


def _object_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            "project commit-safe fields failed: expected object. "
            f"Got: {type(value).__name__!r:.100}"
        )
    return value


def _object_dict_or_none(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return _object_dict(value)


def _commit_safe_axes(axes: dict[str, Any]) -> dict[str, Any]:
    reasons = list(axes.get("reasons") or [])
    reason_codes = [_reason_code(reason) for reason in reasons]
    return {
        "filesystem_state": axes.get("filesystem_state"),
        "coverage_state": axes.get("coverage_state"),
        "runtime_config_state": axes.get("runtime_config_state"),
        "preflight_state": axes.get("preflight_state"),
        "selected_mutation_mode": axes.get("selected_mutation_mode"),
        "reason_codes": reason_codes,
        "reason_count": len(reason_codes),
    }


def _commit_safe_runtime_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    if config is None:
        return None
    reasons = list(config.get("reasons") or [])
    reason_codes = [_reason_code(reason) for reason in reasons]
    return {
        "state": config.get("state"),
        "marketplace_state": config.get("marketplace_state"),
        "plugin_hooks_state": config.get("plugin_hooks_state"),
        "plugin_enablement_state": dict(config.get("plugin_enablement_state") or {}),
        "reason_codes": reason_codes,
        "reason_count": len(reason_codes),
    }


def _commit_safe_diff_classification(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for item in items:
        reasons = list(item.get("reasons") or [])
        reason_codes = [_reason_code(reason) for reason in reasons]
        projected.append(
            {
                "canonical_path": item.get("canonical_path"),
                "mutation_mode": item.get("mutation_mode"),
                "coverage_status": item.get("coverage_status"),
                "outcome": item.get("outcome"),
                "reason_codes": reason_codes,
                "smoke": list(item.get("smoke") or []),
            }
        )
    return projected


def _reason_code(reason: object) -> str:
    text = str(reason)
    exact = {
        "generated residue present": "generated-residue-present",
        "runtime config preflight unavailable": "runtime-config-preflight-unavailable",
        "marketplaces section missing": "config-marketplaces-section-missing",
        "turbo-mode marketplace missing": "config-marketplace-missing",
        "turbo-mode marketplace source_type is not local": (
            "config-marketplace-source-type-mismatch"
        ),
        "turbo-mode marketplace source is not a string": "config-marketplace-source-not-string",
        "turbo-mode marketplace source mismatch": "config-marketplace-source-mismatch",
        "features.plugin_hooks absent": "config-plugin-hooks-absent",
        "features section is not an object": "config-features-section-malformed",
        "features.plugin_hooks disabled": "config-plugin-hooks-disabled",
        "features.plugin_hooks is not boolean": "config-plugin-hooks-malformed",
        "plugins section missing": "config-plugins-section-missing",
        "added-executable-path": "added-executable-path",
        "added-non-doc-path": "added-non-doc-path",
        "executable-doc-surface": "executable-doc-surface",
        "command-shape-changed": "command-shape-changed",
        "projection-parser-warning": "projection-parser-warning",
        "semantic-policy-trigger": "semantic-policy-trigger",
        "coverage-gap-path": "coverage-gap-path",
        "guarded-only-path": "guarded-only-path",
        "fast-safe-path": "fast-safe-path",
        "unmatched-path": "unmatched-path",
    }
    if text in exact:
        return exact[text]
    if text.startswith("missing source root:"):
        return "source-root-missing"
    if text.startswith("missing cache root:"):
        return "cache-root-missing"
    if "parse config failed" in text:
        return "runtime-config-parse-failed"
    if "build manifest" in text:
        return "manifest-build-failed"
    if ".enabled missing" in text:
        return "config-plugin-enabled-missing"
    if ".enabled disabled" in text:
        return "config-plugin-enabled-disabled"
    if ".enabled is not boolean" in text:
        return "config-plugin-enabled-malformed"
    mapped = _commit_safe_inventory_failure_reason_code(
        status="requested-failed",
        raw_reason=text,
    )
    if mapped is not None and mapped != "unknown-inventory-failure":
        return mapped
    return "unknown-reason"


def _commit_safe_inventory_failure_reason_code(
    *,
    status: str,
    raw_reason: object,
) -> str | None:
    if status in {"not-requested", "collected"}:
        return None
    if raw_reason is None:
        return "unknown-inventory-failure"
    text = str(raw_reason)
    if text == "runtime config preflight unavailable":
        return "runtime-config-preflight-unavailable"
    if "stdout closed before response" in text:
        return "app-server-stdout-closed"
    if "response returned error" in text:
        return "app-server-returned-error"
    if "timed out" in text or "timeout" in text:
        return "app-server-timeout"
    if "inventory contract" in text:
        return "app-server-contract-invalid"
    if "app-server" in text or "app server" in text:
        return "app-server-unavailable"
    if "refresh" in text:
        return "refresh-error"
    return "unknown-inventory-failure"


def _runtime_identity_projection(identity: Any) -> dict[str, Any]:
    return {
        "codex_version": identity.codex_version,
        "codex_executable_path": identity.executable_path,
        "codex_executable_sha256": identity.executable_sha256,
        "codex_executable_hash_unavailable_reason": _runtime_hash_unavailable_reason_code(
            identity.executable_hash_unavailable_reason
        ),
        "app_server_server_info": _server_info_projection(identity.server_info),
        "app_server_protocol_capabilities": _protocol_capabilities_projection(
            identity.initialize_capabilities
        ),
        "app_server_parser_version": identity.parser_version,
        "app_server_response_schema_version": identity.accepted_response_schema_version,
    }


def _runtime_identity_projection_from_local_summary(
    identity: object,
    *,
    flattened: bool = False,
) -> dict[str, Any]:
    if not isinstance(identity, dict):
        projected = {
            "codex_version": None,
            "codex_executable_path": None,
            "codex_executable_sha256": None,
            "codex_executable_hash_unavailable_reason": None,
            "app_server_server_info": {"name": None, "version": None},
            "app_server_protocol_capabilities": {"experimentalApi": None},
            "app_server_parser_version": None,
            "app_server_response_schema_version": None,
        }
        return projected if flattened else projected
    projected = {
        "codex_version": identity.get("codex_version"),
        "codex_executable_path": identity.get("executable_path"),
        "codex_executable_sha256": identity.get("executable_sha256"),
        "codex_executable_hash_unavailable_reason": _runtime_hash_unavailable_reason_code(
            identity.get("executable_hash_unavailable_reason")
        ),
        "app_server_server_info": _server_info_projection(identity.get("server_info")),
        "app_server_protocol_capabilities": _protocol_capabilities_projection(
            identity.get("initialize_capabilities")
        ),
        "app_server_parser_version": identity.get("parser_version"),
        "app_server_response_schema_version": identity.get(
            "accepted_response_schema_version"
        ),
    }
    return projected if flattened else projected


def _server_info_projection(server_info: object) -> dict[str, str | None]:
    if not isinstance(server_info, dict):
        return {"name": None, "version": None}
    return {
        "name": _optional_string(server_info.get("name")),
        "version": _optional_string(server_info.get("version")),
    }


def _protocol_capabilities_projection(capabilities: object) -> dict[str, bool | None]:
    if not isinstance(capabilities, dict):
        return {"experimentalApi": None}
    experimental_api = capabilities.get("experimentalApi")
    return {"experimentalApi": experimental_api if isinstance(experimental_api, bool) else None}


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _runtime_hash_unavailable_reason_code(raw_reason: object) -> str | None:
    if raw_reason is None:
        return None
    return "hash-unavailable"


def _inventory_replay_identity(inventory: Any) -> dict[str, Any]:
    return {
        "state": inventory.state,
        "plugin_read_sources": dict(inventory.plugin_read_sources),
        "plugin_list": list(inventory.plugin_list),
        "skills": list(inventory.skills),
        "ticket_hook": dict(inventory.ticket_hook),
        "handoff_hooks": [dict(item) for item in inventory.handoff_hooks],
        "request_methods": list(inventory.request_methods),
        "reasons": [_reason_code(reason) for reason in inventory.reasons],
    }


def _inventory_replay_identity_from_local_summary(
    inventory: dict[str, Any],
) -> dict[str, Any] | None:
    if not inventory:
        return None
    return {
        "state": inventory.get("state"),
        "plugin_read_sources": dict(inventory.get("plugin_read_sources") or {}),
        "plugin_list": list(inventory.get("plugin_list") or []),
        "skills": list(inventory.get("skills") or []),
        "ticket_hook": dict(inventory.get("ticket_hook") or {}),
        "handoff_hooks": [dict(item) for item in list(inventory.get("handoff_hooks") or [])],
        "request_methods": list(inventory.get("request_methods") or []),
        "reasons": [_reason_code(reason) for reason in list(inventory.get("reasons") or [])],
    }


def _app_server_inventory_freshness(
    *,
    status: str,
    inventory_summary: dict[str, Any] | None,
) -> str:
    if status == "collected" and inventory_summary is not None:
        return "recomputed-readonly-inventory"
    if status == "not-requested":
        return "not-requested"
    if status == "requested-blocked":
        return "blocked-runtime-config"
    return "failure-code-only"


def _runtime_identity_freshness(
    *,
    status: str,
    runtime_identity: dict[str, Any] | None,
) -> str:
    if status == "collected" and runtime_identity is not None:
        return "recomputed-readonly-inventory"
    if status == "not-requested":
        return "not-requested"
    if status == "requested-blocked":
        return "blocked-runtime-config"
    return "failure-code-only"


def _commit_safe_omission_reasons() -> dict[str, str]:
    return {
        "raw_app_server_transcript": "local-only",
        "process_gate": "outside-plan-04",
        "post_refresh_cache_manifest": "outside-plan-04",
        "pre_refresh_config_sha256": "outside-plan-04",
        "post_refresh_config_sha256": "outside-plan-04",
        "smoke_summary": "outside-plan-04",
        "rollback_or_restore_status": "outside-plan-04",
        "exclusivity_status": "outside-plan-04",
    }
