# Turbo Mode Installed Refresh Tool Design

## Status

Design accepted in discussion on 2026-05-04 and repaired after scrutiny on 2026-05-04. This document is a design spec only. It does not authorize an implementation until a    separate implementation plan exists.

## Purpose

Add a smaller repeatable tool for assessing and, during a controlled maintenance window, refreshing the live installed Turbo Mode plugins from the repo-local source authority without reusing the one-time source-migration wrapper as the normal interface.

The source-authority migration established:

- Repo source:
  - `/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0`
  - `/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket/1.4.0`
- Repo marketplace:
  - `/Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json`
- Installed runtime cache:
  - `/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0`
  - `/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0`

Editing repo source does not update the installed runtime cache by itself. The routine developer command is non-mutating drift assessment. Installed-cache mutation remains an external-shell maintenance operation until a separate atomic-install certification proves that live concurrent refresh is safe.

## Proposed Command

Tool path:

```bash
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --dry-run
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --plan-refresh
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --refresh --smoke light
python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --guarded-refresh --smoke standard
```

The tool should share small helper functions with migration tooling only after those helpers are extracted into a refresh-safe module with no migration plan, migration base-head, or source-migration evidence constants. The migration wrapper remains a one-time destructive-operation wrapper, not the normal developer refresh interface.

The command help and startup banner must make the UX split explicit:

- `--dry-run` and `--plan-refresh` are routine commands and may be run from a Codex session because they do not mutate the installed cache.
- `--refresh` and `--guarded-refresh` are external-shell maintenance operations. Running either mutation mode from an active Codex Desktop or Codex CLI conversation is expected to self-block.

## Modes

### `--dry-run`

No installed cache, global config, or runtime mutation. Local-only evidence writes are allowed.

Responsibilities:

- Validate repo source roots exist.
- Validate repo marketplace metadata points at the repo-local Handoff and Ticket source roots.
- Validate installed cache roots are discoverable.
- Build source and cache manifests.
- Compute the source/cache filesystem diff.
- Classify changed paths as `fast-safe-with-covered-smoke`, `guarded-only`, or `coverage-gap-fail`.
- Report one terminal plan status: `refresh-allowed`, `guarded-refresh-required`, `coverage-gap-blocked`, `blocked-preflight`, or `no-drift`.
- Write local-only dry-run evidence.

### `--plan-refresh`

No installed cache, global config, or runtime mutation. Local-only evidence writes are allowed.

Responsibilities:

- Run all `--dry-run` checks.
- Select the required mutation mode, smoke tier, and coverage requirements.
- Emit the exact external-shell command that would be allowed if the process gate later passes.
- Emit no mutation command when the terminal status is `coverage-gap-blocked`, `blocked-preflight`, or `no-drift`.
- Emit stop conditions that would block mutation, including guarded-only paths, coverage gaps, generated residue, marketplace mismatch, and expected process blockers.
- Write local-only plan evidence that can be compared with the later mutation run. The later mutation run must recompute manifests and must not trust the plan artifact as current proof.

### `--refresh`

External-shell maintenance refresh for low-risk source/cache diffs. This mode is smaller than `--guarded-refresh`, but it still mutates the installed cache and therefore must not run while hook-capable Codex sessions are present unless a future atomic install certification explicitly changes this rule.

Responsibilities:

- Take a tool lock so two refresh tools cannot run concurrently.
- Refuse to proceed unless the process gate passes.
- Refuse guarded-only or coverage-gap diffs.
- Capture pre-refresh config hash and pre-refresh app-server inventory, even though this mode does not edit global config.
- Snapshot the pre-refresh installed cache roots before app-server install.
- Validate or require the expected Turbo Mode marketplace registration.
- Install Handoff and Ticket through `codex app-server` `plugin/install`.
- Run runtime inventory checks through app-server.
- Verify post-install source/cache equality.
- Run the selected smoke tier, default `light`.
- Restore the pre-refresh cache snapshot if app-server install or post-install verification fails.
- Prove restore with restored cache manifests, unchanged config hash, and fresh post-restore app-server inventory from a newly started app-server process.
- Write local-only evidence.
- Write commit-safe evidence only when `--record-summary` is passed.

This mode does not claim atomic install safety. Its safety boundary is narrower than guarded refresh: process gate, no guarded-only or coverage-gap paths, minimal installed-cache snapshot/restore, runtime inventory after install, and source/cache equality after install. It does not edit global config; rollback proof still verifies that config did not change.

### `--guarded-refresh`

Maintenance-window refresh for hook, engine, workflow, validation, path, parsing, envelope, or unknown-risk changes.

Responsibilities:

- Take the same tool lock as `--refresh`.
- Refuse to proceed unless the process gate passes.
- Snapshot config and cache roots before mutation.
- Disable `features.plugin_hooks` during cache mutation when the setting exists and is true, then restore it before final verification. If the setting is absent or already false, record a no-op hook-disable decision with the parsed config state.
- Install through app-server.
- Run runtime inventory checks.
- Verify post-install source/cache equality.
- Run the selected smoke tier, default `standard`.
- Roll back config/cache if install, inventory, equality, or smoke fails.
- For successful guarded mutation, terminate any app-server child used while hooks were disabled, restore config, start a fresh app-server process, then collect final runtime inventory and run smoke against that fresh process state.
- Verify rollback with restored config hash, restored cache manifests, fresh app-server inventory from a newly started app-server process, expected plugin enablement, and expected hook inventory before declaring rollback complete.
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

The safety classifier operates on canonical refresh paths and returns two independent fields per changed path:

- `mutation_mode`: `fast`, `guarded`, or `blocked`.
- `coverage_status`: `covered` or `coverage_gap`.

The user-facing path outcome is derived from those fields:

| Derived outcome | Rule |
| --- | --- |
| `fast-safe-with-covered-smoke` | `mutation_mode=fast` and `coverage_status=covered` |
| `guarded-only` | `mutation_mode=guarded` and `coverage_status=covered` |
| `coverage-gap-fail` | any path with `coverage_status=coverage_gap`, regardless of mutation mode |

## Safety Classification

Unmatched paths are an internal reason code, not an external classifier result. An unmatched non-executable path must be reported externally as `guarded-only` with reason `unmatched-path`. An unmatched executable path, new executable path, or changed command-shape-bearing path without deterministic smoke must be reported externally as `coverage-gap-fail`. False guarded is acceptable; false fast is not. False covered is not acceptable. Classification uses Python `fnmatch`-style glob patterns against canonical refresh paths.

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

### Fast-Safe With Covered Smoke Paths

These paths may be refreshed through `--refresh` after the no-concurrent-hook-consumer check passes and after the required smoke mapping is selected:

```text
handoff/1.6.0/pyproject.toml
handoff/1.6.0/uv.lock
handoff/1.6.0/scripts/search.py
handoff/1.6.0/scripts/triage.py
handoff/1.6.0/scripts/session_state.py
handoff/1.6.0/skills/**
handoff/1.6.0/references/**
handoff/1.6.0/README.md
handoff/1.6.0/CHANGELOG.md
ticket/1.4.0/README.md
ticket/1.4.0/CHANGELOG.md
ticket/1.4.0/HANDBOOK.md
ticket/1.4.0/pyproject.toml
ticket/1.4.0/uv.lock
ticket/1.4.0/skills/**
ticket/1.4.0/references/**
```

If a path matches both guarded-only and fast-safe-with-covered-smoke classes, guarded-only wins.

Required smoke mapping:

| Path pattern | Minimum smoke |
| --- | --- |
| `handoff/1.6.0/scripts/search.py` | Handoff search |
| `handoff/1.6.0/scripts/triage.py` | Handoff triage |
| `handoff/1.6.0/scripts/session_state.py` | Handoff session-state write/read/clear |
| `handoff/1.6.0/skills/**` | Light smoke unless command-shape triggers fire; command-shape triggers require matching command-shape smoke or coverage-gap failure |
| `handoff/1.6.0/references/**` | Light smoke unless command-shape triggers fire; command-shape triggers require matching command-shape smoke or coverage-gap failure |
| `ticket/1.4.0/skills/**` | Light smoke unless command-shape triggers fire; command-shape triggers require matching Ticket command-shape smoke or coverage-gap failure |
| `ticket/1.4.0/references/**` | Light smoke unless command-shape triggers fire; command-shape triggers require matching Ticket command-shape smoke or coverage-gap failure |
| `ticket/1.4.0/HANDBOOK.md` | Light smoke unless command-shape triggers fire; command-shape triggers require matching Ticket command-shape smoke or coverage-gap failure |
| README files | Light smoke unless command-shape triggers fire; command-shape triggers require matching command-shape smoke or coverage-gap failure |
| CHANGELOG files | Light smoke unless command-shape triggers fire; command-shape triggers require matching command-shape smoke or coverage-gap failure |
| Handoff `pyproject.toml`, Handoff `uv.lock` | At least one installed Handoff command through the documented `uv run --project "$PLUGIN_ROOT/pyproject.toml"` shape |
| Ticket `pyproject.toml`, Ticket `uv.lock` | At least one installed Ticket command through the canonical `python3 -B <PLUGIN_ROOT>/scripts/<script>.py` launcher |

### Coverage-Gap Fail Paths

These paths look lower risk than hook or Ticket engine paths, but they are executable or command-shape-bearing surfaces without a named deterministic smoke in this design. They must fail mutation until deterministic coverage is added and the path is explicitly reclassified with both `mutation_mode` and `coverage_status`:

```text
handoff/1.6.0/scripts/distill.py
handoff/1.6.0/scripts/ticket_parsing.py
```

Any new executable path under either plugin root is `coverage-gap-fail` unless it is explicitly added to a table with both a mutation mode and deterministic smoke mapping. Existing executable paths absent from the guarded-only and fast-safe-with-covered-smoke tables also default to `coverage-gap-fail`. New or unmatched executable paths are not allowed to become merely `guarded-only` by default.

### Concrete Classification Examples

- `handoff/1.6.0/skills/search/SKILL.md`: fast-safe-with-covered-smoke unless command-shape triggers fire without matching smoke.
- `handoff/1.6.0/scripts/session_state.py`: fast-safe-with-covered-smoke, but requires session-state smoke because the changed executable path has path-specific coverage.
- `handoff/1.6.0/scripts/distill.py`: coverage-gap-fail until a deterministic distill smoke exists.
- `handoff/1.6.0/scripts/defer.py`: guarded-only.
- `handoff/1.6.0/hooks/hooks.json`: guarded-only, even though the current expected Handoff hook manifest is empty.
- `ticket/1.4.0/skills/ticket/SKILL.md`: fast-safe-with-covered-smoke only when command-shape triggers have matching smoke; otherwise coverage-gap-fail.
- `ticket/1.4.0/scripts/ticket_engine_core.py`: guarded-only with required guarded Ticket engine smoke.
- `ticket/1.4.0/scripts/new_helper.py`: coverage-gap-fail until explicitly classified with deterministic smoke.

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

### App-Server Request Contract

The implementation must pin the app-server JSON-RPC shape used for install and inventory. The request sequence is:

1. `initialize` with `clientInfo.name = "turbo-mode-installed-refresh"` and `capabilities.experimentalApi = true`.
2. `initialized`.
3. `plugin/install` for Handoff:
   - `marketplacePath = "/Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json"`
   - `pluginName = "handoff"`
   - `remoteMarketplaceName = null`
4. `plugin/install` for Ticket with the same `marketplacePath`, `pluginName = "ticket"`, and `remoteMarketplaceName = null`.
5. `plugin/read` for Handoff and Ticket with the same `marketplacePath`, `pluginName`, and `remoteMarketplaceName = null`.
6. `plugin/list` with the same `marketplacePath` and `remoteMarketplaceName = null`.
7. `skills/list` with `cwds` pointing at the disposable smoke repo.
8. `hooks/list` with `cwds` pointing at the disposable smoke repo.

Any app-server response schema drift is a hard failure until the inventory parser and evidence schema are updated. The transcript stays local-only; commit-safe evidence records request methods, response status summaries, and transcript SHA256.

## Shared Helper Boundary

The refresh implementation must not import `plugins/turbo-mode/tools/migration/migration_common.py` directly. That module is bound to source-migration constants such as the migration plan path, migration base head, source-migration evidence root, and source-migration local-only root.

Allowed helper reuse requires one of these shapes:

- Extract constants-free functions into `plugins/turbo-mode/tools/turbo_mode_tooling_common.py`, with every root, plan, evidence path, and mode supplied by the caller.
- Keep refresh helpers inside `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py` until a clean shared module is justified.

Tests must fail if refresh evidence contains source-migration plan paths, source-migration evidence roots, or `MIGRATION_BASE_HEAD` metadata.

## Process Gate

Both mutation modes use the same no-concurrent-hook-consumer process gate until a separate atomicity certification changes that rule.

The refresh tool must be launched from an external maintenance shell, not from an active Codex Desktop or Codex CLI conversation. Running from inside a Codex session is expected to self-block and should be treated as correct behavior.

Process census command:

```bash
ps -ww -axo pid,ppid,command
```

The process gate must use a structured classifier, not raw substring matching. Each `ps` row is parsed into:

- `pid`
- `ppid`
- raw command line
- best-effort argv tokens using shell-style splitting
- executable basename from the first argv token when parseable
- ancestry relation to the refresh tool process

The process census must request sufficiently wide command output for the target platform. If the command line appears truncated, if shell-style parsing loses quoting needed for a self-exemption decision, or if a wrapper command cannot be matched exactly, the classifier must choose `uncertain-high-risk` rather than applying an exemption.

If a command line contains a known high-risk marker but cannot be parsed confidently, classify it as a blocker rather than ignoring it.

The implementation must avoid a broad self-exemption. It may exempt only:

- the current refresh tool PID;
- direct child app-server PIDs spawned by this refresh tool after the first successful census;
- shell wrapper processes whose command line is exactly the refresh command being executed.

Direct child app-server exemption is valid only when:

- `ppid` is the refresh tool PID;
- executable basename is `codex`;
- argv includes `app-server`;
- argv includes `--listen` and `stdio://`;
- the PID was recorded by the refresh tool when it spawned the child.

Blocker classes:

| Class | Rule |
| --- | --- |
| `codex-desktop` | executable basename is `Codex`, or a parsed app bundle command resolves to Codex Desktop |
| `codex-cli` | executable basename is `codex` and the process is not the refresh tool's recorded direct child app-server |
| `codex-app-server` | parsed argv contains `codex app-server`, unless it is the recorded direct child app-server |
| `ticket-hook-runtime` | command line or executable basename references `ticket_engine_guard.py`, `ticket_engine_runner.py`, `ticket_engine_core.py`, `ticket_workflow.py`, or a `ticket_*.py` executable under `/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/` |
| `ticket-hook-path-consumer` | command line references `/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/` |
| `uncertain-high-risk` | parser could not classify a command line that contains `Codex`, basename token `codex`, `codex app-server`, `ticket_engine_`, `ticket_workflow.py`, or the installed Ticket hook path |

The classifier must not block merely because an unrelated file path contains the string `codex`; it must use executable basename, parsed argv tokens, or explicit installed hook/runtime paths.

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
- blocker detection for active Ticket hook and Ticket workflow processes.
- no blocker for harmless paths that merely contain `codex` as a directory name.
- uncertain high-risk parse fallback.

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
- `--guarded-refresh`: may repair conflicting registration only after the config snapshot is written and verified. It must record the before/after state in evidence and must include the registration repair in config rollback proof if any later gate fails.

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

For successful `--guarded-refresh` runs that disable hooks, final inventory and smoke must be collected after restoring config and starting a fresh app-server process. The app-server child used while hooks were disabled cannot be reused for final `hooks/list` proof, because it may reflect stale in-memory config or plugin state.

Rollback inventory proof uses the same app-server inventory checks, but compares against the pre-refresh inventory and byte-for-byte config SHA256 rather than the attempted post-install target. Because app-server may hold in-memory plugin state from a failed install attempt, rollback proof must terminate the failed-run app-server child and start a fresh app-server process before collecting restored inventory. A rollback summary may not report `ROLLBACK_COMPLETE` or `RESTORE_COMPLETE` until config hash, cache manifests, plugin enablement, runtime inventory, and hook inventory match the pre-run state.

## Smoke Tiers

### `light`

Default for `--refresh`.

Required checks:

- Runtime inventory checks.
- Source/cache equality.
- Handoff search or triage.
- Ticket read list and query.
- For changed Handoff `pyproject.toml` or `uv.lock`, at least one installed Handoff command executed through the documented `uv run --project "$PLUGIN_ROOT/pyproject.toml"` shape.
- For changed Ticket `pyproject.toml` or `uv.lock`, at least one installed Ticket command executed through the canonical `python3 -B <PLUGIN_ROOT>/scripts/<script>.py` launcher. Ticket dependency-file smoke must not substitute Handoff's `uv run --project` shape unless the Ticket hook policy and documented launcher are deliberately redesigned.
- Any changed fast-safe-with-covered-smoke executable path with a path-specific smoke available.

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
- A changed `ticket/1.4.0/skills/ticket/SKILL.md` with command-shape triggers requires a Ticket command-shape smoke: run the documented canonical installed-cache pipeline in a disposable repo through prepare/execute, then prove read/query visibility and audit-log state. Direct script calls that bypass the documented pipeline do not satisfy this requirement.
- A changed Handoff skill with command-shape triggers requires a Handoff command-shape smoke when the documented command can be executed deterministically. If there is no stable skill-execution API or deterministic command path for the changed instruction, the result is `coverage-gap-fail`, not a weaker light smoke.
- Any changed skill, reference, README, or CHANGELOG file that changes command-shape instructions must be paired with a smoke that exercises that documented command shape. If the tool cannot determine whether the change is command-shape-affecting, it must require `standard` smoke or fail with a coverage gap.
- Any changed guarded-only Ticket engine or hook path requires at least `standard`, and the tool should recommend `full`.
- If a changed executable path has no path-specific smoke, the tool must classify the change as `coverage-gap-fail` until deterministic coverage is added.

Command-shape triggers for skill, reference, README, and CHANGELOG docs:

- fenced `bash`, `sh`, `shell`, or untyped command blocks change;
- lines beginning with `python`, `python3`, `uv`, `codex`, `ticket_`, or `./` change;
- JSON payload examples change;
- sections with headings containing `Command`, `Workflow`, `Execute`, `Prepare`, `Payload`, `Recovery`, or `Policy` change;
- markdown tables containing command/state/action fields change.

When any trigger is present in a changed skill, reference, README, or CHANGELOG doc, the tool must either select a matching command-shape smoke or fail with a coverage gap. A pure prose change outside triggered sections may remain fast-safe-with-covered-smoke with `light` smoke.

## Evidence Policy

Every run writes local-only evidence under:

```text
/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/
```

Local-only evidence requirements are mode-specific:

| Artifact | `--dry-run` | `--plan-refresh` | `--refresh` | `--guarded-refresh` |
| --- | --- | --- | --- | --- |
| run metadata with `RUN_ID`, evidence schema version, tool path, tool SHA256, repo `HEAD`, dirty-state policy, source roots, cache roots, marketplace path, and config path | required | required | required | required |
| source manifest and SHA256 | required | required | required | required |
| pre-refresh cache manifest and SHA256 | required | required | required | required |
| post-refresh cache manifest and SHA256 | not applicable | not applicable | required after install or restore | required after install or rollback |
| source/cache diff and safety classification | required | required | required | required |
| terminal plan status | required | required | required | required |
| selected mutation command | not applicable | required when mutation is allowed | required | required |
| process-gate summary and raw local-only process listing | not applicable | optional forecast only | required | required |
| pre-refresh config SHA256 | not applicable | not applicable | required | required |
| post-refresh config SHA256 | not applicable | not applicable | required | required |
| app-server transcript and SHA256 | not applicable | not applicable | required | required |
| runtime inventory summary and SHA256 | not applicable | not applicable | required | required |
| smoke summary and SHA256 | not applicable | not applicable | required | required |
| final status | required | required | required | required |
| restore or rollback status | not applicable | not applicable | required on failed install or post-install verification | required on failed install, inventory, equality, or smoke |

`not applicable` means the artifact must not be invented as an empty success proof. If an implementation chooses to collect extra read-only inventory during `--dry-run` or `--plan-refresh`, that behavior must be explicitly documented and must not be required for the non-mutating path.

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

Commit-safe summaries must also include top-level run metadata and must be validated by refresh-specific current-run and redaction gates before staging. The implementation must not import `plugins/turbo-mode/tools/migration/validate_redaction.py` directly while it depends on `migration_common.py`; that module carries source-migration constants. Either extract the shared redaction rules into a constants-free helper or create a refresh validator with explicit refresh paths.

Required refresh validators:

```bash
python3 plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  --run-id <RUN_ID> \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --local-only-root /Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID> \
  --summary plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json \
  --summary-output /Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/metadata-validation.summary.json

python3 plugins/turbo-mode/tools/refresh_validate_redaction.py \
  --run-id <RUN_ID> \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --scope turbo-mode-refresh \
  --source worktree \
  --include plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json \
  --summary-output /Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/redaction.summary.json \
  --validate-own-summary
```

Required commit-safe summary schema:

- `schema_version`
- `run_id`
- `mode`
- `run_metadata`
- `repo_head`
- `tool_path`
- `tool_sha256`
- `dirty_state_policy`
- `source_manifest_sha256`
- `pre_refresh_cache_manifest_sha256`
- `post_refresh_cache_manifest_sha256`
- `pre_refresh_config_sha256`
- `post_refresh_config_sha256`
- `pre_refresh_inventory_sha256`
- `post_refresh_inventory_sha256`
- `diff_classification`
- `selected_smoke_tier`
- `smoke_summary_sha256`
- `metadata_validation_summary_sha256`
- `redaction_validation_summary_sha256`
- `process_gate_summary`
- `local_only_evidence_root`
- `final_status`
- `rollback_or_restore_status`

Stale evidence rejection:

- A summary is current only when its `RUN_ID`, repo `HEAD`, tool SHA256, source manifest SHA256, pre-refresh cache manifest SHA256, post-refresh cache manifest SHA256, and evidence schema version match the run being reported.
- The metadata validator must recompute the current repo `HEAD`, worktree tool SHA256, manifest digests, config digest, inventory summary digests, and smoke summary digest before accepting the summary.
- The summary must include SHA256 digests for the metadata-validation and redaction-validation summaries that accepted it. To avoid a self-referential digest, validators use this algorithm:
  1. Build the candidate commit-safe summary with `metadata_validation_summary_sha256 = null` and `redaction_validation_summary_sha256 = null`.
  2. Run metadata and redaction validators against the candidate summary.
  3. Write local-only validator summaries whose own payloads include the SHA256 of the candidate summary.
  4. Insert the two validator summary SHA256 values into the final commit-safe summary.
  5. Re-run validators in final mode, where the validated payload projection is the final summary with only `metadata_validation_summary_sha256` and `redaction_validation_summary_sha256` set back to null.
  6. Accept only if the final-mode validator summaries prove that projected payload digest equals the original candidate summary digest and that the validator summary digests match the final summary fields.
- Reusing an older local-only evidence directory for a new commit-safe summary is forbidden unless the summary explicitly records that it is a post-commit binding artifact and validates the original source/cache proof digest.
- Dirty-state policy must be explicit. The default should fail if relevant source, marketplace, or refresh-tool files are modified outside the committed `HEAD`.

## Locking

Both mutation modes take a refresh lock before installation. The lock prevents concurrent refresh tools from racing each other.

Both mutation modes require a no-concurrent-hook-consumer process check until app-server install atomicity is separately certified.

## Crash And Restart Recovery

Mutation modes must leave a local-only run-state marker before the first app-server install request and clear it only after final status is written. The marker records:

- `RUN_ID`
- mode
- repo `HEAD`
- tool SHA256
- pre-refresh config SHA256
- pre-refresh cache manifest SHA256 values
- snapshot paths
- current phase

At startup, mutation modes must check for abandoned run-state markers before taking the refresh lock. If a marker exists, the tool must refuse ordinary mutation and enter a recovery decision path:

- `--dry-run` and `--plan-refresh` report `blocked-preflight` and identify the abandoned run-state marker.
- `--refresh --recover <RUN_ID>` restores cache snapshots, verifies unchanged config hash, starts a fresh app-server, and proves restored inventory before allowing another mutation.
- `--guarded-refresh --recover <RUN_ID>` restores config and cache snapshots, starts a fresh app-server, and proves restored plugin enablement and hook inventory before allowing another mutation.

If the marker exists but a required snapshot is missing or digest verification fails, the tool must fail closed and point to the local-only recovery evidence. It must not attempt a new install over an unclassified abandoned partial refresh.

## Failure Behavior

`--refresh`:

- Fails before mutation for guarded-only diffs.
- Fails before mutation for coverage-gap diffs.
- Fails before mutation for unexpected marketplace registration.
- Snapshots installed cache roots before app-server install.
- Captures pre-refresh config hash and app-server inventory before app-server install.
- Verifies after install.
- If Handoff install succeeds and Ticket install fails, or any post-install inventory, equality, or smoke gate fails, restores the pre-refresh installed cache snapshot for both plugins.
- Stops the failed-run app-server child, starts a fresh app-server process, and verifies restored cache manifests, unchanged config hash, plugin enablement, runtime inventory, and hook inventory before declaring restore complete.
- Does not edit global config and therefore does not provide config rollback.

`--guarded-refresh`:

- Snapshots state before mutation.
- Disables and restores `features.plugin_hooks` when the setting exists and is true.
- On success after hook-disable mutation, starts a fresh app-server after config restore before final inventory and smoke.
- Rolls back config/cache on failed install, inventory, equality, or smoke.
- Stops the failed-run app-server child, starts a fresh app-server process, and verifies config hash, cache manifests, plugin enablement, runtime inventory, and hook inventory before declaring rollback complete.

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
- `--plan-refresh` emits the external-shell mutation plan without mutation and marks mutation modes as maintenance operations.
- `--dry-run` and `--plan-refresh` report `coverage-gap-blocked` without emitting a mutation command when coverage is missing.
- `--refresh` refuses guarded-only diffs, including unmatched paths reported as `guarded-only` with reason `unmatched-path`.
- `--refresh` refuses coverage-gap diffs.
- `--refresh` refuses to mutate unless the process gate passes.
- `--refresh` can update fast-safe-with-covered-smoke installed content through app-server install and prove runtime inventory plus source/cache equality after the process gate passes.
- `--refresh` snapshots installed cache roots and restores them if install or post-install verification fails, then proves restored config hash, cache manifests, plugin enablement, runtime inventory, and hook inventory from a fresh app-server process.
- `--guarded-refresh` enforces no-concurrent-hook-consumer checks before hook-sensitive mutation.
- `--guarded-refresh` disables/restores `features.plugin_hooks` when present and true.
- `--guarded-refresh` successful hook-disable runs collect final inventory and smoke from a fresh app-server process after config restore.
- `--guarded-refresh` snapshots and rolls back on failed install, inventory, equality, or smoke, then proves restored config hash, cache manifests, plugin enablement, runtime inventory, and hook inventory from a fresh app-server process.
- Generated residue in source or cache fails the run before equality diffing.
- Handoff hook inventory assertion matches current truth: expected empty Handoff hook inventory for Handoff 1.6.0.
- Classifier tests use canonical `<plugin>/<version>/<relative_path>` keys and assert concrete Handoff and Ticket examples.
- Classifier tests assert `fast-safe-with-covered-smoke`, `guarded-only`, and `coverage-gap-fail` outcomes.
- Classifier tests assert that `ticket/1.4.0/scripts/new_helper.py` and any other new executable path are `coverage-gap-fail`, not guarded-only.
- Classifier tests assert separate `mutation_mode` and `coverage_status` fields, so guarded mutation cannot imply covered smoke.
- Smoke selection is diff-aware for changed executable and skill-command paths.
- Skill/reference/README/CHANGELOG command-shape triggers force matching smoke or a coverage-gap failure.
- Handoff `pyproject.toml` and `uv.lock` changes require at least one installed command through the documented `uv run --project "$PLUGIN_ROOT/pyproject.toml"` shape.
- Ticket `pyproject.toml` and `uv.lock` changes require at least one installed command through the canonical `python3 -B <PLUGIN_ROOT>/scripts/<script>.py` launcher.
- App-server install and inventory tests assert the pinned request payloads, including `marketplacePath` and `remoteMarketplaceName = null`.
- All modes write local-only evidence.
- `--record-summary` writes a redaction-safe summary suitable for commit, and refresh-specific metadata/redaction validators accept it.
- Tests cover empty/no-diff, fast-safe-with-covered-smoke diff, guarded-only diff, unmatched-path reason, coverage-gap diff, generated residue, Handoff expected-empty hook inventory, marketplace mismatch, structured process-gate self-block/exemption behavior, active Ticket hook process blockers, harmless `codex` path non-blockers, wide `ps -ww` process census, truncated or unparseable process rows, app-server failure, abandoned run-state recovery, guarded successful hook-disable fresh-inventory proof, `--refresh` partial-install restore with fresh-inventory proof, command-shape smoke escalation, plugin-specific dependency-file installed-command smoke, stale evidence rejection, validator digest bootstrap, redaction rejection, and rollback failure.
