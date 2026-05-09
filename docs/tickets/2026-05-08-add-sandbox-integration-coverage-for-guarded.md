# T-20260508-01: Add sandbox integration coverage for guarded refresh orchestration

```yaml
id: T-20260508-01
date: "2026-05-08"
created_at: "2026-05-08T17:11:41Z"
status: open
priority: medium
effort: M
source:
  type: ad-hoc
  ref: ""
  session: codex-followup-pr5
tags: [turbo-mode, plan-06, tests, guarded-refresh]
blocked_by: []
blocks: []
contract_version: "1.0"
```

## Problem
PR #5 now has focused blocker regression coverage, but several guarded-refresh orchestration tests still mock most of the lane. Add behavior-level sandbox integration coverage that exercises real local lock, run-state, snapshot, rollback, process-gate, smoke, and final-status wiring while faking only the external app-server/runtime boundary.

## Acceptance Criteria
- [ ] At least one isolated success-path orchestration test runs against a temporary codex_home without touching the real Codex home.
- [ ] At least one rollback or failure-path orchestration test asserts durable artifacts and restored state, not just call ordering.
- [ ] Tests use real local lock/run-state/snapshot/final-status behavior and fake only the app-server/runtime boundary plus deterministic external process census as needed.
- [ ] Existing unit tests that mock phase boundaries remain allowed for narrow edge cases; the new coverage supplements rather than broadly rewrites them.
- [ ] Verification documents the command used and confirms no generated cache residue under plugins/turbo-mode.
