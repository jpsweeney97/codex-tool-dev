from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from refresh import retained_run
from refresh.models import RefreshError

TOOL_REL = Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def init_repo(repo_root: Path) -> tuple[str, str]:
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
    for rel in (
        TOOL_REL,
        Path("plugins/turbo-mode/tools/refresh/commit_safe.py"),
        Path("plugins/turbo-mode/tools/refresh/validation.py"),
        Path("plugins/turbo-mode/tools/refresh/retained_run.py"),
        Path("plugins/turbo-mode/tools/refresh_validate_run_metadata.py"),
        Path("plugins/turbo-mode/tools/refresh_validate_redaction.py"),
    ):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if rel.as_posix().startswith("plugins/turbo-mode/tools/refresh/"):
            source = Path(__file__).resolve().parents[1] / rel.relative_to(
                "plugins/turbo-mode/tools/refresh"
            )
        else:
            source = Path(__file__).resolve().parents[5] / rel
        if source.is_file():
            path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            path.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "original mutation"], cwd=repo_root, check=True)
    head = git(repo_root, "rev-parse", "HEAD")
    tree = git(repo_root, "rev-parse", "HEAD^{tree}")
    return head, tree


def git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guarded_evidence(source_commit: str, source_tree: str) -> dict[str, object]:
    return {
        "mode": "guarded-refresh",
        "source_implementation_commit": source_commit,
        "source_implementation_tree": source_tree,
        "execution_head": source_commit,
        "execution_tree": source_tree,
        "isolated_rehearsal_run_id": "rehearsal-run",
        "rehearsal_proof_sha256": "3" * 64,
        "rehearsal_proof_validation_status": "validated-before-live-mutation",
        "rehearsal_proof_capture_manifest_sha256": "4" * 64,
        "source_to_rehearsal_execution_delta_status": "identical",
        "source_to_rehearsal_allowed_delta_proof_sha256": "5" * 64,
        "source_to_rehearsal_changed_paths_sha256": "6" * 64,
        "isolated_app_server_authority_proof_sha256": "7" * 64,
        "no_real_home_authority_proof_sha256": "8" * 64,
        "pre_snapshot_app_server_launch_authority_sha256": "9" * 64,
        "pre_install_app_server_target_authority_sha256": "a" * 64,
        "live_app_server_authority_proof_sha256": "b" * 64,
        "source_manifest_sha256": "c" * 64,
        "pre_refresh_cache_manifest_sha256": "d" * 64,
        "post_refresh_cache_manifest_sha256": "e" * 64,
        "pre_refresh_config_sha256": "f" * 64,
        "post_refresh_config_sha256": "0" * 64,
        "post_refresh_inventory_sha256": "1" * 64,
        "selected_smoke_tier": "standard",
        "smoke_summary_sha256": "2" * 64,
        "post_mutation_process_census_sha256": "4" * 64,
        "exclusivity_status": "exclusive_window_observed_by_process_samples",
        "phase_reached": "evidence-published",
        "final_status": "MUTATION_COMPLETE_CERTIFIED",
        "rollback_or_restore_status": "not-attempted",
    }


def write_retained_run(
    tmp_path: Path,
    *,
    status: str = "MUTATION_COMPLETE_EVIDENCE_FAILED",
    successful_prior_mutation: bool = True,
    rollback_or_never_changed: bool = False,
    process_gate_status: str = "non-blocking",
) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    source_commit, source_tree = init_repo(repo_root)
    codex_home = tmp_path / ".codex"
    run_root = codex_home / "local-only/turbo-mode-refresh/run-1"
    write_json(
        run_root / "final-status.json",
        {
            "schema_version": "turbo-mode-refresh-final-status-v1",
            "run_id": "run-1",
            "mode": "guarded-refresh",
            "source_implementation_commit": source_commit,
            "source_implementation_tree": source_tree,
            "execution_head": source_commit,
            "execution_tree": source_tree,
            "final_status": status,
        },
    )
    manifest = run_root / "rehearsal-proof-capture/capture-manifest.json"
    write_json(
        manifest,
        {
            "schema_version": "turbo-mode-refresh-rehearsal-capture-v1",
            "run_id": "run-1",
            "rehearsal_proof_sha256": "3" * 64,
        },
    )
    write_json(
        run_root / "guarded-refresh.summary.json",
        {"mode": "guarded-refresh", "run_id": "run-1"},
    )
    write_json(
        run_root / "retained-certification-evidence.json",
        {
            "schema_version": "turbo-mode-retained-run-evidence-v1",
            "run_id": "run-1",
            "successful_prior_mutation": successful_prior_mutation,
            "rollback_or_never_changed": rollback_or_never_changed,
            "process_gate_status": process_gate_status,
            "source_to_certification_changed_paths": [
                "plugins/turbo-mode/tools/refresh/validation.py"
            ],
            "captured_rehearsal_proof_manifest_path": (
                "rehearsal-proof-capture/capture-manifest.json"
            ),
            "captured_rehearsal_proof_manifest_sha256": sha256_file(manifest),
            "retained_certification_outcome": "retained-certified",
            "guarded_refresh_evidence": guarded_evidence(source_commit, source_tree),
        },
    )
    return repo_root, codex_home, run_root


def no_op_validator(_phase: str, _summary: Path, _published: Path) -> None:
    if _phase == "candidate":
        write_json(_summary.parent / "metadata-validation.summary.json", {"status": "passed"})
        write_json(_summary.parent / "redaction.summary.json", {"status": "passed"})


def test_retained_run_refuses_missing_run_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(RefreshError, match="retained run root is missing"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=tmp_path / ".codex",
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_refuses_non_retained_terminal_status(tmp_path: Path) -> None:
    repo_root, codex_home, _run_root = write_retained_run(
        tmp_path,
        status="MUTATION_COMPLETE_CERTIFIED",
    )

    with pytest.raises(RefreshError, match="unsupported retained terminal status"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_accepts_failed_summary_as_immutable_forensic_evidence(
    tmp_path: Path,
) -> None:
    repo_root, codex_home, _run_root = write_retained_run(tmp_path)
    failed = repo_root / "plugins/turbo-mode/evidence/refresh/run-1.summary.failed.json"
    write_json(failed, {"final_status": "MUTATION_COMPLETE_EVIDENCE_FAILED"})
    before = sha256_file(failed)

    result = retained_run.certify_retained_run(
        run_id="run-1",
        repo_root=repo_root,
        codex_home=codex_home,
        plan_status_collector=lambda: "no-drift",
        validator_runner=no_op_validator,
    )

    assert result.outcome == "retained-certified"
    assert result.published_summary_path.endswith("run-1.retained.summary.json")
    assert sha256_file(failed) == before
    published = json.loads(Path(result.published_summary_path).read_text(encoding="utf-8"))
    assert published["certification_mode"] == "retained-run"
    assert published["prior_failed_summary_status"] == "forensic-demotion-retained"
    assert published["prior_failed_summary_sha256"] == before


def test_retained_run_rejects_second_green_summary_path_state(tmp_path: Path) -> None:
    repo_root, codex_home, _run_root = write_retained_run(tmp_path)
    write_json(repo_root / "plugins/turbo-mode/evidence/refresh/run-1.summary.json", {})

    with pytest.raises(RefreshError, match="summary.json already exists"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_rejects_prior_retained_summary_path_state(tmp_path: Path) -> None:
    repo_root, codex_home, _run_root = write_retained_run(tmp_path)
    write_json(repo_root / "plugins/turbo-mode/evidence/refresh/run-1.retained.summary.json", {})

    with pytest.raises(RefreshError, match="retained summary already exists"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_rejects_no_drift_without_successful_prior_mutation(
    tmp_path: Path,
) -> None:
    repo_root, codex_home, _run_root = write_retained_run(
        tmp_path,
        successful_prior_mutation=False,
    )

    with pytest.raises(RefreshError, match="successful prior mutation"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_rejects_guarded_refresh_required_without_rollback_evidence(
    tmp_path: Path,
) -> None:
    repo_root, codex_home, _run_root = write_retained_run(tmp_path)

    with pytest.raises(RefreshError, match="rollback or never-changed evidence"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "guarded-refresh-required",
            validator_runner=no_op_validator,
        )


def test_retained_run_rejects_exclusivity_unproven_when_process_gate_blocked(
    tmp_path: Path,
) -> None:
    repo_root, codex_home, _run_root = write_retained_run(
        tmp_path,
        status="MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN",
        process_gate_status="blocking",
    )

    with pytest.raises(RefreshError, match="process gate"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_rejects_blocked_source_to_certification_delta(
    tmp_path: Path,
) -> None:
    repo_root, codex_home, run_root = write_retained_run(tmp_path)
    evidence_path = run_root / "retained-certification-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["source_to_certification_changed_paths"] = [
        "plugins/turbo-mode/handoff/1.6.0/SKILL.md"
    ]
    write_json(evidence_path, evidence)

    with pytest.raises(RefreshError, match="source-to-certification delta"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=no_op_validator,
        )


def test_retained_run_demotes_published_summary_on_final_validator_failure(
    tmp_path: Path,
) -> None:
    repo_root, codex_home, _run_root = write_retained_run(tmp_path)

    def fail_final(phase: str, _summary: Path, _published: Path) -> None:
        if phase == "candidate":
            write_json(_summary.parent / "metadata-validation.summary.json", {"status": "passed"})
            write_json(_summary.parent / "redaction.summary.json", {"status": "passed"})
        if phase == "final":
            raise RefreshError("forced final failure")

    with pytest.raises(RefreshError, match="forced final failure"):
        retained_run.certify_retained_run(
            run_id="run-1",
            repo_root=repo_root,
            codex_home=codex_home,
            plan_status_collector=lambda: "no-drift",
            validator_runner=fail_final,
        )

    evidence_root = repo_root / "plugins/turbo-mode/evidence/refresh"
    assert not (evidence_root / "run-1.retained.summary.json").exists()
    assert (evidence_root / "run-1.retained.summary.failed.json").is_file()
    status = json.loads(
        (codex_home / "local-only/turbo-mode-refresh/run-1/retained-certification-status.json")
        .read_text(encoding="utf-8")
    )
    assert status["outcome"] == "retained-certification-failed"
    assert status["demoted_summary_path"].endswith("run-1.retained.summary.failed.json")
