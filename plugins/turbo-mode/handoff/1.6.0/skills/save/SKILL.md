---
name: save
description: Used when user says "wrap this up", "new session", "almost out of context", "save", "next session", or "handoff"; when stopping work with context to preserve.
allowed-tools: Write, Read, Edit, Glob, Grep, Bash
---

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema, chain protocol, storage conventions.

# Save

Create comprehensive session reports that preserve the full context future Codex needs to continue without re-exploration.

**Core Promise:** One action to save (`/save`).

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `docs/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

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
| Write access to `<project_root>/docs/handoffs/` | Yes | **STOP** and ask for alternative path. If `docs/handoffs/` doesn't exist, create it with `mkdir -p`. |
| Project root determinable | No | Use current directory; if ambiguous, ask user |

**STOP:** If `<project_root>/docs/handoffs/` doesn't exist and cannot be created, ask: "I can't write to docs/handoffs/. Where should I save handoffs?"

## Outputs

**Artifacts:**
- Markdown file at `<project_root>/docs/handoffs/YYYY-MM-DD_HH-MM_<slug>.md`
- Frontmatter with session metadata (date, time, created_at, project, title, files)
- Body with all 13 required sections (placeholder content when not applicable)

**Definition of Done:**

| Check | Expected |
|-------|----------|
| File exists at expected path | `ls $(git rev-parse --show-toplevel)/docs/handoffs/YYYY-MM-DD_HH-MM_*.md` returns file |
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

5. **Write permission check:**
   - If `<project_root>/docs/handoffs/` is writable (or can be created), write handoff there.
   - Otherwise, **STOP** and ask: "Can't write to docs/handoffs/. Where should I save this handoff?"

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

6. **Determine output path:**
   - Resolve project root: `$(git rev-parse --show-toplevel)` (falls back to cwd if not in a git repo)
   - If `<project_root>/docs/handoffs/` is not writable, **STOP** and ask for alternative path

7. **Generate markdown** with frontmatter per [format-reference.md](../../references/format-reference.md) and [handoff-contract.md](../../references/handoff-contract.md):
   - Include `session_id:` with the generated UUID from step 2
   - Include `type: handoff` in frontmatter
   - Per chain protocol in [handoff-contract.md](../../references/handoff-contract.md): read `<project_root>/docs/handoffs/.session-state/handoff-<project>-<resume_token>.json` with `session_state.py`; if state exists, set `resumed_from` to its archive path
   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PROJECT_NAME="$(basename "$PROJECT_ROOT")"
   READ_STATE_OUTPUT="$(
     PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \
     uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py" \
       read-state \
       --state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \
       --project "$PROJECT_NAME" \
       --field state_path \
       2>&1
   )"
   READ_STATE_STATUS=$?
   case "$READ_STATE_STATUS" in
     0) STATE_PATH="$READ_STATE_OUTPUT" ;;
     1) STATE_PATH="" ;;
     2) printf '%s\n' "$READ_STATE_OUTPUT" >&2; exit 2 ;;
     *) printf '%s\n' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;
   esac
   READ_ARCHIVE_OUTPUT="$(
     PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \
     uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py" \
       read-state \
       --state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \
       --project "$PROJECT_NAME" \
       --field archive_path \
       2>&1
   )"
   READ_ARCHIVE_STATUS=$?
   case "$READ_ARCHIVE_STATUS" in
     0) RESUMED_FROM="$READ_ARCHIVE_OUTPUT" ;;
     1) RESUMED_FROM="" ;;
     2) printf '%s\n' "$READ_ARCHIVE_OUTPUT" >&2; exit 2 ;;
     *) printf '%s\n' "$READ_ARCHIVE_OUTPUT" >&2; exit "$READ_ARCHIVE_STATUS" ;;
   esac
   ```
   During the upgrade window, `read-state` also detects a legacy plain-text state file at `<project_root>/docs/handoffs/.session-state/handoff-<project>` and migrates it to `handoff-<project>-<resume_token>.json`.
   - Use fallbacks for optional fields (see Inputs → Constraints/Assumptions)

8. **Write file** to `<project_root>/docs/handoffs/YYYY-MM-DD_HH-MM_<slug>.md`

   The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files. Whether `docs/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

9. **Cleanup state file** per chain protocol in [handoff-contract.md](../../references/handoff-contract.md):
   - Clear the JSON state file after a successful write:
   ```bash
   if [ -n "$STATE_PATH" ]; then
     PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
     PYTHONDONTWRITEBYTECODE=1 \
     UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \
     uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py" \
       clear-state \
       --state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" \
       --state-path "$STATE_PATH"
   fi
   ```
   When `clear-state` receives a JSON state path, it best-effort clears both the JSON file and any matching legacy plain-text state file bridge.

If `read-state` exits 2, STOP and ask the user which concurrent resume chain to continue. Do not choose one automatically.
If `read-state` exits 1, keep `STATE_PATH` empty and skip `clear-state`.
If `clear-state` warns after the handoff file is already written, report the warning but do not fail save/quicksave/summary.

10. **Verify and confirm (brief summary only):**
    - Check file exists and frontmatter is valid
    - Confirm briefly: "Handoff saved: `<path>` — <title>"
    - **Do NOT** reproduce handoff content or synthesis answers in chat. The file is the deliverable.

## Verification

After creating handoff, verify:

- [ ] File exists at `<project_root>/docs/handoffs/YYYY-MM-DD_HH-MM_<slug>.md`
- [ ] Frontmatter parses as valid YAML
- [ ] Required fields present and non-blank: date, time, created_at, session_id, project, title, type (hook-enforced)
- [ ] All 13 required sections present (hook-enforced)
- [ ] At least 1 of {Decisions, Changes, Learnings} has substantive content (hook-enforced)
- [ ] Body line count >= 400 (hook-enforced)

**Quick check:** Run `ls "$(git rev-parse --show-toplevel)/docs/handoffs/"` and confirm new file appears. If not, check write permissions.

**If verification fails:** Do not report success. Check Troubleshooting section and resolve before confirming.

## Troubleshooting

### Handoff file not created

**Symptoms:** `/save` completes but no file appears at `<project_root>/docs/handoffs/`

**Likely causes:**
- Permission denied on project `docs/` directory
- Project root couldn't be determined (not in git, ambiguous directory)
- Disk full or path too long

**Next steps:**
1. Check if `docs/handoffs/` exists: `ls -la "$(git rev-parse --show-toplevel)/docs/handoffs/"`
2. Check write permissions: `touch "$(git rev-parse --show-toplevel)/docs/handoffs/test" && trash "$(git rev-parse --show-toplevel)/docs/handoffs/test"`
3. If permissions issue, ask user for alternative path
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
3. Consider adding to existing handoff manually if file still accessible

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
