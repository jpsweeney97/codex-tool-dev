from __future__ import annotations

import fnmatch

from .models import CoverageStatus, DiffKind, MutationMode, PathClassification, PathOutcome

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
    "handoff/1.6.0/skills/**",
    "handoff/1.6.0/references/**",
    "handoff/1.6.0/README.md",
    "handoff/1.6.0/CHANGELOG.md",
    "ticket/1.4.0/README.md",
    "ticket/1.4.0/CHANGELOG.md",
    "ticket/1.4.0/HANDBOOK.md",
    "ticket/1.4.0/pyproject.toml",
    "ticket/1.4.0/uv.lock",
    "ticket/1.4.0/skills/**",
    "ticket/1.4.0/references/**",
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
    "handoff/1.6.0/skills/**": ("light",),
    "handoff/1.6.0/references/**": ("light",),
    "handoff/1.6.0/README.md": ("light",),
    "handoff/1.6.0/CHANGELOG.md": ("light",),
    "handoff/1.6.0/pyproject.toml": ("handoff-installed-command",),
    "handoff/1.6.0/uv.lock": ("handoff-installed-command",),
    "ticket/1.4.0/README.md": ("light",),
    "ticket/1.4.0/CHANGELOG.md": ("light",),
    "ticket/1.4.0/HANDBOOK.md": ("light",),
    "ticket/1.4.0/skills/**": ("light",),
    "ticket/1.4.0/references/**": ("light",),
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


def _text_has_shebang(text: str) -> bool:
    return text.startswith("#!")
