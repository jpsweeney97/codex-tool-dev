---
name: git-hygiene
description: "Analyze cluttered git repositories, propose a safe cleanup plan, group mixed changes into coherent commits, and prune stale branches. Use when the user asks to clean up git, tidy a repo, organize mixed uncommitted work, sort untracked files, or prune stale branches. Do not use for merge conflict resolution, active rebase, merge, cherry-pick, or bisect states, submodule modification, or pushing and PR creation."
---

# Git Hygiene

Clean repo clutter without turning cleanup into data loss or unreadable history. Default to an `audit` pass, organize findings into independent lanes, and execute only the lanes the user approved.

## Quick start

- Verify that the current directory is inside a git repository before doing anything else.
- Abort on complex states such as rebase, merge, cherry-pick, or bisect.
- Default to `audit` mode unless the user clearly asked for a specific execution lane.
- Organize findings into 4 lanes:
  - `untracked-and-ignore`
  - `commit-shaping`
  - `branch-pruning`
  - `config-learning`
- Never skip preview, even if the user says "just do it."
- Use `trash` for approved file deletions. Never use `rm` or `git clean -fd`.
- Create the cleanup branch only for modes that modify the working tree or create commits. Do not create one for audit-only, remote-prune-only, local-branch-delete-only, or no-op runs.
- Do not push, open PRs, rewrite history, or modify submodules.

## Modes

Use one of these modes for each run:

| Mode | Purpose | Mutations allowed |
| ---- | ------- | ----------------- |
| `audit` | Analyze the repo and propose a lane-based plan. This is the default. | None |
| `apply-safe` | Execute approved reversible or low-risk lanes. | `.gitignore` updates, commit shaping, remote-tracking prune, optional config update |
| `apply-destructive` | Execute approved destructive actions. | file deletion with `trash`, local branch deletion |
| `commit-only` | Execute only the approved commit-shaping lane. | staging and commits only |
| `remote-prune-only` | Execute only the safe half of branch pruning. | remote-tracking prune only |
| `local-branch-delete-only` | Execute only approved destructive branch cleanup. | local branch deletion only |

If the user asks for "clean up git" without naming a mode, run `audit`. If the user asks for everything after an audit, execute `apply-safe` first and `apply-destructive` only after an extra confirmation gate.

## Boundaries and defaults

- Work within one repository at a time.
- Treat submodules as read-only. Report their status, but do not stage, clean, or commit inside them.
- Treat unknown files conservatively. Ask instead of guessing.
- Treat protected-pattern files conservatively. Require explicit per-file confirmation before deleting them.
- If analysis finds nothing worth cleaning, report that the repository is already clean and stop.
- Follow repo-specific branch conventions when they are explicit. Otherwise use `codex/cleanup/YYYY-MM-DD-HHMMSS`.

## Preconditions and stop conditions

Abort or pause under these conditions:

- Not inside a git repository: stop and tell the user what directory you checked.
- Rebase, merge, cherry-pick, or bisect in progress: stop and tell the user to finish or abort that operation first.
- Shallow clone detected: warn that branch and merge analysis may be incomplete, then ask whether to continue.
- Large repo detected: if more than 100 changed or untracked files or more than 50 local branches are in scope, ask before continuing with full analysis.

## Workflow

### 1. Preflight

Always do preflight first, regardless of mode.

1. Verify repo context:
   - confirm the repo root
   - detect the current branch or detached HEAD
   - detect the default branch
   - detect worktrees if branch deletion might be proposed later
2. Detect complex state:
   - if rebase, merge, cherry-pick, or bisect is in progress, abort cleanly
3. Check scale:
   - count untracked files
   - count modified, staged, and unstaged files
   - count local branches and stale remote-tracking branches
   - if the repo exceeds the large-repo threshold, pause for confirmation
4. Load optional config:
   - if `.git-hygiene.json` exists at repo root, load and apply it
   - if the file is malformed, report that and ignore it for this run

### 2. Audit

Run audit on the current branch. Do not mutate the repo and do not create the cleanup branch during audit.

Audit produces a structured plan organized into lanes.

#### Lane: `untracked-and-ignore`

Classify each untracked file into exactly one category:

- `ignore candidate`: matches known artifact or editor patterns and should usually become an ignore rule
- `track candidate`: looks like source, config, docs, or test content that probably belongs in version control
- `ask`: ambiguous file that needs a user decision
- `protected`: matches sensitive patterns such as `.env*`, `*.key`, `*.pem`, `credentials.*`, or repo-specific protected patterns

Rules:

- Never auto-delete `ask` or `protected` files.
- Never auto-ignore source-looking files.
- Treat `.gitignore` updates as infrastructure changes that belong in their own commit.
- Separate ignore-rule additions from file deletions in the plan because they have different risk profiles.

#### Lane: `commit-shaping`

Analyze staged and unstaged changes together. Use file paths, diff content, and nearby history to propose semantic groups.

For each proposed group:

- assign a short concern label
- list the files involved
- propose a Conventional Commits message
- mark whether the group is safe to apply without destructive steps
- separate infrastructure changes such as `.gitignore` or formatting-only cleanup from feature or bug-fix work

If the user only wants commit hygiene, this lane can run independently.

#### Lane: `branch-pruning`

Propose candidates in 2 sub-lanes with different risk levels:

- `remote-prune`: remote-tracking branches whose upstream is gone
- `local-branch-delete`: local branches fully merged into the default branch

Before proposing branch deletion:

- check whether the branch is checked out in another worktree
- exclude the current branch, default branch, and repo-protected branches
- keep local branch deletion and remote-tracking prune separate in both preview and approval because the former is destructive and the latter is low risk

#### Lane: `config-learning`

Summarize reusable patterns worth saving to `.git-hygiene.json`, such as:

- ignore patterns the user approved
- protected patterns the user extended
- grouping hints that clearly improved commit shaping
- branch-protection rules the user clarified

Treat this lane as optional. Do not write config changes unless the user approves them.

### 3. Preview

Present the audit output as a lane-based plan. Use this shape:

```text
Mode: audit

Lane: untracked-and-ignore
  .gitignore additions:
    + *.pyc
    + __pycache__/
  Files to delete with trash:
    - tmp/debug.log
  Unknown files:
    ? notes.md - track, ignore, delete, or leave
  Protected files:
    ! credentials.local.json - delete only with explicit per-file confirmation

Lane: commit-shaping
  1. chore: update .gitignore with Python artifacts
  2. fix(auth): validate token expiration before refresh
  3. style(api): apply consistent formatting

Lane: branch-pruning
  Remote tracking to prune:
    - origin/feature/deleted-upstream
  Local branches to delete:
    - feature/old-experiment

Lane: config-learning
  Proposed saved patterns:
    + ignorePatterns: ["*.pyc", "__pycache__/"]
```

If the user says "skip preview" or "just do it," shorten the preview but still show the lane summary and ask for confirmation.

### 4. Collect decisions

Collect approvals lane by lane.

For `untracked-and-ignore`:

- each `ask` file: `track`, `ignore`, `delete`, or `leave`
- each protected file proposed for deletion
- whether ignore-rule changes should be committed now or only proposed

For `commit-shaping`:

- split, merge, reassign, rename, drop, or approve each group

For `branch-pruning`:

- approve local branch deletions separately from remote prune operations

For `config-learning`:

- approve, edit, or decline proposed `.git-hygiene.json` updates

If the user changes any lane materially, regenerate the preview for that lane and reconfirm before execution.

### 5. Lane dependencies

Resolve lane dependencies before choosing an execution mode.

- `untracked-and-ignore -> commit-shaping` when file decisions change which files should be committed, ignored, or deleted.
- `commit-shaping` must run after any approved `.gitignore` commit when both are in scope.
- `remote-prune` is independent of the other lanes and can run on its own.
- `local-branch-delete` is independent of commit shaping, but it still requires destructive approval.
- `config-learning` runs last because it depends on what the user actually approved in the other lanes.

### 6. Execute by mode

#### `audit`

- Do not mutate anything.
- End with the lane-based plan and the recommended next mode.

#### `apply-safe`

Execute only approved non-destructive or lower-risk actions:

1. Resolve lane dependencies first.
2. Create the cleanup branch only if approved safe work will modify the working tree or create commits.
   - Create one for `.gitignore` changes, commit-shaping, or repo-root config changes that the user wants isolated.
   - Do not create one for remote prune alone.
3. Apply `.gitignore` updates and commit them first.
4. Stage and commit approved `commit-shaping` groups.
5. Prune approved remote-tracking branches.
6. Write approved `.git-hygiene.json` updates if the user wanted them.

Do not delete files or local branches in this mode.

#### `apply-destructive`

Require an extra confirmation gate before starting.

Execute only approved destructive actions:

1. Resolve lane dependencies first.
2. Create the cleanup branch only if approved file deletions should be isolated in the working tree.
   - Do not create one for local branch deletion alone.
3. Delete approved files with `trash`.
   - Default: do not stage or commit those deletions in this mode.
   - Leave the deleted files as explicit working-tree changes unless the user later runs `commit-only` or `apply-safe` with an approved commit group that captures them.
4. Delete approved local branches that are safe to delete and not active in any worktree.

Do not smuggle in unrelated safe actions here. This mode is for destructive work only.
Do not create commits or stage deletions in this mode.

#### `commit-only`

1. Resolve lane dependencies first.
2. Confirm that any file decisions from `untracked-and-ignore` that affect commits are already settled.
3. Create the cleanup branch if commit creation should be isolated.
4. Stage each approved change group.
5. Create each approved commit with the approved Conventional Commits message.

Do not modify untracked-file decisions or branch state outside what the commit lane explicitly needs.

#### `remote-prune-only`

1. Prune approved remote-tracking branches.

Do not create a cleanup branch, create commits, or edit `.gitignore` in this mode.

#### `local-branch-delete-only`

Require an extra confirmation gate before starting.

1. Delete approved local branches that passed the worktree and protection checks.

Do not create a cleanup branch, create commits, or edit `.gitignore` in this mode.

### 7. Failure handling

Stop immediately on any failure. Report:

- the current mode
- the lane being executed
- what succeeded
- what failed
- the exact command or operation that failed
- what remains unattempted

Do not guess, continue, or rollback automatically.

## Non-negotiables

- Never skip preview.
- Never delete files without explicit approval.
- Never delete protected files from batch approval alone.
- Never use `rm` or `git clean -fd`; use `trash` for filesystem deletion.
- Never collapse unrelated changes into one "cleanup" commit without first proposing better grouping.
- Never delete branches without checking worktree usage.
- Never create cleanup branches for audit-only or no-op runs.
- Never mix destructive and non-destructive execution behind one vague approval.
- Never treat remote prune approval as approval to delete local branches.

## Decision rules

### Default mode

If the user did not explicitly choose a mode, use `audit`.

### Unknown files

Ask per file: `track`, `ignore`, `delete`, or `leave`. If the user gives a risky batch instruction, restate the affected files before acting.

### Protected file deletion

Require explicit per-file confirmation separate from the main plan approval. Name the matched protection reason in the confirmation line.

### Grouping disagreement

If the user rejects the proposed commit groups, modify the commit-shaping lane and re-present that lane. Do not improvise silently.

### Impatience or pressure

Treat "quickly" as a request for a concise preview, not permission to skip safety or collapse all lanes into one action.

### Destructive actions

If the user approves both safe and destructive lanes together, execute `apply-safe` first and pause for a final destructive confirmation before `apply-destructive`.

## Report format

End with a mode-aware summary in this shape:

```text
Mode completed: apply-safe
Cleanup branch: codex/cleanup/2026-03-20-143052

Lane results:
  untracked-and-ignore:
    .gitignore patterns added: 3
    files deleted with trash: 0
  commit-shaping:
    commits created: 4
      abc1234 chore: update .gitignore with Python artifacts
      def5678 feat(config): add new-feature configuration
  branch-pruning:
    local branches deleted: 0
    remote tracking pruned: 1
  config-learning:
    config updated: no

Recommended next step:
  apply-destructive for approved file or local-branch deletions
```

If no cleanup branch was created, report `Cleanup branch: none`.
If execution stopped early, replace the completion line with a partial-results summary and list what remains unfinished.

## Verification

After execution:

- run `git status` only for modes that changed the working tree or created commits
- expect a clean working tree after `apply-safe` or `commit-only` unless the user explicitly chose to leave files uncommitted
- expect a dirty working tree after `apply-destructive` when file deletions were performed without a follow-up commit; report that state as intentional
- check `git log --oneline <original>..HEAD` when commits were created
- verify only the lane outputs that were actually executed

Examples:

- `commit-shaping` executed: verify created commits
- `remote-prune-only` executed: verify approved remote-tracking refs are gone
- `local-branch-delete-only` executed: verify approved local branches are gone
- `untracked-and-ignore` executed destructively: verify deleted files are gone and note whether the resulting worktree changes are intentionally uncommitted

If verification fails, report the mismatch instead of assuming success.

## Anti-patterns

| Pattern | Problem | Fix |
| ------- | ------- | --- |
| Treating all hygiene work as one big operation | It couples unrelated risks and makes approval too broad. | Split the plan into lanes and execute only approved lanes. |
| Using one branch-cleanup approval for both remote prune and local deletion | It blurs low-risk and destructive work. | Approve `remote-prune` and `local-branch-delete` separately. |
| Running `git add .` and making one cleanup commit | It destroys commit coherence and makes history harder to review, revert, or cherry-pick. | Propose semantic groups first. |
| Running `git clean -fd` because the repo looks messy | It turns cleanup into irreversible deletion. | Preview first and use `trash` only for explicitly approved files. |
| Treating user impatience as informed consent | "Just do it" does not waive safety requirements. | Keep the preview concise, but do not skip it. |
| Mixing `.gitignore` changes with code changes | It muddies history and makes review harder. | Commit `.gitignore` changes separately and first. |
| Deleting branches without a worktree check | A branch may be active elsewhere. | Check worktrees before proposing deletion. |
| Creating a cleanup branch before confirming there is real work | It leaves no-op branches behind. | Audit first, branch later. |

## Example

**User:** "Clean up this repo. I have random untracked files, mixed auth work, and old merged branches."

1. Run `audit`.
2. Present the plan by lane:
   - `untracked-and-ignore`
   - `commit-shaping`
   - `branch-pruning`
   - `config-learning`
3. Collect approvals per lane and resolve dependencies.
4. Execute `apply-safe` for approved `.gitignore`, commit-shaping, remote prune, and config updates.
5. Pause for a final confirmation before `apply-destructive` if approved file deletions or local branch deletions remain.
6. Report lane-by-lane results and the next recommended mode.

## Reference

Read [`references/git-hygiene-config.md`](references/git-hygiene-config.md) when:

- `.git-hygiene.json` exists and you need to interpret it
- the user wants to customize ignore, protection, or grouping behavior
- branch-protection or commit-prefix defaults need explanation
