---
name: ticket-backlog-triage
description: "Review ticket backlog health and recommend next actions. Use when the user asks what needs attention, what to work on next, what is stale or blocked, or asks for ticket backlog triage. Read-only; may suggest capture prompts but must not write tickets. Do not use for direct show, list, search, ticket lookup, or close-readiness requests; use read-ticket."
allowed-tools:
  - Bash
  - Read
---

# Ticket Review

Review ticket backlog health without writing tickets. Use this for read-only
backlog triage, stale-ticket checks, blocker observations, and next-action
recommendations.

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This skill is source-authority guidance, not
installed-runtime proof and not runtime proof. This docs/tests slice does not
perform cutover inventory or normalization.

Backlog triage is read/query/reporting unless it produces candidate mutations
for the future runtime path. Persisted `blocked` status and reverse `blocks`
edges are not target schema; target blockedness derives from `blocked_by`.

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
uv run python -B <PLUGIN_ROOT>/scripts/ticket_review.py review <TICKETS_DIR>
```

Run audit summary:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_review.py audit <TICKETS_DIR>
```

## Output Rules

- Summarize counts, stale tickets, blocker relationships derived from
  `blocked_by`, and the highest-signal next actions from script output.
- Keep the review read-only. Do not create, update, close, reopen, doctor, or
  repair tickets from this skill.
- If the review reveals missing work that should become a ticket, suggest a
  concrete `capture-ticket` prompt instead of writing the ticket.
- Casual audit or backlog review language stays here. Run maintenance or repair
  only when the user explicitly asks for `ticket-doctor`.
