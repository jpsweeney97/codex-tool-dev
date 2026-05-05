from __future__ import annotations

import fnmatch

from .command_projection import extract_command_projection, has_semantic_policy_trigger
from .models import CoverageStatus, DiffKind, MutationMode, PathClassification, PathOutcome

ROOT_DOC_PATTERNS = (
    "handoff/1.6.0/README.md",
    "handoff/1.6.0/CHANGELOG.md",
    "ticket/1.4.0/README.md",
    "ticket/1.4.0/CHANGELOG.md",
    "ticket/1.4.0/HANDBOOK.md",
)

DOC_ROOT_PATTERNS = (
    "handoff/1.6.0/skills/**",
    "handoff/1.6.0/references/**",
    "ticket/1.4.0/skills/**",
    "ticket/1.4.0/references/**",
)

GUARDED_ONLY_PATTERNS = (
    "handoff/1.6.0/hooks/hooks.json",
    "handoff/1.6.0/hooks/*.py",
    "handoff/1.6.0/scripts/defer.py",
    "ticket/1.4.0/hooks/hooks.json",
    "ticket/1.4.0/hooks/*.py",
    "ticket/1.4.0/scripts/ticket_engine_runner.py",
    "ticket/1.4.0/scripts/ticket_engine_core.py",
    "ticket/1.4.0/scripts/ticket_engine_user.py",
    "ticket/1.4.0/scripts/ticket_engine_agent.py",
    "ticket/1.4.0/scripts/ticket_workflow.py",
    "ticket/1.4.0/scripts/ticket_validate.py",
    "ticket/1.4.0/scripts/ticket_parse.py",
    "ticket/1.4.0/scripts/ticket_paths.py",
    "ticket/1.4.0/scripts/ticket_envelope.py",
)

FAST_SAFE_PATTERNS = (
    "handoff/1.6.0/pyproject.toml",
    "handoff/1.6.0/uv.lock",
    "handoff/1.6.0/scripts/search.py",
    "handoff/1.6.0/scripts/triage.py",
    "handoff/1.6.0/scripts/session_state.py",
    "handoff/1.6.0/skills/*.md",
    "handoff/1.6.0/skills/**/*.md",
    "handoff/1.6.0/references/*.md",
    "handoff/1.6.0/references/**/*.md",
    "handoff/1.6.0/README.md",
    "handoff/1.6.0/CHANGELOG.md",
    "ticket/1.4.0/README.md",
    "ticket/1.4.0/CHANGELOG.md",
    "ticket/1.4.0/HANDBOOK.md",
    "ticket/1.4.0/pyproject.toml",
    "ticket/1.4.0/uv.lock",
    "ticket/1.4.0/skills/*.md",
    "ticket/1.4.0/skills/**/*.md",
    "ticket/1.4.0/references/*.md",
    "ticket/1.4.0/references/**/*.md",
)

COVERAGE_GAP_PATTERNS = (
    "handoff/1.6.0/.codex-plugin/plugin.json",
    "handoff/1.6.0/scripts/distill.py",
    "handoff/1.6.0/scripts/ticket_parsing.py",
    "ticket/1.4.0/.codex-plugin/plugin.json",
)

SMOKE_BY_PATTERN = {
    "handoff/1.6.0/scripts/search.py": ("handoff-search",),
    "handoff/1.6.0/scripts/triage.py": ("handoff-triage",),
    "handoff/1.6.0/scripts/session_state.py": ("handoff-session-state-write-read-clear",),
    "handoff/1.6.0/skills/*.md": ("light",),
    "handoff/1.6.0/skills/**/*.md": ("light",),
    "handoff/1.6.0/references/*.md": ("light",),
    "handoff/1.6.0/references/**/*.md": ("light",),
    "handoff/1.6.0/README.md": ("light",),
    "handoff/1.6.0/CHANGELOG.md": ("light",),
    "handoff/1.6.0/pyproject.toml": ("handoff-installed-command",),
    "handoff/1.6.0/uv.lock": ("handoff-installed-command",),
    "ticket/1.4.0/README.md": ("light",),
    "ticket/1.4.0/CHANGELOG.md": ("light",),
    "ticket/1.4.0/HANDBOOK.md": ("light",),
    "ticket/1.4.0/skills/*.md": ("light",),
    "ticket/1.4.0/skills/**/*.md": ("light",),
    "ticket/1.4.0/references/*.md": ("light",),
    "ticket/1.4.0/references/**/*.md": ("light",),
    "ticket/1.4.0/pyproject.toml": ("ticket-installed-command",),
    "ticket/1.4.0/uv.lock": ("ticket-installed-command",),
}


def is_executable_or_command_bearing_path(path: str, *, executable: bool) -> bool:
    return (
        executable
        or _matches_any(path, ("*/scripts/*.py", "*/hooks/*.py"))
        or _matches_any(path, ("*/hooks/hooks.json", "*/.codex-plugin/plugin.json"))
    )


def classify_diff_path(
    path: str,
    *,
    kind: DiffKind,
    source_text: str,
    cache_text: str,
    executable: bool,
) -> PathClassification:
    reasons: list[str] = []
    coverage_status = CoverageStatus.COVERED
    mutation_mode = MutationMode.GUARDED
    smoke: tuple[str, ...] = ()

    if _is_added_executable_path(
        path,
        kind=kind,
        source_text=source_text,
        executable=executable,
    ):
        coverage_status = CoverageStatus.COVERAGE_GAP
        reasons.append("added-executable-path")
    elif _is_added_non_doc_path(path, kind=kind):
        coverage_status = CoverageStatus.COVERAGE_GAP
        reasons.append("added-non-doc-path")
    elif _is_executable_doc_surface(
        path,
        source_text=source_text,
        cache_text=cache_text,
        executable=executable,
    ):
        coverage_status = CoverageStatus.COVERAGE_GAP
        reasons.append("executable-doc-surface")
    elif doc_policy_reasons := _doc_policy_reasons(
        path,
        source_text=source_text,
        cache_text=cache_text,
    ):
        coverage_status = CoverageStatus.COVERAGE_GAP
        reasons.extend(doc_policy_reasons)
    elif _matches_any(path, COVERAGE_GAP_PATTERNS):
        coverage_status = CoverageStatus.COVERAGE_GAP
        reasons.append("coverage-gap-path")
    elif _matches_any(path, GUARDED_ONLY_PATTERNS):
        mutation_mode = MutationMode.GUARDED
        reasons.append("guarded-only-path")
    elif _matches_any(path, FAST_SAFE_PATTERNS):
        mutation_mode = MutationMode.FAST
        reasons.append("fast-safe-path")
        smoke = _smoke_for_path(path)
    else:
        reasons.append("unmatched-path")
        is_unsafe_unmatched = is_executable_or_command_bearing_path(
            path,
            executable=executable,
        )
        if is_unsafe_unmatched:
            coverage_status = CoverageStatus.COVERAGE_GAP

    if _text_has_shebang(source_text) or _text_has_shebang(cache_text):
        if "unmatched-path" in reasons:
            coverage_status = CoverageStatus.COVERAGE_GAP

    if coverage_status == CoverageStatus.COVERAGE_GAP:
        return PathClassification(
            canonical_path=path,
            mutation_mode=MutationMode.BLOCKED,
            coverage_status=CoverageStatus.COVERAGE_GAP,
            outcome=PathOutcome.COVERAGE_GAP_FAIL,
            reasons=tuple(reasons),
            smoke=(),
        )
    if mutation_mode == MutationMode.FAST:
        return PathClassification(
            canonical_path=path,
            mutation_mode=MutationMode.FAST,
            coverage_status=CoverageStatus.COVERED,
            outcome=PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE,
            reasons=tuple(reasons),
            smoke=smoke,
        )
    return PathClassification(
        canonical_path=path,
        mutation_mode=MutationMode.GUARDED,
        coverage_status=CoverageStatus.COVERED,
        outcome=PathOutcome.GUARDED_ONLY,
        reasons=tuple(reasons),
        smoke=smoke,
    )


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _smoke_for_path(path: str) -> tuple[str, ...]:
    for pattern, smoke in SMOKE_BY_PATTERN.items():
        if fnmatch.fnmatchcase(path, pattern):
            return smoke
    return ()


def _is_added_executable_path(
    path: str,
    *,
    kind: DiffKind,
    source_text: str,
    executable: bool,
) -> bool:
    if kind != DiffKind.ADDED:
        return False
    return executable or _text_has_shebang(source_text) or is_executable_or_command_bearing_path(
        path,
        executable=executable,
    )


def _is_executable_doc_surface(
    path: str,
    *,
    source_text: str,
    cache_text: str,
    executable: bool,
) -> bool:
    if not _is_doc_surface_path(path):
        return False
    return executable or _text_has_shebang(source_text) or _text_has_shebang(cache_text)


def _is_added_non_doc_path(path: str, *, kind: DiffKind) -> bool:
    if kind != DiffKind.ADDED or not _is_doc_glob_path(path):
        return False
    return not path.endswith(".md")


def _is_doc_glob_path(path: str) -> bool:
    return _matches_any(path, DOC_ROOT_PATTERNS)


def _is_doc_surface_path(path: str) -> bool:
    return _is_doc_glob_path(path) or _matches_any(path, ROOT_DOC_PATTERNS)


def _doc_policy_reasons(path: str, *, source_text: str, cache_text: str) -> tuple[str, ...]:
    if not _is_doc_surface_path(path):
        return ()

    reasons: list[str] = []
    source_projection = extract_command_projection(source_text)
    cache_projection = extract_command_projection(cache_text)
    if source_projection.items != cache_projection.items:
        reasons.append("command-shape-changed")
    if source_projection.parser_warnings or cache_projection.parser_warnings:
        reasons.append("projection-parser-warning")
    if has_semantic_policy_trigger(source_text) or has_semantic_policy_trigger(cache_text):
        reasons.append("semantic-policy-trigger")
    return tuple(reasons)


def _text_has_shebang(text: str) -> bool:
    return text.startswith("#!")
