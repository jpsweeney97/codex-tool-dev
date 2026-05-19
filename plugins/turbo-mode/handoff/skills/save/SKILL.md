---
name: save
description: Use when user says "wrap this up", "new session", "almost out of context", "save", "next session", or "handoff"; use when stopping work with context to preserve.
---

# Save

Create a comprehensive handoff at `<project_root>/.codex/handoffs/`. Use this for real session boundaries where future Codex needs decisions, file context, risks, and next steps without re-exploration.

Read these only when needed:
- [handoff-contract.md](../../references/handoff-contract.md) for frontmatter, chain protocol, storage conventions.
- [format-reference.md](../../references/format-reference.md) for required handoff sections.
- [synthesis-guide.md](synthesis-guide.md) for the full internal synthesis prompts.
- [skill-details.md](../../references/skill-details.md) for examples, anti-patterns, and troubleshooting.

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files. Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

## Use

- Use for `/save`, `/save <title>`, "wrap this up", "new session", "save", or "handoff".
- Skip trivial sessions with no decisions, changes, gotchas, or next steps unless the user explicitly wants a handoff.
- Do not use to resume prior work; use `load`.
- If active-writer reservation or write fails, report the helper error and STOP. Do not write the final handoff manually or fall back to `docs/handoffs/`.

## Procedure

1. Generate a fresh UUID for `session_id`.
2. Read `synthesis-guide.md` completely. Answer every applicable synthesis prompt internally; do not show those answers in chat.
3. Gather session context, current git branch/commit when available, and the files that should appear in frontmatter `files:`.
4. Select sections from [format-reference.md](../../references/format-reference.md). Include all required handoff sections; use brief placeholders only when a section genuinely does not apply.
5. Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. The literal `python` command must resolve to Python >=3.11.
6. Reserve the final path before writing content:

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

7. Generate complete markdown in a temporary content file, not `ALLOCATED_ACTIVE_PATH`. Include `type: handoff`; if `RESUMED_FROM` is non-empty, include `resumed_from: "$RESUMED_FROM"`.

   ```bash
   CONTENT_FILE="$(mktemp)"
   # Write the complete markdown body to "$CONTENT_FILE" before committing it.
   CONTENT_SHA256="$(python -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$CONTENT_FILE")"
   ```

8. Commit the content through the active writer:

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

9. Verify the file exists under `<project_root>/.codex/handoffs/`, frontmatter parses, required fields are present, and required sections are present.
10. Reply only with `Handoff saved: <path> - <title>`. Do not reproduce handoff content or synthesis answers in chat.
