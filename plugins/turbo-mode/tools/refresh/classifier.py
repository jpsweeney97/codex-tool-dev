from __future__ import annotations

import fnmatch
from dataclasses import dataclass

from .command_projection import extract_command_projection, has_semantic_policy_trigger
from .models import CoverageStatus, DiffKind, MutationMode, PathClassification, PathOutcome

ROOT_DOC_PATTERNS = (
    "handoff/1.7.0/README.md",
    "handoff/1.7.0/CHANGELOG.md",
)

DOC_ROOT_PATTERNS = (
    "handoff/1.7.0/skills/**",
    "handoff/1.7.0/references/**",
)

HANDOFF_RUNTIME_SOURCE_PATTERNS = (
    "handoff/1.7.0/turbo_mode_handoff_runtime/*.py",
    "handoff/turbo_mode_handoff_runtime/*.py",
)

GUARDED_ONLY_PATTERNS = (
    "handoff/1.7.0/hooks/hooks.json",
    "handoff/1.7.0/hooks/*.py",
    *HANDOFF_RUNTIME_SOURCE_PATTERNS,
)

FAST_SAFE_PATTERNS = (
    "handoff/1.7.0/pyproject.toml",
    "handoff/1.7.0/uv.lock",
    "handoff/1.7.0/scripts/search.py",
    "handoff/1.7.0/scripts/session_state.py",
    "handoff/1.7.0/skills/*.md",
    "handoff/1.7.0/skills/**/*.md",
    "handoff/1.7.0/references/*.md",
    "handoff/1.7.0/references/**/*.md",
    "handoff/1.7.0/README.md",
    "handoff/1.7.0/CHANGELOG.md",
)

COVERAGE_GAP_PATTERNS = (
    "handoff/1.7.0/.codex-plugin/plugin.json",
    "handoff/1.7.0/scripts/distill.py",
)

SMOKE_BY_PATTERN = {
    "handoff/1.7.0/scripts/search.py": ("handoff-search",),
    "handoff/1.7.0/scripts/session_state.py": ("handoff-session-state-write-read-clear",),
    "handoff/1.7.0/skills/*.md": ("light",),
    "handoff/1.7.0/skills/**/*.md": ("light",),
    "handoff/1.7.0/references/*.md": ("light",),
    "handoff/1.7.0/references/**/*.md": ("light",),
    "handoff/1.7.0/README.md": ("light",),
    "handoff/1.7.0/CHANGELOG.md": ("light",),
    "handoff/1.7.0/pyproject.toml": ("handoff-installed-command",),
    "handoff/1.7.0/uv.lock": ("handoff-installed-command",),
}


@dataclass(frozen=True)
class HandoffStorageGate5RefreshContract:
    kind: DiffKind
    source_sha256: str
    cache_sha256: str | None


HANDOFF_STORAGE_GATE5_REFRESH_REASON = "handoff-storage-gate5-refresh-coverage"
HANDOFF_STORAGE_GATE5_REFRESH_SMOKE = (
    "handoff-storage-authority-inventory",
    "handoff-session-state-write-read-clear",
)
HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS = {
    "handoff/CHANGELOG.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="44da8da20a199dbfb57e83aea1e4096b81e20908c799cad487bbf19c201bd076",
        cache_sha256="0ddec803b46490b5fbc73e19b5f3a02854d47329ff22c5f74ec47b3d049f7f9d",
    ),
    "handoff/README.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="1eecffca229f37409a4062891edaf5687730c624dfd5e6503be1a918d35efc22",
        cache_sha256="00c3a9bce7a07ccff1ac6a138609045882662d04c059811ff16fbd24862d1aa8",
    ),
    "handoff/references/format-reference.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="e01c801e822d51e027b165a790524dde46d41a8609e077ff32215da94d0fdb7e",
        cache_sha256="41e353acf8c373fa25c3de9109a3352253a11aa1d5993045785045c12120a451",
    ),
    "handoff/references/handoff-contract.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="4fd1a12eb4eb6d81af4cbd7c5f0dda9d8df648b789b2f9bfb25b64f5c6b1d9eb",
        cache_sha256="381e32adf508b769c46ba3ab07d6d7414d95b72dccf51e8627ba878667137571",
    ),
    "handoff/turbo_mode_handoff_runtime/active_writes.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="87c9fb302f05fc214df75e4ab188506b82b59f720f6334b7aacfacff805185e8",
        cache_sha256=None,
    ),
    "handoff/scripts/distill.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="089ea3a0616b5a239154f29881981fb62783f79b093b976eaacd65bd44c7169c",
        cache_sha256="83a60c1479cf8842645e131e4ae74215b8c49820c151dcb312ba592c100393c6",
    ),
    (
        "handoff/turbo_mode_handoff_runtime/installed_host_harness.py"
    ): HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="ab527f284db99416d74d19f28c9ab41f107afd514145192ae486d058ac27c236",
        cache_sha256=None,
    ),
    "handoff/scripts/list_handoffs.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="b77c5557a7741c20f3e03533bcba1955500eda474ef9ed868774034bc05f6cb2",
        cache_sha256=None,
    ),
    "handoff/scripts/load_transactions.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="023a54db31ab3f73a5cf6b96179df572355b9a16fdc05e8d84c648b733f0ca5a",
        cache_sha256=None,
    ),
    "handoff/turbo_mode_handoff_runtime/project_paths.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="352ec06014bc149b1fbae365188335cc2001712b624d43e0060de8a1cf59719c",
        cache_sha256=None,
    ),
    "handoff/turbo_mode_handoff_runtime/quality_check.py": HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="b3022a1e22c29384e36137be49f7d726d848f0215e4ad8660aec9eb3414d22e3",
        cache_sha256=None,
    ),
    (
        "handoff/turbo_mode_handoff_runtime/storage_authority.py"
    ): HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="1d2c6ba474e310746be0ebbc17db1538807e2034b9101e965bd9d1529ea288e6",
        cache_sha256=None,
    ),
    (
        "handoff/turbo_mode_handoff_runtime/storage_authority_inventory.py"
    ): HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="fe0581d0fa920f21eb9c56b94ed0e5cff12e417a2fff8e005b4faac611116b1c",
        cache_sha256=None,
    ),
    (
        "handoff/turbo_mode_handoff_runtime/storage_primitives.py"
    ): HandoffStorageGate5RefreshContract(
        kind=DiffKind.ADDED,
        source_sha256="c03a85b69a0233b31b267d70e98a7e9efa2ad2b52beeb93750dc5d299956e8d3",
        cache_sha256=None,
    ),
    "handoff/skills/load/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="7e8e22f9837cf9cad2b50d599ad4f9079ad77cdf904998adc76d7ed4ca2eaa95",
        cache_sha256="ccbc7a20aa346d6d65e3861b62fd551d37ec44a43538685bfd09ef14b16b5698",
    ),
    "handoff/skills/quicksave/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="83ad9d86a6a22ee9f967f437c9ac65bdfa458ed423e32f371db5fb5de174cae2",
        cache_sha256="ac1430c96316f8fa60971bf20a7d55b98b60e03baac73e91cabbf2995cba56aa",
    ),
    "handoff/skills/save/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="147e1411c6b0ee3f249639155d795172c4628b2732598339c75f01f8132ffac4",
        cache_sha256="377609aefd7bd567c68ee71cbd620b0f03a16bcd4e04dd70a9310cc8132f37ae",
    ),
    "handoff/skills/summary/SKILL.md": HandoffStorageGate5RefreshContract(
        kind=DiffKind.CHANGED,
        source_sha256="bd417cd918974ced7f6e6a2351da77c706663666b737bbb1fec8fdd9eecd0d55",
        cache_sha256="108c18afd8cf8716b058dbfc1aee8e6db6007f8828025faa74fac16993c576b0",
    ),
}


def is_executable_or_command_bearing_path(path: str, *, executable: bool) -> bool:
    return (
        executable
        or _matches_any(path, ("*/scripts/*.py", "*/hooks/*.py"))
        or _matches_any(path, ("*/hooks/hooks.json", "*/.codex-plugin/plugin.json"))
    )


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
    elif _is_added_handoff_runtime_path(path, kind=kind):
        coverage_status = CoverageStatus.COVERAGE_GAP
        reasons.append("added-handoff-runtime-package-path")
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


def _is_added_handoff_runtime_path(path: str, *, kind: DiffKind) -> bool:
    if kind != DiffKind.ADDED:
        return False
    return _matches_any(path, HANDOFF_RUNTIME_SOURCE_PATTERNS)


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
