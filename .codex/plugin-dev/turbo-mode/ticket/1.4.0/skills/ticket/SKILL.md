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

Manages codebase tickets via the 4-stage engine pipeline (classify → plan → preflight → execute) for mutations, and `ticket_read.py` directly for reads.

**Reference:** See [references/pipeline-guide.md](references/pipeline-guide.md) for payload schemas, pipeline state propagation, and all 15 machine states.

---

## Setup (run once per skill invocation)

Resolve the plugin root and locate the tickets directory before any Bash commands. These two values are used throughout.

**Step 1 — Resolve plugin root:**
Set `PLUGIN_ROOT` to the plugin root directory two levels above this `SKILL.md`.
When executing commands, use the absolute path for `PLUGIN_ROOT`; do not pass an environment variable or relative path.

**Step 2 — Resolve tickets directory:**
```bash
git rev-parse --show-toplevel
```
Append `/docs/tickets`. Store as `TICKETS_DIR`.

**Step 3 — Prepare payload path (mutations only):**
```bash
mkdir -p .codex/ticket-tmp
```
Choose a unique payload filename: `.codex/ticket-tmp/payload-<action>-<YYYYMMDDTHHMMSSffffff>-<8hex>.json` (for example, `.codex/ticket-tmp/payload-create-20260305T142355123456-a1b2c3d4.json`). Store this relative path as `PAYLOAD_PATH` and reuse the same path for classify, plan, preflight, and execute. A timestamp-plus-random suffix avoids collisions with prior or concurrent operations.

---

## Routing

Dispatch on the first token of the text typed after `/ticket` (e.g., `/ticket create Fix auth bug` → operation is `create`) or the user's intent. If no operation is clear, ask: "What would you like to do? (create / update / close / reopen / list / query / audit)"

| Operation | Trigger phrases | Execution path |
|-----------|----------------|----------------|
| `create` | "create a ticket", "track this bug/feature" | Engine pipeline |
| `update` | "update ticket T-...", "change priority/status of T-..." | Engine pipeline |
| `close` | "close ticket T-...", "mark T-... done" | Engine pipeline |
| `reopen` | "reopen T-...", "T-... needs more work" | Engine pipeline |
| `list` | "list tickets", "show open tickets", "what's in-progress" | `ticket_read.py list` (direct) |
| `query` | "find ticket T-20260302", "show tickets from March 2" (ID-prefix match) | `ticket_read.py query` (direct) |
| `audit repair` | "repair audit log", "fix corrupt ticket audit trail", "ticket audit repair" | `ticket_audit.py repair` (direct, user-only) |

---

## Read Operations

Read operations call `ticket_read.py` directly — no engine pipeline, no payload file.

**List:**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_read.py list <TICKETS_DIR> [--status open|blocked|in_progress] [--priority high|critical] [--tag <tag>]
```

**Query (ID-prefix match — e.g., `T-20260302` matches `T-20260302-01`, `T-20260302-02`):**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_read.py query <TICKETS_DIR> <id_prefix>
```

Both return `{"state": "ok", "data": {"tickets": [...]}}` where each ticket has: `id`, `title`, `date`, `status`, `priority`, `tags`, `blocked_by`, `blocks`, `path`. Present as a table with ID, title, status, priority, and tags (if non-empty).

---

## Audit Utility

Use this path only when the user explicitly asks to inspect or repair corrupt audit logs. It is not part of the 4-stage engine pipeline.

**Repair audit logs:**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_audit.py repair <TICKETS_DIR> [--dry-run]
```

- `--dry-run` reports corrupt JSONL lines and writes nothing.
- Without `--dry-run`, the script creates a sibling backup `*.jsonl.bak-<YYYYMMDDTHHMMSSZ>` and rewrites the original file with only valid JSON-object lines.
- Report the JSON response summary to the user. This utility is user-only; do not use it for agent-origin requests.

---

## Mutation Operations

All mutations (create, update, close, reopen) follow this flow:

### Step 1: Extract fields from context

From the conversation history, extract:
- **create**: title (required), problem statement, priority (default: medium), key files, tags
- **update**: ticket ID (required), frontmatter fields to change (`status`, `priority`, `tags`, `effort`, `blocked_by`, `blocks`, `defer`)
- **close**: ticket ID (required), resolution (optional)
- **reopen**: ticket ID (required), reopen reason (required by engine)

`update` does not edit markdown body sections in v1.0. Requests to change sections like Problem or Approach must not be encoded as `update` fields.

### Step 2: Confirmation gate

**For update/close/reopen:** First read the existing ticket file to show current state:
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_read.py query <TICKETS_DIR> <ticket-id>
```

Present the proposed operation before writing any files. Use the template for the operation:

**create:**
```
I'll create a ticket with:
  Title: <title>
  Priority: <priority>
  Problem: <extracted problem statement>
  Key files: <extracted files if any>

Continue? [y / edit / n]
```

**update:** (show current state from the read above alongside proposed changes)
```
I'll update T-YYYYMMDD-NN:
  <field>: <current value> → <new value>
  (unchanged fields omitted)

Continue? [y / edit / n]
```

**close:**
```
I'll close T-YYYYMMDD-NN (status: <current status>):
  Resolution: <extracted resolution, or "none provided">

Continue? [y / edit / n]
```

**reopen:**
```
I'll reopen T-YYYYMMDD-NN (status: closed):
  Reason: <extracted reason>

Continue? [y / edit / n]
```

- `y` → proceed to pipeline
- `edit` → ask which fields to change, update, re-confirm
- `n` → stop

**Always confirm before calling execute.** Execute writes a ticket file to disk. Once written, tickets require manual removal — there is no undo. The confirmation gate is the only safety check before a permanent write.

### Step 3: Write initial payload

Write to `<PAYLOAD_PATH>` using the Write tool. See [references/pipeline-guide.md](references/pipeline-guide.md) for per-operation field schemas.

The top-level key for the operation is `action` (not `operation`). The payload file is the pipeline's running state — each stage enriches it. Construct the initial payload with all known fields; the engine fills in the rest.

### Step 4: Run the 4-stage pipeline

**The engine CLI is stateless** — each call reads the payload file, prints a response to stdout, and exits. It does NOT write stage outputs back to the file. After each stage, merge the response `data` fields into the payload and rewrite the file before the next call.

**Stage 1 — classify:**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_engine_user.py classify <PAYLOAD_PATH>
```
Parse stdout. Check `state`. If not `ok`, handle per Step 5 table. If `ok`, merge `response.data` directly into the payload and write it back. `classify` now emits both `intent` / `confidence` and the canonical preflight aliases `classify_intent` / `classify_confidence`.

**Stage 2 — plan:**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_engine_user.py plan <PAYLOAD_PATH>
```
Parse stdout. Check `state`. If `need_fields` or `duplicate_candidate`, handle loops (see [pipeline-guide](references/pipeline-guide.md)). If `ok`, merge `response.data` (adds `dedup_fingerprint`, `target_fingerprint`, `duplicate_of`) into the payload and write it back.

**Stage 3 — preflight:**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_engine_user.py preflight <PAYLOAD_PATH>
```
Parse stdout. Check `state`. If `ok`, merge `response.data` (adds `autonomy_config`) into the payload and write it back.

**Stage 4 — execute:**
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_engine_user.py execute <PAYLOAD_PATH>
```
Parse stdout. Check `state`. No payload write-back needed — execute writes the ticket file to disk.

Stop on any `state` not handled by a loop or the Step 5 table.

### Step 5: Handle the response state

Read `state` from the JSON response (`{"state": ..., "data": {...}}`):

| State | Action |
|-------|--------|
| `ok` | Report success and stop (generic — rare in pipeline context) |
| `ok_create` | Report success: "Created ticket T-YYYYMMDD-NN at docs/tickets/<slug>.md" |
| `ok_update` | Report: "Updated ticket T-..." with list of changed fields |
| `ok_close` / `ok_close_archived` | Report: "Closed ticket T-... (archived to closed-tickets/)" |
| `ok_reopen` | Report: "Reopened ticket T-... (status: open)" |
| `need_fields` | Ask user for missing fields (see [pipeline-guide](references/pipeline-guide.md#need_fields-loop)) |
| `duplicate_candidate` | Show duplicate match, ask for override (see [pipeline-guide](references/pipeline-guide.md#duplicate_candidate-loop)) |
| `preflight_failed` | Report failed checks from `data.checks_failed`, stop |
| `policy_blocked` | Report the policy message, stop |
| `invalid_transition` | Report current status and valid transitions, stop |
| `dependency_blocked` | Report unresolved and/or missing blocker IDs from the response data, stop |
| `not_found` | Report "Ticket T-... not found", stop |
| `escalate` | Report `message` (top-level field), stop |

---

## Troubleshooting

**Exit code 1:** Engine error. Read stderr for details.

**Exit code 2:** Validation failure. Check payload structure against [pipeline-guide.md](references/pipeline-guide.md).

**"Shell metacharacters detected":** A `$` appeared in the Bash command. Ensure you are using the resolved absolute `PLUGIN_ROOT` string from Step 1, not an environment variable.

**"Payload path outside workspace root":** The payload path must be inside the project root. Use `<PAYLOAD_PATH>` (relative), not `/tmp/...`.

**Guard hook blocks command:** Verify the invocation uses `python3` (not `python3.11` or `/usr/bin/python3`) and the full absolute `PLUGIN_ROOT` path (not a relative path).
