# Turbo Mode Installed Refresh Tool Design

## Status

Design accepted in discussion on 2026-05-04 and repaired after scrutiny on 2026-05-04. This document is a design spec only. It does not authorize an implementation until a separate implementation plan exists.

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

Fast developer refresh for low-risk source/cache diffs. This mode is smaller than `--guarded-refresh`, but it still mutates the installed cache and therefore must not run while hook-capable Codex sessions are present unless a future atomic install certification explicitly changes this rule.

Responsibilities:

- Take a tool lock so two refresh tools cannot run concurrently.
- Refuse to proceed unless the process gate passes.
- Refuse guarded-only or unknown diffs.
- Snapshot the pre-refresh installed cache roots before app-server install.
- Validate or require the expected Turbo Mode marketplace registration.
- Install Handoff and Ticket through `codex app-server` `plugin/install`.
- Run runtime inventory checks through app-server.
- Verify post-install source/cache equality.
- Run the selected smoke tier, default `light`.
- Restore the pre-refresh cache snapshot if app-server install or post-install verification fails.
- Write local-only evidence.
- Write commit-safe evidence only when `--record-summary` is passed.

This mode does not claim atomic install safety. Its safety boundary is narrower than guarded refresh: process gate, no guarded-only paths, minimal installed-cache snapshot/restore, runtime inventory after install, and source/cache equality after install. It does not edit or roll back global config.

### `--guarded-refresh`

Maintenance-window refresh for hook, engine, workflow, validation, path, parsing, envelope, or unknown-risk changes.

Responsibilities:

- Take the same tool lock as `--refresh`.
- Refuse to proceed unless the process gate passes.
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

For each plugin root, build manifests keyed by the canonical refresh path:

```text
<plugin>/<version>/<relative_path-inside-plugin-root>
```

Examples:

```text
handoff/1.6.0/skills/search/SKILL.md
handoff/1.6.0/scripts/search.py
ticket/1.4.0/hooks/hooks.json
ticket/1.4.0/scripts/ticket_engine_core.py
```

The same canonical key is used for source manifests, cache manifests, diff output, safety classification, smoke selection, and evidence summaries.

Generated residue is not part of equality manifests, but it is not silently ignored. Before computing equality, scan both repo source and installed cache for generated residue and fail if any generated residue is present.

Residue gate paths:

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

The safety classifier operates on canonical refresh paths.

## Safety Classification

Unknown paths default to guarded-only. False guarded is acceptable; false fast is not. Classification uses Python `fnmatch`-style glob patterns against canonical refresh paths.

### Guarded-Only Paths

Any changed, added, or removed path matching these patterns requires `--guarded-refresh`:

```text
handoff/1.6.0/hooks/hooks.json
handoff/1.6.0/hooks/*.py
handoff/1.6.0/scripts/defer.py
ticket/1.4.0/hooks/hooks.json
ticket/1.4.0/hooks/*.py
ticket/1.4.0/scripts/ticket_engine_guard.py
ticket/1.4.0/scripts/ticket_engine_runner.py
ticket/1.4.0/scripts/ticket_engine_core.py
ticket/1.4.0/scripts/ticket_engine_user.py
ticket/1.4.0/scripts/ticket_engine_agent.py
ticket/1.4.0/scripts/ticket_workflow.py
ticket/1.4.0/scripts/ticket_validate.py
ticket/1.4.0/scripts/ticket_parse.py
ticket/1.4.0/scripts/ticket_paths.py
ticket/1.4.0/scripts/ticket_envelope.py
```

Rationale:

- Ticket hook enforcement can run during shell-backed tool calls.
- Hook command paths may stay stable while file content changes.
- Existing Codex sessions are not proven to hot-reload hook metadata or hook-executed code predictably.
- Handoff `defer.py` crosses into Ticket creation behavior and should not be treated as ordinary documentation.
- Handoff `hooks/hooks.json` is currently empty, but changes to it would change runtime hook registration and are therefore guarded-only.

### Fast-Safe Paths

These paths may be refreshed through `--refresh` after the no-concurrent-hook-consumer check passes:

```text
handoff/1.6.0/skills/**
handoff/1.6.0/references/**
handoff/1.6.0/README.md
handoff/1.6.0/CHANGELOG.md
handoff/1.6.0/pyproject.toml
handoff/1.6.0/uv.lock
handoff/1.6.0/scripts/search.py
handoff/1.6.0/scripts/triage.py
handoff/1.6.0/scripts/distill.py
handoff/1.6.0/scripts/session_state.py
handoff/1.6.0/scripts/ticket_parsing.py
ticket/1.4.0/skills/**
ticket/1.4.0/references/**
ticket/1.4.0/README.md
ticket/1.4.0/CHANGELOG.md
ticket/1.4.0/HANDBOOK.md
ticket/1.4.0/pyproject.toml
ticket/1.4.0/uv.lock
```

If a path matches both guarded-only and fast-safe classes, guarded-only wins.

### Concrete Classification Examples

- `handoff/1.6.0/skills/search/SKILL.md`: fast-safe.
- `handoff/1.6.0/scripts/session_state.py`: fast-safe, but requires session-state smoke because the changed executable path has path-specific coverage.
- `handoff/1.6.0/scripts/defer.py`: guarded-only.
- `handoff/1.6.0/hooks/hooks.json`: guarded-only, even though the current expected Handoff hook manifest is empty.
- `ticket/1.4.0/skills/ticket/SKILL.md`: fast-safe, but requires a smoke tier that exercises the documented command shape when the skill content changes.
- `ticket/1.4.0/scripts/ticket_engine_core.py`: guarded-only.
- `ticket/1.4.0/scripts/new_helper.py`: guarded-only until explicitly classified.

### Atomicity Certification

This design does not assume `plugin/install` is atomic for concurrent live readers. The first implementation must require no hook-capable Codex processes for both `--refresh` and `--guarded-refresh`.

A future design may add an explicitly named concurrent refresh mode only after a separate certification proves:

- cache readers never observe partially installed plugin trees;
- already-running sessions either hot-reload deterministically or do not hot-reload at all;
- hook command execution cannot observe a mixed old/new cache state;
- failed app-server install leaves the installed cache in a known recoverable state.

## Install Mechanism

Use app-server `plugin/install` as the primary install mechanism.

Do not implement direct file copy as the normal refresh path. File copy can make hashes match while bypassing the runtime install contract. The tool should use source/cache equality as a verification gate after app-server install, not as a substitute for install.

## Process Gate

Both mutation modes use the same no-concurrent-hook-consumer process gate until a separate atomicity certification changes that rule.

The refresh tool must be launched from an external maintenance shell, not from an active Codex Desktop or Codex CLI conversation. Running from inside a Codex session is expected to self-block and should be treated as correct behavior.

Process census command:

```bash
ps -axo pid,ppid,command
```

Hook-capable blockers are processes whose command line contains one of these markers, excluding the refresh tool process itself and its direct child `codex app-server --listen stdio://` process after the install phase starts:

```text
Codex
codex
codex app-server
```

The implementation must avoid a broad self-exemption. It may exempt:

- the current refresh tool PID;
- direct child app-server PIDs spawned by this refresh tool after the first successful census;
- shell wrapper processes whose command line is exactly the refresh command being executed.

Required censuses:

1. **Before any mutation**: after acquiring the refresh lock, before cache/config snapshots or app-server install.
2. **Immediately before install**: after snapshots are complete, before the first `plugin/install` request.

If either census finds blockers, the tool fails before mutation and writes a local-only process-gate summary plus a local-only raw process listing. If commit-safe evidence is enabled for that run, the commit-safe summary records only count, marker set, census label, raw listing SHA256, and run metadata. The raw process listing stays under local-only evidence.

For `--guarded-refresh`, if hooks are disabled as part of the guarded flow, a third census must run after hook disable and immediately before cache mutation.

The gate must be tested for:

- self-block when invoked from a simulated Codex command line;
- no self-block for the refresh tool process itself;
- no self-block for the direct child app-server spawned by the tool after the first census;
- blocker detection for unrelated Codex Desktop, Codex CLI, and app-server processes.

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
- `hooks/list` contains no Handoff hook entries for Handoff 1.6.0. Current Handoff `hooks/hooks.json` is empty, and `scripts/cleanup.py` documents that Handoff 1.6.0 does not wire plugin-bundled command hooks into the installed manifest.
- No inventory response contains `/plugin-dev/`.
- Hook paths resolve under `/Users/jp/.codex/plugins/cache/turbo-mode/...`, not repo source.

Authority rules:

- Repo marketplace metadata says where source should come from.
- Global config says which local marketplace root Codex should register.
- Runtime inventory says what Codex currently resolves.
- Installed cache manifests say what files are live on disk.

All four surfaces must align after install. A source/cache equality pass alone is not sufficient.

## Smoke Tiers

### `light`

Default for `--refresh`.

Required checks:

- Runtime inventory checks.
- Source/cache equality.
- Handoff search or triage.
- Ticket read list and query.
- Any changed fast-safe executable path with a path-specific smoke available.

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

Smoke selection is diff-aware:

- A changed `handoff/1.6.0/scripts/session_state.py` requires Handoff session-state write/read/clear, even if the requested smoke tier is `light`.
- A changed `handoff/1.6.0/scripts/search.py` requires Handoff search.
- A changed `handoff/1.6.0/scripts/triage.py` requires Handoff triage.
- A changed `ticket/1.4.0/skills/ticket/SKILL.md` requires a smoke path that exercises the documented command shape, not only direct script calls.
- Any changed skill file that changes command-shape instructions must be paired with a smoke that exercises that documented command shape. If the tool cannot determine whether the skill change is command-shape-affecting, it must require `standard` smoke or fail with a coverage gap.
- Any changed guarded-only Ticket engine or hook path requires at least `standard`, and the tool should recommend `full`.
- If a changed executable path has no path-specific smoke, the tool must classify the change as guarded-only or fail the run until coverage is added.

Command-shape triggers for skill and reference docs:

- fenced `bash`, `sh`, `shell`, or untyped command blocks change;
- lines beginning with `python`, `python3`, `uv`, `codex`, `ticket_`, or `./` change;
- JSON payload examples change;
- sections with headings containing `Command`, `Workflow`, `Execute`, `Prepare`, `Payload`, `Recovery`, or `Policy` change;
- markdown tables containing command/state/action fields change.

When any trigger is present in a changed skill or reference doc, the tool must either select a matching command-shape smoke or fail with a coverage gap. A pure prose change outside triggered sections may remain fast-safe with `light` smoke.

## Evidence Policy

Every run writes local-only evidence under:

```text
/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/
```

Local-only evidence should include:

- run metadata with `RUN_ID`, evidence schema version, tool path, tool SHA256, repo `HEAD`, dirty-state policy, source roots, cache roots, marketplace path, and config path
- source manifest
- pre-refresh cache manifest
- post-refresh cache manifest
- source manifest SHA256
- pre-refresh cache manifest SHA256
- post-refresh cache manifest SHA256
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

Commit-safe summaries must also include top-level run metadata and must be validated by a redaction gate before staging.

Stale evidence rejection:

- A summary is current only when its `RUN_ID`, repo `HEAD`, tool SHA256, source manifest SHA256, pre-refresh cache manifest SHA256, post-refresh cache manifest SHA256, and evidence schema version match the run being reported.
- Reusing an older local-only evidence directory for a new commit-safe summary is forbidden unless the summary explicitly records that it is a post-commit binding artifact and validates the original source/cache proof digest.
- Dirty-state policy must be explicit. The default should fail if relevant source, marketplace, or refresh-tool files are modified outside the committed `HEAD`.

## Locking

Both mutation modes take a refresh lock before installation. The lock prevents concurrent refresh tools from racing each other.

Both mutation modes require a no-concurrent-hook-consumer process check until app-server install atomicity is separately certified.

## Failure Behavior

`--refresh`:

- Fails before mutation for guarded-only or unknown diffs.
- Fails before mutation for unexpected marketplace registration.
- Snapshots installed cache roots before app-server install.
- Verifies after install.
- If Handoff install succeeds and Ticket install fails, or any post-install inventory, equality, or smoke gate fails, restores the pre-refresh installed cache snapshot for both plugins.
- Verifies restored cache manifests before declaring restore complete.
- Does not edit global config and therefore does not provide config rollback.

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
- `--refresh` refuses to mutate unless the process gate passes.
- `--refresh` can update fast-safe installed content through app-server install and prove runtime inventory plus source/cache equality after the process gate passes.
- `--refresh` snapshots installed cache roots and restores them if install or post-install verification fails.
- `--guarded-refresh` enforces no-concurrent-hook-consumer checks before hook-sensitive mutation.
- `--guarded-refresh` snapshots and rolls back on failed install, inventory, equality, or smoke.
- Generated residue in source or cache fails the run before equality diffing.
- Handoff hook inventory assertion matches current truth: expected empty Handoff hook inventory for Handoff 1.6.0.
- Classifier tests use canonical `<plugin>/<version>/<relative_path>` keys and assert concrete Handoff and Ticket examples.
- Smoke selection is diff-aware for changed executable and skill-command paths.
- Skill-doc command-shape triggers force matching smoke or a coverage-gap failure.
- All modes write local-only evidence.
- `--record-summary` writes a redaction-safe summary suitable for commit.
- Tests cover empty/no-diff, fast-safe diff, guarded-only diff, unknown diff, generated residue, Handoff expected-empty hook inventory, marketplace mismatch, process-gate self-block/exemption behavior, app-server failure, `--refresh` partial-install restore, skill-doc command-shape smoke escalation, stale evidence rejection, and rollback failure.
