# Fast-follow — active-write status-partition regression-gate hardening

- **Status:** open — durable capture pending canonical ticket-engine entry
- **Origin:** PR #16 (`feature/handoff-active-write-status-partition`)
  5-agent `/review-pr` (code, tests, types, comments, silent-failure)
- **Priority:** medium · **Effort:** M · **Blocking:** none
- **Tracking note:** the ticket engine is trust-gated (guard-hook
  provenance, not live in a Claude Code source-dev session); this file is
  the interim tracked record. Promote to a canonical ticket with
  `/ticket create "Harden active-write status-partition regression gate
  (PR #16 fast-follow)"` (user-origin path injects the trust triple).

## Problem

The PR #16 review confirmed the status-partition gate is real and
merge-safe (tautology hypothesis empirically falsified via three source
mutations; zero behavior change; alias member sets traced exact). It also
surfaced robustness gaps that do **not** cause a false-green today but
weaken the gate against future driver/layout drift. Bundle as one
fast-follow.

## Acceptance criteria

- [ ] Repoint the write-spy from `active_writes._write_json_atomic` to the
  true chokepoint `storage_primitives.write_json_atomic` so all importers
  (incl. the currently-unspied `chain_state.py` binding) are intercepted;
  update the gate docstring's "single atomic-write chokepoint" claim.
  *(silent-failure-hunter I-1 — dormant false-green vector: a driver that
  induced a legacy-bridge chain-state continuation would write through the
  unspied binding undetected.)*
- [ ] Add a per-driver `assert spy.events, f"{driver.__name__}: zero
  events"` inside the `test_observed_status_coverage` loop, removing the
  implicit cross-test dependency on the sibling test's non-empty guard.
  *(pr-test-analyzer #2 / silent-failure-hunter S-1)*
- [ ] Harden `_drive_cleanup_failed`'s `fail_unlink` to
  `self.resolve() == state_path.resolve()`; current exact-equality works
  only because pytest `tmp_path` is pre-resolved. *(pr-test-analyzer #1)*
- [ ] Add `else: pytest.fail(...)` to `WriteSpy.assert_partitioned` so a
  future status write to a path matching neither domain cannot escape
  silently. *(pr-test-analyzer #3 — latent; unreachable today)*
- [ ] Promote the deferred `ActiveWriteReservation.status` validating-
  coercion at `_reservation_from_payload` from an ADR-0004 sentence to a
  tracked work item; optionally add a one-line "documentary only —
  enforced by the lifecycle-matrix test, not the type checker" comment at
  the `_persist_operation_and_transaction.transaction_status` annotation.
  *(type-design-analyzer; broad `dict[str, object]` payload typing remains
  gated by the documented pyright upgrade signal.)*
- [ ] No production behavior change beyond the named test-robustness
  edits; full Handoff suite green; `ruff` clean.

## Out of scope

- Broad `dict[str, object]` → TypedDict payload pass (ADR 0004 named
  follow-up, gated by the pyright upgrade signal).
- The two C1/I1 doc-correctness blockers — already fixed and pushed in
  commit `8bc8364`.
