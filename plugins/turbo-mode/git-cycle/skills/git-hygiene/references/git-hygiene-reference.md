# Git Hygiene Reference

Load this file when exact command shape, preview format, `.git-hygiene.json`, or examples matter.

## Commands

Preflight:

```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
git branch --show-current
git status --short --branch --untracked-files=all
git remote -v
git worktree list --porcelain
git branch --list
git rev-parse --is-shallow-repository
```

Use the git directory from `git rev-parse --git-dir` to inspect rebase, merge, cherry-pick, revert, and bisect markers. Use `git status --porcelain=v1 --untracked-files=all` for counts. Preview stale remote refs with `git remote prune <remote> --dry-run`.

Branch checks:

```bash
git symbolic-ref --quiet --short refs/remotes/origin/HEAD
git branch --merged <default-branch>
git branch --no-merged <default-branch>
git branch -vv
git worktree list --porcelain
```

A `[gone]` upstream in `git branch -vv` marks a branch whose remote was
deleted — a deletion candidate for the `local-branch-delete` lane, never merge
proof. The marker surfaces only after remote-tracking refs are pruned; in
audit, pair it with the `remote prune --dry-run` preview to catch candidates
the marker has not reached yet.

Safe execution:

```bash
git switch -c chore/cleanup/YYYY-MM-DD-HHMMSS
git add .gitignore
git commit -m "chore: update ignore rules"
git add <approved-paths>
git commit -m "<approved-message>"
git remote prune <remote>
```

Destructive execution, only after approval:

```bash
trash <approved-file>
git branch -d <approved-branch>
```

Use `git branch -d`, not `-D`, unless the user separately requests force deletion and the safety case is clear. One exception is provable: after a squash merge, `-d` fails even though the work landed. `-D` is then acceptable only after confirming the landed work — a merged PR via `gh pr list --head <branch> --state merged`, or the equivalent commits on the default branch. The confirmation makes `-D` safe, never the `-d` failure alone.

## Preview Template

```text
Mode: audit

Decision Summary:
  Safe to apply now: none
  Needs explicit choice: notes.md - track, ignore, delete, or leave
  Destructive and blocked: tmp/debug.log - needs final trash confirmation
  Recommended next command: apply-safe after lane approvals

Lane: untracked-and-ignore
  .gitignore additions:
    + *.pyc
  Files to delete with trash:
    - tmp/debug.log
  Unknown files:
    ? notes.md - track, ignore, delete, or leave
  Protected files:
    ! credentials.local.json - delete only with explicit per-file confirmation

Lane: commit-shaping
  1. chore: update .gitignore with Python artifacts
  2. fix(auth): validate token expiration before refresh

Lane: branch-pruning
  Remote tracking to prune:
    - origin/feature/deleted-upstream
  Local branches to delete:
    - feature/old-experiment (merged)
    - fix/login-timeout ([gone], squash-merged PR #41 - `-D` only after the PR check)

Lane: config-learning
  Proposed saved patterns:
    + ignorePatterns: ["*.pyc"]
```

Decision Summary is a readable index, not consent. Shorten the preview under
time pressure, but still show every lane with pending decisions and collect
approvals lane by lane.

## Final Report Shape

```text
Mode completed: apply-safe
Cleanup branch: chore/cleanup/2026-03-20-143052
Decision Summary:
  Safe to apply now: none
  Needs explicit choice: none
  Destructive and blocked: approved trash deletions still need apply-destructive confirmation
  Recommended next command: apply-destructive for approved deletions
Lane results:
  commit-shaping:
    commits created: 2
Recommended next step:
  apply-destructive for approved deletions
```

Use `Cleanup branch: none` when no branch was created. For partial execution, list completed work, failed operation, and unattempted work.

## Config

Read `.git-hygiene.json` only from repo root. If malformed, report and ignore it for this run.

Fields:

- `ignorePatterns`: candidate `.gitignore` additions, not silent file deletion.
- `protectedPatterns`: extra patterns that require per-file deletion approval.
- `groupingHints`: path prefixes to concern labels for commit grouping.
- `branchProtection`: branch names or globs never proposed for deletion, and the repo-defined protected set used to gate commit creation — `commit-shaping`/`commit-only` branch first rather than commit onto a protected or default branch.
- `defaultCommitPrefix`: Conventional Commits type for ambiguous real changes.

Config rules can strengthen safety rules, never weaken them.

## Example and Anti-patterns

Example flow: audit, present lanes, collect approvals, execute `apply-safe`, pause before `apply-destructive`, report lane results.

| Anti-pattern | Fix |
| ------------ | --- |
| One big cleanup operation | Split by lane. |
| One branch-cleanup approval for remote and local deletion | Approve separately. |
| `git add .` plus one cleanup commit | Propose semantic groups first. |
| `git clean -fd` | Preview first; use `trash` only for approved files. |
| Treating "quickly" as consent | Shorten preview; do not skip it. |
| Mixing `.gitignore` with code changes | Commit ignore rules separately and first. |
| Branch deletion without worktree checks | Check worktrees first. |
| Treating `[gone]` as merge proof | Confirm landed work (merged PR) before `-D`. |
