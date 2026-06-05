# Ticket Plugin

A Codex plugin for repo-local ticket reading, triage, diagnostics, and
runtime-first ticket authority work from within Codex sessions.

This directory is the source-authority package for the Ticket plugin. Installed
cache and runtime artifacts are separate proof surfaces and may diverge until an
explicit cache-refresh or runtime-proof lane verifies them. Source edits here do
not prove installed Codex behavior.

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This README is source-authority documentation, not
installed-runtime proof and not runtime proof. Source edits here do not prove
installed Codex behavior; installed cache, `hooks/list`, `skills/list`, and
live runtime inventory require a separate cache-refresh or runtime-proof lane.
The cache-installed runtime authority is the proof target; a synced personal
plugin copy is staging only, not the proof target. This docs/tests slice does
not perform cutover inventory or normalization and does not mutate
`docs/tickets/`.

Durable runtime modes are `agent_primary` and `discussion_only`.

## Target Post-Cutover Ticket Shape

Post-cutover active tickets use ID-only filenames under
`docs/tickets/T-YYYYMMDD-NN.md`. Ticket content uses YAML frontmatter, followed
by Markdown sections. Closed YAML frontmatter keys are `id`, `title`, `status`,
`priority`, `tags`, `related_paths`, and `blocked_by`.

Target statuses are `idea`, `open`, `blocked`, `done`, and `wontfix`. Target
priorities are `high`, `normal`, and `low`. Required sections are `Problem`,
`Next Action`, and `Change History`. `status: blocked` also requires a
non-empty `Blocked On` section. Unknown frontmatter keys are invalid.
`blocked_by` is optional ticket-ID dependency data for blocked tickets. There
is no persisted reverse `blocks` edge; reverse blocker views are derived by
scanning tickets.

## Target Candidate Mutation Contract

Ticket accepts one target candidate mutation at a time. The candidate fields
are `action`, `ticket_id`, `target.fields`, `target.sections`,
`proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.

`target.fields` and `target.sections` name the exact frontmatter fields or
Markdown sections the candidate proposes to change. `proposed_change` may
contain only those named targets. non-create writes require an expected ticket
fingerprint. Ticket computes candidate identity from canonical candidate
content plus the live target fingerprint; callers do not supply authoritative
identity values. Unknown fields are invalid.

## Target Result Envelope

Target mutation results use only these mechanical states: `ok`, `blocked`,
`needs_discussion`, `invalid_state`, and `no_change`.

Human-facing context belongs in the message and structured facts such as ticket
ID, validation detail, candidate identity, discussion prompt facts, and
post-write fingerprint.

## Target Change History Grammar

Target `Change History` entries use deterministic prose:

```markdown
- <timestamp> | <actor> | <reason>
- <timestamp> | <actor> | <reason> Corrects: <reference>.
```

The actor is a source value such as `codex`, `user-approved`, or `migration`.
The actor is not a workflow label and must not encode action type. `Corrects:
<reference>` is optional.

## Deprecated Source Drift

Deprecated source drift may mention old four-stage, prepare/execute, or
persistent `preview` behavior only as non-target implementation debt. These
surfaces are subordinate to ADR 0006 and the May 30 control doc.

Old capture/update prepare-execute helpers, host-facing autonomy wrappers,
`direct_execute`, stale-read wrapper codes, direct agent-engine execution, and
the Workflow runner are deprecated or diagnostic source facts, not target
product architecture.

Direct `ticket_engine_agent.py execute` is not an autonomous mutation route in
this source slice. It fails closed with `gateway_required`. Runtime-first
source bookkeeping such as
`.codex/ticket-workspace/ticket.pending-summary.jsonl` is diagnostic source
state here, not target ticket content.

## Legacy Cutover Input

Legacy ticket records may still contain fenced YAML, slug filenames, legacy
status or priority values, historical fields, and noncanonical sections. Those
records are input to a future read-only cutover inventory and later reviewed
normalization. This README does not perform that inventory.

## Historical Changelog

Older release notes may describe prior Ticket behavior. Treat those entries as
historical changelog context rather than current authority.

## Maintenance And Diagnostics

Maintenance and diagnostics may use explicit source/cache/runtime probes,
historical audit repair, stale payload cleanup, runtime activation, and
diagnostic dry-run or `preview` evidence. They do not define normal target
ticket mutation.

Host-facing autonomy commands are diagnostic or maintenance inventory here:
`ticket_autonomy.py pause`, `ticket_autonomy.py recover`,
`ticket_autonomy.py apply-turn`, `ticket_autonomy.py doctor-ledger`, and
`ticket_autonomy.py migrate-change-history`.

**Read-only entrypoints:**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_read.py` | `list <tickets_dir> [--status S] [--priority P] [--tag T]` | List/filter tickets |
| `ticket_read.py` | `query <tickets_dir> <search_term>` | ID-prefix search |
| `ticket_read.py` | `check <tickets_dir> <ticket_id>` | Close-readiness check |
| `ticket_review.py` | `review <tickets_dir>` / `audit <tickets_dir> [--days N]` | User-facing read-only backlog review wrapper |

**Maintenance entrypoints:**

| Operation | Request | Entrypoint |
|-----------|---------|------------|
| doctor/repair | explicit maintenance request | `ticket_doctor.py diagnose` |
| `ticket_review.py` | `review <tickets_dir>` / `audit <tickets_dir> [--days N]` | Read-only backlog review |
| `ticket_doctor.py` | `diagnose <tickets_dir> --plugin-root <plugin_root> --cache-root <cache_root> [--runtime-probe-output <path>]` | Explicit diagnostics |
| `ticket_doctor.py` | `activate-runtime <tickets_dir> --marketplace-path <marketplace_path>` | User-owned runtime activation |
| `ticket_doctor.py` | `repair-audit <tickets_dir> [--confirm-repair]` | Historical audit repair |
| `ticket_triage.py` | `doctor <tickets_dir> --plugin-root <plugin_root> --cache-root <cache_root> [--runtime-probe-output <path>]` | Backend diagnostic path |
| `ticket_audit.py` | `repair <tickets_dir> [--fix | --dry-run]` | Historical audit backend repair |

Use `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...` for documented
source commands. Any remaining `python3` hook acceptance is legacy
compatibility.

`ticket_doctor.py diagnose` reports stale `.codex/ticket-tmp/` payloads older
than 24 hours. Cleanup is confirmation-gated with
`ticket_doctor.py clean-stale-payloads <TICKETS_DIR>
--confirm-clean-stale-payloads`.

Existing `docs/tickets/.audit/` files are historical artifacts. Future active
ticket history belongs in `Change History`; `.audit` repair remains maintenance
only. Ticket guard and runtime paths fail closed on blocked or malformed
mutation evidence.

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

- **Check capture and update availability** while write mutation is rebaselined
  onto the target candidate contract.
- **List, query, and check close readiness** with read-only status, priority,
  tag, and ID-prefix search.
- **Review backlog health** with read-only stale-ticket and blocker summaries.
- **Doctor storage and historical audit logs** only when explicitly requested,
  with dry-run repair before mutation and confirmed stale payload cleanup.
- **Describe target Ticket authority** from ADR 0006 and the May 30 control doc
  without claiming current source, installed cache, or live runtime enforcement.

## Components

### Skills (5)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `capture-ticket` | Track, file, capture, ticket, or remember follow-up work | Report capture availability and summarize the intended create candidate; write mutation is temporarily unavailable |
| `read-ticket` | Show, list, find, open, or check close readiness | Read-only `ticket_read.py list`, `query`, and `check` |
| `update-ticket` | Update existing ticket metadata, lifecycle, priority, tags, or blockers | Summarize the intended update candidate; write mutation is temporarily unavailable |
| `ticket-backlog-triage` | Backlog health, stale, blocked, or next-work questions | Read-only `ticket_review.py review` and `audit`; may suggest capture prompts |
| `ticket-doctor` | Explicit storage/plugin diagnostics, installed runtime activation, stale payload cleanup, or audit repair | Maintenance-only `ticket_doctor.py diagnose`, explicit `activate-runtime`, confirmed `clean-stale-payloads`, and dry-run-first `repair-audit` |

Generic creation through the old broad `ticket` skill is no longer user-facing.
Use `capture-ticket` for capture-intent handling. Until a live source entrypoint
accepts the target candidate mutation contract, capture and update skills stop
after a prose candidate summary and do not write tickets.

**Skill-backed operations:**

| Operation | Required Args | Current Source Action |
|-----------|--------------|-----------------------|
| capture intent | natural-language follow-up | Report unavailable write path and summarize the create candidate |
| update intent | ticket ID plus requested field, section, or lifecycle change | Report unavailable write path and summarize the update candidate |
| list/query/check | filters, ID prefix, or ticket ID | Direct read (`ticket_read.py`) |
| backlog review | tickets directory | Read-only `ticket_review.py review` and `audit` |
| doctor/repair | explicit maintenance request | `ticket_doctor.py diagnose`, explicit `activate-runtime`, confirmed `clean-stale-payloads`, or dry-run-first `repair-audit` |

#### Target Candidate Mutation Path

Ticket writes tickets today through the user-origin `ingest` engine path and the
`ticket_autonomy.py apply-turn` autonomy gateway. What this docs slice does not
identify is a live source entrypoint for the literal *target candidate* envelope.
When source exposes that entrypoint, it must accept the target candidate fields
`action`, `ticket_id`, `target.fields`, `target.sections`, `proposed_change`,
`expected_ticket_fingerprint`, and `evidence_summary`, and it must reject unknown
fields.

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

**Read-only entrypoints:**

| Script | Signature | Purpose |
|--------|-----------|---------|
| `ticket_read.py` | `list <tickets_dir> [--status S] [--priority P] [--tag T]` | List/filter tickets |
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
| `ticket_review.py` | `review <tickets_dir>` / `audit <tickets_dir> [--days N]` | Read-only backlog review |
| `ticket_triage.py` | `doctor <tickets_dir> --plugin-root <plugin_root> --cache-root <cache_root> [--runtime-probe-output <path>]` | Static source/cache/project diagnostic |
| `ticket_audit.py` | `repair <tickets_dir> [--fix | --dry-run]` | Repair corrupt historical JSONL audit logs backend (defaults to dry-run; `--fix` mutates) |

For live installed activation and certification, use the cache-installed
runtime authority that `hooks/list` and `skills/list` expose. Treat the synced
personal plugin copy as staging only, not the proof target.

### Reference Documents

| Document | Path | Purpose |
|----------|------|---------|
| Ticket Contract | `references/ticket-contract.md` | Source-facing reference subordinate to ADR 0006 and the May 30 control doc |
| Operator Handbook | `HANDBOOK.md` | Bring-up, operational runbooks, failure recovery, internals |
| Changelog | `CHANGELOG.md` | Version history and release notes |

## Configuration

### Runtime-First Autonomy State

Future autonomous durable history writes to `## Change History` on each
affected ticket. Existing `docs/tickets/.audit/` files are historical
artifacts; `ticket_audit.py` and `ticket_doctor.py repair-audit` are
read/repair tools for existing historical `.audit/` files only.

Local automation setup is strict JSON at `.codex/ticket.local.md`:

```json
{"schema":"codex.ticket.local.v1","mode":"agent_primary"}
```

Target durable modes are `discussion_only` and `agent_primary`. Diagnostic
preview is not a durable mode. Missing or invalid config must block instead of
falling back to older YAML/frontmatter modes.

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
| `docs/tickets/` | Active post-cutover tickets with ID-only filenames |
| affected ticket `## Change History` | Future autonomous durable history |
| `.codex/ticket-workspace/ticket.pending-summary.jsonl` | Source-drift or diagnostic local operational state |
| `docs/tickets/.audit/YYYY-MM-DD/<session_id>.jsonl` | Historical audit artifacts for read/repair only |
| `.codex/ticket-tmp/` | Temporary maintenance payloads and stale-payload diagnostics |

### Ticket Schema

Target tickets use YAML frontmatter, not fenced YAML blocks.

| Field | Format | Values |
|-------|--------|--------|
| `id` | `T-YYYYMMDD-NN` | Auto-allocated |
| `title` | string | Canonical title |
| `status` | string | `idea`, `open`, `blocked`, `done`, `wontfix` |
| `priority` | string | `high`, `normal`, `low` |
| `tags` | list of strings | `[]` |
| `related_paths` | list of strings | `[]` |
| `blocked_by` | list of ticket IDs | `[]` |

Required Markdown sections are `Problem`, `Next Action`, and `Change History`.
Tickets with `status: blocked` also require a non-empty `Blocked On` section.

## Usage Patterns

### Check capture availability

```
Check ticket capture availability for: authentication fails on expired tokens.
```

Codex should report that create mutation is temporarily unavailable until source
exposes a live target-candidate entrypoint, then summarize the intended ticket
candidate without writing.

### Summarize an update candidate

```
Update T-20260309-01 priority to high and add auth tags.
```

Codex should summarize the target fields, sections, proposed change, expected
fingerprint need, and evidence summary without writing.

### List and filter

```
Find open high-priority ticket work.
Show ticket T-2026.
```

### Review ticket health

```
Review ticket backlog health.
```

Produces a structured read-only report: ticket counts, stale tickets, blocker
relationships derived from `blocked_by`, size warnings, and suggested next
actions.

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

### State-Kernel Boundary

ADR 0006 demotes the old workflow engine into a deterministic ticket-state
kernel. Codex owns semantic discovery, candidate selection, prioritization, and
duplicate judgment. Ticket owns deterministic validation and persistence:
allowed fields, canonical paths, schema shape, status values, blocker
references, fingerprints, `Change History` append rules, idempotency, recovery,
and file writes.

### Target Write Envelope

Each candidate targets at most one ticket, performs one action, changes only the
named target fields or sections, and uses the target result states `ok`,
`blocked`, `needs_discussion`, `invalid_state`, and `no_change`.

## Extension Points

### Agent Integration

External autonomous Ticket writes must enter through the future runtime-first
candidate path. This source docs slice does not prove that installed or live
runtime behavior implements that path.

The `agents/` directory is a placeholder (`.gitkeep` only) — consuming projects define their own agent definitions that invoke the agent entrypoint.

### Consuming Project Setup

Runtime-first autonomous setup is not enabled by editing YAML mode flags. Use
strict `.codex/ticket.local.md` JSON only and keep
`.codex/ticket-workspace/` ignored.

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
skills/           # capture-ticket, read-ticket, update-ticket, ticket-backlog-triage, and ticket-doctor skill definitions
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

- The read-only `docs/tickets/` cutover inventory gate has not run in this
  source slice.
- Capture and update writes are temporarily unavailable from active skills until
  source exposes a live target-candidate entrypoint.
- Installed-cache and live runtime behavior remain unproved by this source
  documentation.

## License

MIT.
