from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from refresh.app_server_inventory import AppServerInventoryCheck, CodexRuntimeIdentity
from refresh.evidence import evidence_payload, write_local_evidence
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


def test_evidence_payload_serializes_axes_and_terminal_status(tmp_path: Path) -> None:
    payload = evidence_payload(empty_result(tmp_path), run_id="run-1")

    assert payload["schema_version"] == "turbo-mode-refresh-plan-03"
    assert payload["run_id"] == "run-1"
    assert payload["mode"] == "dry-run"
    assert payload["terminal_plan_status"] == "filesystem-no-drift"
    assert payload["app_server_inventory_status"] == "not-requested"
    assert payload["app_server_inventory_failure_reason"] is None
    assert payload["axes"]["filesystem_state"] == "no-drift"
    assert payload["omission_reasons"]["app_server_inventory"] == "not-requested"


def test_write_local_evidence_uses_private_permissions(tmp_path: Path) -> None:
    result = empty_result(tmp_path)

    evidence_path = write_local_evidence(result, run_id="run-1")

    run_dir_mode = stat.S_IMODE(evidence_path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(evidence_path.stat().st_mode)
    assert run_dir_mode == 0o700
    assert file_mode == 0o600
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["run_id"] == "run-1"


def test_write_local_evidence_rejects_unsafe_run_id(tmp_path: Path) -> None:
    result = empty_result(tmp_path)

    with pytest.raises(ValueError, match="one path segment"):
        write_local_evidence(result, run_id="../escape")


def test_write_local_evidence_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    first = write_local_evidence(result, run_id="run-1")

    with pytest.raises(FileExistsError):
        write_local_evidence(result, run_id="run-1")

    assert json.loads(first.read_text(encoding="utf-8"))["run_id"] == "run-1"


def test_write_local_evidence_rejects_symlinked_run_directory(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    evidence_root = result.paths.local_only_root
    evidence_root.mkdir(parents=True, mode=0o700)
    (evidence_root / "run-1").symlink_to(target, target_is_directory=True)

    with pytest.raises(FileExistsError, match="run directory already exists"):
        write_local_evidence(result, run_id="run-1")


def test_write_local_evidence_rejects_broad_existing_root(tmp_path: Path) -> None:
    result = empty_result(tmp_path)
    result.paths.local_only_root.mkdir(parents=True)
    os.chmod(result.paths.local_only_root, 0o755)

    with pytest.raises(PermissionError, match="evidence root permissions"):
        write_local_evidence(result, run_id="run-1")


def test_write_local_evidence_writes_inventory_transcript_outside_summary(
    tmp_path: Path,
) -> None:
    result = empty_result(tmp_path)
    identity = CodexRuntimeIdentity(
        codex_version="codex-cli 0.test",
        executable_path="/usr/local/bin/codex",
        executable_sha256="abc",
        executable_hash_unavailable_reason=None,
        server_info={"name": "codex-app-server"},
        initialize_capabilities={},
    )
    inventory = AppServerInventoryCheck(
        state="aligned",
        identity=identity,
        plugin_read_sources={},
        plugin_list=(),
        skills=(),
        ticket_hook={},
        handoff_hooks=(),
        request_methods=("initialize",),
        transcript_sha256="abc",
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
        app_server_transcript=({"direction": "recv", "body": {"id": 0}},),
        app_server_inventory_status="collected",
    )

    evidence_path = write_local_evidence(result, run_id="run-1")

    summary = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert "app_server_transcript" not in summary
    assert summary["app_server_inventory"]["state"] == "aligned"
    assert summary["app_server_inventory_status"] == "collected"
    assert summary["omission_reasons"]["app_server_inventory"] == "collected"
    transcript = evidence_path.parent / "app-server-readonly-inventory.transcript.json"
    assert transcript.is_file()
    assert stat.S_IMODE(transcript.stat().st_mode) == 0o600


def test_evidence_payload_distinguishes_requested_failed_inventory(
    tmp_path: Path,
) -> None:
    result = empty_result(tmp_path)
    result = RefreshPlanResult(
        mode=result.mode,
        paths=result.paths,
        residue_issues=result.residue_issues,
        diffs=result.diffs,
        diff_classification=result.diff_classification,
        runtime_config=result.runtime_config,
        axes=result.axes,
        terminal_status=result.terminal_status,
        app_server_inventory_status="requested-failed",
        app_server_inventory_failure_reason="app-server request failed",
    )

    payload = evidence_payload(result, run_id="run-1")

    assert payload["app_server_inventory"] is None
    assert payload["app_server_inventory_status"] == "requested-failed"
    assert payload["app_server_inventory_failure_reason"] == "app-server request failed"
    assert payload["omission_reasons"]["app_server_inventory"] == "requested-failed"
