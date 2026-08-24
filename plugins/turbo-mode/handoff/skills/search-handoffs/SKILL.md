---
name: search-handoffs
description: "Use when the user asks to search saved Markdown handoffs for decisions or context, including `search handoffs`, `find in handoffs`, `what did we decide about`, or `/search` (or `$search`) with a query. Do not use to load a handoff for continuation, save new context, refresh throughline, or treat derived matches as current truth without source verification."
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

1. Use the main working tree of the repository when the current directory is inside a git repository: the first path listed by `git worktree list`. This equals `git rev-parse --show-toplevel` except inside a linked worktree, where the main tree is used so all worktrees of one repository share one handoff location. If the first listed entry is a bare repository, use `git rev-parse --show-toplevel` instead.
2. Otherwise use the current working directory.

If none of these directories exist, report:

```text
No handoffs directory found for this project.
```

## Literal Search

Use literal search by default:

```bash
for d in .agents/handoffs .claude/handoffs .codex/handoffs; do
  [ -d "$PROJECT_ROOT/$d" ] && rg -n --context 3 --fixed-strings -e '<query>' "$PROJECT_ROOT/$d"
done
```

Substitute the query inside the single quotes, escaping any single quote in it as `'\''`. The single quotes stop the shell from expanding `$`, backticks, or embedded double quotes in the query; the `-e` flag stops a query starting with `-` from being read as a flag.

If there are no matches, report:

```text
No handoffs matched `<query>`.
```

## Regex Search

Use regex only when the user explicitly asks for regex:

```bash
for d in .agents/handoffs .claude/handoffs .codex/handoffs; do
  [ -d "$PROJECT_ROOT/$d" ] && rg -n --context 3 -e '<pattern>' "$PROJECT_ROOT/$d"
done
```

The same single-quote and `-e` rules apply as for literal search.

## Results

For a small number of matches, show the matching path, line number, and surrounding context.

For many matches, show a useful handful and offer to narrow. Suggest `/load <path>` (or `$load <path>`) when one result looks like the right continuation artifact.

Matches in `THROUGHLINE.md` are from the derived arc document, not a session handoff: do not suggest `/load <path>` for them, and treat them as derived pointers to verify in source handoffs before treating a claim as decided.
