---
name: quicksave
description: Used when user runs /quicksave to save session state quickly under context pressure. Fast, lightweight alternative to /save. Use when user says "quicksave", "checkpoint", "save state", "quick save", or is running low on context.
allowed-tools: Write, Read, Bash
---


# Quicksave

Fast state capture for context-pressure session cycling. Produces 22-55 line documents — the minimum needed to resume without re-exploration.

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema, chain protocol (state file read/write/cleanup), storage conventions. Follow the contract exactly.

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `docs/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

## When to Use

- User runs `/quicksave` or `/quicksave <title>`
- User says "save state", "quick save", "quicksave", or "checkpoint"
- Session is under context pressure and needs to cycle

## When NOT to Use

- **Full knowledge capture needed** — use `/save` instead
- **Natural stopping point** (PR merged, plan written) — use `/save` instead
- **Session was trivial** — skip

## Procedure

1. **Check prerequisites:**
   - Determine project name per [handoff-contract.md](../../references/handoff-contract.md) (git root name or cwd name).
   - Verify `<project_root>/docs/handoffs/` is writable. If not writable and cannot be created, **STOP** per contract Write Permission section.
   - If session has no work done (no files read, no changes, no progress), ask: "Nothing to quicksave — create one anyway?"
   - If user declines, **STOP**.

2. **Generate a session ID** as a fresh UUID for this checkpoint.

3. **Answer the 4 synthesis prompts (INTERNAL — do not output):**
   - What am I in the middle of right now? → Current Task + In Progress
   - What should I do first on resume? → Next Action + Verification Snapshot
   - What failed or surprised me? → Don't Retry + Key Finding (if applicable)
   - Were any decisions made? → Decisions (if applicable)

4. **Check state file** per chain protocol in [handoff-contract.md](../../references/handoff-contract.md):
   - Read `<project_root>/docs/handoffs/.session-state/handoff-<project>-<resume_token>.json` with `session_state.py`.
   - If state exists, set `resumed_from` to its archive path.
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

5. **Check consecutive checkpoint count via chain walk:**
   - Initialize `prior_checkpoint_count = 0`
   - If `resumed_from` was set in step 4, read the archived file it points to
   - Check its `type:` frontmatter field. If `checkpoint`, increment `prior_checkpoint_count` and follow its `resumed_from` (if present)
   - Stop at first `type: handoff`, missing `type`, missing file, or `prior_checkpoint_count >= 2`
   - Walk the `resumed_from` chain; do not scan the active directory (archived files are not in it)
   - If `resumed_from` was NOT set (no state file — e.g., TTL race, first checkpoint of session): skip the guardrail. Emit no warning — lack of state file is not evidence of checkpoint streaking.
   - If `prior_checkpoint_count >= 2`: prompt "Detected 2 prior checkpoints; this would be your 3rd consecutive checkpoint. Consider /save to capture decisions, codebase knowledge, and session narrative before they decay. Continue with quicksave anyway?"
   - If user wants full handoff, **STOP** and suggest they run `/save`.
   - **Scope limitation:** The guardrail only detects consecutive checkpoints within a single resume chain (connected via `resumed_from`). Cross-session checkpoints without `/load` between them do not trigger the guardrail.

6. **Write file** to `<project_root>/docs/handoffs/YYYY-MM-DD_HH-MM_checkpoint-<slug>.md`
   - Use frontmatter from [handoff-contract.md](../../references/handoff-contract.md) with `type: checkpoint`
   - Title: `"Checkpoint: <descriptive-title>"`
   - Populate frontmatter `files:` from file paths listed in the Active Files section
   - Required sections (5) are always included — use placeholder content for thin sessions (e.g., "No commands run yet" for Verification Snapshot). Conditional sections (3) are omitted when not applicable.

   The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files. Whether `docs/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

7. **Cleanup state file** per chain protocol:
   - Clear state after a successful checkpoint:
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

8. **Verify:** Confirm file exists and frontmatter is valid (required fields present per contract). Report: "Quicksave saved: `<path>`"
   - Do NOT reproduce content in chat. The file is the deliverable.

## Sections

| Section | Required? | Depth | Purpose |
|---------|-----------|-------|---------|
| **Current Task** | Yes | 3-5 lines | What we're working on and why |
| **In Progress** | Yes | 5-15 lines | Approach, working/broken, immediate next action |
| **Active Files** | Yes | 2-10 lines | Files modified or key files read, with purpose |
| **Next Action** | Yes | 2-5 lines | The literal next thing to do on resume |
| **Verification Snapshot** | Yes | 1-3 lines | Last command/test and result |
| **Don't Retry** | If applicable | 1-3 lines/item | "Tried X, failed because Y" |
| **Key Finding** | If applicable | 2-5 lines | Codebase discovery worth preserving |
| **Decisions** | If applicable | 3-5 lines/decision | Choice + driver only |

**Output target:** 22-55 lines body. If exceeding ~80 lines, note: "This quicksave is getting long. Consider `/save` for a full capture."

## Anti-Patterns

| Avoid | Why | Instead |
|-------|-----|---------|
| Writing session narrative | Too expensive under context pressure | Capture state, not story |
| Full decision analysis (8 elements) | That's /save's job | Choice + driver only |
| Codebase knowledge dumps | Quicksave isn't a knowledge base | Key findings only |
| Reproducing content in chat | File is the deliverable | Brief confirmation only |

## Troubleshooting

### File not created

**Symptoms:** Quicksave command completes but no file appears

**Likely causes:**
- Project name detection failed (not in a git repo, ambiguous directory)
- Write permission denied on `<project_root>/docs/handoffs/`

**Next steps:**
1. Check project detection: `git rev-parse --show-toplevel 2>/dev/null || pwd`
2. Check permissions: `ls -la "$(git rev-parse --show-toplevel)/docs/handoffs/"`
3. Create directory manually if needed: `mkdir -p "$(git rev-parse --show-toplevel)/docs/handoffs"`

### Missing resumed_from

**Symptoms:** Checkpoint has no `resumed_from` field after resuming

**Likely causes:**
- State file expired (>24 hours, pruned by cleanup.py)
- Previous session crashed before writing state file

**Next steps:**
- This is informational — the chain link is skipped. No data loss. See contract Known Limitations: State-file TTL race.
