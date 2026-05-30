# ADR 0006 — Ticket runtime-first rebaseline and state-kernel boundary

- **Status:** Accepted (2026-05-30)
- **Scope:** Ticket plugin product architecture, normalized ticket schema,
  runtime mutation authority, and post-cutover compatibility policy.
- **Supersedes where conflicting:**
  `docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md`
  and `docs/superpowers/plans/2026-05-27-ticket-runtime-first-autonomy-implementation.md`.
- **Implementation control:**
  `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
  applies this ADR during Ticket contract migration, ticket-file cutover, and
  source implementation.

## Context

The Ticket plugin's recent runtime-first autonomy work changed the product
model. Ticket should no longer behave like a command-first workflow engine that
turns explicit user requests into a four-stage mutation pipeline. The intended
steady state is that Codex notices relevant ticket work during ordinary thread
work, applies safe ticket mutations through the runtime path, and reports the
result concisely at the end of the turn.

That shift makes the old engine-centered architecture technical debt. The
four-stage `classify` -> `plan` -> `preflight` -> `execute` model, preview-first
manual mutation workflows, automatic approval objects, legacy ticket-generation
handling, and expanded runtime taxonomies preserve architecture that no longer
matches the desired product. The new design should preserve existing ticket
files as project records, but it should not preserve old architecture as a
compatibility layer.

## Decision

Runtime-first autonomy is the center of the Ticket plugin. The former core
engine is demoted to a deterministic ticket-state kernel: it validates,
normalizes, renders, fingerprints, and persists ticket files, and it enforces
hard ticket invariants. It does not own semantic discovery, fuzzy duplicate
judgment, prioritization, candidate relevance, or user-facing workflow
sequencing.

Codex owns semantic discovery. Codex may use Ticket query helpers to inspect
open tickets, then submit one normalized candidate mutation at a time to the
Ticket runtime. Ticket owns deterministic validation and persistence: allowed
fields, canonical paths, schema shape, status values, blocker references,
fingerprints, exact mechanical deduplication, `Change History` append rules,
pause/mode checks, idempotency, operation-log recovery, and file writes.

Manual affordances remain, but their authority collapses into the same
runtime-first path. Read remains a query/view surface. Capture and update
affordances become ways for Codex to form candidate mutations and send them
through the runtime-first path; they are not separate prepare/execute mutation
systems. Backlog triage remains read/query/reporting unless it feeds candidates
into the same runtime path.

There are exactly two durable runtime modes:

- `agent_primary`: a valid candidate mutation is authorized to write when it
  passes deterministic runtime checks.
- `discussion_only`: the same evaluator/candidate path runs, but write
  candidates become questions or proposals until the user gives explicit
  approval tied to the candidate identity.

Preview is not a durable runtime mode. It is a diagnostic option: evaluate a
candidate or turn context and show proposed mutations without writing, using the
same evaluator and validation rules.

Runtime responses use minimal mechanical states such as `ok`, `blocked`,
`needs_discussion`, `invalid_state`, and `no_change`. Human-facing reasons live
in structured facts and prose: ticket IDs, proposed action, evidence summary,
missing decision, and validation failure details. Do not rebuild a large
semantic enum taxonomy.

Automatic approval objects are removed from `agent_primary`. Authorization
comes from mode, candidate identity, deterministic fingerprints, runtime
validation, and write safety. Explicit approval remains only for
`discussion_only` follow-up, where Codex resubmits the same candidate with a
small user-approval fact tied to the candidate identity.

The private operation log stays small and private. It supports idempotency,
crash recovery before user-visible summary, and recent correction context. It is
not a second audit trail, workflow state machine, or long-term project record.
Durable project facts belong in each ticket's `Change History`; user-visible
semantic explanations belong in Codex's final summary and candidate evidence.
Ticket does not track git commit disposition.

## Normalized Ticket Schema

The post-cutover active ticket set lives under the canonical
`docs/tickets/T-YYYYMMDD-NN.md` path shape. Ticket IDs remain
`T-YYYYMMDD-NN`; existing IDs in that shape are preserved. Nonconforming legacy
IDs require an explicit mapping table during cutover and are never silently
reminted.

Ticket filenames are ID-only. The frontmatter `title` is canonical; the
Markdown body starts with `## Problem`, not a duplicated H1 title.

YAML frontmatter is closed and intentionally small:

- required: `id`, `title`, `status`, `priority`
- optional: `tags`, `related_paths`, `blocked_by`

Unknown frontmatter keys are invalid after cutover. The persisted lifecycle
statuses are `open`, `in_progress`, `done`, and `wontfix`. `blocked` is not a
status; blockedness is derived from non-empty `blocked_by`. Store only
`blocked_by`; derive reverse `blocks` views by scanning tickets. `priority` is
limited to `high`, `normal`, and `low`.

Required Markdown sections are exactly:

- `## Problem`
- `## Next Action`
- `## Change History`

Those three sections must exist and remain well-ordered. Other Markdown
sections are allowed as optional human prose, but they have no runtime meaning
unless a candidate mutation explicitly targets that section. By default,
automatic mutations may touch only frontmatter, `Problem`, `Next Action`, and
append to `Change History`. Optional sections are preserved byte-for-byte unless
explicitly targeted.

`Change History` uses minimal dated prose entries: timestamp, actor/source such
as `codex` or `user-approved`, and a short reason. It does not use controlled
label taxonomies. Corrections are ordinary candidate mutations with optional
`corrects_mutation_id` or `corrects_change` facts when known; they do not create
a separate public correction subsystem.

Closed tickets stay in the canonical tickets directory. Closure is represented
by `status: done` or `status: wontfix`. Moving files to an archive is a separate
maintenance operation, not normal lifecycle behavior and not autonomous runtime
behavior.

## Cutover Policy

Preserve existing ticket files as project records, but not old Ticket
architecture. Normalization is a deliberate repo-wide cutover, not lazy runtime
compatibility. A controlled workflow rewrites existing ticket files into the new
schema with a reviewable diff and focused validation. After cutover, runtime
mutation rejects non-normalized active tickets as invalid project state.

Normalization fails on ambiguity. For each ticket, the cutover either produces a
clean normalized ticket or emits a precise blocker naming the field, section, or
ID/path decision requiring human input. It must not carry unmapped legacy data
forward as comments, appendices, or opaque blobs.

The cutover rewrites ticket files only by default and emits an
external-reference report for IDs or paths found outside `docs/tickets/`.
External references are updated only in a separate explicit follow-up after the
mapping is reviewed.

Cutover normalizes in place when the target path is deterministic and
reviewable. It does not delete files or decide archival policy. If old closed
tickets live outside the canonical directory, the cutover may propose
deterministic moves to `docs/tickets/` with ID-only filenames, but applying
moves requires an explicit move step.

The cutover tool is temporary. It may live under a migration or tooling path
with tests during the cutover branch, but it must have an explicit sunset. After
this repo is normalized and runtime rejects old shapes, remove the migration
script or archive it outside the plugin runtime path. `ticket_doctor.py` should
diagnose post-cutover invariants, not carry legacy conversion indefinitely.

Cutover inventory may refine migration mechanics, but it does not preserve
deprecated architecture by default.

## Deprecated By This Decision

The following surfaces are deprecated as product architecture or runtime
contract. They may exist temporarily only as removal or cutover scaffolding:

- Four-stage `classify` / `plan` / `preflight` / `execute` as the Ticket
  product architecture.
- Preview-first `prepare` / `execute` mutation workflows as independent mutation
  semantics.
- Automatic approval objects for `agent_primary`.
- Persistent `preview` mode.
- Legacy generation support, gates, and permanent conversion accommodations.
- `closed-tickets/` as normal lifecycle storage.
- `blocked` as a persisted status.
- Persisted `blocks` reverse edges.
- `component`.
- Confidence, refinement-status, action-tier, workflow-stage, commit-disposition,
  approval-state, classifier-output, and `ticket_change_scope` fields.
- Semantic classifier, semantic deduplication, ranking, or ticket-selection code
  in Ticket runtime.
- Controlled `Change History` label taxonomies.
- Permanent compatibility aliases, wrappers, tests, or docs whose only purpose
  is to keep old Ticket architecture working.

## Consequences

- Future Ticket source work should patch the controlling docs and contracts
  toward this ADR before preserving or extending old architecture.
- The next implementation step is a short read-only cutover inventory against
  current `docs/tickets/`, using this ADR as the target shape. The inventory
  should report blockers and external references without mutating tickets.
- Runtime code can become simpler: one candidate mutation primitive, one
  deterministic state kernel, small modes, small response states, and small
  schema.
- Existing tests and docs that assert old workflow architecture should be
  rewritten or removed unless they protect a deterministic invariant retained by
  this ADR.
- This is intentionally not backwards-compatible. The compatibility boundary is
  the one-time normalization cutover for existing project ticket records.
