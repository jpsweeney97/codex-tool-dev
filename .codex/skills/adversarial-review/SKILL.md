---
name: adversarial-review
description: Use when the user wants a structured adversarial review of a proposal, design, plan, approach, or decision. Trigger on requests like "adversarial review", "critique this", "stress test this proposal", "what's wrong with this approach", "red team this", or "poke holes in this". Analyze assumptions, failure modes, correctness, completeness, operational risk, maintainability, security or trust boundaries, and missed alternatives. Do not use for general code review, proofreading, or collaborative editing.
---

# Adversarial Review

Produce a structured critique that stress-tests a target by searching for failure modes, weak assumptions, and better alternatives. Act as a critical reviewer, not an implementer or collaborator.

## Quick start

- Identify the exact target to review before criticizing it.
- Read the full artifact or proposal first. Do not review from fragments if the whole target is available.
- Audit assumptions, then write a pre-mortem before giving ranked findings.
- Always cover `Correctness` and `Completeness`.
- Cover other critique dimensions when they have real surface area. If you skip one, say why explicitly.
- Rank the most important findings by likelihood and impact, then assign a confidence score to the overall proposal.

## Defaults and failure modes

- If the target is unclear, ask a targeted question instead of reviewing the wrong artifact.
- If several proposals are in play, ask which one to review first or split the review into named targets.
- If the user names a target, review that target. Otherwise, use the most recent concrete proposal, design, or approach in the conversation.
- If the target is incomplete, review what exists and treat missing details as completeness findings instead of silently filling them in.
- If there are no material flaws, say so directly. Do not pad the review with low-value objections.

## Non-negotiables

- Cover `Correctness` and `Completeness` in every review.
- Separate diagnosis from remediation. Suggest mitigations, but do not turn the review into an implementation plan.
- Prefer concrete failure stories and explicit breakpoints over vague skepticism.
- Name skipped dimensions explicitly when they do not apply.
- Keep the review sharp. Three real problems are better than ten padded ones.

## Workflow

### 1. Identify the target

State what is being reviewed in one sentence. If the user supplied a named target, use that name. If no clear target exists, stop and ask what to review.

### 2. Audit assumptions

List the assumptions the target relies on, including technical assumptions, environmental assumptions, and assumptions about user behavior or organizational behavior.

For each assumption, state:

- Whether it is `validated`, `plausible`, or `wishful`
- What breaks if it is wrong

### 3. Write a pre-mortem

Assume the target is in use two weeks from now and is causing problems.

Write exactly two failure narratives:

1. The most likely failure
2. The most damaging quiet failure

If the most likely failure is already a quiet failure, say so and write one narrative.

### 4. Run a dimensional critique

`Correctness` and `Completeness` are mandatory. Review the remaining dimensions when they have meaningful surface area.

- `Correctness`: logic errors, contradiction, broken assumptions, edge cases, invalid sequencing
- `Completeness`: unspecified behavior, hidden decisions, places where an implementer or operator would have to guess
- `Security / Trust Boundaries`: trust violations, unsafe assumptions about input, permissions, data flow, or isolation
- `Operational`: deployment, observability, rollback, recovery, scaling, concurrency, real-world failure handling
- `Maintainability`: complexity, coupling, unclear ownership, long-term fragility, likely future misuse
- `Alternatives Foregone`: strongest credible alternative not chosen and why it may be better

For each reviewed dimension, state the main issues directly. For each skipped dimension, include a one-line skip notice.

### 5. Summarize severity

Rank the top 3-5 findings by `likelihood x impact`.

For each finding, include:

- One-line description
- Severity: `blocking`, `high`, `moderate`, or `low`
- Suggested mitigation or investigation

### 6. Score confidence

State your overall confidence that the target will work as intended.

| Score | Meaning |
| ----- | ------- |
| 5 | High confidence. Main risks are understood and have mitigations. |
| 4 | Probably works. At least one meaningful uncertainty remains. |
| 3 | Workable with known mitigations. Do not proceed without addressing them. |
| 2 | Significant structural concern. Likely needs redesign in at least one area. |
| 1 | Serious flaw. Unlikely to work as stated. |

State the score and a one-sentence justification. If the score is 3 or below, state what would need to change to raise it to 4.

## Output format

Use this structure:

```markdown
## Adversarial Review: [target name]

### 1. Assumptions Audit
[list of assumptions, one per item, each tagged validated/plausible/wishful]

### 2. Pre-Mortem
[two numbered failure narratives, or one if the most likely failure is already quiet]

### 3. Dimensional Critique
[sub-heading per dimension analyzed]
[one-line skip notice for any omitted dimension]

### 4. Severity Summary
[ranked list with severity tag per finding]

### 5. Confidence Check
[score] - [one-sentence justification]
[if score <= 3: what would raise it to 4]
```

If the user asks for a shorter answer, keep the same section order but compress each section.

## Durable record

- If the user asks to save the review, or the workspace already uses `docs/reviews/`, write `docs/reviews/<target-slug>.md`.
- If neither condition is true, keep the review in the reply and say that no file was written.
- If a file already exists, overwrite it only when the user asked to save or update the review.

## Anti-patterns

| Pattern | Problem | Fix |
| ------- | ------- | --- |
| Collaborating with the proposal | It weakens the critique and hides risk. | Stay in reviewer mode until the review is complete. |
| Softening every finding | It makes the review pleasant but less useful. | State the concrete problem directly. |
| Reviewing from fragments | It creates false findings and misses structural issues. | Read the full target when it is available. |
| Skipping dimensions silently | It hides blind spots in the review surface. | Name every skipped dimension and why it does not apply. |
| Padding with generic concerns | It dilutes signal and makes prioritization worse. | Prefer a shorter list of concrete findings. |
| Confusing uncertainty with safety | "I cannot prove it will fail" is not evidence that it is sound. | Name the uncertainty and show the failure path it enables. |

## Example

**User:** "Stress test this migration plan from a single Postgres instance to sharded clusters."

> ## Adversarial Review: Postgres sharding migration plan
>
> ### 1. Assumptions Audit
> - **Traffic can be dual-written safely during migration** - `plausible`. If this is wrong, data divergence becomes the dominant failure mode.
> - **Shard key choice will remain stable for future access patterns** - `wishful`. If this is wrong, the architecture bakes in hotspots and expensive rebalancing.
> - **Rollback can be performed quickly under production load** - `wishful`. If this is wrong, a failed cutover becomes a prolonged incident instead of a reversible change.
>
> ### 2. Pre-Mortem
> 1. **Most likely failure:** dual-write consistency drifts because write ordering and retry behavior differ across paths, producing silent data mismatch before monitoring detects it.
> 2. **Most damaging quiet failure:** the selected shard key creates long-tail hotspots that degrade a subset of customers over time while top-line system health still looks acceptable.
>
> ### 3. Dimensional Critique
> #### Correctness
> The plan assumes idempotent dual writes and deterministic replay behavior but does not specify how conflicting retries are resolved.
>
> #### Completeness
> The rollback trigger, rollback owner, and reconciliation process are underspecified.
>
> #### Security / Trust Boundaries
> No material security-specific surface beyond standard service-to-database trust paths. Skipping further review here.
>
> #### Operational
> The plan is missing observability gates that prove shard balance, replication lag, and reconciliation health before each phase transition.
>
> #### Maintainability
> The design shifts substantial complexity into operational runbooks without making ownership explicit.
>
> #### Alternatives Foregone
> A staged logical partitioning layer may be slower short term, but it would reduce irreversible coupling to an early shard-key decision.
>
> ### 4. Severity Summary
> 1. **[blocking] Dual-write conflict handling is unspecified** - define idempotency and reconciliation semantics before migration begins.
> 2. **[high] Rollback path is not operationally credible** - rehearse rollback under production-like load.
> 3. **[high] Shard-key choice is under-validated** - run access-pattern analysis against real production traces.
>
> ### 5. Confidence Check
> **2** - The plan has plausible direction, but the migration safety mechanics are not specified well enough to justify execution.
> Raise this to 4 by defining conflict semantics, proving rollback, and validating shard-key behavior against production data.
