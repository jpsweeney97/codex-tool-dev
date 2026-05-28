# T-20260526-01: Resolve Slice 1A plan commit boundary

```yaml
id: T-20260526-01
date: "2026-05-26"
created_at: "2026-05-26T05:32:43Z"
status: open
priority: medium
source:
  type: capture
  ref: ""
  session: 019e5ff5-0316-72a0-9dc4-cbb3251b6df0
capture_confidence: high
capture_source: conversation
component: ticket-authority
related_paths: [docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md, docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md]
tags: [maintenance, docs]
blocked_by: []
blocks: []
contract_version: "1.0"
```

## Captured Request
Track the remaining commit-boundary cleanup for the Ticket Slice 1A authority-plan work.

## Problem
The Slice 1A authority plan is currently an untracked control document while the older Slice 1 plan has an unrelated pre-existing modification. Closeout can accidentally omit the new plan or mix unrelated docs work into the same commit.

## Next Action
Before committing, decide the intended staging boundary for the Slice 1A plan and the older Slice 1 plan, then stage only the files that belong to the authority-plan change.

## Acceptance Criteria
- [ ] The Slice 1A authority plan is intentionally tracked or explicitly deferred before closeout.
- [ ] The older Slice 1 plan modification is either included with a documented reason or left out of the Slice 1A commit boundary.
- [ ] Final status output distinguishes the Slice 1A plan from unrelated dirty work.
