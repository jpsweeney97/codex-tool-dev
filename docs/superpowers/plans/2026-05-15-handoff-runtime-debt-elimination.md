# Handoff Runtime Debt Elimination — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive all 23 canonical findings in `docs/audits/2026-05-15-handoff-runtime-post-reseam-debt.md` to zero, leaving the post-reseam Handoff runtime with no remaining technical debt.

**Architecture:** Four surface-scoped passes (docs/knowledge → source dedup/cleanup → CI/packaging → larger refactors), each gated by the repo's bytecode-safe verification harness and committed as a coherent surface-scoped chunk. Behaviour-preserving throughout; the 616-test suite must stay green after every task.

**Tech Stack:** Python ≥3.11 (stdlib + pyyaml), pytest, uv, GitHub Actions. Branch: `chore/handoff-runtime-debt-elimination`.

**Source spec:** `docs/audits/2026-05-15-handoff-runtime-post-reseam-debt.md` §3–§8. Finding IDs (`SY-N`) trace to that report and its ledger.

---

## Verification harness (run after every task unless noted)

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q
```
Expected: `616 passed` (count may rise as tasks add tests; never fall without rationale).
Package import-shape smoke after source edits — imports every submodule (a true import
smoke; package-aware, no args). The pytest suite already enforces this via
`test_runtime_namespace.py` / `test_installed_host_harness.py`; this is the fast standalone check:
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0 python -c "import importlib,pkgutil,turbo_mode_handoff_runtime as p; [importlib.import_module(m.name) for m in pkgutil.iter_modules(p.__path__, p.__name__+'.')]; print('import-smoke ok')"
```
(Single line — multiline `\` continuation breaks under the runner. Use absolute `--directory`.)
NOTE: `turbo_mode_handoff_runtime/installed_host_harness.py` is an installed-runtime proof
CLI (needs `argv[1]` installed-plugin + `argv[2]` source-checkout) — installed-runtime
scope, OUT OF SCOPE here. Never invoke it bare as a source smoke. Changes to that file
(Task 21) are verified via `tests/test_installed_host_harness.py` in the suite.

Whitespace gate before each commit: `git diff --check`.
Lint changed Python: `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check <changed-paths>`.

**Establish the green baseline first** (Task 0). Every later task is a delta against a known-green tree.

---

### Task 0: Confirm green baseline

**Files:** none (read-only)

- [ ] **Step 1:** Run the full suite via the harness above. Expected: `616 passed`.
- [ ] **Step 2:** Run the package import-shape smoke (harness section). Expected: `import-smoke ok`.
- [ ] **Step 3:** Record the pass count in the execution log. If not green, STOP — the audit assumed a green tree; investigate before any change.

---

## PASS 1 — Docs / knowledge (do first: HL1 documents the invariant that protects every later source edit)

Single docs-surface commit at the end of the pass (plus the one `test_architecture_docs.py` change). Order within the pass: HL1 first.

### Task 1: HL1 `[SY-2]` — Document `storage_primitives.py` + the layering invariant

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/README.md` (runtime module table)
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_architecture_docs.py` (`REQUIRED_TOPOLOGY_CLAIMS`)

- [ ] **Step 1:** Read all four files plus `turbo_mode_handoff_runtime/storage_primitives.py:1-40` (its module docstring states the import-direction rule — quote it accurately).
- [ ] **Step 2:** Read `test_architecture_docs.py` to learn the exact `REQUIRED_TOPOLOGY_CLAIMS` structure and how claims are matched against the docs (so the doc wording satisfies the test).
- [ ] **Step 3:** Add a `storage_primitives.py` entry to ARCHITECTURE.md Storage Layout section: name it the zero-import base layer; state the invariant verbatim — *no module in `turbo_mode_handoff_runtime` may be imported by `storage_primitives.py`; it is the one-way foundation for all write-path atomicity and the claim-file lock protocol*. Add the explicit layer order: `storage_primitives → storage_layout/storage_inspection → storage_authority → chain_state → active_writes → {session_state, load_transactions} → domain`.
- [ ] **Step 4:** Add the matching one-line `storage_primitives.py` row to CONTRIBUTING.md Runtime Boundaries and the README runtime module table.
- [ ] **Step 5:** Add the `storage_primitives.py` topology claim to `REQUIRED_TOPOLOGY_CLAIMS` so the doc test enforces it.
- [ ] **Step 6:** Run the harness. The architecture-doc test must now assert and pass the new claim. Expected: green, ≥616.
- [ ] **Step 7:** (no commit yet — Pass 1 commits once at Task 8)

### Task 2: HL2 `[SY-10]` — Locking-model design rationale

**Files:** Modify `references/ARCHITECTURE.md`

- [ ] **Step 1:** Read `storage_primitives.py` lock/claim code: `LockPolicy`, `_CLAIM_TIMEOUT_SECONDS`, `_LOCK_TIMEOUT_SECONDS`, the claim-file CAS acquire/release, and `_try_recover_stale_lock` (find exact line ranges).
- [ ] **Step 2:** Add a "Locking Model" subsection to ARCHITECTURE.md: why stdlib-only (no external lock dep; portability), why claim-file compare-and-swap rather than advisory `flock` (cross-platform, NFS-safe, crash-visible), the claim/lock timeout semantics, and the stale-lock recovery policy. Source the rationale from the reseam execution plan `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md` and the code — do not invent rationale; if a decision's reason is not recoverable from code/plan, state it as "observed behavior" not "rationale".
- [ ] **Step 3:** Run harness. Expected: green.

### Task 3: SY-9 — Chain State Diagnostics runbook

**Files:** Modify `references/ARCHITECTURE.md`; Modify `README.md` (cross-ref)

- [ ] **Step 1:** Enumerate every `ChainStateDiagnosticError(code=...)` raise in `turbo_mode_handoff_runtime/chain_state.py` (grep `code=`); produce the authoritative list of distinct codes with their trigger condition (read each raise site).
- [ ] **Step 2:** Add `## Chain State Diagnostics` to ARCHITECTURE.md: a table `code | when it fires | operator recovery action`. Recovery actions must be concrete (e.g., "`trash` the marker at `<path>`, re-run `/load`") and consistent with actual recovery behavior in the code.
- [ ] **Step 3:** Add a one-line pointer from README's Known Limitations to that section.
- [ ] **Step 4:** Run harness. Expected: green.

### Task 4: SY-11 — Back-fill ADRs

**Files:** Create `docs/decisions/0001-storage-path-move.md`, `0002-runtime-module-extraction.md`, `0003-hook-deferral.md`; Modify `plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md`

- [ ] **Step 1:** Resolve Open Question #1: confirm `docs/decisions/` is an acceptable home. The repo already uses `docs/superpowers/`, `docs/tickets/`, `docs/audits/`; `docs/decisions/` is a consistent sibling for durable decision records. Use it.
- [ ] **Step 2:** Write 3 minimal ADRs (Context / Decision / Consequences, ~20 lines each), rationale sourced from `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md`, the CHANGELOG `[Unreleased]`/1.7.0 entries, and commit history — no invented rationale.
- [ ] **Step 3:** Add a "Decision records: see `docs/decisions/`" line to CONTRIBUTING.md.
- [ ] **Step 4:** Run harness (no test impact expected). Expected: green.

### Task 5: SY-8 — Version/path freeze policy + marketplace URL fix

**Files:** Modify `plugins/turbo-mode/handoff/1.6.0/.codex-plugin/plugin.json`; Modify `CONTRIBUTING.md`

- [ ] **Step 1:** Read `tests/test_release_metadata.py:44-52,130` to confirm it intentionally asserts the literal `1.6.0` path string and the 1.7.0 version. This is the evidence the directory name is a deliberate frozen install path.
- [ ] **Step 2:** Add one sentence to CONTRIBUTING.md: the `1.6.0/` directory name is the frozen marketplace install path for the life of this install slot; only the manifest `version` advances; `test_release_metadata.py` asserts the literal path intentionally.
- [ ] **Step 3:** Fix `plugin.json:14-18` `websiteURL`/`privacyPolicyURL`/`termsOfServiceURL`: keep them consistent with the frozen `1.6.0/` path policy (the path is frozen, so the URLs embedding `1.6.0` are correct under the documented policy — verify each URL resolves to the actual file location; only change a URL if it points somewhere that does not exist). Document the policy decision so future bumps don't churn the URLs.
- [ ] **Step 4:** Run harness — `test_release_metadata.py` must stay green. Expected: green.

### Task 6: SY-3 (doc part) + SY-14 + SY-19 — orientation comments

**Files:** Modify `references/ARCHITECTURE.md`; Modify `turbo_mode_handoff_runtime/storage_authority_inventory.py`; Modify `turbo_mode_handoff_runtime/chain_state.py`

- [ ] **Step 1:** ARCHITECTURE.md Storage Layout: add a one-line note that `storage_authority_inventory.py` is a non-wired dev/CI inventory-gate helper (matches README:66 wording).
- [ ] **Step 2:** `storage_authority_inventory.py` `default_repo_root()`: add a comment on the `parents[5]` literal explaining the assumed repo depth and that it only affects the dev/CI probe (not runtime). No behaviour change.
- [ ] **Step 3:** `chain_state.py:772-797` `_read_json_object`: add a comment stating it deliberately does not use `storage_primitives.read_json_object` because the error type must be `ChainStateDiagnosticError` (and FileNotFound → `{}`).
- [ ] **Step 4:** `chain_state.py:13` `StorageLocation` import: add a comment that `StorageLocation` is the intentional shared bridge type owned by `storage_authority`; this discharges SY-19 (conscious-decision made explicit) without extraction.
- [ ] **Step 5:** Run harness + `installed_host_harness.py` (comments only — must stay green). Expected: green.

### Task 7: SY-3 self-review note

- [ ] **Step 1:** Confirm Open Question #3 disposition: physical relocation of `storage_authority_inventory.py` out of the runtime namespace is **not** done now (low real cost while not distributed standalone; doc note + comment discharge the actionable debt). Record this decision in the execution log with rationale. No file change.

### Task 8: Commit Pass 1

- [ ] **Step 1:** `git diff --check` (clean).
- [ ] **Step 2:** Run full harness once more. Expected: green ≥616.
- [ ] **Step 3:** Stage exactly the Pass-1 files by name (ARCHITECTURE.md, CONTRIBUTING.md, README.md, test_architecture_docs.py, plugin.json, storage_authority_inventory.py, chain_state.py comment-only hunks, the 3 new ADRs). Do NOT `git add -A`.
- [ ] **Step 4:** Commit: `docs: document storage_primitives invariant, locking model, diagnostics, ADRs (SY-2,10,9,11,8,3,14,19)`.

---

## PASS 2 — Source dedup / cleanup (suite must stay 616-green; behaviour-preserving)

### Task 9: HL3 `[SY-1]` — Remove the `search.py` zombie compat shim + its self-test

**Files:**
- Modify: `turbo_mode_handoff_runtime/search.py:13-15,30-37`
- Modify: `tests/test_search.py:27-36`

- [ ] **Step 1:** Re-verify zero live callers: `rg -n 'from .*search import .*(HandoffFile|Section)|search\.(HandoffFile|Section)' --glob '!**/.venv/**'` across the whole repo. Expected: only `tests/test_search.py` and historical docs. If any production caller exists, STOP and re-scope.
- [ ] **Step 2:** Confirm whether `search.py` internally uses `parse_handoff` re-export (CH-5 caveat) — leave `parse_handoff` and its companion test untouched.
- [ ] **Step 3:** Remove `HandoffFile`/`Section` from the re-export block and from `__all__` in `search.py`.
- [ ] **Step 4:** Delete `test_search_runtime_reexports_parser_symbols_for_compatibility` from `test_search.py`.
- [ ] **Step 5:** Run harness + import smoke. Expected: green; collected count drops by exactly 1 (the deleted test) — that is the one sanctioned decrease, log it.
- [ ] **Step 6:** (Pass-2 commits at Task 16.)

### Task 10: SY-12 — Dedup `_registry_key`

**Files:** Modify `turbo_mode_handoff_runtime/storage_primitives.py`, `load_transactions.py:931-937`, `storage_authority.py:760-766`

- [ ] **Step 1:** Read all three sites; confirm the two `_registry_key` bodies are identical.
- [ ] **Step 2:** Add `registry_key(entry)` to `storage_primitives.py` (public-ish, single definition; keep the exact 4-key extraction). Respect the zero-internal-import invariant (Task 1) — `storage_primitives` must not import anything from the package.
- [ ] **Step 3:** Replace both local `_registry_key` definitions with `from turbo_mode_handoff_runtime.storage_primitives import registry_key` and update call sites.
- [ ] **Step 4:** Add a test asserting both modules resolve `registry_key` to the same object and that a representative entry produces the same key (mirror the pattern of the existing `LEGACY_CONSUMED_PREFIX` ownership test).
- [ ] **Step 5:** Run harness. Expected: green, count +1.

### Task 11: SY-13 — Consolidate identical chain_state path scanners

**Files:** Modify `turbo_mode_handoff_runtime/chain_state.py:525-538` (+ call site ~71-77)

- [ ] **Step 1:** Confirm `_state_candidate_paths` and `_state_like_residue_paths` bodies are byte-identical.
- [ ] **Step 2:** Replace both with one `_chain_state_file_paths(root, project_name)`; move the state-location semantic distinction to the caller in `chain_state_recovery_inventory`.
- [ ] **Step 3:** Run harness. Expected: green (existing chain-state recovery tests cover both call sites — verify they still pass; if only one site is covered, add a test exercising the other).

### Task 12: SY-17 — Annotate 14 `layout` params

**Files:** Modify `turbo_mode_handoff_runtime/load_transactions.py` (lines 289,321,375,446,501,513,525,561,611,737,765,802,834,859)

- [ ] **Step 1:** Confirm `StorageLayout` import exists (`get_storage_layout` already imported from `storage_layout`); import the type if needed.
- [ ] **Step 2:** Add `layout: StorageLayout` to each of the 14 private signatures. Mechanical; no logic change.
- [ ] **Step 3:** Run harness + ruff on the file. Expected: green, no new lint.

### Task 13: SY-18 — Remove dead `_skip_reason` branches

**Files:** Modify `turbo_mode_handoff_runtime/storage_authority.py:589-593`

- [ ] **Step 1:** Confirm all three terminal arms `return None`.
- [ ] **Step 2:** Remove the two `if location == StorageLocation.LEGACY_ARCHIVE` / `...PREVIOUS_PRIMARY_HIDDEN_ARCHIVE` blocks; keep the single final `return None`.
- [ ] **Step 3:** Run harness. Expected: green (behaviour identical).

### Task 14: SY-23 — Flat glob instead of `rglob`

**Files:** Modify `turbo_mode_handoff_runtime/storage_authority.py:252`

- [ ] **Step 1:** Read `_discover_handoffs`; confirm active handoffs are written flat to the active dir root (not nested) so `glob("*.md")` is equivalent for the active scan, and confirm archive discovery is a separate path (or add a targeted archive scan if `_discover_handoffs` currently relies on recursion to reach archive).
- [ ] **Step 2:** If and only if Step 1 confirms flat-equivalence: replace `root.rglob("*.md")` with `root.glob("*.md")`. If archive depends on recursion, instead add a targeted `archive` scan and keep behaviour identical — do NOT change discovered-set semantics.
- [ ] **Step 3:** Run harness. Expected: green — discovery tests must show identical candidate sets. If any discovery test changes, revert and treat SY-23 as watch-only (log the decision).

### Task 15: SY-20 — Add LICENSE

**Files:** Create `plugins/turbo-mode/handoff/1.6.0/LICENSE`

- [ ] **Step 1:** Confirm `plugin.json` declares `"license": "MIT"` and author `JP`. Check repo root for an existing LICENSE to copy the canonical MIT text + copyright line style.
- [ ] **Step 2:** Write the MIT license text with the correct copyright holder/year.
- [ ] **Step 3:** Check `test_release_metadata.py` for any LICENSE assertion; run harness. Expected: green.

### Task 16: Commit Pass 2

- [ ] **Step 1:** `git diff --check`; run full harness + import-shape smoke. Expected: green; net collected count = 616 −1 (SY-1) +1 (SY-12 dedup test) [+1 if SY-13 added a test] — reconcile and log.
- [ ] **Step 2:** Stage Pass-2 source/test files by name.
- [ ] **Step 3:** Commit: `refactor: dedup storage helpers, drop dead code, remove zombie shim (SY-1,12,13,17,18,23,20)`.

---

## PASS 3 — CI / packaging (validate workflow YAML; CI is the post-reseam regression gate)

### Task 17: SY-4 — CI Python matrix

**Files:** Modify `.github/workflows/handoff-plugin-tests.yml`

- [ ] **Step 1:** Read the workflow fully. Add `strategy.matrix.python-version: ["3.11", "3.13"]` to the test job; wire `actions/setup-python` to `${{ matrix.python-version }}`.
- [ ] **Step 2:** Validate YAML: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/handoff-plugin-tests.yml'))"`. Expected: no error.
- [ ] **Step 3:** Local harness unaffected; run it. Expected: green.

### Task 18: SY-5 — Pin uv toolchain

**Files:** Modify `.github/workflows/handoff-plugin-tests.yml`

- [ ] **Step 1:** Replace `python -m pip install uv` with `astral-sh/setup-uv@v6` and an explicit `version:` pin (use a current stable uv version; if uncertain, pin the minor that the repo's `uv.lock` `revision` is compatible with and note it in the execution log). Remove the now-redundant pip step.
- [ ] **Step 2:** Optionally pin `runs-on: ubuntu-24.04` (lower priority; do it — exhaustive goal, infrequent risk, one-line).
- [ ] **Step 3:** Re-validate YAML (as Task 17 Step 2). Expected: no error.

### Task 19: SY-6 — zsh availability guard

**Files:** Modify `tests/test_session_state.py:1192,1230`, `tests/test_cli_commands.py:13` (+ any other `/bin/zsh` site — grep first)

- [ ] **Step 1:** `rg -n '/bin/zsh' plugins/turbo-mode/handoff/1.6.0/tests` for the complete site list (do not trust the anchor list alone).
- [ ] **Step 2:** Add `@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")` to each zsh-invoking test (import `shutil` where needed). Behaviour-preserving where zsh exists.
- [ ] **Step 3:** Run harness (zsh present locally → tests still run, still pass). Expected: green. Also confirm `shutil.which("zsh") is None` path is syntactically valid by a quick targeted collect.

### Task 20: SY-21 — slow marker

**Files:** Modify `tests/test_load_transactions.py:1172`

- [ ] **Step 1:** Add `@pytest.mark.slow` immediately above `def test_load_lock_live_contention_with_subprocess` (match the sibling in `test_active_writes.py`).
- [ ] **Step 2:** `pytest --collect-only -q -m "slow"` via the harness dir — expected: now 3 slow tests (was 2).
- [ ] **Step 3:** Decide + document CI slow policy in the execution log: CI currently runs the full suite incl. slow; keep that (explicit choice) unless Task 17/18 changes runtime materially.

### Task 21: SY-7 — Single-source `installed_host_harness.py` version constants

**Files:** Modify `turbo_mode_handoff_runtime/installed_host_harness.py:30,160`; Modify `tests/test_installed_host_harness.py:43`

- [ ] **Step 1:** Read the harness around both literals and the test assertion.
- [ ] **Step 2:** Introduce two named module constants: `HARNESS_CACHE_PATH_VERSION = "1.6.0"` (frozen install slot, ties to SY-8 policy) and `MANIFEST_VERSION` derived at runtime from `plugin.json` (`json.loads((source_plugin_root/".codex-plugin"/"plugin.json").read_text())["version"]`). Replace the two hardcoded literals with these. Add a comment cross-referencing the SY-8 freeze policy explaining the intentional split.
- [ ] **Step 3:** Update `test_installed_host_harness.py:43` to assert against the constant (import it) rather than a bare `"1.6.0"` literal.
- [ ] **Step 4:** Verify via the suite: run `tests/test_installed_host_harness.py` specifically (it imports the harness module and asserts the path/version payload) plus the full harness. Expected: green; the test still asserts version `1.7.0` / path slot `1.6.0` (now via the named constants). Do NOT invoke the harness CLI bare (installed-runtime scope).

### Task 22: SY-22 — Prune `transactions/`

**Files:** Modify `turbo_mode_handoff_runtime/session_state.py:191-212` (`prune_old_state_files`) and/or `cleanup.py:33`; Test in `tests/test_cleanup.py` or `tests/test_session_state.py`

- [ ] **Step 1:** Read `prune_old_state_files`, the transaction-write sites (`load_transactions.py:359,492`), and `cleanup.py`. Determine the transactions dir path and the status field values (`pending`/`completed`/`abandoned`).
- [ ] **Step 2:** Write a failing test: create a transactions dir with one `pending`, one `completed` (mtime old), one `abandoned` (mtime old), one `completed` (mtime fresh); call the prune entry point; assert old non-`pending` records deleted, `pending` and fresh kept.
- [ ] **Step 3:** Run it — expect FAIL (no pruning today).
- [ ] **Step 4:** Extend the prune to also walk `transactions_dir` and delete records whose `status != "pending"` and whose mtime exceeds the existing TTL cutoff. Reuse the existing cutoff constant; do not introduce a new config surface (YAGNI).
- [ ] **Step 5:** Mark the test `@pytest.mark.slow` only if it does real timing; otherwise keep it fast with explicit mtime set via `os.utime`.
- [ ] **Step 6:** Run harness. Expected: green, count +1.

### Task 23: Commit Pass 3

- [ ] **Step 1:** `git diff --check`; YAML re-validate; full harness; import-shape smoke.
- [ ] **Step 2:** Stage Pass-3 files by name.
- [ ] **Step 3:** Commit: `ci: matrix python, pin uv, guard zsh; harden harness versioning + transaction prune (SY-4,5,6,21,7,22)`.

---

## PASS 4 — Larger refactors (behaviour-preserving; one commit each; full verification between)

### Task 24: ST1 `[SY-15]` — Decompose `write_active_handoff`

**Files:** Modify `turbo_mode_handoff_runtime/active_writes.py:463-618`; characterization tests in `tests/test_active_writes.py`

- [ ] **Step 1:** Read `write_active_handoff` fully. Inventory its four concerns and every `_write_json_atomic` call + error path.
- [ ] **Step 2:** Confirm existing `tests/test_active_writes.py` already exercises: success path, reservation-staleness failure, content-hash-mismatch failure, atomic-write failure/cleanup. If any of those four is not covered, add the missing characterization test FIRST (must pass against current code) — this is the refactor safety net.
- [ ] **Step 3:** Extract the atomic-file-write block into `_write_content_to_active_path(active_path, content, content_sha256)` — pure move, identical behaviour, called from the original site.
- [ ] **Step 4:** Run harness after the single extraction. Expected: green, unchanged behaviour.
- [ ] **Step 5:** Extract the repeated transaction-state-update into one helper; replace the scattered call sites.
- [ ] **Step 6:** Run harness + import-shape smoke. Expected: green. Do NOT alter ordering of state writes vs file writes — verify by reading the diff that every error path still updates the transaction record before raising.
- [ ] **Step 7:** Commit: `refactor: extract write_active_handoff atomic-write and state-update helpers (SY-15)`.

### Task 25: ST2 `[SY-16]` — Decompose `session_state.main()`

**Files:** Modify `turbo_mode_handoff_runtime/session_state.py:230-697`; tests `tests/test_cli_commands.py`, `tests/test_session_state.py`

- [ ] **Step 1:** Read `main()` fully; list the 16 command branches and which module each delegates to.
- [ ] **Step 2:** Confirm `test_cli_commands.py` covers each command verb's dispatch. Add characterization tests for any uncovered verb FIRST (pass against current code).
- [ ] **Step 3:** Extract `_build_parser() -> argparse.ArgumentParser` (pure move of parser construction). Run harness — green.
- [ ] **Step 4:** Extract `_dispatch(args) -> int` containing the branch ladder; `main()` becomes parse→dispatch. Run harness — green.
- [ ] **Step 5:** Lift the chain-state command group and the active-writer command group (pure delegations) into `_handle_chain_state(args)` / `_handle_active_writer(args)` helpers called from `_dispatch`. Run harness after each group.
- [ ] **Step 6:** Run full harness + import-shape smoke. CLI behaviour and exit codes unchanged; `test_cli_commands.py` green unmodified (except added characterization tests).
- [ ] **Step 7:** Commit: `refactor: extract session_state parser/dispatch/command-group handlers (SY-16)`.

---

## PASS 5 — Zero-confirmation

### Task 26: Final verification + backlog closeout

- [ ] **Step 1:** Full harness. Expected: green; reconcile final collected count = 616 −1(SY-1) +N(added characterization/dedup/prune tests) — every delta explained in the execution log.
- [ ] **Step 2:** Package import-shape smoke (harness section) — `import-smoke ok`.
- [ ] **Step 3:** `git diff --check` clean; re-run `test_architecture_docs.py` specifically — the new `storage_primitives` topology claim passes.
- [ ] **Step 4:** Walk all 23 `SY-N` in `docs/audits/2026-05-15-handoff-runtime-post-reseam-debt.md`; mark each Closed (with the commit that closed it) or Consciously-Dropped (with rationale: only SY-3-relocation and SY-23-if-reverted are eligible). No `SY-N` may be left unaddressed.
- [ ] **Step 5:** Clean residue: confirm no `__pycache__`/`.pytest_cache`/`.ruff_cache`/`.DS_Store` introduced into plugin source paths by the work (`git status --porcelain`); the gitignored audit workspace is fine.
- [ ] **Step 6:** Update the audit report with a closeout footer (date, branch, final commit range, final pass count) — proof the backlog is empty.

---

## Self-Review (run before execution)

**Spec coverage:** Every `SY-1…SY-23` from the audit maps to a task — SY-1→T9, SY-2→T1, SY-3→T6/T7, SY-4→T17, SY-5→T18, SY-6→T19, SY-7→T21, SY-8→T5, SY-9→T3, SY-10→T2, SY-11→T4, SY-12→T10, SY-13→T11, SY-14→T6, SY-15→T24, SY-16→T25, SY-17→T12, SY-18→T13, SY-19→T6, SY-20→T15, SY-21→T20, SY-22→T22, SY-23→T14. No gaps.

**Placeholders:** Tasks intentionally instruct "read live file then apply the anchored change" rather than transcribing 8k LOC into the plan — this is deliberate for a same-session executor under the repo's evidence-first posture (pre-transcribed code would drift from the live tree the audit anchored to). Each task is still deterministic: exact file, exact anchored change, exact verify command, exact commit. Not treated as a placeholder failure.

**Type/name consistency:** `registry_key` (T10) used consistently; `_write_content_to_active_path`, `_build_parser`, `_dispatch` named once and reused; `HARNESS_CACHE_PATH_VERSION`/`MANIFEST_VERSION` (T21) consistent.

**Risk controls:** behaviour-preserving refactors gated by characterization tests written first; SY-23 and SY-3-relocation have explicit revert/skip conditions; one sanctioned test-count decrease (SY-1) is logged.
