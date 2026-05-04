# Ticket Plugin

A Codex plugin for structured ticket management — creating, updating, closing, triaging, and auditing work tickets from within Codex sessions.

Tickets are stored as Markdown files with fenced YAML frontmatter in `docs/tickets/`. All mutations flow through a 4-stage pipeline (classify, plan, preflight, execute) enforced by a guard hook and trust model, with a full JSONL audit trail.

## Installation

Install via the Codex plugin system:

```bash
codex plugin install ticket
```

The plugin registers its hook, skills, and scripts automatically. No build step required.

### Requirements

- Python >= 3.11
- `pyyaml >= 6.0` (sole runtime dependency, installed with the plugin)

## What It Does

- **Create tickets** with structured fields (priority, tags, effort, dependencies) via a guided pipeline that validates, deduplicates, and enforces schema
- **Update, close, and reopen tickets** with status transition enforcement and confirmation gates
- **List and query tickets** with filters (status, priority, tag) and ID-prefix search
- **Triage** ticket health — stale detection (>7 days without update), blocked dependency chains, size warnings
- **Audit** mutation history via append-only JSONL logs, with a repair utility for corrupt entries
- **Agent autonomy** — external agents can create tickets autonomously, gated by a configurable policy and elevated confidence thresholds

## Components

### Skills (2)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `/ticket` | Explicit invocation only (`disable-model-invocation: true`) | Full CRUD: create, update, close, reopen, list, query, audit repair |
| `/ticket-triage` | Auto-triggerable by Codex | Read-only health dashboard and audit summary |

**`/ticket` operations:**

| Operation | Required Args | Pipeline |
|-----------|--------------|----------|
| `create` | title | 4-stage engine |
| `update` | ticket_id | 4-stage engine |
| `close` | ticket_id | 4-stage engine |
| `reopen` | ticket_id, reopen_reason | 4-stage engine |
| `list` | (none) | Direct read (`ticket_read.py`) |
| `query` | id_prefix | Direct read (`ticket_read.py`) |
| `audit repair` | (none) | Direct (`ticket_audit.py`) |

All mutations display a confirmation prompt (`y / edit / n`) before executing. No bypass flag exists.

### Hook (1)

**`ticket_engine_guard.py`** — PreToolUse hook on the Bash tool.

Intercepts all Bash commands, detects ticket script invocations, and:
- **Engine entrypoints:** validates subcommand against allowlist, validates payload path stays within workspace, atomically injects trust fields (session_id, hook_injected, hook_request_origin) into the payload file
- **Read-only scripts:** allows without injection
- **Audit repair:** allows for user-origin, denies for agent-origin
- **Unknown `ticket_*.py` scripts:** denies (fail-closed catch-all)
- **Non-ticket commands:** passes through silently

Security: blocks shell metacharacters (`|;&`$><\n\r`), enforces path containment, uses atomic writes (temp + fsync + os.replace).

### Scripts (15 modules in `scripts/`)

Source code lives in `scripts/`, not a standard Python package directory. Skills resolve the plugin root from their own installed location and invoke scripts with absolute paths such as `python3 <plugin-root>/scripts/<script>.py`.

**Engine entrypoints (mutation pipeline):**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_engine_user.py` | `<subcommand> <payload_file>` | User-origin mutations |
| `ticket_engine_agent.py` | `<subcommand> <payload_file>` | Agent-origin mutations |

Both delegate to `ticket_engine_runner.py`, which dispatches to `ticket_engine_core.py`.

**Read-only entrypoints:**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_read.py` | `list <tickets_dir> [--status S] [--priority P] [--tag T] [--include-closed]` | List/filter tickets |
| `ticket_read.py` | `query <tickets_dir> <search_term>` | ID-prefix search |
| `ticket_triage.py` | `dashboard <tickets_dir>` | Health dashboard |
| `ticket_triage.py` | `audit <tickets_dir> [--days N]` | Audit trail summary (default 7 days) |
| `ticket_audit.py` | `repair <tickets_dir> [--dry-run]` | Repair corrupt JSONL audit logs (user-only) |

**Response envelope (all engine commands):**

```json
{"state": "<machine_state>", "ticket_id": "<string|null>", "message": "<string>", "error_code": "<string|null>", "data": {}}
```

Exit codes: `0` (success), `1` (engine error), `2` (validation failure / need_fields).

### Reference Documents

| Document | Path | Purpose |
|----------|------|---------|
| Ticket Contract | `references/ticket-contract.md` | Single source of truth: schema, states, error codes, transitions, autonomy, dedup |
| Pipeline Guide | `skills/ticket/references/pipeline-guide.md` | Payload schemas, state propagation, response-to-UX mapping |
| Operator Handbook | `HANDBOOK.md` | Bring-up, operational runbooks, failure recovery, internals |
| Changelog | `CHANGELOG.md` | Version history and release notes |

## Configuration

### Autonomy Policy

Controls agent-origin behavior. Configured per-project in `.codex/ticket.local.md` (YAML frontmatter):

```yaml
---
autonomy_mode: suggest
max_creates_per_session: 5
---
```

| Field | Type | Default | Values |
|-------|------|---------|--------|
| `autonomy_mode` | string | `suggest` | `suggest`, `auto_audit`, `auto_silent` (v1.1 only) |
| `max_creates_per_session` | int | `5` | Per-session cap on agent-created tickets; `0` disables agent creates |

| Mode | Behavior |
|------|----------|
| `suggest` (default) | Agent proposes tickets but cannot create them |
| `auto_audit` | Agent can create tickets with full audit trail |
| `auto_silent` | Reserved for v1.1 — not yet implemented, gated with explicit error |

The agent entrypoint re-reads the live policy at execute time and blocks if it has changed since preflight — preventing policy drift during pipeline execution.

### Path Resolution

Skills and hooks do not require shell environment setup. Skills derive the plugin root from their installed skill path, and the hook derives it from the parent of `hooks/`.

### Ticket Storage (conventions, not configurable)

| Path | Purpose |
|------|---------|
| `docs/tickets/` | Active tickets |
| `docs/tickets/closed-tickets/` | Archived closed tickets |
| `docs/tickets/.audit/YYYY-MM-DD/<session_id>.jsonl` | Append-only audit trail |
| `.codex/ticket-tmp/` | Temporary payload files during pipeline execution |

### Ticket Schema

Tickets use fenced YAML blocks (` ```yaml `, not `---` frontmatter).

**Required fields:**

| Field | Format | Values |
|-------|--------|--------|
| `id` | `T-YYYYMMDD-NN` | Auto-allocated |
| `date` | `YYYY-MM-DD` | Creation date |
| `status` | string | `open`, `in_progress`, `blocked`, `done`, `wontfix` |
| `priority` | string | `critical`, `high`, `medium`, `low` |
| `source` | dict | `{type: "...", ref: "...", session: "..."}` |
| `contract_version` | string | `"1.0"` |

**Optional fields:** `effort` (XS/S/M/L/XL), `tags` (list), `blocked_by` (list of ticket IDs), `blocks` (list), `defer` (dict with `active`, `reason`, `deferred_at`).

## Usage Patterns

### Create a ticket

```
/ticket create "Authentication fails on expired tokens"
```

Codex guides you through the 4-stage pipeline: classifies intent, plans the ticket (checking for duplicates), runs preflight validation, and executes after confirmation.

### Update a ticket

```
/ticket update T-20260309-01 priority=critical tags=["auth","urgent"]
```

### Close a ticket

```
/ticket close T-20260309-01
```

Optionally specify resolution: `done` (default) or `wontfix`. Closed tickets are archived to `docs/tickets/closed-tickets/`.

### List and filter

```
/ticket list --status open --priority high
/ticket query T-2026
```

### Triage ticket health

```
/ticket-triage
```

Produces a structured report: ticket counts by status/priority, stale tickets (>7 days), blocked dependency chains, size warnings, and suggested next actions.

## Architecture

### 4-Stage Pipeline

```
User/Agent Intent
    |
    v
[classify] -- validates action, resolves ticket ID, sets confidence
    |
    v  (skill carries state via payload file)
[plan] -- validates fields, computes dedup fingerprint, scans for duplicates
    |
    v  (skill merges response.data into payload)
[preflight] -- enforcement: origin, autonomy, confidence, dedup, dependencies, TOCTOU
    |
    v  (skill merges autonomy_config into payload)
[execute] -- defense-in-depth re-checks, writes ticket file, appends audit entry
    |
    v
Ticket file on disk + JSONL audit entry
```

The engine is **stateless** — each script invocation reads a payload file, processes one stage, prints JSON to stdout, and exits. The `/ticket` skill (SKILL.md instructions) orchestrates state between stages by merging response data into the payload file before each subsequent call.

### Trust Model

Mutations are secured by a **trust triple** injected atomically by the guard hook:

| Field | Purpose |
|-------|---------|
| `session_id` | Ties the mutation to a specific Codex session |
| `hook_injected` | Proves the command passed through the guard hook |
| `hook_request_origin` | Records whether the caller is `user` or `agent` |

Execute validates all three fields before allowing any write. Agent-origin requests face higher confidence thresholds (0.65 vs 0.5) and require `auto_audit` autonomy mode.

### Defense in Depth

Security checks are duplicated across pipeline stages:

| Check | Stages |
|-------|--------|
| Deduplication | plan, execute |
| Autonomy policy | preflight, execute (with live re-read) |
| Confidence threshold | preflight, execute |
| Agent restrictions | preflight, execute |
| Origin verification | runner, preflight, execute |
| Intent match | preflight, execute |
| Session create cap | preflight, execute |
| TOCTOU fingerprint | preflight, execute |

### Machine States (15)

`ok`, `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `need_fields`, `duplicate_candidate`, `preflight_failed`, `policy_blocked`, `invalid_transition`, `dependency_blocked`, `not_found`, `escalate`, `merge_into_existing` (reserved, not emitted in v1.0).

### Error Codes (12)

`need_fields`, `invalid_transition`, `policy_blocked`, `preflight_failed`, `stale_plan`, `duplicate_candidate`, `parse_error`, `io_error`, `not_found`, `dependency_blocked`, `intent_mismatch`, `origin_mismatch`.

## Extension Points

### Agent Integration

External agents can use `ticket_engine_agent.py` to create and manage tickets autonomously, subject to:

1. **Autonomy policy** in `.codex/ticket.local.md` must be `auto_audit` or higher
2. **Trust triple** injected by the guard hook (hook_injected=true, hook_request_origin="agent")
3. **Higher confidence threshold** (0.65 for agents vs 0.5 for users)
4. **Live policy re-read** at execute time blocks if policy changed since preflight
5. **Session create cap** enforcement via audit trail (configurable via `max_creates_per_session`)
6. **Reopen is user-only** in v1.0 — agents cannot reopen tickets

The `agents/` directory is a placeholder (`.gitkeep` only) — consuming projects define their own agent definitions that invoke the agent entrypoint.

### Consuming Project Setup

To enable agent-origin ticket creation in your project:

1. Create `.codex/ticket.local.md` with `autonomy_mode: auto_audit` in YAML frontmatter
2. Define an agent that invokes `ticket_engine_agent.py` via the Bash tool
3. The guard hook handles trust injection automatically

## Development

### Running Tests

```bash
# From package directory
cd packages/plugins/ticket && uv run pytest

# From repo root (workspace-aware)
uv run --package ticket-plugin pytest

# Specific module
uv run pytest tests/test_hook.py
```

596 tests across 25 test files. Collection time ~0.1s (pure Python, no heavy imports).

### Test Organization

Tests map 1:1 to source modules plus pipeline-stage and integration tests. Fixtures use factory functions (`tests/support/builders.py`) with keyword arguments for creating test tickets with configurable fields.

### Project Structure

```
scripts/          # 15 source modules
hooks/            # Guard hook + registration
skills/           # /ticket and /ticket-triage skill definitions
tests/            # 596 tests (25 files + support/)
references/       # Ticket contract (canonical schema)
agents/           # Placeholder — consuming projects define their own
.codex-plugin/   # Plugin manifest
pyproject.toml    # Package metadata and dependencies
CHANGELOG.md      # Version history
HANDBOOK.md       # Operator handbook
```

Source lives in `scripts/` rather than a standard Python package directory. Modules use `sys.path.insert` for imports, invoked directly via `python3 <path>`.

### Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `pyyaml` | >= 6.0 | YAML parsing/serialization for ticket frontmatter |
| `pytest` | >= 8.0 | Test runner (dev only) |

## Known Limitations

- **No file locking for concurrent updates** — read-modify-write on ticket files is not atomic (v1.3 known limitation)
- **Triage detects linear dependency chains only**, not cycles
- **Session create cap** is audit-based, not lock-based — race conditions possible under concurrent agent sessions
- **Guard hook is fail-open** at the top level — an unhandled exception allows the command through (prevents blocking all Bash commands)
- **`auto_silent` mode** is defined in the contract but gated with an explicit error — reserved for v1.1

## License

MIT.
