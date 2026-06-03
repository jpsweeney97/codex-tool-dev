---
name: capture-ticket
description: "Create repo-local tickets from natural language capture intent. Use when the user says to track, file, capture, ticket, or remember a bug, feature, follow-up, task, or cleanup item. temporarily unavailable for writes until Ticket exposes the target candidate mutation path. Do not trigger from casual statements like 'this is a bug' unless the user also asks to track or file it."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Capture

Capture intent is still a useful user signal, but active create mutation is
temporarily unavailable until source exposes a live target-candidate entrypoint.

## Setup

Resolve these paths before writing the payload or running commands:

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
`related_paths`, and `blocked_by`. Target statuses are `open`, `in_progress`,
`done`, and `wontfix`. Target priorities are `high`, `normal`, and `low`.
Unknown frontmatter keys are invalid. `blocked` is not a status; derive reverse
`blocks` views by scanning `blocked_by`.

## Target Candidate Mutation Contract

Create candidates use the target mutation fields `action`, `ticket_id`,
`target.fields`, `target.sections`, `proposed_change`,
`expected_ticket_fingerprint`, and `evidence_summary`.

non-create writes require an expected ticket fingerprint. Ticket computes
candidate identity from canonical candidate content plus the live target
fingerprint; callers do not supply authoritative identity values. Unknown fields
are invalid.

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

## Active Create Guidance

Create mutation is temporarily unavailable from this skill until Ticket exposes
and documents a live source entrypoint that accepts the target candidate
mutation contract. In `discussion_only`, any future user approval must be
tied to candidate identity before writing. This is approval tied to the
candidate identity, not general permission to write.

While unavailable, summarize the intended ticket in prose and stop without
writing.

Never store raw user wording: do not write verbatim transcript text, and do not
include `raw_user_text`, `raw_request`, or `transcript_excerpt`.

Do not
write `session_id`, `hook_injected`, or `hook_request_origin`; those
hook/provenance fields are hook-owned.

If the user asks to split multiple items, capture the first or clearest ticket.
After creation, show a suggested second capture prompt for the remaining item.

## Deprecated Source Drift

Deprecated source drift only: the old capture prepare-execute helper path is
not active target guidance.

Execute requires the prepared payload and hook/provenance path injected by the
canonical command path. Do not bypass the guard or use noncanonical commands.

## Legacy Cutover Input

Old capture payloads used capture fields such as title, problem, next action,
confidence, priority, tags, component, related paths, and acceptance criteria.
Those fields are legacy cutover input only.

## Maintenance And Diagnostics

Use maintenance diagnostics only when explicitly requested. Do not run old
capture mutation commands as diagnostics for ordinary ticket creation.
