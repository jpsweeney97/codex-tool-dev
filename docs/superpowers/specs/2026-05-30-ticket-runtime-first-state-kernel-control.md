# Ticket Runtime-First State-Kernel Control

## Status

Active implementation control for applying
`docs/decisions/0006-ticket-runtime-first-state-kernel.md`.

ADR 0006 is the accepted architecture decision. This document is the control
surface for applying that decision during Ticket contract migration, ticket-file
cutover, and source implementation.

This document is not runtime proof. Source changes, installed cache refresh, and
live runtime inventory remain separate evidence lanes.

## Authority

When this document conflicts with older Ticket plans, specs, README content,
handbook content, contract text, tests, or source comments, patch or explicitly
supersede the older surface before using it as implementation authority.

In particular, do not preserve old Ticket architecture only because it remains
documented in:

- `docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md`
- `docs/superpowers/plans/2026-05-27-ticket-runtime-first-autonomy-implementation.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/tests/`

The first implementation slice must update or mark superseded any controlling
Ticket contract section it touches. Tests that encode deprecated architecture
should be rewritten or removed unless they protect a deterministic invariant
kept by ADR 0006.

## Scope

This document controls:

- the runtime-first candidate mutation contract;
- the minimal private operation-log facts;
- the hard write envelope for `agent_primary`;
- the cutover inventory and completion gate;
- preview as a diagnostic affordance;
- `Change History` append grammar.

This document does not control installed plugin cache state, live runtime
activation, publishing, or long-term ticket archival policy.

## Candidate Mutation Contract

Ticket accepts one candidate mutation at a time. A wrapper may accept a list for
operator convenience, but each candidate is validated, applied, reported, and
recovered independently.

A candidate mutation has this minimum shape:

```json
{
  "action": "create|update|done|wontfix|reopen|correct",
  "ticket_id": "T-YYYYMMDD-NN or null for create",
  "target": {
    "fields": ["priority", "tags"],
    "sections": ["Problem", "Next Action"]
  },
  "proposed_change": {},
  "expected_ticket_fingerprint": "fingerprint or null",
  "evidence_summary": "one short human-readable reason"
}
```

Rules:

- `ticket_id` is required for every action except `create`.
- `target` names the exact frontmatter fields or Markdown sections the
  candidate intends to change.
- `proposed_change` contains only values for the named target fields or
  sections.
- `expected_ticket_fingerprint` is required for every non-create write.
- `evidence_summary` is required and must be human-readable. Ticket validates
  that it is present and line-shaped; Ticket does not score, rank, or classify
  its semantics.
- Ticket computes candidate identity from canonical candidate content and the
  live target fingerprint. Callers do not supply authoritative identity values.
- Unknown fields are invalid.

The result envelope uses only minimal mechanical states:

```json
{
  "state": "ok|blocked|needs_discussion|invalid_state|no_change",
  "ticket_id": "T-YYYYMMDD-NN or null",
  "message": "one safe sentence",
  "data": {}
}
```

`data` may include ticket path, validation details, candidate identity,
post-write fingerprint, or discussion prompt facts. It must not carry a semantic
classification taxonomy.

## Private Operation Log

The private operation log supports retry, idempotency, crash recovery before the
user-visible summary, and recent correction context. It is not a second audit
trail, a project record, or a workflow state machine.

The log may retain only these durable private facts:

- candidate identity;
- action;
- target ticket ID, when any;
- target fields or sections;
- expected pre-write ticket fingerprint;
- post-write ticket fingerprint, when a write completed;
- whether the ticket write completed;
- whether the user-visible Ticket summary was emitted;
- short failure or pause reason;
- timestamp;
- bounded correction detail for recent corrections.

The log must not retain semantic ranking, classifier output, approval state,
commit disposition, `ticket_change_scope`, or copied ticket content as durable
facts.

Recovery must answer only these questions:

- Was this exact candidate already applied?
- If a prior attempt crashed, is the current ticket state the expected pre-write
  state, the expected post-write state, or neither?
- Does Codex still need to report a user-visible Ticket summary?
- Is recent correction detail still available?

If the log is unreadable, internally contradictory, or cannot be updated
atomically, automatic Ticket mutation pauses and returns `blocked`.

Bounded correction detail expires after 14 days or the most recent 500 retained
correction-ready events, whichever is smaller. Compaction may retain only
lightweight facts: ticket ID, action, timestamp, reason, and correction target.

## Agent-Primary Write Envelope

`agent_primary` authorizes valid candidate writes after deterministic runtime
checks. It does not authorize unbounded mutation.

Hard stops:

- no automatic delete;
- no automatic archive;
- no automatic history repair;
- no write to noncanonical active ticket paths after cutover;
- no write to unknown frontmatter keys;
- no persisted `blocked` status;
- no persisted `blocks` reverse edge;
- no persistent `preview` mode.

Per-candidate limits:

- one candidate targets at most one ticket;
- one candidate performs exactly one action;
- one candidate changes only the named target fields or sections;
- optional sections are preserved byte-for-byte unless explicitly targeted;
- terminal transitions require an expected ticket fingerprint and current
  deterministic preconditions;
- non-create writes fail with `invalid_state` when the target ticket is missing,
  non-normalized after cutover, or fingerprint-stale.

Per-turn limits:

- default automatic writes are capped at five candidates per turn;
- terminal lifecycle writes are capped at one per turn unless the user
  explicitly requested a linked batch;
- candidates above the cap return `needs_discussion`;
- a wrapper list reports independent per-candidate results and never hides
  partial failure.

These limits are mechanical safety stops. Codex still owns semantic discovery,
candidate selection, prioritization, and duplicate judgment.

## Cutover Inventory And Completion Gate

The next cutover step is read-only. It must inspect current `docs/tickets/`
state against ADR 0006 and this control document without writing files.

The inventory must report:

- every ticket source path;
- current ticket ID and proposed target ID;
- current filename and proposed ID-only filename;
- current metadata container, including fenced YAML versus YAML frontmatter;
- unknown frontmatter keys;
- status and priority values requiring mapping;
- persisted `blocked`, `blocks`, `component`, confidence, refinement,
  workflow-stage, action-tier, commit-disposition, approval-state,
  classifier-output, or `ticket_change_scope` fields;
- missing or disordered `Problem`, `Next Action`, and `Change History`
  sections;
- optional sections to preserve;
- deterministic move or rewrite proposal;
- precise blocker when deterministic normalization is impossible;
- external references to old IDs or paths outside `docs/tickets/`.

The inventory output must include an explicit applied state:

- `inventory_only`: no files changed;
- `ready_to_apply`: all mappings are deterministic and blockers are empty;
- `blocked`: at least one ticket needs human mapping, section, or field input;
- `applied`: only for a later mutating cutover step after review.

Runtime may reject old active ticket shapes only after all of these are true:

- inventory reports no blockers;
- source-to-target mappings were reviewed;
- ticket-file normalization was applied in a separate reviewed diff;
- external-reference report was reviewed;
- Ticket contract, README, handbook, and tests no longer present old shapes as
  current authority;
- focused validation passes for normalized tickets and no noncanonical active
  ticket paths remain.

## Preview Ownership

Preview is not a durable runtime mode.

After the rebaseline implementation, `.codex/ticket.local.md` accepts only:

- `agent_primary`
- `discussion_only`

Preview survives only as a diagnostic invocation option, such as a dry-run flag
or explicit diagnostic command. It uses the same evaluator and validation rules
as a real candidate path, but it does not write tickets, write private operation
log state as if a mutation occurred, or create a third product mode.

If a durable local config still contains `preview` after the rebaseline, mode
resolution returns setup-required or invalid-state handling. It must not silently
fall back to `agent_primary` or preserve preview as a compatibility mode.

## Change History Grammar

`Change History` uses deterministic syntax without semantic label taxonomy.

Entry shape:

```markdown
- <timestamp> | <actor> | <reason>
- <timestamp> | <actor> | <reason> Corrects: <reference>.
```

Validation rules:

- `timestamp` is ISO 8601 UTC, for example `2026-05-30T21:06:10Z`.
- `actor` is a source value such as `codex`, `user-approved`, or `migration`.
- `actor` is not a workflow label and must not encode action type.
- `reason` is one short sentence with no newline or raw `|`.
- `Corrects:` is optional and names a candidate identity, mutation identity, or
  short human reference.
- Unknown semantic labels such as `auto-create`, `auto-update`, or
  `discussion-approved` are not valid new grammar after cutover.

Ticket validates shape only. Codex owns the wording of the human reason.

## Verification Gate For This Control Surface

Before implementation uses this document as authority, verify:

- ADR 0006 links to this document.
- `git diff --check` passes.
- Any changed Markdown renders as ordinary Markdown.
- The first implementation slice names which conflicting contract sections it
  updates or supersedes.
