---
name: save
description: Use when user says "wrap this up", "new session", "almost out of context", "save", "next session", or "handoff"; use when stopping work with context to preserve.
allowed-tools: Write, Read, Edit, Glob, Grep, Bash
---

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema, chain protocol, storage conventions.

# Save

Create comprehensive session reports that preserve the full context future Codex needs to continue without re-exploration.

**Core Promise:** One action to save (`/save`).

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

## When to Use

- User explicitly runs `/save` or `/save <title>`
- User says signal phrases: "wrap this up", "new session", "save", "handoff"
- Session contains at least one of: decision made, file changed, gotcha discovered, next step identified
- User is stopping work and wants to resume later with context

## When NOT to Use

- Session was trivial (quick Q&A with no decisions, changes, or learnings)
- User explicitly declines handoff offer
- Context is already captured elsewhere (PR description, committed docs, issue tracker)
- Session is exploratory research with no actionable next steps
- **Resuming from a handoff** — use the `load` skill instead

**Non-goals (this skill does NOT):**
- Resume from handoffs (that's the `load` skill)
- Replace proper documentation (handoffs are ephemeral, docs are permanent)
- Reproduce the raw conversation transcript — but decisions, reasoning chains, codebase knowledge, and user preferences should be captured with enough depth and evidence to be fully actionable
- Work across different machines (handoffs are local to the project directory)

**STOP:** If unclear whether session has meaningful content, ask: "Should I create a handoff? This session seems light on decisions/changes."

## Inputs

**Required:**
- Session context (gathered from conversation history)

**Optional:**
- `title` argument for `/save <title>` — if omitted, Codex generates a descriptive title

**Constraints/Assumptions:**

| Assumption | Required? | Fallback |
|------------|-----------|----------|
| Git repository | No | Omit `branch` and `commit` fields from frontmatter |
| Write access to `<project_root>/.codex/handoffs/` | Yes | **STOP** and report the active-writer error. Do not write to `docs/handoffs/` as a fallback. |
| Project root determinable | No | Use current directory; if ambiguous, ask user |

**STOP:** If active-writer reservation or write fails, report the helper error and do not write the final handoff manually.

## Outputs

**Artifacts:**
- Markdown file at `<project_root>/.codex/handoffs/YYYY-MM-DD_HH-MM_save-<slug>.md`
- Frontmatter with session metadata (date, time, created_at, project, title, files)
- Body with all 13 required sections (placeholder content when not applicable)

**Definition of Done:**

| Check | Expected |
|-------|----------|
| File exists at expected path | `write-active-handoff` returns `status=completed` and `active_path` under `<project_root>/.codex/handoffs/` |
| Frontmatter parses as valid YAML | No YAML syntax errors |
| Required fields present | `date`, `time`, `created_at`, `session_id`, `project`, `title`, `type` all have values |
| Body line count | >=400 for all sessions, >=500 for complex |
| Decision depth | Every decision has all 8 elements (choice, driver, alternatives, rejection reasons, trade-offs, confidence, reversibility, change triggers) |
| Evidence density | Every factual claim has file:line, quote, or output reference |
| Codebase knowledge | All files explored are listed with patterns, architecture, and key locations |
| Session narrative | Exploration arc told chronologically with pivots and triggers |
| User preferences | Captured with verbatim quotes; corrections and push-back included |
| Resumption readiness | Future Codex could continue without re-reading any file explored this session |

**Quick check:** After writing, verify file exists and contains the title. If missing, check write permissions and path.

## Commands

| Command | Action |
|---------|--------|
| `/save` | Create handoff (Codex generates title) |
| `/save <title>` | Create handoff with specified title |

## Decision Points

1. **Signal phrase detected:**
   - If user says "wrap this up", "new session", "save", or "handoff", then offer: "Create a handoff before ending?"
   - If user declines, **STOP**. Do not re-prompt or proceed.

2. **Session content assessment:**
   - If session contains at least one of: decision made, file changed, gotcha discovered, next step identified, then proceed with handoff.
   - Otherwise, ask: "This session seems light — create a handoff anyway, or skip?"

3. **Git repository detection:**
   - If `.git/` directory exists in current or parent directories, then include `branch` and `commit` in frontmatter.
   - Otherwise, omit `branch` and `commit` fields entirely (don't use placeholders).

4. **Timestamp generation:**
   - Generate `created_at` as ISO 8601 UTC timestamp (e.g., `2026-01-12T14:30:00Z`)
   - Use the current time when the handoff is created

5. **Active-writer reservation:**
   - Use `begin-active-write` for storage permission, collision, lock, and chain-state checks.
   - If reservation fails, **STOP** and report the helper error. Do not probe by manually creating files under a handoff directory.

## Procedure

When user runs `/save [title]` or confirms a signal phrase offer:

1. **Check prerequisites:**
   - If session appears trivial (no decisions, changes, or learnings), ask: "This session seems light — create a handoff anyway?"
   - If user declines, **STOP**. Do not proceed.

2. **Generate a session ID** as a fresh UUID for this handoff.

3. **Complete the synthesis process (INTERNAL — do not output to chat):**
   - YOU MUST read [synthesis-guide.md](synthesis-guide.md) completely before proceeding
   - Answer every applicable synthesis prompt in the guide
   - This is not optional — do not skip to filling sections
   - The synthesis prompts are THINKING; the handoff sections are OUTPUT
   - **IMPORTANT:** The synthesis work is internal reasoning. Do NOT present synthesis answers in chat. Only the final handoff file is the deliverable.

4. **Gather context** from the session (informed by your synthesis work)

5. **Select relevant sections** using the checklist in [format-reference.md](../../references/format-reference.md)
   - If no sections have content, **STOP** and ask: "I don't see anything to hand off. What should I capture?"
   - Include all 13 required sections. Use brief placeholder content (e.g., "No risks identified this session.") for sections that genuinely don't apply
   - **Calibration:** Distinguish verified facts (explicitly discussed) from inferred conclusions (reasonable next steps) from assumed context (background not verified this session)

5b. **Depth check before writing:**
   - Verify all 13 required sections present: Goal, Session Narrative, Decisions, Changes, Codebase Knowledge, Context, Learnings, Next Steps, In Progress, Open Questions, Risks, References, Gotchas
   - Verify each Decision entry has all 8 elements from the synthesis prompts
   - Estimate body line count — target 400-700 depending on session complexity
   - If estimate is under 400, you are almost certainly under-capturing. Re-examine: implicit decisions, codebase knowledge gained, conversation dynamics, exploration arc, files read that produced understanding.
   - **Default to inclusion.** If you're unsure whether something belongs, include it.

6. **Reserve output path:**
   - Resolve project root: `$(git rev-parse --show-toplevel)` (falls back to cwd if not in a git repo)
   - Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin version root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"`. The literal `python` command must resolve to Python >=3.11.
   - Run `begin-active-write` with `--operation save` before generating final markdown. Pass `--slug` only when a title-specific slug was chosen; otherwise let the helper bind the default slug. Use its `allocated_active_path` as the only final destination.
   - If the returned JSON field `resumed_from_path` is non-empty, include `resumed_from: <resumed_from_path>` in frontmatter.
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
       --operation save \
       "${SLUG_ARGS[@]}" \
       2>&1
   )" || { printf '%s\n' "$BEGIN_OUTPUT" >&2; exit 1; }
   OPERATION_STATE_PATH="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["operation_state_path"])')"
   ALLOCATED_ACTIVE_PATH="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["allocated_active_path"])')"
   RESUMED_FROM="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; value=json.load(sys.stdin).get("resumed_from_path"); print(value or "")')"
   ```

7. **Generate markdown** with frontmatter per [format-reference.md](../../references/format-reference.md) and [handoff-contract.md](../../references/handoff-contract.md):
   - Include `session_id:` with the generated UUID from step 2
   - Include `type: handoff` in frontmatter
   - If `RESUMED_FROM` was set by `begin-active-write`, include `resumed_from: "$RESUMED_FROM"`
   - Write generated markdown to a temporary content file, not to `ALLOCATED_ACTIVE_PATH`; `write-active-handoff` owns the final write.
   ```bash
   CONTENT_FILE="$(mktemp)"
   # Write the complete markdown body to "$CONTENT_FILE" before committing it.
   CONTENT_SHA256="$(python -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$CONTENT_FILE")"
   ```
   - Use fallbacks for optional fields (see Inputs → Constraints/Assumptions)

8. **Commit file** through the active writer:

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

10. **Verify and confirm (brief summary only):**
    - Check file exists and frontmatter is valid
    - Confirm briefly: "Handoff saved: `<path>` — <title>"
    - **Do NOT** reproduce handoff content or synthesis answers in chat. The file is the deliverable.

## Verification

After creating handoff, verify:

- [ ] File exists at `<project_root>/.codex/handoffs/YYYY-MM-DD_HH-MM_save-<slug>.md`
- [ ] Frontmatter parses as valid YAML
- [ ] Required fields present and non-blank: date, time, created_at, session_id, project, title, type (hook-enforced)
- [ ] All 13 required sections present (hook-enforced)
- [ ] At least 1 of {Decisions, Changes, Learnings} has substantive content (hook-enforced)
- [ ] Body line count >= 400 (hook-enforced)

**Quick check:** Confirm `ACTIVE_PATH` exists under `<project_root>/.codex/handoffs/`. If not, check the `write-active-handoff` error.

**If verification fails:** Do not report success. Check Troubleshooting section and resolve before confirming.

## Troubleshooting

### Handoff file not created

**Symptoms:** `/save` completes but no file appears at `<project_root>/.codex/handoffs/`

**Likely causes:**
- Permission denied on project `.codex/` directory
- Project root couldn't be determined (not in git, ambiguous directory)
- Disk full or path too long

**Next steps:**
1. Check the operation-state JSON returned by `begin-active-write`
2. Retry with `write-active-handoff` if content was generated and the operation state is still pending
3. If permissions block `.codex/handoffs/`, report the helper error
4. If project root undetermined, ask user to specify

### Handoff content missing key decisions

**Symptoms:** Resumed handoff lacks important context from original session

**Likely causes:**
- Handoff created too early (before key decisions made)
- Section checklist didn't capture all relevant categories
- Session had implicit decisions not stated explicitly

**Next steps:**
1. Review session history for decisions made after handoff
2. Create new handoff with more complete context
3. Do not edit committed active-writer output in place; create a replacement handoff if the saved content is materially incomplete

## Anti-Patterns

| Avoid | Why | Instead |
|-------|-----|---------|
| Handoff for trivial sessions | Noise accumulation | Skip if no meaningful decisions/progress |
| Listing files without purpose or detail | Future Codex can't act on bare filenames | Each file gets purpose, approach, and key implementation details |
| Single-sentence decisions | Missing reasoning makes decisions non-actionable | Every decision needs: choice, driver, alternatives, trade-offs, confidence, implications |
| Handoffs under 400 lines | Indicates significant information loss | Re-examine session for under-capture — implicit decisions, codebase knowledge, conversation dynamics |
| Paraphrasing user preferences | Paraphrase loses nuance that makes preferences actionable | Use verbatim quotes for every user preference and correction |
| Missing decisions/rationale | Just listing changes isn't useful | Always capture at least one "why" |
| Re-prompting after user declines | Annoying, ignores user intent | Respect "no" and move on |
| Guessing when uncertain | May create useless handoff | Ask user if handoff is needed |

## Quality Calibration

| Complexity | Target Lines | Required Sections |
|------------|-------------|-------------------|
| All sessions | 400+ | All 13 required (hook-enforced): Goal, Session Narrative, Decisions, Changes, Codebase Knowledge, Context, Learnings, Next Steps, In Progress, Open Questions, Risks, References, Gotchas |
| Moderate (decisions, exploration) | 500+ | Above + Conversation Highlights, User Preferences (quality targets, not hook-enforced) |
| Complex (pivots, design work, discovery) | 500-700+ | All sections fully populated, including Rejected Approaches (quality targets, not hook-enforced) |

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `load` | Complementary: save creates, load resumes |
