---
name: land
description: "Use when the user has endorsed finished work and instructs you to land it — `/land`, `$land`, `land it`, `push it`, `ship this` — running the whole post-endorsement ritual as one authorized sequence: commit, merge or push, save a handoff, refresh the throughline. Do not use to judge whether work is done (`closeout-check`), to author or update a PR (`pr-description`), to preview a landing without performing it, or from a subagent, hook, or scheduled context."
argument-hint: "[target branch] [--no-throughline]"
---

# Land

Run the post-endorsement closeout ritual end to end on a single authorization. The user has already made the only real decision — this work is done — and everything that follows is its foregone conclusion: commit what is in scope, merge or push it, save a handoff, refresh the throughline. Invocation: `/land` or `$land`, or a plain instruction to land, push, or ship the current work.

This skill contributes sequencing and authorization, nothing else. `merge-branch` owns local landing, `save-handoff` owns the handoff, `throughline` owns the refresh. Each keeps its own preconditions, and when one of them stops, its finding is the answer — never overruled, re-derived, or worked around here.

## One authorization

The invocation authorizes the whole sequence. Do not pause between commit, merge, push, handoff, and throughline to confirm the next step: re-asking for permission already granted is the exact cost this skill exists to remove. Only a hard stop interrupts a run.

It does not authorize firing on inference. Run only when the user's own instruction in this turn is to land, push, or ship the work — never from "that looks done", never from a question about what landing would involve, and never from a subagent, hook, cron, or other unattended context. In those cases say what you would have done, and stop.

Read modifiers from the instruction in whatever form they arrive: a named target (`land main`) fixes the merge target, `land --no-throughline` or any plain equivalent skips the refresh, and "just push" or "don't merge" holds the run to the push lane. Anything asking for a pull request is a different lifecycle — hand it to `pr-description`.

## Read state, state the plan, then execute

One read-only pass first, enough to pick the lane and no more — re-running a constituent's own gate here is duplication, not safety:

```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
git branch --show-current
git status --short --branch --untracked-files=all
git log --oneline --decorate -5
git worktree list --porcelain
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
```

Use the `--git-dir` path to check for `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, or `BISECT_LOG`. Do not fetch or pull: remote state is read only through refs already on disk and through the push itself.

Treat repo-defined protected branches first; if the repo defines none, treat `main`, `master`, `develop`, and `release/*` as protected.

Then state the computed plan as one line, and execute it in the same turn — visibility without costing a round-trip:

```text
Plan: commit 4 files → merge chore/x into main (ff) → push main to origin (5 commits) → handoff → throughline
```

## Lane selection

| Observed state | Sequence |
|---|---|
| A git operation is in progress | stop → `resolve-conflicts` |
| The branch was cut in a persistent, locked satellite worktree | stop → `worktree-task-cycle` |
| Dirty tree, every path in scope, branch not protected | commit, then continue |
| Dirty tree, any path unrelated or unclear | stop |
| Dirty tree on a protected branch | stop — branch first |
| Current branch has an upstream | push that branch; do not merge |
| Current branch is local-only and not protected | `merge-branch`, then push the target |
| Current branch is the base or default branch | push it |
| Nothing to commit and nothing ahead of the upstream | skip the push, say so, continue |

An upstream is what decides the merge, because a published branch is usually under review somewhere: pushing it leaves that review intact, while merging it into the base locally lands it behind its own pull request. A local-only branch has no such review to respect, so the local landing lane is the only reading of "land" that does anything.

Then, always: `save-handoff`, then `throughline` — in that order, so the refresh folds the handoff just written. The pair is the default, never an opt-in. Skip the refresh only on an explicit opt-out, and the handoff only when the session genuinely holds no context worth preserving; say which, rather than writing an empty one. Where either skill is unavailable, say so in the packet instead of improvising a handoff by hand.

## Commit

This runs only in the push lane. In the merge lane `merge-branch` commits under its own step, and this section does not run.

Classify every changed path as branch work, unrelated user work, generated artifact, or unclear. Stop on anything unrelated or unclear — ask for a file decision rather than staging broadly. Stage exact paths, never `git add -A`; draft the message from the work just completed in the repo's commit style; review the staged diff before committing.

## Push

Push exactly one ref: the branch the work now lives on — the target `merge-branch` just landed into, or the checked-out branch.

- Fast-forward only. Never `--force`, never `--force-with-lease`, never a refspec that could rewrite remote history.
- A protected branch is a legitimate target when it is this run's own: the branch just merged into, or the branch the user was standing on when they invoked. Any other protected ref is a hard stop.
- Name the ref, the remote, and the commit count in the plan line before pushing.
- A rejected push is a hard stop, not something to reconcile. Do not fetch, pull, rebase, or retry with force — report the exact rejection and hand the reconciliation decision back.

## Hard stops

The gate collapses certain-yes steps only. Stop, and run no later step, when:

- a check the session established as governing this work is known failing
- the remote has diverged, or the push is rejected for any reason
- a merge, rebase, cherry-pick, revert, or bisect is in progress — `resolve-conflicts` owns finishing it
- the push target would be a protected branch that is not this run's own
- the dirty tree holds files outside the work being landed, or the branch is protected and dirty
- any constituent skill stops — surface its finding as that skill stated it

At a stop, report the packet below with everything that did complete, then the blocker and the skill that owns the next move. There are no partial silent landings: what happened and what did not are both stated.

A stop that fires after the push — a refused handoff write, an unavailable skill — does not undo the landing. Never revert, reset, or force-push to walk a completed landing back; report what completed, name the step that did not, and hand the next move over.

## What this is not

- Not the done-verdict. Whether the work is finished is `closeout-check`'s call, made before this runs. `land` runs no fresh verification suite: it acts on the endorsement it was given, and when no check ever ran the packet says so rather than implying one did.
- Not a pull-request workflow. `pr-description` authors a PR body; `gh-pr-review-loop` owns the review-response publish lifecycle.
- Not a fix-application step. Findings are applied before the gate, not by it.
- Not a release or publish step. It never cuts a version, republishes a plugin cache, or syncs a mirror; when the landed work includes a version bump, name that in the packet as a remaining step.
- Not branch cleanup. The source branch survives the merge unless the user asked for deletion, which is `merge-branch`'s own rule.

## Output

```markdown
Landed: <the work, in one clause>
Committed: <hash and subject | none — why>
Merged: <source → target, ff | none — why>
Pushed: <ref → remote, N commits | none — why>
Handoff: <absolute path | skipped — why>
Throughline: <absolute path, folded N | skipped — why>
Stopped at: <none | step, blocker, owning skill>
```
