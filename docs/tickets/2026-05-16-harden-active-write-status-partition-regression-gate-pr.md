# T-20260516-01: Harden active-write status-partition regression gate (PR #16 fast-follow)

```yaml
id: T-20260516-01
date: "2026-05-16"
created_at: "2026-05-16T16:46:05Z"
status: open
priority: medium
effort: M
source:
  type: ad-hoc
  ref: ""
  session: a524d1d2-4bf9-41c4-be4c-2bc5a116e812
tags: [handoff, active-writes, test-robustness, pr-16-followup]
blocked_by: []
blocks: []
contract_version: "1.0"
key_file_paths: [plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py, plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py, plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/chain_state.py, plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py]
```

## Problem
The PR #16 5-agent /review-pr confirmed the active-write status-partition regression gate is real and merge-safe (tautology hypothesis empirically falsified via three source mutations; zero behavior change; alias member sets traced exact). It also surfaced robustness gaps that do NOT cause a false-green today but weaken the gate against future driver/layout drift. Bundle as one fast-follow. Full detail: docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-followup.md

## Acceptance Criteria
- [ ] Repoint the write-spy from active_writes._write_json_atomic to the true chokepoint storage_primitives.write_json_atomic so all importers (incl. the currently-unspied chain_state.py binding) are intercepted; update the gate docstring's 'single atomic-write chokepoint' claim. (silent-failure-hunter I-1 — dormant false-green vector)
- [ ] Add a per-driver assert spy.events inside the test_observed_status_coverage loop, removing the implicit cross-test dependency on the sibling test's non-empty guard. (pr-test-analyzer #2 / silent-failure-hunter S-1)
- [ ] Harden _drive_cleanup_failed fail_unlink to compare self.resolve() == state_path.resolve() (currently relies on pytest tmp_path being pre-resolved). (pr-test-analyzer #1)
- [ ] Add else: pytest.fail(...) to WriteSpy.assert_partitioned so a future status write to a path matching neither domain cannot escape silently. (pr-test-analyzer #3 — latent; unreachable today)
- [ ] Promote the deferred ActiveWriteReservation.status validating-coercion at _reservation_from_payload from an ADR-0004 sentence to a tracked item; optionally add a one-line documentary-only comment at the transaction_status annotation. (type-design-analyzer)
- [ ] No production behavior change beyond named test-robustness edits; full Handoff suite green; ruff clean.

## Key Files
| File | Role | Look For |
|------|------|----------|
| plugins/turbo-mode/handoff/1.6.0/tests/test_active_write_lifecycle_matrix.py | the regression gate (write-spy lifecycle matrix) | WriteSpy monkeypatch target; test_observed_status_coverage events guard; _drive_cleanup_failed fail_unlink; assert_partitioned else-branch |
| plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py | true atomic-write chokepoint to repoint the spy onto | write_json_atomic |
| plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/chain_state.py | holds the currently-unspied second _write_json_atomic binding | module-level _write_json_atomic import |
| plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py | deferred ActiveWriteReservation.status typing | _reservation_from_payload; transaction_status annotation |
