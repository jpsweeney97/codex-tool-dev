# PR Package: Turbo Mode Refresh 06 Guarded Refresh

## PR Title

Implement guarded installed-cache refresh with certified Plan 06 evidence

## PR Body

### Summary

This PR adds the guarded-refresh maintenance lane for Turbo Mode installed-cache
updates. It keeps ordinary planning non-mutating, while allowing a real
installed-cache refresh only through an explicit external maintenance window
with process gates, locks, snapshots, app-server authority proof, isolated
rehearsal proof, smoke, rollback/recovery, and commit-safe evidence.

The branch also includes the live Plan 06 evidence:

- Live guarded refresh:
  `plan06-live-guarded-refresh-20260508-154206`
- Live status:
  `MUTATION_COMPLETE_CERTIFIED`
- Current post-normalization state:
  `plan06-post-normalization-no-drift-20260508-155500`
- Current status:
  `no-drift`

### Major Changes

- Adds guarded refresh orchestration in `plugins/turbo-mode/tools/refresh/mutation.py`.
- Adds process exclusivity checks in `process_gate.py`.
- Adds lock and run-state handling in `lock_state.py`.
- Adds standard installed smoke in `smoke.py`.
- Adds retained-run certification in `retained_run.py`.
- Adds publication replay/demotion handling in `publication.py`.
- Extends app-server authority and install proof support in `app_server_inventory.py`.
- Extends commit-safe and validation schemas for guarded refresh evidence.
- Adds CLI support for:
  - `--guarded-refresh`
  - `--recover <RUN_ID>`
  - `--certify-retained-run <RUN_ID>`
  - `--seed-isolated-rehearsal-home`
  - `--generate-guarded-refresh-approval`
- Records live and post-normalization evidence under
  `plugins/turbo-mode/evidence/refresh/`.
- Normalizes Ticket hook manifest serialization so current dry-runs are
  drift-free.
- Adds a post-review blocker patch for guarded-refresh safety:
  canonical real Codex home derivation, abort propagation during publication,
  fail-closed JSON parsing, and focused safety regression tests.

### Evidence Boundaries

- Live mutation source boundary:
  `081a1a2989f685517d19ab3dde98113ea5c24a57`
- Live evidence commit:
  `913bf62558f98ec611156f9b1a3b4b45f5058214`
- Post-certification cleanup:
  `77ee353183325b6d57b4ebfaac10b0a7e8d89ef5`
- Current no-drift evidence commit:
  `d11b54e3f94e6c5e0bba19af05840ca84fc0798f`

The post-review blocker patch changes refresh tooling source and tests after
those evidence commits. The prior live mutation and no-drift summaries remain
the relevant installed-cache proofs, but they should not be read as a fresh
live mutation proof for the patched source head.

Important evidence files:

- `plugins/turbo-mode/evidence/refresh/plan06-live-guarded-refresh-20260508-154206.summary.json`
- `plugins/turbo-mode/evidence/refresh/plan06-post-normalization-no-drift-20260508-155500.summary.json`
- `docs/superpowers/closeouts/2026-05-08-turbo-mode-refresh-06-final-closeout.md`

### Verification

Final verification after the post-certification cleanup:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Result:

```text
439 passed, 1 skipped in 36.65s
```

Post-review blocker patch verification:

```text
449 passed, 1 skipped in 36.59s
```

Additional checks:

```bash
uv run ruff check plugins/turbo-mode/tools/refresh/tests/test_ticket_hook_manifest.py
git diff --check
find plugins/turbo-mode -name .pytest_cache -o -name __pycache__ -o -name '*.pyc'
```

Results:

- Ruff: `All checks passed!`
- `git diff --check`: passed
- residue scan: no output

Current installed-cache proof:

```text
run_id=plan06-post-normalization-no-drift-20260508-155500
terminal_plan_status=no-drift
final_status=no-drift
source_manifest_sha256=7efea898b6459128c71bf4fb045afcdebcb23337ed8c770eb1c341990a40be14
installed_cache_manifest_sha256=7efea898b6459128c71bf4fb045afcdebcb23337ed8c770eb1c341990a40be14
```

### Review Guidance

Review this PR in three layers:

1. Control surface and safety gates:
   - CLI mode validation
   - external-maintenance-window requirements
   - process gates
   - locks and run-state
   - snapshot/rollback/recovery behavior

2. Authority and evidence:
   - app-server launch/install authority
   - isolated rehearsal proof validation
   - approval candidate/runbook generation
   - commit-safe summary validation
   - publication replay/demotion behavior

3. Installed behavior:
   - Handoff state-helper smoke
   - Ticket hook-backed smoke
   - live certified evidence summary
   - post-normalization no-drift evidence summary

### Known Boundaries

- The live mutation evidence is bound to `081a1a2`, not to later docs or PR
  packaging commits.
- The current no-drift evidence is bound to `77ee353`, after Ticket hook
  serialization normalization.
- The post-review blocker patch is source/tooling/test scoped. It does not
  claim a new live installed-cache mutation.
- The no-drift boundary is non-mutating by design; rerunning a live guarded
  refresh after no drift would add risk without adding evidence value.
- Raw local-only transcripts, process listings, smoke logs, and config/cache
  snapshots remain under `/Users/jp/.codex/local-only/turbo-mode-refresh/` and
  are intentionally not committed.

### Suggested Merge Criteria

- Confirm the branch includes the two evidence summaries listed above.
- Confirm `terminal_plan_status: no-drift` in the post-normalization summary.
- Confirm `MUTATION_COMPLETE_CERTIFIED` in the live guarded-refresh summary.
- Confirm the refresh test suite is still passing in CI or local review.
- Confirm no extra live mutation is requested for this PR.
