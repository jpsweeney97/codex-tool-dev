---
name: implementation-review
description: >
  Review completed code against a plan, spec, or prior task list with an
  adversarial, evidence-first workflow. Use when the user says "review my
  implementation", "review my work", "check this against the plan",
  "did I miss anything", "does this match the spec", or presents finished code
  after a planned task. Force a disconfirming pass that tries to prove the
  implementation wrong before allowing a clean verdict. Do NOT use for initial
  code writing, planning, architecture discussion, or general code questions.
---

# Adversarial Implementation Review

Review completed work against a plan or spec by trying to prove the implementation wrong. Act as a reviewer building a case, not a collaborator trying to make the code look acceptable.

## Preconditions

Verify all three before reviewing:

1. `Spec / plan` — the intended behavior, requirements, and constraints
2. `Implementation` — the code or artifacts that claim to satisfy the spec
3. `Scope boundary` — the changed files, PR diff, commit range, or explicit review target

If any precondition is missing, stop and ask for it. Do not infer the spec from the implementation.

If the scope boundary is missing but a diff or PR is available, derive the changed files from that diff and treat unchanged files as context only.

## Stance

- Treat the implementation as unproven until code evidence shows it satisfies the spec.
- Try to falsify each requirement before you allow yourself to say it is satisfied.
- Separate `observed`, `inferred`, and `unverified` statements. Do not blur them together.
- Refuse to mentally repair broken logic. Review the code that exists, not the code the author probably meant.
- Prefer direct language. Say `this violates the spec because ...`, not `you may want to consider ...`.
- Allow zero findings only after the Evidence Gate passes in full.

## Mandatory Workflow

Follow every step in order. Do not jump to the verdict early.

### 1. Build the review ledger

Extract the review target into two explicit inventories:

- `Requirements ledger` — every explicit requirement from the plan or spec
- `Scope ledger` — every changed file and the functions, classes, or flows that carry the change

For each requirement, record:

- `Requirement ID` — short label such as `R1`
- `Spec source` — exact plan step, acceptance criterion, or quoted requirement
- `Status` — `satisfied`, `violated`, `unverified`, or `not-applicable`

Only mark `not-applicable` when the requirement is truly outside the review scope. Explain why.

### 2. Run a falsification pass for each requirement

For every requirement in the ledger:

1. State the easiest way this requirement could be violated
2. Inspect the relevant code path line by line
3. Record the best evidence for and against compliance
4. Assign the status based on evidence, not intuition

Use this burden of proof:

- `satisfied` — spec evidence and code evidence both exist, and your falsification attempt failed
- `violated` — code contradicts the requirement, omits it, or satisfies only a weaker version
- `unverified` — you cannot prove correctness from available evidence
- `not-applicable` — requirement is real but outside the declared scope boundary

Do not treat passing tests, naming, comments, or apparent intent as enough to mark `satisfied` without code evidence.

### 3. Run a failure-mode pass for each changed area

For each changed file or flow in scope, ask at least one adversarial question from each relevant category:

- `Input and validation` — bad types, empty values, malformed payloads, invalid state
- `Control flow` — skipped branches, off-by-one logic, missing cleanup, incorrect sequencing
- `State and concurrency` — races, retries, idempotency, stale reads, partial updates
- `Trust boundaries` — auth, permissions, escaping, secrets, cross-service assumptions
- `Operational behavior` — observability, rollback, error surfacing, timeout and retry behavior
- `Consistency` — divergence from existing patterns that can create split behavior

Record the strongest failure story you checked for each changed area, even if it did not produce a finding.

### 4. Challenge the plan itself

Check whether the plan or spec is ambiguous, unsafe, or incomplete in a way that could mislead an implementer. Record those as plan findings, separate from implementation findings.

Use the most conservative reasonable reading of the spec when it is ambiguous, and state that interpretation explicitly.

### 5. Write findings from the ledger

Write findings only after the ledger is complete.

Each finding must tie together:

- `Spec expectation`
- `Observed implementation behavior`
- `Evidence`
- `Failure consequence`
- `Concrete fix or investigation`

If the issue is only partly proven because a dependency or runtime behavior is hidden, say `unverified` and explain the exact missing evidence.

## Evidence Standard

Meet this standard for every claim:

- `Correctness claim` — cite both the spec source and the code location
- `Violation claim` — cite the code location and the failure mechanism
- `Inference` — label it as inference and show what observation supports it
- `Unknown` — label it `unverified`

Do not use these as substitutes for evidence:

- intent
- comments
- naming
- test existence
- prior trust in the author
- "similar code looked fine elsewhere"

## Output Format

Use this structure:

```markdown
## Implementation Review: [target]

### 1. Review Scope
- Spec / plan reviewed:
- Code reviewed:
- Scope boundary:

### 2. Requirements Ledger
| ID | Requirement | Status | Spec source | Code evidence | Falsification attempt |
|----|-------------|--------|-------------|---------------|-----------------------|

### 3. Findings
1. [severity] [short title]
   - Location:
   - Spec expectation:
   - Observed behavior:
   - Evidence:
   - Why it matters:
   - Fix:

### 4. Unverified Areas
- [area] — [what remains unknown and why]

### 5. Verdict
- Blocker count:
- Verdict: `Ship` / `Ship with fixes` / `Rework needed`
- Highest-risk area:
- Strongest failed attack attempt:
- Plan gaps surfaced during review:
```

List findings before the verdict. If there are no findings, still include sections 1, 2, 4, and 5.

## Evidence Gate

Do not issue a final verdict until every item passes:

- [ ] List every explicit requirement from the spec or plan in the Requirements Ledger
- [ ] Account for every changed file or changed flow in the review scope
- [ ] Record a status for every requirement
- [ ] Cite spec evidence and code evidence for every `satisfied` requirement
- [ ] Record at least one falsification attempt for every changed area
- [ ] Mark every hidden dependency or unexecuted runtime assumption as `unverified`
- [ ] Tie every finding to a requirement, failure mode, or plan gap
- [ ] State the blocker count, even if zero

Apply this additional gate before returning `Ship` or a zero-findings review:

- [ ] No material requirement is `violated`
- [ ] No material requirement is `unverified`
- [ ] The strongest realistic counterexamples were attempted and documented
- [ ] The review contains no reassurance language such as `looks good`, `seems fine`, or `probably correct`

If any gate item fails, continue reviewing. Do not soften the verdict to compensate.

## Red Flags

Stop and re-review if any of these happen:

- You want to summarize before you have built the ledger
- You marked `satisfied` because the intent was obvious
- You used tests as the primary proof of correctness
- You found only plan-level issues and no implementation-level checks
- You skipped failure-mode analysis because the code was small
- You wrote a clean verdict without documenting failed attack attempts
- You are tempted to say `LGTM`, `looks solid`, or `well implemented`

## Troubleshooting

### Review scope is too large for one pass

Split the work by module or flow, but keep one shared Requirements Ledger. Do not issue the final verdict until every module in scope is covered.

### Spec is ambiguous

Record a plan finding. State the conservative interpretation you used and review against that interpretation.

### Behavior depends on a library, service, or runtime you cannot inspect

Mark the requirement or branch as `unverified` unless the calling code clearly handles bad or unexpected behavior from that boundary.

### You wrote the original plan

Assume you are biased toward confirming your own design. Spend extra time on omitted edge cases, vague acceptance criteria, and hidden assumptions.

## Examples

Read [examples](examples/review-findings.md) for strong finding format, weak anti-patterns, and what a justified zero-findings review looks like.
