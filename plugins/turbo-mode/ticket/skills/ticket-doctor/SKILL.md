---
name: ticket-doctor
description: "Run explicit Ticket plugin maintenance. Use when the user explicitly asks to doctor the ticket system, diagnose ticket storage, repair corrupt ticket audit logs, validate ticket plugin health, or run ticket storage/plugin diagnostics. Do not use for casual audit, review, or triage."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Doctor

Run explicit maintenance and diagnostics for ticket storage or plugin health.
Do not trigger on casual audit, review, triage, or backlog-health language.

## Setup

Resolve paths before running commands:

- `PLUGIN_ROOT`: plugin root three levels above this `SKILL.md`.
- `PROJECT_ROOT`: nearest ancestor of the current working directory that
  contains `.codex`, `.git/`, or a `.git` file.
- `TICKETS_DIR`: `<PROJECT_ROOT>/docs/tickets`; never derive it from
  `PLUGIN_ROOT`.

Use a user-provided `CACHE_ROOT` only when diagnosing source/cache parity. Do
not invent an installed cache path.

## Diagnostics

For static plugin and storage diagnostics, run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_triage.py doctor <TICKETS_DIR> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT>
```

Report the diagnostic result as source/cache/storage evidence. Do not describe
it as live runtime proof.

## Audit Repair

Always dry-run audit repair first:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_audit.py repair <TICKETS_DIR> --dry-run
```

Show the dry-run result and ask before any mutation. If the user explicitly
approves repair, run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_audit.py repair <TICKETS_DIR>
```

Stop on parse, path, permission, or backup errors. Report the failing command
and do not try alternate repair paths unless the user asks.
