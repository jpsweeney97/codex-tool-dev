from __future__ import annotations

import pytest
from refresh.classifier import classify_diff_path
from refresh.models import CoverageStatus, DiffKind, MutationMode, PathOutcome


def assert_path(
    path: str,
    *,
    outcome: PathOutcome,
    mutation_mode: MutationMode,
    coverage_status: CoverageStatus,
    kind: DiffKind = DiffKind.CHANGED,
) -> None:
    result = classify_diff_path(path, kind=kind, source_text="", cache_text="", executable=False)
    assert result.outcome == outcome
    assert result.mutation_mode == mutation_mode
    assert result.coverage_status == coverage_status


def test_fast_safe_paths_with_named_smoke() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/scripts/session_state.py",
        kind=DiffKind.CHANGED,
        source_text="",
        cache_text="",
        executable=False,
    )

    assert result.outcome == PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE
    assert result.mutation_mode == MutationMode.FAST
    assert result.coverage_status == CoverageStatus.COVERED
    assert result.smoke == ("handoff-session-state-write-read-clear",)


def test_guarded_paths_win_over_fast_safe() -> None:
    assert_path(
        "ticket/1.4.0/scripts/ticket_engine_core.py",
        outcome=PathOutcome.GUARDED_ONLY,
        mutation_mode=MutationMode.GUARDED,
        coverage_status=CoverageStatus.COVERED,
    )


def test_coverage_gap_paths_block_even_when_not_guarded() -> None:
    assert_path(
        "handoff/1.6.0/scripts/distill.py",
        outcome=PathOutcome.COVERAGE_GAP_FAIL,
        mutation_mode=MutationMode.BLOCKED,
        coverage_status=CoverageStatus.COVERAGE_GAP,
    )


def test_new_executable_path_is_coverage_gap_not_guarded_only() -> None:
    assert_path(
        "ticket/1.4.0/scripts/new_helper.py",
        kind=DiffKind.ADDED,
        outcome=PathOutcome.COVERAGE_GAP_FAIL,
        mutation_mode=MutationMode.BLOCKED,
        coverage_status=CoverageStatus.COVERAGE_GAP,
    )


@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.6.0/skills/new_tool.py",
        "handoff/1.6.0/references/new_tool.py",
        "ticket/1.4.0/skills/new_tool.py",
        "ticket/1.4.0/references/new_tool.py",
    ],
)
def test_added_executable_under_fast_safe_doc_glob_is_coverage_gap(path: str) -> None:
    result = classify_diff_path(
        path,
        kind=DiffKind.ADDED,
        source_text="print('new')\n",
        cache_text="",
        executable=True,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "added-executable-path" in result.reasons


def test_added_shebang_file_under_fast_safe_doc_glob_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/new_tool",
        kind=DiffKind.ADDED,
        source_text="#!/usr/bin/env python3\nprint('new')\n",
        cache_text="",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "added-executable-path" in result.reasons


def test_unmatched_non_executable_path_is_guarded_only_with_reason() -> None:
    result = classify_diff_path(
        "ticket/1.4.0/notes/operator.md",
        kind=DiffKind.CHANGED,
        source_text="note",
        cache_text="old",
        executable=False,
    )
    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.mutation_mode == MutationMode.GUARDED
    assert result.coverage_status == CoverageStatus.COVERED
    assert "unmatched-path" in result.reasons


def test_added_unmatched_non_executable_path_is_guarded_only() -> None:
    result = classify_diff_path(
        "ticket/1.4.0/notes/operator.md",
        kind=DiffKind.ADDED,
        source_text="note",
        cache_text="",
        executable=False,
    )

    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.mutation_mode == MutationMode.GUARDED
    assert result.coverage_status == CoverageStatus.COVERED
    assert "unmatched-path" in result.reasons


def test_nonexistent_ticket_engine_guard_script_is_coverage_gap() -> None:
    result = classify_diff_path(
        "ticket/1.4.0/scripts/ticket_engine_guard.py",
        kind=DiffKind.ADDED,
        source_text="print('new')\n",
        cache_text="",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP


@pytest.mark.parametrize(
    ("path", "outcome"),
    [
        ("handoff/1.6.0/.codex-plugin/plugin.json", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/hooks/hooks.json", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/scripts/cleanup.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/defer.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/scripts/distill.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/handoff_parsing.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/plugin_siblings.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/project_paths.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/provenance.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/quality_check.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/search.py", PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE),
        ("handoff/1.6.0/scripts/session_state.py", PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE),
        ("handoff/1.6.0/scripts/ticket_parsing.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/scripts/triage.py", PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE),
        ("ticket/1.4.0/.codex-plugin/plugin.json", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/hooks/hooks.json", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/hooks/ticket_engine_guard.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/__init__.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_audit.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_dedup.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_engine_agent.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_engine_core.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_engine_runner.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_engine_user.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_envelope.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_id.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_parse.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_paths.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_read.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_render.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_stage_models.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_triage.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_trust.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_ux.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("ticket/1.4.0/scripts/ticket_validate.py", PathOutcome.GUARDED_ONLY),
        ("ticket/1.4.0/scripts/ticket_workflow.py", PathOutcome.GUARDED_ONLY),
    ],
)
def test_current_executable_surface_outcomes(path: str, outcome: PathOutcome) -> None:
    result = classify_diff_path(
        path,
        kind=DiffKind.CHANGED,
        source_text="",
        cache_text="",
        executable=False,
    )

    assert result.outcome == outcome
    if outcome == PathOutcome.COVERAGE_GAP_FAIL:
        assert result.mutation_mode == MutationMode.BLOCKED
        assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    elif outcome == PathOutcome.GUARDED_ONLY:
        assert result.mutation_mode == MutationMode.GUARDED
        assert result.coverage_status == CoverageStatus.COVERED
    else:
        assert result.mutation_mode == MutationMode.FAST
        assert result.coverage_status == CoverageStatus.COVERED
