from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .app_server_inventory import (
    REAL_CODEX_HOME,
    AppServerInstallAuthority,
    AppServerLaunchAuthority,
    app_server_roundtrip,
    authority_digest,
    build_install_requests,
    build_pre_install_target_authority,
    collect_app_server_launch_authority,
    collect_readonly_runtime_inventory,
    serialize_authority_record,
    validate_install_responses,
)
from .lock_state import RunState, read_run_state, validate_cache_install_allowed
from .manifests import build_manifest, diff_manifests
from .models import fail
from .planner import RefreshPaths, build_plugin_specs


@dataclass(frozen=True)
class MutationContext:
    run_id: str
    mode: str
    repo_root: Path
    codex_home: Path
    local_only_run_root: Path
    source_implementation_commit: str
    source_implementation_tree: str
    execution_head: str
    execution_tree: str
    tool_sha256: str


@dataclass(frozen=True)
class SnapshotSet:
    config_snapshot_path: Path
    config_sha256: str
    cache_snapshot_root: Path
    source_manifest_sha256: dict[str, str]
    pre_refresh_cache_manifest_sha256: dict[str, str]
    config_path: Path
    snapshot_manifest_path: Path


def prove_app_server_home_authority(context: MutationContext) -> AppServerLaunchAuthority:
    authority, transcript = collect_app_server_launch_authority(_refresh_paths(context))
    _validate_launch_authority(authority, context=context, transcript=transcript)
    return authority


def create_snapshot_set(context: MutationContext) -> SnapshotSet:
    config_path = context.codex_home / "config.toml"
    if not config_path.exists():
        fail("create snapshot set", "config snapshot source missing", str(config_path))
    snapshot_root = context.local_only_run_root / "snapshots"
    config_snapshot_path = snapshot_root / "config.toml"
    cache_snapshot_root = snapshot_root / "cache"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot_root.chmod(0o700)
    shutil.copy2(config_path, config_snapshot_path)
    os.chmod(config_snapshot_path, 0o600)

    source_manifest_sha256: dict[str, str] = {}
    pre_refresh_cache_manifest_sha256: dict[str, str] = {}
    for spec in build_plugin_specs(repo_root=context.repo_root, codex_home=context.codex_home):
        source_manifest = build_manifest(spec, root_kind="source")
        cache_manifest = build_manifest(spec, root_kind="cache")
        source_manifest_sha256[spec.name] = authority_digest(source_manifest)
        pre_refresh_cache_manifest_sha256[spec.name] = authority_digest(cache_manifest)
        destination = cache_snapshot_root / spec.name / spec.version
        if destination.exists():
            shutil.rmtree(destination)
        if spec.cache_root.exists():
            shutil.copytree(spec.cache_root, destination)

    config_sha256 = _sha256_file(config_snapshot_path)
    snapshot_manifest_path = snapshot_root / "snapshot-manifest.json"
    _write_private_json(
        snapshot_manifest_path,
        {
            "config_snapshot_path": str(config_snapshot_path),
            "config_sha256": config_sha256,
            "cache_snapshot_root": str(cache_snapshot_root),
            "source_manifest_sha256": source_manifest_sha256,
            "pre_refresh_cache_manifest_sha256": pre_refresh_cache_manifest_sha256,
        },
    )
    return SnapshotSet(
        config_snapshot_path=config_snapshot_path,
        config_sha256=config_sha256,
        cache_snapshot_root=cache_snapshot_root,
        source_manifest_sha256=source_manifest_sha256,
        pre_refresh_cache_manifest_sha256=pre_refresh_cache_manifest_sha256,
        config_path=config_path,
        snapshot_manifest_path=snapshot_manifest_path,
    )


def prepare_plugin_hooks_for_guarded_refresh(
    context: MutationContext,
    *,
    plugin_hooks_state: str,
) -> dict[str, str]:
    config_path = context.codex_home / "config.toml"
    original = config_path.read_bytes()
    original_sha256 = hashlib.sha256(original).hexdigest()
    if plugin_hooks_state == "true":
        text = original.decode("utf-8")
        updated = re.sub(
            r"(^\s*plugin_hooks\s*=\s*)true(\s*(?:#.*)?)$",
            r"\1false\2",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if updated == text:
            fail("prepare plugin hooks", "plugin_hooks=true line missing", str(config_path))
        config_path.write_text(updated, encoding="utf-8")
        hook_disabled_sha256 = _sha256_file(config_path)
        return {
            "plugin_hooks_start_state": plugin_hooks_state,
            "original_config_sha256": original_sha256,
            "expected_intermediate_config_sha256": hook_disabled_sha256,
            "hook_disabled_config_sha256": hook_disabled_sha256,
        }
    if plugin_hooks_state == "absent-default-enabled":
        return {
            "plugin_hooks_start_state": plugin_hooks_state,
            "original_config_sha256": original_sha256,
            "expected_intermediate_config_sha256": original_sha256,
            "hook_disabled_config_sha256": original_sha256,
        }
    fail("prepare plugin hooks", "unsafe plugin_hooks state", plugin_hooks_state)


def restore_config_snapshot(snapshot: SnapshotSet, *, current_expected_sha256: str | None) -> None:
    if current_expected_sha256 is not None:
        current_sha256 = _sha256_file(snapshot.config_path)
        if current_sha256 != current_expected_sha256:
            fail(
                "restore config snapshot",
                "current config SHA256 mismatch",
                {"expected": current_expected_sha256, "actual": current_sha256},
            )
    shutil.copy2(snapshot.config_snapshot_path, snapshot.config_path)
    if _sha256_file(snapshot.config_path) != snapshot.config_sha256:
        fail(
            "restore config snapshot",
            "restored config SHA256 mismatch",
            str(snapshot.config_path),
        )


def install_plugins_via_app_server(context: MutationContext) -> tuple[dict[str, object], ...]:
    if context.codex_home == REAL_CODEX_HOME:
        state = _read_existing_run_state(context)
        validate_cache_install_allowed(state)
    launch_authority = prove_app_server_home_authority(context)
    pre_install_authority = build_pre_install_target_authority(
        launch_authority=launch_authority,
        marketplace_path=context.repo_root / ".agents/plugins/marketplace.json",
        remote_marketplace_name=None,
        allow_real_codex_home=context.codex_home == REAL_CODEX_HOME,
    )
    install_requests = build_install_requests(
        pre_install_authority=pre_install_authority,
        expected_requested_codex_home=context.codex_home,
        expected_launch_authority_sha256=authority_digest(launch_authority),
        expected_marketplace_path=context.repo_root / ".agents/plugins/marketplace.json",
    )
    install_transcript = tuple(
        app_server_roundtrip(
            requests=install_requests,
            env_overrides=launch_authority.child_environment_delta,
            cwd=Path(launch_authority.child_cwd),
        )
    )
    _, same_child_transcript = collect_readonly_runtime_inventory(_refresh_paths(context))
    _, fresh_child_transcript = collect_readonly_runtime_inventory(_refresh_paths(context))
    install_authority: AppServerInstallAuthority = validate_install_responses(
        transcript=install_transcript,
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
        install_requests=tuple(install_requests),
        same_child_post_install_transcript=same_child_transcript,
        fresh_child_post_install_transcript=fresh_child_transcript,
    )
    return (
        {
            "kind": "install-authority",
            "install_authority": serialize_authority_record(install_authority),
            "install_authority_sha256": authority_digest(install_authority),
        },
    )


def verify_source_cache_equality(context: MutationContext) -> dict[str, str]:
    equality: dict[str, str] = {}
    for spec in build_plugin_specs(repo_root=context.repo_root, codex_home=context.codex_home):
        source_manifest = build_manifest(spec, root_kind="source")
        cache_manifest = build_manifest(spec, root_kind="cache")
        diffs = diff_manifests(source_manifest, cache_manifest)
        if diffs:
            fail(
                "verify source/cache equality",
                "source/cache manifest mismatch",
                [diff.canonical_path for diff in diffs],
            )
        equality[spec.name] = authority_digest(source_manifest)
    return equality


def rollback_guarded_refresh(
    context: MutationContext,
    snapshot: SnapshotSet,
    *,
    failed_phase: str,
) -> dict[str, object]:
    _validate_snapshot_for_rollback(snapshot)
    restore_config_snapshot(snapshot, current_expected_sha256=None)
    for spec in build_plugin_specs(repo_root=context.repo_root, codex_home=context.codex_home):
        source = snapshot.cache_snapshot_root / spec.name / spec.version
        if not source.exists():
            fail("rollback guarded refresh", "cache snapshot path missing", str(source))
        if spec.cache_root.exists():
            shutil.rmtree(spec.cache_root)
        shutil.copytree(source, spec.cache_root)
    inventory, transcript = collect_readonly_runtime_inventory(_refresh_paths(context))
    return {
        "failed_phase": failed_phase,
        "final_status": "rollback-complete",
        "rollback_inventory_sha256": authority_digest(inventory),
        "rollback_transcript_sha256": authority_digest(transcript),
    }


def abort_after_config_mutation(
    context: MutationContext,
    snapshot: SnapshotSet,
    *,
    failed_phase: str,
) -> dict[str, object]:
    restore_config_snapshot(snapshot, current_expected_sha256=None)
    return {
        "failed_phase": failed_phase,
        "final_status": "config-restored",
        "restored_config_sha256": _sha256_file(context.codex_home / "config.toml"),
    }


def _refresh_paths(context: MutationContext) -> RefreshPaths:
    return RefreshPaths(
        repo_root=context.repo_root,
        codex_home=context.codex_home,
        marketplace_path=context.repo_root / ".agents/plugins/marketplace.json",
        config_path=context.codex_home / "config.toml",
        local_only_root=context.codex_home / "local-only/turbo-mode-refresh",
    )


def _validate_launch_authority(
    authority: AppServerLaunchAuthority,
    *,
    context: MutationContext,
    transcript: tuple[dict[str, Any], ...],
) -> None:
    if authority.requested_codex_home != str(context.codex_home):
        fail(
            "prove app-server home authority",
            "requested Codex home mismatch",
            authority.requested_codex_home,
        )
    if context.codex_home != REAL_CODEX_HOME:
        for value in _authority_strings(authority, transcript):
            if value.startswith(f"{REAL_CODEX_HOME}/"):
                fail(
                    "prove app-server home authority",
                    "isolated authority resolved live Codex home path",
                    value,
                )


def _authority_strings(
    authority: AppServerLaunchAuthority,
    transcript: tuple[dict[str, Any], ...],
) -> list[str]:
    payload = serialize_authority_record(authority)
    return [*_strings_in(payload), *_strings_in(transcript)]


def _strings_in(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for inner in value.values():
            result.extend(_strings_in(inner))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for inner in value:
            result.extend(_strings_in(inner))
        return result
    return []


def _read_existing_run_state(context: MutationContext) -> RunState:
    local_only_root = context.local_only_run_root.parent
    marker_path = local_only_root / "run-state" / f"{context.run_id}.marker.json"
    if not marker_path.exists():
        fail("install plugins via app-server", "snapshot marker is required", str(marker_path))
    return read_run_state(local_only_root, context.run_id)


def _validate_snapshot_for_rollback(snapshot: SnapshotSet) -> None:
    if not snapshot.snapshot_manifest_path.exists():
        fail(
            "rollback guarded refresh",
            "snapshot manifest is required",
            str(snapshot.snapshot_manifest_path),
        )
    if not snapshot.cache_snapshot_root.exists():
        fail(
            "rollback guarded refresh",
            "cache snapshot root missing",
            str(snapshot.cache_snapshot_root),
        )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)
