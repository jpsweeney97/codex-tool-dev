---
name: load-handoff
description: "Use when continuing from a previous session, when the user runs `/load` or `$load`, or when the user gives `/load` with a named path to load the latest or named Markdown handoff as read-only resume context. Do not use for saving, searching, editing, archiving, deleting, or treating handoffs as current truth without a live-state check."
---

# Load Handoff

Load an existing Markdown handoff as strictly read-only context. The handoff is a resume pointer, not current truth.

This skill never archives, moves, copies, edits, deletes, marks consumed, writes state, or creates recovery metadata.

## Use

- Use for `/load` or `$load`, `/load <path>`, "continue from where we left off", or "pick up the latest handoff."
- If no handoff exists, report that plainly. Suggest `/save` (or `$save`) only if there is current context worth preserving.
- If a provided path does not exist, report `Handoff not found at <path>` and stop.

## Selection

Default search scope for implicit `/load`:

```text
<project_root>/.agents/handoffs/
<project_root>/.claude/handoffs/   (legacy, read-only)
<project_root>/.codex/handoffs/    (legacy, read-only)
```

`.agents/handoffs/` is the shared primary location. The legacy directories stay in the implicit scope so older handoffs remain loadable, but nothing is ever written, moved, or migrated there.

`THROUGHLINE.md` in a handoffs directory is the derived arc document maintained by `/throughline` (or `$throughline`), not a session handoff. Never select it as the implicit handoff, even when file modification time would make it the newest entry.

Project root resolution:

1. Use the main working tree of the repository when the current directory is inside a git repository: the first path listed by `git worktree list`. This equals `git rev-parse --show-toplevel` except inside a linked worktree, where the main tree is used so all worktrees of one repository share one handoff location. If the first listed entry is a bare repository, use `git rev-parse --show-toplevel` instead.
2. Otherwise use the current working directory.

For implicit `/load`, first determine the current branch when inside a git repository. Then choose the newest handoff whose frontmatter `branch` matches the current branch when both values are available. If no branch-matching handoff exists, choose the newest handoff overall.

Newest means comparing the parsed timestamp portion of the basename, never raw string order; candidates are `YYYY-MM-DD_*`-shaped `.md` files. Among timestamp-tied names, prefer the highest collision suffix (`-2`, `-3` — written last), then file modification time. File modification time is also the fallback when filenames do not carry a usable timestamp.

When the branch-matched selection is not the newest handoff overall, name the newer non-matching handoff and its branch in the `Reality check` section so the user can redirect with `/load <path>`.

This is deterministic selection, not semantic ranking or an index.

For explicit `/load <path>`, read exactly that path if it exists. Read a path outside the default scope, such as `docs/handoffs/` or an archive directory, only when the user explicitly provides that path.

If the explicit path is a `THROUGHLINE.md`, do not apply resume-pointer framing or either reply form below. Reply briefly that it is the derived arc document, not a session handoff — read it directly or refresh it with `/throughline` — and stop.

## Live-Reality Check

After reading the handoff, run a live-reality check before treating it as actionable.

Inside a git repository, run:

```bash
git branch --show-current
git log -1 --oneline
git status --short --branch --untracked-files=all
date -u +%Y-%m-%dT%H:%M:%SZ
```

Outside a git repository, do not fail the load just because git state is unavailable. Report the current working directory and state that git state is unavailable because the directory is not a git repository.

If the selected handoff names a branch or commit that differs from live state, call out the mismatch before recommending action.

When the handoff's `commit` differs from live `HEAD`, run `git diff --name-only <commit> HEAD` to see which files changed since the save.

If the handoff names specific important files, read those live files before making claims that depend on them.

## Throughline Context

When `<project_root>/.agents/handoffs/THROUGHLINE.md` exists, read it in full as background arc context — its size discipline keeps a full read cheap. The throughline lives only at that primary path; check it there even when the selected handoff came from a legacy directory. Add a labeled `Throughline:` line to the response: the as-of date, plus a stale note when its `covers_through` is behind the newest source handoff filename timestamp — compared across the throughline's source set (top-level files plus `archive/` in the primary and legacy handoffs directories, never `THROUGHLINE.md` itself). The short form below carries this line only when the throughline is stale.

Arc context only: never base the recommended next move on throughline content unless the selected handoff or live files corroborate it.

## Short Form

Choose the reply form only after the full check above has run. The short form shortens the reply, never the check.

Use the short form only when the check found nothing that differs from the handoff, which means all of these hold:

- The directory is a git repository, and the handoff's frontmatter has `branch` and `commit`.
- The live branch equals `branch`.
- Live `HEAD` is `commit` (compare by prefix, since either may be abbreviated), or `git diff --name-only <commit> HEAD` lists only paths under `.agents/handoffs/`, such as a throughline refresh committed after the save.
- Selection passed over no newer handoff on another branch.
- The working tree agrees with the handoff: no path the handoff names shows uncommitted changes in `git status` that the handoff does not mention, and when the handoff states the working-tree status, the live status matches it.
- Every file the handoff names that the check read still says what the handoff says.

Any difference, or any condition you could not check, means the full form in Response Shape below. A stale throughline is not a difference from the handoff: it describes older history by definition, so it does not rule out the short form, and the short form's `Throughline:` line reports it.

The short form is about five lines with no headings:

```markdown
Loaded: <path>, saved <age> ago.
Nothing has changed since then: `<branch>` at `<HEAD>`, <working-tree summary, such as "clean" or "1 untracked path">.
Next: <the handoff's next action, in one sentence>
Throughline: <one line saying it is stale and how far behind; omit this line unless stale>

Need from you:
1. <each decision the handoff left open for the user, one per number>
```

- Age: compute it from `created_at` against the `date -u` output, converting any offset to UTC. Give minutes under two hours, hours under two days, and days after that. If `created_at` is missing or carries no offset, write `age unknown`; never estimate.
- When `HEAD` moved only by commits under `.agents/handoffs/`, say so in the live-state line, for example "`main` at `c41af07`, one throughline commit after the handoff's `d31f0c9`".
- When the handoff left no decision open, write `Need from you: tell me to start the next action.` on one line.

The user can ask for the full report at any time, for example `full` or `show the whole load`. Answer with the full form from the same check. Do not mention this option in the short reply.

## Response Shape

This is the full form. Use it whenever any short-form condition does not hold, and whenever the user asks for the full report.

```markdown
Loaded: <path>

Current live state:
- CWD: <path>
- Git: <branch/HEAD/worktree summary, or "unavailable: not a git repository">

Throughline: <as of <updated_at>; note staleness when covers_through is behind the newest source handoff; omit this line when no THROUGHLINE.md exists>

Handoff says:
- <goal/current state>
- <key decisions>
- <next action>

Reality check:
- <what matches>
- <what is stale or unverified>

Recommended next move:
- <one concrete continuation>
```

Keep the response focused. Do not display the full handoff unless the user asks for the full text.
