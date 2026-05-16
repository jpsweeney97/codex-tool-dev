# Tech Debt Audit — Handoff Runtime (POST-RESEAM state)

**Target:** `plugins/turbo-mode/handoff/1.6.0/` · **Date:** 2026-05-15 (audit run ~20:35, HEAD `0981c41` = PR#14 merge of the reseam) · **Scope:** subsystem · **Stakes:** high
**Method:** 6 parallel category auditors (code-health, architecture-drift, dependency, test-debt, operational, knowledge) + lead synthesis. **This is a DELTA audit**: a prior audit (`docs/audits/2026-05-15-handoff-debt.md`, 14:39) was rendered stale by 15 same-day commits that executed its entire backlog (reseam, facade removal, CI, version bump, scaffolding). That report is a valid record of the *pre-reseam* state and is preserved unmodified. This report supersedes it for current state. Per-auditor raw findings + ledger live in gitignored `.tech-debt-audit-workspace/`; every claim here is restated with current `file:line` anchors and stands alone.

---

## 1. Audit Snapshot

| | |
|---|---|
| Raw findings | 30 (+1 coverage-note elevation) |
| Canonical findings | 23 (7 merge clusters) |
| Severity | **P0: 0** · P1: 2 · P2: 16 · P3: 5 |
| Corroborated | 7 (3-way `search.py`; bidirectional `storage_primitives`; 4 cross-lens) |
| Contradictions | 0 |
| Auditors failed | 0 (6/6 delivered; suite verified 616/616 green, 32.84s) |
| Tradeoffs mapped | 2 |
| Prior watch items re-checked | 2 dropped as resolved/non-debt |

**The headline is again the zero, and a clean reseam.** Architecture-drift independently verified the reseam *succeeded*: the pre-reseam `storage_authority ↔ active_writes` circular import is eliminated, the 6-stub facade is absent, all four extracted modules (`storage_layout`, `storage_primitives`, `storage_inspection`, `storage_authority_inventory`) are standalone with clean one-way layering, and the scripts-shadowing guard still holds. The suite is green at 616/616. Nothing is actively bleeding.

**What the reseam left behind is latent and cheap.** One **P1** doc/invariant gap on the most-depended-on extracted module, one **P1** bus-factor reality, and a long tail of P2/P3 hygiene — most of it small, mechanical, and clearly remediable. The single highest-value finding: the zero-internal-import invariant that *makes the reseam's layering hold* — and that guards the data-integrity transaction model — is written down nowhere a contributor would look. A "helpful import" added to `storage_primitives.py` would silently re-create the exact circular-import class the reseam just removed.

**Severity inflation check:** 0% P0, ~9% P1 — well within tolerance. Two prior watch items verified and **dropped**: `trash`→`unlink` is no longer silent (`safe_delete` returns a `DeleteResult`; README documents fallback); the 108 JSON-field asserts are schema-stable contract checks, not brittleness.

---

## 2. Focus and Coverage

**Scope:** subsystem (Handoff runtime package). **Archetype:** Single-author (high) + High-velocity startup (high — 15 commits in one day) + active-reseam modifier. **Stakes:** high — data-integrity core reseamed ~2h before audit; published 1.7.0; exhaustive zero-debt goal.

| Auditor | Emphasis | Coverage | One-liner |
|---|---|---|---|
| code-health | primary | deep, all lenses coverage-noted | Clean style, 0 TODO, 3 broad-excepts verified deliberate; debt = post-split duplication + 2 large functions |
| architecture-drift | primary (lead-escalated) | deep, full import graph | Reseam **verified clean**; only a zombie compat shim + one doc-invariant gap + 1 latent P3 coupling |
| dependency | secondary | screened, 6 clean coverage notes | Single MIT dep, `safe_load` only, lock consistent; only version-skew + URL/LICENSE packaging gaps |
| test-debt | primary | deep, suite run 616/616 | Genuinely strong suite incl. fail-closed coverage; gap is one missing marker + the compat-shim's self-test |
| operational | primary | deep, CLI-reframed | No observability surface; CI portability + harness version-split + unbounded `transactions/` |
| knowledge | primary | deep, docs vs live code | Post-reseam docs mostly correct; `storage_primitives` omission is the live drift; bus-factor-1 |

**Bucket note (read before §3):** the skill's buckets target *selective* sprint planning. The governing goal here is *exhaustive* ("no technical debt remains"), so every actionable finding will be remediated. §3–§6 stay rubric-faithful; §7-adjacent **Remediation Execution Order** is what the next phase consumes.

---

## 3. High-Leverage Fixes (do first — unblock the rest)

### HL1 — Document `storage_primitives.py` + the layering invariant `[SY-2]` (P1)
- **category:** knowledge + architecture-drift · bidirectional corroboration (AD-3↔KN-1)
- **anchor:** `turbo_mode_handoff_runtime/storage_primitives.py:1-382`; `references/ARCHITECTURE.md:9-15`; `CONTRIBUTING.md:34-39`; `README.md` module table; `tests/test_architecture_docs.py` `REQUIRED_TOPOLOGY_CLAIMS`
- **problem:** The highest-fan-in module (21 inbound; owns `LockPolicy`, atomic writes, claim-file lock protocol — the data-integrity transaction model) is absent from every topology doc and the architecture-doc test. Its zero-internal-import invariant lives only in a module docstring.
- **impact:** A contributor (or the author months later) adding an import to `storage_primitives.py` silently re-creates the circular-import class the reseam just removed; debugging any write/lock bug requires reconstructing the model from source.
- **recommendation:** Add `storage_primitives.py` to `REQUIRED_TOPOLOGY_CLAIMS` and a one-line entry to ARCHITECTURE.md/CONTRIBUTING.md/README; promote the import-direction invariant from docstring into ARCHITECTURE.md as a stated seam. ~15-20 lines across 3 docs + 1 test. **Unblocks HL2, SY-11, SY-14, SY-19.**
- **effort:** small · **leverage:** high · **severity:** P1

### HL2 — Locking-model design rationale (bus-factor mitigation) `[SY-10]` (P1)
- **category:** knowledge (bus factor) · broadcast-amplified
- **anchor:** `git log -- plugins/turbo-mode/handoff/` → 103 commits, 1 author; `storage_primitives.py` lock/claim protocol
- **problem:** 100% single-author on a just-reseamed data-integrity core. The *why* (stdlib-only, claim-file CAS vs advisory locks, `_CLAIM_TIMEOUT_SECONDS`/`_LOCK_TIMEOUT_SECONDS`, stale-lock recovery) lives only in an execution plan + commit subjects.
- **impact:** If the sole author is unavailable, no one can safely debug a chain-state/lock failure. Compounding with each extraction. (Taxonomy P0 bar: no transition evidence → **P1**, not P0.)
- **recommendation:** Add the locking-model rationale paragraph to ARCHITECTURE.md (same edit pass as HL1). Review-practice change (PR review on next structural change; CODEOWNERS+CI already exist) is the medium-effort companion.
- **effort:** small (doc) / medium (review practice) · **leverage:** high · **severity:** P1

### HL3 — Remove the `search.py` zombie compat shim + its self-test `[SY-1]` (P2)
- **category:** architecture-drift + code-health + test-debt · **3-way independent convergence** (highest confidence in the audit)
- **anchor:** `turbo_mode_handoff_runtime/search.py:13-15,30-37`; `tests/test_search.py:27-36`
- **problem:** `2c0806f` re-exported `HandoffFile`/`Section` from `search.py` "for backward compatibility with callers that import parser symbols" — but a full-repo grep finds **zero** such callers; the only consumer is the test written to pin the shim.
- **impact:** A leaky abstraction (parsing types bleed through search's namespace) plus a brittle self-referential test that will mislead a future maintainer into deleting the test rather than restoring the export.
- **recommendation:** Remove the `HandoffFile`/`Section` re-exports + `__all__` entries + `test_search_runtime_reexports_parser_symbols_for_compatibility` in one change. Canonical import is `handoff_parsing` directly. Keep the separate `parse_handoff` re-export question out of this change (verify internal callers first — CH-5 caveat).
- **effort:** small · **leverage:** medium (collapses 3 raw findings + a brittleness source) · **severity:** P2

---

## 4. Quick Wins — exhaustive sweep (small + clear; P2/P3)

Strictly the rubric yields 0 P0/P1 quick-wins; under the exhaustive goal these small, clear, low-risk fixes are the sweep. All effort = small.

| ID | Title | Anchor | Severity |
|---|---|---|---|
| SY-12 | Dedup `_registry_key` → `storage_primitives.py` (data-integrity-class) | `load_transactions.py:931-937`, `storage_authority.py:760-766` | P2 |
| SY-21 | Add `@pytest.mark.slow` to `test_load_lock_live_contention_with_subprocess` | `tests/test_load_transactions.py:1172` | P2 |
| SY-22 | Prune `transactions/` (TTL on non-`pending` records) + slow test | `load_transactions.py:359,492`; `session_state.py:191-212`; `cleanup.py:33` | P2 |
| SY-6 | `skipif(not shutil.which("zsh"))` on 3 hardcoded `/bin/zsh` tests | `tests/test_session_state.py:1192,1230`, `tests/test_cli_commands.py:13` | P2 |
| SY-7 | Single-source `installed_host_harness.py` version constants | `installed_host_harness.py:30,160`; `tests/test_installed_host_harness.py:43` | P2 |
| SY-4 | CI Python matrix `["3.11","3.13"]` (floor+midpoint; dev is 3.14) | `.github/workflows/handoff-plugin-tests.yml:25`; `pyproject.toml:4` | P2 |
| SY-5 | Pin `uv` via `astral-sh/setup-uv@v6`; consider `ubuntu-24.04` | `.github/workflows/handoff-plugin-tests.yml:17,33` | P2 |
| SY-8 | Document `1.6.0/` dir-freeze policy + fix 3 `plugin.json` marketplace URLs | `CONTRIBUTING.md`; `.codex-plugin/plugin.json:14-18` | P2 |
| SY-9 | `## Chain State Diagnostics` runbook (10 codes: trigger\|recovery) | `references/ARCHITECTURE.md:27-30`; `chain_state.py` 15 raise sites | P2 |
| SY-11 | 3 back-fill ADRs in `docs/decisions/`, linked from CONTRIBUTING.md | `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md` | P2 |
| SY-13 | Consolidate identical `_state_candidate_paths`/`_state_like_residue_paths` | `chain_state.py:525-538` | P2 |
| SY-14 | Comment why `chain_state._read_json_object` shadows the primitive | `chain_state.py:772-797` | P2 |
| SY-3 | `storage_authority_inventory.py` doc note + `parents[5]` comment | `storage_authority_inventory.py:1-188`; ARCHITECTURE.md | P2 |
| SY-17 | Annotate 14 `layout: StorageLayout` private params | `load_transactions.py:289…859` (14 sites) | P3 |
| SY-18 | Remove 2 dead `return None` branches in `_skip_reason` | `storage_authority.py:589-593` | P3 |
| SY-20 | Add MIT `LICENSE` file (published artifact) | `plugins/turbo-mode/handoff/1.6.0/` | P3 |
| SY-23 | `rglob("*.md")` → flat `glob` + targeted archive scan | `storage_authority.py:252` | P3 |

## 5. Strategic Items (larger refactors — sequence last, behind green suite)

### ST1 — Decompose `write_active_handoff` `[SY-15]` (P2, medium)
- **anchor:** `turbo_mode_handoff_runtime/active_writes.py:463-618` — 156 lines, 5-level nesting, 4 interleaved concerns, 8× `_write_json_atomic`, the highest-risk write path.
- **planning_notes:** Behavior-preserving extraction only. Pull out the atomic-file-write block (~515-555) into `_write_content_to_active_path(...)` and the repeated state-update into a helper. TDD/characterization tests around it first; one commit, full suite + `installed_host_harness` after.

### ST2 — Decompose `session_state.main()` `[SY-16]` (P2, medium)
- **anchor:** `turbo_mode_handoff_runtime/session_state.py:230-697` — 468 lines, 16 `if args.command ==` branches.
- **planning_notes:** Extract `_build_parser()` + `_dispatch()`; lift the chain-state and active-writer command groups (pure delegations) into handlers. Pure structural refactor; CLI behavior and `test_cli_commands.py` must stay green unchanged.

## 6. Watch List

- **WL1 `[SY-19]`** `chain_state` imports `StorageLocation` from `storage_authority` — latent coupling, possibly conscious. *Cheap discharge: a one-line "intentional bridge type" comment now resolves the debt without extraction.* Revisit if `storage_authority` ever needs to call `chain_state`.
- **WL2 `[SY-23]`** `rglob` depth — only bites at ~500+ handoffs/project. Listed in §4 because the flat-`glob` fix is small and correct; if deferred, trigger = `/load` latency reported.

---

## 7. Tradeoff Map

**TR1 — Refactor ↔ Ship** *(anchors: `active_writes.py:463-618`, `session_state.py:230-697`)* — ST1+ST2 are medium-effort decompositions landing on one author immediately after a 15-commit reseam day. Resolution in this backlog: they are sequenced **last**, behind the green suite, as pure behavior-preserving refactors — not interleaved with the cheap sweep.

**TR2 — Doc-as-Code ↔ Bus-Factor under-investment** *(anchors: SY-2/SY-10/SY-11)* — HL1+HL2+SY-11 are one overlapping documentation/ADR investment. It is doc time the sole author "already knows," so the cost is visible and the benefit invisible until the bus arrives — the classic under-invested quadrant. Resolution: bundle them into one doc pass so the marginal cost is near-zero.

---

## 8. Remediation Execution Order (consumed by the writing-plans phase)

The goal is **zero debt remaining**, so all 23 are in scope. Sequenced by leverage + dependency + risk, each gated by `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q` + `installed_host_harness.py` + `git diff --check`, committed in coherent surface-scoped chunks:

1. **Docs/knowledge pass** (HL1 SY-2, HL2 SY-10 doc part, SY-11 ADRs, SY-9 diagnostics runbook, SY-8 policy, SY-3 doc note, SY-14/SY-19 rationale comments) → one docs-surface commit + the `test_architecture_docs.py` topology-claim update. *Do first: HL1 documents the invariant that protects every subsequent source edit.*
2. **Source dedup/cleanup pass** (HL3 SY-1 shim removal, SY-12 `_registry_key`, SY-13 path-fn, SY-17 annotations, SY-18 dead branches, SY-20 LICENSE, SY-23 glob) → source-surface commit(s); suite must stay 616-green.
3. **CI/packaging pass** (SY-4 matrix, SY-5 uv pin, SY-6 zsh guard, SY-7 harness constants, SY-21 marker, SY-22 transaction prune) → CI/test-surface commit(s); validate workflow YAML.
4. **Larger refactors** (ST1 SY-15, then ST2 SY-16) → one commit each, behaviour-preserving, full verification between.
5. **Zero-confirmation:** full suite green + `installed_host_harness` pass + `git diff --check` clean + re-run architecture-doc test; restate the backlog with every item closed or consciously dropped with rationale.

## Open Questions (resolve during planning, not blocking)
1. `docs/decisions/` ADR location — repo treats `docs/superpowers/plans/` & `docs/tickets/` as control docs; confirm ADR home fits policy (mirrors prior audit's open-Q on `docs/audits/`).
2. SY-8: is the `1.6.0/` directory name a permanent marketplace-install freeze (then document it + keep the test literal) or should it track the manifest (then rename + update 3 tests + URLs)? Evidence leans freeze (test asserts the literal path intentionally).
3. SY-3 relocation of `storage_authority_inventory.py` out of the runtime namespace — do the cheap doc+comment now; treat physical relocation as optional (low real cost while not distributed standalone).

---

## Closeout — 2026-05-15

**Status: backlog driven to zero. All 23 canonical findings closed.**

- **Branch:** `chore/handoff-runtime-debt-elimination` from `main` `0981c41`.
- **Commits (6):** `ba3ea5d` audit+plan · `750ce7c` Pass 1 docs/knowledge · `e9e7ca1` Pass 2 source dedup · `edcf194` Pass 3 CI/packaging · `71f49f7` SY-15 · `b7df7f5` SY-16.
- **Verification (final):** suite **617 passed** (616 baseline −1 deleted SY-1 self-test +1 SY-12 ownership test +1 SY-22 prune test); package import-shape smoke ok; `test_architecture_docs.py` enforces the new `storage_primitives` topology claim; `test_storage_authority_inventory.py` fixture matches; `ruff check` clean across `turbo_mode_handoff_runtime/` + `tests/`; `git diff --check` clean. Every task gated by the bytecode-safe harness.

**Closure map:**

| Pass | Commit | Findings |
|---|---|---|
| 1 docs/knowledge | `750ce7c` | SY-2, SY-3(doc), SY-8, SY-9, SY-10, SY-11, SY-14, SY-19 |
| 2 source dedup/cleanup | `e9e7ca1` | SY-1, SY-12, SY-13, SY-17, SY-18, SY-20, SY-23 |
| 3 CI/packaging | `edcf194` | SY-4, SY-5, SY-6, SY-7, SY-21, SY-22 |
| 4 larger refactors | `71f49f7`, `b7df7f5` | SY-15, SY-16 |

**Conscious scope decisions (closed via documentation/decision, smallest-credible-change; consistent with the audit's own P3/watch ratings):**
- **SY-3** — physical relocation of `storage_authority_inventory.py` out of the runtime namespace NOT done; doc note + `parents[5]` comment + a documented fixture-regeneration command (CONTRIBUTING.md) discharge the actionable cost. Relocation has near-zero real cost while the package is not distributed standalone.
- **SY-19** — `StorageLocation` coupling documented as the intentional shared bridge type rather than extracted (the audit's disconfirmation noted conscious design was plausible).
- **SY-23** — `rglob` NOT swapped to flat `glob`: evidence showed equivalence depends on a subtle `_skip_reason` over-discover-then-filter invariant (archive dirs are subdirs of the active root); discharged as a documented intentional choice + watch trigger, per the plan's revert-to-watch branch and the audit's P3/watch rating.
- **SY-16** — further `_handle_chain_state`/`_handle_active_writer` sub-handlers (plan Step 5) NOT done; CH-1's named cost is discharged by the `_build_parser`/`_dispatch` split. Additional sub-grouping of a data-integrity CLI adds risk without removing additional audited debt.

**Out-of-scope follow-up (named, not silently fixed, not silently ignored):** Pyright surfaces a pervasive, pre-existing, runtime-correct `dict[str, object]` → `object` value-typing pattern across the runtime (iteration/subscript/`write_text` args). The repo gate is `ruff` + `pytest` (both clean/green); the evidence-based audit (repo standards) did not surface it; the CHANGELOG shows TypedDict adoption is a separate incremental effort. Recommend a future "runtime typing-precision / TypedDict pass" as one named follow-up — explicitly out of this evidence-scoped backlog (folding it in would be unbounded scope expansion the repo posture forbids).

**Residue:** pre-existing gitignored local residue (`.DS_Store` 05-14, `.pytest_cache` 05-14, `__pycache__` 05-15 13:02) predates this work; the bytecode-safe verification commands wrote zero `.pyc` into source paths (`PYTHONPYCACHEPREFIX` redirected to `/private/tmp/codex-tool-dev-pycache`). Preserved as unrelated local state per repo policy.
