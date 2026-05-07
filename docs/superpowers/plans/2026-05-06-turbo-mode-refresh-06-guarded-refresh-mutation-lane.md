# Turbo Mode Refresh 06 Guarded-Refresh Mutation Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first executable `--guarded-refresh` maintenance lane that can refresh the installed Turbo Mode cache from repo source only after explicit process, lock, snapshot, runtime, smoke, rollback, recovery, and evidence gates pass.

**Architecture:** Keep non-mutating planning as the default developer path, and add separate external-shell mutation paths for `--guarded-refresh` and `--recover`. Guarded refresh uses app-server `plugin/install`, not direct file copy, then proves source/cache equality, runtime inventory, smoke, and maintenance-window exclusivity before publishing commit-safe evidence. Recovery is also mutation-capable because it may restore `/Users/jp/.codex/config.toml` and installed-cache snapshots, so it must pass the same external-shell and process-gate contract before touching config or cache. The first integrated app-server mutation must run against an isolated Codex home and return a non-certified rehearsal status before any real `/Users/jp/.codex` mutation is approved.

**Tech Stack:** Python 3.11+, stdlib `argparse` / `fcntl` / `json` / `os` / `pathlib` / `shlex` / `shutil` / `subprocess` / `tempfile`, existing Turbo Mode refresh planner/classifier/app-server inventory/commit-safe validation modules, `uv run pytest`, `ruff`.

---

## Source Evidence Read

Read these before implementation:

- `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`
- `docs/superpowers/plans/2026-05-04-turbo-mode-refresh-01-classifier-state-core.md`
- `docs/superpowers/plans/2026-05-05-turbo-mode-refresh-02-non-mutating-cli.md`
- `docs/superpowers/plans/2026-05-05-turbo-mode-refresh-03-readonly-runtime-inventory.md`
- `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md`
- `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md`
- `plugins/turbo-mode/evidence/refresh/plan05-live-handoff-coverage-20260506-160049.summary.json`
- `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- `plugins/turbo-mode/tools/refresh/planner.py`
- `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- `plugins/turbo-mode/tools/refresh/commit_safe.py`
- `plugins/turbo-mode/tools/refresh/validation.py`
- `plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py`
- `plugins/turbo-mode/tools/migration/tests/test_migration_tools.py`

Historical implementation boundary:

- Plans 01 through 05 are merged on `main`.
- Current live branch at drafting time: `main`.
- Current live `HEAD` at drafting time: `bd428c758da565514b6de91493147ce28b22211a`.
- Plan 05 proves the exact Handoff state-helper direct-Python skill-doc drift is guarded covered.
- Plan 05 does not run installed-cache mutation, config mutation, rollback, recovery, or post-refresh runtime certification.

Fresh pre-plan re-anchor performed while drafting this plan:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id plan06-preplan-reanchor-20260506-1416 \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Observed result:

- `terminal_plan_status = "blocked-preflight"`.
- `runtime_config.state = "aligned"`.
- `app_server_inventory_status = "collected"`.
- `app_server_inventory.state = "aligned"`.
- `plugin_read_sources.handoff = "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0"`.
- `plugin_read_sources.ticket = "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket/1.4.0"`.
- `ticket_hook.command = "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py"`.
- `handoff_hooks = []`.
- `residue_issues` contains installed-cache generated residue:
  - `root_kind = "cache"`
  - `plugin = "handoff"`
  - `path = "scripts/__pycache__/project_paths.cpython-314.pyc"`

This residue is a hard pre-mutation blocker. Do not mutate the installed cache until an operator explicitly approves trashing the generated residue and a fresh non-mutating re-anchor returns the inherited Plan 05 expected state: `guarded-refresh-required`.

The inherited Plan 05 drift set is exactly these six canonical paths from `plugins/turbo-mode/evidence/refresh/plan05-live-handoff-coverage-20260506-160049.summary.json`:

- `handoff/1.6.0/skills/load/SKILL.md`
- `handoff/1.6.0/skills/quicksave/SKILL.md`
- `handoff/1.6.0/skills/save/SKILL.md`
- `handoff/1.6.0/skills/summary/SKILL.md`
- `handoff/1.6.0/tests/test_session_state.py`
- `handoff/1.6.0/tests/test_skill_docs.py`

Plan 06 isolated seed, rehearsal, and live evidence must preserve that set as the intended pre-refresh drift identity unless a later source/cache change is explicitly reviewed and committed before the Plan 06 source implementation boundary is recorded.

## Scope

Plan 06 implements:

- external-shell-only `--guarded-refresh`;
- external-shell-only standalone `--recover <RUN_ID>` only for guarded-refresh run-state markers created by this plan;
- mandatory isolated full-dress `--guarded-refresh` rehearsal before the first real `/Users/jp/.codex` mutation;
- first-class rehearsal proof validation before any real `/Users/jp/.codex` mutation;
- pinned app-server Codex-home/config/cache authority for isolated and real runs;
- structured process-gate classifier and local-only process evidence;
- advisory refresh lock plus owner metadata;
- run-state marker with atomic phase updates;
- cache and config snapshots before mutation;
- guarded `features.plugin_hooks` handling for `true`, `absent-default-enabled`, `absent-unproven`, `absent-disabled`, `false`, `malformed`, and `externally-changed` states;
- app-server `plugin/install` for Handoff and Ticket using the repo marketplace;
- post-install source/cache equality;
- fresh app-server runtime inventory after config restore;
- standard installed smoke sufficient for current Plan 05 guarded docs drift;
- rollback on install, inventory, equality, or smoke failure;
- local-only mutation evidence with `0700` run directories and `0600` raw artifacts;
- commit-safe mutation summary only after validators pass;
- tests for process gates, locks, markers, snapshots, rollback/recovery, app-server request shape, smoke selection, evidence redaction, and failure statuses.

Plan 06 does not implement:

- routine in-session mutation;
- sentinel-aware hook-consumer exclusion;
- concurrent refresh certification;
- `--refresh` fast lane;
- direct source-to-cache file copy as the normal install mechanism;
- global config repair for conflicting marketplace registration;
- hook-enable repair when `features.plugin_hooks = false`;
- certification from `absent-unproven`, `absent-disabled`, `false`, `malformed`, or `externally-changed` hook states;
- broad pruning or deletion of local-only evidence;
- remote publishing, branch cleanup, or PR automation.

## Operating Rules

These rules are part of the implementation contract:

- `--guarded-refresh` and `--recover` must self-block when invoked from an active Codex Desktop or Codex CLI session.
- The allowed launch shape for either mutation-capable mode is an operator-run external shell during an exclusive maintenance window.
- The process gate is sampled evidence. Commit-safe evidence must say `exclusive_window_observed_by_process_samples`, not `concurrency_prevented`.
- The operator must not reopen Codex Desktop, start `codex`, or trigger installed Ticket hook/runtime commands until the live guarded-refresh or recovery command exits. The process gate cannot prevent a process that appears after an earlier sample; it can only detect it at the next sample and downgrade the run to the appropriate non-certified status.
- Real installed-cache mutation is performed through app-server `plugin/install`.
- Direct source-to-cache file copy is allowed only for restoring the pre-refresh cache snapshot during rollback or externally-gated recovery. The only non-recovery exception in Plan 06 is isolated-home seeding for `--seed-isolated-rehearsal-home`: it may copy or synthesize minimal temporary-home config/cache/local-only state outside `/Users/jp/.codex`, must write a seed manifest with source provenance and path-guard results, must not certify anything, and must fail if any generated path resolves under `/Users/jp/.codex`.
- A source/cache equality pass is verification, not the install mechanism.
- A temporary `--codex-home` is not protective unless the app-server process is proven to read config, cache, plugin state, and local-only refresh state from that exact home. Lock, marker, recovery, evidence, rehearsal, and smoke roots must derive from the requested `codex_home`; `/Users/jp/.codex/local-only/turbo-mode-refresh` is valid only when the requested home is `/Users/jp/.codex`. If the current app-server cannot be bound to an isolated Codex home, private experiment mode and live mutation are blocked.
- Local-only raw transcripts, process listings, config snapshots, and smoke logs must not enter commit-safe evidence.
- A failed rollback or recovery is a stop condition requiring manual operator decision.
- Recovery must run process gates before any config/cache restore and after recovery inventory. If either gate blocks, recovery must not touch config/cache or must stop with local-only evidence before clearing the marker.
- Any generated residue in source or installed cache blocks mutation before snapshots.
- Any untracked relevant file under the `plugins/turbo-mode/tools/` Python import root, marketplace metadata, plugin source, or refresh evidence paths blocks mutation before `execution_head/tree` can be treated as an authoritative execution identity.
- Commit-safe evidence must record both `source_implementation_commit/tree` and `execution_head/tree`; a docs/evidence commit after implementation must not be mistaken for the source commit that produced the mutation code.
- Post-live replay validation must use explicit split roots. `source_code_root` is the checkout that supplies validator/tool/source code at `source_implementation_commit`. `execution_repo_root` is the checkout that supplied the live runtime config, app-server inventory, dirty-state checks, execution identity, and published evidence paths. Do not overload one `repo_root` for both jobs.
- Evidence failure after real installed-cache mutation must be recoverable without another cache mutation. Plan 06 must implement a non-mutating retained-run certification lane before live mutation is allowed. The lane validates retained local-only evidence for an existing run id, may publish or demote only repo-local summary files for that same run id, and must not call app-server `plugin/install`, write config, write installed cache, restore snapshots, or require the original pre-mutation `guarded-refresh-required` state.

## File Structure

Create:

- `plugins/turbo-mode/tools/refresh/process_gate.py`
  - Parse `ps -ww -axo pid,ppid,command` output into structured rows.
  - Classify Codex Desktop, every non-child `codex` CLI shape, app-server, Ticket hook/runtime, harmless rows, refresh-tool self rows, direct child app-server rows, and uncertain high-risk rows.
  - Default unrecognized non-child `codex` command rows to blocking or uncertain high-risk; do not allow mutation because a row is not exactly `codex exec`.
  - Write local-only process-gate summaries and raw listings.

- `plugins/turbo-mode/tools/refresh/lock_state.py`
  - Create and hold `<codex_home>/local-only/turbo-mode-refresh/refresh.lock` from an explicit `local_only_root` derived from the requested Codex home.
  - Write lock-owner JSON with `0600` permissions.
  - Create and atomically update run-state marker JSON under `<codex_home>/local-only/turbo-mode-refresh/run-state/`.
  - Reject active held locks and classify stale owner metadata only after lock acquisition.

- `plugins/turbo-mode/tools/refresh/mutation.py`
  - Own guarded-refresh orchestration.
  - Snapshot config bytes and installed cache manifests.
  - Apply the Plugin Hooks Config State Contract, toggling config only for `true`, preserving `absent-default-enabled`, proving `absent-unproven`, and failing closed for disabled, malformed, or externally changed states.
  - Run app-server install, post-install equality, runtime inventory, smoke, rollback, and recovery.
  - Write and validate isolated rehearsal proof records before real `/Users/jp/.codex` mutation.
  - Preserve the existing non-mutating planner boundary.

- `plugins/turbo-mode/tools/refresh/retained_run.py`
  - Own non-mutating certification for retained evidence after `MUTATION_COMPLETE_EVIDENCE_FAILED` or `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`.
  - Rebuild candidate commit-safe summaries from retained local-only evidence, not from a new installed-cache mutation.
  - Enforce split-root replay, dirty-state rules, redaction replay, summary publish/demotion behavior, and no installed-cache/config writes.

- `plugins/turbo-mode/tools/refresh/smoke.py`
  - Run standard installed smoke in a disposable repo.
  - Capture raw stdout/stderr under local-only evidence.
  - Return a redaction-safe smoke summary.

- `plugins/turbo-mode/tools/refresh/tests/test_process_gate.py`
- `plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py`
- `plugins/turbo-mode/tools/refresh/tests/test_lock_state.py`
- `plugins/turbo-mode/tools/refresh/tests/test_mutation.py`
- `plugins/turbo-mode/tools/refresh/tests/test_smoke.py`

Modify:

- `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
  - Accept `--guarded-refresh` instead of rejecting it.
  - Add standalone `--recover <RUN_ID>` as its own CLI mode. It must be mutually exclusive with `--dry-run`, `--inventory-check`, `--refresh`, and `--guarded-refresh`.
  - Add standalone `--certify-retained-run <RUN_ID>` as its own non-mutating CLI mode. It must be mutually exclusive with `--dry-run`, `--inventory-check`, `--refresh`, `--guarded-refresh`, `--recover`, `--seed-isolated-rehearsal-home`, and `--isolated-rehearsal`.
  - Add standalone `--seed-isolated-rehearsal-home` as its own CLI mode. It must be mutually exclusive with `--dry-run`, `--inventory-check`, `--refresh`, `--guarded-refresh`, and `--recover`.
  - Add `--isolated-rehearsal` as a guarded-refresh modifier. It requires `--guarded-refresh`, requires `--codex-home` outside `/Users/jp/.codex`, and is mutually exclusive with real commit-safe certification.
  - Add `--rehearsal-proof <PATH>` and `--rehearsal-proof-sha256 <SHA256>` for real `/Users/jp/.codex --guarded-refresh`; require both before lock acquisition.
  - Add `--source-implementation-commit <FULL_HASH>` and `--source-implementation-tree <TREE_HASH>`; require both for `--guarded-refresh` and `--recover`.
  - Require `--source-implementation-commit <FULL_HASH>` and `--source-implementation-tree <TREE_HASH>` for `--seed-isolated-rehearsal-home`; reject `/Users/jp/.codex` as the seed target.
  - Require summary publication for real guarded-refresh runs against `/Users/jp/.codex`. If the CLI keeps an explicit `--record-summary` flag, reject `--guarded-refresh --codex-home /Users/jp/.codex` unless `--record-summary` is present, and reject `--no-record-summary`. If a private experiment mode is ever needed, it must require a temporary `--codex-home` outside `/Users/jp/.codex` and must be unable to return `MUTATION_COMPLETE_CERTIFIED`.
  - Preserve rejection for `--refresh` in this plan.
  - Dispatch mutation work to `refresh.mutation`.

- `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
  - Own the app-server authority dataclasses, serializer, and digest contract consumed by mutation orchestration.
  - Reuse the pinned read-only inventory request contract for post-install and rollback proof.
  - Add install request builders only if they can remain constants-free and refresh-specific.
  - Add an explicit app-server launch authority contract as a Task 1A stop gate. `app_server_roundtrip()` may not rely on an implicit default home for mutation or rehearsal; it must accept and record the exact Codex home/config/cache authority, environment, cwd, executable path, and runtime identity used to launch the child. If the current app-server cannot be bound to the requested home with a named binding mechanism, stop Plan 06 before implementing process gates, lock, marker, snapshot, install, smoke, recovery, or evidence scaffolding.

- `plugins/turbo-mode/tools/refresh/commit_safe.py`
  - Add mutation-phase commit-safe fields for guarded-refresh summaries.
  - Keep Plan 05 non-mutating summary validation working.

- `plugins/turbo-mode/tools/refresh/validation.py`
  - Add schema validation for guarded-refresh mutation summaries.
  - Add allowed final statuses and omission reasons for phase-aware mutation evidence.

- `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
  - Replace existing `--guarded-refresh` rejection expectations with external-shell/process-gate tests.
  - Keep `--refresh` rejection expectations for Plan 06.

Do not modify:

- `/Users/jp/.codex/config.toml` during implementation or tests outside isolated temporary homes.
- `/Users/jp/.codex/plugins/cache/turbo-mode/` except during an explicit operator-approved live smoke or final mutation run.
- `plugins/turbo-mode/tools/migration/migration_common.py`.
- `plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py` except for read-only reference.

## Commit Boundaries

Plan 06 has three evidence boundaries and several implementation commits:

1. **Plan authority commit**
   - Contains this plan after review repair.
   - Must exist before Task 1A implementation begins.
   - If this file is still untracked, stop and create a branch from current `main`, then commit this plan before writing code.
   - If `.gitignore` carries uncommitted handoff-policy authority edits, resolve that policy conflict in a separate reviewed step before the plan authority commit. Do not smuggle a handoff-policy reversal into the Plan 06 authority boundary.

2. **Incremental implementation commits**
   - Tasks 1A through 7B may each create a separate implementation commit.
   - These commits are checkpoints, not live evidence anchors.
   - No live mutation may run from a partial implementation checkpoint.

3. **Source implementation boundary**
   - The final implementation commit after Tasks 1A through 7B and review fixes.
   - This boundary is recorded as `source_implementation_commit` and `source_implementation_tree`.
   - The live guarded-refresh run and commit-safe summary bind implementation behavior to this exact source implementation commit and tree, even if a later docs-only pre-live evidence commit exists.
   - Task 8 records this source boundary before any pre-live docs/evidence commit and before Task 9 can request live mutation approval.

4. **Live evidence/docs boundary**
   - Created only after a successful operator-approved external-shell guarded-refresh run.
   - Contains commit-safe mutation summary and completion evidence.
   - Does not change implementation source after the run that produced the evidence.
   - This boundary is recorded separately as `execution_head` and `execution_tree`, the exact checkout used to launch the live command.
   - If `execution_head/tree` differs from `source_implementation_commit/tree`, validators must prove the tree delta is limited to approved pre-live documentation/evidence files and does not modify executable source, tests, validators, marketplace metadata, or installed-cache inputs.

5. **Retained-run certification boundary**
   - Created only when a completed live mutation reaches `MUTATION_COMPLETE_EVIDENCE_FAILED` or `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` and is later certified or adjudicated without another installed-cache mutation.
   - Contains the retained-run commit-safe summary and completion/adjudication notes.
   - Records original mutation source/execution identity plus the certification validator source/execution identity.
   - Does not change installed cache, config, snapshots, or recovery markers.

Expected incremental commits:

1. **App-server authority spike**
   - Read-only app-server home-binding discovery, pre-install target authority contracts, install-authority schema checks, mock/protocol-contract tests, and operator-run local-only authority artifacts.
   - Produces exactly one of two outcomes: a validated isolated authority artifact with path/SHA256, or a blocked-plan update explaining why app-server home/install authority is unavailable.
   - Preserve validated unmocked authority artifacts, companion SHA256 files, and any manifest-referenced files until Task 9 live mutation and post-live replay are complete, or until a reviewed blocked-plan update ends the lane. Do not leave the only copy under an auto-pruned temporary directory.
   - No process gate, lock owner, run-state marker, snapshot, smoke, recovery, evidence validator, or mutation orchestration behavior.

2. **Preflight and process-control**
   - Process gate, lock owner, run-state marker, permissions helpers, and tests.
   - No app-server install behavior beyond consuming the validated Task 1A authority contract.

3. **Mutation primitives**
   - Cache/config snapshots, hook disable/restore, app-server install request builder, equality verification, rollback/recovery helpers, and tests.
   - Live mutation still not run.

4. **Installed smoke**
   - Standard smoke helper and tests.
   - Live mutation still not run.

5. **Guarded-refresh orchestration**
   - CLI dispatch, standard smoke, phase-aware local-only evidence, guarded-refresh success/failure statuses, and tests.
   - Live mutation still not run.

6. **Recovery**
   - Recovery-mode implementation and tests.
   - Live mutation still not run.

7. **Commit-safe mutation evidence**
   - Mutation summary schema, validators, and tests.
   - Live mutation still not run.

8. **Retained-run certification**
   - Non-mutating `--certify-retained-run` implementation, replay validators, dirty-state gates, summary demotion tests, and retained-run status handling.
   - Live mutation still not run.

If review fixes change mutation implementation source after a live evidence run, discard that evidence as stale and do not certify it. If review fixes change only retained-run certification validators, commit-safe builders, redaction tooling, tests, or docs/evidence needed to certify an already-mutated retained run, use `--certify-retained-run <RUN_ID>` instead of rerunning mutation, provided the retained-run allowed-delta gate passes.

## Commit And Evidence Identity Rules

Commit-safe mutation evidence must carry these four identity fields:

- `source_implementation_commit`: full commit hash for the final source implementation commit after Tasks 1A through 7B and all review fixes.
- `source_implementation_tree`: tree hash for `source_implementation_commit`.
- `execution_head`: full commit hash checked out when the external-shell `--guarded-refresh` command starts.
- `execution_tree`: tree hash for `execution_head`.

Validation rules:

- `source_implementation_commit/tree` is the authority for executable refresh code, validators, planner logic, smoke logic, app-server request builders, marketplace source files, and tests.
- `execution_head/tree` is the authority for the exact checkout state used by the live command.
- The live CLI must not infer the source implementation boundary from current `HEAD`. `--guarded-refresh` requires explicit `--source-implementation-commit` and `--source-implementation-tree` inputs, and it computes `execution_head/tree` at launch.
- The live CLI must verify that the supplied source commit exists locally and that `git rev-parse "$source_implementation_commit^{tree}"` equals the supplied source tree before any mutation.
- `execution_head` may differ from `source_implementation_commit` only when the intervening commits are documentation or evidence-record commits that do not alter executable refresh code, validators, plugin source, marketplace metadata, tests, or installed-cache input files.
- The live CLI must verify `git merge-base --is-ancestor "$source_implementation_commit" "$execution_head"` before any changed-path endpoint comparison. Endpoint tree or path equivalence alone is not sufficient provenance for Plan 06. If the source implementation commit is not an ancestor of execution head, stop before process gates, locks, snapshots, config edits, cache edits, marketplace changes, app-server install, or smoke, unless a later reviewed plan explicitly replaces ancestry with a stronger authority mechanism.
- Before process gates, locks, snapshots, config edits, cache edits, marketplace changes, app-server install, or smoke, the live CLI must compute `source_implementation_commit..execution_head` changed paths and reject any tracked delta outside approved docs/evidence paths.
- The pre-mutation allowed-delta gate must run before any mutation-capable phase. Post-mutation validators are a second line of defense, not the first enforcement point.
- The metadata validator must reject a certified summary when `execution_head != source_implementation_commit` and the allowed-delta check is absent, incomplete, or includes executable/source input paths.
- The metadata validator must reject a certified summary when `source_implementation_commit` is not an ancestor of `execution_head`.
- The metadata validator must reject a certified summary when replay code runs from a detached source checkout but runtime/config/inventory recomputation is accidentally anchored to that detached checkout. Validator CLI arguments must name `--source-code-root` and `--execution-repo-root` separately.
- The source code root is used for validator code identity, tool path digest, source manifest digest, and source implementation tree checks.
- The execution repo root is used for `execution_head/tree`, dirty-state recomputation, runtime config projection, app-server runtime inventory recomputation, current-run identity, and published summary path containment.
- Task 8 may commit pre-live verification evidence into this plan, but that docs commit must not become the only identity recorded in the live summary.
- Task 9 approval text must name both identities. If the operator wants a stricter run, stop and run live mutation from `source_implementation_commit` directly, then commit evidence afterward.
- Retained-run certification summaries must additionally record `certification_source_commit`, `certification_source_tree`, `certification_execution_head`, and `certification_execution_tree`. These identify the validator/evidence code and checkout used to certify retained local-only evidence after the original mutation. They do not replace the original mutation `source_implementation_commit/tree` and `execution_head/tree`.

## Final Status Vocabulary

Use these exact final statuses:

- `BLOCKED_PREFLIGHT`
- `BLOCKED_PROCESS_GATE`
- `BLOCKED_ACTIVE_RUN_STATE`
- `BLOCKED_RECOVERY_REQUIRED`
- `BLOCKED_UNEXPECTED_TERMINAL_STATUS`
- `BLOCKED_HOOK_CONFIG_STATE`
- `MUTATION_ABORTED_CONFIG_RESTORED`
- `MUTATION_ABORTED_RESTORE_FAILED`
- `MUTATION_FAILED_ROLLBACK_COMPLETE`
- `MUTATION_FAILED_ROLLBACK_FAILED`
- `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`
- `MUTATION_COMPLETE_EVIDENCE_FAILED`
- `MUTATION_COMPLETE_CERTIFIED`
- `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED`
- `MUTATION_REHEARSAL_FAILED`
- `RECOVERY_COMPLETE`
- `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED`

Commit-safe summaries may certify only `MUTATION_COMPLETE_CERTIFIED`. `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED`, `MUTATION_REHEARSAL_FAILED`, `RECOVERY_COMPLETE`, and every failure or blocked status are local-only in Plan 06 unless a later plan defines a complete commit-safe schema and validators for those statuses. Plan 06 bans repo-local failure summaries. A repo-local failure artifact is allowed only as the forensic demotion of an already-published `<RUN_ID>.summary.json` after a later final replay validator fails; that file must be renamed to `<RUN_ID>.summary.failed.json` with crash-safe non-overwriting rename semantics and must not be treated as commit-safe evidence. A retained-run certification may later publish `<RUN_ID>.retained.summary.json` only after the non-mutating retained-run lane validates the retained local-only evidence, records the original mutation source/execution identity, records the certification validator source/execution identity, proves no installed-cache/config mutation occurred during certification, and records the prior summary path state for the same run id.

`MUTATION_COMPLETE_EVIDENCE_FAILED` means the installed-cache mutation, final inventory, source/cache equality, smoke, and post-mutation process census succeeded, but commit-safe summary publication or validation failed. This status is not green. The installed cache may already be refreshed, and a rerun may legitimately return `no-drift` instead of the original `guarded-refresh-required` state. The recovery path for this status is `--certify-retained-run <RUN_ID>` or an explicit manual rollback/adjudication decision. Do not require another live mutation to certify a retained evidence-failed run.

Commit-safe publication rules:

- Build candidate summaries only under the local-only run root until metadata and redaction validators pass.
- Publish repo-local summaries by writing a temporary file under the target directory, fsyncing it, and atomically replacing the final `<RUN_ID>.summary.json`.
- If validation fails before atomic publish, leave no repo-local summary file; record `MUTATION_COMPLETE_EVIDENCE_FAILED` only in local-only evidence.
- If atomic publish succeeds but a later final replay validator fails, demote the repo-local file to `<RUN_ID>.summary.failed.json` with a crash-safe non-overwriting rename before returning, and write a local-only evidence-failed status that names the failed path. If the failed-summary path already exists, stop with local-only evidence and do not overwrite prior forensic evidence.
- Closeout validators must reject any run id where `<RUN_ID>.summary.json` and `<RUN_ID>.summary.failed.json` coexist. Coexistence means demotion was interrupted or externally corrupted, and no completion evidence may be recorded until the path state is manually adjudicated.
- A repo-local `<RUN_ID>.summary.json` may exist only for a certified summary whose final validators passed.
- A repo-local `<RUN_ID>.retained.summary.json` may exist only for a certified retained-run summary whose retained-run final validators passed. It must not coexist with `<RUN_ID>.summary.json`, because that would create two green-looking completion summaries for one run id. It may coexist with `<RUN_ID>.summary.failed.json` only when the retained summary records `prior_failed_summary_path`, `prior_failed_summary_sha256`, `prior_failed_summary_status = "forensic-demotion-retained"`, and the failed summary remains unmodified.

Retained-run certification rules:

- `--certify-retained-run <RUN_ID>` is non-mutating. It must refuse to call app-server `plugin/install`, write `/Users/jp/.codex/config.toml`, write `/Users/jp/.codex/plugins/cache/turbo-mode/`, restore snapshots, clear recovery markers, seed rehearsal homes, or run guarded refresh.
- It may run only when the retained local-only run root exists and contains a durable terminal status of `MUTATION_COMPLETE_EVIDENCE_FAILED` plus successful mutation facts: install authority, final inventory, source/cache equality, standard smoke, non-blocking process summaries, and post-mutation cache manifest. It may inspect `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`, but only to produce retained-uncertified/manual-adjudication output unless the retained evidence proves the status was misclassified and every required original process gate was non-blocking.
- It must accept `terminal_plan_status = "no-drift"` for the current installed cache when retained evidence proves the prior mutation already refreshed the cache. It must also accept `guarded-refresh-required` only when retained evidence proves the installed cache was rolled back or never changed. It must not require `guarded-refresh-required` as a universal certification precondition.
- It must use split roots: `mutation_source_code_root` for the original mutation source implementation commit, `certification_source_code_root` for the validator/evidence code used to certify the retained run, and `execution_repo_root` for current runtime/config/evidence recomputation. The commit-safe summary must name all three roots and their commits/trees.
- If `certification_source_commit` differs from the original mutation `source_implementation_commit`, the allowed delta must be limited to validators, commit-safe summary builders, redaction tooling, tests, and docs/evidence needed to certify the retained run. Changes to mutation orchestration, app-server install behavior, plugin source, marketplace metadata, smoke semantics, or installed-cache input files block retained-run certification.
- Dirty-state rules are stricter than live closeout: before publish, the execution repo may contain only the retained-run candidate artifacts under the local-only root and no tracked or untracked relevant source, plugin, marketplace, tool import-root, installed-cache input, or repo evidence paths. During final replay after publish, the only allowed dirty relevant repo path is `plugins/turbo-mode/evidence/refresh/<RUN_ID>.retained.summary.json`.
- Candidate summaries are rebuilt under the retained local-only root. Publication and final replay use the same atomic publish, split-root validation, redaction replay, final-scan, and crash-safe demotion rules as the original live path, but the retained lane publishes only `<RUN_ID>.retained.summary.json`.
- If retained-run certification starts with an existing `<RUN_ID>.summary.failed.json`, it must keep that file in place as immutable forensic evidence and record its SHA256 in the retained summary. If `<RUN_ID>.summary.json` also exists, stop for manual path-state adjudication before building a retained candidate. If `<RUN_ID>.retained.summary.json` or `<RUN_ID>.retained.summary.failed.json` already exists, stop instead of overwriting prior retained-certification evidence.
- If retained-run certification fails before publish, leave no repo-local retained summary and write a local-only retained-certification failure status. If it fails after publish, demote `<RUN_ID>.retained.summary.json` to `<RUN_ID>.retained.summary.failed.json` with crash-safe non-overwriting rename semantics and write a local-only failure status that preserves replay roots.
- Closeout must state whether the refreshed cache is retained uncertified, retained certified, manually rolled back, or awaiting operator decision. Do not collapse these into green completion.

## Guarded Mutation Phase State Machine

The phase table is the authority for implementation. Task APIs and tests must make these transitions executable before orchestration code is accepted.

| Phase | Persisted fields before entering or immediately after action | Mutation performed in phase | Allowed next phases | Failure status | Required restore action | Marker rule | Commit-safe eligibility |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `lock-acquired` | lock owner JSON, recovery owner absent, original owner absent | none | `marker-started` | `BLOCKED_ACTIVE_RUN_STATE` or `BLOCKED_PROCESS_GATE` | none | no marker yet | no |
| `marker-started` | run id, mode, source implementation commit/tree, execution head/tree, tool SHA256, original run owner SHA256, phase, no snapshot paths | none | `before-snapshot-process-checked` | `BLOCKED_PROCESS_GATE` | none | clear marker after local-only blocker evidence | local-only failure evidence only |
| `before-snapshot-process-checked` | process summary SHA256 for `before-snapshot` | none | `app-server-launch-authority-proven` | `BLOCKED_PROCESS_GATE` | none | clear marker after local-only blocker evidence | local-only failure evidence only |
| `app-server-launch-authority-proven` | `pre_snapshot_app_server_launch_authority_sha256`, app-server executable/version/schema/home-authority status | none | `pre-refresh-inventory-proven` for `absent-unproven`, otherwise `snapshot-written` | `BLOCKED_PREFLIGHT` | none | clear marker after local-only authority blocker evidence | local-only failure evidence only |
| `pre-refresh-inventory-proven` | pre-refresh runtime inventory SHA256 and hook-state proof for `absent-unproven` only | none | `snapshot-written` | `BLOCKED_HOOK_CONFIG_STATE` | none | clear marker after hook-state blocker evidence | local-only failure evidence only |
| `snapshot-written` | `pre_snapshot_app_server_launch_authority_sha256`, config snapshot path, config SHA256, cache snapshot root, source manifest SHA256 map, pre-refresh cache manifest SHA256 map, snapshot manifest digest, recovery eligibility `restore-cache-and-config` | cache/config snapshots only | `hooks-disabled` | `BLOCKED_HOOK_CONFIG_STATE` or `MUTATION_ABORTED_CONFIG_RESTORED` | restore config only if any config write happened; cache restore not needed before install | clear marker only after evidence and restore proof when restore occurred | local-only failure evidence only |
| `hooks-disabled` | plugin-hooks start state, hook-disabled config SHA256 when hooks were toggled, expected intermediate config SHA256, original config SHA256 retained | may write `<codex_home>/config.toml` from `plugin_hooks=true` to `false` | `after-hook-disable-process-checked` | `MUTATION_ABORTED_CONFIG_RESTORED` or `MUTATION_ABORTED_RESTORE_FAILED` | restore original config bytes and verify original config SHA256 | clear marker only after config restore proof; retain marker if restore fails | local-only failure evidence only |
| `after-hook-disable-process-checked` | process summary SHA256 for `after-hook-disable` | none | `before-install-process-checked` | `MUTATION_ABORTED_CONFIG_RESTORED` or `MUTATION_ABORTED_RESTORE_FAILED` | restore original config bytes and verify original config SHA256 | clear marker only after restore proof; retain marker if restore fails | local-only failure evidence only |
| `before-install-process-checked` | process summary SHA256 for `before-install` | none | `install-complete` | `MUTATION_ABORTED_CONFIG_RESTORED` or `MUTATION_ABORTED_RESTORE_FAILED` | restore original config bytes and verify original config SHA256 | clear marker only after restore proof; retain marker if restore fails | local-only failure evidence only |
| `install-complete` | `pre_install_app_server_target_authority_sha256` persisted before first `plugin/install` request; app-server install transcript SHA256, `AppServerInstallAuthority` digest, post-install cache manifest SHA256 map, app-server child PID record, failed/succeeded plugin install status | app-server `plugin/install` may mutate installed cache only after pre-install target authority is recorded | `config-restored-before-final-inventory` or rollback | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | restore original config and both cache roots from snapshots; start fresh app-server and verify rollback inventory | `pre_install_app_server_target_authority_sha256` must be durable before first install request; clear marker only after rollback-complete evidence; retain marker if rollback fails | local-only failure evidence only |
| `config-restored-before-final-inventory` | restored config SHA256, config restore proof, terminated install app-server child record | may restore `<codex_home>/config.toml` to original bytes | `inventory-complete` or rollback | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | verify or restore original config SHA256, restore cache roots, then prove fresh rollback inventory | clear marker only after rollback-complete evidence; retain marker if rollback fails | local-only failure evidence only |
| `inventory-complete` | fresh app-server runtime inventory SHA256, runtime identity fields, child PID record | none | `equality-complete` or rollback | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | verify or restore original config SHA256, restore cache roots, then prove fresh rollback inventory | clear marker only after rollback-complete evidence; retain marker if rollback fails | local-only failure evidence only |
| `equality-complete` | post-refresh source/cache equality summary SHA256, post-refresh cache manifest SHA256 map | none | `smoke-complete` or rollback | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | verify or restore original config SHA256, restore cache roots, then prove fresh rollback inventory | clear marker only after rollback-complete evidence; retain marker if rollback fails | local-only failure evidence only |
| `smoke-complete` | smoke summary SHA256, selected smoke tier, smoke result digests | disposable smoke repo writes only | `post-mutation-process-checked` or rollback | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | verify or restore original config SHA256, restore cache roots, then prove fresh rollback inventory | clear marker only after rollback-complete evidence; retain marker if rollback fails | local-only failure evidence only |
| `post-mutation-process-checked` | process summary SHA256 for `post-mutation`, exclusivity status | none | `evidence-published` or `exclusivity-unproven` | `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` | no rollback; mutation completed but maintenance-window proof failed | clear marker after exclusivity-unproven evidence is durable | no green certified summary; retained lane may publish only uncertified/adjudication status unless original process evidence is proven non-blocking and the status is explicitly corrected |
| `evidence-published` | candidate/final commit-safe summary paths, metadata validator SHA256, redaction validator SHA256, published summary SHA256 | repo evidence summary write only | `certified` | `MUTATION_COMPLETE_EVIDENCE_FAILED` | no rollback by default; mutation completed but evidence failed | clear marker only after evidence-failed local-only status is durable | no certified summary |
| `certified` | final status `MUTATION_COMPLETE_CERTIFIED`, published summary path, final status evidence SHA256 | none | terminal | none | none | clear marker after certified local-only status is durable | certified |

Additional state-machine rules:

- The marker may start sparse, but it must be atomically enriched after snapshots and before hook disable. Hook disable is forbidden while snapshot paths, snapshot manifest digest, original config SHA256, and recovery eligibility are absent.
- The pre-snapshot app-server launch authority digest must be persisted in the marker before `snapshot-written`. Snapshot creation, hook disable, config writes, cache writes, live app-server install, smoke, and recovery scaffolding are forbidden when `pre_snapshot_app_server_launch_authority_sha256` is absent.
- The pre-install app-server target authority digest must be persisted in the marker before the first `plugin/install` request. `plugin/install` is forbidden when `pre_install_app_server_target_authority_sha256` is absent, stale, or not tied to the current run id/source/execution identity and install child.
- A phase update that changes only `phase` is allowed only when no new recovery-critical fields are produced by the phase. Snapshot, hook-disable, install, inventory, equality, smoke, process-census, rollback, and evidence phases require atomic full-state replacement.
- Every process gate that runs after `hooks-disabled` must restore the original config on failure before returning. It may not report a simple `BLOCKED_PROCESS_GATE` because config mutation has already happened.
- Every rollback after `install-complete` must verify or restore original config bytes before rollback inventory. A rollback path may not prove cache restoration while leaving config restoration unproven.
- Every rollback and recovery proof must start a fresh app-server process. The app-server child used during install or while hooks were disabled is not valid final proof.
- Recovery is a mutation path. It must run the same process classifier before restore and after recovery inventory, with active Codex Desktop, Codex CLI, hook, runtime, uncertain high-risk, or unrelated app-server processes blocking recovery before config/cache writes.
- Commit-safe certification requires the terminal `certified` phase. Any earlier terminal state may be documented, but it must not be labeled green.

## Owner Evidence Model

Lock-owner evidence has three separate identities:

- `original_run_owner`: the owner JSON and SHA256 written by the run that created the marker.
- `stale_owner_observation`: immutable local-only copy of stale owner metadata observed before recovery replaces lock owner metadata.
- `recovery_owner`: the owner JSON and SHA256 written by the recovery process after acquiring the lock.

Recovery must not overwrite the only copy of original owner proof. Before writing the recovery owner, it must copy the stale/original owner JSON into the recovery run's local-only evidence and record that copy's SHA256. Recovery validates marker `original_run_owner_sha256` against the preserved original owner SHA256, not against the newly written recovery owner.

Owner start identity collection is part of the lock contract. On macOS, collect it with:

```bash
ps -ww -o pid=,ppid=,lstart=,command= -p "$OWNER_PID"
```

Store the raw row SHA256 and parsed `lstart` value in `LockOwner`. If the row is missing, ambiguous, truncated, or unparsable, stale-owner recovery must fail closed rather than treating PID alone as identity. Tests must cover PID reuse by presenting the same PID with a different `lstart` and asserting recovery rejects it.

## App-Server Failure Taxonomy

App-server install and inventory failures must map to explicit phases and recovery actions:

| Failure | Phase | Status | Recovery action |
| --- | --- | --- | --- |
| app-server executable missing, version unavailable, or Codex-home authority unproven | before `snapshot-written` and before any hook disable | `BLOCKED_PREFLIGHT` | none |
| app-server executable/version/home-authority check is attempted after hooks were touched and fails | after `hooks-disabled` | `MUTATION_ABORTED_CONFIG_RESTORED` or `MUTATION_ABORTED_RESTORE_FAILED` | restore config when hooks were disabled |
| app-server child fails to start before any install request | before `install-complete` | `MUTATION_ABORTED_CONFIG_RESTORED` if hooks were disabled, otherwise `BLOCKED_PROCESS_GATE` or `BLOCKED_PREFLIGHT` | restore config when hooks were disabled |
| Handoff `plugin/install` fails before Ticket install | `install-complete` attempted | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | restore config and both cache roots |
| Handoff install succeeds and Ticket install fails | `install-complete` attempted | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | restore config and both cache roots |
| app-server response schema drift during install/read/list/hooks | install or inventory phase | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | restore config and both cache roots |
| app-server timeout or stdout close during install | install phase | `MUTATION_FAILED_ROLLBACK_COMPLETE` or `MUTATION_FAILED_ROLLBACK_FAILED` | terminate child, restore config and cache, prove with fresh child |
| failed-run app-server child cannot terminate | rollback phase | `MUTATION_FAILED_ROLLBACK_FAILED` | retain marker and require manual decision |
| fresh rollback inventory cannot be collected | rollback phase | `MUTATION_FAILED_ROLLBACK_FAILED` | retain marker and require manual decision |

Tests must cover at least: executable/version/home-authority proof before hook disable, child start failure before install, Handoff install failure, Ticket install failure after Handoff success, install response assertions, response schema drift, timeout, stdout close, child termination failure, and rollback inventory failure.

## App-Server Home Authority Contract

The app-server launch contract is a hard precondition for isolated rehearsal and live mutation.

`app_server_inventory.py` must define the app-server authority dataclasses, serializer, and digest helpers. `mutation.py` must consume those records, not redefine a second authority proof shape.

Implementation must define an `AppServerLaunchAuthority` record for pre-snapshot launch/read authority with:

- requested `codex_home`;
- resolved config path;
- resolved plugin cache root;
- resolved local-only refresh root;
- child environment additions/removals;
- child cwd;
- resolved `codex` executable path and SHA256 or unavailable reason;
- `codex --version`;
- JSON-RPC `initialize.serverInfo`;
- accepted protocol/capability/schema version;
- proof that `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` responses came from the requested home and marketplace, not from an implicit default home. When the install child is intentionally launched while `features.plugin_hooks = false`, the install-child `hooks/list` response is a hook-disabled runtime proof and must record zero hooks; the fresh child after config restore remains the hook-certifying proof.

Implementation must define an `AppServerPreInstallTargetAuthority` record before any unmocked `plugin/install` request with:

- requested `codex_home`;
- resolved plugin cache root that the install operation promises to mutate;
- binding mechanism name and value, such as a CLI flag, environment variable, config path, or app-server protocol field;
- app-server executable path/version/schema digest;
- pre-install read/list authority digest for the same child or a proof that the install target authority was derived before the install child starts;
- proof that the requested marketplace and install destination root are outside `/Users/jp/.codex` for isolated runs;
- proof that the app-server exposed this target before any install write, not only after observing a post-install path.

Implementation must also define an `AppServerInstallAuthority` record for install-phase authority with:

- requested `codex_home`;
- pre-install target authority digest;
- launch authority digest for the child used for install;
- child launch/read authority recorded before the first `plugin/install` request;
- Handoff and Ticket install request digests;
- Handoff and Ticket install response digests;
- expected plugin ids and versions;
- requested marketplace path and remote marketplace value;
- installed destination paths under the requested plugin cache root;
- accepted sparse install success/auth schema and request-id correlation;
- same-child and fresh-child post-install app-server corroboration digests;
- pre-install and post-install cache manifest digests;
- per-plugin post-install cache delta digests.

The install child must have its own `AppServerLaunchAuthority` and `AppServerPreInstallTargetAuthority` recorded and digested before any `plugin/install` request is sent. Do not reuse a pre-snapshot launch/read authority digest from a different child unless the implementation also proves it is the same live child process, with the same executable identity, environment, cwd, requested home, accepted schema, and pre-install target authority. A post-install destination path is not sufficient to prove pre-install target authority.

Do not assume that `--codex-home` on the refresh tool binds the app-server child. Task 1A must discover and encode the actual mechanism used by the current Codex runtime to choose config/cache/home before broader mutation scaffolding begins. Candidate mechanisms include an app-server CLI flag, a parent `codex` CLI flag that app-server honors, a dedicated environment variable, an explicit config path, or an app-server protocol field. If no named mechanism can bind the app-server child to an isolated home and expose the install target before writes, Plan 06 stops before process gate, lock state, marker state, snapshots, install, smoke, recovery, evidence validation, isolated rehearsal, or live mutation are implemented.

Before any real-home mutation request, and before process gate, lock, marker, snapshot, recovery, smoke, or evidence scaffolding is implemented, Task 1A must run read-only home-binding discovery:

1. Create an isolated temporary Codex home with sentinel config/cache/plugin state.
2. Ensure the real `/Users/jp/.codex` home has no matching sentinel.
3. Enumerate binding surfaces with read-only commands and protocol probes, including `codex app-server --help`, parent `codex --help`, documented or observed environment variables, config-path options, and app-server initialization/request fields.
4. Launch app-server with each candidate home-binding mechanism.
5. Collect `initialize`, `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`.
6. Prove returned plugin paths, marketplace source, hook command paths, and local-only roots are under the requested home or requested repo marketplace, as appropriate.
7. Stop with a structured local-only blocker report if no candidate mechanism proves read/list/hooks authority for the isolated home.

Task 1A must then prove pre-install target authority before any unmocked `plugin/install` request:

1. Use only read-only app-server requests, protocol metadata, or documented CLI/config/environment binding semantics to prove the plugin install destination cache root for the requested isolated home.
2. Record `AppServerPreInstallTargetAuthority` with path/SHA256 and no-real-home checks.
3. Fail before any install request if the app-server cannot expose or mechanically prove the install target root before writing.
4. Do not infer install target safety from a future install response, post-install cache delta, or post-write path observation.

Only after read-only home-binding discovery and pre-install target authority pass may Task 1A run the separately approved isolated install spike:

1. Run `plugin/install` for Handoff and Ticket against the requested repo marketplace into the isolated home.
2. Treat each sparse `plugin/install` response only as an install write-completion signal. It must still be tied to the exact request id and must have the accepted generic success/auth schema returned by the current app-server runtime.
3. After install, collect post-install app-server corroboration from the requested isolated home with `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` on both the same install child and a fresh app-server child.
4. Prove Handoff and Ticket identity from the combination of pre-install request identity, app-server post-install read/list/hooks corroboration, installed skill/hook paths under the requested isolated cache root, and local installed-cache manifest digests. Do not infer identity from the sparse install response alone.
5. Compute and record post-install cache manifest delta from local installed-cache evidence rather than requiring `plugin/install` to echo that delta.
6. A generic success response without post-install app-server corroboration remains a blocker and must not be treated as install authority.
7. Fail before process gate, lock, marker, snapshots, hook disable, config writes, real cache writes, real app-server install, smoke, recovery, or evidence scaffolding if any response or post-install path resolves to `/Users/jp/.codex` during an isolated run. This failure is still a blocker because the pre-install or post-install proof was wrong; it is not acceptable proof to continue.

Task 1A has only two valid outcomes:

- `authority-validated`: local-only artifacts exist with path/SHA256 for read-only home-binding discovery, pre-install target authority, executable identity, requested home, marketplace, install request/response digests, same-child and fresh-child post-install app-server corroboration, installed path proof, cache delta proof, and no-real-home path proof.
- `blocked-plan-update`: this plan is patched before implementation continues, naming the failed authority field and choosing one reviewed path: update the Codex app-server/protocol, replace `plugin/install` authority with another approved mechanism, or stop Plan 06.

Do not convert a sparse or generic `plugin/install` success payload into a warning, best-effort proof, or implementation TODO. Plan 06 now chooses a different authority mechanism: sparse install success is accepted only as a write-completion signal, and install authority is established by pre-install authority plus post-install app-server read/list/hooks corroboration and local manifest proof.

Live `/Users/jp/.codex` runs must perform only the launch/read authority proof before snapshots: executable identity, version, accepted schema, requested-home config/cache/local-only path binding, and read-only `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` authority. Live real-home `plugin/install` is forbidden before `snapshot-written` is durable and before the marker records `pre_snapshot_app_server_launch_authority_sha256`, snapshot paths, snapshot manifest digest, original config SHA256, pre-refresh cache manifest SHA256 map, and recovery eligibility. Real install authority proof is collected in the `install-complete` phase after snapshots and before config restore/final inventory.

## Isolated Rehearsal Proof Contract

Real `/Users/jp/.codex --guarded-refresh` must be mechanically bound to a successful isolated rehearsal. Do not satisfy this gate with an informal statement that a rehearsal exists.

An isolated rehearsal must write a local-only `rehearsal-proof.json` and companion SHA256 file under the isolated home's local-only refresh root. The proof record must include:

- `schema_version`;
- `rehearsal_run_id`;
- `seed_run_id`;
- `seed_manifest_path`;
- `seed_manifest_sha256`;
- `seed_expected_drift_paths_sha256`;
- `seed_source_manifest_sha256`;
- `seed_pre_refresh_cache_manifest_sha256`;
- `seed_post_seed_dry_run_manifest_sha256`;
- `isolated_dry_run_id`;
- `isolated_dry_run_proof_sha256`;
- `source_implementation_commit`;
- `source_implementation_tree`;
- `execution_head`;
- `execution_tree`;
- `source_to_rehearsal_execution_delta_status`;
- `source_to_rehearsal_changed_paths_sha256`;
- `source_to_rehearsal_allowed_delta_proof_sha256`;
- `tool_sha256`;
- `requested_codex_home`;
- `app_server_authority_proof_sha256`;
- `no_real_home_authority_proof_sha256`;
- `smoke_summary_sha256`;
- `final_status = "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"`;
- `certification_status = "local-only-non-certified"`.
- `referenced_artifacts`: sorted list of relative artifact paths and SHA256s for the seed manifest, isolated dry-run proof, source-to-rehearsal delta proof, app-server authority proof, no-real-home proof, smoke summary, and any other file whose digest is required to validate the rehearsal proof.

The proof is valid only when all of these checks pass:

- `requested_codex_home` is outside `/Users/jp/.codex`;
- final status is exactly `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED`;
- seed manifest records the exact Plan 05 six-path drift set, the source manifest digest used to seed the isolated home, the pre-refresh cache manifest digest that models the old/drifted installed state, and a post-seed dry-run manifest proving the isolated home still classifies as the same guarded drift before rehearsal;
- source implementation commit/tree matches the live command inputs;
- rehearsal `tool_sha256` matches the digest of the source implementation tool path used for the rehearsal;
- rehearsal `execution_head/tree` is either identical to the source implementation commit/tree with `source_to_rehearsal_execution_delta_status = "identical"`, an empty changed-path list whose SHA256 is recorded in `source_to_rehearsal_changed_paths_sha256`, and a proof digest in `source_to_rehearsal_allowed_delta_proof_sha256` that records the no-delta decision, or has `source_to_rehearsal_execution_delta_status = "approved-docs-evidence-only"` with a changed-path proof that excludes executable refresh code, validators, plugin source, marketplace metadata, tests, and installed-cache input files;
- app-server authority proof records the isolated home as the requested home;
- no config, cache, plugin, hook, local-only, installed, or smoke path resolves under `/Users/jp/.codex`;
- seed manifest digest, isolated dry-run proof digest, source-to-rehearsal allowed-delta proof digest, app-server authority proof digest, no-real-home proof digest, and smoke summary digest match the files on disk;
- the app-server authority proof digest is the same digest recorded in the rehearsal final evidence.

Real `/Users/jp/.codex --guarded-refresh` must require `--rehearsal-proof <PATH>` and `--rehearsal-proof-sha256 <SHA256>`. It must validate the proof before process gates, lock acquisition, marker creation, snapshots, config edits, cache edits, app-server install, smoke, or repo-local summary publication. A stale proof from another source commit/tree, an isolated proof whose files are missing or digest-mismatched, or a proof with any real-home path is a preflight rejection.

After validation and before any live mutation phase, the live run must copy the validated rehearsal proof, its companion SHA256 file, and every digest-referenced artifact named in `referenced_artifacts` into the live run's local-only evidence root under `rehearsal-proof-capture/`. The copy must preserve relative names, write files with `0600` permissions, fsync files and parent directories, and write a capture manifest with source path, captured path, SHA256, byte size, and capture time for each artifact. Live mutation is forbidden until the capture manifest validates against the original proof and companion SHA256. Later certification and retained-run replay must read the captured proof bundle from the live local-only evidence root, not from `/private/tmp` or another isolated-home path that may disappear.

Until the live capture succeeds and post-live replay completes, the original isolated rehearsal proof bundle must also remain available at the operator-approved path or at a reviewed durable relocation path with the same SHA256. If the proof bundle was created under disposable temporary storage, copy it to a durable local-only evidence location and record the relocation path and SHA256 before Task 9 approval. Do not ask the operator to approve a live mutation from a rehearsal proof whose only copy may be pruned or deleted before replay.

## Plugin Hooks Config State Contract

Plan 06 inherits the design spec's `features.plugin_hooks` state machine. Implementation must not silently narrow certification to only the `true` state.

| State | Detection | Guarded-refresh behavior | Certification rule |
| --- | --- | --- | --- |
| `true` | key exists and parses as boolean `true` | snapshot original bytes, set key to `false` during guarded install, restore original bytes before final inventory | certifiable only after fresh final inventory proves expected Ticket Bash `preToolUse` hook |
| `absent-default-enabled` | key absent and read-only runtime inventory proves expected Ticket hook active | preserve absent key; hook-disable phase records no config write and expected intermediate SHA256 equals original config SHA256 | certifiable only after fresh final inventory proves expected Ticket Bash `preToolUse` hook and the key remains absent |
| `absent-unproven` | key absent and runtime inventory was not requested or was unavailable | collect pre-refresh runtime inventory after `before-snapshot` process census and before snapshots; fail before snapshot or mutation if Ticket hook is absent or inventory cannot prove enablement | not certifiable until promoted to `absent-default-enabled` by collected inventory |
| `absent-disabled` | key absent and runtime inventory shows hooks disabled or Ticket hook missing | fail before cache/config mutation | no certified summary |
| `false` | key exists and parses as boolean `false` | fail before cache/config mutation; Plan 06 does not implement hook-enable repair | no certified summary |
| `malformed` | config cannot be parsed or key is non-boolean | fail before cache/config mutation | no certified summary |
| `externally-changed` | current config SHA256 differs from recorded original or expected intermediate SHA256 during rollback/recovery | fail closed without overwriting unrelated edits | manual operator decision required |

Required tests:

- `true` toggles to `false` only after snapshot metadata is durable, then restores original bytes before final inventory.
- `absent-default-enabled` performs no config write, preserves absent key, and remains certifiable only through fresh hook inventory.
- `absent-unproven` forces pre-refresh inventory after `before-snapshot` process census and before snapshots, then fails before snapshot or mutation when inventory cannot prove the Ticket hook.
- `absent-disabled`, `false`, and `malformed` fail before mutation and cannot produce certified summaries.
- `externally-changed` during rollback or recovery records `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED` or the matching rollback-failed status and retains the marker.

## Smoke Proof Boundary

Plan 06 standard smoke is direct installed-command smoke plus app-server runtime inventory. It does not prove full in-chat skill invocation through Codex's natural language planner. Commit-safe evidence must describe this as `installed_command_and_runtime_inventory_smoke`, not as end-to-end conversational skill proof.

End-to-end skill invocation proof is future scope unless a deterministic skill execution API is added to the smoke harness. If a reviewer or operator requires conversational proof before mutation, stop and split that work into a separate plan before executing Task 9.

## Standard Smoke Fixtures

Task 4 must encode these exact installed-cache command shapes and fixture paths. The implementation may use temporary directories, but the command templates and expected outcomes must stay equivalent.

The plugin roots must derive from the `codex_home` passed to `run_standard_smoke()`. The canonical command strings stay equivalent to installed-cache execution, but isolated rehearsal smoke must never read `/Users/jp/.codex/plugins/cache`. Tests must prove an isolated rehearsal with a temporary `codex_home` resolves Handoff and Ticket roots under that temporary home and rejects any real-home path.

Common scratch layout:

```bash
#!/usr/bin/env bash
set -euo pipefail
SMOKE_ROOT="$(mktemp -d /private/tmp/turbo-mode-refresh-smoke.XXXXXX)"
SMOKE_REPO="$SMOKE_ROOT/repo"
SMOKE_STATE="$SMOKE_ROOT/state"
SMOKE_PAYLOADS="$SMOKE_REPO/.smoke-payloads"
mkdir -p "$SMOKE_REPO/docs/tickets" "$SMOKE_PAYLOADS" "$SMOKE_STATE"
git -C "$SMOKE_REPO" init
CODEX_HOME="${CODEX_HOME:?CODEX_HOME is required}"
HANDOFF_PLUGIN="$CODEX_HOME/plugins/cache/turbo-mode/handoff/1.6.0"
TICKET_PLUGIN="$CODEX_HOME/plugins/cache/turbo-mode/ticket/1.4.0"
case "$HANDOFF_PLUGIN:$TICKET_PLUGIN" in
  /Users/jp/.codex/plugins/cache/*)
    if [ "${ALLOW_REAL_CODEX_HOME_SMOKE:-0}" != "1" ]; then
      echo "smoke aborted: real Codex home plugin root requires explicit real-home run" >&2
      exit 1
    fi
    ;;
esac
```

These smoke snippets are Bash snippets. Do not run the scalar `$COMMAND` execution form under zsh; zsh does not split scalar command strings the same way. The implementation may prefer argv arrays, but it must keep a separate canonical command string for the installed hook input.

Handoff session-state command smoke:

```bash
mkdir -p "$SMOKE_REPO/docs/handoffs"
cat > "$SMOKE_REPO/docs/handoffs/2026-05-06_00-00_smoke.md" <<'MD'
---
date: 2026-05-06
time: "00:00"
created_at: "2026-05-06T00:00:00Z"
session_id: 00000000-0000-4000-8000-000000000006
project: smoke-repo
title: Smoke
type: summary
files: []
---

Smoke handoff.
MD
PYTHONDONTWRITEBYTECODE=1 python3 "$HANDOFF_PLUGIN/scripts/session_state.py" archive \
  --source "$SMOKE_REPO/docs/handoffs/2026-05-06_00-00_smoke.md" \
  --archive-dir "$SMOKE_REPO/docs/handoffs/archive" \
  --field archived_path
PYTHONDONTWRITEBYTECODE=1 python3 "$HANDOFF_PLUGIN/scripts/session_state.py" write-state \
  --state-dir "$SMOKE_REPO/docs/handoffs/.session-state" \
  --project smoke-repo \
  --archive-path "$SMOKE_REPO/docs/handoffs/archive/2026-05-06_00-00_smoke.md" \
  --field state_path
PYTHONDONTWRITEBYTECODE=1 python3 "$HANDOFF_PLUGIN/scripts/session_state.py" read-state \
  --state-dir "$SMOKE_REPO/docs/handoffs/.session-state" \
  --project smoke-repo \
  --field archive_path
PYTHONDONTWRITEBYTECODE=1 python3 "$HANDOFF_PLUGIN/scripts/session_state.py" clear-state \
  --state-dir "$SMOKE_REPO/docs/handoffs/.session-state" \
  --project smoke-repo
```

Expected Handoff result:

- each command exits `0`;
- `archive` moves the source into the archive directory;
- `write-state` returns a JSON state path;
- `read-state` returns the archived handoff path;
- `clear-state` removes the state file without writing `__pycache__`.

Handoff defer command smoke:

```bash
printf '%s\n' \
  '{"summary":"Smoke deferred task","problem":"Verify installed defer command shape.","source_type":"plan","source_ref":"plan06-smoke","session_id":"plan06-smoke","acceptance_criteria":["Installed defer command emits an envelope."],"priority":"low","effort":"S"}' \
  | (cd "$SMOKE_REPO" && PYTHONDONTWRITEBYTECODE=1 python3 "$HANDOFF_PLUGIN/scripts/defer.py" --tickets-dir docs/tickets)
```

Expected Handoff defer result:

- command exits `0`;
- JSON stdout reports `status = "ok"`;
- at least one deferred-work envelope is created under `$SMOKE_REPO/docs/tickets/.envelopes`;
- raw stdout/stderr stay local-only.

Ticket create/update/read/query command smoke:

```bash
run_ticket_hook() {
  command="$1"
  label="$2"
  payload_path="$3"
  hook_out="$SMOKE_ROOT/hook-${label}.json"
  python3 - "$command" "$SMOKE_REPO" <<'PY' | CODEX_PLUGIN_ROOT="$TICKET_PLUGIN" python3 "$TICKET_PLUGIN/hooks/ticket_engine_guard.py" > "$hook_out"
import json
import sys

command = sys.argv[1]
cwd = sys.argv[2]
print(json.dumps({
    "tool_name": "Bash",
    "tool_input": {"command": command},
    "cwd": cwd,
    "session_id": "plan06-smoke",
}))
PY
  python3 - "$hook_out" "$payload_path" <<'PY'
import json
import sys

path = sys.argv[1]
payload_path = sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
if decision != "allow":
    raise SystemExit(f"ticket hook did not allow command: {data!r}")
payload = json.load(open(payload_path, encoding="utf-8"))
expected = {
    "hook_injected": True,
    "hook_request_origin": "user",
    "session_id": "plan06-smoke",
}
for key, expected_value in expected.items():
    if payload.get(key) != expected_value:
        raise SystemExit(
            f"ticket hook did not inject {key}: expected {expected_value!r}, got {payload.get(key)!r}"
        )
PY
}

cat > "$SMOKE_PAYLOADS/ticket-create.json" <<'JSON'
{"action":"create","fields":{"title":"Smoke ticket","problem":"Verify installed Ticket command shape.","priority":"low","status":"open","tags":["smoke"],"acceptance_criteria":["Smoke read/query can find this ticket."],"key_files":[]}}
JSON
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py prepare $SMOKE_PAYLOADS/ticket-create.json"
run_ticket_hook "$COMMAND" create-prepare "$SMOKE_PAYLOADS/ticket-create.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-create.prepare.stdout.json" 2> "$SMOKE_ROOT/ticket-create.prepare.stderr.txt")
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py execute $SMOKE_PAYLOADS/ticket-create.json"
run_ticket_hook "$COMMAND" create-execute "$SMOKE_PAYLOADS/ticket-create.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-create.execute.stdout.json" 2> "$SMOKE_ROOT/ticket-create.execute.stderr.txt")
TICKET_ID="$(python3 - "$SMOKE_ROOT/ticket-create.execute.stdout.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
ticket_id = data.get("ticket_id")
if not isinstance(ticket_id, str) or not ticket_id:
    raise SystemExit(f"missing ticket_id in create execute output: {data!r}")
print(ticket_id)
PY
)"
(cd "$SMOKE_REPO" && python3 -B "$TICKET_PLUGIN/scripts/ticket_read.py" list docs/tickets --status open > "$SMOKE_ROOT/ticket-list.stdout.json" 2> "$SMOKE_ROOT/ticket-list.stderr.txt")
(cd "$SMOKE_REPO" && python3 -B "$TICKET_PLUGIN/scripts/ticket_read.py" query docs/tickets "$TICKET_ID" > "$SMOKE_ROOT/ticket-query.stdout.json" 2> "$SMOKE_ROOT/ticket-query.stderr.txt")
cat > "$SMOKE_PAYLOADS/ticket-update.json" <<JSON
{"action":"update","ticket_id":"$TICKET_ID","fields":{"tags":["smoke","updated"]}}
JSON
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py prepare $SMOKE_PAYLOADS/ticket-update.json"
run_ticket_hook "$COMMAND" update-prepare "$SMOKE_PAYLOADS/ticket-update.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-update.prepare.stdout.json" 2> "$SMOKE_ROOT/ticket-update.prepare.stderr.txt")
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py execute $SMOKE_PAYLOADS/ticket-update.json"
run_ticket_hook "$COMMAND" update-execute "$SMOKE_PAYLOADS/ticket-update.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-update.execute.stdout.json" 2> "$SMOKE_ROOT/ticket-update.execute.stderr.txt")
(cd "$SMOKE_REPO" && python3 -B "$TICKET_PLUGIN/scripts/ticket_read.py" query docs/tickets "$TICKET_ID" > "$SMOKE_ROOT/ticket-query-updated.stdout.json" 2> "$SMOKE_ROOT/ticket-query-updated.stderr.txt")
```

Ticket close/reopen command smoke:

```bash
cat > "$SMOKE_PAYLOADS/ticket-close.json" <<JSON
{"action":"close","ticket_id":"$TICKET_ID","fields":{"resolution":"done"}}
JSON
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py prepare $SMOKE_PAYLOADS/ticket-close.json"
run_ticket_hook "$COMMAND" close-prepare "$SMOKE_PAYLOADS/ticket-close.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-close.prepare.stdout.json" 2> "$SMOKE_ROOT/ticket-close.prepare.stderr.txt")
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py execute $SMOKE_PAYLOADS/ticket-close.json"
run_ticket_hook "$COMMAND" close-execute "$SMOKE_PAYLOADS/ticket-close.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-close.execute.stdout.json" 2> "$SMOKE_ROOT/ticket-close.execute.stderr.txt")
cat > "$SMOKE_PAYLOADS/ticket-reopen.json" <<JSON
{"action":"reopen","ticket_id":"$TICKET_ID","fields":{"reopen_reason":"Plan 06 smoke verifies reopen lifecycle."}}
JSON
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py prepare $SMOKE_PAYLOADS/ticket-reopen.json"
run_ticket_hook "$COMMAND" reopen-prepare "$SMOKE_PAYLOADS/ticket-reopen.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-reopen.prepare.stdout.json" 2> "$SMOKE_ROOT/ticket-reopen.prepare.stderr.txt")
COMMAND="python3 -B $TICKET_PLUGIN/scripts/ticket_workflow.py execute $SMOKE_PAYLOADS/ticket-reopen.json"
run_ticket_hook "$COMMAND" reopen-execute "$SMOKE_PAYLOADS/ticket-reopen.json"
(cd "$SMOKE_REPO" && $COMMAND > "$SMOKE_ROOT/ticket-reopen.execute.stdout.json" 2> "$SMOKE_ROOT/ticket-reopen.execute.stderr.txt")
```

Ticket audit repair dry-run smoke:

```bash
(cd "$SMOKE_REPO" && PYTHONDONTWRITEBYTECODE=1 python3 -B "$TICKET_PLUGIN/scripts/ticket_audit.py" repair docs/tickets --dry-run)
```

Expected Ticket result:

- each command exits `0`;
- every `ticket_workflow.py prepare` and `ticket_workflow.py execute` command is first allowed by the installed `ticket_engine_guard.py` Bash hook;
- smoke payloads are seeded without `session_id`, `request_origin`, `hook_injected`, or `hook_request_origin`;
- after every hook call, the smoke harness asserts the payload now contains `hook_injected = true`, `hook_request_origin = "user"`, and `session_id = "plan06-smoke"`;
- trust fields are injected by the installed hook, not hand-forged by the smoke harness or inferred from prepare output;
- create returns a concrete ticket id and writes one ticket file under `$SMOKE_REPO/docs/tickets`;
- update changes that ticket without changing its identity, using only update-supported fields such as `tags`;
- read/list/query can find that ticket id and the updated metadata;
- close and reopen transition that ticket without corrupting the audit log;
- audit repair dry-run reports no unrecoverable corruption;
- no raw payload JSON, ticket body, stdout, or stderr is copied into commit-safe evidence.

## Task 0: Re-Anchor And Clear Pre-Mutation Blockers

**Files:**

- Modify only if still untracked: `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md`

- [ ] **Step 1: Verify live branch and handoff authority state**

Run:

```bash
git status --short --branch
git status --short --branch --ignored docs/handoffs
git rev-parse HEAD
```

Expected:

- branch is `main` or a new implementation branch from `main`;
- `HEAD` is at or after `bd428c758da565514b6de91493147ce28b22211a`;
- no tracked dirty source, test, config, marketplace, evidence, or installed-cache paths;
- no untracked relevant tool import-root, plugin source, marketplace metadata, or refresh evidence paths except this plan before the plan-authority commit;
- active instructions for this workspace currently classify repository handoff files under `docs/handoffs/` and `docs/handoffs/archive/` as durable project artifacts when they are tracked or intentionally included in the repo's durable state;
- ignored active resume files and `.session-state/` files are session mechanics, not Plan 06 authority artifacts, unless a reviewed repo policy explicitly promotes a named file;
- Plan 06 must not delete, untrack, force-add, stage, preserve-by-assumption, or reclassify `docs/handoffs/**` as part of the plan-authority commit;
- if `.gitignore`, tracked handoff state, or active ignored handoff files conflict with the active instruction contract, treat that as a handoff-policy authority conflict requiring a separate reviewed decision before implementation;
- Task 0 must record the classification in the implementation notes: `handoff-authority-clean`, `handoff-authority-conflict-blocked`, or `handoff-policy-waiver-recorded`.

Task 0 must run `git status --short --ignored docs/handoffs`, `git check-ignore -v docs/handoffs/.session-state docs/handoffs/archive docs/handoffs/example.md`, `git ls-files docs/handoffs`, and `sed -n '11,14p' .gitignore`. These commands are evidence collection only. They do not decide whether handoff artifacts are durable or disposable. At this review boundary, the live instruction surface says repository handoff files under `docs/handoffs/` and `docs/handoffs/archive/` are durable project artifacts when tracked or intentionally included in durable repo state; therefore, any plan text or `.gitignore` comment that says `docs/handoffs/` is categorically not durable project documentation is not sufficient authority for Plan 06. If that policy reversal is still desired, write and review an explicit waiver or repo policy change before the Plan 06 authority commit. Until then, do not include `.gitignore` handoff-policy edits in the Plan 06 commit and do not treat tracked handoff deletion as cleanup debt.

Source-authority note for Plan 06: the active instruction block supplied for this workspace outranks `.gitignore` as an instruction source. `.gitignore` can describe git visibility for ignored active resume state, but it cannot by itself waive a preservation instruction for tracked or intentionally durable `docs/handoffs/` artifacts. A future task may change this policy only through an explicit reviewed artifact that names the instruction conflict and the intended override. Without that artifact, Plan 06 must preserve repository handoff files during cleanup, branch setup, and authority commits.

Task 0 must record handoff files in three categories with allowed actions:

- `tracked-durable-handoff-artifact`: any `git ls-files docs/handoffs` result, or any handoff file explicitly named by a reviewed repo policy as durable. Preserve it, do not delete or untrack it, and do not let Plan 06 reclassify it.
- `ignored-active-session-artifact`: untracked ignored handoff summaries, checkpoints, or `.session-state/` files created by the handoff plugin for the current session chain. Load/archive the current resume artifact if needed, leave ignored session mechanics out of commits, and record their presence in Task 0 notes.
- `policy-conflict-artifact`: any `.gitignore` comment, active instruction, tracked file state, or ignored active file whose classification is contradictory. Stop before the plan-authority commit unless a separate reviewed waiver or repo policy update resolves the conflict.

The current Plan 06 resume summary should normally be archived before implementation. At the review boundary that repaired this plan, active ignored resume files included `docs/handoffs/2026-05-06_15-07_summary-plan-06-execution-surface-repair.md`, `docs/handoffs/2026-05-06_15-54_summary-plan-06-review-ready-guardrails.md`, `docs/handoffs/2026-05-06_16-27_summary-plan-06-major-revision.md`, and `docs/handoffs/2026-05-06_16-40_summary-plan-06-proof-schema-closed.md`; the earlier `docs/handoffs/2026-05-06_14-32_summary-plan-06-guarded-lane.md` summary may also appear in stale checkouts. If any ignored active `docs/handoffs/` file appears before Task 1A, do not commit it. Classify it under the three-category model above and continue only if no non-handoff tracked project files are dirty and no `policy-conflict-artifact` is unresolved.

- [ ] **Step 2: Commit the reviewed plan before implementation**

If this plan is untracked/modified after review, create a branch from current `main` and commit only the plan before writing implementation code. If `.gitignore` carries uncommitted handoff-policy authority edits, stop and resolve that policy conflict separately before this commit:

```bash
git switch -c chore/turbo-refresh-plan06-guarded-lane
git add docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md
git commit -m "docs: plan guarded refresh mutation lane"
```

Expected:

- current branch is `chore/turbo-refresh-plan06-guarded-lane` or another reviewed branch name from current `main`;
- the staged set contains exactly this plan file;
- the authority commit contains the reviewed control document and no handoff-policy `.gitignore` edit;
- implementation commits can cite this committed control document.

- [ ] **Step 3: Reproduce current non-mutating blocker**

Run with a fresh run id:

```bash
RUN_ID="plan06-preflight-reanchor-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected before cleanup:

- `terminal_plan_status = "blocked-preflight"`;
- `runtime_config.state = "aligned"`;
- `app_server_inventory_status = "collected"`;
- `residue_issues` includes `cache` / `handoff` / `scripts/__pycache__/project_paths.cpython-314.pyc`.

- [ ] **Step 4: Stop for operator approval before trashing generated residue**

If Step 3 still reports generated residue, stop implementation and ask the operator to approve trashing the exact generated residue path and its empty parent directory if needed:

```bash
command -v trash >/dev/null || { echo "trash command is required; stop instead of using rm" >&2; exit 1; }
find /Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/scripts/__pycache__ -maxdepth 1 -mindepth 1 -print
python3 - <<'PY'
from pathlib import Path

pycache = Path("/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/scripts/__pycache__")
expected = pycache / "project_paths.cpython-314.pyc"
entries = sorted(pycache.iterdir()) if pycache.exists() else []
if entries != [expected]:
    raise SystemExit(f"pycache cleanup requires renewed approval. Got: {[str(path) for path in entries]!r}")
PY
trash /Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/scripts/__pycache__/project_paths.cpython-314.pyc
trash /Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/scripts/__pycache__
```

Expected:

- both paths are generated cache residue only;
- the pre-trash listing shows exactly the approved `.pyc` file before the directory is trashed;
- no source file, tracked file, config file, marketplace file, or evidence file is trashed.

- [ ] **Step 5: Re-run current dry-run inventory after cleanup**

Run with a new run id:

```bash
RUN_ID="plan06-current-guarded-reanchor-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected after cleanup:

- command exits `0`;
- `terminal_plan_status = "guarded-refresh-required"`;
- `runtime_config.state = "aligned"`;
- `runtime_config.plugin_hooks_state = "true"`;
- `app_server_inventory_status = "collected"`;
- `residue_issues = []`;
- current drift is the Plan 05 six-path set unless a later source/cache change is intentionally added and classified before mutation.

If the result is anything other than `guarded-refresh-required`, stop and update this plan before implementing mutation.

## Task 1A: Prove App-Server Home And Install Authority

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py`

- [ ] **Step 1: Write app-server authority contract tests**

Add default-suite tests that prove the app-server authority contract without requiring a live local Codex app-server:

- a sentinel temporary `codex_home` is passed into the app-server launch path;
- binding-surface discovery records every candidate mechanism checked, including CLI flags, environment variables, config-path options, and app-server protocol fields;
- `app_server_roundtrip()` records the requested home, resolved config path, plugin cache root, local-only root, child cwd, environment delta, executable identity, version, `initialize.serverInfo`, and accepted schema;
- `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` responses resolve config, cache, plugin, hook, and local-only authority under the requested temporary home or the requested repo marketplace;
- `AppServerPreInstallTargetAuthority` is required before fixture-backed install request builders can be invoked;
- fixture-backed install request builders refuse to run when pre-install target authority is missing, stale, or points outside the requested isolated home;
- fixture-backed sparse `plugin/install` responses are accepted only as write-completion signals tied to exact request ids and accepted generic success/auth schema;
- post-install app-server `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` fixtures from the same install child and a fresh child prove requested plugin, requested marketplace, installed paths under the temporary home cache, accepted runtime schema, and no-real-home path authority;
- local installed-cache fixtures for Handoff and Ticket prove post-install cache manifest delta independently from the sparse `plugin/install` responses;
- a generic install success response without post-install app-server read/list/hooks corroboration fails closed as insufficient app-server install authority;
- `app_server_inventory.py` owns `AppServerLaunchAuthority`, `AppServerInstallAuthority`, their serializers, and digest helpers; mutation code imports and consumes those records instead of defining parallel proof shapes;
- the authority probe fails closed before snapshots or hook disable if any response resolves to `/Users/jp/.codex` during an isolated run;
- fixture-backed missing-home-binding responses fail closed before snapshots or hook disable;
- no process gate, lock, run-state marker, snapshot, config write, real-home cache write, broader install orchestration, smoke, recovery, or evidence validator implementation is started when this contract cannot be made to pass.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py -q
```

Expected: default tests pass with mocked/protocol fixtures once the authority contract is encoded. The default refresh test suite must not require a working local `codex app-server`, a machine-specific protocol build, or live plugin install semantics.

- [ ] **Step 2: Implement the app-server authority contract**

Update `app_server_inventory.py` so `app_server_roundtrip()` can launch `codex app-server --listen stdio://` with the discovered explicit home-binding mechanism. If the only available behavior is the current implicit default-home launch, stop Plan 06 and do not continue to process gates or mutation scaffolding.

The read-only discovery portion is complete only when:

- the test temporary home receives all authority-resolved config/cache/plugin/local-only paths;
- the real `/Users/jp/.codex` home is not read as isolated authority;
- the discovered mechanism is named and reproducible from the recorded command/protocol evidence;
- a local-only read-only discovery artifact records all candidate mechanisms checked and the accepted mechanism, or a structured blocker report explains why none is acceptable.

The isolated install spike is allowed only after read-only discovery and pre-install target authority pass. It is complete only when:

- the pre-install target authority artifact exists and proves the install cache root before any unmocked `plugin/install` write;
- the isolated `plugin/install` spike mutates only the temporary home cache and returns accepted generic success/auth responses for Handoff and Ticket;
- the same install child and a fresh app-server child both corroborate post-install state with `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` rooted under the requested isolated home or requested repo marketplace, as appropriate;
- an unmocked local-only spike artifact exists under the isolated home's local-only refresh root, records the exact app-server executable path/SHA256, requested home, repo marketplace, pre-install target authority digest, install request/response digests, same-child and fresh-child post-install corroboration transcript digests, installed cache paths, no-real-home path checks, post-install cache manifest delta, and artifact SHA256, and is referenced in the Task 1A commit message or implementation notes;
- serialized authority proof digests are produced by `app_server_inventory.py` and consumed by mutation code without reserializing a different shape;
- the authority proof can be serialized for later rehearsal proof digests;
- failures return a hard blocker status, not a warning.

Task 1A implementation must include a separate operator-run integration command for the unmocked local app-server authority spike. It may be gated by an explicit environment variable such as `CODEX_REFRESH_RUN_APP_SERVER_AUTHORITY_SPIKE=1` or by a dedicated script/CLI mode, but it must not run as part of the default `uv run pytest plugins/turbo-mode/tools/refresh/tests -q` suite.

Run the unmocked spike from an external shell only after the default contract tests pass:

```bash
CODEX_REFRESH_RUN_APP_SERVER_AUTHORITY_SPIKE=1 \
PYTHONDONTWRITEBYTECODE=1 \
uv run pytest plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py -q -k app_server_authority_spike
```

Expected: the command first writes a local-only read-only discovery artifact and pre-install target authority artifact, then writes a local-only isolated install proof artifact and SHA256. If any gate blocks, it exits nonzero after writing a structured local-only blocker report. The pytest command must not edit this plan. If the spike blocks, patch this plan in a separate explicit docs step that cites the blocker report and chooses one reviewed path: update the Codex app-server/protocol, replace `plugin/install` authority with another approved mechanism, or stop Plan 06.

### Blocked Decision: 2026-05-07 Task 1A authority spike

Observed blocker from the operator-run Task 1A authority spike:

- run id: `plan06-task1a-authority-spike-20260507-041723`
- durable blocker report: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-041723/authority-blocker.json`
- blocker report SHA256: `0c50e30e46fe0f5ab7eb190c63fae7950f1e2160c9b5d97cf6f067dd4b42ece6`
- durable read-only transcript: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-041723/readonly-discovery.transcript.json`
- durable read-only transcript SHA256: `83c261d3038571cc47c02693dbf43cc2c02690f51f4cba6afe8b79263dd7c29d`
- durable launch-authority artifact: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-041723/launch-authority.json`
- launch-authority SHA256: `b320051f8daf54679acea616a69363caf3aa96a02ae3d4ccfc59b84bf9af1e1d`
- durable pre-install target authority artifact: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-041723/preinstall-target-authority.json`
- pre-install target authority SHA256: `f02d8d897dfd11af0a6e79b401515a001c2a255c5b91d2e92482c068d0aea1e9`
- durable install transcript: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-041723/install.transcript.json`
- durable install transcript SHA256: `438bc777ef5d8f3f9c7fe351b12af9e15b12f13a898b42dae862496a6582d9c7`
- isolated home used for the spike: `/private/tmp/plan06-task1a-authority-spike-20260507-041723-bj35slzn/.codex`

Observed read-only and pre-install authority result:

- `initialize.result.codexHome` bound to the isolated home.
- `skills/list` returned Handoff and Ticket skill paths under the isolated home cache.
- `hooks/list.sourcePath` and `hooks/list.command` both resolved under the isolated Ticket cache root for the requested isolated home.
- `launch-authority.json` and `preinstall-target-authority.json` were written before any unmocked `plugin/install` request.
- this run supersedes the earlier read-only blocker recorded in the docs-only blocked update: install-root-bound Ticket hook metadata cleared the no-real-home hook-command blocker in isolated read-only discovery, but it did not unblock install authority.

Observed isolated install-authority blocker:

- the isolated `plugin/install` transcript still returned only generic success/auth payloads and did not expose install identity fields for Handoff or Ticket;
- the validator now computes post-install cache manifest delta from local installed-cache evidence, so the remaining blocker is not missing `cacheDelta`;
- the blocker report records the current missing install identity fields as `pluginName`, `marketplacePath`, `remoteMarketplaceName`, `installedPath`, and `status`.

Follow-up implementation spike after the alternate authority validator patch:

- run id: `plan06-task1a-authority-spike-20260507-043440`
- durable blocker report: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-043440/authority-blocker.json`
- blocker report SHA256: `47631be38ce4482e6ade6bfa14142b42010e853ab05605c14e5cfbdfd703411e`
- durable read-only transcript SHA256: `8d3eeb4ab117c705616d0d15e66db5e411dd6f8d41769d48122443c41629e7e0`
- durable launch-authority SHA256: `fc905c1accc3dc005c9b850e5a596b38e9df920e7c0a178095e74b8b66bc65a7`
- durable pre-install target authority SHA256: `b15334e53f114e967f31999c57c6612e53e90a185dd40ffc131c1476a83376a3`
- durable install transcript SHA256: `f35f7671f224667ccbb19efde4664cbbd107fe9ef7da5b776961beb3cf672efc`
- durable same-child post-install corroboration transcript SHA256: `9cb92f025f9932b713e07b1558c9f13ae304221bf86c472552cd527da8035545`
- durable fresh-child post-install corroboration transcript SHA256: `4cd76b220bcb2c67a6bbe49a984f9b8233393b4261fc636a378c1eadaa16f096`
- isolated home used for the spike: `/private/tmp/plan06-task1a-authority-spike-20260507-043440-a4zhd3k2/.codex`

Observed follow-up blocker:

- sparse `plugin/install` response validation moved past the previous missing response-identity blocker;
- same-child post-install app-server corroboration failed because `hooks/list.command` returned `python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py`;
- the repo source manifest `plugins/turbo-mode/ticket/1.4.0/hooks/hooks.json` still contains that absolute real-home command, and the current Ticket release provenance test intentionally pins it;
- no documented app-server hook-command placeholder, installed-root expansion, or portable plugin-root launcher was found in this repo;
- therefore the alternate authority mechanism is implemented in the validator but still blocked at runtime by post-install Ticket hook command authority.

Follow-up implementation spike after post-install installed-cache Ticket hook rewrite:

- run id: `plan06-task1a-authority-spike-20260507-044924`
- durable artifact root: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan06-task1a-authority-spike-20260507-044924`
- durable read-only transcript SHA256: `cbd5093c0b0fec1b22c14b6d0565cddefbd74df75a141ab3b468b806fd3a549b`
- durable launch-authority SHA256: `6a84eb2262fed4bb2c916d94bb37cff34b4817e1ae440871f7edac21e5e33d28`
- durable pre-install target authority SHA256: `add463e2604b8f879ba34af8d183e7b62add23f6af83dc241c1142cc9bc5f349`
- durable install transcript SHA256: `7b0842440ff5edda53338d2d6c04e26f0523e1d3f0a6ce4fed40d9e2cbe64277`
- durable same-child post-install corroboration transcript SHA256: `edbd11cb6a93baf1adee6fc9752847b38da246d6a0b7bb6b1155d1d77d2ff615`
- durable fresh-child post-install corroboration transcript SHA256: `cbd5093c0b0fec1b22c14b6d0565cddefbd74df75a141ab3b468b806fd3a549b`
- durable install-authority artifact SHA256: `f1f7cef1dec15e5caff7de5d4ce5a7ac4bd2f5c84fa23f9ba661de20dc520f28`
- isolated home used for the spike: `/private/tmp/plan06-task1a-authority-spike-20260507-044924-ejckxgbw/.codex`

Observed validated authority result:

- sparse Handoff and Ticket `plugin/install` responses were accepted only as `sparse-success-auth-v1` write-completion signals with request-id correlation;
- after the Ticket install response, the spike rewrote the installed Ticket `hooks/hooks.json` command to the actual isolated installed Ticket root before same-child post-install inventory;
- same-child `hooks/list.command` returned `python3 /private/tmp/plan06-task1a-authority-spike-20260507-044924-ejckxgbw/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py`;
- same-child `hooks/list.sourcePath` returned `/private/tmp/plan06-task1a-authority-spike-20260507-044924-ejckxgbw/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json`;
- fresh-child `hooks/list.command` and `sourcePath` returned the same isolated installed Ticket root;
- `install-authority.json` records installed destination paths for Handoff and Ticket under the isolated home, same-child and fresh-child corroboration digests, accepted sparse install schemas, pre/post cache manifest SHA256 maps, and cache manifest delta SHA256s.

Plan 06 consequence:

- Task 1A now reaches `authority-validated` in the local isolated spike.
- The selected authority mechanism is sparse install success plus explicit post-install installed-cache Ticket hook command rewrite, same-child app-server corroboration, fresh-child app-server corroboration, and local cache manifest proof.
- Post-install cache delta proof alone is not sufficient; do not infer install authority from a generic success payload plus post-write observation.
- Task 1B may start only after Task 1A is committed with this authority evidence boundary. Do not skip the commit boundary into process gate, lock, marker, snapshot, smoke, recovery, retained-run, or mutation-orchestration work.

Reviewed paths resolved by this authority decision:

1. Codex app-server/plugin-install response identity remains OpenAI-owned and sparse in this repo; do not fabricate richer response identity locally.
2. The approved local mechanism is post-install installed-cache hook-command rewrite plus app-server and manifest corroboration, not source manifest portability.
3. The source Ticket hook manifest and release provenance test may continue pinning the real-home installed runtime command while isolated install proof rewrites only the installed cache copy for the requested home.

Selected unblock path:

- use the alternate authority mechanism as the current project-facing repair because the Codex app-server runtime is OpenAI-owned and cannot be changed in this repository;
- preserve the current app-server `plugin/install` response as a write-completion signal only, with accepted generic success/auth schema and exact request-id correlation;
- prove install authority from a separate post-install authority chain: same-child app-server `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`; fresh-child app-server `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`; local installed-cache manifest digests; and no-real-home path checks;
- require Handoff skills and Ticket skills/hooks to resolve under the requested isolated cache root after install, and require `plugin/read` / `plugin/list` to preserve requested marketplace identity and runtime schema;
- post-install cache manifest delta may be computed from local installed-cache evidence and does not need to be echoed by `plugin/install`;
- do not weaken the gate by inferring install identity from a generic success payload, cache side effects, or post-write observation alone. Post-write observation is acceptable only when it is bound to the same pre-install authority, same requested home, same marketplace request identity, app-server post-install corroboration from both same-child and fresh-child sessions, and local cache manifest proof.

Task 1A unblock acceptance:

- the install-root-bound Ticket hook metadata fix remains in place so `hooks/list.command` and `hooks/list.sourcePath` both resolve under the same installed Ticket plugin root for the requested home;
- read-only Task 1A discovery proves `initialize.result.codexHome`, Handoff and Ticket skill paths, Ticket hook `sourcePath`, Ticket hook `command`, and local-only roots bind to the requested isolated home or requested repo marketplace as appropriate;
- pre-install target authority is recorded before any unmocked `plugin/install` request;
- the isolated `plugin/install` responses have accepted generic success/auth schema and are correlated to the exact Handoff and Ticket install requests;
- same-child and fresh-child post-install app-server corroboration proves Handoff and Ticket plugin state through `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` without resolving config, cache, plugin, hook, local-only, or installed paths under `/Users/jp/.codex`;
- local installed-cache manifests prove the expected Handoff and Ticket installed roots under the requested isolated home;
- post-install cache manifest delta is computed from local installed-cache evidence and recorded in `AppServerInstallAuthority`;
- the isolated `plugin/install` spike produces validated local-only authority artifacts and SHA256s without any config, cache, plugin, hook, local-only, or installed path resolving under `/Users/jp/.codex`;
- after the unblock implementation lands, rerun Plan 06 from Task 0 with a fresh run id before marking Task 1A `authority-validated`.

The isolated authority spike now passes for Task 1A. This is not a live real-home guarded refresh and does not certify Task 1B or any later mutation scaffolding.

Task 1B and Task 2 must not start until the Task 1A code and plan evidence are committed. Mock-only authority tests remain insufficient for the process gate, lock, marker, snapshot, recovery, smoke, or evidence scaffolding boundary.

- [ ] **Step 3: Commit Task 1A**

If Task 1A outcome is `authority-validated`, run:

```bash
git add plugins/turbo-mode/tools/refresh/app_server_inventory.py plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py
git commit -m "feat: prove guarded refresh app-server authority"
```

If Task 1A outcome is `blocked-plan-update`, do not create the `feat: prove guarded refresh app-server authority` commit. Instead, stage only the blocked-decision plan update and commit a docs-only blocked update, for example:

```bash
git add docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md
git commit -m "docs: record plan06 task1a authority block"
```

The validated-path commit message or implementation notes must include the validated spike artifact path/SHA256. The blocked-path commit must not overclaim proof of authority, and it must not stage process gate, lock, marker, smoke, recovery, evidence, or mutation orchestration files.

## Task 1B: Implement Process Gate Helpers

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/process_gate.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_process_gate.py`

- [ ] **Step 1: Write process row parsing tests**

Add tests that cover:

- `Codex` app bundle command classified as `codex-desktop`;
- `codex exec` classified as blocking `codex-cli`;
- bare interactive `codex`, `codex resume`, `codex login`, `codex mcp`, `codex app-server`, and any other non-child `codex` command shape classified as blocking `codex-cli`, blocking `codex-app-server`, or blocking `uncertain-high-risk`;
- unrelated `codex app-server` classified as blocking `codex-app-server`;
- installed Ticket hook command classified as `ticket-hook-runtime`;
- harmless path containing `/tmp/codex-not-a-process/file.txt` classified as non-blocking;
- refresh tool PID classified as self;
- recorded direct child `codex app-server --listen stdio://` classified as allowed child;
- shell wrapper command classified as non-blocking only when the parsed command line exactly wraps the current refresh command;
- shell wrapper command classified as `uncertain-high-risk` when quoting, truncation, or argv parsing prevents exact self-exemption;
- truncated row containing `codex`, `Codex`, `codex app-server`, `ticket_engine_`, `ticket_workflow.py`, or the installed Ticket hook path classified as `uncertain-high-risk`;
- unparsable row containing `codex app-server` classified as `uncertain-high-risk`;
- no non-child `codex` process row is classified as non-blocking unless it is the exact current refresh process or a recorded direct child app-server owned by the current refresh PID.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_process_gate.py -q
```

Expected: tests fail because `process_gate.py` does not exist or because process classification is still too narrow.

- [ ] **Step 2: Implement `process_gate.py`**

Required public API:

- `ProcessRow`: frozen dataclass with `pid: int`, `ppid: int`, `command: str`, `argv: Sequence[str]`, and `executable_basename: str | None`.
- `ProcessGateFinding`: frozen dataclass with `pid: int`, `classification: str`, `blocking: bool`, and `command_marker: str`.
- `parse_ps_output(text: str) -> Sequence[ProcessRow]`.
- `classify_processes(rows: Sequence[ProcessRow], *, refresh_pid: int, refresh_command: Sequence[str], recorded_child_app_server_pids: frozenset[int]) -> Sequence[ProcessGateFinding]`.
- `capture_process_gate(*, label: str, local_only_run_root: Path, refresh_pid: int, refresh_command: Sequence[str], recorded_child_app_server_pids: frozenset[int]) -> dict[str, object]`.

Classification values:

- `self-refresh-tool`
- `allowed-child-app-server`
- `codex-desktop`
- `codex-cli`
- `codex-app-server`
- `ticket-hook-runtime`
- `ticket-hook-path-consumer`
- `uncertain-high-risk`
- `non-blocking`

`capture_process_gate()` must run:

```bash
ps -ww -axo pid,ppid,command
```

and write:

- raw process listing: `process-<label>.txt` with mode `0600`;
- summary: `process-<label>.summary.json` with mode `0600`.

The summary must include `blocked_process_count`, `blocking_classifications`, `raw_process_sha256`, and `exclusivity_status = "exclusive_window_observed_by_process_samples"` only when no blockers are found.

Self-exemption rules must be exact:

- exempt the refresh tool PID itself;
- exempt recorded direct child app-server PIDs only when `ppid` is the refresh PID, executable basename is `codex`, argv includes `app-server`, and argv includes `--listen` with `stdio://`;
- exempt shell wrappers only when parsed argv proves they are exactly wrapping the current refresh command;
- block every other non-child `codex` row by default, including interactive/resume/app-server/utility variants, unless a future plan proves that specific shape harmless;
- treat truncated or ambiguous rows as blockers when they contain high-risk markers.

- [ ] **Step 3: Run Task 1B tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_process_gate.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 1B**

Run:

```bash
git add plugins/turbo-mode/tools/refresh/process_gate.py plugins/turbo-mode/tools/refresh/tests/test_process_gate.py
git commit -m "feat: add guarded refresh process gates"
```

## Task 2: Implement Lock Owner And Run-State Marker

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/lock_state.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_lock_state.py`

- [ ] **Step 1: Write lock and marker tests**

Add tests for:

- local-only refresh root and `run-state` directory created with `0700`;
- lock owner file written with `0600`;
- marker file written with `0600`;
- nonblocking lock acquisition fails while another descriptor holds the lock;
- stale owner metadata is copied into immutable local-only evidence before recovery owner metadata is written;
- marker phase-only update is rejected for phases that produce recovery-critical fields;
- marker full-state replacement persists `pre_snapshot_app_server_launch_authority_sha256`, snapshot paths, snapshot manifest digest, original config SHA256, hook-disabled config SHA256, `pre_install_app_server_target_authority_sha256`, post-install cache manifest, and recovery eligibility;
- hook disable is rejected when marker recovery eligibility or snapshot metadata is absent;
- hook disable, cache install, smoke, and recovery scaffolding are rejected when `pre_snapshot_app_server_launch_authority_sha256` is absent from the marker;
- lock owner start identity is collected with `ps -ww -o pid=,ppid=,lstart=,command= -p "$OWNER_PID"` and stored with raw row SHA256;
- recovery rejects PID reuse when the same owner PID has a different `lstart` value;
- recovery rejects marker `run_id` mismatch.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_lock_state.py -q
```

Expected: tests fail because `lock_state.py` does not exist.

- [ ] **Step 2: Implement `lock_state.py`**

Required public API:

- `LockOwner`: frozen dataclass with schema version, run id, mode, source implementation commit, execution head, tool SHA256, PID, parent PID, observed process start time or boot-relative identity, raw owner process row SHA256, acquisition timestamp, and command-line sequence.
- `RunState`: frozen dataclass with schema version, run id, mode, source implementation commit, source implementation tree, execution head, execution tree, tool SHA256, phase, original run owner SHA256, recovery owner SHA256, `pre_snapshot_app_server_launch_authority_sha256`, `pre_install_app_server_target_authority_sha256`, plugin-hooks start state, original config SHA256, expected intermediate config SHA256, hook-disabled config SHA256, pre-refresh cache manifest SHA256 map, post-install cache manifest SHA256 map, snapshot path map, snapshot manifest digest, process summary SHA256 map, app-server child PID map, smoke summary SHA256, evidence summary SHA256, recovery eligibility, and final status.
- `acquire_refresh_lock(*, local_only_root: Path, run_id: str, mode: str, source_implementation_commit: str, execution_head: str, tool_sha256: str) -> Iterator[LockOwner]`.
- `write_initial_run_state(local_only_root: Path, state: RunState) -> Path`.
- `replace_run_state(local_only_root: Path, state: RunState) -> Path`.
- `update_run_state_phase(local_only_root: Path, run_id: str, phase: str) -> None` only for phase changes that add no recovery-critical fields.
- `read_run_state(local_only_root: Path, run_id: str) -> RunState`.
- `clear_run_state(local_only_root: Path, run_id: str) -> None`.
- `preserve_original_owner_for_recovery(local_only_root: Path, run_id: str, owner_path: Path) -> dict[str, str]`.

Use advisory exclusive `fcntl.flock` on the lock file under the explicit `local_only_root` passed by the caller:

```text
<local_only_root>/refresh.lock
```

`local_only_root` must be derived from `<codex_home>/local-only/turbo-mode-refresh` by orchestration code. Tests must cover an isolated temporary Codex home and assert no lock, owner, marker, recovery, or evidence path resolves under `/Users/jp/.codex` for isolated runs. Keep the lock descriptor open for the full mutation run.

- [ ] **Step 3: Run lock tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_lock_state.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 2**

Run:

```bash
git add plugins/turbo-mode/tools/refresh/lock_state.py plugins/turbo-mode/tools/refresh/tests/test_lock_state.py
git commit -m "feat: add guarded refresh lock state"
```

## Task 3: Implement Mutation Primitives

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/mutation.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_mutation.py`
- Modify: `plugins/turbo-mode/tools/refresh/app_server_inventory.py`

- [ ] **Step 1: Write primitive tests**

Add tests for:

- config byte snapshot and SHA256 capture;
- cache manifest snapshot for Handoff and Ticket;
- guarded hook disable writes `features.plugin_hooks = false` only from starting state `true`;
- `absent-default-enabled` preserves the absent key, performs no config write, and records expected intermediate config SHA256 equal to original config SHA256;
- `absent-unproven` requires pre-refresh inventory after `before-snapshot` process census and before snapshots, and fails before mutation if runtime inventory cannot prove expected Ticket hook enablement;
- `absent-disabled`, `false`, and `malformed` states fail before cache mutation and cannot produce certified evidence;
- guarded hook restore returns config bytes to the original SHA256;
- externally changed config fails before cache mutation for new runs and fails closed during rollback/recovery;
- app-server install request sequence uses `plugin/install` for Handoff then Ticket with `marketplacePath` and `remoteMarketplaceName = null`;
- app-server launch authority probe proves a temporary `codex_home` does not read config/cache/plugin state from `/Users/jp/.codex`;
- app-server launch authority proof fails before snapshot or hook disable when `plugin/read`, `plugin/list`, `skills/list`, or `hooks/list` resolves to the wrong Codex home;
- app-server install request builders fail before any `plugin/install` request when `AppServerPreInstallTargetAuthority` is missing, stale, from a different child/mechanism, or resolves the destination cache root under `/Users/jp/.codex` during an isolated run;
- snapshot creation persists `pre_snapshot_app_server_launch_authority_sha256` in the run-state marker before `snapshot-written`;
- hook disable, live cache install, smoke, and recovery scaffolding fail closed if `pre_snapshot_app_server_launch_authority_sha256` is missing or stale;
- live real-home `plugin/install` is not called until `snapshot-written` is durable and marker state includes snapshot paths, snapshot manifest digest, original config SHA256, pre-refresh cache manifest SHA256 map, and recovery eligibility;
- attempts to call live real-home `plugin/install` with missing or incomplete snapshot marker state fail closed before starting app-server install;
- install-phase code records the install child `AppServerLaunchAuthority` before the first `plugin/install` request;
- install-phase code records `AppServerPreInstallTargetAuthority` before the first `plugin/install` request;
- install-phase code rejects an `AppServerInstallAuthority` whose launch authority digest or pre-install target authority digest is missing, stale, from a different child process, or recorded after any install request;
- app-server install responses assert only accepted generic success/auth schema and request-id correlation for both Handoff and Ticket;
- same-child post-install app-server corroboration asserts expected installed plugin identity through `plugin/read`, `plugin/list`, and `skills/list`; when the same child was launched with `features.plugin_hooks = false`, `hooks/list` must be retained as a hook-disabled zero-hook proof, not as hook certification;
- fresh-child post-install app-server corroboration runs after config restore and asserts expected installed plugin identity through `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`, including source marketplace path and installed skill/hook paths for both Handoff and Ticket;
- app-server failure taxonomy for child start failure, Handoff install failure, Ticket install failure after Handoff success, response schema drift, timeout, stdout close, child termination failure, and rollback inventory failure;
- post-install equality compares repo source manifests to installed cache manifests;
- rollback restores both cache roots from snapshots and restores original config bytes;
- rollback proof starts a fresh app-server inventory collector rather than reusing the failed-run child.
- rollback rejects missing snapshot paths, missing snapshot manifest digest, or marker phases without recovery eligibility.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_mutation.py -q
```

Expected: tests fail because mutation primitives do not exist.

- [ ] **Step 2: Implement mutation primitives**

Required public API in `mutation.py`:

- `MutationContext`: frozen dataclass with run id, mode, repo root, Codex home, local-only run root, source implementation commit, source implementation tree, execution head, execution tree, and tool SHA256.
- import and consume `AppServerLaunchAuthority` and `AppServerInstallAuthority` from `app_server_inventory.py`; do not define duplicate authority dataclasses, serializers, or digest logic in `mutation.py`.
- `SnapshotSet`: frozen dataclass with config snapshot path, config SHA256, cache snapshot root, source manifest SHA256 map, and pre-refresh cache manifest SHA256 map.
- `prove_app_server_home_authority(context: MutationContext) -> AppServerLaunchAuthority`.
- `create_snapshot_set(context: MutationContext) -> SnapshotSet`.
- `prepare_plugin_hooks_for_guarded_refresh(context: MutationContext, *, plugin_hooks_state: str) -> dict[str, str]`.
- `restore_config_snapshot(snapshot: SnapshotSet, *, current_expected_sha256: str | None) -> None`.
- `install_plugins_via_app_server(context: MutationContext) -> Sequence[dict[str, object]]`.
- `verify_source_cache_equality(context: MutationContext) -> dict[str, str]`.
- `rollback_guarded_refresh(context: MutationContext, snapshot: SnapshotSet, *, failed_phase: str) -> dict[str, object]`.
- `abort_after_config_mutation(context: MutationContext, snapshot: SnapshotSet, *, failed_phase: str) -> dict[str, object]`.

`prove_app_server_home_authority()` must pass before snapshots, hook disable, config writes, cache writes, app-server install, or smoke. It must prove only launch/read authority for real `/Users/jp/.codex` runs before snapshots, and must fail closed if the current app-server runtime cannot be explicitly bound to the requested Codex home.

`install_plugins_via_app_server()` must use app-server `plugin/install`; it must not copy source files into the cache. It must assert request shape, request-id correlation, and the current pinned sparse success/auth response schema: Handoff install succeeds before Ticket install, Ticket install succeeds, and both responses are retained as write-completion evidence rather than identity evidence. For real `/Users/jp/.codex` runs, this function must refuse to start app-server install until the snapshot marker is durable and includes snapshot paths, snapshot manifest digest, original config SHA256, pre-refresh cache manifest SHA256 map, and recovery eligibility. It must record the install child `AppServerLaunchAuthority` and `AppServerPreInstallTargetAuthority` before sending the first `plugin/install` request, then collect same-child post-install app-server corroboration with `plugin/read`, `plugin/list`, `skills/list`, and a hook-disabled `hooks/list` response when the child was launched with hooks disabled. It must restore config, start a fresh app-server child, and collect hook-certifying fresh-child post-install corroboration with `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`. The returned `AppServerInstallAuthority` from `app_server_inventory.py` must include the launch authority digest, pre-install target authority digest, install request/response digests, same-child post-install corroboration digest, fresh-child post-install corroboration digest, installed cache paths, post-install cache manifest SHA256 map, and cache delta digests. If launch authority or pre-install target authority is missing, stale, from a different child/mechanism, recorded after any install request, or points at `/Users/jp/.codex` during an isolated run, fail closed before sending or asserting install success.

Do not satisfy `install_plugins_via_app_server()` by enriching sparse `plugin/install` responses inside the refresh tool from the request payload alone. Post-install filesystem observation is also insufficient by itself. The accepted authority chain is sparse install success plus same-child app-server corroboration, fresh-child app-server corroboration, and local cache manifest proof tied to the same pre-install authority and requested home.

`rollback_guarded_refresh()` is the only primitive allowed to restore cache contents by file copy, and only from the per-run snapshot.

`abort_after_config_mutation()` must restore original config bytes and verify original config SHA256 when a process gate or hook-sensitive pre-install gate fails after `hooks-disabled` but before app-server install begins.

- [ ] **Step 3: Run primitive tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_mutation.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 3**

Run:

```bash
git add plugins/turbo-mode/tools/refresh/mutation.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py plugins/turbo-mode/tools/refresh/app_server_inventory.py
git commit -m "feat: add guarded refresh mutation primitives"
```

## Task 4: Implement Standard Installed Smoke

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/smoke.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_smoke.py`

- [ ] **Step 1: Write smoke tests**

Add tests that use temporary repos and stubbed commands for:

- the exact command templates in `## Standard Smoke Fixtures`;
- `HANDOFF_PLUGIN` and `TICKET_PLUGIN` derive from the `codex_home` argument passed to `run_standard_smoke()`;
- isolated rehearsal smoke rejects any Handoff or Ticket root under `/Users/jp/.codex`;
- real-home smoke requires an explicit real-home run context before `/Users/jp/.codex/plugins/cache` is accepted;
- Handoff session-state archive/write-state/read-state/clear-state;
- Handoff defer envelope emission through installed `defer.py`;
- Ticket create/update/read/query lifecycle through installed-cache command shape;
- Ticket update payload uses only update-supported fields. It must not include `acceptance_criteria`, because installed `ticket_workflow.py prepare` rejects that section for update.
- Ticket close/reopen lifecycle;
- Ticket audit repair dry-run;
- shell snippets are emitted or executed with Bash semantics, or the implementation uses argv arrays while separately preserving the canonical hook command string;
- raw smoke stdout/stderr written local-only with `0600`;
- redaction-safe smoke summary omits raw payload bodies and records output SHA256 values.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_smoke.py -q
```

Expected: tests fail because `smoke.py` does not exist.

- [ ] **Step 2: Implement `smoke.py`**

Required public API:

- `SmokeResult`: frozen dataclass with label, command sequence, exit code, stdout SHA256, stderr SHA256, and redacted status.
- `run_standard_smoke(*, local_only_run_root: Path, codex_home: Path, repo_root: Path) -> dict[str, object]`.

`run_standard_smoke()` must resolve installed plugin roots as `codex_home / "plugins/cache/turbo-mode/..."`. It must not embed `/Users/jp/.codex` constants. When `codex_home` is outside `/Users/jp/.codex`, any command path or environment variable that resolves under `/Users/jp/.codex` is a smoke failure before command execution.

The smoke summary must include:

- `selected_smoke_tier = "standard"`;
- `smoke_labels`;
- `results`;
- `raw_stdout_sha256`;
- `raw_stderr_sha256`;
- `final_status = "passed"` only when every smoke command exits `0`.

- [ ] **Step 3: Run smoke tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_smoke.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add plugins/turbo-mode/tools/refresh/smoke.py plugins/turbo-mode/tools/refresh/tests/test_smoke.py
git commit -m "feat: add guarded refresh installed smoke"
```

## Task 5: Wire `--guarded-refresh` Orchestration

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Modify: `plugins/turbo-mode/tools/refresh/mutation.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_mutation.py`

- [ ] **Step 1: Write orchestration and CLI tests**

Add tests for:

- `--guarded-refresh` rejects missing or mismatched `--source-implementation-commit` / `--source-implementation-tree` before process gates or mutation;
- `--guarded-refresh` rejects when `source_implementation_commit` is not an ancestor of `execution_head` before changed-path allowlisting, process gates, or mutation;
- `--guarded-refresh` computes `source_implementation_commit..execution_head` changed paths and rejects tracked executable/source/test/validator/plugin/marketplace deltas before process gates or mutation;
- `--guarded-refresh` allows a source-to-execution delta before mutation only when all changed paths are approved docs/evidence paths and records that proof in local-only evidence for later commit-safe validation;
- `--guarded-refresh` rejects untracked relevant files under `plugins/turbo-mode/tools/`, `plugins/turbo-mode/handoff/`, `plugins/turbo-mode/ticket/`, `plugins/turbo-mode/evidence/refresh/`, and `.agents/plugins/marketplace.json` before process gates or mutation;
- `--guarded-refresh --no-record-summary --codex-home /Users/jp/.codex` is rejected by argument parsing or preflight before process gates or mutation;
- `--guarded-refresh --codex-home /Users/jp/.codex` without `--record-summary` is rejected by argument parsing or preflight before process gates or mutation if summary publication is not made unconditional in the parser;
- `--isolated-rehearsal` without `--guarded-refresh` is rejected by argument parsing;
- `--guarded-refresh --isolated-rehearsal --codex-home /Users/jp/.codex` is rejected by argument parsing or preflight before process gates or mutation;
- real `/Users/jp/.codex --guarded-refresh` rejects missing `--rehearsal-proof` or missing `--rehearsal-proof-sha256` before process gates, lock acquisition, markers, snapshots, or mutation;
- real `/Users/jp/.codex --guarded-refresh` rejects a stale rehearsal proof when source implementation commit/tree, rehearsal execution head/tree, source-to-rehearsal delta proof, tool SHA256, app-server authority proof digest, seed manifest digest, dry-run proof digest, smoke digest, final status, requested isolated home, no-real-home proof, proof path, or proof SHA256 does not validate;
- real `/Users/jp/.codex --guarded-refresh` accepts only a rehearsal proof with `final_status = "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"` and `certification_status = "local-only-non-certified"`;
- real `/Users/jp/.codex --guarded-refresh` copies the validated rehearsal proof, companion SHA256, and digest-referenced artifacts into the live local-only evidence root before process gates, lock acquisition, markers, snapshots, or mutation;
- real `/Users/jp/.codex --guarded-refresh` rejects mutation when the live rehearsal-proof capture manifest is missing, digest-mismatched, permission-mismatched, or still points certification at `/private/tmp` instead of the captured bundle;
- `--seed-isolated-rehearsal-home` is mutually exclusive with `--dry-run`, `--inventory-check`, `--refresh`, `--guarded-refresh`, and `--recover`;
- `--seed-isolated-rehearsal-home --codex-home /Users/jp/.codex` is rejected by argument parsing or preflight before writing anything;
- `--seed-isolated-rehearsal-home` rejects missing or mismatched `--source-implementation-commit` / `--source-implementation-tree`;
- `--seed-isolated-rehearsal-home` creates only isolated-home config/cache/local-only seed state, records a local-only seed manifest, and never writes under `/Users/jp/.codex`;
- seeded isolated homes dry-run to `guarded-refresh-required` before rehearsal;
- `--guarded-refresh --isolated-rehearsal` requires `--codex-home` outside `/Users/jp/.codex`, runs full orchestration against only that isolated home, and returns `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED` instead of `MUTATION_COMPLETE_CERTIFIED`;
- isolated rehearsal writes a `rehearsal-proof.json` and companion SHA256 file keyed to the same source implementation commit/tree, seed manifest, isolated dry-run proof, app-server authority proof, no-real-home proof, smoke proof, and non-certified final status;
- real `/Users/jp/.codex` `--guarded-refresh` is rejected until a successful isolated rehearsal proof from the same source implementation commit/tree and app-server authority contract is supplied and validated;
- `--guarded-refresh` fails before mutation when `plan_refresh()` does not return `guarded-refresh-required`;
- `--guarded-refresh` proves app-server executable, version, schema, and Codex-home launch/read authority before snapshots or hook disable without calling live real-home `plugin/install`;
- `--guarded-refresh` atomically persists `pre_snapshot_app_server_launch_authority_sha256` in the run-state marker before `snapshot-written`;
- `--guarded-refresh` rejects snapshot creation, hook disable, live cache install, smoke, or recovery scaffolding when `pre_snapshot_app_server_launch_authority_sha256` is missing, stale, or not tied to the same run id/source/execution identity;
- live real-home `plugin/install` is called only after `snapshot-written` marker evidence is durable;
- `plugin/install` is rejected until the marker contains `pre_install_app_server_target_authority_sha256` for the same run id/source/execution identity and install child before the first install request;
- app-server executable/version/home-authority failure after hooks were touched restores original config or retains the marker with `MUTATION_ABORTED_RESTORE_FAILED`;
- `--guarded-refresh` fails before mutation when process gate blocks;
- `--guarded-refresh` runs required censuses in order: `before-snapshot`, `after-hook-disable`, `before-install`, `post-mutation`;
- run-state marker phases follow the Guarded Mutation Phase State Machine exactly;
- snapshot metadata is atomically persisted before hook disable;
- `true`, `absent-default-enabled`, `absent-unproven`, `absent-disabled`, `false`, `malformed`, and `externally-changed` hook states follow the Plugin Hooks Config State Contract;
- hook state is restored before final inventory and smoke;
- final inventory uses a fresh app-server child;
- process-gate failure after hooks are disabled restores config and records `MUTATION_ABORTED_CONFIG_RESTORED`;
- process-gate failure after hooks are disabled that cannot restore config records `MUTATION_ABORTED_RESTORE_FAILED` and retains the marker;
- failure in install, equality, inventory, or smoke calls rollback and records `MUTATION_FAILED_ROLLBACK_COMPLETE`;
- post-mutation process blocker records `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` and suppresses certified commit-safe summary;
- commit-safe validation failure after successful mutation records `MUTATION_COMPLETE_EVIDENCE_FAILED` and does not claim green completion.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py -q
```

Expected: tests fail until orchestration is wired.

- [ ] **Step 2: Implement guarded-refresh orchestration**

Required behavior:

1. Build `RefreshPlanResult` with `mode = "plan-refresh"` and `inventory_check = True`.
2. Require `terminal_plan_status = "guarded-refresh-required"` before mutation.
3. Require summary publication for real guarded-refresh runs against `/Users/jp/.codex`. Either make summary publication unconditional for that mode or reject a missing `--record-summary` flag before process gates or mutation. Also reject `--no-record-summary` for real guarded-refresh runs.
4. Parse `--isolated-rehearsal` only as a guarded-refresh modifier and reject it with real `/Users/jp/.codex`.
5. Parse `--rehearsal-proof <PATH>` and `--rehearsal-proof-sha256 <SHA256>` as required real `/Users/jp/.codex --guarded-refresh` inputs. Validate both and copy the validated proof bundle into the live local-only evidence root before process gates, lock acquisition, marker creation, snapshots, config edits, cache edits, app-server install, smoke, or summary publication.
6. Implement `--seed-isolated-rehearsal-home` as a non-mutating-to-real-home seed mode:
   - require `--codex-home` outside `/Users/jp/.codex`;
   - require source implementation commit/tree inputs and verify the tree;
   - create the minimal isolated config/cache/local-only state needed to model the exact Plan 05 six-path pre-refresh drift set, using the Plan 06 isolated-seed carve-out from the direct-copy rule;
   - write a local-only seed manifest under the isolated home with the expected six-path drift list and digest, source paths, source commit/tree, source manifest digest, pre-refresh cache manifest digest, post-seed dry-run manifest digest, created isolated paths, per-path SHA256 digests, and path-guard results;
   - return only a seed status/proof that is explicitly non-certifying and cannot be used as installed-refresh completion evidence;
   - fail if any generated seed path resolves under `/Users/jp/.codex`.
7. Require `--isolated-rehearsal` for temporary-Codex-home guarded refresh. It must run the same orchestration, app-server install, config handling, rollback eligibility, smoke, and local-only evidence code paths against the isolated home, return `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED`, write the rehearsal proof contract, and prove no path under `/Users/jp/.codex` was read as the app-server config/cache/plugin authority. It must not enter the repo-local commit-safe publication path.
8. Compute `execution_head/tree`.
9. Require `git merge-base --is-ancestor "$source_implementation_commit" "$execution_head"` before any endpoint changed-path comparison. Reject non-ancestor execution heads before process gates, locks, markers, snapshots, config edits, cache edits, marketplace changes, app-server install, or smoke.
10. Reject disallowed tracked source-to-execution deltas before process gates, locks, markers, snapshots, config edits, cache edits, marketplace changes, app-server install, or smoke. The allowed set is docs/evidence-only and must exclude executable refresh code, validators, plugin source, marketplace metadata, tests, and installed-cache input files.
11. Reject untracked relevant files before process gates, locks, markers, snapshots, config edits, cache edits, marketplace changes, app-server install, or smoke. The untracked check must use git, honor `.gitignore`, and cover the full `plugins/turbo-mode/tools/` Python import root, `.agents/plugins/marketplace.json`, plugin source, and refresh evidence paths.
12. For real `/Users/jp/.codex` runs, copy the validated rehearsal proof bundle into the live local-only evidence root and verify the capture manifest before any mutation-capable phase.
13. Acquire the refresh lock.
14. Write run-state marker before config, cache, marketplace, or app-server install mutation.
15. Run `before-snapshot` process gate.
16. Prove app-server executable, version, accepted schema, and Codex-home launch/read authority before snapshots or hook disable. This includes confirming that a child app-server will use the requested Codex home/config/cache roots for read-only `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list` requests. For real `/Users/jp/.codex` runs, this step must not call `plugin/install`.
17. Atomically replace marker with `pre_snapshot_app_server_launch_authority_sha256` and phase `app-server-launch-authority-proven`.
18. If plugin hook state is `absent-unproven`, collect pre-refresh runtime inventory before snapshots; continue only if it proves expected Ticket hook enablement and promotes the state to `absent-default-enabled`.
19. Snapshot config and cache roots.
20. Atomically replace marker with the retained `pre_snapshot_app_server_launch_authority_sha256`, snapshot paths, snapshot manifest digest, original config SHA256, pre-refresh cache manifest SHA256 map, and recovery eligibility.
21. Apply the Plugin Hooks Config State Contract:
   - `true`: disable hooks by writing `features.plugin_hooks = false`;
   - `absent-default-enabled`: preserve the absent key and record no config write;
   - `absent-unproven`: unreachable here because it must already be proven or blocked before snapshots;
   - `absent-disabled`, `false`, `malformed`, or `externally-changed`: fail before cache mutation.
22. Atomically replace marker with plugin-hooks start state, hook-disabled config SHA256 when a write occurred, and expected intermediate config SHA256.
23. Run `after-hook-disable` process gate.
24. If `after-hook-disable` blocks, restore original config, write abort evidence, and clear or retain the marker according to restore result.
25. Run `before-install` process gate.
26. If `before-install` blocks, restore original config, write abort evidence, and clear or retain the marker according to restore result.
27. Start app-server, prove `AppServerPreInstallTargetAuthority` for the install child, and atomically replace marker with `pre_install_app_server_target_authority_sha256` before the first `plugin/install` request. This step is allowed only after snapshot marker durability has been verified.
28. Run `plugin/install` for Handoff and Ticket only after the marker contains that pre-install target authority digest. Assert sparse success/auth schema and request-id correlation for both install responses, rewrite the installed Ticket hook manifest to the active Codex home, restore config bytes on disk, then collect same-child post-install app-server corroboration with `plugin/read`, `plugin/list`, `skills/list`, and a hook-disabled `hooks/list` response when the child was launched with hooks disabled.
29. Terminate the install child, start a fresh app-server child, and collect hook-certifying fresh-child post-install app-server corroboration with `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`.
30. Write `AppServerInstallAuthority` from the install transcript, same-child corroboration transcript, fresh-child corroboration transcript, retained pre-install target authority digest, installed cache paths, and post-install cache manifest SHA256 map.
31. Atomically replace marker with install transcript digest, same-child and fresh-child corroboration transcript digests, `AppServerInstallAuthority` digest, retained `pre_install_app_server_target_authority_sha256`, app-server child PID records, and post-install cache manifest SHA256 map.
32. Restore config before final inventory and smoke.
33. Start fresh app-server inventory and verify runtime alignment.
34. Verify source/cache equality.
35. Run standard smoke.
36. Run `post-mutation` process gate.
37. If `post-mutation` blocks, write `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`, suppress certified commit-safe summary, and clear marker only after local-only evidence is durable. The operator must then choose retained-run certification or manual rollback/adjudication before claiming closeout.
38. Branch by run type before repo-local summary publication:
   - isolated rehearsal: write only local-only non-certified rehearsal evidence, write final status `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED`, write `rehearsal-proof.json` plus SHA256, and skip candidate summary creation, commit-safe validation, repo-local summary publication, and certified status naming;
   - real `/Users/jp/.codex` guarded refresh: continue to commit-safe publication only after the supplied rehearsal proof remains valid and the captured rehearsal-proof bundle under the live local-only evidence root validates. Real guarded-refresh runs may not skip summary publication.
39. For real `/Users/jp/.codex` guarded refresh, publish commit-safe summary only after metadata and redaction validators pass.
40. If commit-safe publication or validation fails after successful real mutation, write `MUTATION_COMPLETE_EVIDENCE_FAILED`, suppress green completion, demote any repo-local summary to `<RUN_ID>.summary.failed.json` with crash-safe non-overwriting rename semantics, and clear marker only after evidence-failed status is durable. The operator must then choose retained-run certification or manual rollback/adjudication before claiming closeout.
41. Write `MUTATION_COMPLETE_CERTIFIED` local-only final status only for real `/Users/jp/.codex` guarded refresh after all gates pass.
42. Clear run-state marker only after final local-only evidence is durable.

Any failure from `plugin/install` through smoke must call `rollback_guarded_refresh()`. Any failure after config mutation but before install must call `abort_after_config_mutation()`. No failure path after `hooks-disabled` may return without either restoring config or retaining the marker for recovery.

- [ ] **Step 3: Run orchestration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 5**

Run:

```bash
git add plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh/mutation.py plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py
git commit -m "feat: wire guarded refresh mutation lane"
```

## Task 6: Add Recovery Mode

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Modify: `plugins/turbo-mode/tools/refresh/lock_state.py`
- Modify: `plugins/turbo-mode/tools/refresh/mutation.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_lock_state.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_mutation.py`

- [ ] **Step 1: Write recovery tests**

Add tests for:

- ordinary `--guarded-refresh` refuses when any run-state marker exists;
- `--recover <RUN_ID>` acquires the refresh lock before acting;
- `--guarded-refresh --recover <RUN_ID>` is rejected by argument parsing as a conflicting mode;
- `--guarded-refresh` and `--recover` reject missing `--source-implementation-commit` or `--source-implementation-tree`;
- `--guarded-refresh` rejects a source commit/tree mismatch before process gates or mutation;
- `--recover <RUN_ID>` rejects a source commit/tree mismatch before process gates, lock acquisition, config restore, cache restore, or app-server inventory;
- `--recover <RUN_ID>` rejects when the current execution head/tree or tool SHA256 differs from the marker `execution_head`, `execution_tree`, or `tool_sha256`;
- `--recover <RUN_ID>` rejects when the marker source implementation commit/tree differs from the supplied source implementation commit/tree;
- `--recover <RUN_ID>` does not use a docs/evidence-only delta allowance. Recovery either runs from the exact marker execution identity or stops with `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED`;
- `--recover <RUN_ID>` self-blocks when invoked from an active Codex Desktop or Codex CLI session;
- recovery rejects active Codex Desktop, Codex CLI, hook, runtime, uncertain high-risk, or unrelated app-server process rows before config restore, cache restore, or app-server inventory;
- recovery runs a post-recovery process gate after fresh inventory and records local-only evidence if exclusivity is unproven;
- recovery rejects held lock;
- recovery rejects live owner PID/start-time mismatch ambiguity using the owner PID plus observed process start time or boot-relative identity recorded in `LockOwner`;
- recovery preserves the original owner JSON under immutable local-only evidence before writing recovery owner metadata;
- recovery validates marker `original_run_owner_sha256` against the preserved original owner, not against recovery owner;
- recovery is phase-aware for config SHA expectations: phases before `config-restored-before-final-inventory` require current config SHA256 to equal the recorded expected intermediate SHA256 before restore, while phases at or after `config-restored-before-final-inventory` accept only the original config SHA256 and must not rewrite config unnecessarily;
- recovery restores config and cache snapshots;
- recovery starts fresh app-server inventory before declaring `RECOVERY_COMPLETE`;
- recovery fails closed with `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED` when config SHA256 differs from the phase-appropriate expected value.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_lock_state.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py -q
```

Expected: tests fail until recovery is implemented.

- [ ] **Step 2: Implement recovery**

Standalone `--recover <RUN_ID>` must:

1. Run only from an external shell during an exclusive maintenance window, using the same self-blocking caller check as `--guarded-refresh`.
2. Acquire the same refresh lock.
3. Re-read marker and owner metadata after lock acquisition.
4. Copy original/stale owner metadata to immutable local-only recovery evidence before writing recovery owner metadata.
5. Verify marker `run_id`, `mode`, `source_implementation_commit`, `source_implementation_tree`, `execution_head`, `execution_tree`, `tool_sha256`, and `original_run_owner_sha256`.
6. Require exact recovery authority:
   - supplied source implementation commit/tree must match the marker source implementation commit/tree;
   - current execution head/tree must match the marker execution head/tree;
   - current tool SHA256 must match the marker tool SHA256;
   - no tracked or untracked relevant delta approval can override a recovery identity mismatch in Plan 06.
7. If recovery would require code from a different source or execution boundary, stop with `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED` before process gates, lock writes beyond recovery owner preservation, config restore, cache restore, or app-server inventory. Plan 06 does not define a supervised automated path for defective recovery code; that is manual recovery territory.
8. Verify snapshot paths, snapshot manifest digest, original config SHA256, and recovery eligibility are present for the marker phase.
9. Run `before-recovery-restore` process gate and reject active Codex Desktop, Codex CLI, hook, runtime, uncertain high-risk, or unrelated app-server processes before config or cache restore.
10. Apply phase-aware config SHA validation:
   - before `config-restored-before-final-inventory`, restore config only if current SHA256 matches the expected intermediate state recorded by the marker;
   - at or after `config-restored-before-final-inventory`, require current SHA256 to equal the original config SHA256 and record that no config rewrite was needed;
   - any other current SHA256 is `externally-changed` and must fail closed without overwriting unrelated edits.
11. Restore cache from snapshot paths when the phase may have reached cache mutation.
12. Start fresh app-server inventory and verify restored plugin/read, skills, and hooks.
13. Run `post-recovery` process gate.
14. Write `RECOVERY_COMPLETE` local-only evidence only if recovery inventory and post-recovery process gate pass.
15. If recovery inventory or post-recovery process gate fails after restore, retain marker and write local-only `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED` evidence.
16. Clear marker only after recovery evidence is durable.

- [ ] **Step 3: Run recovery tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_lock_state.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 6**

Run:

```bash
git add plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh/lock_state.py plugins/turbo-mode/tools/refresh/mutation.py plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_lock_state.py plugins/turbo-mode/tools/refresh/tests/test_mutation.py
git commit -m "feat: add guarded refresh recovery"
```

## Task 7: Add Mutation Commit-Safe Evidence

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Modify: `plugins/turbo-mode/tools/refresh_validate_run_metadata.py`
- Modify: `plugins/turbo-mode/tools/refresh_validate_redaction.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_validation.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

- [ ] **Step 1: Write evidence schema tests**

Add tests proving guarded-refresh commit-safe summaries:

- use schema version `turbo-mode-refresh-commit-safe-plan-06`;
- contain `mode = "guarded-refresh"`;
- contain `source_implementation_commit`, `source_implementation_tree`, `execution_head`, and `execution_tree`;
- for retained-run certification, also contain `certification_source_commit`, `certification_source_tree`, `certification_execution_head`, `certification_execution_tree`, `certification_mode = "retained-run"`, `retained_summary_path`, `original_run_final_status`, `retained_certification_outcome`, and `prior_summary_path_state`;
- contain `isolated_rehearsal_run_id`, `rehearsal_proof_sha256`, `rehearsal_proof_validation_status`, `source_to_rehearsal_execution_delta_status`, `source_to_rehearsal_allowed_delta_proof_sha256`, `source_to_rehearsal_changed_paths_sha256`, `isolated_app_server_authority_proof_sha256`, `no_real_home_authority_proof_sha256`, `pre_snapshot_app_server_launch_authority_sha256`, `pre_install_app_server_target_authority_sha256`, and `live_app_server_authority_proof_sha256`;
- contain `rehearsal_proof_capture_manifest_sha256` and reject certified summaries when retained-run replay cannot validate the captured proof bundle under the live local-only evidence root;
- contain `final_status`;
- contain `phase_reached`;
- contain `exclusivity_status`;
- contain SHA256s for pre/post cache manifests, pre/post config, post-refresh inventory, smoke summary, and post-mutation process census;
- contain `rollback_or_restore_status = "not-attempted"` only for successful certified mutation;
- reject raw process listings, app-server transcripts, config bytes, smoke stdout, and smoke stderr;
- reject `exclusive_window_observed_by_process_samples` unless every required process gate summary is present and non-blocking;
- reject stale local-only evidence when `execution_head`, tool SHA256, source manifest, post-refresh cache manifest, inventory digest, smoke digest, or process census digest differs;
- reject certified summaries when rehearsal proof fields are missing, rehearsal proof validation status is not `validated-before-live-mutation`, rehearsal proof SHA256 differs from the supplied proof file, isolated app-server authority proof digest differs from the rehearsal proof, no-real-home authority proof digest differs from the rehearsal proof, `pre_snapshot_app_server_launch_authority_sha256` is absent from the marker/local-only evidence before `snapshot-written`, `pre_install_app_server_target_authority_sha256` is absent from marker/local-only evidence before the first install request, or live app-server authority proof digest is absent from live local-only evidence;
- reject certified summaries when the rehearsal proof's `tool_sha256` does not match the source implementation tool digest or when the proof's `source_to_rehearsal_execution_delta_status` is missing for a rehearsal executed from a different `execution_head/tree`;
- reject certified summaries when `source_implementation_commit` is not an ancestor of `execution_head`;
- reject certified summaries when `execution_head != source_implementation_commit` unless an allowed-delta proof shows only approved docs/evidence paths changed between those commits;
- reject certified summaries when the live CLI did not run the same allowed-delta proof before mutation;
- allow final post-publish replay dirty-state recomputation to see exactly the published summary path, and no other relevant dirty path, because Task 9 replay intentionally runs after the repo-local summary file is written and before it is committed;
- reject live final post-publish replay when any dirty relevant path other than `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json` is present;
- reject retained final post-publish replay when any dirty relevant path other than `plugins/turbo-mode/evidence/refresh/<RUN_ID>.retained.summary.json` is present;
- reject live final replay when both `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json` and `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.failed.json` exist for the same run id;
- reject retained-run certification when `<RUN_ID>.summary.json` already exists, because retained certification may not create a second green summary beside a live certified summary;
- allow retained-run certification when `<RUN_ID>.summary.failed.json` exists only if the retained summary records the failed summary path, SHA256, and forensic-demotion status without modifying the failed summary;
- reject retained-run certification when `<RUN_ID>.retained.summary.json` or `<RUN_ID>.retained.summary.failed.json` already exists;
- reject detached replay when validator/tool/source code comes from `source_implementation_commit` but runtime config, app-server inventory, dirty-state, and execution identity are recomputed from the detached source checkout instead of the execution checkout;
- reject retained-run certification when validator/tool/source code comes from `certification_source_commit` but original mutation evidence is recomputed as if the mutation executed from that newer certification commit;
- reject retained-run certification when the current installed-cache state is `no-drift` but retained local-only evidence cannot prove a successful prior mutation for the same run id;
- reject retained-run certification when current installed-cache state is `guarded-refresh-required` unless retained local-only evidence proves the cache was rolled back or never changed;
- reject green retained-run certification from `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` unless retained evidence proves the original exclusivity-unproven status was misclassified and every required original process gate summary was present and non-blocking;
- reject retained-run certification when source-to-certification deltas include mutation orchestration, app-server install behavior, plugin source, marketplace metadata, smoke semantics, or installed-cache input files;
- prove the Plan 05 failure mode with a regression fixture: create a detached source-code root that lacks the execution checkout's runtime config/app-server inventory context, run validators with `source_code_root != execution_repo_root`, and assert the split-root invocation passes only when runtime-bound recomputation uses `execution_repo_root`;
- reject legacy replay invocations that pass only `--repo-root` for guarded-refresh final validation after the split-root API exists;
- leave no repo-local `<RUN_ID>.summary.json` when candidate validation fails before publish;
- demote a published but final-replay-failed live summary to `<RUN_ID>.summary.failed.json` with crash-safe non-overwriting rename semantics, without overwriting an existing failed summary, and reject any final state where live summary names coexist;
- demote a published but final-replay-failed retained summary to `<RUN_ID>.retained.summary.failed.json` with crash-safe non-overwriting rename semantics, without overwriting existing retained evidence.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py plugins/turbo-mode/tools/refresh/tests/test_validation.py plugins/turbo-mode/tools/refresh/tests/test_cli.py -q
```

Expected: tests fail until evidence schema is implemented.

- [ ] **Step 2: Implement mutation commit-safe summaries**

Base summary fields required for `MUTATION_COMPLETE_CERTIFIED`:

- `schema_version`
- `run_id`
- `mode`
- `source_implementation_commit`
- `source_implementation_tree`
- `execution_head`
- `execution_tree`
- `tool_path`
- `tool_sha256`
- `isolated_rehearsal_run_id`
- `rehearsal_proof_sha256`
- `rehearsal_proof_validation_status`
- `source_to_rehearsal_execution_delta_status`
- `source_to_rehearsal_allowed_delta_proof_sha256`
- `source_to_rehearsal_changed_paths_sha256`
- `isolated_app_server_authority_proof_sha256`
- `no_real_home_authority_proof_sha256`
- `pre_snapshot_app_server_launch_authority_sha256`
- `pre_install_app_server_target_authority_sha256`
- `live_app_server_authority_proof_sha256`
- `source_manifest_sha256`
- `pre_refresh_cache_manifest_sha256`
- `post_refresh_cache_manifest_sha256`
- `pre_refresh_config_sha256`
- `post_refresh_config_sha256`
- `post_refresh_inventory_sha256`
- `selected_smoke_tier`
- `smoke_summary_sha256`
- `post_mutation_process_census_sha256`
- `exclusivity_status`
- `phase_reached`
- `final_status`
- `rollback_or_restore_status`
- `local_only_evidence_root`
- `metadata_validation_summary_sha256`
- `redaction_validation_summary_sha256`

Additional fields required when `certification_mode = "retained-run"`:

- `certification_mode = "retained-run"`
- `certification_source_commit`
- `certification_source_tree`
- `certification_execution_head`
- `certification_execution_tree`
- `retained_summary_path = "plugins/turbo-mode/evidence/refresh/<RUN_ID>.retained.summary.json"`
- `original_run_final_status`
- `retained_certification_outcome`
- `prior_summary_path_state`
- `prior_summary_path`
- `prior_summary_sha256`
- `prior_failed_summary_path`
- `prior_failed_summary_sha256`
- `prior_failed_summary_status`
- `source_to_certification_delta_status`
- `source_to_certification_changed_paths_sha256`
- `source_to_certification_allowed_delta_proof_sha256`
- `rehearsal_proof_capture_manifest_sha256`
- `retained_no_mutation_proof_sha256`

For retained-run certification from a prior `MUTATION_COMPLETE_EVIDENCE_FAILED`, `retained_certification_outcome` may be `retained-certified` only when original mutation facts, original process samples, captured rehearsal proof, source/cache equality, final inventory, standard smoke, redaction, metadata, and current no-mutation proof all validate. For retained-run certification from a prior `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`, `retained_certification_outcome` may be `retained-certified` only when retained evidence proves the original status was misclassified and every required original process gate summary was present and non-blocking. If the original post-mutation process gate actually blocked or is missing, retained closeout must use `retained-uncertified` or `manual-adjudication-required`, must not publish `<RUN_ID>.retained.summary.json` as green certified evidence, and must not set `final_status = "MUTATION_COMPLETE_CERTIFIED"`.

Use the existing candidate/final validator digest bootstrap from Plan 04/05. Do not publish the repo-local summary until candidate and final validators pass.

For `MUTATION_COMPLETE_CERTIFIED`, `rehearsal_proof_validation_status` must be exactly `validated-before-live-mutation`. The summary must not include raw rehearsal proof JSON, raw app-server transcripts, raw path inventories, or local-only file contents. It may include only the bounded SHA256 digests listed above plus the isolated rehearsal run id.

`source_to_rehearsal_execution_delta_status` must be exactly one of:

- `identical`: rehearsal `execution_head/tree` equals `source_implementation_commit/tree`; `source_to_rehearsal_changed_paths_sha256` is the SHA256 of the empty sorted changed-path list, and `source_to_rehearsal_allowed_delta_proof_sha256` points to a local-only proof record that states no source-to-rehearsal delta existed.
- `approved-docs-evidence-only`: rehearsal `execution_head/tree` differs from `source_implementation_commit/tree`, and the changed-path proof shows only approved docs/evidence paths changed.

Recovery evidence in Plan 06 is local-only. Do not implement a commit-safe `RECOVERY_COMPLETE` summary in this plan. A later plan may add recovery certification only if it defines a complete schema, dirty-state policy, validator replay contract, and demotion behavior for recovery summaries.

Split-root validator CLI contract:

- `refresh_validate_run_metadata.py` and `refresh_validate_redaction.py` must accept `--source-code-root` and `--execution-repo-root` for guarded-refresh validation.
- `--repo-root` must not be used by guarded-refresh final replay. Keep it only for older non-mutating validation modes if compatibility is required.
- `source_code_root` supplies validator code, `tool_path` digest checks, source manifest checks, and `source_implementation_commit/tree` verification.
- `execution_repo_root` supplies `execution_head/tree`, dirty-state recomputation, runtime config projection, app-server runtime inventory recomputation, current-run identity, and published evidence path containment.
- Final replay mode after publish must accept a single dirty relevant path only when it exactly equals the summary under validation: `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json` for the live lane, or `plugins/turbo-mode/evidence/refresh/<RUN_ID>.retained.summary.json` for retained-run certification. Candidate validation before publish must still require no dirty relevant paths.
- If `source_code_root != execution_repo_root`, validators must record that split in their validation summaries without copying absolute local-only paths into commit-safe evidence.
- A validator that needs both source and runtime context must name both parameters in function signatures. Do not pass a single `repo_root` through helpers that perform mixed source/runtime work.

Allowed-delta proof fields required when `execution_head != source_implementation_commit`:

- `source_to_execution_ancestor_status = "source-is-ancestor"`;
- `source_to_execution_merge_base`;
- `source_to_execution_delta_status = "docs-evidence-only"`;
- `source_to_execution_changed_paths`;
- `source_to_execution_rejected_paths = []`;
- `source_to_execution_diff_sha256`.

- [ ] **Step 3: Run evidence tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py plugins/turbo-mode/tools/refresh/tests/test_validation.py plugins/turbo-mode/tools/refresh/tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 7**

Run:

```bash
git add plugins/turbo-mode/tools/refresh/commit_safe.py plugins/turbo-mode/tools/refresh/validation.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py plugins/turbo-mode/tools/refresh/tests/test_validation.py plugins/turbo-mode/tools/refresh/tests/test_cli.py
git commit -m "feat: add guarded refresh commit-safe evidence"
```

## Task 7B: Add Retained-Run Certification

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Add: `plugins/turbo-mode/tools/refresh/retained_run.py`
- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Modify: `plugins/turbo-mode/tools/refresh_validate_run_metadata.py`
- Modify: `plugins/turbo-mode/tools/refresh_validate_redaction.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
- Add or modify: `plugins/turbo-mode/tools/refresh/tests/test_retained_run.py`

- [ ] **Step 1: Write retained-run certification tests**

Add tests proving:

- `--certify-retained-run <RUN_ID>` is mutually exclusive with mutation, recovery, dry-run, inventory, refresh, seed, and rehearsal modes;
- the mode refuses to run when the retained local-only run root is missing or the retained status is not `MUTATION_COMPLETE_EVIDENCE_FAILED` or `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`;
- the mode refuses to call app-server `plugin/install`, write config, write installed cache, restore snapshots, seed rehearsal homes, or clear recovery markers;
- the mode accepts current `terminal_plan_status = "no-drift"` only when retained local-only evidence proves a successful prior mutation for the same run id;
- the mode accepts current `terminal_plan_status = "guarded-refresh-required"` only when retained evidence proves rollback occurred or the cache was never changed;
- the mode publishes retained certification only to `plugins/turbo-mode/evidence/refresh/<RUN_ID>.retained.summary.json`;
- the mode rejects path state where `<RUN_ID>.summary.json` already exists;
- the mode accepts an existing `<RUN_ID>.summary.failed.json` only as immutable forensic evidence and records its path/SHA256/status in the retained summary;
- the mode rejects path state where `<RUN_ID>.retained.summary.json` or `<RUN_ID>.retained.summary.failed.json` already exists;
- the mode demotes a failed retained post-publish replay only to `<RUN_ID>.retained.summary.failed.json`;
- the mode does not green-certify `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` when the original post-mutation process gate actually blocked or is missing;
- the mode may green-certify a prior `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN` only when retained evidence proves that status was misclassified and every original process gate summary was present and non-blocking;
- the mode rejects source-to-certification deltas that touch mutation orchestration, app-server install behavior, plugin source, marketplace metadata, smoke semantics, or installed-cache input files;
- the mode permits only validator, commit-safe builder, redaction tooling, tests, and docs/evidence deltas needed to certify the retained run;
- candidate validation requires no dirty relevant repo paths before publish;
- final replay after publish allows only `plugins/turbo-mode/evidence/refresh/<RUN_ID>.retained.summary.json` as a dirty relevant repo path;
- retained-run certification validates the captured rehearsal-proof bundle from the live local-only evidence root, not from the original isolated `/private/tmp` path;
- pre-publish failure leaves no repo-local summary and writes a local-only retained-certification failure status;
- post-publish failure demotes `<RUN_ID>.retained.summary.json` to `<RUN_ID>.retained.summary.failed.json` with crash-safe non-overwriting rename semantics and preserves replay roots.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_retained_run.py plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py plugins/turbo-mode/tools/refresh/tests/test_validation.py -q
```

Expected: tests fail until retained-run certification is implemented.

- [ ] **Step 2: Implement retained-run certification**

Required behavior:

1. Parse `--certify-retained-run <RUN_ID>` as a standalone non-mutating mode.
2. Locate the retained local-only run root and terminal status without creating or mutating installed-cache state.
3. Recompute current non-mutating plan status and classify `no-drift` vs `guarded-refresh-required` according to the retained evidence rules above.
4. Build split roots for mutation source, certification source, and execution repo.
5. Validate source-to-certification changed paths against the retained-run allowlist.
6. Validate the live captured rehearsal-proof bundle and companion SHA256 under the retained run's local-only evidence root.
7. Rebuild candidate commit-safe summary under the local-only root with original mutation source/execution identity, retained-run certification identity, retained summary path state, and retained outcome.
8. Run metadata and redaction candidate validators before publish.
9. Atomically publish `<RUN_ID>.retained.summary.json` only after candidate validators pass.
10. Run final split-root replay and redaction replay after publish.
11. Demote or preserve summaries according to the Retained-run certification rules in the Final Status Vocabulary section.
12. Write local-only retained-certification status that states one of: `retained-certified`, `retained-uncertified`, `manual-rollback-required`, or `manual-adjudication-required`.

- [ ] **Step 3: Run retained-run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_retained_run.py plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py plugins/turbo-mode/tools/refresh/tests/test_validation.py -q
```

Expected: pass.

- [ ] **Step 4: Commit Task 7B**

Run:

```bash
git add plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh/retained_run.py plugins/turbo-mode/tools/refresh/commit_safe.py plugins/turbo-mode/tools/refresh/validation.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py plugins/turbo-mode/tools/refresh/tests/test_cli.py plugins/turbo-mode/tools/refresh/tests/test_retained_run.py plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py plugins/turbo-mode/tools/refresh/tests/test_validation.py
git commit -m "feat: add retained run certification"
```

## Task 8: Pre-Live Verification Gate

**Files:**

- Modify: `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md`

- [ ] **Step 1: Verify implementation runtime**

Run:

```bash
python3 - <<'PY'
import sys
print(sys.version)
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
```

Expected:

- command exits `0`;
- Python is `>= 3.11`;
- record the exact version in `## Pre-Live Verification Evidence`.

- [ ] **Step 2: Run targeted refresh tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected:

- all refresh tests pass;
- no `__pycache__`, `.pytest_cache`, or `.ruff_cache` residue appears under `plugins/turbo-mode/`.

- [ ] **Step 3: Run formatting and lint gates**

Run:

```bash
uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py
git diff --check
```

Expected: both commands pass.

- [ ] **Step 4: Run residue scan**

Run:

```bash
find plugins/turbo-mode -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .venv \) -print
find plugins/turbo-mode -type f \( -name '*.pyc' -o -name .DS_Store \) -print
```

Expected: no output.

- [ ] **Step 5: Re-run non-mutating plan status**

Run:

```bash
RUN_ID="plan06-prelive-reanchor-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected:

- `terminal_plan_status = "guarded-refresh-required"`;
- `app_server_inventory_status = "collected"`;
- `residue_issues = []`.

Do not continue to live mutation if this returns `blocked-preflight`, `coverage-gap-blocked`, `repairable-runtime-config-mismatch`, `unrepairable-runtime-config-mismatch`, `filesystem-no-drift`, or `no-drift`.

- [ ] **Step 6: Run isolated full-dress guarded-refresh rehearsal**

This is mandatory before any real `/Users/jp/.codex` mutation. It must exercise the integrated app-server install, config handling, marker lifecycle, rollback eligibility, source/cache equality, smoke, process gates, and evidence path against an isolated Codex home. It must not read or mutate `/Users/jp/.codex` as app-server config/cache/plugin authority, and it must not return `MUTATION_COMPLETE_CERTIFIED`.

The isolated home must be seeded as a miniature of the intended pre-refresh drift state. An empty temporary home is not acceptable because it can fail preflight before exercising the integrated mutation path. This is the only Plan 06 direct-copy/synthesis carve-out outside rollback/recovery: it is non-certifying, targets only the temporary Codex home, records provenance and path guards in the seed manifest, and cannot be reused as evidence of real installed-cache completion. The seeding step must copy or synthesize only the minimum temporary-home state needed to model:

- an aligned runtime config baseline with the intended hook state;
- pre-refresh installed Handoff and Ticket cache roots that intentionally represent the exact inherited Plan 05 six-path old/drifted state;
- a repo marketplace reference pointing at the source plugins under `EXECUTION_ROOT`;
- local-only refresh roots under the isolated home, not under `/Users/jp/.codex`;
- no config, cache, hook, local-only, or installed path that resolves to `/Users/jp/.codex`.

The seed manifest must contain the six canonical drift paths named in the Source Evidence Read section, the sorted-path-list SHA256 for that set, the source manifest SHA256, the pre-refresh isolated-cache manifest SHA256 before rehearsal, and a post-seed dry-run manifest SHA256 proving the isolated home returns the same `guarded-refresh-required` classification for that drift set. A rehearsal seeded with a plausible but different drift set is not valid for Task 9 approval.

Run from an external shell, not from inside this Codex conversation:

```bash
set -euo pipefail
EXECUTION_ROOT="/Users/jp/Projects/active/codex-tool-dev"
ISOLATED_CODEX_HOME="$(mktemp -d /private/tmp/codex-tool-dev-plan06-rehearsal-home.XXXXXX)"
SEED_RUN_ID="plan06-isolated-seed-$(date -u +%Y%m%d-%H%M%S)"
PREFLIGHT_RUN_ID="plan06-isolated-preflight-$(date -u +%Y%m%d-%H%M%S)"
RUN_ID="plan06-isolated-rehearsal-$(date -u +%Y%m%d-%H%M%S)"
REHEARSAL_PROOF_PATH="$ISOLATED_CODEX_HOME/local-only/turbo-mode-refresh/rehearsals/$RUN_ID/rehearsal-proof.json"
REHEARSAL_PROOF_SHA256_PATH="$REHEARSAL_PROOF_PATH.sha256"
PYTHON_BIN="$(command -v python3)"
test "$ISOLATED_CODEX_HOME" != "/Users/jp/.codex"
test -d "$ISOLATED_CODEX_HOME"
"$PYTHON_BIN" - <<'PY'
import sys
print(sys.executable)
print(sys.version)
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache "$PYTHON_BIN" \
  "$EXECUTION_ROOT/plugins/turbo-mode/tools/refresh_installed_turbo_mode.py" \
  --seed-isolated-rehearsal-home \
  --run-id "$SEED_RUN_ID" \
  --repo-root "$EXECUTION_ROOT" \
  --codex-home "$ISOLATED_CODEX_HOME" \
  --source-implementation-commit "<full-source-implementation-commit>" \
  --source-implementation-tree "<source-implementation-tree>" \
  --json
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache "$PYTHON_BIN" \
  "$EXECUTION_ROOT/plugins/turbo-mode/tools/refresh_installed_turbo_mode.py" \
  --dry-run \
  --inventory-check \
  --run-id "$PREFLIGHT_RUN_ID" \
  --repo-root "$EXECUTION_ROOT" \
  --codex-home "$ISOLATED_CODEX_HOME" \
  --require-terminal-status guarded-refresh-required \
  --json
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache "$PYTHON_BIN" \
  "$EXECUTION_ROOT/plugins/turbo-mode/tools/refresh_installed_turbo_mode.py" \
  --guarded-refresh \
  --isolated-rehearsal \
  --smoke standard \
  --run-id "$RUN_ID" \
  --repo-root "$EXECUTION_ROOT" \
  --codex-home "$ISOLATED_CODEX_HOME" \
  --source-implementation-commit "<full-source-implementation-commit>" \
  --source-implementation-tree "<source-implementation-tree>" \
  --require-terminal-status guarded-refresh-required \
  --json
test -f "$REHEARSAL_PROOF_PATH"
test -f "$REHEARSAL_PROOF_SHA256_PATH"
REHEARSAL_PROOF_SHA256="$(cut -d ' ' -f 1 "$REHEARSAL_PROOF_SHA256_PATH")"
ACTUAL_REHEARSAL_PROOF_SHA256="$(shasum -a 256 "$REHEARSAL_PROOF_PATH" | awk '{print $1}')"
test "$REHEARSAL_PROOF_SHA256" = "$ACTUAL_REHEARSAL_PROOF_SHA256"
```

Expected:

- seeding creates the minimal isolated config/cache/local-only state and records a local-only seed manifest;
- seed manifest binds to the exact Plan 05 six-path drift set, source manifest, pre-refresh cache manifest, and post-seed dry-run manifest;
- the isolated dry-run exits `0` with `terminal_plan_status = "guarded-refresh-required"` before rehearsal starts;
- the isolated dry-run proves app-server authority for `$ISOLATED_CODEX_HOME` and does not resolve app-server config/cache/plugin authority under `/Users/jp/.codex`;
- command exits `0`;
- terminal status is `MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED`;
- app-server authority proof records requested home `$ISOLATED_CODEX_HOME`;
- app-server pre-install target authority proof records the install destination cache root under `$ISOLATED_CODEX_HOME` before any `plugin/install` request;
- app-server authority proof records no config, cache, plugin, hook, local-only, or installed path under `/Users/jp/.codex`; same-child install evidence may record a hook-disabled zero-hook response, while fresh-child evidence after config restore must record the isolated Ticket hook path;
- Handoff and Ticket `plugin/install` request and response schema assertions pass;
- config toggle and restore, cache snapshot, marker lifecycle, rollback eligibility, source/cache equality, runtime inventory, smoke, and process gates all ran against the isolated home;
- no repo-local certified summary is published;
- local-only rehearsal evidence records the exact source implementation commit/tree, seed manifest, isolated dry-run proof, app-server authority proof, no-real-home proof, smoke proof, and final non-certified status;
- local-only rehearsal evidence records the app-server pre-install target authority proof digest used before install;
- local-only rehearsal evidence records rehearsal execution head/tree, rehearsal tool SHA256, and source-to-rehearsal execution delta status/proof;
- `rehearsal-proof.json` and its SHA256 companion exist, validate against current disk contents, and are ready to be supplied to the live run through `--rehearsal-proof` and `--rehearsal-proof-sha256`.

If the current app-server cannot be explicitly bound to `$ISOLATED_CODEX_HOME`, record that as a rehearsal blocker and do not proceed to Task 9.

- [ ] **Step 7: Commit pre-live plan evidence**

Add a `## Pre-Live Verification Evidence` section to this plan with:

- `source_implementation_commit` and `source_implementation_tree` for the final implementation commit before this docs evidence commit;
- the command used to compute `source_implementation_tree`, for example `git rev-parse "$SOURCE_IMPLEMENTATION_COMMIT^{tree}"`;
- a note that `execution_head` and `execution_tree` are computed by the live CLI at launch and are not recorded inside this self-committing section;
- the expected source-to-execution ancestry and allowed-delta policy if a docs evidence commit exists between source implementation and live execution;
- Python version;
- test commands and pass/fail status;
- unmocked Task 1A read-only app-server home-binding discovery artifact path and SHA256;
- unmocked Task 1A pre-install target authority artifact path and SHA256;
- unmocked Task 1A isolated app-server install-authority spike artifact path and SHA256;
- non-mutating run id;
- terminal plan status;
- residue result;
- isolated rehearsal run id;
- isolated rehearsal terminal status;
- isolated rehearsal proof path;
- isolated rehearsal proof SHA256;
- isolated rehearsal execution head/tree;
- isolated rehearsal tool SHA256;
- source-to-rehearsal execution delta status and proof SHA256;
- app-server home-authority proof result;
- pre-snapshot app-server launch authority proof field name expected in the live marker: `pre_snapshot_app_server_launch_authority_sha256`;
- pre-install app-server target authority proof field name expected in the live marker: `pre_install_app_server_target_authority_sha256`;
- seed manifest SHA256;
- seed expected drift path-set SHA256, source manifest SHA256, pre-refresh cache manifest SHA256, and post-seed dry-run manifest SHA256;
- no-real-home authority proof SHA256;
- explicit statement that no real `/Users/jp/.codex` config/cache/plugin authority was used by the rehearsal app-server.

Run:

```bash
git add docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md
git commit -m "docs: record guarded refresh pre-live gate"
```

## Task 9: Operator-Approved Live Guarded Refresh

**Files:**

- Create after successful live run: `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json`
- Create before live run: `/Users/jp/.codex/local-only/turbo-mode-refresh/approvals/<RUN_ID>/guarded-refresh-approval.json`
- Create before live run: `/Users/jp/.codex/local-only/turbo-mode-refresh/approvals/<RUN_ID>/guarded-refresh-runbook.sh`
- Modify after successful live run: `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md`

- [ ] **Step 1: Stop before mutation and get explicit operator approval**

This step is required even if every automated gate is green. Before active Codex sessions close, generate a filled approval/runbook artifact pair under `/Users/jp/.codex/local-only/turbo-mode-refresh/approvals/<RUN_ID>/` and record their SHA256s in the approval text. The runbook must be executable as-is from the external shell, must contain no `<placeholder>` tokens, and must fail a static preflight if any approved value is empty, placeholder-shaped, or inconsistent with the approval JSON. The approval text must identify:

- exact approved run id;
- expected local-only evidence root for that run id;
- expected run-state marker path and recovery handle for that run id;
- expected repo-local certified summary path and failed-summary path for that run id;
- filled approval JSON path and SHA256;
- filled runbook shell path and SHA256;
- current branch and `HEAD`;
- `source_implementation_commit/tree`;
- `execution_head/tree`;
- isolated rehearsal proof path and SHA256;
- the exact `APPROVED_SOURCE_IMPLEMENTATION_COMMIT` and `APPROVED_SOURCE_IMPLEMENTATION_TREE` values that the external shell must compare against immediately before launch;
- the exact `APPROVED_EXECUTION_HEAD` and `APPROVED_EXECUTION_TREE` values that the external shell must compare against immediately before launch;
- whether source and execution identities match, and the exact approved changed-path list in both cases. If identities match, the approved list must be an existing empty file;
- that active Codex Desktop and CLI sessions must be closed for the maintenance window and must not be reopened until the external-shell command exits;
- the handoff/save or resume packet path that lets the agentic worker recover context after active Codex sessions close;
- exact external-shell Python path and `platform.python_version()` version string;
- that the command mutates `/Users/jp/.codex/plugins/cache/turbo-mode/`;
- that the guarded flow may temporarily edit `/Users/jp/.codex/config.toml` to disable and restore hooks;
- rollback and recovery behavior.

- [ ] **Step 2: Run guarded-refresh from a generated external-shell runbook**

After the operator closes active Codex sessions and approves the maintenance window, run the generated `guarded-refresh-runbook.sh` from an external terminal, not from inside this Codex conversation. The shell block below is the required template for that generated artifact; the implementation must materialize it with concrete approved values before approval and must verify that no placeholder text remains:

```bash
set -euo pipefail
EXECUTION_ROOT="/Users/jp/Projects/active/codex-tool-dev"
APPROVED_RUN_ID="plan06-live-guarded-refresh-<YYYYMMDD-HHMMSS>"
EXPECTED_LOCAL_ONLY_RUN_ROOT="/Users/jp/.codex/local-only/turbo-mode-refresh/$APPROVED_RUN_ID"
EXPECTED_MARKER_PATH="/Users/jp/.codex/local-only/turbo-mode-refresh/run-state/$APPROVED_RUN_ID.json"
EXPECTED_SUMMARY_PATH="$EXECUTION_ROOT/plugins/turbo-mode/evidence/refresh/$APPROVED_RUN_ID.summary.json"
EXPECTED_FAILED_SUMMARY_PATH="$EXECUTION_ROOT/plugins/turbo-mode/evidence/refresh/$APPROVED_RUN_ID.summary.failed.json"
APPROVED_SOURCE_IMPLEMENTATION_COMMIT="<full-source-implementation-commit-approved-for-launch>"
APPROVED_SOURCE_IMPLEMENTATION_TREE="<source-implementation-tree-approved-for-launch>"
APPROVED_EXECUTION_HEAD="<full-execution-head-approved-for-launch>"
APPROVED_EXECUTION_TREE="<execution-tree-approved-for-launch>"
APPROVED_CHANGED_PATHS_FILE="<absolute-path-to-approved-source-to-execution-path-list-empty-if-identities-match>"
APPROVED_PYTHON_BIN="<absolute-path-to-approved-python3>"
APPROVED_PYTHON_VERSION="<approved-platform.python_version-output>"
APPROVED_REHEARSAL_PROOF="<absolute-path-to-isolated-rehearsal-proof.json>"
APPROVED_REHEARSAL_PROOF_SHA256="<sha256-of-isolated-rehearsal-proof.json>"
SOURCE_IMPLEMENTATION_COMMIT="$APPROVED_SOURCE_IMPLEMENTATION_COMMIT"
SOURCE_IMPLEMENTATION_TREE="$(git -C "$EXECUTION_ROOT" rev-parse "${SOURCE_IMPLEMENTATION_COMMIT}^{tree}")"
EXECUTION_HEAD="$(git -C "$EXECUTION_ROOT" rev-parse HEAD)"
EXECUTION_TREE="$(git -C "$EXECUTION_ROOT" rev-parse HEAD^{tree})"
if [ "$SOURCE_IMPLEMENTATION_COMMIT" != "$APPROVED_SOURCE_IMPLEMENTATION_COMMIT" ] || [ "$SOURCE_IMPLEMENTATION_TREE" != "$APPROVED_SOURCE_IMPLEMENTATION_TREE" ]; then
  echo "guarded refresh aborted: source implementation identity changed after approval" >&2
  echo "approved source commit/tree: $APPROVED_SOURCE_IMPLEMENTATION_COMMIT $APPROVED_SOURCE_IMPLEMENTATION_TREE" >&2
  echo "actual source commit/tree:   $SOURCE_IMPLEMENTATION_COMMIT $SOURCE_IMPLEMENTATION_TREE" >&2
  exit 1
fi
case "$APPROVED_RUN_ID" in
  plan06-live-guarded-refresh-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
  *)
    echo "guarded refresh aborted: approved run id is malformed" >&2
    echo "$APPROVED_RUN_ID" >&2
    exit 1
    ;;
esac
RUN_ID="$APPROVED_RUN_ID"
if [ -e "$EXPECTED_LOCAL_ONLY_RUN_ROOT" ] || [ -e "$EXPECTED_MARKER_PATH" ] || [ -e "$EXPECTED_SUMMARY_PATH" ] || [ -e "$EXPECTED_FAILED_SUMMARY_PATH" ]; then
  echo "guarded refresh aborted: approved run id already has evidence paths" >&2
  printf '%s\n' "$EXPECTED_LOCAL_ONLY_RUN_ROOT" "$EXPECTED_MARKER_PATH" "$EXPECTED_SUMMARY_PATH" "$EXPECTED_FAILED_SUMMARY_PATH" >&2
  exit 1
fi
if [ "$EXECUTION_HEAD" != "$APPROVED_EXECUTION_HEAD" ] || [ "$EXECUTION_TREE" != "$APPROVED_EXECUTION_TREE" ]; then
  echo "guarded refresh aborted: execution identity changed after approval" >&2
  echo "approved head/tree: $APPROVED_EXECUTION_HEAD $APPROVED_EXECUTION_TREE" >&2
  echo "actual head/tree:   $EXECUTION_HEAD $EXECUTION_TREE" >&2
  exit 1
fi
if ! git -C "$EXECUTION_ROOT" merge-base --is-ancestor "$SOURCE_IMPLEMENTATION_COMMIT" "$EXECUTION_HEAD"; then
  echo "guarded refresh aborted: source implementation commit is not an ancestor of execution head" >&2
  echo "source implementation commit: $SOURCE_IMPLEMENTATION_COMMIT" >&2
  echo "execution head:                $EXECUTION_HEAD" >&2
  exit 1
fi
if [ ! -f "$APPROVED_CHANGED_PATHS_FILE" ]; then
  echo "guarded refresh aborted: approved changed-paths file is missing" >&2
  echo "$APPROVED_CHANGED_PATHS_FILE" >&2
  exit 1
fi
if ! git -C "$EXECUTION_ROOT" diff --quiet; then
  echo "guarded refresh aborted: execution worktree has unstaged changes" >&2
  git -C "$EXECUTION_ROOT" status --short >&2
  exit 1
fi
if ! git -C "$EXECUTION_ROOT" diff --cached --quiet; then
  echo "guarded refresh aborted: execution worktree has staged changes" >&2
  git -C "$EXECUTION_ROOT" status --short >&2
  exit 1
fi
UNTRACKED_RELEVANT="$(
  git -C "$EXECUTION_ROOT" ls-files --others --exclude-standard -- \
    plugins/turbo-mode/tools \
    plugins/turbo-mode/handoff \
    plugins/turbo-mode/ticket \
    plugins/turbo-mode/evidence/refresh \
    .agents/plugins/marketplace.json
)"
if [ -n "$UNTRACKED_RELEVANT" ]; then
  echo "guarded refresh aborted: execution worktree has untracked relevant files" >&2
  printf '%s\n' "$UNTRACKED_RELEVANT" >&2
  exit 1
fi
ACTUAL_CHANGED_PATHS="$(git -C "$EXECUTION_ROOT" diff --name-only "$SOURCE_IMPLEMENTATION_COMMIT..$EXECUTION_HEAD" -- . | sort)"
APPROVED_CHANGED_PATHS="$(sort "$APPROVED_CHANGED_PATHS_FILE")"
if [ "$ACTUAL_CHANGED_PATHS" != "$APPROVED_CHANGED_PATHS" ]; then
  echo "guarded refresh aborted: source-to-execution changed paths differ from approved list" >&2
  echo "approved changed paths:" >&2
  printf '%s\n' "$APPROVED_CHANGED_PATHS" >&2
  echo "actual changed paths:" >&2
  printf '%s\n' "$ACTUAL_CHANGED_PATHS" >&2
  exit 1
fi
PYTHON_BIN="$(command -v python3)"
if [ "$PYTHON_BIN" != "$APPROVED_PYTHON_BIN" ]; then
  echo "guarded refresh aborted: python executable changed after approval" >&2
  echo "approved python: $APPROVED_PYTHON_BIN" >&2
  echo "actual python:   $PYTHON_BIN" >&2
  exit 1
fi
if [ ! -f "$APPROVED_REHEARSAL_PROOF" ]; then
  echo "guarded refresh aborted: rehearsal proof is missing" >&2
  echo "$APPROVED_REHEARSAL_PROOF" >&2
  exit 1
fi
ACTUAL_REHEARSAL_PROOF_SHA256="$(shasum -a 256 "$APPROVED_REHEARSAL_PROOF" | awk '{print $1}')"
if [ "$ACTUAL_REHEARSAL_PROOF_SHA256" != "$APPROVED_REHEARSAL_PROOF_SHA256" ]; then
  echo "guarded refresh aborted: rehearsal proof SHA256 changed after approval" >&2
  echo "approved rehearsal proof sha256: $APPROVED_REHEARSAL_PROOF_SHA256" >&2
  echo "actual rehearsal proof sha256:   $ACTUAL_REHEARSAL_PROOF_SHA256" >&2
  exit 1
fi
ACTUAL_PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import platform
print(platform.python_version())
PY
)"
if [ "$ACTUAL_PYTHON_VERSION" != "$APPROVED_PYTHON_VERSION" ]; then
  echo "guarded refresh aborted: python version changed after approval" >&2
  echo "approved python version: $APPROVED_PYTHON_VERSION" >&2
  echo "actual python version:   $ACTUAL_PYTHON_VERSION" >&2
  exit 1
fi
if ! "$PYTHON_BIN" - <<'PY'
import sys
print(sys.executable)
print(sys.version)
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  echo "python3 >= 3.11 is required for guarded refresh" >&2
  exit 1
fi
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache "$PYTHON_BIN" \
  "$EXECUTION_ROOT/plugins/turbo-mode/tools/refresh_installed_turbo_mode.py" \
  --guarded-refresh \
  --smoke standard \
  --run-id "$RUN_ID" \
  --repo-root "$EXECUTION_ROOT" \
  --codex-home /Users/jp/.codex \
  --source-implementation-commit "$SOURCE_IMPLEMENTATION_COMMIT" \
  --source-implementation-tree "$SOURCE_IMPLEMENTATION_TREE" \
  --rehearsal-proof "$APPROVED_REHEARSAL_PROOF" \
  --rehearsal-proof-sha256 "$APPROVED_REHEARSAL_PROOF_SHA256" \
  --record-summary \
  --require-terminal-status guarded-refresh-required \
  --json
```

Expected:

- command exits `0`;
- external shell aborts before mutation with a nonzero exit if the operator-approved run id is malformed, was generated after approval, or already has a local-only root, run-state marker path, certified summary path, or failed-summary path;
- external shell aborts before mutation with a nonzero exit if the approval JSON or generated runbook SHA256 differs from the operator-approved digest, if either file is missing, or if the generated runbook still contains placeholder-shaped tokens;
- external shell aborts before mutation with a nonzero exit if unstaged or staged changes exist in `execution_repo_root`;
- external shell aborts before mutation with a nonzero exit if untracked relevant files exist under the tools import root, plugin source, marketplace metadata, or refresh evidence paths;
- external shell aborts before mutation with a nonzero exit if `source_implementation_commit/tree` differs from the operator-approved identity;
- external shell aborts before mutation with a nonzero exit if `execution_head/tree` differs from the operator-approved identity;
- external shell aborts before mutation with a nonzero exit if `source_implementation_commit` is not an ancestor of `execution_head`;
- external shell aborts before mutation with a nonzero exit if the operator-approved changed-paths file is missing, including when source and execution identities match;
- external shell aborts before mutation with a nonzero exit if `source_implementation_commit..execution_head` changed paths differ from the operator-approved changed-path list;
- external shell aborts before mutation with a nonzero exit if the rehearsal proof file is missing or its SHA256 differs from the operator-approved digest;
- external-shell Python path and `platform.python_version()` exactly equal the operator-approved values, and version is still `>= 3.11`;
- live CLI records `source_implementation_commit = "$SOURCE_IMPLEMENTATION_COMMIT"` and computes `execution_head = "$EXECUTION_HEAD"`;
- live CLI verifies `SOURCE_IMPLEMENTATION_TREE` against the supplied source commit before mutation;
- live CLI validates the supplied rehearsal proof before lock acquisition, including source commit/tree, rehearsal execution head/tree, rehearsal tool SHA256, source-to-rehearsal delta status/proof, final non-certified status, app-server authority proof digest, seed manifest digest, no-real-home proof digest, smoke digest, requested isolated home outside `/Users/jp/.codex`, and absence of real-home config/cache/plugin/hook/local-only paths;
- live CLI copies the validated rehearsal proof, companion SHA256, and digest-referenced artifacts into `$EXPECTED_LOCAL_ONLY_RUN_ROOT/rehearsal-proof-capture/` before mutation and validates the capture manifest against the original proof;
- local-only evidence root exists with `0700`;
- raw local-only artifacts are `0600`;
- published commit-safe summary exists under `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json`;
- final status is `MUTATION_COMPLETE_CERTIFIED`;
- `exclusivity_status = "exclusive_window_observed_by_process_samples"`;
- post-refresh source/cache equality passes;
- final runtime inventory is collected from a fresh app-server process after config restore;
- standard smoke passes.

- [ ] **Step 3: If live mutation fails, do not continue as if refreshed**

If the command reports `MUTATION_FAILED_ROLLBACK_COMPLETE`, inspect the local-only summary and run a fresh non-mutating dry run. Record the failure evidence in this plan. Do not claim installed-refresh completion.

If the command reports `MUTATION_FAILED_ROLLBACK_FAILED` or `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED`, stop all implementation and preserve local-only evidence. Do not run another mutation command until the operator makes a manual recovery decision.

If the command reports `MUTATION_COMPLETE_EXCLUSIVITY_UNPROVEN`, treat the installed cache as possibly updated but not maintenance-window certified. Record that status explicitly and do not publish a green closeout. The operator must choose one of: run `--certify-retained-run <RUN_ID>` after reviewing whether exclusivity proof can be retained-certified, manually roll back from retained snapshots, or leave the refreshed cache in place with an explicit uncertified-state note.

If the command reports `MUTATION_COMPLETE_EVIDENCE_FAILED`, treat the installed cache as possibly updated and functionally refreshed, but not commit-safe certified. Preserve local-only evidence and do not rerun mutation. The next non-manual path is `--certify-retained-run <RUN_ID>` after validator/summary repair and source-to-certification review. If retained-run certification is rejected, the operator must choose manual rollback/adjudication or leave the refreshed cache in place with an explicit uncertified-state note.

If any repo-local summary file exists for an evidence-failed run, it must be named `<RUN_ID>.summary.failed.json`, not `<RUN_ID>.summary.json`. A green-looking `<RUN_ID>.summary.json` is allowed only after final replay validators pass.

- [ ] **Step 4: Recovery incident runbook**

Use this only if a run leaves a retained marker and reports recovery is required. Recovery is also a mutation path, so it must be run from an external shell during an exclusive maintenance window, not from inside this Codex conversation. Recovery approval must include the exact external-shell Python path and `platform.python_version()` version string:

```bash
set -euo pipefail
EXECUTION_ROOT="/Users/jp/Projects/active/codex-tool-dev"
RUN_ID="<run-id-that-left-a-marker>"
APPROVED_SOURCE_IMPLEMENTATION_COMMIT="<full-source-implementation-commit-approved-for-recovery>"
APPROVED_SOURCE_IMPLEMENTATION_TREE="<source-implementation-tree-approved-for-recovery>"
APPROVED_EXECUTION_HEAD="<full-marker-execution-head-approved-for-recovery>"
APPROVED_EXECUTION_TREE="<marker-execution-tree-approved-for-recovery>"
APPROVED_PYTHON_BIN="<absolute-path-to-approved-python3>"
APPROVED_PYTHON_VERSION="<approved-platform.python_version-output>"
SOURCE_IMPLEMENTATION_TREE="$(git -C "$EXECUTION_ROOT" rev-parse "${APPROVED_SOURCE_IMPLEMENTATION_COMMIT}^{tree}")"
EXECUTION_HEAD="$(git -C "$EXECUTION_ROOT" rev-parse HEAD)"
EXECUTION_TREE="$(git -C "$EXECUTION_ROOT" rev-parse HEAD^{tree})"
if [ "$SOURCE_IMPLEMENTATION_TREE" != "$APPROVED_SOURCE_IMPLEMENTATION_TREE" ]; then
  echo "recovery aborted: source implementation tree changed after approval" >&2
  exit 1
fi
if [ "$EXECUTION_HEAD" != "$APPROVED_EXECUTION_HEAD" ] || [ "$EXECUTION_TREE" != "$APPROVED_EXECUTION_TREE" ]; then
  echo "recovery aborted: execution identity changed after approval" >&2
  exit 1
fi
if ! git -C "$EXECUTION_ROOT" diff --quiet || ! git -C "$EXECUTION_ROOT" diff --cached --quiet; then
  echo "recovery aborted: execution worktree has tracked dirty state" >&2
  git -C "$EXECUTION_ROOT" status --short >&2
  exit 1
fi
UNTRACKED_RELEVANT="$(
  git -C "$EXECUTION_ROOT" ls-files --others --exclude-standard -- \
    plugins/turbo-mode/tools \
    plugins/turbo-mode/handoff \
    plugins/turbo-mode/ticket \
    plugins/turbo-mode/evidence/refresh \
    .agents/plugins/marketplace.json
)"
if [ -n "$UNTRACKED_RELEVANT" ]; then
  echo "recovery aborted: execution worktree has untracked relevant files" >&2
  printf '%s\n' "$UNTRACKED_RELEVANT" >&2
  exit 1
fi
PYTHON_BIN="$(command -v python3)"
if [ "$PYTHON_BIN" != "$APPROVED_PYTHON_BIN" ]; then
  echo "recovery aborted: python executable changed after approval" >&2
  echo "approved python: $APPROVED_PYTHON_BIN" >&2
  echo "actual python:   $PYTHON_BIN" >&2
  exit 1
fi
ACTUAL_PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import platform
print(platform.python_version())
PY
)"
if [ "$ACTUAL_PYTHON_VERSION" != "$APPROVED_PYTHON_VERSION" ]; then
  echo "recovery aborted: python version changed after approval" >&2
  echo "approved python version: $APPROVED_PYTHON_VERSION" >&2
  echo "actual python version:   $ACTUAL_PYTHON_VERSION" >&2
  exit 1
fi
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache "$PYTHON_BIN" \
  "$EXECUTION_ROOT/plugins/turbo-mode/tools/refresh_installed_turbo_mode.py" \
  --recover "$RUN_ID" \
  --repo-root "$EXECUTION_ROOT" \
  --codex-home /Users/jp/.codex \
  --source-implementation-commit "$APPROVED_SOURCE_IMPLEMENTATION_COMMIT" \
  --source-implementation-tree "$APPROVED_SOURCE_IMPLEMENTATION_TREE" \
  --json
```

Expected:

- command exits `0` only if recovery completes;
- recovery external shell aborts before executing recovery code if the Python path or `platform.python_version()` differs from the operator-approved values;
- recovery self-blocks if active Codex Desktop, Codex CLI, hook, runtime, uncertain high-risk, or unrelated app-server processes are observed before restore;
- recovery external shell aborts before executing recovery code if untracked relevant files exist under the tools import root, plugin source, marketplace metadata, or refresh evidence paths;
- recovery CLI aborts before config restore, cache restore, or app-server inventory if current execution head/tree or tool SHA256 differs from the marker `execution_head`, `execution_tree`, or `tool_sha256`;
- recovery CLI aborts before config restore, cache restore, or app-server inventory if the supplied source implementation commit/tree differs from the marker source implementation commit/tree;
- recovery preserves original owner evidence, validates owner PID/start identity, and records recovery owner evidence;
- recovery applies phase-aware config SHA rules before restore;
- recovery starts a fresh app-server inventory after restore;
- recovery runs `post-recovery` process gate;
- final status is local-only `RECOVERY_COMPLETE`; no commit-safe recovery summary is produced in Plan 06.

If recovery returns `RECOVERY_FAILED_MANUAL_DECISION_REQUIRED`, preserve local-only evidence and do not run another mutation or recovery command until the operator decides the manual recovery path.

- [ ] **Step 5: Validate published summary with split-root source/runtime replay**

Do not assume the post-live summary file exists in a checkout of `source_implementation_commit`. The replay uses a detached source-code worktree for validator code and absolute paths back to the execution worktree evidence. Runtime-bound recomputation must stay anchored to the execution checkout:

```bash
set -euo pipefail
RUN_ID="<actual-run-id>"
EXECUTION_ROOT="/Users/jp/Projects/active/codex-tool-dev"
SOURCE_IMPLEMENTATION_COMMIT="<source-implementation-commit-recorded-in-summary>"
SOURCE_REPLAY_ROOT="/private/tmp/codex-tool-dev-plan06-source-${RUN_ID}"
SUMMARY="${EXECUTION_ROOT}/plugins/turbo-mode/evidence/refresh/${RUN_ID}.summary.json"
LOCAL_ONLY_ROOT="/Users/jp/.codex/local-only/turbo-mode-refresh/${RUN_ID}"
CANDIDATE_SUMMARY="${LOCAL_ONLY_ROOT}/commit-safe.candidate.summary.json"
REPLAY_ATTEMPT_ID="$(date -u +%Y%m%d-%H%M%S)"
FINAL_SCAN_SUMMARY="${LOCAL_ONLY_ROOT}/redaction-final-scan.${REPLAY_ATTEMPT_ID}.summary.json"
FAILED_SUMMARY="${EXECUTION_ROOT}/plugins/turbo-mode/evidence/refresh/${RUN_ID}.summary.failed.json"
REPLAY_FAILURE_STATUS="${LOCAL_ONLY_ROOT}/post-live-replay-failed.${REPLAY_ATTEMPT_ID}.status.json"
if [ -e "$SOURCE_REPLAY_ROOT" ]; then
  echo "source replay root already exists; choose a fresh RUN_ID or trash the stale root after inspection: $SOURCE_REPLAY_ROOT" >&2
  exit 1
fi
git -C "$EXECUTION_ROOT" worktree add --detach "$SOURCE_REPLAY_ROOT" "$SOURCE_IMPLEMENTATION_COMMIT"
set +e
PYTHONDONTWRITEBYTECODE=1 python3 "$SOURCE_REPLAY_ROOT/plugins/turbo-mode/tools/refresh_validate_run_metadata.py" \
  --mode final \
  --run-id "$RUN_ID" \
  --source-code-root "$SOURCE_REPLAY_ROOT" \
  --execution-repo-root "$EXECUTION_ROOT" \
  --local-only-root "$LOCAL_ONLY_ROOT" \
  --summary "$SUMMARY" \
  --published-summary-path "$SUMMARY" \
  --candidate-summary "$CANDIDATE_SUMMARY" \
  --existing-validation-summary "$LOCAL_ONLY_ROOT/metadata-validation.summary.json"
METADATA_REPLAY_STATUS="$?"
PYTHONDONTWRITEBYTECODE=1 python3 "$SOURCE_REPLAY_ROOT/plugins/turbo-mode/tools/refresh_validate_redaction.py" \
  --mode final \
  --run-id "$RUN_ID" \
  --source-code-root "$SOURCE_REPLAY_ROOT" \
  --execution-repo-root "$EXECUTION_ROOT" \
  --scope commit-safe-summary \
  --source plan-06-cli \
  --summary "$SUMMARY" \
  --local-only-root "$LOCAL_ONLY_ROOT" \
  --published-summary-path "$SUMMARY" \
  --candidate-summary "$CANDIDATE_SUMMARY" \
  --final-scan-output "$FINAL_SCAN_SUMMARY" \
  --existing-validation-summary "$LOCAL_ONLY_ROOT/redaction.summary.json"
REDACTION_REPLAY_STATUS="$?"
set -e
if [ "$METADATA_REPLAY_STATUS" -ne 0 ] || [ "$REDACTION_REPLAY_STATUS" -ne 0 ]; then
  if [ -e "$FAILED_SUMMARY" ]; then
    echo "post-live replay failed, but failed-summary path already exists; refusing to overwrite forensic evidence: $FAILED_SUMMARY" >&2
    exit 1
  fi
  python3 - "$SUMMARY" "$FAILED_SUMMARY" <<'PY'
import ctypes
import os
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
if target.exists():
    raise SystemExit(f"failed-summary path already exists: {target}")
if not source.exists():
    raise SystemExit(f"summary path missing before demotion: {source}")
if source.parent != target.parent:
    raise SystemExit(f"summary demotion requires same directory. Got: {source!s} -> {target!s}")

# macOS renamex_np(..., RENAME_EXCL) gives atomic no-overwrite rename semantics.
# Do not fall back to link+unlink; interruption between those calls can leave
# a certified-looking summary beside the failed summary.
libc = ctypes.CDLL(None, use_errno=True)
renamex_np = getattr(libc, "renamex_np", None)
if renamex_np is None:
    raise SystemExit("renamex_np unavailable; refusing non-crash-safe summary demotion")
RENAME_EXCL = 0x00000004
result = renamex_np(bytes(source), bytes(target), RENAME_EXCL)
if result != 0:
    err = ctypes.get_errno()
    raise SystemExit(f"summary demotion failed: errno={err}. Got: {source!s} -> {target!s}")
if source.exists() or not target.exists():
    raise SystemExit(f"summary demotion final path validation failed. Got: source_exists={source.exists()} target_exists={target.exists()}")
dir_fd = os.open(str(target.parent), os.O_RDONLY)
try:
    os.fsync(dir_fd)
finally:
    os.close(dir_fd)
PY
  python3 - "$REPLAY_FAILURE_STATUS" "$RUN_ID" "$SUMMARY" "$FAILED_SUMMARY" "$SOURCE_REPLAY_ROOT" "$METADATA_REPLAY_STATUS" "$REDACTION_REPLAY_STATUS" <<'PY'
import json
import os
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
payload = {
    "schema_version": "turbo-mode-refresh-post-live-replay-failed-plan-06",
    "run_id": sys.argv[2],
    "final_status": "MUTATION_COMPLETE_EVIDENCE_FAILED",
    "demoted_from": sys.argv[3],
    "demoted_to": sys.argv[4],
    "retained_source_replay_root": sys.argv[5],
    "metadata_replay_exit_status": int(sys.argv[6]),
    "redaction_replay_exit_status": int(sys.argv[7]),
}
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
fd = os.open(status_path, flags, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
  echo "post-live replay failed; summary demoted to $FAILED_SUMMARY" >&2
  echo "local-only replay failure status written to $REPLAY_FAILURE_STATUS" >&2
  echo "source replay root retained for inspection: $SOURCE_REPLAY_ROOT" >&2
  exit 1
fi
command -v trash >/dev/null || { echo "trash command is required; stop instead of using rm" >&2; exit 1; }
trash "$SOURCE_REPLAY_ROOT"
git -C "$EXECUTION_ROOT" worktree prune
```

Expected:

- the detached source replay worktree is exactly `source_implementation_commit`;
- the summary path is absolute and points back to the execution worktree artifact;
- `source_code_root` is used for validator/tool/source digests and source implementation identity;
- `execution_repo_root` is used for runtime config projection, app-server inventory recomputation, execution identity, dirty-state checks, and published evidence paths;
- both validators pass;
- validation does not depend on the summary being present in the source replay worktree;
- replay final scan output is attempt-specific so reruns do not fail on an existing `redaction-final-scan.summary.json` file;
- if either validator fails, preserve `$SOURCE_REPLAY_ROOT` for inspection, demote `$SUMMARY` to `$FAILED_SUMMARY` with crash-safe non-overwriting rename semantics before closeout, validate that `$SUMMARY` no longer exists and `$FAILED_SUMMARY` exists, write a `MUTATION_COMPLETE_EVIDENCE_FAILED` local-only replay failure status, and record both retained/demoted paths in the failure notes;
- if both validators pass, `trash` exists, the temporary source replay worktree is trashed, and `git worktree prune` removes stale worktree metadata. If `trash` is missing, stop instead of using `rm`.

- [ ] **Step 6: Record completion evidence and commit**

Add a `## Completion Evidence` section to this plan with:

- implementation source commit hash and tree hash;
- execution head and tree hash;
- source-to-execution delta status;
- live run id;
- local-only evidence root;
- commit-safe summary path;
- final status;
- exclusivity status;
- post-refresh runtime inventory status;
- smoke tier and status;
- rollback or recovery status;
- exact validator commands and results.

Run:

```bash
git add plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json docs/superpowers/plans/2026-05-06-turbo-mode-refresh-06-guarded-refresh-mutation-lane.md
git commit -m "docs: record guarded refresh mutation evidence"
```

## Verification Matrix

Required before live mutation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py
git diff --check
find plugins/turbo-mode -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .venv \) -print
find plugins/turbo-mode -type f \( -name '*.pyc' -o -name .DS_Store \) -print
```

Also required before live mutation:

- successful isolated full-dress `--guarded-refresh --isolated-rehearsal` from the same `source_implementation_commit/tree`;
- validated `rehearsal-proof.json` and SHA256 from that isolated rehearsal;
- live command inputs include `--rehearsal-proof` and `--rehearsal-proof-sha256`;
- live mutation implementation captures the validated rehearsal-proof bundle into the live local-only evidence root before mutation;
- unmocked Task 1A authority artifacts and isolated rehearsal proof artifacts are preserved at approved durable local-only paths until live mutation and post-live replay complete;
- filled approval JSON and generated external-shell runbook exist with recorded SHA256s, contain no placeholders, and match the exact values in the operator approval packet before active Codex sessions close;
- retained-run certification implementation and tests pass before any live mutation approval;
- recorded app-server home-authority proof for the isolated rehearsal;
- no isolated rehearsal response resolving config, cache, plugin, hook, local-only, or installed state under `/Users/jp/.codex`;
- recorded app-server launch/read-authority proof for the intended live `/Users/jp/.codex` run before snapshots;
- no live real-home `plugin/install` request before `snapshot-written` marker evidence is durable.

Required after live mutation:

```bash
RUN_ID="<actual-run-id>"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id "plan06-postlive-recheck-${RUN_ID}" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected after successful certified mutation:

- `terminal_plan_status = "no-drift"`;
- `runtime_config.state = "aligned"`;
- `app_server_inventory_status = "collected"`;
- `app_server_inventory.state = "aligned"`;
- `residue_issues = []`;
- source/cache diffs are empty.

## Stop Conditions

Stop before implementation if:

- the current branch is not `main` or a fresh branch from current `main`;
- tracked source, test, config, marketplace, evidence, or installed-cache files are dirty before Task 1A;
- non-mutating re-anchor does not return the expected Plan 05 guarded drift after generated residue is explicitly cleaned;
- active handoff mechanics are mistaken for tracked Plan 06 project work;
- the active instruction contract for `docs/handoffs/` conflicts with `.gitignore`, tracked handoff state, or plan text, and no reviewed waiver or repo policy update resolves that conflict;
- `.gitignore` handoff-policy edits are dirty and would be committed with the Plan 06 authority artifact.

Stop before live mutation if:

- generated residue exists in source or installed cache;
- runtime inventory is not collected and aligned;
- `features.plugin_hooks` is `false`, `absent-unproven`, `absent-disabled`, `malformed`, or `externally-changed`;
- process gate finds blockers;
- a run-state marker exists and recovery has not completed;
- source implementation changed after the `source_implementation_commit` recorded in pre-live evidence;
- `source_implementation_commit` is not an ancestor of `execution_head`;
- `execution_head` differs from `source_implementation_commit` without a docs/evidence-only allowed-delta proof;
- the unmocked Task 1A read-only home-binding discovery artifact is missing or digest-mismatched;
- the Task 1A pre-install target authority artifact is missing, digest-mismatched, or does not prove the isolated install destination before writes;
- the unmocked Task 1A install spike artifact is missing, digest-mismatched, records sparse `plugin/install` success without same-child and fresh-child post-install app-server corroboration, or lacks local installed-cache manifest proof for the requested isolated home;
- the approved run id, expected local-only evidence root, expected run-state marker path, expected certified summary path, or expected failed-summary path is absent from the approval packet;
- the approved run id is malformed or any expected path for that run id already exists;
- the external-shell Python path or exact `platform.python_version()` value differs from the approval packet;
- retained-run certification is not implemented, tested, and available as a non-mutating recovery path for evidence-failed completed mutations;
- the live rehearsal-proof capture contract is not implemented or does not copy digest-referenced rehearsal artifacts into the live local-only evidence root before mutation;
- the pre-snapshot app-server launch authority proof is not persisted in the marker before `snapshot-written`;
- the operator has not explicitly approved the external-shell maintenance window;
- the operator cannot keep Codex Desktop, Codex CLI, and installed Ticket hook/runtime commands closed until the external-shell command exits.

Stop after live mutation if:

- rollback fails;
- recovery fails;
- post-mutation process census is unproven;
- final inventory or standard smoke fails;
- commit-safe validators fail and retained-run certification has not either certified the retained run or produced an explicit operator decision to roll back, leave uncertified, or manually adjudicate;
- post-live non-mutating recheck is not `no-drift`.

## Self-Review Checklist

- This plan preserves the distinction between Plan 05 guarded coverage and installed-refresh completion.
- This plan keeps `--guarded-refresh` external-shell-only and does not introduce routine mutation.
- This plan uses app-server `plugin/install` as the install mechanism.
- This plan allows direct source-to-cache file copy only for rollback/recovery from a captured snapshot, plus the explicitly non-certifying isolated-home seed carve-out.
- This plan treats sampled process gates as evidence, not machine-wide exclusion.
- This plan keeps source implementation identity separate from execution/evidence identity.
- This plan requires source implementation commit ancestry before accepting source-to-execution changed-path allowlists.
- This plan treats `docs/handoffs/` policy as an instruction-authority issue, not as something `.gitignore` can decide by itself, and blocks implementation until any conflict is resolved by a reviewed waiver or repo policy update.
- This plan derives lock, marker, recovery, evidence, rehearsal, and smoke roots from `codex_home`.
- This plan proves read-only app-server home binding and pre-install target authority before any unmocked `plugin/install`, then proves isolated app-server install mutation authority in its own Task 1A commit boundary before process gate, lock, or recovery scaffolding.
- This plan persists pre-snapshot app-server launch authority in the run-state marker before snapshots, hook disable, live install, smoke, or recovery scaffolding.
- This plan requires the live run id, marker path, evidence root, summary path, failed-summary path, Python path, and Python version to be approved before launch.
- This plan binds isolated seed and rehearsal proof to the exact inherited Plan 05 six-path drift set.
- This plan captures the validated rehearsal-proof bundle into the live local-only evidence root before mutation so later replay does not depend on `/private/tmp`.
- This plan defines non-mutating retained-run certification for evidence-failed or exclusivity-unproven completed mutations.
- This plan implements or fails closed on every governing `features.plugin_hooks` state.
- This plan prevents repo-local certified summaries from surviving failed final validation.
- This plan records the current generated residue blocker instead of normalizing it away.
- This plan has explicit stop conditions before destructive or hard-to-reverse operations.
- This plan does not require committing local-only raw evidence.
- This plan does not edit `/Users/jp/.codex/config.toml` except inside the future guarded-refresh live mutation after explicit approval.
