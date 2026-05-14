---
name: load
description: Use when continuing from a previous session, when user runs `/load` to load the most recent handoff, or when user runs `/load <path>` for a specific handoff.
allowed-tools: Write, Read, Edit, Glob, Grep, Bash
---

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema, chain protocol, and type semantics. The runtime storage locations below are controlled by the storage-authority scripts during the handoff storage reversal.

# Load

Continue work from a previous handoff.

**Core Promise:** One action to resume (`/load`).

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether runtime handoff paths are tracked or ignored is host-repository policy, not a plugin invariant.

## When to Use

- User explicitly runs `/load` or `/load <path>`
- User says "continue from where we left off" or "pick up where I stopped"
- Starting a new session that should continue previous work

## When NOT to Use

- **Creating a new handoff** — use the `save` skill instead
- Session has no prior handoffs for this project
- User wants to start fresh without prior context

**Non-goals (this skill does NOT):**
- Create handoffs (that's the `save` skill)
- Auto-inject handoffs at session start (explicit load only)
- Suggest handoffs (user must request)
- Load the synthesis guide (not needed for load)

## Inputs

**Required:**
- Project context (determined from git root or current directory)

**Optional:**
- `path` argument for `/load <path>` — specific handoff to load

**Constraints/Assumptions:**

| Assumption | Required? | Fallback |
|------------|-----------|----------|
| Project name determinable | Yes | Ask user to specify |
| Handoff exists for project | No | Report "No handoffs found" |

## Outputs

**Artifacts:**
- Archived or copied handoff at `<project_root>/.codex/handoffs/archive/<filename>`
- State file at `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`
- Transaction record under `<project_root>/.codex/handoffs/.session-state/transactions/`

**Side Effects:**
- Primary active handoffs from `<project_root>/.codex/handoffs/*.md` are moved to `.codex/handoffs/archive/`
- Primary archive loads reuse the existing archive file
- Reviewed legacy active handoffs from `docs/handoffs/*.md` are copied to `.codex/handoffs/archive/` and marked consumed; the legacy source remains in place
- Explicit legacy archive loads from `docs/handoffs/archive/` or `.codex/handoffs/.archive/` are copied or reused through the copied-archive registry
- Readable pending load transactions are recovered before a new load is selected
- Unreadable or corrupt transaction records block `/load` with a global fail-closed operator diagnostic
- Context loaded into conversation

**Definition of Done:**

| Check | Expected |
|-------|----------|
| Handoff content displayed | User sees full handoff context |
| Load transaction completed | Command emits `archive_path`, `state_path`, and `storage_location` |
| State file created | Path recorded for next handoff's `resumed_from` |
| Next step offered | "Continue with [next step]?" |

## Commands

| Command | Action |
|---------|--------|
| `/load` | Load most recent eligible active handoff for this project |
| `/load <path>` | Load specific handoff by path |
| `/list-handoffs` | List eligible active handoffs for project |

## Decision Points

1. **Project detection:**
   - If in git repository: use git root directory name as project.
   - If not in git: use current directory name.
   - If project name is ambiguous or undeterminable: ask user to specify.

2. **Path argument provided:**
   - If path provided: validate it exists, then pass it to the load transaction.
   - If path doesn't exist: report "Handoff not found at <path>" and **STOP**.
   - If no path: let `load_transactions.py` select the first eligible active candidate from storage authority.

3. **Handoff availability:**
   - If eligible handoffs exist: load the first storage-authority candidate.
   - If no handoffs are eligible: report "No handoffs found for this project" and **STOP**.

4. **Interrupted load recovery:**
   - If a readable pending load transaction exists for this project, the load command completes recovery before selecting a new handoff.
   - Report the recovered `archive_path` and continue from that handoff.
   - If transaction JSON is unreadable or corrupt, report the stderr diagnostic and **STOP**. Transaction records share one state directory, so unreadable records are treated as global fail-closed until operator review.

## Procedure

### Load (`/load [path]`)

When user runs `/load [path]`:

1. **Define project paths:**
   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PROJECT_NAME="$(basename "$PROJECT_ROOT")"
   ```

2. **Resolve plugin root before running helpers.**
   Set `PLUGIN_ROOT` to the plugin version root, three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"`. The literal `python` command must resolve to Python >=3.11.

3. **Run the load transaction.**
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

   The command emits JSON with `transaction_id`, `transaction_path`, `source_path`, `archive_path`, `state_path`, and `storage_location`. If it exits non-zero, report the stderr message and **STOP**. Do not delete transaction, lock, or recovery-claim files unless the operator explicitly confirms the diagnostic repair path.

4. **Read handoff content from `archive_path`.**
   Use the `archive_path` returned by the transaction JSON. Do not read from the original source after mutation because primary active handoffs may have been moved.

5. **Display and summarize:**
   - Show full handoff/checkpoint/summary content
   - Note the type: "Resuming from **checkpoint**: ...", "Resuming from **summary**: ...", or "Resuming from **handoff**: ..."
   - Summarize key points: goal/current task, decisions, next steps/next action
   - Offer: "Continue with [first next step/action]?"

### List (`/list-handoffs`)

When user runs `/list-handoffs`:

1. **Define project paths and plugin root** using the same setup as `/load`.
2. **Run the storage-backed listing helper:**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/list_handoffs.py" \
     --project-root "$PROJECT_ROOT"
   ```
3. If `total` is `0`, report "No handoffs found for this project" and **STOP**.
4. Format `handoffs` as a table: date, title, type, branch, storage location, path.
   - `type` comes from frontmatter `type` field. If missing, display as `handoff` for backwards compatibility.

## Storage

Primary runtime storage:
- Active handoffs: `<project_root>/.codex/handoffs/`
- Archive: `<project_root>/.codex/handoffs/archive/`
- Resume state: `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`
- Load transactions: `<project_root>/.codex/handoffs/.session-state/transactions/`

Legacy read compatibility:
- Reviewed legacy active inputs may be read from `<project_root>/docs/handoffs/*.md`
- Explicit legacy archive inputs may be read from `<project_root>/docs/handoffs/archive/*.md`
- Previous hidden primary archives may be read from `<project_root>/.codex/handoffs/.archive/*.md`

Legacy sources are not deleted by load. Copies and registry records are written under primary `.codex/handoffs/` state.

See [format-reference.md](../../references/format-reference.md) for filename format and document content expectations. See [handoff-contract.md](../../references/handoff-contract.md) for frontmatter and chain metadata semantics.

## Background Cleanup

Handoff `1.6.0` does not ship plugin-bundled command hooks. State-file cleanup is handled by explicit handoff workflows, and the dormant cleanup helper is not a publication gate for this release:

1. Prunes state files older than 24 hours
2. Produces no output (no auto-inject, no prompts)

Handoffs and archives are not auto-pruned.

## Verification

After loading, verify:

- [ ] Handoff content displayed to user
- [ ] Transaction JSON includes `archive_path`, `state_path`, and `storage_location`
- [ ] State file exists at `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`
- [ ] Type displayed on load ("Resuming from **checkpoint**:", "Resuming from **summary**:", or "Resuming from **handoff**:")
- [ ] User offered continuation prompt

**Quick check:** `PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/list_handoffs.py" --project-root "$PROJECT_ROOT"` shows currently eligible active handoffs.

## Troubleshooting

### Load not finding handoff

**Symptoms:** `/load` says "No handoffs found" or finds wrong handoff

**Likely causes:**
- Handoff was already archived; use `/load <path>` with the archive path
- Running from different project directory than where handoff was created
- Legacy active handoff is not listed in the reviewed opt-in manifest
- Source is tracked in git and blocked by storage authority

**Next steps:**
1. Run `/list-handoffs` to see eligible active handoffs for current project
2. Check primary runtime storage directly: `<project_root>/.codex/handoffs/`
3. If found in archive, use `/load <full-path>`

### Load reports a pending transaction

**Symptoms:** `/load` resumes a handoff different from the one expected

**Likely causes:**
- A previous load was interrupted after mutating archive/state but before marking the transaction completed

**Next steps:**
1. Let the transaction command complete recovery
2. Read the returned `archive_path`
3. Continue from the recovered handoff before starting another load

### Load reports corrupt or unreadable transaction state

**Symptoms:** `/load` exits non-zero with "pending transaction record unreadable"

**Likely causes:**
- A transaction JSON file under `<project_root>/.codex/handoffs/.session-state/transactions/` is truncated, unreadable, or malformed
- Because the project field is inside the JSON payload, unreadable transaction records are global fail-closed and may block every project using this state directory

**Next steps:**
1. Report the exact `transaction_path` from stderr
2. Ask the operator to inspect the file before changing state
3. Retry `/load` only after the operator repairs or explicitly removes the corrupt record

### Load reports a recovery claim or foreign-host lock

**Symptoms:** `/load` exits non-zero with "recovery claim file present" or "stale lock from another host"

**Likely causes:**
- A prior stale-lock recovery crashed after creating a `.recovery` claim file
- The lock was created under a different hostname, or this machine's hostname changed

**Next steps:**
1. Report the exact claim or lock path from stderr
2. Ask the operator to confirm no process is actively recovering the lock
3. For `recovery claim file present`, follow the emitted `trash <claim_path>` command only after operator confirmation
4. For `stale lock from another host`, require operator review of the lock metadata before any cleanup

### State file not created

**Symptoms:** Next handoff missing `resumed_from` field

**Likely causes:**
- Permission denied on `<project_root>/.codex/handoffs/.session-state/`
- Session ended before the transaction completed

**Next steps:**
1. Check if `<project_root>/.codex/handoffs/.session-state/` exists
2. Re-run `/load`; readable pending transactions are recovered before new selection, while unreadable records stop with an operator diagnostic

## Anti-Patterns

| Avoid | Why | Instead |
|-------|-----|---------|
| Auto-injecting handoffs | Stale handoffs clutter unrelated sessions | Explicit `/load` only |
| Suggesting old handoffs | Context may be irrelevant | User decides when to load |
| Loading synthesis guide | Not needed for load, wastes context | Load skill is lightweight |
| Modifying handoff content | Handoffs are immutable snapshots | Create new handoff if needed |
| Hand-editing resume state | Breaks transaction recovery | Use `load_transactions.py` |

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `save` | Complementary: save creates, load resumes |
