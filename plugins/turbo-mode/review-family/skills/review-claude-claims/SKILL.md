---
name: review-claude-claims
description: >
  Use only when explicitly invoked as `$review-claude-claims` to evaluate pasted
  Claude or external review claims item by item against a recorded live target
  snapshot covering repository, branch, HEAD, PR diff, tests, docs, or other
  relevant evidence. Classify each claim as Valid, Invalid, Partially valid, or
  Unverified; separately record severity and disposition. Read-only unless the
  user explicitly asks Codex to proceed after the evaluation.
---

# Review Claude Claims

Evaluate pasted reviewer claims against current evidence. Treat the pasted
review as allegations to verify, not as authority.

## Boundaries

- Explicit-only: use only when the user invokes `$review-claude-claims`.
- Stay read-only: do not edit files, stage, commit, push, delete, or implement
  fixes unless the user explicitly asks Codex to proceed after the evaluation.
- Current-snapshot scope: evaluate whether each claim is supported by the
  recorded current target snapshot. Do not adjudicate whether an older PR review
  was true at its original review snapshot; use `review-reviewer` for historical
  review-truth adjudication. If a claim depends on an unavailable earlier
  snapshot, classify that historical truth as `Unverified` and name the needed
  recovery check.
- If the review text is missing, ask for it.
- If the target repo, PR, branch, diff, or artifact is unclear and cannot be
  inferred from the current workspace, ask one targeted clarification.
- Prefer live repo truth over the pasted review. Re-read relevant files even
  when the pasted review quotes code.
- Record target provenance before classifying claims: `cwd`, repo root or
  non-repo status, branch, HEAD, dirty state, PR/diff/base when applicable, and
  material evidence gaps.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:review-claude-claims`.

- Use this skill only when explicitly invoked for itemized validation of pasted
  Claude or external review claims against the current target snapshot.
- Use `review-reviewer` instead when the user wants to adjudicate whether a
  supplied review was reliable, historically correct, overreaching, underpowered,
  or missing issues.
- Use `implementation-review` for completed code against a plan/spec,
  `scrutinize` for broad adversarial critique, `system-design-review` for
  architecture tradeoffs, and `request-claude-pr-review` for drafting a Claude
  PR-review prompt.
- If this skill is not the right review-family target, name the better skill
  and switch only when invocation rules allow it; otherwise ask one routing
  question.

## Workflow

1. Identify and record the review target snapshot: current branch, PR, commit
   range, changed files, named artifact, or live repo area.
2. Split the pasted review into discrete claims. Give each claim a stable ID
   and preserve a short source excerpt or source locator. Break compound bullets
   into separate claims when one part could be true and another false.
3. For each claim, inspect the smallest relevant evidence set: code, tests,
   docs, configs, generated artifacts, PR metadata, command output, or local
   contracts.
4. Classify each claim using the definitions below. Do not upgrade a claim past
   `Unverified` without direct evidence.
5. Separately assign severity and disposition. Do not let truth classification
   decide priority or implementation scope by itself.
6. End with a short summary of which items are worth acting on now.

Use safe targeted commands when they materially change classification, such as
`pwd`, `git status --short`, `git branch --show-current`, `git rev-parse HEAD`,
`git diff --stat`, `git diff`, `rg`, focused tests, or `gh pr view` when PR
context is needed and available.
If a useful check is too broad, unavailable, flaky, mutating, or blocked by
permissions, mark the item `Unverified` and name the exact check.

## Classifications

- `Valid`: supported by code, tests, docs, contracts, or runtime evidence.
- `Invalid`: contradicted by the implementation, tests, docs, contracts, or
  explicit repo policy.
- `Partially valid`: identifies a real concern, but overstates severity,
  misstates the mechanism, targets the wrong scope, or proposes the wrong fix.
- `Unverified`: plausible, but available evidence is insufficient; needs a
  targeted check before implementation.

## Severity And Disposition

Severity describes impact, not whether the claim is true:

- `blocker`: likely to cause data loss, security failure, broken release,
  incorrect behavior, or a material requirement failure in the reviewed scope.
- `should-fix`: real issue with bounded blast radius or meaningful maintenance
  risk.
- `note`: true or partially true observation that does not need immediate repair.
- `none`: use for `Invalid` claims unless a separate follow-up is needed.

Disposition describes what to do next:

- `fix`: implement a repair in the reviewed scope.
- `narrow`: repair only the true or in-scope part of an overstated claim.
- `reject`: do not implement based on this claim.
- `defer`: track later because the claim is true but outside the current scope.
- `verify`: run the named check before deciding.

## Output

Start with:

- `Target snapshot`: `cwd`, repo root or non-repo status, branch, HEAD, dirty
  state, PR/diff/base when applicable, and evidence gaps.

Then provide an item-by-item table or compact list. For each item include:

- `Claim ID`: stable identifier.
- `Source`: short excerpt or source locator from the pasted review.
- `Claim`: concise restatement without changing scope.
- `Classification`: one of `Valid`, `Invalid`, `Partially valid`, or
  `Unverified`.
- `Severity`: one of `blocker`, `should-fix`, `note`, or `none`.
- `Evidence`: file/line references, command output summary, PR metadata, or the
  reason evidence is missing.
- `Reasoning`: why the evidence supports that classification.
- `Disposition`: `fix`, `narrow`, `reject`, `defer`, or `verify` with a named
  check.

Then include:

- `Act on now`: `Valid` or `Partially valid` claims with `blocker` or
  `should-fix` severity and `fix` or `narrow` disposition.
- `Do not act on`: claims classified `Invalid`.
- `Needs verification`: claims classified `Unverified` and the specific check
  required.
- `Deferred`: true or partially true claims intentionally outside current scope.

## Review Discipline

- Cite exact file paths and line numbers for file-backed conclusions.
- Separate source evidence, tests, docs/contracts, runtime evidence, and PR
  metadata when they point in different directions.
- Do not treat reviewer confidence, apparent plausibility, or matching wording
  as evidence.
- Do not let one valid subclaim make a compound claim fully valid.
- Do not silently fix anything during the evaluation. If the user later says to
  proceed, re-read the selected files, re-check the target snapshot, and
  implement only the selected items.
