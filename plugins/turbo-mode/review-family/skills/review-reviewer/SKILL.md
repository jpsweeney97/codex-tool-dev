---
name: review-reviewer
description: "Use only when the user explicitly invokes `/review-reviewer` or `$review-reviewer` to adjudicate a supplied review, or to check one or more pasted claims, against current evidence before acting. Do not use for first-pass artifact reviews, generic scrutiny, implementation reviews, basic claim extraction without evidence checking, natural-language review requests, or follow-up fixes."
disable-model-invocation: true
---

# Review Reviewer

Adjudicate another review without rubber-stamping it. Treat the supplied review as allegations to test, not as authority or as an enemy to defeat. A single claim, or a few pasted claims with no review around them, gets the same treatment.

## Boundaries

- Required input: the supplied review or claims. If none was supplied, ask for it and stop; do not infer a review from the surrounding conversation. Infer the target from the review, the claims, and the immediate context; if more than one plausible target remains, ask which.
- Default to read-only. You may inspect files, diffs, git metadata, PR metadata, docs, and run bounded non-mutating checks directly tied to the inferred target, a disputed claim, or a bounded independent or missed issue; do not edit files, stage, commit, push, delete, sync, publish, or implement fixes unless the user explicitly asks for that separate action; the same gate covers installing dependencies, creating tickets, and running broad test suites.
- Stop after the adjudication unless the user also asked for the fixes. Give dispositions and the next action.
- Other review work: completed code against a plan or spec → `implementation-review`; first-pass adversarial critique → `scrutinize`; architecture tradeoffs → `system-design-review`; an agent skill or skill contract → `scrutinize-skill`.

## Method

1. Read the target fresh before judging the review's claims, and note any issue you find on your own.
2. Split the review into the smallest meaningful claims of fact, severity, or remedy, with stable IDs such as `R1` and `R1.a`.
3. Check each claim against inspected evidence, and give it a truth verdict and a disposition.
4. Look for high-signal issues the review missed, in the files, hunks, and requirement sections its claims touch and in the failure modes directly beside them. Do not widen into a full review of the target.

Each verdict needs a compact evidence pointer: file and line, PR comment or diff hunk, command output, or a named doc section. A reviewer's quotation shows what the review claimed; it is not evidence about the target. If the target cannot be read, target-dependent claims stay `unverified`, and inaccessible evidence never justifies `challenged`.

## Verdicts And Dispositions

Truth verdict says whether the claim holds on inspected evidence:

- `confirmed`: the material claim and implied consequence both hold on inspected evidence.
- `challenged`: the core fact is wrong, the severity is materially inflated, the recommendation does not follow at the truth boundary, or inspection establishes that the cited evidence is absent or contradicted at that boundary.
- `unverified`: available evidence cannot settle the claim; name the exact check or artifact access that would.

A claim that was true when the review was written and no longer applies keeps `confirmed` and gets a `reject` or `defer` disposition with a note that it is stale.

Disposition says what to do next, with one terse action sentence:

- `act`: address the confirmed issue now.
- `narrow`: address only the true or in-scope part of an overstated current claim.
- `defer`: real issue, but outside the current review scope or not urgent here.
- `reject`: do not act on this review claim.
- `verify-first`: perform the named check before accepting or rejecting it.

Severity, for issues you found yourself and issues the review missed:

- `blocker`: likely to break a material requirement, release, data integrity, security boundary, or user-visible behavior in the reviewed scope.
- `should-fix`: real issue with bounded impact or meaningful maintenance risk.
- `note`: true observation that does not require immediate action.

## Output

Open with one sentence that says how much of the review held. Then give one entry per claim: its ID, the claim in brief, the truth verdict, the evidence pointer, and the disposition. Then give missed issues, and anything that needs a check before it can be settled. Leave out a part that has nothing in it. If you authored the target or the review, say so.

Close with two lists:

- `Act On Now`: confirmed claims and missed issues with an `act` or `narrow` disposition.
- `Do Not Act On`: claims with a `reject` disposition, each with its reason in a few words.
