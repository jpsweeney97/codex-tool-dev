from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from refresh import commit_safe, validation
from refresh.app_server_inventory import AppServerInventoryCheck, CodexRuntimeIdentity
from refresh.commit_safe import (
    SAFE_REASON_CODES,
    build_commit_safe_summary,
    ensure_relevant_worktree_clean,
)
from refresh.evidence import write_local_evidence
from refresh.models import (
    CoverageState,
    CoverageStatus,
    FilesystemState,
    MutationMode,
    PathClassification,
    PathOutcome,
    PlanAxes,
    PreflightState,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.planner import RefreshPaths, RefreshPlanResult, RuntimeConfigCheck

TOOL_PATH = Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py")
MALICIOUS_FAILURE = (
    "response returned error {'body': {'token': 'ghp_abcdefghijklmnopqrstuvwxyz123456', "
    "'path': '/Users/jp/.codex/config.toml', 'email': 'person@example.com'}}"
)


def empty_result(tmp_path: Path) -> RefreshPlanResult:
    paths = RefreshPaths(
        repo_root=tmp_path / "repo",
        codex_home=tmp_path / ".codex",
        marketplace_path=tmp_path / "repo/.agents/plugins/marketplace.json",
        config_path=tmp_path / ".codex/config.toml",
        local_only_root=tmp_path / ".codex/local-only/turbo-mode-refresh",
    )
    axes = PlanAxes(
        filesystem_state=FilesystemState.NO_DRIFT,
        coverage_state=CoverageState.NOT_APPLICABLE,
        runtime_config_state=RuntimeConfigState.UNCHECKED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.NONE,
    )
    return RefreshPlanResult(
        mode="dry-run",
        paths=paths,
        residue_issues=(),
        diffs=(),
        diff_classification=(),
        runtime_config=None,
        axes=axes,
        terminal_status=TerminalPlanStatus.FILESYSTEM_NO_DRIFT,
    )


def build_payload(result: RefreshPlanResult, tmp_path: Path) -> dict[str, object]:
    local_summary = write_local_evidence(result, run_id="run-1")
    return build_commit_safe_summary(
        result,
        run_id="run-1",
        local_summary_path=local_summary,
        repo_head="abc123",
        repo_tree="def456",
        tool_path=TOOL_PATH,
        tool_sha256="tool-sha",
        dirty_state={
            "status": "clean-relevant-paths",
            "relevant_paths_checked": [],
            "post_commit_binding": False,
        },
        metadata_validation_summary_sha256=None,
        redaction_validation_summary_sha256=None,
    )


def test_commit_safe_plan06_constants_and_reason_allowlist() -> None:
    assert commit_safe.COMMIT_SAFE_SCHEMA_VERSION == "turbo-mode-refresh-commit-safe-plan-06"
    assert "handoff-state-helper-direct-python-doc-migration" in commit_safe.SAFE_REASON_CODES
    assert commit_safe.RELEVANT_DIRTY_PATHS == (
        ".agents/plugins/marketplace.json",
        "plugins/turbo-mode/handoff/1.6.0",
        "plugins/turbo-mode/ticket/1.4.0",
        "plugins/turbo-mode/tools/refresh",
        "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
        "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
        "plugins/turbo-mode/tools/refresh_validate_redaction.py",
    )


def test_commit_safe_and_validation_reason_allowlists_match() -> None:
    assert commit_safe.SAFE_REASON_CODES == validation.SAFE_REASON_CODES


@pytest.mark.parametrize(
    "reason",
    [
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
    ],
)
def test_commit_safe_classifier_reasons_have_explicit_codes(reason: str) -> None:
    assert commit_safe._reason_code(reason) == reason


def test_commit_safe_summary_omits_raw_transcript_and_records_omissions(
    tmp_path: Path,
) -> None:
    result = empty_result(tmp_path)

    payload = build_payload(result, tmp_path)

    assert payload["schema_version"] == "turbo-mode-refresh-commit-safe-plan-06"
    assert payload["source_local_summary_schema_version"] == "turbo-mode-refresh-plan-03"
    assert payload["local_only_summary_sha256"]
    assert payload["terminal_plan_status"] == "filesystem-no-drift"
    assert payload["final_status"] == "filesystem-no-drift"
    assert payload["omission_reasons"]["raw_app_server_transcript"] == "local-only"
    assert payload["omission_reasons"]["process_gate"] == "outside-non-mutating-refresh-plan"
    assert "app_server_transcript" not in payload


def test_commit_safe_summary_preserves_prior_plan_reason_code(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    classification = PathClassification(
        canonical_path="handoff/1.6.0/skills/save/SKILL.md",
        mutation_mode=MutationMode.GUARDED,
        coverage_status=CoverageStatus.COVERED,
        outcome=PathOutcome.GUARDED_ONLY,
        reasons=("handoff-state-helper-direct-python-doc-migration",),
        smoke=(
            "handoff-state-helper-docs",
            "handoff-session-state-write-read-clear",
        ),
    )
    result = RefreshPlanResult(
        mode=result.mode,
        paths=result.paths,
        residue_issues=result.residue_issues,
        diffs=result.diffs,
        diff_classification=(classification,),
        runtime_config=result.runtime_config,
        axes=PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
        ),
        terminal_status=TerminalPlanStatus.GUARDED_REFRESH_REQUIRED,
    )

    payload = build_payload(result, tmp_path)

    assert payload["schema_version"] == "turbo-mode-refresh-commit-safe-plan-06"
    assert payload["diff_classification"][0]["reason_codes"] == [
        "handoff-state-helper-direct-python-doc-migration"
    ]


def test_commit_safe_inventory_projection_uses_replay_identity_not_transcript_sha(
    tmp_path: Path,
) -> None:
    result = empty_result(tmp_path)
    identity = CodexRuntimeIdentity(
        codex_version="codex-cli 0.test",
        executable_path="/opt/homebrew/bin/codex",
        executable_sha256="codex-sha",
        executable_hash_unavailable_reason=None,
        server_info={"name": "codex-app-server", "version": "0.test", "path": "/tmp/raw"},
        initialize_capabilities={"experimentalApi": True, "raw": {"body": "drop"}},
    )
    inventory = AppServerInventoryCheck(
        state="aligned",
        identity=identity,
        plugin_read_sources={"handoff": "/raw/source"},
        plugin_list=("handoff@turbo-mode", "ticket@turbo-mode"),
        skills=("handoff:load", "ticket:ticket"),
        ticket_hook={"command": "python3 /raw/ticket_engine_guard.py"},
        handoff_hooks=(),
        request_methods=("initialize", "initialized", "plugin/read"),
        transcript_sha256="raw-transcript-sha",
        reasons=("raw reason should not copy",),
    )
    result = RefreshPlanResult(
        mode=result.mode,
        paths=result.paths,
        residue_issues=result.residue_issues,
        diffs=result.diffs,
        diff_classification=result.diff_classification,
        runtime_config=result.runtime_config,
        axes=result.axes,
        terminal_status=result.terminal_status,
        app_server_inventory=inventory,
        app_server_transcript=(
            {"direction": "recv", "body": {"secret": "ghp_abcdefghijklmnopqrstuvwxyz123456"}},
        ),
        app_server_inventory_status="collected",
    )

    payload = build_payload(result, tmp_path)
    dumped = json.dumps(payload, sort_keys=True)

    assert payload["app_server_request_methods"] == [
        "initialize",
        "initialized",
        "plugin/read",
    ]
    assert payload["app_server_inventory_summary_sha256"]
    assert payload["app_server_inventory_summary_sha256"] != "raw-transcript-sha"
    assert payload["codex_version"] == "codex-cli 0.test"
    assert payload["app_server_parser_version"] == "refresh-app-server-inventory-1"
    assert payload["app_server_response_schema_version"] == "app-server-readonly-inventory-v1"
    assert payload["app_server_server_info"] == {
        "name": "codex-app-server",
        "version": "0.test",
    }
    assert payload["app_server_protocol_capabilities"] == {"experimentalApi": True}
    assert "raw-transcript-sha" not in dumped
    assert "abcdefghijklmnopqrstuvwxyz123456" not in dumped


def test_requested_failed_inventory_reduces_malicious_failure_to_reason_code(
    tmp_path: Path,
) -> None:
    result = empty_result(tmp_path)
    axes = PlanAxes(
        filesystem_state=FilesystemState.UNKNOWN,
        coverage_state=CoverageState.UNKNOWN,
        runtime_config_state=RuntimeConfigState.UNKNOWN,
        preflight_state=PreflightState.BLOCKED,
        selected_mutation_mode=SelectedMutationMode.UNKNOWN,
        reasons=(MALICIOUS_FAILURE,),
    )
    result = RefreshPlanResult(
        mode=result.mode,
        paths=result.paths,
        residue_issues=result.residue_issues,
        diffs=result.diffs,
        diff_classification=result.diff_classification,
        runtime_config=result.runtime_config,
        axes=axes,
        terminal_status=TerminalPlanStatus.BLOCKED_PREFLIGHT,
        app_server_inventory_status="requested-failed",
        app_server_inventory_failure_reason=MALICIOUS_FAILURE,
    )

    payload = build_payload(result, tmp_path)
    dumped = json.dumps(payload, sort_keys=True)

    assert payload["app_server_inventory_failure_reason_code"] == "app-server-returned-error"
    assert "app_server_inventory_failure_reason" not in payload
    assert "ghp_" not in dumped
    assert "person@example.com" not in dumped
    assert "/Users/jp/.codex/config.toml" not in dumped
    assert MALICIOUS_FAILURE not in dumped
    assert payload["axes"]["reason_codes"] == ["app-server-returned-error"]


def test_nested_projection_uses_allowlisted_reason_codes(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    axes = PlanAxes(
        filesystem_state=FilesystemState.DRIFT,
        coverage_state=CoverageState.COVERAGE_GAP,
        runtime_config_state=RuntimeConfigState.REPAIRABLE_MISMATCH,
        preflight_state=PreflightState.BLOCKED,
        selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
        reasons=("runtime config preflight unavailable", "raw unique details /tmp/config"),
    )
    runtime_config = RuntimeConfigCheck(
        state=RuntimeConfigState.REPAIRABLE_MISMATCH,
        marketplace_state="conflicting-source",
        plugin_hooks_state="true",
        plugin_enablement_state={
            "handoff@turbo-mode": "enabled",
            "ticket@turbo-mode": "enabled",
        },
        reasons=("turbo-mode marketplace source mismatch", "local path /Users/jp/source"),
    )
    classification = PathClassification(
        canonical_path="handoff/1.6.0/SKILL.md",
        mutation_mode=MutationMode.BLOCKED,
        coverage_status=CoverageStatus.COVERAGE_GAP,
        outcome=PathOutcome.COVERAGE_GAP_FAIL,
        reasons=("coverage-gap-path", "unmatched custom raw detail"),
        smoke=("smoke-doc",),
    )
    result = RefreshPlanResult(
        mode=result.mode,
        paths=result.paths,
        residue_issues=result.residue_issues,
        diffs=result.diffs,
        diff_classification=(classification,),
        runtime_config=runtime_config,
        axes=axes,
        terminal_status=TerminalPlanStatus.COVERAGE_GAP_BLOCKED,
    )

    payload = build_payload(result, tmp_path)
    dumped = json.dumps(payload, sort_keys=True)

    assert set(payload["axes"]) == {
        "filesystem_state",
        "coverage_state",
        "runtime_config_state",
        "preflight_state",
        "selected_mutation_mode",
        "reason_codes",
        "reason_count",
    }
    assert "reasons" not in payload["axes"]
    assert payload["axes"]["reason_codes"] == [
        "runtime-config-preflight-unavailable",
        "unknown-reason",
    ]
    assert payload["axes"]["reason_count"] == 2
    assert set(payload["runtime_config"]) == {
        "state",
        "marketplace_state",
        "plugin_hooks_state",
        "plugin_enablement_state",
        "reason_codes",
        "reason_count",
    }
    assert "reasons" not in payload["runtime_config"]
    assert payload["runtime_config"]["plugin_enablement_state"] == {
        "handoff@turbo-mode": "enabled",
        "ticket@turbo-mode": "enabled",
    }
    assert payload["runtime_config"]["reason_codes"] == [
        "config-marketplace-source-mismatch",
        "unknown-reason",
    ]
    assert set(payload["diff_classification"][0]) == {
        "canonical_path",
        "mutation_mode",
        "coverage_status",
        "outcome",
        "reason_codes",
        "smoke",
    }
    assert payload["diff_classification"][0]["reason_codes"] == [
        "coverage-gap-path",
        "unknown-reason",
    ]
    assert "raw unique details" not in dumped
    assert "local path" not in dumped
    assert "unmatched custom raw detail" not in dumped
    for container in (
        payload["axes"],
        payload["runtime_config"],
        payload["diff_classification"][0],
    ):
        assert all(code in SAFE_REASON_CODES for code in container["reason_codes"])
        if "reason_count" in container:
            assert container["reason_count"] == len(container["reason_codes"])


def init_repo(repo_root: Path) -> None:
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
    for rel in (
        ".agents/plugins/marketplace.json",
        "plugins/turbo-mode/tools/refresh/existing.py",
        "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
        "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
        "plugins/turbo-mode/tools/refresh_validate_redaction.py",
        "plugins/turbo-mode/handoff/1.6.0/README.md",
        "plugins/turbo-mode/ticket/1.4.0/README.md",
        "docs/readme.md",
    ):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo_root, check=True)


@pytest.mark.parametrize(
    "dirty_path",
    [
        ".agents/plugins/marketplace.json",
        "plugins/turbo-mode/handoff/1.6.0/README.md",
        "plugins/turbo-mode/ticket/1.4.0/README.md",
        "plugins/turbo-mode/tools/refresh/existing.py",
        "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
        "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
        "plugins/turbo-mode/tools/refresh_validate_redaction.py",
    ],
)
def test_relevant_dirty_paths_fail_before_summary_write(
    tmp_path: Path,
    dirty_path: str,
) -> None:
    repo_root = tmp_path / "repo"
    init_repo(repo_root)
    (repo_root / dirty_path).write_text("dirty\n", encoding="utf-8")

    with pytest.raises(ValueError, match="relevant dirty state"):
        ensure_relevant_worktree_clean(repo_root)


def test_unrelated_dirty_file_does_not_fail_relevant_dirty_gate(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_repo(repo_root)
    (repo_root / "docs/readme.md").write_text("dirty\n", encoding="utf-8")

    assert ensure_relevant_worktree_clean(repo_root)["status"] == "clean-relevant-paths"


def test_existing_local_only_run_cannot_be_reused(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    write_local_evidence(result, run_id="run-1")

    with pytest.raises(FileExistsError, match="run directory already exists"):
        write_local_evidence(result, run_id="run-1")


def guarded_refresh_evidence() -> dict[str, object]:
    return {
        "mode": "guarded-refresh",
        "source_implementation_commit": "1" * 40,
        "source_implementation_tree": "2" * 40,
        "execution_head": "1" * 40,
        "execution_tree": "2" * 40,
        "isolated_rehearsal_run_id": "rehearsal-run",
        "rehearsal_proof_sha256": "3" * 64,
        "rehearsal_proof_validation_status": "validated-before-live-mutation",
        "source_to_rehearsal_execution_delta_status": "identical",
        "source_to_rehearsal_allowed_delta_proof_sha256": "4" * 64,
        "source_to_rehearsal_changed_paths_sha256": "5" * 64,
        "isolated_app_server_authority_proof_sha256": "3" * 64,
        "no_real_home_authority_proof_sha256": "3" * 64,
        "pre_snapshot_app_server_launch_authority_sha256": "6" * 64,
        "pre_install_app_server_target_authority_sha256": "7" * 64,
        "live_app_server_authority_proof_sha256": "8" * 64,
        "source_manifest_sha256": "9" * 64,
        "pre_refresh_cache_manifest_sha256": "a" * 64,
        "post_refresh_cache_manifest_sha256": "b" * 64,
        "pre_refresh_config_sha256": "c" * 64,
        "post_refresh_config_sha256": "d" * 64,
        "post_refresh_inventory_sha256": "e" * 64,
        "selected_smoke_tier": "standard",
        "smoke_summary_sha256": "f" * 64,
        "post_mutation_process_census_sha256": "0" * 64,
        "exclusivity_status": "exclusive_window_observed_by_process_samples",
        "phase_reached": "evidence-published",
        "final_status": "MUTATION_COMPLETE_CERTIFIED",
        "rollback_or_restore_status": "not-attempted",
    }


def test_guarded_refresh_commit_safe_summary_uses_plan06_schema_and_required_fields(
    tmp_path: Path,
) -> None:
    evidence = guarded_refresh_evidence()

    payload = commit_safe.build_guarded_refresh_commit_safe_summary(
        evidence,
        run_id="run-1",
        local_only_evidence_root=tmp_path / ".codex/local-only/turbo-mode-refresh/run-1",
        tool_path=TOOL_PATH,
        tool_sha256="tool-sha",
        dirty_state={
            "status": "clean-relevant-paths",
            "relevant_paths_checked": [],
            "post_commit_binding": False,
        },
        metadata_validation_summary_sha256=None,
        redaction_validation_summary_sha256=None,
    )

    assert payload["schema_version"] == "turbo-mode-refresh-commit-safe-plan-06"
    assert payload["mode"] == "guarded-refresh"
    for key, expected in evidence.items():
        assert payload[key] == expected
    assert payload["local_only_evidence_root"].endswith(
        "/local-only/turbo-mode-refresh/run-1"
    )
    assert "raw_process_listing" not in json.dumps(payload, sort_keys=True)


def test_guarded_refresh_summary_requires_validated_rehearsal_proof(
    tmp_path: Path,
) -> None:
    evidence = {
        **guarded_refresh_evidence(),
        "rehearsal_proof_validation_status": "captured-but-not-validated",
    }

    with pytest.raises(ValueError, match="rehearsal proof validation status"):
        commit_safe.build_guarded_refresh_commit_safe_summary(
            evidence,
            run_id="run-1",
            local_only_evidence_root=tmp_path / ".codex/local-only/turbo-mode-refresh/run-1",
            tool_path=TOOL_PATH,
            tool_sha256="tool-sha",
            dirty_state={
                "status": "clean-relevant-paths",
                "relevant_paths_checked": [],
                "post_commit_binding": False,
            },
            metadata_validation_summary_sha256=None,
            redaction_validation_summary_sha256=None,
        )
