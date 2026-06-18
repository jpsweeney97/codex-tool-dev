---
name: closeout-check
description: "Use when the user asks whether local work is done, ready, verified, or asks to close out local work with a final local commit. Do not use for ordinary status orientation, broad review, git cleanup, PR review loops, merge/push/publish workflows, branch deletion, remote mutation, or generic session wrap-up/handoff requests."
---

# Closeout Check

Decide whether local work can truthfully be called done. When the user asks to
close the work out, verify it and create the final local commit only if the
evidence supports that claim.

This skill protects completion claims. It is not a broad status report,
commit-shaping workflow, PR workflow, merge workflow, handoff writer, or general
cleanup lane.

## Modes

Use the lightest mode that matches the user's request.

- `readiness`: for "is this done?", "is this ready?", "what proof remains?",
  or similar questions. Inspect and report; do not mutate unless the user also
  asks for closeout.
- `closeout`: for "close this out", "finish this local work", "verify and
  commit", "create the final commit", or equivalent. This authorizes
  focused verification, repo-standard quick checks, narrow safe fixes for
  blocking failures, and local commit creation when all gates pass.

Closeout mode does not authorize pushing, merging, opening or updating PRs,
resolving review threads, deleting files or branches, syncing plugins or
marketplace state, mutating remote state, installing dependencies, publishing,
or writing durable artifacts.

## Trigger Boundaries

Use this skill when the user's main question is completion truth:

- whether a local change is done, verified, ready to commit, ready to hand off,
  or safe to call complete
- closing out local work with verification and a final local commit
- identifying remaining proof gaps before finish

Do not use this skill as the primary lane for:

- broad project status or live-vs-doc orientation; use `orient-status`
- source-of-truth or baseline questions; use `baseline`
- code review, plan review, or skill-contract scrutiny; use the relevant review
  skill
- repository cleanup, broad commit shaping, branch pruning, or untracked-file
  decisions; use `git-hygiene`
- local branch landing or merging; use `merge-branch`
- GitHub PR review response, thread replies, pushes, or re-review requests; use
  `gh-address-comments` to address review comments locally, or `gh-pr-review-loop`
  (explicit-invoke) for the full publish lifecycle when it is available
- debugging or implementation before the work has reached a finish line

If the request mixes closeout with another lifecycle action, complete only the
closeout portion. Then name the owning workflow for the next step.

## Core Workflow

1. Identify the target work and the claim being closed: source behavior, docs
   alignment, tests passing, PR comments addressed, runtime behavior, handoff
   readiness, or another explicit outcome.
2. Inspect live local state before trusting prior notes:
   - `git status --short --branch --untracked-files=all`
   - relevant `git diff --stat`, staged diff, unstaged diff, recent commits,
     and named files
   - repo instructions, touched docs, tests, manifests, or workflow notes that
     define done for this work
3. Classify changed paths as original work, unrelated user work, generated local
   artifacts, or unclear. Stop if unrelated or unclear changes would make
   staging ambiguous.
4. Decide whether the original work is coherent as one final commit. If it has
   multiple separable concerns, stop with `decision needed` instead of splitting
   commits automatically.
5. Run focused verification for the touched behavior.
6. Run the repo's established quick checks by default.
7. Fix blocking failures only within the policies below.
8. In closeout mode, review the final diff, stage exact relevant paths, and
   create local commit(s) only if every gate passes.
9. Report the verdict, evidence, verification, commit(s), proof boundary, and
   remaining next move.

## Verification

Run both focused and repo-standard verification before a closeout commit.

Focused verification should match the touched behavior: targeted tests, parser
checks, dry runs, linters, formatting checks, docs checks, or realistic smoke
checks that prove the edited surface.

Repo-standard quick checks are the cheap established checks named or strongly
implied by repo instructions, README/dev docs, package metadata, CI names, test
docs, or nearby workflow guidance. Do not invent a broad slow suite just because
one exists. Do not install dependencies, fetch remotes, start external services,
or mutate caches unless the user explicitly asks or the repo-standard check
requires it and the action is safe.

If no meaningful focused verification or quick check exists, say so plainly.
Do not convert structural validation into behavior proof, plugin proof, or live
runtime proof.

A passing check suite is not a review. When the work is substantial, risky, or
outward-facing and no review pass has happened, list the missing review as a
remaining gap and name the owning review lane — `review-family:implementation-review`
for code against a plan or spec, when it is available. If an acceptance map was
produced for this work and never verified against the result, list that unverified
map as a remaining gap too. Do not run the review inside closeout, and do not let
its absence block an otherwise-passing closeout unless the user's definition of
done includes review.

## Proof Boundary

Label what was actually proven:

- `source inspected`: live files, diffs, or commit history support the claim
- `structurally validated`: parsing, schema, frontmatter, formatting, or static
  checks passed
- `behavior checked`: focused tests, dry runs, or smoke checks exercised the
  changed behavior
- `runtime verified`: a live app, plugin, service, hook, or other runtime
  surface was inspected
- `remote verified`: remote PR, issue, CI, or service state was refreshed
- `not verified`: a claim would require evidence not gathered in this pass

Use these as honest boundaries, not as ceremony. A source or structural check
does not prove behavior, remote state, plugin installation state, or end-to-end
behavior unless that path was actually exercised. When the edited file is itself
the live source, those structural checks are its proof; install, cache,
distributed-copy, hook, service, and other runtime surfaces need their own checks
only when that surface is part of the claim.

## Blocking Failures

Any failing focused verification or repo-standard quick check blocks the final
commit.

If the failure is caused by the original work, fix it in closeout mode, rerun
the relevant checks, and continue only after they pass.

If the failure appears pre-existing or unrelated, do not commit the original
work with a known failing standard check. Address it only when all of these are
true:

- the failure blocks a repo-standard quick check
- the cause is narrow and understood
- the repair is safe and in scope for closeout
- the repair touches no file already changed by the original work
- the repair can be staged separately from the original work

Commit a qualifying unrelated repair as a separate preliminary local commit —
subject to the same protected-branch gate as the final commit (see Commit
Policy) — then rerun verification before committing the original work.

If an unrelated repair would touch any file already changed by the original
work, stop and ask. Do not split hunks or attempt partial staging to separate
unrelated repair work during closeout.

If the unrelated failure is broad, risky, ambiguous, or cannot be staged
separately, stop with `not ready` and ask for the user's decision before
expanding scope.

## Commit Policy

In closeout mode, "close this out" authorizes local commit creation when every
gate passes.

Before staging, confirm the commit will land on a non-protected work branch. The
branch is already surfaced at workflow step 2 (`git status --short --branch`) —
gate on it; do not re-inspect. Treat repo-defined protected branches first; if
the repo defines none, treat `main`, `master`, `develop`, and `release/*` as
protected. If the checked-out branch is protected or the repo's default branch,
stop with `decision needed` and ask whether to branch first (or hand off to
`git-hygiene` or `merge-branch`) — do not commit. A skill whose job is to protect
completion claims must not itself land an illegitimate or hook-rejected commit on
a protected branch.

Create at most one final commit for the original work. Before committing:

- inspect `git diff --stat` and the relevant diff
- confirm all staged paths belong to the intended commit
- stage exact paths only; do not use broad staging such as `git add -A`
- avoid empty commits
- match the repo's commit-message style when one is clear

Do not split original work into multiple commits automatically. If the original
work contains multiple separable concerns, stop with `decision needed`, name the
concerns, and ask whether to commit them together, switch to `git-hygiene`
commit shaping, or close out only a named subset.

The only automatic extra commit allowed is a preliminary repair commit for a
narrow unrelated pre-existing quick-check failure that satisfies the blocking
failure policy.

## Stop Conditions

Stop and ask instead of committing when:

- the target work or completion claim is unclear
- unrelated or unclear dirty files make safe staging ambiguous
- the closeout commit (including a preliminary repair commit) would land on a
  protected or default branch (see the Commit Policy protected-branch gate) —
  branch first
- focused verification or repo-standard quick checks fail and cannot be safely
  fixed within closeout mode
- a pre-existing repair would touch a file changed by the original work
- the original work is not coherent as one final commit
- the next step requires product, policy, compatibility, ownership, or user
  judgment
- remote, runtime, installation, PR, issue, merge, push, deletion, or publish
  action is needed
- validation is skipped, unavailable, or too weak for the claim being closed

At a stop, report the blocker, evidence, verification state, and exact decision
or repair needed.

## Artifacts And Lifecycle

This skill is chat-only by default.

Do not write handoffs, status docs, summaries, tickets, issue comments, PR
comments, or other durable artifacts unless the user explicitly asks for that
artifact or the owning workflow requires it after separate authorization.

Closeout mode also performs none of the other actions excluded under Modes.
Name the appropriate next workflow instead.

## Output

Start with the verdict.

Use this compact shape for normal closeout:

```markdown
Closeout Verdict: committed | ready but not committed | not ready | decision needed
Claim Checked: <what "done" meant>
Evidence: <live files, diffs, docs, tests, or state inspected>
Verification Run: <commands and results, or not run>
Commit: <hash and message, or none>
Proof Boundary: <source/local/behavior/runtime/remote limits>
Remaining Gaps: <none, or exact gaps>
Next Move: <stop | handoff | merge-branch | git-hygiene | PR workflow | user decision>
```

For small readiness checks, compress the packet but keep the proof boundary
visible when it affects the answer.
