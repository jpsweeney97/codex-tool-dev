---
name: exiting-worktrees
description: "Use when the user explicitly asks to exit, remove, or clean up a worktree after work has landed, or confirms cleanup after a merged PR or branch. Removes the worktree and its branch after checking that the work landed. Do not use for ordinary git hygiene, branch cleanup alone, manual worktree experiments, unlanded work, or persistent locked satellite worktrees (parked skill workspaces — `worktree-task-cycle` where available)."
---

# Exiting Worktrees

Remove a worktree and its branch once the branch's work has landed. The user's request to exit is the approval to remove; ask again only before discarding work.

## Stops

- **Parked satellite.** If `git worktree list --porcelain` shows the worktree as `locked` with a parked-skill-workspace reason, stop: it is a permanent satellite, parked between tasks, and is not removed through this skill. Route to `worktree-task-cycle` where available; satellite retirement happens only on the user's explicit instruction through the owning repo's procedure.
- **Uncommitted changes.** Ask whether to commit or discard them, and wait for the answer.
- **Work not landed.** Check that the branch's commits are on the target branch, or that its PR merged (`gh pr list --head <branch> --state merged`; after a squash merge the branch looks unmerged, which is expected). A branch with no upstream has pushed nothing, so treat every commit on it as unpushed. If the work still needs landing, land it first (`merge-branch`). If it is neither landed nor mergeable, say that removal loses it and let the user choose.

Do not fetch, pull, or rebase the target branch here.

## Removing

- Run removal from the main checkout, never from inside the worktree: `git worktree remove` run from inside leaves the shell in a deleted directory. The first `worktree` entry of `git worktree list --porcelain` is the main checkout.

  ```bash
  git -C <main-repo-path> worktree remove <worktree-path>
  git -C <main-repo-path> branch -d <branch-name>
  ```

- In Claude Code, prefer the `ExitWorktree` tool when it applies (it is deferred: fetch its schema with `ToolSearch` first). It removes the worktree and returns the session to the directory it was in before `EnterWorktree`.
  - `action` (required): `"remove"` (delete worktree and branch) or `"keep"` (leave both intact).
  - `discard_changes` (optional, default false): with `action: "remove"`, forces removal despite uncommitted files or unmerged commits. Use it only when the user said to discard, when the commits are already on the target, or when the worktree directory is already gone.
  - Scope: it acts only on a worktree that `EnterWorktree` created in the current session. For a worktree created manually, in an earlier session, or with `claude --worktree`, it is a no-op ("no worktree session is active"); use the git commands above.
  - It may leave the branch behind. Delete a surviving branch with `git branch -d`.
- Use `git branch -D` only after a squash merge, when `-d` refuses and `gh pr list --head <branch> --state merged` confirms the PR merged. The merged PR is the proof, not the refusal. A "used by worktree" refusal means the worktree still exists: remove it first.
- Never `rm -rf` a worktree directory: it leaves orphaned git metadata.

After removal, show `git worktree list` and confirm the worktree and the branch are gone.
