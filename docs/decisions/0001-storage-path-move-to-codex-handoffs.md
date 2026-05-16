# ADR 0001 — Move handoff storage to `.codex/handoffs/`

- **Status:** Accepted (back-fill record; shipped in handoff 1.7.0, 2026-05-15)
- **Scope:** `plugins/turbo-mode/handoff/`

## Context

Handoff storage historically lived under `<project_root>/docs/handoffs/`. That path
conflated user-facing project docs with plugin runtime state and made host-repo
tracking policy ambiguous. A durable, plugin-owned location was needed without the
plugin taking on gitignore/staging/commit responsibility.

## Decision

Move active and archived handoff storage to `<project_root>/.codex/handoffs/`
(archive remains `archive/`). `is_handoff_path()` matches the new location.
`search.py` and `triage.py` retain **controlled** legacy `docs/handoffs/` fallback
discovery for pre-cutover history; `get_legacy_handoffs_dir()` (in `project_paths.py`)
plus a legacy-fallback warning support the transition. The plugin still does not add
gitignore rules, stage, or auto-commit; host-repo tracking policy remains external.
This is a BREAKING change recorded in the 1.7.0 CHANGELOG.

## Consequences

- Pre-cutover repositories keep working via the legacy fallback until they migrate;
  the fallback's removal condition is recorded in `references/ARCHITECTURE.md`
  ("Legacy Fallback Exit Condition").
- No auto-pruning is applied to handoff files (only session-state has a 24h TTL).
- Any future relocation must update `is_handoff_path()`, the fallback discovery,
  and the documented exit condition together.
