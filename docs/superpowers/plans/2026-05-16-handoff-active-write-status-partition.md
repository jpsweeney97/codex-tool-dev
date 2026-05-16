# Handoff Active-Write Status-Domain Partition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode the active-write status-domain partition (operation-state-record statuses vs transaction-record statuses) as two source-grounded `Literal` aliases, gated by a write-spy lifecycle-matrix regression test that asserts the partition on *every* write (transients included), with an advisory (non-blocking) pyright CI surface — the named PR #15 out-of-scope follow-up, executed as the incremental partition slice, NOT the broad `dict[str, object]` pass.

**Architecture:** The product is a *documented, test-enforced status partition*, not TypedDict coverage. Two `Literal` aliases land in `active_writes.py` (the lifecycle authority that emits these strings), matching the in-package `distill.py` alias convention. Only the `_persist_operation_and_transaction.transaction_status` parameter is annotated — every call site passes a string literal, so pyright gains real value with zero new boundary noise. The `ActiveWriteReservation.status` field annotation is **deliberately deferred** (it would introduce a new pyright error at the `_reservation_from_payload` JSON boundary that only a validating-coercion — broader-follow-up scope — should resolve). The real regression gate is a lifecycle-matrix pytest that monkeypatches the single atomic-write chokepoint (`active_writes._write_json_atomic`) and asserts the discriminating invariant on the *complete write history* of every reachable path (begin, success-with-transients, abandon, reservation_expired write-path, begin-time auto-expire, content_mismatch, reservation_conflict ×2, cleanup_failed, recovery ×3 including recover-success). Coverage is asserted **per status domain** (operation-state members in operation-state writes, transaction members in transaction writes), not as a domain-blind union. `session_state.py` is NOT modified and gains NO module-level import of the alias (documented layering trap); a test-layer consistency check keeps `TERMINAL_TRANSACTION_STATUSES` aligned.

**Tech Stack:** Python ≥3.11 (`typing.Literal`, `typing.get_args`), pytest 8 (`monkeypatch`, bytecode-safe harness), uv 0.10.11, ruff, GitHub Actions (`ubuntu-24.04`, py 3.11/3.13), pyright (advisory only).

---

## Source-Grounded Status Vocabulary (authoritative — derived from live source at HEAD, NOT from the Codex dialogue)

Verified by reading `turbo_mode_handoff_runtime/active_writes.py` at commit `6d43d8d`. Every **persisted** status below has a write site; the **Domain** column is the path the status is written to. The single exception — `unreadable` — is a synthetic read-path record that is never persisted; it is listed separately, after the persisted tables, and is *not* claimed to have a write site.

**Operation-state-record statuses** — written to `.../active-writes/<project>/<run>.json`:

| status | write site (active_writes.py) | runtime-observable by Task 3? |
|---|---|---|
| `begun` | :213 → :217 (reservation init) | scenario `begin` |
| `content-generated` | :557 → :563 (transient) | scenario `success` (spy) |
| `content_mismatch` | :578 → :580 (write path) ; :773 → :775 (recovery) | scenarios `content_mismatch`, `recover_mismatch` |
| `write-pending` | :592 → :600 (transient) | scenario `success` (spy) |
| `cleanup_failed` | :615 → :621 | scenario `cleanup_failed` (fault-injected) |
| `committed` | :631 ; :793 → :804 — **operation-state ONLY** | scenarios `success`, `recover_success` |
| `abandoned` | :705 → :713 | scenario `abandon` |
| `reservation_expired` | :942 → :946 (write path) ; :401 → :402 (auto-expire) | scenarios `reservation_expired`, `auto_expire` |
| `pending_before_write` | :752 → :754 (recovery reset) | scenario `recover_pending` |
| `reservation_conflict` | :978 → :985 (snapshot) ; :1020 → :1026 (watermark) | scenarios `conflict_snapshot`, `conflict_watermark` |

**Synthetic operation-state status (read-path, NOT persisted):**

| status | construction site (active_writes.py) | persisted? | runtime-observable by Task 3? |
|---|---|---|---|
| `unreadable` | :1104 in `_unreadable_active_write_record`, returned by the read-only `list_active_writes` (:666, :670) | **No** — never passed to `_write_json_atomic` by any flow | **static-pin only** (see Gate G3 rationale) |

`unreadable` is operation-state-*shaped* (it carries `status: "unreadable"` and `list_active_writes` groups it with operation-state records) but it is constructed in memory and returned to a read-only caller — never written through the atomic-write chokepoint. It stays in `ActiveWriteOperationStateStatus` as a statically-pinned member (a real status string the module emits) and is deliberately excluded from the runtime write-spy coverage gate (Gate G3).

**Transaction-record statuses** — written to `.../transactions/<txn>.json`:

| status | write site (active_writes.py) | runtime-observable by Task 3? |
|---|---|---|
| `pending_before_write` | :222 (begin) ; :760 (recovery) | scenarios `begin`, `recover_pending` |
| `content-generated` | :567 (transient; also the residual tx status on the write-path content-mismatch) | scenarios `success` (spy), `content_mismatch` |
| `content_mismatch` | :781 (recovery ONLY) | scenario `recover_mismatch` |
| `write-pending` | :604 (transient) | scenario `success` (spy) |
| `cleanup_failed` | :625 | scenario `cleanup_failed` |
| `completed` | :642 ; :808 → :811 — **transaction ONLY** | scenarios `success`, `recover_success` |
| `abandoned` | :717 | scenario `abandon` |
| `reservation_expired` | :404 (auto-expire) ; :952 (write path) | scenarios `reservation_expired`, `auto_expire` |
| `reservation_conflict` | :991 (snapshot) ; :1031 (watermark) | scenarios `conflict_snapshot`, `conflict_watermark` |

**Discriminating invariant (the stop-tripwire):** `committed` ∈ operation-state domain only; `completed` ∈ transaction domain only. Additionally `begun` is a *persisted* operation-state-only status, and `unreadable` is a synthetic operation-state-shaped status that is never persisted at all. All other statuses appear in both domains. If any *write* (not just final state) ever puts `completed` into an operation-state file, or `committed`/`begun`/`unreadable` into a transaction file, the source-domain model is wrong — **STOP** (see Stop Conditions). The `unreadable` arm of this tripwire asserts an invariant that must hold *trivially* — `unreadable` is never written by any flow — so if the Task 3 write-spy ever observes it, the synthetic-record assumption itself is false (Stop Condition 1 / Gate G3).

**Correctness note (was a latent plan defect, now pinned):** on the *write-path* content-mismatch (`write_active_handoff`), only the operation-state record is updated to `content_mismatch` (active_writes.py:580 writes operation state only); the transaction record is left at its last value, `content-generated` (:567). Transaction `content_mismatch` is produced **only** by the recovery path (:781). Task 3 asserts exactly this — it does not assume the transaction becomes `content_mismatch` on the write path.

---

## Stop Conditions, Evidence Gates, Commit Boundaries

This is an execution-control document. Honor these gates.

**Stop conditions (halt and report; do not proceed):**

1. **Domain-model tripwire (Codex dialogue evidence (i)), now write-granular:** If the Task 3 write-spy observes ANY call writing `completed` into a path under `.../active-writes/`, or `committed`/`begun`/`unreadable` into a path under `.../transactions/` — at *any* point in a lifecycle, including transient/intermediate writes — the partition model is falsified. Stop, convert Task 3 into lifecycle bug-triage, do NOT land the aliases as written.
2. **Noise-threshold tripwire (dialogue evidence (ii)) — measured as a delta, never inferred:** *Introduced count* = (Task 4 Step 3 post-annotation pyright `--stats` error count) − (Task 2 Step 1 pre-annotation baseline error count). Both probes MUST use the **identical command and scope**: `pyright --stats turbo_mode_handoff_runtime/active_writes.py` — deliberately the single annotated file (the annotation's blast radius), narrower than the Task 5 package-wide CI surface; the two scopes are **not** cross-compared. If the introduced delta exceeds ~3 new `cast(...)`/`# type: ignore`/`Any` widenings (NOT pre-existing unrelated `dict[str, object]` findings), drop scope: keep Tasks 0, 1, 3, 5 (alias + runtime gate + CI advisory), file a tracked baseline-reduction ticket, do NOT land Task 2. Record the baseline count, the post count, and the delta in the closeout. (Expected delta: 0 — every `transaction_status` call site passes a string literal; this a-priori expectation does NOT substitute for capturing the baseline.)
3. **Coverage-gap tripwire (round-2 review Finding 2):** If `test_observed_status_coverage` shows any runtime-reachable alias member (every member except the explicitly-enumerated `unreadable`) was NOT observed by the write-spy *in its own status domain* (operation-state members in operation-state writes; transaction members in transaction writes — a domain-blind union does NOT satisfy this), STOP — the gate does not actually prove the partition; investigate the missing path before landing docs/ADR claims of runtime enforcement.
4. Repo-level: any destructive cleanup decision, stale runtime state, or generated residue blocking verification — name it and the decision needed.

**Evidence gates (must pass before the dependent commit):**

- **G0 (after Task 0):** branch `feature/handoff-active-write-status-partition` exists off `main`; this plan file is committed (tracked) so later ADR/closeout references resolve to a real artifact.
- **G1 (after Task 1):** new partition test green; full Handoff suite green; ruff clean on changed paths.
- **G2 (after Task 2):** Task 2 Step 1 pre-annotation pyright baseline captured to `/tmp/handoff-partition-pyright-baseline.txt` (same command/scope as the Task 4 Step 3 probe) BEFORE the annotation edit, so Stop Condition 2's introduced-count is a real delta and not an inferred 0; full Handoff suite still green (annotation is behavior-preserving); ruff clean.
- **G3 (after Task 3):** all 12 lifecycle-matrix scenarios green; `test_observed_status_coverage` green AND `RUNTIME_OP_MEMBERS ⊆ observed["op"]` and `RUNTIME_TX_MEMBERS ⊆ observed["tx"]` (per-domain, not a domain-blind union). The only excepted member is `unreadable`, enumerated as static-pin-only with rationale: it is a synthetic unreadable-record marker, never written via the `_write_json_atomic` chokepoint by any lifecycle or recovery flow. Stop Condition 3 applies if any other member is unobserved in its own domain.
- **G4 (after Task 4):** consistency test green; pyright introduced-count recorded as the measured delta (Task 4 Step 3 post − Task 2 Step 1 baseline, identical command/scope); `git diff` shows ZERO changes to `session_state.py`.
- **G5 (after Task 5):** workflow YAML parses; pyright step is `continue-on-error: true` with NO `|| true` swallow and captures `pyright --version`; existing pytest steps byte-for-byte unchanged.

**Commit boundaries (one coherent commit per task, surfaces not mixed):** T0 plan-as-authority · T1 source alias + pin test · T2 single annotation · T3 write-spy runtime gate · T4 layering-safe consistency test · T5 CI advisory · T6 docs/ADR/closeout.

**Verification command (bytecode-safe, per project CLAUDE.md):**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q
```

Ruff:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py
```

---

## File Structure

- `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition.md` — **Commit (Task 0).** This plan is the execution-control authority the ADR and closeout reference; it must be tracked before later tasks reference it.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py` — **Modify.** Add `Literal` import + two module-level aliases + partition docstring (Task 1); annotate `_persist_operation_and_transaction`'s `transaction_status` param only (Task 2). `ActiveWriteReservation.status` field annotation deferred (JSON-boundary; see Task 2 rationale).
- `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py` — **Create.** Pins alias membership + discriminating invariant (Task 1), the layering-safe `TERMINAL_TRANSACTION_STATUSES` consistency check (Task 4).
- `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py` — **Create.** The real gate: write-spy on `_write_json_atomic`, per-scenario partition assertion over the full write history, plus `test_observed_status_coverage` (Task 3).
- `.github/workflows/handoff-plugin-tests.yml` — **Modify.** Append one advisory, non-blocking pyright step (no `|| true`; captures version) after the existing pytest steps (Task 5).
- `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md` — **Modify.** Document the partition + invariant + tripwires after the layering-invariant paragraph (`:18`) (Task 6).
- `docs/decisions/0004-active-write-status-domain-partition.md` — **Create.** ADR in the established `000N-` shape (Task 6).
- `docs/superpowers/plans/2026-05-15-handoff-runtime-debt-elimination-review-followup.md` — **Modify.** Append the resolution note directly after the real anchor at `:578` (the `transaction_status: str` → `Literal`/`Enum` line) (Task 6).
- `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-closeout.md` — **Create (Task 6).** The closeout / evidence ledger. Records the Task 4 pyright probe verbatim (`pyright --version`, the probe exit status, the error count, and the introduced-count reasoning that feeds Stop Condition 2) plus the final all-gates result. This is the durable landing spot the prior revision referenced but never created (round-2 review Finding 3); `docs/superpowers/plans/` holds durable closeouts per repo CLAUDE.md.

`session_state.py`, `load_transactions.py`, `chain_state.py`: **NOT modified.** Deliberate (layering + scope control).

---

### Task 0: Branch and pin the plan as execution authority

**Files:**
- Commit: `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition.md`

Rationale (closes review Finding 4, second half): the ADR (Task 6) and the debt-plan closeout both cite this plan path as durable authority. If the plan is never committed, implementation history lands referencing a non-existent artifact. `docs/superpowers/plans/` is tracked execution-control state per repo CLAUDE.md, so committing it first is correct and policy-aligned.

**Executor note — Task 0 is already done.** The branch `feature/handoff-active-write-status-partition` was created and this plan committed during the 2026-05-16 plan-revision session (the same commit that landed the round-3 review revisions). Gate G0 is already satisfied. Begin execution at **Task 1**; do NOT re-run Step 1 — the branch exists and `git checkout -b` would fail. Steps 1–2 are retained as execution-control history.

- [x] **Step 1: Create the feature branch from `main`** — done 2026-05-16 (revision session)

```bash
git checkout main && git pull --ff-only && git checkout -b feature/handoff-active-write-status-partition
```

Expected: on a new branch `feature/handoff-active-write-status-partition`.

- [x] **Step 2: Commit this plan (Gate G0)** — done 2026-05-16 (revision session)

```bash
git add docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition.md
git commit -m "docs: add active-write status-domain partition execution plan

Execution-control authority for the PR #15 typing follow-up partition
slice; referenced by the Task 6 ADR and debt-plan closeout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

Expected: plan file tracked; `git status --short` no longer shows it as `??`.

---

### Task 1: Status-domain Literal aliases + partition docstring

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py` (typing import after `from pathlib import Path` at `:12`; new aliases after `class ActiveWriteError` at `:48`)
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py` (create)

- [ ] **Step 1: Create the failing test**

Create `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py`:

```python
from __future__ import annotations

from typing import get_args

import turbo_mode_handoff_runtime.active_writes as active_writes

# Source-grounded expected vocabularies (see plan "Source-Grounded Status
# Vocabulary"). Every member has a verified source site in active_writes.py:
# a write site, except the synthetic read-path "unreadable" record
# (constructed in _unreadable_active_write_record, never persisted).
EXPECTED_OPERATION_STATE_STATUSES = {
    "begun",
    "pending_before_write",
    "content-generated",
    "content_mismatch",
    "write-pending",
    "cleanup_failed",
    "committed",
    "abandoned",
    "reservation_expired",
    "reservation_conflict",
    "unreadable",
}
EXPECTED_TRANSACTION_STATUSES = {
    "pending_before_write",
    "content-generated",
    "content_mismatch",
    "write-pending",
    "cleanup_failed",
    "completed",
    "abandoned",
    "reservation_expired",
    "reservation_conflict",
}


def test_operation_state_status_alias_matches_source_vocabulary() -> None:
    members = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    assert members == EXPECTED_OPERATION_STATE_STATUSES


def test_transaction_status_alias_matches_source_vocabulary() -> None:
    members = set(get_args(active_writes.ActiveWriteTransactionStatus))
    assert members == EXPECTED_TRANSACTION_STATUSES


def test_discriminating_invariant_committed_is_operation_state_only() -> None:
    op = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    tx = set(get_args(active_writes.ActiveWriteTransactionStatus))
    assert "committed" in op and "committed" not in tx
    assert "completed" in tx and "completed" not in op
    assert {"begun", "unreadable"} <= op
    assert not ({"begun", "unreadable"} & tx)


def test_shared_statuses_are_exactly_the_documented_overlap() -> None:
    op = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    tx = set(get_args(active_writes.ActiveWriteTransactionStatus))
    assert op & tx == {
        "pending_before_write",
        "content-generated",
        "content_mismatch",
        "write-pending",
        "cleanup_failed",
        "abandoned",
        "reservation_expired",
        "reservation_conflict",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 \
  pytest tests/test_active_write_status_partition.py -q -p no:cacheprovider
```

Expected: FAIL — `AttributeError: module 'turbo_mode_handoff_runtime.active_writes' has no attribute 'ActiveWriteOperationStateStatus'`.

- [ ] **Step 3: Add the `Literal` import**

In `active_writes.py`, the stdlib import block ends at `:12` (`from pathlib import Path`). Add a typing import immediately after line 12 (before the blank line and the `from turbo_mode_handoff_runtime ...` block at `:14`), matching the `distill.py` convention:

```python
from pathlib import Path
from typing import Literal
```

- [ ] **Step 4: Add the aliases + partition docstring**

In `active_writes.py`, immediately after the `ActiveWriteError` class (ends at `:48` with `pass`) and before `DEFAULT_SLUGS` (`:51`), insert:

```python
# --- Active-write status-domain partition -------------------------------
#
# The active-write lifecycle persists TWO record kinds with DISTINCT status
# vocabularies:
#
#   * operation-state records  (.../active-writes/<project>/<run>.json)
#   * transaction records      (.../transactions/<txn>.json)
#
# Discriminating invariant (enforced by the write-spy lifecycle-matrix
# regression test, NOT by these annotations — the repo gates on
# ruff+pytest only): "committed" is an operation-state-only terminal;
# "completed" is a transaction-only terminal; "begun"/"unreadable" are
# operation-state-only. The two domains are NOT mergeable — a single
# unified status type would mis-model the lifecycle and reintroduce the
# PR #15 class of bug. Every member below is emitted by this module: each
# has a verified write site, EXCEPT the synthetic read-path "unreadable"
# record (built by _unreadable_active_write_record and returned by the
# read-only list_active_writes; never persisted via _write_json_atomic).
# See docs/superpowers/plans/2026-05-16-handoff-active-write-status-
# partition.md.
ActiveWriteOperationStateStatus = Literal[
    "begun",
    "pending_before_write",
    "content-generated",
    "content_mismatch",
    "write-pending",
    "cleanup_failed",
    "committed",
    "abandoned",
    "reservation_expired",
    "reservation_conflict",
    "unreadable",
]
ActiveWriteTransactionStatus = Literal[
    "pending_before_write",
    "content-generated",
    "content_mismatch",
    "write-pending",
    "cleanup_failed",
    "completed",
    "abandoned",
    "reservation_expired",
    "reservation_conflict",
]
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 \
  pytest tests/test_active_write_status_partition.py -q -p no:cacheprovider
```

Expected: PASS (4 passed).

- [ ] **Step 6: Run the full Handoff suite + ruff (Gate G1)**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py
```

Expected: full suite PASS (no regressions — aliases unused so far); ruff: `All checks passed!`.

- [ ] **Step 7: Commit**

```bash
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py
git commit -m "feat(handoff): add source-grounded active-write status-domain Literal aliases

Encodes the operation-state vs transaction status partition as two Literal
aliases with the discriminating invariant pinned by test. Named PR #15
out-of-scope typing follow-up, executed as the partition slice.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Apply the single low-noise annotation (`transaction_status` only)

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py` (`_persist_operation_and_transaction` signature, `transaction_status: str` at `:503`)

**Scope decision (closes review Finding 3):** the original plan also annotated `ActiveWriteReservation.status`. That is **deferred**. `ActiveWriteReservation` has a second construction site, `_reservation_from_payload()` (active_writes.py:311-345), which passes `status=str(payload["status"])` — a plain `str`. Annotating the field `ActiveWriteOperationStateStatus` (a `Literal`) would introduce a NEW pyright error at exactly the JSON deserialization boundary. The honest fix is a validating coercion at that boundary, which is behavior-changing and belongs to the broader payload-typing follow-up, not this minimal slice. Under the repo's ruff+pytest gate the field annotation has near-zero static value anyway (the runtime gate is Task 3). So Task 2 annotates only `transaction_status`, where every call site passes a string literal and pyright gains real value with zero new boundary noise.

- [ ] **Step 1: Capture the pre-annotation pyright baseline (feeds Stop Condition 2)**

Run this BEFORE editing `active_writes.py` for Task 2. At this point the Task 1 aliases are present and `transaction_status` is NOT yet annotated — this is the exact "pre-Task-2" state Stop Condition 2 measures against. Use the **identical command and scope** as the Task 4 Step 3 post-probe so the introduced count is a mechanically derivable delta, not an inference:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 --with pyright \
  sh -c 'pyright --version; pyright --stats turbo_mode_handoff_runtime/active_writes.py' \
  > /tmp/handoff-partition-pyright-baseline.txt 2>&1
echo "pyright baseline exit: $?"
tail -5 /tmp/handoff-partition-pyright-baseline.txt
```

The exit status is captured by a **separate** `echo` (not `| tail`-swallowed — same hardening as Task 4 Step 3). `/tmp/handoff-partition-pyright-baseline.txt` is execution-time evidence, NOT committed (consistent with the Task 4 Step 3 probe file; the Task 2 commit still contains only `active_writes.py`). Transcribe the `pyright --version` line, the `--stats` error/warning counts, and the `pyright baseline exit:` value into the Task 6 closeout "Pre-Task-2 baseline" slot. Stop Condition 2's introduced count = (Task 4 Step 3 post error count) − (this baseline error count), same command/scope.

- [ ] **Step 2: Annotate `_persist_operation_and_transaction`'s `transaction_status`**

In `active_writes.py`, the signature at `:498-505` has `    transaction_status: str,` at `:503`. Replace that one line:

```python
    transaction_status: ActiveWriteTransactionStatus,
```

Do NOT change the function body. Every existing call site passes a literal in `{"content-generated","write-pending","cleanup_failed","completed"}` — all valid `ActiveWriteTransactionStatus` members (verified: `:567`, `:604`, `:625`, `:642`).

- [ ] **Step 3: Run the full Handoff suite (behavior-preserving check)**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

Expected: PASS, identical count to Task 1 Step 6 (annotation erased at runtime; zero behavior change).

- [ ] **Step 4: Ruff + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py
git commit -m "feat(handoff): type _persist_operation_and_transaction.transaction_status

Behavior-preserving. Only the one site where the Literal has static value
without a JSON-boundary coercion (every call site passes a string literal).
ActiveWriteReservation.status field annotation deferred (see plan Task 2 /
ADR 0004): _reservation_from_payload is a str-typed deserialization
boundary that belongs to the broader payload-typing follow-up.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Write-spy lifecycle-matrix regression test (the real gate)

**Files:**
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py` (create)

This test, not the annotations, is what prevents the PR #15 bug class under the repo's ruff+pytest gate. It monkeypatches the single atomic-write chokepoint (`active_writes._write_json_atomic`, aliased from `storage_primitives.write_json_atomic` at active_writes.py:43; every op-state, transaction, transient, conflict and recovery write funnels through it) and asserts the partition on the **complete write history** of every reachable path — not just final file state. Coverage is asserted **per status domain** via `WriteSpy.observed_by_domain()`, not a domain-blind union (round-2 review Finding 2). Setups for the conflict, recovery, cleanup-failure, and auto-expire scenarios are copied from existing **named passing** tests in `tests/test_active_writes.py` (no invented setup); the previously-synthetic `_drive_cleanup_failed` now copies `test_write_active_handoff_persists_cleanup_failed_when_both_mechanisms_fail` so the genuine cleanup path runs (round-2 review Finding 4). The driver set covers **every** `_write_json_atomic` status write site, including recovery-success and begin-time auto-expire (round-2 review Finding 1); the only status not driven through the chokepoint is the synthetic `unreadable` record, which is never written via `_write_json_atomic` by any flow.

- [ ] **Step 1: Create the lifecycle-matrix test**

Create `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py`:

```python
"""Write-spy lifecycle-matrix gate for the active-write status-domain partition.

Spies the single atomic-write chokepoint (active_writes._write_json_atomic)
and asserts the discriminating invariant on EVERY write (transients
included), for every reachable lifecycle path. This is the runtime
enforcement of the partition (the Literal aliases have no teeth under the
repo's ruff+pytest gate).

Tripwire (Stop Condition 1): if any write puts 'completed' into a
.../active-writes/ path, or 'committed'/'begun'/'unreadable' into a
.../transactions/ path, the source-domain model is falsified -- STOP.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import get_args

import pytest
import turbo_mode_handoff_runtime.active_writes as active_writes

OP_MEMBERS = set(get_args(active_writes.ActiveWriteOperationStateStatus))
TX_MEMBERS = set(get_args(active_writes.ActiveWriteTransactionStatus))
CREATED_AT = "2026-05-13T16:45:00Z"

# Runtime-reachable members. Every member EXCEPT operation-state
# 'unreadable' is produced by some scenario below. 'unreadable' is the
# synthetic unreadable-record marker (active_writes.py:1104); it is never
# emitted by a normal lifecycle or recovery flow, so it is intentionally
# static-pin-only (Task 1) and excluded here (Gate G3 rationale).
RUNTIME_OP_MEMBERS = OP_MEMBERS - {"unreadable"}
RUNTIME_TX_MEMBERS = set(TX_MEMBERS)


class WriteSpy:
    """Records (domain, status) for every _write_json_atomic call and
    delegates to the real writer so behavior is unchanged."""

    def __init__(self) -> None:
        self._real = active_writes._write_json_atomic
        self.events: list[tuple[str, object]] = []

    def __call__(self, path: Path, payload: dict[str, object]) -> None:
        parts = Path(path).parts
        if "transactions" in parts:
            domain = "tx"
        elif "active-writes" in parts:
            domain = "op"
        else:
            domain = "other"
        self.events.append((domain, payload.get("status")))
        self._real(path, payload)

    def statuses(self) -> set[object]:
        return {status for _, status in self.events}

    def observed_by_domain(self) -> dict[str, set[object]]:
        """Statuses observed, bucketed by the file domain they were
        written to. The coverage gate (review Finding 2) must check op
        members against op-domain writes and tx members against tx-domain
        writes -- a domain-blind union lets a shared status seen in only
        one domain mask a per-domain regression in the other."""
        by_domain: dict[str, set[object]] = {"op": set(), "tx": set()}
        for domain, status in self.events:
            if domain in by_domain:
                by_domain[domain].add(status)
        return by_domain

    def assert_partitioned(self, scenario: str) -> None:
        for domain, status in self.events:
            if domain == "op":
                assert status in OP_MEMBERS, (
                    f"{scenario}: op write status {status!r} not in op alias"
                )
                assert status != "completed", (
                    f"{scenario}: TRIPWIRE 'completed' written to operation-state file"
                )
            elif domain == "tx":
                assert status in TX_MEMBERS, (
                    f"{scenario}: tx write status {status!r} not in tx alias"
                )
                assert status not in {"committed", "begun", "unreadable"}, (
                    f"{scenario}: TRIPWIRE {status!r} written to transaction file"
                )


def _install_spy(monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = WriteSpy()
    monkeypatch.setattr(active_writes, "_write_json_atomic", spy)
    return spy


def _begin(tmp_path: Path, *, slug: str, lease_seconds: int = 1800):
    return active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug=slug,
        created_at=CREATED_AT,
        lease_seconds=lease_seconds,
    )


def _read(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- scenario drivers (each returns its WriteSpy) -----------------------


def _drive_begin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="begin")
    assert _read(res.operation_state_path)["status"] == "begun"
    assert _read(res.transaction_path)["status"] == "pending_before_write"
    return spy


def _drive_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="success")
    content = "body"
    active_writes.write_active_handoff(
        tmp_path,
        operation_state_path=res.operation_state_path,
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    assert _read(res.operation_state_path)["status"] == "committed"
    assert _read(res.transaction_path)["status"] == "completed"
    # The transient window (content-generated -> write-pending) MUST have
    # been written on both domains and MUST satisfy the partition.
    assert "content-generated" in spy.statuses()
    assert "write-pending" in spy.statuses()
    return spy


def _drive_abandon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="abandon")
    active_writes.abandon_active_write(
        tmp_path,
        operation_state_path=res.operation_state_path,
        reason="test",
    )
    assert _read(res.operation_state_path)["status"] == "abandoned"
    assert _read(res.transaction_path)["status"] == "abandoned"
    return spy


def _drive_reservation_expired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="expired", lease_seconds=0)
    content = "body"
    with pytest.raises(active_writes.ActiveWriteError, match="reservation expired"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    assert _read(res.operation_state_path)["status"] == "reservation_expired"
    assert _read(res.transaction_path)["status"] == "reservation_expired"
    return spy


def _drive_content_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="mismatch")
    res.allocated_active_path.parent.mkdir(parents=True, exist_ok=True)
    res.allocated_active_path.write_text("OTHER CONTENT", encoding="utf-8")
    content = "body"
    with pytest.raises(active_writes.ActiveWriteError, match="content mismatch"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    # Write-path mismatch persists ONLY operation state (active_writes.py:580);
    # the transaction stays at its last value, content-generated (:567).
    assert _read(res.operation_state_path)["status"] == "content_mismatch"
    assert _read(res.transaction_path)["status"] == "content-generated"
    return spy


def _drive_conflict_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_rejects_changed_state_snapshot_before_output_write
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="state-conflict")
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    conflicting_state = state_dir / "handoff-demo-conflict.json"
    conflicting_state.write_text(
        json.dumps(
            {
                "state_path": str(conflicting_state),
                "project": "demo",
                "resume_token": "conflict",
                "archive_path": "/tmp/other.md",
                "created_at": "2026-05-13T16:01:00Z",
            }
        ),
        encoding="utf-8",
    )
    content = "body"
    with pytest.raises(active_writes.ActiveWriteError, match="state snapshot changed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    updated = _read(res.operation_state_path)
    assert updated["status"] == "reservation_conflict"
    assert updated["conflict_reason"] == "state_snapshot_changed"
    assert _read(res.transaction_path)["status"] == "reservation_conflict"
    return spy


def _drive_conflict_watermark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_rejects_changed_transaction_watermark_before_output_write
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="transaction-conflict")
    conflict_transaction = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "transactions"
        / "external-conflict.json"
    )
    conflict_transaction.write_text(
        json.dumps(
            {
                "transaction_id": "external-conflict",
                "operation": "load",
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )
    content = "body"
    with pytest.raises(
        active_writes.ActiveWriteError, match="transaction watermark changed"
    ):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    updated = _read(res.operation_state_path)
    assert updated["status"] == "reservation_conflict"
    assert updated["conflict_reason"] == "transaction_watermark_changed"
    assert _read(res.transaction_path)["status"] == "reservation_conflict"
    return spy


def _drive_cleanup_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_persists_cleanup_failed_when_both_mechanisms_fail
    # Drives the REAL cleanup branch (active_writes.py:607-628 via
    # _clear_snapshotted_primary_state -> _storage_primitives.safe_delete)
    # by failing BOTH delete mechanisms -- it does NOT monkeypatch the
    # cleanup helper itself, so the genuine persistence path runs (review
    # Finding 4: prefer the copied real setup over synthetic injection).
    spy = _install_spy(monkeypatch)
    archive = tmp_path / ".codex" / "handoffs" / "archive" / "previous.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("---\ntitle: Previous\n---\n", encoding="utf-8")
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-resume.json"
    state_path.write_text(
        json.dumps(
            {
                "state_path": str(state_path),
                "project": "demo",
                "resume_token": "resume",
                "archive_path": str(archive),
                "created_at": "2026-05-13T16:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    res = _begin(tmp_path, slug="cleanup-both-fail")
    content = "body"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    original_subprocess_run = active_writes._storage_primitives.subprocess.run

    def fail_trash(*args: object, **kwargs: object) -> object:
        if not args or not isinstance(args[0], list) or args[0][:1] != ["trash"]:
            return original_subprocess_run(*args, **kwargs)
        raise FileNotFoundError("trash")

    original_unlink = Path.unlink

    def fail_unlink(self: Path, *a: object, **k: object) -> None:
        if self == state_path:
            raise PermissionError("unlink denied")
        return original_unlink(self, *a, **k)

    monkeypatch.setattr(
        active_writes._storage_primitives.subprocess, "run", fail_trash
    )
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(active_writes.ActiveWriteError, match="state cleanup failed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )
    assert _read(res.operation_state_path)["status"] == "cleanup_failed"
    assert _read(res.transaction_path)["status"] == "cleanup_failed"
    return spy


def _drive_recover_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_active_write_transaction_recover_records_pending_before_write
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="recover-pending")
    state = _read(res.operation_state_path)
    state["status"] = "written_not_confirmed"
    state["content_hash"] = hashlib.sha256(b"missing output").hexdigest()
    state["output_sha256"] = state["content_hash"]
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=res.operation_state_path,
    )
    assert recovered["status"] == "pending_before_write"
    assert _read(res.transaction_path)["status"] == "pending_before_write"
    return spy


def _drive_recover_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_active_write_transaction_recover_records_content_mismatch
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="recover-mismatch")
    expected = "---\ntitle: Expected\n---\n\n# Expected\n"
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    res.allocated_active_path.write_text(
        "---\ntitle: Different\n---\n\n# Different\n", encoding="utf-8"
    )
    state = _read(res.operation_state_path)
    state["status"] = "written_not_confirmed"
    state["content_hash"] = expected_hash
    state["output_sha256"] = expected_hash
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    with pytest.raises(active_writes.ActiveWriteError, match="content mismatch"):
        active_writes.recover_active_write_transaction(
            tmp_path,
            operation_state_path=res.operation_state_path,
        )
    assert _read(res.operation_state_path)["status"] == "content_mismatch"
    assert _read(res.transaction_path)["status"] == "content_mismatch"
    return spy


def _drive_recover_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_active_write_transaction_recover_commits_verified_written_output
    # (direct-API form, matching the other drivers). This is the ONLY
    # driver that exercises the recovery-success write site
    # (active_writes.py:804 op->'committed', :811 tx->'completed') -- the
    # single most dangerous site to leave unguarded because it writes BOTH
    # discriminating terminals. Its absence was the blocking review
    # finding; the plan's own vocabulary table had admitted "recover happy
    # not driven".
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="recover-success")
    content = "---\ntitle: Recover\n---\n\n# Written\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    res.allocated_active_path.write_text(content, encoding="utf-8")
    state = _read(res.operation_state_path)
    state["status"] = "written_not_confirmed"
    state["content_hash"] = content_hash
    state["output_sha256"] = content_hash
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=res.operation_state_path,
    )
    assert recovered["status"] == "committed"
    assert _read(res.operation_state_path)["status"] == "committed"
    assert _read(res.transaction_path)["status"] == "completed"
    return spy


def _drive_auto_expire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_begin_active_write_auto_expires_stale_pre_output_reservation
    # This is the ONLY driver that exercises the begin-time auto-expire
    # write site (active_writes.py:402 op, :404 tx via
    # _auto_expire_pre_output_reservation) -- distinct from the write-path
    # expiry that _drive_reservation_expired covers. A second compatible
    # begin auto-expires the stale pre-output reservation.
    spy = _install_spy(monkeypatch)
    first = _begin(tmp_path, slug="auto-expire", lease_seconds=-1)
    active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="auto-expire-replacement",
        created_at="2026-05-13T16:46:00Z",
    )
    assert _read(first.operation_state_path)["status"] == "reservation_expired"
    assert _read(first.transaction_path)["status"] == "reservation_expired"
    return spy


ALL_DRIVERS = (
    _drive_begin,
    _drive_success,
    _drive_abandon,
    _drive_reservation_expired,
    _drive_auto_expire,
    _drive_content_mismatch,
    _drive_conflict_snapshot,
    _drive_conflict_watermark,
    _drive_cleanup_failed,
    _drive_recover_pending,
    _drive_recover_mismatch,
    _drive_recover_success,
)


@pytest.mark.parametrize("driver", ALL_DRIVERS, ids=lambda d: d.__name__)
def test_scenario_partition_holds_for_every_write(
    driver, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = driver(tmp_path, monkeypatch)
    assert spy.events, f"{driver.__name__}: spy captured no writes"
    spy.assert_partitioned(driver.__name__)


def test_observed_status_coverage(tmp_path: Path) -> None:
    """Gate G3 / Stop Condition 3: every runtime-reachable alias member
    must be observed BY ITS OWN DOMAIN -- an operation-state member in an
    operation-state (.../active-writes/) write, a transaction member in a
    transaction (.../transactions/) write. A domain-blind union (the prior
    implementation) let a shared status observed in only one domain mask a
    per-domain regression in the other (review Finding 2). Each driver runs
    in its OWN MonkeyPatch context so a fault-injection patch (e.g.
    _drive_cleanup_failed's subprocess/Path.unlink overrides) cannot leak
    into a later driver and silently corrupt coverage. 'unreadable' is the
    only deliberately-excluded member (synthetic record, never written via
    the atomic-write chokepoint by any lifecycle flow)."""
    observed: dict[str, set[object]] = {"op": set(), "tx": set()}
    for index, driver in enumerate(ALL_DRIVERS):
        scenario_dir = tmp_path / f"s{index}"
        scenario_dir.mkdir()
        with pytest.MonkeyPatch.context() as mp:
            spy = driver(scenario_dir, mp)
            spy.assert_partitioned(driver.__name__)
            for domain, statuses in spy.observed_by_domain().items():
                observed[domain] |= statuses
    missing_op = RUNTIME_OP_MEMBERS - observed["op"]
    missing_tx = RUNTIME_TX_MEMBERS - observed["tx"]
    assert not missing_op, (
        f"operation-state members never observed in an operation-state "
        f"write: {missing_op}"
    )
    assert not missing_tx, (
        f"transaction members never observed in a transaction write: "
        f"{missing_tx}"
    )
    assert "unreadable" not in (observed["op"] | observed["tx"]), (
        "'unreadable' was observed in a lifecycle write — the vocabulary "
        "model's static-pin-only assumption is wrong; revisit Gate G3."
    )
```

- [ ] **Step 2: Run it to verify all scenarios + coverage pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 \
  pytest tests/test_active_write_lifecycle_matrix.py -q -p no:cacheprovider
```

Expected: 13 passed (12 parametrized scenarios + `test_observed_status_coverage`). If a scenario's final-status assertion fails, the live lifecycle diverges from the source-grounded vocabulary table — apply Stop Condition 1 (do NOT "fix" the test to pass; investigate the lifecycle). If `test_observed_status_coverage` reports an unobserved member in its own domain, apply Stop Condition 3.

- [ ] **Step 3: Full suite (Gate G3) + ruff + commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py
git add plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py
git commit -m "test(handoff): write-spy lifecycle-matrix gate for the status partition

Spies the single atomic-write chokepoint and asserts the
committed(op-only)/completed(tx-only) invariant on EVERY write (transients
included) across 12 lifecycle/recovery paths (incl. recovery-success and
begin-time auto-expire), plus a per-domain observed-coverage gate. This is
the real gate under ruff+pytest; the Literal aliases are the
static-analysis handle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Layering-safe `TERMINAL_TRANSACTION_STATUSES` consistency check + pyright probe

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py` (append)

`session_state.py:51` defines `TERMINAL_TRANSACTION_STATUSES = frozenset({"committed","completed","abandoned","reservation_expired"})`. The documented layering trap (ARCHITECTURE.md:18: `... → chain_state → active_writes → session_state ...`) forbids importing the alias from `active_writes` into `session_state` at module level. Resolution: pin consistency in the TEST layer (which already imports both modules), with NO source change to `session_state.py`.

Note: `TERMINAL_TRANSACTION_STATUSES` legitimately contains `committed` because it is the *cross-domain TTL-prune* terminal **allow-list** (write-transaction terminal `{committed, abandoned, reservation_expired}` ∪ load-transaction terminal `{completed, abandoned}` = `{committed, completed, abandoned, reservation_expired}`; see the source comment at `session_state.py:46-53`), not a pure transaction-status set. It is load-bearing: silently dropping a member disables TTL pruning for that terminal status. A subset-only check (`terminal <= …`) would let such an omission pass. So the test pins the set **exactly** (completeness, not just "no unknowns") AND documents the partition linkage: every member is in (`ActiveWriteTransactionStatus` ∪ `ActiveWriteOperationStateStatus`), and every non-`committed` member is a valid transaction status (`committed` is the op-only cross-domain member).

- [ ] **Step 1: Append the consistency test**

Append to `plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py`:

```python
# Source-grounded from session_state.py:51-53 (write-transaction terminal
# {committed, abandoned, reservation_expired} ∪ load-transaction terminal
# {completed, abandoned}). This is a TTL-prune ALLOW-LIST: a subset-only
# check would let a future edit silently drop a required terminal (e.g.
# 'completed') and still pass, disabling pruning for it. Pin it EXACTLY.
EXPECTED_TERMINAL_TRANSACTION_STATUSES = {
    "committed",
    "completed",
    "abandoned",
    "reservation_expired",
}


def test_terminal_transaction_statuses_align_with_partition() -> None:
    """session_state.TERMINAL_TRANSACTION_STATUSES is the cross-domain
    TTL-prune terminal allow-list. It is pinned EXACTLY (completeness, not
    just 'no unknowns' — dropping a required terminal silently disables its
    pruning), and its partition linkage is documented. Enforced in the test
    layer to avoid a session_state -> active_writes module-level import
    (documented layering trap, ARCHITECTURE.md:18)."""
    import turbo_mode_handoff_runtime.session_state as session_state

    terminal = set(session_state.TERMINAL_TRANSACTION_STATUSES)
    op = set(get_args(active_writes.ActiveWriteOperationStateStatus))
    tx = set(get_args(active_writes.ActiveWriteTransactionStatus))

    # Exact pin: catches BOTH unknown additions AND silent omissions.
    assert terminal == EXPECTED_TERMINAL_TRANSACTION_STATUSES, (
        f"TERMINAL_TRANSACTION_STATUSES drifted from the source-grounded "
        f"allow-list: missing={EXPECTED_TERMINAL_TRANSACTION_STATUSES - terminal} "
        f"unexpected={terminal - EXPECTED_TERMINAL_TRANSACTION_STATUSES}"
    )
    # Partition linkage (diagnostic specificity + documents WHY each member
    # is allowed): every member is a known status in some domain; every
    # non-'committed' member is a valid transaction status ('committed' is
    # the op-only cross-domain member).
    assert terminal <= (op | tx), f"unknown terminal status(es): {terminal - (op | tx)}"
    assert (terminal - {"committed"}) <= tx, (
        f"non-'committed' terminals not in transaction alias: "
        f"{(terminal - {'committed'}) - tx}"
    )
```

- [ ] **Step 2: Run it (passes immediately — pins existing alignment)**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 \
  pytest tests/test_active_write_status_partition.py -q -p no:cacheprovider
```

Expected: PASS (5 passed). Regression tripwire: any future divergence between `session_state`'s prune set and the source-grounded allow-list fails here — including a silently dropped required terminal (e.g. `completed`), which the prior subset-only check would have missed.

- [ ] **Step 3: Record the pyright probe (feeds Stop Condition 2)**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 --with pyright \
  sh -c 'pyright --version; pyright --stats turbo_mode_handoff_runtime/active_writes.py' \
  > /tmp/handoff-partition-pyright.txt 2>&1
echo "pyright probe exit: $?"
tail -5 /tmp/handoff-partition-pyright.txt
```

This post-annotation probe uses the **identical command and scope** as the Task 2 Step 1 pre-annotation baseline (`pyright --stats turbo_mode_handoff_runtime/active_writes.py` — the single annotated file, the annotation's blast radius). The output is redirected to a file and the `uv run` exit status is captured by a **separate** `echo` (no `| tail` swallowing it — round-2 review Finding 3). Transcribe the full `/tmp/handoff-partition-pyright.txt` (the `pyright --version` line, the `--stats` error/warning counts) and the printed `pyright probe exit:` value into the Task 6 closeout artifact `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-closeout.md` (created and committed in Task 6 Step 4 / Step 6). **Apply Stop Condition 2 as a measured delta:** introduced count = (this probe's `--stats` error count) − (the Task 2 Step 1 `/tmp/handoff-partition-pyright-baseline.txt` error count). The a-priori expectation is 0 (every `transaction_status` call site passes a string literal), but the closeout MUST record the actual measured delta, not the expectation. If the delta is >~3 new suppressions/errors, halt and drop Task 2 per the plan, and record that decision in the closeout. Note: the Task 5 CI step deliberately runs the broader package-wide scope (`turbo_mode_handoff_runtime/`); that count is NOT the SC2 measurement and is never differenced against this file-scoped pair.

- [ ] **Step 4: Confirm zero `session_state.py` change (Gate G4) + commit**

```bash
git diff --stat -- plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py
```

Expected: EMPTY output. Then:

```bash
git add plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_status_partition.py
git commit -m "test(handoff): pin TERMINAL_TRANSACTION_STATUSES to typed status partition

Test-layer consistency check; no session_state -> active_writes module
import (preserves documented layering, ARCHITECTURE.md:18).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Advisory (non-blocking) pyright CI surface

**Files:**
- Modify: `.github/workflows/handoff-plugin-tests.yml` (append a step after the existing final `Run Handoff tests` step)

**Fix vs. original (closes review Finding 5):** `continue-on-error: true` *alone* makes a step non-blocking while preserving its real exit status and logs in the GitHub UI. The original plan's extra `|| true` additionally swallowed the exit code, erasing the distinction between "pyright ran and found type issues" and "pyright/uv failed to install or invoke" — destroying the advisory signal. The `|| true` is removed; `pyright --version` is captured so the advisory is legible and diffable.

- [ ] **Step 1: Append the advisory pyright step**

The current final step in `.github/workflows/handoff-plugin-tests.yml` is `Run Handoff tests`. Append this as a new list item at the same indentation as the other `- name:` steps:

```yaml
      - name: Advisory pyright (non-blocking)
        continue-on-error: true
        run: |
          PYTHONDONTWRITEBYTECODE=1 \
          PYTHONPYCACHEPREFIX="${RUNNER_TEMP}/codex-tool-dev-pycache" \
          uv run --directory plugins/turbo-mode/handoff/1.6.0 --with pyright \
          sh -c 'pyright --version && pyright --stats turbo_mode_handoff_runtime/'
```

`continue-on-error: true` makes this informational only — a non-zero exit (type findings OR setup failure) cannot fail the matrix, but the real status and logs remain visible in the UI. Intentionally unpinned (`--with pyright`) because it is advisory; pin a specific pyright version only if/when the project decides to make it blocking (dialogue evidence (iii) upgrade signal).

- [ ] **Step 2: Validate the workflow YAML parses**

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 python -c \
  "import yaml,sys; yaml.safe_load(open(sys.argv[1])); print('YAML OK')" \
  "$PWD/.github/workflows/handoff-plugin-tests.yml"
```

Expected: `YAML OK`. (pyyaml is a Handoff dependency, so the `uv run --directory` form is reliable; a bare `python3` may lack `yaml`.)

- [ ] **Step 3: Confirm the existing pytest steps are byte-for-byte unchanged (Gate G5)**

```bash
git diff -- .github/workflows/handoff-plugin-tests.yml
```

Expected: diff shows ONLY the appended `Advisory pyright` step; `Collect Handoff tests` and `Run Handoff tests` untouched; the appended step has `continue-on-error: true` and NO `|| true`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/handoff-plugin-tests.yml
git commit -m "ci(handoff): add advisory non-blocking pyright step

Informational only (continue-on-error; NO || true so a setup failure is
still visible). Captures pyright --version. Not a gate; upgrade to
blocking only per the documented upgrade signal.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Documentation, ADR, and follow-up closeout

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md` (after the layering-invariant paragraph at `:18`)
- Create: `docs/decisions/0004-active-write-status-domain-partition.md`
- Modify: `docs/superpowers/plans/2026-05-15-handoff-runtime-debt-elimination-review-followup.md` (after the anchor at `:578`)
- Create: `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-closeout.md` (the evidence ledger — pyright probe + final gate results)

- [ ] **Step 1: Document the partition in ARCHITECTURE.md**

In `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md`, the layering-invariant paragraph is at `:18` (begins "Layering invariant: imports flow one way ..."). Insert this block immediately after that paragraph:

```markdown
### Active-write status-domain partition

The active-write lifecycle persists two record kinds with **distinct,
non-mergeable** status vocabularies, typed in `active_writes.py` as
`ActiveWriteOperationStateStatus` and `ActiveWriteTransactionStatus`:

- **operation-state records** (`.../active-writes/<project>/<run>.json`):
  terminal `committed`; also exclusively `begun`, `unreadable`.
- **transaction records** (`.../transactions/<txn>.json`): terminal
  `completed`.

`committed` (operation-state) and `completed` (transaction) are the
discriminating pair. Merging the two vocabularies would re-introduce the
PR #15 prune-bug class. The invariant is enforced at runtime by
`tests/test_active_write_lifecycle_matrix.py`, which spies the single
atomic-write chokepoint and asserts the partition on every write
(transients included) across the lifecycle/recovery matrix; the Literal
aliases are the static-analysis handle and an advisory non-blocking
pyright CI step is the cheap precision surface.
`session_state.TERMINAL_TRANSACTION_STATUSES` is a cross-domain TTL-prune
terminal set, kept aligned via a test-layer check (no `session_state` →
`active_writes` module import — that would invert this layering).

Tripwires: (i) any write putting `completed` into an operation-state file
or `committed`/`begun`/`unreadable` into a transaction file falsifies the
model — stop and triage. (ii) >~3 new pyright suppressions to land the
`transaction_status` annotation → drop to runtime-gate-only + tracked
ticket. (iii) Make pyright blocking only if a low-noise prototype holds
and status/payload bugs recur beyond PR #15.
```

- [ ] **Step 2: Write the ADR (established `000N-` shape)**

`docs/decisions/` uses sequentially-numbered records (`0001-`, `0002-`, `0003-`) with the shape `# ADR 000N — <title>` / `- **Status:**` / `- **Scope:**` / `## Context` / `## Decision` / `## Consequences`. The next number is `0004`. This repo-local convention overrides the generic `YYYY-MM-DD-<slug>.md` default (repo patterns outrank skill/tooling defaults per repo CLAUDE.md). Create `docs/decisions/0004-active-write-status-domain-partition.md`:

```markdown
# ADR 0004 — Active-write status-domain partition (not a full TypedDict pass)

- **Status:** Accepted
- **Scope:** `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py`,
  `plugins/turbo-mode/handoff/1.6.0/tests/`,
  `.github/workflows/handoff-plugin-tests.yml`

## Context

PR #15 named, and deliberately deferred, an out-of-scope follow-up: a
pervasive runtime-correct `dict[str, object]` typing pattern. A
making-recommendations evaluation plus a Codex dialogue (convergence,
4/6 turns) reframed the deliverable. A first adversarial review found that
the active-write lifecycle persists two record kinds whose status
vocabularies are NOT mergeable, and that a final-state test cannot prove
the partition. A second adversarial review of the revised plan found the
runtime gate still under-covered: it omitted the recovery-success and
begin-time auto-expire write sites, and its coverage check was
domain-blind (a shared status seen in one domain could mask a per-domain
regression in the other). A third adversarial review hardened the
evidence gates: Stop Condition 2's introduced-pyright count was inferred
rather than measured (no pre-Task-2 baseline), the
`TERMINAL_TRANSACTION_STATUSES` consistency check was subset-only (a
dropped required terminal would pass), and `unreadable` was documented as
a persisted write-site status when it is synthetic read-path return data.
All three rounds are resolved in the current plan (see its Self-Review).

## Decision

Execute the follow-up as an **incremental status-domain partition**, not
the broad `dict[str, object]` → TypedDict pass:

1. Two source-grounded `Literal` aliases in `active_writes.py`.
2. A write-spy lifecycle-matrix pytest as the real regression gate — it
   asserts the `committed`(op-only)/`completed`(tx-only) invariant on
   every write, transients included (the repo gates on ruff+pytest;
   Literal annotations have no runtime teeth).
3. Annotate only `_persist_operation_and_transaction.transaction_status`
   (string-literal call sites; zero new boundary noise). The
   `ActiveWriteReservation.status` field annotation is deferred: its
   second construction site `_reservation_from_payload` is a `str`-typed
   JSON deserialization boundary whose honest fix is a validating
   coercion — broader-follow-up scope.
4. An advisory, non-blocking pyright CI step (no `|| true`).
5. Layering-safe test-layer consistency for the `session_state` prune set.

Rejected: a full TypedDict pass (no static gate to justify the churn;
the dialogue verified a careless unification would *introduce* a bug —
the two status domains are not mergeable). Track-only/defer became weak
once a CI surface was found to already exist, making the enforcement gap
cheap to close.

## Consequences

- The partition (two domains) is documented and runtime-enforced on every
  `_write_json_atomic` status write site — all 12 lifecycle/recovery
  drivers (incl. recovery-success and begin-time auto-expire), with
  coverage asserted per status domain, not as a domain-blind union.
- pyright remains advisory; broad payload typing AND the
  `ActiveWriteReservation.status` validating-coercion remain the named
  next follow-up if the upgrade signal fires.
- Residual risk: an advisory CI job can rot if unowned. `unreadable` is
  the one status pinned statically but not runtime-observed — it is a
  synthetic in-memory record from `_unreadable_active_write_record`, never
  written through the atomic-write chokepoint by any flow, so it is
  correctly excluded from the coverage gate.
```

- [ ] **Step 3: Close the named follow-up at the real anchor**

The PR #15 typing follow-up anchor is **not** in `2026-05-15-handoff-runtime-debt-elimination.md`. It is in `docs/superpowers/plans/2026-05-15-handoff-runtime-debt-elimination-review-followup.md` at `:578`, the line beginning:

> `- transaction_status: str` → `Literal`/`Enum` (bundled with the PR's already-named `dict[str, object]` typing follow-up; ...)

Append this resolution note as a new bullet/paragraph directly after that line (do not delete the original — it is execution-control history):

```markdown
> **Resolved 2026-05-16 (partition slice):** Addressed as an incremental
> status-domain partition, not the broad TypedDict pass. `transaction_status`
> is now typed `ActiveWriteTransactionStatus`; the partition is runtime-
> enforced by `tests/test_active_write_lifecycle_matrix.py`. See
> `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition.md`
> and ADR `docs/decisions/0004-active-write-status-domain-partition.md`.
> Broad `dict[str, object]` payload typing and the
> `ActiveWriteReservation.status` validating-coercion at
> `_reservation_from_payload` remain the named next follow-up, gated by the
> documented pyright upgrade signal.
```

- [ ] **Step 4: Write the closeout / evidence ledger**

Create `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-closeout.md`. The bracketed `<…>` slots are **execution-time evidence captures** (filled when the steps run), not authoring placeholders — distinct from the spec-placeholder ban in Self-Review §2:

```markdown
# Closeout — Active-write status-domain partition (2026-05-16)

Plan: `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition.md`
ADR: `docs/decisions/0004-active-write-status-domain-partition.md`
Branch: `feature/handoff-active-write-status-partition`

## Pyright probe — Stop Condition 2 measured delta (scope: `turbo_mode_handoff_runtime/active_writes.py`)

The pre-Task-2 baseline (Task 2 Step 1) and the post-annotation probe (Task 4 Step 3) use the **identical command and scope**. Introduced = post error count − baseline error count (a measured delta, not the a-priori expectation).

Pre-Task-2 baseline — `/tmp/handoff-partition-pyright-baseline.txt`:
- `pyright --version`: `<captured version>`
- Baseline exit status (`pyright baseline exit:` line): `<int>`
- `--stats` error / warning counts: `<errors>` / `<warnings>`

Post-annotation probe — `/tmp/handoff-partition-pyright.txt`:
- `pyright --version`: `<captured version>`
- Probe exit status (`pyright probe exit:` line): `<int>`
- `--stats` error / warning counts: `<errors>` / `<warnings>`

- **Introduced delta** (post errors − baseline errors): `<n>` new suppressions/errors
- Stop Condition 2 verdict: `<PASS (delta ≤ ~3, Task 2 kept) | DROP Task 2 (delta > ~3) — reason>`
- CI-surface context — NOT the SC2 measurement (scope `turbo_mode_handoff_runtime/`, deliberately broader, never differenced against the file-scoped pair): `<package-wide error count if captured, else "n/a — see CI advisory logs">`
- Raw outputs transcribed below (baseline first, then post-probe).

```
<paste the full /tmp/handoff-partition-pyright-baseline.txt here (pre-Task-2)>
```

```
<paste the full /tmp/handoff-partition-pyright.txt here (post-annotation)>
```

## Gate results

- G0 plan committed: `<commit sha>`
- G1 alias + pin test green; full Handoff suite green; ruff clean: `<pass/fail + counts>`
- G2 pre-Task-2 pyright baseline captured (same scope as Task 4 probe, BEFORE the annotation) + annotation behavior-preserving (suite count identical to G1): `<pass/fail>`
- G3 all 12 lifecycle scenarios + per-domain `test_observed_status_coverage` green: `<13 passed?>`
- G4 consistency test green; pyright introduced-count recorded as the measured delta (see Pyright probe section); `git diff` shows ZERO `session_state.py` change: `<pass/fail>`
- G5 workflow YAML parses; pyright step `continue-on-error: true`, no `|| true`: `<pass/fail>`

## Stop conditions

- SC1 domain-model tripwire: `<not tripped | tripped — detail>`
- SC2 noise threshold: `<see Pyright probe verdict>`
- SC3 per-domain coverage gap: `<not tripped | tripped — missing members>`
- SC4 repo-level cleanup/residue: `<none | detail>`
```

- [ ] **Step 5: Final full-suite verification (all gates) + residue check**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
git status --short
git diff --check
```

Expected: full suite PASS; `git status` shows only intended files; `git diff --check` clean. If any `__pycache__`/`.pytest_cache`/`.ruff_cache`/`.DS_Store` appeared under plugin source, remove with `trash <path>` and note it.

- [ ] **Step 6: Commit**

```bash
git add plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md \
  docs/decisions/0004-active-write-status-domain-partition.md \
  docs/superpowers/plans/2026-05-15-handoff-runtime-debt-elimination-review-followup.md \
  docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-closeout.md
git commit -m "docs(handoff): document status-domain partition + ADR 0004; close PR #15 follow-up

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage** (against the Codex dialogue synthesis + the adversarial review findings):

| Requirement | Task | Notes |
|---|---|---|
| Two distinct Literal aliases, `completed` tx-only / `committed` op-only | T1 | source-grounded; includes `unreadable`/`begun` op-only |
| Annotate `_persist_operation_and_transaction.transaction_status` | T2 | `ActiveWriteReservation.status` deferred — review Finding 3 |
| Lifecycle-matrix runtime gate reading partition state | T3 | write-spy on `_write_json_atomic`; every write asserted — review Finding 2 |
| Conflict scenarios use real mechanism (not 2nd `begin`) | T3 | copied from passing `test_active_writes.py` tests — review Finding 1 |
| Observed-coverage gate over the full vocabulary | T3 `test_observed_status_coverage` + Stop Condition 3 | `unreadable` enumerated as static-pin-only; per-driver `MonkeyPatch.context()` isolation so fault patches can't leak |
| Advisory pyright CI, non-blocking, signal-preserving | T5 | no `|| true`; captures version — review Finding 5 |
| Respect layering trap (no session_state→active_writes import) | T4 | test-layer check; G4 asserts zero session_state change |
| Stop tripwire (completed in op / committed in tx) | T3 `WriteSpy.assert_partitioned` + Stop Condition 1 | now write-granular |
| Noise-threshold tripwire (measured delta) | T2 Step 1 baseline + T4 Step 3 post + Stop Condition 2 | introduced = post − baseline, identical scope; expected 0 but measured, not inferred |
| Plan committed as durable authority | T0 + Gate G0 | review Finding 4 (2nd half) |
| Closeout targets the real anchor | T6 Step 3 → `…-review-followup.md:578` | review Finding 4 (1st half) |
| ADR matches established local convention | T6 Step 2 → `0004-…` `# ADR 000N` shape | review Maintainability point |
| NOT the broad pass | Scope-controlled: 1 annotation site; ADR records the rejection |

The round-1 "review Finding N" tags above refer to the **first** adversarial review and are retained as execution-control history. The **second** adversarial pass (2026-05-16, against the revised plan) is resolved as follows:

| Round-2 finding (severity) | Resolution | Where |
|---|---|---|
| 1 — runtime gate omits recovery-success and begin-time auto-expire write sites (blocking) | Added `_drive_recover_success` (copied from `test_active_write_transaction_recover_commits_verified_written_output`) and `_drive_auto_expire` (copied from `test_begin_active_write_auto_expires_stale_pre_output_reservation`); `ALL_DRIVERS` now 12; vocabulary table no longer says "recover happy not driven"; every `_write_json_atomic` status site is driven | T3 |
| 2 — coverage test is domain-blind (high) | `WriteSpy.observed_by_domain()` added; `test_observed_status_coverage` now checks `RUNTIME_OP_MEMBERS ⊆ observed["op"]` and `RUNTIME_TX_MEMBERS ⊆ observed["tx"]`; Stop Condition 3 + Gate G3 reworded per-domain | T3, Stop/Gate |
| 3 — pyright probe exit-masked, no durable evidence home (moderate) | Probe split so `echo "pyright probe exit: $?"` is not `\| tail`-swallowed; output redirected to a file; new closeout artifact created/committed in T6 holds the version, exit, counts, and SC2 verdict | T4, T6 |
| 4 — `_drive_cleanup_failed` synthetic (moderate) | Rewritten to copy `test_write_active_handoff_persists_cleanup_failed_when_both_mechanisms_fail`: real `safe_delete` two-mechanism failure, no `_clear_snapshotted_primary_state` bypass | T3 |

The **third** adversarial pass (2026-05-16, against this revised plan) is resolved as follows:

| Round-3 finding (severity) | Resolution | Where |
|---|---|---|
| 1 — Stop Condition 2 could not prove *introduced* pyright noise: no pre-Task-2 baseline was captured, so the delta was inferred, not measured (high) | Added Task 2 Step 1 pre-annotation baseline (`/tmp/handoff-partition-pyright-baseline.txt`), identical command/scope as the Task 4 Step 3 post-probe; SC2 redefined as a measured delta = post − baseline; G2 now gates baseline capture; closeout records baseline, post, and delta | SC2, G2/G4, T2 Step 1, T4 Step 3, T6 closeout |
| 2 — `TERMINAL_TRANSACTION_STATUSES` consistency test was subset-only, letting a silently dropped required terminal pass (moderate) | Replaced with an EXACT source-grounded pin (`EXPECTED_TERMINAL_TRANSACTION_STATUSES`) catching omissions and additions; partition-linkage asserts retained for diagnostic specificity | T4 Step 1 |
| 3 — `unreadable` documented as a persisted write-site status when it is synthetic read-path return data (moderate) | Vocabulary header reworded; `unreadable` moved out of the persisted table into a dedicated "synthetic, NOT persisted" subsection; discriminating invariant and the inserted source/test comments corrected (ADR text was already accurate) | Vocabulary §, T1 test/source comments |
| 4 — local SC2 probe scope (`active_writes.py`) diverged from the CI surface (`turbo_mode_handoff_runtime/`), and SC2's own text contradicted the Task 4 command (low) | SC2 standardized on the file scope (annotation blast radius) matching Task 4/closeout; CI's broader scope explicitly legitimized and marked "not the SC2 measurement, never differenced"; closeout records the two scopes separately | SC2, T4 Step 3, T5, T6 closeout |

No gaps. Round-1 (5 findings + ADR-convention), round-2 (4 findings), and round-3 (4 findings) are all addressed with source-grounded fixes verified against `active_writes.py` / `session_state.py` at `HEAD 6d43d8d`.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code/YAML/markdown block is literal and complete. Conflict, recovery, recovery-success, auto-expire, and cleanup-failure setups are copied from named passing tests in `tests/test_active_writes.py`. The closeout artifact's bracketed `<…>` slots (T6 Step 4) are execution-time evidence captures, explicitly distinguished from spec placeholders. Pyright is intentionally unpinned with an explicit reasoned justification (advisory) — not a placeholder.

**3. Type/identifier consistency:** `ActiveWriteOperationStateStatus` / `ActiveWriteTransactionStatus` named identically in T1 (def), T2 (annotation), T3 (`get_args`), T4 (`get_args`). T3 helpers (`WriteSpy` incl. `statuses`/`observed_by_domain`/`assert_partitioned`, `_install_spy`, `_begin`, `_read`, `_drive_*` ×12, `ALL_DRIVERS`) consistent. Monkeypatch/attribute targets verified against live source at `HEAD 6d43d8d`: `active_writes._write_json_atomic` (module global, alias of `storage_primitives.write_json_atomic`, active_writes.py:43); `_drive_cleanup_failed` patches `active_writes._storage_primitives.subprocess.run` and `Path.unlink` (the exact targets the copied passing test uses, test_active_writes.py:1592-1607) — it no longer patches `_clear_snapshotted_primary_state`, so the real cleanup path runs. `begin_active_write` signature (`project_root`, `*`, `project_name`, `operation`, `slug`, `created_at`, `lease_seconds`) and `recover_active_write_transaction(project_root, *, operation_state_path)` match live source; `_drive_recover_success` uses the direct-API form and asserts op→`committed` (:804) / tx→`completed` (:811); `_drive_auto_expire` does a second compatible `begin_active_write` to trigger `_auto_expire_pre_output_reservation` (op :402 / tx :404). `TERMINAL_TRANSACTION_STATUSES` referenced as it exists (`session_state.py:51`). Member sets in the T1 test exactly match the T1 alias definitions and the Source-Grounded Vocabulary table.
