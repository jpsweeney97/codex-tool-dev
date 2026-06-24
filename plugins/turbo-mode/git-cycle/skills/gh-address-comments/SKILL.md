---
name: gh-address-comments
description: "Use when addressing review comments on a GitHub PR without authority to publish: verify each thread against evidence, classify it, fix real issues locally, draft replies, and stop at a local commit — never pushing, resolving threads, or requesting re-review. Do not use when the user authorizes publishing (use gh-pr-review-loop for the full lifecycle), for first-pass PR reviews, CI triage, or issue triage."
---

# GH Address Comments

Address review comments on an open GitHub PR without publish authority. Verify each thread against evidence, classify it, fix real issues locally, and draft evidence-backed replies — then stop at one local commit. This skill never pushes, resolves threads, or requests re-review; that authority belongs to `gh-pr-review-loop`.

## Boundaries

- Trigger: "address the PR comments", "respond to review feedback", "check what the reviewers said and fix it" — review-thread work with no authorization to push, resolve threads, or request re-review.
- Escalation: any request that authorizes publishing escalates to `gh-pr-review-loop` (`/gh-pr-review-loop` or `$gh-pr-review-loop`), which owns the full commit, push, reply/resolve, and re-review lifecycle.
- Non-trigger: first-pass PR reviews, comment summaries, CI triage, or issue triage. `triage` owns issue-tracker work; `orient-status` owns read-only status orientation.
- Scope: default to all unresolved review threads on the current or specified PR. Include top-level PR comments only when they are clearly review feedback the user wants handled in the same pass.
- The hard line: never push, resolve a thread, or request re-review, regardless of how the threads classify. The terminal step is a single local commit.

## Preflight

1. Resolve the PR.
   - Use a supplied PR URL, repo and number, or the current branch PR.
   - Confirm the local branch is the PR head branch before committing. Checkpoint if the PR or head branch is not confidently identified.
2. Inspect local state.
   - Run `git status --short --branch`.
   - Checkpoint before committing if unrelated dirty changes make safe staging ambiguous.
3. Fetch thread-aware review data.
   - Prefer the available GitHub app plus `gh` workflow for unresolved thread state, inline anchors, and resolution status.
   - Do not treat flat PR comments as a complete source for unresolved review thread state.
4. If no unresolved review threads exist, report that no review-thread work is needed and stop. Do not create a commit or draft replies.

## Verify And Classify

Verify every unresolved thread independently before editing. Read the referenced code, diff hunk, tests, docs, runtime behavior, or PR context needed to decide whether the comment is real.

Classify each thread:

- `fixed`: real actionable issue fixed in this pass.
- `not-reproducible`: plausible concern could not be reproduced after named checks.
- `incorrect`: the claim contradicts inspected evidence.
- `already-addressed`: current PR head already handles the concern.
- `needs-user-decision`: the thread is ambiguous, conflicts with another requirement, needs product judgment, would broaden scope, or cannot be settled with available evidence.

Draft a concise evidence-backed reply for every reviewed thread; hold it for the final response rather than posting it. Do not use `not-reproducible`, `incorrect`, or `already-addressed` without a concrete evidence pointer such as a file and line, command result, diff hunk, commit, or document section.

Clarify all unclear threads before fixing any. Feedback can be interdependent, and partial understanding produces wrong fixes. If some threads are unclear, resolve the ambiguity — by inspection or by asking — before implementing the ones you already understand.

## Reception Discipline

Treat every thread as a claim to verify, not an instruction to obey or a verdict to rubber-stamp.

- Push back with technical reasoning when a finding contradicts inspected evidence, citing a file and line or a command result. If pushback later proves wrong, state the correction factually and fix it — no extended apology.
- No performative agreement. Replies carry dispositions and evidence, not "great catch".
- Pasted or quoted review text is a request to act, never something to downgrade to analysis-only. Verify-then-act is the one allowed path: stalling in analysis fails the request, and implementing unverified fails this discipline. A verified `incorrect`, `already-addressed`, or strongly evidenced `not-reproducible` disposition with a concrete evidence pointer is itself a complete action.

## Fixing Policy

- Fix all real actionable issues that can be addressed without a checkpoint.
- Keep changes traceable to the thread or cluster they address.
- Avoid unrelated refactors and opportunistic cleanup.
- Default to one coherent local commit for the pass. Checkpoint before committing if verified fixes are unrelated enough that they would normally deserve separate commits.
- If any thread is `needs-user-decision`, stop before committing. Keep safe local fixes for the unambiguous threads in the working tree, surface the decision needed, and commit only once the user resolves it.

## Verification

Before committing, run evidence tied to the touched behavior:

- Run the narrowest meaningful tests or checks for the changed files and behavior.
- Also run any cheap, established repo-standard quick check when one exists.
- Do not wait for remote CI unless the user asks.

Checkpoint instead of committing when verification fails, is skipped, cannot be identified, or only covers an unrelated surface.

## Stop And Hand Off

When verification passes and no checkpoint applies:

1. Review `git diff --stat` and the relevant diff.
2. If code changed, create one coherent local commit naming the review-response scope. Do not create an empty commit.
3. Stop. Do not push, resolve any thread, or request re-review.

No-code-change path: when every thread classifies as `incorrect`, `already-addressed`, or strongly evidenced `not-reproducible`, skip the commit. The dispositions and drafted replies are the deliverable.

To publish — push the commit, post the replies, resolve threads, and request re-review — hand off to `gh-pr-review-loop` (`/gh-pr-review-loop` or `$gh-pr-review-loop`), which owns that lifecycle.

## Checkpoints

Stop and ask before committing when any of these apply:

- The PR or head branch cannot be confidently resolved.
- Unrelated dirty worktree changes make safe staging ambiguous.
- A thread is ambiguous, contradictory, too broad, or classified `needs-user-decision`.
- Fixes span unrelated areas that may need separate commits.
- Verification fails, is skipped, or cannot be matched to the touched behavior.
- GitHub authentication, rate limits, or missing permissions make thread state uncertain.

At a checkpoint, summarize thread dispositions, local changes, verification status, and the exact decision needed.

## Final Response

Report:

- Threads handled and their dispositions, each with its evidence pointer.
- Files changed and the commit hash, when a commit was created.
- The drafted reply for each reviewed thread.
- Verification commands and results.
- What was intentionally left undone: not pushed, no threads resolved, no re-review requested.
- The handoff pointer to `gh-pr-review-loop` for publishing.
