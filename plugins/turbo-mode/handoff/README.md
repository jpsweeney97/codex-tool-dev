# Handoff

Handoff is a skill-only Codex plugin for session continuity. It helps Codex save, load, and search Markdown handoffs under the current project's `.codex/handoffs/` directory.

Handoffs are resume pointers, not live truth. A future session should read the handoff, check the live repository or working directory, and then continue from what still matches reality.

## Installation

Bundled in the `turbo-mode` marketplace:

```bash
codex plugin marketplace update turbo-mode
codex plugin install handoff@turbo-mode
```

Or install directly from the development repo:

```bash
codex plugin install ./plugins/turbo-mode/handoff
```

## What It Does

| Skill | Purpose |
| --- | --- |
| `/save` | Writes a Markdown handoff with session context and project-arc context. |
| `/load` | Reads a handoff as context, then checks live repository or working-directory state before recommending action. |
| `/search` | Searches project handoffs with `rg`. Literal search is the default; regex is used only when requested. |

Handoff does not ship runtime modules, helper scripts, command hooks, validators, transaction state, chain state, archive-on-load behavior, recovery protocols, or durable learning extraction.

`/quicksave`, `/summary`, and `/distill` are retired behavior. They are not wrappers, aliases, or compatibility entry points in this source bundle.

## Storage

Primary storage is:

```text
<project_root>/.codex/handoffs/
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

Handoff filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

Writes use direct path selection with no hidden state:

1. Create `<project_root>/.codex/handoffs/` if needed.
2. Choose the timestamp path.
3. Write with an exclusive-create primitive.
4. If the path exists, append `-2`, `-3`, and so on before `.md` until a free path is found.
5. If the direct write fails for any other reason, stop and report the write failure plainly.

The plugin does not add gitignore rules, stage files, commit files, auto-prune files, or manage cross-machine continuity. Whether `.codex/handoffs/` is tracked or ignored remains host-repository policy.

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

These headings are prompts, not a schema. The quality bar is the resumption test: could future Codex continue without wasting time, repeating avoidable exploration, or trusting a stale claim?

## Boundaries

- `/save` is the only write-oriented skill.
- `/load` and `/search` are read-only.
- Loading never archives, moves, copies, edits, deletes, marks consumed, or writes recovery metadata.
- Searching does not parse a custom schema, build an index, rank semantically, deduplicate, or mutate files.
- Source shape does not prove installed runtime behavior. Plugin install, local cache refresh, marketplace update, or current-thread runtime reload require separate explicit proof.
