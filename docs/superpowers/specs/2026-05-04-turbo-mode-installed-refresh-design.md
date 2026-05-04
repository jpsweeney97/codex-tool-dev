# Turbo Mode Installed Refresh Tool Design

## Status

This document is a design spec only. It does not authorize an implementation until a    separate implementation plan exists.

## Purpose

Add a repeatable control tool for assessing and, during a controlled maintenance window, refreshing the live installed Turbo Mode plugins from the repo-local source authority without reusing the one-time source-migration wrapper as the normal interface.

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

Terminology:

- **Non-mutating routine developer commands**: `--dry-run`, `--plan-refresh`, local-only evidence review, and local-only prune preview. These may run from Codex sessions because they do not mutate installed cache, global config, or runtime state.
- **Maintenance-window mutation**: `--refresh`, `--guarded-refresh`, and explicit recovery runs launched from an external shell during an operator-enforced exclusive maintenance window. These are allowed by this design when their gates pass.
- **Routine mutation**: any installed-cache, global-config, or runtime mutation attempted as a normal in-session developer convenience command without the external-shell maintenance-window contract. Routine mutation remains blocked until sentinel-aware hook consumers or another enforceable exclusion mechanism is certified.

## Modes

### `--dry-run`

No installed cache, global config, or runtime mutation. Local-only evidence writes are allowed.

Responsibilities:

- Validate repo source roots exist.
- Validate repo marketplace metadata points at the repo-local Handoff and Ticket source roots.
- Validate installed cache roots are discoverable.
- Validate global config marketplace registration and plugin enablement state.
- Optionally collect read-only app-server inventory when requested by `--inventory-check`; this starts app-server but does not mutate installed cache or config.
- Build source and cache manifests.
- Compute the source/cache filesystem diff.
- Classify changed paths as `fast-safe-with-covered-smoke`, `guarded-only`, or `coverage-gap-fail`.
- Report separate state axes plus one derived terminal plan status: `refresh-allowed`, `guarded-refresh-required`, `coverage-gap-blocked`, `blocked-preflight`, `repairable-runtime-config-mismatch`, `unrepairable-runtime-config-mismatch`, `filesystem-no-drift`, or `no-drift`.
- Write local-only dry-run evidence.

### `--plan-refresh`

No installed cache, global config, or runtime mutation. Local-only evidence writes are allowed.

Responsibilities:

- Run all `--dry-run` checks.
- Select the required mutation mode, smoke tier, and coverage requirements.
- Emit the exact external-shell command that would be allowed if the process gate later passes.
- Emit a guarded external-shell command when the terminal status is `repairable-runtime-config-mismatch`.
- Emit no mutation command when the terminal status is `coverage-gap-blocked`, `blocked-preflight`, `unrepairable-runtime-config-mismatch`, `filesystem-no-drift`, or `no-drift`.
- Emit stop conditions that would block mutation, including guarded-only paths, coverage gaps, generated residue, marketplace mismatch, and expected process blockers.
- Write local-only plan evidence that can be compared with the later mutation run. The later mutation run must recompute manifests and must not trust the plan artifact as current proof.

### Terminal Plan Status

Non-mutating modes must keep filesystem drift, runtime/config state, and coverage gaps distinct:

Plan evidence must persist these fields before computing the terminal status:

| Field | Allowed values |
| --- | --- |
| `filesystem_state` | `drift`, `no-drift`, `unknown` |
| `coverage_state` | `covered`, `coverage-gap`, `not-applicable`, `unknown` |
| `runtime_config_state` | `aligned`, `unchecked`, `repairable-mismatch`, `unrepairable-mismatch`, `unknown` |
| `preflight_state` | `passed`, `blocked` |
| `selected_mutation_mode` | `refresh`, `guarded-refresh`, `none`, `unknown` |
| `terminal_plan_status` | one of the statuses below |

When multiple conditions coexist, the terminal status is selected by this precedence table. Lower-priority facts must still be recorded in the state axes and evidence details; they are not discarded just because a higher-priority terminal status wins.

| Priority | Condition | Terminal status |
| --- | --- | --- |
| 1 | `preflight_state=blocked` | `blocked-preflight` |
| 2 | `coverage_state=coverage-gap` | `coverage-gap-blocked` |
| 3 | `runtime_config_state=unrepairable-mismatch` | `unrepairable-runtime-config-mismatch` |
| 4 | `runtime_config_state=repairable-mismatch` | `repairable-runtime-config-mismatch` |
| 5 | `filesystem_state=drift` and `selected_mutation_mode=guarded-refresh` | `guarded-refresh-required` |
| 6 | `filesystem_state=drift` and `selected_mutation_mode=refresh` | `refresh-allowed` |
| 7 | `filesystem_state=no-drift` and `runtime_config_state=aligned` | `no-drift` |
| 8 | `filesystem_state=no-drift` and `runtime_config_state=unchecked` | `filesystem-no-drift` |

If the required inputs cannot be computed consistently, the status is `blocked-preflight` with a specific reason. The tool must not pick the first failed check in implementation order when a higher-precedence status is also present.

| Status | Meaning |
| --- | --- |
| `refresh-allowed` | source/cache drift exists, all changed paths are `fast-safe-with-covered-smoke`, and preflight state allows external-shell `--refresh` if the later mutation process gate passes |
| `guarded-refresh-required` | source/cache drift exists, at least one changed path is `guarded-only`, all changed paths are covered, and preflight state allows external-shell `--guarded-refresh` if the later mutation process gate passes |
| `coverage-gap-blocked` | at least one changed path is `coverage-gap-fail`; no mutation command may be emitted |
| `blocked-preflight` | generated residue, abandoned run state, missing roots, unparseable config, marketplace metadata failure, or other non-runtime preflight failure blocks planning |
| `repairable-runtime-config-mismatch` | the only runtime/config mismatch is a conflicting Turbo Mode marketplace registration that guarded refresh is allowed to repair; this status wins even when source/cache drift is otherwise fast-safe, guarded-only, or absent |
| `unrepairable-runtime-config-mismatch` | plugin enablement state, requested read-only runtime inventory, config parse state, missing config sections, or any mismatch outside guarded marketplace-registration repair is not aligned |
| `filesystem-no-drift` | source/cache manifests match and config preflight passes, but read-only runtime inventory was not requested, so runtime alignment is unproven |
| `no-drift` | source/cache manifests match, config preflight passes, and requested read-only runtime inventory aligns |

`no-drift` must not be emitted when runtime inventory was not checked. Use `filesystem-no-drift` instead.

When `runtime_config_state=repairable-mismatch`, `selected_mutation_mode` must be `guarded-refresh`. `--plan-refresh` emits only a guarded external-shell command for that status, even if the source/cache diff would otherwise be `refresh-allowed`, because marketplace repair mutates global config and uses guarded config snapshot and rollback semantics.

### `--refresh`

External-shell maintenance refresh for low-risk source/cache diffs. This mode is narrower than `--guarded-refresh`, but it still mutates the installed cache and therefore must not run while hook-capable Codex sessions are present unless a future atomic install certification explicitly changes this rule.

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
- Apply the `features.plugin_hooks` config-state machine before mutation. Disable hooks during cache mutation only for the `true` state, preserve `absent-default-enabled`, and fail before mutation for disabled, malformed, or externally changed states.
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

### Executable And Command-Bearing Surfaces

A path is executable or script-bearing for classification if any of these are true:

- canonical path matches `<plugin>/<version>/scripts/*.py`;
- canonical path matches `<plugin>/<version>/hooks/*.py`;
- canonical path is `<plugin>/<version>/hooks/hooks.json`;
- canonical path is `<plugin>/<version>/.codex-plugin/plugin.json`;
- file mode has any executable bit set;
- file begins with a shebang;
- file is referenced as a command target by a hook manifest, plugin manifest, skill doc, README, HANDBOOK, or reference doc.

For the current Handoff and Ticket trees, classifier fixture tests must enumerate every `scripts/*.py`, every `hooks/*.py`, every `hooks/hooks.json`, and every plugin manifest command-bearing path. A current script that is not listed in guarded-only or fast-safe-with-covered-smoke tables must be `coverage-gap-fail`.

Command-shape detection compares source and installed-cache file content for the same canonical path. For `changed` files, compare both projections. For `added` files, compare the source projection against an empty cache projection. For `removed` files, compare an empty source projection against the prior cache projection. Added or removed command-bearing docs are `coverage-gap-fail` unless deterministic smoke coverage exists for the new or removed command shape.

The detector should use a Markdown-aware projection when possible:

- fenced `bash`, `sh`, `shell`, or untyped command blocks;
- JSON payload examples;
- command-like lines beginning with `python`, `python3`, `uv`, `codex`, `ticket_`, or `./`;
- markdown tables containing command, state, or action columns;
- sections with headings containing `Command`, `Workflow`, `Execute`, `Prepare`, `Payload`, `Recovery`, or `Policy`.

If the projection parser fails, if the source/cache diff touches a command-bearing file but the projection cannot prove the command shape is unchanged, or if a changed doc already contains command-bearing content outside a recognized projection, the result is `coverage-gap-fail`. The fallback is intentionally conservative: changed command-bearing docs require deterministic smoke or no mutation.

Skill, reference, README, CHANGELOG, and HANDBOOK prose is also behavior when it changes agent-facing authority or operating policy. A prose change outside command-shape projections must still trigger semantic-policy classification when it changes any of these surfaces:

- plugin, project, or ticket root authority;
- permission posture, approval expectations, or sandbox expectations;
- lifecycle transitions such as prepare, execute, close, reopen, recover, repair, or rollback;
- denial, enforcement, validation, or hook behavior;
- recovery, audit-log, evidence, redaction, or certification claims;
- marketplace registration, global config, installed-cache, or runtime-inventory authority;
- operator maintenance-window obligations or process-gate claims.

Semantic-policy triggers set `mutation_mode=guarded` at minimum. They set `coverage_status=coverage_gap` unless the design names a deterministic smoke or proof that exercises the changed policy surface. A pure prose change may remain `fast-safe-with-covered-smoke` only when both command-shape and semantic-policy triggers are absent.

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
| `handoff/1.6.0/skills/**` | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching proof or coverage-gap failure |
| `handoff/1.6.0/references/**` | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching proof or coverage-gap failure |
| `ticket/1.4.0/skills/**` | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching Ticket proof or coverage-gap failure |
| `ticket/1.4.0/references/**` | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching Ticket proof or coverage-gap failure |
| `ticket/1.4.0/HANDBOOK.md` | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching Ticket proof or coverage-gap failure |
| README files | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching proof or coverage-gap failure |
| CHANGELOG files | Light smoke unless command-shape or semantic-policy triggers fire; triggers require matching proof or coverage-gap failure |
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

- `handoff/1.6.0/skills/search/SKILL.md`: fast-safe-with-covered-smoke unless command-shape or semantic-policy triggers fire without matching proof.
- `handoff/1.6.0/scripts/session_state.py`: fast-safe-with-covered-smoke, but requires session-state smoke because the changed executable path has path-specific coverage.
- `handoff/1.6.0/scripts/distill.py`: coverage-gap-fail until a deterministic distill smoke exists.
- `handoff/1.6.0/scripts/defer.py`: guarded-only.
- `handoff/1.6.0/hooks/hooks.json`: guarded-only, even though the current expected Handoff hook manifest is empty.
- `ticket/1.4.0/skills/ticket/SKILL.md`: fast-safe-with-covered-smoke only when command-shape and semantic-policy triggers are absent or have matching proof; otherwise coverage-gap-fail.
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

The app-server/runtime identity is part of the evidence contract. Before issuing install or inventory requests, the tool records:

- `codex --version` output;
- resolved `codex` executable path;
- executable SHA256 when the resolved path is a readable local file, or an explicit unavailable reason when hashing is not feasible;
- JSON-RPC `initialize` `serverInfo`;
- protocol and capability fields returned by the server;
- refresh app-server parser version and accepted response schema version.

If runtime identity cannot be captured or the returned schema is not one of the accepted schemas for the tool version, mutation modes fail before cache/config mutation. This keeps later replay from confusing refresh-tool defects with app-server behavior drift.

## Shared Helper Boundary

The refresh implementation must not import `plugins/turbo-mode/tools/migration/migration_common.py` directly. That module is bound to source-migration constants such as the migration plan path, migration base head, source-migration evidence root, and source-migration local-only root.

Allowed helper reuse requires one of these shapes:

- Extract constants-free functions into `plugins/turbo-mode/tools/turbo_mode_tooling_common.py`, with every root, plan, evidence path, and mode supplied by the caller.
- Keep refresh helpers inside `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py` until a clean shared module is justified.

Tests must fail if refresh evidence contains source-migration plan paths, source-migration evidence roots, or `MIGRATION_BASE_HEAD` metadata.

## Process Gate

Both mutation modes use the same no-concurrent-hook-consumer process gate until a separate atomicity certification changes that rule.

The refresh tool must be launched from an external maintenance shell, not from an active Codex Desktop or Codex CLI conversation. Running from inside a Codex session is expected to self-block and should be treated as correct behavior.

This process gate is sampled evidence, not enforceable machine-wide mutual exclusion. The required operational contract is an operator-enforced exclusive maintenance window: close active Codex Desktop and CLI sessions, do not start new Codex sessions during mutation, and run the mutation command from an external shell. Until hook consumers are updated to honor a machine-local maintenance sentinel, the tool can only prove that no known hook-capable consumers were observed at required census points.

Commit-safe evidence must describe this as `exclusive_window_observed_by_process_samples`, not as `concurrency_prevented`.

This sampled boundary is intentionally not the graduation target for routine mutation. A future routine mutation mode requires either sentinel-aware hook consumers that fail closed while a machine-local maintenance sentinel is active, or another enforceable OS-level exclusion mechanism. Until then, successful mutation evidence can certify only that the operator-maintained window was observed at the required samples.

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
3. **Immediately after mutation**: after final inventory and smoke, before clearing the run-state marker.

If a pre-mutation census finds blockers, the tool fails before mutation and writes a local-only process-gate summary plus a local-only raw process listing. If the post-mutation census finds blockers, the tool must fail the exclusivity evidence gate and report the refresh as `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`; it must not claim the maintenance window was clean. The installed cache may be the current on-disk state after this status, but the run is not release/maintenance-window certified and commit-safe evidence must be either suppressed or explicitly marked `exclusivity_status = "unproven"`. The run-state marker may be cleared only after final status and local-only evidence record `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`; it must not be cleared before that evidence is durable. If commit-safe evidence is enabled for that run, the commit-safe summary records only count, marker set, census label, raw listing SHA256, and run metadata. The raw process listing stays under local-only evidence.

For `--guarded-refresh`, if hooks are disabled as part of the guarded flow, an additional census must run after hook disable and immediately before cache mutation.

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

## Plugin Hooks Config State

The tool must model `features.plugin_hooks` as an explicit config state machine. It must not treat hook-disable as a generic no-op and then later require Ticket hook inventory without explaining which state made that proof valid.

| State | Detection | Planning behavior | Mutation behavior | Final inventory expectation |
| --- | --- | --- | --- | --- |
| `true` | key exists and parses as boolean `true` | certifiable | `--guarded-refresh` may atomically set false during mutation, then restore true before final inventory | Ticket Bash `preToolUse` hook must be present |
| `false` | key exists and parses as boolean `false` | `unrepairable-runtime-config-mismatch` unless a future explicit hook-enable repair mode is designed | mutation modes fail before cache/config mutation | no certified refresh summary may claim expected Ticket hook registration |
| `absent-default-enabled` | key is absent and read-only runtime inventory proves the expected Ticket hook is active | certifiable, preserving the absent key | guarded hook-disable is a recorded no-op because there is no key to toggle | Ticket Bash `preToolUse` hook must be present |
| `absent-unproven` | key is absent and runtime inventory was not requested | `filesystem-no-drift` or drift status may be reported, but hook runtime alignment is unproven | mutation modes must collect pre-refresh inventory before mutation and fail if Ticket hook is absent | Ticket Bash `preToolUse` hook must be present for certification |
| `absent-disabled` | key is absent and runtime inventory shows hooks disabled or the Ticket hook missing | `unrepairable-runtime-config-mismatch` | mutation modes fail before cache/config mutation | no certified refresh summary may claim expected Ticket hook registration |
| `malformed` | config cannot be parsed or the key has a non-boolean value | `blocked-preflight` | mutation modes fail before mutation | no runtime inventory proof is accepted |
| `externally-changed` | config SHA256 differs from the expected snapshot or intermediate state during rollback/recovery | `blocked-preflight` for new runs | rollback and `--recover` fail closed without overwriting unrelated edits | manual operator decision required |
| `restored` | rollback/recovery restored the original bytes and SHA256 | not a planning input | only used after rollback/recovery proof | inventory must match pre-run inventory |

For successful guarded mutation from a `true` starting state, final inventory must be collected only after restoring `features.plugin_hooks=true` and starting a fresh app-server process. For `absent-default-enabled`, the absent key is preserved; certification depends on fresh runtime inventory proving the expected Ticket hook is still active.

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
- Any changed skill, reference, README, CHANGELOG, or HANDBOOK file that changes command-shape instructions must be paired with a smoke that exercises that documented command shape. If the tool cannot determine whether the change is command-shape-affecting, it must require `standard` smoke or fail with a coverage gap.
- Any changed skill, reference, README, CHANGELOG, or HANDBOOK prose that changes roots, permissions, lifecycle transitions, denial/enforcement behavior, recovery, evidence claims, runtime authority, or maintenance-window policy must be treated as a semantic-policy trigger. The tool must select a matching deterministic proof or fail with a coverage gap; it must not silently keep the path in the fast lane with only light smoke.
- Any changed guarded-only Ticket engine or hook path requires at least `standard`, and the tool should recommend `full`.
- If a changed executable path has no path-specific smoke, the tool must classify the change as `coverage-gap-fail` until deterministic coverage is added.

Command-shape triggers for skill, reference, README, CHANGELOG, and HANDBOOK docs:

- fenced `bash`, `sh`, `shell`, or untyped command blocks change;
- lines beginning with `python`, `python3`, `uv`, `codex`, `ticket_`, or `./` change;
- JSON payload examples change;
- sections with headings containing `Command`, `Workflow`, `Execute`, `Prepare`, `Payload`, `Recovery`, or `Policy` change;
- markdown tables containing command/state/action fields change.

When any trigger is present in a changed skill, reference, README, CHANGELOG, or HANDBOOK doc, the tool must either select a matching command-shape smoke or fail with a coverage gap. A pure prose change outside command-shape and semantic-policy triggers may remain fast-safe-with-covered-smoke with `light` smoke.

## Evidence Policy

Every run writes local-only evidence under:

```text
/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/
```

The local-only evidence root and every per-run directory must be created with `0700` permissions. Raw artifact files, lock-owner files, marker files, process listings, app-server transcripts, config byte snapshots, and validator summaries must be written with `0600` permissions. If the existing directory permissions are broader, mutation modes fail before writing additional local evidence and instruct the operator to repair permissions.

Local-only does not mean unclassified. Raw process listings and app-server transcripts remain local-only, but the tool must still run a local sensitivity scan for token-like values, email addresses, config contents, and unexpectedly broad path disclosure. Commit-safe summaries must never include raw local-only payloads. Local-only sensitivity findings are summarized as counts, redacted examples, and affected artifact names.

Retention policy:

- Raw local-only run directories are retained for 30 days by default.
- A run referenced by a committed summary is retained until the operator explicitly prunes it, even after 30 days.
- The tool must provide a non-mutating review command, `--review-local-evidence --run-id <RUN_ID>`, that reports artifact classes, permissions, sensitivity-scan results, and prune eligibility.
- The tool must provide a prune preview command, `--prune-local-evidence --older-than <duration>`, that prints eligible run directories and reasons without deleting anything.
- Any future destructive prune execution must move selected run directories to the OS Trash and require an explicit execute flag; it must not silently delete raw evidence.

Local-only evidence requirements are mode-specific:

| Artifact | `--dry-run` | `--plan-refresh` | `--refresh` | `--guarded-refresh` |
| --- | --- | --- | --- | --- |
| run metadata with `RUN_ID`, evidence schema version, tool path, tool SHA256, repo `HEAD`, dirty-state policy, source roots, cache roots, marketplace path, and config path | required | required | required | required |
| app-server/runtime identity with `codex --version`, executable path/hash or unavailable reason, `serverInfo`, protocol capabilities, parser version, and accepted response schema version | required only when read-only inventory is requested | required only when read-only inventory is requested | required before mutation | required before mutation |
| source manifest and SHA256 | required | required | required | required |
| pre-refresh cache manifest and SHA256 | required | required | required | required |
| post-refresh cache manifest and SHA256 | not applicable | not applicable | required after install or restore | required after install or rollback |
| source/cache diff and safety classification | required | required | required | required |
| terminal plan status | required | required | required | required |
| runtime/config mismatch summary | required when mismatch is detected | required when mismatch is detected | required when mismatch is detected | required when mismatch is detected |
| selected mutation command | not applicable | required when mutation is allowed | required | required |
| process-gate summary and raw local-only process listing | not applicable | optional forecast only | required | required |
| pre-refresh config SHA256 | not applicable | not applicable | required | required |
| post-refresh config SHA256 | not applicable | not applicable | required | required |
| cache parent metadata and unexpected-side-effect scan | not applicable | not applicable | required | required |
| app-server transcript and SHA256 | not applicable | not applicable | required | required |
| runtime inventory summary and SHA256 | not applicable | not applicable | required | required |
| smoke summary and SHA256 | not applicable | not applicable | required | required |
| final status | required | required | required | required |
| restore or rollback status | not applicable | not applicable | required on failed install or post-install verification | required on failed install, inventory, equality, or smoke |

`not applicable` means the artifact must not be invented as an empty success proof. If an implementation chooses to collect extra read-only inventory during `--dry-run` or `--plan-refresh`, that behavior must be explicitly documented and must not be required for the non-mutating path.

Evidence requirements are also phase- and final-status-aware. Each final status records a `phase_reached` value and every omitted artifact records `omission_reason` rather than an empty success payload.

| Final status class | Required artifacts | Forbidden fake artifacts |
| --- | --- | --- |
| preflight stop such as `blocked-preflight`, abandoned marker, residue, malformed config, or process blockers before mutation | run metadata, any manifests/diffs already computed, terminal status, local-only blocker summary, and raw evidence for the blocker when applicable | post-refresh cache manifest, app-server install transcript, smoke summary, success inventory, restore/rollback success |
| non-mutating coverage or runtime/config stop such as `coverage-gap-blocked`, `repairable-runtime-config-mismatch`, or `unrepairable-runtime-config-mismatch` | run metadata, source/cache manifests when roots are readable, diff/classification, terminal state axes, mismatch summary when applicable | mutation transcript, post-refresh cache manifest, smoke summary, restore/rollback success |
| mutation failure before smoke with successful restore or rollback | run metadata, pre/post cache manifests, config digests, app-server transcript through the failed phase, runtime identity, restore/rollback proof, final status | smoke pass summary |
| mutation failure during smoke with successful restore or rollback | all artifacts through smoke attempt, failed smoke summary, restore/rollback proof, final status | successful smoke summary |
| `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` | full local-only mutation evidence through post-mutation census plus exclusivity-unproven final status | commit-safe certification that implies a clean maintenance window |
| successful certified mutation | all required mutation artifacts, successful smoke summary, post-mutation census, `exclusivity_status=exclusive_window_observed_by_process_samples`, final status | restore/rollback success artifacts when no restore/rollback was attempted |

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
- `codex_version`
- `codex_executable_path`
- `codex_executable_sha256`
- `codex_executable_hash_unavailable_reason`
- `app_server_server_info`
- `app_server_protocol_capabilities`
- `app_server_parser_version`
- `app_server_response_schema_version`
- `dirty_state_policy`
- `source_manifest_sha256`
- `pre_refresh_cache_manifest_sha256`
- `post_refresh_cache_manifest_sha256`
- `pre_refresh_config_sha256`
- `post_refresh_config_sha256`
- `pre_refresh_inventory_sha256`
- `post_refresh_inventory_sha256`
- `runtime_config_mismatch_summary_sha256`
- `cache_parent_metadata_sha256`
- `unexpected_side_effect_scan_sha256`
- `post_mutation_process_census_sha256`
- `exclusivity_status`
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

- A summary is current only when its `RUN_ID`, repo `HEAD`, tool SHA256, source manifest SHA256, pre-refresh cache manifest SHA256, post-refresh cache manifest SHA256, evidence schema version, app-server/runtime identity fields, accepted response schema version, runtime/config mismatch summary SHA256 when present, cache parent metadata SHA256, unexpected-side-effect scan SHA256, post-mutation process census SHA256, and exclusivity status match the run being reported.
- The metadata validator must recompute the current repo `HEAD`, worktree tool SHA256, manifest digests, config digest, inventory summary digests, smoke summary digest, runtime/config mismatch digest when present, cache parent metadata digest, unexpected-side-effect scan digest, post-mutation census digest, app-server/runtime identity fields, accepted response schema version, and exclusivity status before accepting the summary.
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

Both mutation modes require sampled no-concurrent-hook-consumer process checks and an operator-enforced exclusive maintenance window until app-server install atomicity or hook-consumer sentinel support is separately certified.

Concrete lock contract:

- Lock path: `/Users/jp/.codex/local-only/turbo-mode-refresh/refresh.lock`.
- Run-state marker directory: `/Users/jp/.codex/local-only/turbo-mode-refresh/run-state/`.
- Per-run marker path: `/Users/jp/.codex/local-only/turbo-mode-refresh/run-state/<RUN_ID>.json`.
- Lock and marker files are local-only evidence. Commit-safe summaries may record their SHA256 and status, but not raw contents.
- The refresh root and `run-state` directory must be `0700`; lock and marker files must be `0600`.
- The lock primitive is a nonblocking advisory exclusive file lock on `refresh.lock` using the platform's `fcntl`/`flock` equivalent. The implementation must hold the file descriptor open for the full mutation run.
- After acquiring the lock, the tool writes lock-owner JSON with `schema_version`, `RUN_ID`, mode, repo `HEAD`, tool SHA256, PID, parent PID, process start time, acquired timestamp, and command line by atomic temp-file replace.
- A held lock always wins over stale owner metadata. If the lock cannot be acquired, the tool fails before mutation and reports the current owner metadata when readable.
- If owner metadata exists but the lock is not held, the tool records a stale-lock observation in local-only evidence, verifies that the recorded PID/start-time no longer identifies the same process, then replaces the owner metadata after acquiring the lock.
- The run-state marker is written only after lock acquisition, but before any config, cache, marketplace, or app-server install mutation. The marker phase is updated atomically at every mutation boundary.
- Clearing the marker requires final local-only status evidence. For `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`, the marker is cleared only after that status and its post-mutation census evidence are durable.

## Crash And Restart Recovery

Mutation modes must write a local-only run-state marker before any config, cache, marketplace, or app-server install mutation and clear it only after final status is written. The marker records:

- `schema_version`
- `RUN_ID`
- mode
- repo `HEAD`
- tool SHA256
- lock-owner SHA256
- plugin-hooks config state
- pre-refresh config SHA256
- original config byte-snapshot path when config may be mutated
- pre-refresh cache manifest SHA256 values
- snapshot paths
- current phase

For `--guarded-refresh`, the original config bytes must be snapshotted before changing `features.plugin_hooks` or marketplace registration. Config mutation must be an atomic write using a temp file, fsync, and replace. Rollback and explicit `--recover` must fail closed if the current config SHA256 no longer matches the tool's expected intermediate config state, because that indicates external config mutation during the run or after a crash. In that case the tool must not blindly overwrite unrelated user edits; it must leave local-only recovery evidence and require manual operator decision.

At startup, all modes may do an advisory marker scan before taking the refresh lock. A pre-lock marker scan can only report that marker state exists; it must not decide that the marker is abandoned. If a marker exists, ordinary mutation must refuse and explicit recovery must acquire the refresh lock before acting on the marker:

- `--dry-run` and `--plan-refresh` report `blocked-preflight` and identify the run-state marker without classifying it as abandoned.
- `--refresh --recover <RUN_ID>` restores cache snapshots, verifies unchanged config hash, starts a fresh app-server, and proves restored inventory before allowing another mutation.
- `--guarded-refresh --recover <RUN_ID>` restores config and cache snapshots, starts a fresh app-server, and proves restored plugin enablement and hook inventory before allowing another mutation.

After recovery lock acquisition, if the marker exists but a required snapshot is missing or digest verification fails, the tool must fail closed and point to the local-only recovery evidence. It must not attempt a new install over an unclassified partial refresh.

Recovery lock ordering:

- Pre-lock marker reads are advisory only. They may report `blocked-preflight` for `--dry-run` and `--plan-refresh`, or tell mutation callers that recovery is required, but they must not restore files, edit config, clear markers, or classify a run as abandoned.
- Ordinary mutation modes and `--recover` modes must acquire the same refresh lock before acting on any marker state.
- After acquiring the lock, the tool must re-read the marker and lock-owner metadata, verify the lock owner is not a live active refresh, and confirm that the marker's `RUN_ID`, repo `HEAD`, tool SHA256, and lock-owner SHA256 match the recovery request.
- If the lock is still held by another process, recovery fails before mutation with an active-run blocker. A held lock wins over marker contents.
- If the lock is acquired but marker metadata indicates an owner process that is still alive with the same PID/start-time, recovery fails closed and records an inconsistent-owner blocker.
- Only after lock acquisition and active-owner rejection may `--recover` treat the marker as abandoned and restore config or cache snapshots.

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

## Implementation Plan Requirements

This design is not a single-helper-script task. The implementation plan must split delivery into staged checkpoints with tests at each layer:

1. Classifier and command-shape projection only, with fixtures for the full current Handoff and Ticket trees.
2. Non-mutating `--dry-run` and `--plan-refresh` evidence, including state axes, terminal-status precedence, and runtime/config mismatch statuses.
3. App-server client, runtime identity capture, compatibility gate, and read-only inventory parser using the pinned request contract.
4. Process census classifier and exclusive-window evidence model.
5. Locking, run-state marker, crash recovery, config snapshot, and rollback primitives.
6. `--refresh` mutation path with restore proof.
7. `--guarded-refresh` mutation path with hook-disable, config rollback, and fresh app-server final inventory.
8. Phase-aware local-only evidence, retention/review commands, commit-safe summary validators, and redaction gates.

The lock/recovery checkpoint must include active-owner fixtures: marker present with held lock, marker present with stale owner and free lock, marker present with live PID/start-time but free lock, and recovery requested for a mismatched `RUN_ID`.

Each checkpoint must have its own commit and verification gate. The full acceptance matrix should not be implemented as one undifferentiated script change.

## Acceptance Criteria

- `--dry-run` classifies source/cache drift without mutation.
- `--plan-refresh` emits the external-shell mutation plan without mutation and marks mutation modes as maintenance operations.
- `--dry-run` and `--plan-refresh` distinguish `filesystem-no-drift`, `no-drift`, `repairable-runtime-config-mismatch`, and `unrepairable-runtime-config-mismatch`.
- `--dry-run` and `--plan-refresh` persist separate `filesystem_state`, `coverage_state`, `runtime_config_state`, `preflight_state`, and `selected_mutation_mode` fields, then derive terminal status through the documented precedence table.
- `no-drift` is emitted only when source/cache manifests match, config preflight passes, and requested read-only runtime inventory aligns; otherwise matching manifests use `filesystem-no-drift`, `repairable-runtime-config-mismatch`, or `unrepairable-runtime-config-mismatch`.
- `repairable-runtime-config-mismatch` always selects `guarded-refresh`, including when source/cache drift is otherwise fast-safe or absent.
- `--plan-refresh` emits a guarded repair command only for `repairable-runtime-config-mismatch`; it emits no mutation command for `unrepairable-runtime-config-mismatch`.
- `--dry-run` and `--plan-refresh` report `coverage-gap-blocked` without emitting a mutation command when coverage is missing.
- `--refresh` refuses guarded-only diffs, including unmatched paths reported as `guarded-only` with reason `unmatched-path`.
- `--refresh` refuses coverage-gap diffs.
- `--refresh` refuses to mutate unless the process gate passes.
- `--refresh` can update fast-safe-with-covered-smoke installed content through app-server install and prove runtime inventory plus source/cache equality after the process gate passes.
- `--refresh` snapshots installed cache roots and restores them if install or post-install verification fails, then proves restored config hash, cache manifests, plugin enablement, runtime inventory, and hook inventory from a fresh app-server process.
- Mutation runs record cache parent metadata and fail if app-server install changes unexpected paths outside the two versioned Turbo Mode cache roots.
- `--guarded-refresh` enforces no-concurrent-hook-consumer checks before hook-sensitive mutation.
- `--guarded-refresh` implements the `features.plugin_hooks` config-state machine, including `true`, `false`, `absent-default-enabled`, `absent-unproven`, `absent-disabled`, `malformed`, `externally-changed`, and `restored`.
- `--guarded-refresh` disables/restores `features.plugin_hooks` only when present and true, and treats disabled or unproven hook states according to the state machine before claiming Ticket hook inventory.
- `--guarded-refresh` successful hook-disable runs collect final inventory and smoke from a fresh app-server process after config restore.
- `--guarded-refresh` snapshots and rolls back on failed install, inventory, equality, or smoke, then proves restored config hash, cache manifests, plugin enablement, runtime inventory, and hook inventory from a fresh app-server process.
- Generated residue in source or cache fails the run before equality diffing.
- Handoff hook inventory assertion matches current truth: expected empty Handoff hook inventory for Handoff 1.6.0.
- Process-gate evidence says `exclusive_window_observed_by_process_samples`, not `concurrency_prevented`, unless a later sentinel-aware design is implemented.
- Routine mutation remains blocked until a sentinel-aware hook-consumer design or other enforceable exclusion mechanism exists; sampled process evidence is not described as machine-wide exclusion.
- Mutation runs include pre-mutation, pre-install, and post-mutation process censuses.
- `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` writes durable local-only evidence before clearing the run-state marker and is not release/maintenance-window certified.
- `--recover` cannot restore files, edit config, clear markers, or classify a run as abandoned until it acquires the refresh lock and proves no active owner remains.
- Evidence validators accept legitimate fail-closed runs without requiring fake app-server, smoke, or rollback-success artifacts from phases that were never reached.
- Commit-safe summaries include runtime/config mismatch, cache parent metadata, unexpected-side-effect scan, post-mutation process census, app-server/runtime identity, and exclusivity-status fields.
- App-server/runtime identity evidence records `codex --version`, executable path/hash or unavailable reason, `initialize` `serverInfo`, protocol capabilities, parser version, and accepted response schema version.
- Local-only evidence directories are `0700`, raw files are `0600`, raw artifacts receive sensitivity classification, and review/prune commands implement the retention policy.
- Refresh locking uses the specified local-only lock path, advisory lock primitive, owner metadata, stale-lock handling, and run-state marker path/schema.
- Run-state marker is written before any config, cache, marketplace, or app-server install mutation.
- Guarded config mutation uses original byte snapshots, atomic writes, and fail-closed rollback or recovery if config changed externally.
- Classifier tests define executable/script-bearing surfaces and cover every current Handoff/Ticket `scripts/*.py`, `hooks/*.py`, `hooks/hooks.json`, and plugin manifest command-bearing path.
- Command-shape tests cover added and removed command-bearing docs by comparing against an empty projection and requiring deterministic smoke or `coverage-gap-fail`.
- Classifier tests use canonical `<plugin>/<version>/<relative_path>` keys and assert concrete Handoff and Ticket examples.
- Classifier tests assert `fast-safe-with-covered-smoke`, `guarded-only`, and `coverage-gap-fail` outcomes.
- Classifier tests assert that `ticket/1.4.0/scripts/new_helper.py` and any other new executable path are `coverage-gap-fail`, not guarded-only.
- Classifier tests assert separate `mutation_mode` and `coverage_status` fields, so guarded mutation cannot imply covered smoke.
- Smoke selection is diff-aware for changed executable and skill-command paths.
- Skill/reference/README/CHANGELOG/HANDBOOK command-shape triggers force matching smoke or a coverage-gap failure.
- Skill/reference/README/CHANGELOG/HANDBOOK semantic-policy triggers for roots, permissions, lifecycle, denial/enforcement, recovery, evidence, runtime authority, or maintenance-window claims force guarded classification and matching proof or a coverage-gap failure.
- Handoff `pyproject.toml` and `uv.lock` changes require at least one installed command through the documented `uv run --project "$PLUGIN_ROOT/pyproject.toml"` shape.
- Ticket `pyproject.toml` and `uv.lock` changes require at least one installed command through the canonical `python3 -B <PLUGIN_ROOT>/scripts/<script>.py` launcher.
- App-server install and inventory tests assert the pinned request payloads, including `marketplacePath` and `remoteMarketplaceName = null`.
- All modes write local-only evidence.
- `--record-summary` writes a redaction-safe summary suitable for commit, and refresh-specific metadata/redaction validators accept it.
- Tests cover empty/no-diff, fast-safe-with-covered-smoke diff, guarded-only diff, unmatched-path reason, coverage-gap diff, generated residue, Handoff expected-empty hook inventory, marketplace mismatch, structured process-gate self-block/exemption behavior, active Ticket hook process blockers, harmless `codex` path non-blockers, wide `ps -ww` process census, truncated or unparseable process rows, app-server failure, abandoned run-state recovery, guarded successful hook-disable fresh-inventory proof, `--refresh` partial-install restore with fresh-inventory proof, command-shape smoke escalation, plugin-specific dependency-file installed-command smoke, stale evidence rejection, validator digest bootstrap, redaction rejection, and rollback failure.
