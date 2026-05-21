# Ticket Plugin — Operator Handbook

## Overview

The ticket plugin provides capture-first structured work tracking for Codex sessions. It manages tickets as markdown files with YAML frontmatter. New-ticket creation is user-facing through `ticket-capture`; existing-ticket lifecycle, metadata, and focused refinement mutations use `ticket_update.py` while preserving the underlying 4-stage mutation pipeline (classify → plan → preflight → execute) for engine dispatch and debugging.

**Scope:** Ticket capture, existing-ticket lifecycle mutations, scoped frontmatter metadata updates, read queries, backlog health review, explicit diagnostics, and audit trail repair.

**Not covered:** External issue tracker integrations, UI rendering, cross-project ticket syncing, or agent-orchestration workflows (roadmap).

**Source scope:** This handbook describes the source-authority package at
`plugins/turbo-mode/ticket/` in `/Users/jp/Projects/active/codex-tool-dev`.
Installed cache and runtime artifacts are separate proof surfaces and may
diverge until an explicit cache-refresh or runtime-proof lane verifies them.
Source edits here do not prove installed Codex behavior.

---

## At a Glance

### Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `ticket-capture` | `skills/ticket-capture/SKILL.md` | Capture new tickets from natural language after preview confirmation |
| `ticket-find` | `skills/ticket-find/SKILL.md` | Read-only show, list, query, and close-readiness checks |
| `ticket-update` | `skills/ticket-update/SKILL.md` | Existing-ticket lifecycle and frontmatter metadata updates |
| `ticket-review` | `skills/ticket-review/SKILL.md` | Read-only backlog health, stale, blocked, and next-action review |
| `ticket-doctor` | `skills/ticket-doctor/SKILL.md` | Explicit-only storage/plugin diagnostics, stale payload cleanup, and audit repair |

Generic creation through the old broad `ticket` skill is no longer user-facing.
Low-confidence captures are allowed when a next action exists; they should carry
`refinement_status: needs_refinement`. `needs_refinement` is metadata, not a lifecycle status.

### CLI Entrypoints

| Script | Origin | Purpose |
|--------|--------|---------|
| `scripts/ticket_engine_user.py` | User | Mutation pipeline with `request_origin="user"` |
| `scripts/ticket_engine_agent.py` | Agent | Mutation pipeline with `request_origin="agent"` (autonomy-gated) |
| `scripts/ticket_capture.py` | User | Capture-first prepare/execute workflow for new tickets |
| `scripts/ticket_update.py` | User | Preview-first prepare/execute workflow for existing tickets |
| `scripts/ticket_review.py` | Any | User-facing read-only review and audit wrapper |
| `scripts/ticket_doctor.py` | User | Explicit-only diagnostics and dry-run-first audit repair wrapper |
| `scripts/ticket_workflow.py` | Any | Internal/debugging legacy prepare/execute/recover workflow runner |
| `scripts/ticket_read.py` | Any | Read-only: list, query by ID-prefix, and close-readiness check |
| `scripts/ticket_triage.py` | Any | Read-only: dashboard counts, stale/blocked detection, audit summary |
| `scripts/ticket_audit.py` | Any | Audit trail validation and corrupt-line repair |

Canonical Bash launcher for these scripts:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <PROJECT_ROOT>/docs/tickets
```

### Supported Mutation Surfaces

Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`.

- `capture`: `ticket_capture.py prepare` then `ticket_capture.py execute`
- `update`: `ticket_update.py prepare` then `ticket_update.py execute`
- `ingest`: `ticket_engine_user.py ingest <payload_file>` or `ticket_engine_agent.py ingest <payload_file>`

`capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths, not normal user-facing mutation interfaces.

`ticket_workflow.py` is a compatibility/debug runner kept for tests and
low-level recovery work, not a supported user-facing mutation surface.

### Recovery Hints

User-facing mutation and recovery surfaces may include `data.recovery_hint`.
When present, it is safe to show directly to a human user. Valid codes are
`stale_plan`, `trust_setup`, `retry_preview`, `cleanup_stale_preview`,
`policy_blocked`, and `preflight_failed`.

The schema is `{"code": "...", "summary": "...", "next_step": "..."}`. The
whole object is transcript-safe. `plugin hook setup` is allowed only as
setup-level recovery wording for `trust_setup`; hook/provenance field names and
command repair instructions remain internal.

Ingest stdout is a machine-readable JSON envelope. Skills and transcript-facing
workflows must parse it and render only the allowlisted projection: recovery
summary, recovery next step, safe message, ticket ID, duplicate candidate ticket
ID, and user-safe ingest outcome prose. Raw `data` fields such as processed
paths, incoming envelope paths, and envelope provenance are not transcript
fields.

### Hook

| Hook | Event | Purpose |
|------|-------|---------|
| `hooks/ticket_engine_guard.py` | `PreToolUse` (Bash) | Validates commands, injects trust fields, blocks metacharacters and path traversal |

---

## Core Components

### Pipeline Stages

| File | Responsibility | Key Dependencies |
|------|----------------|-----------------|
| `scripts/ticket_engine_core.py` | Orchestrates 4 stages; parses `AutonomyConfig`; writes audit trail | `ticket_parse`, `ticket_render`, `ticket_validate`, `ticket_id`, `ticket_dedup`, `ticket_paths`, `ticket_trust` |
| `scripts/ticket_engine_runner.py` | CLI dispatcher: parses args, reads JSON payload, calls stage function, prints response | `ticket_engine_core` |

### Pipeline Inputs

| File | Responsibility |
|------|----------------|
| `scripts/ticket_stage_models.py` | Dataclass boundary models: `ClassifyInput`, `PlanInput`, `PreflightInput`, `ExecuteInput` |

### Support Modules

| File | Responsibility |
|------|----------------|
| `scripts/ticket_parse.py` | Markdown → structured; resolves Gen 1/2/3 legacy ID formats |
| `scripts/ticket_render.py` | Structured → markdown with canonical YAML serialization and fixed section ordering |
| `scripts/ticket_validate.py` | Field schema validation; rejects unknown keys in mutation payloads |
| `scripts/ticket_id.py` | ID allocation: `T-YYYYMMDD-NN` format, scans live tickets for next slot |
| `scripts/ticket_dedup.py` | SHA-256 fingerprint of normalized problem + key file paths; 24-hour window |
| `scripts/ticket_paths.py` | Project root discovery (nearest `.codex/` or `.git/`); path containment validation |
| `scripts/ticket_trust.py` | Trust triple validation: `session_id`, `hook_injected`, `request_origin` consistency |
| `scripts/ticket_triage.py` | Dashboard aggregation; stale/blocked chain detection; `.audit/` JSONL aggregation |
| `scripts/ticket_read.py` | Query engine: filters by status/priority/tag, ID-prefix lookup |
| `scripts/ticket_audit.py` | Reads `.audit/YYYY-MM-DD/*.jsonl`; validates and repairs corrupt lines with backups |

### Entrypoints

| File | Responsibility |
|------|----------------|
| `scripts/ticket_engine_user.py` | Sets `request_origin="user"`, delegates to `ticket_engine_runner` |
| `scripts/ticket_engine_agent.py` | Sets `request_origin="agent"`, delegates to `ticket_engine_runner` |

### Hook

| File | Responsibility |
|------|----------------|
| `hooks/ticket_engine_guard.py` | Tokenizes Bash commands with `shlex`; allowlists canonical endpoints; injects trust fields atomically |

---

## Configuration and Bring-Up

### Prerequisites

- Python ≥ 3.11
- `pyyaml` ≥ 6.0
- A project with a `.git/` or `.codex/` directory (required for project root discovery)
- For installed-runtime checks, explicit install/cache-refresh evidence is
  required; this source checkout alone is not runtime proof

### Autonomy Configuration

Create `.codex/ticket.local.md` at the project root to configure agent behavior. The file must include YAML frontmatter:

```yaml
---
autonomy_mode: suggest
max_creates_per_session: 5
---
```

| Key | Default | Values | Purpose |
|-----|---------|--------|---------|
| `autonomy_mode` | `suggest` | `suggest`, `auto_audit` | `suggest`: only user mutations allowed. `auto_audit`: agent mutations allowed with audit trail. |
| `max_creates_per_session` | `5` | integer, `0` = disabled | Per-session agent create cap; tracked in audit trail |

If `.codex/ticket.local.md` is absent, the plugin defaults to `autonomy_mode: suggest` and `max_creates_per_session: 5`.

### Path Resolution

No shell environment variable is required. Skills resolve `PLUGIN_ROOT` from their installed skill path, the hook resolves it from the parent of `hooks/`, and `PROJECT_ROOT` is discovered by walking up from the current working directory to the nearest `.codex`, `.git/`, or `.git` marker.

### Tickets Directory

The `tickets_dir` defaults to `<project_root>/docs/tickets/`. Read, triage, and audit scripts accept it as a positional argument. Engine entrypoints resolve it from the payload or use the default. In every case it must resolve inside the project root — path traversal is blocked.

The `.audit/` subdirectory (`docs/tickets/.audit/`) is created automatically on the first agent mutation.

---

## Operating Model

### Trust Model

Every mutation must carry a **trust triple** injected by the hook:

| Field | Source | Purpose |
|-------|--------|---------|
| `session_id` | Hook (`event.session_id`) | Session identity; sanitized (no `/`, `\`, `\0`) before filesystem use |
| `hook_injected` | Hook | Proves request passed through the hook |
| `hook_request_origin` | Hook | Hook-observed provenance metadata; current runtime may report `"user"` even for the certified direct-execute lane, and activation readiness does not treat it as caller identity |

The hook injects these fields atomically into the payload file before allowing
the Bash command to proceed. At classify and execute stages, the engine
re-validates the trust triple against the selected policy lane. Missing or
malformed trust data rejects with an error, and the certified direct-execute
lane accepts the current host's `hook_request_origin="user"` observation as
provenance metadata rather than caller identity.

**Flow:** Hook validates and injects → entrypoint selects a policy lane →
pipeline re-validates the triple.

### Autonomy Enforcement

Agent mutations face additional gating that user mutations do not:

1. **Preflight reads** `autonomy_mode` from `.codex/ticket.local.md`. If mode is `suggest`, agent mutations are blocked entirely.
2. **Execute re-reads** the config and re-checks. A config change between preflight and execute is caught at execute.
3. **Session create cap** is enforced at execute by counting prior agent creates in the audit trail for the current session.

User mutations skip the autonomy policy check — they pass through regardless of `autonomy_mode`.

Activation V1 certifies only `ticket_engine_agent.py execute`. Activation V1
proves installed hook-mediated direct-execute wiring, not host-owned or
spawned-agent identity. `hook_request_origin` is hook-observed provenance
metadata on the current host and may still be reported as `"user"` for the
certified direct-execute lane. `capture`, `update`, and `ticket_workflow.py`
remain outside the activation proof scope and require a separate follow-up
before widening certification. `dangerFullAccess` runs and prompt-driven smokes
are diagnostics only. AgentControl child smoke, when captured, is
same-membrane corroboration only and not identity proof. Normal agent direct
execute fails with `runtime_readiness_required` when the runtime proof is
missing, stale, or mismatched.

`auto_audit` is single-writer in this slice. Do not intentionally launch two or more ticket-capable agents in the same Codex session. Future locking/queueing work is triggered by any workflow that intentionally launches two or more ticket-capable agents in the same Codex session, or enables `auto_audit` for delegated multi-agent work.

### Audit Trail

Located at `docs/tickets/.audit/YYYY-MM-DD/*.jsonl`. Each line is a JSON object recording one mutation event with action, result, session, and payload snapshot.

- **Agent mutations:** Audit trail write is fail-closed. If the write fails, the mutation is blocked.
- **User mutations:** Audit trail write is advisory. If the write fails, the mutation proceeds.

---

## Component Runbooks

### `ticket-capture` skill

**When to use**
Use when the user asks to track, file, capture, ticket, or remember a bug,
feature, follow-up, task, or cleanup item. This is the only user-facing generic
creation surface.

**Flow**
1. Resolve plugin root from the skill's own directory
2. Resolve `PROJECT_ROOT` from the current working directory
3. Determine `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. Synthesize a capture payload with title, problem, next action, confidence,
   priority, tags, component, related paths, and acceptance criteria
5. Run `ticket_capture.py prepare` and show the compact preview
6. Execute only after explicit `create` confirmation

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| `error: trust_triple_invalid` | Hook not running or trust fields absent | Verify `hooks/ticket_engine_guard.py` is registered in `settings.json` |
| `error: path_traversal` | `tickets_dir` resolves outside project root | Confirm project has `.git/` or `.codex/` at expected root |
| `error: dedup_collision` | Same problem+files created within 24 hours | Review existing open tickets with `ticket-find`; update the duplicate instead |
| Mutation silently rejected | `autonomy_mode: suggest` blocks agent mutations | User must perform the mutation, or set `autonomy_mode: auto_audit` |

---

### `ticket-find` skill

**When to use**
Show, list, search, open, or check close readiness for tickets. This skill is
read-only and calls only `ticket_read.py list`, `query`, and `check`.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Resolve `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. Run the requested `ticket_read.py` command
5. For ordinary open-work output, group `refinement_status: needs_refinement`
   tickets separately from ready open work

---

### `ticket-update` skill

**When to use**
Update an existing ticket's lifecycle, priority, tags, blockers, component,
related paths, or focused refinement fields. Do not use it for arbitrary
body-section editing in v1. Source, defer, and capture provenance metadata are
not supported by `ticket_update.py` in v1. Placeholder problem, next action, and
acceptance criteria refinement uses the focused `ticket_update.py` backend.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Create an absolute payload under `<PROJECT_ROOT>/.codex/ticket-tmp/`
4. Run `ticket_update.py prepare`
5. Show the preview and wait for explicit confirmation
6. Run `ticket_update.py execute` only after confirmation

---

### `ticket_update.py`

Use for user-facing existing-ticket mutations. `prepare` validates scoped
lifecycle, metadata, and focused refinement fields, then returns a preview.
`execute` performs the write after user confirmation. These workflow commands
require canonical Bash invocation so the guard hook can inject trust fields.
Payload paths must be absolute, must live inside the active workspace root, and
must not contain whitespace. Recreate unsupported payloads under a path such as
`<PROJECT_ROOT>/.codex/ticket-tmp/payload.json`.

---

### `ticket_workflow.py`

Use as an internal/debugging legacy workflow runner when diagnosing the
lower-level mutation pipeline. `ticket_workflow.py` is a compatibility/debug
runner. It is not the current user-facing update path.
`prepare` hydrates a legacy payload, `execute` performs the write after user
confirmation, and `recover` applies supported user-selected payload patches.

---

### `ticket-review` skill

**When to use**
Read-only health check for the ticket backlog. Surfaces stale tickets, blocked
dependency chains, audit activity, and next-action recommendations. It may
suggest `ticket-capture` prompts but must not write tickets.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Resolve `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. Run `ticket_review.py review` → counts by status, stale list, blocked chain detection, size warnings
5. Run `ticket_review.py audit` → aggregate by action/result/session from `.audit/` JSONL
6. Format and render recommendations

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| No audit data shown | `.audit/` directory absent | No agent mutations have occurred yet; expected for user-only workflows |
| Stale threshold seems wrong | Old tickets lack `updated` field | Triage falls back to file mtime — results may be approximate |

---

### `ticket-doctor` skill

**When to use**
Explicit maintenance only: diagnose ticket storage, validate plugin health, or
repair corrupt audit logs. Casual audit, triage, or review language belongs to
`ticket-review`.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Resolve `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. For live installed activation, use the cache-installed runtime authority that
   `hooks/list` and `skills/list` expose. Treat the synced personal plugin copy
   as staging only, not the proof target.
5. For diagnostics, run `ticket_doctor.py diagnose`
6. For stale payload cleanup, run `ticket_doctor.py clean-stale-payloads <TICKETS_DIR>` first
7. Run `ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads` only after explicit approval
8. For audit repair, run `ticket_doctor.py repair-audit`
9. Run `ticket_doctor.py repair-audit --confirm-repair` only after explicit approval

**Stale payload cleanup:** `ticket_doctor.py diagnose` reports stale
`.codex/ticket-tmp/` payloads older than 24 hours without mutating them.
Cleanup is TTL-scoped to stale JSON payloads under
`<PROJECT_ROOT>/.codex/ticket-tmp/` and is confirmation-gated with
`--confirm-clean-stale-payloads`.

---

### `ticket_engine_user.py` / `ticket_engine_agent.py`

**When to use**
Called by skills to execute the 4-stage mutation pipeline. `ticket_engine_user.py` for interactive user operations; `ticket_engine_agent.py` for autonomous agent mutations.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_engine_user.py <subcommand> <payload_json_path>
uv run python -B <PLUGIN_ROOT>/scripts/ticket_engine_agent.py <subcommand> <payload_json_path>
```

Valid subcommands: `classify`, `plan`, `preflight`, `execute`, `ingest`.

**Response envelope**
```json
{
  "state": "<machine_state>",
  "ticket_id": "<string|null>",
  "message": "human-readable result",
  "data": { ... },
  "error_code": "<string on failure only>"
}
```

Success responses omit `error_code`; error responses include it at the top level.

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| `error_code: origin_mismatch` | Origin in payload doesn't match entrypoint | Do not call agent entrypoint with user-origin payload, or vice versa |
| `state: policy_blocked` | Agent mutations attempted under `suggest` mode | Set `autonomy_mode: auto_audit` in `.codex/ticket.local.md` |
| `state: policy_blocked` | Per-session create limit reached | Raise `max_creates_per_session` or start a new session |
| `state: duplicate_candidate` | Matching ticket exists within 24 hours | Use the returned `ticket_id` to update the existing ticket instead |

---

### `ticket_read.py`

**When to use**
List or query tickets without triggering the mutation pipeline. Safe to run at any time; no writes.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <tickets_dir> [--status open|blocked|in_progress] [--priority high|critical] [--tag <tag>]
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py query <tickets_dir> <id_prefix>
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py check <tickets_dir> <ticket_id> [--resolution done|wontfix]
```

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Empty results | Tickets directory doesn't exist | Verify `docs/tickets/` exists in project root |
| Parse errors in output | Malformed ticket YAML | Run `ticket_audit.py` to identify corrupt files |

---

### `ticket_triage.py`

**When to use**
Lower-level health check backend; called by `ticket_review.py`. Produces dashboard and audit summary without mutations.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <tickets_dir>
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py audit <tickets_dir> [--days <N>]
```

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Blocked chain not detected | Cycle in `blocked_by`/`blocks` graph | Manual review; triage detects linear chains only, not cycles |

---

### `ticket_audit.py`

**When to use**
Lower-level audit repair backend; called by `ticket_doctor.py repair-audit`.
Direct use is for debugging. User-facing repair should go through
`ticket_doctor.py`, which always dry-runs first.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_audit.py repair <tickets_dir> [--dry-run]
```

**Behavior:** Reads all `.audit/YYYY-MM-DD/*.jsonl` files, validates each line as parseable JSON. In repair mode: rewrites files with corrupt lines replaced, backs up originals with ISO8601 timestamp suffix.

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Cross-line corruption not repaired | JSONL is line-delimited; multi-line corruption not handled | Recover from the ISO8601-suffixed backup created during the repair run |

---

### `ticket_engine_guard.py` hook

**When to use**
Registered as `PreToolUse` hook in `settings.json`. Runs automatically before any Bash tool call. Not invoked directly.

**What it enforces**
- Allowlists only canonical plugin endpoint paths using `uv run python -B <ABS_PLUGIN_ROOT>/scripts/...`
- `python3` launchers may still be accepted as legacy compatibility, but `uv run python -B` is the documented public launcher form
- Rejects shell metacharacters: `|`, `;`, `` ` ``, `$`, `&`, `<`, `>`, newlines
- Validates that payload file paths resolve inside `event.cwd`
- Injects `session_id`, `hook_injected`, `hook_request_origin` into the payload atomically

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Ticket commands pass through without trust fields | Hook not registered | Verify `hooks/ticket_engine_guard.py` appears in `settings.json` hooks array |
| `denied: shell_metachar` on a valid command | Command constructed with shell features | Use plain argument passing; no subshells or pipes in ticket commands |
| `denied: path_outside_cwd` | Payload path resolves outside working directory | Launch Codex from the project root containing `.git/` or `.codex/` |

---

## Internals

### 4-Stage Mutation Pipeline

Every mutation traverses all four stages in sequence. A stage failure stops the pipeline and returns an error — no partial writes occur.

```
Input payload (JSON)
       │
       ▼
 ┌─────────────┐
 │  CLASSIFY   │  Intent resolution: infer operation (create/update/close/reopen)
 │             │  from payload fields. Confidence scored; ambiguous intents error.
 └──────┬──────┘  Validates trust triple consistency.
        │
        ▼
 ┌─────────────┐
 │    PLAN     │  Field validation: checks required fields, resolves defaults,
 │             │  rejects unknown keys. Runs dedup fingerprint check (SHA-256
 └──────┬──────┘  of normalized problem + key file paths). 24-hour window.
        │
        ▼
 ┌─────────────┐
 │  PREFLIGHT  │  Policy enforcement: reads autonomy config from
 │             │  .codex/ticket.local.md. Blocks agent mutations if
 └──────┬──────┘  autonomy_mode = suggest. Validates status transitions
        │         against dependency graph. Takes TOCTOU fingerprint snapshot.
        ▼
 ┌─────────────┐
 │   EXECUTE   │  Re-reads autonomy config (catches mid-flight config changes).
 │             │  Re-checks TOCTOU snapshot. Dispatches file write (exclusive
 └─────────────┘  creation with bounded retry). Writes audit trail (fail-closed
                  for agent requests). Increments session create counter.
```

### Status Transitions

Key transition rules:

- `open` → `in_progress` requires no extra fields
- `open` or `in_progress` → `blocked` requires non-empty `blocked_by`
- `open`, `in_progress`, or `blocked` → `done` requires an Acceptance Criteria section
- `*` → `wontfix` is allowed
- `done` or `wontfix` → `open` requires `reopen_reason` and is user-only in v1.0

### ID Allocation

IDs follow `T-YYYYMMDD-NN` format (e.g., `T-20260309-01`). The allocator scans live tickets to find the next available `NN` for today, zero-padded to 2 digits. Under concurrent load, exclusive file creation (`O_EXCL`) is used with bounded retry — but parallel subagent creates are not fully serialized (see Known Limitations).

### TOCTOU Protection

At preflight, the engine takes a fingerprint snapshot of any existing ticket being mutated. At execute, it re-reads and re-fingerprints before writing. If the live file changed between stages, the mutation is blocked with the public `stale_plan` error code. `toctou_conflict` is descriptive prose only, not a public error code.

---

## Failure and Recovery Matrix

| Symptom | Likely Cause | Diagnosis | Recovery |
|---------|-------------|-----------|---------|
| All agent mutations rejected | `autonomy_mode: suggest` (default) | Check `.codex/ticket.local.md`; absent file → defaults to `suggest` | Set `autonomy_mode: auto_audit` in `.codex/ticket.local.md` |
| `trust_triple_invalid` error | Hook not running | Check `settings.json` for hook registration | Register `hooks/ticket_engine_guard.py` as PreToolUse hook |
| `trust_triple_mismatch` error | Agent entrypoint called with user payload | Inspect `request_origin` in payload vs entrypoint | Ensure skill routes mutations to correct entrypoint |
| `dedup_collision` on first create | Another ticket with same problem exists within 24 hours | Run `ticket_read.py list` and look for near-duplicate | Update existing ticket; or override dedup if content is genuinely distinct |
| `session_cap_exceeded` | Agent created ≥ `max_creates_per_session` tickets this session | Check `max_creates_per_session` in `.codex/ticket.local.md` | Raise cap or start a new session |
| `audit_write_failed` blocks agent mutation | Disk full, permission error, or `.audit/` not writable | Check disk space and permissions on `docs/tickets/.audit/` | Fix underlying issue; mutation will proceed once audit write succeeds |
| `stale_plan` on update | Concurrent write between preflight and execute | Inspect ticket file mtime | Re-run update after verifying current state |
| Corrupt audit JSONL lines | Interrupted write (crash during mutation) | Run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <tickets_dir>` | After explicit approval, run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <tickets_dir> --confirm-repair` |
| Stale `.codex/ticket-tmp/` payloads | Interrupted or abandoned prepare/execute flow | Run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py diagnose <tickets_dir> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT>` | After explicit approval, run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads` |
| Stale tickets not surfaced by triage | Missing `updated` field in old ticket YAML | Inspect ticket frontmatter | Triage falls back to file mtime; results are approximate for legacy tickets |
| `path_outside_cwd` from hook | Project root not at Codex launch directory | Check hook's `event.cwd` vs actual tickets path | Launch Codex from the project root containing `.git/` or `.codex/` |

---

## Known Limitations

**Single-writer `auto_audit` boundary:** Session create cap and ID allocation are not fully serialized for intentional parallel ticket-capable agents. The direct-execute runtime proof is separate from multi-agent serialization and does not add locking or queueing. Avoid running multiple ticket-creating agents in the same session in parallel.

**`auto_silent` mode reserved:** The `auto_silent` autonomy mode is defined in the contract but not implemented. Setting it has undefined behavior — do not use until implemented.

**24-hour dedup window only:** Dedup fingerprinting covers a 24-hour same-day window. Tickets created on different calendar days with identical content will not be detected as duplicates, even if created minutes apart around midnight.

**Dependency cycle detection:** `ticket_triage.py` detects blocked chains by linear traversal. Cycles in the `blocked_by`/`blocks` graph are not detected and will cause triage to report misleading results.

**Gen 1/2 legacy IDs:** `ticket_parse.py` resolves slug-based (Gen 1), alpha-ID (Gen 2), and short-ID (Gen 3) formats. Legacy tickets may parse with reduced field completeness if they predate required fields added in contract v1.0.

---

## Verification

Run from the package root when validating this source tree. These checks do not prove that the installed cache copy has been refreshed.

### 1. Prerequisites

```bash
# Confirm Python version
python3 --version   # Must be ≥ 3.11

# Confirm plugin dependencies
cd /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket
uv run python -c "import yaml; print('deps ok')"
```

### 2. Test Suite

```bash
ENV_DIR="$(mktemp -d /private/tmp/ticket-uv-env.XXXXXX)" || exit 1
cleanup() {
  if [ -n "${ENV_DIR:-}" ] && [ -d "$ENV_DIR" ]; then
    trash "$ENV_DIR"
  fi
}
trap cleanup EXIT
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT="$ENV_DIR" \
  uv run --project /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket/pyproject.toml \
  pytest -q -p no:cacheprovider
# Expected: all collected tests pass
```

### 3. Hook Registration

```bash
grep -r "ticket_engine_guard" ~/.codex/settings.json
# Should return the installed-cache hook registration entry
```

### 4. Read Smoke Test

```bash
# From a project with docs/tickets/
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <PROJECT_ROOT>/docs/tickets
# Should return JSON list (empty [] is valid if no tickets exist)
```

### 5. Triage Smoke Test

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <PROJECT_ROOT>/docs/tickets
# Should return JSON with counts (all zeros valid for empty directory)
```

### 6. Capture Preview Smoke Test

```bash
mkdir -p <PROJECT_ROOT>/.codex/ticket-tmp
cat > <PROJECT_ROOT>/.codex/ticket-tmp/capture-smoke.json << 'EOF'
{
  "tickets_dir": "docs/tickets",
  "capture": {
    "title": "Handbook verification test",
    "captured_request": "Verify the capture preview path from the handbook.",
    "problem": "The handbook capture smoke should exercise the user-facing preview path.",
    "next_action": "Run the capture prepare command and inspect the compact preview.",
    "capture_confidence": "high",
    "capture_source": "manual-smoke",
    "priority": "low",
    "tags": ["test"],
    "acceptance_criteria": [
      "Capture prepare returns a preview without writing a ticket."
    ]
  }
}
EOF

uv run python -B <PLUGIN_ROOT>/scripts/ticket_capture.py prepare <PROJECT_ROOT>/.codex/ticket-tmp/capture-smoke.json
# Expected: {"state": "ready_to_execute", ...}; do not run execute unless you intend to create the ticket.
```

### 7. Audit Trail Verification

```bash
# After a successful agent mutation (requires auto_audit mode)
ls docs/tickets/.audit/
# Should show YYYY-MM-DD/ directory with at least one .jsonl file

uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <PROJECT_ROOT>/docs/tickets
# Should complete with no errors
```

`references/ticket-contract.md` is the canonical schema source for field shapes and machine states.
