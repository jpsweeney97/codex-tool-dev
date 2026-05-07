from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
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
from .evidence import write_local_evidence
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
from .models import DiffEntry, DiffKind, PluginSpec, fail
from .planner import RefreshPaths, build_plugin_specs, plan_refresh
from .process_gate import capture_process_gate
from .smoke import run_standard_smoke

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
            smoke_summary = run_standard_smoke(
                local_only_run_root=context.local_only_run_root,
                codex_home=context.codex_home,
                repo_root=context.repo_root,
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

            final_status = (
                "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"
                if isolated_rehearsal
                else "MUTATION_COMPLETE_CERTIFIED"
            )
            if isolated_rehearsal:
                rehearsal_proof_path = context.local_only_run_root / "rehearsal-proof.json"
                _write_private_json(
                    rehearsal_proof_path,
                    {
                        "schema_version": "turbo-mode-refresh-rehearsal-proof-v1",
                        "run_id": context.run_id,
                        "source_implementation_commit": (context.source_implementation_commit),
                        "source_implementation_tree": context.source_implementation_tree,
                        "execution_head": context.execution_head,
                        "execution_tree": context.execution_tree,
                        "requested_codex_home": str(context.codex_home),
                        "no_real_home_proof": context.codex_home != REAL_CODEX_HOME,
                        "install_records_sha256": authority_digest(install_records),
                        "final_inventory_sha256": authority_digest(final_inventory),
                        "final_inventory_transcript_sha256": authority_digest(
                            final_inventory_transcript
                        ),
                        "source_cache_equality_sha256": authority_digest(equality),
                        "smoke_summary_sha256": authority_digest(smoke_summary),
                        "final_status": final_status,
                        "certification_status": "local-only-non-certified",
                    },
                )
            return _write_final_status(
                context,
                final_status=final_status,
                phase_log=phase_log,
                final_status_path=final_status_path,
                rehearsal_proof_path=rehearsal_proof_path,
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
) -> GuardedRefreshResult:
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
        },
    )
    return GuardedRefreshResult(
        final_status=final_status,
        final_status_path=str(final_status_path),
        rehearsal_proof_path=str(rehearsal_proof_path)
        if rehearsal_proof_path is not None
        else None,
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


def _write_private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(serialize_authority_record(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)
