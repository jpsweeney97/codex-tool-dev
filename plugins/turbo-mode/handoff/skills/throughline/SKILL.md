---
name: throughline
description: "Use when the user runs `/throughline` or `$throughline`, or asks to create, refresh, or rebuild the project's derived `.agents/handoffs/THROUGHLINE.md` from saved handoffs. Do not use for loading, saving, or searching individual handoffs, ad hoc Markdown synthesis, or treating the throughline as authoritative current truth."
---

# Throughline

Maintain one derived, concise Markdown document per project that condenses the
handoff pile into a readable history: project narrative, decisions that hold,
abandoned paths, and the current frontier.

Invoked as `/throughline` or `$throughline`.

The throughline is derived evidence, not authority: on conflict, the
underlying handoffs and live state win. It is regenerable at any time from the
pile.

When a separate `markdown-synthesis` skill is available, ad hoc multi-document
synthesis into standalone files belongs to it; this skill owns only the
canonical, maintained project handoff arc at its fixed path.

## The Artifact

One document per project:

```text
<project_root>/.agents/handoffs/THROUGHLINE.md
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

Frontmatter and section prompts live in `../../references/throughline-format.md`.
The frontmatter coverage pair — `covers_through` (basename of the newest
source handoff folded in) and `sources_folded` (total count of source files
folded) — is the only machinery. It is a high-water mark of what was folded,
not proof of complete coverage, and never truth: when it conflicts with the
listed source set or live reality, rebuild rather than trust it.

## Source Set

Source material is timestamped session handoffs — `*.md` files with the
`YYYY-MM-DD_*` filename shape — in:

```text
<project_root>/.agents/handoffs/
<project_root>/.claude/handoffs/   (legacy, read-only)
<project_root>/.codex/handoffs/    (legacy, read-only)
```

Top-level files plus files in each directory's `archive/` subdirectory, one
named level only. Archived handoffs are often most of a project's history.

`THROUGHLINE.md` itself, other subdirectories, and non-handoff files are never
source material: the throughline must not ingest its own derived content.

Ordering: compare by the parsed timestamp portion of the basename, never raw
string order — `-` and `_` sort differently at the precision boundary, so
lexicographic comparison misorders mixed-precision names. Treat
minute-precision legacy names conservatively; when two names tie at the
available precision — including `-2`/`-3` collision suffixes — include each
tied file for reading and break remaining ties by full basename. Skipping is
the dangerous direction; re-reading one file is cheap. `covers_through`
defines a cut line, not a file identity: basenames equal to the marker are
re-read regardless of which source directory holds them.

## Refresh Behavior

- **First run** (no `THROUGHLINE.md`): read the full source set, synthesize,
  write the document — creating `<project_root>/.agents/handoffs/` first if it
  does not exist (a legacy-only pile has sources but no primary directory).
  If the source set is empty, report plainly that no handoffs exist and write
  nothing.
- **Subsequent runs**: read the existing document, then list the full source
  set — listing is cheap; reading is the cost. Check for drift: if the count
  of source files at or below `covers_through` does not match
  `sources_folded`, older files have appeared or vanished below the water
  line (restored archive, copied legacy handoffs, branch switch) — fall back
  to a full rebuild. Otherwise read only source handoffs newer than
  `covers_through`, then rewrite the whole document, folding in new material
  and compressing older material as needed. Rewrite, not append — that is
  what keeps the document concise forever.
- **Recovery**: coverage frontmatter missing or malformed, document
  inconsistent with reality, or user asks for a rebuild → re-read the full
  source set and regenerate.
- **Coverage honesty**: advance `covers_through` and `sources_folded` only
  over handoffs actually read in full. If the source set cannot be fully read
  (size, unreadable files), either fold a bounded batch or stop and report
  the blocked rebuild. A bounded batch folds the oldest unfolded sources
  first, so the coverage pair stays a true claim about everything at or below
  the water line. Never claim coverage past what was read.

## Synthesis

- Preserve branch and project qualifiers from handoff frontmatter: a decision
  made on a side branch is recorded as branch-scoped unless it demonstrably
  governs the project. Only truly project-level settled choices belong under
  "Decisions That Hold".
- Weigh concrete session and evidence sections over broad "Project Arc"
  restatements: handoffs saved after the throughline exists may echo the
  throughline itself, and an echo is not independent confirmation.
- Keep the document short enough to load alongside a handoff without
  dominating context. Size discipline is judgment, not a validator.

## Boundaries

- Never edit, move, archive, delete, or mark handoffs — the pile is untouched
  source material.
- No index files, no per-handoff state, no content hashes, no per-branch
  throughlines. One throughline per project.
- Never run automatically from save or load; those skills only nudge.
- Do not reproduce the full document in chat.

## Reply

```text
Throughline updated: <absolute path> (folded N handoffs, covers through <newest folded handoff>)
```

For a bounded-batch fold, use the partial wording instead — never the normal
reply:

```text
Throughline updated (partial): <absolute path> — N of M sources folded; run /throughline again to continue
```

If creating the primary directory or writing `THROUGHLINE.md` fails, stop and
report the write failure plainly; never use either updated reply for a write
that did not complete.
