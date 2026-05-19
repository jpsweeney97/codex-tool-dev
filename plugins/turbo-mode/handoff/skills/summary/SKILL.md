---
name: summary
description: Session summary with project arc context. Use when a full /save is overkill but /quicksave would lose decisions, codebase knowledge, and session narrative. Captures session context at moderate depth (120-250 lines) and synthesizes the project arc across sessions to prevent drift.
---

# Summary

Create a moderate-depth session summary at `<project_root>/.codex/handoffs/`: more durable than `/quicksave`, lighter than `/save`.

Read these only when needed:
- [handoff-contract.md](../../references/handoff-contract.md) for frontmatter, chain protocol, storage conventions.
- [skill-details.md](../../references/skill-details.md) for section depth targets, anti-patterns, and troubleshooting.

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files. Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

## Use

- Use for `/summary`, `/summary <title>`, or a user request to summarize a meaningful session.
- Prefer `/save` for complex sessions with deep decisions, pivots, or design work.
- Prefer `/quicksave` for context pressure when a fast checkpoint is enough.
- Skip trivial sessions unless the user explicitly wants a summary.
- If active-writer reservation or write fails, report the helper error and STOP. Do not write the final summary manually or fall back to `docs/handoffs/`.

## Procedure

1. Generate a fresh UUID for `session_id`.
2. Gather current conversation context, relevant archived handoff titles/dates from `<project_root>/.codex/handoffs/archive/`, and recent git history.
3. Internally synthesize: goal, session narrative, decisions, changes, codebase knowledge, learnings, next steps, and project arc. Do not show synthesis answers in chat.
4. Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. The literal `python` command must resolve to Python >=3.11.
5. Reserve the final path before writing content:

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

6. Generate complete markdown in a temporary content file, not `ALLOCATED_ACTIVE_PATH`. Include `type: summary`; if `RESUMED_FROM` is non-empty, include `resumed_from: "$RESUMED_FROM"`.

   ```bash
   CONTENT_FILE="$(mktemp)"
   # Write the complete markdown body to "$CONTENT_FILE" before committing it.
   CONTENT_SHA256="$(python -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$CONTENT_FILE")"
   ```

7. Commit the content through the active writer:

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

8. Verify `ACTIVE_PATH` exists under `<project_root>/.codex/handoffs/`, frontmatter parses, required fields are present, all eight summary sections are present, and the Project Arc is populated.
9. Reply only with `Summary saved: <path> - <title>`. Do not reproduce summary content or synthesis answers in chat.
