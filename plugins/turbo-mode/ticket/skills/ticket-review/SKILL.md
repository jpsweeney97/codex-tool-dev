---
name: ticket-review
description: "Review ticket backlog health and recommend next actions. Use when the user asks what needs attention, what to work on next, what is stale or blocked, or asks for ticket backlog triage. Read-only; may suggest capture prompts but must not write tickets."
allowed-tools:
  - Bash
  - Read
---

# Ticket Review

Review ticket backlog health without writing tickets. Use this for read-only
backlog triage, stale-ticket checks, blocked-chain analysis, and next-action
recommendations.

## Setup

Resolve paths before running commands:

- `PLUGIN_ROOT`: plugin root three levels above this `SKILL.md`.
- `PROJECT_ROOT`: nearest ancestor of the current working directory that
  contains `.codex`, `.git/`, or a `.git` file.
- `TICKETS_DIR`: `<PROJECT_ROOT>/docs/tickets`; never derive it from
  `PLUGIN_ROOT`.

If `TICKETS_DIR` is missing, report that no repo-local ticket directory exists
and stop.

## Commands

Run dashboard:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_review.py review <TICKETS_DIR>
```

Run audit summary:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_review.py audit <TICKETS_DIR>
```

## Output Rules

- Summarize counts, stale tickets, blocked chains, and the highest-signal next
  actions from script output.
- Keep the review read-only. Do not create, update, close, reopen, doctor, or
  repair tickets from this skill.
- If the review reveals missing work that should become a ticket, suggest a
  concrete `ticket-capture` prompt instead of writing the ticket.
- Casual audit or backlog review language stays here. Run maintenance or repair
  only when the user explicitly asks for `ticket-doctor`.
