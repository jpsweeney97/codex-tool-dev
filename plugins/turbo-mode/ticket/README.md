# Ticket Plugin

A Codex plugin for capture-first repo-local ticket management from within Codex sessions.

Tickets are stored as Markdown files with fenced YAML frontmatter in `docs/tickets/`. User-facing creation flows through `ticket-capture`, which synthesizes a compact preview from natural language and writes only after explicit confirmation. Existing-ticket lifecycle, metadata, and focused refinement changes flow through `ticket_update.py prepare` and `ticket_update.py execute`, which reuse the same engine, guard hook, and trust model as the lower-level 4-stage pipeline.

This directory is the source-authority package for the Ticket plugin. Installed
cache and runtime artifacts are separate proof surfaces and may diverge until an
explicit cache-refresh or runtime-proof lane verifies them. Source edits here do
not prove installed Codex behavior.

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

- **Capture tickets** from natural language with synthesized fields, duplicate checks, and explicit create confirmation
- **Update existing tickets** with scoped lifecycle, frontmatter metadata, and focused refinement changes through preview-first `ticket_update.py` commands
- **List, query, and check close readiness** with read-only filters and ID-prefix search
- **Review backlog health** with the read-only `ticket_review.py` wrapper for stale detection, blocked dependency chains, size warnings, and next-action recommendations
- **Doctor storage and historical audit logs** only when explicitly requested through `ticket_doctor.py`, with dry-run repair before mutation and confirmed stale payload cleanup
- **Runtime-first autonomy source work** — direct agent execution fails closed until the engine-owned gateway applies approved autonomous mutations

## Components

### Skills (5)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `ticket-capture` | Track, file, capture, ticket, or remember follow-up work | Create one ticket from natural language after preview confirmation |
| `ticket-find` | Show, list, find, open, or check close readiness | Read-only `ticket_read.py list`, `query`, and `check` |
| `ticket-update` | Update existing ticket metadata, lifecycle, or focused refinement fields | Preview-first updates via `ticket_update.py prepare` and `execute` |
| `ticket-review` | Backlog health, stale, blocked, or next-work questions | Read-only `ticket_review.py review` and `audit`; may suggest capture prompts |
| `ticket-doctor` | Explicit storage/plugin diagnostics, installed runtime activation, stale payload cleanup, or audit repair | Maintenance-only `ticket_doctor.py diagnose`, explicit `activate-runtime`, confirmed `clean-stale-payloads`, and dry-run-first `repair-audit` |

Generic creation through the old broad `ticket` skill is no longer user-facing.
Use `ticket-capture` for new tickets. Low-confidence captures are allowed when a
concrete next action can be synthesized; those tickets carry
`refinement_status: needs_refinement`. `needs_refinement` is capture metadata,
not a lifecycle status.

**Skill-backed operations:**

| Operation | Required Args | Pipeline |
|-----------|--------------|----------|
| capture | natural-language follow-up | `ticket_capture.py prepare` then `execute` |
| update metadata/refinement | ticket_id plus scoped update fields | `ticket_update.py prepare` then `execute` |
| close/reopen | ticket_id plus required resolution or reopen reason | `ticket_update.py prepare` then `execute` |
| list/query/check | filters, ID prefix, or ticket_id | Direct read (`ticket_read.py`) |
| backlog review | tickets directory | Read-only `ticket_review.py review` and `audit` |
| doctor/repair | explicit maintenance request | `ticket_doctor.py diagnose`, explicit `activate-runtime`, confirmed `clean-stale-payloads`, or dry-run-first `repair-audit` |

#### Supported Mutation Surfaces

Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`.

- `capture`: `ticket_capture.py prepare` then `ticket_capture.py execute`
- `update`: `ticket_update.py prepare` then `ticket_update.py execute`
- `ingest`: `ticket_engine_user.py ingest <payload_file>` or `ticket_engine_agent.py ingest <payload_file>`, consuming a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`

`capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths. They are not normal user-facing mutation interfaces and must not be documented as the preferred way to create or mutate tickets.

`ticket_workflow.py` is a compatibility/debug runner kept for tests and low-level recovery work. `ticket_workflow.py` is not a supported user-facing mutation surface.

All mutations display a confirmation prompt (`y / edit / n`) before executing. No bypass flag exists.

### Hook (1)

**`ticket_engine_guard.py`** — PreToolUse hook on the Bash tool.

Intercepts all Bash commands, detects ticket script invocations, and:
- **Engine entrypoints:** validates subcommand against allowlist, validates the absolute payload path stays within workspace, atomically injects trust fields (session_id, hook_injected, hook_request_origin) into the payload file
- **Read-only scripts:** allows without injection
- **Historical audit repair:** allows for user-origin, denies for agent-origin
- **Unknown `ticket_*.py` scripts:** denies (fail-closed catch-all)
- **Non-ticket commands:** passes through silently

Security: blocks shell metacharacters (`|;&`$><\n\r`), enforces path containment, uses atomic writes (temp + fsync + os.replace).

### Scripts

Source code lives in `scripts/`, not a standard Python package directory. Skills resolve the plugin root from their own installed location and invoke scripts through the canonical Bash launcher `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py`. The hook may still accept `python3` launchers as legacy compatibility, but `uv run python -B` is the documented public contract.

Canonical Bash launcher for plugin scripts:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <PROJECT_ROOT>/docs/tickets
```

**Engine entrypoints (mutation pipeline):**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_engine_user.py` | `<subcommand> <payload_file>` | User-origin mutations |
| `ticket_engine_agent.py` | `<subcommand> <payload_file>` | Agent-origin mutations |
| `ticket_capture.py` | `prepare <payload_file>` / `execute <payload_file>` | User-facing capture-first ticket creation |
| `ticket_update.py` | `prepare <payload_file>` / `execute <payload_file>` | User-facing existing-ticket lifecycle, metadata, and focused refinement updates |

Both delegate to `ticket_engine_runner.py`, which dispatches to `ticket_engine_core.py`.

**Host-facing autonomy entrypoints:**

| Command | Purpose |
|---------|---------|
| `ticket_autonomy.py pause` | Write a workspace pause marker and force discussion-only local mode |
| `ticket_autonomy.py recover` | Project pending-summary recovery state before new automatic writes |
| `ticket_autonomy.py apply-turn` | Apply runtime-first turn candidates through the gateway |
| `ticket_autonomy.py doctor-ledger` | Inspect or repair deterministic pending-summary ledger gaps |
| `ticket_autonomy.py migrate-change-history` | Insert missing `## Change History` sections with dry-run/apply modes |

**Read-only entrypoints:**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_read.py` | `list <tickets_dir> [--status S] [--priority P] [--tag T] [--include-closed]` | List/filter tickets |
| `ticket_read.py` | `query <tickets_dir> <search_term>` | ID-prefix search |
| `ticket_read.py` | `check <tickets_dir> <ticket_id>` | Close-readiness check |
| `ticket_triage.py` | `dashboard <tickets_dir>` | Health dashboard |
| `ticket_triage.py` | `audit <tickets_dir> [--days N]` | Historical audit summary (default 7 days) |
| `ticket_review.py` | `review <tickets_dir>` / `audit <tickets_dir> [--days N]` | User-facing read-only backlog review wrapper |
| `ticket_doctor.py` | `diagnose <tickets_dir> --plugin-root <plugin_root> --cache-root <cache_root> [--runtime-probe-output <path>]` | User-facing explicit diagnostics wrapper |
| `ticket_triage.py` | `doctor <tickets_dir> --plugin-root <plugin_root> --cache-root <cache_root> [--runtime-probe-output <path>]` | Static source/cache/project diagnostic |

**Maintenance entrypoints:**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_doctor.py` | `activate-runtime <tickets_dir> --marketplace-path <marketplace_path>` | User-facing direct_execute-only runtime activation wrapper |
| `ticket_doctor.py` | `clean-stale-payloads <tickets_dir> [--confirm-clean-stale-payloads]` | User-facing confirmed cleanup for stale prepare payloads |
| `ticket_doctor.py` | `repair-audit <tickets_dir> [--confirm-repair]` | User-facing dry-run-first audit repair wrapper |
| `ticket_audit.py` | `repair <tickets_dir> [--fix | --dry-run]` | Repair corrupt historical JSONL audit logs backend (defaults to dry-run; `--fix` mutates) |
| `ticket_workflow.py` | `prepare <payload_file>` / `execute <payload_file>` / `recover <payload_file> <action>` | Internal/debugging legacy workflow runner for lower-level orchestration |

**Response envelope (all engine commands):**

```json
{"state": "<machine_state>", "ticket_id": "<string|null>", "message": "<string>", "data": {}, "error_code": "<string on failure only>"}
```

Success responses omit `error_code`; error responses include it at the top level.

Exit codes: `0` (success), `1` (engine error), `2` (validation failure / need_fields).

For live installed activation and certification, use the cache-installed
runtime authority that `hooks/list` and `skills/list` expose. Treat the synced
personal plugin copy as staging only, not the proof target.

### Reference Documents

| Document | Path | Purpose |
|----------|------|---------|
| Ticket Contract | `references/ticket-contract.md` | Single source of truth: schema, states, error codes, transitions, autonomy, dedup |
| Operator Handbook | `HANDBOOK.md` | Bring-up, operational runbooks, failure recovery, internals |
| Changelog | `CHANGELOG.md` | Version history and release notes |

## Configuration

### Runtime-First Autonomy State

Future autonomous durable history writes to `## Change History` on each affected ticket. Future local operational state writes to `.codex/ticket-workspace/ticket.pending-summary.jsonl`. Existing `docs/tickets/.audit/` files are historical artifacts; `ticket_audit.py` and `ticket_doctor.py repair-audit` are read/repair tools for existing historical `.audit/` files only.

Direct `ticket_engine_agent.py execute` is not an autonomous mutation route in this source slice. It fails closed with `gateway_required`. Source autonomous writes enter through `ticket_autonomy.py apply-turn`, where the runtime-first gateway validates a gateway-approved decision, appends pending-summary bookkeeping, and writes ticket-local `## Change History`. This is a fail-closed source boundary, not installed-runtime proof.

Local automation setup is strict JSON at `.codex/ticket.local.md`:

```json
{"schema":"codex.ticket.local.v1","mode":"agent_primary"}
```

Allowed modes are `discussion_only`, `preview`, and `agent_primary`. Missing or invalid config is `setup_required`; the engine does not fall back to older YAML/frontmatter modes. Guided setup choices map `automatic` to `agent_primary` and `ask_first` to `discussion_only`; `preview` is manual-only config.

Local runtime-first workspace state lives under `.codex/ticket-workspace/`, which must stay ignored by git. The workspace owns local mode snapshots and `pause.json`; a workspace pause immediately blocks autonomous mode resolution until resume rewrites strict JSON config from an explicit setup choice and invalidates stale mode snapshots.

### Path Resolution

Skills and hooks do not require shell environment setup. Skills derive the plugin root from their installed skill path, and the hook derives it from the parent of `hooks/`.

`PLUGIN_ROOT` and `PROJECT_ROOT` are separate:
- `PLUGIN_ROOT` identifies this plugin package.
- `PROJECT_ROOT` identifies the active workspace root by walking up from the current working directory until `.codex`, `.git/`, or a `.git` file is found.
- `TICKETS_DIR` is always `<PROJECT_ROOT>/docs/tickets`, never a path under `PLUGIN_ROOT`.
- `TICKET_RUNTIME_PROOF_PATH` and `TICKET_RUNTIME_ACTIVATION_BOOTSTRAP=1` are
  internal activation/test overrides used only by the explicit runtime
  activation flow. They are not normal operator inputs.

`hooks/hooks.json` in this source tree describes install-target metadata for the personal marketplace. It is not live runtime proof for the installed cache copy.

### Ticket Storage (conventions, not configurable)

| Path | Purpose |
|------|---------|
| `docs/tickets/` | Active tickets |
| `docs/tickets/closed-tickets/` | Archived closed tickets |
| affected ticket `## Change History` | Future autonomous durable history |
| `.codex/ticket-workspace/ticket.pending-summary.jsonl` | Future local autonomous operational state |
| `docs/tickets/.audit/YYYY-MM-DD/<session_id>.jsonl` | Historical audit artifacts for read/repair only |
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

**Optional fields:** `effort` (XS/S/M/L/XL), `tags` (list), `blocked_by` (list of ticket IDs), `blocks` (list), `defer` (dict with `active`, `reason`, `deferred_at`), `acceptance_criteria` (list of strings), `verification` (string), `key_files` (list of `{file, role, look_for}` objects), `key_file_paths` (list of strings).

`acceptance_criteria` is create-time `list[string]` input only. Bare strings are rejected before rendering.

## Usage Patterns

### Guided UX Layer

The user-facing creation path is `ticket-capture`. It writes a capture payload,
runs `ticket_capture.py prepare`, presents a compact preview, and writes only
after explicit `create` confirmation. Existing-ticket changes use
`ticket_update.py prepare` to validate scoped lifecycle, metadata, or focused
refinement fields, then present one preview before `ticket_update.py execute`.
The lower-level engine stages and `ticket_workflow.py` remain available for
debugging and tests. The update runner preserves the hook-injected trust triple
and does not write tickets until execute.

### Capture a ticket

```
Track this follow-up: authentication fails on expired tokens.
```

Codex uses `ticket-capture` to synthesize title, problem, next action,
confidence, priority, tags, and acceptance criteria. If the request is vague
but has a concrete next action, it can create a low-confidence ticket marked
with `refinement_status: needs_refinement`.

### Update an existing ticket

```
Update T-20260309-01 priority to critical and add auth, urgent tags.
```

### Close or reopen a ticket

```
Close T-20260309-01 as done.
```

Optionally specify resolution: `done` (default) or `wontfix`. Closed tickets are archived to `docs/tickets/closed-tickets/`.

### List and filter

```
Find open high-priority ticket work.
Show ticket T-2026.
```

### Review ticket health

```
Review ticket backlog health.
```

Produces a structured report: ticket counts by status/priority, stale tickets (>7 days), blocked dependency chains, size warnings, and suggested next actions.

### Doctor stale payloads

`ticket_doctor.py diagnose` reports stale `.codex/ticket-tmp/` payloads older
than 24 hours without mutating them. Pass
`--runtime-probe-output <path>` only when you want a read-only runtime probe
artifact written under a caller-chosen temp path for later inspection. Cleanup
is TTL-scoped and confirmation-gated: first run
`ticket_doctor.py clean-stale-payloads <TICKETS_DIR>` to see that cleanup
requires confirmation, then run
`ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads`
only after explicit approval. The confirmation flag is
`--confirm-clean-stale-payloads`.

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
    v  (skill carries verified stage data into payload)
[execute] -- defense-in-depth re-checks and writes ticket files for supported user-directed paths
    |
    v
Ticket file on disk
```

The engine is **stateless** — each script invocation reads a payload file, processes one stage, prints JSON to stdout, and exits. The update workflow skill instructions orchestrate state between stages by merging response data into the payload file before each subsequent call.

### Trust Model

Mutations are secured by a **trust triple** injected atomically by the guard hook:

| Field | Purpose |
|-------|---------|
| `session_id` | Ties the mutation to a specific Codex session |
| `hook_injected` | Proves the command passed through the guard hook |
| `hook_request_origin` | Records hook-observed provenance such as `user` or `agent`; on current Codex runtime it is metadata, not security-grade caller identity |

Execute validates all three fields before allowing any write. Direct requests
routed through `ticket_engine_agent.py execute` fail closed until the
runtime-first gateway supplies a gateway-approved decision.

### Defense in Depth

Security checks are duplicated across pipeline stages:

| Check | Stages |
|-------|--------|
| Deduplication | plan, execute |
| Direct-agent gateway requirement | execute |
| Confidence threshold | preflight, execute |
| Agent restrictions | preflight, execute |
| Origin verification | runner, preflight, execute |
| Intent match | preflight, execute |
| TOCTOU fingerprint | preflight, execute |

### Machine States (15)

`ok`, `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `need_fields`, `duplicate_candidate`, `preflight_failed`, `policy_blocked`, `invalid_transition`, `dependency_blocked`, `not_found`, `escalate`, `merge_into_existing` (reserved, not emitted in v1.0).

### Core Engine Error Codes (13)

`need_fields`, `invalid_transition`, `policy_blocked`, `preflight_failed`, `stale_plan`, `duplicate_candidate`, `parse_error`, `io_error`, `internal_error`, `not_found`, `dependency_blocked`, `intent_mismatch`, `origin_mismatch`.

## Extension Points

### Agent Integration

External autonomous Ticket writes must enter through the runtime-first gateway. The gateway is responsible for validating approval, checking pause/config state, writing ticket-local `## Change History`, and appending pending-summary bookkeeping. Direct `ticket_engine_agent.py execute` remains a low-level compatibility path and fails closed for create, update, close, and reopen without that gateway-approved decision contract.

The `agents/` directory is a placeholder (`.gitkeep` only) — consuming projects define their own agent definitions that invoke the agent entrypoint.

### Consuming Project Setup

Runtime-first autonomous setup is not enabled by editing YAML mode flags. Use strict `.codex/ticket.local.md` JSON only, keep `.codex/ticket-workspace/` ignored, and route autonomous writes through `ticket_autonomy.py apply-turn` and the runtime-first gateway.

## Development

### Running Tests

```bash
# From package directory
cd /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket && uv run pytest

# From repo root
uv run pytest plugins/turbo-mode/ticket/tests

# Specific module
uv run pytest tests/test_hook.py
```
Treat success as "all collected tests pass". Do not rely on a hard-coded count in this source package.

### Test Organization

Tests map 1:1 to source modules plus pipeline-stage and integration tests. Fixtures use factory functions (`tests/support/builders.py`) with keyword arguments for creating test tickets with configurable fields.

### Project Structure

```
scripts/          # plugin script entrypoints and support modules
hooks/            # Guard hook + registration
skills/           # ticket-capture, find, update, review, and doctor skill definitions
tests/            # pytest suite + support fixtures
references/       # Ticket contract (canonical schema)
agents/           # Placeholder — consuming projects define their own
.codex-plugin/   # Plugin manifest
pyproject.toml    # Package metadata and dependencies
CHANGELOG.md      # Version history
HANDBOOK.md       # Operator handbook
```

Source lives in `scripts/` rather than a standard Python package directory. Modules use `sys.path.insert` for imports and the documented Bash contract is `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...`. Any remaining `python3` hook acceptance is legacy compatibility, not the public launcher form.

### Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `pyyaml` | >= 6.0 | YAML parsing/serialization for ticket frontmatter |
| `pytest` | >= 8.0 | Test runner (dev only) |

## Known Limitations

- **Triage detects linear dependency chains only**, not cycles
- **Guard hook fails closed for Ticket candidates** — malformed hook input and internal guard errors emit stop entries instead of allowing the command through.
- **Direct agent execute is not the autonomy gateway** — autonomous create, update, close, and reopen route through `ticket_autonomy.py apply-turn` and the runtime-first gateway; direct `ticket_engine_agent.py execute` fails closed with `gateway_required`.

## License

MIT.
