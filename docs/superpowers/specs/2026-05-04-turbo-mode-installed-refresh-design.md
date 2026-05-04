# Turbo Mode Installed Refresh Tool Design

## Status

Design accepted in discussion on 2026-05-04. This document is a design spec only. It does not authorize an implementation until a separate implementation plan exists.

## Purpose

Add a smaller repeatable tool for refreshing the live installed Turbo Mode plugins from the repo-local source authority without reusing the one-time source-migration wrapper as a daily developer command.

The source-authority migration established:

- Repo source:
  - `/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0`
  - `/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket/1.4.0`
- Repo marketplace:
  - `/Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json`
- Installed runtime cache:
  - `/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0`
  - `/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0`

Editing repo source does not update the installed runtime cache by itself. This tool provides the refresh path and proves what is live after the refresh.

## Proposed Command

Tool path:

```bash
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --dry-run
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --refresh --smoke light
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --guarded-refresh --smoke standard
```

The tool should share small helper functions with the migration tooling where that reduces duplication, but it should be a separate user-facing command. The migration wrapper remains a one-time destructive-operation wrapper, not the normal developer refresh interface.

## Modes

### `--dry-run`

No mutation.

Responsibilities:

- Validate repo source roots exist.
- Validate repo marketplace metadata points at the repo-local Handoff and Ticket source roots.
- Validate installed cache roots are discoverable.
- Build source and cache manifests.
- Compute the source/cache filesystem diff.
- Classify changed paths as fast-safe, guarded-only, or unknown.
- Report whether `--refresh` is allowed or `--guarded-refresh` is required.
- Write local-only dry-run evidence.

### `--refresh`

Fast developer refresh. This mode may run while other Codex sessions exist, but only for fast-safe source/cache diffs.

Responsibilities:

- Take a tool lock so two refresh tools cannot run concurrently.
- Refuse guarded-only or unknown diffs.
- Validate or require the expected Turbo Mode marketplace registration.
- Install Handoff and Ticket through `codex app-server` `plugin/install`.
- Run runtime inventory checks through app-server.
- Verify post-install source/cache equality.
- Run the selected smoke tier, default `light`.
- Write local-only evidence.
- Write commit-safe evidence only when `--record-summary` is passed.

This mode does not claim maintenance-window safety and does not provide full rollback semantics.

### `--guarded-refresh`

Maintenance-window refresh for hook, engine, workflow, validation, path, parsing, envelope, or unknown-risk changes.

Responsibilities:

- Take the same tool lock as `--refresh`.
- Refuse to proceed while hook-capable Codex processes are present.
- Snapshot config and cache roots before mutation.
- Optionally disable `features.plugin_hooks` during cache mutation, then restore it.
- Install through app-server.
- Run runtime inventory checks.
- Verify post-install source/cache equality.
- Run the selected smoke tier, default `standard`.
- Roll back config/cache if install, inventory, equality, or smoke fails.
- Verify rollback before declaring rollback complete.
- Write local-only evidence.
- Write commit-safe evidence by default, unless `--no-record-summary` is explicitly passed.

## Diff Basis

The classifier must compare repo source to installed cache as filesystem trees. It must not rely on Git diff, because the cache is not a Git repo and may drift from source for reasons unrelated to the current commit.

For each plugin root, build `{relative_path: sha256}` manifests for source and cache.

Ignore generated residue:

```text
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
.DS_Store
.codex/ticket-tmp/
```

Diff categories:

- `added`: present in source, absent from cache.
- `removed`: present in cache, absent from source.
- `changed`: present in both, different SHA256.

The safety classifier operates on these source/cache diff paths.

## Safety Classification

Unknown paths default to guarded-only. False guarded is acceptable; false fast is not.

### Guarded-Only Paths

Any changed, added, or removed path matching these patterns requires `--guarded-refresh`:

```text
*/hooks/hooks.json
*/hooks/*.py
*/scripts/ticket_engine_guard.py
*/scripts/ticket_engine_runner.py
*/scripts/ticket_engine_core.py
*/scripts/ticket_engine_user.py
*/scripts/ticket_engine_agent.py
*/scripts/ticket_workflow.py
*/scripts/ticket_validate.py
*/scripts/ticket_parse.py
*/scripts/ticket_paths.py
*/scripts/ticket_envelope.py
*/scripts/defer.py
*/scripts/quality_check.py
```

Rationale:

- Ticket hook enforcement can run during shell-backed tool calls.
- Hook command paths may stay stable while file content changes.
- Existing Codex sessions are not proven to hot-reload hook metadata or hook-executed code predictably.
- Handoff `quality_check.py` is hook-executed.
- Handoff `defer.py` crosses into Ticket creation behavior and should not be treated as ordinary documentation.

### Fast-Safe Paths

These paths may be refreshed through `--refresh` while other Codex sessions exist:

```text
*/skills/**
*/references/**
*/README.md
*/CHANGELOG.md
*/HANDBOOK.md
*/pyproject.toml
*/uv.lock
handoff/1.6.0/scripts/search.py
handoff/1.6.0/scripts/triage.py
handoff/1.6.0/scripts/distill.py
handoff/1.6.0/scripts/session_state.py
handoff/1.6.0/scripts/ticket_parsing.py
```

If a path matches both guarded-only and fast-safe classes, guarded-only wins.

## Install Mechanism

Use app-server `plugin/install` as the primary install mechanism.

Do not implement direct file copy as the normal refresh path. File copy can make hashes match while bypassing the runtime install contract. The tool should use source/cache equality as a verification gate after app-server install, not as a substitute for install.

## Marketplace Registration

The expected Turbo Mode marketplace source is:

```text
/Users/jp/Projects/active/codex-tool-dev
```

The expected marketplace metadata file is:

```text
/Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json
```

Default behavior:

- `--dry-run`: report registration state.
- `--refresh`: fail if `turbo-mode` is registered from a different source. Do not silently replace registration.
- `--guarded-refresh`: may repair conflicting registration, but must record the before/after state in evidence.

## Runtime Inventory Checks

After install, verify through app-server inventory:

- `plugin/read` for Handoff points at the repo source root.
- `plugin/read` for Ticket points at the repo source root.
- `plugin/list` contains Handoff and Ticket from the Turbo Mode marketplace.
- `skills/list` contains expected installed Handoff and Ticket skills.
- `hooks/list` contains the expected Ticket Bash `preToolUse` hook.
- Handoff hook inventory is present as expected for installed Handoff.
- No inventory response contains `/plugin-dev/`.
- Hook paths resolve under `/Users/jp/.codex/plugins/cache/turbo-mode/...`, not repo source.

## Smoke Tiers

### `light`

Default for `--refresh`.

Required checks:

- Runtime inventory checks.
- Source/cache equality.
- Handoff search or triage.
- Ticket read list and query.

### `standard`

Default for `--guarded-refresh`.

Required checks:

- Everything in `light`.
- Handoff defer in a disposable repo.
- Handoff session-state write/read/clear.
- Ticket create/update/read/query in a disposable repo.
- Ticket close/reopen lifecycle.
- Ticket audit repair dry-run.

### `full`

Migration-grade installed smoke. Use for hook or Ticket engine changes when practical.

Required checks:

- Everything in `standard`.
- Noncanonical command denial with hash-stable artifacts.
- Scalar `acceptance_criteria` rejection.
- Any additional Step 12 smoke cases from the source migration wrapper that are still relevant.

For guarded-only Ticket hook or engine changes, the tool should default to at least `standard` and recommend `full`.

## Evidence Policy

Every run writes local-only evidence under:

```text
/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/
```

Local-only evidence should include:

- source manifest
- pre-refresh cache manifest
- post-refresh cache manifest
- source/cache diff and safety classification
- app-server transcript
- app-server transcript SHA256
- runtime inventory summary
- smoke summary
- final status
- rollback status for guarded failures

Commit-safe evidence is opt-in for `--refresh`:

```bash
--record-summary
```

Commit-safe refresh summaries should live under:

```text
plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json
```

`--guarded-refresh` records commit-safe evidence by default. `--no-record-summary` may disable this for private experiments.

Commit-safe summaries must not contain raw app-server transcripts, config contents, process lists, or unredacted local-only raw proof. They may contain hashes, statuses, classifications, repo/source/cache paths already allowed by the migration redaction policy, and pointers to local-only evidence.

## Locking

Both mutation modes take a refresh lock before installation. The lock prevents concurrent refresh tools from racing each other.

The fast path lock does not block other Codex sessions. Guarded refresh additionally requires a no-concurrent-hook-consumer process check.

## Failure Behavior

`--refresh`:

- Fails before mutation for guarded-only or unknown diffs.
- Fails before mutation for unexpected marketplace registration.
- Verifies after install.
- If post-install verification fails, reports that the installed cache is not proven current and that guarded recovery is required.
- Does not claim rollback.

`--guarded-refresh`:

- Snapshots state before mutation.
- Rolls back config/cache on failed install, inventory, equality, or smoke.
- Verifies rollback before declaring rollback complete.

## Version Semantics

The installed cache path is versioned:

```text
handoff/1.6.0
ticket/1.4.0
```

Refreshing changed source into the same versioned cache path is a same-version local refresh. This is valid for local development, but the evidence should label it as such.

For release-like use, warn when source behavior changes but `.codex-plugin/plugin.json` version does not change. Do not fail by default for local development.

## Non-Goals

- Publishing Turbo Mode to a remote marketplace.
- Turning `codex plugin marketplace upgrade turbo-mode` into the refresh mechanism.
- Automatically pushing changes to a Git remote.
- Proving hot-reload behavior for already-running Codex sessions.
- Replacing the existing source-migration evidence.

## Acceptance Criteria

- `--dry-run` classifies source/cache drift without mutation.
- `--refresh` refuses guarded-only and unknown diffs.
- `--refresh` can update fast-safe installed content through app-server install and prove runtime inventory plus source/cache equality.
- `--guarded-refresh` enforces no-concurrent-hook-consumer checks before hook-sensitive mutation.
- `--guarded-refresh` snapshots and rolls back on failed install, inventory, equality, or smoke.
- All modes write local-only evidence.
- `--record-summary` writes a redaction-safe summary suitable for commit.
- Tests cover empty/no-diff, fast-safe diff, guarded-only diff, unknown diff, marketplace mismatch, app-server failure, and rollback failure.
