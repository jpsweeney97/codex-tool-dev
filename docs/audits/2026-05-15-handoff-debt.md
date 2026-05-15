# Tech Debt Audit — Handoff Plugin 1.6.0

**Target:** `plugins/turbo-mode/handoff/1.6.0/` · **Date:** 2026-05-15 · **Scope:** subsystem · **Stakes:** medium
**Method:** 6 parallel category-scoped auditors (code-health, architecture-drift, dependency, test-debt, operational, knowledge) + lead synthesis. The per-auditor raw findings and synthesis ledger lived in `.tech-debt-audit-workspace/`, which is **gitignored, untracked scratch — not part of this tracked record**. Every claim that matters is restated with `file:line` anchors in this self-contained report; the report does not depend on the scratch directory existing.

---

## 1. Audit Snapshot

| | |
|---|---|
| Raw findings | 38 |
| Canonical findings | 20 (10 merge clusters) |
| Severity | **P0: 0** · P1: 6 · P2: 11 · P3: 3 |
| Buckets | quick-wins: 4 · high-leverage: 2 · strategic: 1 · watch: 13 |
| Corroborated | 6 (independent or cross-lens) |
| Contradictions | 3 resolved, 0 escalated |
| Auditors failed | 0 (6/6 delivered) |
| Tradeoffs mapped | 3 |

**The headline is the zero.** Nothing in this plugin is actively bleeding — no incidents, no velocity-stop, no P0. For a published single-author tool mid-refactor, the debt is **latent and concentrated**, not pervasive: one structural hotspot (`storage_authority.py`, 1733 lines, flagged independently by three lenses) and a cluster of cheap release-hygiene gaps that are wrong *right now* for a published artifact.

**Why the watch list is 65% (and why that's not inflation):** The rubric flags >40% watch as "logging observations." Here it is the opposite — it is an accurate portrait of a clean codebase. The P0/P1 surface is genuinely small; most real debt is latent (P2) and several watch items are *cheap companions* to the quick-wins (test-suite-readiness pairs with the CI fix; runbook/ADR pair with the bus-factor fix). The watch list below is grouped by companion relationship, not dumped flat.

**Severity inflation check:** 0% P0, 30% P1 — within tolerance. One silent-failure finding (SY-13) was *raised* P2→P1 with explicit rationale; one structural finding (SY-1) raised P2→P1 on corroboration. **Correction:** SY-12's earlier P2→P1 raise has been **retracted** and the finding demoted to P3/watch — see WL13. `quality_check.py` is not a wired gate in 1.6.0, so the "fails open" rationale that justified the raise does not apply at this version.

---

## 2. Focus and Coverage

**Scope:** `subsystem` — the Handoff plugin package only. **Archetype:** Single-author project (high confidence) + High-velocity startup (medium), with published/versioned mature-platform modifiers. **Stakes:** medium — data-integrity + published plugin, no SLA/payments/incidents.

**Emphasis map (archetype-derived):**

| Auditor | Emphasis | Coverage status |
|---------|----------|-----------------|
| code-health | primary | **deep** — 6 lenses, all coverage-noted |
| test-debt | primary | **deep** — 6 lenses, ran no suite (read-only), mocks-vs-reality verified clean |
| operational | primary | **deep** — reinterpreted for CLI plugin (no server runtime) |
| knowledge | primary | **deep** — docs cross-referenced against live source |
| architecture-drift | secondary | **screened + promoted** — import graph mapped, shadowing sentinel run |
| dependency | secondary | **screened** — thin surface, 6 clean coverage notes |

**Per-category one-liners:** Code Health — clean style, one genuine mixed-concern module. Architecture — sound; migration landed cleanly; one managed circular import + a leaky facade. Dependency — clean (single MIT dep, lockfile present, safe_load only); only release-integrity gaps. Test Debt — genuinely strong suite; the gap is *automation*, not coverage. Operational — release/bring-up hygiene gaps, no observability gap (CLI tool). Knowledge — bus-factor-1 and doc drift dominate, as the archetype predicts.

**Framing correction:** Lead reconnaissance said "no lockfile." A `uv.lock` exists (pins pyyaml 6.0.3). The dependency auditor verified against the live tree rather than trusting the frame — proof discipline working as intended. This partially de-risks SY-4.

---

## 3. Quick Wins

*Bucket: (P0/P1) + small effort + clear remediation. Ordered by severity then leverage. Start here with QW1-QW4. The former QW5 identifier is retained only as a redirect for traceability and is not part of this execution queue.*

### QW1 — Add CI to run the existing test suite `[SY-3]`
- **category:** test-debt + operational (independent convergence — two auditors, two framings)
- **anchor:** repo: no `.github/workflows/` anywhere
- **problem:** A substantial pytest suite covering the data-integrity paths, with **zero** automation. *(Do not hard-code a count here: it drifts. As of this audit, `pytest --collect-only -q` reports ~600 tests across 23 modules; the README's "354 / 10 modules" is already stale — see QW3. The exact number is whatever `--collect-only` currently returns.)* The runtime-package migration (6 commits) and two BREAKING changes shipped with no regression gate.
- **impact:** Every change to `active_writes.py` / `load_transactions.py` / `storage_authority.py` is unverified until someone runs pytest by hand. Highest-leverage gap in the audit — it gates safe execution of every refactor below.
- **recommendation:** GitHub Actions workflow running the bytecode-safe form `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/... uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q` on push/PR for the subtree. Bundle the cheap companions WL7/WL8/WL9 (markers, flake-hardening, coverage) so the pipeline is actually useful.
- **effort:** small · **leverage:** high (unblocks regression detection for all data-integrity findings; safety net for SY-1/SY-2)

### QW2 — Reconcile `plugin.json` version with the `[Unreleased]` CHANGELOG `[SY-4]`
- **category:** dependency + operational + knowledge (triple independent convergence)
- **anchor:** `.codex-plugin/plugin.json:3`, `pyproject.toml:3`, `uv.lock:16`, `CHANGELOG.md:7-19`, `tests/test_release_metadata.py:38-44`
- **problem:** `plugin.json` says `1.6.0` while `[Unreleased]` carries two BREAKING changes (storage path move, module namespace move) already present in source.
- **impact:** A *published* plugin whose version label misrepresents shipped behavior. Any version-gated tooling (refresh tooling, marketplace gates) draws wrong conclusions; rollback has no clean baseline.
- **recommendation:** Cut `1.7.0` (semantically correct — these are BREAKING) and bump it **consistently across all version surfaces**: `.codex-plugin/plugin.json`, `pyproject.toml`, the `handoff-plugin` entry in `uv.lock`, plus a stamped `CHANGELOG` section. **Critical second-order effect:** `tests/test_release_metadata.py::test_versions_are_aligned()` hard-codes `== "1.6.0"` for *both* `plugin.json` and `pyproject.toml`, so any bump turns that test **red** unless the assertions are updated in the same change. A partial bump (e.g. `plugin.json` + `uv.lock` only, as an earlier draft of this item suggested) leaves `pyproject.toml` stale **and** breaks the suite. Or, if truly unshipped, roll source back. Do not leave BREAKING changes stranded under an unbumped published version, and do not bump partially.
- **effort:** small · **leverage:** medium

### QW3 — Fix the broken README install/dev paths (+ missing `/summary`, stale count) `[SY-5]`
- **category:** knowledge + operational (independent convergence)
- **anchor:** `README.md:17, 251-253, 257, 268, 36-44`
- **problem:** README points to `packages/plugins/handoff` (does not exist; actual: `plugins/turbo-mode/handoff/1.6.0`). `uv run --package handoff-plugin` resolves nothing (no workspace). README also omits the `/summary` skill and claims a stale "354 tests / 10 modules" (actual ~23 modules).
- **impact:** Deterministic failure at step 1 for every contributor/dev following the docs on a *published* plugin. Compounding contributor-acquisition tax.
- **recommendation:** Replace all `packages/plugins/handoff` with `plugins/turbo-mode/handoff/1.6.0`; replace the `--package` command with the `--directory` bytecode-safe form; add the `/summary` row to the skills + capabilities tables and the `summary` frontmatter value; replace the hardcoded test count with a `--collect-only` command or drop it.
- **effort:** small · **leverage:** medium

### QW4 — De-duplicate the `LEGACY_CONSUMED_PREFIX = "MIGRATED:"` constant `[SY-13]`
- **category:** architecture-drift (boundary erosion)
- **anchor:** `storage_authority.py:73`, `session_state.py:35`
- **problem:** The same on-disk consumed-marker sentinel is defined independently in two modules. Test-debt confirms **no contract test** guards their agreement.
- **impact:** A future edit to one (different prefix / payload) silently misreads consumed legacy state as unconsumed → **chain-state resurrection**, the exact silent data-integrity failure this plugin exists to prevent.
- **recommendation:** Define once (export from `storage_primitives.py`), import in both sites. ~5 minutes. Add a one-line test asserting both sites resolve to the same value.
- **effort:** small · **leverage:** medium · *(severity raised P2→P1: compounding correctness debt in a published data tool with no guarding test)*

### QW5 — Retired / reclassified; see WL13 `[SY-12]`
- **status:** Not a quick win. The earlier QW5 framing treated `quality_check.py` as an active gate, but live 1.6.0 keeps it unwired (`hooks.json` empty; README/tests enforce non-wiring).
- **action:** No 1.6.0 action here. Track the latent helper behavior under WL13 and harden it only if future hook-enablement work wires this helper into a PostToolUse hook.

---

## 4. High-Leverage Fixes

*Bucket: leverage = high, effort ≤ medium. Investing here removes other backlog items. Ordered by downstream count.*

### HL1 — Remove the `storage_authority` active-write proxy facade `[SY-2]`
- **category:** architecture-drift (primary) + code-health (corroborating)
- **anchor:** `storage_authority.py:127-232`, `active_writes.py:17-22`, `load_transactions.py:17-24`
- **problem:** Six zero-logic forwarding stubs proxy `active_writes` functions. Callers (`load_transactions`, skills via `session_state`) bypass the facade and import directly — so it adds no enforced boundary, only cost. It is also the cause of the managed `storage_authority`↔`active_writes` circular import and the `project` vs `project_name` parameter-rename drift.
- **impact / unblocks (4):** removes the circular import (AD-1), dissolves the naming drift (CH-4/AD-7), shrinks `storage_authority.py` toward the SY-1 reseam, and clears the path for the SY-14 `session_state` extraction.
- **recommendation:** Decide the public API surface: either enforce `storage_authority` as the single facade via `__init__.py` re-exports, or (recommended) delete the stubs and let callers import from `active_writes` directly. The latter eliminates AD-1 as a side effect.
- **effort:** medium · **leverage:** high · **severity:** P2 · *cross-lens followup confirmed (prompted by code-health CH-1)*

### HL2 — Add contributor scaffolding: CODEOWNERS + CONTRIBUTING + architecture map `[SY-8]`
- **category:** knowledge (bus factor + ownership + onboarding)
- **anchor:** repo root (no CODEOWNERS / CONTRIBUTING anywhere); `storage_authority.py`/`active_writes.py`/`load_transactions.py`/`session_state.py`
- **problem:** Every commit to every critical module is single-author. No CODEOWNERS, no CONTRIBUTING, no design-level orientation. The one person who understands the 1733-line state machine is the only person who can debug a data-integrity issue or cut a release.
- **impact / unblocks (3):** a CONTRIBUTING + architecture map directly resolves the SY-19 recovery-runbook gap and the SY-20 ADR gap (same knowledge-scaffolding investment), and pairs with the QW1 CI gate (CODEOWNERS unblocks PR review automation).
- **recommendation:** (1) `.github/CODEOWNERS` → `plugins/turbo-mode/handoff/ @jpsweeney97` (2-min). (2) `CONTRIBUTING.md` with the correct setup/test commands and a pointer to `handoff-contract.md`. (3) A 10-20 line module docstring on `storage_authority.py`/`session_state.py` + optional `references/ARCHITECTURE.md` covering the transaction/locking model.
- **effort:** medium · **leverage:** high · **severity:** P1 · *(P0 bar applied strictly by the auditor — no transition evidence, so P1 not P0)*

---

## 5. Strategic Items

*Bucket: (P0/P1) + large effort. Roadmap planning, not a single sprint.*

### ST1 — Reseam `storage_authority.py` (1733-line mixed-concern module) `[SY-1]`
- **category:** code-health × architecture-drift × knowledge (independent convergence: CH-1 + AD-4, plus KN-6 undocumented)
- **anchor:** `turbo_mode_handoff_runtime/storage_authority.py:1-1733`
- **problem:** One module owns four responsibilities with no internal seams — path/layout arithmetic, filesystem discovery, the chain-state state machine, and the active-write proxy facade — behind a single one-line docstring. Testing chain-state logic forces setup of discovery/layout state.
- **impact:** Highest-churn module in the subtree; every chain-state change pays a navigation + review-surface tax. The undocumented model (KN-6) compounds the bus-factor risk (HL2) — the same person who must maintain it is the only one who understands it.
- **recommendation:** Sequenced reseam, not a big-bang. **planning_notes:** (1) Do HL1 first — removing the facade shrinks the module and breaks the circular import, making extraction safe. (2) Extract `storage_layout.py` (`StorageLayout`/`get_storage_layout`/path arithmetic) — lowest-risk slice, immediately independently testable. (3) Extract the chain-state lifecycle as a second pass. (4) Gate every step behind the QW1 CI suite. Fold the hotspot-local cleanups SY-9 (duplicated helpers) and SY-11 (`write_active_handoff` complexity) *into* this work rather than patching them separately (avoids merge churn — see TR1).
- **effort:** large · **leverage:** medium · **severity:** P1

---

## 6. Watch List

*Latent (mostly P2) or cheap companions. Track the trigger; revisit then. Grouped by relationship.*

**Companions to QW1 (CI) — do them when you set up the workflow:**
- **WL7 `[SY-16]`** No pytest markers / no `[tool.pytest.ini_options]` — can't extract a fast unit subset. *Trigger: with QW1.*
- **WL8 `[SY-17]`** Two live lock-contention tests use `time.sleep` polling — latent flake. *Trigger: at QW1 — harden readiness or mark slow before CI runs them.*
- **WL9 `[SY-18]`** No coverage instrumentation — `storage_authority` branch coverage unknown. *Trigger: with QW1; run once before ST1 to map untested branches.*

**Companions to HL2 (knowledge scaffolding) — same investment:**
- **WL10 `[SY-19]`** No recovery runbook for the 5 `ChainStateDiagnosticError` codes. *Trigger: before a 2nd user/contributor, or fold into HL2.*
- **WL11 `[SY-20]`** No ADR practice — migration/storage-path/hook rationale only in execution plans. *Trigger: fold the 3 back-fill ADRs into HL2.*

**Companions to ST1 (storage reseam) — fold in, don't patch separately:**
- **WL3 `[SY-9]`** Duplicated path/git/lock helpers in the storage layer. *Trigger: during ST1 step 2-3.*
- **WL5 `[SY-11]`** `write_active_handoff` — 148 lines, 5-level nesting, data-integrity write path. *Trigger: during ST1; or immediately if a write-path data bug is traced here.*
- **WL6 `[SY-14]`** `session_state.py main()` — 460+-line cross-domain dispatcher. *Trigger: after HL1; cheap interim = add a scope doc-comment now.*

**Standalone latent:**
- **WL1 `[SY-6]`** `trash` documented as required but silently degrades to permanent `unlink`. *Trigger: before any Linux/CI distribution, or if any unexpected permanent-delete is reported. Cheap honest fix: correct README wording + one runtime warning.*
- **WL2 `[SY-7]`** Brittle tests — 108 exact JSON-field asserts + a full-string error equality. *Trigger: before the next operation-state schema change / `schema_version` bump.*
- **WL4 `[SY-10]`** Unbounded growth — `transactions/`/`markers/` dirs + `rglob` scans, no pruning. *Trigger: when any project's `.session-state/transactions/` exceeds ~hundreds of files or `/load` latency becomes perceptible.*
- **WL12 `[SY-15]`** Legacy `docs/handoffs/` fallback has no exit condition (P3). *Trigger: add the 5-min removal-condition comment now; remove the shim at 2.0 or when no user repos retain `docs/handoffs/`.*
- **WL13 `[SY-12]`** `quality_check.py:419-426, 431-443` swallows its own `validate()`/serialization exceptions and returns 0 (P3) — **reclassified from QW5**; dormant because it is *not* a wired gate in 1.6.0 (`hooks.json` empty; README/tests enforce non-wiring). *Trigger: only if a future release wires this helper into a PostToolUse hook — harden it in the same change. No action for 1.6.0.*

---

## 7. Tradeoff Map

**TR1 — Stop-the-Bleeding ↔ Build-the-Future** *(anchor: `storage_authority.py`)*
The hotspot has both a 5-minute data-integrity fix (QW4/SY-13) and a multi-week reseam (ST1). Patching SY-9/SY-11 locally now creates merge churn against the eventual reseam; deferring everything leaves the data-integrity divergence (SY-13) unguarded. **Resolution in this backlog:** SY-13 now (cannot wait — silent corruption class), SY-9/SY-11 folded into ST1.

**TR2 — Refactor ↔ Ship** *(anchors: SY-2, SY-1, single maintainer)*
The runtime-package migration just landed. HL1→ST1 front-loads another structural refactor before feature/skill work — all on one person. The audit's position: HL1 is cheap and unblocking enough to be worth it before more features; ST1 is explicitly roadmap, not next-sprint.

**TR3 — Bus-Factor Fix ↔ Speed** *(anchors: SY-8, the `storage_authority` hotspot)*
HL2's cure (CONTRIBUTING, architecture docs, eventual non-author review on `storage_authority`) slows the single author who is currently fastest working solo. The cost is visible immediately; the benefit is invisible until the author is unavailable. This is the classic under-invested tradeoff — named here so it is a conscious choice, not a default.

*(Test-Coverage ↔ Deploy-Speed is non-applicable: no CI exists, so test gates cost zero pipeline time today. The auditors correctly collapsed it rather than forcing a generic tradeoff.)*

---

## 8. Open Questions / Next Probes

1. **Is the `[Unreleased]` block actually shipped or genuinely pending?** QW2's remediation forks on this. Note: there is **no `1.6.0` git tag in this checkout** (`git tag --list` is empty), so "after the 1.6.0 tag" is not a usable signal — the earlier draft's tag-based dating was unsupported. What *is* observable: the BREAKING source changes (storage-path move, module-namespace move) are already present in the working tree and the changelog, which points toward shipped. Confirm against the actual release/publish record before choosing "cut 1.7.0" vs "roll back source."
2. **Is the facade (HL1) intentional API isolation or migration residue?** AD-7's naming-drift evidence points to residue. A 1-line confirmation from the author changes HL1 from "remove" to "enforce" — worth resolving before the work starts.
3. **What is the real handoff-history scale in practice?** SY-10's severity (watch vs promote) depends on whether any real project has hundreds of sessions. If long-lived projects are the norm, the unbounded-growth cliff moves up.
4. **Should `docs/audits/` be the durable home for these reports?** This used the skill default. The repo treats `docs/superpowers/plans/` and `docs/tickets/` as tracked control docs — confirm the audit artifact location fits the repo's documentation policy.

---
*Workspace artifacts: `.tech-debt-audit-workspace/` is **gitignored, untracked, local-only scratch** (per-auditor findings, framing, synthesis ledger). It is not a durable evidence bundle, will not exist in a fresh clone, and must not be cited as audit evidence — this report stands alone on its own anchored claims. The scratch directory is safe to delete.*
