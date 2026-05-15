from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from refresh.classifier import (
    HANDOFF_STATE_HELPER_DOC_CONTRACTS,
    HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS,
    HANDOFF_STORAGE_GATE5_REFRESH_SMOKE,
    classify_diff_path,
)
from refresh.command_projection import (
    CommandProjection,
    extract_command_projection,
    has_semantic_policy_trigger,
)
from refresh.models import CoverageStatus, DiffKind, MutationMode, PathOutcome

REPO_ROOT = Path(__file__).resolve().parents[5]
HANDOFF_ROOT = REPO_ROOT / "plugins/turbo-mode/handoff/1.6.0"
TICKET_ROOT = REPO_ROOT / "plugins/turbo-mode/ticket/1.4.0"
HANDOFF_STATE_HELPER_DOC_FIXTURES = json.loads(
    (
        Path(__file__).parent / "fixtures" / "handoff_state_helper_doc_migration.json"
    ).read_text(encoding="utf-8")
)

EXPECTED_COMMAND_SURFACE_PATHS = (
    "handoff/1.6.0/.codex-plugin/plugin.json",
    "handoff/1.6.0/hooks/hooks.json",
    "handoff/1.6.0/scripts/defer.py",
    "handoff/1.6.0/scripts/distill.py",
    "handoff/1.6.0/scripts/list_handoffs.py",
    "handoff/1.6.0/scripts/load_transactions.py",
    "handoff/1.6.0/scripts/plugin_siblings.py",
    "handoff/1.6.0/scripts/search.py",
    "handoff/1.6.0/scripts/session_state.py",
    "handoff/1.6.0/scripts/triage.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/cleanup.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/defer.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/distill.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/handoff_parsing.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/installed_host_harness.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/list_handoffs.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/plugin_siblings.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/provenance.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/quality_check.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/search.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/ticket_parsing.py",
    "handoff/1.6.0/turbo_mode_handoff_runtime/triage.py",
    "ticket/1.4.0/.codex-plugin/plugin.json",
    "ticket/1.4.0/hooks/hooks.json",
    "ticket/1.4.0/hooks/ticket_engine_guard.py",
    "ticket/1.4.0/scripts/__init__.py",
    "ticket/1.4.0/scripts/ticket_audit.py",
    "ticket/1.4.0/scripts/ticket_dedup.py",
    "ticket/1.4.0/scripts/ticket_engine_agent.py",
    "ticket/1.4.0/scripts/ticket_engine_core.py",
    "ticket/1.4.0/scripts/ticket_engine_runner.py",
    "ticket/1.4.0/scripts/ticket_engine_user.py",
    "ticket/1.4.0/scripts/ticket_envelope.py",
    "ticket/1.4.0/scripts/ticket_id.py",
    "ticket/1.4.0/scripts/ticket_parse.py",
    "ticket/1.4.0/scripts/ticket_paths.py",
    "ticket/1.4.0/scripts/ticket_read.py",
    "ticket/1.4.0/scripts/ticket_render.py",
    "ticket/1.4.0/scripts/ticket_stage_models.py",
    "ticket/1.4.0/scripts/ticket_triage.py",
    "ticket/1.4.0/scripts/ticket_trust.py",
    "ticket/1.4.0/scripts/ticket_ux.py",
    "ticket/1.4.0/scripts/ticket_validate.py",
    "ticket/1.4.0/scripts/ticket_workflow.py",
)

EXPECTED_MARKDOWN_PROJECTION_PATHS = (
    "handoff/1.6.0/CHANGELOG.md",
    "handoff/1.6.0/README.md",
    "handoff/1.6.0/references/handoff-contract.md",
    "handoff/1.6.0/skills/defer/SKILL.md",
    "handoff/1.6.0/skills/distill/SKILL.md",
    "handoff/1.6.0/skills/load/SKILL.md",
    "handoff/1.6.0/skills/quicksave/SKILL.md",
    "handoff/1.6.0/skills/save/SKILL.md",
    "handoff/1.6.0/skills/search/SKILL.md",
    "handoff/1.6.0/skills/summary/SKILL.md",
    "handoff/1.6.0/skills/triage/SKILL.md",
    "ticket/1.4.0/CHANGELOG.md",
    "ticket/1.4.0/HANDBOOK.md",
    "ticket/1.4.0/README.md",
    "ticket/1.4.0/skills/ticket/SKILL.md",
    "ticket/1.4.0/skills/ticket/references/pipeline-guide.md",
    "ticket/1.4.0/skills/ticket-triage/SKILL.md",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def test_current_source_tree_surfaces_match_pinned_fixture_lists() -> None:
    assert tuple(_discover_command_surface_paths()) == EXPECTED_COMMAND_SURFACE_PATHS
    projection_paths: list[str] = []

    for plugin_root, prefix in ((HANDOFF_ROOT, "handoff/1.6.0"), (TICKET_ROOT, "ticket/1.4.0")):
        for path in sorted(plugin_root.rglob("*.md")):
            projection = extract_command_projection(path.read_text(encoding="utf-8"))
            assert projection.parser_warnings == ()
            if projection.items:
                projection_paths.append(f"{prefix}/{path.relative_to(plugin_root).as_posix()}")

    assert tuple(projection_paths) == EXPECTED_MARKDOWN_PROJECTION_PATHS


def _discover_command_surface_paths() -> list[str]:
    paths: list[str] = []
    for plugin_root, prefix in ((HANDOFF_ROOT, "handoff/1.6.0"), (TICKET_ROOT, "ticket/1.4.0")):
        for relative in (".codex-plugin/plugin.json", "hooks/hooks.json"):
            path = plugin_root / relative
            if path.exists():
                paths.append(f"{prefix}/{relative}")
        paths.extend(
            f"{prefix}/{path.relative_to(plugin_root).as_posix()}"
            for path in sorted((plugin_root / "hooks").glob("*.py"))
        )
        paths.extend(
            f"{prefix}/{path.relative_to(plugin_root).as_posix()}"
            for path in sorted((plugin_root / "scripts").glob("*.py"))
        )
        if prefix == "handoff/1.6.0":
            paths.extend(
                f"{prefix}/{path.relative_to(plugin_root).as_posix()}"
                for path in sorted((plugin_root / "turbo_mode_handoff_runtime").glob("*.py"))
                if path.name != "__init__.py"
            )
    return sorted(paths)


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


def test_added_handoff_runtime_module_path_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/turbo_mode_handoff_runtime/new_module.py",
        kind=DiffKind.ADDED,
        source_text="from __future__ import annotations\n",
        cache_text="",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "added-handoff-runtime-package-path" in result.reasons


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


@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.6.0/skills/search/SKILL.md",
        "handoff/1.6.0/references/handoff-contract.md",
        "ticket/1.4.0/skills/ticket/SKILL.md",
        "ticket/1.4.0/references/pipeline-guide.md",
    ],
)
def test_changed_fast_safe_doc_glob_with_executable_mode_is_coverage_gap(path: str) -> None:
    result = classify_diff_path(
        path,
        kind=DiffKind.CHANGED,
        source_text="# Heading\n",
        cache_text="# Heading\n",
        executable=True,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "executable-doc-surface" in result.reasons


def test_changed_fast_safe_doc_glob_with_new_shebang_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="#!/usr/bin/env python3\nprint('new')\n",
        cache_text="# Search skill\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "executable-doc-surface" in result.reasons


@pytest.mark.parametrize(
    ("path", "source_text", "executable"),
    [
        ("handoff/1.6.0/README.md", "#!/usr/bin/env python3\nprint('new')\n", False),
        ("handoff/1.6.0/CHANGELOG.md", "# Changelog\n", True),
        ("ticket/1.4.0/README.md", "#!/usr/bin/env bash\n", False),
        ("ticket/1.4.0/CHANGELOG.md", "# Changelog\n", True),
        ("ticket/1.4.0/HANDBOOK.md", "# Handbook\n", True),
    ],
)
def test_changed_root_fast_safe_doc_with_executable_surface_is_coverage_gap(
    path: str,
    source_text: str,
    executable: bool,
) -> None:
    result = classify_diff_path(
        path,
        kind=DiffKind.CHANGED,
        source_text=source_text,
        cache_text="# Previous\n",
        executable=executable,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "executable-doc-surface" in result.reasons


@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.6.0/references/handoff-contract.md",
        "ticket/1.4.0/references/ticket-contract.md",
    ],
)
def test_root_reference_markdown_paths_remain_fast_safe(path: str) -> None:
    result = classify_diff_path(
        path,
        kind=DiffKind.CHANGED,
        source_text="# Contract\n",
        cache_text="# Contract\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE
    assert result.mutation_mode == MutationMode.FAST
    assert result.coverage_status == CoverageStatus.COVERED
    assert result.smoke == ("light",)


def test_changed_doc_with_unchanged_command_projection_remains_fast_safe() -> None:
    source_text = """# Search

Use this command when needed:

```bash
python3 scripts/search.py query
```

Updated surrounding prose.
"""
    cache_text = """# Search

Use this command when needed:

```bash
python3 scripts/search.py query
```
"""

    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=source_text,
        cache_text=cache_text,
        executable=False,
    )

    assert result.outcome == PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE
    assert result.mutation_mode == MutationMode.FAST
    assert result.coverage_status == CoverageStatus.COVERED


def test_changed_doc_with_new_command_projection_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="Run `python3 scripts/search.py query` before summarizing.\n",
        cache_text="Search before summarizing.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "command-shape-changed" in result.reasons


def test_changed_doc_with_new_shell_fence_command_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="""# Search

```bash
git status --short
```
""",
        cache_text="# Search\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "command-shape-changed" in result.reasons


@pytest.mark.parametrize("fence", ['```bash title="smoke"', "``` bash"])
def test_changed_doc_with_shell_fence_info_string_command_is_coverage_gap(fence: str) -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=f"""# Search

{fence}
git status --short
```
""",
        cache_text="# Search\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "command-shape-changed" in result.reasons


def test_changed_doc_with_added_slash_command_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="Run /save then /load.\n",
        cache_text="Run /save.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "command-shape-changed" in result.reasons


def test_changed_doc_with_changed_slash_command_prefix_is_coverage_gap() -> None:
    result = classify_diff_path(
        "ticket/1.4.0/skills/ticket-triage/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="Run /ticket-triage.\n",
        cache_text="Run /ticket.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "command-shape-changed" in result.reasons


def test_changed_doc_with_projection_parser_warning_is_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/references/handoff-contract.md",
        kind=DiffKind.CHANGED,
        source_text='```json\n{"request": "tool/execute", "action": }\n```\n',
        cache_text="# Contract\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "projection-parser-warning" in result.reasons


def test_changed_doc_with_semantic_policy_trigger_is_coverage_gap() -> None:
    result = classify_diff_path(
        "ticket/1.4.0/HANDBOOK.md",
        kind=DiffKind.CHANGED,
        source_text="Runtime inventory authority now controls maintenance windows.\n",
        cache_text="Operational handbook.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "semantic-policy-trigger" in result.reasons


@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.6.0/skills/load/SKILL.md",
        "handoff/1.6.0/skills/quicksave/SKILL.md",
        "handoff/1.6.0/skills/save/SKILL.md",
        "handoff/1.6.0/skills/summary/SKILL.md",
    ],
)
def test_handoff_state_helper_direct_python_doc_migration_is_guarded(path: str) -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES[path]
    source_text = contract["source_text"]
    cache_text = contract["cache_text"]

    assert _sha256(source_text) == contract["source_sha256"]
    assert _sha256(cache_text) == contract["cache_sha256"]
    assert extract_command_projection(source_text).items == tuple(contract["source_items"])
    assert extract_command_projection(cache_text).items == tuple(contract["cache_items"])
    assert extract_command_projection(source_text).parser_warnings == tuple(
        contract["source_parser_warnings"]
    )
    assert extract_command_projection(cache_text).parser_warnings == tuple(
        contract["cache_parser_warnings"]
    )
    assert contract["source_parser_warnings"] == []
    assert contract["cache_parser_warnings"] == []
    assert has_semantic_policy_trigger(source_text) is contract["source_semantic_policy_trigger"]
    assert has_semantic_policy_trigger(cache_text) is contract["cache_semantic_policy_trigger"]

    result = classify_diff_path(
        path,
        kind=DiffKind.CHANGED,
        source_text=source_text,
        cache_text=cache_text,
        executable=False,
    )

    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.mutation_mode == MutationMode.GUARDED
    assert result.coverage_status == CoverageStatus.COVERED
    assert result.reasons == ("handoff-state-helper-direct-python-doc-migration",)
    assert result.smoke == (
        "handoff-state-helper-docs",
        "handoff-session-state-write-read-clear",
    )


def test_handoff_state_helper_doc_migration_rejects_hash_only_content_change() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/load/SKILL.md"]
    source_text = contract["source_text"].replace(
        "Continue work from a previous handoff.",
        "Continue work from an earlier handoff.",
    )
    cache_text = contract["cache_text"]

    assert _sha256(source_text) != contract["source_sha256"]
    assert extract_command_projection(source_text).items == tuple(contract["source_items"])
    assert extract_command_projection(source_text).parser_warnings == tuple(
        contract["source_parser_warnings"]
    )
    assert has_semantic_policy_trigger(source_text) is contract["source_semantic_policy_trigger"]

    result = classify_diff_path(
        "handoff/1.6.0/skills/load/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=source_text,
        cache_text=cache_text,
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "handoff-state-helper-direct-python-doc-migration" not in result.reasons


def test_handoff_state_helper_doc_contracts_have_valid_hashes_and_fallback_trigger() -> None:
    for contract in HANDOFF_STATE_HELPER_DOC_CONTRACTS.values():
        assert re.fullmatch(r"[0-9a-f]{64}", contract.source_sha256)
        assert re.fullmatch(r"[0-9a-f]{64}", contract.cache_sha256)
        assert contract.source_semantic_policy_trigger is True
        assert contract.cache_semantic_policy_trigger is True


def test_handoff_state_helper_doc_migration_rejects_extra_command_item() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/save/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/save/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"]
        + (
            '\nRun `python "$PLUGIN_ROOT/scripts/session_state.py" prune-state '
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state"`.\n'
        ),
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_handoff_state_helper_doc_migration_rejects_added_slash_command() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/load/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/load/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"] + "\nUse `/summary` if loading is ambiguous.\n",
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_handoff_state_helper_doc_migration_rejects_added_policy_text() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/quicksave/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/quicksave/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"]
        + "\nRollback and recovery hooks must be approved by the operator.\n",
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "semantic-policy-trigger" in result.reasons


def test_handoff_state_helper_doc_migration_requires_exact_state_helper_command() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/summary/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/summary/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"].replace("read-state \\", "repair-state \\"),
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_unrelated_uv_run_state_helper_doc_change_stays_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=(
            'Run `uv run --project "$PLUGIN_ROOT/pyproject.toml" python '
            '"$PLUGIN_ROOT/scripts/session_state.py" read-state`.\n'
        ),
        cache_text="Run `python3 scripts/search.py`.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_unrelated_handoff_command_doc_change_stays_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="Run `python3 scripts/search.py --new-mode`.\n",
        cache_text="Run `python3 scripts/search.py`.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_handoff_state_helper_doc_migration_rejects_projection_parser_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/save/SKILL.md"]
    original_extract = extract_command_projection

    def warn_for_same_bytes(text: str) -> CommandProjection:
        projection = original_extract(text)
        return CommandProjection(
            items=projection.items,
            parser_warnings=("json-payload-parse-failed",),
        )

    monkeypatch.setattr("refresh.classifier.extract_command_projection", warn_for_same_bytes)
    result = classify_diff_path(
        "handoff/1.6.0/skills/save/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"],
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "projection-parser-warning" in result.reasons


@pytest.mark.parametrize(
    ("kind", "source_text", "cache_text"),
    [
        (DiffKind.ADDED, "Run `python3 scripts/search.py query`.\n", ""),
        (DiffKind.REMOVED, "", "Run `python3 scripts/search.py query`.\n"),
    ],
)
def test_added_or_removed_command_bearing_doc_is_coverage_gap(
    kind: DiffKind,
    source_text: str,
    cache_text: str,
) -> None:
    result = classify_diff_path(
        "handoff/1.6.0/references/handoff-contract.md",
        kind=kind,
        source_text=source_text,
        cache_text=cache_text,
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "command-shape-changed" in result.reasons


@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.6.0/skills/new_tool.py",
        "handoff/1.6.0/references/new_tool.sh",
        "ticket/1.4.0/skills/new_tool.py",
        "ticket/1.4.0/references/new_tool.sh",
    ],
)
def test_added_non_doc_file_under_fast_safe_doc_glob_is_coverage_gap(path: str) -> None:
    result = classify_diff_path(
        path,
        kind=DiffKind.ADDED,
        source_text="content\n",
        cache_text="",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "added-non-doc-path" in result.reasons


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
    ("path", "contract"),
    sorted(HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS.items()),
)
def test_handoff_storage_gate5_refresh_contract_is_exact_hash_guarded(
    path: str,
    contract,
) -> None:
    result = classify_diff_path(
        path,
        kind=contract.kind,
        source_text="",
        cache_text="",
        executable=False,
        source_sha256=contract.source_sha256,
        cache_sha256=contract.cache_sha256,
    )

    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.mutation_mode == MutationMode.GUARDED
    assert result.coverage_status == CoverageStatus.COVERED
    assert result.reasons == ("handoff-storage-gate5-refresh-coverage",)
    assert result.smoke == HANDOFF_STORAGE_GATE5_REFRESH_SMOKE


@pytest.mark.parametrize(
    ("path", "contract"),
    sorted(HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS.items()),
)
def test_handoff_storage_gate5_refresh_contract_source_hash_matches_live_file(
    path: str,
    contract,
) -> None:
    source_path = REPO_ROOT / "plugins/turbo-mode" / path
    if not source_path.exists():
        assert contract.kind == DiffKind.REMOVED
        return

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == contract.source_sha256


def test_handoff_storage_gate5_refresh_contract_rejects_hash_drift() -> None:
    contract = HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS[
        "handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py"
    ]

    result = classify_diff_path(
        "handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py",
        kind=contract.kind,
        source_text="print('changed')\n",
        cache_text="",
        executable=False,
        source_sha256="0" * 64,
        cache_sha256=contract.cache_sha256,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert result.mutation_mode == MutationMode.BLOCKED
    assert result.coverage_status == CoverageStatus.COVERAGE_GAP
    assert "added-handoff-runtime-package-path" in result.reasons


@pytest.mark.parametrize(
    ("path", "outcome"),
    [
        ("handoff/1.6.0/.codex-plugin/plugin.json", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/hooks/hooks.json", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/cleanup.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/scripts/defer.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/scripts/distill.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/handoff_parsing.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/scripts/plugin_siblings.py", PathOutcome.COVERAGE_GAP_FAIL),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/provenance.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/quality_check.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/scripts/search.py", PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE),
        ("handoff/1.6.0/scripts/session_state.py", PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py", PathOutcome.GUARDED_ONLY),
        ("handoff/1.6.0/turbo_mode_handoff_runtime/ticket_parsing.py", PathOutcome.GUARDED_ONLY),
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
