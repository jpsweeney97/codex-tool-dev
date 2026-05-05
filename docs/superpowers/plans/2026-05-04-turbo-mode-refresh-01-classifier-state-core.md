# Turbo Mode Refresh Classifier And State Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure, non-mutating classifier and plan-state core for the Turbo Mode installed-refresh tool.

**Architecture:** This checkpoint creates a small `plugins/turbo-mode/tools/refresh/` Python package with typed models, source/cache manifest diffing, generated-residue gates, path safety classification, command-shape projection, semantic-policy detection, smoke selection, and terminal plan-status derivation. It does not create the CLI, app-server client, process gate, lock, recovery, config mutation, installed-cache mutation, or evidence retention commands.

**Tech Stack:** Python 3.11+, dataclasses, enums, `pathlib`, `hashlib`, `fnmatch`, `re`, `pytest`, `ruff`.

---

## Modular Build Strategy

The refresh design should be implemented as a suite of small plans, not one large plan. Each plan must produce a reviewable commit and must leave mutation unavailable until the relevant gates exist.

| Plan | Scope | Mutation allowed | Output |
| --- | --- | --- | --- |
| 01 classifier-state-core | Pure models, manifests, diffs, classifier, command projection, semantic-policy triggers, smoke selection, terminal status precedence | No | Importable library and fixture tests |
| 02 non-mutating-cli-evidence | `refresh_installed_turbo_mode.py --dry-run` and `--plan-refresh`, local-only evidence writes, root/config/marketplace preflight, plan command emission | No | Routine developer commands |
| 03 app-server-readonly-inventory | Pinned app-server JSON-RPC client, runtime identity capture, response-schema compatibility, read-only inventory parser | No installed-cache or config mutation | Optional `--inventory-check` |
| 04 process-gate | Wide process census, blocker classification, external-shell/self-exemption evidence wording | No installed-cache or config mutation | Maintenance-window precondition model |
| 05 lock-recovery-config-primitives | Refresh lock, run-state marker, recovery state machine, config byte snapshots, atomic config writes, rollback preconditions | Recovery primitives only in fixtures until mutation plans consume them | Local-only safety primitives |
| 06 refresh-mutation | `--refresh`, cache snapshot/restore, app-server install, source/cache equality proof, fresh restore inventory | External-shell maintenance only | Low-risk refresh lane |
| 07 guarded-refresh-mutation | `--guarded-refresh`, hook config state machine, guarded marketplace repair, fresh app-server final inventory | External-shell maintenance only | Guarded refresh lane |
| 08 evidence-review-retention | Evidence review/prune commands, commit-safe summaries, redaction validators, stale evidence rejection | No direct mutation beyond local-only evidence management | Evidence governance |

Stop condition between plans: do not begin a mutation plan until all prior non-mutating plans pass their tests and the current implementation still refuses mutation from ordinary in-session execution.

## Checkpoint 01 Scope

This first plan owns the pure core needed by future modes. It deliberately stops before runtime I/O.

In scope:

- Canonical refresh keys: `<plugin>/<version>/<relative_path>`.
- Generated-residue detection that fails before equality diffing.
- Source/cache manifest building for fixture roots.
- Source/cache diff categories: `added`, `removed`, `changed`.
- Safety classification fields: `mutation_mode` and `coverage_status`.
- User-facing path outcomes: `fast-safe-with-covered-smoke`, `guarded-only`, `coverage-gap-fail`.
- Current Handoff 1.6.0 and Ticket 1.4.0 executable surface fixture coverage.
- Command-shape projection for command-projection Markdown and JSON examples.
- Conservative semantic-policy trigger detection for docs and skill prose.
- Smoke selection names for the paths explicitly covered by the design.
- Plan-state axis and terminal-status derivation.

Out of scope:

- The command-line interface.
- Reads from `/Users/jp/.codex/config.toml`.
- Reads from app-server.
- Reads from process tables.
- Writes to local-only evidence directories.
- Writes to installed cache or global config.
- Any direct file copy into installed plugin cache roots.

## Files

Create:

- `plugins/turbo-mode/tools/refresh/__init__.py`
- `plugins/turbo-mode/tools/refresh/models.py`
- `plugins/turbo-mode/tools/refresh/paths.py`
- `plugins/turbo-mode/tools/refresh/manifests.py`
- `plugins/turbo-mode/tools/refresh/classifier.py`
- `plugins/turbo-mode/tools/refresh/command_projection.py`
- `plugins/turbo-mode/tools/refresh/state_machine.py`
- `plugins/turbo-mode/tools/refresh/tests/conftest.py`
- `plugins/turbo-mode/tools/refresh/tests/test_models.py`
- `plugins/turbo-mode/tools/refresh/tests/test_manifests.py`
- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- `plugins/turbo-mode/tools/refresh/tests/test_command_projection.py`
- `plugins/turbo-mode/tools/refresh/tests/test_state_machine.py`

Modify:

- None for checkpoint 01.

Do not import from `plugins/turbo-mode/tools/migration/migration_common.py` in this checkpoint. The migration module contains one-time migration constants and plan metadata. Shared helpers can be extracted in a future refactor only after this refresh core has its own tests.

## Current Surface Fixture Lists

The classifier fixture tests must pin these current source-tree surfaces.

Handoff 1.6.0 command-bearing or executable paths:

```text
handoff/1.6.0/.codex-plugin/plugin.json
handoff/1.6.0/hooks/hooks.json
handoff/1.6.0/scripts/cleanup.py
handoff/1.6.0/scripts/defer.py
handoff/1.6.0/scripts/distill.py
handoff/1.6.0/scripts/handoff_parsing.py
handoff/1.6.0/scripts/plugin_siblings.py
handoff/1.6.0/scripts/project_paths.py
handoff/1.6.0/scripts/provenance.py
handoff/1.6.0/scripts/quality_check.py
handoff/1.6.0/scripts/search.py
handoff/1.6.0/scripts/session_state.py
handoff/1.6.0/scripts/ticket_parsing.py
handoff/1.6.0/scripts/triage.py
```

Ticket 1.4.0 command-bearing or executable paths:

```text
ticket/1.4.0/.codex-plugin/plugin.json
ticket/1.4.0/hooks/hooks.json
ticket/1.4.0/hooks/ticket_engine_guard.py
ticket/1.4.0/scripts/__init__.py
ticket/1.4.0/scripts/ticket_audit.py
ticket/1.4.0/scripts/ticket_dedup.py
ticket/1.4.0/scripts/ticket_engine_agent.py
ticket/1.4.0/scripts/ticket_engine_core.py
ticket/1.4.0/scripts/ticket_engine_runner.py
ticket/1.4.0/scripts/ticket_engine_user.py
ticket/1.4.0/scripts/ticket_envelope.py
ticket/1.4.0/scripts/ticket_id.py
ticket/1.4.0/scripts/ticket_parse.py
ticket/1.4.0/scripts/ticket_paths.py
ticket/1.4.0/scripts/ticket_read.py
ticket/1.4.0/scripts/ticket_render.py
ticket/1.4.0/scripts/ticket_stage_models.py
ticket/1.4.0/scripts/ticket_triage.py
ticket/1.4.0/scripts/ticket_trust.py
ticket/1.4.0/scripts/ticket_ux.py
ticket/1.4.0/scripts/ticket_validate.py
ticket/1.4.0/scripts/ticket_workflow.py
```

Current command-projection Markdown paths:

```text
handoff/1.6.0/CHANGELOG.md
handoff/1.6.0/README.md
handoff/1.6.0/references/handoff-contract.md
handoff/1.6.0/skills/defer/SKILL.md
handoff/1.6.0/skills/distill/SKILL.md
handoff/1.6.0/skills/load/SKILL.md
handoff/1.6.0/skills/quicksave/SKILL.md
handoff/1.6.0/skills/save/SKILL.md
handoff/1.6.0/skills/search/SKILL.md
handoff/1.6.0/skills/summary/SKILL.md
handoff/1.6.0/skills/triage/SKILL.md
ticket/1.4.0/CHANGELOG.md
ticket/1.4.0/HANDBOOK.md
ticket/1.4.0/README.md
ticket/1.4.0/skills/ticket-triage/SKILL.md
ticket/1.4.0/skills/ticket/SKILL.md
ticket/1.4.0/skills/ticket/references/pipeline-guide.md
```

## Task 1: Package Skeleton And Typed Models

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/__init__.py`
- Create: `plugins/turbo-mode/tools/refresh/models.py`
- Create: `plugins/turbo-mode/tools/refresh/tests/conftest.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_models.py`

- [ ] **Step 1: Write model import tests**

Create `plugins/turbo-mode/tools/refresh/tests/test_models.py` with:

```python
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
```

- [ ] **Step 2: Add test import path helper**

Create `plugins/turbo-mode/tools/refresh/tests/conftest.py` with:

```python
from __future__ import annotations

import sys
from pathlib import Path


REFRESH_PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REFRESH_PARENT))
```

- [ ] **Step 3: Run the failing model test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_models.py -q
```

Expected: fail because `refresh.models` does not exist.

- [ ] **Step 4: Add public model definitions**

Create `plugins/turbo-mode/tools/refresh/__init__.py` as an empty package marker.

Create `plugins/turbo-mode/tools/refresh/models.py` with public definitions for:

```python
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
```

- [ ] **Step 5: Run the model test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_models.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/tools/refresh
git commit -m "feat: add turbo-mode refresh core models"
```

## Task 2: Canonical Paths, Manifest Building, Diffing, And Residue Gate

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/paths.py`
- Create: `plugins/turbo-mode/tools/refresh/manifests.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_manifests.py`

- [ ] **Step 1: Write manifest and residue tests**

Create tests that cover:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from refresh.manifests import build_manifest, diff_manifests, scan_generated_residue
from refresh.models import DiffKind, PluginSpec, RefreshError
from refresh.paths import canonical_key


def plugin_spec(tmp_path: Path) -> PluginSpec:
    return PluginSpec(
        name="handoff",
        version="1.6.0",
        source_root=tmp_path / "source",
        cache_root=tmp_path / "cache",
    )


def test_canonical_key_uses_plugin_version_and_posix_relative_path(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    path = spec.source_root / "skills" / "search" / "SKILL.md"
    assert canonical_key(spec, path, root=spec.source_root) == "handoff/1.6.0/skills/search/SKILL.md"


def test_generated_residue_is_reported_before_manifest_diff(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    residue = spec.source_root / "scripts" / "__pycache__" / "x.pyc"
    residue.parent.mkdir(parents=True)
    residue.write_bytes(b"compiled")

    issues = scan_generated_residue([spec])

    assert [(issue.plugin, issue.path, issue.reason) for issue in issues] == [
        ("handoff", "scripts/__pycache__/x.pyc", "generated-residue")
    ]


def test_manifest_rejects_generated_residue(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    residue = spec.cache_root / ".pytest_cache" / "README.md"
    residue.parent.mkdir(parents=True)
    residue.write_text("cache", encoding="utf-8")

    with pytest.raises(RefreshError):
        build_manifest(spec, root_kind="cache")


def test_manifest_rejects_file_symlink_before_hashing(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = spec.source_root / "README.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)

    with pytest.raises(RefreshError):
        build_manifest(spec, root_kind="source")


def test_manifest_rejects_directory_symlink_before_hashing(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "SKILL.md").write_text("external", encoding="utf-8")
    link = spec.source_root / "skills"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(RefreshError):
        build_manifest(spec, root_kind="source")


def test_diff_manifests_reports_added_removed_and_changed(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    source_only = spec.source_root / "README.md"
    cache_only = spec.cache_root / "CHANGELOG.md"
    changed_source = spec.source_root / "skills" / "search" / "SKILL.md"
    changed_cache = spec.cache_root / "skills" / "search" / "SKILL.md"
    source_only.parent.mkdir(parents=True)
    cache_only.parent.mkdir(parents=True)
    changed_source.parent.mkdir(parents=True)
    changed_cache.parent.mkdir(parents=True)
    source_only.write_text("source", encoding="utf-8")
    cache_only.write_text("cache", encoding="utf-8")
    changed_source.write_text("new", encoding="utf-8")
    changed_cache.write_text("old", encoding="utf-8")

    diffs = diff_manifests(build_manifest(spec, root_kind="source"), build_manifest(spec, root_kind="cache"))

    assert [(diff.canonical_path, diff.kind) for diff in diffs] == [
        ("handoff/1.6.0/CHANGELOG.md", DiffKind.REMOVED),
        ("handoff/1.6.0/README.md", DiffKind.ADDED),
        ("handoff/1.6.0/skills/search/SKILL.md", DiffKind.CHANGED),
    ]


def test_diff_manifests_reports_executable_metadata_drift(tmp_path: Path) -> None:
    spec = plugin_spec(tmp_path)
    source_path = spec.source_root / "scripts" / "search.py"
    cache_path = spec.cache_root / "scripts" / "search.py"
    source_path.parent.mkdir(parents=True)
    cache_path.parent.mkdir(parents=True)
    source_path.write_text("print('same')\n", encoding="utf-8")
    cache_path.write_text("print('same')\n", encoding="utf-8")
    source_path.chmod(0o755)
    cache_path.chmod(0o644)

    diffs = diff_manifests(build_manifest(spec, root_kind="source"), build_manifest(spec, root_kind="cache"))

    assert [(diff.canonical_path, diff.kind) for diff in diffs] == [
        ("handoff/1.6.0/scripts/search.py", DiffKind.CHANGED)
    ]
```

- [ ] **Step 2: Run manifest tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_manifests.py -q
```

Expected: fail because manifest helpers do not exist.

- [ ] **Step 3: Implement path and manifest helpers**

Create `paths.py` with:

```python
from __future__ import annotations

from pathlib import Path

from .models import PluginSpec, fail


def canonical_key(spec: PluginSpec, path: Path, *, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        fail("canonicalize path", "path is outside root", {"path": str(path), "root": str(root)})
    return f"{spec.name}/{spec.version}/{rel.as_posix()}"
```

Create `manifests.py` with functions:

- `has_shebang(path: Path) -> bool`
- `is_executable_mode(path: Path) -> bool`
- `reject_symlink_or_escape(path: Path, *, root: Path, root_kind: str) -> None`
- `scan_generated_residue(specs: list[PluginSpec]) -> list[ResidueIssue]`
- `build_manifest(spec: PluginSpec, *, root_kind: str) -> dict[str, ManifestEntry]`
- `diff_manifests(source: dict[str, ManifestEntry], cache: dict[str, ManifestEntry]) -> list[DiffEntry]`

`build_manifest` must fail before hashing if any discovered entry is a symlinked file or symlinked directory. Use `Path.lstat()` and `Path.is_symlink()` on every entry before `read_bytes()`. For non-symlink files, resolve the root and resolved file path and fail unless the resolved file is contained by the resolved root. The manifest diff must compare SHA256 and execution metadata; equal bytes with different mode, executable bit, or shebang status is `DiffKind.CHANGED`.

Residue rules must match the design:

```python
GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv"}
GENERATED_FILES = {".DS_Store"}
GENERATED_PATH_FRAGMENTS = {".codex/ticket-tmp"}
```

- [ ] **Step 4: Run manifest tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_manifests.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/turbo-mode/tools/refresh
git commit -m "feat: add turbo-mode refresh manifests"
```

## Task 3: Path Classifier And Smoke Selection

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/classifier.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`

- [ ] **Step 1: Write classifier tests for design examples**

Create tests for the concrete examples from the design:

```python
from __future__ import annotations

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
    assert_path(
        "handoff/1.6.0/scripts/session_state.py",
        outcome=PathOutcome.FAST_SAFE_WITH_COVERED_SMOKE,
        mutation_mode=MutationMode.FAST,
        coverage_status=CoverageStatus.COVERED,
    )


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
```

- [ ] **Step 2: Write current surface enumeration tests**

Add a parameterized test containing the current surface fixture lists in this plan. Expected outcomes:

- `handoff/1.6.0/hooks/hooks.json`: `guarded-only`.
- `handoff/1.6.0/scripts/defer.py`: `guarded-only`.
- `handoff/1.6.0/scripts/search.py`, `triage.py`, `session_state.py`: `fast-safe-with-covered-smoke`.
- `handoff/1.6.0/scripts/distill.py` and `ticket_parsing.py`: `coverage-gap-fail`.
- Other Handoff `scripts/*.py` not explicitly classified by the design: `coverage-gap-fail`.
- `ticket/1.4.0/hooks/hooks.json` and `hooks/ticket_engine_guard.py`: `guarded-only`.
- Ticket engine/parser/validation paths listed in guarded-only: `guarded-only`.
- Other Ticket `scripts/*.py` not explicitly classified by the design, including `scripts/__init__.py`: `coverage-gap-fail`.
- Both `.codex-plugin/plugin.json` paths: `coverage-gap-fail` until the app-server install request contract plan gives them deterministic coverage.

- [ ] **Step 3: Run classifier tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_classifier.py -q
```

Expected: fail because `classifier.py` does not exist.

- [ ] **Step 4: Implement classifier rules**

Create `classifier.py` with:

- `GUARDED_ONLY_PATTERNS`
- `FAST_SAFE_PATTERNS`
- `COVERAGE_GAP_PATTERNS`
- `SMOKE_BY_PATTERN`
- `is_executable_or_command_bearing_path(path: str, *, executable: bool) -> bool`
- `classify_diff_path(path: str, *, kind: DiffKind, source_text: str, cache_text: str, executable: bool) -> PathClassification`

Use `fnmatch.fnmatchcase` against canonical refresh paths. Guarded-only wins over fast-safe when both match. Coverage-gap wins over every other user-facing outcome when `coverage_status=coverage_gap`.

- [ ] **Step 5: Run classifier tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_classifier.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/tools/refresh
git commit -m "feat: add turbo-mode refresh classifier"
```

## Task 4: Command-Shape Projection And Semantic-Policy Triggers

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/command_projection.py`
- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_command_projection.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`

- [ ] **Step 1: Write command projection tests**

Create tests for command blocks, command-like lines, JSON payload examples, and command/state/action tables:

```python
from __future__ import annotations

from refresh.command_projection import extract_command_projection, has_semantic_policy_trigger


def test_projection_extracts_shell_blocks_and_command_lines() -> None:
    text = """# Command

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <TICKETS_DIR>
```

uv run pytest tests/test_ticket.py -q
"""

    projection = extract_command_projection(text)

    assert "python3 -B <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <TICKETS_DIR>" in projection.items
    assert "uv run pytest tests/test_ticket.py -q" in projection.items


def test_projection_extracts_command_table_rows() -> None:
    text = """| Command | Action |
| --- | --- |
| `/load` | load handoff |
"""

    projection = extract_command_projection(text)

    assert "/load" in " ".join(projection.items)


def test_semantic_policy_trigger_detects_runtime_authority_claim() -> None:
    assert has_semantic_policy_trigger(
        "Installed cache and runtime inventory authority changed during maintenance windows."
    )


def test_semantic_policy_trigger_ignores_plain_changelog_note() -> None:
    assert not has_semantic_policy_trigger("Fixed typo in heading and normalized capitalization.")
```

- [ ] **Step 2: Add classifier trigger tests**

Add tests asserting:

- A changed skill doc with unchanged command projection and no semantic-policy trigger remains `fast-safe-with-covered-smoke`.
- A changed skill doc with a new `python3` command becomes `coverage-gap-fail`.
- A changed skill doc with a runtime-authority semantic-policy trigger becomes `coverage-gap-fail`.
- Added or removed command-bearing docs compare against an empty projection and become `coverage-gap-fail`.

- [ ] **Step 3: Run projection and classifier tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_command_projection.py plugins/turbo-mode/tools/refresh/tests/test_classifier.py -q
```

Expected: fail because projection helpers do not exist and classifier does not consume them.

- [ ] **Step 4: Implement projection helpers**

Create `command_projection.py` with:

- `CommandProjection(items: tuple[str, ...], parser_warnings: tuple[str, ...])`
- `extract_command_projection(text: str) -> CommandProjection`
- `has_semantic_policy_trigger(text: str) -> bool`

Projection extraction must cover:

- fenced `bash`, `sh`, or `shell` command blocks;
- untyped fenced blocks only when the block contains a command-like line, a slash-command token, or a JSON object with request/action keys;
- JSON payload examples containing request/action keys;
- command-like lines beginning with `python`, `python3`, `uv`, `codex`, `ticket_`, or `./`;
- slash-command tokens such as `/save`, `/load`, `/ticket`, and `/ticket-triage`;
- markdown table rows when the header contains `Command`, or when a row cell contains a slash-command token or command-like launcher;
- sections with headings containing `Command`, `Workflow`, `Execute`, `Prepare`, `Payload`, `Recovery`, or `Policy` only when the section body contains one of the command projection items above.

Generic `state` or `action` prose and tables are not command projection by themselves. They are semantic-policy input only when they match the semantic trigger groups below. This keeps reference templates such as `handoff/1.6.0/references/format-reference.md` and synthesis guidance such as `handoff/1.6.0/skills/save/synthesis-guide.md` out of the command-projection fixture unless they gain concrete command tokens or command-bearing examples.

Semantic trigger detection must include these keyword groups:

- root authority;
- permission, approval, sandbox;
- prepare, execute, close, reopen, recover, repair, rollback;
- denial, enforcement, validation, hook;
- recovery, audit-log, evidence, redaction, certification;
- marketplace, global config, installed cache, runtime inventory;
- maintenance window, process gate, operator exclusivity.

- [ ] **Step 5: Wire projection into classifier**

In `classify_diff_path`, when the canonical path is under `skills/**`, `references/**`, or is `README.md`, `CHANGELOG.md`, or `HANDBOOK.md`:

- Compare source and cache command projections.
- For `added`, compare source projection with an empty cache projection.
- For `removed`, compare empty source projection with cache projection.
- If projections differ, return `coverage-gap-fail` with reason `command-shape-changed`.
- If semantic-policy triggers appear in source or cache text and the path has no deterministic proof, return `coverage-gap-fail` with reason `semantic-policy-trigger`.

- [ ] **Step 6: Run projection and classifier tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_command_projection.py plugins/turbo-mode/tools/refresh/tests/test_classifier.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add plugins/turbo-mode/tools/refresh
git commit -m "feat: detect refresh command-shape changes"
```

## Task 5: Terminal Plan-State Derivation

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/state_machine.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_state_machine.py`

- [ ] **Step 1: Write terminal precedence tests**

Create `test_state_machine.py` with tests for every precedence row:

```python
from __future__ import annotations

import pytest

from refresh.models import (
    CoverageState,
    FilesystemState,
    PlanAxes,
    PreflightState,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.state_machine import derive_terminal_plan_status


@pytest.mark.parametrize(
    ("axes", "expected"),
    [
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERAGE_GAP,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.BLOCKED,
                selected_mutation_mode=SelectedMutationMode.REFRESH,
            ),
            TerminalPlanStatus.BLOCKED_PREFLIGHT,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERAGE_GAP,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.REFRESH,
            ),
            TerminalPlanStatus.COVERAGE_GAP_BLOCKED,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.UNREPAIRABLE_MISMATCH,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            ),
            TerminalPlanStatus.UNREPAIRABLE_RUNTIME_CONFIG_MISMATCH,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.REPAIRABLE_MISMATCH,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
            ),
            TerminalPlanStatus.REPAIRABLE_RUNTIME_CONFIG_MISMATCH,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERED,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.GUARDED_REFRESH,
            ),
            TerminalPlanStatus.GUARDED_REFRESH_REQUIRED,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERED,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.REFRESH,
            ),
            TerminalPlanStatus.REFRESH_ALLOWED,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            ),
            TerminalPlanStatus.NO_DRIFT,
        ),
        (
            PlanAxes(
                filesystem_state=FilesystemState.NO_DRIFT,
                coverage_state=CoverageState.NOT_APPLICABLE,
                runtime_config_state=RuntimeConfigState.UNCHECKED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            ),
            TerminalPlanStatus.FILESYSTEM_NO_DRIFT,
        ),
    ],
)
def test_terminal_status_precedence(axes: PlanAxes, expected: TerminalPlanStatus) -> None:
    assert derive_terminal_plan_status(axes) == expected
```

- [ ] **Step 2: Write inconsistent-axis tests**

Add tests asserting:

- `runtime_config_state=repairable-mismatch` with `selected_mutation_mode != guarded-refresh` raises `RefreshError`.
- `filesystem_state=drift`, `coverage_state=covered`, and `selected_mutation_mode=none` raises `RefreshError`.
- `filesystem_state=no-drift` and `selected_mutation_mode=refresh` raises `RefreshError`.
- `filesystem_state=drift` with `runtime_config_state=unchecked` returns `blocked-preflight`, not a mutation-capable status.
- `filesystem_state=unknown`, `coverage_state=unknown`, `runtime_config_state=unknown`, or `selected_mutation_mode=unknown` returns `blocked-preflight` unless a higher-priority explicit block already applies.
- `derive_terminal_plan_status` never returns `refresh-allowed` or `guarded-refresh-required` when any required axis is unknown or unchecked.

Use this concrete test shape:

```python
from refresh.models import RefreshError


def test_drift_with_unchecked_runtime_config_fails_closed() -> None:
    axes = PlanAxes(
        filesystem_state=FilesystemState.DRIFT,
        coverage_state=CoverageState.COVERED,
        runtime_config_state=RuntimeConfigState.UNCHECKED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.REFRESH,
    )

    assert derive_terminal_plan_status(axes) == TerminalPlanStatus.BLOCKED_PREFLIGHT


@pytest.mark.parametrize(
    "axes",
    [
        PlanAxes(
            filesystem_state=FilesystemState.UNKNOWN,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.UNKNOWN,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.UNKNOWN,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.REFRESH,
        ),
        PlanAxes(
            filesystem_state=FilesystemState.DRIFT,
            coverage_state=CoverageState.COVERED,
            runtime_config_state=RuntimeConfigState.ALIGNED,
            preflight_state=PreflightState.PASSED,
            selected_mutation_mode=SelectedMutationMode.UNKNOWN,
        ),
    ],
)
def test_unknown_axes_fail_closed_to_blocked_preflight(axes: PlanAxes) -> None:
    assert derive_terminal_plan_status(axes) == TerminalPlanStatus.BLOCKED_PREFLIGHT


def test_inconsistent_axes_raise_refresh_error() -> None:
    with pytest.raises(RefreshError):
        derive_terminal_plan_status(
            PlanAxes(
                filesystem_state=FilesystemState.DRIFT,
                coverage_state=CoverageState.COVERED,
                runtime_config_state=RuntimeConfigState.ALIGNED,
                preflight_state=PreflightState.PASSED,
                selected_mutation_mode=SelectedMutationMode.NONE,
            )
        )
```

- [ ] **Step 3: Run state-machine tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_state_machine.py -q
```

Expected: fail because `state_machine.py` does not exist.

- [ ] **Step 4: Implement terminal derivation**

Create `state_machine.py` with:

- `validate_axes(axes: PlanAxes) -> None`
- `derive_terminal_plan_status(axes: PlanAxes) -> TerminalPlanStatus`

The implementation must follow the exact precedence table from the design, validate repairable marketplace mismatch as guarded-only planning, and fail closed for unproven axes. Unknown axis values and `filesystem_state=drift` with `runtime_config_state=unchecked` must derive `blocked-preflight`; inconsistent axis combinations that would let Plan 02 emit a mutation command from incomplete state must raise `RefreshError`.

- [ ] **Step 5: Run state-machine tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_state_machine.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/tools/refresh
git commit -m "feat: add turbo-mode refresh plan state machine"
```

## Task 6: Integration Fixture For Pure Core

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_manifests.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_state_machine.py`

- [ ] **Step 1: Add fixture-backed diff classification test**

Create a temporary source/cache pair that includes:

- one unchanged file;
- one fast-safe changed path;
- one guarded-only changed path;
- one coverage-gap changed path;
- one unmatched non-executable changed path;
- one generated residue path.

Assert:

- residue detection reports the generated path before diffing;
- after removing residue, diffing returns canonical paths;
- path classification preserves separate `mutation_mode` and `coverage_status`;
- the derived aggregate axes become `coverage-gap-blocked` when any changed path has `coverage_status=coverage_gap`.

- [ ] **Step 2: Add current-tree surface fixture test**

Use the actual repo source roots only for read-only discovery:

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HANDOFF_ROOT = REPO_ROOT / "plugins/turbo-mode/handoff/1.6.0"
TICKET_ROOT = REPO_ROOT / "plugins/turbo-mode/ticket/1.4.0"
```

Assert the discovered `scripts/*.py`, `hooks/*.py`, `hooks/hooks.json`, and `.codex-plugin/plugin.json` canonical paths equal the pinned lists in this plan. Also run `extract_command_projection` against every Markdown file under the Handoff and Ticket source roots and assert every file with a non-empty projection equals the pinned command-projection Markdown list in this plan. This test is intentional drift detection: if source surfaces or command-projection docs change, the refresh classifier must be reviewed and updated in the same commit.

- [ ] **Step 3: Run all checkpoint 01 tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: pass.

- [ ] **Step 4: Run lint**

Run:

```bash
uv run ruff check plugins/turbo-mode/tools/refresh
```

Expected: pass.

- [ ] **Step 5: Check ignored Python residue**

Run:

```bash
residue="$(find plugins/turbo-mode/tools/refresh \( -name __pycache__ -o -name '*.pyc' \) -print)"
if [ -n "$residue" ]; then
  printf '%s\n' "$residue"
  exit 1
fi
```

Expected: exit 0 with no output.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/tools/refresh
git commit -m "test: cover turbo-mode refresh classifier fixtures"
```

## Checkpoint 01 Verification Gate

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests -q
uv run ruff check plugins/turbo-mode/tools/refresh
residue="$(find plugins/turbo-mode/tools/refresh \( -name __pycache__ -o -name '*.pyc' \) -print)"
if [ -n "$residue" ]; then
  printf '%s\n' "$residue"
  exit 1
fi
git status --short
```

Expected:

- All refresh core tests pass.
- Ruff reports no issues.
- The residue check exits 0 and prints no ignored bytecode or `__pycache__` paths.
- Working tree contains only intentional plan/checkpoint changes or is clean after commit.
- No command reads or writes installed cache roots.
- No command reads or writes `/Users/jp/.codex/config.toml`.
- No command starts app-server.

## Hand-Off To Plan 02

Plan 02 may consume these public APIs:

- `build_manifest`
- `diff_manifests`
- `scan_generated_residue`
- `classify_diff_path`
- `extract_command_projection`
- `has_semantic_policy_trigger`
- `derive_terminal_plan_status`

Plan 02 must not reinterpret classifier outcomes. It should build `--dry-run` and `--plan-refresh` around this core, persist the separate state axes, and emit mutation commands only according to the terminal status.
