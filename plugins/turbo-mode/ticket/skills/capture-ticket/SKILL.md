---
name: capture-ticket
description: "Create repo-local tickets from natural language capture intent. Use when the user says to track, file, capture, ticket, or remember a bug, feature, follow-up, task, or cleanup item. Infer aggressively, synthesize a compact ticket preview, and require explicit confirmation before writing. Do not trigger from casual statements like 'this is a bug' unless the user also asks to track or file it."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Capture

Create one repo-local ticket from capture intent. Infer useful ticket fields,
show a compact preview, and write only after explicit user confirmation.

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

## Capture Payload

Synthesize the payload from conversation context. Never store raw user wording:
do not write verbatim transcript text, and do not include `raw_user_text`,
`raw_request`, or `transcript_excerpt`.

Write a JSON object to `PAYLOAD_PATH` with a `capture` object only. Do not
write `session_id`, `hook_injected`, or `hook_request_origin`; those
hook/provenance fields are hook-owned and injected by the canonical command
path.

- `capture.title`: short synthesized title.
- `capture.captured_request`: synthesized summary of the requested work.
- `capture.problem`: 1-2 synthesized sentences explaining the issue or need.
- `capture.next_action`: one concrete next step.
- `capture.capture_confidence`: `low`, `medium`, or `high`.
- `capture.priority`: `critical`, `high`, `medium`, or `low`.
- `capture.tags`: controlled tags only: `needs-refinement`, `bug`, `feature`,
  `docs`, `test`, `maintenance`, and `security`.
- `capture.component`: optional compact component name.
- `capture.related_paths`: repo-relative paths when useful.
- `capture.acceptance_criteria`: concise, checkable criteria.

Use deterministic inference boundaries:

- Default priority to `medium`.
- Set priority to `critical` only for explicit production, data-loss, security,
  or release-blocking language.
- Set priority to `high` only for explicit blocker, regression, CI-red, or
  cannot-ship language.
- Set priority to `low` only for explicit cleanup, polish, or nice-to-have
  language.
- Do not invent component tags.
- Set `related_paths` only from explicit user text and files immediately
  discussed in the current turn. Do not scan the whole git diff by default.
- Set `component` only when user-supplied or obvious from explicit paths.

Infer aggressively. Ask one follow-up only when no useful `next_action` can be
synthesized. For vague but actionable captures, use `capture_confidence: low`
and concrete acceptance criteria instead of asking for more detail.

If the user asks to split multiple items, capture the first or clearest ticket.
After creation, show a suggested second capture prompt for the remaining item.

## Prepare

Run:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_capture.py prepare <PAYLOAD_PATH>
```

If the response needs fields, ask for one missing field at a time. If the
response is policy-blocked, show the policy message and stop.

Show the preview in exactly this compact shape:

```text
Capture ticket

Title: <synthesized title>
Problem: <1-2 sentence synthesized problem>
Next action: <single concrete next step>
Confidence: low|medium|high
Duplicate: none | possible T-... "<title>"

Create this ticket? [create / edit / cancel]
```

Show `Priority: <priority>` only when priority is not `medium` or confidence is
`low`. Do not show hidden payload fields unless the user asks.

## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields in the transcript.

- `stale_plan`: say the preview is no longer current; rerun prepare and ask for
  confirmation again.
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

## User Choice

- `create`: run execute for the same `PAYLOAD_PATH`.
- `edit`: safely update the payload with the scoped edit, then rerun the
  canonical prepare command for the same `PAYLOAD_PATH`. Do not put free-form
  edit text on the shell command line.
- `cancel`: stop without writing a ticket.

Require explicit `create` confirmation before writing. Do not treat silence,
approval-like wording outside this prompt, or earlier intent to track as execute
approval.

## Execute

After the user chooses `create`, run:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_capture.py execute <PAYLOAD_PATH>
```

Execute requires the prepared payload and hook/provenance path injected by the
canonical command path. If execute returns `policy_blocked`, `preflight_failed`,
or another non-success state, show the returned message and stop. Do not bypass
the guard or use noncanonical commands.

Report the created ticket ID and path from the JSON response.
