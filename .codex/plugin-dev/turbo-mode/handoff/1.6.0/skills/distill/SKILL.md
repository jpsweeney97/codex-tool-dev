---
name: distill
description: Extract durable knowledge from handoffs into learnings. Use when user says "/distill", "distill handoff", "extract knowledge", "graduate knowledge", or wants to turn handoff insights into reusable learnings. Reads handoff files, extracts candidates from Decisions/Learnings/Codebase Knowledge/Gotchas, checks for duplicates, and appends synthesized entries to docs/learnings/learnings.md.
argument-hint: "[path]"
allowed-tools:
  - Bash
  - Read
  - Edit
---

# Distill

Synthesize handoff content into durable Phase 0 learning entries. The `distill.py` script handles deterministic work (parsing, hashing, dedup). This skill handles judgment: synthesis, semantic dedup, confirmation UX, and appending confirmed entries.

## Inputs

| Input | Behavior |
|-------|----------|
| `/distill` | Most recent handoff in `<project_root>/docs/handoffs/` (non-recursive, skip `archive/`) |
| `/distill <path>` | Specific handoff file at `<path>` |
| `--include-section <name>` | Add section to extraction scope (e.g., `--include-section Context`) |

## Procedure

### Step 1: Locate handoff

If path provided, validate it exists. If not:

```bash
ls -t "$(git rev-parse --show-toplevel)/docs/handoffs"/*.md | head -1
```

Skip `archive/` subdirectory. Use the project name from the current working directory (same as other handoff skills).

**If no handoff files exist:** Report "No handoffs found for project `<project>`" and STOP.

### Step 2: Run distill.py

```bash
python ../../scripts/distill.py <handoff_path> --learnings <learnings_path>
```

- `<learnings_path>` = `docs/learnings/learnings.md` relative to the project root (resolve to absolute path before passing).
- If user passed `--include-section <name>`, append `--include-section <name>` to the command.

Parse JSON output from stdout. If the `error` field is non-null, display the error message and STOP.

### Step 3: Group candidates by dedup status

Display a summary table of all candidates:

| Status | Meaning | Action |
|--------|---------|--------|
| `EXACT_DUP_SOURCE` | Same source, same content | Auto-skip (terminal) |
| `EXACT_DUP_CONTENT` | Different source, same content | Auto-skip (terminal) |
| `UPDATED_SOURCE` | Same source, content changed | Prompt user |
| `NEW` | Never distilled | Synthesize |

For terminal states (`EXACT_DUP_SOURCE`, `EXACT_DUP_CONTENT`): show one-line summary per candidate. No synthesis, no confirmation.

**If no NEW or UPDATED_SOURCE candidates:** Report "All candidates already distilled or content-identical" and STOP.

### Step 4: Synthesize each NEW candidate

Convert `raw_markdown` into a Phase 0 paragraph using the format mapping table below. Target 6-8 sentences, max 10. Preserve reasoning chains -- a decision's "why" MUST stay with its "what."

**Format mapping table:**

| Source section | Source fields | Target in paragraph |
|---------------|-------------|-------------------|
| Decisions | `**Choice:**` | What was decided |
| Decisions | `**Driver:**` | Why -- the evidence or reasoning |
| Decisions | `**Alternatives considered:**` | Context (what else was evaluated) |
| Decisions | `**Trade-offs accepted:**` | Limitations acknowledged |
| Decisions | `**Confidence:**` | Certainty level |
| Learnings | `**Mechanism:**` | What/how it works |
| Learnings | `**Evidence:**` | Proof it's true |
| Learnings | `**Implication:**` | Takeaway for future work |
| Learnings | `**Watch for:**` | Caveat or edge case |
| Codebase Knowledge | (raw markdown) | Pattern or convention |
| Gotchas | (raw markdown) | Workaround or pitfall |

### Step 5: Semantic dedup against existing learnings

For each synthesized paragraph, compare against existing entries in `docs/learnings/learnings.md`:

1. Read the file and identify each `### YYYY-MM-DD [tags]` entry.
2. For each existing entry, check whether the new candidate covers the same core insight (same concept, decision, or pattern — even if worded differently).
3. If a match is found, annotate the candidate as `LIKELY_DUPLICATE` and record the matched entry's heading and first sentence.

Semantic dedup is advisory -- the user makes the final call.

### Step 6: Present candidates

Show each non-terminal candidate with:

```
**Source:** {source_section}/{subsection_heading}
  (Use "(section body)" if subsection_heading is empty)
**Status:** NEW | LIKELY_DUPLICATE (with matched entry) | UPDATED_SOURCE
**Durability:** {durability_hint}  (Codebase Knowledge and Gotchas only)
**Tags:** [{tag1}, {tag2}]

> <proposed Phase 0 text>
```

**Tag mapping:**

| Source section | Default tags | Override |
|---------------|-------------|---------|
| Decisions | `[architecture]` or `[workflow]` | Infer from content |
| Learnings | Infer from content | Common: `[debugging]`, `[testing]`, `[pattern]`, `[workflow]` |
| Codebase Knowledge | `[pattern]` or `[architecture]` | Infer from content |
| Gotchas | `[debugging]` or `[workflow]` | Infer from content |

### Step 7: User confirmation

Prompt by status. NEVER auto-append without confirmation.

**UPDATED_SOURCE:** Locate existing entry in `docs/learnings/learnings.md` by scanning for `<!-- distill-meta` comment with matching `source_uid`. Show diff (old paragraph vs new).

Check the entry block for `<!-- promote-meta`. If found, extract `target` and `promoted_at`.

**If promoted** (has `promote-meta`):

> ⚠ This entry was promoted to `{target}` on {promoted_at}. Replacing it invalidates that promotion.

Options:
- `replace` (default) — delete old entry (heading through all meta comments), append new. Previous promotion invalidated; entry re-surfaces in `/promote`.
- `replace + keep promoted` — delete old entry, append new with original `promote-meta` preserved. User asserts the promoted Codex instruction artifact still correct despite source change.
- `skip` — do nothing

**If not promoted:**

Options:
- `replace` (default) — delete old entry (heading through meta comment inclusive), append new at end
- `keep both` — append new without removing old
- `skip` — do nothing

**UNIQUE_NEW** (NEW, no semantic match): Options:
- `append` (default)
- `skip`

**LIKELY_DUPLICATE** (NEW, semantic match found): Options:
- `merge` -- combine with existing entry
- `replace` -- overwrite existing entry
- `keep both` -- append as separate entry
- `skip`

Present all candidates at once. Accept batch input (e.g., "append all", "skip 2 and 5") or individual responses.

**Red flags — STOP and re-confirm:**

| Thought | Reality |
|---------|---------|
| "User said 'append all' last time, I'll do the same" | Each run is independent. Always present and confirm. |
| "These are obviously NEW, no need to show them" | The user decides what's obvious. Present every candidate. |
| "Semantic dedup found nothing, skip to append" | Step 6 (present) is mandatory even with no duplicates. |
| "I'll just append and tell the user after" | NEVER write before confirmation. Show first, write after. |

### Step 8: Append confirmed entries

Write each confirmed entry to `docs/learnings/learnings.md` in this format:

```markdown
### YYYY-MM-DD [tag1, tag2]

<synthesized paragraph>
<!-- distill-meta {"content_sha256": "<from candidate>", "distilled_at": "YYYY-MM-DD", "source_anchor": "<from candidate>", "source_uid": "<from candidate>", "v": 1} -->
```

**Requirements:**
- `distilled_at` MUST be today's ISO date (YYYY-MM-DD). NEVER leave empty.
- `content_sha256` = the candidate's `content_sha256` field.
- `source_anchor` = the candidate's `source_anchor` field.
- `source_uid` = the candidate's `source_uid` field.
- Append at end of file, after a blank line.
- For `replace` operations: delete old entry from `### ` heading line through the last metadata comment in the block (`<!-- distill-meta ... -->` or `<!-- promote-meta ... -->`, whichever comes last), then append new entry at end.
- For `replace + keep promoted` operations: delete old entry as above, then append new entry with the original `promote-meta` comment re-attached after the new `distill-meta`.

## Failure Modes

| Failure | Recovery |
|---------|----------|
| `distill.py` returns error JSON | Display error message, STOP |
| No NEW or UPDATED_SOURCE candidates | Report "All candidates already distilled or content-identical", STOP |
| `docs/learnings/learnings.md` not found | Create with: `# Learnings\n\nProject insights captured from consultations.` |
| Handoff has no extractable sections | Report "No Decisions, Learnings, Codebase Knowledge, or Gotchas sections found", STOP |
| Script path does not resolve | Resolve `../../scripts/distill.py` relative to this skill's directory |

## Examples

### Example 1: First distill from a handoff

**User:** `/distill`

**Actions:**
1. Find most recent handoff: `<project_root>/docs/handoffs/2026-02-27_14-30_api-redesign.md`
2. Run distill.py, get 4 candidates: 2 NEW (Decisions), 1 NEW (Learnings), 1 NEW (Gotchas)
3. Synthesize each into Phase 0 paragraph
4. No semantic duplicates found
5. Present all 4 with proposed text and tags
6. User says "append all"
7. Append 4 entries to `docs/learnings/learnings.md`

**Result:** "4 entries appended to docs/learnings/learnings.md"

### Example 2: Re-distilling after content update

**User:** `/distill <project_root>/docs/handoffs/2026-02-27_14-30_api-redesign.md`

**Actions:**
1. Run distill.py, get 4 candidates: 3 EXACT_DUP_SOURCE, 1 UPDATED_SOURCE
2. Show 3 auto-skipped duplicates as one-line summary
3. Show UPDATED_SOURCE with old vs new diff
4. User says "replace"
5. Delete old entry, append updated entry

**Result:** "1 entry replaced in docs/learnings/learnings.md. 3 duplicates skipped."

## Scope

- **Read-only:** handoff files, `docs/learnings/learnings.md` (for dedup checking)
- **Write:** `docs/learnings/learnings.md` (append confirmed entries only)
- **Does NOT:** modify handoff files, create new handoff files, or write outside learnings.md
