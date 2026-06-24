# Git Cycle

Get local work safely from a dirty working tree to merged-and-shared. Seven skills covering one arc:

- `git-hygiene` — audit and clean local git state; shape commits by concern; prune branches.
- `closeout-check` — decide whether work is truly done and create the final local commit.
- `merge-branch` — fast-forward-land a completed branch into a verified target, locally.
- `exiting-worktrees` — verify work landed, then remove the worktree safely (native `git worktree`, with Claude Code's `ExitWorktree` as an optimization).
- `pr-description` — author a reviewer-oriented PR title and body from the diff, the intent, and the real verification record; open or update the PR only on explicit authority.
- `gh-address-comments` — verify, classify, and fix PR review threads locally; stop at one commit.
- `gh-pr-review-loop` — the full publish lifecycle on top of `gh-address-comments` (explicit-invoke).

Shared safety conventions (the protected-branch set, in-progress-operation markers, fast-forward landing discipline) are kept inline in each skill — never behind a conditionally-loaded pointer — and the protected-branch sentence is guarded against drift by `scripts/check-protected-set.sh`.
