from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RefreshError(RuntimeError):
    """Raised when refresh planning cannot continue safely."""


def fail(operation: str, reason: str, got: object) -> None:
    raise RefreshError(f"{operation} failed: {reason}. Got: {got!r:.100}")


class DiffKind(Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class MutationMode(Enum):
    FAST = "fast"
    GUARDED = "guarded"
    BLOCKED = "blocked"


class CoverageStatus(Enum):
    COVERED = "covered"
    COVERAGE_GAP = "coverage_gap"


class PathOutcome(Enum):
    FAST_SAFE_WITH_COVERED_SMOKE = "fast-safe-with-covered-smoke"
    GUARDED_ONLY = "guarded-only"
    COVERAGE_GAP_FAIL = "coverage-gap-fail"


class FilesystemState(Enum):
    DRIFT = "drift"
    NO_DRIFT = "no-drift"
    UNKNOWN = "unknown"


class CoverageState(Enum):
    COVERED = "covered"
    COVERAGE_GAP = "coverage-gap"
    NOT_APPLICABLE = "not-applicable"
    UNKNOWN = "unknown"


class RuntimeConfigState(Enum):
    ALIGNED = "aligned"
    UNCHECKED = "unchecked"
    REPAIRABLE_MISMATCH = "repairable-mismatch"
    UNREPAIRABLE_MISMATCH = "unrepairable-mismatch"
    UNKNOWN = "unknown"


class PreflightState(Enum):
    PASSED = "passed"
    BLOCKED = "blocked"


class SelectedMutationMode(Enum):
    REFRESH = "refresh"
    GUARDED_REFRESH = "guarded-refresh"
    NONE = "none"
    UNKNOWN = "unknown"


class TerminalPlanStatus(Enum):
    BLOCKED_PREFLIGHT = "blocked-preflight"
    COVERAGE_GAP_BLOCKED = "coverage-gap-blocked"
    UNREPAIRABLE_RUNTIME_CONFIG_MISMATCH = "unrepairable-runtime-config-mismatch"
    REPAIRABLE_RUNTIME_CONFIG_MISMATCH = "repairable-runtime-config-mismatch"
    GUARDED_REFRESH_REQUIRED = "guarded-refresh-required"
    REFRESH_ALLOWED = "refresh-allowed"
    NO_DRIFT = "no-drift"
    FILESYSTEM_NO_DRIFT = "filesystem-no-drift"


@dataclass(frozen=True)
class PluginSpec:
    name: str
    version: str
    source_root: Path
    cache_root: Path


@dataclass(frozen=True)
class ManifestEntry:
    canonical_path: str
    sha256: str
    size: int
    mode: int
    executable: bool
    has_shebang: bool


@dataclass(frozen=True)
class ResidueIssue:
    root_kind: str
    plugin: str
    path: str
    reason: str


@dataclass(frozen=True)
class DiffEntry:
    canonical_path: str
    kind: DiffKind
    source: ManifestEntry | None
    cache: ManifestEntry | None


@dataclass(frozen=True)
class PathClassification:
    canonical_path: str
    mutation_mode: MutationMode
    coverage_status: CoverageStatus
    outcome: PathOutcome
    reasons: tuple[str, ...]
    smoke: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanAxes:
    filesystem_state: FilesystemState
    coverage_state: CoverageState
    runtime_config_state: RuntimeConfigState
    preflight_state: PreflightState
    selected_mutation_mode: SelectedMutationMode
    reasons: tuple[str, ...] = field(default_factory=tuple)
