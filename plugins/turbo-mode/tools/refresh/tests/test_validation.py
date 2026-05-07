from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from refresh import validation
from refresh.app_server_inventory import AppServerInventoryCheck, CodexRuntimeIdentity
from refresh.commit_safe import (
    build_commit_safe_summary,
    build_current_run_identity_from_paths,
    ensure_relevant_worktree_clean,
    sha256_file,
    sha256_payload,
)
from refresh.evidence import write_local_evidence
from refresh.models import (
    CoverageState,
    FilesystemState,
    PlanAxes,
    PreflightState,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.planner import RefreshPaths, RefreshPlanResult
from refresh.validation import (
    assert_commit_safe_payload,
    projected_summary_for_validator_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
METADATA_TOOL = REPO_ROOT / "plugins/turbo-mode/tools/refresh_validate_run_metadata.py"
REDACTION_TOOL = REPO_ROOT / "plugins/turbo-mode/tools/refresh_validate_redaction.py"
TOOL_REL = Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py")


def test_validation_plan06_schema_constant() -> None:
    assert validation.EXPECTED_COMMIT_SAFE_SCHEMA_VERSION == (
        "turbo-mode-refresh-commit-safe-plan-06"
    )


def test_commit_safe_accepts_prior_plan_reason_code_under_plan06_schema() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-06",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "covered",
            "runtime_config_state": "aligned",
            "preflight_state": "passed",
            "selected_mutation_mode": "guarded-refresh",
            "reason_codes": ["handoff-state-helper-direct-python-doc-migration"],
            "reason_count": 1,
        },
    }

    assert_commit_safe_payload(payload)


def test_commit_safe_rejects_plan04_schema_with_plan05_reason_code() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "covered",
            "runtime_config_state": "aligned",
            "preflight_state": "passed",
            "selected_mutation_mode": "guarded-refresh",
            "reason_codes": ["handoff-state-helper-direct-python-doc-migration"],
            "reason_count": 1,
        },
    }

    with pytest.raises(ValueError, match="invalid schema_version"):
        assert_commit_safe_payload(payload)


def test_commit_safe_rejects_stale_plan04_omission_reason_under_plan06_schema() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-06",
        "run_id": "run-1",
        "omission_reasons": {
            "raw_app_server_transcript": "local-only",
            "process_gate": "outside-plan-04",
        },
    }

    with pytest.raises(ValueError, match="invalid omission reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_raw_transcript_key() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "app_server_transcript": [{"body": {"id": 0}}],
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_unknown_raw_payload_shape() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "debug_payload": [{"jsonrpc": "2.0"}],
    }

    with pytest.raises(ValueError, match="unknown key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_token_like_values() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "codex_version": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
    }

    with pytest.raises(ValueError, match="sensitive value"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_axes_reasons_bypass() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "coverage-gap",
            "runtime_config_state": "aligned",
            "preflight_state": "blocked",
            "selected_mutation_mode": "none",
            "reasons": ["response returned error: ghp_abcdefghijklmnopqrstuvwxyz1234567890"],
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_unknown_reason_code_value() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "coverage-gap",
            "runtime_config_state": "aligned",
            "preflight_state": "blocked",
            "selected_mutation_mode": "none",
            "reason_codes": ["/Users/jp/.codex/raw/path/from/exception"],
            "reason_count": 1,
        },
    }

    with pytest.raises(ValueError, match="invalid reason code"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_reason_count_mismatch() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "coverage-gap",
            "runtime_config_state": "aligned",
            "preflight_state": "blocked",
            "selected_mutation_mode": "none",
            "reason_codes": ["app-server-returned-error"],
            "reason_count": 2,
        },
    }

    with pytest.raises(ValueError, match="reason count mismatch"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_invalid_failure_reason_code() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "app_server_inventory_failure_reason_code": "/private/tmp/raw-failure",
    }

    with pytest.raises(ValueError, match="invalid inventory failure reason code"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_invalid_unavailable_reason() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "current_run_identity": {
            "source_manifest_sha256": None,
            "source_manifest_unavailable_reason": "/private/tmp/raw-error",
        },
    }

    with pytest.raises(ValueError, match="invalid unavailable reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_top_level_executable_hash_unavailable_reason() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "codex_executable_hash_unavailable_reason": (
            "[Errno 13] Permission denied: '/Users/jp/.codex/bin/codex'"
        ),
    }

    with pytest.raises(ValueError, match="invalid unavailable reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_nested_executable_hash_unavailable_reason() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "current_run_identity": {
            "runtime_identity": {
                "codex_executable_hash_unavailable_reason": (
                    "[Errno 13] Permission denied: '/Users/jp/.codex/bin/codex'"
                ),
            },
        },
    }

    with pytest.raises(ValueError, match="invalid unavailable reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_current_run_identity_unknown_key() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "current_run_identity": {
            "local_summary_schema_version": "turbo-mode-refresh-plan-03",
            "transcript_status_summary": {"response": {"body": "raw app-server payload"}},
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_dirty_state_hidden_config_payload() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "dirty_state": {
            "status": "clean-relevant-paths",
            "relevant_paths_checked": ["plugins/turbo-mode/tools/refresh"],
            "post_commit_binding": False,
            "config_shadow": {"token": "not-allowed-even-without-token-shape"},
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_server_info_extra_payload() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "app_server_server_info": {
            "name": "codex-app-server",
            "version": "0.test",
            "response_status": {"id": 0, "result": {"body": "raw"}},
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_capabilities_extra_payload() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "app_server_protocol_capabilities": {
            "experimentalApi": True,
            "workspaceRoots": ["/Users/jp/.codex/raw"],
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_omission_reason_extra_key() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "omission_reasons": {
            "raw_app_server_transcript": "local-only",
            "config_contents": "local-only",
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_validator_projection_nulls_validator_digests() -> None:
    payload = {
        "metadata_validation_summary_sha256": "abc",
        "redaction_validation_summary_sha256": "def",
        "run_id": "run-1",
    }

    projected = projected_summary_for_validator_digest(payload)

    assert projected["metadata_validation_summary_sha256"] is None
    assert projected["redaction_validation_summary_sha256"] is None
    assert projected["run_id"] == "run-1"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def init_refresh_repo(tmp_path: Path) -> tuple[Path, Path, RefreshPlanResult]:
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / ".codex"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
    marketplace = repo_root / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "turbo-mode",
                "plugins": [
                    {
                        "name": "handoff",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/handoff/1.6.0",
                        },
                    },
                    {
                        "name": "ticket",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/ticket/1.4.0",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    config = codex_home / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )
    for base in (
        repo_root / "plugins/turbo-mode/handoff/1.6.0",
        repo_root / "plugins/turbo-mode/ticket/1.4.0",
        codex_home / "plugins/cache/turbo-mode/handoff/1.6.0",
        codex_home / "plugins/cache/turbo-mode/ticket/1.4.0",
    ):
        base.mkdir(parents=True)
        (base / "README.md").write_text("same\n", encoding="utf-8")
    for rel in (
        TOOL_REL,
        Path("plugins/turbo-mode/tools/refresh_validate_run_metadata.py"),
        Path("plugins/turbo-mode/tools/refresh_validate_redaction.py"),
        Path("plugins/turbo-mode/tools/refresh/__init__.py"),
    ):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test tool\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo_root, check=True)
    paths = RefreshPaths(
        repo_root=repo_root.resolve(),
        codex_home=codex_home.resolve(),
        marketplace_path=marketplace.resolve(),
        config_path=config.resolve(),
        local_only_root=(codex_home / "local-only/turbo-mode-refresh").resolve(),
    )
    axes = PlanAxes(
        filesystem_state=FilesystemState.NO_DRIFT,
        coverage_state=CoverageState.NOT_APPLICABLE,
        runtime_config_state=RuntimeConfigState.UNCHECKED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.NONE,
    )
    result = RefreshPlanResult(
        mode="dry-run",
        paths=paths,
        residue_issues=(),
        diffs=(),
        diff_classification=(),
        runtime_config=None,
        axes=axes,
        terminal_status=TerminalPlanStatus.FILESYSTEM_NO_DRIFT,
    )
    return repo_root, codex_home, result


def git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def build_candidate_summary(tmp_path: Path) -> dict[str, object]:
    repo_root, codex_home, result = init_refresh_repo(tmp_path)
    run_id = "run-1"
    local_summary = write_local_evidence(result, run_id=run_id)
    run_root = local_summary.parent
    payload = build_commit_safe_summary(
        result,
        run_id=run_id,
        local_summary_path=local_summary,
        repo_head=git(repo_root, "rev-parse", "HEAD"),
        repo_tree=git(repo_root, "rev-parse", "HEAD^{tree}"),
        tool_path=TOOL_REL,
        tool_sha256=sha256_file(repo_root / TOOL_REL),
        dirty_state=ensure_relevant_worktree_clean(repo_root),
        metadata_validation_summary_sha256=None,
        redaction_validation_summary_sha256=None,
    )
    candidate = run_root / "commit-safe.candidate.summary.json"
    write_json(candidate, payload)
    return {
        "repo_root": repo_root,
        "codex_home": codex_home,
        "run_root": run_root,
        "candidate": candidate,
        "payload": payload,
        "published": repo_root / "plugins/turbo-mode/evidence/refresh/run-1.summary.json",
    }


def inventory_fixture(*, version: str, hook_command: str) -> AppServerInventoryCheck:
    identity = CodexRuntimeIdentity(
        codex_version=version,
        executable_path="/opt/homebrew/bin/codex",
        executable_sha256="0" * 64,
        executable_hash_unavailable_reason=None,
        server_info={"name": "codex-app-server", "version": version},
        initialize_capabilities={"experimentalApi": True},
    )
    return AppServerInventoryCheck(
        state="aligned",
        identity=identity,
        plugin_read_sources={
            "handoff": "/repo/plugins/turbo-mode/handoff/1.6.0",
            "ticket": "/repo/plugins/turbo-mode/ticket/1.4.0",
        },
        plugin_list=("handoff@turbo-mode", "ticket@turbo-mode"),
        skills=("handoff:save", "ticket:ticket"),
        ticket_hook={
            "plugin_id": "ticket@turbo-mode",
            "event_name": "preToolUse",
            "matcher": "Bash",
            "command": hook_command,
            "source_path": "/cache/hooks/hooks.json",
        },
        handoff_hooks=(),
        request_methods=(
            "initialize",
            "initialized",
            "plugin/read",
            "plugin/read",
            "plugin/list",
            "skills/list",
            "hooks/list",
        ),
        transcript_sha256="1" * 64,
    )


def test_current_run_identity_recollects_collected_inventory(tmp_path: Path) -> None:
    repo_root, codex_home, _result = init_refresh_repo(tmp_path)
    stale_inventory = inventory_fixture(version="codex-cli stale", hook_command="old")
    current_inventory = inventory_fixture(version="codex-cli current", hook_command="new")
    local_summary = {
        "schema_version": "turbo-mode-refresh-plan-03",
        "run_id": "run-1",
        "mode": "dry-run",
        "app_server_inventory_status": "collected",
        "app_server_inventory": {
            "state": stale_inventory.state,
            "identity": {
                "codex_version": stale_inventory.identity.codex_version,
                "executable_path": stale_inventory.identity.executable_path,
                "executable_sha256": stale_inventory.identity.executable_sha256,
                "executable_hash_unavailable_reason": (
                    stale_inventory.identity.executable_hash_unavailable_reason
                ),
                "server_info": stale_inventory.identity.server_info,
                "initialize_capabilities": stale_inventory.identity.initialize_capabilities,
                "parser_version": stale_inventory.identity.parser_version,
                "accepted_response_schema_version": (
                    stale_inventory.identity.accepted_response_schema_version
                ),
            },
            "plugin_read_sources": stale_inventory.plugin_read_sources,
            "plugin_list": list(stale_inventory.plugin_list),
            "skills": list(stale_inventory.skills),
            "ticket_hook": stale_inventory.ticket_hook,
            "handoff_hooks": list(stale_inventory.handoff_hooks),
            "request_methods": list(stale_inventory.request_methods),
            "reasons": list(stale_inventory.reasons),
        },
    }

    current_identity = build_current_run_identity_from_paths(
        repo_root=repo_root,
        codex_home=codex_home,
        run_id="run-1",
        local_summary=local_summary,
        inventory_collector=lambda _paths: current_inventory,
    )

    assert current_identity["runtime_identity"]["codex_version"] == "codex-cli current"
    assert current_identity["runtime_identity_freshness"] == "recomputed-readonly-inventory"
    assert current_identity["app_server_inventory_freshness"] == (
        "recomputed-readonly-inventory"
    )
    assert current_identity["app_server_inventory_summary_sha256"] != sha256_payload(
        {
            "state": stale_inventory.state,
            "plugin_read_sources": dict(stale_inventory.plugin_read_sources),
            "plugin_list": list(stale_inventory.plugin_list),
            "skills": list(stale_inventory.skills),
            "ticket_hook": dict(stale_inventory.ticket_hook),
            "handoff_hooks": [dict(item) for item in stale_inventory.handoff_hooks],
            "request_methods": list(stale_inventory.request_methods),
            "reasons": [],
        }
    )


def run_metadata(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(METADATA_TOOL), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def run_redaction(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REDACTION_TOOL), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def common_args(case: dict[str, object], *, summary: Path, mode: str) -> list[str]:
    return [
        "--run-id",
        "run-1",
        "--repo-root",
        str(case["repo_root"]),
        "--mode",
        mode,
        "--local-only-root",
        str(case["run_root"]),
        "--summary",
        str(summary),
        "--published-summary-path",
        str(case["published"]),
    ]


def test_validator_scripts_candidate_and_final_flow(tmp_path: Path) -> None:
    case = build_candidate_summary(tmp_path)
    run_root = case["run_root"]
    candidate = case["candidate"]
    published = case["published"]
    metadata_summary = run_root / "metadata-validation.summary.json"
    redaction_summary = run_root / "redaction.summary.json"
    metadata = run_metadata(
        [
            *common_args(case, summary=candidate, mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )
    assert metadata.returncode == 0, metadata.stderr
    metadata_payload = json.loads(metadata_summary.read_text(encoding="utf-8"))
    assert metadata_payload["status"] == "passed"
    assert metadata_payload["candidate_summary_sha256"] == sha256_file(candidate)
    assert metadata_payload["validated_payload_projection_sha256"] == sha256_payload(
        projected_summary_for_validator_digest(case["payload"])
    )

    redaction = run_redaction(
        [
            "--run-id",
            "run-1",
            "--repo-root",
            str(case["repo_root"]),
            "--mode",
            "candidate",
            "--scope",
            "refresh-plan-04",
            "--source",
            "worktree",
            "--summary",
            str(candidate),
            "--local-only-root",
            str(run_root),
            "--published-summary-path",
            str(published),
            "--summary-output",
            str(redaction_summary),
            "--validate-own-summary",
        ]
    )
    assert redaction.returncode == 0, redaction.stderr
    redaction_payload = json.loads(redaction_summary.read_text(encoding="utf-8"))
    assert redaction_payload["status"] == "passed"
    assert redaction_payload["candidate_summary_sha256"] == sha256_file(candidate)
    assert redaction_payload["validated_payload_projection_sha256"] == sha256_payload(
        projected_summary_for_validator_digest(case["payload"])
    )
    candidate_mtime = redaction_summary.stat().st_mtime_ns

    final_payload = {
        **case["payload"],
        "metadata_validation_summary_sha256": sha256_file(metadata_summary),
        "redaction_validation_summary_sha256": sha256_file(redaction_summary),
    }
    final_summary = run_root / "commit-safe.final.summary.json"
    write_json(final_summary, final_payload)
    final_metadata = run_metadata(
        [
            *common_args(case, summary=final_summary, mode="final"),
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(metadata_summary),
        ]
    )
    assert final_metadata.returncode == 0, final_metadata.stderr
    final_scan = run_root / "redaction-final-scan.summary.json"
    final_redaction = run_redaction(
        [
            "--run-id",
            "run-1",
            "--repo-root",
            str(case["repo_root"]),
            "--mode",
            "final",
            "--scope",
            "refresh-plan-04",
            "--source",
            "worktree",
            "--summary",
            str(final_summary),
            "--local-only-root",
            str(run_root),
            "--published-summary-path",
            str(published),
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(redaction_summary),
            "--final-scan-output",
            str(final_scan),
        ]
    )
    assert final_redaction.returncode == 0, final_redaction.stderr
    assert redaction_summary.stat().st_mtime_ns == candidate_mtime
    assert json.loads(final_scan.read_text(encoding="utf-8"))["status"] == "passed"


def guarded_payload(case: dict[str, object]) -> dict[str, object]:
    source_head = git(case["repo_root"], "rev-parse", "HEAD")
    source_tree = git(case["repo_root"], "rev-parse", "HEAD^{tree}")
    return {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-06",
        "run_id": "run-1",
        "mode": "guarded-refresh",
        "source_implementation_commit": source_head,
        "source_implementation_tree": source_tree,
        "execution_head": source_head,
        "execution_tree": source_tree,
        "tool_path": "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
        "tool_sha256": sha256_file(case["repo_root"] / TOOL_REL),
        "dirty_state_policy": "fail-relevant-dirty-state",
        "dirty_state": {
            "status": "clean-relevant-paths",
            "relevant_paths_checked": sorted(validation.ALLOWED_DIRTY_RELEVANT_PATHS),
            "post_commit_binding": False,
        },
        "local_only_evidence_root": str(case["run_root"]),
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
        "metadata_validation_summary_sha256": None,
        "redaction_validation_summary_sha256": None,
    }


def guarded_common_args(
    case: dict[str, object],
    *,
    summary: Path,
    mode: str,
) -> list[str]:
    return [
        "--run-id",
        "run-1",
        "--source-code-root",
        str(case["repo_root"]),
        "--execution-repo-root",
        str(case["repo_root"]),
        "--mode",
        mode,
        "--local-only-root",
        str(case["run_root"]),
        "--summary",
        str(summary),
        "--published-summary-path",
        str(case["published"]),
    ]


def test_guarded_refresh_validator_requires_split_root_cli(tmp_path: Path) -> None:
    case = build_candidate_summary(tmp_path)
    guarded = guarded_payload(case)
    summary = case["run_root"] / "guarded.summary.json"
    write_json(summary, guarded)
    metadata_summary = case["run_root"] / "guarded-metadata.summary.json"

    legacy = run_metadata(
        [
            "--run-id",
            "run-1",
            "--repo-root",
            str(case["repo_root"]),
            "--mode",
            "candidate",
            "--local-only-root",
            str(case["run_root"]),
            "--summary",
            str(summary),
            "--published-summary-path",
            str(case["published"]),
            "--summary-output",
            str(metadata_summary),
        ]
    )
    assert legacy.returncode == 1
    assert "--source-code-root" in legacy.stderr

    split = run_metadata(
        [
            *guarded_common_args(case, summary=summary, mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )
    assert split.returncode == 0, split.stderr
    payload = json.loads(metadata_summary.read_text(encoding="utf-8"))
    assert payload["source_code_root_role"] == "validator-and-source"
    assert payload["execution_repo_root_role"] == "runtime-and-dirty-state"


def test_guarded_refresh_redaction_validator_requires_split_root_cli(
    tmp_path: Path,
) -> None:
    case = build_candidate_summary(tmp_path)
    guarded = guarded_payload(case)
    summary = case["run_root"] / "commit-safe.candidate.summary.json"
    write_json(summary, guarded)
    write_json(case["run_root"] / "guarded-refresh.summary.json", {"mode": "guarded-refresh"})
    write_json(case["run_root"] / "metadata-validation.summary.json", {"status": "passed"})
    redaction_summary = case["run_root"] / "guarded-redaction.summary.json"

    legacy = run_redaction(
        [
            "--run-id",
            "run-1",
            "--repo-root",
            str(case["repo_root"]),
            "--mode",
            "candidate",
            "--scope",
            "commit-safe-summary",
            "--source",
            "plan-06-cli",
            "--summary",
            str(summary),
            "--local-only-root",
            str(case["run_root"]),
            "--published-summary-path",
            str(case["published"]),
            "--summary-output",
            str(redaction_summary),
        ]
    )
    assert legacy.returncode == 1
    assert "--source-code-root" in legacy.stderr

    split = run_redaction(
        [
            "--run-id",
            "run-1",
            "--source-code-root",
            str(case["repo_root"]),
            "--execution-repo-root",
            str(case["repo_root"]),
            "--mode",
            "candidate",
            "--scope",
            "commit-safe-summary",
            "--source",
            "plan-06-cli",
            "--summary",
            str(summary),
            "--local-only-root",
            str(case["run_root"]),
            "--published-summary-path",
            str(case["published"]),
            "--summary-output",
            str(redaction_summary),
        ]
    )
    assert split.returncode == 0, split.stderr


def test_guarded_final_replay_allows_only_published_summary_dirty_path(
    tmp_path: Path,
) -> None:
    case = build_candidate_summary(tmp_path)
    guarded = guarded_payload(case)
    candidate = case["run_root"] / "guarded.candidate.summary.json"
    write_json(candidate, guarded)
    metadata_summary = case["run_root"] / "guarded-metadata.summary.json"
    metadata = run_metadata(
        [
            *guarded_common_args(case, summary=candidate, mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )
    assert metadata.returncode == 0, metadata.stderr
    final_payload = {
        **guarded,
        "metadata_validation_summary_sha256": sha256_file(metadata_summary),
    }
    final_summary = case["run_root"] / "guarded.final.summary.json"
    write_json(final_summary, final_payload)
    published = case["published"]
    published.parent.mkdir(parents=True, exist_ok=True)
    published.write_text("published dirty\n", encoding="utf-8")

    allowed = run_metadata(
        [
            *guarded_common_args(case, summary=final_summary, mode="final"),
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(metadata_summary),
        ]
    )
    assert allowed.returncode == 0, allowed.stderr

    extra_dirty = case["repo_root"] / "plugins/turbo-mode/tools/refresh/extra.py"
    extra_dirty.write_text("# dirty\n", encoding="utf-8")
    rejected = run_metadata(
        [
            *guarded_common_args(case, summary=final_summary, mode="final"),
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(metadata_summary),
        ]
    )
    assert rejected.returncode == 1
    assert "relevant paths dirty" in rejected.stderr


def test_retained_run_metadata_uses_certification_identity_for_split_root(
    tmp_path: Path,
) -> None:
    case = build_candidate_summary(tmp_path)
    guarded = guarded_payload(case)
    retained = {
        **guarded,
        "certification_mode": "retained-run",
        "certification_source_commit": guarded["source_implementation_commit"],
        "certification_source_tree": guarded["source_implementation_tree"],
        "certification_execution_head": guarded["execution_head"],
        "certification_execution_tree": guarded["execution_tree"],
        "retained_summary_path": (
            "plugins/turbo-mode/evidence/refresh/run-1.retained.summary.json"
        ),
        "original_run_final_status": "MUTATION_COMPLETE_EVIDENCE_FAILED",
        "retained_certification_outcome": "retained-certified",
        "prior_summary_path_state": "none",
        "retained_no_mutation_proof_sha256": "1" * 64,
        "rehearsal_proof_capture_manifest_sha256": "2" * 64,
        "prior_failed_summary_path": None,
        "prior_failed_summary_sha256": None,
        "prior_failed_summary_status": None,
    }
    retained["source_implementation_commit"] = "0" * 40
    retained["source_implementation_tree"] = "0" * 40
    summary = case["run_root"] / "retained.candidate.summary.json"
    write_json(summary, retained)
    metadata_summary = case["run_root"] / "retained-metadata.summary.json"

    completed = run_metadata(
        [
            *guarded_common_args(case, summary=summary, mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(metadata_summary.read_text(encoding="utf-8"))
    assert payload["certification_mode"] == "retained-run"
    assert payload["certification_source_commit"] == retained["certification_source_commit"]


def test_retained_final_replay_allows_only_retained_summary_dirty_path(
    tmp_path: Path,
) -> None:
    case = build_candidate_summary(tmp_path)
    retained_published = (
        case["repo_root"] / "plugins/turbo-mode/evidence/refresh/run-1.retained.summary.json"
    )
    case = {**case, "published": retained_published}
    retained = {
        **guarded_payload(case),
        "certification_mode": "retained-run",
        "certification_source_commit": git(case["repo_root"], "rev-parse", "HEAD"),
        "certification_source_tree": git(case["repo_root"], "rev-parse", "HEAD^{tree}"),
        "certification_execution_head": git(case["repo_root"], "rev-parse", "HEAD"),
        "certification_execution_tree": git(case["repo_root"], "rev-parse", "HEAD^{tree}"),
        "retained_summary_path": (
            "plugins/turbo-mode/evidence/refresh/run-1.retained.summary.json"
        ),
        "original_run_final_status": "MUTATION_COMPLETE_EVIDENCE_FAILED",
        "retained_certification_outcome": "retained-certified",
        "prior_summary_path_state": "none",
        "retained_no_mutation_proof_sha256": "1" * 64,
        "rehearsal_proof_capture_manifest_sha256": "2" * 64,
        "prior_failed_summary_path": None,
        "prior_failed_summary_sha256": None,
        "prior_failed_summary_status": None,
    }
    candidate = case["run_root"] / "retained.candidate.summary.json"
    write_json(candidate, retained)
    metadata_summary = case["run_root"] / "retained-metadata.summary.json"
    metadata = run_metadata(
        [
            *guarded_common_args(case, summary=candidate, mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )
    assert metadata.returncode == 0, metadata.stderr
    final_payload = {
        **retained,
        "metadata_validation_summary_sha256": sha256_file(metadata_summary),
    }
    final_summary = case["run_root"] / "retained.final.summary.json"
    write_json(final_summary, final_payload)
    retained_published.parent.mkdir(parents=True, exist_ok=True)
    retained_published.write_text("published dirty\n", encoding="utf-8")

    allowed = run_metadata(
        [
            *guarded_common_args(case, summary=final_summary, mode="final"),
            "--candidate-summary",
            str(candidate),
            "--existing-validation-summary",
            str(metadata_summary),
        ]
    )

    assert allowed.returncode == 0, allowed.stderr


def test_metadata_validator_rejects_stale_existing_candidate_summary(tmp_path: Path) -> None:
    case = build_candidate_summary(tmp_path)
    metadata_summary = case["run_root"] / "metadata-validation.summary.json"
    completed = run_metadata(
        [
            *common_args(case, summary=case["candidate"], mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    existing = json.loads(metadata_summary.read_text(encoding="utf-8"))
    existing["repo_head"] = "stale"
    metadata_summary.unlink()
    write_json(metadata_summary, existing)
    final_payload = {
        **case["payload"],
        "metadata_validation_summary_sha256": sha256_file(metadata_summary),
        "redaction_validation_summary_sha256": None,
    }
    final_summary = case["run_root"] / "commit-safe.final.summary.json"
    write_json(final_summary, final_payload)

    rejected = run_metadata(
        [
            *common_args(case, summary=final_summary, mode="final"),
            "--candidate-summary",
            str(case["candidate"]),
            "--existing-validation-summary",
            str(metadata_summary),
        ]
    )

    assert rejected.returncode == 1


@pytest.mark.parametrize(
    "dirty_path",
    [
        "plugins/turbo-mode/handoff/1.6.0/README.md",
        "plugins/turbo-mode/ticket/1.4.0/README.md",
    ],
)
def test_metadata_validator_rejects_dirty_plugin_source_paths(
    tmp_path: Path,
    dirty_path: str,
) -> None:
    case = build_candidate_summary(tmp_path)
    metadata_summary = case["run_root"] / "metadata-validation.summary.json"
    (case["repo_root"] / dirty_path).write_text("dirty\n", encoding="utf-8")

    rejected = run_metadata(
        [
            *common_args(case, summary=case["candidate"], mode="candidate"),
            "--summary-output",
            str(metadata_summary),
        ]
    )

    assert rejected.returncode == 1
    assert "relevant paths dirty" in rejected.stderr


def test_metadata_validator_rejects_recomputed_dirty_relevant_paths(tmp_path: Path) -> None:
    case = build_candidate_summary(tmp_path)
    dirty = case["repo_root"] / "plugins/turbo-mode/tools/refresh/__init__.py"
    dirty.write_text("# dirty\n", encoding="utf-8")

    rejected = run_metadata(
        [
            *common_args(case, summary=case["candidate"], mode="candidate"),
            "--summary-output",
            str(case["run_root"] / "metadata-validation.summary.json"),
        ]
    )

    assert rejected.returncode == 1
    assert "relevant paths dirty" in rejected.stderr


def test_redaction_validator_rejects_raw_transcript_and_marketplace_plugin_keys(
    tmp_path: Path,
) -> None:
    case = build_candidate_summary(tmp_path)
    metadata = run_metadata(
        [
            *common_args(case, summary=case["candidate"], mode="candidate"),
            "--summary-output",
            str(case["run_root"] / "metadata-validation.summary.json"),
        ]
    )
    assert metadata.returncode == 0, metadata.stderr
    payload = {**case["payload"], "app_server_transcript": [{"body": {"id": 0}}]}
    bad_summary = case["run_root"] / "bad.summary.json"
    write_json(bad_summary, payload)

    rejected = run_redaction(
        [
            "--run-id",
            "run-1",
            "--repo-root",
            str(case["repo_root"]),
            "--mode",
            "candidate",
            "--scope",
            "refresh-plan-04",
            "--source",
            "worktree",
            "--summary",
            str(bad_summary),
            "--local-only-root",
            str(case["run_root"]),
            "--published-summary-path",
            str(case["published"]),
            "--summary-output",
            str(case["run_root"] / "redaction.summary.json"),
        ]
    )
    assert rejected.returncode == 1
    assert "forbidden key" in rejected.stderr

    plugin_key_payload = {
        **case["payload"],
        "runtime_config": {
            "state": "aligned",
            "marketplace_state": "aligned",
            "plugin_hooks_state": "true",
            "plugin_enablement_state": {"handoff": "enabled", "ticket": "enabled"},
            "reason_codes": [],
            "reason_count": 0,
        },
    }
    bad_keys = case["run_root"] / "bad-plugin-keys.summary.json"
    write_json(bad_keys, plugin_key_payload)
    rejected_keys = run_redaction(
        [
            "--run-id",
            "run-1",
            "--repo-root",
            str(case["repo_root"]),
            "--mode",
            "candidate",
            "--scope",
            "refresh-plan-04",
            "--source",
            "worktree",
            "--summary",
            str(bad_keys),
            "--local-only-root",
            str(case["run_root"]),
            "--published-summary-path",
            str(case["published"]),
            "--summary-output",
            str(case["run_root"] / "redaction-2.summary.json"),
        ]
    )
    assert rejected_keys.returncode == 1
    assert "forbidden key" in rejected_keys.stderr


def test_validator_summary_write_rejects_missing_or_non_private_parent(tmp_path: Path) -> None:
    case = build_candidate_summary(tmp_path)
    missing_parent = tmp_path / "missing/metadata.summary.json"
    rejected_missing = run_metadata(
        [
            *common_args(case, summary=case["candidate"], mode="candidate"),
            "--summary-output",
            str(missing_parent),
        ]
    )
    assert rejected_missing.returncode == 1
    assert "parent directory does not exist" in rejected_missing.stderr

    broad_parent = tmp_path / "broad"
    broad_parent.mkdir()
    os.chmod(broad_parent, 0o755)
    rejected_mode = run_metadata(
        [
            *common_args(case, summary=case["candidate"], mode="candidate"),
            "--summary-output",
            str(broad_parent / "metadata.summary.json"),
        ]
    )
    assert rejected_mode.returncode == 1
    assert "parent directory must be 0700" in rejected_mode.stderr
