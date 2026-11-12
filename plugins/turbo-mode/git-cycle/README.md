# Git Cycle

Get local work safely from a dirty working tree to merged-and-shared. Ten skills covering one arc:

- `git-hygiene` — audit and clean local git state; shape commits by concern; prune branches.
- `closeout-check` — decide whether work is truly done and create the final local commit.
- `merge-branch` — fast-forward-land a completed branch into a verified target, locally; also holds the 3 rules for finishing a merge, rebase, cherry-pick, or revert that stopped on conflicts.
- `land` — on the user's explicit instruction to land, push, or ship, run the whole post-endorsement ritual as one authorized sequence: commit what is in scope, merge or push, save a handoff, refresh the throughline; any constituent skill's stop is the answer.
- `exiting-worktrees` — check that work landed, then remove the worktree and its branch (`git worktree`, or Claude Code's `ExitWorktree` where it applies).
- `worktree-task-cycle` — work a task through its full lifecycle in a persistent, locked satellite worktree, including landing into the primary checkout.
- `release-cut` — derive the next semver from the real landed change class, bump the authoritative manifest, and write the dated CHANGELOG section in lockstep, stopping at a staged local bump.
- `pr-description` — draft a PR title and body and stop; open or update the PR only on explicit authority; never assume `main` as the base.
- `gh-address-comments` — verify, classify, and fix PR review threads locally; stop at one commit.
- `gh-pr-review-loop` — the full publish lifecycle on top of `gh-address-comments` (explicit-invoke).

Shared safety conventions (the protected-branch set, in-progress-operation markers, fast-forward landing discipline) are kept inline in each skill — never behind a conditionally-loaded pointer — and the protected-branch sentence is guarded against drift by `scripts/check-protected-set.sh`.
