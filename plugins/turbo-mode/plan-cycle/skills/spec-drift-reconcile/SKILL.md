---
name: spec-drift-reconcile
description: "Use when intent changed mid-stream and the artifacts it flowed into — PRD, acceptance map, plan, issues, code — have gone stale against the true current intent and need reconciling: 'the spec changed, what's now stale, reconcile it.' Surfaces each drift with two-sided evidence and blast radius, takes the human's direction decision, then drives the fix through the owning skills. Do not use to detect code-vs-doc reference drift read-only (doc-drift-audit), resolve which source-of-truth governs a claim (baseline), map an interface change's blast radius alone (contract-change-propagation), or author fresh artifacts forward (to-prd/implementation-planning/to-issues)."
---

# Spec Drift Reconcile

When intent changed mid-stream and the artifacts it flowed into — PRD, acceptance map, plan, issues, code — have gone stale against the true current intent, reconcile them: surface each drift, take the human's direction decision, then drive the fix through the owning skills. Invocation: `/spec-drift-reconcile` or `$spec-drift-reconcile`.

The forward chain (`outcome-shaping → to-prd → acceptance-map → implementation-planning`, then either `execute-plan` or `to-issues → implement-issue`) is generate-once and one-directional. When intent moves, the agent tends to patch the leaf — the code, or one artifact — while everything upstream silently rots. This skill is the reconciliation path that chain lacks.

## The cardinal invariant

**No artifact is mutated until a human direction decision is recorded, and the skill never infers which way intent moved.**

A stale spec and a buggy implementation are indistinguishable from the artifacts alone: when the code does X and the PRD says Y, nothing in the repo tells you whether X is an intended evolution or a regression — that fact lives only in the human's head. Any skill that derives direction from the artifacts will, on some real drifts, rewrite a spec to bless a live bug, or revert deliberate new-intent code to satisfy a stale spec. So the skill manufactures a decidable question and enforces the human's answer; it does not answer for them. This one stop is firm. Everything else is judgment.

## What it owns (and nothing else does)

1. **Decidability construction** — turning "these artifacts disagree" into a sharp, answerable question: each live drift with the evidence on *both* sides, the two or three coherent candidate directions, and the blast radius of each.
2. **The direction decision record** — the human's chosen direction for that drift, persisted with its rationale and the per-artifact target end-state. This record is the product; it is what makes the propagation mechanical.
3. **Direction-faithful dispatch** — driving the fix to the owning skills *along the record*, then checking each owner honored it.

## Direction Record

Write the record at `docs/reconciliations/YYYY-MM-DD-<topic>.md` in the reconciled repository unless that repository names another location. It carries the direction question, chosen direction, rationale, each artifact's target end-state and repair mode, and the reconciled repository's HEAD at decision time. Write and commit it at the gate on a working branch, before any dispatch, as its own `docs: record reconciliation direction for <topic>` commit; never write or commit it on a protected branch. A resumed session locates this path and dispatches nothing without the record. A changed direction creates a new record rather than editing the old decision.

## Workflow

`Map → Cluster → Resolve authority → Construct decidability → GATE → Dispatch → Reconcile-faithfulness → Hand off`

1. **Map (read-only).** Inventory the chain artifacts for the affected feature and record what each claims about the disputed behavior. Read the tests — red tests are *evidence* a change may be unfinished, never a verdict.
2. **Cluster.** Trace the artifact drifts to the underlying intent change and ask one direction question per intent change, not one per diff. Surface the clustering for correction ("I read these four drifts as one decision — sync vs async — right?").
3. **Resolve authority — consume `baseline` where available.** If which artifact even *is* the spec is unclear, invoke `baseline` and take its authority verdict in as evidence without re-deriving precedence. If `baseline` is unavailable, put the authority question to the user and take the answer as the verdict.
4. **Construct decidability.** For each intent question, assemble both sides' evidence, the coherent candidate directions, and each direction's blast radius. Run any interface delta through `contract-change-propagation` where available; otherwise list the consumers found and mark the map unverified. Offer a recommended reading, clearly a recommendation. This provokes the decision; it does not make it.
5. **GATE — elicit and record.** Ask the single direction question; capture the human's true current intent and write and commit the direction record described above. Nothing else is mutated before this record exists. Run the elicitation conversationally — one question per intent change — but own it — the question is "which of *these* directions, given *this* blast radius."
6. **Dispatch along the record, in dependency order** — orchestration only (see Tension 2).
7. **Reconcile-faithfulness.** After each owner runs, confirm its output matches the recorded direction (the regenerated check now says 202, not "blocks until ready"). This is the skill's own check, not a new test runner.
8. **Hand off.** Done-ness goes to `closeout-check` and landing to the protected-branch floor plus `git-cycle` where those companions are available. If either is unavailable, report the proof boundary and stop before landing. Never commit on a protected branch; re-inline none of that apparatus.

The minimal case — a single spec↔code pair — is the same shape scaled down, and it still has a direction question. That question is exactly what makes it a reconciliation and not an audit.

## Tension 1 — baseline overlap

Standing authority over a claim → `baseline`, consumed at step 3; reimplement no precedence. A usable baseline does not skip the gate: authority says which artifact governs, not whether intent moved — run the gate regardless, and treat `baseline`'s own `Decision needed` on a changed-intent claim as a seam *into* this skill, not a contested job.

## Tension 2 — orchestrate, never reimplement

Artifact changes are dispatched to an owner where one exists; the reconciler applies the recorded repair mode where none does. The skill also writes its own direction record. The chain was built forward-only, so be honest about where revision is owned and where it is not:

- **In-place owners — dispatch cleanly.** `acceptance-map` updates its artifact in place. Code goes through `tdd` then `keep-green` where available; without them, test first inline and stop when the checks pass. Run an interface delta through `contract-change-propagation` before the plan is finalized where available; without it, list the consumers found and mark the map unverified.
- **Forward-create-only nodes — no revision owner exists.** `to-prd` synthesizes a *new* PRD (no in-place mode), `to-issues` only forward-creates, `implementation-planning` writes a *fresh dated* plan, and `/triage` cannot rewrite a stale issue body. At these nodes, supersede by default: create the corrected artifact, mark the old one superseded, and route tracker state through `/triage` where available. Apply a surgical edit in the owner's format only when the direction record's per-artifact target explicitly selects that repair mode. Flag that the forward-only chain lacks revision modes, and do not grow a general revision engine.

Each owner keeps its own downstream gate, and they stack with this one: this gate approves the *direction*; the owners still gate their own publication, commit, or plan approval.

## Boundaries

- Read-only until the direction record is committed at the gate; orchestrated or recorded surgical mutation after; never commit on a protected branch; landing deferred to `git-cycle` and done-ness to `closeout-check` where available, otherwise stopped with the proof boundary.
- Down-route a pure mechanical noun-drift with no bug-vs-intent question (a symbol was unambiguously renamed) to `doc-drift-audit` + `/triage`. Its routed-out behavioral/intent worklist is, conversely, a feed *into* here.
- Hand a muddy intent the human has not yet formed to `outcome-shaping`; a direction needing net-new design ("keep it synchronous, solve the timeout another way") to `design-exploration`. This skill reconciles a drift; it does not design the new thing.
- The decision record is reconciliation-scoped, not a durable ADR.

## Done when

- Every live drift traces to a recorded human direction decision; nothing was mutated before that record existed.
- Each stale artifact was driven to the recorded target through its owner — or surgically corrected / superseded where no revision owner exists, with the gap flagged.
- Faithfulness was checked per owner; landing and done-ness were handed to `git-cycle` / `closeout-check`, not performed here.
