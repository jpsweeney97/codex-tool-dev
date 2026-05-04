---
name: load
description: Used when continuing from a previous session; when user runs `/load` to load the most recent handoff, or `/load <path>` for a specific handoff.
allowed-tools: Write, Read, Edit, Glob, Grep, Bash
---

**Read [handoff-contract.md](../../references/handoff-contract.md) for:** frontmatter schema, chain protocol, storage conventions.

# Load

Continue work from a previous handoff.

**Core Promise:** One action to resume (`/load`).

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
- Archived handoff at `<project_root>/docs/handoffs/archive/<filename>`
- State file at `<project_root>/docs/handoffs/.session-state/handoff-<project>`

**Side Effects:**
- Original handoff moved to archive
- Context loaded into conversation

**Definition of Done:**

| Check | Expected |
|-------|----------|
| Handoff content displayed | User sees full handoff context |
| Original archived | File moved to `archive/` |
| State file created | Path recorded for next handoff's `resumed_from` |
| Next step offered | "Continue with [next step]?" |

## Commands

| Command | Action |
|---------|--------|
| `/load` | Load most recent handoff for this project |
| `/load <path>` | Load specific handoff by path |
| `/list-handoffs` | List available handoffs for project |

## Decision Points

1. **Path argument provided:**
   - If path provided: validate file exists, then use that specific handoff.
   - If path doesn't exist: report "Handoff not found at <path>" and **STOP**.
   - If no path: search for most recent handoff in project directory.

2. **Handoff availability:**
   - If handoffs found for project: select most recent by filename timestamp.
   - If no handoffs found: report "No handoffs found for this project" and **STOP**.

3. **Project detection:**
   - If in git repository: use git root directory name as project.
   - If not in git: use current directory name.
   - If project name ambiguous or undeterminable: ask user to specify.

4. **Archive directory:**
   - If `archive/` exists: move handoff there.
   - If `archive/` doesn't exist: create it, then move handoff.
   - If cannot create `archive/`: warn user but continue (handoff still readable).

5. **State file creation:**
   - If `<project_root>/docs/handoffs/.session-state/` writable: write state file with archive path.
   - If not writable: warn user (next handoff won't have `resumed_from` field).

## Procedure

### Load (`/load [path]`)

When user runs `/load [path]`:

1. **Locate handoff:**
   - If path provided: validate it exists, use that handoff
   - If no path:
     1. Use Bash: `ls "$(git rev-parse --show-toplevel)/docs/handoffs"/*.md 2>/dev/null` (shell glob is non-recursive — unlike the Glob tool, it won't descend into `archive/`)
     2. If no output from primary location, check legacy location:
        1. `ls "$(git rev-parse --show-toplevel)/.codex/handoffs"/*.md 2>/dev/null`
        2. If found, report: "Found handoffs at legacy location `.codex/handoffs/`. Run `/save` to migrate — the next save will write to `docs/handoffs/`."
        3. Use the legacy file for this load
     3. If still no output, report "No handoffs found for this project" and **STOP**
     4. Select most recent by filename (format: `YYYY-MM-DD_HH-MM_*.md`)

2. **Read handoff content**

3. **Display and summarize:**
   - Show full handoff/checkpoint content
   - Note the type: "Resuming from **checkpoint**: ...", "Resuming from **summary**: ...", or "Resuming from **handoff**: ..."
   - Summarize key points: goal/current task, decisions, next steps/next action
   - Offer: "Continue with [first next step/action]?"

4. **Archive the handoff:**
   - Create `<project_root>/docs/handoffs/archive/` if needed
   - Move handoff to `archive/<filename>` via plain `mv`:
   ```bash
   mv "<source_path>" "<archive_path>"
   ```
   Handoffs are local-only working memory — no git operation fires. See `references/handoff-contract.md` for the Git Tracking section.

5. **Write state file:**
   - Create `<project_root>/docs/handoffs/.session-state/` if needed. If creating, also write a `.gitignore` inside it with content `*` followed by `!.gitignore` (state files are ephemeral and must not be git-tracked).
   - Write archive path to `<project_root>/docs/handoffs/.session-state/handoff-<project>` using the project name from the contract.

### List (`/list-handoffs`)

When user runs `/list-handoffs`:

1. Use Bash: `ls "$(git rev-parse --show-toplevel)/docs/handoffs"/*.md 2>/dev/null` (shell glob is non-recursive — unlike the Glob tool, it won't descend into `archive/`)
2. If no output, report "No handoffs found for this project" and **STOP**
3. Read frontmatter from each file
4. Format as table: date, title, type, branch
   - `type` comes from frontmatter `type` field. If missing, display as `handoff` (backwards compatibility).

## Storage

See [format-reference.md](../../references/format-reference.md) for:
- Storage location (`<project_root>/docs/handoffs/`)
- Filename format (`YYYY-MM-DD_HH-MM_<slug>.md`)
- Archive location (`<project_root>/docs/handoffs/archive/`)
- Retention policies (No auto-prune)

See also [handoff-contract.md](../../references/handoff-contract.md) for storage conventions, retention policies, and filename format.

## Background Cleanup (SessionStart Hook)

The plugin's SessionStart hook runs silently at session start:

1. Prunes state files older than 24 hours
2. Produces no output (no auto-inject, no prompts)

This is automatic — no user action required. Handoffs and archives are not auto-pruned.

## Verification

After loading, verify:

- [ ] Handoff content displayed to user
- [ ] Original file moved to `archive/`
- [ ] State file exists at `<project_root>/docs/handoffs/.session-state/handoff-<project>`
- [ ] Type displayed on load ("Resuming from **checkpoint**:", "Resuming from **summary**:", or "Resuming from **handoff**:")
- [ ] User offered continuation prompt

**Quick check:** `ls "$(git rev-parse --show-toplevel)/docs/handoffs/archive/"` shows the archived file.

## Troubleshooting

### Load not finding handoff

**Symptoms:** `/load` says "No handoffs found" or finds wrong handoff

**Likely causes:**
- Handoff was archived (check `docs/handoffs/archive/`)
- Running from different project directory than where handoff was created
- Handoff saved with different project name

**Next steps:**
1. Run `/list-handoffs` to see available handoffs for current project
2. Check handoffs directory directly: `ls "$(git rev-parse --show-toplevel)/docs/handoffs/"`
3. If found in different project, use `/load <full-path>`

### Archive directory not created

**Symptoms:** Load fails when trying to archive

**Likely causes:**
- Permission denied on handoffs directory
- Disk full

**Next steps:**
1. Check write permissions on `<project_root>/docs/handoffs/`
2. Create `archive/` manually if needed: `mkdir "$(git rev-parse --show-toplevel)/docs/handoffs/archive"`

### State file not created

**Symptoms:** Next handoff missing `resumed_from` field

**Likely causes:**
- Permission denied on `<project_root>/docs/handoffs/.session-state/`
- Session ended before state file written

**Next steps:**
1. Check if `<project_root>/docs/handoffs/.session-state/` exists
2. Create manually if needed: `mkdir -p "$(git rev-parse --show-toplevel)/docs/handoffs/.session-state"`

## Anti-Patterns

| Avoid | Why | Instead |
|-------|-----|---------|
| Auto-injecting handoffs | Stale handoffs clutter unrelated sessions | Explicit `/load` only |
| Suggesting old handoffs | Context may be irrelevant | User decides when to load |
| Loading synthesis guide | Not needed for load, wastes context | Load skill is lightweight |
| Modifying handoff content | Handoffs are immutable snapshots | Create new handoff if needed |

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `save` | Complementary: save creates, load resumes |
