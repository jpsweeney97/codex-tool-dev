---
name: save-handoff
description: Use when user says "/save", "wrap this up", "new session", "almost out of context", "save", "next session", or "handoff"; use when stopping work with context to preserve.
---

# Save Handoff

Create a Markdown handoff at `<project_root>/.agents/handoffs/` so a future session can resume without avoidable re-exploration.

Use this for real session boundaries where there is useful context to preserve: decisions, changed files, current state, risks, open questions, or the next action.

Do not use this to resume prior work; use `load-handoff`.

## What To Capture

Every saved handoff should include both:

- session context: what happened in this session, what changed, what was decided, what is in flight
- project-arc context: where the broader project stands, why this session matters, what prior decisions are load-bearing, and what a future session should not forget

Use `../../references/handoff-format.md` when you need the recommended frontmatter and section prompts.

## Storage

Primary storage is:

```text
<project_root>/.agents/handoffs/
```

This directory is shared by Claude Code and Codex sessions, so either runtime can resume from a handoff the other saved.

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

Handoff filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

Use a short lowercase slug from the requested title or session topic. Replace spaces with hyphens and omit punctuation that is awkward in filenames.

## Direct Write Procedure

1. Gather current context, current working directory, and git branch/commit when available.
2. Create `<project_root>/.agents/handoffs/` if needed.
3. Choose the timestamp path.
4. Write the Markdown file with an exclusive-create primitive, such as an `Add File` patch or a file API opened in exclusive-create mode.
5. If the path exists, append `-2`, `-3`, and so on before `.md` until a free path is found.
6. If the direct write fails for any other reason, stop and report the file write failure plainly.
7. Reply only with:

```text
Handoff saved: <absolute path>
```

Do not reproduce the full handoff in chat.

## Boundaries

- Do not call plugin helper scripts.
- Do not create transaction state, active-write reservations, chain state, consumed markers, content hashes, recovery metadata, or `.session-state` files.
- Do not fall back to `docs/handoffs/`.
- Do not write to the legacy `.claude/handoffs/` or `.codex/handoffs/` directories; those are read-only legacy locations for `load-handoff` and `search-handoffs`.
- Do not add gitignore rules, stage files, commit files, auto-prune files, or manage cross-machine continuity.
- Whether `.agents/handoffs/` is tracked or ignored remains host-repository policy.
