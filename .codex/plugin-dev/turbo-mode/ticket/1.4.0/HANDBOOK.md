# Ticket Plugin — Operator Handbook

## Overview

The ticket plugin provides structured work-tracking for Codex sessions. It manages tickets as markdown files with YAML frontmatter, enforcing a 4-stage mutation pipeline (classify → plan → preflight → execute) that gates both user and agent writes.

**Scope:** Ticket lifecycle mutations (create/update/close/reopen), read queries (list/query), health triage, and audit trail repair.

**Not covered:** External issue tracker integrations, UI rendering, cross-project ticket syncing, or agent-orchestration workflows (roadmap).

---

## At a Glance

### Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `/ticket` | `skills/ticket/SKILL.md` | Lifecycle mutations and read queries via full pipeline |
| `/ticket-triage` | `skills/ticket-triage/SKILL.md` | Health dashboard: stale detection, blocked chains, audit summary |

### CLI Entrypoints

| Script | Origin | Purpose |
|--------|--------|---------|
| `scripts/ticket_engine_user.py` | User | Mutation pipeline with `request_origin="user"` |
| `scripts/ticket_engine_agent.py` | Agent | Mutation pipeline with `request_origin="agent"` (autonomy-gated) |
| `scripts/ticket_read.py` | Any | Read-only: list and query by ID-prefix |
| `scripts/ticket_triage.py` | Any | Read-only: dashboard counts, stale/blocked detection, audit summary |
| `scripts/ticket_audit.py` | Any | Audit trail validation and corrupt-line repair |

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
| `scripts/ticket_render.py` | Structured → markdown via Jinja2; preserves section ordering |
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
- `pyyaml` ≥ 6.0, `jinja2` (installed via plugin package)
- A project with a `.git/` or `.codex/` directory (required for project root discovery)
- Plugin installed at `~/.codex/plugins/ticket/` or via `codex plugin install`

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

No shell environment variable is required. Skills resolve the plugin root from their installed skill path, and the hook resolves it from the parent of `hooks/`.

### Tickets Directory

The `tickets_dir` defaults to `<project_root>/docs/tickets/`. All CLI scripts accept it as a positional argument. Must resolve inside the project root — path traversal is blocked.

The `.audit/` subdirectory (`docs/tickets/.audit/`) is created automatically on the first agent mutation.

---

## Operating Model

### Trust Model

Every mutation must carry a **trust triple** injected by the hook:

| Field | Source | Purpose |
|-------|--------|---------|
| `session_id` | Hook (`event.session_id`) | Session identity; sanitized (no `/`, `\`, `\0`) before filesystem use |
| `hook_injected` | Hook | Proves request passed through the hook |
| `request_origin` | Hook (`agent_id` presence) | `"user"` or `"agent"`; must match the entrypoint called |

The hook injects these fields atomically into the payload file before allowing the Bash command to proceed. At classify and execute stages, the engine re-validates that the trust triple is internally consistent. Mismatches reject with an error — not a warning.

**Flow:** Hook validates and injects → entrypoint asserts origin matches → pipeline re-validates triple.

### Autonomy Enforcement

Agent mutations face additional gating that user mutations do not:

1. **Preflight reads** `autonomy_mode` from `.codex/ticket.local.md`. If mode is `suggest`, agent mutations are blocked entirely.
2. **Execute re-reads** the config and re-checks. A config change between preflight and execute is caught at execute.
3. **Session create cap** is enforced at execute by counting prior agent creates in the audit trail for the current session.

User mutations skip the autonomy policy check — they pass through regardless of `autonomy_mode`.

### Audit Trail

Located at `docs/tickets/.audit/YYYY-MM-DD/*.jsonl`. Each line is a JSON object recording one mutation event with action, result, session, and payload snapshot.

- **Agent mutations:** Audit trail write is fail-closed. If the write fails, the mutation is blocked.
- **User mutations:** Audit trail write is advisory. If the write fails, the mutation proceeds.

---

## Component Runbooks

### `/ticket` skill

**When to use**
The primary interface for all ticket operations in a Codex session. Use when creating, updating, closing, reopening, listing, or querying tickets from natural language. Delegates mutations to `ticket_engine_user.py`; read operations call `ticket_read.py` directly.

**Flow**
1. Resolve plugin root from the skill's own directory
2. Determine tickets directory (`<project_root>/docs/tickets/`)
3. Classify the operation (create/update/close/reopen/list/query/audit)
4. For mutations: construct JSON payload → call `ticket_engine_user.py` → interpret response
5. For reads: call `ticket_read.py` directly → format output

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| `error: trust_triple_invalid` | Hook not running or trust fields absent | Verify `hooks/ticket_engine_guard.py` is registered in `settings.json` |
| `error: path_traversal` | `tickets_dir` resolves outside project root | Confirm project has `.git/` or `.codex/` at expected root |
| `error: dedup_collision` | Same problem+files created within 24 hours | Review existing open tickets with `/ticket list`; update the duplicate instead |
| Mutation silently rejected | `autonomy_mode: suggest` blocks agent mutations | User must perform the mutation, or set `autonomy_mode: auto_audit` |

---

### `/ticket-triage` skill

**When to use**
Health check for the ticket backlog. Surfaces stale tickets (>30 days), blocked dependency chains, and audit activity. Makes no changes.

**Flow**
1. Resolve plugin root and tickets directory
2. Run `ticket_triage.py dashboard` → counts by status, stale list, blocked chain detection, size warnings
3. Run `ticket_triage.py audit` → aggregate by action/result/session from `.audit/` JSONL
4. Format and render recommendations

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| No audit data shown | `.audit/` directory absent | No agent mutations have occurred yet; expected for user-only workflows |
| Stale threshold seems wrong | Old tickets lack `updated` field | Triage falls back to file mtime — results may be approximate |

---

### `ticket_engine_user.py` / `ticket_engine_agent.py`

**When to use**
Called by skills to execute the 4-stage mutation pipeline. `ticket_engine_user.py` for interactive user operations; `ticket_engine_agent.py` for autonomous agent mutations.

**Inputs**
```
ticket_engine_user.py <operation> <payload_json_path> <tickets_dir>
ticket_engine_agent.py <operation> <payload_json_path> <tickets_dir>
```

**Response envelope**
```json
{
  "state": "success" | "error" | "conflict",
  "ticket_id": "T-YYYYMMDD-NN",
  "message": "human-readable result",
  "data": { ... }
}
```

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| `state: error`, `trust_triple_mismatch` | Origin in payload doesn't match entrypoint | Do not call agent entrypoint with user-origin payload, or vice versa |
| `state: error`, `autonomy_blocked` | Agent mutations attempted under `suggest` mode | Set `autonomy_mode: auto_audit` in `.codex/ticket.local.md` |
| `state: error`, `session_cap_exceeded` | Per-session create limit reached | Raise `max_creates_per_session` or start a new session |
| `state: conflict`, `dedup_collision` | Matching ticket exists within 24 hours | Use the returned `ticket_id` to update the existing ticket instead |

---

### `ticket_read.py`

**When to use**
List or query tickets without triggering the mutation pipeline. Safe to run at any time; no writes.

**Inputs**
```
ticket_read.py list <tickets_dir> [--status open|closed|...] [--priority high|...] [--tag <tag>]
ticket_read.py query <tickets_dir> <id_prefix>
```

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Empty results | Tickets directory doesn't exist | Verify `docs/tickets/` exists in project root |
| Parse errors in output | Malformed ticket YAML | Run `ticket_audit.py` to identify corrupt files |

---

### `ticket_triage.py`

**When to use**
Standalone health check; called by `/ticket-triage` skill. Produces dashboard and audit summary without mutations.

**Inputs**
```
ticket_triage.py dashboard <tickets_dir> [--days <N>]   # N = stale window, default 30
ticket_triage.py audit <tickets_dir>
```

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Blocked chain not detected | Cycle in `blocked_by`/`blocks` graph | Manual review; triage detects linear chains only, not cycles |

---

### `ticket_audit.py`

**When to use**
Repair corrupted audit trail JSONL files. Always run with `--dry-run` first.

**Inputs**
```
ticket_audit.py <tickets_dir> [--dry-run]
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
- Allowlists only canonical plugin endpoint paths (hardened against renaming or wrapping)
- Rejects shell metacharacters: `|`, `;`, `` ` ``, `$`, `&`, `(`, `)`, `<`, `>`, newlines
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

- `open` → `closed` requires a `resolution` field (or explicit `wontfix` override)
- `closed` → `open` creates a `reopen_history` entry with reason
- Transitions are blocked if `blocked_by` tickets are not in a terminal state (unless resolution-aware bypass is used)
- `defer` status available for tickets explicitly deferred to a future session

### ID Allocation

IDs follow `T-YYYYMMDD-NN` format (e.g., `T-20260309-01`). The allocator scans live tickets to find the next available `NN` for today, zero-padded to 2 digits. Under concurrent load, exclusive file creation (`O_EXCL`) is used with bounded retry — but parallel subagent creates are not fully serialized (see Known Limitations).

### TOCTOU Protection

At preflight, the engine takes a fingerprint snapshot of any existing ticket being mutated. At execute, it re-reads and re-fingerprints before writing. If the live file changed between stages (concurrent write), the mutation is blocked with a `toctou_conflict` error.

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
| `toctou_conflict` on update | Concurrent write between preflight and execute | Inspect ticket file mtime | Re-run update after verifying current state |
| Corrupt audit JSONL lines | Interrupted write (crash during mutation) | Run `ticket_audit.py <tickets_dir> --dry-run` | Run `ticket_audit.py <tickets_dir>` to repair with backup |
| Stale tickets not surfaced by triage | Missing `updated` field in old ticket YAML | Inspect ticket frontmatter | Triage falls back to file mtime; results are approximate for legacy tickets |
| `path_outside_cwd` from hook | Project root not at Codex launch directory | Check hook's `event.cwd` vs actual tickets path | Launch Codex from the project root containing `.git/` or `.codex/` |

---

## Known Limitations

**Concurrent agent creates:** Session create cap and ID allocation are not fully serialized under parallel subagent execution. Parallel agents can each read the audit trail before either write completes, both see cap space, both allocate the same ID, and both proceed — overrunning the cap and colliding on IDs. Avoid running multiple ticket-creating agents in the same session in parallel.

**`auto_silent` mode reserved:** The `auto_silent` autonomy mode is defined in the contract but not implemented. Setting it has undefined behavior — do not use until implemented.

**24-hour dedup window only:** Dedup fingerprinting covers a 24-hour same-day window. Tickets created on different calendar days with identical content will not be detected as duplicates, even if created minutes apart around midnight.

**Dependency cycle detection:** `ticket_triage.py` detects blocked chains by linear traversal. Cycles in the `blocked_by`/`blocks` graph are not detected and will cause triage to report misleading results.

**Gen 1/2 legacy IDs:** `ticket_parse.py` resolves slug-based (Gen 1), alpha-ID (Gen 2), and short-ID (Gen 3) formats. Legacy tickets may parse with reduced field completeness if they predate required fields added in contract v1.0.

---

## Verification

Run from the project root with the plugin installed.

### 1. Prerequisites

```bash
# Confirm Python version
python3 --version   # Must be ≥ 3.11

# Confirm plugin dependencies
cd packages/plugins/ticket
uv run python -c "import yaml, jinja2; print('deps ok')"
```

### 2. Test Suite

```bash
cd packages/plugins/ticket
uv run pytest tests/ -q
# Expected: 596 passed, 0 failed
```

### 3. Hook Registration

```bash
grep -r "ticket_engine_guard" ~/.codex/settings.json
# Should return the hook registration entry
```

### 4. Read Smoke Test

```bash
# From a project with docs/tickets/
uv run scripts/ticket_read.py list docs/tickets/
# Should return JSON list (empty [] is valid if no tickets exist)
```

### 5. Triage Smoke Test

```bash
uv run scripts/ticket_triage.py dashboard docs/tickets/
# Should return JSON with counts (all zeros valid for empty directory)
```

### 6. Mutation Smoke Test (user origin)

```bash
cat > /tmp/test_payload.json << 'EOF'
{
  "operation": "create",
  "problem": "Handbook verification test",
  "priority": "low",
  "source": "operator",
  "session_id": "test-session",
  "hook_injected": true,
  "request_origin": "user"
}
EOF

uv run scripts/ticket_engine_user.py create /tmp/test_payload.json docs/tickets/
# Expected: {"state": "success", "ticket_id": "T-YYYYMMDD-NN", ...}
```

### 7. Audit Trail Verification

```bash
# After a successful agent mutation (requires auto_audit mode)
ls docs/tickets/.audit/
# Should show YYYY-MM-DD/ directory with at least one .jsonl file

uv run scripts/ticket_audit.py docs/tickets/ --dry-run
# Should complete with no errors
```

---

*Plugin v1.2.0 · Contract v1.0 · `references/ticket-contract.md` is the canonical schema source*
