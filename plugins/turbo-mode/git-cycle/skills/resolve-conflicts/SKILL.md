---
name: resolve-conflicts
description: "Use when a git merge, rebase, cherry-pick, or revert is in progress and has left conflicts you need to resolve faithfully and then finish. Do not use for clean fast-forward landing (merge-branch), driving lint or tests back to green after a change with no conflict (keep-green), worktree removal (exiting-worktrees), or general local git cleanup (git-hygiene)."
---

# Resolve Conflicts

Resolve an in-progress merge or rebase conflict faithfully, then finish the operation.

Default behavior: reconstruct each side's intent before touching a hunk, preserve both intents where they can coexist, run the project's checks, and complete the operation — never resolve by discarding a side you did not understand. Higher-priority user, repo, and safety instructions override this skill.

## Use This Skill

- A merge, rebase, cherry-pick, or revert is in progress and has left conflict markers: `git status` shows "Unmerged paths", or a `git merge` / `git rebase` / `git cherry-pick` just stopped on a conflict.
- You need to resolve the conflicting hunks and complete the operation — commit the merge, or continue the rebase to the end.

## Do Not Use

Each of these is a sibling's job, not this one:

- **Clean fast-forward landing of a completed branch** → `merge-branch`. It is fast-forward-only and stops the moment a real (non-ff) merge or rebase is needed — this skill is where that resolution happens.
- **Lint or tests are red after a change you made, with no conflict involved** → `keep-green`.
- **Removing a worktree after work has landed** → `exiting-worktrees`.
- **General local git cleanup** — untracked files, commit shaping, stale branches → `git-hygiene`, which refuses to run during an in-progress operation anyway.

## Procedure

### 1. See the current state

Identify which operation is in progress, its stated goal, and every conflicting file before editing anything.

```bash
git status --short --branch
git rev-parse --git-dir        # then look for MERGE_HEAD, rebase-merge/, rebase-apply/, CHERRY_PICK_HEAD, REVERT_HEAD
git diff --name-only --diff-filter=U   # the unmerged (conflicting) files
git log --oneline --decorate -5
```

Name the operation's goal in one line — what is being merged or replayed onto what, and why. Every hunk decision below serves that goal. For a rebase, remember the sides are swapped: "ours" is the branch you are replaying onto, "theirs" is the commit being replayed.

### 2. Reconstruct each side's intent

For each conflicting hunk, understand *why* each side made its change before deciding — do not resolve from the diff shape alone.

- Read the commit messages behind both sides.
- Where the tracker or PRs are reachable, check the issue or PR that motivated each change.
- If a side's intent is genuinely unclear and the choice is consequential, stop and ask rather than guessing.

### 3. Resolve each hunk

- **Preserve both intents where they can coexist.** Most conflicts are two independent changes touching adjacent lines — keep both.
- **Where they genuinely conflict, pick the side matching the operation's stated goal (step 1) and note the trade-off** in your summary, so the dropped intent is visible, not silently lost.
- **Never invent behavior neither side had** to paper over a hard hunk.
- Resolve the conflict rather than `--abort`-ing to escape the work. Aborting abandons the whole operation — take it only if the user asks or the operation itself was a mistake, never as a shortcut around a difficult hunk.

Remove every conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`) and stage each file as you finish it.

### 4. Run the project's checks

Discover the project's automated checks and run them — typically typecheck, then tests, then format — and fix anything the merge broke. A conflict that resolves cleanly on the page can still break behavior.

```bash
git diff --check   # no leftover conflict markers or whitespace errors
# then the project's own gate, e.g. typecheck → tests → format
```

If repairing merge-broken checks turns into an unbounded fix→re-run loop, hand that loop to `keep-green` (bounded anti-thrash), then return here to finish. Never reach green by deleting or loosening a test to dodge a real regression the merge exposed.

### 5. Finish the operation

Complete the in-progress operation — do not leave the repo mid-merge.

- **Merge / cherry-pick / revert:** stage everything resolved, then commit. A bare `git commit` preserves the prepared merge message — keep it.
- **Rebase:** `git rebase --continue`, then repeat steps 1–4 for each subsequent commit that conflicts until the rebase completes.

Before committing, check where the commit lands: if completing the operation would put a commit directly on a protected branch (mid-merge on `main`, or a rebase whose result lands on a protected branch), surface that and confirm before proceeding rather than committing silently. Treat repo-defined protected branches first; if the repo defines none, treat `main`, `master`, `develop`, and `release/*` as protected.

Confirm the end state:

```bash
git status --short --branch   # no "Unmerged paths", no operation in progress
git log --oneline --decorate -3
```

Report one concise result line: what was merged or rebased, any trade-off where a side's intent was dropped, and the check result.
