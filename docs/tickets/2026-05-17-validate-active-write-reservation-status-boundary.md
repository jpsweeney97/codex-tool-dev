# T-20260517-01: Validate ActiveWriteReservation status at the JSON boundary

```yaml
id: T-20260517-01
date: "2026-05-17"
created_at: "2026-05-17T04:39:51Z"
status: open
priority: medium
effort: S
source:
  type: follow-up
  ref: "T-20260516-01"
  session: active-write-status-partition-fast-follow
tags: [handoff, active-writes, typing, validation]
blocked_by: []
blocks: []
contract_version: "1.0"
key_file_paths: [plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py, plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py]
```

## Problem
ADR 0004 deliberately deferred annotating `ActiveWriteReservation.status` because `_reservation_from_payload()` currently deserializes the value from JSON with `str(payload["status"])`. Annotating the field honestly requires a validating coercion at that boundary, not a broad `dict[str, object]` to TypedDict rewrite.

## Acceptance Criteria
- [ ] `_reservation_from_payload()` validates and coerces the persisted operation-state status against `ActiveWriteOperationStateStatus` before constructing `ActiveWriteReservation`.
- [ ] Invalid persisted statuses fail closed with an `ActiveWriteError` that names the reservation payload/status boundary.
- [ ] Focused coverage exercises both a valid persisted status and an invalid persisted status at the JSON boundary.
- [ ] The change does not widen into the broader payload TypedDict pass or unrelated `dict[str, object]` typing cleanup.
- [ ] Handoff focused tests and `ruff` pass for the changed surface.
