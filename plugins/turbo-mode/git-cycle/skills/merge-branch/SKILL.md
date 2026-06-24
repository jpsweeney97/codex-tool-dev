---
name: merge-branch
description: "Use when the user explicitly asks to locally land or merge a completed non-protected git branch into a verified base/default branch. Do not use for PRs, pushes, remote merges, status checks, branch cleanup alone, ambiguous done phrasing, protected branches, active git operations, or unclear merge targets."
---

# Merge Branch

Local fast path for landing a completed branch without a PR or push.

Default behavior: commit only relevant pending changes, merge the current branch into the verified target branch, and keep the source branch unless deletion was explicitly requested or confirmed. Higher-priority user, repo, and safety instructions override this skill.

## Use This Skill

- The user explicitly asks to merge or land the current branch locally, such as "merge this branch into main", "land this branch locally", or "commit and merge into develop".
- The current branch is a non-protected work branch.
- The user does not want a PR, remote push, remote merge, or review-only status check.

Branch deletion is a separate cleanup step. Treat "merge and clean up", "delete the branch after merge", or an explicit confirmation after merge as cleanup approval. Otherwise, merge and retain the source branch.

## Do Not Use

- The user asks to push, publish, open a PR, merge a PR, or update a remote.
- The user asks only for status, review, audit, branch cleanup, or git hygiene.
- The current branch is the target branch, a protected branch, or detached HEAD.
- A rebase, merge, cherry-pick, revert, or bisect is in progress.
- The merge target is unclear after the preflight checks.
- Pending changes include unrelated or ambiguous user work.
- The source branch is checked out in another worktree.

## Procedure

### 1. Preflight

Identify the repo, source branch, target branch, operation state, dirty state, and worktree ownership before mutating anything.

```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
git branch --show-current
git status --short --branch --untracked-files=all
git diff --stat
git diff --staged --stat
git log --oneline --decorate -5
git worktree list --porcelain
git symbolic-ref --quiet --short refs/remotes/origin/HEAD
```

Use the path from `git rev-parse --git-dir` to check for operation markers such as `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, or `BISECT_LOG`.

Treat repo-defined protected branches first; if the repo defines none, treat `main`, `master`, `develop`, and `release/*` as protected.

Stop if any precondition fails:

- Current branch is empty, detached, protected, or already the target branch.
- A git operation is in progress.
- The source branch is checked out in another worktree.
- The target branch cannot be determined confidently.
- The working tree contains unrelated or ambiguous changes.

### 2. Determine The Target Branch

Use this authority order:

1. Explicit target branch named by the user.
2. Repo instructions or branch policy in `AGENTS.md` or `CLAUDE.md`.
3. Default branch from `refs/remotes/origin/HEAD`, stripping the remote prefix.
4. A single obvious local default branch: `main`, `master`, or `develop`.

If multiple candidates remain, ask the user which branch to merge into. Do not default to `main` just because it exists. If `origin/HEAD` is missing, fall through to local default detection. Do not fetch or change remotes unless the user explicitly asks.

Before merging, verify the target branch exists locally. If it does not, stop and report the missing branch rather than fetching or creating it unless the user explicitly asked for that.

Also confirm the target branch is not checked out in another worktree (inspect the `git worktree list --porcelain` output from preflight). If it is, `git switch <target-branch>` in Step 4 will fail — stop now and report that the target is checked out elsewhere. Checking this before Step 3 means you do not commit work to the source branch only to discover you cannot land it.

For this fast path, require the target to be an ancestor of the source branch:

```bash
git merge-base --is-ancestor <target-branch> <source-branch>
```

If this fails, stop and explain that a non-fast-forward merge or rebase decision is needed.

### 3. Commit Relevant Changes

If the worktree has staged, unstaged, or untracked changes:

1. Inspect the changed paths and relevant diffs.
2. Classify each path as part of the branch work, unrelated user work, generated local artifact, or unclear.
3. Stop if any path is unrelated or unclear. Ask for a file decision instead of staging broadly.
4. Stage only approved branch-work paths. Prefer exact pathspecs over `git add -A`.
5. Draft a commit message from the diff and match the repo's commit style.
6. Commit after reviewing the staged diff.

If there are no pending changes and the branch already contains the intended work in commits, continue to merge.

### 4. Merge

Now that Step 3 has committed the branch work, require the source to be strictly ahead of the target — at least one commit to land:

```bash
git rev-list --count <target-branch>..<source-branch>
```

If the count is `0`, the source has no commits the target lacks (identical refs, or work already landed). Stop with "Nothing to merge: `<source>` has no commits ahead of `<target>`." Do not switch, merge, report success, or delete the branch: a `git merge --ff-only` here prints "Already up to date" and exits 0, which would otherwise read as a successful landing.

Then confirm the worktree is clean — no staged or unstaged tracked changes:

```bash
git status --porcelain
```

If this shows any staged or unstaged tracked entry (any line not prefixed `??`), stop and report the dirty tree rather than switching: `git switch` does not fail on a dirty tree and silently carries staged changes onto the target branch. Untracked files (`??`) that Step 3 already classified as approved generated artifacts are acceptable and may remain; any other dirty state is a stop.

Switch to the verified target branch and fast-forward merge the source:

```bash
git switch <target-branch>
git merge --ff-only <source-branch>
```

If `git switch <target-branch>` fails (for example, the target is checked out in another worktree), stop before merging: any commit you made in Step 3 is safe and intact on the source branch — it is simply not yet landed. Report that and the unblock needed.

If the fast-forward merge fails, stop. Report that the branch was not merged and name the next decision: rebase the source, perform an explicit merge commit, or abort the local landing. As above, the Step 3 commit remains intact on the source branch; nothing is lost.

Once the merge succeeds, confirm the source's commits actually landed on the target — while the source ref still exists, before any cleanup:

```bash
git merge-base --is-ancestor <source-branch> <target-branch>
```

This must pass (exit 0): the source is now contained in the target. If it does not, the landing did not happen — stop and report that instead of proceeding to cleanup or a success line.

### 5. Clean Up Source Branch

Delete the source branch only when cleanup approval exists from the original request or a separate user confirmation.

```bash
git branch -d <source-branch>
```

Use `-d`, never `-D`. If deletion fails, leave the branch in place and report the exact failure. Do not force-delete.

### 6. Confirm Result

Show the resulting state (the landing itself was verified at the end of Step 4):

```bash
git status --short --branch
git log --oneline --decorate -3
```

Report one concise result line:

- If the source branch was deleted (cleanup approved and `git branch -d` succeeded): "Merged `<source>` into `<target>` and deleted the source branch."
- If cleanup was approved but deletion failed: "Merged `<source>` into `<target>`; could not delete the source branch — <exact failure>."
- If cleanup was not approved: "Merged `<source>` into `<target>` and kept the source branch."
