# PR #15 Review Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two must-fix and three important findings from the PR #15 multi-agent review before that PR merges, without touching the verified-clean refactors.

**Architecture:** One source behaviour fix (transaction-prune allow-list) plus three test/doc changes that pin contracts the review found unenforced. All work lands on the existing open PR branch `chore/handoff-runtime-debt-elimination`; no new branch, no installed-cache/runtime mutation, source + tests + docs only.

**Tech Stack:** Python 3.11/3.13, `pytest`, `ruff`, stdlib `ast`. Repo bytecode-safe harness required for every test run.

**Task order == commit order.** Execute Task 1→2→3→4; each task ends with exactly one commit (A→B→C→D, chronological). Do not reorder; do not defer a commit to a later task.

---

## Preconditions (verify before Task 1)

- [ ] **P1:** On branch `chore/handoff-runtime-debt-elimination`; no modified or staged *tracked* files.

Run: `git status --short --branch`
Expected: header `## chore/handoff-runtime-debt-elimination...`. The only acceptable entry is the untracked plan doc itself (`?? docs/superpowers/plans/2026-05-15-handoff-runtime-debt-elimination-review-followup.md`). Any ` M`, `M `, `A `, or other `??` under `plugins/` or `tests/` means the tree is dirty — stop and report.

- [ ] **P2:** Baseline suite green at the reviewed count.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q`
Expected: `617 passed`. Record the per-module baseline for the three modules this plan touches:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_session_state.py tests/test_runtime_namespace.py tests/test_storage_authority.py tests/test_active_writes.py --co -q | tail -1`
Note the four collected counts; the final gate checks **deltas against these**, not a brittle global integer.

**Plan-wide stop condition:** if a step marked "expected FAIL" instead passes (or an "expected PASS" characterization step fails), stop and report. That means live code diverges from the review's findings and the plan must be re-derived against current code — do not force the step through.

**Commit rules:** one commit per task, named files only (never `git add -A`/`.`), pre-commit hooks must run (no `--no-verify`). Commit messages end with the repo's `Co-Authored-By` trailer.

---

## Task 1 — Transaction-prune allow-list: never prune in-flight/recovery records (must-fix #1) → Commit A

**Why:** `session_state.py:224-227` prunes every transaction past TTL whose `status != "pending"`. The write-side lifecycle uses non-`pending` non-terminal statuses (`pending_before_write`, `content-generated`, `content_mismatch`, `write-pending`, `cleanup_failed`, `reservation_conflict`); the deny-list silently deletes those operator-recovery records. Invert to an allow-list keyed on the lifecycle's own terminal set, treating non-string/`None` status as malformed-and-prunable (matching the existing "unreadable/malformed past TTL is safe to drop" intent).

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py` (add constant before `def _delete_path` at line 46; replace predicate at lines 224-227)
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py` (append after line 276)

Terminal set is derived from the lifecycle, not invented: `active_writes.py:372` checks `record.get("status") in {"committed", "abandoned", "reservation_expired"}` (write-transaction terminal); `load_transactions.py` transitions records to `"completed"` (line 365) and `"abandoned"` (line 498) (load-transaction terminal). Union → `{"committed", "completed", "abandoned", "reservation_expired"}`.

- [ ] **Step 1: Write the failing regression test**

Append to `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py` after line 276 (the file already imports `json`, `os`, `Path`, `prune_old_state_files`):

```python
def test_prune_keeps_in_flight_and_recovery_write_transactions(tmp_path: Path) -> None:
    """Regression (PR #15 review #1): non-'pending' in-flight / operator-recovery
    write-transaction records must survive TTL prune."""
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    transactions = state_dir / "transactions"
    transactions.mkdir()

    in_flight_statuses = [
        "pending",
        "pending_before_write",
        "content-generated",
        "content_mismatch",
        "write-pending",
        "cleanup_failed",
        "reservation_conflict",
    ]
    kept: list[Path] = []
    for status in in_flight_statuses:
        path = transactions / f"{status}.json"
        path.write_text(json.dumps({"status": status}), encoding="utf-8")
        old = path.stat().st_mtime - (25 * 60 * 60)
        os.utime(path, (old, old))
        kept.append(path)

    deleted = prune_old_state_files(state_dir=state_dir)

    for path in kept:
        assert path.exists(), f"{path.name} was pruned but is in-flight/recovery"
        assert path not in deleted
```

- [ ] **Step 2: Run it — verify it FAILS on current code**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_session_state.py::test_prune_keeps_in_flight_and_recovery_write_transactions`
Expected: **FAIL** — `AssertionError: pending_before_write.json was pruned but is in-flight/recovery`.

If it PASSES, stop (live code already differs from finding #1).

- [ ] **Step 3: Add the terminal-status constant**

In `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`, insert immediately before `def _delete_path(path: Path, *, context: str) -> bool:` (currently line 46):

```python
# Terminal transaction statuses, derived from the lifecycle's own terminal
# transitions: the write-transaction terminal check in active_writes
# ({"committed", "abandoned", "reservation_expired"}) plus the
# load-transaction terminal transitions in load_transactions ("completed",
# "abandoned"). Anything else is in-flight or an operator-recovery signal.
TERMINAL_TRANSACTION_STATUSES = frozenset(
    {"committed", "completed", "abandoned", "reservation_expired"}
)


```

- [ ] **Step 4: Replace the deny-rule with the allow-list**

Replace exactly this block (currently `session_state.py:224-227`):

```python
                # Never prune in-flight ("pending") transactions. Any terminal,
                # unreadable, or malformed record past the TTL is safe to drop.
                if status == "pending":
                    continue
```

with:

```python
                # Allow-list, not deny-list: past the TTL, prune only genuinely
                # terminal records, plus unreadable/malformed/typeless records
                # (status is None or a non-string). Any string status not in the
                # terminal set is in-flight or an operator-recovery signal and is
                # kept (e.g. pending, write-pending, cleanup_failed,
                # content_mismatch, reservation_conflict).
                prunable = (
                    not isinstance(status, str)
                    or status in TERMINAL_TRANSACTION_STATUSES
                )
                if not prunable:
                    continue
```

- [ ] **Step 5: Run the regression test — verify it PASSES**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_session_state.py::test_prune_keeps_in_flight_and_recovery_write_transactions`
Expected: **PASS**.

- [ ] **Step 6: Add characterization tests (must stay green — pin the documented intent under the new rule)**

Append after the Step 1 test:

```python
def test_prune_drops_terminal_unreadable_and_malformed_records_past_ttl(
    tmp_path: Path,
) -> None:
    """Characterization: the allow-list still drops genuinely terminal records
    and the documented unreadable/malformed/typeless cases (including a
    present-but-non-string status value, which is malformed)."""
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    transactions = state_dir / "transactions"
    transactions.mkdir()

    def _stale(name: str, body: str) -> Path:
        path = transactions / name
        path.write_text(body, encoding="utf-8")
        old = path.stat().st_mtime - (25 * 60 * 60)
        os.utime(path, (old, old))
        return path

    committed = _stale("committed.json", json.dumps({"status": "committed"}))
    reservation_expired = _stale(
        "reservation-expired.json", json.dumps({"status": "reservation_expired"})
    )
    invalid_json = _stale("garbage.json", "{not json")
    non_dict = _stale("list.json", "[]")
    no_status = _stale("no-status.json", json.dumps({"operation": "load"}))
    junk_value = _stale("junk-value.json", json.dumps({"status": 42}))

    deleted = prune_old_state_files(state_dir=state_dir)

    for path in (
        committed,
        reservation_expired,
        invalid_json,
        non_dict,
        no_status,
        junk_value,
    ):
        assert not path.exists(), f"{path.name} should have been pruned"
        assert path in deleted


def test_prune_ttl_boundary_keeps_records_at_or_within_cutoff(tmp_path: Path) -> None:
    """Characterization: prune uses `st_mtime >= cutoff -> keep`. A terminal
    record exactly at the cutoff is kept; just inside is kept; just past is
    dropped."""
    import time

    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    transactions = state_dir / "transactions"
    transactions.mkdir()
    cutoff = time.time() - (24 * 60 * 60)

    def _at(name: str, mtime: float) -> Path:
        path = transactions / name
        path.write_text(json.dumps({"status": "completed"}), encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path

    at_cutoff = _at("at.json", cutoff)
    within = _at("within.json", cutoff + 5)
    past = _at("past.json", cutoff - 5)

    prune_old_state_files(state_dir=state_dir)

    assert at_cutoff.exists()  # mtime >= cutoff -> kept
    assert within.exists()
    assert not past.exists()  # terminal and strictly past cutoff -> pruned


def test_prune_handles_missing_transactions_dir(tmp_path: Path) -> None:
    """Characterization: absent transactions/ dir must not raise."""
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()

    assert prune_old_state_files(state_dir=state_dir) == []
```

- [ ] **Step 7: Run the module + verify per-module delta and the preserved baseline test**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_session_state.py`
Expected: **PASS**; collected count = P2 baseline for this module **+ 4**. The pre-existing `test_prune_old_state_files_prunes_terminal_transactions` must still pass (proves intended behaviour preserved: `completed`/`abandoned` still pruned, `pending` still kept).

- [ ] **Step 8: Lint changed files**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
Expected: `All checks passed!`

- [ ] **Step 9: Commit A**

```bash
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py
git commit -m "fix: prune only terminal transactions, never in-flight/recovery records

PR #15 review finding #1. Inverts the TTL-prune from a deny-list
(!= 'pending') to an allow-list keyed on the lifecycle's own terminal
status set; non-string/None status is treated as malformed and prunable
(documented intent), every other string status is kept. Adds regression
+ characterization tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — Enforce and correctly describe the storage base-layer import invariant (must-fix C1 + important I1) → Commit B

**Why:** `ARCHITECTURE.md:18` + `docs/decisions/0002-...md:32-35` claim the base-layer zero-internal-import invariant is "enforced mechanically via `tests/test_runtime_namespace.py`", but no test enforces it (the prohibited import would pass CI), and line 18 also wrongly implies `storage_layout`/`storage_inspection` import `storage_primitives` (they are independent stdlib-only peers). Make the promised enforcement real *and* fix the description, in one commit (one concern).

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py` (append; reuses existing `_parse`, `RUNTIME_DIR`, `RUNTIME_PACKAGE`)
- Modify: `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md` (line 18 only)

Note: the base-layer files' existence is already enforced by the existing `test_runtime_module_inventory_is_explicit` (it asserts the exact module set), so the new test deliberately does not re-assert existence.

- [ ] **Step 1: Write the enforcement test**

Append to `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py` (end of file):

```python
STDLIB_ONLY_BASE_LAYER = {
    "storage_primitives.py",
    "storage_layout.py",
    "storage_inspection.py",
}


def test_storage_base_layer_has_no_internal_imports() -> None:
    """Enforces the ARCHITECTURE.md / ADR-0002 layering invariant: the
    stdlib-only base layer must not import any turbo_mode_handoff_runtime
    module, by absolute OR relative import. An internal import here
    re-creates the cycle the reseam removed."""
    for name in STDLIB_ONLY_BASE_LAYER:
        tree = _parse(RUNTIME_DIR / name)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert node.level == 0, f"{name}: relative intra-package import"
                assert module != RUNTIME_PACKAGE, name
                assert not module.startswith(f"{RUNTIME_PACKAGE}."), name
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != RUNTIME_PACKAGE, name
                    assert not alias.name.startswith(f"{RUNTIME_PACKAGE}."), name
```

- [ ] **Step 2: Run it — verify it PASSES (invariant currently holds)**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_runtime_namespace.py::test_storage_base_layer_has_no_internal_imports`
Expected: **PASS**.

- [ ] **Step 3: Prove the guard is non-vacuous (the core of finding C1)**

Add this line to `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py` immediately after its existing `from __future__ import annotations` line:

```python
from turbo_mode_handoff_runtime.storage_layout import StorageLayout  # TEMP probe
```

Run the Step 2 command again.
Expected: **FAIL** — `AssertionError: storage_primitives.py`.

If it PASSES with the probe present, the test is vacuous (C1 not fixed) — stop and fix the test.

- [ ] **Step 4: Revert the probe and re-verify**

Remove the `# TEMP probe` line. Run:
`git diff --stat plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py`
Expected: **no output** (byte-identical to HEAD). Re-run Step 2 command → Expected: **PASS**.

- [ ] **Step 5: Fix the ARCHITECTURE.md import-flow line**

Replace exactly this line (currently `ARCHITECTURE.md:18`):

```
Layering invariant: imports flow one way, lowest to highest — `storage_primitives` → `storage_layout`/`storage_inspection` → `storage_authority` → `chain_state` → `active_writes` → `session_state`/`load_transactions` → domain modules. `storage_primitives.py` is the zero-internal-import foundation (highest fan-in in the runtime): it must not import any `turbo_mode_handoff_runtime` module. Adding such an import would re-create the cross-module import cycle the storage reseam removed and is prohibited.
```

with:

```
Layering invariant: imports flow one way, lowest to highest. The base layer is three independent, stdlib-only modules with no internal imports — `storage_primitives`, `storage_layout`, and `storage_inspection` (they are peers; none imports another). Above them: `storage_authority` → `chain_state` → `active_writes` → `session_state`/`load_transactions` → domain modules. No base-layer module may import any `turbo_mode_handoff_runtime` module (by absolute or relative import); doing so re-creates the cross-module import cycle the storage reseam removed and is prohibited. This is enforced mechanically by `tests/test_runtime_namespace.py::test_storage_base_layer_has_no_internal_imports`.
```

- [ ] **Step 6: Verify topology doc tests still pass**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_architecture_docs.py tests/test_runtime_namespace.py`
Expected: **PASS**. `test_architecture_docs.py` ownership-map substrings (ARCHITECTURE.md lines 11-15) are untouched by a line-18-only edit; the new line introduces no `STALE_TOPOLOGY_PATTERNS` match.

- [ ] **Step 7: Lint and commit B**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
Expected: `All checks passed!`

```bash
git add plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md
git commit -m "test: enforce storage base-layer zero-internal-import invariant; fix ARCHITECTURE wording

PR #15 review findings C1 + I1. Adds an AST test that fails when any
base-layer module imports an internal module (absolute or relative,
proven by probe), making the ADR-0002 'enforced mechanically' claim
true. Corrects the ARCHITECTURE.md line that implied layout/inspection
depend on primitives (they are independent stdlib-only peers).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Pin `_skip_reason` legacy/hidden-archive equivalence (important #3) → Commit C

**Why:** `git diff main...HEAD` confirms PR #15 deleted, from `_skip_reason`, the branches `if location == StorageLocation.LEGACY_ARCHIVE: return None` and `if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE: return None`, which sat *after* `if path.parent != root: return "nested_file"` and immediately before the existing `return None` — provably dead code (same result either way). No test pins this equivalence. These are **characterization** tests: expected green, locking the post-deletion behaviour at both the unit (`_skip_reason`) and the real call site (`discover_handoff_inventory`, the path that previously passed the now-removed `location` arg). `LEGACY_ARCHIVE` is scanned under `active-selection`+`history-search`; `PREVIOUS_PRIMARY_HIDDEN_ARCHIVE` only under `history-search` (`storage_authority.py:101,108-112`), so the call-site test uses `history-search`.

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py` (append; add imports to the existing `from turbo_mode_handoff_runtime.storage_authority import (...)` block)

- [ ] **Step 1: Extend the storage_authority import block**

In `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`, the existing import block (lines 16-22) is:

```python
from turbo_mode_handoff_runtime.storage_authority import (
    SelectionEligibility,
    StorageLocation,
    discover_handoff_inventory,
    eligible_active_candidates,
    eligible_history_candidates,
)
```

Replace it with (adds `_skip_reason`, `root_for_location`):

```python
from turbo_mode_handoff_runtime.storage_authority import (
    SelectionEligibility,
    StorageLocation,
    _skip_reason,
    discover_handoff_inventory,
    eligible_active_candidates,
    eligible_history_candidates,
    root_for_location,
)
```

- [ ] **Step 2: Write the unit + call-site characterization tests**

Append to the end of `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py` (`_handoff` helper is defined at line 31; `Path`, `pytest` already imported):

```python
@pytest.mark.parametrize(
    "location",
    [
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    ],
)
def test_skip_reason_unit_equivalence_for_archive_locations(
    tmp_path: Path, location: StorageLocation
) -> None:
    """Characterization (PR #15 #3, unit): the deleted location short-circuits
    in `_skip_reason` were dead code (returned None before the existing
    `return None`). Pin that a flat file at these roots is not skipped, while
    the generic nested/hidden rules still apply."""
    root = root_for_location(tmp_path, location)
    root.mkdir(parents=True, exist_ok=True)

    flat = root / "2026-05-13_12-00_a.md"
    flat.write_text("---\nproject: demo\n---\n", encoding="utf-8")
    nested = root / "sub" / "2026-05-13_12-00_b.md"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("---\nproject: demo\n---\n", encoding="utf-8")
    hidden = root / ".hidden.md"
    hidden.write_text("---\nproject: demo\n---\n", encoding="utf-8")

    assert _skip_reason(root, flat) is None
    assert _skip_reason(root, nested) == "nested_file"
    assert _skip_reason(root, hidden) == "hidden_basename"


def test_discovery_does_not_skip_flat_archive_files(tmp_path: Path) -> None:
    """Characterization (PR #15 #3, call site): through the real
    discover_handoff_inventory path (which formerly passed the now-deleted
    `location` arg), a flat handoff in legacy-archive and previous-primary-
    hidden-archive must be discovered with skip_reason None; a nested one is
    still skipped 'nested_file'. history-search covers both locations."""
    legacy_root = root_for_location(tmp_path, StorageLocation.LEGACY_ARCHIVE)
    hidden_root = root_for_location(
        tmp_path, StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE
    )
    legacy_flat = _handoff(legacy_root / "2026-05-13_12-00_legacy.md")
    hidden_flat = _handoff(hidden_root / "2026-05-13_12-00_hidden.md")
    legacy_nested = _handoff(legacy_root / "sub" / "2026-05-13_12-00_nested.md")

    inventory = discover_handoff_inventory(tmp_path, scan_mode="history-search")
    by_path = {candidate.path: candidate for candidate in inventory.candidates}

    assert by_path[legacy_flat.resolve()].skip_reason is None
    assert by_path[hidden_flat.resolve()].skip_reason is None
    assert by_path[legacy_nested.resolve()].skip_reason == "nested_file"
```

- [ ] **Step 3: Run them — verify they PASS (pin current equivalence)**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_storage_authority.py::test_skip_reason_unit_equivalence_for_archive_locations tests/test_storage_authority.py::test_discovery_does_not_skip_flat_archive_files`
Expected: **PASS** (2 parametrized unit cases + 1 call-site test = 3).

If the call-site test errors with `KeyError` on a `.resolve()` path, the discovery scan or `_handoff` path shape differs from this plan's assumption — stop and inspect `inventory.candidates` (do not silently weaken the assertion); the equivalence is unverified until the real call site is exercised.

- [ ] **Step 4: Lint and commit C**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
Expected: `All checks passed!` (note: `_skip_reason` is intentionally imported; if ruff flags the leading underscore import, keep it — it is the unit under test.)

```bash
git add plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py
git commit -m "test: pin _skip_reason equivalence for legacy/hidden-archive locations

PR #15 review finding #3. Characterization at the unit (_skip_reason)
and the real call site (discover_handoff_inventory, history-search)
locking the post-dead-branch-removal behaviour so a future skip rule
cannot silently regress legacy/hidden-archive discovery.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Pin `_persist_operation_and_transaction` partial-failure contract (important #5) → Commit D

**Why:** The extracted helper writes operation-state first, then the transaction mirror. Write-side recovery (`recover_active_write_transaction`) keys off operation-state, so "op-state before transaction" is recovery-critical. The extraction preserved it; no test injects a between-writes failure. Characterization test pinning the contract.

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py` (append; `json`, `Path`, `pytest`, `active_writes` already imported)

`active_writes.py:43` aliases `write_json_atomic as _write_json_atomic`, so `active_writes._write_json_atomic` is the monkeypatch target (matches the file's existing `monkeypatch.setattr(active_writes, ...)` idiom).

- [ ] **Step 1: Write the characterization test**

Append to the end of `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`:

```python
def test_persist_operation_and_transaction_failure_leaves_operation_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characterization (PR #15 #5): if the transaction write fails after the
    operation-state write, the error propagates and operation state is on disk
    (recovery keys off operation state, written first). The transaction file
    must not exist."""
    op_path = tmp_path / "active-writes" / "demo" / "run.json"
    tx_path = tmp_path / "transactions" / "run.json"
    state: dict[str, object] = {"project": "demo", "status": "write-pending"}

    real_write = active_writes._write_json_atomic

    def selective_write(path: Path, payload: dict[str, object]) -> None:
        if path == tx_path:
            raise OSError("transaction write failed")
        real_write(path, payload)

    monkeypatch.setattr(active_writes, "_write_json_atomic", selective_write)

    with pytest.raises(OSError, match="transaction write failed"):
        active_writes._persist_operation_and_transaction(
            op_path,
            tx_path,
            state,
            transaction_status="write-pending",
        )

    assert op_path.exists()
    assert json.loads(op_path.read_text(encoding="utf-8"))["status"] == "write-pending"
    assert not tx_path.exists()
```

- [ ] **Step 2: Run it — verify it PASSES (pins current contract)**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_active_writes.py::test_persist_operation_and_transaction_failure_leaves_operation_state`
Expected: **PASS**. If it FAILS, the extraction did not preserve the ordering/propagation contract — stop and report (contradicts the review consensus; do not edit the test to pass).

- [ ] **Step 3: Lint and commit D**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
Expected: `All checks passed!`

```bash
git add plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py
git commit -m "test: pin _persist_operation_and_transaction partial-failure contract

PR #15 review finding #5. Fault-injection characterization: op-state is
written before the transaction mirror and a transaction-write failure
propagates with op-state intact (recovery keys off op-state).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final evidence gate (run after Commit D)

- [ ] **G1: Suite green; the named tests present and passing; per-module deltas correct**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q`
Expected: **all passed, 0 failed**. Then assert the work is present (robust to unrelated suite drift — do not gate on a bare global integer):

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q tests/test_session_state.py tests/test_runtime_namespace.py tests/test_storage_authority.py tests/test_active_writes.py`
Expected: **PASS**, and collected counts vs the P2 per-module baseline = `test_session_state.py` **+4**, `test_runtime_namespace.py` **+1**, `test_storage_authority.py` **+3**, `test_active_writes.py` **+1** (net **+9**; global ≈ 626 barring unrelated drift). If the global differs but all four per-module deltas hold and every named test below passes, that is a PASS — investigate the global only if a delta is wrong.

Named tests that must all pass:
`test_prune_keeps_in_flight_and_recovery_write_transactions`, `test_prune_drops_terminal_unreadable_and_malformed_records_past_ttl`, `test_prune_ttl_boundary_keeps_records_at_or_within_cutoff`, `test_prune_handles_missing_transactions_dir`, `test_storage_base_layer_has_no_internal_imports`, `test_skip_reason_unit_equivalence_for_archive_locations` (×2 params), `test_discovery_does_not_skip_flat_archive_files`, `test_persist_operation_and_transaction_failure_leaves_operation_state`. The pre-existing `test_prune_old_state_files_prunes_terminal_transactions` must still pass.

- [ ] **G2: Lint clean across all changed Python**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
Expected: `All checks passed!`

- [ ] **G3: No tracked-source residue; declared diff clean**

Run: `git diff --check` (expected: no output) and `git status --short`.
Expected: clean tree except the untracked plan doc. `uv run` may create gitignored `.venv`/uv-lock residue and pytest may create `__pycache__`/`.pytest_cache`/`.DS_Store` under the plugin tree — for each such path run `git check-ignore <path>`; if ignored, it is expected and **not** a blocker (do not stage it, do not `rm`). Only an un-ignored residue file is a closeout blocker; report it.

- [ ] **G4: Update PR #15 description (ask the user first — modifies shared state)**

Propose (do not push/edit without explicit confirmation, per repo git rules) a "Review follow-up" section for PR #15: findings #1 (fix), C1/I1, #3, #5 closed; 9 tests added; one source behaviour change (prune allow-list, strictly fewer deletions).

---

## Out of scope (named follow-ups, not in this plan)

Suggestion-tier review items, deliberately excluded to keep the change minimal/reversible; track separately if desired:

- `_build_parser`/`_dispatch` error-path tests (SystemExit on missing/unknown subcommand).
- `installed_host_harness.py` version-constant-divergence guard test.
- Prune success-path summary logging (behaviour change; own decision).
- `transaction_status: str` → `Literal`/`Enum` (bundled with the PR's already-named `dict[str, object]` typing follow-up; note: importing the terminal set from `active_writes` into `session_state` would invert the documented layering, so the `session_state`-local constant in Task 1 is the layering-correct choice, not duplication to be "fixed" here).
- ARCHITECTURE.md "highest fan-in" wording / `expired-chain-state` runbook-row specificity.
- `_build_parser`/`_dispatch` docstrings.

## Self-review (plan author + adversarial-review responses)

- **Finding coverage:** #1→Task 1; C1+I1→Task 2; #3→Task 3; #5→Task 4. All five must-fix/important findings mapped; suggestions deferred above.
- **Adversarial-review dispositions:** (1) brittle global count gate → fixed: G1 now asserts per-module deltas + named-test presence, no bare-integer hard gate. (2) commit-order self-inconsistency → fixed: tasks renumbered so task order == commit order A→B→C→D, Task 2 commits its own concern (no held commit). (3) Task 3 premise that the deleted branches were in another function → **refuted by `git diff main...HEAD`** (they were in `_skip_reason`, dead code); the review's actionable core accepted → Task 3 now also exercises the real `discover_handoff_inventory` call site, stop-condition language softened to characterization framing. (4) junk-status records kept forever + inaccurate comment → fixed: predicate is `not isinstance(status, str) or status in TERMINAL_…`, comment corrected, `{"status": 42}` case added. (5) imprecise provenance citations → fixed: constant comment now says "derived from the lifecycle's terminal transitions" with accurate site references. Minor: P1 accounts for the untracked plan doc; Task 2 test also rejects relative intra-package imports and documents that existence is covered by the inventory test; G3 accounts for gitignored `uv`/pytest residue.
- **Placeholder scan:** every code/Edit/command step has literal code or an exact command + expected output; no TBD/"similar to".
- **Name/number consistency:** `TERMINAL_TRANSACTION_STATUSES`, `STDLIB_ONLY_BASE_LAYER`, `_skip_reason`/`root_for_location`/`discover_handoff_inventory`, `_persist_operation_and_transaction`/`_write_json_atomic` all verified against live symbols; task numbers == commit letters == execution order.
- **TDD honesty:** only Task 1 Step 2 is a true red; Tasks 3 & 4 are labeled characterization (expected green) with explicit "if it fails, stop — do not edit the test" guards; Task 2 includes the probe step proving the guard is non-vacuous.
