---
name: quicksave
description: Used when user runs /quicksave to save session state quickly under context pressure. Fast, lightweight alternative to /save. Use when user says "quicksave", "checkpoint", "save state", "quick save", or is running low on context.
allowed-tools: Write, Read, Bash
---


# Quicksave

Fast state capture for context-pressure session cycling. Produces 22-55 line documents — the minimum needed to resume without re-exploration.

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema and storage conventions. Use the active-writer protocol below for reservation, chain-state bridging, final write, and cleanup.

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

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
   - Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin version root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"`. The literal `python` command must resolve to Python >=3.11.
   - If session has no work done (no files read, no changes, no progress), ask: "Nothing to quicksave — create one anyway?"
   - If user declines, **STOP**.

2. **Generate a session ID** as a fresh UUID for this checkpoint.

3. **Answer the 4 synthesis prompts (INTERNAL — do not output):**
   - What am I in the middle of right now? → Current Task + In Progress
   - What should I do first on resume? → Next Action + Verification Snapshot
   - What failed or surprised me? → Don't Retry + Key Finding (if applicable)
   - Were any decisions made? → Decisions (if applicable)

4. **Reserve output path:**
   - Run `begin-active-write` with `--operation quicksave` before generating final markdown. Pass `--slug` only when a title-specific slug was chosen; otherwise let the helper bind the default slug. Use its `allocated_active_path` as the only final destination.
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
       --operation quicksave \
       "${SLUG_ARGS[@]}" \
       2>&1
   )" || { printf '%s\n' "$BEGIN_OUTPUT" >&2; exit 1; }
   OPERATION_STATE_PATH="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["operation_state_path"])')"
   ALLOCATED_ACTIVE_PATH="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["allocated_active_path"])')"
   RESUMED_FROM="$(printf '%s\n' "$BEGIN_OUTPUT" | python -c 'import json,sys; value=json.load(sys.stdin).get("resumed_from_path"); print(value or "")')"
   ```

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

6. **Generate markdown** in a temporary content file:
   - Use frontmatter from [handoff-contract.md](../../references/handoff-contract.md) with `type: checkpoint`
   - Title: `"Checkpoint: <descriptive-title>"`
   - Populate frontmatter `files:` from file paths listed in the Active Files section
   - If `RESUMED_FROM` was set by `begin-active-write`, include `resumed_from: "$RESUMED_FROM"`
   - Required sections (5) are always included — use placeholder content for thin sessions (e.g., "No commands run yet" for Verification Snapshot). Conditional sections (3) are omitted when not applicable.
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

8. **Verify:** Confirm `ACTIVE_PATH` exists under `<project_root>/.codex/handoffs/` and frontmatter is valid (required fields present per contract). Report: "Quicksave saved: `<path>`"
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
- Write permission denied on `<project_root>/.codex/handoffs/`

**Next steps:**
1. Check project detection: `git rev-parse --show-toplevel 2>/dev/null || pwd`
2. Check the operation-state JSON returned by `begin-active-write`
3. Retry with `write-active-handoff` if content was generated and the operation state is still pending

### Missing resumed_from

**Symptoms:** Checkpoint has no `resumed_from` field after resuming

**Likely causes:**
- State file expired (>24 hours, pruned by cleanup.py)
- Previous session crashed before writing state file

**Next steps:**
- This is informational — the chain link is skipped. No data loss. See contract Known Limitations: State-file TTL race.
