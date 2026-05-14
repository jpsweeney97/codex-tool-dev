---
name: summary
description: Session summary with project arc context. Use when a full /save is overkill but /quicksave would lose decisions, codebase knowledge, and session narrative. Captures session context at moderate depth (120-250 lines) and synthesizes the project arc across sessions to prevent drift.
allowed-tools: Write, Read, Bash, Glob
---

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema, chain protocol, storage conventions.

# Summary

Capture what happened this session and where the project stands. Moderate depth — more than a checkpoint, less than a full handoff.

**Core Promise:** One action to summarize (`/summary`).

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

## When to Use

- End of a meaningful session where `/save` feels like overkill but `/quicksave` would lose too much
- Session had decisions, exploration, or codebase learning worth preserving at moderate depth
- Working on a multi-session project where arc awareness matters
- User says "summary" or "summarize"

## When NOT to Use

- **Context pressure / need to cycle fast** — use `/quicksave`
- **Complex session with deep decisions, pivots, or design work** — use `/save` (the 8-element decision analysis and full narrative matter)
- **Session was trivial** — skip entirely
- **Resuming from a handoff** — use the `load` skill instead

**Heuristic:** If the session had 3+ significant decisions with trade-offs worth recording in depth, lean toward `/save`. If the session was mostly execution with 0-2 decisions, `/summary` is the right fit.

## Inputs

**Required:**
- Session context (gathered from conversation history)

**Optional:**
- `title` argument for `/summary <title>` — if omitted, Codex generates a descriptive title

**Constraints/Assumptions:**

| Assumption | Required? | Fallback |
|------------|-----------|----------|
| Git repository | No | Omit `branch` and `commit` fields from frontmatter |
| Write access to `<project_root>/.codex/handoffs/` | Yes | **STOP** and report the active-writer error. Do not write to `docs/handoffs/` as a fallback. |
| Project root determinable | No | Use current directory; if ambiguous, ask user |

## Outputs

**Artifacts:**
- Markdown file at `<project_root>/.codex/handoffs/YYYY-MM-DD_HH-MM_summary-<slug>.md`
- Frontmatter with session metadata
- Body with 8 required sections

**Definition of Done:**

| Check | Expected |
|-------|----------|
| File exists at expected path | `ls` confirms file |
| Frontmatter parses as valid YAML | No YAML syntax errors |
| Required fields present | `date`, `time`, `created_at`, `session_id`, `project`, `title`, `type` all have values |
| Body line count | 120-250 |
| All 8 sections present | Goal, Session Narrative, Decisions, Changes, Codebase Knowledge, Learnings, Next Steps, Project Arc |
| At least 1 of {Decisions, Changes, Learnings} has substantive content | Hollow-summary guardrail |
| Project Arc populated | Contains arc context, not just session context |

## Commands

| Command | Action |
|---------|--------|
| `/summary` | Create summary (Codex generates title) |
| `/summary <title>` | Create summary with specified title |

## Procedure

When user runs `/summary [title]` or confirms an offer:

1. **Check prerequisites:**
   - If session appears trivial (no decisions, changes, or learnings), ask: "This session seems light — create a summary anyway?"
   - If user declines, **STOP**.

2. **Generate a session ID** as a fresh UUID for this summary.

3. **Gather arc context:**
   - List files in `<project_root>/.codex/handoffs/archive/` — scan titles and dates to identify relevant prior handoffs
   - Read any archived handoffs/checkpoints/summaries that appear relevant to the current project arc. Use judgment — not all archived files may be relevant, especially in repos with multiple workstreams.
   - Check recent git history: `git log --oneline -30` or similar. Look at commit messages for what's been done across sessions.
   - Combine with: conversation context, any loaded handoff from the current session, and general awareness of the project.

4. **Answer the 7 synthesis prompts (INTERNAL — do not output to chat):**

   **Prompt 1 — Goal:** What did I set out to do, and why does it matter?

   **Prompt 2 — Session Narrative:** What happened this session — what was the arc from start to finish? What pivoted? Where did understanding shift?

   **Prompt 3 — Decisions:** What choices were made, and what were the alternatives? For each: the choice, what drove it, what alternatives existed, and what trade-offs were accepted.

   **Prompt 4 — Changes:** What did I build or change? For each file: purpose, approach, key implementation details.

   **Prompt 5 — Codebase Knowledge:** What did I learn about the codebase that future Codex needs? Patterns, architecture, key locations with file:line references.

   **Prompt 6 — Learnings:** What insights or gotchas should survive this session? What was surprising?

   **Prompt 7 — Project Arc + Next Steps:** Where does the project stand now — what's done, what's next, what's at risk of being forgotten? Did anything we did this session necessitate changes elsewhere — downstream impacts, cascading updates, things that are now out of sync?

   You are not summarizing prior handoffs. You are answering: where does this project stand right now, and what would a new Codex need to know to avoid drift? Prior handoffs and git history are *input* to this synthesis, not the output.

   **IMPORTANT:** The synthesis work is internal reasoning. Do NOT present synthesis answers in chat. Only the final summary file is the deliverable.

5. **Reserve output path:**
   - Resolve project root: `$(git rev-parse --show-toplevel)` (falls back to cwd if not in a git repo)
   - Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin version root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"`. The literal `python` command must resolve to Python >=3.11.
   - Run `begin-active-write` with `--operation summary` before generating final markdown. Pass `--slug` only when a title-specific slug was chosen; otherwise let the helper bind the default slug. Use its `allocated_active_path` as the only final destination.
   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PROJECT_NAME="$(basename "$PROJECT_ROOT")"
   SLUG_ARGS=()
   if [ -n "${SLUG:-}" ]; then
     SLUG_ARGS=(--slug "$SLUG")
   fi
   BEGIN_OUTPUT="$(
     PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" \
       begin-active-write \
       --project-root "$PROJECT_ROOT" \
       --project "$PROJECT_NAME" \
       --operation summary \
       "${SLUG_ARGS[@]}" \
       2>&1
   )" || { printf '%s\n' "$BEGIN_OUTPUT" >&2; exit 1; }
   OPERATION_STATE_PATH="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["operation_state_path"])')"
   ALLOCATED_ACTIVE_PATH="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["allocated_active_path"])')"
   RESUMED_FROM="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; value=json.load(sys.stdin).get("resumed_from_path"); print(value or "")')"
   ```

6. **Generate markdown** with frontmatter per [handoff-contract.md](../../references/handoff-contract.md):
   - Include `session_id:` with the generated UUID from step 2
   - Include `type: summary` in frontmatter
   - Title: `"Summary: <descriptive-title>"`
   - Populate frontmatter `files:` from file paths mentioned in Changes and Codebase Knowledge sections
   - If `RESUMED_FROM` was set by `begin-active-write`, include `resumed_from: "$RESUMED_FROM"`
   - Write generated markdown to a temporary content file, not to `ALLOCATED_ACTIVE_PATH`; `write-active-handoff` owns the final write.
   ```bash
   CONTENT_FILE="$(mktemp)"
   # Write the complete markdown body to "$CONTENT_FILE" before committing it.
   CONTENT_SHA256="$(python -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$CONTENT_FILE")"
   ```

7. **Commit file** through the active writer:
   ```bash
   WRITE_OUTPUT="$(
     PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" \
       write-active-handoff \
       --project-root "$PROJECT_ROOT" \
       --operation-state-path "$OPERATION_STATE_PATH" \
       --content-file "$CONTENT_FILE" \
       --content-sha256 "$CONTENT_SHA256" \
       2>&1
   )" || { printf '%s\n' "$WRITE_OUTPUT" >&2; exit 1; }
   ACTIVE_PATH="$(printf '%s\n' "$WRITE_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["active_path"])')"
   ```

   The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files. Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

If `begin-active-write` reports chain-state recovery, ambiguity, lock, collision, or cleanup errors, **STOP** and report the helper error. Do not manually choose a chain state and do not write final content outside `write-active-handoff`.

8. **Verify and confirm (brief summary only):**
    - Check file exists and frontmatter is valid
    - Confirm briefly: "Summary saved: `<path>` — <title>"
    - **Do NOT** reproduce summary content or synthesis answers in chat. The file is the deliverable.

## Sections

| Section | Depth Target | Purpose |
|---------|-------------|---------|
| **Goal** | 5-10 lines | What we're working on, why, connection to project |
| **Session Narrative** | 20-40 lines | What happened — story with pivots, not a list of actions |
| **Decisions** | 10-15 lines per decision | Choice, driver, alternatives, trade-offs (4 elements) |
| **Changes** | 5-10 lines per file | Files modified/created with purpose and key details |
| **Codebase Knowledge** | 20-40 lines | Patterns, architecture, key locations with file:line |
| **Learnings** | 5-10 lines per item | Insights, gotchas, surprising discoveries |
| **Next Steps** | 5-10 lines per item | What to do next — includes dependencies, blockers, open questions |
| **Project Arc** | 20-50 lines | Where the project stands across sessions |

### Project Arc Elements

| Element | Description |
|---------|-------------|
| **Accomplishments** | What's been completed across the project arc — not just this session |
| **Current position** | Where we are — what phase, what milestone |
| **What's ahead** | Remaining work, upcoming milestones, known future decisions |
| **Load-bearing decisions** | Key decisions from prior sessions still governing the work |
| **Accumulated understanding** | Mental model, architecture insights, constraints from multiple sessions |
| **Drift risks** | Things easy to forget — subtle constraints, rejected approaches, scope boundaries |
| **Downstream impacts** | Things done this session that necessitate changes elsewhere |

## Verification

After creating summary, verify:

- [ ] File exists at `<project_root>/.codex/handoffs/YYYY-MM-DD_HH-MM_summary-<slug>.md`
- [ ] Frontmatter parses as valid YAML
- [ ] Required fields present and non-blank: date, time, created_at, session_id, project, title, type (hook-enforced)
- [ ] All 8 required sections present (hook-enforced)
- [ ] At least 1 of {Decisions, Changes, Learnings} has substantive content (hook-enforced)
- [ ] Body line count 120-250 (hook-enforced)
- [ ] Project Arc contains arc context, not just session context

**Quick check:** Confirm `ACTIVE_PATH` exists under `<project_root>/.codex/handoffs/`.

## Anti-Patterns

| Avoid | Why | Instead |
|-------|-----|---------|
| Using summary for complex sessions | Loses 8-element decision depth and full narrative | Use `/save` |
| Skipping arc context gathering | Defeats the primary purpose — arc awareness | Always scan archive and git before writing |
| Writing Project Arc as a digest of prior handoffs | Arc is a synthesis of project state, not a handoff summary | Answer "where does the project stand?" not "what happened before?" |
| Exceeding 250 lines | Drifting toward full handoff territory | If content demands it, switch to `/save` |
| Reproducing content in chat | File is the deliverable | Brief confirmation only |
| Full 8-element decision analysis | That's `/save`'s job | 4 elements: choice, driver, alternatives, trade-offs |

## Troubleshooting

### Summary file not created

**Symptoms:** `/summary` completes but no file appears at `<project_root>/.codex/handoffs/`

**Likely causes:**
- Permission denied on project `.codex/` directory
- Project root couldn't be determined (not in git, ambiguous directory)

**Next steps:**
1. Check the operation-state JSON returned by `begin-active-write`
2. Retry with `write-active-handoff` if content was generated and the operation state is still pending
3. If permissions block `.codex/handoffs/`, report the helper error

### Summary body exceeds 250 lines

**Symptoms:** Hook warns about line count

**Likely causes:**
- Session was more complex than expected
- Sections exceeded depth targets

**Next steps:**
- This is a warning, not an error — the summary is still valid
- Consider whether this session warranted a full `/save` instead
- If depth is justified, the warning can be accepted

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `save` | For deeper capture: complex sessions, design work, pivots |
| `quicksave` | For lighter capture: context pressure, quick state dump |
| `load` | Complementary: summary creates, load resumes |
