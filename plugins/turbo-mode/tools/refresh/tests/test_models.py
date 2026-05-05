from __future__ import annotations

from refresh.models import CoverageStatus, DiffKind, MutationMode, PathOutcome, TerminalPlanStatus


def test_enum_values_match_design_contract() -> None:
    assert MutationMode.FAST.value == "fast"
    assert MutationMode.GUARDED.value == "guarded"
    assert MutationMode.BLOCKED.value == "blocked"
    assert CoverageStatus.COVERED.value == "covered"
    assert CoverageStatus.COVERAGE_GAP.value == "coverage_gap"
    assert PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE.value == "fast-safe-with-covered-smoke"
    assert PathOutcome.GUARDED_ONLY.value == "guarded-only"
    assert PathOutcome.COVERAGE_GAP_FAIL.value == "coverage-gap-fail"
    assert DiffKind.ADDED.value == "added"
    assert DiffKind.REMOVED.value == "removed"
    assert DiffKind.CHANGED.value == "changed"
    assert TerminalPlanStatus.REFRESH_ALLOWED.value == "refresh-allowed"
    assert TerminalPlanStatus.GUARDED_REFRESH_REQUIRED.value == "guarded-refresh-required"
