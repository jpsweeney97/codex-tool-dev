from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

COMMIT_SAFE_TOP_LEVEL_KEYS = {
    "schema_version",
    "run_id",
    "mode",
    "source_local_summary_schema_version",
    "repo_head",
    "repo_tree",
    "source_implementation_commit",
    "source_implementation_tree",
    "execution_head",
    "execution_tree",
    "tool_path",
    "tool_sha256",
    "dirty_state_policy",
    "dirty_state",
    "current_run_identity",
    "local_only_evidence_root",
    "local_only_summary_sha256",
    "terminal_plan_status",
    "final_status",
    "isolated_rehearsal_run_id",
    "rehearsal_proof_sha256",
    "rehearsal_proof_validation_status",
    "source_to_rehearsal_execution_delta_status",
    "source_to_rehearsal_allowed_delta_proof_sha256",
    "source_to_rehearsal_changed_paths_sha256",
    "isolated_app_server_authority_proof_sha256",
    "no_real_home_authority_proof_sha256",
    "pre_snapshot_app_server_launch_authority_sha256",
    "pre_install_app_server_target_authority_sha256",
    "live_app_server_authority_proof_sha256",
    "source_manifest_sha256",
    "pre_refresh_cache_manifest_sha256",
    "post_refresh_cache_manifest_sha256",
    "pre_refresh_config_sha256",
    "post_refresh_config_sha256",
    "post_refresh_inventory_sha256",
    "selected_smoke_tier",
    "smoke_summary_sha256",
    "post_mutation_process_census_sha256",
    "exclusivity_status",
    "phase_reached",
    "rollback_or_restore_status",
    "axes",
    "diff_classification",
    "runtime_config",
    "app_server_inventory_status",
    "app_server_inventory_failure_reason_code",
    "app_server_inventory_summary_sha256",
    "app_server_request_methods",
    "codex_version",
    "codex_executable_path",
    "codex_executable_sha256",
    "codex_executable_hash_unavailable_reason",
    "app_server_server_info",
    "app_server_protocol_capabilities",
    "app_server_parser_version",
    "app_server_response_schema_version",
    "metadata_validation_summary_sha256",
    "redaction_validation_summary_sha256",
    "omission_reasons",
}

NESTED_ALLOWED_KEYS = {
    "dirty_state": {"status", "relevant_paths_checked", "post_commit_binding"},
    "current_run_identity": {
        "local_summary_schema_version",
        "local_summary_run_id",
        "local_summary_mode",
        "source_manifest_sha256",
        "source_manifest_unavailable_reason",
        "installed_cache_manifest_sha256",
        "installed_cache_manifest_unavailable_reason",
        "repo_marketplace_sha256",
        "repo_marketplace_unavailable_reason",
        "local_config_metadata_sha256",
        "local_config_metadata_unavailable_reason",
        "runtime_config_projection_sha256",
        "runtime_config_projection_unavailable_reason",
        "app_server_inventory_summary_sha256",
        "app_server_inventory_freshness",
        "runtime_identity",
        "runtime_identity_freshness",
    },
    "runtime_identity": {
        "codex_version",
        "codex_executable_path",
        "codex_executable_sha256",
        "codex_executable_hash_unavailable_reason",
        "app_server_server_info",
        "app_server_protocol_capabilities",
        "app_server_parser_version",
        "app_server_response_schema_version",
    },
    "app_server_server_info": {"name", "version"},
    "app_server_protocol_capabilities": {"experimentalApi"},
    "axes": {
        "filesystem_state",
        "coverage_state",
        "runtime_config_state",
        "preflight_state",
        "selected_mutation_mode",
        "reason_codes",
        "reason_count",
    },
    "runtime_config": {
        "state",
        "marketplace_state",
        "plugin_hooks_state",
        "plugin_enablement_state",
        "reason_codes",
        "reason_count",
    },
    "runtime_config_plugin_enablement_state": {
        "handoff@turbo-mode",
        "ticket@turbo-mode",
    },
    "diff_classification_item": {
        "canonical_path",
        "mutation_mode",
        "coverage_status",
        "outcome",
        "reason_codes",
        "smoke",
    },
    "omission_reasons": {
        "raw_app_server_transcript",
        "process_gate",
        "post_refresh_cache_manifest",
        "pre_refresh_config_sha256",
        "post_refresh_config_sha256",
        "smoke_summary",
        "rollback_or_restore_status",
        "exclusivity_status",
    },
}

ALLOWED_PLUGIN_ENABLEMENT_VALUES = {"enabled", "disabled", "missing", "malformed"}
ALLOWED_OMISSION_REASON_VALUES = {"local-only", "outside-non-mutating-refresh-plan"}
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
    "handoff-state-helper-direct-python-doc-migration",
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
ALLOWED_INVENTORY_FAILURE_REASON_CODES = {
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
ALLOWED_UNAVAILABLE_REASONS = {
    None,
    "source-root-unavailable",
    "installed-cache-root-unavailable",
    "runtime-config-parse-failed",
    "path-not-found",
    "permission-denied",
    "unavailable",
    "hash-unavailable",
}

FORBIDDEN_KEYS = {
    "app_server_transcript",
    "app_server_inventory_failure_reason",
    "raw_transcript",
    "events",
    "requests",
    "responses",
    "body",
    "config",
    "process_listing",
    "raw_process_listing",
    "config_contents",
    "config_toml",
    "request_bodies",
    "response_bodies",
    "reasons",
}

FORBIDDEN_KEY_FRAGMENTS = ("transcript", "request", "response", "config")

SENSITIVE_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)
CONFIG_OR_TRANSCRIPT_PATTERNS = (
    re.compile(r"(?i)\bjsonrpc\b"),
    re.compile(r"(?i)\brequest\b.*\bbody\b"),
    re.compile(r"(?i)\bresponse\b.*\bbody\b"),
    re.compile(r"(?m)^\s*\[plugins\]"),
    re.compile(r"(?m)^\s*(source|enabled|command)\s*="),
)
SAFE_SHORT_TEXT = re.compile(r"^[A-Za-z0-9._:@+ -]{0,120}$")
SAFE_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9._@+/=-]{1,240}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
BROAD_ABSOLUTE_PATH_PATTERN = re.compile(r"(^|\s)/(Users|private|tmp|var|etc|opt|home)/[^\s'\"]+")

EXPECTED_TOOL_PATH = "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"
EXPECTED_DIRTY_STATE_POLICY = "fail-relevant-dirty-state"
EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION = "turbo-mode-refresh-plan-03"
EXPECTED_COMMIT_SAFE_SCHEMA_VERSION = "turbo-mode-refresh-commit-safe-plan-06"
ALLOWED_DIRTY_RELEVANT_PATHS = {
    ".agents/plugins/marketplace.json",
    "plugins/turbo-mode/handoff/1.6.0",
    "plugins/turbo-mode/ticket/1.4.0",
    "plugins/turbo-mode/tools/refresh",
    "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
    "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
    "plugins/turbo-mode/tools/refresh_validate_redaction.py",
}
ALLOWED_APP_SERVER_METHODS = {
    "initialize",
    "initialized",
    "plugin/read",
    "plugin/list",
    "skills/list",
    "hooks/list",
}


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"load JSON object failed: {exc}. Got: {str(path)!r:.100}") from exc
    if not isinstance(payload, dict):
        raise ValueError(
            "load JSON object failed: top-level value is not an object. "
            f"Got: {type(payload).__name__!r:.100}"
        )
    return payload


def assert_commit_safe_payload(payload: dict[str, Any]) -> None:
    forbidden_top_level = set(payload) & FORBIDDEN_KEYS
    if forbidden_top_level:
        raise ValueError(
            "validate commit-safe payload failed: forbidden key. "
            f"Got: {sorted(forbidden_top_level)!r:.100}"
        )
    unknown_keys = set(payload) - COMMIT_SAFE_TOP_LEVEL_KEYS
    if unknown_keys:
        raise ValueError(
            "validate commit-safe payload failed: unknown key. "
            f"Got: {sorted(unknown_keys)!r:.100}"
        )
    _assert_nested_commit_safe_shapes(payload)
    _assert_commit_safe_enum_values(payload)
    _walk_payload(payload, path="$", allow_local_only_paths=False)
    _assert_field_values(payload)


def assert_no_sensitive_values(payload: dict[str, Any]) -> None:
    _walk_payload(payload, path="$", allow_local_only_paths=True)


def projected_summary_for_validator_digest(payload: dict[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(payload)
    projected["metadata_validation_summary_sha256"] = None
    projected["redaction_validation_summary_sha256"] = None
    return projected


def _assert_nested_commit_safe_shapes(payload: dict[str, Any]) -> None:
    dirty_state = payload.get("dirty_state")
    if isinstance(dirty_state, dict):
        _assert_allowed_keys("dirty_state", dirty_state, NESTED_ALLOWED_KEYS["dirty_state"])
    current_run_identity = payload.get("current_run_identity")
    if isinstance(current_run_identity, dict):
        _assert_allowed_keys(
            "current_run_identity",
            current_run_identity,
            NESTED_ALLOWED_KEYS["current_run_identity"],
        )
        _assert_runtime_identity(current_run_identity.get("runtime_identity"))
    _assert_server_info(payload.get("app_server_server_info"), name="app_server_server_info")
    _assert_protocol_capabilities(
        payload.get("app_server_protocol_capabilities"),
        name="app_server_protocol_capabilities",
    )
    axes = payload.get("axes")
    if isinstance(axes, dict):
        _assert_allowed_keys("axes", axes, NESTED_ALLOWED_KEYS["axes"])
    runtime_config = payload.get("runtime_config")
    if isinstance(runtime_config, dict):
        _assert_allowed_keys(
            "runtime_config",
            runtime_config,
            NESTED_ALLOWED_KEYS["runtime_config"],
        )
        plugin_enablement = runtime_config.get("plugin_enablement_state")
        if isinstance(plugin_enablement, dict):
            _assert_allowed_keys(
                "runtime_config.plugin_enablement_state",
                plugin_enablement,
                NESTED_ALLOWED_KEYS["runtime_config_plugin_enablement_state"],
            )
            invalid = [
                value
                for value in plugin_enablement.values()
                if value not in ALLOWED_PLUGIN_ENABLEMENT_VALUES
            ]
            if invalid:
                raise ValueError(
                    "validate commit-safe payload failed: invalid plugin enablement value. "
                    f"Got: {invalid!r:.100}"
                )
    diff_classification = payload.get("diff_classification")
    if isinstance(diff_classification, list):
        for item in diff_classification:
            if not isinstance(item, dict):
                raise ValueError(
                    "validate commit-safe payload failed: diff classification item is not "
                    f"an object. Got: {item!r:.100}"
                )
            _assert_allowed_keys(
                "diff_classification item",
                item,
                NESTED_ALLOWED_KEYS["diff_classification_item"],
            )
    omission_reasons = payload.get("omission_reasons")
    if isinstance(omission_reasons, dict):
        _assert_allowed_keys(
            "omission_reasons",
            omission_reasons,
            NESTED_ALLOWED_KEYS["omission_reasons"],
        )
        invalid = [
            value
            for value in omission_reasons.values()
            if value not in ALLOWED_OMISSION_REASON_VALUES
        ]
        if invalid:
            raise ValueError(
                "validate commit-safe payload failed: invalid omission reason. "
                f"Got: {invalid!r:.100}"
            )


def _assert_runtime_identity(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(
            "validate commit-safe payload failed: runtime identity is not an object. "
            f"Got: {value!r:.100}"
        )
    _assert_allowed_keys("runtime_identity", value, NESTED_ALLOWED_KEYS["runtime_identity"])
    _assert_server_info(
        value.get("app_server_server_info"),
        name="runtime_identity.app_server_server_info",
    )
    _assert_protocol_capabilities(
        value.get("app_server_protocol_capabilities"),
        name="runtime_identity.app_server_protocol_capabilities",
    )


def _assert_server_info(value: Any, *, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(
            "validate commit-safe payload failed: server info is not an object. "
            f"Got: {name!r:.100}"
        )
    _assert_allowed_keys(name, value, NESTED_ALLOWED_KEYS["app_server_server_info"])


def _assert_protocol_capabilities(value: Any, *, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(
            "validate commit-safe payload failed: protocol capabilities is not an object. "
            f"Got: {name!r:.100}"
        )
    _assert_allowed_keys(name, value, NESTED_ALLOWED_KEYS["app_server_protocol_capabilities"])


def _assert_field_values(payload: dict[str, Any]) -> None:
    _assert_equals_if_present(
        "schema_version",
        payload.get("schema_version"),
        EXPECTED_COMMIT_SAFE_SCHEMA_VERSION,
    )
    _assert_equals_if_present(
        "source_local_summary_schema_version",
        payload.get("source_local_summary_schema_version"),
        EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION,
    )
    _assert_equals_if_present(
        "dirty_state_policy",
        payload.get("dirty_state_policy"),
        EXPECTED_DIRTY_STATE_POLICY,
    )
    _assert_equals_if_present("tool_path", payload.get("tool_path"), EXPECTED_TOOL_PATH)
    if "local_only_evidence_root" in payload:
        _assert_local_only_evidence_root(payload.get("local_only_evidence_root"))
    if "dirty_state" in payload:
        _assert_dirty_state_values(payload.get("dirty_state"))
    _assert_server_info_values(payload.get("app_server_server_info"), path="app_server_server_info")
    _assert_protocol_capability_values(payload.get("app_server_protocol_capabilities"))
    _assert_runtime_identity_values(payload.get("current_run_identity"))
    _assert_request_methods(payload.get("app_server_request_methods"))
    _assert_diff_classification_values(payload.get("diff_classification"))
    executable = payload.get("codex_executable_path")
    if executable is not None and not _is_allowed_codex_executable_path(executable):
        raise ValueError(
            "validate commit-safe payload failed: invalid codex executable path. "
            f"Got: {executable!r:.100}"
        )
    if payload.get("mode") == "guarded-refresh":
        _assert_guarded_refresh_values(payload)


def _assert_equals_if_present(name: str, value: object, expected: object) -> None:
    if value is not None and value != expected:
        raise ValueError(
            f"validate commit-safe payload failed: invalid {name}. Got: {value!r:.100}"
        )


def _assert_guarded_refresh_values(payload: dict[str, Any]) -> None:
    required = {
        "source_implementation_commit",
        "source_implementation_tree",
        "execution_head",
        "execution_tree",
        "isolated_rehearsal_run_id",
        "rehearsal_proof_sha256",
        "rehearsal_proof_validation_status",
        "source_to_rehearsal_execution_delta_status",
        "source_to_rehearsal_allowed_delta_proof_sha256",
        "source_to_rehearsal_changed_paths_sha256",
        "isolated_app_server_authority_proof_sha256",
        "no_real_home_authority_proof_sha256",
        "pre_snapshot_app_server_launch_authority_sha256",
        "pre_install_app_server_target_authority_sha256",
        "live_app_server_authority_proof_sha256",
        "source_manifest_sha256",
        "pre_refresh_cache_manifest_sha256",
        "post_refresh_cache_manifest_sha256",
        "pre_refresh_config_sha256",
        "post_refresh_config_sha256",
        "post_refresh_inventory_sha256",
        "selected_smoke_tier",
        "smoke_summary_sha256",
        "post_mutation_process_census_sha256",
        "exclusivity_status",
        "phase_reached",
        "final_status",
        "rollback_or_restore_status",
    }
    missing = sorted(key for key in required if key not in payload)
    if missing:
        raise ValueError(
            "validate commit-safe payload failed: missing guarded-refresh field. "
            f"Got: {missing!r:.100}"
        )
    if payload.get("rehearsal_proof_validation_status") != "validated-before-live-mutation":
        raise ValueError(
            "validate commit-safe payload failed: invalid rehearsal proof validation status. "
            f"Got: {payload.get('rehearsal_proof_validation_status')!r:.100}"
        )
    if payload.get("source_to_rehearsal_execution_delta_status") not in {
        "identical",
        "approved-docs-evidence-only",
    }:
        raise ValueError(
            "validate commit-safe payload failed: invalid source-to-rehearsal delta status. "
            f"Got: {payload.get('source_to_rehearsal_execution_delta_status')!r:.100}"
        )
    if payload.get("final_status") == "MUTATION_COMPLETE_CERTIFIED" and payload.get(
        "rollback_or_restore_status"
    ) != "not-attempted":
        raise ValueError(
            "validate commit-safe payload failed: invalid rollback_or_restore_status. "
            f"Got: {payload.get('rollback_or_restore_status')!r:.100}"
        )
    if payload.get("exclusivity_status") == "exclusive_window_observed_by_process_samples":
        if not payload.get("post_mutation_process_census_sha256"):
            raise ValueError(
                "validate commit-safe payload failed: missing process gate summary. "
                "Got: post_mutation_process_census_sha256"
            )


def _assert_local_only_evidence_root(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError(
            "validate commit-safe payload failed: local-only evidence root is not a string. "
            f"Got: {value!r:.100}"
        )
    path = Path(value)
    if not path.is_absolute() or "/local-only/turbo-mode-refresh/" not in value:
        raise ValueError(
            "validate commit-safe payload failed: invalid local-only evidence root. "
            f"Got: {value!r:.100}"
        )
    if not SAFE_RUN_ID.fullmatch(path.name):
        raise ValueError(
            "validate commit-safe payload failed: invalid run id in local-only evidence root. "
            f"Got: {path.name!r:.100}"
        )


def _assert_dirty_state_values(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError(
            "validate commit-safe payload failed: dirty_state is not an object. "
            f"Got: {value!r:.100}"
        )
    if value.get("status") != "clean-relevant-paths":
        raise ValueError(
            "validate commit-safe payload failed: invalid dirty state status. "
            f"Got: {value.get('status')!r:.100}"
        )
    if value.get("post_commit_binding") is not False:
        raise ValueError(
            "validate commit-safe payload failed: invalid post_commit_binding. "
            f"Got: {value.get('post_commit_binding')!r:.100}"
        )
    paths = value.get("relevant_paths_checked")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise ValueError(
            "validate commit-safe payload failed: invalid dirty relevant paths. "
            f"Got: {paths!r:.100}"
        )
    unknown = set(paths) - ALLOWED_DIRTY_RELEVANT_PATHS
    if unknown:
        raise ValueError(
            "validate commit-safe payload failed: invalid dirty relevant path. "
            f"Got: {sorted(unknown)!r:.100}"
        )


def _assert_runtime_identity_values(current_run_identity: object) -> None:
    if not isinstance(current_run_identity, dict):
        return
    runtime_identity = current_run_identity.get("runtime_identity")
    if runtime_identity is None:
        return
    if not isinstance(runtime_identity, dict):
        raise ValueError(
            "validate commit-safe payload failed: runtime identity is not an object. "
            f"Got: {runtime_identity!r:.100}"
        )
    _assert_server_info_values(
        runtime_identity.get("app_server_server_info"),
        path="current_run_identity.runtime_identity.app_server_server_info",
    )
    _assert_protocol_capability_values(runtime_identity.get("app_server_protocol_capabilities"))
    executable = runtime_identity.get("codex_executable_path")
    if executable is not None and not _is_allowed_codex_executable_path(executable):
        raise ValueError(
            "validate commit-safe payload failed: invalid codex executable path. "
            f"Got: {executable!r:.100}"
        )


def _assert_server_info_values(value: object, *, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(
            "validate commit-safe payload failed: server info is not an object. "
            f"Got: {path!r:.100}"
        )
    for key in ("name", "version"):
        item = value.get(key)
        if (
            item is not None
            and (not isinstance(item, str) or not SAFE_SHORT_TEXT.fullmatch(item) or "/" in item)
        ):
            raise ValueError(
                "validate commit-safe payload failed: invalid server info value. "
                f"Got: {path}.{key}={item!r:.100}"
            )


def _assert_protocol_capability_values(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(
            "validate commit-safe payload failed: protocol capabilities is not an object. "
            f"Got: {value!r:.100}"
        )
    experimental_api = value.get("experimentalApi")
    if experimental_api is not None and not isinstance(experimental_api, bool):
        raise ValueError(
            "validate commit-safe payload failed: invalid experimentalApi capability. "
            f"Got: {experimental_api!r:.100}"
        )


def _assert_request_methods(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(
            "validate commit-safe payload failed: request methods must be strings. "
            f"Got: {value!r:.100}"
        )
    unknown = set(value) - ALLOWED_APP_SERVER_METHODS
    if unknown:
        raise ValueError(
            "validate commit-safe payload failed: invalid request method. "
            f"Got: {sorted(unknown)!r:.100}"
        )


def _assert_diff_classification_values(value: object) -> None:
    if not isinstance(value, list):
        return
    for item in value:
        if not isinstance(item, dict):
            continue
        canonical_path = item.get("canonical_path")
        if (
            not isinstance(canonical_path, str)
            or canonical_path.startswith("/")
            or ".." in canonical_path.split("/")
            or not SAFE_RELATIVE_PATH.fullmatch(canonical_path)
        ):
            raise ValueError(
                "validate commit-safe payload failed: invalid canonical path. "
                f"Got: {canonical_path!r:.100}"
            )


def _is_allowed_codex_executable_path(value: object) -> bool:
    if not isinstance(value, str):
        return False
    path = Path(value)
    return path.is_absolute() and path.name == "codex" and "\n" not in value


def _assert_commit_safe_enum_values(payload: dict[str, Any]) -> None:
    failure_code = payload.get("app_server_inventory_failure_reason_code")
    if failure_code not in ALLOWED_INVENTORY_FAILURE_REASON_CODES:
        raise ValueError(
            "validate commit-safe payload failed: invalid inventory failure reason code. "
            f"Got: {failure_code!r:.100}"
        )
    for container_name in ("axes", "runtime_config"):
        container = payload.get(container_name)
        if isinstance(container, dict):
            _assert_reason_codes(container_name, container, require_count=True)
    diff_classification = payload.get("diff_classification")
    if isinstance(diff_classification, list):
        for index, item in enumerate(diff_classification):
            if isinstance(item, dict):
                _assert_reason_codes(f"diff_classification[{index}]", item, require_count=False)
    _assert_unavailable_reasons(payload, path="$")


def _assert_reason_codes(name: str, container: dict[str, Any], *, require_count: bool) -> None:
    codes = container.get("reason_codes")
    if codes is None:
        return
    if not isinstance(codes, list) or not all(isinstance(code, str) for code in codes):
        raise ValueError(
            "validate commit-safe payload failed: reason_codes is not a string list. "
            f"Got: {name!r:.100}"
        )
    invalid = [code for code in codes if code not in SAFE_REASON_CODES]
    if invalid:
        raise ValueError(
            "validate commit-safe payload failed: invalid reason code. "
            f"Got: {invalid!r:.100}"
        )
    if require_count and container.get("reason_count") != len(codes):
        raise ValueError(
            "validate commit-safe payload failed: reason count mismatch. "
            f"Got: {name!r:.100}"
        )


def _assert_unavailable_reasons(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key.endswith("_unavailable_reason") and item not in ALLOWED_UNAVAILABLE_REASONS:
                raise ValueError(
                    "validate commit-safe payload failed: invalid unavailable reason. "
                    f"Got: {item_path}={item!r:.100}"
                )
            _assert_unavailable_reasons(item, path=item_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_unavailable_reasons(item, path=f"{path}[{index}]")


def _assert_allowed_keys(name: str, value: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(value) - allowed
    if unknown:
        label = "forbidden key" if _contains_forbidden_key_fragment(unknown) else "forbidden key"
        raise ValueError(
            f"validate commit-safe payload failed: {label}. "
            f"Got: {name}:{sorted(unknown)!r:.100}"
        )


def _contains_forbidden_key_fragment(keys: set[str]) -> bool:
    return any(fragment in key for key in keys for fragment in FORBIDDEN_KEY_FRAGMENTS)


def _walk_payload(value: Any, *, path: str, allow_local_only_paths: bool) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                raise ValueError(
                    "validate commit-safe payload failed: forbidden key. "
                    f"Got: {key!r:.100}"
                )
            _walk_payload(item, path=f"{path}.{key}", allow_local_only_paths=allow_local_only_paths)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_payload(
                item,
                path=f"{path}[{index}]",
                allow_local_only_paths=allow_local_only_paths,
            )
        return
    if isinstance(value, str):
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(value):
                raise ValueError(
                    "validate commit-safe payload failed: sensitive value. "
                    f"Got: {path!r:.100}"
                )
        for pattern in CONFIG_OR_TRANSCRIPT_PATTERNS:
            if pattern.search(value):
                raise ValueError(
                    "validate commit-safe payload failed: config or transcript shaped value. "
                    f"Got: {path!r:.100}"
                )
        if (
            not allow_local_only_paths
            and _looks_like_broad_absolute_path(value)
            and not _path_value_allowed(path, value)
        ):
            raise ValueError(
                "validate commit-safe payload failed: broad absolute path value. "
                f"Got: {path!r:.100}"
            )


def _looks_like_broad_absolute_path(value: str) -> bool:
    return bool(BROAD_ABSOLUTE_PATH_PATTERN.search(value))


def _path_value_allowed(path: str, value: str) -> bool:
    if path == "$.local_only_evidence_root":
        return "/local-only/turbo-mode-refresh/" in value
    if path.endswith(".codex_executable_path"):
        return _is_allowed_codex_executable_path(value)
    return False


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
