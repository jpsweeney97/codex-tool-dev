#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.app_server_inventory import REAL_CODEX_HOME  # noqa: E402
from refresh.commit_safe import (  # noqa: E402
    build_commit_safe_summary,
    ensure_relevant_worktree_clean,
    sha256_file,
)
from refresh.evidence import evidence_payload, validate_run_id, write_local_evidence  # noqa: E402
from refresh.lock_state import ensure_no_active_run_state_markers  # noqa: E402
from refresh.models import RefreshError  # noqa: E402
from refresh.mutation import (  # noqa: E402
    MutationContext,
    capture_rehearsal_proof_bundle,
    run_guarded_refresh_orchestration,
    run_guarded_refresh_recovery,
    seed_isolated_rehearsal_home,
    validate_rehearsal_proof_bundle,
    verify_source_execution_identity,
)
from refresh.planner import plan_refresh  # noqa: E402
from refresh.retained_run import certify_retained_run  # noqa: E402
from refresh.validation import assert_commit_safe_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess Turbo Mode installed-cache drift without mutation."
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--plan-refresh", action="store_true")
    modes.add_argument("--refresh", action="store_true")
    modes.add_argument("--guarded-refresh", action="store_true")
    modes.add_argument("--recover", metavar="RUN_ID")
    modes.add_argument("--certify-retained-run", metavar="RUN_ID")
    modes.add_argument("--seed-isolated-rehearsal-home", action="store_true")
    modes.add_argument("--generate-guarded-refresh-approval", action="store_true")
    parser.add_argument("--smoke", choices=("light", "standard"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--run-id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--inventory-check", action="store_true")
    parser.add_argument("--record-summary", action="store_true")
    parser.add_argument("--no-record-summary", action="store_true")
    parser.add_argument("--require-terminal-status")
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--source-implementation-commit")
    parser.add_argument("--source-implementation-tree")
    parser.add_argument("--isolated-rehearsal", action="store_true")
    parser.add_argument("--rehearsal-proof", type=Path)
    parser.add_argument("--rehearsal-proof-sha256")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh:
        parser.error("--refresh is outside non-mutating refresh planning")
    if args.isolated_rehearsal and not args.guarded_refresh:
        parser.error("--isolated-rehearsal requires --guarded-refresh")
    if args.smoke is not None and not args.guarded_refresh:
        parser.error("--smoke is only accepted with mutation modes")
    if args.seed_isolated_rehearsal_home:
        return seed_isolated_rehearsal_home_main(args, parser)
    if args.generate_guarded_refresh_approval:
        return generate_guarded_refresh_approval_main(args, parser)
    if args.recover is not None:
        return recover_main(args, parser)
    if args.certify_retained_run is not None:
        return certify_retained_run_main(args, parser)
    if args.guarded_refresh:
        return guarded_refresh_main(args, parser)
    mode = "plan-refresh" if args.plan_refresh else "dry-run"
    run_id = args.run_id or uuid.uuid4().hex
    try:
        dirty_state = (
            ensure_relevant_worktree_clean(args.repo_root) if args.record_summary else None
        )
        result = plan_refresh(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            mode=mode,
            inventory_check=args.inventory_check,
        )
        if args.require_terminal_status is not None:
            terminal_status = result.terminal_status.value
            if terminal_status != args.require_terminal_status:
                raise RefreshError(
                    "required terminal status mismatch: "
                    f"expected {args.require_terminal_status!r}, got {terminal_status!r}"
                )
        evidence_path = write_local_evidence(result, run_id=run_id)
        published_summary_path = None
        candidate_summary_path = None
        final_summary_path = None
        if args.record_summary:
            if dirty_state is None:
                raise RefreshError(
                    "record refresh summary failed: dirty state invariant missing. "
                    "Got: None"
                )
            published_summary_path = resolve_commit_safe_summary_output(
                repo_root=args.repo_root,
                run_id=run_id,
                requested=args.summary_output,
            )
            run_root = result.paths.local_only_root / run_id
            candidate_summary_path = run_root / "commit-safe.candidate.summary.json"
            final_summary_path = run_root / "commit-safe.final.summary.json"
            metadata_summary_path = run_root / "metadata-validation.summary.json"
            redaction_summary_path = run_root / "redaction.summary.json"
            redaction_final_scan_path = run_root / "redaction-final-scan.summary.json"
            candidate_payload = build_commit_safe_summary(
                result,
                run_id=run_id,
                local_summary_path=evidence_path,
                repo_head=git_rev_parse(args.repo_root, "HEAD"),
                repo_tree=git_rev_parse(args.repo_root, "HEAD^{tree}"),
                tool_path=Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"),
                tool_sha256=sha256_file(CURRENT_FILE),
                dirty_state=dirty_state,
                metadata_validation_summary_sha256=None,
                redaction_validation_summary_sha256=None,
            )
            assert_commit_safe_payload(candidate_payload)
            write_json_0600_exclusive(candidate_summary_path, candidate_payload)
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_run_metadata.py"),
                    "--mode",
                    "candidate",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--local-only-root",
                    str(run_root),
                    "--summary",
                    str(candidate_summary_path),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--summary-output",
                    str(metadata_summary_path),
                ]
            )
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_redaction.py"),
                    "--mode",
                    "candidate",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--scope",
                    "commit-safe-summary",
                    "--source",
                    "plan-05-cli",
                    "--summary",
                    str(candidate_summary_path),
                    "--local-only-root",
                    str(run_root),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--summary-output",
                    str(redaction_summary_path),
                    "--validate-own-summary",
                ]
            )
            final_payload = build_commit_safe_summary(
                result,
                run_id=run_id,
                local_summary_path=evidence_path,
                repo_head=git_rev_parse(args.repo_root, "HEAD"),
                repo_tree=git_rev_parse(args.repo_root, "HEAD^{tree}"),
                tool_path=Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"),
                tool_sha256=sha256_file(CURRENT_FILE),
                dirty_state=dirty_state,
                metadata_validation_summary_sha256=sha256_file(metadata_summary_path),
                redaction_validation_summary_sha256=sha256_file(redaction_summary_path),
            )
            assert_commit_safe_payload(final_payload)
            write_json_0600_exclusive(final_summary_path, final_payload)
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_run_metadata.py"),
                    "--mode",
                    "final",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--local-only-root",
                    str(run_root),
                    "--summary",
                    str(final_summary_path),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--candidate-summary",
                    str(candidate_summary_path),
                    "--existing-validation-summary",
                    str(metadata_summary_path),
                ]
            )
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_redaction.py"),
                    "--mode",
                    "final",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--scope",
                    "commit-safe-summary",
                    "--source",
                    "plan-05-cli",
                    "--summary",
                    str(final_summary_path),
                    "--local-only-root",
                    str(run_root),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--candidate-summary",
                    str(candidate_summary_path),
                    "--existing-validation-summary",
                    str(redaction_summary_path),
                    "--final-scan-output",
                    str(redaction_final_scan_path),
                ]
            )
            publish_json_0600_exclusive(final_summary_path, published_summary_path)
    except (RefreshError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = evidence_payload(result, run_id=run_id)
    payload["evidence_path"] = str(evidence_path)
    if candidate_summary_path is not None:
        payload["commit_safe_candidate_summary_path"] = str(candidate_summary_path)
    if final_summary_path is not None:
        payload["commit_safe_final_summary_path"] = str(final_summary_path)
    if published_summary_path is not None:
        payload["published_summary_path"] = str(published_summary_path)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode: {mode}")
        print(f"terminal_plan_status: {result.terminal_status.value}")
        print(f"evidence_path: {evidence_path}")
        if candidate_summary_path is not None:
            print(f"commit_safe_candidate_summary_path: {candidate_summary_path}")
        if final_summary_path is not None:
            print(f"commit_safe_final_summary_path: {final_summary_path}")
        if published_summary_path is not None:
            print(f"published_summary_path: {published_summary_path}")
        print(f"app_server_inventory_status: {result.app_server_inventory_status}")
        if result.app_server_inventory_failure_reason is not None:
            print(
                "app_server_inventory_failure_reason: "
                f"{result.app_server_inventory_failure_reason}"
            )
        if result.app_server_inventory is not None:
            print(f"app_server_inventory: {result.app_server_inventory.state}")
        print(f"mutation_command_available: {str(result.mutation_command_available).lower()}")
        if result.future_external_command is not None:
            print(f"future_external_command: {result.future_external_command}")
            print(f"requires_plan: {result.requires_plan}")
    return 0


def seed_isolated_rehearsal_home_main(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    codex_home = args.codex_home.expanduser().resolve(strict=False)
    real_codex_home = REAL_CODEX_HOME
    if codex_home == real_codex_home or real_codex_home in codex_home.parents:
        parser.error(
            "--seed-isolated-rehearsal-home requires "
            f"--codex-home outside {real_codex_home}"
        )
    if args.inventory_check:
        parser.error("--inventory-check is not accepted with --seed-isolated-rehearsal-home")
    if args.record_summary or args.no_record_summary:
        parser.error("--record-summary is not accepted with --seed-isolated-rehearsal-home")
    if args.require_terminal_status is not None:
        parser.error(
            "--require-terminal-status is not accepted with --seed-isolated-rehearsal-home"
        )
    if args.summary_output is not None:
        parser.error("--summary-output is not accepted with --seed-isolated-rehearsal-home")
    if args.source_implementation_commit is None:
        parser.error(
            "--source-implementation-commit is required for --seed-isolated-rehearsal-home"
        )
    if args.source_implementation_tree is None:
        parser.error("--source-implementation-tree is required for --seed-isolated-rehearsal-home")

    try:
        run_id = validate_run_id(args.run_id or uuid.uuid4().hex)
        seed = seed_isolated_rehearsal_home(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            run_id=run_id,
            source_implementation_commit=args.source_implementation_commit,
            source_implementation_tree=args.source_implementation_tree,
        )
    except (RefreshError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "run_id": run_id,
        "mode": "seed-isolated-rehearsal-home",
        "terminal_plan_status": seed.terminal_plan_status,
        "seed_manifest_path": seed.seed_manifest_path,
        "post_seed_dry_run_id": seed.post_seed_dry_run_id,
        "post_seed_dry_run_path": seed.post_seed_dry_run_path,
        "canonical_drift_paths": seed.canonical_drift_paths,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"seed_manifest_path: {seed.seed_manifest_path}")
        print(f"post_seed_dry_run_path: {seed.post_seed_dry_run_path}")
        print(f"terminal_plan_status: {seed.terminal_plan_status}")
    return 0


def generate_guarded_refresh_approval_main(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    if args.inventory_check:
        parser.error("--inventory-check is not accepted with approval generation")
    if args.record_summary or args.no_record_summary:
        parser.error("--record-summary is not accepted with approval generation")
    if args.require_terminal_status is not None:
        parser.error("--require-terminal-status is not accepted with approval generation")
    if args.summary_output is not None:
        parser.error("--summary-output is not accepted with approval generation")
    if args.isolated_rehearsal:
        parser.error("--isolated-rehearsal is not accepted with approval generation")
    if args.smoke is not None:
        parser.error("--smoke is not accepted with approval generation")
    if args.run_id is None:
        parser.error("--run-id is required for approval generation")
    if args.source_implementation_commit is None:
        parser.error(
            "--source-implementation-commit is required for approval generation"
        )
    if args.source_implementation_tree is None:
        parser.error("--source-implementation-tree is required for approval generation")
    if args.rehearsal_proof is None:
        parser.error("--rehearsal-proof is required for approval generation")
    if args.rehearsal_proof_sha256 is None:
        parser.error("--rehearsal-proof-sha256 is required for approval generation")

    try:
        result = generate_guarded_refresh_approval_candidate(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            run_id=args.run_id,
            source_implementation_commit=args.source_implementation_commit,
            source_implementation_tree=args.source_implementation_tree,
            rehearsal_proof=args.rehearsal_proof,
            rehearsal_proof_sha256=args.rehearsal_proof_sha256,
        )
    except (RefreshError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"approval_status: {result['approval_status']}")
        print(f"operator_approval_packet_path: {result['operator_approval_packet_path']}")
        print(f"approval_json_path: {result['approval_json_path']}")
        print(f"runbook_path: {result['runbook_path']}")
    return 0


def generate_guarded_refresh_approval_candidate(
    *,
    repo_root: Path,
    codex_home: Path,
    run_id: str,
    source_implementation_commit: str,
    source_implementation_tree: str,
    rehearsal_proof: Path,
    rehearsal_proof_sha256: str,
) -> dict[str, object]:
    normalized_repo_root = repo_root.expanduser().resolve(strict=True)
    normalized_codex_home = codex_home.expanduser().resolve(strict=False)
    run_id = validate_run_id(run_id)
    if not run_id.startswith("plan06-live-guarded-refresh-"):
        raise ValueError(
            "validate run id failed: run id must be Plan 06 live. "
            f"Got: {run_id!r:.100}"
        )

    proof_path = rehearsal_proof.expanduser().resolve(strict=True)
    validate_rehearsal_proof_bundle(
        proof_path=proof_path,
        expected_sha256=rehearsal_proof_sha256,
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
        tool_sha256=sha256_file(CURRENT_FILE),
        approved_codex_home=normalized_codex_home,
    )

    local_only_root = normalized_codex_home / "local-only/turbo-mode-refresh"
    approval_dir = local_only_root / "approvals" / run_id
    expected_local_only_run_root = local_only_root / run_id
    expected_marker_path = local_only_root / "run-state" / f"{run_id}.marker.json"
    evidence_root = normalized_repo_root / "plugins/turbo-mode/evidence/refresh"
    expected_summary_path = evidence_root / f"{run_id}.summary.json"
    expected_failed_summary_path = evidence_root / f"{run_id}.summary.failed.json"
    for path in (
        expected_local_only_run_root,
        expected_marker_path,
        expected_summary_path,
        expected_failed_summary_path,
    ):
        if path.exists():
            raise FileExistsError(
                "generate approval candidate failed: approved run id already has evidence path. "
                f"Got: {str(path)!r:.100}"
            )

    source_execution_proof = verify_source_execution_identity(
        repo_root=normalized_repo_root,
        local_only_run_root=approval_dir,
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
    )

    approval_json_path = approval_dir / "guarded-refresh-approval.json"
    runbook_path = approval_dir / "guarded-refresh-runbook.sh"
    changed_paths_path = approval_dir / "approved-source-to-execution-changed-paths.txt"
    digests_path = approval_dir / "guarded-refresh-approved-digests.json"
    packet_path = approval_dir / "operator-approval-packet.md"

    _write_text_0600_exclusive(
        changed_paths_path,
        "".join(f"{path}\n" for path in source_execution_proof.changed_paths),
    )

    python_bin = sys.executable
    python_version = platform.python_version()
    rehearsal_companion = proof_path.with_name(f"{proof_path.name}.sha256")
    rehearsal_companion_sha256 = (
        sha256_file(rehearsal_companion) if rehearsal_companion.is_file() else None
    )
    source_execution_identity_match = (
        source_execution_proof.execution_head == source_implementation_commit
        and source_execution_proof.execution_tree == source_implementation_tree
        and not source_execution_proof.changed_paths
    )
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    changed_paths_sha256 = sha256_file(changed_paths_path)

    runbook = _build_guarded_refresh_runbook(
        approval_json_path=approval_json_path,
        digests_path=digests_path,
        run_id=run_id,
        repo_root=normalized_repo_root,
        expected_local_only_run_root=expected_local_only_run_root,
        expected_marker_path=expected_marker_path,
        expected_summary_path=expected_summary_path,
        expected_failed_summary_path=expected_failed_summary_path,
        codex_home=normalized_codex_home,
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
        execution_head=source_execution_proof.execution_head,
        execution_tree=source_execution_proof.execution_tree,
        changed_paths_path=changed_paths_path,
        python_bin=python_bin,
        python_version=python_version,
        rehearsal_proof=proof_path,
        rehearsal_proof_sha256=rehearsal_proof_sha256,
    )
    _write_text_executable_exclusive(runbook_path, runbook)
    runbook_sha256 = sha256_file(runbook_path)

    approval_payload: dict[str, object] = {
        "schema_version": "turbo-mode-plan06-guarded-refresh-approval-candidate-v1",
        "approval_status": "blocked-before-operator-approval",
        "blocked_reason": (
            "Operator approval has not been granted for the external maintenance window."
        ),
        "project": normalized_repo_root.name,
        "branch": git_rev_parse(normalized_repo_root, "--abbrev-ref", "HEAD"),
        "generated_at": generated_at,
        "run_id": run_id,
        "execution_root": str(normalized_repo_root),
        "codex_home": str(normalized_codex_home),
        "approval_json_path": str(approval_json_path),
        "approved_digests_path": str(digests_path),
        "runbook_path": str(runbook_path),
        "runbook_sha256": runbook_sha256,
        "approved_changed_paths": list(source_execution_proof.changed_paths),
        "approved_changed_paths_file": str(changed_paths_path),
        "approved_changed_paths_file_sha256": changed_paths_sha256,
        "source_implementation_commit": source_implementation_commit,
        "source_implementation_tree": source_implementation_tree,
        "execution_head": source_execution_proof.execution_head,
        "execution_tree": source_execution_proof.execution_tree,
        "source_execution_identity_match": source_execution_identity_match,
        "source_execution_identity_proof_path": source_execution_proof.proof_path,
        "source_execution_identity_proof_sha256": sha256_file(
            Path(source_execution_proof.proof_path)
        ),
        "python_bin": python_bin,
        "python_version": python_version,
        "rehearsal_proof_path": str(proof_path),
        "rehearsal_proof_sha256": rehearsal_proof_sha256,
        "expected_local_only_run_root": str(expected_local_only_run_root),
        "expected_marker_path": str(expected_marker_path),
        "expected_recovery_handle": run_id,
        "expected_summary_path": str(expected_summary_path),
        "expected_failed_summary_path": str(expected_failed_summary_path),
        "operator_requirements": {
            "external_shell_only": True,
            "close_active_codex_desktop": True,
            "close_active_codex_cli_sessions": True,
            "do_not_reopen_until_external_command_exits": True,
            "mutates_installed_cache": (
                f"{normalized_codex_home / 'plugins/cache/turbo-mode'}/"
            ),
            "may_temporarily_edit_config": str(
                normalized_codex_home / "config.toml"
            ),
        },
        "rollback_and_recovery_behavior": {
            "rollback_complete_status": "MUTATION_FAILED_ROLLBACK_COMPLETE",
            "rollback_failed_status": "MUTATION_FAILED_ROLLBACK_FAILED",
            "manual_recovery_status": "RECOVERY_FAILED_MANUAL_DECISION_REQUIRED",
        },
    }
    if rehearsal_companion.is_file():
        approval_payload["rehearsal_proof_companion_path"] = str(rehearsal_companion)
        approval_payload["rehearsal_proof_companion_sha256"] = rehearsal_companion_sha256
    write_json_0600_exclusive(approval_json_path, approval_payload)
    approval_json_sha256 = sha256_file(approval_json_path)

    digests_payload: dict[str, object] = {
        "schema_version": "turbo-mode-plan06-guarded-refresh-approved-digests-v1",
        "approval_status": "blocked-before-operator-approval",
        "run_id": run_id,
        "approval_json_path": str(approval_json_path),
        "approval_json_sha256": approval_json_sha256,
        "runbook_path": str(runbook_path),
        "runbook_sha256": runbook_sha256,
        "approved_changed_paths_file": str(changed_paths_path),
        "approved_changed_paths_file_sha256": changed_paths_sha256,
        "rehearsal_proof_path": str(proof_path),
        "rehearsal_proof_sha256": rehearsal_proof_sha256,
    }
    write_json_0600_exclusive(digests_path, digests_payload)
    digests_sha256 = sha256_file(digests_path)

    packet = _build_operator_approval_packet(
        run_id=run_id,
        approval_json_path=approval_json_path,
        approval_json_sha256=approval_json_sha256,
        runbook_path=runbook_path,
        runbook_sha256=runbook_sha256,
        digests_path=digests_path,
        digests_sha256=digests_sha256,
        changed_paths_path=changed_paths_path,
        changed_paths_sha256=changed_paths_sha256,
        branch=str(approval_payload["branch"]),
        source_implementation_commit=source_implementation_commit,
        source_implementation_tree=source_implementation_tree,
        execution_head=source_execution_proof.execution_head,
        execution_tree=source_execution_proof.execution_tree,
        changed_paths=source_execution_proof.changed_paths,
        python_bin=python_bin,
        python_version=python_version,
        rehearsal_proof=proof_path,
        rehearsal_proof_sha256=rehearsal_proof_sha256,
        codex_home=normalized_codex_home,
        expected_local_only_run_root=expected_local_only_run_root,
        expected_marker_path=expected_marker_path,
        expected_summary_path=expected_summary_path,
        expected_failed_summary_path=expected_failed_summary_path,
    )
    _write_text_0600_exclusive(packet_path, packet)

    return {
        "approval_status": "blocked-before-operator-approval",
        "run_id": run_id,
        "approval_dir": str(approval_dir),
        "operator_approval_packet_path": str(packet_path),
        "approval_json_path": str(approval_json_path),
        "approval_json_sha256": approval_json_sha256,
        "runbook_path": str(runbook_path),
        "runbook_sha256": runbook_sha256,
        "approved_digests_path": str(digests_path),
        "approved_digests_sha256": digests_sha256,
        "approved_changed_paths_file": str(changed_paths_path),
        "approved_changed_paths_file_sha256": changed_paths_sha256,
        "source_implementation_commit": source_implementation_commit,
        "source_implementation_tree": source_implementation_tree,
        "execution_head": source_execution_proof.execution_head,
        "execution_tree": source_execution_proof.execution_tree,
    }


def guarded_refresh_main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    codex_home = args.codex_home.expanduser().resolve(strict=False)
    real_codex_home = REAL_CODEX_HOME
    live_target = not args.isolated_rehearsal
    if args.no_record_summary and live_target:
        parser.error("--no-record-summary is not allowed for real guarded refresh")
    if args.isolated_rehearsal and codex_home == real_codex_home:
        parser.error(
            f"--isolated-rehearsal requires --codex-home outside {real_codex_home}"
        )
    if live_target:
        if args.rehearsal_proof is None:
            parser.error("--rehearsal-proof is required for real guarded refresh")
        if args.rehearsal_proof_sha256 is None:
            parser.error("--rehearsal-proof-sha256 is required for real guarded refresh")
        if not args.record_summary:
            parser.error("--record-summary is required for real guarded refresh")
        if args.run_id is None:
            parser.error("--run-id is required for real guarded refresh")
    if args.source_implementation_commit is None:
        parser.error("--source-implementation-commit is required for --guarded-refresh")
    if args.source_implementation_tree is None:
        parser.error("--source-implementation-tree is required for --guarded-refresh")
    run_id = args.run_id or uuid.uuid4().hex
    rehearsal_capture = None
    try:
        run_id = validate_run_id(run_id)
        if live_target:
            if args.rehearsal_proof is None:
                raise RefreshError(
                    "run guarded refresh failed: rehearsal proof is required. Got: None"
                )
            if args.rehearsal_proof_sha256 is None:
                raise RefreshError(
                    "run guarded refresh failed: rehearsal proof SHA256 is required. "
                    "Got: None"
                )
            validated_rehearsal_proof = validate_rehearsal_proof_bundle(
                proof_path=args.rehearsal_proof,
                expected_sha256=args.rehearsal_proof_sha256,
                source_implementation_commit=args.source_implementation_commit,
                source_implementation_tree=args.source_implementation_tree,
                tool_sha256=sha256_file(CURRENT_FILE),
                approved_codex_home=codex_home,
            )
            rehearsal_capture = capture_rehearsal_proof_bundle(
                validated_rehearsal_proof,
                live_run_root=codex_home / "local-only/turbo-mode-refresh" / run_id,
            )
        ensure_no_active_run_state_markers(codex_home / "local-only/turbo-mode-refresh")
    except (RefreshError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if rehearsal_capture is not None:
        print(
            "rehearsal proof capture complete: "
            f"{rehearsal_capture.capture_manifest_path}",
            file=sys.stderr,
        )

    try:
        result = plan_refresh(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            mode="plan-refresh",
            inventory_check=True,
        )
        if result.terminal_status.value != "guarded-refresh-required":
            raise RefreshError(
                "guarded refresh preflight failed: terminal plan status is not "
                f"'guarded-refresh-required'. Got: {result.terminal_status.value!r}"
            )
        proof = verify_source_execution_identity(
            repo_root=args.repo_root,
            local_only_run_root=result.paths.local_only_root / run_id,
            source_implementation_commit=args.source_implementation_commit,
            source_implementation_tree=args.source_implementation_tree,
        )
        if result.runtime_config is None:
            raise RefreshError("guarded refresh preflight failed: runtime config unavailable")
        source_execution_identity_proof_sha256 = sha256_file(Path(proof.proof_path))
        source_to_rehearsal_delta_status = (
            "identical"
            if proof.execution_head == args.source_implementation_commit
            and proof.execution_tree == args.source_implementation_tree
            and not proof.changed_paths
            else "approved-docs-evidence-only"
        )
        orchestration = run_guarded_refresh_orchestration(
            MutationContext(
                run_id=run_id,
                mode="guarded-refresh",
                repo_root=result.paths.repo_root,
                codex_home=result.paths.codex_home,
                local_only_run_root=result.paths.local_only_root / run_id,
                source_implementation_commit=args.source_implementation_commit,
                source_implementation_tree=args.source_implementation_tree,
                execution_head=proof.execution_head,
                execution_tree=proof.execution_tree,
                tool_sha256=sha256_file(CURRENT_FILE),
                source_execution_identity_proof_path=proof.proof_path,
                source_execution_identity_proof_sha256=source_execution_identity_proof_sha256,
                source_to_rehearsal_execution_delta_status=(
                    source_to_rehearsal_delta_status
                ),
                source_to_rehearsal_changed_paths_sha256=sha256_json(proof.changed_paths),
                source_to_rehearsal_allowed_delta_proof_sha256=(
                    source_execution_identity_proof_sha256
                ),
                live_target=live_target,
            ),
            terminal_plan_status=result.terminal_status.value,
            plugin_hooks_state=result.runtime_config.plugin_hooks_state,
            isolated_rehearsal=args.isolated_rehearsal,
        )
        payload = {
            "run_id": run_id,
            "mode": "guarded-refresh",
            "terminal_plan_status": result.terminal_status.value,
            "source_execution_identity_proof": proof.proof_path,
            "final_status": orchestration.final_status,
            "final_status_path": orchestration.final_status_path,
            "rehearsal_proof_path": orchestration.rehearsal_proof_path,
            "rehearsal_proof_sha256": orchestration.rehearsal_proof_sha256,
            "rehearsal_proof_sha256_path": orchestration.rehearsal_proof_sha256_path,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"guarded-refresh final_status: {orchestration.final_status}")
            print(f"final_status_path: {orchestration.final_status_path}")
            if orchestration.rehearsal_proof_path is not None:
                print(f"rehearsal_proof_path: {orchestration.rehearsal_proof_path}")
        if orchestration.final_status == "MUTATION_COMPLETE_CERTIFIED":
            return 0
        if (
            args.isolated_rehearsal
            and orchestration.final_status == "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"
        ):
            return 0
        return 1
    except (RefreshError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def recover_main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.source_implementation_commit is None:
        parser.error("--source-implementation-commit is required for --recover")
    if args.source_implementation_tree is None:
        parser.error("--source-implementation-tree is required for --recover")
    if args.inventory_check:
        parser.error("--inventory-check is not accepted with --recover")
    if args.record_summary or args.no_record_summary:
        parser.error("--record-summary is not accepted with --recover")
    if args.require_terminal_status is not None:
        parser.error("--require-terminal-status is not accepted with --recover")
    if args.summary_output is not None:
        parser.error("--summary-output is not accepted with --recover")
    if args.isolated_rehearsal:
        parser.error("--isolated-rehearsal is not accepted with --recover")
    if args.rehearsal_proof is not None or args.rehearsal_proof_sha256 is not None:
        parser.error("--rehearsal-proof is not accepted with --recover")

    try:
        run_id = validate_run_id(str(args.recover))
        repo_root = args.repo_root.expanduser().resolve(strict=True)
        codex_home = args.codex_home.expanduser().resolve(strict=False)
        result = run_guarded_refresh_recovery(
            MutationContext(
                run_id=run_id,
                mode="recover",
                repo_root=repo_root,
                codex_home=codex_home,
                local_only_run_root=(
                    codex_home / "local-only/turbo-mode-refresh" / run_id
                ),
                source_implementation_commit=args.source_implementation_commit,
                source_implementation_tree=args.source_implementation_tree,
                execution_head=git_rev_parse(repo_root, "HEAD"),
                execution_tree=git_rev_parse(repo_root, "HEAD^{tree}"),
                tool_sha256=sha256_file(CURRENT_FILE),
            ),
        )
    except (RefreshError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "run_id": run_id,
        "mode": "recover",
        "final_status": result.final_status,
        "final_status_path": result.final_status_path,
        "phase_log": result.phase_log,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"recovery final_status: {result.final_status}")
        print(f"final_status_path: {result.final_status_path}")
    return 0 if result.final_status == "RECOVERY_COMPLETE" else 1


def certify_retained_run_main(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    if args.inventory_check:
        parser.error("--inventory-check is not accepted with --certify-retained-run")
    if args.record_summary or args.no_record_summary:
        parser.error("--record-summary is not accepted with --certify-retained-run")
    if args.require_terminal_status is not None:
        parser.error("--require-terminal-status is not accepted with --certify-retained-run")
    if args.summary_output is not None:
        parser.error("--summary-output is not accepted with --certify-retained-run")
    if args.isolated_rehearsal:
        parser.error("--isolated-rehearsal is not accepted with --certify-retained-run")
    if args.rehearsal_proof is not None or args.rehearsal_proof_sha256 is not None:
        parser.error("--rehearsal-proof is not accepted with --certify-retained-run")
    if args.source_implementation_commit is not None or args.source_implementation_tree is not None:
        parser.error(
            "--source-implementation-commit is not accepted with --certify-retained-run"
        )

    try:
        run_id = validate_run_id(str(args.certify_retained_run))
        result = certify_retained_run(
            run_id=run_id,
            repo_root=args.repo_root,
            codex_home=args.codex_home,
        )
    except (RefreshError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "run_id": run_id,
        "mode": "certify-retained-run",
        "outcome": result.outcome,
        "final_status": result.final_status,
        "published_summary_path": result.published_summary_path,
        "retained_certification_status_path": result.status_path,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"retained certification outcome: {result.outcome}")
        print(f"final_status: {result.final_status}")
        print(f"published_summary_path: {result.published_summary_path}")
        print(f"retained_certification_status_path: {result.status_path}")
    return 0 if result.outcome == "retained-certified" else 1


def git_rev_parse(repo_root: Path, *revision: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", *revision],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def sha256_json(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_commit_safe_summary_output(
    *,
    repo_root: Path,
    run_id: str,
    requested: Path | None,
) -> Path:
    evidence_root = (repo_root / "plugins/turbo-mode/evidence/refresh").resolve(strict=False)
    requested_path = requested or evidence_root / f"{run_id}.summary.json"
    if not requested_path.is_absolute():
        requested_path = repo_root / requested_path
    final_path = requested_path.resolve(strict=False)
    if evidence_root != final_path.parent and evidence_root not in final_path.parents:
        raise ValueError(
            "resolve summary output failed: path must stay under evidence root. "
            f"Got: {str(requested_path)!r:.100}"
        )
    if final_path.name.endswith(".summary.json") is False:
        raise ValueError(
            "resolve summary output failed: file name must end with .summary.json. "
            f"Got: {final_path.name!r:.100}"
        )
    _reject_symlink_parents(final_path, stop_at=repo_root.resolve(strict=False).parent)
    try:
        existing_stat = final_path.lstat()
    except FileNotFoundError:
        return final_path
    if stat.S_ISDIR(existing_stat.st_mode):
        raise IsADirectoryError(
            "resolve summary output failed: output path is a directory. "
            f"Got: {str(final_path)!r:.100}"
        )
    raise FileExistsError(
        "resolve summary output failed: output path already exists. "
        f"Got: {str(final_path)!r:.100}"
    )


def _reject_symlink_parents(path: Path, *, stop_at: Path) -> None:
    current = path.parent
    parents = []
    while current != stop_at and current != current.parent:
        parents.append(current)
        current = current.parent
    for parent in reversed(parents):
        try:
            parent_stat = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(parent_stat.st_mode):
            raise ValueError(
                "validate summary output failed: symlink parent is not allowed. "
                f"Got: {str(parent)!r:.100}"
            )


def write_json_0600_exclusive(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ValueError(
            "write JSON failed: parent directory does not exist. "
            f"Got: {str(path.parent)!r:.100}"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def _write_text_0600_exclusive(path: Path, text: str) -> None:
    if not path.parent.is_dir():
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def _write_text_executable_exclusive(path: Path, text: str) -> None:
    if not path.parent.is_dir():
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o700)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o700)


def _shell_quote(value: Path | str) -> str:
    text = str(value)
    return "'" + text.replace("'", "'\\''") + "'"


def _build_guarded_refresh_runbook(
    *,
    approval_json_path: Path,
    digests_path: Path,
    run_id: str,
    repo_root: Path,
    expected_local_only_run_root: Path,
    expected_marker_path: Path,
    expected_summary_path: Path,
    expected_failed_summary_path: Path,
    codex_home: Path,
    source_implementation_commit: str,
    source_implementation_tree: str,
    execution_head: str,
    execution_tree: str,
    changed_paths_path: Path,
    python_bin: str,
    python_version: str,
    rehearsal_proof: Path,
    rehearsal_proof_sha256: str,
) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

EXECUTION_ROOT={_shell_quote(repo_root)}
APPROVAL_JSON_PATH={_shell_quote(approval_json_path)}
APPROVED_DIGESTS_PATH={_shell_quote(digests_path)}
APPROVAL_STATUS="blocked-before-operator-approval"
APPROVED_RUN_ID={_shell_quote(run_id)}
APPROVED_CODEX_HOME={_shell_quote(codex_home)}
EXPECTED_LOCAL_ONLY_RUN_ROOT={_shell_quote(expected_local_only_run_root)}
EXPECTED_MARKER_PATH={_shell_quote(expected_marker_path)}
EXPECTED_SUMMARY_PATH={_shell_quote(expected_summary_path)}
EXPECTED_FAILED_SUMMARY_PATH={_shell_quote(expected_failed_summary_path)}
APPROVED_SOURCE_IMPLEMENTATION_COMMIT={_shell_quote(source_implementation_commit)}
APPROVED_SOURCE_IMPLEMENTATION_TREE={_shell_quote(source_implementation_tree)}
APPROVED_EXECUTION_HEAD={_shell_quote(execution_head)}
APPROVED_EXECUTION_TREE={_shell_quote(execution_tree)}
APPROVED_CHANGED_PATHS_FILE={_shell_quote(changed_paths_path)}
APPROVED_PYTHON_BIN={_shell_quote(python_bin)}
APPROVED_PYTHON_VERSION={_shell_quote(python_version)}
APPROVED_REHEARSAL_PROOF={_shell_quote(rehearsal_proof)}
APPROVED_REHEARSAL_PROOF_SHA256={_shell_quote(rehearsal_proof_sha256)}
export EXECUTION_ROOT APPROVAL_JSON_PATH APPROVED_DIGESTS_PATH APPROVAL_STATUS
export APPROVED_RUN_ID APPROVED_CODEX_HOME
export EXPECTED_LOCAL_ONLY_RUN_ROOT EXPECTED_MARKER_PATH
export EXPECTED_SUMMARY_PATH EXPECTED_FAILED_SUMMARY_PATH
export APPROVED_SOURCE_IMPLEMENTATION_COMMIT APPROVED_SOURCE_IMPLEMENTATION_TREE
export APPROVED_EXECUTION_HEAD APPROVED_EXECUTION_TREE APPROVED_CHANGED_PATHS_FILE
export APPROVED_PYTHON_BIN APPROVED_PYTHON_VERSION
export APPROVED_REHEARSAL_PROOF APPROVED_REHEARSAL_PROOF_SHA256

fail() {{
  echo "$1" >&2
  exit 1
}}

sha256_file() {{
  shasum -a 256 "$1" | awk '{{print $1}}'
}}

require_value() {{
  name="$1"
  value="$2"
  if [ -z "$value" ]; then
    fail "guarded refresh aborted: approved value is empty: $name"
  fi
  lt='<'
  gt='>'
  case "$value" in
    *"$lt"placeholder"$gt"*|*"$lt"YYYYMMDD-HHMMSS"$gt"*|*"$lt"full-*|*"$lt"absolute-*|*"$lt"sha256-*)
      fail "guarded refresh aborted: approved value is placeholder-shaped: $name=$value"
      ;;
  esac
}}

for pair in \\
  "APPROVED_RUN_ID=$APPROVED_RUN_ID" \\
  "APPROVED_CODEX_HOME=$APPROVED_CODEX_HOME" \\
  "EXPECTED_LOCAL_ONLY_RUN_ROOT=$EXPECTED_LOCAL_ONLY_RUN_ROOT" \\
  "EXPECTED_MARKER_PATH=$EXPECTED_MARKER_PATH" \\
  "EXPECTED_SUMMARY_PATH=$EXPECTED_SUMMARY_PATH" \\
  "EXPECTED_FAILED_SUMMARY_PATH=$EXPECTED_FAILED_SUMMARY_PATH" \\
  "APPROVED_SOURCE_IMPLEMENTATION_COMMIT=$APPROVED_SOURCE_IMPLEMENTATION_COMMIT" \\
  "APPROVED_SOURCE_IMPLEMENTATION_TREE=$APPROVED_SOURCE_IMPLEMENTATION_TREE" \\
  "APPROVED_EXECUTION_HEAD=$APPROVED_EXECUTION_HEAD" \\
  "APPROVED_EXECUTION_TREE=$APPROVED_EXECUTION_TREE" \\
  "APPROVED_CHANGED_PATHS_FILE=$APPROVED_CHANGED_PATHS_FILE" \\
  "APPROVED_PYTHON_BIN=$APPROVED_PYTHON_BIN" \\
  "APPROVED_PYTHON_VERSION=$APPROVED_PYTHON_VERSION" \\
  "APPROVED_REHEARSAL_PROOF=$APPROVED_REHEARSAL_PROOF" \\
  "APPROVED_REHEARSAL_PROOF_SHA256=$APPROVED_REHEARSAL_PROOF_SHA256"; do
  require_value "${{pair%%=*}}" "${{pair#*=}}"
done

case "$APPROVED_RUN_ID" in
  plan06-live-guarded-refresh-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9])
    ;;
  *) fail "guarded refresh aborted: approved run id is malformed: $APPROVED_RUN_ID" ;;
esac

if [ ! -f "$APPROVAL_JSON_PATH" ]; then
  fail "guarded refresh aborted: approval JSON is missing: $APPROVAL_JSON_PATH"
fi
if [ ! -f "$APPROVED_DIGESTS_PATH" ]; then
  fail "guarded refresh aborted: approved digest file is missing: $APPROVED_DIGESTS_PATH"
fi

ACTUAL_APPROVAL_JSON_SHA256="$(sha256_file "$APPROVAL_JSON_PATH")"
ACTUAL_RUNBOOK_SHA256="$(sha256_file "$0")"
DIGEST_APPROVAL_JSON_SHA256="$(
  "$APPROVED_PYTHON_BIN" - "$APPROVED_DIGESTS_PATH" <<'RUNBOOK_DIGEST_APPROVAL'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8"))["approval_json_sha256"])
RUNBOOK_DIGEST_APPROVAL
)"
DIGEST_RUNBOOK_SHA256="$(
  "$APPROVED_PYTHON_BIN" - "$APPROVED_DIGESTS_PATH" <<'RUNBOOK_DIGEST_RUNBOOK'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8"))["runbook_sha256"])
RUNBOOK_DIGEST_RUNBOOK
)"
if [ "$ACTUAL_APPROVAL_JSON_SHA256" != "$DIGEST_APPROVAL_JSON_SHA256" ]; then
  fail "guarded refresh aborted: approval JSON SHA256 differs from approved digest"
fi
if [ "$ACTUAL_RUNBOOK_SHA256" != "$DIGEST_RUNBOOK_SHA256" ]; then
  fail "guarded refresh aborted: runbook SHA256 differs from approved digest"
fi

$APPROVED_PYTHON_BIN - "$APPROVAL_JSON_PATH" <<'RUNBOOK_JSON_CHECK'
from __future__ import annotations
import json
import os
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
checks = {{
    "run_id": os.environ["APPROVED_RUN_ID"],
    "approval_status": os.environ["APPROVAL_STATUS"],
    "execution_root": os.environ["EXECUTION_ROOT"],
    "codex_home": os.environ["APPROVED_CODEX_HOME"],
    "expected_local_only_run_root": os.environ["EXPECTED_LOCAL_ONLY_RUN_ROOT"],
    "expected_marker_path": os.environ["EXPECTED_MARKER_PATH"],
    "expected_summary_path": os.environ["EXPECTED_SUMMARY_PATH"],
    "expected_failed_summary_path": os.environ["EXPECTED_FAILED_SUMMARY_PATH"],
    "source_implementation_commit": os.environ["APPROVED_SOURCE_IMPLEMENTATION_COMMIT"],
    "source_implementation_tree": os.environ["APPROVED_SOURCE_IMPLEMENTATION_TREE"],
    "execution_head": os.environ["APPROVED_EXECUTION_HEAD"],
    "execution_tree": os.environ["APPROVED_EXECUTION_TREE"],
    "approved_changed_paths_file": os.environ["APPROVED_CHANGED_PATHS_FILE"],
    "python_bin": os.environ["APPROVED_PYTHON_BIN"],
    "python_version": os.environ["APPROVED_PYTHON_VERSION"],
    "rehearsal_proof_path": os.environ["APPROVED_REHEARSAL_PROOF"],
    "rehearsal_proof_sha256": os.environ["APPROVED_REHEARSAL_PROOF_SHA256"],
}}
for key, expected in checks.items():
    actual = payload.get(key)
    if actual != expected:
        raise SystemExit(
            f"guarded refresh aborted: approval JSON mismatch for {{key}}. "
            f"Got: {{actual!r}} expected {{expected!r}}"
        )
RUNBOOK_JSON_CHECK

SOURCE_IMPLEMENTATION_COMMIT="$APPROVED_SOURCE_IMPLEMENTATION_COMMIT"
SOURCE_IMPLEMENTATION_TREE="$(
  git -C "$EXECUTION_ROOT" rev-parse "${{SOURCE_IMPLEMENTATION_COMMIT}}^{{tree}}"
)"
EXECUTION_HEAD="$(git -C "$EXECUTION_ROOT" rev-parse HEAD)"
EXECUTION_TREE="$(git -C "$EXECUTION_ROOT" rev-parse HEAD^{{tree}})"
if [ "$SOURCE_IMPLEMENTATION_TREE" != "$APPROVED_SOURCE_IMPLEMENTATION_TREE" ]; then
  fail "guarded refresh aborted: source implementation identity changed after approval"
fi
if [ "$EXECUTION_HEAD" != "$APPROVED_EXECUTION_HEAD" ] || \
   [ "$EXECUTION_TREE" != "$APPROVED_EXECUTION_TREE" ]; then
  fail "guarded refresh aborted: execution identity changed after approval"
fi
if ! git -C "$EXECUTION_ROOT" merge-base \
  --is-ancestor "$SOURCE_IMPLEMENTATION_COMMIT" "$EXECUTION_HEAD"; then
  fail "guarded refresh aborted: source implementation commit is not an ancestor of execution head"
fi
if [ ! -f "$APPROVED_CHANGED_PATHS_FILE" ]; then
  fail "guarded refresh aborted: approved changed-paths file is missing"
fi
if ! git -C "$EXECUTION_ROOT" diff --quiet; then
  git -C "$EXECUTION_ROOT" status --short >&2
  fail "guarded refresh aborted: execution worktree has unstaged changes"
fi
if ! git -C "$EXECUTION_ROOT" diff --cached --quiet; then
  git -C "$EXECUTION_ROOT" status --short >&2
  fail "guarded refresh aborted: execution worktree has staged changes"
fi
UNTRACKED_RELEVANT="$(
  git -C "$EXECUTION_ROOT" ls-files --others --exclude-standard -- \
    plugins/turbo-mode/tools \
    plugins/turbo-mode/handoff \
    plugins/turbo-mode/ticket \
    plugins/turbo-mode/evidence/refresh \
    .agents/plugins/marketplace.json
)"
if [ -n "$UNTRACKED_RELEVANT" ]; then
  printf '%s\n' "$UNTRACKED_RELEVANT" >&2
  fail "guarded refresh aborted: execution worktree has untracked relevant files"
fi
ACTUAL_CHANGED_PATHS="$(
  git -C "$EXECUTION_ROOT" diff \
    --name-only "$SOURCE_IMPLEMENTATION_COMMIT..$EXECUTION_HEAD" -- . | sort
)"
APPROVED_CHANGED_PATHS="$(sort "$APPROVED_CHANGED_PATHS_FILE")"
if [ "$ACTUAL_CHANGED_PATHS" != "$APPROVED_CHANGED_PATHS" ]; then
  fail "guarded refresh aborted: source-to-execution changed paths differ from approved list"
fi
if [ ! -f "$APPROVED_REHEARSAL_PROOF" ]; then
  fail "guarded refresh aborted: rehearsal proof is missing"
fi
ACTUAL_REHEARSAL_PROOF_SHA256="$(sha256_file "$APPROVED_REHEARSAL_PROOF")"
if [ "$ACTUAL_REHEARSAL_PROOF_SHA256" != "$APPROVED_REHEARSAL_PROOF_SHA256" ]; then
  fail "guarded refresh aborted: rehearsal proof SHA256 changed after approval"
fi
ACTUAL_PYTHON_VERSION="$($APPROVED_PYTHON_BIN - <<'RUNBOOK_PY_VERSION'
import platform
print(platform.python_version())
RUNBOOK_PY_VERSION
)"
if [ "$ACTUAL_PYTHON_VERSION" != "$APPROVED_PYTHON_VERSION" ]; then
  fail "guarded refresh aborted: python version changed after approval"
fi
if ! "$APPROVED_PYTHON_BIN" - <<'RUNBOOK_PY_MIN'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
RUNBOOK_PY_MIN
then
  fail "python3 >= 3.11 is required for guarded refresh"
fi
if [ -e "$EXPECTED_LOCAL_ONLY_RUN_ROOT" ] || \
   [ -e "$EXPECTED_MARKER_PATH" ] || \
   [ -e "$EXPECTED_SUMMARY_PATH" ] || \
   [ -e "$EXPECTED_FAILED_SUMMARY_PATH" ]; then
  fail "guarded refresh aborted: approved run id already has evidence paths"
fi

if [ "${{1:-}}" = "--static-preflight-only" ]; then
  echo "guarded refresh static preflight passed for $APPROVED_RUN_ID"
  echo "approval_status=$APPROVAL_STATUS"
  exit 0
fi

if [ "$APPROVAL_STATUS" != "approved-for-external-maintenance-window" ]; then
  fail "guarded refresh aborted: approval packet is not approved for live mutation"
fi

PYTHONDONTWRITEBYTECODE=1 \\
PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \\
"$APPROVED_PYTHON_BIN" \\
  "$EXECUTION_ROOT/plugins/turbo-mode/tools/refresh_installed_turbo_mode.py" \\
  --guarded-refresh \\
  --smoke standard \\
  --run-id "$APPROVED_RUN_ID" \\
  --repo-root "$EXECUTION_ROOT" \\
  --codex-home "$APPROVED_CODEX_HOME" \\
  --source-implementation-commit "$SOURCE_IMPLEMENTATION_COMMIT" \\
  --source-implementation-tree "$SOURCE_IMPLEMENTATION_TREE" \\
  --rehearsal-proof "$APPROVED_REHEARSAL_PROOF" \\
  --rehearsal-proof-sha256 "$APPROVED_REHEARSAL_PROOF_SHA256" \\
  --record-summary \\
  --require-terminal-status guarded-refresh-required \\
  --json
"""


def _build_operator_approval_packet(
    *,
    run_id: str,
    approval_json_path: Path,
    approval_json_sha256: str,
    runbook_path: Path,
    runbook_sha256: str,
    digests_path: Path,
    digests_sha256: str,
    changed_paths_path: Path,
    changed_paths_sha256: str,
    branch: str,
    source_implementation_commit: str,
    source_implementation_tree: str,
    execution_head: str,
    execution_tree: str,
    changed_paths: tuple[str, ...],
    python_bin: str,
    python_version: str,
    rehearsal_proof: Path,
    rehearsal_proof_sha256: str,
    codex_home: Path,
    expected_local_only_run_root: Path,
    expected_marker_path: Path,
    expected_summary_path: Path,
    expected_failed_summary_path: Path,
) -> str:
    changed_paths_text = "\n".join(f"- `{path}`" for path in changed_paths)
    if not changed_paths_text:
        changed_paths_text = "- none; the approved changed-path file exists and is empty."
    return f"""# Plan 06 Task 9 Operator Approval Candidate

Status: blocked-before-operator-approval

This packet records concrete Task 9 approval mechanics for run `{run_id}`.
It is not approval to run live mutation. Operator approval for the external
maintenance window is still required.

## Artifacts

- Approval JSON: `{approval_json_path}`
- Approval JSON SHA256: `{approval_json_sha256}`
- Runbook: `{runbook_path}`
- Runbook SHA256: `{runbook_sha256}`
- Approved digest sidecar: `{digests_path}`
- Approved digest sidecar SHA256: `{digests_sha256}`
- Approved changed paths file: `{changed_paths_path}`
- Approved changed paths SHA256: `{changed_paths_sha256}`

## Approved Identities

- Run id: `{run_id}`
- Branch: `{branch}`
- Source implementation commit: `{source_implementation_commit}`
- Source implementation tree: `{source_implementation_tree}`
- Execution head: `{execution_head}`
- Execution tree: `{execution_tree}`
- Source/execution identity match: {str(not changed_paths).lower()}
- Approved changed paths:
{changed_paths_text}

## Approved Runtime Inputs

- Python: `{python_bin}`
- Python version: `{python_version}`
- Codex home: `{codex_home}`
- Rehearsal proof: `{rehearsal_proof}`
- Rehearsal proof SHA256: `{rehearsal_proof_sha256}`

## Expected Paths

- Local-only run root: `{expected_local_only_run_root}`
- Run-state marker: `{expected_marker_path}`
- Recovery handle: `{run_id}`
- Certified summary: `{expected_summary_path}`
- Failed summary: `{expected_failed_summary_path}`

## Operator Boundary

The operator must close active Codex Desktop and CLI sessions, keep them closed
until the external command exits, and run the generated runbook from an external
shell only after explicitly approving the maintenance window.

## Static Check

```bash
{runbook_path} --static-preflight-only
```
"""


def publish_json_0600_exclusive(source_payload_path: Path, final_path: Path) -> None:
    _reject_symlink_parents(final_path, stop_at=final_path.anchor and Path(final_path.anchor))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_parents(final_path, stop_at=final_path.anchor and Path(final_path.anchor))
    payload = json.loads(source_payload_path.read_text(encoding="utf-8"))
    write_json_0600_exclusive(final_path, payload)


def run_validator(command: list[str]) -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise RefreshError(
            "run validator failed: validator exited non-zero. "
            f"Got: {completed.stderr.strip() or completed.stdout.strip()!r:.100}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
