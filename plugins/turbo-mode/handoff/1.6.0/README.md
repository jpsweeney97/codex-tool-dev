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
codex plugin install ./plugins/turbo-mode/handoff/1.6.0
```

**Requirements:** Python 3.11+, PyYAML 6.0+. The optional `trash` command is used for recoverable cleanup when available; cleanup falls back to `unlink` with warnings if `trash` is unavailable or fails.

## What It Does

| Capability | Skills | Description |
|------------|--------|-------------|
| **Session save/resume** | `/save`, `/load`, `/quicksave`, `/summary` | Create structured handoff documents capturing session state. Resume later with full context. Quicksave for fast checkpoints and summary for medium-depth session capture. |
| **Deferred work tracking** | `/defer`, `/triage` | Extract work items from conversation into structured tickets. Audit ticket health, detect orphaned items, organize by priority. |
| **Knowledge extraction** | `/distill` | Synthesize durable insights from handoff documents into a project learnings file with deduplication. |
| **Handoff search** | `/search` | Query past handoffs by keyword or regex across active and archived files. |
| **State maintenance** | `/load`, `/save`, `/quicksave`, `/summary` | Manage chain state files during explicit handoff workflows. |

## Components

### Skills

| Skill | Trigger Phrases | Purpose |
|-------|----------------|---------|
| **save** | `/save`, "wrap this up", "new session", "handoff" | Full session report (13 sections, 400+ lines). Writes to `<project_root>/.codex/handoffs/`. |
| **load** | `/load`, "continue from where we left off" | Resume from a previous handoff. Archives the source file, writes a state file for chain linking. |
| **quicksave** | `/quicksave`, "checkpoint", "save state" | Lightweight checkpoint (22-55 lines, 5 sections). Warns on 3rd consecutive checkpoint. |
| **summary** | `/summary`, "summary", "summarize" | Medium-depth session summary with project arc context. Writes to `<project_root>/.codex/handoffs/`. |
| **defer** | `/defer`, "track these for later", "create tickets" | Extract deferred work items from conversation into ticket files in `docs/tickets/`. |
| **triage** | `/triage`, "what's in the backlog", "any open tickets" | Audit open tickets by priority. Detect orphaned handoff items not tracked by tickets. |
| **distill** | `/distill`, "extract knowledge", "graduate knowledge" | Extract durable insights from handoffs into `docs/learnings/learnings.md` with SHA256 deduplication. |
| **search** | `/search`, "find in handoffs", "what did we decide about" | Section-aware search across active and archived handoffs. Supports literal and regex queries. |

### Hooks

Handoff `1.6.0` does not ship plugin-bundled command hooks. The dormant hook-compatible scripts are retained in source, but the installed plugin manifest exposes no bundled hook command contract. Plugin-bundled command hooks are deferred from `1.6.0` until Codex provides a documented portable launcher contract or a separate generated-config architecture is approved.

### Runtime Package and CLI Facades

Core logic lives in `turbo_mode_handoff_runtime/`. The `scripts/` directory now contains only thin executable CLI facades for skill-facing command paths. `scripts.*` is not a supported library import API.

| Script Facade | Purpose | Called By |
|---------------|---------|-----------|
| `defer.py` | Ticket ID allocation, rendering, writing | `/defer` skill |
| `distill.py` | Candidate extraction, dedup, metadata | `/distill` skill |
| `list_handoffs.py` | Enumerate active handoff candidates | `/load` skill |
| `load_transactions.py` | Load transaction lifecycle management | `/load` skill |
| `plugin_siblings.py` | Resolve sibling plugin roots | `/defer` skill |
| `search.py` | Section-aware handoff search | `/search` skill |
| `session_state.py` | Chain and active-writer state operations | `/save`, `/quicksave`, `/summary` skills |
| `triage.py` | Ticket scanning, orphan detection, matching | `/triage` skill |

Runtime-only helpers such as `turbo_mode_handoff_runtime/quality_check.py`, `turbo_mode_handoff_runtime/cleanup.py`, and `turbo_mode_handoff_runtime/storage_authority_inventory.py` remain source utilities and are not wired into Handoff `1.6.0` skill entrypoints or hooks.

## Configuration

### Storage Locations

| Location | Contents | Retention |
|----------|----------|-----------|
| `<project_root>/.codex/handoffs/` | Active handoffs and checkpoints | No auto-prune |
| `<project_root>/.codex/handoffs/archive/` | Archived handoffs (moved by `/load`) | No auto-prune |
| `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json` | Chain protocol state files | 24 hours |
| `docs/tickets/` | Deferred work tickets | Permanent |
| `docs/learnings/learnings.md` | Distilled knowledge entries | Permanent |

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant.

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
| `type` | Yes | `handoff`, `checkpoint`, or `summary` | Document type |
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
                                        (<project_root>/.codex/handoffs/2026-03-09_14-30_feature-work.md)

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
├─ Runtime Package (Implementation) ─────────────────┤
│  turbo_mode_handoff_runtime/*                      │
├─ CLI Facades (Executable Paths) ───────────────────┤
│  scripts/defer.py, distill.py, list_handoffs.py    │
│  scripts/load_transactions.py, plugin_siblings.py  │
│  scripts/search.py, session_state.py, triage.py    │
├─ Runtime-only Helpers (Not Skill/Hook-wired) ──────┤
│  cleanup, quality_check, storage_authority_inventory│
├─ Storage ─────────────────────────────────────────┤
│  Active:  <project_root>/.codex/handoffs/         │
│  Archive: <project_root>/.codex/handoffs/archive/ │
│  State:   .codex/handoffs/.session-state/      │
└─ References ──────────────────────────────────────┘
   handoff-contract.md  format-reference.md
   synthesis-guide.md
```

### Chain Protocol

The chain protocol links sessions together via state files:

```
Session A (/save)
  └─ Writes handoff with active-writer reservation

Session B (/load)
  └─ Archives handoff under .codex/handoffs/archive/ → writes JSON state file

Session C (/save, resumed from B)
  └─ Reads JSON state → sets resumed_from → writes new handoff → clears consumed state
```

State files are JSON records under `.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`. Created by `/load`, consumed by `/save`, `/quicksave`, and `/summary`, then cleared after use. Active writers can bridge one valid legacy state file when needed and mark that source consumed without modifying legacy bytes. A 24-hour TTL handles orphaned state files from crashed sessions.

### Design Principles

- **Skills handle judgment, runtime modules handle computation.** Skills analyze conversation and prompt users. Runtime modules parse files, allocate IDs, and validate structure.
- **JSON contracts between layers.** CLI facades communicate with skills via JSON on stdin/stdout and delegate to runtime modules.
- **Provenance tracking.** Tickets and learnings include metadata (`defer-meta`, `distill-meta`) for source tracing and dedup.
- **Validation helpers are non-gating in 1.6.0.** Hook-compatible validation code remains in source, but installed Handoff does not expose plugin-bundled command hooks in this release.
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

### Hook Scope

Handoff plugin-bundled command hooks are deferred from 1.6.0 until Codex exposes a documented plugin-root launcher contract or a generated-config architecture is designed and proven.

### Adding Runtime Code

Add new implementation under `turbo_mode_handoff_runtime/<name>.py`, and keep runtime modules import-only (no shebang, no `if __name__ == "__main__":` block). If the behavior must be skill-invokable, add or update one of the approved `scripts/*.py` facades to call the runtime module's `main()`.

## Development

### Setup

```bash
cd plugins/turbo-mode/handoff/1.6.0
uv sync
```

### Testing

To inspect the current test inventory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest --collect-only -q -p no:cacheprovider
```

To run the suite from the repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

To run a single module from the plugin directory:

```bash
uv run pytest tests/test_defer.py -q
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
| `CHANGELOG.md` | Version history (1.0.0-1.6.0) |

## License

MIT
