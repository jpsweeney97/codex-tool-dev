---
name: search
description: Search across handoff history for decisions, learnings, and context. Use when user says "search handoffs", "find in handoffs", "what did we decide about", or runs /search.
argument-hint: "<query> [--regex]"
---

# Search

Search active and archived handoffs for the current project. Returns full matching sections.

## Procedure

When user runs `/search <query>`:

1. **Run the search script:**

   ```bash
   python3 ../../scripts/search.py '<query>'
   ```

   **Query quoting:** Wrap the query in single quotes to prevent shell expansion. If the query contains single quotes, escape each `'` as `'\''`.

   If user passed `--regex`, append `--regex` to the command.

   **Note:** Literal search is case-insensitive. Regex search is case-sensitive by default — users can add `(?i)` to their pattern for case-insensitive regex (e.g., `(?i)merge.*strategy`).

   **Important:** Do NOT `cd` into the plugin directory before running. `get_project_name()` resolves the project from the current working directory — changing CWD to the plugin directory would resolve to the plugin's repo name instead of the user's project.

2. **Parse JSON output** from stdout.

3. **Handle errors:**
   - If `error` is non-null: display the error message and stop.
   - If `total_matches` is 0: "No handoffs matched `<query>`."
   - If `skipped` is non-empty: mention "N files could not be read" after results.
   - If `project_source` is `"cwd"`: mention "Note: project name resolved from directory name (git not available)."

4. **Present results:**
   - **1-5 results:** For each result, show:
     ```
     **<title>** (<date>, <type>) — <section_heading>
     <section_content>
     ```
   - **6+ results:** Show summary table of all matches:
     ```
     | Date | Title | Section | Archived |
     ```
     Then show the 3 most recent results in full.
     Offer: "Want to see the rest?"

## Examples

**User:** `/search merge strategy`

**Result (1 match):**
> **PR #26 reviewed, merged** (2026-02-25, handoff) — ## Decisions
>
> ### Regular merge over squash merge for PR #26
>
> **Choice:** Regular merge preserving all 22 commits.
> ...

**User:** `/search --regex "option-[AB]"`

Searches using regex pattern.

**User:** `/search nonexistent_thing`

> No handoffs matched `nonexistent_thing`.
