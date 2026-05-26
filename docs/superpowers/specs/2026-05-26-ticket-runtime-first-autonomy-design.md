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

## Visibility And Audit

Autonomous mutations must not create noisy inline chatter during ordinary work.
Instead, every autonomous mutation appends a structured record to a per-turn
batch, and Codex emits one end-of-turn summary.

Each mutation record must include:

- ticket ID
- action kind
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

### `ticket_turn_batch.py`

Small collector that accumulates per-turn applied, skipped, and
discussion-required records, then renders the end-of-turn summary and audit
payload.

## Failure Handling

Failure handling is intentionally narrow:

- conflicting evidence for one ticket -> skip that ticket only
- delete, archive, or history-repair action -> route to discussion required and
  do not write
- candidate discovery failure -> perform no autonomous writes and record the
  failure in the turn batch
- one fanout target fails local validation or a write precondition -> skip that
  target unless the failure means the shared evidence model is invalid

The default failure posture for v1 is "do not write this candidate," not
"disable all autonomy for the turn."

## Rollout Sequence

Rollout should be incremental:

1. Wire the shared autonomy runtime and turn batch into update and review-style
   mutations first.
2. Add capture and agent entrypoint integration next.
3. Broaden candidate discovery and hygiene-driven fanout once the runtime layer
   is stable.
4. Keep doctor and history-repair paths explicitly discussion-gated and last.

This rollout order prioritizes the highest-value autonomous mutation paths
first while keeping the narrow human-discussion lane intact.

## Verification

The implementation plan derived from this design must include four test bands.

### 1. Policy decision tests

Prove that:

- ordinary non-destructive mutations route to `apply_autonomously`
- delete, archive, and history-repair actions route to
  `require_user_discussion`
- conflicting candidates route to `skip_due_to_conflict`

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
- emit one correct end-of-turn summary

### 4. Audit and summary tests

Prove that:

- the end-of-turn summary exactly reflects applied, skipped, and
  discussion-required outcomes
- the audit trail records the same structured facts as the user-facing summary
- autonomous writes are not hidden from the durable audit surface

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
