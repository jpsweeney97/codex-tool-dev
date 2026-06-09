---
name: search-handoffs
description: Search across Markdown handoffs for decisions and context. Use when user says "search handoffs", "find in handoffs", "what did we decide about", or runs `/search <query>`.
---

# Search Handoffs

Search project Markdown handoffs as a read-only convenience. This skill does not parse a custom schema, build an index, rank semantically, deduplicate, or mutate files.

## Scope

Default search scope:

```text
<project_root>/.agents/handoffs/
<project_root>/.claude/handoffs/   (legacy, read-only)
<project_root>/.codex/handoffs/    (legacy, read-only)
```

`.agents/handoffs/` is the shared primary location for Claude Code and Codex sessions. The legacy directories stay searchable so older handoffs remain findable; nothing is written or migrated there.

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

If none of these directories exist, report:

```text
No handoffs directory found for this project.
```

## Literal Search

Use literal search by default:

```bash
for d in .agents/handoffs .claude/handoffs .codex/handoffs; do
  [ -d "$PROJECT_ROOT/$d" ] && rg -n --context 3 --fixed-strings "<query>" "$PROJECT_ROOT/$d"
done
```

If there are no matches, report:

```text
No handoffs matched `<query>`.
```

## Regex Search

Use regex only when the user explicitly asks for regex:

```bash
for d in .agents/handoffs .claude/handoffs .codex/handoffs; do
  [ -d "$PROJECT_ROOT/$d" ] && rg -n --context 3 "<pattern>" "$PROJECT_ROOT/$d"
done
```

## Results

For a small number of matches, show the matching path, line number, and surrounding context.

For many matches, show a useful handful and offer to narrow. Suggest `/load <path>` when one result looks like the right continuation artifact.
