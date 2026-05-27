# System Design Review: Ticket Runtime-First Autonomy Design

Reviewed artifact:
`docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md`

## Review Snapshot

- Scope: subsystem, specifically the Ticket autonomy runtime and write-path
  control design.
- Archetypes: internal control plane plus audit-sensitive local mutation
  system.
- Stakes: high for local project-state integrity because the design authorizes
  autonomous writes across repo-local tickets and relies on a wrapper/engine
  trust boundary.
- Overall read: the runtime-first replacement is a conscious and coherent
  direction. The largest remaining architecture gaps are not product intent;
  they are the concrete trigger, authority, durability, and rollback mechanisms
  that would make aggressive autonomy non-bypassable and recoverable.

## Focus And Coverage

- Structural: screened, deep. Sentinel: components and boundaries. Anchor:
  `Runtime Boundary` and `Components`, lines 113-149 and 346-390. Disposition:
  runtime-owned partition is explicit, but the write gateway authority contract
  is not yet concrete.
- Behavioral: screened, deep. Sentinel: runtime under failure, retry, and
  overload. Anchor: `Fanout Semantics` and `Failure Handling`, lines 253-293
  and 397-420. Disposition: per-ticket fail-soft behavior is explicit;
  concurrency and turn lifecycle remain underspecified.
- Data: screened, deep. Sentinel: critical datum and source of truth. Anchor:
  `Evidence Model` and `Visibility And Audit`, lines 200-250 and 295-344.
  Disposition: evidence and mutation records are named; durable storage,
  schema, and source-of-truth ownership are open.
- Reliability: screened, deep. Sentinel: guarantees, recovery, and
  degradation. Anchor: outbox and recovery rules, lines 323-338, plus rollback
  lines 441-444. Disposition: recovery intent is explicit; atomicity and
  recovery mechanics need a consistency model.
- Change: screened. Sentinel: migration, rollback, and test isolation. Anchor:
  `Rollout Sequence` and `Verification`, lines 423-518. Disposition:
  incremental rollout is clear; mode migration and config propagation are not.
- Cognitive: screened. Sentinel: responsibility and rationale discoverability.
  Anchor: `Status`, `Non-Goals`, and replacement rationale, lines 3-16, 49-59,
  and 521-536. Disposition: rationale is unusually clear and product posture is
  discoverable.
- Trust/Safety: screened, deep. Sentinel: trust, privilege, and sensitive
  mutation boundary. Anchor: product boundary and engine enforcement, lines
  61-67 and 145-149. Disposition: destructive actions are gated, but
  non-forgeable authorization mechanics are not specified.
- Operational: screened, deep. Sentinel: deploy, config, observability, and
  ownership. Anchor: runtime modes and rollback, lines 98-111 and 441-444.
  Disposition: modes exist as controls; their owner, source of truth, and
  immediate enforcement path are open.

Selected deep lenses: Boundary Definition, Trust Boundary Integrity,
Correctness, Consistency Model, Durability, Recoverability, Configuration
Clarity, Auditability, and Reversibility.

## Findings

### 1. Ordinary-thread autonomy has no concrete trigger or flush owner

- Lens: Operational Ownership, Behavioral Correctness.
- Decision state: underspecified.
- Anchor: purpose and product boundary require thread-scoped triggering and an
  end-of-turn summary, lines 29-35 and 69-76; the outbox/recovery model depends
  on end-of-turn and next-turn behavior, lines 295-338.
- Problem: the design wants autonomous ticket mutation during ordinary thread
  work, without explicit Ticket-only invocation and without an ambient
  reconciler. It does not name the component that observes ordinary thread
  activity, starts candidate discovery, allocates the turn batch, flushes the
  end-of-turn summary, or runs recovery before the next Ticket-aware turn.
- Impact: the runtime-first intent can collapse back into wrapper-local behavior
  or hook-specific behavior. Recovery summaries may never run if no explicit
  Ticket command executes after a failed summary.
- Recommendation: pick one trigger boundary. For example, define a
  thread-turn coordinator in the app-server or hook path that owns candidate
  discovery, turn batch allocation, summary flush, and recovery. If the v1
  boundary is explicit wrappers only, state that and narrow the product claim.

### 2. Engine-owned write authority is stated but not made non-forgeable

- Lens: Trust Boundary Integrity, Boundary Definition.
- Decision state: underspecified.
- Anchor: engine-owned enforcement, lines 145-149; adapter limits and gateway
  responsibility, lines 372-388; bypass-prevention tests, lines 500-508.
- Problem: adapters are not allowed to grant write authority, and the engine
  gateway must reject omitted, forged, or reused autonomy decisions. The design
  does not yet define what makes an autonomy decision valid, bound to one
  proposed mutation, bound to a ticket snapshot, bound to a mode revision, and
  consumable only once.
- Impact: stale decisions, copied decision payloads, or direct low-level write
  paths can bypass the intended boundary while still appearing to satisfy the
  high-level evaluator contract.
- Recommendation: specify an `AutonomyDecision` envelope minted by the runtime
  or gateway. It should bind `mutation_id`, ticket ID, proposed mutation
  fingerprint, evidence fingerprint, ticket snapshot hash, evaluator version,
  mode revision, expiry, and one-consumer semantics. The gateway should reject
  absent, stale, mismatched, or already-consumed decisions.

### 3. The durable outbox lacks a filesystem consistency model

- Lens: Durability, Recoverability, Consistency Model.
- Decision state: explicit decision with underspecified mechanics.
- Anchor: outbox requirements, lines 323-338; turn batch component, lines
  390-394; failure handling for persistence and recovery, lines 412-417.
- Problem: the spec correctly requires a durable attempt record before or
  atomically with mutation, durable summary recovery, and idempotent retry. It
  does not say where outbox records live, what schema/version they use, how
  they are locked, how atomic writes are achieved, or how ticket-file mutation
  and audit/outbox mutation are reconciled after a crash.
- Impact: concurrent turns or process crashes can produce applied ticket
  changes without summaries, duplicate audit rows, stuck pending records, or
  recovery summaries that do not match ticket reality.
- Recommendation: define the outbox source of truth, record state machine,
  schema version, lock scope, atomic write/rename protocol, and reconciliation
  algorithm. Decide explicitly whether the ticket audit and outbox share a
  transaction boundary or are repaired by a recovery pass.

### 4. `plausible unless conflicting` needs internal evidence-source obligations

- Lens: Correctness, Minimal Surprise.
- Decision state: explicit tradeoff with underspecified guardrails.
- Anchor: broad evidence and fanout policy, lines 77-96; evidence floors and
  conflict predicates, lines 200-250; fanout caps, lines 253-287.
- Problem: the aggressive product choice is clear: ambiguity should fan out and
  contradiction is the blocker. The public evidence states stay coarse, which is
  reasonable. The missing part is what evidence sources must be checked before
  claiming a candidate has no conflict, especially under repo-wide open-set
  discovery.
- Impact: an absence of discovered contradiction can become a false safety
  signal. That is most risky for lifecycle, blocker, and `wontfix` mutations
  where user surprise and audit repair cost are higher.
- Recommendation: keep the coarse public state, but add an internal evidence
  matrix by action tier. Include required fresh signal type, required current
  ticket read, required negative-evidence checks, and a `not_searched`
  disposition that cannot apply autonomously for lifecycle or blocker changes.

### 5. Rollback mode is named, but config authority and propagation are open

- Lens: Configuration Clarity, Reversibility.
- Decision state: underspecified.
- Anchor: runtime modes, lines 98-111; rollback semantics, lines 441-444;
  rollback tests, lines 510-518.
- Problem: `discussion_only`, `preview`, and `agent_primary` are the rollout
  and rollback controls, but the design does not specify where project mode
  lives, who can change it, how mode changes are audited, how often mutating
  processes reload it, or what happens when mode config cannot be read.
- Impact: the kill switch can become advisory rather than authoritative. A
  process with cached `agent_primary` state could continue autonomous writes
  after a downgrade.
- Recommendation: define the mode source of truth, mode revision, reload rule
  before each decision, fail-closed behavior for config read errors, and audit
  entry for mode changes. Gateway validation should bind each decision to the
  mode revision it was evaluated under.

## Tension Map

- Aggressive autonomy vs durable recoverability. The product boundary pushes
  toward low-friction autonomous writes, lines 61-111, while the outbox model
  requires durable pre-write records and recovery summaries, lines 323-338. The
  hidden cost is an operational coordinator and storage protocol that must be
  treated as core architecture, not implementation detail.
- Broad inference vs minimal surprise. Repo-wide open-set discovery and
  multi-ticket fanout are explicit goals, lines 77-96, while evidence remains
  intentionally coarse, lines 211-224. The hidden cost is that the evaluator
  must perform enough negative-evidence discovery to make "non-conflicting"
  meaningful.

## Questions And Next Probes

1. What component owns an ordinary thread turn: trigger, candidate discovery,
   turn batch creation, end-of-turn flush, and recovery before the next
   mutation?
2. What is the durable outbox source of truth, and what lock/atomic-write
   protocol makes it consistent with ticket file mutations?
3. What exact fields make an `AutonomyDecision` valid, non-forgeable,
   non-reusable, and bound to a current mode revision?
4. Where does project autonomy mode live, and what read/reload rule makes
   `discussion_only` an immediate kill switch?
