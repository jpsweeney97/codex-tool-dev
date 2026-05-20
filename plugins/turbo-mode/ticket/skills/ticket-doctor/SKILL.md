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
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py diagnose <TICKETS_DIR> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT>
```

Report the diagnostic result as source/cache/storage evidence. Do not describe
it as live runtime proof.

`diagnose` reports stale `.codex/ticket-tmp/` payloads older than 24 hours
without mutating them.

## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields in the transcript.

- `cleanup_stale_preview`: say old abandoned Ticket preview state can be cleaned
  up after review. Do not clean anything until the user explicitly approves the
  confirmed cleanup command.

## Audit Repair

Always dry-run audit repair first:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <TICKETS_DIR>
```

Show the dry-run result and ask before any mutation. If the user explicitly
approves repair, run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <TICKETS_DIR> --confirm-repair
```

Stop on parse, path, permission, or backup errors. Report the failing command
and do not try alternate repair paths unless the user asks.

## Stale Payload Cleanup

Always run diagnostics first. Show the stale `.codex/ticket-tmp/` payloads
report and ask before any cleanup mutation. If the user explicitly approves
stale payload cleanup, run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads
```

The unconfirmed command is:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR>
```

Short form: `ticket_doctor.py clean-stale-payloads <TICKETS_DIR>`.

Cleanup is limited to stale JSON payloads under
`<PROJECT_ROOT>/.codex/ticket-tmp/` and uses a 24 hours TTL. The confirmation
flag is `--confirm-clean-stale-payloads`.
