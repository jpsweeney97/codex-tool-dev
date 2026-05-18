# T-20260518-02: Design and implement activation-capable Ticket runtime readiness

```yaml
id: T-20260518-02
date: "2026-05-18"
created_at: "2026-05-18T00:00:00Z"
status: open
priority: high
effort: L
source:
  type: follow-up
  ref: ticket-autonomy-ingest-contract-hardening
  session: 2026-05-18-ticket-autonomy-ingest-contract-hardening
tags: [ticket, autonomy, runtime-readiness, follow-up]
blocked_by: []
blocks: []
contract_version: "1.0"
key_file_paths: [plugins/turbo-mode/ticket/scripts/ticket_engine_core.py, plugins/turbo-mode/ticket/scripts/ticket_doctor.py, plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py, plugins/turbo-mode/ticket/references/ticket-contract.md]
```

## Problem
This source slice documents that current agent-origin `auto_audit` execute remains governed by the existing guarded provenance/trust model. It does not add activation-capable runtime readiness, does not write `.codex/ticket-runtime-proof.json`, and does not add a new execute readiness gate.

Before Ticket makes any stronger installed-runtime trust claim, or before delegated multi-agent `auto_audit` is rolled out, Ticket needs an activation-capable readiness boundary that proves the installed runtime path and the live hook-mediated mutation path.

## Trigger
- Before enabling `agent + auto_audit + execute` through runtime readiness.
- Before public docs, contracts, or status reports claim stronger installed-runtime readiness than the current guarded provenance/trust model.
- Before delegated multi-agent `auto_audit` rollout.

## Required Scope
- Ticket-owned app-server inventory producer for activation evidence.
- Activation-mode doctor command that performs live app-server inventory itself.
- Live installed Codex hook-mediated smoke inside activation-mode doctor.
- Run nonce correlation between inventory, hook smoke, and activation proof write.
- Installed cache identity and executing Ticket root identity checks.
- Structural separation between activation proof output and debug/external evidence.
- `engine_execute()` gate integration only after the activation producer is structurally correct.

## Hard Stop
No activation proof file can be written without live app-server inventory plus live installed hook-mediated smoke. External evidence, fixture transcripts, source-checkout diagnostics, and handwritten JSON must not be able to write or promote `.codex/ticket-runtime-proof.json`.

## Acceptance Criteria
- [ ] Activation mode starts and records a fresh app-server inventory covering plugin/read, plugin/list, skills/list, and schema-proven hook inventory.
- [ ] Activation mode runs a live installed hook-mediated smoke through Codex, not by invoking the hook script directly.
- [ ] The smoke records installed `PLUGIN_ROOT`, hook source/command, `session_id`, hook event, injected fields, nonce, Codex version, and outcome.
- [ ] The activation proof binds project root, Ticket plugin id/version, installed cache path, matched hook identity, exact guard command/script identity, and exactly one Bash PreToolUse guard.
- [ ] Source-checkout execution can inspect or explain installed readiness but cannot satisfy activation for `agent + auto_audit + execute`.
- [ ] External/debug evidence writes only non-activation diagnostics or stdout and cannot overwrite the activation proof path.
- [ ] `engine_execute()` gates only agent-origin ticket-capable execute surfaces after the activation producer and live smoke pass.
- [ ] Tests prove inventory-only, fixture-only, source-only, unavailable-smoke, and malformed-smoke paths do not activate autonomy.
