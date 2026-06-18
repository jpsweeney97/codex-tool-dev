---
name: gh-pr-review-loop
description: "Use only when the user explicitly invokes `/gh-pr-review-loop` or `$gh-pr-review-loop`, or clearly asks for the full GitHub PR review-response lifecycle, including fixing real review-thread issues and publishing the result with commit, push, thread replies/resolution, and re-review request. Do not use for ordinary comment addressing (use gh-address-comments), first-pass PR reviews, CI debugging, issue triage, or comment summaries without that full-loop authorization."
disable-model-invocation: true
---

# GH PR Review Loop

Run an end-to-end PR-level review response: the `gh-address-comments` inner loop
(verify, classify, fix locally, draft replies, one local commit) plus the
publish authority to push, reply, resolve threads, and request re-review. This
is an orchestration skill — `gh-address-comments` owns the per-thread
verification, the disposition taxonomy, fixing, and reception discipline; this
skill owns the publish policy, checkpoints, and publication order. Use the
GitHub app, `gh`, and existing GitHub review-comment workflows for the
mechanics.

## Boundaries

- Full-loop trigger: use this skill when the user invokes `$gh-pr-review-loop`
  (`/gh-pr-review-loop` in Claude Code) or clearly requests the full commit,
  push, reply/resolve, and re-review lifecycle.
- Full-loop authorization: that clear full-loop request authorizes local edits,
  one coherent commit when needed, one push, thread replies and resolution, and a
  top-level `@codex review` request when all checkpoint conditions are clear.
- Non-trigger: ordinary "address PR comments", comment summaries, first-pass PR
  reviews, CI triage, issue triage, or requests that do not clearly authorize
  GitHub write actions. Use `gh-address-comments`, which runs the same inner loop
  but stops at a local commit.
- Scope: default to all unresolved review threads on the current or specified
  PR. Include top-level PR comments only when they are clearly review feedback
  the user wants handled in the same loop.
- Human-reviewer caution: verify and fix human-authored threads, but resolve
  them only when the thread is clearly mechanical or repo practice supports
  author resolution. Otherwise reply with evidence and leave the thread open.

## Inner Loop

Run the `gh-address-comments` inner loop on the target PR. It resolves the PR,
fetches thread-aware review data, verifies and classifies every unresolved
thread (the disposition taxonomy and the evidence-pointer rule live there),
applies the reception discipline, fixes real actionable issues, drafts a concise
evidence-backed reply per thread, runs verification tied to the touched
behavior, and produces one coherent local commit — or takes the no-code-change
path.

Do not proceed to publication unless the inner loop reached a clean stop:
verification passed, no thread is left `needs-user-decision`, and fixes did not
fragment into changes that should be separate commits. If a thread is
`needs-user-decision`, stop and let the user decide before publishing.

If the inner loop reports no unresolved review threads, there is nothing to
publish: do not create an empty commit, push, resolve anything, or request
`@codex review` unless the user explicitly asked for a fresh review request.

## Publish Preflight

Beyond the inner loop's own checks, before publishing:

- Confirm the local branch is the PR head branch and the intended push target.
- Checkpoint if unrelated dirty changes remain in the worktree, or if GitHub
  authentication, write permissions, or rate limits are uncertain.

## Publication Order

When all publish preconditions hold:

1. Review `git diff --stat` and the relevant diff for the inner-loop commit.
2. Push the inner-loop commit once to the PR head branch. On the no-code-change
   path there is no commit — skip to replies. If the push is rejected here
   (non-fast-forward, protected branch, required-PR rule, or denied permission),
   stop before steps 3-5 and report the exact rejection and next move: replying,
   resolving threads, or requesting re-review now would publish review state for
   a commit that never reached the remote.
3. Reply to every reviewed thread with its disposition and concise evidence.
4. Resolve appropriate threads:
   - Resolve bot/Codex threads classified as `fixed`, `incorrect`,
     `already-addressed`, or strongly evidenced `not-reproducible`.
   - Resolve human-authored threads only when clearly mechanical or normal for
     the repo; otherwise reply and leave open.
   - Never resolve `needs-user-decision` threads.
5. If all review threads are resolved and the PR is otherwise ready, post a new
   top-level PR comment exactly containing `@codex review`, unless repo
   documentation specifies a different trigger. Do not include the trigger in
   per-thread replies.

## Checkpoints

Stop and ask before pushing, resolving, or requesting re-review when any of these
apply:

- The inner loop did not reach a clean stop: verification failed, was skipped, or
  could not be matched to the touched behavior; a thread is `needs-user-decision`;
  or fixes span unrelated areas that may need separate commits.
- The PR or head branch cannot be confidently resolved, or the push target is
  ambiguous.
- Unrelated dirty worktree changes make safe publishing ambiguous.
- Human-thread resolution is socially or procedurally unclear.
- GitHub authentication, rate limits, or missing permissions make thread state or
  write actions uncertain.

At a checkpoint, summarize thread dispositions, local changes, verification
status, and the exact decision needed.

## Final Response

Report:

- Threads handled and their dispositions.
- Files changed and commit hash, when a commit was created.
- Push target, when pushed.
- Verification commands and results.
- Threads replied to, resolved, or intentionally left open.
- Whether a top-level `@codex review` request was posted.
