from __future__ import annotations

import pytest
from refresh.models import (
    CoverageState,
    FilesystemState,
    PlanAxes,
    PreflightState,
    RefreshError,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.state_machine import derive_terminal_plan_status


@pytest.mark.parametrize(
    ("axes", "expected"),
    [
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERAGE_GAP,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.BLOCKED,
                selected_mutation_mode=SelectedMutationMode.REFRESH,
            ),
            TerminalPlanStatus.BLOCKED_PREFLIGHT,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERAGE_GAP,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.REFRESH,
            ),
            TerminalPlanStatus.COVERAGE_GAP_BLOCKED,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            ),
            TerminalPlanStatus.UNREPAIRABLE_RUNTIME_CONFIG_MISMATCH,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.REPAIRABLE_MISMATCH,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
            ),
            TerminalPlanStatus.REPAIRABLE_RUNTIME_CONFIG_MISMATCH,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERED,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
            ),
            TerminalPlanStatus.GUARDED_REFRESH_REQUIRED,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERED,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.REFRESH,
            ),
            TerminalPlanStatus.REFRESH_ALLOWED,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            ),
            TerminalPlanStatus.NO_DRIFT,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.UNCHECKED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            ),
            TerminalPlanStatus.FILESYSTEM_NO_DRIFT,
        ),
    ],
)
def test_terminal_status_precedence(axes: PlanAxes, expected: TerminalPlanStatus) -> None:
    assert derive_terminal_plan_status(axes) == expected


def test_drift_with_unchecked_runtime_config_fails_closed() -> None:
    axes = PlanAxes(
        filesystem_state=FilesystemState.DRIFT,
        coverage_state=CoverageState.COVERED,
        runtime_config_state=RuntimeConfigState.UNCHECKED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.REFRESH,
    )

    assert derive_terminal_plan_status(axes) == TerminalPlanStatus.BLOCKED_PREFLIGHT


@pytest.mark.parametrize(
    "axes",
    [
        PlanAxes(
            filesystem_state=FilesystemState.UNKNOWN,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.UNKNOWN,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.UNKNOWN,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.UNKNOWN,
        ),
    ],
)
def test_unknown_axes_fail_closed_to_blocked_preflight(axes: PlanAxes) -> None:
    assert derive_terminal_plan_status(axes) == TerminalPlanStatus.BLOCKED_PREFLIGHT


def test_preflight_block_takes_precedence_over_unknown_axes() -> None:
    axes = PlanAxes(
        filesystem_state=FilesystemState.UNKNOWN,
        coverage_state=CoverageState.UNKNOWN,
        runtime_config_state=RuntimeConfigState.UNKNOWN,
        preflight_state=PreflightState.BLOCKED,
        selected_mutation_mode=SelectedMutationMode.UNKNOWN,
    )

    assert derive_terminal_plan_status(axes) == TerminalPlanStatus.BLOCKED_PREFLIGHT


@pytest.mark.parametrize(
    "axes",
    [
        PlanAxes(
            filesystem_state=FilesystemState.NO_DRIFT,
            coverage_state=CoverageState.NOT_APPLICABLE,
            runtime_config_state=RuntimeConfigState.REPAIRABLE_MISMATCH,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.NONE,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.NO_DRIFT,
            coverage_state=CoverageState.NOT_APPLICABLE,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.NOT_APPLICABLE,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.NOT_APPLICABLE,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
        ),
    ],
)
def test_inconsistent_axes_raise_refresh_error(axes: PlanAxes) -> None:
    with pytest.raises(RefreshError):
        derive_terminal_plan_status(axes)
