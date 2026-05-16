# Handoff Storage Authority Reseam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reseam `turbo_mode_handoff_runtime/storage_authority.py` into explicit storage-layout, storage-inspection, residual storage-authority, and chain-state modules without changing Handoff runtime behavior.

**Architecture:** Use hard moves, not compatibility re-export facades. Extract stable layout arithmetic first, then shared filesystem/git inspection helpers, then chain-state inventory, diagnostics, read, and lifecycle behavior. Keep residual `storage_authority.py` responsible for handoff discovery, candidate classification, and active/history eligibility.

**Tech Stack:** Python 3.11+, standard library, existing Handoff pytest suite.

---

## Required Preconditions

- Handoff CI exists and passes before starting this plan.
- Active-write proxy facade residue has already been removed or intentionally enforced by tests.
- `LEGACY_CONSUMED_PREFIX` is shared from `storage_primitives.py`.
- Contributor architecture docs exist and state that `scripts/` contains executable CLI facades only.
- The executor has read the live `storage_authority.py`, `active_writes.py`, `load_transactions.py`, `project_paths.py`, `session_state.py`, `tests/test_storage_authority.py`, `tests/test_session_state.py`, `tests/test_active_writes.py`, and `tests/test_runtime_namespace.py` files before editing.

## Scope

In scope:

- Create `turbo_mode_handoff_runtime/storage_layout.py`.
- Create `turbo_mode_handoff_runtime/storage_inspection.py`.
- Create `turbo_mode_handoff_runtime/chain_state.py`.
- Update direct importers to use the new module owners.
- Preserve public CLI command behavior and JSON payload schemas.
- Add or update tests that prove moved symbols are no longer exposed from old modules.
- Run focused behavioral gates before the full Handoff suite.

Out of scope:

- Refactoring `active_writes.write_active_handoff()` beyond import updates required by the new module boundaries.
- Splitting `session_state.main()`.
- Moving or redesigning lock primitives.
- Installed-cache mutation, guarded refresh, plugin install, or runtime inventory mutation.
- Publishing ignored handoff artifacts.

Deferred follow-ups:

- Active-write complexity split after the storage-layout and chain-state APIs are stable.
- `session_state.main()` command-dispatch decomposition after this reseam lands with CLI regression coverage.

## Target Module Topology

`turbo_mode_handoff_runtime/storage_layout.py` owns:

- `StorageLayout`
- `get_storage_layout(project_root: Path) -> StorageLayout`
- Layout path arithmetic only.

`turbo_mode_handoff_runtime/storage_inspection.py` owns:

- `git_visibility(project_root: Path, path: Path) -> str`
- `fs_status(path: Path) -> str`
- `is_relative_to(path: Path, root: Path) -> bool`
- Private `_inside_git_worktree(project_root: Path) -> bool`

`turbo_mode_handoff_runtime/storage_authority.py` remains responsible for:

- `StorageLocation`
- `SelectionEligibility`
- `HandoffCandidate`
- `HandoffInventory`
- `discover_handoff_inventory()`
- `eligible_active_candidates()`
- `eligible_history_candidates()`
- `root_for_location()`
- Handoff discovery, candidate classification, active-selection ordering, history deduplication, legacy-active opt-in checks, and consumed legacy-active registry classification.

`turbo_mode_handoff_runtime/chain_state.py` owns:

- `ChainStateDiagnosticError`
- `chain_state_recovery_inventory()`
- `read_chain_state()`
- `mark_chain_state_consumed()`
- `continue_chain_state()`
- `abandon_primary_chain_state()`
- Private chain-state selector, marker, parser, TTL, stable-key, and operator-diagnostic helpers.
- Plain legacy-state parsing through `storage_primitives.LEGACY_CONSUMED_PREFIX`; `chain_state.py` must not re-export the prefix, and `storage_authority.py` must not remain part of that prefix contract.
- `_project_relative_path()` if its audited callers remain chain-state-only.
- `_read_json_object()` if its audited callers remain chain-state-only and it remains chain-state-marker specific.

## Global Rules

- Use hard moves. Do not re-export moved symbols from `storage_authority.py`.
- Do not import private `_`-prefixed helpers across runtime module boundaries.
- Do not add new `scripts.*` imports.
- Do not touch lock primitives in this plan. Lock behavior already belongs to `storage_primitives.py` and is covered by `tests/test_storage_primitives.py`.
- Do not claim installed-runtime success from source tests.
- Every commit boundary must leave the full Handoff suite green.
- Before each slice, run `git status --short --branch` and preserve unrelated dirty work.
- Keep `LEGACY_CONSUMED_PREFIX` publicly owned by `storage_primitives.py`; other modules may use it through a private module alias but must not expose a new public prefix contract.

## Hard Stops

- Stop if a slice requires installed-cache mutation to prove source behavior.
- Stop if a slice changes JSON payload schemas without updating focused behavioral tests and skill/reference docs in the same commit.
- Stop if a task cannot run the focused gate and full Handoff suite green before commit.
- Stop if a proposed move requires a private cross-module import.
- Stop if `chain_state.py` cannot import the public `StorageLocation` owner without an import cycle. Resolve ownership in a small public enum module before moving chain-state behavior.
- Stop if the helper audit finds a shared helper that is not routed to a public owner before chain-state extraction.
- Stop if runtime module inventory, no-reexport, or direct launcher smoke coverage is missing after an import-boundary change.

## Slice Order

1. Hard-move layout ownership into `storage_layout.py`.
2. Audit helper ownership and extract shared inspection helpers into `storage_inspection.py`.
3. Hard-move chain-state inventory, diagnostics, read, and lifecycle behavior into `chain_state.py`.
4. Tighten residual `storage_authority.py` tests and docs for the new topology.

## Slice 1: Hard-Move Storage Layout

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_layout.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
- Create or modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_layout.py`

- [ ] **Step 1: Add layout module inventory coverage**

  Update `tests/test_runtime_namespace.py` so `RUNTIME_MODULES` includes `storage_layout.py`.

- [ ] **Step 2: Move layout behavior test to the new owner**

  Move the existing layout assertion into `tests/test_storage_layout.py` and import from `turbo_mode_handoff_runtime.storage_layout`. Do not duplicate it. Remove the old `get_storage_layout` import and layout assertion from `tests/test_storage_authority.py`, because this slice must not keep a storage-layout compatibility path through `storage_authority.py`.

  Required assertion shape:

  ```python
  from pathlib import Path

  from turbo_mode_handoff_runtime.storage_layout import get_storage_layout


  def test_storage_layout_uses_codex_handoffs_as_primary(tmp_path: Path) -> None:
      layout = get_storage_layout(tmp_path)

      assert layout.primary_active_dir == tmp_path / ".codex" / "handoffs"
      assert layout.primary_archive_dir == tmp_path / ".codex" / "handoffs" / "archive"
      assert layout.primary_state_dir == tmp_path / ".codex" / "handoffs" / ".session-state"
      assert layout.legacy_active_dir == tmp_path / "docs" / "handoffs"
      assert layout.legacy_archive_dir == tmp_path / "docs" / "handoffs" / "archive"
      assert (
          layout.previous_primary_hidden_archive_dir
          == tmp_path / ".codex" / "handoffs" / ".archive"
      )
  ```

- [ ] **Step 3: Add no-reexport coverage**

  Update `tests/test_storage_authority.py` with a no-reexport assertion:

  ```python
  def test_storage_authority_does_not_export_storage_layout_facade() -> None:
      import turbo_mode_handoff_runtime.storage_authority as storage_authority

      assert not hasattr(storage_authority, "StorageLayout")
      assert not hasattr(storage_authority, "get_storage_layout")
  ```

- [ ] **Step 4: Create `storage_layout.py`**

  Move `StorageLayout` and `get_storage_layout()` from `storage_authority.py` into `storage_layout.py`.

  Required module content:

  ```python
  """Storage layout paths for Handoff runtime state."""

  from __future__ import annotations

  from dataclasses import dataclass
  from pathlib import Path


  @dataclass(frozen=True)
  class StorageLayout:
      project_root: Path
      primary_active_dir: Path
      primary_archive_dir: Path
      primary_state_dir: Path
      legacy_active_dir: Path
      legacy_archive_dir: Path
      legacy_state_dir: Path
      previous_primary_hidden_archive_dir: Path


  def get_storage_layout(project_root: Path) -> StorageLayout:
      """Return the post-cutover Handoff storage layout for a project root."""
      root = project_root.resolve()
      primary = root / ".codex" / "handoffs"
      legacy = root / "docs" / "handoffs"
      return StorageLayout(
          project_root=root,
          primary_active_dir=primary,
          primary_archive_dir=primary / "archive",
          primary_state_dir=primary / ".session-state",
          legacy_active_dir=legacy,
          legacy_archive_dir=legacy / "archive",
          legacy_state_dir=legacy / ".session-state",
          previous_primary_hidden_archive_dir=primary / ".archive",
      )
  ```

- [ ] **Step 5: Update layout importers**

  Update direct layout consumers to import from `turbo_mode_handoff_runtime.storage_layout`.

  Required direct consumers:

  - `storage_authority.py`
  - `project_paths.py`
  - `active_writes.py`
  - `load_transactions.py`
  - tests that use `get_storage_layout`

  In `storage_authority.py`, do not import the symbols directly. Use a private module alias so moved names are not visible as `storage_authority.StorageLayout` or `storage_authority.get_storage_layout`:

  ```python
  from turbo_mode_handoff_runtime import storage_layout as _storage_layout
  ```

  Internal type annotations should use `_storage_layout.StorageLayout`, and internal calls should use `_storage_layout.get_storage_layout(...)`.

- [ ] **Step 6: Run focused layout gate**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_storage_layout.py tests/test_storage_authority.py::test_storage_authority_does_not_export_storage_layout_facade tests/test_runtime_namespace.py::test_runtime_module_inventory_is_explicit -q -p no:cacheprovider
  ```

  Expected: all selected tests pass.

- [ ] **Step 7: Run launcher smoke from repo root**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help
  ```

  Expected: command exits `0` and prints help text.

- [ ] **Step 8: Run launcher smoke from repo root**

  Run a direct CLI facade smoke that imports `storage_authority.py` through a command-facing launcher:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py --help
  ```

  Expected: command exits `0` and prints help text.

- [ ] **Step 9: Run full Handoff suite**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
  ```

  Expected: full suite passes.

## Slice 2: Audit Helpers And Extract Shared Storage Inspection

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_inspection.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Create: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_inspection.py`

- [ ] **Step 1: Audit private helper callers before moving code**

  Run these commands and inspect every hit:

  ```bash
  rg -n "_project_relative_path\(|_absolute_path_key\(|_git_visibility\(|_fs_status\(|_is_relative_to\(|_inside_git_worktree\(|_read_json_object\(|_chain_state_marker_status\(|_parse_chain_state\(" plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py
  rg -n "def _project_relative_path|def _absolute_path_key|def _git_visibility|def _fs_status|def _is_relative_to|def _inside_git_worktree|def _read_json_object|def _chain_state_marker_status|def _parse_chain_state" plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py
  ```

  Required routing decisions:

  - `_git_visibility()` becomes public `git_visibility()` in `storage_inspection.py`.
  - `_fs_status()` becomes public `fs_status()` in `storage_inspection.py`.
  - `_is_relative_to()` becomes public `is_relative_to()` in `storage_inspection.py`.
  - `_inside_git_worktree()` moves as a private helper in `storage_inspection.py`.
  - `_absolute_path_key()` stays in `storage_authority.py` because it is discovery ordering only.
  - `_project_relative_path()` moves with chain-state only if the audit still shows chain-state-only callers.
  - `_read_json_object()` moves with chain-state only if the audit still shows chain-state-marker-only callers.
  - `_chain_state_marker_status()` and `_parse_chain_state()` move with chain-state if their callers remain inside the chain-state inventory/read/lifecycle group.

  Hard stop: if any helper needed by `chain_state.py` also has residual discovery/classification callers and is not already covered by `storage_inspection.py`, promote it to a public helper in `storage_inspection.py` with tests before Slice 3.

- [ ] **Step 2: Add inspection module inventory coverage**

  Update `tests/test_runtime_namespace.py` so `RUNTIME_MODULES` includes `storage_inspection.py`.

- [ ] **Step 3: Create storage-inspection tests**

  Add `tests/test_storage_inspection.py` covering:

  - `is_relative_to()` returns `True` for child paths and `False` for sibling paths.
  - `fs_status()` returns `missing`, `regular-file`, `directory`, and `symlink`.
  - `git_visibility()` returns `not-git-repo` outside a git worktree.
  - `git_visibility()` returns `tracked-conflict` for a tracked path inside a git worktree.

  Required tracked-path assertion shape:

  ```python
  import subprocess
  from pathlib import Path

  from turbo_mode_handoff_runtime.storage_inspection import git_visibility


  def test_git_visibility_reports_tracked_conflict(tmp_path: Path) -> None:
      subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
      subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
      subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
      handoff = tmp_path / ".codex" / "handoffs" / "2026-05-13_12-00_primary.md"
      handoff.parent.mkdir(parents=True)
      handoff.write_text("---\ntitle: Primary\n---\n", encoding="utf-8")
      subprocess.run(["git", "add", str(handoff.relative_to(tmp_path))], cwd=tmp_path, check=True)

      assert git_visibility(tmp_path, handoff) == "tracked-conflict"
  ```

- [ ] **Step 4: Create `storage_inspection.py`**

  Move and rename the shared inspection helpers:

  - `_git_visibility()` to `git_visibility()`
  - `_fs_status()` to `fs_status()`
  - `_is_relative_to()` to `is_relative_to()`
  - `_inside_git_worktree()` remains private in this module

  `storage_inspection.py` must not import `storage_authority.py`.

- [ ] **Step 5: Update residual storage-authority callers**

  Update `storage_authority.py` to import public helpers from `storage_inspection.py`.

  Required form:

  ```python
  from turbo_mode_handoff_runtime.storage_inspection import (
      fs_status as _fs_status,
      git_visibility as _git_visibility,
      is_relative_to as _is_relative_to,
  )
  ```

  This keeps existing private call sites readable inside `storage_authority.py` without exporting private helpers across module boundaries.

- [ ] **Step 6: Verify no lock code moved**

  Confirm that `storage_primitives.py`, `active_writes.py`, and `load_transactions.py` still own lock primitives and operation-specific lock wrappers.

  Run:

  ```bash
  rg -n "def acquire_lock|def release_lock|def _try_recover_stale_lock|LockPolicy|def _acquire_lock" plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py
  ```

  Expected: lock primitives remain in `storage_primitives.py`; operation wrappers remain in `active_writes.py` and `load_transactions.py`.

- [ ] **Step 7: Run focused inspection gate**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_storage_inspection.py tests/test_storage_authority.py::test_tracked_primary_active_source_is_blocked tests/test_runtime_namespace.py::test_runtime_module_inventory_is_explicit -q -p no:cacheprovider
  ```

  Expected: all selected tests pass.

- [ ] **Step 8: Run launcher smoke from repo root**

  Run a direct CLI facade smoke that imports `storage_authority.py` through a command-facing launcher:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py --help
  ```

  Expected: command exits `0` and prints help text.

- [ ] **Step 9: Run full Handoff suite**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
  ```

  Expected: full suite passes.

## Slice 3: Hard-Move Chain State

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/chain_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- Create or modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_chain_state.py`

- [ ] **Step 1: Add chain-state module inventory coverage**

  Update `tests/test_runtime_namespace.py` so `RUNTIME_MODULES` includes `chain_state.py`.

- [ ] **Step 2: Add no-reexport coverage for chain-state symbols**

  Add or update `tests/test_storage_authority.py` so `storage_authority.py` does not expose moved chain-state symbols.

  Required assertion shape:

  ```python
  def test_storage_authority_does_not_export_chain_state_facade() -> None:
      import turbo_mode_handoff_runtime.storage_authority as storage_authority

      moved_exports = {
          "CHAIN_STATE_TTL_SECONDS",
          "ChainStateDiagnosticError",
          "LEGACY_CONSUMED_PREFIX",
          "chain_state_recovery_inventory",
          "read_chain_state",
          "mark_chain_state_consumed",
          "continue_chain_state",
          "abandon_primary_chain_state",
      }
      for name in moved_exports:
          assert not hasattr(storage_authority, name)
  ```

- [ ] **Step 3: Create `chain_state.py`**

  Move these public symbols from `storage_authority.py` into `chain_state.py`:

  - `CHAIN_STATE_TTL_SECONDS`, renamed to private `_CHAIN_STATE_TTL_SECONDS`
  - `ChainStateDiagnosticError`
  - `chain_state_recovery_inventory()`
  - `read_chain_state()`
  - `mark_chain_state_consumed()`
  - `continue_chain_state()`
  - `abandon_primary_chain_state()`

  Move their private chain-state helpers only after the Slice 2 audit confirms they are not residual discovery/classification helpers.

  First resolve the `StorageLocation` dependency explicitly. Default to keeping `StorageLocation` public in `storage_authority.py` and importing it from `chain_state.py`. Immediately after creating `chain_state.py`, run the structural import smoke below before continuing. If this smoke fails because of an import cycle, stop and move `StorageLocation` into a small public enum owner before extracting the rest of chain-state behavior.

  Expected private chain-state helper set if the audit confirms current ownership:

  - `_CHAIN_STATE_TTL_SECONDS`
  - `_operator_error()`
  - `_select_chain_state_candidate()`
  - `_state_candidate_paths()`
  - `_state_like_residue_paths()`
  - `_chain_state_record()`
  - `_chain_state_marker_status()`
  - `_chain_state_stable_key()`
  - `_chain_state_format()`
  - `_parse_chain_state()`
  - `_apply_chain_state_ttl()`
  - `_parse_tokenized_chain_state()`
  - `_parse_plain_chain_state()`
  - `_invalid_chain_state()`
  - `_resume_token_from_state_filename()`
  - `_project_relative_path()`
  - `_age_seconds()`
  - `_read_json_object()`
  - `_chain_state_diagnostic()`

  `chain_state.py` should import:

  ```python
  from turbo_mode_handoff_runtime import storage_primitives as _storage_primitives
  from turbo_mode_handoff_runtime.storage_layout import StorageLayout, get_storage_layout
  from turbo_mode_handoff_runtime.storage_inspection import fs_status, git_visibility
  from turbo_mode_handoff_runtime.storage_primitives import (
      sha256_regular_file_or_none as _content_sha256,
      write_json_atomic as _write_json_atomic,
  )
  from turbo_mode_handoff_runtime.storage_authority import StorageLocation
  ```

  Plain legacy-state parsing must use `_storage_primitives.LEGACY_CONSUMED_PREFIX`; do not import or expose `LEGACY_CONSUMED_PREFIX` as a public `chain_state.py` attribute.

  Run the import smoke from the plugin root:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 python -c "import turbo_mode_handoff_runtime.chain_state; import turbo_mode_handoff_runtime.storage_authority"
  ```

  Expected: command exits `0`.

- [ ] **Step 4: Update session-state function-local imports**

  Update all function-local imports in `session_state.py` that currently import chain-state symbols from `storage_authority.py`.

  Required command branches:

  - `chain-state-recovery-inventory`
  - `list-chain-state`
  - `read-chain-state`
  - `mark-chain-state-consumed`
  - `continue-chain-state`
  - `abandon-primary-chain-state`

  All moved symbols must import from `turbo_mode_handoff_runtime.chain_state`.

- [ ] **Step 5: Update active-write chain-state imports**

  Update `active_writes.py` so `_continue_legacy_chain_state_if_unambiguous()` uses `ChainStateDiagnosticError`, `read_chain_state()`, and `continue_chain_state()` from `chain_state.py`.

- [ ] **Step 6: Update tests to import moved symbols from chain-state**

  Update tests that directly import moved chain-state symbols.

  Required files:

  - `tests/test_storage_authority.py`
  - `tests/test_session_state.py`
  - `tests/test_active_writes.py`
  - new or updated `tests/test_chain_state.py`

  Update the legacy consumed-prefix contract in `tests/test_session_state.py` so it no longer imports `LEGACY_CONSUMED_PREFIX` from `storage_authority.py` or `chain_state.py`. Rename the test to make the single public owner explicit:

  ```python
  def test_legacy_consumed_prefix_is_storage_primitives_owned() -> None:
      from turbo_mode_handoff_runtime import storage_primitives
      import turbo_mode_handoff_runtime.chain_state as chain_state
      from turbo_mode_handoff_runtime.session_state import LEGACY_CONSUMED_PREFIX as state_prefix

      assert storage_primitives.LEGACY_CONSUMED_PREFIX == "MIGRATED:"
      assert state_prefix == storage_primitives.LEGACY_CONSUMED_PREFIX
      assert not hasattr(chain_state, "LEGACY_CONSUMED_PREFIX")
  ```

- [ ] **Step 7: Run focused structural gate**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_runtime_namespace.py::test_runtime_module_inventory_is_explicit tests/test_storage_authority.py::test_storage_authority_does_not_export_chain_state_facade tests/test_session_state.py::test_legacy_consumed_prefix_is_storage_primitives_owned -q -p no:cacheprovider
  ```

  Expected: selected tests pass.

- [ ] **Step 8: Run focused behavioral-equivalence gate**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest \
    tests/test_session_state.py::test_mark_chain_state_consumed_suppresses_unresolved_legacy_state \
    tests/test_session_state.py::test_continue_chain_state_from_legacy_writes_primary_and_marks_source_consumed \
    tests/test_session_state.py::test_abandon_primary_chain_state_moves_exact_primary_and_unblocks_legacy \
    tests/test_session_state.py::test_consumed_legacy_state_marker_survives_copied_project_root \
    tests/test_session_state.py::test_continue_chain_state_from_state_like_residue_mints_primary_token \
    tests/test_active_writes.py::test_active_writer_flow_cli_bridges_legacy_state_and_marks_source_consumed \
    -q -p no:cacheprovider
  ```

  Expected: all selected tests pass. This gate proves marker writes, primary-state continuation, primary abandonment, copied-root marker stability, state-like residue continuation, and active-writer chain-state bridging.

- [ ] **Step 9: Run launcher smoke from repo root**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help
  ```

  Expected: command exits `0` and prints help text.

- [ ] **Step 10: Run full Handoff suite**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
  ```

  Expected: full suite passes.

## Slice 4: Residual Storage Authority Topology Documentation

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/README.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md`
- Modify as needed: `plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority_inventory.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json`
- Create or modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_architecture_docs.py`

- [ ] **Step 1: Update storage-authority module docstring**

  Update the docstring to state that `storage_authority.py` owns handoff discovery, candidate classification, active/history selection, and legacy-active policy checks. It must not claim ownership of storage layout or chain-state lifecycle after the move.

- [ ] **Step 2: Update contributor/runtime boundary docs**

  Update README, CONTRIBUTING, and architecture docs so the module topology matches this plan:

  - `storage_layout.py`: storage paths.
  - `storage_inspection.py`: filesystem and git inspection helpers.
  - `storage_authority.py`: handoff discovery and selection authority.
  - `chain_state.py`: chain-state inventory, diagnostics, read, and lifecycle.
  - `scripts/`: executable CLI facades only.

- [ ] **Step 3: Add stale-topology and current-topology doc coverage**

  Add a docs topology test that reads README, CONTRIBUTING, and ARCHITECTURE. The test must reject stale ownership claims after the reseam and require each doc to state the current module-owner topology.

  Required assertion shape:

  ```python
  import re
  from pathlib import Path


  PLUGIN_ROOT = Path(__file__).parent.parent
  TOPOLOGY_DOCS = [
      PLUGIN_ROOT / "README.md",
      PLUGIN_ROOT / "CONTRIBUTING.md",
      PLUGIN_ROOT / "references" / "ARCHITECTURE.md",
  ]
  STALE_TOPOLOGY_PATTERNS = [
      r"`storage_authority\.py`[^.\n]*(owns|handles)[^.\n]*storage layout",
      r"chain-state[^.\n]*(from|in) `storage_authority\.py`",
      r"`storage_authority\.py`[^.\n]*(owns|handles)[^.\n]*chain-state",
  ]
  REQUIRED_TOPOLOGY_CLAIMS = {
      "`storage_layout.py`": "storage paths",
      "`storage_inspection.py`": "filesystem and git inspection",
      "`storage_authority.py`": "handoff discovery and selection",
      "`chain_state.py`": "chain-state inventory, diagnostics, read, and lifecycle",
  }


  def test_topology_docs_do_not_claim_old_storage_authority_ownership() -> None:
      for path in TOPOLOGY_DOCS:
          text = path.read_text(encoding="utf-8")
          for stale_pattern in STALE_TOPOLOGY_PATTERNS:
              assert re.search(stale_pattern, text) is None, path


  def test_topology_docs_state_current_runtime_module_owners() -> None:
      for path in TOPOLOGY_DOCS:
          text = path.read_text(encoding="utf-8")
          for module_name, ownership in REQUIRED_TOPOLOGY_CLAIMS.items():
              assert module_name in text, path
              assert ownership in text, path
  ```

- [ ] **Step 4: Refresh storage-authority inventory fixture**

  If README, references, quality-check text, or refresh-smoke storage text changed, refresh the generated inventory fixture. `storage_authority_inventory.py` is an import-only runtime helper, not a CLI facade; do not add command-mode behavior just to update the fixture.

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 python -c "from turbo_mode_handoff_runtime.storage_authority_inventory import build_inventory, check_inventory, default_fixture_path, default_plugin_root, default_repo_root, render_inventory; plugin_root = default_plugin_root(); fixture_path = default_fixture_path(plugin_root); current = build_inventory(repo_root=default_repo_root(), plugin_root=plugin_root); fixture_path.write_text(render_inventory(current), encoding='utf-8'); check_inventory(current, fixture_path)"
  ```

  Expected: command exits `0`; `tests/fixtures/storage_authority_inventory.json` reflects the current docs hashes; no command-mode entrypoint was added to `storage_authority_inventory.py`.

- [ ] **Step 5: Run docs-focused tests**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_architecture_docs.py tests/test_skill_docs.py tests/test_runtime_namespace.py tests/test_storage_authority_inventory.py -q -p no:cacheprovider
  ```

  Expected: selected tests pass.

- [ ] **Step 6: Run full Handoff suite**

  Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
  ```

  Expected: full suite passes.

## Final Verification

Run after all slices:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime plugins/turbo-mode/handoff/1.6.0/tests
git diff --check
```

Expected:

- Full Handoff suite passes.
- Root launcher smokes exit `0`.
- Ruff passes for changed Handoff runtime and tests.
- `git diff --check` reports no whitespace errors.
- `git status --short --branch` shows only intentional source, test, and docs changes.

## Deferred Follow-Up Scope

Do not implement these in this plan:

- `active_writes.write_active_handoff()` complexity refactor.
- `session_state.main()` command-dispatch split.
- Lock primitive redesign.
- Installed-cache refresh or runtime mutation.

Follow-up plans should depend on this reseam only after all final verification gates pass.
