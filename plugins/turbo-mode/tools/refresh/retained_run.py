from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .commit_safe import (
    build_retained_run_commit_safe_summary,
    ensure_relevant_worktree_clean,
    sha256_file,
    sha256_payload,
)
from .models import RefreshError
from .planner import plan_refresh
from .publication import (
    PublicationReplayPaths,
    publish_and_replay_commit_safe_summary,
)
from .validation import assert_commit_safe_payload, load_json_object

TOOL_RELATIVE_PATH = Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py")
EVIDENCE_ROOT_RELATIVE = Path("plugins/turbo-mode/evidence/refresh")
LOCAL_ONLY_RELATIVE = Path("local-only/turbo-mode-refresh")
RETAINED_EVIDENCE_FILE = "retained-certification-evidence.json"
RETAINED_STATUS_FILE = "retained-certification-status.json"
RETAINED_NO_MUTATION_PROOF_FILE = "retained-no-mutation-proof.json"
ALLOWED_RETAINED_SOURCE_DELTA_PREFIXES = (
    "docs/",
    "plugins/turbo-mode/evidence/refresh/",
    "plugins/turbo-mode/tools/refresh/commit_safe.py",
    "plugins/turbo-mode/tools/refresh/retained_run.py",
    "plugins/turbo-mode/tools/refresh/tests/",
    "plugins/turbo-mode/tools/refresh/validation.py",
    "plugins/turbo-mode/tools/refresh_validate_redaction.py",
    "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
)
SUPPORTED_RETAINED_STATUSES = {
    "MUTATION_COMPLETE_EVIDENCE_FAILED",
    "MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN",
}


@dataclass(frozen=True)
class RetainedRunResult:
    outcome: str
    published_summary_path: str
    status_path: str
    final_status: str


def certify_retained_run(
    *,
    run_id: str,
    repo_root: Path,
    codex_home: Path,
    plan_status_collector: Callable[[], str] | None = None,
    validator_runner: Callable[[str, Path, Path], None] | None = None,
) -> RetainedRunResult:
    repo_root = repo_root.expanduser().resolve(strict=True)
    codex_home = codex_home.expanduser().resolve(strict=False)
    run_root = codex_home / LOCAL_ONLY_RELATIVE / run_id
    if not run_root.is_dir():
        raise RefreshError(
            "certify retained run failed: retained run root is missing. "
            f"Got: {str(run_root)!r:.100}"
        )
    run_root.chmod(0o700)
    final_status = load_json_object(run_root / "final-status.json")
    evidence = load_json_object(run_root / RETAINED_EVIDENCE_FILE)
    _validate_retained_identity(run_id, final_status=final_status, evidence=evidence)
    original_final_status = str(final_status["final_status"])
    if original_final_status not in SUPPORTED_RETAINED_STATUSES:
        raise RefreshError(
            "certify retained run failed: unsupported retained terminal status. "
            f"Got: {original_final_status!r:.100}"
        )
    path_state = _inspect_summary_path_state(repo_root, run_id=run_id)
    current_plan_status = (
        plan_status_collector()
        if plan_status_collector is not None
        else _collect_current_plan_status(repo_root=repo_root, codex_home=codex_home)
    )
    _validate_current_plan_status(current_plan_status, evidence)
    _validate_original_process_gate(original_final_status, evidence)
    _validate_source_to_certification_delta(evidence)
    rehearsal_manifest_sha256 = _validate_captured_rehearsal_bundle(run_root, evidence)
    before_mutation_surface = _mutation_surface_snapshot(codex_home)
    retained_no_mutation_proof_path = run_root / RETAINED_NO_MUTATION_PROOF_FILE
    _write_private_json(
        retained_no_mutation_proof_path,
        {
            "schema_version": "turbo-mode-retained-no-mutation-proof-v1",
            "run_id": run_id,
            "current_terminal_plan_status": current_plan_status,
            "codex_home_config_snapshot": before_mutation_surface["config"],
            "installed_cache_snapshot": before_mutation_surface["installed_cache"],
        },
    )
    after_mutation_surface = _mutation_surface_snapshot(codex_home)
    if after_mutation_surface != before_mutation_surface:
        raise RefreshError(
            "certify retained run failed: certification mutated installed state. "
            f"Got: {after_mutation_surface!r:.100}"
        )

    certification_source_commit = _git(repo_root, "rev-parse", "HEAD")
    certification_source_tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    certification_execution_head = certification_source_commit
    certification_execution_tree = certification_source_tree
    dirty_state = ensure_relevant_worktree_clean(repo_root)
    summary_paths = _summary_paths(repo_root=repo_root, run_root=run_root, run_id=run_id)
    guarded_evidence = evidence.get("guarded_refresh_evidence")
    if not isinstance(guarded_evidence, dict):
        raise RefreshError(
            "certify retained run failed: guarded refresh evidence is missing. "
            f"Got: {type(guarded_evidence).__name__!r:.100}"
        )

    try:
        publication = publish_and_replay_commit_safe_summary(
            operation="certify retained run",
            paths=PublicationReplayPaths(
                candidate=summary_paths["candidate"],
                final=summary_paths["final"],
                metadata=summary_paths["metadata"],
                redaction=summary_paths["redaction"],
                redaction_final=summary_paths["redaction_final"],
                published=summary_paths["published"],
                failed=summary_paths["failed"],
            ),
            build_candidate_payload=lambda: build_retained_run_commit_safe_summary(
                guarded_evidence,
                run_id=run_id,
                local_only_evidence_root=run_root,
                tool_path=TOOL_RELATIVE_PATH,
                tool_sha256=sha256_file(repo_root / TOOL_RELATIVE_PATH),
                dirty_state=dirty_state,
                metadata_validation_summary_sha256=None,
                redaction_validation_summary_sha256=None,
                certification_source_commit=certification_source_commit,
                certification_source_tree=certification_source_tree,
                certification_execution_head=certification_execution_head,
                certification_execution_tree=certification_execution_tree,
                retained_summary_path=_repo_relative(repo_root, summary_paths["published"]),
                original_run_final_status=original_final_status,
                retained_certification_outcome=str(evidence["retained_certification_outcome"]),
                prior_summary_path_state=path_state["state"],
                retained_no_mutation_proof_sha256=sha256_file(retained_no_mutation_proof_path),
                rehearsal_proof_capture_manifest_sha256=rehearsal_manifest_sha256,
                prior_failed_summary_path=path_state["failed_relative"],
                prior_failed_summary_sha256=path_state["failed_sha256"],
                prior_failed_summary_status=path_state["failed_status"],
            ),
            build_final_payload=lambda metadata_sha, redaction_sha: (
                build_retained_run_commit_safe_summary(
                    guarded_evidence,
                    run_id=run_id,
                    local_only_evidence_root=run_root,
                    tool_path=TOOL_RELATIVE_PATH,
                    tool_sha256=sha256_file(repo_root / TOOL_RELATIVE_PATH),
                    dirty_state=dirty_state,
                    metadata_validation_summary_sha256=metadata_sha,
                    redaction_validation_summary_sha256=redaction_sha,
                    certification_source_commit=certification_source_commit,
                    certification_source_tree=certification_source_tree,
                    certification_execution_head=certification_execution_head,
                    certification_execution_tree=certification_execution_tree,
                    retained_summary_path=_repo_relative(repo_root, summary_paths["published"]),
                    original_run_final_status=original_final_status,
                    retained_certification_outcome=str(
                        evidence["retained_certification_outcome"]
                    ),
                    prior_summary_path_state=path_state["state"],
                    retained_no_mutation_proof_sha256=sha256_file(
                        retained_no_mutation_proof_path
                    ),
                    rehearsal_proof_capture_manifest_sha256=rehearsal_manifest_sha256,
                    prior_failed_summary_path=path_state["failed_relative"],
                    prior_failed_summary_sha256=path_state["failed_sha256"],
                    prior_failed_summary_status=path_state["failed_status"],
                )
            ),
            validate_payload=assert_commit_safe_payload,
            run_candidate_validation=lambda paths: _run_validation(
                phase="candidate",
                run_id=run_id,
                repo_root=repo_root,
                run_root=run_root,
                summary=paths.candidate,
                published=paths.published,
                validator_runner=validator_runner,
                candidate=None,
                existing_metadata=None,
                existing_redaction=None,
            ),
            run_final_validation=lambda paths: _run_validation(
                phase="final",
                run_id=run_id,
                repo_root=repo_root,
                run_root=run_root,
                summary=paths.final,
                published=paths.published,
                validator_runner=validator_runner,
                candidate=paths.candidate,
                existing_metadata=paths.metadata,
                existing_redaction=paths.redaction,
            ),
        )
    except BaseException as exc:
        demoted_summary_path = getattr(exc, "demoted_summary_path", None)
        _write_status(
            run_root,
            run_id=run_id,
            outcome="retained-certification-failed",
            final_status=(
                "RETAINED_CERTIFICATION_POST_PUBLISH_FAILED"
                if demoted_summary_path is not None
                else "RETAINED_CERTIFICATION_PRE_PUBLISH_FAILED"
            ),
            demoted_summary_path=demoted_summary_path,
        )
        raise

    status_path = _write_status(
        run_root,
        run_id=run_id,
        outcome=str(evidence["retained_certification_outcome"]),
        final_status="MUTATION_COMPLETE_CERTIFIED",
        demoted_summary_path=None,
    )
    return RetainedRunResult(
        outcome=str(evidence["retained_certification_outcome"]),
        published_summary_path=publication.published_summary_path,
        status_path=str(status_path),
        final_status="MUTATION_COMPLETE_CERTIFIED",
    )


def _collect_current_plan_status(*, repo_root: Path, codex_home: Path) -> str:
    result = plan_refresh(
        repo_root=repo_root,
        codex_home=codex_home,
        mode="plan-refresh",
        inventory_check=True,
    )
    return result.terminal_status.value


def _validate_retained_identity(
    run_id: str,
    *,
    final_status: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    if final_status.get("run_id") != run_id or evidence.get("run_id") != run_id:
        raise RefreshError(
            "certify retained run failed: run id mismatch. "
            f"Got: {final_status.get('run_id')!r:.100}"
        )
    if evidence.get("schema_version") != "turbo-mode-retained-run-evidence-v1":
        raise RefreshError(
            "certify retained run failed: invalid retained evidence schema. "
            f"Got: {evidence.get('schema_version')!r:.100}"
        )
    if evidence.get("retained_certification_outcome") != "retained-certified":
        raise RefreshError(
            "certify retained run failed: unsupported retained certification outcome. "
            f"Got: {evidence.get('retained_certification_outcome')!r:.100}"
        )


def _inspect_summary_path_state(repo_root: Path, *, run_id: str) -> dict[str, str | None]:
    evidence_root = repo_root / EVIDENCE_ROOT_RELATIVE
    live_summary = evidence_root / f"{run_id}.summary.json"
    failed_summary = evidence_root / f"{run_id}.summary.failed.json"
    retained_summary = evidence_root / f"{run_id}.retained.summary.json"
    retained_failed = evidence_root / f"{run_id}.retained.summary.failed.json"
    if live_summary.exists():
        raise RefreshError(
            "certify retained run failed: summary.json already exists for run id. "
            f"Got: {str(live_summary)!r:.100}"
        )
    if retained_summary.exists() or retained_failed.exists():
        raise RefreshError(
            "certify retained run failed: retained summary already exists for run id. "
            f"Got: {str(retained_summary if retained_summary.exists() else retained_failed)!r:.100}"
        )
    if failed_summary.exists():
        return {
            "state": "forensic-demotion-retained",
            "failed_relative": _repo_relative(repo_root, failed_summary),
            "failed_sha256": sha256_file(failed_summary),
            "failed_status": "forensic-demotion-retained",
        }
    return {
        "state": "none",
        "failed_relative": None,
        "failed_sha256": None,
        "failed_status": None,
    }


def _validate_current_plan_status(status: str, evidence: dict[str, Any]) -> None:
    if status == "no-drift":
        if evidence.get("successful_prior_mutation") is not True:
            raise RefreshError(
                "certify retained run failed: no-drift requires successful prior mutation "
                "evidence. Got: successful_prior_mutation"
            )
        return
    if status == "guarded-refresh-required":
        if evidence.get("rollback_or_never_changed") is not True:
            raise RefreshError(
                "certify retained run failed: guarded-refresh-required requires rollback or "
                "never-changed evidence. Got: rollback_or_never_changed"
            )
        return
    raise RefreshError(
        "certify retained run failed: unsupported current terminal plan status. "
        f"Got: {status!r:.100}"
    )


def _validate_original_process_gate(status: str, evidence: dict[str, Any]) -> None:
    process_gate = evidence.get("process_gate_status")
    if status == "MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN":
        if process_gate != "misclassified-non-blocking":
            raise RefreshError(
                "certify retained run failed: exclusivity-unproven process gate is not "
                f"certifiable. Got: {process_gate!r:.100}"
            )
    elif process_gate not in {"non-blocking", "misclassified-non-blocking"}:
        raise RefreshError(
            "certify retained run failed: original process gate is not certifiable. "
            f"Got: {process_gate!r:.100}"
        )


def _validate_source_to_certification_delta(evidence: dict[str, Any]) -> None:
    paths = evidence.get("source_to_certification_changed_paths")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise RefreshError(
            "certify retained run failed: source-to-certification delta is invalid. "
            f"Got: {paths!r:.100}"
        )
    blocked = [
        path
        for path in paths
        if not path.startswith(ALLOWED_RETAINED_SOURCE_DELTA_PREFIXES)
    ]
    if blocked:
        raise RefreshError(
            "certify retained run failed: source-to-certification delta touches blocked "
            f"path. Got: {blocked!r:.100}"
        )


def _validate_captured_rehearsal_bundle(run_root: Path, evidence: dict[str, Any]) -> str:
    relative = evidence.get("captured_rehearsal_proof_manifest_path")
    if not isinstance(relative, str):
        raise RefreshError(
            "certify retained run failed: captured rehearsal proof manifest is missing. "
            f"Got: {relative!r:.100}"
        )
    manifest = (run_root / relative).resolve(strict=False)
    try:
        manifest.relative_to(run_root.resolve(strict=False))
    except ValueError as exc:
        raise RefreshError(
            "certify retained run failed: captured rehearsal proof manifest escaped run root. "
            f"Got: {relative!r:.100}"
        ) from exc
    if not manifest.is_file():
        raise RefreshError(
            "certify retained run failed: captured rehearsal proof manifest is missing. "
            f"Got: {str(manifest)!r:.100}"
        )
    digest = sha256_file(manifest)
    if evidence.get("captured_rehearsal_proof_manifest_sha256") != digest:
        raise RefreshError(
            "certify retained run failed: captured rehearsal proof manifest digest mismatch. "
            "Got: captured_rehearsal_proof_manifest_sha256"
        )
    return digest


def _mutation_surface_snapshot(codex_home: Path) -> dict[str, Any]:
    return {
        "config": _snapshot_path(codex_home / "config.toml"),
        "installed_cache": _snapshot_path(codex_home / "plugins/cache/turbo-mode"),
    }


def _snapshot_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "missing"}
    if path.is_file():
        return {"state": "file", "sha256": sha256_file(path)}
    if path.is_dir():
        entries = []
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            entries.append(
                {
                    "path": child.relative_to(path).as_posix(),
                    "sha256": sha256_file(child),
                }
            )
        return {"state": "directory", "entries_sha256": sha256_payload(entries)}
    return {"state": "other"}


def _summary_paths(*, repo_root: Path, run_root: Path, run_id: str) -> dict[str, Path]:
    evidence_root = repo_root / EVIDENCE_ROOT_RELATIVE
    return {
        "candidate": run_root / "commit-safe.candidate.summary.json",
        "final": run_root / "commit-safe.final.summary.json",
        "metadata": run_root / "metadata-validation.summary.json",
        "redaction": run_root / "redaction.summary.json",
        "redaction_final": run_root / "redaction-final-scan.summary.json",
        "published": evidence_root / f"{run_id}.retained.summary.json",
        "failed": evidence_root / f"{run_id}.retained.summary.failed.json",
    }


def _run_validation(
    *,
    phase: str,
    run_id: str,
    repo_root: Path,
    run_root: Path,
    summary: Path,
    published: Path,
    validator_runner: Callable[[str, Path, Path], None] | None,
    candidate: Path | None,
    existing_metadata: Path | None,
    existing_redaction: Path | None,
) -> None:
    if validator_runner is not None:
        validator_runner(phase, summary, published)
        return
    refresh_parent = repo_root / "plugins/turbo-mode/tools"
    metadata_command = [
        sys.executable,
        str(refresh_parent / "refresh_validate_run_metadata.py"),
        "--mode",
        phase,
        "--run-id",
        run_id,
        "--source-code-root",
        str(repo_root),
        "--execution-repo-root",
        str(repo_root),
        "--local-only-root",
        str(run_root),
        "--summary",
        str(summary),
        "--published-summary-path",
        str(published),
    ]
    redaction_command = [
        sys.executable,
        str(refresh_parent / "refresh_validate_redaction.py"),
        "--mode",
        phase,
        "--run-id",
        run_id,
        "--source-code-root",
        str(repo_root),
        "--execution-repo-root",
        str(repo_root),
        "--scope",
        "commit-safe-summary",
        "--source",
        "retained-run",
        "--summary",
        str(summary),
        "--local-only-root",
        str(run_root),
        "--published-summary-path",
        str(published),
    ]
    if phase == "candidate":
        _run_validator(
            [
                *metadata_command,
                "--summary-output",
                str(run_root / "metadata-validation.summary.json"),
            ]
        )
        _run_validator(
            [
                *redaction_command,
                "--summary-output",
                str(run_root / "redaction.summary.json"),
                "--validate-own-summary",
            ]
        )
        return
    assert candidate is not None
    assert existing_metadata is not None
    assert existing_redaction is not None
    _run_validator(
        [
            *metadata_command,
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(existing_metadata),
        ]
    )
    _run_validator(
        [
            *redaction_command,
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(existing_redaction),
            "--final-scan-output",
            str(run_root / "redaction-final-scan.summary.json"),
        ]
    )


def _run_validator(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise RefreshError(
            "certify retained run failed: validator exited non-zero. "
            f"Got: {completed.stderr.strip() or completed.stdout.strip()!r:.100}"
        )


def _write_status(
    run_root: Path,
    *,
    run_id: str,
    outcome: str,
    final_status: str,
    demoted_summary_path: Path | None,
) -> Path:
    status_path = run_root / RETAINED_STATUS_FILE
    if status_path.exists():
        status_path.unlink()
    payload = {
        "schema_version": "turbo-mode-retained-certification-status-v1",
        "run_id": run_id,
        "outcome": outcome,
        "final_status": final_status,
        "demoted_summary_path": str(demoted_summary_path) if demoted_summary_path else None,
    }
    _write_private_json(status_path, payload)
    return status_path


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(
            "write retained-run JSON failed: output already exists. "
            f"Got: {str(path)!r:.100}"
        )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def _repo_relative(repo_root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(repo_root.resolve(strict=False)).as_posix()


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()
