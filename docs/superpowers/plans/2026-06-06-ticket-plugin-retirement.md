# Ticket Plugin Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution with review checkpoints. Do not use subagents for primary execution because the archive/removal boundary and active-tree repair need one coherent working tree. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Ticket and ticket-backed Handoff workflows from the active repo tree while preserving retired Ticket material under `/Users/jp/archive/`.

**Architecture:** Treat retirement as one source-repo cutover with three dependent repairs: archive first, remove active Ticket and ticket-backed Handoff files, then rebaseline Turbo Mode refresh/runtime tests to expect only Handoff and Review Family. Installed runtime/cache mutation remains out of scope and must not be performed by this plan.

**Tech Stack:** Python 3.11, pytest, ruff, JSON plugin manifests, Markdown skill/docs files, shell archive commands using `ditto`, repository deletion using `trash`.

---

## Source Authority

- Design spec: `docs/superpowers/specs/2026-06-06-ticket-plugin-retirement-design.md`
- Archive destination: `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/`
- Retired active paths:
  - `plugins/turbo-mode/ticket/`
  - `docs/tickets/`
  - Handoff ticket-backed `/defer` and `/triage` surfaces
- Active plugin set after retirement:
  - `handoff`
  - `review-family`

## Stop Conditions

- Stop before writing `/Users/jp/archive/` unless filesystem approval is granted.
- Stop if either `plugins/turbo-mode/ticket/` or `docs/tickets/` is missing before archive creation; the archive must preserve the live source tree that is being retired.
- Stop if `ditto` archive copy succeeds for only one retired tree.
- Stop if the archive verification cannot prove both retired trees and `RETIREMENT.md` exist.
- Stop if tests still require Ticket as an active plugin after the source tree has been removed.
- Do not mutate `/Users/jp/.codex/plugins/cache/`, `/Users/jp/.codex/plugins/`, `/Users/jp/.agents/`, or Codex app-server runtime state.

## File Structure

### Archive Output

- Create: `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/plugins/turbo-mode/ticket/`
- Create: `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/docs/tickets/`
- Create: `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/RETIREMENT.md`

### Delete From Active Repo

- Delete: `plugins/turbo-mode/ticket/`
- Delete: `docs/tickets/`
- Delete: `plugins/turbo-mode/handoff/skills/defer/`
- Delete: `plugins/turbo-mode/handoff/skills/triage/`
- Delete: `plugins/turbo-mode/handoff/scripts/defer.py`
- Delete: `plugins/turbo-mode/handoff/scripts/triage.py`
- Delete: `plugins/turbo-mode/handoff/scripts/plugin_siblings.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/defer.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/triage.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/plugin_siblings.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/ticket_parsing.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/provenance.py`
- Delete: `plugins/turbo-mode/handoff/tests/test_defer.py`
- Delete: `plugins/turbo-mode/handoff/tests/test_triage.py`
- Delete: `plugins/turbo-mode/handoff/tests/test_ticket_parsing.py`
- Delete: `plugins/turbo-mode/handoff/tests/test_provenance.py`
- Delete: `plugins/turbo-mode/handoff/tests/test_plugin_siblings.py`
- Delete: `plugins/turbo-mode/tools/refresh/tests/test_ticket_hook_manifest.py`
- Delete: `plugins/turbo-mode/tools/migration/copy_ticket_source.py`

Use `trash <path>` for active-tree deletion. Do not use `rm`.

### Modify Active Repo

- Modify: `.agents/plugins/marketplace.json`
- Modify: `.codex/skills/turbo-plugin-refresh/SKILL.md`
- Modify: `.codex/skills/turbo-plugin-refresh/agents/openai.yaml`
- Modify: `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`
- Modify: `plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/handoff/README.md`
- Modify: `plugins/turbo-mode/handoff/CHANGELOG.md`
- Modify: `plugins/turbo-mode/handoff/references/skill-details.md`
- Modify: `plugins/turbo-mode/handoff/references/ARCHITECTURE.md`
- Modify: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/project_paths.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_cli_commands.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_runtime_namespace.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_skill_docs.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_release_metadata.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_architecture_docs.py`
- Modify: `plugins/turbo-mode/tools/dev_refresh_turbo_mode.py`
- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py` only if CLI help text still mentions Ticket after downstream edits
- Modify: `plugins/turbo-mode/tools/migration/validate_staged_content.py`
- Modify: `plugins/turbo-mode/tools/migration/migration_common.py`
- Modify: `plugins/turbo-mode/tools/migration/tests/test_migration_tools.py`
- Modify: `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/manifests.py`
- Modify: `plugins/turbo-mode/tools/refresh/planner.py`
- Modify: `plugins/turbo-mode/tools/refresh/process_gate.py`
- Modify: `plugins/turbo-mode/tools/refresh/smoke.py`
- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Modify refresh tests under `plugins/turbo-mode/tools/refresh/tests/` that assert Ticket inventory, hook, smoke, classifier, process-gate, or manifest behavior.

## Commit Boundary

Make one final source-retirement commit after the archive exists and focused verification passes. The active-tree deletions and dependent Handoff/refresh repairs are too coupled to land as separate green commits.

Commit message:

```bash
git commit -m "chore: retire ticket plugin"
```

## Task 0: Preflight And Archive

**Files:**
- Create outside repo: `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/`
- Read: `docs/superpowers/specs/2026-06-06-ticket-plugin-retirement-design.md`
- Read: `plugins/turbo-mode/ticket/`
- Read: `docs/tickets/`

- [ ] **Step 1: Confirm clean starting context**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
test -d plugins/turbo-mode/ticket
test -d docs/tickets
```

Expected:

- status shows no unstaged or staged changes
- HEAD prints the current implementation baseline
- both `test -d` commands exit 0

- [ ] **Step 2: Request archive write approval**

Ask for approval to write `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/`.

After approval, run:

```bash
mkdir -p /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/plugins/turbo-mode
mkdir -p /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/docs
```

Expected:

- both directories exist
- no active repo file has changed

- [ ] **Step 3: Copy retired trees to archive**

Run:

```bash
ditto plugins/turbo-mode/ticket /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/plugins/turbo-mode/ticket
ditto docs/tickets /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/docs/tickets
```

Expected:

- `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/plugins/turbo-mode/ticket/.codex-plugin/plugin.json` exists
- `/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/docs/tickets/` contains the retired ticket files and `.audit` history

- [ ] **Step 4: Write the archive retirement note**

Create `/private/tmp/codex-tool-dev-ticket-retirement-RETIREMENT.md` with this content, replacing only the branch and commit values with the exact outputs from Step 1:

```markdown
# Ticket Plugin Retirement Archive

Source repo: `/Users/jp/Projects/active/codex-tool-dev`
Archive date: 2026-06-06
Archive branch: `main`
Archive source commit: `<exact short HEAD from Step 1>`

This archive preserves Ticket source material removed from the active
`codex-tool-dev` tree during Ticket plugin retirement.

Archived source paths:

- `plugins/turbo-mode/ticket/`
- `docs/tickets/`

Retirement design:

- `docs/superpowers/specs/2026-06-06-ticket-plugin-retirement-design.md`
- `docs/superpowers/plans/2026-06-06-ticket-plugin-retirement.md`

Runtime boundary:

This archive step did not mutate installed Codex runtime state, personal plugin
copies, or installed plugin cache paths. Runtime retirement requires a separate
live-inventory plan.

Verification:

- Archive path exists.
- Retired Ticket plugin source exists under the archive.
- Retired `docs/tickets/` history exists under the archive.
- Source-retirement verification was run in the active repo after active-tree
  removal and dependent repair.
```

Copy it into the archive:

```bash
ditto /private/tmp/codex-tool-dev-ticket-retirement-RETIREMENT.md /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/RETIREMENT.md
```

Expected:

- `RETIREMENT.md` exists in the archive root
- the note states that runtime/cache state was not mutated

- [ ] **Step 5: Verify archive content before deleting active files**

Run:

```bash
test -f /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/plugins/turbo-mode/ticket/.codex-plugin/plugin.json
test -d /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/docs/tickets/.audit
test -f /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/RETIREMENT.md
```

Expected: all commands exit 0.

## Task 1: Remove Ticket Active Source

**Files:**
- Delete: `plugins/turbo-mode/ticket/`
- Delete: `docs/tickets/`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.codex/skills/turbo-plugin-refresh/SKILL.md`
- Modify: `.codex/skills/turbo-plugin-refresh/agents/openai.yaml`
- Modify: `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`

- [ ] **Step 1: Remove Ticket from the repo marketplace**

Edit `.agents/plugins/marketplace.json` so the `plugins` array contains only `handoff` and `review-family`.

Expected JSON shape:

```json
{
  "name": "turbo-mode",
  "interface": {
    "displayName": "Turbo Mode"
  },
  "plugins": [
    {
      "name": "handoff",
      "source": {
        "source": "local",
        "path": "./plugins/turbo-mode/handoff"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    },
    {
      "name": "review-family",
      "source": {
        "source": "local",
        "path": "./plugins/turbo-mode/review-family"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

- [ ] **Step 2: Patch the repo-local refresh skill**

Edit `.codex/skills/turbo-plugin-refresh/SKILL.md` and `.codex/skills/turbo-plugin-refresh/agents/openai.yaml` so they describe Handoff and Review Family only.

Required wording changes:

- replace `Handoff, Ticket, and Review Family` with `Handoff and Review Family`
- replace ``handoff`, `ticket`, and `review-family`` with ``handoff` and `review-family``
- remove instructions that require `ticket` to appear in planned copy operations, plugin list output, or runtime inventory
- keep the source-vs-installed-runtime proof boundary intact

- [ ] **Step 3: Patch the historical refresh design status section**

Edit only the current-baseline `## Status` section of `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`.

Required current-baseline replacements:

- `Current roots include plugins/turbo-mode/handoff/ and plugins/turbo-mode/ticket/.` becomes `Current roots include plugins/turbo-mode/handoff/ and plugins/turbo-mode/review-family/.`
- Any current-baseline bullet that says routine sync installs Handoff and Ticket becomes Handoff and Review Family.

Leave the later historical body intact unless a sentence currently tells agents to use Ticket as routine development infrastructure.

- [ ] **Step 4: Remove the retired source trees from the active repo**

Run only after Task 0 archive verification passed:

```bash
trash plugins/turbo-mode/ticket
trash docs/tickets
```

Expected:

- `test ! -e plugins/turbo-mode/ticket` exits 0
- `test ! -e docs/tickets` exits 0
- archive copies still exist

- [ ] **Step 5: Inspect active Ticket references**

Run:

```bash
rg -n "plugins/turbo-mode/ticket|docs/tickets|ticket@turbo-mode|Ticket plugin|ticket plugin" .agents .codex/skills/turbo-plugin-refresh plugins/turbo-mode docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md
```

Expected:

- matches remain only in historical specs/plans/closeouts/evidence or in code that is about to be patched in later tasks
- no current marketplace or refresh skill text still presents Ticket as expected

Do not commit yet.

## Task 2: Remove Ticket-Backed Handoff Workflow

**Files:**
- Delete: `plugins/turbo-mode/handoff/skills/defer/`
- Delete: `plugins/turbo-mode/handoff/skills/triage/`
- Delete: `plugins/turbo-mode/handoff/scripts/defer.py`
- Delete: `plugins/turbo-mode/handoff/scripts/triage.py`
- Delete: `plugins/turbo-mode/handoff/scripts/plugin_siblings.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/defer.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/triage.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/plugin_siblings.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/ticket_parsing.py`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/provenance.py`
- Modify: `plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/handoff/README.md`
- Modify: `plugins/turbo-mode/handoff/CHANGELOG.md`
- Modify: `plugins/turbo-mode/handoff/references/skill-details.md`
- Modify: `plugins/turbo-mode/handoff/references/ARCHITECTURE.md`
- Modify: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/project_paths.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_runtime_namespace.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_skill_docs.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_cli_commands.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_release_metadata.py`
- Modify: `plugins/turbo-mode/handoff/tests/test_architecture_docs.py`

- [ ] **Step 1: Delete ticket-only Handoff files**

Run:

```bash
trash plugins/turbo-mode/handoff/skills/defer
trash plugins/turbo-mode/handoff/skills/triage
trash plugins/turbo-mode/handoff/scripts/defer.py
trash plugins/turbo-mode/handoff/scripts/triage.py
trash plugins/turbo-mode/handoff/scripts/plugin_siblings.py
trash plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/defer.py
trash plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/triage.py
trash plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/plugin_siblings.py
trash plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/ticket_parsing.py
trash plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/provenance.py
trash plugins/turbo-mode/handoff/tests/test_defer.py
trash plugins/turbo-mode/handoff/tests/test_triage.py
trash plugins/turbo-mode/handoff/tests/test_ticket_parsing.py
trash plugins/turbo-mode/handoff/tests/test_provenance.py
trash plugins/turbo-mode/handoff/tests/test_plugin_siblings.py
```

Expected:

- all listed paths no longer exist
- `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/distill.py` still exists because it owns its own distill-meta behavior

- [ ] **Step 2: Rebaseline Handoff manifest metadata**

Edit `plugins/turbo-mode/handoff/.codex-plugin/plugin.json`.

Required changes:

- description: `Session handoff, resume, search, and durable learning extraction for context continuity`
- remove keywords `defer`, `triage`, and `tickets`
- shortDescription: `Save, resume, search, and distill session handoffs`
- longDescription: `Preserve Codex session context as structured handoffs, resume prior work, search history, and extract durable learnings across repositories.`

Keep version `1.7.0`.

- [ ] **Step 3: Rebaseline Handoff README and references**

Edit `plugins/turbo-mode/handoff/README.md` and `plugins/turbo-mode/handoff/references/skill-details.md`.

Required README outcome:

- first paragraph describes session continuity, resume, search, distill, and summary behavior only
- remove the `Deferred work tracking` feature row
- remove `defer` and `triage` skill rows
- remove `defer.py`, `triage.py`, `plugin_siblings.py`, `ticket_parsing.py`, and ticket storage rows from script/storage tables
- remove the `Ticket Frontmatter` section
- command lists no longer show `/defer` or `/triage`
- architecture diagram no longer lists `/defer`, `/triage`, `defer.py`, `triage.py`, or `ticket_parsing.py`
- add a short current-facing note: `Ticket-backed deferred-work tracking was retired on 2026-06-06; use handoff prose for follow-up context until a replacement tracking workflow is designed.`

Required `skill-details.md` outcome:

- remove the `/defer` detail block
- remove the `/triage` detail block
- keep search, distill, save, quicksave, summary, and load details intact

- [ ] **Step 4: Rebaseline Handoff architecture docs and path comments**

Edit `plugins/turbo-mode/handoff/references/ARCHITECTURE.md` and `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/project_paths.py`.

Required outcome:

- remove ticket parser/provenance/triage module ownership claims
- remove wording that says project path helpers are used by triage
- keep storage, chain-state, load, save, search, and distill topology intact

- [ ] **Step 5: Update runtime namespace tests**

Edit `plugins/turbo-mode/handoff/tests/test_runtime_namespace.py`.

Replace the module inventories with:

```python
RUNTIME_MODULES = {
    "active_writes.py",
    "cleanup.py",
    "chain_state.py",
    "distill.py",
    "handoff_parsing.py",
    "installed_host_harness.py",
    "list_handoffs.py",
    "load_transactions.py",
    "project_paths.py",
    "quality_check.py",
    "search.py",
    "session_state.py",
    "storage_authority.py",
    "storage_authority_inventory.py",
    "storage_inspection.py",
    "storage_layout.py",
    "storage_primitives.py",
}

CLI_FACADES = {
    "distill.py",
    "list_handoffs.py",
    "load_transactions.py",
    "search.py",
    "session_state.py",
}
```

Keep `STRING_RETURNING_FACADES = {"distill.py", "list_handoffs.py", "search.py"}`.

- [ ] **Step 6: Update Handoff skill doc tests**

Edit `plugins/turbo-mode/handoff/tests/test_skill_docs.py`.

Required replacements:

```python
COMMAND_SKILLS = [
    PLUGIN_ROOT / "skills" / "search-handoffs" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "distill" / "SKILL.md",
]
```

Remove `test_defer_skill_uses_plugin_siblings_plain_field` and `test_defer_skill_hides_ticket_ingest_transcript_internals`.

Keep state-skill tests intact, but update stale skill paths if the file still refers to `skills/load`, `skills/save`, or `skills/summary`; the current directories are `load-handoff`, `save-handoff`, and `save-summary`.

- [ ] **Step 7: Update Handoff CLI tests**

Edit `plugins/turbo-mode/handoff/tests/test_cli_commands.py`.

Remove:

- `test_triage_command_runs_from_normal_repo_cwd`
- `test_defer_pipeline_matches_ticket_guard_contract`

Keep search and distill command tests unchanged.

- [ ] **Step 8: Update Handoff release and architecture tests**

Edit `plugins/turbo-mode/handoff/tests/test_release_metadata.py` and `plugins/turbo-mode/handoff/tests/test_architecture_docs.py`.

Required outcomes:

- test path constants use `load-handoff`, `save-handoff`, `save-summary`, and `quicksave`
- release metadata tests assert the README no longer advertises `/defer`, `/triage`, `docs/tickets`, or Ticket-backed tracking
- architecture docs tests do not expect ticket-only module ownership claims
- existing storage-authority, chain-state, load, save, search, and distill claims remain asserted

- [ ] **Step 9: Run focused Handoff checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff pytest tests/test_runtime_namespace.py tests/test_skill_docs.py tests/test_cli_commands.py tests/test_release_metadata.py tests/test_architecture_docs.py -q
```

Expected: all selected tests pass.

Do not commit yet.

## Task 3: Rebaseline Turbo Refresh And Runtime Tooling

**Files:**
- Modify: `plugins/turbo-mode/tools/dev_refresh_turbo_mode.py`
- Modify: `plugins/turbo-mode/tools/migration/validate_staged_content.py`
- Modify: `plugins/turbo-mode/tools/migration/migration_common.py`
- Delete: `plugins/turbo-mode/tools/migration/copy_ticket_source.py`
- Modify: `plugins/turbo-mode/tools/migration/tests/test_migration_tools.py`
- Modify: `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/manifests.py`
- Modify: `plugins/turbo-mode/tools/refresh/planner.py`
- Modify: `plugins/turbo-mode/tools/refresh/process_gate.py`
- Modify: `plugins/turbo-mode/tools/refresh/smoke.py`
- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/*.py`
- Delete: `plugins/turbo-mode/tools/refresh/tests/test_ticket_hook_manifest.py`

- [ ] **Step 1: Remove the ticket copy helper**

Run:

```bash
trash plugins/turbo-mode/tools/migration/copy_ticket_source.py
trash plugins/turbo-mode/tools/refresh/tests/test_ticket_hook_manifest.py
```

Expected: both paths no longer exist.

- [ ] **Step 2: Rebaseline planner plugin specs**

Edit `plugins/turbo-mode/tools/refresh/planner.py`.

Required constants:

```python
EXPECTED_MARKETPLACE_SOURCES = {
    "handoff": "./plugins/turbo-mode/handoff",
    "review-family": "./plugins/turbo-mode/review-family",
}
EXPECTED_CONFIG_PLUGINS = (
    "handoff@turbo-mode",
    "review-family@turbo-mode",
)
```

Required `build_plugin_specs()` return value:

```python
return [
    PluginSpec(
        name="handoff",
        version="1.7.0",
        source_root=repo_root / "plugins/turbo-mode/handoff",
        cache_root=codex_home / "plugins/cache/turbo-mode/handoff/1.7.0",
    ),
    PluginSpec(
        name="review-family",
        version="0.1.0",
        source_root=repo_root / "plugins/turbo-mode/review-family",
        cache_root=codex_home / "plugins/cache/turbo-mode/review-family/0.1.0",
    ),
]
```

If existing tests require Handoff cache version `1.6.0`, update those tests and fixture paths to `1.7.0` because the live manifest is `1.7.0`.

- [ ] **Step 3: Rebaseline app-server inventory**

Edit `plugins/turbo-mode/tools/refresh/app_server_inventory.py`.

Required outcomes:

- remove `EXPECTED_TICKET_SKILLS`
- remove `ticket` from `PLUGIN_VERSIONS`
- remove `ticket` from `PLUGIN_READ_RESPONSE_IDS`
- remove `ticket` from `EXPECTED_SKILLS_BY_PLUGIN`
- remove the Ticket `plugin/read` request from `build_readonly_inventory_requests()`
- keep Handoff and Review Family `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`
- remove `rewrite_ticket_hook_manifest()`, `parse_ticket_guard_command()`, and Ticket guard command helpers if no remaining code imports them
- remove `ticket_hook` from `AppServerInventoryCheck` and replace summaries/tests with generic hook inventory or no hook assertion

Expected request IDs after the edit:

```text
0 initialize
1 plugin/read handoff
2 plugin/list
3 skills/list
4 hooks/list
5 plugin/read review-family
```

- [ ] **Step 4: Rebaseline dev refresh**

Edit `plugins/turbo-mode/tools/dev_refresh_turbo_mode.py`.

Required outcomes:

- remove import of `rewrite_ticket_hook_manifest`
- remove `_repair_installed_plugin_metadata()` or make it a no-op with no Ticket special case
- runtime inventory summary no longer includes `ticket_hook`
- install requests are still generated from the marketplace plugin list, now Handoff and Review Family only

- [ ] **Step 5: Rebaseline standard smoke**

Edit `plugins/turbo-mode/tools/refresh/smoke.py`.

Required outcomes:

- `_SmokeState` has no `ticket_plugin` or `ticket_id`
- `_prepare_state()` no longer creates `smoke_repo / "docs/tickets"`
- `_build_smoke_plan()` contains only:
  - `smoke-repo-git-init`
  - `handoff-session-state-archive`
  - `handoff-session-state-write`
  - `handoff-session-state-read`
  - `handoff-session-state-clear`
- remove `_ticket_workflow_pair`, `_ticket_workflow_command`, `_ticket_hook_command`, ticket payload factories, ticket ID recording, ticket hook assertions, and Ticket audit/list/query commands

Expected smoke labels:

```python
[
    "smoke-repo-git-init",
    "handoff-session-state-archive",
    "handoff-session-state-write",
    "handoff-session-state-read",
    "handoff-session-state-clear",
]
```

- [ ] **Step 6: Rebaseline classifier and process gate**

Edit `plugins/turbo-mode/tools/refresh/classifier.py`.

Required outcomes:

- remove every `ticket/1.4.0/...` pattern
- remove `handoff/1.6.0/scripts/defer.py`
- remove `handoff/1.6.0/scripts/triage.py`
- remove Ticket smoke labels
- keep Handoff session-state, search, distill, README, CHANGELOG, skills, and references classification

Edit `plugins/turbo-mode/tools/refresh/process_gate.py`.

Required outcomes:

- remove `TICKET_HOOK_ROOT`
- remove `_is_ticket_hook_runtime()`
- remove `_is_ticket_hook_path_consumer()`
- remove `ticket-engine`, `ticket-workflow`, and `ticket-hook-path` from high-risk marker detection
- keep Codex Desktop, Codex CLI, and Codex app-server blockers

- [ ] **Step 7: Rebaseline commit-safe and validation allowlists**

Edit `plugins/turbo-mode/tools/refresh/validation.py`.

Required outcomes:

- remove `ticket@turbo-mode` from `NESTED_ALLOWED_KEYS["runtime_config_plugin_enablement_state"]`
- remove `plugins/turbo-mode/ticket` from `ALLOWED_DIRTY_RELEVANT_PATHS`
- keep `.agents/plugins/marketplace.json`, `plugins/turbo-mode/handoff`, `plugins/turbo-mode/review-family`, `plugins/turbo-mode/tools/refresh`, and refresh tool paths

Edit `plugins/turbo-mode/tools/refresh/commit_safe.py` only if its serialized runtime-config projection explicitly requires Ticket keys.

Edit `plugins/turbo-mode/tools/refresh/manifests.py`:

- remove `.codex/ticket-tmp` from generated path fragments unless a test proves it is still needed for historical fixture compatibility

- [ ] **Step 8: Rebaseline migration helpers and tests**

Edit migration files so current validation no longer expects Ticket:

- `plugins/turbo-mode/tools/migration/validate_staged_content.py`
- `plugins/turbo-mode/tools/migration/migration_common.py`
- `plugins/turbo-mode/tools/migration/tests/test_migration_tools.py`

Required outcome:

- no current migration validation path requires `plugins/turbo-mode/ticket`
- no test imports `copy_ticket_source.py`
- historical migration evidence files under `plugins/turbo-mode/evidence/` are not rewritten

- [ ] **Step 9: Update refresh tests**

Run a first refresh test collection to expose stale imports:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests --collect-only -q
```

Expected:

- collection succeeds
- no collected test name mentions `ticket_hook_manifest`

Patch refresh tests so they assert:

- marketplace and planner expected plugins are `handoff` and `review-family`
- runtime config plugin enablement keys are `handoff@turbo-mode` and `review-family@turbo-mode`
- app-server inventory expected skills exclude Ticket and Handoff `defer`/`triage`
- standard smoke excludes Handoff `/defer` and all Ticket commands
- process-gate tests cover Codex blockers, not Ticket hook blockers
- classifier tests do not require Ticket path classification

- [ ] **Step 10: Run focused refresh checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: refresh tests pass.

Do not commit yet.

## Task 4: Active Reference Sweep

**Files:**
- Modify any current-facing file found by the sweeps below.
- Do not rewrite historical docs except current status sections.

- [ ] **Step 1: Sweep active source and skill references**

Run:

```bash
rg -n "Ticket|ticket|docs/tickets|/defer|/triage|ticket@turbo-mode|plugins/turbo-mode/ticket|ticket_engine|ticket_workflow" .agents .codex plugins/turbo-mode package.json docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md docs/superpowers/specs/2026-06-06-ticket-plugin-retirement-design.md docs/superpowers/plans/2026-06-06-ticket-plugin-retirement.md
```

Expected allowed matches:

- this retirement spec
- this implementation plan
- historical body text in `2026-05-04-turbo-mode-installed-refresh-design.md`
- historical evidence fixtures clearly scoped to old migration behavior

Patch any current-facing match that still says Ticket is active.

- [ ] **Step 2: Sweep removed file imports**

Run:

```bash
rg -n "turbo_mode_handoff_runtime\\.(defer|triage|plugin_siblings|ticket_parsing|provenance)|scripts/(defer|triage|plugin_siblings)\\.py|copy_ticket_source" plugins/turbo-mode .codex docs/superpowers/plans/2026-06-06-ticket-plugin-retirement.md
```

Expected allowed matches:

- this implementation plan only

Patch all active code/test references outside this plan.

- [ ] **Step 3: Check JSON and TOML syntax**

Run:

```bash
python -m json.tool .agents/plugins/marketplace.json >/dev/null
python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json >/dev/null
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
from pathlib import Path
import tomllib

tomllib.loads(Path("plugins/turbo-mode/handoff/pyproject.toml").read_text())
PY
```

Expected: all commands exit 0.

## Task 5: Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Verify archive still exists**

Run:

```bash
test -f /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/plugins/turbo-mode/ticket/.codex-plugin/plugin.json
test -d /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/docs/tickets/.audit
test -f /Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/RETIREMENT.md
```

Expected: all commands exit 0.

- [ ] **Step 2: Verify active source removal**

Run:

```bash
test ! -e plugins/turbo-mode/ticket
test ! -e docs/tickets
test ! -e plugins/turbo-mode/handoff/skills/defer
test ! -e plugins/turbo-mode/handoff/skills/triage
test ! -e plugins/turbo-mode/handoff/scripts/defer.py
test ! -e plugins/turbo-mode/handoff/scripts/triage.py
```

Expected: all commands exit 0.

- [ ] **Step 3: Run Handoff suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff pytest -q
```

Expected: Handoff tests pass.

- [ ] **Step 4: Run refresh suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: refresh tests pass.

- [ ] **Step 5: Run migration tests if migration files changed**

Run if `git diff --name-only` includes `plugins/turbo-mode/tools/migration/`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/migration/tests -q
```

Expected: migration tests pass.

- [ ] **Step 6: Run lint on changed Python paths**

Build the changed Python path list:

```bash
git diff --name-only -- '*.py'
```

Run ruff on those paths that still exist. Example command shape:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check <existing changed python paths>
```

Expected: ruff passes.

- [ ] **Step 7: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 8: Check generated residue**

Run:

```bash
find plugins/turbo-mode/handoff plugins/turbo-mode/tools -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .DS_Store
```

Expected:

- no generated residue under changed source paths
- if residue appears, clean it with `trash <path>` and rerun the check

## Task 6: Review, Stage, Commit

**Files:**
- Stage all intentional retirement changes.
- Do not stage unrelated local handoffs or runtime artifacts.

- [ ] **Step 1: Review diff stats**

Run:

```bash
git status --short --branch
git diff --stat
```

Expected:

- deletions include `plugins/turbo-mode/ticket/` and `docs/tickets/`
- modifications include Handoff and refresh rebaseline files
- no `/Users/jp/.codex/`, `/Users/jp/.agents/`, or installed cache path is staged or modified by git

- [ ] **Step 2: Review targeted diffs**

Run:

```bash
git diff -- .agents/plugins/marketplace.json
git diff -- plugins/turbo-mode/handoff/.codex-plugin/plugin.json
git diff -- plugins/turbo-mode/tools/refresh/planner.py
git diff -- plugins/turbo-mode/tools/refresh/app_server_inventory.py
git diff -- plugins/turbo-mode/tools/refresh/smoke.py
```

Expected:

- marketplace has Handoff and Review Family only
- Handoff metadata no longer advertises ticket-backed tracking
- planner and inventory expect Handoff and Review Family only
- smoke no longer runs Handoff defer or Ticket commands

- [ ] **Step 3: Stage intentional changes**

Run:

```bash
git add -A .agents/plugins/marketplace.json .codex/skills/turbo-plugin-refresh docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md plugins/turbo-mode/handoff plugins/turbo-mode/tools
git add -A docs/tickets plugins/turbo-mode/ticket
```

Expected:

- deletions for retired active paths are staged
- no archive files are staged because `/Users/jp/archive/` is outside the repo

- [ ] **Step 4: Review staged diff**

Run:

```bash
git diff --cached --stat
git diff --cached --name-status
```

Expected:

- staged diff matches the retirement scope
- no unrelated files are staged

- [ ] **Step 5: Commit**

Run:

```bash
git commit -m "chore: retire ticket plugin"
```

Expected: commit succeeds.

## Final Report Requirements

Report these proof classes separately:

- `source`: active repo paths removed, docs/tests patched, commit hash
- `archive`: archive directory path and verification commands
- `installed runtime`: explicitly unchanged and unproven
- `local cache`: explicitly unchanged and unproven

Mention any tests skipped or blocked. Do not claim installed Ticket is gone from Codex unless a separate runtime inventory/uninstall plan is executed.
