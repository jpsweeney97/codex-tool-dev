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


@dataclass(frozen=True)
class HandoffStorageGate5RefreshContract:
    kind: DiffKind
    source_sha256: str
    cache_sha256: str | None


HANDOFF_STATE_HELPER_DOC_SMOKE = (
    "handoff-state-helper-docs",
    "handoff-session-state-write-read-clear",
)
HANDOFF_STORAGE_GATE5_REFRESH_REASON = "handoff-storage-gate5-refresh-coverage"
HANDOFF_STORAGE_GATE5_REFRESH_SMOKE = (
    "handoff-storage-authority-inventory",
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

HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS = {
    "handoff/1.6.0/CHANGELOG.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="eac73d2d3e8189d2bc4d5fcbf7f82cf4a9602efce8d9fb495f56461e339e973c",
        cache_sha256="0ddec803b46490b5fbc73e19b5f3a02854d47329ff22c5f74ec47b3d049f7f9d",
    ),
    "handoff/1.6.0/README.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="86a2ead8d5c598613394921989a0add333211cac875fdd53d598ad454cf03615",
        cache_sha256="00c3a9bce7a07ccff1ac6a138609045882662d04c059811ff16fbd24862d1aa8",
    ),
    "handoff/1.6.0/references/format-reference.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="e01c801e822d51e027b165a790524dde46d41a8609e077ff32215da94d0fdb7e",
        cache_sha256="41e353acf8c373fa25c3de9109a3352253a11aa1d5993045785045c12120a451",
    ),
    "handoff/1.6.0/references/handoff-contract.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="4fd1a12eb4eb6d81af4cbd7c5f0dda9d8df648b789b2f9bfb25b64f5c6b1d9eb",
        cache_sha256="381e32adf508b769c46ba3ab07d6d7414d95b72dccf51e8627ba878667137571",
    ),
    "handoff/1.6.0/scripts/active_writes.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="4a0aebe32e04886a783a22324f1a3e3a249c799704f611950c79337c1be879ef",
        cache_sha256=None,
    ),
    "handoff/1.6.0/scripts/distill.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="ebc2d24658b6e93b4795a65c94f92bbc8664ab83e6b59edae40a2b685d5c35c0",
        cache_sha256="83a60c1479cf8842645e131e4ae74215b8c49820c151dcb312ba592c100393c6",
    ),
    "handoff/1.6.0/scripts/installed_host_harness.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="8cd3041280b2c22cfc61ba015ba2295fd324f11fb2f235499625834472a0c096",
        cache_sha256=None,
    ),
    "handoff/1.6.0/scripts/list_handoffs.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="fdae6f266546acd90f42b437507d5349eb08e314b59585e6040c99cc683bbbdc",
        cache_sha256=None,
    ),
    "handoff/1.6.0/scripts/load_transactions.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="2b0135d3dd74682bf434b2a42370946b8de73f6c5474822c61cab5e612607cde",
        cache_sha256=None,
    ),
    "handoff/1.6.0/scripts/project_paths.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="9d593b901825db9b52841b5d2da59ae91236ddbb9b2714074d8f56df58335927",
        cache_sha256="ca378736b107be47a2d504f004bd6584d5faf15c3f572bcc15f825bb10910ede",
    ),
    "handoff/1.6.0/scripts/quality_check.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="e56e1f33fab92d2d733b8a128d36c81eda0b2dca181c2e3cccbc2a9dc1aa7d28",
        cache_sha256="883fff0a7eba02ab8c87a95aa915277e04cd48dd418e6848a210f125ec458f7f",
    ),
    "handoff/1.6.0/scripts/storage_authority.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="4bd0da91bd676414f27ee1213541d73a32672812d3f0d0a5f2ceeccfc036f9aa",
        cache_sha256=None,
    ),
    "handoff/1.6.0/scripts/storage_authority_inventory.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="b471e99352bea672829c2fb05a16b05b8676bd4bc74ba4c90537f2a5b97b4c71",
        cache_sha256=None,
    ),
    "handoff/1.6.0/scripts/storage_primitives.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="82703beeb804f4cec0fdc415dcd4ed66f006454d5d536ba75dd4dfaf728f745f",
        cache_sha256=None,
    ),
    "handoff/1.6.0/skills/load/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="f657d40d1f700c13ed32c8700011d412cddd9b97406cc2d232fd87f3b147672f",
        cache_sha256="ccbc7a20aa346d6d65e3861b62fd551d37ec44a43538685bfd09ef14b16b5698",
    ),
    "handoff/1.6.0/skills/quicksave/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="d9eaaae771d9db3601ee25df8d979cc22b16ce3c5e9a65b0fae31ece7252b91e",
        cache_sha256="ac1430c96316f8fa60971bf20a7d55b98b60e03baac73e91cabbf2995cba56aa",
    ),
    "handoff/1.6.0/skills/save/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="33e76da645b84e6d8487a3309019794960bb8b6ae7802973be94584eccd9ea6f",
        cache_sha256="377609aefd7bd567c68ee71cbd620b0f03a16bcd4e04dd70a9310cc8132f37ae",
    ),
    "handoff/1.6.0/skills/summary/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="8b3585333f2a5745dd603b2a586bde0e3f3dfff6ce377bffa0b2e22baa543771",
        cache_sha256="108c18afd8cf8716b058dbfc1aee8e6db6007f8828025faa74fac16993c576b0",
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


def _handoff_storage_gate5_refresh_contract(
    path: str,
    *,
    kind: DiffKind,
    source_sha256: str | None,
    cache_sha256: str | None,
) -> HandoffStorageGate5RefreshContract | None:
    contract = HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS.get(path)
    if contract is None:
        return None
    if kind != contract.kind:
        return None
    if source_sha256 != contract.source_sha256:
        return None
    if cache_sha256 != contract.cache_sha256:
        return None
    return contract


def classify_diff_path(
    path: str,
    *,
    kind: DiffKind,
    source_text: str,
    cache_text: str,
    executable: bool,
    source_sha256: str | None = None,
    cache_sha256: str | None = None,
) -> PathClassification:
    reasons: list[str] = []
    coverage_status = CoverageStatus.COVERED
    mutation_mode = MutationMode.GUARDED
    smoke: tuple[str, ...] = ()

    if _handoff_storage_gate5_refresh_contract(
        path,
        kind=kind,
        source_sha256=source_sha256,
        cache_sha256=cache_sha256,
    ):
        mutation_mode = MutationMode.GUARDED
        reasons.append(HANDOFF_STORAGE_GATE5_REFRESH_REASON)
        smoke = HANDOFF_STORAGE_GATE5_REFRESH_SMOKE
    elif _is_added_executable_path(
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
