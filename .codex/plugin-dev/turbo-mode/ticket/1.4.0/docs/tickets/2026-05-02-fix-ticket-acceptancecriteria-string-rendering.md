# T-20260502-01: Fix Ticket acceptance_criteria string rendering

```yaml
id: T-20260502-01
date: "2026-05-02"
created_at: "2026-05-02T05:37:08Z"
status: open
priority: medium
effort: S
source:
  type: ad-hoc
  ref: ""
  session: ec705ab6-32c2-45fc-92af-a453e524770d
tags: [ticket, rendering, acceptance-criteria, turbo-mode-live-smoke-20260502T051842Z-5767068b]
blocked_by: []
blocks: []
contract_version: "1.0"
```

## Problem
When ticket creation receives acceptance_criteria as a string, the renderer emits character-level checklist items instead of treating the string as one criterion or rejecting the shape. Observed during Turbo Mode live smoke RUN_ID=turbo-mode-live-smoke-20260502T051842Z-5767068b. Lifecycle still passed because the Acceptance Criteria section was non-empty, but formatting was incorrect.

## Acceptance Criteria
- [ ] A string acceptance_criteria value is rendered as one checklist item, or validation rejects it with a clear error.
- [ ] The renderer no longer emits one checklist item per character.
- [ ] Regression coverage exists for string and list acceptance_criteria inputs.
