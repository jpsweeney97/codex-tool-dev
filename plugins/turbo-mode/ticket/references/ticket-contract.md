# Ticket Contract v1.0

Current source-facing reference for the Ticket plugin. ADR 0006 and the May 30
control doc supersede this reference where they conflict.

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This contract is source-authority documentation, not
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

The host-facing autonomy CLI, `direct_execute`, `gateway_required`,
`stale_plan`, `toctou_conflict`, direct `ticket_engine_agent.py execute`, and
the Workflow runner are deprecated or diagnostic source facts, not target
product architecture.

Direct `ticket_engine_agent.py execute` is not an autonomous mutation route in
this source slice. It fails closed with `gateway_required`.

`ticket_autonomy.py apply-turn` and source bookkeeping such as
`.codex/ticket-workspace/ticket.pending-summary.jsonl` are diagnostic source
state here, not target ticket content.

## Legacy Cutover Input

Legacy ticket records may still contain fenced YAML, slug filenames, old
statuses, old priorities, historical fields, and noncanonical sections. Those
records are input to a future read-only cutover inventory and later reviewed
normalization. This contract does not perform that inventory.

## Historical Changelog

Older release notes may describe prior Ticket behavior. Treat those entries as
historical changelog context rather than current authority.

## Maintenance And Diagnostics

Maintenance and diagnostics may use explicit source/cache/runtime probes,
historical audit repair, stale payload cleanup, runtime activation, diagnostic
dry-run or `preview` evidence, and exit-code mapping. They do not define normal
target ticket mutation.

Use `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...` for documented
source commands. Any remaining `python3` hook acceptance is legacy
compatibility.

Existing `docs/tickets/.audit/` files are historical artifacts. Recovery hints
such as `data.recovery_hint`, `retry_preview`, `cleanup_stale_preview`, and
`engine_gate_required` are maintenance or deprecated wrapper details, not target
result states.

Exit code diagnostics remain source-maintenance facts. Do not treat old
machine-state or code sets as target authority.

## Source Reference Boundaries

This contract is a source-facing reference subordinate to ADR 0006 and the May
30 control doc. It does not prove installed cache, hook registration, or live
runtime behavior.

## Storage

- Active post-cutover tickets: `docs/tickets/T-YYYYMMDD-NN.md`.
- Future autonomous durable history writes to `## Change History` on each
  affected ticket.
- Existing `docs/tickets/.audit/` files are historical artifacts. Future active
  Ticket history must not write there; `ticket_audit.py` and
  `ticket_doctor.py repair-audit` are read/repair tools for existing historical
  `.audit/` files only.
- Path boundary: all `tickets_dir` arguments must resolve inside the active
  project root.

## ID Allocation

- Target format: `T-YYYYMMDD-NN`.
- Existing IDs in that shape are preserved.
- Nonconforming legacy IDs require an explicit mapping table during cutover and
  are never silently reminted.

## Target Schema Reference

Target tickets use ID-only filenames and closed YAML frontmatter. Required
frontmatter keys are `id`, `title`, `status`, and `priority`. Optional
frontmatter keys are `tags`, `related_paths`, and `blocked_by`.

Target statuses are `open`, `in_progress`, `done`, and `wontfix`. Target
priorities are `high`, `normal`, and `low`. Blockedness derives from
`blocked_by`; reverse blocker views are derived by scanning tickets.

Required Markdown sections are `Problem`, `Next Action`, and `Change History`.
Optional sections are preserved unless a target candidate explicitly names the
section.

## Target Interfaces

Canonical script launcher: `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...`.
Hook acceptance of `python3` launchers is legacy compatibility only, not the
public contract.

Read-only helpers may list, query, and check tickets. Explicit maintenance
helpers may diagnose source/cache/storage state, repair historical audit files,
clean stale payloads after confirmation, or run installed-runtime activation
when the operator explicitly asks for that proof lane.

Active capture and update mutation guidance is temporarily unavailable until
source exposes a live entrypoint that accepts the target candidate mutation
contract.

## Autonomy Model

Durable target modes are `agent_primary` and `discussion_only`.

Config is strict local `.codex/ticket.local.md` JSON:

```json
{"schema":"codex.ticket.local.v1","mode":"agent_primary"}
```

Diagnostic preview is not a durable mode. Missing config, unknown keys,
Markdown, YAML frontmatter, comments, and older mode names must block instead
of silently falling back.

## Fingerprints And Write Safety

Target non-create writes require `expected_ticket_fingerprint`. Ticket computes
candidate identity from canonical candidate content plus the live target
fingerprint. Callers do not supply authoritative identity values.

## Integration

External consumers read target tickets as Markdown with YAML frontmatter under
`docs/tickets/`. This docs slice does not perform the read-only `docs/tickets/`
cutover inventory gate, normalize tickets, refresh the installed cache, or
prove live runtime behavior.

## Versioning

ADR 0006 and the May 30 control doc define the current target authority.

## 11. DeferredWorkEnvelope Schema (v1.0)

Bridge format for deferred work items from the handoff plugin. Envelopes are JSON files consumed by the ticket engine to create deferred tickets.

For v1.0, the envelope id is the envelope filename under `docs/tickets/.envelopes/`. Ticket owns this input contract and uses that id for idempotency.

### Storage

- Incoming: `docs/tickets/.envelopes/<timestamp>-<slug>.json`
- Processed: `docs/tickets/.envelopes/.processed/<filename>`
- Retention: Processed envelopes are retained indefinitely for now as the idempotency ledger and cross-plugin audit trail.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `envelope_version` | string | Must be "1.0" |
| `title` | string | Ticket title |
| `problem` | string | Problem description |
| `source` | object | `{type: string, ref: string, session: string}` |
| `emitted_at` | string | ISO 8601 UTC timestamp when envelope was created |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `context` | string | "" | Context section content |
| `prior_investigation` | string | "" | Prior investigation section content |
| `approach` | string | "" | Approach section content |
| `acceptance_criteria` | list[string] | [] | Acceptance criteria items |
| `verification` | string | "" | Verification command |
| `key_files` | list[object] | [] | `{file, role, look_for}` table rows |
| `key_file_paths` | list[string] | [] | File paths for dedup fingerprinting |
| `suggested_priority` | string | "medium" | One of: critical, high, medium, low |
| `suggested_tags` | list[string] | [] | Categorization tags |
| `effort` | string | "S" | Effort estimate (freeform) |

### Consumer Behavior

The ticket engine's envelope consumer:
1. Reads and validates the JSON against this schema
2. Maps fields to engine create vocabulary (no `status` — consumer synthesizes `open` with `defer.active: true`)
3. Sets `defer.reason` to `"deferred via envelope"` and `defer.deferred_at` to `emitted_at`
4. Creates ticket through the normal engine pipeline
5. Moves consumed envelope to `.processed/`

Before creating a ticket, ingest checks whether `.processed/<filename>` already exists. If it does, ingest returns a duplicate/replay outcome, preserves the incoming envelope, and creates no ticket. Similar-content envelopes with different filenames go through normal duplicate detection and are not auto-collapsed.

### Invariants

- Envelopes carry no `status` field — the consumer is the sole authority for initial ticket state
- `emitted_at` is required for provenance — it becomes `defer.deferred_at`
- Unknown fields are rejected (closed schema)
