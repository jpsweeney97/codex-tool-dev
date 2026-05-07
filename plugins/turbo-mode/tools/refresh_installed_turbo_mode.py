#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

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
            assert dirty_state is not None
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
    real_codex_home = Path("/Users/jp/.codex")
    if codex_home == real_codex_home or real_codex_home in codex_home.parents:
        parser.error(
            "--seed-isolated-rehearsal-home requires --codex-home outside /Users/jp/.codex"
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

    run_id = args.run_id or uuid.uuid4().hex
    try:
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


def guarded_refresh_main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    codex_home = args.codex_home.expanduser().resolve(strict=False)
    real_codex_home = Path("/Users/jp/.codex")
    is_real_home = codex_home == real_codex_home
    if args.no_record_summary and is_real_home:
        parser.error("--no-record-summary is not allowed for real guarded refresh")
    if args.isolated_rehearsal and is_real_home:
        parser.error("--isolated-rehearsal requires --codex-home outside /Users/jp/.codex")
    if not is_real_home and not args.isolated_rehearsal:
        parser.error("--guarded-refresh with temporary --codex-home requires --isolated-rehearsal")
    if is_real_home:
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
        if is_real_home:
            assert args.rehearsal_proof is not None
            assert args.rehearsal_proof_sha256 is not None
            validated_rehearsal_proof = validate_rehearsal_proof_bundle(
                proof_path=args.rehearsal_proof,
                expected_sha256=args.rehearsal_proof_sha256,
                source_implementation_commit=args.source_implementation_commit,
                source_implementation_tree=args.source_implementation_tree,
                tool_sha256=sha256_file(CURRENT_FILE),
            )
            rehearsal_capture = capture_rehearsal_proof_bundle(
                validated_rehearsal_proof,
                live_run_root=codex_home / "local-only/turbo-mode-refresh" / run_id,
            )
        ensure_no_active_run_state_markers(codex_home / "local-only/turbo-mode-refresh")
    except (RefreshError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if is_real_home:
        if rehearsal_capture is not None:
            print(
                "rehearsal proof capture complete: "
                f"{rehearsal_capture.capture_manifest_path}",
                file=sys.stderr,
            )
        print(
            "real guarded refresh blocked after rehearsal proof capture: "
            "live mutation and certified summary publication are not complete "
            "in this task slice",
            file=sys.stderr,
        )
        return 1

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

    run_id = str(args.recover)
    try:
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

    run_id = str(args.certify_retained_run)
    try:
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


def git_rev_parse(repo_root: Path, revision: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", revision],
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
