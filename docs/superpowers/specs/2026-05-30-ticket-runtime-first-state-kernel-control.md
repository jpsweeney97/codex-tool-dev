# Ticket Runtime-First State-Kernel Control

## Status

Active implementation control for applying
`docs/decisions/0006-ticket-runtime-first-state-kernel.md`.

ADR 0006 is the accepted architecture decision. This document is the control
surface for applying that decision during Ticket contract migration, ticket-file
cutover, and source implementation.

For Ticket source work, "control surface" means implementation authority. Source
objects, tests, skills, references, README/HANDBOOK text, diagnostics, and
cross-plugin adapters either conform to this document, are patched toward it in
the same slice, or are explicitly labeled obsolete before they are used as
evidence.

This document is not runtime proof. Source changes, installed cache refresh, and
live runtime inventory remain separate evidence lanes.

## Authority

When this document conflicts with older Ticket plans, specs, README content,
handbook content, contract text, tests, or source comments, patch or explicitly
supersede the older surface before using it as implementation authority.

Compatibility is not a default. A legacy source surface may remain only when
this document names its current product purpose and the exact target contract it
feeds. Existing tests, installed-cache paths, Handoff payloads, historical
ticket files, or stale callers do not by themselves create a compatibility
requirement.

For the candidate-mutation source slice, the following Ticket-owned surfaces
must converge on the contract below before they are treated as target source:

- `CandidateMutation`;
- `GatewayMutation`;
- candidate mutation identity payloads;
- gateway application and result data;
- private pending-summary or operation-log events;
- external mutation inputs, including any Handoff-originated deferred-work
  input.

External inputs are not target contracts. For example, a Handoff
`DeferredWorkEnvelope` may survive only as an adapter input that is converted
into a target `create` candidate before Ticket validation, identity, gateway
application, and operation logging. If that adapter has no current product
purpose, drop it instead of reshaping Ticket around it.

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
- the target result envelope;
- the minimal private operation-log facts;
- the board reconciliation wrapper;
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

A candidate mutation has exactly this top-level shape:

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

- No other top-level keys are valid.
- `ticket_id` is required for every action except `create`.
- `target.fields` names target frontmatter fields from the target ticket schema:
  `title`, `status`, `priority`, `tags`, `related_paths`, or `blocked_by`.
  `id` is kernel-owned; callers do not target or propose it.
- `target.sections` names exact level-2 Markdown section headings. Required
  target sections are `Problem`, `Next Action`, and `Change History`; optional
  sections, including `Blocked On`, may be targeted only by exact heading.
- `target` names the user-visible ticket fields or sections the candidate
  intends to change. The deterministic `Change History` append for a successful
  write is a kernel side effect, not a caller-owned raw section rewrite.
- `proposed_change` contains only values for the named target fields or
  sections. It must not contain control keys, workflow labels, generated IDs,
  mutation IDs, evidence objects, or raw operation-log data.
- `expected_ticket_fingerprint` is required for every non-create write.
- `evidence_summary` is required and must be human-readable. Ticket validates
  that it is present and line-shaped; Ticket does not score, rank, or classify
  its semantics.
- Ticket computes candidate identity from canonical candidate content and the
  live target fingerprint. Callers do not supply authoritative identity values.
- Unknown fields are invalid.

Action-specific rules:

- `create`: `ticket_id` and `expected_ticket_fingerprint` are `null`.
  `proposed_change` supplies target ticket content such as `title`, `priority`,
  `status`, `tags`, `related_paths`, `blocked_by`, `Problem`, `Next Action`,
  and optional prose sections. New ticket status is `open` by default and may be
  `idea` when Codex chooses a visible parking status for a real but not-yet
  actionable follow-up, or `blocked` when the follow-up is active but not
  currently actionable. Ticket allocates `id`, validates the status-specific
  shape, and appends the first `Change History` entry.
- `update`: `ticket_id` and `expected_ticket_fingerprint` are present.
  `proposed_change` may touch only the named target fields or sections. It may
  set non-terminal `status` values only when the deterministic transition policy
  allows it. `idea` is pre-lifecycle: it may move to `open` when the user asks
  or when later work makes the idea concrete and actionable. An `idea -> open`
  promotion is an ordinary non-create write: it requires an expected ticket
  fingerprint, rewrites `Problem` and `Next Action` into normal actionable
  ticket language, and supplies a clear human reason for the `Change History`
  entry explaining why the idea became actionable. After promotion to `open`,
  the ticket follows the normal lifecycle. `open` and `blocked` are both active
  work states: `open` is currently actionable, and `blocked` is active but stuck.
  A ticket may move `open -> blocked` when a blocker appears and
  `blocked -> open` when the blocker resolves.
- `done`: `proposed_change.status` is `done`, the target ticket is `open` or
  `blocked`, and deterministic close-readiness checks pass. An `open` target
  names `status`; a `blocked` target also names `blocked_by` and `Blocked On`
  cleanup so the same write clears live blocker shape.
- `wontfix`: `proposed_change.status` is `wontfix`, the target ticket is `open`
  or `blocked`, and deterministic close-readiness checks pass. An `open` target
  names `status`; a `blocked` target also names `blocked_by` and `Blocked On`
  cleanup so the same write clears live blocker shape.
- `reopen`: `proposed_change.status` is `open` or `blocked`, and deterministic
  reopen checks pass. `reopen -> open` names normal open-ticket shape with no
  `Blocked On` and no live blocker fields. `reopen -> blocked` names valid
  blocked-ticket shape, including `Blocked On` and `blocked_by` when ticket-ID
  dependencies are present. The human reason belongs in `evidence_summary`, not
  in a separate `reopen_reason` field.
- `correct`: an ordinary candidate mutation that repairs a recent Ticket write.
  Its `target` and `proposed_change` follow the same rules as the underlying
  content change. If recent operation-log context identifies the corrected
  mutation, Ticket may use it to append `Corrects:` in `Change History`; callers
  do not add a separate correction-control field.

Status-specific ticket shape:

- `idea`: visible parking status for real but not-yet actionable work. It is not
  active work. `Next Action` should describe the condition that would make the
  idea worth promoting to `open`; Codex owns that writing convention.
- `open`: active and currently actionable work. It must not carry `Blocked On`
  or live blocker fields.
- `blocked`: active work that is not currently actionable. It requires
  `Blocked On` and `Next Action`. `Blocked On` is the visible prose condition
  stopping progress. `Next Action` should use a two-part convention: how to
  unblock the ticket, then what work resumes after unblocking. Codex owns that
  writing convention; Ticket validates only the required section shape.
- `done` and `wontfix`: terminal states. They must not carry `Blocked On` or
  live blocker fields.

`blocked_by` contains only ticket IDs. It is optional for `blocked` tickets and
invalid as a live blocker field on non-blocked tickets. Codex may unblock a
`blocked` ticket when the exact `blocked_by` ticket references are resolved or
when the ticket's `Blocked On` prose condition is no longer true. Unblocking
requires `blocked -> open`, with `target` naming `status`, `blocked_by`,
`Blocked On`, and `Next Action`; the same write clears `blocked_by`, removes
`Blocked On`, rewrites `Next Action` to the continuation step, and appends a
`Change History` reason. Historical blocker context belongs only in
`Change History`.

These legacy actions and fields are not aliases: `close`, `correction`,
`reprioritize`, `stale_cleanup`, `blocker_edit`, `refine`, `archive`, `delete`,
`history_repair`, `summarize`, `compact`, `pause_automation`,
`classify_intent`, `classify_confidence`, `dedup_fingerprint`,
`target_fingerprint`, `candidate_id`, `mutation_id`, `pending_summary_status`,
`RuntimeDecisionKind`, `conflict_reason`, `evidence`, `source_context`,
`envelope_version`, `emitted_at`, `key_file_paths`, `suggested_priority`, and
`effort`.

## Target Result Envelope

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
classification taxonomy, runtime decision taxonomy, candidate-routing label, or
stage-pipeline output.

`needs_discussion` is reserved for mechanical or policy boundaries where Ticket
understands the candidate but cannot apply it automatically without an explicit
human choice. Examples include ordinary candidates above the applicable per-turn
cap, terminal lifecycle batches outside reconciliation without explicit
linked-batch intent, operations outside the v1 write envelope, or missing target
choices that Ticket cannot infer mechanically. `needs_discussion` is not a Codex
confidence state, uncertainty score, semantic hesitation label, or substitute
for judging whether the human-readable reason is strong enough. If Codex can
make a bounded allowed write and state the reason honestly, it should emit a
valid candidate; if it cannot formulate the target or reason honestly, Codex
should discuss in ordinary chat instead of encoding uncertainty in Ticket state.

## Private Operation Log

The private operation log supports retry, idempotency, crash recovery before the
user-visible summary, and recent correction context. It is not a second audit
trail, a project record, or a workflow state machine.

The log may retain only these durable private facts:

- candidate identity;
- action, limited to the six target actions;
- target ticket ID, when any;
- target fields or sections;
- expected pre-write ticket fingerprint;
- post-write ticket fingerprint, when a write completed;
- evidence summary, only as the candidate's own one-line user-visible reason;
- whether the ticket write completed;
- whether the user-visible Ticket summary was emitted;
- short mechanical failure or pause reason;
- timestamp;
- bounded correction detail for recent corrections.

The log must not retain semantic ranking, classifier output, approval state,
commit disposition, `ticket_change_scope`, copied ticket content, runtime
decision kinds, pending-summary status taxonomies, evidence-kind taxonomies,
semantic action families, Handoff envelope metadata, or
classify/plan/preflight/execute stage outputs as durable facts.

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

## Board Reconciliation Wrapper

`reconcile_board` is a wrapper operation for handoff, status, completion, and
other claim points where Codex asks the user, future Codex, or the repository to
trust current ticket state. It is not a seventh candidate action. It finds
relevant tickets and emits ordinary `create`, `update`, `done`, `wontfix`,
`reopen`, or `correct` candidates, each validated, applied, reported, and
recovered independently.

Reconciliation must actively look for relevant tickets instead of updating only
the ticket Codex already has in mind. Relevant tickets include tickets matching
the current user request, touched files, branch or worktree context, explicit
ticket links, and any `open` or `blocked` ticket whose problem overlaps with
what Codex learned during the turn. Reconciliation normally focuses on active
`open` and `blocked` tickets, including unblocking blocked tickets when their
blockers have resolved. It inspects `idea` tickets only when the current work
could plausibly promote them to `open`.

At reconciliation points, Codex should update every relevant ticket it can
safely update and create missing tickets for every relevant follow-up it can
honestly describe. New follow-ups may be created directly as `open` when they
are actionable now or as `idea` when they are real enough to remember but not
yet actionable. Low importance, speculative value, or "maybe later" uncertainty
is not by itself a reason to drop a follow-up; Codex expresses that in visible
ticket content, priority, tags, or `idea` status. Duplicates and malformed or
unsupported ticket content remain blockers.

`idea` is a visible parking status in the same ticket board, not a second board
or private backlog. `idea` tickets are not expected to move unless the user asks
or later work makes the idea concrete and actionable. Ideas only move
`idea -> open`; they do not move directly to `done` or `wontfix`. For an
`idea` ticket, `Next Action` should describe the condition that would make the
idea worth promoting to `open`, not the task to execute now. Codex owns that
writing convention; Ticket validates that the required section exists.

`reconcile_board` may automatically promote an `idea` to `open` when the current
work makes it concrete and actionable. That promotion is an ordinary
reconciliation write with no special cap, and it still obeys ordinary
non-create write safety rules, including expected fingerprint, valid target, and
deterministic transition checks.

Reconciliation is best-effort across the whole relevant set. If one relevant
ticket is blocked by a concrete safety issue, Codex still updates the other
relevant tickets and reports the blocked item in the final message or handoff.
Incomplete ticket reconciliation qualifies claims about board freshness, but it
does not automatically invalidate claims about the underlying work. Ticket must
not persist reconciliation blockers as a separate workflow state.

## Agent-Primary Write Envelope

`agent_primary` authorizes valid candidate writes after deterministic runtime
checks. It does not authorize unbounded mutation.

Hard stops:

- no automatic delete;
- no automatic archive;
- no automatic history repair;
- no write to noncanonical active ticket paths after cutover;
- no write to unknown frontmatter keys;
- no persisted `blocks` reverse edge;
- no `Blocked On` section on non-blocked tickets;
- no `blocked_by` value outside ticket IDs or live blocked-ticket shape;
- no persistent `preview` mode.

Per-candidate limits:

- one candidate targets at most one ticket;
- one candidate performs exactly one action;
- one candidate changes only the named target fields or sections;
- optional sections are preserved byte-for-byte unless explicitly targeted;
- terminal transitions require an expected ticket fingerprint and current
  deterministic preconditions;
- blocked transitions require status-specific shape, including `Blocked On` for
  `blocked` targets and no `Blocked On` for non-blocked targets;
- non-create writes fail with `invalid_state` when the target ticket is missing,
  non-normalized after cutover, or fingerprint-stale.

Per-turn limits:

- default automatic writes are capped at five candidates per turn;
- terminal lifecycle writes are capped at one per turn unless the user
  explicitly requested a linked batch;
- `reconcile_board` at handoff, status, completion, or other claim points updates
  every relevant ticket it can safely update instead of stopping at the default
  automatic write cap or terminal lifecycle cap;
- candidates above the applicable cap return `needs_discussion`;
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
- invalid `blocked` ticket shapes, persisted `blocks`, `component`, confidence,
  refinement, workflow-stage, action-tier, commit-disposition, approval-state,
  classifier-output, or `ticket_change_scope` fields;
- missing or disordered `Problem`, `Next Action`, and `Change History`
  sections, plus missing `Blocked On` when status is `blocked`;
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
