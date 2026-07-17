---
name: exiting-worktrees
description: "Use when the user explicitly asks to exit, remove, or clean up a worktree after work has landed, or confirms cleanup after a merged PR or branch. Uses native `git worktree` removal (with Claude Code's ExitWorktree as an optimization when available), landed-work verification, and user confirmation before removal. Do not use for ordinary git hygiene, branch cleanup alone, manual worktree experiments, unlanded work, or persistent locked satellite worktrees (parked skill workspaces — `worktree-task-cycle` where available)."
---

# Exiting Worktrees

Safe worktree exit with verification. Prevents data loss from manual cleanup.

## Removing a Worktree

The baseline removal path is native `git worktree`, which works in every runtime. The Claude Code `ExitWorktree` built-in is an **optimization layered on top** — prefer it when it is available, but the native path below is the contract and must carry every guard.

### Native baseline (all runtimes)

Run removal from the **main repo directory**, never from inside the worktree — running `git worktree remove` from inside the worktree invalidates the shell CWD and every later command fails with "Path does not exist."

```bash
# 0. Resolve <main-repo-path>. From inside a worktree, `git rev-parse --show-toplevel`
#    returns the WORKTREE path, not main; the first `worktree` entry of the porcelain
#    list is always the main checkout:
git worktree list --porcelain | awk '/^worktree /{print $2; exit}'
# 1. Remove the worktree from the main repo (the -C flag never changes your shell CWD):
git -C <main-repo-path> worktree remove <worktree-path>
# 2. Delete the branch from the main repo:
git -C <main-repo-path> branch -d <branch-name>
```

Reuse the `<main-repo-path>` resolved in step 0 for every `git -C` command. This native path is the only acceptable removal mechanism when `ExitWorktree` is unavailable or was a no-op.

### ExitWorktree optimization (Claude Code only)

When the Claude Code `ExitWorktree` built-in is available (deferred — fetch its schema via `ToolSearch` before first use), prefer it: it removes the worktree and restores the session to the original working directory (the directory before `EnterWorktree`) in a single atomic operation, so you are never stranded in a deleted path.

- `action` (required): `"remove"` (delete worktree + branch) or `"keep"` (leave both intact).
- `discard_changes` (optional, default false): with `action: "remove"`, forces removal even with uncommitted files or unmerged commits. The tool refuses without this flag if the worktree has unsaved state.

**Scope:** `ExitWorktree` only operates on a worktree that `EnterWorktree` created in the *current* session. For a worktree created manually (`git worktree add`), in a previous session, or via `claude --worktree`, it is a guaranteed **no-op** ("no worktree session is active") — calling it is harmless, but then fall back to the native baseline above, run from the main repo directory.

**Branch cleanup:** `ExitWorktree` may not delete the branch (notably with `discard_changes: true`); Exit Procedure step 3 verifies this and deletes any survivor.

## Pre-Exit Checklist

Run these checks in order. Stop and resolve any that fail.

### 1. Confirm you're in a worktree

```bash
git worktree list
git worktree list --porcelain   # shows lock state and the lock reason
```

If only one entry (the main repo), you're not in a worktree — nothing to exit.

If the porcelain listing shows the worktree as `locked` with a parked-skill-workspace reason, stop: it is a permanent satellite, parked between tasks — not removed through this skill. Route to `worktree-task-cycle` where available; satellite retirement happens only on the user's explicit instruction through the owning repo's procedure.

### 2. Check for uncommitted changes

```bash
git status --short
```

If uncommitted changes exist, ask the user:
> "There are uncommitted changes in the worktree. Commit them before exiting, or discard?"

Do NOT proceed until the user decides. Commit if requested, or note they'll be discarded.

### 3. Check for unpushed commits

First check whether the branch has an upstream. Without one, `@{upstream}` is undefined and `git log @{upstream}..` errors out to *empty* — which looks identical to "nothing unpushed" and would wrongly suggest the work is safely pushed:

```bash
git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null
```

- **Nothing printed (no upstream):** the branch was never pushed. Do NOT read this as "all pushed" — treat every commit as unpushed. List them against the base branch (e.g. `git log main.. --oneline`) and handle as the "If no PR" case below.
- **An upstream printed:** list commits not yet on it:

  ```bash
  git log @{upstream}.. --oneline
  ```

If unpushed commits exist:
- **If a PR was squash-merged:** Unpushed commits are expected — the squash commit on main contains the work. Confirm with the user: "The PR was squash-merged, so these local commits are already represented on main. OK to proceed?"
- **If no PR:** Ask whether to push first.

### 4. Verify the branch's work is merged

This check depends on how the work was integrated:

**If a PR exists:**
```bash
gh pr list --head <branch-name> --state merged --json number,title --jq '.[0]'
```
A merged PR means the work is on main (via squash or merge commit). The branch itself won't appear in `git branch --merged main` after a squash merge — that's expected and not a problem.

**If merged locally (no PR):**
```bash
git log main --oneline -5
```
Verify the merge commit or the branch's commits appear on main.

**If work needs to be merged now (no PR, not yet on main):**

You cannot `git checkout main` from inside a worktree — main is already checked out in the main worktree. Git prevents two worktrees from having the same branch checked out. This is also why you cannot hand this case to `merge-branch`: it lands by switching to the target, and it deliberately refuses when the target is checked out in another worktree (which it always is here). So carry its guards inline — verify the target, require fast-forward ancestry — and merge from the main repo with `git -C`:

```bash
# 1. Confirm the main repo has the INTENDED target checked out.
#    `git -C <path> merge` merges into whatever is checked out THERE — not
#    necessarily main — so verify before trusting the "already on main" claim.
git -C <main-repo-path> rev-parse --abbrev-ref HEAD   # must be the target (e.g. main)
# 2. Fast-forward-only merge of the worktree branch into that verified target.
git -C <main-repo-path> merge --ff-only <branch-name>
# 3. Verify
git -C <main-repo-path> log --oneline -3
```

If step 1 does not show the intended target, stop: the main repo has a different branch checked out, so this merge would silently land on the wrong branch. Settle which branch should receive the work before merging.

If the `--ff-only` merge fails (the branch is not a fast-forward of the target), stop and report — do NOT retry with a plain `git -C <main-repo-path> merge`. A failed `--ff-only` changes nothing (clean tree, no merge in progress), so there is nothing to abort; decide the next step from the main repo — rebase the branch onto the target, or make an explicit merge there. Never do this from inside the worktree — you cannot check out the target branch there. If that rebase or explicit merge conflicts, `resolve-conflicts` owns resolving it and finishing (from the main repo).

After this `--ff-only` merge succeeds into the verified target, `ExitWorktree(action: "remove", discard_changes: true)` is safe — the "discarded" commit is already on the target. The tool reports discarding because the worktree branch's commit is no longer exclusive to it, not because work is lost.

**If neither merged nor mergeable:** Warn the user that exiting will lose work unless they choose to keep the worktree.

### 5. Ensure local main has the changes

First check whether the repo has an `origin` remote. On the no-PR / local-only path (the natural habitat of this flow) there may be none, and an unconditional `git fetch origin` aborts fatally (exit 128, "'origin' does not appear to be a git repository"):

```bash
git remote get-url origin 2>/dev/null
```

- **Nothing printed (no `origin`):** there is no remote to sync against — local main is authoritative for this landing. Skip the fetch and the `origin/main` comparisons, and continue to the Exit Procedure.
- **A URL printed:** compare local main against the remote:

  ```bash
  git fetch origin
  git log main..origin/main --oneline
  git log origin/main..main --oneline
  ```

Three cases:
  - **Local main behind origin:** Pull needed. Run from the main repo (not the worktree): `git -C <main-repo-path> pull origin main`
  - **Local main ahead of origin:** Local commits exist that aren't pushed. This is fine — just note it.
  - **Diverged:** Local main has commits not on origin AND origin has commits not on local. Use `git -C <main-repo-path> pull --rebase origin main` to replay local commits on top of origin.

After syncing, verify:
```bash
git -C <main-repo-path> log --oneline -3
```

## Exit Procedure

After all checks pass:

**1. Confirm with the user:**

> "All changes are on local main. Ready to remove worktree `<name>` and delete the branch. Proceed?"

Wait for explicit confirmation.

**2. Remove the worktree:**

If the Claude Code `ExitWorktree` tool is available, prefer it:

```
ExitWorktree(action: "remove")
```

If it reports uncommitted files or unmerged commits, go back to the checklist — do NOT retry with `discard_changes: true` unless the user explicitly says to discard, or the worktree directory is already gone (broken state from a prior attempt).

If `ExitWorktree` is unavailable (any non-Claude-Code runtime) or returns the no-op "no worktree session is active", run the native baseline from "Removing a Worktree" — from the main repo, never from inside the worktree.

**3. Verify and clean up:**

```bash
git worktree list
git log --oneline -3
git branch --list '<branch-pattern>'
```

Confirm the worktree is gone and main shows the expected history. If the branch survived (common with `discard_changes: true`), delete it: `git branch -d <branch-name>`; after a squash merge `-d` will refuse — use the rule in "Branch Deletion After Squash Merge".

## Prohibited Actions

| Action | Why | Use Instead |
|--------|-----|-------------|
| `git worktree remove` run **from inside the worktree** | Invalidates the shell CWD; later commands fail | `git -C <main-repo-path> worktree remove` from the main repo (or `ExitWorktree`) |
| `git branch -D` (force delete) without merge proof | Silently deletes unmerged work | `git branch -d` first; `-D` only after confirmed squash merge (see below) |
| `rm -rf` on worktree directory | Leaves orphaned git metadata | `ExitWorktree` tool |
| `discard_changes: true` as first attempt | Masks unresolved issues | Run checklist first, resolve issues |
| Proceeding without user confirmation | Risk of data loss | Always confirm before removing |

### Branch Deletion After Squash Merge

`ExitWorktree` handles branch deletion automatically. But if branch cleanup falls through (e.g., `ExitWorktree` was a no-op for a manually-created worktree, or `action: "keep"` was used), you may need to delete the branch manually.

**First, make sure the worktree is already removed.** A branch checked out in a live worktree cannot be deleted — both `git branch -d` and `-D` fail with "cannot delete branch '<x>' used by worktree at '<path>'". This is the usual state after an `ExitWorktree` no-op (see Scope): remove the worktree via the native baseline first, *then* delete the branch.

After a squash merge, `git branch -d` fails because git doesn't recognize the squash commit as merging the branch (the SHAs differ). This is the one case where `-D` is acceptable:

1. Confirm the PR was merged: `gh pr list --head <branch> --state merged`
2. Confirm the worktree holding the branch is already removed (above).
3. Try safe delete: `git branch -d <branch>`
4. If `-d` fails with "not fully merged" AND step 1 confirmed the PR is merged: `git branch -D <branch>` is safe — the PR merge serves as proof the work landed.

Do NOT use `-D` without first confirming the merge via `gh pr list`. The PR confirmation is what makes `-D` safe, not the failure of `-d`. A `-d`/`-D` failure that says "used by worktree" is not a merge-proof problem — the worktree still exists; remove it first.

## Edge Cases

Situations the checklist and procedure sections already own (squash-merged "unmerged" branches, diverged main, not-yet-landed work, surviving branches) are handled there; this table carries only the cases with no owning step.

| Situation | Action |
|-----------|--------|
| Worktree directory already gone (broken state) | `ExitWorktree(action: "remove", discard_changes: true)` — handles orphaned metadata. |
| Multiple worktrees exist | Only exit the one being discussed. Don't touch others. |
| Remote branch already deleted by PR merge | Normal — GitHub deletes the remote branch on merge. Local branch cleanup still needed. |
| Worktree created in a previous session or manually | `ExitWorktree` no-ops (current-session `EnterWorktree` worktrees only — see Scope); use the native baseline. |

## Integration

This skill only *exits* worktrees; it does not create them. Worktrees are created by the `EnterWorktree` tool (see "Removing a Worktree" above). Landing the work is normally decided by the flow you used before exiting — a local fast-forward via `merge-branch`, or a merged PR — and this skill then runs afterward to verify and remove. The exception is the not-yet-landed case (Pre-Exit Checklist step 4): there this skill carries the local merge inline with `merge-branch`'s guards (verified target, fast-forward only), because `merge-branch` cannot run against a target checked out in another worktree.

**Typical sequence:**
1. Land the branch — a local fast-forward (`merge-branch`), or a PR that gets merged.
2. **This skill activates** → sync main, confirm, ExitWorktree, verify.
