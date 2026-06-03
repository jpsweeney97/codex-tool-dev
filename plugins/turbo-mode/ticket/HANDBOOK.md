# Ticket Plugin — Operator Handbook

## Overview

The ticket plugin provides repo-local ticket reading, triage, diagnostics, and
runtime-first ticket authority work for Codex sessions.

**Scope:** Ticket capture availability, existing-ticket update availability,
read queries, backlog health review, explicit diagnostics, and historical audit
repair while write mutation is rebaselined onto the target candidate contract.

**Not covered:** External issue tracker integrations, UI rendering, cross-project ticket syncing, or agent-orchestration workflows (roadmap).

**Source scope:** This handbook describes the source-authority package at
`plugins/turbo-mode/ticket/` in `/Users/jp/Projects/active/codex-tool-dev`.
Installed cache and runtime artifacts are separate proof surfaces and may
diverge until an explicit cache-refresh or runtime-proof lane verifies them.
Source edits here do not prove installed Codex behavior.

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This handbook is source-authority documentation, not
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

Target statuses are `open`, `in_progress`, `done`, and `wontfix`. Target
priorities are `high`, `normal`, and `low`. Required sections are `Problem`,
`Next Action`, and `Change History`. Unknown frontmatter keys are invalid.
`blocked` is not a status; blockedness derives from `blocked_by`. Store
`blocked_by` only and derive reverse `blocks` views by scanning tickets.

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

Direct `ticket_engine_agent.py execute` is not an autonomous mutation route in
this source slice. It fails closed with `gateway_required`. The runtime-first
gateway, direct execution gate, and old update/capture prepare-execute helpers
remain deprecated or diagnostic source facts, not target product architecture.

Runtime-first source bookkeeping such as
`.codex/ticket-workspace/ticket.pending-summary.jsonl` is diagnostic source
state here, not target ticket content.

## Legacy Cutover Input

Legacy ticket records may still contain fenced YAML, slug filenames, old
statuses, old priorities, historical fields, and noncanonical sections. Those
records are input to a future read-only cutover inventory and later reviewed
normalization. This handbook does not perform that inventory.

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

`scripts/ticket_doctor.py` | User | Explicit-only diagnostics.

Runtime activation is maintenance-only:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py activate-runtime <TICKETS_DIR> --marketplace-path <MARKETPLACE_PATH>
```

`ticket_doctor.py diagnose` reports source/cache parity, runtime-proof status,
installed Ticket runtime facts when supplied, and stale `.codex/ticket-tmp/`
payloads older than 24 hours. It may mention target statuses such as
`in_progress` only while diagnosing existing files.

The backend/diagnostic path
`ticket_triage.py doctor` is not the preferred user-facing doctor entrypoint.
Use:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py doctor <tickets_dir> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT> [--runtime-probe-output <path>]
```

`ticket_engine_activation_smoke.py` is a private activation-smoke entrypoint.

`ticket_engine_runner.py execute` may honor `TICKET_RUNTIME_PROOF_PATH`.
`TICKET_RUNTIME_ACTIVATION_BOOTSTRAP=1` is an internal activation/test
override. classify, plan, preflight, and ingest ignore it. At execute and
ingest stages, the engine re-validates the trust triple.

Use `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...` for documented
source commands. Any remaining `python3` hook acceptance is legacy
compatibility.

`ticket_doctor.py clean-stale-payloads <TICKETS_DIR>` reports stale
`.codex/ticket-tmp/` payloads. Cleanup requires
`--confirm-clean-stale-payloads` after review. Existing `docs/tickets/.audit/`
files are historical artifacts; `ticket_doctor.py repair-audit <TICKETS_DIR>`
and `ticket_doctor.py repair-audit <TICKETS_DIR> --confirm-repair` are
maintenance-only repair paths.

Ticket guard and runtime paths fail closed on blocked or malformed mutation
evidence.

---

## At a Glance

### Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `capture-ticket` | `skills/capture-ticket/SKILL.md` | Report capture availability and summarize the intended create candidate; write mutation is temporarily unavailable |
| `read-ticket` | `skills/read-ticket/SKILL.md` | Read-only show, list, query, and close-readiness checks |
| `update-ticket` | `skills/update-ticket/SKILL.md` | Summarize intended update candidates; write mutation is temporarily unavailable |
| `ticket-backlog-triage` | `skills/ticket-backlog-triage/SKILL.md` | Read-only backlog health, stale, blocker, and next-action review |
| `ticket-doctor` | `skills/ticket-doctor/SKILL.md` | Explicit-only storage/plugin diagnostics, stale payload cleanup, and audit repair |

Generic creation through the old broad `ticket` skill is no longer user-facing.
Use `capture-ticket` for capture-intent handling. Until a live source entrypoint
accepts the target candidate mutation contract, capture and update skills stop
after a prose candidate summary and do not write tickets.

### CLI Entrypoints

| Script | Origin | Purpose |
|--------|--------|---------|
| `scripts/ticket_review.py` | Any | User-facing read-only review and historical audit wrapper |
| `scripts/ticket_doctor.py` | User | Explicit-only diagnostics, runtime activation, stale payload cleanup, and dry-run-first historical audit repair wrapper |
| `scripts/ticket_read.py` | Any | Read-only: list, query by ID-prefix, and close-readiness check |
| `scripts/ticket_triage.py` | Any | Read-only: dashboard counts, stale/blocked detection, historical audit summary |
| `scripts/ticket_audit.py` | Any | Historical audit validation and corrupt-line repair |

Canonical Bash launcher for these scripts:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <PROJECT_ROOT>/docs/tickets
```

### Target Candidate Mutation Path

This docs slice does not identify a live source entrypoint that accepts target
candidate mutations. When source exposes that entrypoint, it must accept
`action`, `ticket_id`, `target.fields`, `target.sections`, `proposed_change`,
`expected_ticket_fingerprint`, and `evidence_summary`, and it must reject
unknown fields.

### Recovery Hints

Maintenance and diagnostic surfaces may include `data.recovery_hint`. When a
hint appears, show the safe recovery summary and next step. Do not treat
recovery hint codes as target result-envelope states.

### Hook

| Hook | Event | Purpose |
|------|-------|---------|
| `hooks/ticket_engine_guard.py` | `PreToolUse` (Bash) | Validates commands, injects trust fields, blocks metacharacters and path traversal |

---

## Core Components

### State-Kernel Boundary

ADR 0006 demotes the old workflow engine into a deterministic ticket-state
kernel. Codex owns semantic discovery, candidate selection, prioritization, and
duplicate judgment. Ticket owns deterministic validation and persistence:
allowed fields, canonical paths, schema shape, status values, blocker
references, fingerprints, `Change History` append rules, idempotency, recovery,
and file writes.

### Support Modules

| File | Responsibility |
|------|----------------|
| `scripts/ticket_parse.py` | Markdown parsing and legacy cutover inspection support |
| `scripts/ticket_render.py` | Markdown rendering with canonical serialization and section ordering |
| `scripts/ticket_validate.py` | Field schema validation; rejects unknown target fields |
| `scripts/ticket_id.py` | ID allocation: `T-YYYYMMDD-NN` format, scans live tickets for next slot |
| `scripts/ticket_dedup.py` | Deterministic fingerprint helpers |
| `scripts/ticket_paths.py` | Project root discovery (nearest `.codex/` or `.git/`); path containment validation |
| `scripts/ticket_trust.py` | Historical trust/provenance validation support |
| `scripts/ticket_triage.py` | Dashboard aggregation; stale and blocker summaries; historical `.audit/` JSONL aggregation |
| `scripts/ticket_read.py` | Query engine: filters by status/priority/tag, ID-prefix lookup |
| `scripts/ticket_audit.py` | Reads `.audit/YYYY-MM-DD/*.jsonl`; validates and repairs corrupt lines with backups |

### Entrypoints

| File | Responsibility |
|------|----------------|
| `scripts/ticket_read.py` | Read-only list, query, and close-readiness checks |
| `scripts/ticket_review.py` | Read-only backlog review |
| `scripts/ticket_doctor.py` | Explicit diagnostics and maintenance |
| `scripts/ticket_triage.py doctor` | Backend source/cache/project diagnostic |
| `scripts/ticket_audit.py repair` | Historical audit backend repair |

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
preview is not a durable mode. Missing, Markdown, YAML frontmatter, old mode
names, comments, or unknown keys all require setup instead of falling back to a
default.

Local runtime-first workspace state lives under `.codex/ticket-workspace/`, which must stay ignored by git. The workspace owns local mode snapshots and `pause.json`; a pause immediately blocks autonomous mode resolution until resume rewrites strict JSON config from an explicit setup choice and invalidates stale snapshots.

### Path Resolution

No shell environment variable is required for normal operation. Skills resolve
`PLUGIN_ROOT` from their installed skill path, the hook resolves it from the
parent of `hooks/`, and `PROJECT_ROOT` is discovered by walking up from the
current working directory to the nearest `.codex`, `.git/`, or `.git` marker.
During activation and test flows, `ticket_engine_runner.py execute` may honor
`TICKET_RUNTIME_PROOF_PATH`; classify, plan, preflight, and ingest ignore it.
`TICKET_RUNTIME_ACTIVATION_BOOTSTRAP=1` is an internal activation/test override
used only while explicit runtime activation proves the post-activation lane.
Neither variable is a normal operator input.

### Tickets Directory

The `tickets_dir` defaults to `<project_root>/docs/tickets/`. Read, triage, and
audit scripts accept it as a positional argument. In every case it must resolve
inside the project root; path traversal is blocked.

The `.audit/` subdirectory (`docs/tickets/.audit/`) may exist in older projects as historical data. Future runtime execution does not create it.

---

## Operating Model

### Autonomy Boundary

Current source docs do not prove installed or live runtime autonomy behavior.
Future writes must use the target candidate mutation contract and target result
envelope. Installed runtime activation remains a separate proof lane and does
not enable source-local autonomous writes.

### Historical Audit Files

Located at `docs/tickets/.audit/YYYY-MM-DD/*.jsonl` in projects that already have legacy audit data. Each line is a historical JSON object recording an older mutation event with action, result, session, and payload snapshot.

- **Future autonomous writes:** durable history belongs in affected tickets'
  `## Change History`.
- **Historical repair:** `ticket_audit.py` and `ticket_doctor.py repair-audit` remain available to validate and repair existing historical `.audit/` files.

---

## Component Runbooks

### `capture-ticket` skill

**When to use**
Use when the user asks to track, file, capture, ticket, or remember a bug,
feature, follow-up, task, or cleanup item.

**Flow**
1. Resolve plugin root from the skill's own directory
2. Resolve `PROJECT_ROOT` from the current working directory
3. Determine `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. Report that active create mutation is temporarily unavailable
5. Summarize the intended target candidate in prose without writing

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| `error: path_traversal` | `tickets_dir` resolves outside project root | Confirm project has `.git/` or `.codex/` at expected root |
| Write requested | Target candidate entrypoint is unavailable in this source slice | Summarize the candidate and stop |

---

### `read-ticket` skill

**When to use**
Show, list, search, open, or check close readiness for tickets. This skill is
read-only and calls only `ticket_read.py list`, `query`, and `check`.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Resolve `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. Run the requested `ticket_read.py` command
5. Present ID, title, status, priority, and path

---

### `update-ticket` skill

**When to use**
Use when the user asks to update an existing ticket's lifecycle, priority, tags,
blockers, related paths, or target sections.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Report that active update mutation is temporarily unavailable
4. Summarize the intended target candidate in prose without writing

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

### `ticket-backlog-triage` skill

**When to use**
Read-only health check for the ticket backlog. Surfaces stale tickets, blocker
relationships derived from `blocked_by`, historical audit activity, and
next-action recommendations. It may suggest `capture-ticket` prompts but must
not write tickets.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Resolve `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. Run `ticket_review.py review` for counts, stale tickets, blocker
   relationships, size warnings, and next actions
5. Run `ticket_review.py audit` → aggregate historical `.audit/` JSONL by action/result/session
6. Format and render recommendations

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| No historical audit data shown | `.audit/` directory absent | Expected for projects without legacy audit artifacts |
| Stale threshold seems wrong | Old tickets lack `updated` field | Triage falls back to file mtime — results may be approximate |

---

### `ticket-doctor` skill

**When to use**
Explicit maintenance only: diagnose ticket storage, validate plugin health,
activate the installed direct-execute runtime, or repair corrupt audit logs.
Casual audit, triage, or review language belongs to `ticket-backlog-triage`.

**Flow**
1. Resolve plugin root
2. Resolve `PROJECT_ROOT` from the current working directory
3. Resolve `TICKETS_DIR` as `<PROJECT_ROOT>/docs/tickets/`
4. For live installed activation, use the cache-installed runtime authority that
   `hooks/list` and `skills/list` expose. Treat the synced personal plugin copy
   as staging only, not the proof target.
5. For diagnostics, run `ticket_doctor.py diagnose`
6. For runtime activation, run `ticket_doctor.py activate-runtime` only when the
   user explicitly requests installed-runtime activation
7. For stale payload cleanup, run `ticket_doctor.py clean-stale-payloads <TICKETS_DIR>` first
8. Run `ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads` only after explicit approval
9. For audit repair, run `ticket_doctor.py repair-audit`
10. Run `ticket_doctor.py repair-audit --confirm-repair` only after explicit approval

**Runtime activation:** `ticket_doctor.py activate-runtime` is an explicit
operator flow for the installed Ticket runtime. It certifies only the
direct-execute lane and must not be treated as source-local proof or as a broad
mutation-surface certificate.

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py activate-runtime <TICKETS_DIR> --marketplace-path <MARKETPLACE_PATH>
```

The guard also accepts `ticket_engine_activation_smoke.py` as a private
activation-smoke entrypoint for contained proof bootstrap. It is not a normal
operator command and must not be used outside the explicit activation flow.

**Diagnostics:** `ticket_doctor.py diagnose` reports source/cache parity,
runtime-proof status, stale payload state, and optional runtime-probe output.
`activate-runtime` is the only path in this surface that exercises live
direct-execute runtime certification.

**Stale payload cleanup:** `ticket_doctor.py diagnose` reports stale
`.codex/ticket-tmp/` payloads older than 24 hours without mutating them.
Pass `--runtime-probe-output <path>` only when you want the diagnose command to
write a read-only runtime probe artifact under a caller-chosen temp path for
later inspection.
Cleanup is TTL-scoped to stale JSON payloads under
`<PROJECT_ROOT>/.codex/ticket-tmp/` and is confirmation-gated with
`--confirm-clean-stale-payloads`.

---

### `ticket_read.py`

**When to use**
List or query tickets without triggering the mutation pipeline. Safe to run at any time; no writes.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py list <tickets_dir> [--status open|in_progress|done|wontfix] [--priority high|normal|low] [--tag <tag>]
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py query <tickets_dir> <id_prefix>
uv run python -B <PLUGIN_ROOT>/scripts/ticket_read.py check <tickets_dir> <ticket_id> [--resolution done|wontfix]
```

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Empty results | Tickets directory doesn't exist | Verify `docs/tickets/` exists in project root |
| Parse errors in output | Malformed ticket YAML | Run `ticket_read.py check` or explicit doctor diagnostics to identify corrupt files |

---

### `ticket_triage.py`

**When to use**
Lower-level health check backend; called by `ticket_review.py`. Produces dashboard and audit summary without mutations.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <tickets_dir>
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py audit <tickets_dir> [--days <N>]
uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py doctor <tickets_dir> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT> [--runtime-probe-output <path>]
```

`ticket_triage.py doctor` is a backend/diagnostic path used by the doctor
wrapper, not the preferred user-facing doctor entrypoint.

**Failure modes**
| Symptom | Cause | Recovery |
|---------|-------|---------|
| Blocker cycle not summarized | Cyclic `blocked_by` references | Manual review; triage reports source data and should not persist reverse `blocks` edges |

---

### `ticket_audit.py`

**When to use**
Lower-level historical audit repair backend; called by `ticket_doctor.py repair-audit`.
Direct use is for debugging. User-facing repair should go through
`ticket_doctor.py`, which always dry-runs first.

**Inputs**
```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_audit.py repair <tickets_dir> [--fix | --dry-run]
```

Default is dry-run. Pass `--fix` to rewrite files; `--dry-run` remains accepted
but is redundant.

**Behavior:** Reads all existing historical `.audit/YYYY-MM-DD/*.jsonl` files, validates each line as parseable JSON. In repair mode: rewrites files with corrupt lines replaced, backs up originals with ISO8601 timestamp suffix.

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

### Target Candidate Flow

```text
Codex discovery -> target candidate -> deterministic validation -> write or mechanical result
```

Ticket should validate only the target candidate shape and deterministic ticket
state. It should not own semantic discovery, ranking, or workflow sequencing.

### Status Values

Target persisted statuses are `open`, `in_progress`, `done`, and `wontfix`.
Blockedness derives from `blocked_by`; it is not a persisted status.

### ID Allocation

IDs follow `T-YYYYMMDD-NN` format (e.g., `T-20260309-01`). The allocator scans live tickets to find the next available `NN` for today, zero-padded to 2 digits. Under concurrent load, exclusive file creation (`O_EXCL`) is used with bounded retry — but parallel subagent creates are not fully serialized (see Known Limitations).

### TOCTOU Protection

Target non-create writes require `expected_ticket_fingerprint`. If the live file
changed after candidate creation, the target result is `invalid_state` or
`blocked` with safe validation details.

---

## Failure and Recovery Matrix

| Symptom | Likely Cause | Diagnosis | Recovery |
|---------|-------------|-----------|---------|
| Write unavailable | Capture/update target candidate entrypoint is not exposed in this source slice | Check active skill docs | Summarize the candidate without writing |
| Corrupt audit JSONL lines | Interrupted write (crash during mutation) | Run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <tickets_dir>` | After explicit approval, run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <tickets_dir> --confirm-repair` |
| Stale `.codex/ticket-tmp/` payloads | Interrupted or abandoned diagnostic payload flow | Run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py diagnose <tickets_dir> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT>` | After explicit approval, run `uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads` |
| Installed runtime proof missing | Source docs do not prove cache/runtime state | Inspect `hooks/list` and `skills/list` in a separate proof lane | Refresh or prove runtime only when explicitly requested |

---

## Known Limitations

- Runtime-first source behavior is not installed runtime proof.
- Legacy source tests may still assert old behavior until source implementation
  is rebased.
- Installed runtime activation is a separate operator action and not implied by
  source edits.

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

### 6. Capture Availability Check

Read [skills/capture-ticket/SKILL.md](skills/capture-ticket/SKILL.md) and
confirm active create guidance says mutation is temporarily unavailable until
source exposes a live target-candidate entrypoint. This is a docs check only;
do not write a ticket.

### 7. Historical Audit Repair Verification

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <PROJECT_ROOT>/docs/tickets
# Dry-run should complete with no errors when historical audit files are present or absent
```

`references/ticket-contract.md` is a source-facing reference subordinate to
ADR 0006 and the May 30 control doc.
