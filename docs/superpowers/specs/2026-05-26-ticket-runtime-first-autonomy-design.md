# Ticket Runtime-First Autonomy Design

## Status

This document is the active design baseline for replacing the superseded
Ticket authority-kernel plan family.

Superseded historical context:

- `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md`
- `docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md`
- `docs/superpowers/plans/2026-05-26-ticket-authority-kernel-slice1a1-reopen-reason-present.md`

The replacement direction is runtime-first and product-first. Ticket autonomy
must be decided at the real mutation choke points, not in a passive
source-local policy framework that is disconnected from write behavior.

## Purpose

Build a primarily autonomous Ticket plugin where Codex can create, update,
manage, open, close, reopen, reprioritize, maintain blockers, and perform
ticket hygiene during ordinary thread work without requiring an explicit
interactive confirmation round for each mutation.

The design goal is agent-primary ticket management with a narrow human
discussion lane:

- autonomous by default for nearly all non-destructive ticket mutations
- user discussion required only for delete, archive, and history-repair style
  actions
- thread-scoped triggering instead of explicit Ticket-only command invocation
- repo-wide open ticket set rather than one bound ticket per thread
- broad inference from thread context to candidate tickets
- multi-ticket fanout when several tickets plausibly fit the current work
- one batched end-of-turn summary instead of inline mutation narration

## Goals

- Put autonomy policy in the runtime write path for Ticket mutation entrypoints.
- Centralize autonomous write decisions in one shared runtime evaluator.
- Support aggressive autonomy for non-destructive lifecycle and metadata work.
- Allow repo-wide candidate selection from broad thread evidence.
- Support multi-ticket fanout when multiple tickets plausibly fit the work.
- Suppress writes only when evidence for a candidate ticket is conflicting.
- Produce one exact end-of-turn mutation summary and durable audit trail.
- Reuse existing Ticket engine and wrapper machinery where possible instead of
  inventing a parallel control-plane framework.

## Non-Goals

- Do not revive the authority-kernel or shard-registry design direction.
- Do not add a passive policy module that is not wired into runtime writes.
- Do not require explicit Ticket command invocation before autonomy can act.
- Do not make delete, archive, or history-repair autonomous in v1.
- Do not build an ambient background reconciler that mutates tickets outside
  the scope of the active thread.
- Do not require a probabilistic ranking system or one "best" ticket winner in
  v1.
- Do not duplicate autonomy logic independently in each wrapper or skill.

## Product Boundary

The v1 autonomy boundary is aggressive:

- autonomous: create, update, reprioritize, blocker edits, stale cleanup,
  refinement changes, `done`, `wontfix`, and `reopen`
- discussion-required: delete, archive, and history-repair style actions

Autonomy is thread-scoped:

- Codex may autonomously mutate tickets during ordinary work in the current
  thread
- autonomy is not limited to explicit `ticket-*` command sessions

Ticket scope is repo-wide and open-set:

- Codex may autonomously mutate any ticket in the repo when the current thread
  gives enough context to justify it

Evidence policy is broad:

- any plausible inferred relation from the current thread is enough to include
  a ticket candidate unless there is conflicting evidence

Visibility policy is batched:

- autonomous ticket mutations are reported in one end-of-turn summary with
  exact ticket IDs and reasons

Ambiguity policy is multi-ticket fanout:

- when multiple tickets plausibly fit the work, Codex should apply all
  plausible mutations that survive conflict checks instead of selecting a
  single winner or suppressing writes for ordinary ambiguity
- fanout is capped by action class; candidates above the cap route to the
  discussion-required lane instead of being silently skipped

Runtime modes are rollout and rollback controls, not a narrower product goal.
The steady-state mode is `agent_primary`:

- `discussion_only`: kill switch and rollback mode; no autonomous writes
- `preview`: dry-run rollout mode; builds candidates, evidence, fanout
  decisions, outbox records, and summaries without mutating ticket state
- `agent_primary`: normal v1 mode; autonomously applies all approved
  non-destructive Ticket mutations, including lifecycle `done`, `wontfix`, and
  `reopen`, subject to evidence floors, fanout caps, durable outbox, and
  engine-gateway enforcement

The mode system must not reintroduce confirmation-heavy behavior as the normal
path. `discussion_only` and `preview` exist to make rollout observable and
rollback cheap.

## Runtime Boundary

Autonomy must be enforced at the real Ticket mutation choke points:

- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_review.py` for backlog and hygiene
  mutations
- `plugins/turbo-mode/ticket/scripts/ticket_engine_agent.py`
- other low-level mutating engine entrypoints that can write Ticket state

`ticket_doctor.py` is explicitly outside normal autonomous mutation. Any
history-repair style action discovered there must route to the discussion
required lane.

Every mutating entrypoint must build a shared runtime decision input before any
write occurs. The runtime decision layer answers four operational questions:

1. Is this mutation autonomous, discussion-required, or skipped?
2. Which ticket or tickets may be touched?
3. Is thread evidence sufficient to justify open-set fanout?
4. What must be recorded for the end-of-turn batch summary and audit trail?

This design changes current preview-first behavior for autonomous writes:

- when the runtime decision is autonomous, the mutation may execute without a
  separate interactive confirmation prompt
- when the runtime decision is discussion-required, the mutation must not write
  until the user explicitly resolves it
- all autonomous writes must still produce the same audit-grade record quality
  as interactive flows

The enforcement point must be engine-owned. Wrappers may collect context and
construct inputs, but supported autonomous writes must not reach ticket-state
mutation unless the engine write path receives an approved autonomy decision.
`ticket_engine_core.py` or a small engine-owned write gateway must reject
autonomous writes that lack that decision. Adapter tests and static/text guards
are defense-in-depth; they are not the primary boundary.

## Decision Model

Each mutating path should construct one `AutonomyIntent` before any write.

Required fields:

- `action_kind`
- `candidate_tickets`
- `evidence`
- `proposed_mutation`
- `source_context`

`action_kind` covers at least:

- `create`
- `update`
- `reprioritize`
- `blocker_edit`
- `stale_cleanup`
- `refine`
- `done`
- `wontfix`
- `reopen`
- `archive`
- `history_repair`

The shared evaluator returns exactly one runtime decision per candidate ticket:

- `apply_autonomously`
- `require_user_discussion`
- `skip_due_to_conflict`

Decision rules:

- `archive`, `delete`, and history-repair style actions always return
  `require_user_discussion`
- ordinary non-destructive create, update, lifecycle, blocker, stale, and
  refinement actions may return `apply_autonomously`
- ambiguity is not a blocker by itself
- contradiction is the blocker; a ticket with conflicting evidence must return
  `skip_due_to_conflict`
- candidates that exceed the action-tier fanout cap must return
  `require_user_discussion`

The evaluator is operational, not semantic-taxonomy-first. It does not need a
large registry of policy nouns to be useful. It needs to make correct runtime
write decisions for the product boundary above.

## Evidence Model

Candidate ticket discovery must produce explicit evidence links for each
candidate ticket. Evidence may come from:

- explicit ticket IDs or prefixes in the thread
- explicit blocker, duplicate, or follow-up relationships
- file or component ownership already attached to the ticket
- current diff or failing tests that point at a ticket-owned surface
- backlog or hygiene state that the current work clearly resolves

Evidence is intentionally coarse in v1. Each candidate ticket receives one of
two evidence states:

- `plausible`
- `conflicting`

Rules:

- `plausible` means the ticket may be included in autonomous fanout
- `conflicting` means the ticket must be suppressed for this mutation
- v1 does not need numeric ranking or a single best candidate selector

The public evidence result stays coarse, but the evaluator must apply an
action-tiered evidence floor before `plausible` can become
`apply_autonomously`:

- Low-risk metadata and hygiene edits need at least one fresh plausible signal.
- Blocker and refinement edits need either explicit ticket linkage or
  file/component linkage plus current-thread relevance.
- Lifecycle `done`, `reopen`, and close-style mutations need stronger evidence:
  fresh ticket state, a current-thread reason that the ticket's work or failure
  state changed, and no blocker or conflict predicate.
- `wontfix` needs explicit user or product-decision evidence that the work
  should not be done, even under aggressive autonomy.

Fresh evidence means evidence derived from the current thread, current diff,
current failing/passing tests, or a ticket file read immediately before the
write decision. Stale ticket metadata may support discovery, but it must not be
the only evidence for lifecycle mutation.

The evaluator must treat these conditions as conflicting evidence:

- the user explicitly excludes the ticket or chooses a different ticket
- the ticket's current status does not match the proposed lifecycle action
- unresolved blockers, missing acceptance criteria, or failed validation make a
  close-style mutation unsafe
- the ticket changed after the evidence snapshot used for the decision
- file, component, or test evidence points at a different ticket-owned surface
  with stronger current-thread relevance
- the proposed mutation would duplicate an already-applied lifecycle or history
  entry rather than produce a no-op

## Fanout Semantics

Multi-ticket fanout works in four steps:

1. Build the candidate set from broad thread inference.
2. Drop any candidate ticket with conflicting evidence.
3. Apply the mutation independently to every remaining candidate ticket.
4. Record exact per-ticket reasons for the batched summary and audit trail.

Fanout is per-ticket fail-soft:

- one conflicting candidate must not block unrelated plausible candidates
- one candidate failing a local validation or write precondition must not abort
  the whole fanout unless that failure invalidates the shared evidence model

This design intentionally favors aggressive action when evidence is plausible
and non-conflicting. The safety boundary is contradiction, not general
uncertainty.

Fanout caps are action-tiered:

- metadata and hygiene edits have a soft cap of 5 tickets
- blocker and refinement edits have a soft cap of 3 tickets
- lifecycle `done` and `reopen` mutations have a hard cap of 1 ticket by
  default, raised to 2 only when the tickets are explicitly linked as the same
  batch
- `wontfix` has no fanout unless the same explicit user or product decision
  clearly applies to every candidate ticket

Soft cap overflow routes the excess candidates to `require_user_discussion`.
Hard cap overflow routes the whole over-cap lifecycle batch to
`require_user_discussion` unless explicit linked-batch evidence satisfies the
exception. Above-cap candidates must still be recorded in the turn batch with
the evidence that would have made them plausible and the cap that prevented
autonomous application.

Every autonomous mutation must have a stable `mutation_id` derived from the
turn, action kind, ticket ID, proposed mutation fingerprint, and evidence
fingerprint. Retrying the same turn-level fanout must be idempotent: it may
resume or complete an existing mutation record, but it must not duplicate
blocker edits, lifecycle transitions, reopen history entries, or audit rows.

## Visibility And Audit

Autonomous mutations must not create noisy inline chatter during ordinary work.
Instead, every autonomous mutation appends a structured record to a per-turn
batch, and Codex emits one end-of-turn summary.

Each mutation record must include:

- ticket ID
- action kind
- turn ID
- mutation ID
- short reason
- evidence links
- disposition: applied, skipped, or discussion-required
- compact before/after description of the changed fields or lifecycle state

The end-of-turn summary groups records into exactly three buckets:

- `Applied`
- `Skipped`
- `Discussion required`

The same structured record must also be written into the Ticket audit trail.
The chat summary is human-facing. The audit entry is machine-usable. Both must
describe the same mutation facts.

The per-turn batch must be durable, not only in memory. The runtime must use
an outbox model:

1. Allocate a `turn_id` and stable `mutation_id` before any autonomous write.
2. Write an outbox/audit attempt record before or atomically with the ticket
   mutation.
3. Fail closed before ticket mutation if the outbox/audit attempt record cannot
   be persisted.
4. Update the record to `applied`, `skipped`, or `discussion_required` after the
   decision or write result.
5. Render the end-of-turn summary from durable outbox records, then mark those
   records as summarized.

If summary emission fails after mutations succeeded, the next Ticket-aware turn
must detect unsummarized outbox records and emit a recovery summary before new
autonomous mutations. The recovery summary must use the same `Applied`,
`Skipped`, and `Discussion required` buckets as the normal end-of-turn summary.

Discussion-required records are pending-decision records. Each must include the
candidate ticket, proposed mutation, evidence, reason for discussion, expiry or
revalidation rule, and the user action that would authorize the write. A
discussion-required mutation may not execute until the pending record is
revalidated against current ticket state and resolved by the user.

## Components

The implementation should stay small and runtime-owned.

### `ticket_autonomy_runtime.py`

Shared runtime module that:

- builds `AutonomyIntent`
- evaluates `apply_autonomously`, `require_user_discussion`, and
  `skip_due_to_conflict`
- emits structured mutation records for the per-turn batch

### `ticket_candidate_discovery.py`

Focused helper that derives the open candidate set plus evidence links from:

- thread context
- explicit ticket mentions
- blocker and duplicate relationships
- current diff and test signals
- ticket metadata and hygiene state

This module owns broad inference and candidate expansion. It must not own write
authorization.

### Entry-point adapters

Existing mutation flows such as `ticket_capture.py`, `ticket_update.py`,
`ticket_review.py`, and agent-facing runtime entrypoints call the shared
autonomy runtime before they write. The autonomy policy must not be
reimplemented independently inside those wrappers.

Adapters are allowed to build `AutonomyIntent` context, but they are not allowed
to grant write authority. The engine-owned write path must be able to reject an
adapter call that omits, forges, or reuses an invalid autonomy decision.

### Engine-owned write gateway

`ticket_engine_core.py` or a small engine-owned helper must be the only path
that can apply autonomous ticket-state mutations. It validates the autonomy
decision, enforces idempotency, writes or updates the durable outbox record, and
then delegates to the existing ticket mutation mechanics.

### `ticket_turn_batch.py`

Durable outbox-backed collector that accumulates per-turn applied, skipped, and
discussion-required records, renders the end-of-turn summary and audit payload,
marks summarized records, and emits recovery summaries for unsummarized records
from earlier turns.

## Failure Handling

Failure handling is intentionally narrow:

- conflicting evidence for one ticket -> skip that ticket only
- delete, archive, or history-repair action -> route to discussion required and
  do not write
- `discussion_only` mode -> route autonomous candidates to discussion required
  and do not write
- `preview` mode -> record preview dispositions and summaries, but do not write
  ticket state
- candidate discovery failure -> perform no autonomous writes and record the
  failure in the turn batch
- one fanout target fails local validation or a write precondition -> skip that
  target unless the failure means the shared evidence model is invalid
- outbox/audit attempt record cannot be persisted before write -> fail closed
  and perform no ticket mutation for that candidate
- end-of-turn summary emission fails after successful mutations -> leave durable
  unsummarized records for recovery-summary emission on the next Ticket-aware
  turn
- retry observes an existing `mutation_id` -> resume or report the existing
  record instead of applying the mutation a second time

The default failure posture for v1 is "do not write this candidate," not
"disable all autonomy for the turn."

## Rollout Sequence

Rollout should be incremental:

1. Ship `discussion_only` and `preview` mode handling with the shared autonomy
   runtime and durable turn batch.
2. Wire the shared autonomy runtime and turn batch into update and review-style
   mutations in `preview` mode first.
3. Enable `agent_primary` for update and review-style mutations after preview
   evidence shows the outbox, recovery summary, and cap behavior are stable.
4. Add capture and agent entrypoint integration next.
5. Broaden candidate discovery and hygiene-driven fanout once the runtime layer
   is stable.
6. Keep doctor and history-repair paths explicitly discussion-gated and last.

This rollout order prioritizes the highest-value autonomous mutation paths
first while keeping the narrow human-discussion lane intact.

Rollback means switching the project mode to `discussion_only`. Downgrade from
`agent_primary` to `preview` or `discussion_only` must prevent new autonomous
writes immediately while preserving existing outbox records for summary and
audit recovery.

## Verification

The implementation plan derived from this design must include six test bands.

### 1. Policy decision tests

Prove that:

- ordinary non-destructive mutations route to `apply_autonomously`
- delete, archive, and history-repair actions route to
  `require_user_discussion`
- conflicting candidates route to `skip_due_to_conflict`
- `discussion_only` mode prevents autonomous writes
- `preview` mode records decisions without ticket-state mutation
- `agent_primary` mode applies approved non-destructive mutations, including
  lifecycle `done`, `wontfix`, and `reopen`
- action-tier evidence floors are enforced for metadata, blocker/refinement,
  lifecycle, and `wontfix` mutations
- above-cap candidates route to `require_user_discussion`

### 2. Candidate discovery tests

Prove broad inference from:

- explicit thread references
- blocker and duplicate relationships
- file and component ownership
- diff and failing-test signals
- hygiene and stale-state signals

### 3. Fanout integration tests

Prove one thread can:

- mutate multiple plausible tickets
- skip contradictory candidates without blocking the whole batch
- route above-cap candidates to discussion required
- retry partial fanout without duplicate blocker edits, lifecycle transitions,
  reopen history entries, or audit rows
- emit one correct end-of-turn summary

### 4. Audit and summary tests

Prove that:

- the end-of-turn summary exactly reflects applied, skipped, and
  discussion-required outcomes
- the audit trail records the same structured facts as the user-facing summary
- autonomous writes are not hidden from the durable audit surface
- autonomous mutation fails closed when the outbox/audit attempt record cannot
  be persisted
- unsummarized durable outbox records produce a recovery summary before the next
  autonomous mutation

### 5. Bypass prevention tests

Prove that:

- supported mutating entrypoints cannot write ticket state without an approved
  autonomy decision when running in autonomous mode
- wrappers cannot forge or reuse stale autonomy decisions
- static or text guards flag new ticket-state write paths outside the
  engine-owned gateway, except explicit maintenance or doctor paths

### 6. Rollback mode tests

Prove that:

- downgrading from `agent_primary` to `preview` or `discussion_only` prevents
  new autonomous writes immediately
- existing outbox records remain available for summary and audit recovery after
  downgrade
- `discussion_only` can be used as a kill switch without deleting or corrupting
  prior autonomous mutation records

## Why This Replaces The Authority-Kernel Direction

The authority-kernel plans drifted toward a passive semantic framework. That
direction did not directly build an agent-primary autonomous ticket operator.

This design replaces that approach with:

- runtime-owned policy instead of passive source-local policy
- direct integration at write-time choke points instead of deferred proof
  artifacts
- product-level mutation decisions instead of fine-grained policy taxonomy
- centralized operational behavior instead of wrapper-local duplication

The result is a plan family that is aligned with the actual product goal:
Codex should primarily manage tickets autonomously during work, with a narrow,
explicit discussion lane for destructive or history-repair operations.
