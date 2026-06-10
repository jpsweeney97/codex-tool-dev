---
name: load-handoff
description: Use when continuing from a previous session, when user runs `/load` to load the most recent handoff, or when user runs `/load <path>` for a specific handoff.
---

# Load Handoff

Load an existing Markdown handoff as strictly read-only context. The handoff is a resume pointer, not current truth.

This skill never archives, moves, copies, edits, deletes, marks consumed, writes state, or creates recovery metadata.

## Use

- Use for `/load`, `/load <path>`, "continue from where we left off", or "pick up the latest handoff."
- If no handoff exists, report that plainly. Suggest `/save` only if there is current context worth preserving.
- If a provided path does not exist, report `Handoff not found at <path>` and stop.

## Selection

Default search scope for implicit `/load`:

```text
<project_root>/.agents/handoffs/*.md
<project_root>/.claude/handoffs/*.md   (legacy, read-only)
<project_root>/.codex/handoffs/*.md    (legacy, read-only)
```

`.agents/handoffs/` is the shared primary location. The legacy directories stay in the implicit scope so older handoffs remain loadable, but nothing is ever written, moved, or migrated there.

`THROUGHLINE.md` in a handoffs directory is the derived arc document maintained by `/throughline` (or `$throughline`), not a session handoff. Never select it as the implicit handoff, even when file modification time would make it the newest entry.

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

For implicit `/load`, first determine the current branch when inside a git repository. Then choose the newest handoff whose frontmatter `branch` matches the current branch when both values are available. If no branch-matching handoff exists, choose the newest handoff by filename timestamp. File modification time is an acceptable fallback if filenames do not sort usefully.

This is deterministic selection, not semantic ranking or an index.

For explicit `/load <path>`, read exactly that path if it exists. Read a path outside the default scope, such as `docs/handoffs/` or an archive directory, only when the user explicitly provides that path.

If the explicit path is a `THROUGHLINE.md`, do not apply resume-pointer framing or the response shape below. Reply briefly that it is the derived arc document, not a session handoff — read it directly or refresh it with `/throughline` — and stop.

## Live-Reality Check

After reading the handoff, run a live-reality check before treating it as actionable.

Inside a git repository, run:

```bash
git branch --show-current
git log -1 --oneline
git status --short --branch --untracked-files=all
```

Outside a git repository, do not fail the load just because git state is unavailable. Report the current working directory and state that git state is unavailable because the directory is not a git repository.

If the selected handoff names a branch or commit that differs from live state, call out the mismatch before recommending action.

If the handoff names specific important files, read those live files before making claims that depend on them.

## Throughline Context

When `<project_root>/.agents/handoffs/THROUGHLINE.md` exists, read it in full as background arc context — its size discipline keeps a full read cheap. The throughline lives only at that primary path; check it there even when the selected handoff came from a legacy directory. Add a labeled `Throughline:` line to the response: the as-of date, plus a stale note when its `covers_through` is behind the newest source handoff filename timestamp — compared across the throughline's source set (top-level files plus `archive/` in the primary and legacy handoffs directories, never `THROUGHLINE.md` itself).

Arc context only: never base the recommended next move on throughline content unless the selected handoff or live files corroborate it.

## Response Shape

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
