# Changelog

All notable changes to the ticket plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- `DeferredWorkEnvelope` schema validator with JSON Schema-based validation (T-04a, #69)
- `ticket_envelope.py` module: envelope read, field mapping, and lifecycle management for consuming deferred work envelopes (T-04a, #69)
- `DeferredWorkEnvelope` schema documented in ticket contract §11 (T-04a, #69)
- `effort` field in `DeferredWorkEnvelope` schema for sizing deferred work items (T-04b, #70)
- `IngestInput` stage model at dispatch boundary for envelope ingestion pipeline (T-04b, #70)
- `ingest` subcommand in engine runner: read-validate-map-plan-preflight-execute-move pipeline for consuming deferred work envelopes (T-04b, #70)
- `ingest` added to guard hook `VALID_SUBCOMMANDS` allowlist (T-04b, #70)
- `defer` field passed through `_execute_create` to `render_ticket` for envelope-originated tickets (T-04a, #69)

### Changed

- Audit repair default flipped to dry-run; `--fix` flag required for actual file mutations, closing safety bug where `repair_audit_logs` modified files without explicit opt-in (T-03, #69)

### Fixed

- Archived tickets included in blocker resolution and dedup scan — `_list_tickets_with_closed()` helper prevents false "missing" blocker reports and dedup false negatives on done/wontfix tickets (C-003, #68)
- Legacy write gate rejects mutations on pre-v1.0 tickets until migrated via engine; `contract_version` now engine-owned and stamped on all write paths (C-001/C-004)
- `key_file_paths` persisted in YAML frontmatter for round-trip dedup reliability; `dedup_override` bound to `duplicate_of` field (C-002/C-008)
- Full contract shapes enforced for `source`, `defer`, and `key_files` fields before any file mutation (C-005)
- Contract documentation aligned with implementation; agent-preflight hook gate removed (C-006/C-007/C-009/C-010)
- Envelope `move_to_processed` rejects overwrite of existing processed file, preventing silent data loss (code review I-1, #69)
- Envelope move exception catch widened from `FileExistsError` to `OSError` for filesystem robustness (T-04b, #70)
- `envelope_path` containment check and input type validation added to ingest pipeline, preventing path traversal (T-04b, #70)

## 1.4.0 — 2026-03-09

### Added

- `ClassifyInput`, `PlanInput`, `PreflightInput`, and `ExecuteInput` typed models at dispatch boundary, making pipeline stage contracts explicit (A-002, #62)
- `PayloadError` exception type for structured pipeline stage failures (A-002/A-003, #62/#63)
- Shared in-process entrypoint runner, eliminating subprocess overhead and consolidating execution path (A-003, #63)
- `live_warnings` propagated in `policy_changed_since_preflight` and defense-in-depth mode-block responses when autonomy config is malformed, so callers can distinguish intentional policy blocks from degraded configs (A-009, #65)
- Operator handbook at `HANDBOOK.md` covering bring-up, configuration, pipeline internals, and failure recovery

### Changed

- Entrypoints rewritten as thin wrappers delegating to shared runner (A-003, #63)
- `test_engine.py` split by pipeline stage into focused test modules (A-008, #64)

### Fixed

- Acceptance criteria bypass via `close` action — AC check now fires on `target == "done"` regardless of current ticket status (#59)
- Guard hook Branch 2b for `ticket_audit.py` — user invocations allowed, agent invocations denied (#59)
- Dedup window changed from YYYY-MM-DD date-field day granularity to file mtime with second-level precision, closing near-midnight duplicate escape (#59)
- Dedup window refined from file mtime to `created_at` field with end-of-day fallback for cross-filesystem reliability
- Leading-space interpreter bypass closed — shlex-based candidate detection replaces regex prefilter in guard hook (#60)
- Guard hook now skips interpreter flags (`-u`, `-O`, `-m pdb`, `-X dev`) and `env` option flags before identifying the script operand, closing flag-injection bypasses (#60)
- Lowercase env-var assignments denied by prefilter (#60)
- Full trust triple (`hook_injected`, `hook_request_origin`, `session_id`) enforced at both entrypoint and engine layers for all request origins (#60)
- Structural stage prerequisites (`classify_intent`, `classify_confidence`, `dedup_fingerprint`) enforced before execute proceeds (#60)
- Truthiness-based `agent_id` checks replaced with explicit 3-state origin helper that denies malformed values (#60)
- Schema validation for `priority`, `status`, `resolution`, `tags`, `blocked_by`, `blocks`, and scalar string fields before any file mutation (#60)
- `Path.cwd()` fallback replaced with marker-based project-root resolution (`.codex/`, `.git/`, or worktree file ancestor walk) (#60)
- Empty `session_id` rejected before payload injection (#60)
- `error_code` invariant enforced on all `EngineResponse` instances; 7 escalate paths that omitted `error_code` fixed (A-005, #61)
- `_execute_reopen` moves archived ticket back from `closed-tickets/` before YAML write; rolls back rename on write failure (#66)
- `engine_plan` computes `target_fingerprint` from `ticket_id` for non-create intents (#66)
- `engine_count_session_creates` filters by `request_origin` so user creates don't consume agent session budget (#66)
- `ticket_read`, `ticket_triage`, and `ticket_audit` use `discover_project_root` instead of `Path.cwd()` (#66)
- `ticket_validate` checks `source.type` required key (#66)
- Audit result write failure triggers `escalate` with fail-closed cap sealing via `attempt_started` entries (#66)

## 1.3.0 — 2026-03-06

### Added

- `classify_intent` and `classify_confidence` emitted at engine boundary so skills can plain-merge `response.data` without manual field renaming (#52)
- `ticket_audit.py` repair utility with `--dry-run`, timestamped backups, and structured JSON output for fixing malformed tickets (#52)
- `O_EXCL` exclusive file creation with 3-attempt bounded retry and orphan cleanup on write/fsync failure, preventing silent overwrite of existing tickets (#52)

### Changed

- All mutation paths (create/update/close/reopen) unified on a single serialization surface in `ticket_render.py`, eliminating dual-serializer drift (#52)
- `key_file_paths` locked as dedup-only; create without `key_files` produces a valid ticket with no Key Files section (#52)

## 1.2.0 — 2026-03-06

### Added

- Title field included in engine API responses (#51)
- `ticket_paths.py` module for centralized path helpers and read-path containment (#51)
- Payload uniqueness enforcement to prevent duplicate payloads across pipeline stages (#51)

### Changed

- Request origin tracked and validated across all pipeline stages (#51)

### Fixed

- Update corruption stopped — state loss during concurrent updates prevented (#51)
- Autonomy trust hardened against config bypass vectors (#51)
- Missing blockers now surfaced in classify output (#51)

## 1.1.1 — 2026-03-05

### Fixed

- 9 eval findings from skill-creator review: pipeline statelessness documentation, classify key naming, guard hook edge cases, and SKILL.md accuracy (#49)

## 1.1.0 — 2026-03-05

### Added

- `/ticket` skill with full mutation pipeline using stateless design — skill manages payload progression between classify, preflight, and execute stages (#48)
- `/ticket-triage` skill for dashboard and audit operations (#48)
- `pipeline-guide.md` reference document: exact key mappings, stateless model, and classify-to-preflight key rename behavior (#48)
- CLI entry points for `ticket_read.py` (`list`/`query`) and `ticket_triage.py` (`dashboard`/`audit`) so scripts are directly invokable (#47)

### Changed

- Guard hook redesigned with 4-branch allowlist (read → triage → deny → passthrough), replacing single-regex approach for more precise allow/deny control (#48)

### Fixed

- `yaml.safe_dump` enforced for all ticket frontmatter rendering, closing YAML injection vector (#47)
- Path traversal validation added before file operations (#47)
- Archive collision on same-day duplicate title fixed (#47)
- Python launcher bypass variants closed: absolute paths (`/usr/bin/python3`), versioned interpreters (`python3.11`), `env` launcher, and env-var launchers (#48)

## 1.0.0 — 2026-03-04

### Added

- Plugin scaffold: `plugin.json`, `pyproject.toml`, test fixture directory
- Ticket contract v1.0 reference document defining schema, pipeline stages, and error codes
- `ticket_parse.py`: 4-generation legacy format support with migration golden tests
- `ticket_id.py`: ID allocation with slug generation and collision prevention
- `ticket_render.py`: v1.0 Markdown rendering with fenced YAML frontmatter
- `ticket_read.py`: shared read module for listing and querying tickets
- `ticket_dedup.py`: duplicate detection with `normalize()` and target fingerprinting; TOCTOU-safe fingerprint computation
- Engine pipeline: `engine_classify` (intent validation), `engine_plan` (dedup detection), `engine_preflight` (autonomy enforcement), `engine_execute` (full lifecycle — create/update/close/reopen)
- Config-driven autonomy enforcement system: `suggest`, `auto_audit`, and `auto_silent` modes with session caps, override rejection, and per-action exclusions (#46)
- Defense-in-depth in `engine_execute`: agent creates blocked unless `auto_audit` mode active (#46)
- Config snapshot between preflight and execute to prevent TOCTOU policy bypass (#46)
- Triage script with stale/blocked/size dashboard, audit trail reader, and orphan detection (uid_match/id_ref/manual_review) (#46)
- `hook_injected` and `dependency_override` wired through preflight entrypoints (#46)

<!-- Historical comparison links were intentionally removed during the Codex
     marketplace conversion because the old source repository is no longer the
     canonical distribution surface for these plugin artifacts. -->
