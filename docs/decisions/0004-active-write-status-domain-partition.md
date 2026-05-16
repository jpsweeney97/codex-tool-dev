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

- **Enforced value is the pytest gate, not the types (stated plainly).**
  Under this repo's ruff+pytest CI the two `Literal` aliases and the
  `transaction_status` annotation carry NO enforced static guarantee. Their
  durable role is to be the single source of truth (`get_args(...)`) that
  the write-spy gate and the `TERMINAL_TRANSACTION_STATUSES` consistency
  test both read — a typed enumeration backing a pytest invariant, not a
  static-analysis improvement. This ADR's title is "partition" (the modeled
  and pytest-enforced invariant), deliberately NOT "typing pass": the types
  are the handle, the write-spy is the enforcement, advisory pyright is
  decorative until the documented upgrade signal fires. Read Tasks 1/2/5 as
  scaffolding for a non-gating reader; the deliverable that prevents
  regressions is Task 3.
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
