---
name: distill
description: Extract durable knowledge from handoffs into learnings. Use when user says "/distill", "distill handoff", "extract knowledge", "graduate knowledge", or wants to turn handoff insights into reusable learnings. Reads handoff files, extracts candidates from Decisions/Learnings/Codebase Knowledge/Gotchas, checks for duplicates, and appends synthesized entries to docs/learnings/learnings.md.
allowed-tools:
  - Bash
  - Read
  - Edit
---

# Distill

Turn handoff content into durable learning entries in `docs/learnings/learnings.md`. The script handles parsing, hashing, and exact dedup; the assistant handles synthesis, semantic dedup, confirmation, and append/replace choices.

Read [skill-details.md](../../references/skill-details.md) only when you need section mapping details, confirmation options, metadata examples, or troubleshooting.

## Use

- Use for `/distill`, `/distill <path>`, "distill handoff", "extract knowledge", or "graduate knowledge".
- Never append or replace learning entries without presenting candidates and getting user confirmation.
- Handoff files are read-only. The only write target is `docs/learnings/learnings.md`.

## Setup

Resolve plugin root before running helpers. Set `PLUGIN_ROOT` to the plugin root directory three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. When executing commands, use the absolute path for `PLUGIN_ROOT`; do not `cd` into the plugin directory.

## Procedure

1. Locate the source handoff. If the user gave a path, validate it exists. If not, use the most recent active handoff in `docs/handoffs/` and skip `archive/`. If no handoff exists, report "No handoffs found for project `<project>`" and STOP.
2. Run the extractor:

   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PYTHONDONTWRITEBYTECODE=1 \
   UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff" \
   uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/distill.py" "<handoff_path>" --learnings "<learnings_path>"
   ```

   Use an absolute `<learnings_path>` for `docs/learnings/learnings.md`. If the user passed `--include-section <name>`, append that option. If stdout contains `error`, display it and STOP.

3. Group candidates by deterministic status: `EXACT_DUP_SOURCE`, `EXACT_DUP_CONTENT`, `UPDATED_SOURCE`, or `NEW`.
4. Auto-skip exact duplicates with a one-line summary. For `NEW` and `UPDATED_SOURCE`, synthesize Phase 0 paragraphs that preserve each decision's "why" with its "what".
5. Compare synthesized candidates against existing learning entries for semantic duplicates. Mark likely duplicates, but let the user decide.
6. Present every non-terminal candidate with source section, status, durability hint when available, tags, proposed text, and duplicate match if any.
7. Ask for confirmation. Valid choices include append, replace, replace plus keep promoted metadata, merge, keep both, skip, batch input such as "append all", or numbered overrides.
8. Apply confirmed writes only:
   - Append new entries at the end of `docs/learnings/learnings.md`.
   - For replace operations, delete the old entry block from `### ` heading through its metadata comments before appending the replacement.
   - Include `distilled_at` as today's ISO date and preserve `content_sha256`, `source_anchor`, and `source_uid` from the candidate.
9. Report appended, replaced, skipped, and duplicate counts.
