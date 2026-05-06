from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass

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


@dataclass(frozen=True)
class HandoffStateHelperDocContract:
    source_sha256: str
    cache_sha256: str
    source_items: tuple[str, ...]
    cache_items: tuple[str, ...]
    source_parser_warnings: tuple[str, ...]
    cache_parser_warnings: tuple[str, ...]
    source_semantic_policy_trigger: bool
    cache_semantic_policy_trigger: bool


HANDOFF_STATE_HELPER_DOC_SMOKE = (
    "handoff-state-helper-docs",
    "handoff-session-state-write-read-clear",
)
HANDOFF_STATE_HELPER_UV_ENV = (
    'PYTHONDONTWRITEBYTECODE=1 '
    'UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \\'
)
HANDOFF_STATE_HELPER_UV_RUN = (
    'uv run --project "$PLUGIN_ROOT/pyproject.toml" '
    'python "$PLUGIN_ROOT/scripts/session_state.py" \\'
)

HANDOFF_STATE_HELPER_DOC_CONTRACTS = {
    "handoff/1.6.0/skills/load/SKILL.md": HandoffStateHelperDocContract(
        source_sha256="ccbc7a20aa346d6d65e3861b62fd551d37ec44a43538685bfd09ef14b16b5698",
        cache_sha256="6cc5f0c631fb03fa310171ca49fec6d40ec59ab9641a342e194180470749f509",
        source_items=(
            "/load",
            "/load <path>",
            "/list-handoffs",
            "/save",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            "python",
            'ARCHIVED_PATH="$(',
            'PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" \\',
            "archive \\",
            '--source "$SOURCE_PATH" \\',
            '--archive-dir "$PROJECT_ROOT/docs/handoffs/archive" \\',
            "--field archived_path",
            ')"',
            'STATE_PATH="$(',
            "write-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--archive-path "$ARCHIVED_PATH" \\',
            "--field state_path",
        ),
        cache_items=(
            "/load",
            "/load <path>",
            "/list-handoffs",
            "/save",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'ARCHIVED_PATH="$(',
            HANDOFF_STATE_HELPER_UV_ENV,
            HANDOFF_STATE_HELPER_UV_RUN,
            "archive \\",
            '--source "$SOURCE_PATH" \\',
            '--archive-dir "$PROJECT_ROOT/docs/handoffs/archive" \\',
            "--field archived_path",
            ')"',
            'STATE_PATH="$(',
            "write-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--archive-path "$ARCHIVED_PATH" \\',
            "--field state_path",
        ),
        source_parser_warnings=(),
        cache_parser_warnings=(),
        source_semantic_policy_trigger=True,
        cache_semantic_policy_trigger=True,
    ),
    "handoff/1.6.0/skills/quicksave/SKILL.md": HandoffStateHelperDocContract(
        source_sha256="ac1430c96316f8fa60971bf20a7d55b98b60e03baac73e91cabbf2995cba56aa",
        cache_sha256="644b183f4c68a50511b45854f7a3fd7115bcdc5cea8355f9cfb6ff41265d0c8d",
        source_items=(
            "/quicksave",
            "/save",
            "python",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'READ_STATE_OUTPUT="$(',
            'PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" \\',
            "read-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--field state_path \\',
            "2>&1",
            ')"',
            "READ_STATE_STATUS=$?",
            'case "$READ_STATE_STATUS" in',
            '0) STATE_PATH="$READ_STATE_OUTPUT" ;;',
            '1) STATE_PATH="" ;;',
            '2) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;',
            "esac",
            'READ_ARCHIVE_OUTPUT="$(',
            "--field archive_path \\",
            "READ_ARCHIVE_STATUS=$?",
            'case "$READ_ARCHIVE_STATUS" in',
            '0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;',
            '1) RESUMED_FROM="" ;;',
            '2) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;',
            "/load",
            'if [ -n "$STATE_PATH" ]; then',
            "clear-state \\",
            '--state-path "$STATE_PATH"',
            "fi",
        ),
        cache_items=(
            "/quicksave",
            "/save",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'READ_STATE_OUTPUT="$(',
            HANDOFF_STATE_HELPER_UV_ENV,
            HANDOFF_STATE_HELPER_UV_RUN,
            "read-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--field state_path \\',
            "2>&1",
            ')"',
            "READ_STATE_STATUS=$?",
            'case "$READ_STATE_STATUS" in',
            '0) STATE_PATH="$READ_STATE_OUTPUT" ;;',
            '1) STATE_PATH="" ;;',
            '2) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;',
            "esac",
            'READ_ARCHIVE_OUTPUT="$(',
            "--field archive_path \\",
            "READ_ARCHIVE_STATUS=$?",
            'case "$READ_ARCHIVE_STATUS" in',
            '0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;',
            '1) RESUMED_FROM="" ;;',
            '2) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;',
            "/load",
            'if [ -n "$STATE_PATH" ]; then',
            "PYTHONDONTWRITEBYTECODE=1 \\",
            'UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \\',
            "clear-state \\",
            '--state-path "$STATE_PATH"',
            "fi",
        ),
        source_parser_warnings=(),
        cache_parser_warnings=(),
        source_semantic_policy_trigger=True,
        cache_semantic_policy_trigger=True,
    ),
    "handoff/1.6.0/skills/save/SKILL.md": HandoffStateHelperDocContract(
        source_sha256="377609aefd7bd567c68ee71cbd620b0f03a16bcd4e04dd70a9310cc8132f37ae",
        cache_sha256="55b8d897a91ac70e119c7299ca294e6028aeffcd71994d7daa096e2c5cd43d85",
        source_items=(
            "/save",
            "/save <title>",
            "python",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'READ_STATE_OUTPUT="$(',
            'PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" \\',
            "read-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--field state_path \\',
            "2>&1",
            ')"',
            "READ_STATE_STATUS=$?",
            'case "$READ_STATE_STATUS" in',
            '0) STATE_PATH="$READ_STATE_OUTPUT" ;;',
            '1) STATE_PATH="" ;;',
            '2) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;',
            "esac",
            'READ_ARCHIVE_OUTPUT="$(',
            "--field archive_path \\",
            "READ_ARCHIVE_STATUS=$?",
            'case "$READ_ARCHIVE_STATUS" in',
            '0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;',
            '1) RESUMED_FROM="" ;;',
            '2) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;',
            'if [ -n "$STATE_PATH" ]; then',
            "clear-state \\",
            '--state-path "$STATE_PATH"',
            "fi",
        ),
        cache_items=(
            "/save",
            "/save <title>",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'READ_STATE_OUTPUT="$(',
            HANDOFF_STATE_HELPER_UV_ENV,
            HANDOFF_STATE_HELPER_UV_RUN,
            "read-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--field state_path \\',
            "2>&1",
            ')"',
            "READ_STATE_STATUS=$?",
            'case "$READ_STATE_STATUS" in',
            '0) STATE_PATH="$READ_STATE_OUTPUT" ;;',
            '1) STATE_PATH="" ;;',
            '2) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;',
            "esac",
            'READ_ARCHIVE_OUTPUT="$(',
            "--field archive_path \\",
            "READ_ARCHIVE_STATUS=$?",
            'case "$READ_ARCHIVE_STATUS" in',
            '0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;',
            '1) RESUMED_FROM="" ;;',
            '2) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;',
            'if [ -n "$STATE_PATH" ]; then',
            "PYTHONDONTWRITEBYTECODE=1 \\",
            'UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \\',
            "clear-state \\",
            '--state-path "$STATE_PATH"',
            "fi",
        ),
        source_parser_warnings=(),
        cache_parser_warnings=(),
        source_semantic_policy_trigger=True,
        cache_semantic_policy_trigger=True,
    ),
    "handoff/1.6.0/skills/summary/SKILL.md": HandoffStateHelperDocContract(
        source_sha256="108c18afd8cf8716b058dbfc1aee8e6db6007f8828025faa74fac16993c576b0",
        cache_sha256="ad8c4b0eca09103c4d396238191d0f424abf9b9ee1d47d3b6126d24628f8d5c0",
        source_items=(
            "/save",
            "/quicksave",
            "/summary",
            "/summary <title>",
            "python",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'READ_STATE_OUTPUT="$(',
            'PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" \\',
            "read-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--field state_path \\',
            "2>&1",
            ')"',
            "READ_STATE_STATUS=$?",
            'case "$READ_STATE_STATUS" in',
            '0) STATE_PATH="$READ_STATE_OUTPUT" ;;',
            '1) STATE_PATH="" ;;',
            '2) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;',
            "esac",
            'READ_ARCHIVE_OUTPUT="$(',
            "--field archive_path \\",
            "READ_ARCHIVE_STATUS=$?",
            'case "$READ_ARCHIVE_STATUS" in',
            '0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;',
            '1) RESUMED_FROM="" ;;',
            '2) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;',
            'if [ -n "$STATE_PATH" ]; then',
            "clear-state \\",
            '--state-path "$STATE_PATH"',
            "fi",
        ),
        cache_items=(
            "/save",
            "/quicksave",
            "/summary",
            "/summary <title>",
            'PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'PROJECT_NAME="$(basename "$PROJECT_ROOT")"',
            'READ_STATE_OUTPUT="$(',
            HANDOFF_STATE_HELPER_UV_ENV,
            HANDOFF_STATE_HELPER_UV_RUN,
            "read-state \\",
            '--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \\',
            '--project "$PROJECT_NAME" \\',
            '--field state_path \\',
            "2>&1",
            ')"',
            "READ_STATE_STATUS=$?",
            'case "$READ_STATE_STATUS" in',
            '0) STATE_PATH="$READ_STATE_OUTPUT" ;;',
            '1) STATE_PATH="" ;;',
            '2) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;',
            "esac",
            'READ_ARCHIVE_OUTPUT="$(',
            "--field archive_path \\",
            "READ_ARCHIVE_STATUS=$?",
            'case "$READ_ARCHIVE_STATUS" in',
            '0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;',
            '1) RESUMED_FROM="" ;;',
            '2) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;',
            '*) printf \'%s\\n\' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;',
            'if [ -n "$STATE_PATH" ]; then',
            "PYTHONDONTWRITEBYTECODE=1 \\",
            'UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \\',
            "clear-state \\",
            '--state-path "$STATE_PATH"',
            "fi",
        ),
        source_parser_warnings=(),
        cache_parser_warnings=(),
        source_semantic_policy_trigger=True,
        cache_semantic_policy_trigger=True,
    ),
}


def is_executable_or_command_bearing_path(path: str, *, executable: bool) -> bool:
    return (
        executable
        or _matches_any(path, ("*/scripts/*.py", "*/hooks/*.py"))
        or _matches_any(path, ("*/hooks/hooks.json", "*/.codex-plugin/plugin.json"))
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_handoff_state_helper_direct_python_doc_migration(
    path: str,
    *,
    source_text: str,
    cache_text: str,
) -> bool:
    contract = HANDOFF_STATE_HELPER_DOC_CONTRACTS.get(path)
    if contract is None:
        return False
    if _sha256_text(source_text) != contract.source_sha256:
        return False
    if _sha256_text(cache_text) != contract.cache_sha256:
        return False

    source_projection = extract_command_projection(source_text)
    cache_projection = extract_command_projection(cache_text)
    if source_projection.parser_warnings != contract.source_parser_warnings:
        return False
    if cache_projection.parser_warnings != contract.cache_parser_warnings:
        return False
    if source_projection.parser_warnings or cache_projection.parser_warnings:
        return False
    if source_projection.items != contract.source_items:
        return False
    if cache_projection.items != contract.cache_items:
        return False
    if has_semantic_policy_trigger(source_text) is not contract.source_semantic_policy_trigger:
        return False
    if has_semantic_policy_trigger(cache_text) is not contract.cache_semantic_policy_trigger:
        return False
    return True


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
    elif _is_handoff_state_helper_direct_python_doc_migration(
        path,
        source_text=source_text,
        cache_text=cache_text,
    ):
        mutation_mode = MutationMode.GUARDED
        reasons.append("handoff-state-helper-direct-python-doc-migration")
        smoke = HANDOFF_STATE_HELPER_DOC_SMOKE
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
