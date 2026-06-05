---
name: update-ticket
description: "Refine or change existing repo-local tickets. Use when the user asks to update a ticket, mark work open or blocked, close, reopen, change priority, edit tags, or add blockers. temporarily unavailable for writes until Ticket exposes the target candidate mutation path."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Update

Existing-ticket mutation is temporarily unavailable until source exposes a live
target-candidate entrypoint. Use `read-ticket` for inspection and summarize
requested updates without writing.

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

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This skill is source-authority guidance, not
installed-runtime proof and not runtime proof. This docs/tests slice does not
perform cutover inventory or normalization.

Durable runtime modes are `agent_primary` and `discussion_only`.

## Target Post-Cutover Ticket Shape

Target tickets use ID-only filenames, YAML frontmatter, and the sections
`Problem`, `Next Action`, and `Change History`.

Target frontmatter fields are `id`, `title`, `status`, `priority`, `tags`,
`related_paths`, and `blocked_by`. Target statuses are `idea`, `open`,
`blocked`, `done`, and `wontfix`. Target priorities are `high`, `normal`, and
`low`. `blocked_on` is the writable adapter for the visible `Blocked On`
section when moving into or out of `blocked`; `status: blocked` requires that
section to be non-empty. `blocked_by` is optional ticket-ID dependency data for
blocked tickets. When unblocking with `blocked -> open`, send `blocked_by: []`
and `blocked_on: null` together so live blocker IDs and visible blocker prose
clear in the same write. Unknown frontmatter keys are invalid. There is no
persisted reverse `blocks` edge; reverse blocker views are derived by scanning
tickets.

## Target Candidate Mutation Contract

Update candidates use the target mutation fields `action`, `ticket_id`,
`target.fields`, `target.sections`, `proposed_change`,
`expected_ticket_fingerprint`, and `evidence_summary`.

non-create writes require an expected ticket fingerprint. Ticket computes
candidate identity from canonical candidate content plus the live target
fingerprint; callers do not supply authoritative identity values. Unknown fields
are invalid.

Example target candidate:

```json
{
  "action": "update",
  "ticket_id": "T-20260518-01",
  "target": {
    "fields": ["priority"],
    "sections": ["Next Action"]
  },
  "proposed_change": {
    "priority": "high",
    "Next Action": "Add a focused regression test for close readiness."
  },
  "expected_ticket_fingerprint": "fingerprint",
  "evidence_summary": "The current branch changed the close-readiness rule."
}
```

Do not write `session_id`, `hook_injected`, or `hook_request_origin`; the
canonical hook injects trust fields.

## Target Result Envelope

The target result envelope uses only `ok`, `blocked`, `needs_discussion`,
`invalid_state`, and `no_change`.

## Target Change History Grammar

Target entries use:

```markdown
- <timestamp> | <actor> | <reason>
- <timestamp> | <actor> | <reason> Corrects: <reference>.
```

The actor is a source value such as `codex`, `user-approved`, or `migration`.
The actor is not a workflow label and must not encode action type.

## Active Update Guidance

Update mutation is temporarily unavailable from this skill until Ticket exposes
and documents a live source entrypoint that accepts the target candidate
mutation contract. Summarize the requested candidate and stop without writing.

## Deprecated Source Drift

Old update prepare-execute helper guidance is deprecated source drift only. It
is not active target mutation guidance.

Old focused update fields and old backend payloads are legacy cutover input
only.

## Maintenance And Diagnostics

Use maintenance diagnostics only when explicitly requested. Do not run old
update mutation commands as diagnostics for ordinary ticket updates.
