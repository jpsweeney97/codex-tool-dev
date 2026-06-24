---
name: git-hygiene
description: "Use when the user asks to audit or clean local git repository state, including untracked files, mixed changes, commit shaping, stale branch pruning, or lane-based cleanup. Do not use during active rebase/merge/cherry-pick/bisect, for submodule edits, pushes, PR workflows, implementation, or ordinary status orientation."
---

# Git Hygiene

Default to `audit`. Separate cleanup by lane, preview before mutation, and execute only approved lanes. Higher-priority system, user, and repo instructions override this skill.

Read [`references/git-hygiene-reference.md`](references/git-hygiene-reference.md) for command shapes, full preview/report templates, config details, examples, and anti-patterns.

## Core Rules

- One repository at a time; submodules are read-only.
- If scope, file classification, or branch safety is ambiguous, no-op and ask.
- Never commit onto the default branch or a protected branch. The default branch is always protected; resolve the *protected* set repo-defined first, where "repo-defined" means the configured `branchProtection` policy — not the mere existence of a default branch. Treat repo-defined protected branches first; if the repo defines none, treat `main`, `master`, `develop`, and `release/*` as protected. Before any `commit-shaping` or `commit-only` commit, create a working branch (`chore/`, `fix/`, or `feature/`) when the checked-out branch is the default branch or is protected under that resolution; reuse the branch and default branch already captured in preflight.
- Never skip preview, even when the user says "just do it."
- Never use `rm` or `git clean -fd`; use `trash` only after explicit approval.
- Never delete protected files from batch approval alone.
- Never push, open PRs, rewrite history, or modify submodules.
- Stop on failure; report succeeded, failed, and unattempted work.

## Modes

- `audit`: analyze and propose a lane plan; mutate nothing.
- `apply-safe`: run approved `.gitignore`, commit-shaping, remote-prune, or config work.
- `apply-destructive`: after final confirmation, run only approved `trash` or local branch deletion.
- `commit-only`: stage and commit only approved semantic groups.
- `remote-prune-only`: prune only approved remote-tracking refs.
- `local-branch-delete-only`: delete only approved local branches.

Do not create a cleanup branch for audit-only, no-op, remote-prune-only, or local-branch-delete-only runs. For "everything" after audit, run `apply-safe`, then pause for destructive confirmation.

## Preflight

Before audit or execution, confirm repo root, branch, default branch, remotes, and worktrees; abort on any in-progress git operation (rebase, merge, cherry-pick, revert, or bisect); count file and branch scope; ask before full analysis above 100 changed/untracked files or 50 local branches; warn on shallow clones; load valid repo-root `.git-hygiene.json` only.

## Lanes and Gates

- `untracked-and-ignore`: classify untracked files as `ignore candidate`, `track candidate`, `ask`, or `protected`.
- `commit-shaping`: group staged and unstaged changes by concern with Conventional Commits messages.
- `branch-pruning`: keep `remote-prune` separate from destructive `local-branch-delete`; a `[gone]` upstream marks a deletion candidate, never merge proof.
- `config-learning`: propose `.git-hygiene.json` updates only after the user approves the pattern.

Collect approvals lane by lane. `ask` files require `track`, `ignore`, `delete`, or `leave`. Protected deletion requires explicit per-file confirmation naming the protection reason. If a decision changes a lane materially, regenerate that preview and reconfirm.

## Execution and Report

- `apply-safe`: resolve dependencies, branch only for worktree edits or commits, commit `.gitignore` first, then approved groups, remote prune, and config.
- `apply-destructive`: require final confirmation, `trash` approved files, delete only unprotected, unused approved branches that are merged or `[gone]` with confirmed landed proof (see the reference's `-D` rule); do not stage or commit deletions.
- `commit-only`: confirm file decisions are settled, branch first when on the default/protected branch or when isolation is needed, then stage and commit approved groups.

Verify only executed lanes: `git status` after worktree or commit changes, `git log <original>..HEAD` after commits, and ref checks after pruning or branch deletion.

Before previews and final lane reports, include `Decision Summary`:

- `Safe to apply now`: approved non-destructive lanes, or `None`.
- `Needs explicit choice`: files, groups, or refs needing a user decision.
- `Destructive and blocked`: trash or local branch deletion waiting on final confirmation.
- `Recommended next command`: the smallest next mode or command to run.

`Decision Summary` is not approval. Continue to require lane-by-lane approvals, per-file decisions for `ask` files, and explicit per-file confirmation for protected deletion.

End with mode or partial status, cleanup branch or `none`, lane results, intentional dirty state, and recommended next step.
