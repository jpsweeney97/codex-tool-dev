# Handoff

Session continuity plugin for Codex. Saves session state as structured markdown documents, resumes work across sessions, tracks deferred work as tickets, and extracts durable knowledge from past sessions.

## Installation

Bundled in the `turbo-mode` marketplace:

```bash
codex plugin marketplace update turbo-mode
codex plugin install handoff@turbo-mode
```

Or install directly from the development repo:

```bash
codex plugin install ./packages/plugins/handoff
```

**Requirements:** Python 3.11+, PyYAML 6.0+, `trash` command (for cleanup).

## What It Does

| Capability | Skills | Description |
|------------|--------|-------------|
| **Session save/resume** | `/save`, `/load`, `/quicksave` | Create structured handoff documents capturing session state. Resume later with full context. Quicksave for fast checkpoints under context pressure. |
| **Deferred work tracking** | `/defer`, `/triage` | Extract work items from conversation into structured tickets. Audit ticket health, detect orphaned items, organize by priority. |
| **Knowledge extraction** | `/distill` | Synthesize durable insights from handoff documents into a project learnings file with deduplication. |
| **Handoff search** | `/search` | Query past handoffs by keyword or regex across active and archived files. |
| **Automatic maintenance** | *(hooks)* | Prune state files (24h) at session start. Validate handoff format on write. |

## Components

### Skills

| Skill | Trigger Phrases | Purpose |
|-------|----------------|---------|
| **save** | `/save`, "wrap this up", "new session", "handoff" | Full session report (13 sections, 400+ lines). Writes to `<project_root>/docs/handoffs/`. |
| **load** | `/load`, "continue from where we left off" | Resume from a previous handoff. Archives the source file, writes a state file for chain linking. |
| **quicksave** | `/quicksave`, "checkpoint", "save state" | Lightweight checkpoint (22-55 lines, 5 sections). Warns on 3rd consecutive checkpoint. |
| **defer** | `/defer`, "track these for later", "create tickets" | Extract deferred work items from conversation into ticket files in `docs/tickets/`. |
| **triage** | `/triage`, "what's in the backlog", "any open tickets" | Audit open tickets by priority. Detect orphaned handoff items not tracked by tickets. |
| **distill** | `/distill`, "extract knowledge", "graduate knowledge" | Extract durable insights from handoffs into `docs/learnings/learnings.md` with SHA256 deduplication. |
| **search** | `/search`, "find in handoffs", "what did we decide about" | Section-aware search across active and archived handoffs. Supports literal and regex queries. |

### Hooks

| Event | Script | Behavior |
|-------|--------|----------|
| **SessionStart** | `cleanup.py` | Silently prunes state files >24h. Always exits 0. |
| **PostToolUse** (Write) | `quality_check.py` | Validates handoff/checkpoint frontmatter, required sections, and line count. Non-blocking — outputs feedback via `additionalContext`. |

### Scripts

Core logic lives in `scripts/`. Skills handle UX and judgment; scripts handle deterministic work.

| Script | Purpose | Called By |
|--------|---------|-----------|
| `cleanup.py` | Archive pruning and state file TTL | SessionStart hook |
| `quality_check.py` | Handoff/checkpoint format validation | PostToolUse hook |
| `defer.py` | Ticket ID allocation, rendering, writing | `/defer` skill |
| `distill.py` | Candidate extraction, dedup, metadata | `/distill` skill |
| `triage.py` | Ticket scanning, orphan detection, matching | `/triage` skill |
| `search.py` | Section-aware handoff search | `/search` skill |
| `handoff_parsing.py` | Frontmatter and section parsing | Shared by distill, triage, search |
| `ticket_parsing.py` | Ticket YAML parsing and validation | Shared by defer, triage |
| `project_paths.py` | Project name and directory resolution | Shared by all scripts |
| `provenance.py` | Source tracking and dedup metadata | Shared by defer, distill, triage |

## Configuration

### Storage Locations

| Location | Contents | Retention |
|----------|----------|-----------|
| `<project_root>/docs/handoffs/` | Active handoffs and checkpoints | No auto-prune (gitignored, local-only) |
| `<project_root>/docs/handoffs/archive/` | Archived handoffs (moved by `/load`) | No auto-prune (gitignored, local-only) |
| `<project_root>/docs/handoffs/.session-state/handoff-<UUID>` | Chain protocol state files | 24 hours |
| `docs/tickets/` | Deferred work tickets | Permanent |
| `docs/learnings/learnings.md` | Distilled knowledge entries | Permanent |

Handoff files are gitignored and local-only — `/save`, `/load`, and `/quicksave` write or move files on the filesystem without committing. See `references/handoff-contract.md` for the Git Tracking section.

### Handoff Frontmatter

Every handoff/checkpoint uses YAML frontmatter with these fields:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `date` | Yes | `YYYY-MM-DD` | Creation date |
| `time` | Yes | `HH-MM` | Creation time |
| `created_at` | Yes | ISO 8601 | UTC timestamp |
| `session_id` | Yes | UUID | Session that created the document |
| `project` | Yes | string | Project name |
| `title` | Yes | string | Descriptive title |
| `type` | Yes | `handoff` or `checkpoint` | Document type |
| `branch` | No | string | Git branch name |
| `commit` | No | string | Git commit hash |
| `resumed_from` | No | path | Previous handoff (chain protocol) |

Full schema: `references/handoff-contract.md`.

### Ticket Frontmatter

Tickets created by `/defer` include:

| Field | Type | Values |
|-------|------|--------|
| `id` | string | `T-YYYYMMDD-NN` (auto-allocated) |
| `date` | `YYYY-MM-DD` | Creation date |
| `summary` | string | One-line title |
| `priority` | enum | `critical`, `high`, `medium`, `low` |
| `effort` | enum | `XS`, `S`, `M`, `L`, `XL` |
| `status` | enum | `tracked`, `in-progress`, `done`, `wontfix` |

## Usage Patterns

### Save and Resume

```
Session 1:
  /save                              → Creates handoff document
                                        (<project_root>/docs/handoffs/2026-03-09_14-30_feature-work.md)

Session 2:
  /load                              → Loads most recent handoff, archives it
                                        Creates state file linking sessions

  ... work continues ...

  /save                              → New handoff with resumed_from pointing to Session 1
```

### Context Pressure Cycling

```
  /quicksave                         → Fast checkpoint (22-55 lines)
  ... new session ...
  /load                              → Resume from checkpoint
  ... work continues ...
  /save                              → Full handoff when work is complete
```

### Defer and Triage Workflow

```
  /defer                             → Extract work items from conversation
                                        Creates ticket files in docs/tickets/

  ... later session ...

  /triage                            → Review open tickets by priority
                                        Detect orphaned items from handoffs
                                        Match tickets to source sessions
```

### Knowledge Extraction

```
  /distill                           → Extract insights from most recent handoff
                                        Dedup against existing learnings
                                        Append confirmed entries to docs/learnings/learnings.md
```

### Search Past Sessions

```
  /search "authentication"           → Literal search across all handoffs
  /search --regex "session|decision" → Regex search (case-sensitive)
```

## Architecture

```
┌─ Skills (User Entry Points) ──────────────────────┐
│  /save  /quicksave  /load  /defer                  │
│  /search  /distill  /triage                        │
├─ Scripts (Deterministic Work) ────────────────────┤
│  Core:    project_paths, handoff_parsing           │
│  Domain:  defer, distill, triage, search           │
│  Audit:   provenance, ticket_parsing               │
│  Maint:   cleanup                                  │
├─ Hooks (Automatic Validation) ────────────────────┤
│  SessionStart → cleanup (prune old files)          │
│  PostToolUse  → quality_check (validate format)    │
├─ Storage ─────────────────────────────────────────┤
│  Active:  <project_root>/docs/handoffs/         │
│  Archive: <project_root>/docs/handoffs/archive/  │
│  State:   docs/handoffs/.session-state/handoff-<UUID>│
└─ References ──────────────────────────────────────┘
   handoff-contract.md  format-reference.md
   synthesis-guide.md
```

### Chain Protocol

The chain protocol links sessions together via state files:

```
Session A (/save)
  └─ Writes handoff → cleans up state file

Session B (/load)
  └─ Archives handoff → writes state file (points to archive)

Session C (/save, resumed from B)
  └─ Reads state file → sets resumed_from → writes new handoff → cleans up state file
```

State files are plain text containing a single path. Created by `/load`, consumed by `/save` and `/quicksave`, cleaned up after use. 24-hour TTL handles orphaned state files from crashed sessions.

### Design Principles

- **Skills handle judgment, scripts handle computation.** Skills analyze conversation and prompt users. Scripts parse files, allocate IDs, and validate structure.
- **JSON contracts between layers.** Scripts communicate with skills via JSON on stdin/stdout.
- **Provenance tracking.** Tickets and learnings include metadata (`defer-meta`, `distill-meta`) for source tracing and dedup.
- **Non-blocking validation.** The PostToolUse hook validates after write — it provides feedback but cannot prevent the write.
- **Safety-first I/O.** Uses `trash` instead of `rm`. Graceful degradation on read errors. TTL cleanup for orphaned files.

## Extension Points

### Adding a Skill

Create `skills/<name>/SKILL.md` with YAML frontmatter:

```yaml
---
name: my-skill
description: Brief description for trigger detection
argument-hint: "[optional-argument]"
allowed-tools:
  - Bash
  - Read
  - Write
---
```

See `skills/save/SKILL.md` for a comprehensive example.

### Adding a Hook

Edit `hooks/hooks.json` to register new event handlers:

```json
{
  "type": "command",
  "command": "python3 /absolute/path/to/plugin/scripts/my-script.py"
}
```

Supported events: `SessionStart`, `PostToolUse` (with `matcher` for tool filtering).

### Adding a Script

Create `scripts/<name>.py` following the existing pattern:

- Implement `main(argv=None) -> int` for CLI compatibility
- Use `project_paths.get_project_name()` for project detection
- Return JSON on stdout, diagnostics on stderr
- Exit 0 on success, non-zero on failure

## Development

### Setup

```bash
cd packages/plugins/handoff
uv sync
```

### Testing

354 tests across 10 test modules (2:1 test-to-code ratio):

```bash
uv run pytest                          # All tests
uv run pytest tests/test_defer.py      # Single module
uv run pytest tests/test_defer.py -v   # Verbose
```

Or from the repo root:

```bash
uv run --package handoff-plugin pytest
```

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

## Known Limitations

Three inherited edge cases are documented in `references/handoff-contract.md`:

1. **Resume-crash gap** — If a session crashes after `/load` but before `/save`, the `resumed_from` chain breaks. The archived file remains intact; the state file persists until 24h TTL.
2. **Archive-failure poisoning** — If archiving fails but the state file is written, the next handoff's `resumed_from` points to a non-existent file. Skills handle this gracefully.
3. **State-file TTL race** — Sessions spanning >24 hours may lose their state file to cleanup, resulting in a missing `resumed_from` link.

## References

| Document | Purpose |
|----------|---------|
| `references/handoff-contract.md` | Frontmatter schema, chain protocol, storage conventions, known limitations |
| `references/format-reference.md` | Section checklist, quality targets, worked examples |
| `skills/save/synthesis-guide.md` | Internal synthesis guidance for the save skill |
| `CHANGELOG.md` | Version history (1.0.0–1.5.0) |

## License

MIT
