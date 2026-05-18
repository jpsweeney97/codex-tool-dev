---
name: load
description: Use when continuing from a previous session, when user runs `/load` to load the most recent handoff, or when user runs `/load <path>` for a specific handoff.
allowed-tools: Write, Read, Edit, Glob, Grep, Bash
---

# Load

Resume work from an existing Handoff artifact. Loading may archive or copy the selected handoff and writes resume state under `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`.

Read these only when needed:
- [handoff-contract.md](../../references/handoff-contract.md) for frontmatter, chain protocol, and type semantics.
- [format-reference.md](../../references/format-reference.md) for document content expectations.
- [skill-details.md](../../references/skill-details.md) for storage details, anti-patterns, and troubleshooting.

## Use

- Use for `/load`, `/load <path>`, "continue from where we left off", or "pick up where I stopped".
- Do not create handoffs; use `save`, `summary`, or `quicksave`.
- If no eligible handoff exists, report "No handoffs found for this project" and STOP.
- If a provided path does not exist, report `Handoff not found at <path>` and STOP.

## Procedure

1. Define project paths:

   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PROJECT_NAME="$(basename "$PROJECT_ROOT")"
   ```

2. Resolve plugin root before running helpers. Set `PLUGIN_ROOT` to the plugin root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. The literal `python` command must resolve to Python >=3.11.

3. Run the load transaction.

   For implicit `/load`:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/load_transactions.py" \
     load \
     --project-root "$PROJECT_ROOT" \
     --project "$PROJECT_NAME"
   ```

   For explicit `/load <path>`:

   ```bash
   SOURCE_PATH="/absolute/path/from-user"
   PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/load_transactions.py" \
     load \
     --project-root "$PROJECT_ROOT" \
     --project "$PROJECT_NAME" \
     --explicit-path "$SOURCE_PATH"
   ```

   The command emits JSON with `transaction_id`, `transaction_path`, `source_path`, `archive_path`, `state_path`, and `storage_location`. If it exits non-zero, report stderr and STOP. Do not delete transaction, lock, or recovery-claim files unless the operator explicitly confirms the diagnostic repair path.

4. Read handoff content from the returned `archive_path`, not from the original source. Primary active handoffs may have been moved to `<project_root>/.codex/handoffs/archive/<filename>`.
5. Display the full handoff/checkpoint/summary content, note its type, summarize goal/current task, decisions, and next steps, then offer the first next action.

## List

For `/list-handoffs`, use the same setup and run:

```bash
PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/list_handoffs.py" \
  --project-root "$PROJECT_ROOT"
```

If `total` is `0`, report "No handoffs found for this project" and STOP. Otherwise present a table with date, title, type, branch, storage location, and path.

## Recovery Boundaries

- Readable pending load transactions are recovered before a new load is selected.
- Unreadable or corrupt transaction records block `/load` with a global fail-closed diagnostic because the project field is inside the JSON payload.
- A `recovery claim file present` diagnostic requires operator review before cleanup.
- A `stale lock from another host` diagnostic requires operator review of lock metadata before cleanup.
- Legacy sources are not deleted by load; reviewed legacy active handoffs are copied into primary storage and marked consumed.

## Done

- Handoff content is displayed to the user.
- Transaction JSON includes `archive_path`, `state_path`, and `storage_location`.
- State file exists at `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`.
- The response names whether this is a checkpoint, summary, or handoff and offers a concrete continuation prompt.
