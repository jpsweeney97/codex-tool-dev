---
name: ticket-triage
description: "Analyze ticket health, detect stale tickets, blocked dependency chains, and audit activity. Use when the user says 'triage tickets', 'what's in the backlog', 'show ticket health', 'any stale tickets', 'ticket dashboard', 'what tickets are blocked', 'what should I work on next', 'what's outstanding', or 'catch me up on the project'. Also use at session start when the user wants project orientation, or whenever they want any kind of health check or overview of the ticket system."
allowed-tools:
  - Bash
  - Read
---

# /ticket-triage

Read-only ticket health analysis. Runs dashboard + audit, then adds
recommendations. No mutations.

## Setup

Resolve `PLUGIN_ROOT`, `PROJECT_ROOT`, and `TICKETS_DIR` before running
commands.

### Resolve plugin root

Set `PLUGIN_ROOT` to the plugin root directory three levels above this `SKILL.md`.

### Resolve project root

Set `PROJECT_ROOT` to the nearest ancestor of the current working directory
that contains `.codex`, `.git/`, or a `.git` file.

### Resolve tickets directory

Set `TICKETS_DIR` to `<PROJECT_ROOT>/docs/tickets`.
Never derive `TICKETS_DIR` from `PLUGIN_ROOT`.

## Procedure

### Step 1: Run dashboard

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <TICKETS_DIR>
```

Response fields include:
- `counts`
- `priority_counts`
- `total`
- `active_tickets`
- `stale`
- `blocked_chains`
- `next_actions`
- `size_warnings`

### Step 2: Run audit

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_triage.py audit <TICKETS_DIR>
```

### Step 3: Run doctor when requested

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_triage.py doctor <TICKETS_DIR> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT>
```

Doctor is diagnostic only. It reports project root, tickets directory, config
presence, source/cache equality, declared hook metadata, and whether a live
runtime hook probe was run.

### Step 4: Format the report

Present a structured summary using only the script outputs.

Include:
- active ticket counts by status
- priority counts
- stale tickets
- blocked chains
- recent audit activity

**Recommended next actions:**
- start_or_assign_critical — T-20260503-01: Critical ticket is open and not in progress

If `next_actions` is present, surface the first few actions in priority order
with the ticket ID and reason.

## Constraints

- Do not mutate tickets from this skill.
- Do not substitute a real installed cache path into examples. Use `<CACHE_ROOT>`.
- If doctor is not requested, do not run it.
