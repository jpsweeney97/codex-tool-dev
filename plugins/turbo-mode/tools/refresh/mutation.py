from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
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
    build_readonly_inventory_requests,
    build_same_child_post_install_requests,
    collect_app_server_launch_authority,
    collect_readonly_runtime_inventory,
    normalize_same_child_post_install_transcript,
    rewrite_ticket_hook_manifest,
    serialize_authority_record,
    validate_install_responses,
)
from .commit_safe import (
    build_guarded_refresh_commit_safe_summary,
    ensure_relevant_worktree_clean,
)
from .evidence import ensure_private_evidence_root, write_local_evidence
from .lock_state import (
    RunState,
    acquire_refresh_lock,
    clear_run_state,
    preserve_original_owner_for_recovery,
    read_owner_file,
    read_run_state,
    replace_run_state,
    validate_cache_install_allowed,
    validate_recovery_run_state,
    write_initial_run_state,
)
from .manifests import build_manifest, diff_manifests
from .models import DiffEntry, DiffKind, PluginSpec, RefreshError, fail
from .planner import RefreshPaths, build_plugin_specs, plan_refresh
from .process_gate import capture_process_gate
from .publication import (
    PublicationReplayPaths,
    PublicationReplayResult,
    publish_and_replay_commit_safe_summary,
)
from .smoke import run_standard_smoke
from .validation import assert_commit_safe_payload

PLAN05_DRIFT_PATHS = (
    "handoff/1.6.0/skills/load/SKILL.md",
    "handoff/1.6.0/skills/quicksave/SKILL.md",
    "handoff/1.6.0/skills/save/SKILL.md",
    "handoff/1.6.0/skills/summary/SKILL.md",
    "handoff/1.6.0/tests/test_session_state.py",
    "handoff/1.6.0/tests/test_skill_docs.py",
)
PLAN05_SEED_FIXTURE = Path(__file__).parent / (
    "tests/fixtures/handoff_state_helper_doc_migration.json"
)
TICKET_HOOK_MANIFEST_CANONICAL_PATH = "ticket/1.4.0/hooks/hooks.json"
TICKET_HOOK_COMMAND_SENTINEL = "<ticket-hook-command>"
REHEARSAL_PROOF_SCHEMA_VERSION = "turbo-mode-refresh-rehearsal-proof-v1"
REHEARSAL_CAPTURE_SCHEMA_VERSION = "turbo-mode-refresh-rehearsal-capture-v1"
NO_REAL_HOME_AUTHORITY_SCHEMA_VERSION = "turbo-mode-refresh-no-real-home-proof-v1"
NO_REAL_HOME_AUTHORITY_PATH_FIELDS = (
    "resolved_config_path",
    "resolved_plugin_cache_root",
    "resolved_local_only_root",
    "resolved_run_root",
    "resolved_handoff_plugin_root",
    "resolved_ticket_plugin_root",
    "resolved_ticket_hook_manifest_path",
)
REQUIRED_REHEARSAL_PROOF_FIELDS = frozenset(
    {
        "schema_version",
        "rehearsal_run_id",
        "seed_run_id",
        "seed_manifest_path",
        "seed_manifest_sha256",
        "seed_expected_drift_paths_sha256",
        "seed_source_manifest_sha256",
        "seed_pre_refresh_cache_manifest_sha256",
        "seed_post_seed_dry_run_manifest_sha256",
        "isolated_dry_run_id",
        "isolated_dry_run_proof_sha256",
        "source_implementation_commit",
        "source_implementation_tree",
        "execution_head",
        "execution_tree",
        "source_to_rehearsal_execution_delta_status",
        "source_to_rehearsal_changed_paths_sha256",
        "source_to_rehearsal_allowed_delta_proof_sha256",
        "tool_sha256",
        "requested_codex_home",
        "app_server_authority_proof_sha256",
        "no_real_home_authority_proof_sha256",
        "smoke_summary_sha256",
        "final_status",
        "certification_status",
        "referenced_artifacts",
    }
)
REQUIRED_REHEARSAL_ARTIFACT_DIGEST_FIELDS = (
    "seed_manifest_sha256",
    "seed_post_seed_dry_run_manifest_sha256",
    "isolated_dry_run_proof_sha256",
    "source_to_rehearsal_allowed_delta_proof_sha256",
    "app_server_authority_proof_sha256",
    "no_real_home_authority_proof_sha256",
    "smoke_summary_sha256",
)


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
    source_execution_identity_proof_path: str | None = None
    source_execution_identity_proof_sha256: str | None = None
    source_to_rehearsal_execution_delta_status: str = "identical"
    source_to_rehearsal_changed_paths_sha256: str = ""
    source_to_rehearsal_allowed_delta_proof_sha256: str | None = None


@dataclass(frozen=True)
class SnapshotSet:
    config_snapshot_path: Path
    config_sha256: str
    cache_snapshot_root: Path
    source_manifest_sha256: dict[str, str]
    pre_refresh_cache_manifest_sha256: dict[str, str]
    config_path: Path
    snapshot_manifest_path: Path


@dataclass(frozen=True)
class SourceExecutionProof:
    source_implementation_commit: str
    source_implementation_tree: str
    execution_head: str
    execution_tree: str
    changed_paths: tuple[str, ...]
    allowed_delta_status: str
    untracked_relevant_paths: tuple[str, ...]
    proof_path: str


@dataclass(frozen=True)
class GuardedRefreshResult:
    final_status: str
    final_status_path: str
    rehearsal_proof_path: str | None
    rehearsal_proof_sha256: str | None
    rehearsal_proof_sha256_path: str | None
    demoted_summary_path: str | None
    publication_failure_reason: str | None
    phase_log: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryResult:
    final_status: str
    final_status_path: str
    phase_log: tuple[str, ...]


@dataclass(frozen=True)
class SeedIsolatedRehearsalHomeResult:
    seed_manifest_path: str
    post_seed_dry_run_id: str
    post_seed_dry_run_path: str
    terminal_plan_status: str
    canonical_drift_paths: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedRehearsalProof:
    proof_path: str
    proof_sha256: str
    companion_path: str
    artifact_root: str
    payload: dict[str, Any]
    referenced_artifacts: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class RehearsalProofCaptureResult:
    capture_root: str
    capture_manifest_path: str
    capture_manifest_sha256: str


def prove_app_server_home_authority(
    context: MutationContext,
    *,
    ticket_hook_policy: str = "required",
) -> AppServerLaunchAuthority:
    authority, transcript = collect_app_server_launch_authority(
        _refresh_paths(context),
        ticket_hook_policy=ticket_hook_policy,
    )
    _validate_launch_authority(authority, context=context, transcript=transcript)
    return authority


def validate_rehearsal_proof_bundle(
    *,
    proof_path: Path,
    expected_sha256: str,
    source_implementation_commit: str,
    source_implementation_tree: str,
    tool_sha256: str,
) -> ValidatedRehearsalProof:
    normalized_proof = proof_path.expanduser().resolve(strict=True)
    actual_sha256 = _sha256_file(normalized_proof)
    if actual_sha256 != expected_sha256:
        fail(
            "validate rehearsal proof",
            "rehearsal proof SHA256 mismatch",
            {"expected": expected_sha256, "actual": actual_sha256},
        )
    companion_path = normalized_proof.with_name(f"{normalized_proof.name}.sha256")
    _validate_sha256_companion(
        companion_path,
        expected_path=normalized_proof,
        expected_sha256=actual_sha256,
    )
    proof = _load_json_object(normalized_proof, operation="validate rehearsal proof")
    missing = sorted(REQUIRED_REHEARSAL_PROOF_FIELDS - set(proof))
    if missing:
        fail("validate rehearsal proof", "missing rehearsal proof field", missing)
    _require_field(
        proof,
        "schema_version",
        REHEARSAL_PROOF_SCHEMA_VERSION,
        operation="validate rehearsal proof",
    )
    _require_field(
        proof,
        "source_implementation_commit",
        source_implementation_commit,
        operation="validate rehearsal proof",
    )
    _require_field(
        proof,
        "source_implementation_tree",
        source_implementation_tree,
        operation="validate rehearsal proof",
    )
    _require_field(proof, "tool_sha256", tool_sha256, operation="validate rehearsal proof")
    _require_field(
        proof,
        "final_status",
        "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED",
        operation="validate rehearsal proof",
    )
    _require_field(
        proof,
        "certification_status",
        "local-only-non-certified",
        operation="validate rehearsal proof",
    )
    requested_home = Path(str(proof["requested_codex_home"]))
    if _is_under_path(requested_home, REAL_CODEX_HOME):
        fail(
            "validate rehearsal proof",
            "requested Codex home resolves under real home",
            str(requested_home),
        )
    delta_status = proof["source_to_rehearsal_execution_delta_status"]
    if delta_status not in {
        "identical",
        "approved-docs-evidence-only",
    }:
        fail(
            "validate rehearsal proof",
            "invalid source-to-rehearsal delta status",
            delta_status,
        )
    if delta_status == "identical":
        _require_field(
            proof,
            "execution_head",
            source_implementation_commit,
            operation="validate rehearsal proof",
        )
        _require_field(
            proof,
            "execution_tree",
            source_implementation_tree,
            operation="validate rehearsal proof",
        )
    artifact_root = normalized_proof.parent.parent
    referenced_artifacts = _validate_referenced_artifacts(
        proof,
        artifact_root=artifact_root,
    )
    _validate_source_to_rehearsal_delta_proof(
        proof,
        referenced_artifacts,
        artifact_root=artifact_root,
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
    )
    _validate_seed_manifest(
        proof,
        artifact_root=artifact_root,
        expected_requested_home=str(requested_home),
    )
    _validate_digest_referenced_json(
        proof,
        referenced_artifacts,
        "isolated_dry_run_proof_sha256",
        artifact_root=artifact_root,
        expected_fields={"terminal_plan_status": "guarded-refresh-required"},
    )
    _validate_digest_referenced_json(
        proof,
        referenced_artifacts,
        "app_server_authority_proof_sha256",
        artifact_root=artifact_root,
        expected_fields={"requested_codex_home": str(requested_home)},
    )
    _validate_no_real_home_authority_proof(
        proof,
        referenced_artifacts,
        artifact_root=artifact_root,
        expected_requested_home=str(requested_home),
    )
    _validate_digest_referenced_json(
        proof,
        referenced_artifacts,
        "smoke_summary_sha256",
        artifact_root=artifact_root,
        expected_fields={"final_status": "passed"},
    )
    return ValidatedRehearsalProof(
        proof_path=str(normalized_proof),
        proof_sha256=actual_sha256,
        companion_path=str(companion_path),
        artifact_root=str(artifact_root),
        payload=proof,
        referenced_artifacts=referenced_artifacts,
    )


def capture_rehearsal_proof_bundle(
    validated: ValidatedRehearsalProof,
    *,
    live_run_root: Path,
) -> RehearsalProofCaptureResult:
    capture_root = live_run_root / "rehearsal-proof-capture"
    ensure_private_evidence_root(live_run_root.parent)
    if live_run_root.is_symlink():
        fail("capture rehearsal proof", "live run root uses symlink", str(live_run_root))
    if live_run_root.exists() and not live_run_root.is_dir():
        fail("capture rehearsal proof", "live run root is not a directory", str(live_run_root))
    if capture_root.exists():
        fail("capture rehearsal proof", "capture root already exists", str(capture_root))
    live_run_root.mkdir(parents=True, exist_ok=True)
    live_run_root.chmod(0o700)
    capture_root.mkdir(parents=True, exist_ok=False)
    capture_root.chmod(0o700)
    artifact_root = Path(validated.artifact_root)
    copy_plan: dict[str, Path] = {}
    proof_path = Path(validated.proof_path)
    companion_path = Path(validated.companion_path)
    copy_plan[_relative_to_artifact_root(proof_path, artifact_root)] = proof_path
    copy_plan[_relative_to_artifact_root(companion_path, artifact_root)] = companion_path
    for artifact in validated.referenced_artifacts:
        relative_path = artifact["relative_path"]
        copy_plan[relative_path] = _resolve_referenced_artifact_path(
            artifact_root,
            relative_path,
            operation="capture rehearsal proof",
        )

    captured_at = datetime.now(UTC).isoformat()
    captured_artifacts: list[dict[str, object]] = []
    for relative_path in sorted(copy_plan):
        source_path = copy_plan[relative_path]
        captured_path = capture_root / relative_path
        _copy_private_file(source_path, captured_path)
        digest = _sha256_file(captured_path)
        captured_artifacts.append(
            {
                "relative_path": relative_path,
                "source_path": str(source_path),
                "captured_path": str(captured_path),
                "sha256": digest,
                "byte_size": captured_path.stat().st_size,
                "captured_at": captured_at,
            }
        )
    manifest_path = capture_root / "capture-manifest.json"
    manifest = {
        "schema_version": REHEARSAL_CAPTURE_SCHEMA_VERSION,
        "rehearsal_proof_path": validated.proof_path,
        "rehearsal_proof_sha256": validated.proof_sha256,
        "source_artifact_root": validated.artifact_root,
        "capture_root": str(capture_root),
        "captured_artifacts": captured_artifacts,
    }
    _write_private_json(manifest_path, manifest)
    _fsync_file_and_parent(manifest_path)
    _validate_capture_manifest(manifest)
    return RehearsalProofCaptureResult(
        capture_root=str(capture_root),
        capture_manifest_path=str(manifest_path),
        capture_manifest_sha256=_sha256_file(manifest_path),
    )


def verify_source_execution_identity(
    *,
    repo_root: Path,
    local_only_run_root: Path,
    source_implementation_commit: str,
    source_implementation_tree: str,
) -> SourceExecutionProof:
    actual_source_tree = _git(
        repo_root,
        "rev-parse",
        f"{source_implementation_commit}^{{tree}}",
        operation="verify source implementation tree",
    )
    if actual_source_tree != source_implementation_tree:
        fail(
            "verify source/execution identity",
            "source implementation tree mismatch",
            {
                "expected": source_implementation_tree,
                "actual": actual_source_tree,
            },
        )

    execution_head = _git(repo_root, "rev-parse", "HEAD", operation="resolve execution head")
    execution_tree = _git(
        repo_root,
        "rev-parse",
        "HEAD^{tree}",
        operation="resolve execution tree",
    )
    if not _git_success(
        repo_root,
        "merge-base",
        "--is-ancestor",
        source_implementation_commit,
        execution_head,
    ):
        fail(
            "verify source/execution identity",
            "source implementation commit is not an ancestor of execution head",
            {"source": source_implementation_commit, "execution_head": execution_head},
        )

    changed_paths = tuple(
        path
        for path in _git(
            repo_root,
            "diff",
            "--name-only",
            f"{source_implementation_commit}..{execution_head}",
            operation="compute source/execution delta",
        ).splitlines()
        if path
    )
    disallowed_paths = tuple(path for path in changed_paths if not _is_allowed_delta_path(path))
    if disallowed_paths:
        fail(
            "verify source/execution identity",
            "disallowed source-to-execution delta",
            list(disallowed_paths),
        )

    untracked_relevant = _untracked_relevant_paths(repo_root)
    if untracked_relevant:
        fail(
            "verify source/execution identity",
            "untracked relevant files",
            list(untracked_relevant),
        )

    proof_path = local_only_run_root / "source-execution-identity.proof.json"
    proof = SourceExecutionProof(
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
        execution_head=execution_head,
        execution_tree=execution_tree,
        changed_paths=changed_paths,
        allowed_delta_status="docs-evidence-only" if changed_paths else "none",
        untracked_relevant_paths=(),
        proof_path=str(proof_path),
    )
    _write_private_json(proof_path, proof)
    return proof


def seed_isolated_rehearsal_home(
    *,
    repo_root: Path,
    codex_home: Path,
    run_id: str,
    source_implementation_commit: str,
    source_implementation_tree: str,
) -> SeedIsolatedRehearsalHomeResult:
    normalized_repo_root = repo_root.expanduser().resolve(strict=True)
    normalized_codex_home = codex_home.expanduser().resolve(strict=False)
    if _is_under_path(normalized_codex_home, REAL_CODEX_HOME):
        fail(
            "seed isolated rehearsal home",
            "codex home must be outside /Users/jp/.codex",
            str(normalized_codex_home),
        )

    local_only_root = normalized_codex_home / "local-only/turbo-mode-refresh"
    local_only_run_root = local_only_root / run_id
    source_identity = verify_source_execution_identity(
        repo_root=normalized_repo_root,
        local_only_run_root=local_only_run_root,
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
    )
    local_only_root.chmod(0o700)

    config_path = normalized_codex_home / "config.toml"
    cache_root = normalized_codex_home / "plugins/cache/turbo-mode"
    _reject_real_home_paths(
        (
            config_path,
            cache_root,
            local_only_root,
            local_only_run_root,
        )
    )
    for target in (config_path, cache_root):
        if target.exists():
            fail("seed isolated rehearsal home", "target already exists", str(target))

    _write_seed_config(config_path, repo_root=normalized_repo_root)
    seed_records = _load_plan05_seed_records()
    for spec in build_plugin_specs(
        repo_root=normalized_repo_root,
        codex_home=normalized_codex_home,
    ):
        if not spec.source_root.exists():
            fail("seed isolated rehearsal home", "source root missing", str(spec.source_root))
        shutil.copytree(spec.source_root, spec.cache_root)

    for canonical_path in PLAN05_DRIFT_PATHS:
        record = seed_records.get(canonical_path)
        if not isinstance(record, dict):
            fail("seed isolated rehearsal home", "missing seed fixture record", canonical_path)
        source_path = normalized_repo_root / "plugins/turbo-mode" / canonical_path
        cache_path = normalized_codex_home / "plugins/cache/turbo-mode" / canonical_path
        source_text = source_path.read_text(encoding="utf-8")
        if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != record.get("source_sha256"):
            fail(
                "seed isolated rehearsal home",
                "source seed fixture hash mismatch",
                canonical_path,
            )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(str(record["cache_text"]), encoding="utf-8")

    source_manifest_sha256: dict[str, str] = {}
    pre_refresh_cache_manifest_sha256: dict[str, str] = {}
    observed_drift_paths: list[str] = []
    for spec in build_plugin_specs(
        repo_root=normalized_repo_root,
        codex_home=normalized_codex_home,
    ):
        source_manifest = build_manifest(spec, root_kind="source")
        cache_manifest = build_manifest(spec, root_kind="cache")
        source_manifest_sha256[spec.name] = authority_digest(source_manifest)
        pre_refresh_cache_manifest_sha256[spec.name] = authority_digest(cache_manifest)
        observed_drift_paths.extend(
            diff.canonical_path for diff in diff_manifests(source_manifest, cache_manifest)
        )
    if tuple(sorted(observed_drift_paths)) != PLAN05_DRIFT_PATHS:
        fail(
            "seed isolated rehearsal home",
            "seeded drift set mismatch",
            sorted(observed_drift_paths),
        )
    isolated_ticket_hook_manifest = rewrite_ticket_hook_manifest(
        ticket_plugin_root=normalized_codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"
    )

    post_seed_dry_run = plan_refresh(
        repo_root=normalized_repo_root,
        codex_home=normalized_codex_home,
        mode="dry-run",
        inventory_check=True,
    )
    if post_seed_dry_run.terminal_status.value != "guarded-refresh-required":
        fail(
            "seed isolated rehearsal home",
            "post-seed dry-run status mismatch",
            post_seed_dry_run.terminal_status.value,
        )
    post_seed_dry_run_id = f"{run_id}-post-seed-dry-run"
    post_seed_dry_run_path = write_local_evidence(
        post_seed_dry_run,
        run_id=post_seed_dry_run_id,
    )
    generated_paths = tuple(
        sorted(
            str(path.resolve(strict=False))
            for path in (
                normalized_codex_home,
                config_path,
                cache_root,
                local_only_root,
                local_only_run_root,
                isolated_ticket_hook_manifest,
                post_seed_dry_run_path,
            )
        )
    )
    _reject_real_home_paths(Path(path) for path in generated_paths)

    seed_manifest_path = local_only_run_root / "seed-manifest.json"
    _write_private_json(
        seed_manifest_path,
        {
            "schema_version": "turbo-mode-refresh-isolated-seed-v1",
            "run_id": run_id,
            "source_implementation_commit": source_implementation_commit,
            "source_implementation_tree": source_implementation_tree,
            "source_execution_identity_proof": source_identity.proof_path,
            "execution_head": source_identity.execution_head,
            "execution_tree": source_identity.execution_tree,
            "requested_codex_home": str(normalized_codex_home),
            "isolated_ticket_hook_manifest_path": str(isolated_ticket_hook_manifest),
            "canonical_drift_paths": PLAN05_DRIFT_PATHS,
            "canonical_drift_paths_sha256": authority_digest(PLAN05_DRIFT_PATHS),
            "source_manifest_sha256": authority_digest(source_manifest_sha256),
            "source_manifest_sha256_by_plugin": source_manifest_sha256,
            "pre_refresh_isolated_cache_manifest_sha256": authority_digest(
                pre_refresh_cache_manifest_sha256
            ),
            "pre_refresh_isolated_cache_manifest_sha256_by_plugin": (
                pre_refresh_cache_manifest_sha256
            ),
            "post_seed_dry_run_id": post_seed_dry_run_id,
            "post_seed_dry_run_path": str(post_seed_dry_run_path),
            "post_seed_dry_run_manifest_sha256": _sha256_file(post_seed_dry_run_path),
            "post_seed_terminal_status": post_seed_dry_run.terminal_status.value,
            "generated_paths": generated_paths,
            "no_real_home_paths": True,
        },
    )
    return SeedIsolatedRehearsalHomeResult(
        seed_manifest_path=str(seed_manifest_path),
        post_seed_dry_run_id=post_seed_dry_run_id,
        post_seed_dry_run_path=str(post_seed_dry_run_path),
        terminal_plan_status=post_seed_dry_run.terminal_status.value,
        canonical_drift_paths=PLAN05_DRIFT_PATHS,
    )


def run_guarded_refresh_orchestration(
    context: MutationContext,
    *,
    terminal_plan_status: str,
    plugin_hooks_state: str,
    isolated_rehearsal: bool,
) -> GuardedRefreshResult:
    if terminal_plan_status != "guarded-refresh-required":
        fail(
            "run guarded refresh orchestration",
            "terminal plan status is not guarded-refresh-required",
            terminal_plan_status,
        )
    if context.codex_home == REAL_CODEX_HOME and isolated_rehearsal:
        fail(
            "run guarded refresh orchestration",
            "isolated rehearsal cannot use real Codex home",
            str(context.codex_home),
        )

    local_only_root = context.local_only_run_root.parent
    phase_log: list[str] = []
    final_status_path = context.local_only_run_root / "final-status.json"
    rehearsal_proof_path: Path | None = None

    with acquire_refresh_lock(
        local_only_root=local_only_root,
        run_id=context.run_id,
        mode=context.mode,
        source_implementation_commit=context.source_implementation_commit,
        execution_head=context.execution_head,
        tool_sha256=context.tool_sha256,
    ) as owner:
        owner_sha256 = authority_digest(owner)
        write_initial_run_state(
            local_only_root,
            RunState(
                run_id=context.run_id,
                mode=context.mode,
                source_implementation_commit=context.source_implementation_commit,
                source_implementation_tree=context.source_implementation_tree,
                execution_head=context.execution_head,
                execution_tree=context.execution_tree,
                tool_sha256=context.tool_sha256,
                original_run_owner_sha256=owner_sha256,
                phase="marker-started",
            ),
        )
        try:
            before_snapshot = _run_process_gate(context, label="before-snapshot")
            _raise_if_process_blocked(before_snapshot, failed_phase="before-snapshot")
            _replace_state(
                context,
                phase="before-snapshot-process-checked",
                process_summary_sha256={
                    "before-snapshot": authority_digest(before_snapshot),
                },
            )
            phase_log.append("before-snapshot")

            launch_authority = prove_app_server_home_authority(context)
            launch_authority_proof_path = context.local_only_run_root / (
                "app-server-authority.proof.json"
            )
            _write_private_json(launch_authority_proof_path, launch_authority)
            launch_authority_sha256 = authority_digest(launch_authority)
            _replace_state(
                context,
                phase="app-server-launch-authority-proven",
                pre_snapshot_app_server_launch_authority_sha256=launch_authority_sha256,
            )
            phase_log.append("app-server-launch-authority-proven")

            snapshot = create_snapshot_set(context)
            _replace_state(
                context,
                phase="snapshot-written",
                pre_snapshot_app_server_launch_authority_sha256=launch_authority_sha256,
                snapshot_path_map={
                    "config": str(snapshot.config_snapshot_path),
                    "cache": str(snapshot.cache_snapshot_root),
                    "manifest": str(snapshot.snapshot_manifest_path),
                },
                snapshot_manifest_digest=_sha256_file(snapshot.snapshot_manifest_path),
                original_config_sha256=snapshot.config_sha256,
                pre_refresh_cache_manifest_sha256=snapshot.pre_refresh_cache_manifest_sha256,
                recovery_eligibility="restore-cache-and-config",
            )
            phase_log.append("snapshot-written")

            hook_state = prepare_plugin_hooks_for_guarded_refresh(
                context,
                plugin_hooks_state=plugin_hooks_state,
            )
            _replace_state(
                context,
                phase="hooks-disabled",
                pre_snapshot_app_server_launch_authority_sha256=launch_authority_sha256,
                plugin_hooks_start_state=hook_state["plugin_hooks_start_state"],
                original_config_sha256=hook_state["original_config_sha256"],
                expected_intermediate_config_sha256=hook_state[
                    "expected_intermediate_config_sha256"
                ],
                hook_disabled_config_sha256=hook_state["hook_disabled_config_sha256"],
                snapshot_path_map={
                    "config": str(snapshot.config_snapshot_path),
                    "cache": str(snapshot.cache_snapshot_root),
                    "manifest": str(snapshot.snapshot_manifest_path),
                },
                snapshot_manifest_digest=_sha256_file(snapshot.snapshot_manifest_path),
                pre_refresh_cache_manifest_sha256=snapshot.pre_refresh_cache_manifest_sha256,
                recovery_eligibility="restore-cache-and-config",
            )
            phase_log.append("hooks-disabled")

            after_hook = _run_process_gate(context, label="after-hook-disable")
            _raise_if_process_blocked(after_hook, failed_phase="after-hook-disable")
            phase_log.append("after-hook-disable")

            before_install = _run_process_gate(context, label="before-install")
            _raise_if_process_blocked(before_install, failed_phase="before-install")
            phase_log.append("before-install")

            install_records = install_plugins_via_app_server(
                context,
                restore_config_before_post_install=lambda: restore_config_snapshot(
                    snapshot,
                    current_expected_sha256=hook_state["expected_intermediate_config_sha256"],
                ),
                pre_install_ticket_hook_policy=(
                    "disabled" if hook_state["plugin_hooks_start_state"] == "true" else "required"
                ),
                same_child_ticket_hook_policy="required",
            )
            phase_log.append("install-complete")
            phase_log.append("config-restored")

            final_inventory, final_inventory_transcript = collect_readonly_runtime_inventory(
                _refresh_paths(context)
            )
            equality = verify_source_cache_equality(context)
            try:
                smoke_summary = _run_standard_smoke_for_context(context)
            except (RefreshError, OSError, ValueError) as exc:
                rollback_guarded_refresh(context, snapshot, failed_phase="smoke")
                return _write_final_status(
                    context,
                    final_status="MUTATION_FAILED_ROLLBACK_COMPLETE",
                    phase_log=phase_log,
                    final_status_path=final_status_path,
                    rehearsal_proof_path=None,
                    failure_reason=str(exc),
                )
            if smoke_summary.get("final_status") != "passed":
                rollback_guarded_refresh(context, snapshot, failed_phase="smoke")
                return _write_final_status(
                    context,
                    final_status="MUTATION_FAILED_ROLLBACK_COMPLETE",
                    phase_log=phase_log,
                    final_status_path=final_status_path,
                    rehearsal_proof_path=None,
                )
            phase_log.append("smoke-passed")

            post_mutation = _run_process_gate(context, label="post-mutation")
            _raise_if_process_blocked(post_mutation, failed_phase="post-mutation")
            phase_log.append("post-mutation")

            if isolated_rehearsal:
                final_status = "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"
                rehearsal_proof_path = context.local_only_run_root / "rehearsal-proof.json"
                smoke_summary_path = context.local_only_run_root / "standard-smoke.summary.json"
                if not smoke_summary_path.exists():
                    _write_private_json(smoke_summary_path, smoke_summary)
                no_real_home_proof_path = context.local_only_run_root / (
                    "no-real-home-authority.proof.json"
                )
                _write_private_json(
                    no_real_home_proof_path,
                    {
                        "schema_version": NO_REAL_HOME_AUTHORITY_SCHEMA_VERSION,
                        "run_id": context.run_id,
                        "requested_codex_home": str(context.codex_home),
                        "authority_result": "isolated-home-authority-proven",
                        "no_real_home_paths": True,
                        "resolved_config_path": str(context.codex_home / "config.toml"),
                        "resolved_plugin_cache_root": str(
                            context.codex_home / "plugins/cache/turbo-mode"
                        ),
                        "resolved_local_only_root": str(
                            context.codex_home / "local-only/turbo-mode-refresh"
                        ),
                        "resolved_run_root": str(context.local_only_run_root),
                        "resolved_handoff_plugin_root": str(
                            context.codex_home
                            / "plugins/cache/turbo-mode/handoff/1.6.0"
                        ),
                        "resolved_ticket_plugin_root": str(
                            context.codex_home
                            / "plugins/cache/turbo-mode/ticket/1.4.0"
                        ),
                        "resolved_ticket_hook_manifest_path": str(
                            context.codex_home
                            / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
                        ),
                        "app_server_authority_proof_sha256": _sha256_file(
                            launch_authority_proof_path
                        ),
                        "smoke_summary_sha256": _sha256_file(smoke_summary_path),
                    },
                )
                seed_manifest_path, seed_manifest = _find_seed_manifest_for_rehearsal(context)
                source_delta_proof_path = _require_existing_artifact_path(
                    context.source_execution_identity_proof_path,
                    operation="write rehearsal proof",
                    reason="source execution identity proof missing",
                )
                referenced_artifacts = _build_rehearsal_referenced_artifacts(
                    context.local_only_run_root.parent,
                    (
                        seed_manifest_path,
                        Path(str(seed_manifest["post_seed_dry_run_path"])),
                        source_delta_proof_path,
                        launch_authority_proof_path,
                        no_real_home_proof_path,
                        smoke_summary_path,
                    ),
                )
                _write_private_json(
                    rehearsal_proof_path,
                    {
                        "schema_version": REHEARSAL_PROOF_SCHEMA_VERSION,
                        "rehearsal_run_id": context.run_id,
                        "seed_run_id": seed_manifest["run_id"],
                        "seed_manifest_path": _relative_to_artifact_root(
                            seed_manifest_path,
                            context.local_only_run_root.parent,
                        ),
                        "seed_manifest_sha256": _sha256_file(seed_manifest_path),
                        "seed_expected_drift_paths_sha256": seed_manifest[
                            "canonical_drift_paths_sha256"
                        ],
                        "seed_source_manifest_sha256": seed_manifest[
                            "source_manifest_sha256"
                        ],
                        "seed_pre_refresh_cache_manifest_sha256": seed_manifest[
                            "pre_refresh_isolated_cache_manifest_sha256"
                        ],
                        "seed_post_seed_dry_run_manifest_sha256": seed_manifest[
                            "post_seed_dry_run_manifest_sha256"
                        ],
                        "isolated_dry_run_id": seed_manifest["post_seed_dry_run_id"],
                        "isolated_dry_run_proof_sha256": seed_manifest[
                            "post_seed_dry_run_manifest_sha256"
                        ],
                        "source_implementation_commit": (context.source_implementation_commit),
                        "source_implementation_tree": context.source_implementation_tree,
                        "execution_head": context.execution_head,
                        "execution_tree": context.execution_tree,
                        "tool_sha256": context.tool_sha256,
                        "requested_codex_home": str(context.codex_home),
                        "no_real_home_proof": context.codex_home != REAL_CODEX_HOME,
                        "source_execution_identity_proof_path": (
                            context.source_execution_identity_proof_path
                        ),
                        "source_execution_identity_proof_sha256": (
                            context.source_execution_identity_proof_sha256
                        ),
                        "source_to_rehearsal_execution_delta_status": (
                            context.source_to_rehearsal_execution_delta_status
                        ),
                        "source_to_rehearsal_changed_paths_sha256": (
                            context.source_to_rehearsal_changed_paths_sha256
                        ),
                        "source_to_rehearsal_allowed_delta_proof_sha256": (
                            _sha256_file(source_delta_proof_path)
                        ),
                        "app_server_authority_proof_sha256": _sha256_file(
                            launch_authority_proof_path
                        ),
                        "no_real_home_authority_proof_sha256": _sha256_file(
                            no_real_home_proof_path
                        ),
                        "smoke_summary_sha256": _sha256_file(smoke_summary_path),
                        "final_status": final_status,
                        "certification_status": "local-only-non-certified",
                        "referenced_artifacts": referenced_artifacts,
                        "install_records_sha256": authority_digest(install_records),
                        "final_inventory_sha256": authority_digest(final_inventory),
                        "final_inventory_transcript_sha256": authority_digest(
                            final_inventory_transcript
                        ),
                        "source_cache_equality_sha256": authority_digest(equality),
                    },
                )
                rehearsal_proof_sha256 = _write_sha256_companion(rehearsal_proof_path)
                return _write_final_status(
                    context,
                    final_status=final_status,
                    phase_log=phase_log,
                    final_status_path=final_status_path,
                    rehearsal_proof_path=rehearsal_proof_path,
                    rehearsal_proof_sha256=rehearsal_proof_sha256,
                )
            try:
                publish_guarded_refresh_commit_safe_summary(
                    context=context,
                    source_code_root=context.repo_root,
                    execution_repo_root=context.repo_root,
                    guarded_evidence=_build_live_guarded_refresh_commit_safe_evidence(
                        context=context,
                        launch_authority_sha256=launch_authority_sha256,
                        launch_authority_proof_path=launch_authority_proof_path,
                        install_records=install_records,
                        snapshot=snapshot,
                        final_inventory=final_inventory,
                        equality=equality,
                        smoke_summary=smoke_summary,
                        post_mutation=post_mutation,
                    ),
                )
                phase_log.append("evidence-published")
            except BaseException as exc:
                return _write_final_status(
                    context,
                    final_status="MUTATION_COMPLETE_EVIDENCE_FAILED",
                    phase_log=phase_log,
                    final_status_path=final_status_path,
                    rehearsal_proof_path=None,
                    demoted_summary_path=getattr(exc, "demoted_summary_path", None),
                    publication_failure_reason=str(exc),
                )
            return _write_final_status(
                context,
                final_status="MUTATION_COMPLETE_CERTIFIED",
                phase_log=phase_log,
                final_status_path=final_status_path,
                rehearsal_proof_path=None,
            )
        finally:
            clear_run_state(local_only_root, context.run_id)


def run_guarded_refresh_recovery(context: MutationContext) -> RecoveryResult:
    local_only_root = context.local_only_run_root.parent
    state = read_run_state(local_only_root, context.run_id)
    _validate_recovery_identity(context, state)
    validate_recovery_run_state(state, expected_run_id=context.run_id)
    owner_path = local_only_root / "run-state" / f"{context.run_id}.owner.json"
    original_owner = read_owner_file(owner_path)
    original_owner_sha256 = authority_digest(original_owner)
    if state.original_run_owner_sha256 != original_owner_sha256:
        fail(
            "run guarded refresh recovery",
            "original run owner SHA256 mismatch",
            {
                "expected": state.original_run_owner_sha256,
                "actual": original_owner_sha256,
            },
        )

    phase_log: list[str] = []
    final_status_path = context.local_only_run_root / "final-status.json"
    with acquire_refresh_lock(
        local_only_root=local_only_root,
        run_id=context.run_id,
        mode="recover",
        source_implementation_commit=context.source_implementation_commit,
        execution_head=context.execution_head,
        tool_sha256=context.tool_sha256,
    ) as recovery_owner:
        state = read_run_state(local_only_root, context.run_id)
        _validate_recovery_identity(context, state)
        preserved_owner = preserve_original_owner_for_recovery(
            local_only_root,
            context.run_id,
            owner_path,
        )
        recovery_owner_sha256 = authority_digest(recovery_owner)
        replace_run_state(
            local_only_root,
            replace(
                state,
                recovery_owner_sha256=recovery_owner_sha256,
            ),
        )

        before_restore = _run_process_gate(context, label="before-recovery-restore")
        _raise_if_process_blocked(before_restore, failed_phase="before-recovery-restore")
        phase_log.append("before-recovery-restore")

        snapshot = _snapshot_from_recovery_state(context, state)
        restored_config_sha256 = _restore_config_for_recovery(snapshot, state)
        cache_restore_status = "not-needed-before-cache-mutation"
        if _recovery_phase_may_have_cache_mutation(state.phase):
            _restore_cache_snapshots(context, snapshot)
            cache_restore_status = "restored-from-snapshot"
        phase_log.append("snapshots-restored")

        inventory, transcript = collect_readonly_runtime_inventory(_refresh_paths(context))
        phase_log.append("inventory-complete")

        post_recovery = _run_process_gate(context, label="post-recovery")
        _raise_if_process_blocked(post_recovery, failed_phase="post-recovery")
        phase_log.append("post-recovery")

        _write_private_json(
            final_status_path,
            {
                "schema_version": "turbo-mode-refresh-recovery-status-v1",
                "run_id": context.run_id,
                "mode": "recover",
                "source_implementation_commit": context.source_implementation_commit,
                "source_implementation_tree": context.source_implementation_tree,
                "execution_head": context.execution_head,
                "execution_tree": context.execution_tree,
                "final_status": "RECOVERY_COMPLETE",
                "phase_log": tuple(phase_log),
                "preserved_original_owner_path": preserved_owner["preserved_owner_path"],
                "preserved_original_owner_sha256": preserved_owner["preserved_owner_sha256"],
                "recovery_owner_sha256": recovery_owner_sha256,
                "restored_config_sha256": restored_config_sha256,
                "cache_restore_status": cache_restore_status,
                "recovery_inventory_sha256": authority_digest(inventory),
                "recovery_transcript_sha256": authority_digest(transcript),
                "post_recovery_process_summary_sha256": authority_digest(post_recovery),
                "certification_status": "local-only-non-certified",
            },
        )
        clear_run_state(local_only_root, context.run_id)
        return RecoveryResult(
            final_status="RECOVERY_COMPLETE",
            final_status_path=str(final_status_path),
            phase_log=tuple(phase_log),
        )


def publish_guarded_refresh_commit_safe_summary(
    *,
    context: MutationContext,
    source_code_root: Path,
    execution_repo_root: Path,
    guarded_evidence: dict[str, Any],
    validator_runner: Callable[[str, PublicationReplayPaths], None] | None = None,
) -> PublicationReplayResult:
    normalized_source_root = source_code_root.expanduser().resolve(strict=True)
    normalized_execution_root = execution_repo_root.expanduser().resolve(strict=True)
    tool_path = Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py")
    dirty_state = ensure_relevant_worktree_clean(normalized_execution_root)
    _write_private_json(
        context.local_only_run_root / "guarded-refresh.summary.json",
        {
            "mode": "guarded-refresh",
            "run_id": context.run_id,
            "source_implementation_commit": context.source_implementation_commit,
            "source_implementation_tree": context.source_implementation_tree,
            "execution_head": context.execution_head,
            "execution_tree": context.execution_tree,
            "final_status": guarded_evidence.get("final_status"),
        },
    )
    publication_paths = PublicationReplayPaths(
        candidate=context.local_only_run_root / "commit-safe.candidate.summary.json",
        final=context.local_only_run_root / "commit-safe.final.summary.json",
        metadata=context.local_only_run_root / "metadata-validation.summary.json",
        redaction=context.local_only_run_root / "redaction.summary.json",
        redaction_final=context.local_only_run_root / "redaction-final-scan.summary.json",
        published=(
            normalized_execution_root
            / "plugins/turbo-mode/evidence/refresh"
            / f"{context.run_id}.summary.json"
        ),
        failed=(
            normalized_execution_root
            / "plugins/turbo-mode/evidence/refresh"
            / f"{context.run_id}.summary.failed.json"
        ),
    )

    return publish_and_replay_commit_safe_summary(
        operation="publish guarded refresh summary",
        paths=publication_paths,
        build_candidate_payload=lambda: build_guarded_refresh_commit_safe_summary(
            guarded_evidence,
            run_id=context.run_id,
            local_only_evidence_root=context.local_only_run_root,
            tool_path=tool_path,
            tool_sha256=_sha256_file(normalized_source_root / tool_path),
            dirty_state=dirty_state,
            metadata_validation_summary_sha256=None,
            redaction_validation_summary_sha256=None,
        ),
        build_final_payload=lambda metadata_sha, redaction_sha: (
            build_guarded_refresh_commit_safe_summary(
                guarded_evidence,
                run_id=context.run_id,
                local_only_evidence_root=context.local_only_run_root,
                tool_path=tool_path,
                tool_sha256=_sha256_file(normalized_source_root / tool_path),
                dirty_state=dirty_state,
                metadata_validation_summary_sha256=metadata_sha,
                redaction_validation_summary_sha256=redaction_sha,
            )
        ),
        validate_payload=assert_commit_safe_payload,
        run_candidate_validation=lambda paths: _run_guarded_refresh_publication_validation(
            phase="candidate",
            context=context,
            source_code_root=normalized_source_root,
            execution_repo_root=normalized_execution_root,
            paths=paths,
            validator_runner=validator_runner,
        ),
        run_final_validation=lambda paths: _run_guarded_refresh_publication_validation(
            phase="final",
            context=context,
            source_code_root=normalized_source_root,
            execution_repo_root=normalized_execution_root,
            paths=paths,
            validator_runner=validator_runner,
        ),
    )


def _build_live_guarded_refresh_commit_safe_evidence(
    *,
    context: MutationContext,
    launch_authority_sha256: str,
    launch_authority_proof_path: Path,
    install_records: tuple[dict[str, object], ...],
    snapshot: SnapshotSet,
    final_inventory: object,
    equality: dict[str, str],
    smoke_summary: dict[str, object],
    post_mutation: dict[str, object],
) -> dict[str, Any]:
    captured_rehearsal = _load_live_captured_rehearsal_proof(context)
    if len(install_records) != 1:
        fail(
            "build live guarded refresh evidence",
            "install authority record count mismatch",
            len(install_records),
        )
    install_record = install_records[0]
    pre_install_target_sha256 = install_record.get("pre_install_target_authority_sha256")
    if not isinstance(pre_install_target_sha256, str) or not pre_install_target_sha256:
        fail(
            "build live guarded refresh evidence",
            "missing pre-install target authority digest",
            pre_install_target_sha256,
        )
    smoke_summary_path = context.local_only_run_root / "standard-smoke.summary.json"
    if not smoke_summary_path.is_file():
        fail(
            "build live guarded refresh evidence",
            "smoke summary path missing",
            str(smoke_summary_path),
        )
    post_mutation_summary_path = context.local_only_run_root / "process-post-mutation.summary.json"
    if not post_mutation_summary_path.is_file():
        fail(
            "build live guarded refresh evidence",
            "post-mutation process summary path missing",
            str(post_mutation_summary_path),
        )
    post_refresh_config_path = context.codex_home / "config.toml"
    if not post_refresh_config_path.is_file():
        fail(
            "build live guarded refresh evidence",
            "post-refresh config path missing",
            str(post_refresh_config_path),
        )
    return {
        "mode": "guarded-refresh",
        "source_implementation_commit": context.source_implementation_commit,
        "source_implementation_tree": context.source_implementation_tree,
        "execution_head": context.execution_head,
        "execution_tree": context.execution_tree,
        "isolated_rehearsal_run_id": captured_rehearsal["rehearsal_run_id"],
        "rehearsal_proof_sha256": captured_rehearsal["rehearsal_proof_sha256"],
        "rehearsal_proof_validation_status": "validated-before-live-mutation",
        "rehearsal_proof_capture_manifest_sha256": captured_rehearsal[
            "capture_manifest_sha256"
        ],
        "source_to_rehearsal_execution_delta_status": captured_rehearsal[
            "source_to_rehearsal_execution_delta_status"
        ],
        "source_to_rehearsal_allowed_delta_proof_sha256": captured_rehearsal[
            "source_to_rehearsal_allowed_delta_proof_sha256"
        ],
        "source_to_rehearsal_changed_paths_sha256": captured_rehearsal[
            "source_to_rehearsal_changed_paths_sha256"
        ],
        "isolated_app_server_authority_proof_sha256": captured_rehearsal[
            "isolated_app_server_authority_proof_sha256"
        ],
        "no_real_home_authority_proof_sha256": captured_rehearsal[
            "no_real_home_authority_proof_sha256"
        ],
        "pre_snapshot_app_server_launch_authority_sha256": launch_authority_sha256,
        "pre_install_app_server_target_authority_sha256": pre_install_target_sha256,
        "live_app_server_authority_proof_sha256": _sha256_file(launch_authority_proof_path),
        "source_manifest_sha256": authority_digest(snapshot.source_manifest_sha256),
        "pre_refresh_cache_manifest_sha256": authority_digest(
            snapshot.pre_refresh_cache_manifest_sha256
        ),
        "post_refresh_cache_manifest_sha256": authority_digest(
            _post_refresh_cache_manifest_digests(context)
        ),
        "pre_refresh_config_sha256": snapshot.config_sha256,
        "post_refresh_config_sha256": _sha256_file(post_refresh_config_path),
        "post_refresh_inventory_sha256": authority_digest(final_inventory),
        "selected_smoke_tier": "standard",
        "smoke_summary_sha256": _sha256_file(smoke_summary_path),
        "post_mutation_process_census_sha256": _sha256_file(post_mutation_summary_path),
        "exclusivity_status": str(post_mutation.get("exclusivity_status")),
        "phase_reached": "evidence-published",
        "final_status": "MUTATION_COMPLETE_CERTIFIED",
        "rollback_or_restore_status": "not-attempted",
    }


def _load_live_captured_rehearsal_proof(context: MutationContext) -> dict[str, str]:
    manifest_path = context.local_only_run_root / "rehearsal-proof-capture/capture-manifest.json"
    manifest = _load_json_object(
        manifest_path,
        operation="load live captured rehearsal proof",
    )
    _require_field(
        manifest,
        "schema_version",
        REHEARSAL_CAPTURE_SCHEMA_VERSION,
        operation="load live captured rehearsal proof",
    )
    capture_root = Path(str(manifest.get("capture_root")))
    if capture_root != manifest_path.parent:
        fail(
            "load live captured rehearsal proof",
            "capture root mismatch",
            {"expected": str(manifest_path.parent), "actual": str(capture_root)},
        )
    source_artifact_root = Path(str(manifest.get("source_artifact_root")))
    source_proof_path = Path(str(manifest.get("rehearsal_proof_path")))
    try:
        relative_proof_path = source_proof_path.relative_to(source_artifact_root)
    except ValueError:
        fail(
            "load live captured rehearsal proof",
            "rehearsal proof path escaped source artifact root",
            str(source_proof_path),
        )
    captured_proof_path = capture_root / relative_proof_path
    if not captured_proof_path.is_file():
        fail(
            "load live captured rehearsal proof",
            "captured rehearsal proof path missing",
            str(captured_proof_path),
        )
    expected_proof_sha256 = manifest.get("rehearsal_proof_sha256")
    if not isinstance(expected_proof_sha256, str) or not expected_proof_sha256:
        fail(
            "load live captured rehearsal proof",
            "captured rehearsal proof digest missing",
            expected_proof_sha256,
        )
    actual_proof_sha256 = _sha256_file(captured_proof_path)
    if actual_proof_sha256 != expected_proof_sha256:
        fail(
            "load live captured rehearsal proof",
            "captured rehearsal proof digest mismatch",
            {"expected": expected_proof_sha256, "actual": actual_proof_sha256},
        )
    proof = _load_json_object(
        captured_proof_path,
        operation="load live captured rehearsal proof",
    )
    _require_field(
        proof,
        "schema_version",
        REHEARSAL_PROOF_SCHEMA_VERSION,
        operation="load live captured rehearsal proof",
    )
    _require_field(
        proof,
        "source_implementation_commit",
        context.source_implementation_commit,
        operation="load live captured rehearsal proof",
    )
    _require_field(
        proof,
        "source_implementation_tree",
        context.source_implementation_tree,
        operation="load live captured rehearsal proof",
    )
    rehearsal_run_id = proof.get("rehearsal_run_id")
    if not isinstance(rehearsal_run_id, str) or not rehearsal_run_id:
        fail(
            "load live captured rehearsal proof",
            "rehearsal run id missing",
            rehearsal_run_id,
        )
    fields = {
        "source_to_rehearsal_execution_delta_status": proof.get(
            "source_to_rehearsal_execution_delta_status"
        ),
        "source_to_rehearsal_allowed_delta_proof_sha256": proof.get(
            "source_to_rehearsal_allowed_delta_proof_sha256"
        ),
        "source_to_rehearsal_changed_paths_sha256": proof.get(
            "source_to_rehearsal_changed_paths_sha256"
        ),
        "isolated_app_server_authority_proof_sha256": proof.get(
            "app_server_authority_proof_sha256"
        ),
        "no_real_home_authority_proof_sha256": proof.get(
            "no_real_home_authority_proof_sha256"
        ),
    }
    invalid = [key for key, value in fields.items() if not isinstance(value, str) or not value]
    if invalid:
        fail(
            "load live captured rehearsal proof",
            "captured rehearsal proof field missing",
            invalid,
        )
    return {
        "rehearsal_run_id": rehearsal_run_id,
        "rehearsal_proof_sha256": expected_proof_sha256,
        "capture_manifest_sha256": _sha256_file(manifest_path),
        **{key: str(value) for key, value in fields.items()},
    }


def _post_refresh_cache_manifest_digests(context: MutationContext) -> dict[str, str]:
    return {
        spec.name: authority_digest(build_manifest(spec, root_kind="cache"))
        for spec in build_plugin_specs(repo_root=context.repo_root, codex_home=context.codex_home)
    }


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


def _validate_recovery_identity(context: MutationContext, state: RunState) -> None:
    if state.source_implementation_commit != context.source_implementation_commit:
        fail(
            "run guarded refresh recovery",
            "source implementation commit mismatch",
            {
                "expected": state.source_implementation_commit,
                "actual": context.source_implementation_commit,
            },
        )
    if state.source_implementation_tree != context.source_implementation_tree:
        fail(
            "run guarded refresh recovery",
            "source implementation tree mismatch",
            {
                "expected": state.source_implementation_tree,
                "actual": context.source_implementation_tree,
            },
        )
    if state.execution_head != context.execution_head:
        fail(
            "run guarded refresh recovery",
            "execution head mismatch",
            {"expected": state.execution_head, "actual": context.execution_head},
        )
    if state.execution_tree != context.execution_tree:
        fail(
            "run guarded refresh recovery",
            "execution tree mismatch",
            {"expected": state.execution_tree, "actual": context.execution_tree},
        )
    if state.tool_sha256 != context.tool_sha256:
        fail(
            "run guarded refresh recovery",
            "tool SHA256 mismatch",
            {"expected": state.tool_sha256, "actual": context.tool_sha256},
        )


def _snapshot_from_recovery_state(context: MutationContext, state: RunState) -> SnapshotSet:
    config_snapshot = state.snapshot_path_map.get("config")
    cache_snapshot = state.snapshot_path_map.get("cache")
    manifest = state.snapshot_path_map.get("manifest")
    if not config_snapshot or not cache_snapshot or not manifest:
        fail(
            "run guarded refresh recovery",
            "snapshot path map incomplete",
            state.snapshot_path_map,
        )
    snapshot = SnapshotSet(
        config_snapshot_path=Path(config_snapshot),
        config_sha256=str(state.original_config_sha256),
        cache_snapshot_root=Path(cache_snapshot),
        source_manifest_sha256={},
        pre_refresh_cache_manifest_sha256=state.pre_refresh_cache_manifest_sha256,
        config_path=context.codex_home / "config.toml",
        snapshot_manifest_path=Path(manifest),
    )
    _validate_snapshot_for_rollback(snapshot)
    actual_manifest_digest = _sha256_file(snapshot.snapshot_manifest_path)
    if actual_manifest_digest != state.snapshot_manifest_digest:
        fail(
            "run guarded refresh recovery",
            "snapshot manifest digest mismatch",
            {
                "expected": state.snapshot_manifest_digest,
                "actual": actual_manifest_digest,
            },
        )
    return snapshot


def _restore_config_for_recovery(snapshot: SnapshotSet, state: RunState) -> str:
    if _recovery_phase_requires_original_config(state.phase):
        current_sha256 = _sha256_file(snapshot.config_path)
        if current_sha256 != state.original_config_sha256:
            fail(
                "run guarded refresh recovery",
                "phase-appropriate expected config SHA256 mismatch",
                {
                    "phase": state.phase,
                    "expected": state.original_config_sha256,
                    "actual": current_sha256,
                },
            )
        return current_sha256
    expected = state.expected_intermediate_config_sha256
    if not expected:
        fail(
            "run guarded refresh recovery",
            "expected intermediate config SHA256 missing",
            state.phase,
        )
    current_sha256 = _sha256_file(snapshot.config_path)
    if current_sha256 != expected:
        fail(
            "run guarded refresh recovery",
            "phase-appropriate expected config SHA256 mismatch",
            {
                "phase": state.phase,
                "expected": expected,
                "actual": current_sha256,
            },
        )
    restore_config_snapshot(snapshot, current_expected_sha256=expected)
    return _sha256_file(snapshot.config_path)


def _recovery_phase_requires_original_config(phase: str) -> bool:
    return phase in {
        "marker-started",
        "before-snapshot-process-checked",
        "app-server-launch-authority-proven",
        "pre-refresh-inventory-proven",
        "snapshot-written",
        "config-restored-before-final-inventory",
        "inventory-complete",
        "equality-complete",
        "smoke-complete",
        "post-mutation-process-checked",
        "evidence-published",
        "exclusivity-unproven",
    }


def _recovery_phase_may_have_cache_mutation(phase: str) -> bool:
    return phase in {
        "install-complete",
        "config-restored-before-final-inventory",
        "inventory-complete",
        "equality-complete",
        "smoke-complete",
        "post-mutation-process-checked",
        "evidence-published",
        "exclusivity-unproven",
    }


def _restore_cache_snapshots(context: MutationContext, snapshot: SnapshotSet) -> None:
    for spec in build_plugin_specs(repo_root=context.repo_root, codex_home=context.codex_home):
        source = snapshot.cache_snapshot_root / spec.name / spec.version
        if not source.exists():
            fail("run guarded refresh recovery", "cache snapshot path missing", str(source))
        if spec.cache_root.exists():
            shutil.rmtree(spec.cache_root)
        shutil.copytree(source, spec.cache_root)


def install_plugins_via_app_server(
    context: MutationContext,
    *,
    restore_config_before_post_install: Callable[[], None] | None = None,
    pre_install_ticket_hook_policy: str = "required",
    same_child_ticket_hook_policy: str = "required",
) -> tuple[dict[str, object], ...]:
    if context.codex_home == REAL_CODEX_HOME:
        state = _read_existing_run_state(context)
        validate_cache_install_allowed(state)
    launch_authority = prove_app_server_home_authority(
        context,
        ticket_hook_policy=pre_install_ticket_hook_policy,
    )
    pre_install_authority = build_pre_install_target_authority(
        launch_authority=launch_authority,
        marketplace_path=context.repo_root / ".agents/plugins/marketplace.json",
        remote_marketplace_name=None,
        allow_real_codex_home=context.codex_home == REAL_CODEX_HOME,
    )
    pre_install_authority_path = context.local_only_run_root / (
        "pre-install-target-authority.proof.json"
    )
    _write_private_json(pre_install_authority_path, pre_install_authority)
    install_requests = build_install_requests(
        pre_install_authority=pre_install_authority,
        expected_requested_codex_home=context.codex_home,
        expected_launch_authority_sha256=authority_digest(launch_authority),
        expected_marketplace_path=context.repo_root / ".agents/plugins/marketplace.json",
    )
    paths = _refresh_paths(context)
    with tempfile.TemporaryDirectory(prefix="turbo-mode-refresh-install-") as tmpdir:
        scratch_cwd = Path(tmpdir)
        install_roundtrip_requests = [
            build_readonly_inventory_requests(paths, scratch_cwd=scratch_cwd)[0],
            {"method": "initialized"},
            *install_requests,
            *build_same_child_post_install_requests(paths, scratch_cwd=scratch_cwd),
        ]

        def after_install_response(
            request: dict[str, Any],
            response: dict[str, Any],
            _transcript: list[dict[str, Any]],
        ) -> None:
            if request.get("id") != 2 or response.get("id") != 2:
                return
            rewrite_ticket_hook_manifest(
                ticket_plugin_root=context.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"
            )
            if restore_config_before_post_install is not None:
                restore_config_before_post_install()

        install_transcript = tuple(
            app_server_roundtrip(
                requests=install_roundtrip_requests,
                env_overrides=launch_authority.child_environment_delta,
                cwd=Path(launch_authority.child_cwd),
                after_response=after_install_response,
            )
        )
    same_child_transcript = normalize_same_child_post_install_transcript(install_transcript)
    _, fresh_child_transcript = collect_readonly_runtime_inventory(paths)
    install_authority: AppServerInstallAuthority = validate_install_responses(
        transcript=install_transcript,
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
        install_requests=tuple(install_requests),
        same_child_post_install_transcript=same_child_transcript,
        fresh_child_post_install_transcript=fresh_child_transcript,
        same_child_ticket_hook_policy=same_child_ticket_hook_policy,
    )
    install_authority_path = context.local_only_run_root / "install-authority.proof.json"
    _write_private_json(install_authority_path, install_authority)
    return (
        {
            "kind": "install-authority",
            "pre_install_target_authority_path": str(pre_install_authority_path),
            "pre_install_target_authority_sha256": _sha256_file(pre_install_authority_path),
            "install_authority_path": str(install_authority_path),
            "install_authority_file_sha256": _sha256_file(install_authority_path),
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
        unexpected_diffs = [
            diff
            for diff in diffs
            if not _is_expected_ticket_hook_manifest_localization(context, spec, diff)
        ]
        if unexpected_diffs:
            fail(
                "verify source/cache equality",
                "source/cache manifest mismatch",
                [diff.canonical_path for diff in unexpected_diffs],
            )
        equality[spec.name] = authority_digest(source_manifest)
    return equality


def _is_expected_ticket_hook_manifest_localization(
    context: MutationContext,
    spec: PluginSpec,
    diff: DiffEntry,
) -> bool:
    if (
        spec.name != "ticket"
        or spec.version != "1.4.0"
        or diff.kind is not DiffKind.CHANGED
        or diff.canonical_path != TICKET_HOOK_MANIFEST_CANONICAL_PATH
        or diff.source is None
        or diff.cache is None
    ):
        return False
    if (
        diff.source.mode != diff.cache.mode
        or diff.source.executable != diff.cache.executable
        or diff.source.has_shebang != diff.cache.has_shebang
    ):
        return False

    source_path = spec.source_root / "hooks/hooks.json"
    cache_path = spec.cache_root / "hooks/hooks.json"
    try:
        source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        source_command = _ticket_hook_manifest_command(source_payload)
        cache_command = _ticket_hook_manifest_command(cache_payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        return False

    expected_source_command = (
        f"python3 {REAL_CODEX_HOME}/plugins/cache/turbo-mode/ticket/"
        f"{spec.version}/hooks/ticket_engine_guard.py"
    )
    expected_cache_command = f"python3 {spec.cache_root}/hooks/ticket_engine_guard.py"
    if source_command != expected_source_command or cache_command != expected_cache_command:
        return False

    normalized_source = deepcopy(source_payload)
    normalized_cache = deepcopy(cache_payload)
    _set_ticket_hook_manifest_command(normalized_source, TICKET_HOOK_COMMAND_SENTINEL)
    _set_ticket_hook_manifest_command(normalized_cache, TICKET_HOOK_COMMAND_SENTINEL)
    return normalized_source == normalized_cache


def _ticket_hook_manifest_command(payload: dict[str, Any]) -> str:
    command = payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    if not isinstance(command, str):
        raise TypeError("Ticket hook command is not a string")
    return command


def _set_ticket_hook_manifest_command(payload: dict[str, Any], command: str) -> None:
    payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = command


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


def _run_standard_smoke_for_context(context: MutationContext) -> dict[str, object]:
    with _allow_real_home_smoke_for_context(context):
        return run_standard_smoke(
            local_only_run_root=context.local_only_run_root,
            codex_home=context.codex_home,
            repo_root=context.repo_root,
        )


@contextmanager
def _allow_real_home_smoke_for_context(context: MutationContext):
    if context.codex_home != REAL_CODEX_HOME:
        yield
        return

    previous = os.environ.get("ALLOW_REAL_CODEX_HOME_SMOKE")
    os.environ["ALLOW_REAL_CODEX_HOME_SMOKE"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ALLOW_REAL_CODEX_HOME_SMOKE", None)
        else:
            os.environ["ALLOW_REAL_CODEX_HOME_SMOKE"] = previous


def _find_seed_manifest_for_rehearsal(
    context: MutationContext,
) -> tuple[Path, dict[str, Any]]:
    local_only_root = context.local_only_run_root.parent
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(local_only_root.glob("*/seed-manifest.json")):
        seed = _load_json_object(path, operation="find isolated seed manifest")
        if (
            seed.get("requested_codex_home") == str(context.codex_home)
            and seed.get("source_implementation_commit")
            == context.source_implementation_commit
            and seed.get("source_implementation_tree") == context.source_implementation_tree
            and seed.get("post_seed_terminal_status") == "guarded-refresh-required"
            and seed.get("no_real_home_paths") is True
        ):
            candidates.append((path, seed))
    if len(candidates) != 1:
        fail(
            "find isolated seed manifest",
            "expected exactly one matching seed manifest",
            [str(path) for path, _seed in candidates],
        )
    return candidates[0]


def _require_existing_artifact_path(
    raw_path: str | None,
    *,
    operation: str,
    reason: str,
) -> Path:
    if raw_path is None:
        fail(operation, reason, None)
    path = Path(raw_path)
    if not path.is_file():
        fail(operation, reason, str(path))
    return path


def _build_rehearsal_referenced_artifacts(
    artifact_root: Path,
    paths: tuple[Path, ...],
) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for path in paths:
        relative_path = _relative_to_artifact_root(path, artifact_root)
        artifacts.append({"relative_path": relative_path, "sha256": _sha256_file(path)})
    artifacts.sort(key=lambda item: item["relative_path"])
    return artifacts


def _relative_to_artifact_root(path: Path, artifact_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(
            artifact_root.resolve(strict=False)
        ).as_posix()
    except ValueError:
        fail(
            "resolve rehearsal artifact path",
            "artifact is outside rehearsal artifact root",
            {"artifact": str(path), "artifact_root": str(artifact_root)},
        )


def _copy_private_file(source_path: Path, destination_path: Path) -> None:
    if source_path.is_symlink() or not source_path.is_file():
        fail("capture rehearsal proof", "source artifact missing", str(source_path))
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(destination_path, flags, 0o600)
    with source_path.open("rb") as source, os.fdopen(fd, "wb") as destination:
        shutil.copyfileobj(source, destination)
        destination.flush()
        os.fsync(destination.fileno())
    os.chmod(destination_path, 0o600)
    _fsync_directory(destination_path.parent)


def _fsync_file_and_parent(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _validate_capture_manifest(manifest: dict[str, Any]) -> None:
    artifacts = manifest.get("captured_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        fail("capture rehearsal proof", "capture manifest has no artifacts", manifest)
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            fail("capture rehearsal proof", "capture manifest artifact invalid", artifact)
        captured_path = Path(str(artifact.get("captured_path")))
        if not captured_path.is_file():
            fail("capture rehearsal proof", "captured artifact missing", str(captured_path))
        if _sha256_file(captured_path) != artifact.get("sha256"):
            fail("capture rehearsal proof", "captured artifact SHA256 mismatch", artifact)
        if captured_path.stat().st_size != artifact.get("byte_size"):
            fail("capture rehearsal proof", "captured artifact byte size mismatch", artifact)


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
            if _contains_real_home_path(value):
                fail(
                    "prove app-server home authority",
                    "isolated authority resolved live Codex home path",
                    value,
                )


def _validate_sha256_companion(
    companion_path: Path,
    *,
    expected_path: Path,
    expected_sha256: str,
) -> None:
    if not companion_path.is_file():
        fail("validate rehearsal proof", "SHA256 companion is missing", str(companion_path))
    lines = companion_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("validate rehearsal proof", "SHA256 companion is empty", str(companion_path))
    first_line = lines[0]
    parts = first_line.split()
    if not parts or parts[0] != expected_sha256:
        fail(
            "validate rehearsal proof",
            "SHA256 companion digest mismatch",
            {"expected": expected_sha256, "actual": parts[0] if parts else None},
        )
    if len(parts) > 1 and Path(parts[1]).name != expected_path.name:
        fail(
            "validate rehearsal proof",
            "SHA256 companion path mismatch",
            {"expected": expected_path.name, "actual": parts[1]},
        )


def _load_json_object(path: Path, *, operation: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(operation, str(exc), str(path))
    if not isinstance(payload, dict):
        fail(operation, "JSON payload is not an object", type(payload).__name__)
    return payload


def _require_field(
    payload: dict[str, Any],
    key: str,
    expected: object,
    *,
    operation: str,
) -> None:
    actual = payload.get(key)
    if actual != expected:
        fail(
            operation,
            f"{key} mismatch",
            {"expected": expected, "actual": actual},
        )


def _validate_referenced_artifacts(
    proof: dict[str, Any],
    *,
    artifact_root: Path,
) -> tuple[dict[str, str], ...]:
    raw_artifacts = proof.get("referenced_artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        fail(
            "validate rehearsal proof",
            "referenced_artifacts must be a non-empty list",
            raw_artifacts,
        )
    artifacts: list[dict[str, str]] = []
    last_relative_path = ""
    observed_digests: set[str] = set()
    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            fail("validate rehearsal proof", "referenced artifact is not an object", raw)
        relative_path = raw.get("relative_path")
        expected_sha256 = raw.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            fail("validate rehearsal proof", "referenced artifact fields invalid", raw)
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts or relative_path == "":
            fail("validate rehearsal proof", "referenced artifact path invalid", relative_path)
        if relative_path <= last_relative_path:
            fail(
                "validate rehearsal proof",
                "referenced_artifacts must be sorted by relative_path",
                raw_artifacts,
            )
        path = _resolve_referenced_artifact_path(
            artifact_root,
            relative_path,
            operation="validate rehearsal proof",
        )
        actual_sha256 = _sha256_file(path)
        if actual_sha256 != expected_sha256:
            fail(
                "validate rehearsal proof",
                "referenced artifact SHA256 mismatch",
                {
                    "relative_path": relative_path,
                    "expected": expected_sha256,
                    "actual": actual_sha256,
                },
            )
        _reject_real_home_strings_in_json_artifact(path)
        artifacts.append({"relative_path": relative_path, "sha256": expected_sha256})
        observed_digests.add(expected_sha256)
        last_relative_path = relative_path
    missing_digest_fields = [
        field
        for field in REQUIRED_REHEARSAL_ARTIFACT_DIGEST_FIELDS
        if proof.get(field) not in observed_digests
    ]
    if missing_digest_fields:
        fail(
            "validate rehearsal proof",
            "rehearsal digest field is not backed by referenced_artifacts",
            missing_digest_fields,
        )
    return tuple(artifacts)


def _resolve_referenced_artifact_path(
    artifact_root: Path,
    relative_path: str,
    *,
    operation: str,
) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative_path == "":
        fail(operation, "referenced artifact path invalid", relative_path)
    root = artifact_root.expanduser().resolve(strict=True)
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            fail(operation, "referenced artifact path uses symlink", str(candidate))
    if not candidate.is_file():
        fail(operation, "referenced artifact is missing", str(candidate))
    resolved = candidate.resolve(strict=True)
    if not _is_under_path(resolved, root):
        fail(
            operation,
            "referenced artifact escapes artifact root",
            {"artifact": str(candidate), "artifact_root": str(root)},
        )
    return candidate


def _reject_real_home_strings_in_json_artifact(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    for value in _strings_in(payload):
        if _contains_real_home_path(value):
            fail(
                "validate rehearsal proof",
                "referenced artifact resolves real Codex home path",
                {"artifact": str(path), "value": value},
        )


def _validate_source_to_rehearsal_delta_proof(
    proof: dict[str, Any],
    artifacts: tuple[dict[str, str], ...],
    *,
    artifact_root: Path,
    source_implementation_commit: str,
    source_implementation_tree: str,
) -> None:
    _path, delta_proof = _load_digest_referenced_json(
        proof,
        artifacts,
        "source_to_rehearsal_allowed_delta_proof_sha256",
        artifact_root=artifact_root,
    )
    expected_fields = {
        "source_implementation_commit": source_implementation_commit,
        "source_implementation_tree": source_implementation_tree,
        "execution_head": proof["execution_head"],
        "execution_tree": proof["execution_tree"],
    }
    for key, expected in expected_fields.items():
        if delta_proof.get(key) != expected:
            fail(
                "validate rehearsal proof",
                f"source-to-rehearsal proof {key} mismatch",
                {"expected": expected, "actual": delta_proof.get(key)},
            )

    raw_changed_paths = delta_proof.get("changed_paths")
    if not isinstance(raw_changed_paths, list) or not all(
        isinstance(path, str) for path in raw_changed_paths
    ):
        fail(
            "validate rehearsal proof",
            "source-to-rehearsal proof changed_paths invalid",
            raw_changed_paths,
        )
    changed_paths = tuple(raw_changed_paths)
    invalid_paths = [
        path
        for path in changed_paths
        if path == "" or Path(path).is_absolute() or ".." in Path(path).parts
    ]
    if invalid_paths:
        fail(
            "validate rehearsal proof",
            "source-to-rehearsal proof changed_paths invalid",
            invalid_paths,
        )
    if len(set(changed_paths)) != len(changed_paths):
        fail(
            "validate rehearsal proof",
            "source-to-rehearsal proof changed_paths contain duplicates",
            list(changed_paths),
        )
    expected_changed_paths_sha256 = authority_digest(changed_paths)
    if proof["source_to_rehearsal_changed_paths_sha256"] != expected_changed_paths_sha256:
        fail(
            "validate rehearsal proof",
            "source-to-rehearsal changed paths SHA256 mismatch",
            {
                "expected": expected_changed_paths_sha256,
                "actual": proof["source_to_rehearsal_changed_paths_sha256"],
            },
        )

    raw_untracked = delta_proof.get("untracked_relevant_paths")
    if raw_untracked != []:
        fail(
            "validate rehearsal proof",
            "source-to-rehearsal proof has untracked relevant paths",
            raw_untracked,
        )

    delta_status = proof["source_to_rehearsal_execution_delta_status"]
    if delta_status == "identical":
        if changed_paths:
            fail(
                "validate rehearsal proof",
                "identical source-to-rehearsal proof has changed paths",
                list(changed_paths),
            )
        if delta_proof.get("allowed_delta_status") != "none":
            fail(
                "validate rehearsal proof",
                "source-to-rehearsal proof allowed_delta_status mismatch",
                {"expected": "none", "actual": delta_proof.get("allowed_delta_status")},
            )
        return

    if delta_proof.get("allowed_delta_status") != "docs-evidence-only":
        fail(
            "validate rehearsal proof",
            "source-to-rehearsal proof allowed_delta_status mismatch",
            {
                "expected": "docs-evidence-only",
                "actual": delta_proof.get("allowed_delta_status"),
            },
        )
    if not changed_paths:
        fail(
            "validate rehearsal proof",
            "approved source-to-rehearsal proof has no changed paths",
            changed_paths,
        )
    disallowed_paths = [
        path for path in changed_paths if not _is_allowed_delta_path(path)
    ]
    if disallowed_paths:
        fail(
            "validate rehearsal proof",
            "disallowed source-to-rehearsal proof paths",
            disallowed_paths,
        )


def _validate_seed_manifest(
    proof: dict[str, Any],
    *,
    artifact_root: Path,
    expected_requested_home: str,
) -> None:
    seed_path = _resolve_proof_artifact_path(
        artifact_root,
        str(proof["seed_manifest_path"]),
    )
    seed = _load_json_object(seed_path, operation="validate rehearsal proof")
    if _sha256_file(seed_path) != proof["seed_manifest_sha256"]:
        fail("validate rehearsal proof", "seed manifest SHA256 mismatch", str(seed_path))
    expected_fields = {
        "run_id": proof["seed_run_id"],
        "requested_codex_home": expected_requested_home,
        "canonical_drift_paths_sha256": proof["seed_expected_drift_paths_sha256"],
        "source_manifest_sha256": proof["seed_source_manifest_sha256"],
        "pre_refresh_isolated_cache_manifest_sha256": proof[
            "seed_pre_refresh_cache_manifest_sha256"
        ],
        "post_seed_dry_run_manifest_sha256": proof[
            "seed_post_seed_dry_run_manifest_sha256"
        ],
        "post_seed_terminal_status": "guarded-refresh-required",
        "no_real_home_paths": True,
    }
    for key, expected in expected_fields.items():
        if seed.get(key) != expected:
            fail(
                "validate rehearsal proof",
                f"seed manifest {key} mismatch",
                {"expected": expected, "actual": seed.get(key)},
            )
    if tuple(seed.get("canonical_drift_paths", ())) != PLAN05_DRIFT_PATHS:
        fail(
            "validate rehearsal proof",
            "seed manifest drift path set mismatch",
            seed.get("canonical_drift_paths"),
        )


def _resolve_proof_artifact_path(artifact_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        artifact_root_resolved = artifact_root.resolve(strict=True)
        try:
            relative_path = path.resolve(strict=True).relative_to(
                artifact_root_resolved
            ).as_posix()
        except ValueError:
            fail(
                "validate rehearsal proof",
                "proof artifact path is outside rehearsal artifact root",
                {"artifact": str(path), "artifact_root": str(artifact_root_resolved)},
            )
    else:
        relative_path = value
    return _resolve_referenced_artifact_path(
        artifact_root,
        relative_path,
        operation="validate rehearsal proof",
    )


def _load_digest_referenced_json(
    proof: dict[str, Any],
    artifacts: tuple[dict[str, str], ...],
    digest_field: str,
    *,
    artifact_root: Path,
) -> tuple[Path, dict[str, Any]]:
    digest = proof[digest_field]
    matches = [artifact for artifact in artifacts if artifact["sha256"] == digest]
    if not matches:
        fail(
            "validate rehearsal proof",
            "digest field has no referenced artifact",
            digest_field,
        )
    for artifact in matches:
        path = _resolve_referenced_artifact_path(
            artifact_root,
            artifact["relative_path"],
            operation="validate rehearsal proof",
        )
        payload = _load_json_object(path, operation="validate rehearsal proof")
        return path, payload
    fail(
        "validate rehearsal proof",
        "digest field has no JSON referenced artifact",
        digest_field,
    )


def _validate_digest_referenced_json(
    proof: dict[str, Any],
    artifacts: tuple[dict[str, str], ...],
    digest_field: str,
    *,
    artifact_root: Path,
    expected_fields: dict[str, object],
) -> None:
    _path, payload = _load_digest_referenced_json(
        proof,
        artifacts,
        digest_field,
        artifact_root=artifact_root,
    )
    if all(payload.get(key) == expected for key, expected in expected_fields.items()):
        return
    fail(
        "validate rehearsal proof",
        "referenced artifact content mismatch",
        {"digest_field": digest_field, "expected_fields": expected_fields},
    )


def _validate_no_real_home_authority_proof(
    proof: dict[str, Any],
    artifacts: tuple[dict[str, str], ...],
    *,
    artifact_root: Path,
    expected_requested_home: str,
) -> None:
    _path, payload = _load_digest_referenced_json(
        proof,
        artifacts,
        "no_real_home_authority_proof_sha256",
        artifact_root=artifact_root,
    )
    expected_fields = {
        "schema_version": NO_REAL_HOME_AUTHORITY_SCHEMA_VERSION,
        "requested_codex_home": expected_requested_home,
        "authority_result": "isolated-home-authority-proven",
        "no_real_home_paths": True,
        "app_server_authority_proof_sha256": proof["app_server_authority_proof_sha256"],
        "smoke_summary_sha256": proof["smoke_summary_sha256"],
    }
    for key, expected in expected_fields.items():
        if payload.get(key) != expected:
            fail(
                "validate rehearsal proof",
                f"no-real-home authority proof {key} mismatch",
                {"expected": expected, "actual": payload.get(key)},
            )

    requested_home = Path(expected_requested_home)
    if not requested_home.is_absolute():
        fail(
            "validate rehearsal proof",
            "requested Codex home is not absolute",
            expected_requested_home,
        )
    expected_paths = {
        "resolved_config_path": requested_home / "config.toml",
        "resolved_plugin_cache_root": requested_home / "plugins/cache/turbo-mode",
        "resolved_local_only_root": requested_home / "local-only/turbo-mode-refresh",
        "resolved_run_root": (
            requested_home
            / "local-only/turbo-mode-refresh"
            / str(proof["rehearsal_run_id"])
        ),
        "resolved_handoff_plugin_root": (
            requested_home / "plugins/cache/turbo-mode/handoff/1.6.0"
        ),
        "resolved_ticket_plugin_root": (
            requested_home / "plugins/cache/turbo-mode/ticket/1.4.0"
        ),
        "resolved_ticket_hook_manifest_path": (
            requested_home / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
        ),
    }
    for field, expected_path in expected_paths.items():
        actual = payload.get(field)
        if actual != str(expected_path):
            fail(
                "validate rehearsal proof",
                f"no-real-home authority proof {field} mismatch",
                {"expected": str(expected_path), "actual": actual},
            )
    path_values = [payload[field] for field in NO_REAL_HOME_AUTHORITY_PATH_FIELDS]
    for value in path_values:
        path = Path(str(value))
        if not _is_under_path(path, requested_home):
            fail(
                "validate rehearsal proof",
                "no-real-home authority proof path outside requested home",
                str(path),
            )
        if _is_under_path(path, REAL_CODEX_HOME):
            fail(
                "validate rehearsal proof",
                "no-real-home authority proof resolves real Codex home path",
                str(path),
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


def _contains_real_home_path(value: str) -> bool:
    real_home = str(REAL_CODEX_HOME)
    return value == real_home or f"{real_home}/" in value


def _read_existing_run_state(context: MutationContext) -> RunState:
    local_only_root = context.local_only_run_root.parent
    marker_path = local_only_root / "run-state" / f"{context.run_id}.marker.json"
    if not marker_path.exists():
        fail("install plugins via app-server", "snapshot marker is required", str(marker_path))
    return read_run_state(local_only_root, context.run_id)


def _replace_state(context: MutationContext, **changes: Any) -> None:
    local_only_root = context.local_only_run_root.parent
    state = read_run_state(local_only_root, context.run_id)
    replace_run_state(local_only_root, replace(state, **changes))


def _run_process_gate(context: MutationContext, *, label: str) -> dict[str, object]:
    return capture_process_gate(
        label=label,
        local_only_run_root=context.local_only_run_root,
        refresh_pid=os.getpid(),
        refresh_command=("python3", "refresh_installed_turbo_mode.py", "--guarded-refresh"),
        recorded_child_app_server_pids=frozenset(),
    )


def _run_guarded_refresh_publication_validation(
    *,
    phase: str,
    context: MutationContext,
    source_code_root: Path,
    execution_repo_root: Path,
    paths: PublicationReplayPaths,
    validator_runner: Callable[[str, PublicationReplayPaths], None] | None,
) -> None:
    if validator_runner is not None:
        validator_runner(phase, paths)
        return
    tool_root = source_code_root / "plugins/turbo-mode/tools"
    metadata_command = [
        sys.executable,
        str(tool_root / "refresh_validate_run_metadata.py"),
        "--mode",
        phase,
        "--run-id",
        context.run_id,
        "--source-code-root",
        str(source_code_root),
        "--execution-repo-root",
        str(execution_repo_root),
        "--local-only-root",
        str(context.local_only_run_root),
        "--summary",
        str(paths.candidate if phase == "candidate" else paths.published),
        "--published-summary-path",
        str(paths.published),
    ]
    redaction_command = [
        sys.executable,
        str(tool_root / "refresh_validate_redaction.py"),
        "--mode",
        phase,
        "--run-id",
        context.run_id,
        "--source-code-root",
        str(source_code_root),
        "--execution-repo-root",
        str(execution_repo_root),
        "--scope",
        "commit-safe-summary",
        "--source",
        "plan-06-cli",
        "--summary",
        str(paths.candidate if phase == "candidate" else paths.published),
        "--local-only-root",
        str(context.local_only_run_root),
        "--published-summary-path",
        str(paths.published),
    ]
    if phase == "candidate":
        _run_validator_command(
            [
                *metadata_command,
                "--summary-output",
                str(paths.metadata),
            ]
        )
        _run_validator_command(
            [
                *redaction_command,
                "--summary-output",
                str(paths.redaction),
                "--validate-own-summary",
            ]
        )
        return
    _run_validator_command(
        [
            *metadata_command,
            "--candidate-summary",
            str(paths.candidate),
            "--existing-validation-summary",
            str(paths.metadata),
        ]
    )
    _run_validator_command(
        [
            *redaction_command,
            "--candidate-summary",
            str(paths.candidate),
            "--existing-validation-summary",
            str(paths.redaction),
            "--final-scan-output",
            str(paths.redaction_final),
        ]
    )


def _run_validator_command(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise RefreshError(
            "publish guarded refresh summary failed: validator exited non-zero. "
            f"Got: {completed.stderr.strip() or completed.stdout.strip()!r:.100}"
        )


def _raise_if_process_blocked(summary: dict[str, object], *, failed_phase: str) -> None:
    blocked_count = summary.get("blocked_process_count")
    if isinstance(blocked_count, int) and blocked_count > 0:
        fail("run process gate", "process gate blocked", failed_phase)


def _write_seed_config(config_path: Path, *, repo_root: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
            "[features]\nplugin_hooks = true\n"
            '[plugins."handoff@turbo-mode"]\nenabled = true\n'
            '[plugins."ticket@turbo-mode"]\nenabled = true\n'
        )
    os.chmod(config_path, 0o600)


def _load_plan05_seed_records() -> dict[str, object]:
    try:
        data = json.loads(PLAN05_SEED_FIXTURE.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("load Plan 05 seed fixture", str(exc), str(PLAN05_SEED_FIXTURE))
    if not isinstance(data, dict):
        fail("load Plan 05 seed fixture", "top-level value is not an object", data)
    return data


def _is_under_path(path: Path, root: Path) -> bool:
    resolved_path = path.expanduser().resolve(strict=False)
    resolved_root = root.expanduser().resolve(strict=False)
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _reject_real_home_paths(paths: object) -> None:
    for raw_path in paths:
        path = Path(raw_path)
        if _is_under_path(path, REAL_CODEX_HOME):
            fail("validate isolated seed paths", "path resolves under real Codex home", str(path))


def _write_final_status(
    context: MutationContext,
    *,
    final_status: str,
    phase_log: list[str],
    final_status_path: Path,
    rehearsal_proof_path: Path | None,
    rehearsal_proof_sha256: str | None = None,
    demoted_summary_path: str | None = None,
    publication_failure_reason: str | None = None,
    failure_reason: str | None = None,
) -> GuardedRefreshResult:
    rehearsal_proof_sha256_path = (
        f"{rehearsal_proof_path}.sha256" if rehearsal_proof_path is not None else None
    )
    _write_private_json(
        final_status_path,
        {
            "schema_version": "turbo-mode-refresh-final-status-v1",
            "run_id": context.run_id,
            "mode": context.mode,
            "source_implementation_commit": context.source_implementation_commit,
            "source_implementation_tree": context.source_implementation_tree,
            "execution_head": context.execution_head,
            "execution_tree": context.execution_tree,
            "final_status": final_status,
            "phase_log": tuple(phase_log),
            "rehearsal_proof_path": str(rehearsal_proof_path)
            if rehearsal_proof_path is not None
            else None,
            "rehearsal_proof_sha256": rehearsal_proof_sha256,
            "rehearsal_proof_sha256_path": rehearsal_proof_sha256_path,
            "demoted_summary_path": demoted_summary_path,
            "publication_failure_reason": publication_failure_reason,
            "failure_reason": failure_reason,
        },
    )
    return GuardedRefreshResult(
        final_status=final_status,
        final_status_path=str(final_status_path),
        rehearsal_proof_path=str(rehearsal_proof_path)
        if rehearsal_proof_path is not None
        else None,
        rehearsal_proof_sha256=rehearsal_proof_sha256,
        rehearsal_proof_sha256_path=rehearsal_proof_sha256_path,
        demoted_summary_path=demoted_summary_path,
        publication_failure_reason=publication_failure_reason,
        phase_log=tuple(phase_log),
    )


def _git(repo_root: Path, *args: str, operation: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail(operation, completed.stderr.strip() or "git command failed", list(args))
    return completed.stdout.strip()


def _git_success(repo_root: Path, *args: str) -> bool:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _is_allowed_delta_path(path: str) -> bool:
    if path.startswith("docs/"):
        return True
    if path.startswith("plugins/turbo-mode/evidence/refresh/"):
        return True
    return False


def _untracked_relevant_paths(repo_root: Path) -> tuple[str, ...]:
    relevant_roots = (
        "plugins/turbo-mode/tools/",
        "plugins/turbo-mode/handoff/",
        "plugins/turbo-mode/ticket/",
        "plugins/turbo-mode/evidence/refresh/",
        ".agents/plugins/marketplace.json",
    )
    completed = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *relevant_roots,
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail(
            "check untracked relevant files",
            completed.stderr.strip() or "git status failed",
            list(relevant_roots),
        )
    untracked: list[str] = []
    for line in completed.stdout.splitlines():
        if line.startswith("?? "):
            untracked.append(line[3:].strip())
    return tuple(untracked)


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


def _write_sha256_companion(path: Path) -> str:
    digest = _sha256_file(path)
    companion = path.with_name(f"{path.name}.sha256")
    fd = os.open(companion, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path}\n")
    os.chmod(companion, 0o600)
    return digest


def _write_private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(serialize_authority_record(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)
