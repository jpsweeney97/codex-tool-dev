---
name: quicksave
description: Used when user runs /quicksave to save session state quickly under context pressure. Fast, lightweight alternative to /save. Use when user says "quicksave", "checkpoint", "save state", "quick save", or is running low on context.
allowed-tools: Write, Read, Bash
---

# Quicksave

Create a fast checkpoint at `<project_root>/.codex/handoffs/` so the next session can resume without re-exploration.

Read these only when needed:
- [handoff-contract.md](../../references/handoff-contract.md) for frontmatter, chain protocol, storage conventions.
- [skill-details.md](../../references/skill-details.md) for section targets, anti-patterns, and troubleshooting.

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files. Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

## Use

- Use for `/quicksave`, `/quicksave <title>`, "checkpoint", "save state", "quick save", or context pressure.
- Prefer `/save` for a natural stopping point, deep decisions, or full session narrative.
- If there was no work, ask whether to create a checkpoint anyway.
- If active-writer reservation or write fails, report the helper error and STOP. Do not write final content outside the active writer.

## Procedure

1. Generate a fresh UUID for this checkpoint.
2. Internally answer: current task, in-progress state, next action, verification snapshot, surprises, and decisions. Do not output synthesis answers.
3. Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. The literal `python` command must resolve to Python >=3.11.
4. Reserve the final path before writing content:

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

5. If `RESUMED_FROM` is non-empty, walk its chain only far enough to detect two prior consecutive checkpoints. At two prior checkpoints, ask whether to continue or switch to `/save`.
6. Generate checkpoint markdown in a temporary content file, not `ALLOCATED_ACTIVE_PATH`. Include `type: checkpoint`; if `RESUMED_FROM` is non-empty, include `resumed_from: "$RESUMED_FROM"`.

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

8. Verify `ACTIVE_PATH` exists under `<project_root>/.codex/handoffs/` and required frontmatter fields are present.
9. Reply only with `Quicksave saved: <path>`. Do not reproduce checkpoint content in chat.
