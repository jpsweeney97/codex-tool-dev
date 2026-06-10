# Handoff

Handoff is a skill-only plugin for session continuity in Claude Code and Codex. It helps the agent save, load, and search Markdown handoffs under the current project's `.agents/handoffs/` directory, which both runtimes share.

Handoffs are resume pointers, not live truth. A future session should read the handoff, check the live repository or working directory, and then continue from what still matches reality.

## Installation

The canonical source lives at `~/.agents/plugins/handoff/` and is listed in the
personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the
installed copy after source edits):

```bash
codex plugin add handoff@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a
symlink in `~/.claude/skills/` managed by
`~/.agents/scripts/claude-skills-sync.sh`.

## What It Does

| Skill | Purpose |
| --- | --- |
| `/save` | Writes a Markdown handoff with session context and project-arc context. |
| `/load` | Reads a handoff as context, then checks live repository or working-directory state before recommending action. |
| `/search` | Searches project handoffs with `rg`. Literal search is the default; regex is used only when requested. |
| `/throughline` | Maintains `THROUGHLINE.md`, a rolling, regenerable condensation of the project's handoff pile: narrative, decisions that hold, abandoned paths, frontier. Never mutates handoffs. |

Handoff does not ship runtime modules, helper scripts, command hooks, validators, transaction state, chain state, archive-on-load behavior, or recovery protocols. The only derived document is the throughline: a rolling, regenerable arc summary that never mutates handoffs and is always rebuildable from them.

`/quicksave`, `/summary`, and `/distill` are retired behavior. They are not wrappers, aliases, or compatibility entry points in this source bundle, and `/throughline` is not a revival of them — it is a new derived-arc contract.

## Storage

Primary storage is:

```text
<project_root>/.agents/handoffs/
```

This directory is shared by Claude Code and Codex sessions. Legacy handoffs
under `.claude/handoffs/` and `.codex/handoffs/` remain readable by `/load`
and `/search` but are never written to.

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

Handoff filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

Writes use direct path selection with no hidden state:

1. Create `<project_root>/.agents/handoffs/` if needed.
2. Choose the timestamp path.
3. Write with an exclusive-create primitive.
4. If the path exists, append `-2`, `-3`, and so on before `.md` until a free path is found.
5. If the direct write fails for any other reason, stop and report the write failure plainly.

The plugin does not add gitignore rules, stage files, commit files, auto-prune files, or manage cross-machine continuity. Whether `.agents/handoffs/` is tracked or ignored remains host-repository policy.

## Handoff Format

Handoffs are Markdown files with minimal YAML frontmatter. See `references/handoff-format.md`.

Recommended frontmatter:

```yaml
---
created_at: "2026-06-09T14:30:00Z"
type: handoff
title: "Skill-only Handoff redesign"
project: codex-tool-dev
branch: main
commit: abc1234
---
```

`created_at`, `type`, `title`, and `project` should be present. Include `branch` and `commit` when available.

Recommended body prompts:

```markdown
# Handoff: <title>

## Session Context
## Project Arc
## Decisions
## Evidence Checked
## Current State
## Next Action
## Open Questions
## Risks
## References
```

These headings are prompts, not a schema. The quality bar is the resumption test: could a future session continue without wasting time, repeating avoidable exploration, or trusting a stale claim?

## Boundaries

- `/save` is the only skill that writes session handoffs. `/throughline` writes only the derived `THROUGHLINE.md` and never mutates handoffs.
- `/load` and `/search` are read-only.
- Loading never archives, moves, copies, edits, deletes, marks consumed, or writes recovery metadata.
- Searching does not parse a custom schema, build an index, rank semantically, deduplicate, or mutate files.
- Source shape does not prove installed runtime behavior. Plugin install, local cache refresh, marketplace update, or current-thread runtime reload require separate explicit proof.
