# Ticket Runtime-First Autonomy Design

## Status

This document is the active design baseline for replacing the superseded
Ticket authority-kernel plan family.

Source implementation should start only after this design baseline is landed or
rebased onto `main`, then branch from `main` using the repository's normal
branch policy. If implementation must begin before `main` contains the baseline,
record an explicit user-approved docs-baseline exception in the implementation
closeout.

Superseded historical context:

- `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md`
- `docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md`
- `docs/superpowers/plans/2026-05-26-ticket-authority-kernel-slice1a1-reopen-reason-present.md`

The replacement direction is runtime-first and product-first. Ticket autonomy
must be decided at the real mutation choke points, not in a passive
source-local policy framework that is disconnected from write behavior.

## Replacement Posture

This design replaces the soon-to-be-superseded Ticket autonomy model. It may
reuse current Ticket plugin components, schemas, and workflows when they are
useful, but it is not constrained by old modes, labels, formats,
compatibility aliases, workflows, or architecture.

Do not add compatibility accommodations for superseded behavior unless this
document explicitly names them as required for project-state integrity or a
chosen migration boundary. Prefer the cleaner runtime-first design over
preserving legacy semantics that would make the new system heavier, less
clear, or less trustworthy.

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
- Do not preserve superseded Ticket modes, labels, formats, workflows, or
  compatibility aliases unless this design explicitly requires that boundary.
- Do not require explicit Ticket command invocation before autonomy can act.
- Do not make delete, archive, or history-repair autonomous in v1.
- Do not build an ambient background reconciler that mutates tickets outside
  the scope of the active thread.
- Do not require a preview-only rollout phase before real automatic Ticket
  changes can run after the user chooses automatic mode.
- Do not require a probabilistic ranking system or one "best" ticket winner in
  v1.
- Do not duplicate autonomy logic independently in each wrapper or skill.

## Resolved Product Decisions

- Codex should notice and apply Ticket updates during normal work, without an
  explicit Ticket command, then show a concise end-of-turn summary.
- Codex collects candidate Ticket changes during the turn and applies approved
  automatic changes near the end of the turn, using the full turn context before
  writing.
- The Codex host/thread runtime owns the turn boundary because it knows when a
  turn is ending. The Ticket plugin owns mutation rules, approval validation,
  write safety, and ticket-state mutation. Avoid the bare term "app" for this
  boundary because it blurs host/runtime ownership with Ticket ownership.
- Keep the Codex host/thread runtime thin. It provides `thread_id`, `turn_id`,
  final turn context, current pause or mode signal, and renders the Ticket summary or
  question projection returned by Ticket. It must not understand Ticket
  candidates, approvals, partial failure states, raw ledger records, or ticket
  mutation internals.
- Start the host-facing Ticket autonomy API as a lightweight JSON-in/JSON-out
  CLI with Ticket-level commands such as `recover` and `apply-turn`. Do not
  expose raw ledger commands such as append, consume approval, or mark
  summarized as host-facing APIs.
- Use narrow hard rules for safety and trust: no automatic delete, archive, or
  history repair; pause when pending-summary bookkeeping is unhealthy; respect
  the thread-scoped mode snapshot; require a fresh one-use approval for each
  automatic change; and do not guess when correction evidence is gone.
- The autonomous write gateway is field-authoritative. An automatic action is
  allowed only with the exact fields that action permits; forbidden fields must
  route to discussion or fail closed before live engine dispatch.
- Treat an explicit chat request to pause Ticket automation as workspace-wide
  for the current checkout before the next autonomous write. Thread-scoped mode
  may still be cached for normal config reads, but the engine-owned write
  gateway must recheck the workspace pause marker immediately before consuming
  approval and mutating ticket state.
- One-use approvals expire quickly. They are valid only within the current
  turn, for no more than 10 minutes after creation, and are consumed by the
  first matching write.
- Leave Codex judgment for semantic work: relevance, priority, ticket creation
  quality, summary wording, identifying what deserves a new ticket, deciding
  whether a low-risk correction is obvious, and choosing the highest-priority
  `needs discussion` question.
- Use one Ticket-owned local operational ledger at
  `.codex/ticket-workspace/ticket.pending-summary.jsonl` for unsummarized and
  recent correction-ready records. Keep it, sibling temporary or lock files,
  and a small sibling `.codex/ticket-workspace/AGENTS.md` out of git with
  explicit ignore rules.
- Codex host/thread runtime may reference Ticket automation state only through
  Ticket-owned CLI projections. The raw operational ledger is private Ticket
  state, not a host/runtime contract and not a second ticket database.
- Use a sibling lock/temp-file flow inside `.codex/ticket-workspace/` for
  pending-summary writes. Codex should wait briefly when another writer is
  active, and pause automatic Ticket updates if it cannot update the log
  cleanly.
- Treat the pending-summary file as append-first JSONL. Normal operation appends
  one JSON object per event. Cleanup and compaction may later rewrite the file
  under the same lock using a temporary file and atomic replace.
- Normal operation does not edit old JSONL lines to mark entries summarized,
  corrected, or inactive. It appends follow-up event lines that reference the
  original mutation ID. Compaction may later collapse old event chains into a
  smaller summary.
- Every pending-summary JSONL entry uses a strict envelope plus typed
  `details`. The envelope has finite `event_type`, `status`, `action`, and
  `decision` values; event-specific fields live only under `details`.
  `event_id` identifies the logical JSONL event; `mutation_id` identifies the
  original ticket change or pending action the line belongs to.
- `event_id` is repeatable for retries of the same event. If Codex retries the
  same receipt after a crash or timeout, it must reuse the same `event_id`.
  Genuinely new follow-up events get new `event_id` values.
- `event_id`, `mutation_id`, and `approval_id` are deterministic IDs derived
  from canonical inputs, not random IDs. This makes retries, duplicate
  detection, crash recovery, and one-use approval validation reliable.
- `turn_id` stays runtime-assigned by the Codex host/thread runtime. It
  represents the actual turn boundary; deterministic IDs provide retry and
  write safety inside that turn.
- Runtime-first mode snapshots are keyed by `(project_root, thread_id)`.
  `thread_id` identifies the ongoing Codex conversation for mode stability,
  `project_root` scopes it to the checkout, and `turn_id` remains a per-turn
  evaluation/write boundary. Legacy hook `session_id` remains valid for
  hook-mediated engine payloads but is not the runtime-first mode-snapshot key.
- Keep full before/after correction detail only on correction-ready entries in
  the local pending-summary log for 14 days, capped at the most recent 500
  correction-ready events. Older detail compacts into lightweight facts: ticket
  ID, action, timestamp, reason, and prior commit hash only when referencing an
  already-created commit is useful.
- Store long-term lightweight audit facts in the affected ticket's
  `## Change History` section. Do not add a new global committed audit log in
  v1. If `## Change History` cannot hold the durable facts cleanly, pause or
  defer the automatic Ticket update.
- Move future autonomous durable history entirely into `## Change History` plus
  local pending-summary bookkeeping. Existing `docs/tickets/.audit/` files are
  historical artifacts unless a later migration explicitly chooses otherwise.
- Include an immediate migration step that disables future `.audit/` writes.
  The current `.audit/` write path is not in use, so v1 should prevent new
  audit artifacts now instead of waiting for the autonomous runtime replacement.
  The same implementation commit should update README/HANDBOOK so they stop
  presenting `.audit/` as active behavior.
- The `.audit/` migration should delete or cleanly bypass the write path where
  practical, but preserve read/doctor support for existing historical `.audit/`
  files until a separate migration decides their fate.
- Make `## Change History` a required Ticket contract section for durable
  lightweight history facts. Entries use compact pipe-separated bullets:
  `<timestamp> | <label> | <reason>`, with optional `Prior commit: <hash>.`
  only when referencing an already-created commit is genuinely useful. Keep YAML
  for current metadata, not growing history.
- `## Change History` labels are controlled, not ad hoc. Initial labels are
  `auto-create`, `auto-update`, `auto-blocker`, `auto-close`, `auto-reopen`,
  `correction`, and `discussion-approved`, each with contract-defined meaning.
- Do not design compatibility aliases or accommodations for superseded
  `## Change History` labels. Automatic writers must validate new entries
  against the finite label set.
- Do not try to write a commit's own hash into the same committed ticket
  change. The ticket file is written before that hash exists. The end-of-turn
  summary may include the created commit hash; later history entries may
  reference earlier commit hashes when genuinely useful.
- Automatic Ticket changes should write their `## Change History` entry in the
  same ticket update whenever possible. If Codex cannot update `## Change
  History` cleanly, pause or defer the automatic ticket change rather than
  leave durable project history incomplete.
- Distinguish ticket-state completion from turn cleanup. A mutation is
  `applied` when the ticket file, required `## Change History` entry, and
  pending-summary ledger outcome are written. A turn is cleanly complete only
  when Ticket records a commit disposition: `commit_recorded`,
  `commit_bundled_with_work`, or `commit_deferred` with a reason. Any
  end-of-turn summary for a ticket write must include that commit disposition.
- Do not require repo-wide `## Change History` backfill before `agent_primary`.
  The first automatic mutation for a ticket may create `## Change History` when
  it is missing, in the same ticket-file mutation, if the ticket is otherwise
  parseable and the insertion point is deterministic. Provide an explicit
  `migrate-change-history --dry-run/--apply` maintenance command for teams that
  want to normalize existing tickets before automatic mode.
- If the pending-summary log cannot be written, appended with follow-up status
  events, validated, or compacted under its limits, pause automatic Ticket
  updates and report the concise pause reason. User-directed Ticket work may
  still proceed through the normal discussion or confirmation path.
- User-triggered correction is automatic for ordinary automatic changes. If the
  user says an automatic Ticket update was wrong, Codex should correct or
  reverse it without another approval round, except delete, archive, and history
  repair still require discussion.
- Automatic correction may reverse or amend current ticket state and add a
  correction `## Change History` entry. It must not delete records, rewrite
  `## Change History`, remove prior audit entries, or alter git history; those
  actions are history repair and require discussion.
- Automatic local commits are the repo-wide default for completed Codex work.
  Commit related automatic Ticket updates with the same verified work commit;
  create a small ticket-only local commit only when the turn produced automatic
  Ticket updates without related code/doc changes.
- Do not push automatic Ticket commits unless the user explicitly asks to
  publish.
- Reuse `.codex/ticket.local.md` for the new mode system. There is no required
  compatibility migration for the old `suggest`, `auto_audit`, and
  `auto_silent` values because no existing repo uses them in
  `.codex/ticket.local.md`.
- Use strict JSON as the entire contents of `.codex/ticket.local.md`. The
  `.md` path is the existing local config surface, not a Markdown parsing
  contract.
- Missing or invalid config should trigger a guided setup prompt with
  `Automatic` mapped to `agent_primary` and `Ask first` mapped to
  `discussion_only`; keep `preview` as an advanced/manual config value.
  After the user chooses, Codex writes or repairs `.codex/ticket.local.md`
  immediately and continues without a second confirmation.
- Keep `.codex/ticket.local.md` local-only and ignored. The active automation
  mode is a user/workspace preference, not committed project state. Setup must
  ensure the file is ignored using the repo's existing ignore style; if that
  requires a `.gitignore` edit, commit the ignore-rule change as normal project
  policy while leaving the config file unstaged.

## Product Boundary

The v1 autonomy boundary is aggressive:

- autonomous: create, update, reprioritize, blocker edits, stale cleanup,
  refinement changes, `done`, `wontfix`, and `reopen`
- discussion-required: delete, archive, and history-repair style actions

Automatic `done` and `wontfix` are close-status changes only. They must not
archive ticket files as part of the same automatic action. If a candidate or
gateway payload includes `archive`, `archive: true`, or another non-allowlisted
close field, it is an archive-shaped or unsupported close request and must route
to `require_user_discussion` or fail closed before engine dispatch. Do not
silently strip forbidden fields and proceed.

Autonomy is thread-scoped:

- Codex may autonomously mutate tickets during ordinary work in the current
  thread
- autonomy is not limited to explicit `ticket-*` command sessions

Ticket scope is repo-wide and open-set:

- Codex may autonomously mutate any ticket in the repo when the current thread
  gives enough context to justify it

Automatic creation is in scope:

- Codex may create new tickets during normal work when it can name the problem,
  affected area or file/component, and a concrete next action
- full acceptance criteria are useful but not required for automatic creation
- vague ideas, broad cleanup themes, and "maybe later" items route to
  `require_user_discussion`

Evidence policy is broad:

- any plausible inferred relation from the current thread is enough to include
  a ticket candidate unless there is conflicting evidence

Visibility policy is batched:

- autonomous ticket mutations are reported in one concise end-of-turn
  `Ticket updates` mini-section with counts, exact ticket IDs, and one short
  reason per changed ticket
- if no Ticket changes were made and no decisions need discussion, Codex says
  nothing about tickets in the final response

Ambiguity policy is multi-ticket fanout:

- when multiple tickets plausibly fit the work, Codex should apply all
  plausible mutations that survive conflict checks instead of selecting a
  single winner or suppressing writes for ordinary ambiguity
- fanout is capped by action class; candidates above the cap route to the
  discussion-required lane instead of being silently skipped

Runtime modes are session controls, not a narrower product goal. The
steady-state mode is `agent_primary`:

- `discussion_only`: kill switch and rollback mode; no autonomous writes
- `preview`: explicit dry-run diagnostic mode; builds candidates, evidence,
  fanout decisions, pending-summary records, and summaries without mutating
  ticket state
- `agent_primary`: normal v1 mode; autonomously applies all approved
  non-destructive Ticket mutations, including create, lifecycle `done`,
  `wontfix`, and `reopen`, subject to evidence floors, fanout caps, durable
  pending-summary bookkeeping, and engine-gateway enforcement

The mode system must not reintroduce confirmation-heavy behavior as the normal
path. When a user chooses automatic mode, Codex should begin making real
automatic Ticket changes immediately rather than forcing a preview-only rollout
phase.

The project mode lives in the existing repo-local `.codex/ticket.local.md`
config file. Keep that file local-only and ignored; the active automation mode
is a user/workspace preference, not committed project state. The setup flow
should create or repair it per workspace and ensure it is ignored using the
repo's existing ignore style. If setup must edit `.gitignore`, that ignore-rule
change is committed as normal project policy; `.codex/ticket.local.md` remains
unstaged and local-only. Shared defaults can live in docs or a template later
if needed.

Do not introduce a second Ticket automation config file for the new mode model.
The new config accepts `discussion_only`, `preview`, and `agent_primary`. There
is no required compatibility migration for older `suggest`, `auto_audit`, and
`auto_silent` values because no existing repo uses those values in
`.codex/ticket.local.md`; if they appear, treat the config as invalid and use
the guided setup path.

Codex reads `.codex/ticket.local.md` before the first automatic Ticket change
for a `(project_root, thread_id)` pair and stores that value as a local
thread-scoped mode snapshot under `.codex/ticket-workspace/`. Later turns for
the same thread/project use that snapshot instead of rereading config.
Direct config file edits after snapshot creation take effect only for a new
mode snapshot, such as a different `thread_id` in the same project or a
deliberately reset snapshot, not for the current thread/project. If the config
file is missing, unreadable, or invalid before a snapshot exists, Codex pauses
automatic Ticket updates, asks the user what mode they want, and repairs the
config from the user's answer. An explicit chat request such as "pause Ticket
automation" takes effect immediately for the current checkout before the next
autonomous write, writes a workspace-local pause marker, and writes the
repo-local config for future sessions. Other live threads in the same checkout
must observe that pause at the engine-owned write gateway even if they cached
`agent_primary` earlier in their thread-scoped snapshot.

Resuming after a workspace pause is not raw marker deletion. A production resume
flow must ask for an explicit `Automatic` or `Ask first` choice, remove the pause
marker, invalidate project-local mode snapshots, and rewrite strict JSON config
from that choice before a later turn can create a fresh snapshot. A private
test-only helper may clear the marker for isolated tests, but host-facing runtime
surfaces must not expose an unqualified `clear pause` action that would revive a
stale cached `agent_primary` snapshot.

The guided setup prompt should use user-facing choices before internal mode
names:

- `Automatic` -> write `agent_primary`
- `Ask first` -> write `discussion_only`

`preview` remains an advanced/manual config value, not a default first-run
choice. After the user chooses `Automatic` or `Ask first`, Codex should write or
repair `.codex/ticket.local.md` immediately and continue without a second
confirmation. It should mention the file it created or repaired.

The file contents must be one strict JSON object. The canonical automatic-mode
file is:

```json
{"schema":"codex.ticket.local.v1","mode":"agent_primary"}
```

The exact validation schema is:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["schema", "mode"],
  "properties": {
    "schema": {"const": "codex.ticket.local.v1"},
    "mode": {"enum": ["discussion_only", "preview", "agent_primary"]}
  }
}
```

Validation rules:

- parse the entire file as one JSON object
- require exactly `schema` and `mode`; reject unknown keys
- require `schema` to equal `codex.ticket.local.v1`
- require `mode` to be one of `discussion_only`, `preview`, or `agent_primary`
- reject empty files, Markdown, fenced JSON, YAML frontmatter, comments,
  trailing prose, timestamps, audit history, and old mode names
- treat any invalid file as a setup condition: pause automatic Ticket updates,
  ask the user for `Automatic` or `Ask first`, rewrite the whole file, and
  continue

Setup writes `{"schema":"codex.ticket.local.v1","mode":"agent_primary"}` for
`Automatic` and `{"schema":"codex.ticket.local.v1","mode":"discussion_only"}`
for `Ask first`. Manual advanced `preview` uses the same strict JSON object
with `"mode":"preview"`.

## Runtime Boundary

Autonomy must be enforced at the real Ticket mutation choke points:

- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_review.py` for backlog and hygiene
  mutations
- `plugins/turbo-mode/ticket/scripts/ticket_engine_agent.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` when reached by
  `ticket_engine_agent.py`
- other low-level mutating engine entrypoints that can write Ticket state

`ticket_doctor.py` is explicitly outside normal autonomous mutation. Any
history-repair style action discovered there must route to the discussion
required lane.

Every mutating entrypoint must build a shared runtime decision input before any
write occurs. The runtime decision layer answers four operational questions:

1. Is this mutation autonomous, discussion-required, or skipped?
2. Which ticket or tickets may be touched?
3. Is thread evidence sufficient to justify open-set fanout?
4. What must be recorded for the pending-summary log, end-of-turn summary, and
   audit trail?

Ordinary-thread autonomy needs a turn-level boundary owner. The Codex
host/thread runtime owns that turn boundary because it knows when the turn is
ending. It must stay thin: allocate or pass `thread_id` and `turn_id`, provide
final turn context and the current pause or mode signal, call Ticket's recovery
projection before new autonomous writes, call Ticket's turn-apply command near
the end of the turn, and render the returned `Ticket updates` summary or one
discussion question. The host/runtime must not own candidate discovery, approval
consumption, raw ledger parsing, idempotency, partial-failure recovery, or
ticket-state mutation. The Ticket plugin owns mutation rules, approval
validation, write safety, idempotency, pending-summary bookkeeping, recovery
detection, summary payload construction, and ticket-state mutation.

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

`ticket_engine_agent.py` and the shared `ticket_engine_runner.py` are not a
second autonomous gateway. A direct agent execute path may remain only as
explicitly non-autonomous compatibility or as a fail-closed legacy path. Any
supported autonomous agent write must enter the engine-owned gateway with
explicit `thread_id`, approval validation, pending-summary bookkeeping, and the
same Change History contract as `apply-turn`.

The write-authority inventory is positive:

- Autonomous writes may apply ticket-state changes only through the engine-owned
  autonomous write gateway.
- User-directed ordinary ticket writes may use the existing engine execution
  path, but they must be explicitly non-autonomous and must not consume or
  satisfy autonomy approvals.
- Maintenance and doctor writes may bypass the autonomous write gateway only
  through named commands such as audit repair or
  `migrate-change-history --apply`, and only when they are dry-run-first or
  explicitly confirmed.
- Direct low-level file writes to active tickets outside those paths are
  invalid.

## Host-Facing CLI Contract

The first host-facing autonomy API should be a small JSON-in/JSON-out CLI. It
exposes Ticket-level operations rather than raw ledger operations:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_autonomy.py recover \
  --project-root <PROJECT_ROOT> \
  --turn-id <TURN_ID>

uv run python -B <PLUGIN_ROOT>/scripts/ticket_autonomy.py apply-turn \
  --project-root <PROJECT_ROOT> \
  --turn-id <TURN_ID> \
  --context-file <PATH_TO_CONTEXT_JSON>
```

`recover` is a projection command. It validates the Ticket-owned operational
ledger, detects unsummarized records from previous turns, returns display-ready
recovery summary data, and returns whether new autonomous writes may proceed.
The Codex host/thread runtime must call it before new autonomous writes in a
Ticket-aware turn.

`apply-turn` is the transactional turn gateway. It verifies live repo context,
reads mode/config, discovers candidate tickets from the supplied context
snapshot, evaluates candidates, appends ledger attempt records, validates
one-use approvals internally, applies approved mutations through the
engine-owned write gateway, appends follow-up status records, and returns
display-ready summary data plus at most one discussion question.

For runtime-first mode, `thread_id` is the session-like key. Ticket resolves
mode from a local snapshot keyed by `(project_root, thread_id)`: if the snapshot
exists, Ticket uses it; if it does not exist, Ticket reads strict local config
and writes the first snapshot for that thread/project. `turn_id` scopes the
current evaluation and approval batch only. `apply-turn` must reject missing
`thread_id`, missing `turn_id`, or a context `turn_id` that disagrees with the
CLI `--turn-id`.

The context file uses strict JSON. It should include:

- `schema: "codex.ticket.turn_context.v1"`
- `thread_id` for the `(project_root, thread_id)` mode snapshot key
- `turn_id` for the current evaluation/write batch
- current user request and assistant work summary
- touched files, verification commands and outcomes, and relevant evidence
- `git.branch`, `git.head`, and `git.worktree_root`
- a stable repo/worktree identity such as `git.repo_root` and
  `git.repo_fingerprint`

The supplied `git` object is input, not proof. Before candidate discovery or
write bookkeeping, Ticket must build live repo context from `project_root` and
compare it with the supplied `git` object. `repo_root`, `worktree_root`,
`repo_fingerprint`, `branch`, and `head` must match whenever git metadata is
available. A mismatch fails closed before autonomous writes. Ticket records the
verified live repo/worktree context in the operational ledger so later recovery
can distinguish branch-specific work, unrelated backlog maintenance, and stale
records from a different worktree or checkout state.

CLI responses use strict JSON. A successful or paused command should still
print a parseable response to stdout. Exit codes are:

- `0`: valid response; host/runtime should parse stdout JSON
- `1`: operational failure with JSON error when possible
- `2`: invalid input or contract violation
- `3`: automation paused or fail-closed condition with JSON pause output

The host-facing CLI must not expose raw ledger mutation commands such as
`append-event`, `consume-approval`, or `mark-summarized`. Ledger repair belongs
to explicit maintenance commands such as:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_autonomy.py doctor-ledger \
  --project-root <PROJECT_ROOT> \
  --dry-run

uv run python -B <PLUGIN_ROOT>/scripts/ticket_autonomy.py doctor-ledger \
  --project-root <PROJECT_ROOT> \
  --confirm-repair
```

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

`apply_autonomously` must produce a fresh `AutonomyDecision` approval envelope
for exactly one proposed ticket change. The decision is short-lived and
single-use. It must be bound to the exact ticket, proposed mutation fingerprint,
current ticket-state fingerprint, current evidence snapshot, thread-scoped mode,
`thread_id`, and `mutation_id`. The envelope's `approval_id` is deterministic,
not random: derive it from a versioned canonical tuple containing `thread_id`,
the ticket ID, `mutation_id`, proposed mutation fingerprint, current
ticket-state fingerprint, evidence fingerprint, thread-scoped mode, and decision
kind. A decision cannot be reused for another ticket, another mutation, another
thread, another thread-scoped mode, or a ticket that changed after the decision
was created.

The approval envelope also has a short validity window. It is valid only until
the first of these events:

- the matching write consumes it
- 10 minutes pass after approval creation
- the current turn ends
- thread-scoped mode is superseded by an explicit chat pause
- the ticket-state fingerprint changes

Expired approvals must not be used. If an approval expires before the write,
Codex must discard it, re-read current ticket state, and re-run evaluation. A
new automatic write needs a new one-use approval bound to the current state.

Decision rules:

- `archive`, `delete`, and history-repair style actions always return
  `require_user_discussion`
- `done` and `wontfix` with `archive`, `archive: true`, or any
  non-allowlisted close field return `require_user_discussion`; automatic close
  dispatch may only carry explicitly allowed close-resolution fields
- ordinary non-destructive create, update, lifecycle, blocker, stale, and
  refinement actions may return `apply_autonomously`
- ambiguity is not a blocker by itself
- contradiction is the blocker; a ticket with conflicting evidence must return
  `skip_due_to_conflict`
- candidates that exceed the action-tier fanout cap must return
  `require_user_discussion`
- user-triggered correction of an earlier automatic ordinary change may return
  `apply_autonomously` when the pending-summary log still has correction detail
  or current evidence makes the correction obvious and low-risk
- automatic correction may reverse or amend current ticket state and add a
  correction note; it must not delete records, rewrite `## Change History`,
  remove prior audit entries, or alter git history
- when correction detail has expired and the correction is not obvious,
  Codex must inspect the current ticket and lightweight audit history, propose
  the likely correction, and ask before applying it

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

These evidence floors are guardrails for Codex judgment, not a replacement for
it. Codex should use judgment to decide which tickets are relevant, what new
tickets to create, how to prioritize competing candidates, and whether a
low-risk correction is obvious enough to apply. The runtime should enforce the
hard safety boundaries while preserving that semantic judgment.

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
exception. Above-cap candidates must still be recorded in the pending-summary
log with the evidence that would have made them plausible and the cap that
prevented autonomous application.

`require_user_discussion` items appear in the concise end-of-turn Ticket
summary. Codex should ask direct questions about them one at a time, starting
with the highest-priority question. Unanswered discussion items remain pending,
do not apply their proposed change, do not block unrelated automatic updates,
and resurface only when the same ticket becomes relevant again or when the user
asks for pending Ticket decisions.

Every autonomous mutation must have a deterministic `mutation_id` derived from
a versioned canonical tuple containing the thread ID, turn ID, action kind,
ticket ID, proposed mutation fingerprint, and evidence fingerprint. Retrying the
same turn-level fanout must be idempotent: it may resume or complete an existing
mutation record, but it must not duplicate blocker edits, lifecycle transitions,
reopen history entries, or audit rows. Identical ticket/action/fingerprint
inputs in two different `thread_id` values must produce different mutation
identities and separate recovery state.

`turn_id` itself is runtime-assigned by the Codex host/thread runtime, not
derived from the Ticket mutation content. It names the actual host/thread turn
boundary. Ticket must not rely on `turn_id` being globally unique across the
workspace; deterministic IDs use both `thread_id` and `turn_id` when they need
thread and turn scoping.

## Visibility And Audit

Autonomous mutations must not create noisy inline chatter during ordinary work.
Instead, every autonomous mutation appends a structured record to the local
pending-summary log, and Codex emits one concise end-of-turn summary.

Every pending-summary JSONL entry must use a strict envelope plus typed
`details`. Each JSONL line is exactly one JSON object. Unknown top-level fields
are invalid.

The required envelope fields are:

- `schema`
- `event_id`
- `event_type`
- `timestamp`
- `thread_id`
- `turn_id`
- `mutation_id`
- `ticket_id`
- `action`
- `current_mode`
- `status`
- `reason`
- `ticket_state_fingerprint`
- `mutation_fingerprint`
- `evidence_fingerprint`
- `repo_context`
- `decision`
- `evidence`
- `details`

Use `schema: "codex.ticket.pending_summary.v1"` for every line. Use ISO 8601
UTC timestamps. `thread_id` identifies the mode snapshot's Codex conversation,
while `turn_id` identifies one end-of-turn batch. `current_mode` uses the same
`discussion_only`, `preview`, and `agent_primary` enum as `.codex/ticket.local.md`.
`repo_context` is a strict object built from live repo/worktree state after
validating the supplied turn-context `git` object. The runtime carries that
verified state as a `VerifiedRepoContext` value and gateway-owned events must use
that verified value, not raw caller-supplied `git` dictionaries or placeholder
context. When git metadata is available, it must include `repo_root`,
`worktree_root`, `repo_fingerprint`, `branch`, and `head`. Use `null` for `ticket_id`,
`mutation_id`, `ticket_state_fingerprint`, `mutation_fingerprint`, or
`decision` only on workspace-level operational events that do not belong to a
specific ticket mutation. Require `reason` to be one short sentence with no
newline.

`event_id` is the deterministic receipt for one logical JSONL event.
`mutation_id` is the deterministic ID for the original ticket change or pending
action. Follow-up
entries include both their own `event_id` and the original `mutation_id` so
duplicate detection, summary rendering, correction, and compaction can reason
about event chains without reusing `mutation_id` as a per-event identifier.
Retries of the same event reuse the same `event_id`; genuinely new follow-up
events get new `event_id` values.

`event_id`, `mutation_id`, and `approval_id` must be content-derived, not
random. Derive each ID from a versioned canonical tuple and encode it with a
fixed type prefix plus a SHA-256 hash prefix. Use a canonical JSON
serialization for object-like inputs: sorted keys, no insignificant whitespace,
and normalized path strings. Timestamps are validated as ISO 8601 UTC but are
not ID inputs, because retrying the same logical event must not produce a new
receipt solely because wall-clock time advanced.

ID format is exact:

- hash algorithm: SHA-256 over the UTF-8 bytes of the canonical JSON tuple
- hash encoding: lowercase hexadecimal
- hash length in IDs: first 32 hexadecimal characters of the SHA-256 digest
  (128 bits)
- `event_id`: `evt_<32 lowercase hex chars>`
- `mutation_id`: `mut_<32 lowercase hex chars>`
- `approval_id`: `appr_<32 lowercase hex chars>`

If canonicalization or ID inputs need to change later, bump the pending-summary
schema version rather than silently changing the meaning of existing IDs.

`turn_id` is intentionally not content-derived. The Codex host/thread runtime
assigns it at the turn boundary; Ticket automation records it and uses it with
`thread_id` as scoping input for deterministic IDs inside that thread turn.

Canonical ID inputs:

- `mutation_id`: schema version, thread ID, turn ID, action, ticket ID, proposed
  mutation fingerprint, and evidence fingerprint.
- `event_id`: schema version, event type, thread ID, turn ID, mutation ID,
  status, action, ticket ID when present, and a fingerprint of the event payload
  excluding `event_id` and `timestamp`.
- `approval_id`: schema version, thread ID, ticket ID, mutation ID, proposed
  mutation fingerprint, ticket-state fingerprint, evidence fingerprint, current
  mode, and decision kind.

The finite `event_type` values are:

- `mutation_attempt`: original event before an automatic ticket write, preview
  result, pending decision, or deferred action.
- `mutation_status`: follow-up event recording the result or later status of a
  mutation.
- `summary_receipt`: follow-up event proving the mutation was included in a
  normal or recovery summary.
- `compaction_receipt`: event recording that correction-ready detail was
  compacted.
- `automation_pause`: workspace-level event recording why automatic Ticket
  updates paused.

The finite `status` values are:

- `pending`
- `approval_consumed`
- `ticket_written`
- `applied`
- `skipped`
- `discussion_required`
- `deferred`
- `summarized`
- `corrected`
- `inactive`
- `compacted`
- `paused`
- `failed`

Valid `event_type` and `status` combinations are:

| `event_type` | Valid `status` values |
| --- | --- |
| `mutation_attempt` | `pending` |
| `mutation_status` | `approval_consumed`, `ticket_written`, `applied`, `skipped`, `discussion_required`, `deferred`, `corrected`, `inactive`, `failed` |
| `summary_receipt` | `summarized` |
| `compaction_receipt` | `compacted` |
| `automation_pause` | `paused` |

The finite `action` values are:

- ticket actions: `create`, `update`, `reprioritize`, `blocker_edit`,
  `stale_cleanup`, `refine`, `done`, `wontfix`, `reopen`, `archive`, `delete`,
  `history_repair`, `correction`
- operational actions: `summarize`, `compact`, `pause_automation`

`archive`, `delete`, and `history_repair` may appear in pending-summary records
only with non-applied outcomes such as `discussion_required`, `skipped`, or
`failed`.

The finite `decision` values are:

- `apply_autonomously`
- `require_user_discussion`
- `skip_due_to_conflict`
- `defer_until_retry_condition`
- `preview_only`

Use `decision: null` for pure operational events such as `summary_receipt`,
`compaction_receipt`, and `automation_pause`.

The finite `commit_disposition` values are:

- `commit_recorded`: Ticket created a ticket-only local commit for the automatic
  ticket write.
- `commit_bundled_with_work`: Ticket included the ticket write in the same
  created local commit as related completed and verified code or doc work.
- `commit_deferred`: Ticket intentionally left the ticket write uncommitted for
  now and recorded the defer reason.

The `evidence` field is a strict array of objects with `kind` and `ref`. The
finite `evidence.kind` values are:

- `thread`
- `user`
- `ticket_state`
- `diff`
- `file`
- `component`
- `test`
- `commit`
- `history`
- `validation`
- `bookkeeping`

The `details` object is strict and typed by `event_type`:

- `mutation_attempt`: include `proposed_change`. Include `approval` only when
  `decision` is `apply_autonomously`. The `approval` object must include
  `approval_id`, `one_use: true`, `created_at`, `expires_at`,
  `bound_thread_id`, `bound_ticket_id`, `bound_mutation_id`,
  `bound_current_mode`, `bound_decision`,
  `bound_mutation_fingerprint`, `bound_ticket_state_fingerprint`, and
  `bound_evidence_fingerprint`. `expires_at` must be no more than 10 minutes
  after `created_at`. Include `correction_ready: true` plus `before` and
  `after` when the entry needs correction support.
- `mutation_status`: include `previous_event_id`. Require `approval_id` when
  `status` is `approval_consumed`; require `post_write_fingerprint` when
  `status` is `ticket_written`; require `question` when `status` is
  `discussion_required`; require `retry_condition` when `status` is `deferred`;
  require `error_code` when `status` is `failed`; require
  `commit_disposition` when `status` is `applied` for a ticket-file write. A
  `commit_recorded` disposition must include `commit_hash`; a
  `commit_bundled_with_work` disposition must include the related commit hash
  or commit identifier once the containing commit exists; and a
  `commit_deferred` disposition must include a one-sentence defer reason. If the
  containing commit is not yet created, use `commit_deferred` rather than
  claiming `commit_bundled_with_work`.
- `summary_receipt`: include `summary_kind` as `normal` or `recovery`, and
  `bucket` as `applied`, `skipped`, `discussion_required`, or `deferred`.
- `compaction_receipt`: include `retention_days`, `retention_count`,
  `compacted_before`, and `compacted_detail_count`.
- `automation_pause`: include `pause_reason`.

The finite `pause_reason` values are:

- `invalid_config`
- `pending_summary_unhealthy`
- `lock_timeout`
- `duplicate_event_conflict`
- `validation_failed`
- `history_incomplete`
- `unknown_label`
- `unsafe_staging`

A representative mutation-attempt envelope is:

```json
{
  "schema": "codex.ticket.pending_summary.v1",
  "event_id": "evt_0123456789abcdef0123456789abcdef",
  "event_type": "mutation_attempt",
  "timestamp": "2026-05-27T14:03:22Z",
  "thread_id": "thread_...",
  "turn_id": "turn_...",
  "mutation_id": "mut_0123456789abcdef0123456789abcdef",
  "ticket_id": "T-20260527-001",
  "action": "done",
  "current_mode": "agent_primary",
  "status": "pending",
  "reason": "Marked done after verification passed.",
  "ticket_state_fingerprint": "sha256:...",
  "mutation_fingerprint": "sha256:...",
  "evidence_fingerprint": "sha256:...",
  "repo_context": {
    "repo_root": "/workspace/project",
    "worktree_root": "/workspace/project",
    "repo_fingerprint": "sha256:...",
    "branch": "feature/example",
    "head": "abc123"
  },
  "decision": "apply_autonomously",
  "evidence": [
    {"kind": "test", "ref": "uv run pytest plugins/turbo-mode/ticket -q"}
  ],
  "details": {
    "proposed_change": {
      "summary": "Set status to done and add Change History entry.",
      "fields": ["status", "change_history"]
    },
    "approval": {
      "approval_id": "appr_0123456789abcdef0123456789abcdef",
      "one_use": true,
      "created_at": "2026-05-27T14:03:22Z",
      "expires_at": "2026-05-27T14:13:22Z",
      "bound_thread_id": "thread_...",
      "bound_ticket_id": "T-20260527-001",
      "bound_mutation_id": "mut_0123456789abcdef0123456789abcdef",
      "bound_current_mode": "agent_primary",
      "bound_decision": "apply_autonomously",
      "bound_mutation_fingerprint": "sha256:...",
      "bound_ticket_state_fingerprint": "sha256:...",
      "bound_evidence_fingerprint": "sha256:..."
    },
    "correction_ready": true,
    "before": {},
    "after": {}
  }
}
```

Before appending an entry, validate the full envelope, finite enum values,
event/status/action/decision compatibility, evidence shape, typed `details`,
ticket-state fingerprint, and reason format. Reject any line that cannot be
validated. If the active log cannot be validated cleanly, pause automatic
Ticket updates.

The end-of-turn summary appears as a small `Ticket updates` mini-section only
when something changed or needs discussion. It groups records into three
buckets when those buckets are non-empty:

- `Applied`
- `Skipped`
- `Discussion required`

The chat summary is human-facing and terse: counts, ticket IDs, and one short
reason per changed or pending ticket. Detailed before/after information stays
out of chat unless the user explicitly asks for it.

The pending-summary log is the Ticket-owned operational ledger, not project
history. It is the single local machine-readable file
`.codex/ticket-workspace/ticket.pending-summary.jsonl`, must be added to
`.gitignore` when its path is introduced, and must not be staged or committed.
Any temporary or lock files used beside it are also local-only and ignored. It
stores unsummarized records, pending discussion items, deferred actions, and
recent compact before/after data for correction support.

The raw ledger schema is private to Ticket. Codex host/thread runtime may
reference Ticket automation state only through Ticket-owned CLI projections such
as `recover`, `apply-turn`, `pending-decisions`, and
`recent-correction-context`. The ledger must not become a second ticket database;
project truth remains the ticket files plus committed `## Change History`
entries.

The log format is append-first JSONL. Normal operation appends one JSON object
per event instead of rewriting the file. Cleanup and compaction may reduce
older detail later, but must run under the same sibling lock and use a
temporary file plus atomic replace so the active log is never partially
rewritten.

Status changes are also append-only during normal operation. Codex must not edit
an existing event line to mark it summarized, corrected, or inactive. Instead,
it appends a follow-up event line with a new logical `event_id` that references
the original `mutation_id`. Retries of that same follow-up event reuse that
same `event_id`. Compaction may later collapse old chains of original and
follow-up events into a smaller summary record.

Setup should also create or repair a small `.codex/ticket-workspace/AGENTS.md`
beside the pending-summary log. That local instruction file should identify the
Ticket automation state in `.codex/ticket-workspace/` as operational,
local-only bookkeeping that must not be staged, committed, pushed, or treated
as project history. The file is part of the local setup surface, not shared repo
policy, so it is ignored along with the pending-summary log.

The durable Ticket audit trail stores lightweight project-history facts only:
ticket ID, action, timestamp, reason, and a prior commit hash only when
referencing an already-created commit is useful. Those long-term facts must
live in the affected ticket's `## Change History` section for v1. The Ticket
contract should define `## Change History` as a required section with compact
entries containing timestamp, controlled label, one-sentence reason, and prior
commit hash only when referencing an already-created commit is genuinely useful.
Use compact
pipe-separated bullets:

```markdown
- 2026-05-27T14:03:22Z | auto-update | Marked done after verification passed.
- 2026-05-27T14:10:04Z | correction | Reopened after user said the automatic close was wrong. Prior commit: abc123.
```

Do not try to write the containing commit's own hash into the same committed
ticket change. The ticket file is written before that hash exists. The
end-of-turn summary may report the created commit hash, and a later
`## Change History` entry may reference an earlier commit hash when that is
genuinely useful. Keep YAML frontmatter for current ticket metadata, not a
growing history log. Do not introduce a new global committed audit log in v1. If
the affected ticket's `## Change History` section cannot hold the durable facts
cleanly, pause or defer the automatic Ticket update. The local pending-summary
log is operational bookkeeping, not durable project history. Existing
`docs/tickets/.audit/` files are historical artifacts for future autonomous
work unless a later migration explicitly chooses otherwise.

`## Change History` labels are finite and contract-defined:

- `auto-create`: Codex automatically created this ticket for clear follow-up
  work.
- `auto-update`: Codex automatically updated non-lifecycle ticket metadata,
  refinement text, priority, tags, component, or other ordinary fields.
- `auto-blocker`: Codex automatically changed blocker or dependency state.
- `auto-close`: Codex automatically closed the ticket as `done` or `wontfix`.
- `auto-reopen`: Codex automatically reopened the ticket.
- `correction`: Codex corrected or reversed a prior automatic Ticket change.
- `discussion-approved`: Codex applied a change after policy required user
  discussion, such as delete, archive, or history repair. Do not use this label
  for ordinary user-requested Ticket changes that fit an action-specific label.

There are no compatibility aliases for superseded or ad hoc labels. Any
automatic write that would create a `## Change History` entry with an unknown
label must fail validation and pause or defer that automatic ticket change.

For automatic Ticket changes, the `## Change History` entry should be written
as part of the same ticket-file mutation whenever possible. If the runtime
cannot append or update the `## Change History` entry cleanly for an automatic
change, it must pause or defer that automatic ticket change instead of leaving
the durable project-history record incomplete.

Do not require a repo-wide backfill before enabling `agent_primary`. Existing
tickets that lack `## Change History` may receive the section during their first
automatic mutation, in the same ticket-file write as the automatic change. That
is allowed only when the ticket is otherwise parseable and the insertion point
is deterministic: after `## Related` when present, otherwise before
`## Reopen History` when present, otherwise at the end of the file. If the
section cannot be inserted cleanly, defer or pause that candidate rather than
writing a ticket mutation without durable history.

Provide an explicit maintenance command for proactive normalization:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_autonomy.py migrate-change-history \
  --project-root <PROJECT_ROOT> \
  --dry-run

uv run python -B <PLUGIN_ROOT>/scripts/ticket_autonomy.py migrate-change-history \
  --project-root <PROJECT_ROOT> \
  --apply
```

Full correction detail remains local-only in the pending-summary log for 14
days, capped at the most recent 500 correction-ready events. Older correction
detail is compacted away and reduced to lightweight history facts: ticket ID,
action, timestamp, reason, and prior commit hash only when referencing an
already-created commit is useful.

The per-turn pending-summary log must be durable, not only in memory. The
runtime must use a log-backed pending-summary model:

1. Require `thread_id`, allocate a `turn_id`, and derive the deterministic
   `mutation_id` before any autonomous write.
2. Acquire the sibling pending-summary lock, waiting briefly if another writer
   is active.
3. Append each normal pending-summary event as one JSON line with its
   deterministic `event_id`.
4. Write a pending-summary attempt record before or atomically with the ticket
   mutation.
5. Fail closed before ticket mutation if the pending-summary attempt record
   cannot be persisted.
6. Append follow-up status events for `approval_consumed`, `ticket_written`,
   `applied`, `skipped`, or `discussion_required` as each transition occurs. Each
   follow-up event has its own deterministic `event_id` and references the
   original mutation ID instead of editing the original line.
7. Render the end-of-turn summary from durable pending-summary records, then
   append follow-up events that mark the summarized records by referencing their
   original mutation IDs.

Every automatic mutation uses this derived state machine:

```text
attempt_recorded
  -> approval_consumed
  -> ticket_written
  -> status_recorded
  -> summary_recorded
```

The states are derived from append-only ledger events:

- `attempt_recorded`: a `mutation_attempt` line with `status: "pending"` exists.
- `approval_consumed`: a `mutation_status` line with
  `status: "approval_consumed"` exists.
- `ticket_written`: a `mutation_status` line with `status: "ticket_written"`
  and the expected post-write fingerprint exists.
- `status_recorded`: a terminal or pending-disposition `mutation_status` line
  exists, such as `applied`, `skipped`, `discussion_required`, `deferred`,
  `corrected`, `inactive`, or `failed`. For a ticket-file write,
  `status: "applied"` means the ticket file, required `## Change History`
  entry, and pending-summary ledger outcome were written; it does not by itself
  mean the local commit was created.
- `summary_recorded`: a `summary_receipt` line with `status: "summarized"`
  exists. Summaries for ticket-file writes must include the recorded commit
  disposition so dirty or deferred commit state is visible.

Recovery must be explicit for each gap:

- No `attempt_recorded`: no autonomous write is trusted; evaluate normally.
- `attempt_recorded` only: no ticket write is trusted yet. Re-read ticket state,
  revalidate the approval inputs, then retry with the same `mutation_id` or
  append `failed`.
- `approval_consumed` but no `ticket_written`: treat the protected write section
  as interrupted. Compare current ticket state to both the approval's bound
  pre-write fingerprint and the expected post-write fingerprint. If the
  post-write fingerprint matches, append the missing `ticket_written` and
  terminal status events without rewriting the ticket. If the pre-write
  fingerprint still matches, retry with the same `mutation_id`. If neither
  fingerprint matches, pause that candidate for reconciliation instead of
  rewriting or marking the write as cleanly failed.
- `ticket_written` but no `status_recorded`: inspect the ticket file and compare
  it to the expected post-write fingerprint. If it matches, append the outcome
  status without rewriting the ticket. If it does not match, append `failed` with
  a reconcile-required reason and pause that candidate.
- `status_recorded` but no `summary_recorded`: do not retry the mutation. Emit a
  recovery summary on the next Ticket-aware turn and append `summary_receipt`.
- `summary_recorded`: the mutation is complete. Retries must report the existing
  completion instead of reapplying the mutation.

`approval_consumed` means Ticket entered the protected write section; it is not
a permanent rejection of all later retries. A retry may continue only when the
exact bound ticket state still holds.

Compaction is not part of the ordinary event-write path. It may run later under
the same lock, write the compacted content to a sibling temporary file, validate
that file, and atomically replace the active JSONL file only after validation
succeeds.

Compaction must enforce both retention limits for correction-ready detail:
keep detailed correction-ready records for no more than 14 days and no more
than the most recent 500 correction-ready events. Entries beyond either limit
must be reduced to lightweight facts rather than retained with full
before/after correction detail.

Before appending under the lock, the writer should check whether the same
`event_id` already exists. If an event with the same deterministic ID and same
canonical ID inputs already exists, the retry treats the event as already
recorded and does not append a duplicate line, even if the retry reconstructed
a different append timestamp. If the same `event_id` exists with conflicting
non-timestamp content, Codex must pause automatic Ticket updates with the
pending-summary bookkeeping cleanup message.

If the lock cannot be acquired within the brief wait window, the log changes
under Codex before the write can be safely completed, the temporary file cannot
be atomically promoted, or validation after write fails, Codex must pause
automatic Ticket updates with the pending-summary bookkeeping cleanup message
instead of risking lost summaries or invalid correction records.

If summary emission fails after mutations succeeded, the next Ticket-aware turn
must detect unsummarized pending-summary records and emit a recovery summary
before new autonomous mutations. The recovery summary must use the same
`Applied`, `Skipped`, and `Discussion required` buckets as the normal
end-of-turn summary.

Discussion-required records are pending-decision records. Each must include the
candidate ticket, proposed mutation, evidence, reason for discussion, expiry or
revalidation rule, and the user action that would authorize the write. A
discussion-required mutation may not execute until the pending record is
revalidated against current ticket state and resolved by the user.

Deferred unrelated backlog-maintenance records are pending-action records. Each
must include the proposed Ticket action, reason, and retry condition. They stay
separate from applied updates and resurface only when `main` is available for a
safe ticket-only commit or when the user asks for pending Ticket decisions.

## Components

The implementation should stay small and runtime-owned.

### Host/thread runtime coordinator

Thin Codex host/thread-runtime coordinator that assigns or passes `thread_id`
and `turn_id`, captures final turn context, calls `ticket_autonomy.py recover`
before new autonomous writes, calls `ticket_autonomy.py apply-turn` near the end
of the turn, and renders the concise `Ticket updates` mini-section or one
returned discussion question. It must not parse raw ledger records, own Ticket
transaction state, or grant write authority.

### `ticket_autonomy.py`

Host-facing JSON-in/JSON-out CLI for Ticket-level autonomy operations. It owns
the public CLI commands `recover`, `apply-turn`, `doctor-ledger`, and
`migrate-change-history`. It is the only host-facing surface for autonomous
turn application and recovery projections.

### `ticket_autonomy_runtime.py`

Shared runtime module that:

- builds `AutonomyIntent`
- evaluates `apply_autonomously`, `require_user_discussion`, and
  `skip_due_to_conflict`
- emits structured mutation records for the pending-summary log

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
decision, receives the already verified live repo context, rechecks the
workspace pause marker, enforces idempotency, appends durable pending-summary
events, updates or creates `## Change History` when required, and then delegates
to the existing ticket mutation mechanics. Existing wrappers may prepare context
or payloads, but autonomous writes that bypass this gateway are invalid.

The gateway must also enforce closed field allowlists per automatic action
before calling the live engine. For lifecycle close actions, `done` and
`wontfix` map to engine `close` with their explicit `resolution` and no
`archive` field. Passing `archive` through the automatic gateway would widen the
autonomous product boundary and is invalid even though the lower-level engine
supports archived close for discussion-approved flows.

The gateway is not a general file-writing helper. User-directed ordinary ticket
writes may continue through the existing engine execution path only when they
are explicitly non-autonomous and do not consume autonomy approvals. Named
maintenance or doctor commands may bypass the autonomous gateway only for
dry-run-first or explicitly confirmed repair operations. All other direct
low-level writes to active tickets are invalid.

Static bypass checks must prove named authorized functions or call paths, not
whole-file allowlists. Write-heavy modules such as `ticket_engine_core.py` and
`ticket_engine_gateway.py` are not acceptable as blanket exceptions. The
autonomous path is the named gateway path; user-directed engine mutations and
maintenance repairs are exceptions only through explicitly named non-autonomous,
dry-run-first, or confirm-gated entrypoints.

### `ticket_turn_batch.py`

Durable pending-summary-log-backed collector that accumulates per-turn applied,
skipped, discussion-required, and deferred records; validates and compacts the
local `.codex/ticket-workspace/ticket.pending-summary.jsonl` log; renders the
end-of-turn summary and lightweight audit payload; appends follow-up status
events for summarized, corrected, inactive, and commit-disposition records;
uses sibling lock/temp-file writes; and emits recovery summaries for
unsummarized records from earlier turns.

### Ticket commit coordinator

Focused helper that stages only Ticket-owned files and automation-created audit
records for automatic ticket-only commits, runs lightweight structural checks,
creates local commits with standard messages, and avoids staging unrelated user
work. It must not push commits.

## Git And Commit Behavior

Automatic Ticket updates should not leave the worktree dirty by default.

This design assumes the repo-wide default that completed Codex file changes are
locally committed after focused verification when a coherent commit can be made.
Ticket automation follows that default instead of creating a separate commit
path for ordinary work.

Commit behavior:

- when related code/doc work is complete and verified, include directly related
  automatic Ticket updates in the same local commit
- when automatic Ticket updates happen without related code/doc changes, create
  a small ticket-only local commit
- Ticket changes are allowed directly on `main`; do not force branch creation
  merely because the automatic update touches Ticket state
- never push automatic Ticket commits unless the user explicitly asks Codex to
  publish

Commit disposition is recorded separately from the ticket-state mutation:

- `commit_recorded`: a ticket-only local commit was created for the automatic
  ticket write
- `commit_bundled_with_work`: the automatic ticket write was staged and
  committed with related completed and verified code or doc work
- `commit_deferred`: Ticket intentionally left the ticket write uncommitted and
  recorded a one-sentence reason, such as overlapping user changes, unsafe
  staging, or an unrelated backlog action waiting for `main`

`Applied` in the Ticket summary means the ticket file and required
`## Change History` entry were written and the pending-summary ledger recorded
the outcome. It does not imply the repository is clean. Whenever a ticket write
happened, the end-of-turn summary must include the commit disposition so a
dirty, bundled, or deferred commit state is visible.

Ticket-only commit messages are standardized:

- `tickets: update project state` for mixed Ticket updates
- `tickets: capture follow-up work` when the commit only creates new tickets
- include a commit body only when multiple notable Ticket actions need context

Ticket-only commits must stage only Ticket-owned files and automation-created
durable audit records. The pending-summary log is local-only and must not be
staged. When unrelated user changes exist, Codex may still create the
ticket-only commit only if it can stage exactly the Ticket-owned files and
automation-created audit records it touched and there is no file overlap or
ambiguity. If there is overlap or ambiguity, defer the automatic commit and
explain the defer reason briefly.

Same-ticket unstaged overlap is always ambiguous and must defer rather than
stage over user work. Detached HEAD must defer because branch ownership is
unknown. Unrelated backlog maintenance may commit only on `main` with a clean
worktree and safe branch state; if reaching `main` would require switching away
from dirty or ambiguous work, defer and record the retry condition.

Automation-created durable audit records are part of ticket-owned project
state. Record them inside the affected ticket file's `## Change History`
section. Do not create or use a separate global committed audit file in v1.
For automatic Ticket mutations, the `## Change History` entry should be staged
with the same ticket-file change; if that entry cannot be written cleanly, defer
the automatic mutation rather than committing an unexplained ticket change.

Automatic Ticket commits belong on the current branch when they directly
describe that branch's work. Unrelated backlog maintenance should be committed
on `main` only when the worktree is clean and switching is safe. If switching
is not safe, defer the unrelated Ticket action instead of contaminating the PR
branch.

When a ticket-only commit is created, the end-of-turn Ticket summary includes a
terse breadcrumb such as `Committed: abc123 tickets: update project state`.
When a ticket write is bundled with related work, the summary names the related
commit when it exists. When a commit is deferred, the summary names the defer
reason.

Ticket-only automatic commits use lightweight verification only:

- changed-ticket schema and parse validation
- pending-summary log validation
- `git diff --check`

Do not run broad tests for ticket-only commits unless code changed. A dedicated
lightweight Ticket verification tool may be added later to make these checks
fast and explicit.

## Failure Handling

Failure handling is intentionally narrow:

- missing, unreadable, or invalid mode config -> pause automatic Ticket updates,
  ask the user what mode they want, and repair the repo-local config from the
  answer
- explicit chat request to pause Ticket automation -> write the workspace-local
  pause marker, pause automatic Ticket updates in the current checkout before
  the next autonomous write, and update repo-local config for future sessions
- explicit chat request to resume Ticket automation -> ask for `Automatic` or
  `Ask first`, clear the pause marker only as part of that setup-choice flow,
  invalidate project-local mode snapshots, and write fresh strict JSON config
- engine-owned write gateway observes the workspace pause marker before
  mutation -> reject the autonomous write with paused output, even if that live
  thread cached `agent_primary` earlier
- supplied turn-context repo/worktree/branch/HEAD does not match live
  `project_root` state -> fail closed before candidate discovery or autonomous
  write bookkeeping
- conflicting evidence for one ticket -> skip that ticket only
- delete, archive, or history-repair action -> route to discussion required and
  do not write
- `done` or `wontfix` candidate includes `archive` or another forbidden close
  field -> route to discussion required or fail closed before engine dispatch
- `discussion_only` mode -> route autonomous candidates to discussion required
  and do not write
- `preview` mode -> record preview dispositions and summaries, but do not write
  ticket state
- candidate discovery failure -> perform no autonomous writes and record the
  failure in the pending-summary log
- missing or stale `.codex/ticket-workspace/AGENTS.md` local guidance -> setup
  should repair it before automatic Ticket writes, but this is an operational
  setup repair, not a project-history change
- automatic Ticket change cannot write its required `## Change History` entry
  cleanly -> pause or defer that automatic change and do not leave the ticket
  mutated without durable project history
- automatic Ticket change would create a `## Change History` entry with an
  unknown label -> fail validation and pause or defer that automatic change
- one fanout target fails local validation or a write precondition -> skip that
  target unless the failure means the shared evidence model is invalid
- pending-summary attempt record cannot be persisted before write -> fail
  closed and perform no ticket mutation for that candidate
- pending-summary log cannot be written, appended with follow-up status events,
  validated, or compacted under its limits -> pause automatic Ticket updates and report
  `Ticket automation paused because pending-summary bookkeeping needs cleanup.`
- retry sees the same `event_id` with the same canonical non-timestamp content
  -> treat the event as already recorded and do not append a duplicate line
- retry sees the same `event_id` with conflicting non-timestamp content ->
  pause automatic Ticket updates with the pending-summary bookkeeping cleanup
  message
- sibling pending-summary lock cannot be acquired after a brief wait, the log
  changes underneath the writer, or temp-file promotion fails -> pause automatic
  Ticket updates with the same bookkeeping cleanup message
- end-of-turn summary emission fails after successful mutations -> leave durable
  unsummarized records for recovery-summary emission on the next Ticket-aware
  turn
- retry observes an existing `mutation_id` -> resume or report the existing
  record instead of applying the mutation a second time
- one-use approval is expired, already consumed, from another turn, or bound to
  stale ticket state -> reject it, do not write, and re-run evaluation against
  current ticket state before any new automatic write
- crash occurs after approval consumption and ticket write but before
  `ticket_written` is recorded -> compare current ticket state with the expected
  post-write fingerprint and, when it matches, append the missing
  `ticket_written` and terminal status events without rewriting
- crash recovery sees neither the bound pre-write fingerprint nor expected
  post-write fingerprint -> pause that candidate for reconciliation
- ticket file and `## Change History` are written but a local commit cannot be
  created safely -> record `commit_deferred` with the reason and include that
  disposition in the end-of-turn summary
- user says an automatic ordinary Ticket update was wrong -> automatically
  correct or reverse the prior change when correction detail still exists or
  the correction is obvious and low-risk
- automatic correction would delete records, rewrite `## Change History`,
  remove prior audit entries, or alter git history -> route to discussion
  required as history repair
- correction detail has expired and the correction is not obvious -> inspect
  current ticket state and lightweight audit history, propose the likely
  correction, and ask before applying it
- unrelated backlog maintenance cannot be safely committed on `main` -> defer
  the Ticket action with a retry condition instead of dirtying the PR branch

The default failure posture for v1 is "do not write this candidate," not
"disable all autonomy for the turn."

Failure scope must be explicit:

| Failure class | Scope | Owner | Recovery trigger | Summary behavior |
| --- | --- | --- | --- | --- |
| Candidate conflict or local validation failure | Candidate | Ticket | New evidence or user request | Include skipped item when relevant |
| Missing `## Change History` insertion point or unknown history label | Candidate | Ticket | Ticket repair or migration command | Defer or pause candidate with reason |
| Pending-summary ledger unhealthy, duplicate-event conflict, or lock failure | Workspace automation | Ticket | `doctor-ledger` repair or manual cleanup | Report one pause reason; no new automatic writes |
| Missing or invalid local mode config | Workspace setup | Ticket plus host prompt | Guided setup answer | Ask setup question before automatic writes |
| Summary emission failure after successful mutation | Turn recovery | Ticket projection rendered by host | Next Ticket-aware `recover` call | Emit recovery summary before new writes |
| Unrelated backlog maintenance cannot safely commit on `main` | Action | Ticket commit coordinator | Clean worktree and safe branch switch | Defer with retry condition |

Unrelated candidates may continue only when the failure is candidate-scoped and
does not invalidate shared evidence, mode, ledger health, or write-gateway
state.

## Rollout Sequence

Rollout should be incremental:

1. Disable future `docs/tickets/.audit/` writes immediately while preserving
   existing `.audit/` files as historical artifacts. This migration should not
   wait for the autonomous runtime replacement because the current `.audit/`
   write path is not in use. The same implementation commit must update
   README/HANDBOOK to describe `.audit/` as historical or legacy only, not
   active behavior. Delete or cleanly bypass the `.audit/` write path where
   practical, but keep read/doctor support for existing historical `.audit/`
   files until a separate migration decides their fate. Add a static guard or
   focused test that fails if future autonomous write code writes to
   `docs/tickets/.audit/`.
2. Ship repo-local mode config, thread-scoped mode snapshots, explicit chat
   pause handling, the shared autonomy runtime, the `ticket_autonomy.py recover`
   and `apply-turn` CLI, and the durable Ticket-owned operational ledger.
3. Implement the mutation state machine and engine-owned autonomous write
   gateway so retries recover from gaps between attempt recording, approval
   consumption, ticket write, status recording, and summary receipt.
4. Wire update and review-style mutations into `agent_primary` behind the
   thread-scoped mode gate. When the user chooses automatic mode, apply real
   automatic changes immediately rather than forcing a preview-only phase.
5. Add concise end-of-turn summaries, pending discussion questions, recovery
   summaries, and pending-summary compaction.
6. Add automatic `## Change History` insertion on first automatic mutation when
   existing tickets lack the section, plus explicit
   `migrate-change-history --dry-run/--apply` maintenance support.
7. Add automatic ticket-only commit support with lightweight verification and
   local-only pending-summary bookkeeping.
8. Add capture and agent entrypoint integration next, including automatic
   creation of clear actionable follow-up tickets.
9. Broaden candidate discovery and hygiene-driven fanout once the runtime layer
   is stable.
10. Keep doctor, delete, archive, and history-repair paths explicitly
   discussion-gated and last.

This rollout order prioritizes the highest-value autonomous mutation paths
first while keeping the narrow human-discussion lane intact.

Rollback during a thread/project mode snapshot means the user explicitly asks
Codex to pause Ticket automation. That pause is workspace-wide for the current
checkout before the next autonomous write: Ticket writes a workspace-local pause
marker, the engine-owned write gateway rechecks it immediately before mutation,
and other live threads in the same checkout must observe it even if they cached
`agent_primary` earlier. The same pause writes the repo-local config for future
sessions and preserves existing pending-summary records for summary,
correction, and recovery. Editing the mode config file directly after a
`(project_root, thread_id)` snapshot exists does not change that thread/project
behavior; Ticket reads config again only when creating a new mode snapshot.

## Verification

The implementation plan derived from this design must include these test bands.

### 1. Policy decision tests

Prove that:

- ordinary non-destructive mutations route to `apply_autonomously`
- delete, archive, and history-repair actions route to
  `require_user_discussion`
- `done` or `wontfix` with `archive`, `archive: true`, or any non-allowlisted
  close field routes to `require_user_discussion`
- conflicting candidates route to `skip_due_to_conflict`
- `discussion_only` mode prevents autonomous writes
- missing, unreadable, or invalid mode config pauses automation and produces a
  guided setup path
- `.codex/ticket.local.md` parses only as a strict JSON object with exactly
  `schema: codex.ticket.local.v1` and mode `discussion_only`, `preview`, or
  `agent_primary`
- Markdown, fenced JSON, YAML frontmatter, comments, trailing prose, unknown
  keys, and old mode names make `.codex/ticket.local.md` invalid
- guided setup creates or repairs `.codex/ticket.local.md` by rewriting the
  whole strict JSON object, ensures the config file is ignored, and leaves the
  config file unstaged
- if setup must add the ignore rule, the `.gitignore` change is handled as
  committable project policy while `.codex/ticket.local.md` remains local-only
- setup ensures `.codex/ticket-workspace/ticket.pending-summary.jsonl`, its
  sibling temporary or lock files, and sibling
  `.codex/ticket-workspace/AGENTS.md` are ignored and local-only
- `thread_id` and `turn_id` are required in strict turn context; `thread_id`
  keys the mode snapshot with `project_root`, while `turn_id` scopes one
  evaluation/write batch
- thread-scoped mode is read from `.codex/ticket.local.md` before the first
  automatic change for `(project_root, thread_id)` and held in a local snapshot
  for later turns in that same thread/project
- direct config edits after snapshot creation do not affect later turns in the
  same `(project_root, thread_id)`; a different `thread_id` in the same project
  reads current strict config and receives its own snapshot
- explicit chat pause takes effect immediately and updates repo-local config
- explicit chat pause writes a workspace-local pause marker and prevents other
  live threads in the same checkout from making autonomous writes before their
  next mutation, even when those threads cached `agent_primary` earlier
- the engine-owned write gateway rechecks the workspace pause marker immediately
  before consuming approval and mutating ticket state
- `preview` mode records decisions without ticket-state mutation
- `agent_primary` mode applies approved non-destructive mutations, including
  lifecycle `done`, `wontfix`, and `reopen`
- action-tier evidence floors are enforced for metadata, blocker/refinement,
  lifecycle, and `wontfix` mutations
- above-cap candidates route to `require_user_discussion`
- every autonomous write requires a fresh, one-use decision bound to the exact
  ticket, mutation, ticket-state fingerprint, evidence snapshot,
  `thread_id`, thread-scoped mode, and `mutation_id`
- one-use approvals are valid only within the current turn and for no more than
  10 minutes after creation
- expired, already-consumed, cross-thread, cross-turn, or stale-ticket-state
  approvals are rejected before write and force re-evaluation against current
  ticket state
- `approval_id` is deterministic from its canonical inputs and changes when the
  bound thread, ticket, mutation, ticket-state fingerprint, evidence
  fingerprint, thread-scoped mode, or decision kind changes
- `turn_id` is runtime-assigned by the Codex host/thread runtime and is not
  content-derived from Ticket mutation inputs
- the Codex host/thread runtime can call `ticket_autonomy.py recover` before new
  autonomous writes and `ticket_autonomy.py apply-turn` near end of turn without
  parsing raw ledger records or understanding Ticket partial-failure states
- `recover` and `apply-turn` return strict JSON projection payloads with
  display-ready summary data, at most one discussion question, and a machine
  pause object when automation is paused
- invalid CLI input exits with a contract error, and paused automation returns a
  parseable JSON response instead of raw stderr-only diagnostics

### 2. Candidate discovery tests

Prove broad inference from:

- explicit thread references
- blocker and duplicate relationships
- file and component ownership
- diff and failing-test signals
- hygiene and stale-state signals
- clear actionable follow-up work that can become an automatic new ticket
- vague ideas, broad cleanup themes, and "maybe later" items routing to
  discussion required

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
- every end-of-turn summary for a ticket write includes commit disposition:
  `commit_recorded`, `commit_bundled_with_work`, or `commit_deferred` with a
  reason
- the summary appears only when Ticket changes happened or discussion is needed
- the summary stays concise: counts, ticket IDs, and one short reason per item
- detailed before/after data stays out of chat unless explicitly requested
- the pending-summary log records unsummarized items, pending decisions,
  deferred actions, and bounded correction detail
- correction-ready detail is retained for no more than 14 days and no more than
  the most recent 500 correction-ready events before compaction reduces it to
  lightweight facts
- every pending-summary JSONL entry validates as the strict
  `codex.ticket.pending_summary.v1` envelope with no unknown top-level fields
- `event_type`, `status`, `action`, `current_mode`, `decision`,
  `evidence.kind`, and `pause_reason` values are finite and reject unknown
  values
- event/status/action/decision combinations outside the compatibility rules
  fail validation and pause automatic Ticket updates
- every pending-summary JSONL entry includes a deterministic `event_id`;
  ticket-specific mutation events include `ticket_id`, ticket-state
  fingerprint, mutation fingerprint, and evidence fingerprint
- `event_id`, `mutation_id`, and `approval_id` are deterministic,
  content-derived IDs using SHA-256, the exact `evt_`, `mut_`, or `appr_`
  prefix, and the first 32 lowercase hexadecimal characters of the digest;
  retries of the same canonical input reproduce the same IDs
- timestamps are validated as ISO 8601 UTC but are not used as ID inputs
- `thread_id` and `turn_id` are recorded in every envelope and used as scoping
  inputs for deterministic IDs; identical mutation content in different threads
  produces different IDs and separate recovery state
- every pending-summary JSONL entry includes strict `repo_context` with
  normalized repo/worktree identity, branch, and HEAD when git metadata is
  available
- `apply-turn` builds live repo context from `project_root`, compares it with
  the supplied turn-context `git` object, fails closed on mismatch before
  candidate discovery or write bookkeeping, and records only the verified live
  context in pending-summary events
- typed `details` validate according to `event_type`, including required
  questions for `discussion_required`, retry conditions for `deferred`, error
  codes for `failed`, and pause reasons for `automation_pause`
- retries of the same logical event reuse the same `event_id`; identical
  already-recorded events do not produce duplicate lines, and conflicting
  duplicate `event_id` content pauses automation
- heavier before/after detail appears only on correction-ready entries or other
  entries that need correction support
- summarized, corrected, inactive, applied, skipped, and discussion-required
  status changes append follow-up events with their own deterministic
  `event_id` that reference the original `mutation_id` instead of editing the
  original line
- the mutation state machine is recoverable from append-only ledger events:
  `attempt_recorded -> approval_consumed -> ticket_written -> status_recorded
  -> summary_recorded`
- retries at each state-machine gap follow the explicit recovery matrix and do
  not duplicate ticket writes, blocker edits, lifecycle transitions,
  `## Change History` entries, or summary receipts
- recovery in the `approval_consumed` but no `ticket_written` gap compares
  current ticket state to both the bound pre-write fingerprint and expected
  post-write fingerprint
- matching expected post-write state in that gap appends missing
  `ticket_written` and terminal status events without rewriting the ticket
- matching neither pre-write nor post-write state in that gap pauses the
  candidate for reconciliation
- `.codex/ticket-workspace/ticket.pending-summary.jsonl`, its sibling temporary
  or lock files, and sibling `.codex/ticket-workspace/AGENTS.md` are
  local-only, gitignored, and not staged
- pending-summary writes use the sibling lock/temp-file flow, wait briefly for
  active writers, and fail closed when clean update cannot be proven
- normal pending-summary writes append one JSON object per line, while
  compaction uses the same lock plus temporary-file atomic replacement
- the durable audit trail records lightweight facts only, in the affected
  ticket's committed `## Change History` section
- `## Change History` is the v1 ticket-owned location for durable
  lightweight history facts, with compact pipe-separated timestamp, label,
  reason, and optional prior-commit references
- `## Change History` labels are limited to the contract-defined finite set and
  Codex does not create ad hoc labels
- unknown `## Change History` labels fail validation for automatic writes; there
  are no compatibility aliases for superseded labels
- `## Change History` entries do not try to include the hash of the commit that
  contains that same entry; the end-of-turn summary may report that commit hash
- automatic Ticket changes write their `## Change History` entry in the same
  ticket-file mutation when possible
- automatic Ticket changes pause or defer when `## Change History` cannot be
  updated cleanly
- first automatic mutation may create missing `## Change History` in the same
  ticket-file write when the ticket is parseable and the insertion point is
  deterministic
- `migrate-change-history --dry-run/--apply` can normalize existing tickets
  without being required before `agent_primary`
- YAML frontmatter remains current metadata and is not used as a growing
  history log
- no global committed audit log is created or used in v1; automatic Ticket
  updates pause or defer when `## Change History` cannot hold the durable facts
  cleanly
- future autonomous durable history does not write to `docs/tickets/.audit/`;
  existing `.audit/` files are treated as historical artifacts unless a later
  migration explicitly changes the contract
- the immediate migration disables future `.audit/` writes without deleting or
  rewriting existing historical `.audit/` files
- the same implementation commit that disables future `.audit/` writes updates
  README/HANDBOOK so they no longer present `.audit/` as active behavior
- the immediate migration deletes or cleanly bypasses `.audit/` write behavior
  while preserving read/doctor support for existing historical `.audit/` files
- a static guard or focused test fails if future autonomous write code writes
  to `docs/tickets/.audit/`
- autonomous mutation fails closed when the pending-summary attempt record
  cannot be persisted
- pending-summary bookkeeping failure pauses automatic Ticket updates
- unsummarized durable pending-summary records produce a recovery summary before
  the next autonomous mutation

### 5. Bypass prevention tests

Prove that:

- supported mutating entrypoints cannot write ticket state without an approved
  autonomy decision when running in autonomous mode
- `ticket_autonomy.py apply-turn` reaches ticket-state mutation only through the
  engine-owned write gateway
- autonomous writes are the only writes that may consume autonomy approvals, and
  they can apply ticket-state changes only through the engine-owned autonomous
  write gateway
- the gateway enforces per-action field allowlists before live engine dispatch,
  including rejection of `archive` on automatic `done`/`wontfix`
- gateway-owned pending-summary events carry the explicit `thread_id`, and
  approval validation rejects missing or mismatched thread binding
- user-directed ordinary ticket writes are explicitly non-autonomous and may use
  the existing engine execution path without satisfying autonomy approvals
- maintenance and doctor bypasses are limited to named dry-run-first or
  explicitly confirmed repair commands
- direct low-level file writes to active tickets outside the gateway or named
  exceptions are rejected or flagged by static/text guards
- static/text guards do not accept whole write-heavy files as proof; they must
  name the authorized function or call path
- wrappers cannot forge or reuse stale autonomy decisions
- static or text guards flag new ticket-state write paths outside the
  engine-owned gateway, except explicit maintenance or doctor paths
- static or text guards flag any future autonomous `.audit/` write path while
  allowing explicit read/doctor support for existing historical `.audit/` files

### 6. Correction tests

Prove that:

- user-triggered correction of an ordinary automatic Ticket update applies
  without another approval round when correction detail still exists
- a wrongly created ticket is corrected by marking it `wontfix` with a short
  correction note rather than deleting it
- delete, archive, and history repair remain discussion-required even when the
  user asks to correct a mistaken automatic update
- automatic correction may reverse or amend current ticket state and append a
  correction note, but may not delete records, rewrite `## Change History`,
  remove prior audit entries, or alter git history
- expired correction detail causes Codex to inspect current ticket state and
  lightweight audit history, then ask unless the correction is obvious and
  low-risk

### 7. Git integration tests

Prove that:

- automatic Ticket updates are committed with related completed and verified
  code/doc work in the same local commit
- ticket-only automatic commits stage only Ticket-owned files and
  automation-created durable audit records
- ticket-only automatic commits never stage the pending-summary log
- ticket-only automatic commits use the standard commit messages
- ticket-only automatic commits run changed-ticket schema/parse validation,
  pending-summary log validation, and `git diff --check`
- ticket writes that are committed immediately record `commit_recorded` with the
  created commit hash
- ticket writes bundled with related completed work record
  `commit_bundled_with_work` and name the related commit hash or identifier
- ticket writes that cannot be committed safely record `commit_deferred` with a
  one-sentence reason and surface that reason in the end-of-turn summary
- unrelated user changes in other files are not staged
- overlap or ambiguity defers the automatic commit with a brief reason
- automatic Ticket commits are allowed on `main` without branch creation
- automatic Ticket commits are local only and never pushed without explicit user
  request

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
