# Changelog

All notable changes to the handoff plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **BREAKING:** Handoff storage moved from `<project_root>/.codex/handoffs/` to `<project_root>/docs/handoffs/`. Handoffs remain local-only working memory — gitignored and never auto-committed. Archive renamed from `.archive/` to `archive/`. No auto-pruning — handoffs are ephemeral by design.
- Cleanup hook (`cleanup.py`) prunes session-state files only (24h TTL); handoff files are never auto-pruned.
- `is_handoff_path()` now matches `docs/handoffs/` (active and archived) instead of `.codex/handoffs/`.
- `search.py` and `triage.py` check legacy `.codex/handoffs/` location as fallback.

### Added
- `get_legacy_handoffs_dir()` in `project_paths.py` for fallback discovery.
- `Bash` added to `allowed-tools` for save, load, quicksave skills.
- Legacy fallback warning when handoffs found at old location.

### Fixed
- Organize tickets into subdirectories and fix triage subdirectory bug
- Add warnings for silent coercions and error handling in `triage.main()`
- Specific exception handling and nonzero exit code in `defer.main()`
- Add warnings to silent failure points in defer/triage pipelines
- Add diagnostic warnings to `parse_ticket` failure paths
- Escape backslash and newline in `_quote` for valid YAML output
- Broaden ticket ID regex to support 3+ digit sequences

### Changed
- Add TypedDicts for return types, document TicketFile limits
- Extract `section_name` to `handoff_parsing`, add `allocate_id` concurrency note
- Fix SKILL.md priority enum, regex patterns, and lookback note

### Added
- End-to-end integration tests for defer and triage pipelines
- Priority/effort validation tests
- Tests for provenance fallback, YAML null, stdin wrapping, and warning paths

## [1.5.0] - 2026-02-28

### Added
- `/defer` skill -- extract deferred work items from conversation into structured tickets
- `/triage` skill -- review open tickets and detect orphaned handoff items
- `defer.py` -- ticket ID allocation, rendering, and file writing
- `triage.py` -- ticket reading, status normalization, handoff scanning, orphan detection, and report generation
- `provenance.py` -- defer-meta parsing, dual-read, session matching
- `ticket_parsing.py` -- fenced YAML extraction and parsing
- `TicketFile` type with schema validation and `parse_ticket()`
- `get_archive_dir()` to `project_paths.py`
- PyYAML dependency for ticket parsing

## [1.4.0] - 2026-02-27

### Added
- `/distill` skill -- extract durable knowledge from handoffs into Phase 0 learnings
- Signal extraction and main pipeline in `distill.py`
- Provenance tracking and exact dedup for distill
- Subsection parser and durability hints for distill
- Shared `project_paths` module
- Shared `handoff_parsing` module

### Fixed
- Address 11 PR review findings across 3 files
- Fix double-emission bug and strengthen test assertions
- Fix Pyright type errors in TypedDict usage
- Correlate source and content dedup checks per record
- Always track skipped files internally in `search_handoffs`

### Changed
- Typed returns with TypedDict + Literal for `extract_candidates`
- Freeze dataclasses, fix preamble merge mutation
- Migrate `search.py` to shared parsing and path modules
- Fix docstrings from PR review

## [1.3.0] - 2026-02-27

### Changed
- Rename skills to "video game save system" naming (`/save`, `/load`, `/quicksave`)

### Fixed
- Remove plugin commands to avoid FQN skill resolution bug

## [1.2.0] - 2026-02-26

### Added
- `/search` skill -- section-aware search across handoff files
- Markdown parser for handoff files
- CLI entry point for search script
- Quality validation PostToolUse hook

### Fixed
- Report skipped files in search results instead of silent drop
- Report error when handoffs directory not found
- Include `project_source` in search output to surface fallback
- Compile regex once in `search_handoffs`, remove duplicate validation
- Add search command wrapper and prevent shell expansion in query
- Restore handoff commands (checkpoint, handoff, resume)
- Make subprocess test portable

## [1.1.1] - 2026-02-26

### Fixed
- Replace Glob with shell `ls` in resume/list procedures (Glob unavailable in plugin context)

## [1.1.0] - 2026-02-25

### Added
- `/quicksave` (checkpoint) skill for fast state saves
- `/checkpoint` command wrapper
- Shared handoff contract for cross-skill consistency
- `type` field in handoff schema with display in resume and list-handoffs
- Contract references in resume and list-handoffs skills
- Checkpoint format section and precedence text in contract
- Test infrastructure and baseline `cleanup.py` tests
- Coverage for `get_handoffs_dir`, state_files stat OSError, default state_dir

### Fixed
- Use `trash` instead of `unlink` in `cleanup.py`
- Extract `_trash` helper, fix `deleted.append`, refactor `prune_old_state_files`
- Add `main()` exception guard, clarify error handling
- Add `.archive/` post-filter to Glob in resume skill
- Correct instruction accuracy across contract and skills
- Remove unused pytest import, add OSError catch to `get_project_name`
- Add trash-failure warning to skills, state file pruning to resume

## [1.0.0] - 2026-01-21

### Added
- Initial release as standalone plugin marketplace
- `/handoff` (save) skill with synthesis guide for comprehensive session reports
- `/resume` (load) skill -- 71% lighter context than monolithic skill
- Shared format reference for cross-skill consistency
- SessionStart cleanup hook for retention pruning
- Plugin manifest and README
- Artifact/chat output separation convention

### Fixed
- Create standalone marketplace (path traversal not allowed)

### Changed
- Rename skills to gerund form per skill-writing guide
- Migrate commands and simplify skill frontmatter
