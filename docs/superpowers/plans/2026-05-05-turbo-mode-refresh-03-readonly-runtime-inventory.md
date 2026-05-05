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
- runtime identity capture: `codex --version`, resolved executable path, executable SHA256 or unavailable reason, `initialize.serverInfo`, protocol/capability fields, parser version, and accepted response schema version
- local-only raw transcript evidence under `<codex_home>/local-only/turbo-mode-refresh/<RUN_ID>/`
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
  - Run `codex app-server --listen stdio://`.
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

Plan 03 accepts only responses with the matching integer ids above. It treats a response `error`, missing response id, timeout, closed stdout, malformed JSON response stream, or missing required inventory field as fail-closed inventory failure. The app-server process timeout is 30 seconds per request, and the child process is terminated in success, error, and timeout paths.

The response parser accepts:

- `initialize.result.serverInfo` and `initialize.result.capabilities` as runtime identity fields when present.
- `plugin/read` responses only when they contain the expected repo source path for each plugin and no `/plugin-dev/` path.
- `plugin/list` responses only when they contain both `handoff@turbo-mode` and `ticket@turbo-mode` and no `/plugin-dev/` path.
- `skills/list` responses only when they contain all expected Handoff and Ticket skill names from installed cache paths and no `/plugin-dev/` path.
- `hooks/list` responses only when they contain exactly one Ticket Bash `preToolUse` hook with command `python3 <codex_home>/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py`, source path `<codex_home>/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json`, and no Handoff hook entries.

Additional unrelated hooks are tolerated only when they do not appear as Handoff hooks and do not conflict with the single expected Ticket hook. They are not summarized as proof.

## Task 1: Add The Read-Only Inventory Parser

- [x] Write tests for request construction and successful response parsing.
- [x] Implement `build_readonly_inventory_requests()`.
- [x] Implement `validate_readonly_inventory_contract()` with strict required responses.
- [x] Prove missing Ticket hook, unexpected Handoff hook presence, plugin-dev paths, wrong Ticket hook command/source path, and missing skills fail closed.

## Task 2: Add Runtime Identity Capture And Roundtrip Execution

- [x] Write tests for identity hashing and unavailable hash reasons.
- [x] Implement `collect_codex_runtime_identity()`.
- [x] Implement `app_server_roundtrip()` without import coupling to migration tooling.
- [x] Ensure app-server process termination happens on success, error, and timeout.

## Task 3: Integrate Inventory With Planner

- [x] Write a test proving no-drift plus aligned config remains `filesystem-no-drift` without `--inventory-check`.
- [x] Write a test proving no-drift plus aligned config plus aligned inventory becomes `no-drift`.
- [x] Write a test proving failed inventory blocks preflight, persists `requested-failed`, and does not erase manifest facts.
- [x] Write a test proving requested inventory blocked by config preflight persists `requested-blocked`.
- [x] Implement `inventory_check` on `plan_refresh()`.

## Task 4: Extend CLI And Evidence

- [x] Write CLI tests for `--inventory-check` with a fake planner result or injected inventory collector.
- [x] Write evidence tests proving summary omits raw transcript and writes transcript as `0600`.
- [x] Write evidence tests proving requested-but-failed inventory is not reported as `not-requested`.
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

Current completion evidence after the review-fix pass:

- Branch: `feature/turbo-mode-refresh-plan-03-runtime-inventory`.
- Base/current HEAD at verification time: `9e36c72`.
- Worktree state at verification time: dirty implementation branch with `.gitignore` modified before Plan 03, Plan 03 files modified, and new plan/inventory test files still untracked.
- Focused tests: `186 passed` from `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q`.
- Lint: `All checks passed!` from `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`.
- Residue scan over Handoff, Ticket, and refresh roots printed nothing.
- Live read-only inventory smoke evidence path: `/Users/jp/.codex/local-only/turbo-mode-refresh/plan03-reviewfix-live-smoke-20260505/dry-run.summary.json`.
- Live smoke result: `app_server_inventory_status = collected`, runtime inventory aligned, `terminal_plan_status = coverage-gap-blocked`.

This is not a merge-ready closeout by itself because no commit has been created and the worktree remains dirty. The completed checkboxes mean the branch implementation has local verification evidence, not that the work is merged or that live status is no-drift.
