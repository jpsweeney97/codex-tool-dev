from __future__ import annotations

import pytest
from refresh import classifier
from refresh.classifier import (
    HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS,
    classify_diff_path,
    is_executable_or_command_bearing_path,
)
from refresh.models import CoverageStatus, DiffKind, MutationMode, PathOutcome


def classify(
    path: str,
    *,
    kind: DiffKind = DiffKind.CHANGED,
    source_text: str = "new\n",
    cache_text: str = "old\n",
    executable: bool = False,
    source_sha256: str | None = None,
    cache_sha256: str | None = None,
):
    return classify_diff_path(
        path,
        kind=kind,
        source_text=source_text,
        cache_text=cache_text,
        executable=executable,
        source_sha256=source_sha256,
        cache_sha256=cache_sha256,
    )


@pytest.mark.parametrize(
    ("path", "smoke"),
    [
        ("handoff/1.7.0/scripts/search.py", ("handoff-search",)),
        (
            "handoff/1.7.0/scripts/session_state.py",
            ("handoff-session-state-write-read-clear",),
        ),
        ("handoff/1.7.0/skills/save/SKILL.md", ("light",)),
        ("handoff/1.7.0/references/format-reference.md", ("light",)),
        ("handoff/1.7.0/README.md", ("light",)),
    ],
)
def test_known_fast_safe_paths_have_covered_smoke(
    path: str,
    smoke: tuple[str, ...],
) -> None:
    result = classify(path)

    assert result.outcome == PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE
    assert result.mutation_mode == MutationMode.FAST
    assert result.coverage_status == CoverageStatus.COVERED
    assert result.reasons == ("fast-safe-path",)
    assert result.smoke == smoke


@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.7.0/hooks/hooks.json",
        "handoff/1.7.0/hooks/safety.py",
        "handoff/1.7.0/turbo_mode_handoff_runtime/project_paths.py",
        "handoff/turbo_mode_handoff_runtime/project_paths.py",
    ],
)
def test_guarded_only_paths_require_guarded_refresh(path: str) -> None:
    result = classify(path)

    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.mutation_mode == MutationMode.GUARDED
    assert result.coverage_status == CoverageStatus.COVERED
    assert result.reasons == ("guarded-only-path",)


def test_added_command_bearing_path_is_a_coverage_gap() -> None:
    result = classify(
        "handoff/1.7.0/scripts/new_command.py",
        kind=DiffKind.ADDED,
        source_text="print('new')\n",
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert result.reasons == ("added-executable-path",)


def test_added_handoff_runtime_module_is_a_coverage_gap() -> None:
    result = classify(
        "handoff/1.7.0/turbo_mode_handoff_runtime/new_module.py",
        kind=DiffKind.ADDED,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.reasons == ("added-handoff-runtime-package-path",)


def test_added_non_markdown_doc_surface_is_a_coverage_gap() -> None:
    result = classify(
        "handoff/1.7.0/skills/save/helper.py",
        kind=DiffKind.ADDED,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.reasons == ("added-non-doc-path",)


def test_added_markdown_doc_surface_uses_fast_light_smoke() -> None:
    result = classify(
        "handoff/1.7.0/skills/save/references/new.md",
        kind=DiffKind.ADDED,
        source_text="Plain note.\n",
    )

    assert result.outcome == PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE
    assert result.reasons == ("fast-safe-path",)
    assert result.smoke == ("light",)


def test_plugin_manifest_changes_are_coverage_gaps() -> None:
    result = classify("handoff/1.7.0/.codex-plugin/plugin.json")

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.reasons == ("coverage-gap-path",)


def test_doc_command_shape_changes_are_coverage_gaps() -> None:
    result = classify(
        "handoff/1.7.0/README.md",
        source_text="```bash\npython scripts/search.py query\n```\n",
        cache_text="```bash\npython scripts/session_state.py read-state\n```\n",
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.reasons == ("command-shape-changed",)


def test_doc_semantic_policy_triggers_are_coverage_gaps() -> None:
    result = classify(
        "handoff/1.7.0/references/security.md",
        source_text="This changes sandbox approval behavior.\n",
        cache_text="This is a plain note.\n",
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.reasons == ("semantic-policy-trigger",)


def test_unmatched_plain_path_is_guarded_but_unmatched_executable_blocks() -> None:
    plain = classify("review-family/0.1.0/README.md")
    executable = classify(
        "review-family/0.1.0/scripts/new.py",
        source_text="#!/usr/bin/env python3\nprint('x')\n",
    )

    assert plain.outcome == PathOutcome.GUARDED_ONLY
    assert plain.reasons == ("unmatched-path",)
    assert executable.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert executable.reasons == ("unmatched-path",)


def test_exact_handoff_storage_contract_remains_guarded_with_required_smoke() -> None:
    path = "handoff/turbo_mode_handoff_runtime/storage_authority.py"
    contract = HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS[path]

    result = classify(
        path,
        kind=contract.kind,
        source_sha256=contract.source_sha256,
        cache_sha256=contract.cache_sha256,
    )

    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.reasons == ("handoff-storage-gate5-refresh-coverage",)
    assert result.smoke == (
        "handoff-storage-authority-inventory",
        "handoff-session-state-write-read-clear",
    )


def test_command_bearing_helper_recognizes_hooks_and_manifests() -> None:
    assert is_executable_or_command_bearing_path(
        "handoff/1.7.0/hooks/hooks.json",
        executable=False,
    )
    assert is_executable_or_command_bearing_path(
        "handoff/1.7.0/.codex-plugin/plugin.json",
        executable=False,
    )
    assert not is_executable_or_command_bearing_path(
        "handoff/1.7.0/README.md",
        executable=False,
    )


def test_active_classifier_patterns_target_current_handoff_layout() -> None:
    surfaces = (
        classifier.ROOT_DOC_PATTERNS,
        classifier.DOC_ROOT_PATTERNS,
        classifier.HANDOFF_RUNTIME_SOURCE_PATTERNS,
        classifier.GUARDED_ONLY_PATTERNS,
        classifier.FAST_SAFE_PATTERNS,
        tuple(classifier.SMOKE_BY_PATTERN),
        tuple(classifier.HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS),
    )
    text = "\n".join(item for surface in surfaces for item in surface)

    assert "handoff/1.7.0" in text
    assert "handoff/1.7.0/turbo_mode_handoff_runtime" in text
