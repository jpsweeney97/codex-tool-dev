from __future__ import annotations

from .models import (
    CoverageState,
    FilesystemState,
    PlanAxes,
    PreflightState,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
    fail,
)


def validate_axes(axes: PlanAxes) -> None:
    """Reject inconsistent plan axes that could permit unsafe mutation planning."""
    if (
        axes.runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH
        and axes.selected_mutation_mode != SelectedMutationMode.GUARDED_REFRESH
    ):
        fail(
            "validate plan axes",
            "repairable runtime config mismatch requires guarded refresh",
            axes,
        )
    if (
        axes.filesystem_state == FilesystemState.DRIFT
        and axes.coverage_state == CoverageState.NOT_APPLICABLE
    ):
        fail("validate plan axes", "filesystem drift requires coverage classification", axes)
    if (
        axes.filesystem_state == FilesystemState.DRIFT
        and axes.coverage_state == CoverageState.COVERED
        and axes.runtime_config_state == RuntimeConfigState.ALIGNED
        and axes.selected_mutation_mode == SelectedMutationMode.NONE
    ):
        fail("validate plan axes", "filesystem drift requires a selected mutation mode", axes)
    if (
        axes.filesystem_state == FilesystemState.NO_DRIFT
        and axes.selected_mutation_mode != SelectedMutationMode.NONE
        and not (
            axes.runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH
            and axes.selected_mutation_mode == SelectedMutationMode.GUARDED_REFRESH
        )
    ):
        fail("validate plan axes", "no filesystem drift cannot select mutation mode", axes)


def derive_terminal_plan_status(axes: PlanAxes) -> TerminalPlanStatus:
    """Derive the terminal refresh plan status from independently tracked axes."""
    if axes.preflight_state == PreflightState.BLOCKED:
        return TerminalPlanStatus.BLOCKED_PREFLIGHT

    if _has_unknown_axis(axes) or _drift_runtime_config_unchecked(axes):
        return TerminalPlanStatus.BLOCKED_PREFLIGHT

    validate_axes(axes)

    if axes.coverage_state == CoverageState.COVERAGE_GAP:
        return TerminalPlanStatus.COVERAGE_GAP_BLOCKED
    if axes.runtime_config_state == RuntimeConfigState.UNREPAIRABLE_MISMATCH:
        return TerminalPlanStatus.UNREPAIRABLE_RUNTIME_CONFIG_MISMATCH
    if axes.runtime_config_state == RuntimeConfigState.REPAIRABLE_MISMATCH:
        return TerminalPlanStatus.REPAIRABLE_RUNTIME_CONFIG_MISMATCH
    if axes.filesystem_state == FilesystemState.NO_DRIFT:
        if axes.runtime_config_state == RuntimeConfigState.UNCHECKED:
            return TerminalPlanStatus.FILESYSTEM_NO_DRIFT
        return TerminalPlanStatus.NO_DRIFT
    if axes.selected_mutation_mode == SelectedMutationMode.GUARDED_REFRESH:
        return TerminalPlanStatus.GUARDED_REFRESH_REQUIRED
    if axes.selected_mutation_mode == SelectedMutationMode.REFRESH:
        return TerminalPlanStatus.REFRESH_ALLOWED

    return TerminalPlanStatus.BLOCKED_PREFLIGHT


def _has_unknown_axis(axes: PlanAxes) -> bool:
    return (
        axes.filesystem_state == FilesystemState.UNKNOWN
        or axes.coverage_state == CoverageState.UNKNOWN
        or axes.runtime_config_state == RuntimeConfigState.UNKNOWN
        or axes.selected_mutation_mode == SelectedMutationMode.UNKNOWN
    )


def _drift_runtime_config_unchecked(axes: PlanAxes) -> bool:
    return (
        axes.filesystem_state == FilesystemState.DRIFT
        and axes.runtime_config_state == RuntimeConfigState.UNCHECKED
    )
