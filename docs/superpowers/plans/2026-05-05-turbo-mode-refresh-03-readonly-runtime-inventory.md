# Turbo Mode Refresh 03 Read-Only Runtime Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add optional read-only app-server/runtime inventory to the Turbo Mode refresh CLI.

**Architecture:** Plan 03 extends the Plan 02 non-mutating CLI with an `--inventory-check` flag. The planner still owns source/cache/config assessment; a new app-server inventory module owns JSON-RPC request construction, runtime identity capture, response parsing, and fail-closed schema validation. Evidence remains local-only and stores raw transcripts outside the summary payload.

**Tech Stack:** Python 3.11 project tests, direct `python3` script compatibility, stdlib `subprocess` / `json` / `hashlib`, existing `refresh` package modules, `pytest`, `ruff`.

---

## Scope

Plan 03 implements:

- `python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --dry-run --inventory-check`
- `python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --plan-refresh --inventory-check`
- read-only app-server requests: `initialize`, `initialized`, `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`
- runtime identity capture: one resolved `codex` executable path used for both app-server launch and `codex --version` / SHA256 capture, the full `initialize.result` object, optional `initialize.result.serverInfo` and `initialize.result.capabilities` fields when present, parser version, and accepted response schema version
- local-only raw transcript evidence under `<codex_home>/local-only/turbo-mode-refresh/<RUN_ID>/`, including partial transcripts for requested inventory attempts that fail after app-server exchange begins
- planner integration where aligned local config plus aligned runtime inventory may set `runtime_config_state=aligned`
- explicit app-server inventory states: `not-requested`, `requested-blocked`, `requested-failed`, and `collected`

Plan 03 does not implement:

- `plugin/install`
- executable `--refresh`
- executable `--guarded-refresh`
- installed-cache mutation
- global config mutation
- process gates, locks, rollback, recovery, or commit-safe evidence

## File Structure

- Create: `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
  - Build pinned read-only JSON-RPC requests.
  - Resolve `codex` once, then run `<resolved-codex> app-server --listen stdio://`.
  - Capture runtime identity.
  - Validate app-server responses fail-closed.
  - Return summary fields plus raw transcript for local-only evidence writing.

- Modify: `plugins/turbo-mode/tools/refresh/planner.py`
  - Accept `inventory_check: bool`.
  - Call the app-server inventory collector only when requested.
  - Preserve Plan 02 behavior when inventory is not requested.
  - Promote aligned local config to `RuntimeConfigState.ALIGNED` only when inventory also aligns.

- Modify: `plugins/turbo-mode/tools/refresh/evidence.py`
  - Bump schema to `turbo-mode-refresh-plan-03`.
  - Write raw app-server transcript as a sibling local-only JSON artifact.
  - Keep raw transcript out of the summary payload.
  - Persist `app_server_inventory_status` and `app_server_inventory_failure_reason` separately from raw transcript presence.
  - Update omission reasons so app-server inventory is one of `not-requested`, `requested-blocked`, `requested-failed`, or `collected`.

- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
  - Add `--inventory-check`.
  - Pass inventory choice to the planner.
  - Include inventory status in human-readable output.

- Test: `plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_evidence.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

## Pinned App-Server Contract

Plan 03 pins this read-only request sequence:

1. `initialize`, request id `0`, with `clientInfo.name = "turbo-mode-installed-refresh"`, `clientInfo.version = "0"`, and `capabilities.experimentalApi = true`.
2. `initialized` notification with no request id and no response required.
3. `plugin/read`, request id `1`, with `marketplacePath = <repo>/.agents/plugins/marketplace.json`, `pluginName = "handoff"`, and `remoteMarketplaceName = null`.
4. `plugin/read`, request id `2`, with the same marketplace params and `pluginName = "ticket"`.
5. `plugin/list`, request id `3`, with the same marketplace params.
6. `skills/list`, request id `4`, with `cwds` containing a temporary disposable directory.
7. `hooks/list`, request id `5`, with `cwds` containing the same temporary disposable directory.

Plan 03 accepts only responses with the matching integer ids above. It treats a response `error`, missing response id, duplicate response id, unexpected response id, timeout, closed stdout, malformed JSON response stream, or missing required inventory field as fail-closed inventory failure. Notification messages without ids are tolerated only as app-server notifications and are not counted as inventory proof. The app-server process timeout is 30 seconds per request, and the child process is terminated in success, error, and timeout paths.

The response parser accepts:

- full `initialize.result` as runtime identity evidence, plus `initialize.result.serverInfo` and `initialize.result.capabilities` as optional convenience fields when present. In the current `codex-cli 0.128.0` live evidence, `serverInfo` and `capabilities` are absent while `codexHome`, platform fields, and `userAgent` are present in `initialize.result`.
- `plugin/read` responses only when the plugin source path structurally appears at `result.source.path` or `result.plugin.summary.source.path`, exactly matches the expected repo source path for the requested plugin, and no `/plugin-dev/` path appears.
- `plugin/list` responses only when plugin ids or structural plugin records under `result.plugins` or the matching `result.marketplaces[].plugins[]` entry contain both `handoff@turbo-mode` and `ticket@turbo-mode`, and no `/plugin-dev/` path appears.
- `skills/list` responses only when structural skill records under `result.skills` or `result.data[].skills` contain every expected Handoff and Ticket skill name with a `path` or `sourcePath` under the expected installed-cache skill root, and no `/plugin-dev/` path appears.
- `hooks/list` responses only when structural hook records under `result.hooks` or `result.data[].hooks` contain exactly one Ticket hook, and that hook is a Bash `preToolUse` hook with command `python3 <codex_home>/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py`, source path `<codex_home>/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json`, and no Handoff hook entries.

Additional unrelated hooks are tolerated only when they are not Handoff hooks and are not additional Ticket hooks. The executable conflict rule is: Handoff hooks are forbidden, and Ticket must expose exactly one hook total, the expected Bash `preToolUse` guard. Hooks from unrelated plugins are ignored and are not summarized as proof.

## Task 1: Add The Read-Only Inventory Parser

- [x] Write tests for request construction and successful response parsing.
- [x] Implement `build_readonly_inventory_requests()`.
- [x] Implement `validate_readonly_inventory_contract()` with strict required responses.
- [x] Prove missing Ticket hook, unexpected Handoff hook presence, plugin-dev paths, wrong Ticket hook command/source path, and missing skills fail closed.
- [x] Prove malformed response streams, duplicate ids, unexpected ids, and expected strings in structurally wrong fields fail closed.
- [x] Prove top-level structural `result.plugins[]` records are accepted for `plugin/list`.
- [x] Prove additional Ticket hooks fail closed under the exactly-one-Ticket-hook rule.

## Task 2: Add Runtime Identity Capture And Roundtrip Execution

- [x] Write tests for identity hashing and unavailable hash reasons.
- [x] Prove `collect_codex_runtime_identity()` hash success, missing executable, `codex --version` failure, and hash `OSError` handling directly.
- [x] Prove one resolved `codex` executable path is used for both app-server launch and identity capture.
- [x] Implement `collect_codex_runtime_identity()`.
- [x] Implement `app_server_roundtrip()` without import coupling to migration tooling.
- [x] Ensure app-server process termination happens on success, error, and timeout.

## Task 3: Integrate Inventory With Planner

- [x] Write a test proving no-drift plus aligned config remains `filesystem-no-drift` without `--inventory-check`.
- [x] Write a test proving no-drift plus aligned config plus aligned inventory becomes `no-drift`.
- [x] Write a test proving failed inventory blocks preflight, persists `requested-failed`, and does not erase manifest facts.
- [x] Write a test proving requested-failed inventory preserves partial app-server transcripts when the collector has one.
- [x] Write a test proving requested inventory blocked by config preflight persists `requested-blocked`.
- [x] Implement `inventory_check` on `plan_refresh()`.

## Task 4: Extend CLI And Evidence

- [x] Write CLI tests for `--inventory-check` with a fake planner result or injected inventory collector.
- [x] Write evidence tests proving summary omits raw transcript and writes transcript as `0600`.
- [x] Write evidence tests proving requested-but-failed inventory is not reported as `not-requested`.
- [x] Write evidence tests proving requested-failed inventory writes a partial transcript artifact when present.
- [x] Add `--inventory-check` to the CLI.
- [x] Bump evidence schema and write raw transcript local-only when present.

## Task 5: Verify

- [x] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

- [x] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py
```

- [x] Run the generated-residue scan over Handoff, Ticket, and refresh tool roots. It must print nothing.

## Completion Evidence

Current Plan 03 proof lane:

- Intended contract: this document requires structural response validation, duplicate-id rejection, unexpected-id rejection, malformed-stream rejection, runtime executable identity binding to one resolved path, explicit current-state reconciliation before merge readiness, and ignored-handoff visibility before closeout.
- Branch: `feature/turbo-mode-refresh-plan-03-runtime-inventory`.
- Current committed Plan 03 artifact boundary at the 2026-05-05 scrutiny checkpoint: `64cfecba45d12a7988f6c8a0ad2bc9ae3a4c98bc`, tree `5a618dc04e7982b64146d179e110b43c24c558ee`, committed as `64cfecb docs: record identity binding boundary`.
- Executable proof boundary: `33a588b192f0deefb07f925e7a0809b1ea0ac4c5`, tree `f0be53663e75c436cf7815e7ca0217658ae34ae7`, committed as `33a588b fix: bind inventory identity executable`.
- Runtime identity proof: one resolved `codex` path is used for app-server launch and identity capture, and tests prove that shared-path binding. This is path-bound provenance, not immutable-binary provenance; Plan 03 accepts the local race where the bytes at that path could change between launch and post-roundtrip version/hash capture.
- Focused refresh test evidence at the current checkpoint: `203 passed` from `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q`.
- Lint evidence at the current checkpoint: `All checks passed!` from `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`.
- Residue evidence at the current checkpoint: the generated-residue scan over Handoff, Ticket, and refresh roots printed nothing.
- Current live read-only inventory smoke evidence path: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan03-scrutinize-live-20260505/dry-run.summary.json`.
- Current live smoke result: `app_server_inventory_status = collected`, runtime inventory aligned, `terminal_plan_status = coverage-gap-blocked`.
- Current live smoke summary SHA256: `a9c09eb5cbf2b3a2ee074d0b6ab09c46527b1a8aa322805199dda92133fc0146`.
- Current live smoke transcript SHA256: `932c49c6905912a53622c3178173446568dc3f5def73a59a3b20035b781a6e3f`.

Superseded historical proof lane:

- Implementation boundary: Plan 03 feature work was committed as `e4a4805 feat: add refresh runtime inventory check`.
- Separate policy boundary: active handoff summary ignore policy was committed separately as `18b90ff chore: ignore active handoff summaries`.
- Parser-contract repair boundary: structural parser hardening was committed as `03b04e4 fix: harden refresh runtime inventory parser`.
- Closeout-ledger repair boundary: runtime identity tests and evidence ledger repair were committed as `4d26c46 fix: close refresh inventory evidence gaps`.
- Runtime identity timeout repair boundary: `d3cfbd53c6a93faba9ecd9ffc1dbbab487593f5b`, tree `f15c9dd7af6646912b486d7f06d549ec982edee0`, committed as `d3cfbd5 fix: handle codex version timeouts`.
- Failed-transcript preservation boundary: `bfefeef5fbbcc095f8c0c23c16800a80d7c64a57`, tree `57bc165238b812993e8be600df65458ef35b01c1`, committed as `bfefeef fix: preserve failed inventory transcripts`.
- Prior docs-only artifact boundaries: `bc2aa838cdbcdb78e9d27209f9804df894798bef` / tree `287ea481da3b6c85243dfb221a11e4987791b5f5` and `06cc849ac296bf641a52dd3c8070657a1aa3fea6` / tree `d0386abe114b6316b9bff1ff3b5516dd0583cb88`.
- Earlier proof entries with `186`, `192`, `196`, `197`, or `202` focused test passes, earlier lint passes, earlier clean residue scans, and earlier local-only smoke hashes are historical repair evidence only. They do not supersede the current proof lane above.

The `18b90ff` ignore rule is accepted policy for this branch because the user explicitly requested the remaining `.gitignore` change be committed separately with rationale on 2026-05-05. Its scope is active session handoff summaries as local resume artifacts; it does not change the repository rule that handoff files in current work are durable artifacts when they are in scope. Tracked handoff files still surface in `git status`.

Merge readiness requires all of the following:

- The executable proof boundary at `33a588b` or a later reviewed implementation boundary.
- The current committed Plan 03 artifact boundary recorded above, or a later docs boundary that explicitly supersedes it.
- A clean tracked worktree at review time.
- `git status --short --ignored docs/handoffs` checked at review time, plus `git status --short --ignored --untracked-files=all docs/handoffs` if the short form collapses ignored directories. Ignored `docs/handoffs/.session-state/` and `docs/handoffs/archive/` entries are expected local handoff mechanics. Any ignored active `docs/handoffs/*.md` file outside those directories must be archived, force-added and reviewed, or otherwise explicitly resolved before claiming closeout cleanliness.

The completed checkboxes mean the branch implementation has local verification evidence, not that the work is merged or that live status is no-drift. The live status warning is load-bearing: Plan 03 runtime inventory can be collected and aligned while the installed-cache/source assessment still ends in `coverage-gap-blocked`. A docs commit cannot self-name its own hash; after any ledger-only update, use `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` to record the next committed artifact boundary.
