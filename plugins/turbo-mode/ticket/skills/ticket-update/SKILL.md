---
name: ticket-update
description: "Refine or change existing repo-local tickets. Use when the user asks to update a ticket, mark work in progress, close, reopen, change priority, edit tags, add blockers, set component or related paths, or replace placeholder problem, next action, or acceptance criteria. Requires preview before writing."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Update

Refine or change an existing repo-local ticket through the focused
`ticket_update.py` backend. This skill does not create new tickets; use
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

Supported v1 changes are existing-ticket lifecycle, metadata, and focused
refinement updates:

- status changes: `in_progress`, `blocked`, `done`, `wontfix`, and reopen to
  `open` when the workflow accepts the transition.
- priority changes.
- tag changes.
- blockers and dependency metadata.
- component and `related_paths` metadata.
- synthesized `Problem` replacement.
- synthesized `Next Action` replacement.
- synthesized `Acceptance Criteria` replacement.

Do not perform arbitrary body-section editing in v1. Only the focused
refinement fields `problem`, `next_action`, and `acceptance_criteria` may change
ticket body sections. Reject requests to replace unrelated sections such as
`Approach`, `Verification`, `Context`, or free-form markdown body content.

For a ticket with `refinement_status: needs_refinement`, the backend clears
`refinement_status` and removes the `needs-refinement` tag only when the update
provides concrete `problem`, `next_action`, and `acceptance_criteria` values.
Priority-only or tag-only updates keep `refinement_status`; if a tag update
omits `needs-refinement`, the backend preserves that tag while refinement is
still active.

## Payload Shape

Write a compact JSON object to `PAYLOAD_PATH` with top-level `ticket_id` and an
`update` object. Use only the requested existing-ticket operation and scoped
fields:

```json
{
  "tickets_dir": "docs/tickets",
  "ticket_id": "T-20260518-01",
  "update": {
    "priority": "high",
    "tags": ["bug"]
  }
}
```

For close:

```json
{
  "tickets_dir": "docs/tickets",
  "ticket_id": "T-20260518-01",
  "update": {"status": "done"}
}
```

For reopen:

```json
{
  "tickets_dir": "docs/tickets",
  "ticket_id": "T-20260518-01",
  "update": {
    "status": "open",
    "reopen_reason": "Regression reproduced after the earlier fix."
  }
}
```

For refinement:

```json
{
  "tickets_dir": "docs/tickets",
  "ticket_id": "T-20260518-01",
  "update": {
    "problem": "The ticket lacks a concrete close-readiness rule.",
    "next_action": "Add a focused regression test for close readiness.",
    "acceptance_criteria": [
      "Close readiness rejects placeholder acceptance criteria.",
      "The preview reports when needs-refinement will be cleared."
    ]
  }
}
```

`update` must contain only these keys: `problem`, `next_action`,
`acceptance_criteria`, `priority`, `tags`, `component`, `related_paths`,
`blocked_by`, `blocks`, `status`, and `reopen_reason`. Do not write
`session_id`, `hook_injected`, or `hook_request_origin`; the canonical hook
injects trust fields when the backend command runs. Do not include arbitrary
markdown body edits in `update`.

Lifecycle close or reopen payloads must not include metadata or refinement
fields. If the user asks for a lifecycle change plus another edit, run separate
preview/execute cycles so no requested field is silently dropped.

## Preview First

Write the requested scoped change to `PAYLOAD_PATH`, then run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_update.py prepare <PAYLOAD_PATH>
```

Show the returned preview and wait for explicit user confirmation before any
write. Do not treat the original update request as execute approval.

If the preview message includes `Refinement: will clear needs-refinement`, tell
the user that execution will remove the refinement metadata and tag.

If the user confirms, run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_update.py execute <PAYLOAD_PATH>
```

If the user edits the proposed change, update the same payload and rerun
`prepare` for the same `PAYLOAD_PATH`.

## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields in the transcript.

- `stale_plan`: say the preview is no longer current; rerun prepare and ask for
  confirmation again. Include the ticket ID when available: "Ticket <id>
  changed since preview; rerun the preview against the current ticket, then
  confirm again."
- `retry_preview`: say the saved preview state is no longer usable; rerun
  prepare and ask for confirmation again.
- `trust_setup`: stop without writing; say Ticket setup needs attention and
  suggest ticket-doctor diagnostics or plugin hook setup verification. The
  phrase "plugin hook setup" is allowed setup-level language; do not include
  hook/provenance field names or command-shape repair.
- `policy_blocked`: stop without writing; say the write is blocked by Ticket
  policy and the request or policy must change before retrying.
- `preflight_failed`: stop without writing; ask the user to review the check
  details, adjust the request, and rerun the preview.
