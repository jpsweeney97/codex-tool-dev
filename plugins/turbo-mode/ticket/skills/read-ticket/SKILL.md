---
name: read-ticket
description: "Read, list, and search repo-local tickets. Use when the user asks to show a ticket, list tickets, find tickets about a topic, show open work, or check close readiness. Read-only; do not create, update, close, reopen, triage, repair, prioritize, or answer what to work on next; use ticket-backlog-triage for backlog health and next-action analysis."
allowed-tools:
  - Bash
  - Read
---

# Ticket Find

Read repo-local tickets without mutation. Use only `ticket_read.py` with the
`list`, `query`, and `check` subcommands.

## Setup

Resolve paths before running commands:

- `PLUGIN_ROOT`: plugin root three levels above this `SKILL.md`.
- `PROJECT_ROOT`: nearest ancestor of the current working directory that
  contains `.codex`, `.git/`, or a `.git` file.
- `TICKETS_DIR`: `<PROJECT_ROOT>/docs/tickets`; never derive it from
  `PLUGIN_ROOT`.

If `PROJECT_ROOT` or `TICKETS_DIR` cannot be resolved, explain the missing path
and stop.

## Target Post-Cutover Ticket Shape

Target statuses are `open`, `in_progress`, `done`, and `wontfix`. Target
priorities are `high`, `normal`, and `low`. Blockedness derives from
`blocked_by`; it is not a persisted lifecycle status.

## Commands

List tickets:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <TICKETS_DIR> [--status open|in_progress|done|wontfix] [--priority high|normal|low] [--tag <tag>]
```

Search or open by ticket ID prefix:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py query <TICKETS_DIR> <search_term>
```

Check close readiness:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py check <TICKETS_DIR> <ticket_id> [--resolution done|wontfix]
```

## Output Rules

- Present ticket ID first, then title, status, priority, and path.
- Use `check` before answering whether a ticket can close.
- Do not call mutation scripts, triage scripts, audit repair, or doctor
  diagnostics from this skill.

## Legacy Cutover Input

Old filters such as blocked lifecycle status and critical or medium priorities
may appear in legacy source data before cutover. Treat them as read-only
compatibility facts, not target schema.
