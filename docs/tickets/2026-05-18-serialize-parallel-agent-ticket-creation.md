# T-20260518-01: Serialize parallel autonomous ticket creation before delegated auto_audit

```yaml
id: T-20260518-01
date: "2026-05-18"
created_at: "2026-05-18T00:00:00Z"
status: open
priority: medium
effort: M
source:
  type: follow-up
  ref: ticket-autonomy-ingest-contract-hardening
  session: 2026-05-18-ticket-autonomy-ingest-contract-hardening
tags: [ticket, autonomy, concurrency, follow-up]
blocked_by: []
blocks: []
contract_version: "1.0"
key_file_paths: [plugins/turbo-mode/ticket/scripts/ticket_engine_core.py, plugins/turbo-mode/ticket/scripts/ticket_capture.py, plugins/turbo-mode/ticket/scripts/ticket_update.py, plugins/turbo-mode/ticket/references/ticket-contract.md]
```

## Problem
Ticket is deliberately single-writer for autonomous creation in the current source slice. Adding file locking, queueing, or daemon coordination now would pay complexity before parallel autonomous ticket creation is a real near-term requirement.

The trigger is concrete: any workflow intentionally launches two or more ticket-capable agents in the same Codex session, or `auto_audit` is enabled for delegated multi-agent work.

## Acceptance Criteria
- [ ] The design chooses a serialization mechanism for parallel ticket-capable agents in one Codex session.
- [ ] The implementation protects ticket id allocation, audit writes, processed-envelope moves, and capture/update payload cleanup from parallel writes.
- [ ] Tests exercise two ticket-capable agents racing to create or ingest tickets.
- [ ] Docs state when parallel autonomous ticket creation is supported and which paths remain single-writer.
- [ ] Delegated multi-agent `auto_audit` rollout depends on this work and activation-capable runtime readiness.
