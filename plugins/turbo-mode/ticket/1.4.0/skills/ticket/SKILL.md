---
name: ticket
description: "Manage codebase tickets: create, update, close, reopen, list, query, and repair corrupt audit logs. Use when the user says 'create a ticket', 'update ticket T-...', 'close ticket', 'reopen ticket', 'list tickets', 'show open tickets', 'find ticket about...', 'track this bug', 'log this issue', 'repair the ticket audit log', 'ticket audit repair', 'I want to remember this task', or asks to track a bug, feature, or task persistently — even if they don't say 'ticket' explicitly."
disable-model-invocation: true
argument-hint: "[create|update|close|reopen|list|query|audit repair] [ticket-id or details]"
allowed-tools:
  - Bash
  - Write
  - Read
---

# /ticket

Manages codebase tickets through the guided `ticket_workflow.py` runner for
mutations, and `ticket_read.py` directly for reads. The lower-level
classify/plan/preflight/execute pipeline remains documented in
`references/pipeline-guide.md` for debugging and implementation work.

## Setup (run once per skill invocation)

Resolve `PLUGIN_ROOT`, `PROJECT_ROOT`, and `TICKETS_DIR` before any Bash
commands. Keep them separate throughout the workflow.

### Step 1: Resolve plugin root

Set `PLUGIN_ROOT` to the plugin root directory three levels above this `SKILL.md`.

Example:
If this file is
`<PLUGIN_ROOT>/skills/ticket/SKILL.md`, `PLUGIN_ROOT` is three levels above
that installed skill file.

When executing commands, use the absolute path for `PLUGIN_ROOT`; do not pass
an environment variable or relative path.

### Step 2: Resolve project root

Set `PROJECT_ROOT` to the nearest ancestor of the current working directory
that contains `.codex`, `.git/`, or a `.git` file.

### Step 3: Resolve tickets directory

Set `TICKETS_DIR` to `<PROJECT_ROOT>/docs/tickets`.
Never derive `TICKETS_DIR` from `PLUGIN_ROOT`.

### Step 4: Prepare payload path for mutations

Run:

```bash
mkdir -p <PROJECT_ROOT>/.codex/ticket-tmp
```

Choose a unique payload filename under
`<PROJECT_ROOT>/.codex/ticket-tmp/` and store it as an absolute `PAYLOAD_PATH`.
Reuse the same `PAYLOAD_PATH` for `prepare`, `recover`, and `execute`. Do not
use a relative payload path.

## Routing

Dispatch on the first token of the text typed after `/ticket`, or infer the
operation from user intent. If no operation is clear, ask:
"What would you like to do? (create / update / close / reopen / list / query / audit)"

| Operation | Trigger phrases | Execution path |
|-----------|----------------|----------------|
| `create` | "create a ticket", "track this bug/feature" | `ticket_workflow.py prepare` then `ticket_workflow.py execute` |
| `update` | "update ticket T-...", "change priority/status of T-..." | `ticket_workflow.py prepare` then `ticket_workflow.py execute` |
| `close` | "close ticket T-...", "mark T-... done" | `ticket_workflow.py prepare` then `ticket_workflow.py execute` |
| `reopen` | "reopen T-...", "T-... needs more work" | `ticket_workflow.py prepare` then `ticket_workflow.py execute` |
| `list` | "list tickets", "show open tickets", "what's in-progress" | `ticket_read.py list` (direct) |
| `query` | "find ticket T-20260302", "show tickets from March 2" | `ticket_read.py query` (direct) |
| `audit repair` | "repair audit log", "fix corrupt ticket audit trail", "ticket audit repair" | `ticket_audit.py repair` (direct, user-only) |

## Read Operations

Read operations call `ticket_read.py` directly. They do not use the workflow
runner.

### List

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_read.py list <TICKETS_DIR> [--status open|blocked|in_progress] [--priority critical|high|medium|low] [--tag <tag>]
```

### Query

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_read.py query <TICKETS_DIR> <id_prefix>
```

### Check close readiness

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_read.py check <TICKETS_DIR> <ticket_id> [--resolution done|wontfix]
```

Use `check` before closing a ticket when the user asks whether it is ready to
close, or when close fails because acceptance criteria or blockers are missing.

`list` and `query` return display metadata for ticket identity, status labels,
priority labels, sort keys, and query-match context. Present read output as a
compact table using ticket ID first and filename/path second.

## Audit Utility

Use this path only when the user explicitly asks to inspect or repair corrupt
audit logs.

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_audit.py repair <TICKETS_DIR> [--dry-run]
```

## Mutation Operations

All mutations use the guided workflow runner.

### Step 1: Extract fields from context

From the conversation history, extract:
- create: `title` (required), `problem`, `priority`, optional tags and file context
- update: `ticket_id` plus frontmatter fields to change
- close: `ticket_id` plus optional `resolution`
- reopen: `ticket_id` plus `reopen_reason`

`update` does not edit markdown body sections in v1.0. Requests to change
section content belong in manual ticket editing or future tooling, not
`update` fields.

### Step 2: Write the initial payload

Write a JSON payload to `PAYLOAD_PATH`. The top-level operation key is
`action`.

### Step 3: Prepare the change

Run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_workflow.py prepare <PAYLOAD_PATH>
```

The workflow runner executes classify, plan, preflight, and read-only
execute-policy checks, writes enriched state back to the payload, and returns a
Unified Preview. Do not call `execute` until the user confirms the preview.

`PAYLOAD_PATH` must be absolute and must not contain whitespace. If it does,
recreate the payload under `<PROJECT_ROOT>/.codex/ticket-tmp/` before running
workflow commands.

### Step 4: Unified Preview

Show the returned preview before any write:

```text
Proposed ticket change

Action: Create
Ticket: new
Will write: docs/tickets/
Status: open
Priority: high
Tags: auth, retry
Close-ready: yes
Potential duplicate: none

Proceed? [y / edit / cancel]
```

If the user chooses:
- `y`: continue to execute
- `edit`: update the payload or use a recovery path, then rerun `prepare`
- `cancel`: stop

### Step 5: Execute after confirmation

Run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_workflow.py execute <PAYLOAD_PATH>
```

### Step 6: Report the result

Interpret `state` from stdout JSON:

| State | Action |
|-------|--------|
| `ready_to_execute` | Show preview and wait for confirmation |
| `ok_create` | Report the created ticket ID and path |
| `ok_update` | Report changed fields |
| `ok_close` / `ok_close_archived` | Report close success and archive status |
| `ok_reopen` | Report reopen success |
| `need_fields` / `duplicate_candidate` / `invalid_transition` / `dependency_blocked` | Use Recovery Options |
| `policy_blocked` | Show the policy message and stop |
| `not_found` | Show the searched ticket ID and stop |
| `escalate` | Show the message and stop |

## Recovery Options

When a workflow response includes `data.recovery_options`, show the available
choices. If the user selects an option with `recover_command`, run the returned `recover_command`
exactly, then rerun `ticket_workflow.py prepare` for the same
`PAYLOAD_PATH`. If the user selects an option with
`suggested_ticket_command`, show that command and ask before running it. Do not
invent label-only recovery actions.

| State | User-facing message | Offer |
|-------|---------------------|-------|
| `need_fields` | More information needed | Ask for one missing field at a time |
| `duplicate_candidate` | Potential duplicate found | update existing via `suggested_ticket_command` / create anyway via `recover_command` / cancel |
| `invalid_transition` | Status change is not allowed | check readiness / choose valid status via `recover_command` / cancel |
| `dependency_blocked` | Blocking tickets are unresolved | resolve blockers via `suggested_ticket_command` / close as wontfix via `recover_command` / cancel |
| `policy_blocked` | Blocked by ticket policy | show policy message and stop |
| `not_found` | Ticket not found | show searched ID and suggest `/ticket list` |

Example sequence:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_workflow.py recover <PAYLOAD_PATH> create_anyway
python3 -B <PLUGIN_ROOT>/scripts/ticket_workflow.py prepare <PAYLOAD_PATH>
```

## Reference

Use `references/pipeline-guide.md` when you need lower-level payload schemas,
stage-by-stage engine details, or direct engine debugging commands.

## Troubleshooting

If the guard hook blocks a command, verify all of the following:
- the launcher is exactly `python3 -B`
- the script path is exactly `<PLUGIN_ROOT>/scripts/...`
- `PAYLOAD_PATH` is absolute
- `PAYLOAD_PATH` does not contain whitespace
- the payload lives inside the active workspace root
