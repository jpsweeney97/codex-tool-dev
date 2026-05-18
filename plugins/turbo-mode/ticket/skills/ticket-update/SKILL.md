---
name: ticket-update
description: "Change existing repo-local ticket lifecycle and metadata. Use when the user asks to update a ticket, mark work in progress, close, reopen, change priority, edit tags, add blockers, set component or related paths, or change capture metadata. Requires preview before writing."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Update

Change existing repo-local ticket lifecycle and frontmatter metadata through the
guided workflow runner. This skill does not create new tickets; use
`ticket-capture` for capture intent.

## Setup

Resolve paths before writing a payload or running commands:

- `PLUGIN_ROOT`: plugin root three levels above this `SKILL.md`.
- `PROJECT_ROOT`: nearest ancestor of the current working directory that
  contains `.codex`, `.git/`, or a `.git` file.
- `TICKETS_DIR`: `<PROJECT_ROOT>/docs/tickets`; never derive it from
  `PLUGIN_ROOT`.
- `PAYLOAD_PATH`: an absolute path under
  `<PROJECT_ROOT>/.codex/ticket-tmp/`; do not use a relative path or a path with
  whitespace.

Create the payload directory if needed:

```bash
mkdir -p <PROJECT_ROOT>/.codex/ticket-tmp
```

## Supported Changes

Supported v1 changes are existing-ticket lifecycle and frontmatter metadata
updates:

- status changes: `in_progress`, `blocked`, `done`, `wontfix`, and reopen to
  `open` when the workflow accepts the transition.
- priority changes.
- effort changes.
- tag changes.
- blockers and dependency metadata.
- source and defer metadata.
- capture metadata: `capture_confidence`, `capture_source`, and
  `refinement_status`.
- component and `related_paths` metadata.

Do not perform arbitrary body-section editing in v1. The current workflow
runner rejects section fields such as `problem` and `acceptance_criteria`, and
rejects unknown fields such as `next_action`. If the user asks to refine
placeholder problem, next action, or acceptance criteria content, explain that
this needs the future dedicated `ticket_update.py` backend from Task 5 and is
not available through the current workflow runner.

## Payload Shape

Write a compact JSON object to `PAYLOAD_PATH`. Use only the requested existing
ticket operation and scoped fields:

```json
{
  "action": "update",
  "ticket_id": "T-20260518-01",
  "args": {"ticket_id": "T-20260518-01"},
  "fields": {
    "priority": "high",
    "tags": ["bug"]
  }
}
```

For close:

```json
{
  "action": "close",
  "ticket_id": "T-20260518-01",
  "args": {"ticket_id": "T-20260518-01"},
  "fields": {"resolution": "done"}
}
```

For reopen:

```json
{
  "action": "reopen",
  "ticket_id": "T-20260518-01",
  "args": {"ticket_id": "T-20260518-01"},
  "fields": {"reopen_reason": "Regression reproduced after the earlier fix."}
}
```

`action` must be `update`, `close`, or `reopen`. `ticket_id` must be present at
top level and in `args.ticket_id`. `fields` must be a dict and must contain only
scoped fields for this operation. Do not write `session_id`, `hook_injected`, or
`hook_request_origin`; the canonical hook injects trust fields when the workflow
command runs. Do not include arbitrary markdown body edits in `fields`.

## Preview First

Write the requested scoped change to `PAYLOAD_PATH`, then run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_workflow.py prepare <PAYLOAD_PATH>
```

Show the returned preview and wait for explicit user confirmation before any
write. Do not treat the original update request as execute approval.

If the user confirms, run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_workflow.py execute <PAYLOAD_PATH>
```

If the user edits the proposed change, update the same payload and rerun
`prepare`. If the response includes a `recover_command`, run only the returned
recovery command and then rerun `prepare` for the same `PAYLOAD_PATH`.

There is no dedicated `ticket_update.py` backend yet. Use the existing
`ticket_workflow.py prepare` and `execute` path until a dedicated backend is
implemented.
