# Ticket ADR Source/Repo Satisfaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the local source/repo Ticket lane into honest satisfaction of ADR 0006 and the May 30 state-kernel control doc, without claiming installed runtime proof.

**Architecture:** This is a source/repo cutover plan, not a cache-refresh or live-runtime plan. It normalizes repo ticket records first, then makes normal Ticket product surfaces reject non-normalized active ticket files while leaving explicit diagnostic/cutover inventory able to explain invalid legacy files. After the repo records and schema boundary are stable, it normalizes the write/persistence kernel so creates and updates persist only target-shaped ID-only records, then collapses the candidate contract, response envelope, Change History grammar, and deprecated workflow machinery in coherent source commits.

**Tech Stack:** Python >=3.11, PyYAML, dataclasses, Markdown/YAML parsing, existing Ticket scripts, pytest, ruff, `git mv`, bytecode-safe `uv run` verification.

---

## Scope Check

This plan covers the source/repo finish line only.

In scope:

- Normalize the seven current `docs/tickets/*.md` records into ADR 0006 target schema and ID-only filenames.
- Prove no noncanonical Ticket storage remains under `docs/`.
- Add deterministic target-ticket validation and make normal Ticket read/mutation/product surfaces reject non-normalized active tickets after cutover.
- Normalize write/persistence surfaces so `validate_fields()`, `render_ticket()`, ID filename helpers, engine create/update/defaults, gateway create defaults, and envelope-to-ticket mapping cannot persist old ticket shapes.
- Keep explicit diagnostic/cutover inventory able to inspect invalid files and report why they are invalid.
- Move the live source candidate contract toward `action`, `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`, with unknown-field rejection.
- Collapse normal result states toward `ok`, `blocked`, `needs_discussion`, `invalid_state`, and `no_change`.
- Replace controlled `Change History` labels with the target dated prose grammar.
- Delete deprecated prepare/execute/workflow architecture unless a narrow diagnostic/cutover use remains with a sunset condition.
- Update active README, contract, skills, and docs-contract tests so old behavior is not presented as target authority.

Out of scope:

- Installed cache refresh under `/Users/jp/.codex/plugins/cache`.
- Runtime inventory through `plugin/read`, `plugin/list`, `skills/list`, `hooks/list`, or live hook smokes.
- Publishing, pushing, or PR creation.
- Updating external references to old ticket paths outside `docs/tickets/`; this plan reports them for a separate explicit follow-up.
- Long-term archival policy beyond proving closed tickets stay canonical while represented as `status: done` or `status: wontfix`.

Closeout claim for this plan:

```text
ADR 0006 and the May 30 control doc are satisfied for the local source/repo lane: current ticket records are normalized, normal source surfaces reject non-normalized active tickets, normal writes persist only target-shaped ID-only records, active docs/tests no longer preserve old Ticket architecture as current behavior, and remaining runtime/cache proof is a separate unclaimed lane.
```

Do not use this claim until every verification gate in this plan passes.

## Live Inventory From 2026-06-02

Baseline checked in this session:

- Branch: `chore/ticket-runtime-first-rebaseline-adr`
- HEAD: `9479a985`
- Tracked worktree before this plan file: clean
- Installed runtime: not inspected
- Cache state: not inspected
- Plan revision source: review-reviewer adjudication against current HEAD `e008a27e`; the review confirmed the original plan under-scoped write/persistence, strict-read test blast radius, Change History gateway coupling, result-state/autonomy emitters, doctor stale-payload sunset, and residue-gate ownership.

Primary authority:

- `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`

### Ticket Record Inventory

There are seven current ticket files under `docs/tickets/`. All seven are pre-cutover:

- slug filenames instead of `T-YYYYMMDD-NN.md`;
- duplicated H1 title lines instead of frontmatter `title`;
- fenced YAML blocks instead of YAML frontmatter;
- old keys such as `date`, `created_at`, `effort`, `source`, `blocks`, `contract_version`, `key_file_paths`, `capture_confidence`, `capture_source`, and `component`;
- `priority: medium` in six tickets, which maps to target `priority: normal`;
- missing `## Change History` in all seven;
- missing `## Next Action` in six tickets.

Target rewrite map:

| Current path | Target path | Status | Priority map | Required-section work |
|---|---|---:|---:|---|
| `docs/tickets/2026-05-08-add-sandbox-integration-coverage-for-guarded.md` | `docs/tickets/T-20260508-01.md` | `done` | `medium` -> `normal` | add `Next Action`, add `Change History` |
| `docs/tickets/2026-05-08-classify-and-harden-turbo-mode-migration.md` | `docs/tickets/T-20260508-02.md` | `open` | `medium` -> `normal` | add `Next Action`, add `Change History` |
| `docs/tickets/2026-05-16-harden-active-write-status-partition-regression-gate-pr.md` | `docs/tickets/T-20260516-01.md` | `open` | `medium` -> `normal` | add `Next Action`, add `Change History` |
| `docs/tickets/2026-05-17-validate-active-write-reservation-status-boundary.md` | `docs/tickets/T-20260517-01.md` | `open` | `medium` -> `normal` | add `Next Action`, add `Change History` |
| `docs/tickets/2026-05-18-serialize-parallel-agent-ticket-creation.md` | `docs/tickets/T-20260518-01.md` | `open` | `medium` -> `normal` | add `Next Action`, add `Change History` |
| `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md` | `docs/tickets/T-20260518-02.md` | `open` | `high` -> `high` | add `Next Action`, add `Change History` |
| `docs/tickets/2026-05-26-resolve-slice-1a-plan-commit-boundary.md` | `docs/tickets/T-20260526-01.md` | `open` | `medium` -> `normal` | add `Change History` |

No old `closed-tickets/` or Ticket archive directory was found under `docs/` in this session. `docs/handoffs/archive` exists and is unrelated to Ticket normalization.

External references found outside `docs/tickets/`:

- `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition-followup.md` references old path `docs/tickets/2026-05-16-harden-active-write-status-partition-regression-gate-pr.md`.
- `docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md` references old path `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`.
- `docs/superpowers/plans/2026-05-18-ticket-autonomy-ingest-contract-hardening.md` references old paths and embedded historical ticket creation text.
- Tests and skills contain ticket IDs as fixtures. ID references are not path rewrite blockers.

Do not update those external historical plan references in this source/repo satisfaction pass unless the user explicitly widens scope. Report them in the closeout as reviewed external references.

### Source Drift Inventory

Current schema/parser/write drift:

- `plugins/turbo-mode/ticket/scripts/ticket_parse.py` parses fenced YAML, applies legacy generations, normalizes old statuses, applies legacy defaults, and still includes `blocked`, `blocks`, `capture_confidence`, `component`, and `contract_version`.
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py` allows `critical`, `medium`, and `blocked`, and validates old capture/refinement/component fields.
- `plugins/turbo-mode/ticket/scripts/ticket_render.py` renders fenced YAML and old field order including `date`, `created_at`, `effort`, `source`, `capture_confidence`, `component`, `blocks`, and `contract_version`.
- `plugins/turbo-mode/ticket/scripts/ticket_id.py` still builds `YYYY-MM-DD-<slug>.md` filenames through `build_filename()` instead of target ID-only filenames.
- `plugins/turbo-mode/ticket/scripts/ticket_envelope.py` accepts `critical` and `medium`, defaults envelope-created tickets to `medium`, and maps old deferred envelope fields into engine create fields.
- `plugins/turbo-mode/ticket/scripts/ticket_read.py` silently skips unparseable files, scans `closed-tickets` when requested, and returns old fields such as `date`, `blocks`, `capture.confidence`, and `capture.component`.

Current candidate/runtime drift:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` defines `CandidateMutation(ticket_id, action, proposed_change, evidence, conflict_reason)` rather than the target `target`, `expected_ticket_fingerprint`, and `evidence_summary` shape.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py` extracts known old structured fields and ignores unknown fields instead of rejecting them.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py` still adapts old candidate/runtime structures into gateway writes.

Current workflow/response drift:

- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` is still a `classify | plan | preflight | execute` pipeline and `engine_execute()` still requires classifier and plan-stage fields.
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py` still models classify/plan/preflight/execute inputs.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`, `plugins/turbo-mode/ticket/scripts/ticket_update.py`, `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`, and related tests still preserve prepare/execute saved-preview behavior.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` still dispatches low-level stage commands for compatibility/debug surfaces.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` still stores repo context with branch/head and old pending-summary states such as `skipped`, `discussion_required`, `ticket_written`, and `applied`, while already rejecting old `commit_disposition`, `commit_hash`, `commit_reason`, and `ticket_change_scope` details.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py` and `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` still emit or validate `ticket_update_blocked`; this token is not emitted by `ticket_turn_batch.py`.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, `ticket_workflow.py`, and tests still use states such as `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `policy_blocked`, `need_fields`, `preflight_failed`, `dependency_blocked`, and `invalid_transition`.

Current Change History drift:

- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py` uses `ChangeHistoryLabel` values `auto-create`, `auto-update`, `auto-blocker`, `auto-close`, `auto-reopen`, `correction`, and `discussion-approved`.
- `ChangeHistoryEntry` still has `prior_commit`, which is not target grammar.

Docs/tests state:

- README and `references/ticket-contract.md` already describe the target schema, target candidate contract, target result envelope, and target Change History grammar.
- They also preserve old surfaces as deprecated/diagnostic source facts. That is acceptable only until source removal finishes; the final source/repo closeout must not leave old behavior usable as normal product authority.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` already guards many target-doc sections and should be extended from docs-only target claims into source/repo guards after implementation.
- `plugins/turbo-mode/ticket/tests/support/builders.py` emits legacy fenced-YAML tickets by default, so strict reads require a builder migration plus explicit legacy/cutover fixtures.
- `plugins/turbo-mode/ticket/tests/test_migration.py` asserts direct `parse_ticket()` acceptance of legacy generations; after strict reads it must be repointed to diagnostic/cutover parsing or deleted with equivalent cutover coverage.

## Stop Conditions

Stop before implementation edits if:

- `git status --short --branch` shows tracked dirty files unrelated to this plan.
- ADR 0006 or the May 30 control doc no longer defines this source/repo finish line.
- A ticket record has a non-date-shaped ID, ambiguous target path, ambiguous status, or ambiguous priority mapping.
- A noncanonical Ticket storage directory appears under `docs/` and deterministic mapping is unclear.
- The implementation would need to mutate installed cache, runtime state, or `/Users/jp/.codex/plugins/cache`.

Stop during implementation if:

- Normal ticket readers would silently skip invalid active ticket files instead of returning `invalid_state` or an equivalent explicit block.
- Diagnostic/cutover inventory can no longer inspect invalid old files.
- Ticket normalization would carry old metadata forward as opaque comments, appendices, or runtime-significant fields.
- A non-create write can pass without `expected_ticket_fingerprint`.
- Unknown candidate fields are accepted on normal mutation paths after the candidate-contract task.
- Normal create or update can persist fenced YAML, slug filenames, H1 title lines, `priority: medium`, `priority: critical`, `status: blocked`, `blocks`, `source`, `date`, `created_at`, `contract_version`, `capture_confidence`, `component`, `defer`, or other non-target storage fields.
- `build_filename()` or the engine create path can produce anything other than `T-YYYYMMDD-NN.md` after write-path normalization.
- Strict-read changes leave `tests/support/builders.py` generating invalid normal tickets by default or leave `test_migration.py` asserting direct normal parsing of legacy tickets.
- `ChangeHistoryLabel` is deleted before `ticket_engine_gateway.py` and gateway tests are updated to the actor grammar.
- Deprecated prepare/execute behavior remains as a usable normal product path without a narrow diagnostic label and sunset condition.
- Target docs claim installed runtime success or cache refresh.

## Commit Boundaries

Use coherent commits by surface:

1. `docs(ticket): plan adr source repo satisfaction`
2. `test(ticket): add target ticket schema guards`
3. `docs(ticket): normalize repo ticket records`
4. `fix(ticket): reject non-normalized active ticket files`
5. `fix(ticket): normalize target write persistence`
6. `fix(ticket): adopt target candidate mutation contract`
7. `fix(ticket): collapse ticket response states`
8. `fix(ticket): update change history grammar`
9. `fix(ticket): remove deprecated workflow mutation paths`
10. `docs(ticket): align active ticket docs with source repo cutover`

If a later task exposes that two adjacent boundaries cannot pass independently, merge the commit boundary and state why in the closeout.

## Task 0: Reconfirm Inventory Before Edits

**Files:**

- Read: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `docs/tickets/*.md`
- Read: `plugins/turbo-mode/ticket/scripts/*.py`
- Read: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Read: `plugins/turbo-mode/ticket/tests/support/builders.py`
- Read: `plugins/turbo-mode/ticket/tests/test_validate.py`
- Read: `plugins/turbo-mode/ticket/tests/test_render.py`
- Read: `plugins/turbo-mode/ticket/tests/test_id.py`
- Read: `plugins/turbo-mode/ticket/tests/test_envelope.py`
- Read: `plugins/turbo-mode/ticket/tests/test_migration.py`
- Read: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Read: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Read: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Read: `plugins/turbo-mode/ticket/tests/test_doctor.py`

- [ ] **Step 1: Confirm branch and cleanliness**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
```

Expected: branch is `chore/ticket-runtime-first-rebaseline-adr` or an execution branch created from it; no unrelated tracked dirty files.

- [ ] **Step 2: Re-run ticket inventory**

Run:

```bash
find docs/tickets -maxdepth 2 -type f -print
find docs -maxdepth 4 -type d -iname '*ticket*' -print
```

Expected: seven active ticket files before Task 2, no `docs/tickets/closed-tickets`, and no Ticket archive storage outside `docs/tickets`.

- [ ] **Step 3: Re-run source drift inventory**

Run:

```bash
rg -n "fenced YAML|closed-tickets|capture_confidence|component|contract_version|build_filename|suggested_priority|ready_to_execute|prepare|execute|classify_confidence|ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|auto-create|auto-update|discussion-approved|ChangeHistoryLabel|ticket_update_blocked|commit_disposition|ticket_change_scope" \
  plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references
```

Expected: hits are assignable to this plan, diagnostic/historical docs, or already-accepted target guards. In particular:

- `ticket_validate.py`, `ticket_render.py`, `ticket_id.py`, `ticket_engine_core.py`, `ticket_engine_gateway.py`, and `ticket_envelope.py` are assigned to Task 4.
- `tests/support/builders.py` and `test_migration.py` are assigned to Task 3.
- `ticket_autonomy.py`, `ticket_autonomy_runtime.py`, and `ticket_turn_batch.py` state vocabulary hits are assigned to Task 6.
- `ticket_engine_gateway.py` Change History hits are assigned to Task 7.
- `ticket_doctor.py` stale-payload cleanup hits are assigned to Task 8.

## Task 1: Add Target Ticket Schema Validation

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py`
- Create: `plugins/turbo-mode/ticket/tests/test_target_schema.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Write target-schema tests**

Add tests covering:

```python
def test_target_ticket_accepts_id_only_yaml_frontmatter(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    ticket.write_text(
        "---\n"
        "id: T-20260508-01\n"
        "title: Example\n"
        "status: open\n"
        "priority: normal\n"
        "tags: []\n"
        "related_paths: []\n"
        "blocked_by: []\n"
        "---\n\n"
        "## Problem\nExample problem.\n\n"
        "## Next Action\nExample next action.\n\n"
        "## Change History\n"
        "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n",
        encoding="utf-8",
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.ticket_id == "T-20260508-01"
```

Also add separate failing tests for:

- slug filename;
- fenced YAML;
- duplicated H1;
- unknown frontmatter key;
- `priority: medium`;
- `status: blocked`;
- missing or disordered `Problem`, `Next Action`, `Change History`;
- invalid Change History actor/label such as `auto-create`;
- invalid `blocks` reverse edge.

- [ ] **Step 2: Implement validation module**

Implement `ticket_target_schema.py` with:

- `TARGET_FRONTMATTER_REQUIRED = ("id", "title", "status", "priority")`
- `TARGET_FRONTMATTER_OPTIONAL = ("tags", "related_paths", "blocked_by")`
- `TARGET_FRONTMATTER_FIELDS = TARGET_FRONTMATTER_REQUIRED + TARGET_FRONTMATTER_OPTIONAL`
- `TARGET_SECTIONS_REQUIRED = ("Problem", "Next Action", "Change History")`
- `TARGET_STATUSES = ("open", "in_progress", "done", "wontfix")`
- `TARGET_PRIORITIES = ("high", "normal", "low")`
- `TARGET_CANDIDATE_ACTIONS = ("create", "update", "done", "wontfix", "reopen", "correct")`
- `validate_target_ticket_file(path: Path) -> TargetTicketValidation`
- `validate_target_ticket_text(path: Path, text: str) -> TargetTicketValidation`

Validation must be deterministic and mechanical. It must not score ticket semantics or decide priority.

- [ ] **Step 3: De-duplicate docs-contract vocabulary**

In `test_docs_contract.py`, replace local target vocabulary tuples such as `TARGET_TICKET_FIELDS`, `TARGET_TICKET_STATUSES`, and `TARGET_TICKET_PRIORITIES` with imports from `scripts.ticket_target_schema`.

Expected import shape:

```python
from scripts.ticket_target_schema import (
    TARGET_CANDIDATE_ACTIONS,
    TARGET_FRONTMATTER_FIELDS,
    TARGET_PRIORITIES,
    TARGET_STATUSES,
    validate_target_ticket_file,
)
```

Docs-contract assertions must compare against those imported tuples so docs/static tests and source validation cannot drift apart.

- [ ] **Step 4: Run focused target-schema tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_target_schema.py tests/test_docs_contract.py -q
```

Expected: PASS.

## Task 2: Normalize Current `docs/tickets/`

**Files:**

- Move: seven current `docs/tickets/2026-*.md` files to ID-only target filenames listed in the inventory table.
- Modify: the moved ticket files.
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Move files with `git mv`**

Run:

```bash
git mv docs/tickets/2026-05-08-add-sandbox-integration-coverage-for-guarded.md docs/tickets/T-20260508-01.md
git mv docs/tickets/2026-05-08-classify-and-harden-turbo-mode-migration.md docs/tickets/T-20260508-02.md
git mv docs/tickets/2026-05-16-harden-active-write-status-partition-regression-gate-pr.md docs/tickets/T-20260516-01.md
git mv docs/tickets/2026-05-17-validate-active-write-reservation-status-boundary.md docs/tickets/T-20260517-01.md
git mv docs/tickets/2026-05-18-serialize-parallel-agent-ticket-creation.md docs/tickets/T-20260518-01.md
git mv docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md docs/tickets/T-20260518-02.md
git mv docs/tickets/2026-05-26-resolve-slice-1a-plan-commit-boundary.md docs/tickets/T-20260526-01.md
```

- [ ] **Step 2: Rewrite each ticket to target schema**

For every moved ticket:

- remove the H1 title line;
- replace fenced YAML with YAML frontmatter;
- add frontmatter `title` from the old H1;
- keep only `id`, `title`, `status`, `priority`, `tags`, `related_paths`, and `blocked_by`;
- map `medium` to `normal`;
- keep `high` as `high`;
- preserve old `Problem` prose byte-for-byte where possible;
- preserve old optional prose sections such as `Acceptance Criteria`, `Key Files`, `Captured Request`, `Trigger`, `Required Scope`, and `Hard Stop`;
- add `## Next Action` where missing;
- add `## Change History` with one migration entry using actor `migration` and reason `Normalized ticket into ADR 0006 schema.`;
- do not carry old `source`, `contract_version`, `blocks`, `component`, or confidence fields forward as comments.

Use this default `Next Action` rule:

- `done` ticket: `No next action; ticket is already done.`
- open ticket with existing `Acceptance Criteria`: `Complete the first unchecked acceptance criterion, then update this ticket with the result.`
- `T-20260518-02`: `Run the activation-capable runtime-readiness work under an explicit runtime-proof lane.`
- `T-20260526-01`: keep the existing `Next Action` text.

- [ ] **Step 3: Add repo-ticket normalization guard**

In `test_docs_contract.py`, add a test that scans `REPO_ROOT / "docs" / "tickets"` and validates every active `*.md` with `validate_target_ticket_file()`.

Expected assertion shape:

```python
def test_repo_ticket_records_are_target_normalized() -> None:
    tickets_dir = REPO_ROOT / "docs" / "tickets"
    failures = []
    for path in sorted(tickets_dir.glob("*.md")):
        result = validate_target_ticket_file(path)
        if not result.ok:
            failures.append(f"{path}: {result.error}")
    assert failures == []
```

- [ ] **Step 4: Verify no noncanonical Ticket storage remains**

Run:

```bash
find docs -maxdepth 4 -type d -iname '*ticket*' -print
find docs/tickets -maxdepth 2 -type f -print
```

Expected: only `docs/tickets` for Ticket storage, and seven ID-only `docs/tickets/T-*.md` files.

## Task 3: Add Diagnostic Cutover Inventory And Normal-Surface Rejection

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_read.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_parse.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_paths.py` for invalid active-ticket path/error plumbing.
- Create: `plugins/turbo-mode/ticket/scripts/ticket_cutover_inventory.py`
- Create: `plugins/turbo-mode/ticket/tests/test_cutover_inventory.py`
- Modify: `plugins/turbo-mode/ticket/tests/support/builders.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_read.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_parse.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_migration.py`
- Modify read-path-coupled tests that use `make_ticket()`, `list_tickets()`, `find_ticket_by_id()`, or `parse_ticket()` with normal fixtures:
  - `plugins/turbo-mode/ticket/tests/test_capture_contract.py`
  - `plugins/turbo-mode/ticket/tests/test_blocker_resolution.py`
  - `plugins/turbo-mode/ticket/tests/test_ux.py`
  - `plugins/turbo-mode/ticket/tests/test_render.py`
  - `plugins/turbo-mode/ticket/tests/test_capture.py`
  - `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
  - `plugins/turbo-mode/ticket/tests/test_dedup_persistence.py`
  - `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
  - `plugins/turbo-mode/ticket/tests/test_review_findings.py`
  - `plugins/turbo-mode/ticket/tests/test_execute.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
  - `plugins/turbo-mode/ticket/tests/test_plan.py`

- [ ] **Step 1: Add diagnostic inventory tests**

Add tests proving `ticket_cutover_inventory.py` can inspect invalid legacy files and report:

- source path;
- current ID;
- proposed target path;
- metadata container;
- unknown keys;
- status/priority mapping need;
- missing required sections;
- optional sections to preserve;
- blocker list.

Expected state for a fixture matching current legacy shape: `blocked` or `ready_to_apply` depending on whether the fixture has deterministic `Next Action` and `Change History` mapping.

- [ ] **Step 2: Split normal and legacy test builders**

Change `tests/support/builders.py` so `make_ticket()` emits target-normalized tickets by default:

- normal fixtures must use ID-only filenames. Change `make_ticket()` to ignore legacy slug filename arguments and write to `f"{id}.md"`. Move non-ID filename fixtures into `make_legacy_ticket_for_cutover()` or tests that explicitly assert invalid-state filename rejection;
- the default helper body must use YAML frontmatter, no H1, target frontmatter keys only, `priority: normal` by default, and required `Problem`, `Next Action`, and `Change History` sections;
- add a separate helper such as `make_legacy_ticket_for_cutover()` for fenced-YAML fixtures used only by `test_cutover_inventory.py`, diagnostic parse tests, or migration tests;
- keep generation-specific helpers such as `make_gen1_ticket()` through `make_gen4_ticket()` only for cutover inventory or diagnostic migration tests.

Expected default fixture shape:

```python
content = textwrap.dedent(f"""\
    ---
    id: {id}
    title: {title}
    status: {status}
    priority: {priority}
    tags: {tags}
    related_paths: {related_paths}
    blocked_by: {blocked_by}
    ---

    ## Problem
    {problem}

    ## Next Action
    Continue work on this ticket.

    ## Change History
    - 2026-06-02T00:00:00Z | migration | Test fixture normalized to target schema.
""")
```

- [ ] **Step 3: Make normal reads strict**

Change normal `list_tickets()` / `find_ticket_by_id()` behavior so active ticket files are target-validated by default. Invalid active files must produce an explicit invalid-state error that CLI entrypoints render as JSON with target state `invalid_state`.

Do not silently skip invalid active files.

- [ ] **Step 4: Preserve diagnostic parsing**

Keep legacy fenced-YAML parsing available only through diagnostic/cutover inventory helpers. Name the helper accordingly, for example `parse_legacy_ticket_for_cutover()`, so normal product surfaces cannot accidentally rely on it as valid ticket authority.

- [ ] **Step 5: Resolve migration-suite ownership**

Repoint `test_migration.py` to the diagnostic/cutover parser or delete obsolete direct-normal-parser assertions and replace them with equivalent `test_cutover_inventory.py` coverage. The retained tests must prove legacy generations can be inventoried and mapped, not that `parse_ticket()` accepts them as normal active tickets.

Expected assertion shape:

```python
inventory = inspect_legacy_ticket_for_cutover(path)
assert inventory.current_id == "handoff-chain-viz"
assert inventory.metadata_container == "fenced_yaml"
assert inventory.proposed_target_path.name.startswith("T-")
```

- [ ] **Step 6: Verify strict read behavior and fixture blast radius**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_target_schema.py \
  tests/test_cutover_inventory.py \
  tests/test_read.py \
  tests/test_parse.py \
  tests/test_migration.py \
  tests/test_capture_contract.py \
  tests/test_blocker_resolution.py \
  tests/test_ux.py \
  tests/test_render.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_dedup_persistence.py \
  tests/test_engine_policy.py \
  tests/test_review_findings.py \
  tests/test_execute.py \
  tests/test_autonomy_corrections.py \
  tests/test_plan.py \
  -q
```

Expected: PASS.

Then run:

```bash
rg -n "```ya?ml|contract_version|priority: medium|status: blocked|^# T-" plugins/turbo-mode/ticket/tests/support plugins/turbo-mode/ticket/tests/test_read.py plugins/turbo-mode/ticket/tests/test_parse.py plugins/turbo-mode/ticket/tests/test_migration.py
```

Expected: matches appear only in diagnostic/cutover fixture helpers or tests explicitly named as legacy inventory tests.

## Task 4: Normalize Target Write Persistence

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_render.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_id.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_envelope.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_validate.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_render.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_id.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_envelope.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Write write-path schema tests**

Add or update tests proving the normal write path rejects old storage fields and values:

```python
def test_validate_fields_rejects_deprecated_priority_and_status_values() -> None:
    assert "priority" in "; ".join(validate_fields({"priority": "medium"}))
    assert "priority" in "; ".join(validate_fields({"priority": "critical"}))
    assert "status" in "; ".join(validate_fields({"status": "blocked"}))
```

Add separate tests proving:

- `validate_fields({"priority": "normal"})` passes;
- `validate_fields({"priority": "high"})` and `validate_fields({"priority": "low"})` pass;
- `validate_fields({"blocks": ["T-20260508-01"]})` fails;
- `validate_fields({"source": {"type": "ad-hoc", "ref": "", "session": "s"}})` fails on normal write input;
- `validate_fields({"capture_confidence": "high"})`, `validate_fields({"component": "ticket"})`, `validate_fields({"contract_version": "1.0"})`, and `validate_fields({"defer": {"active": True}})` fail.

- [ ] **Step 2: Write render and filename tests**

Update `test_render.py` and `test_id.py` so normal rendered tickets and filenames match the target:

```python
def test_render_ticket_emits_target_frontmatter_without_legacy_storage() -> None:
    text = render_ticket(
        id="T-20260602-01",
        title="Target write",
        status="open",
        priority="normal",
        problem="Persist the target shape.",
        next_action="Run the focused write-path tests.",
        change_history_entry="- 2026-06-02T00:00:00Z | codex | Created target ticket.",
    )

    assert text.startswith("---\n")
    assert "\n---\n\n## Problem\n" in text
    assert "```yaml" not in text
    assert "# T-20260602-01:" not in text
    assert "date:" not in text
    assert "created_at:" not in text
    assert "source:" not in text
    assert "contract_version:" not in text
```

```python
def test_build_filename_returns_id_only_filename() -> None:
    assert build_filename("T-20260602-01", "Ignored title") == "T-20260602-01.md"
```

If collision handling remains needed, it must fail with `invalid_state` rather than inventing `-2` suffixes for active target tickets. ID allocation prevents collisions; filename suffixes are legacy behavior.

- [ ] **Step 3: Write engine and envelope persistence tests**

Update engine/gateway/envelope tests to prove:

- create defaults to `priority: normal`;
- engine create writes `docs/tickets/T-YYYYMMDD-NN.md`, not a title-slug filename;
- created files pass `validate_target_ticket_file()`;
- envelope-created fields use target priorities only and default to `normal`;
- envelope mapping does not persist `source`, `defer`, `effort`, or `key_file_paths` as frontmatter fields;
- gateway autonomous create defaults to `normal`, not `medium`.

Expected assertion shape:

```python
response = _execute_create(
    {"title": "Target create", "problem": "Target create problem."},
    session_id="test-session",
    request_origin="user",
    tickets_dir=tmp_tickets,
)
assert response.state in {"ok", "ok_create"}
ticket_path = Path(response.data["ticket_path"])
assert ticket_path.name == f"{response.ticket_id}.md"
assert validate_target_ticket_file(ticket_path).ok is True
assert "priority: normal" in ticket_path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Implement target write validation**

Change `ticket_validate.py` to import target vocabulary from `ticket_target_schema` and reject old storage fields on normal writes. Validation may accept transient section inputs used to compose the Markdown body, but it must reject old frontmatter/storage keys.

Target accepted input fields:

- frontmatter writes: `title`, `status`, `priority`, `tags`, `related_paths`, `blocked_by`;
- section writes: `problem`, `next_action`, `change_history_entry`;
- optional prose section writes only when explicitly targeted by candidate contract after Task 5: `acceptance_criteria`, `verification`, `context`, `prior_investigation`, `approach`, `decisions_made`, `related`.

Explicitly reject normal-write keys:

- `date`
- `created_at`
- `effort`
- `source`
- `capture_confidence`
- `capture_source`
- `refinement_status`
- `component`
- `blocks`
- `contract_version`
- `defer`
- `key_file_paths`
- `key_files`

- [ ] **Step 5: Implement target rendering and ID-only filenames**

Change `render_ticket()` so normal persistence:

- emits YAML frontmatter between `---` fences, not fenced YAML;
- omits duplicated H1 headings;
- writes only target frontmatter keys;
- writes `## Problem`, `## Next Action`, and `## Change History` in order;
- preserves optional prose sections only when supplied;
- requires a Change History entry string or a `ChangeHistoryEntry` render result from Task 7-compatible helpers.

Change `build_filename()` to return `f"{ticket_id}.md"` for target IDs. If the target file exists, return an `invalid_state`/validation failure through the caller instead of appending a suffix.

Change `allocate_id()` scanning so it can read target YAML frontmatter for current tickets and may use the cutover helper for legacy diagnostic scans only.

- [ ] **Step 6: Implement engine/gateway/envelope create defaults**

Change engine and gateway create paths so:

- default priority is `normal`;
- create passes target-shaped fields to `render_ticket()`;
- persisted target path is ID-only;
- `ticket_envelope.py` accepts only `high`, `normal`, and `low` in `suggested_priority`;
- envelope default priority is `normal`;
- envelope mapping does not carry old `source`, `defer`, `effort`, `key_files`, or `key_file_paths` into target frontmatter. If those facts remain useful, place them in optional prose sections or diagnostic output, not persisted target frontmatter.

- [ ] **Step 7: Verify write-path normalization**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_validate.py \
  tests/test_render.py \
  tests/test_id.py \
  tests/test_execute.py \
  tests/test_engine_gateway.py \
  tests/test_envelope.py \
  tests/test_target_schema.py \
  tests/test_docs_contract.py \
  -q
```

Expected: PASS.

Then run:

```bash
rg -n "priority: (medium|critical)|status: blocked|^blocks:|^source:|^date:|^created_at:|^contract_version:|^capture_confidence:|^component:|```ya?ml|^# T-" plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_render.py plugins/turbo-mode/ticket/tests/test_id.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_envelope.py
```

Expected: matches appear only in tests proving legacy rejection or diagnostic/cutover behavior.

## Task 5: Adopt Target Candidate Mutation Contract

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Write candidate-contract tests**

Tests must prove:

- accepted candidate keys are exactly `action`, `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`;
- accepted `action` values are exactly `create`, `update`, `done`, `wontfix`, `reopen`, and `correct`;
- `ticket_id` is required except for create;
- `target.fields` and `target.sections` are lists of target field/section names;
- `proposed_change` keys match the target names;
- non-create writes require `expected_ticket_fingerprint`;
- `evidence_summary` is a one-line string;
- unknown fields reject with `invalid_state`.
- old action values `close`, `correction`, `reprioritize`, `blocker_edit`, `stale_cleanup`, `refine`, `archive`, `delete`, and `history_repair` are not accepted as normal candidate actions after this task. `done` and `wontfix` replace `close`; `correct` replaces `correction`.

- [ ] **Step 2: Update candidate dataclasses and identity**

Replace old `CandidateMutation` fields with target-shaped fields. Compute identity from canonical candidate content plus the live target fingerprint. Callers do not supply mutation IDs as authority.

Target dataclass shape:

```python
@dataclass(frozen=True, slots=True)
class CandidateMutation:
    action: str
    ticket_id: str | None
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    expected_ticket_fingerprint: str | None
    evidence_summary: str
```

`CandidateTarget` should hold only `fields: tuple[str, ...]` and `sections: tuple[str, ...]`, with names validated against target frontmatter fields and allowed section names from `ticket_target_schema.py`.

- [ ] **Step 3: Update discovery**

`ticket_candidate_discovery.py` may continue to extract deterministic candidates from turn context, but normal structured candidates must reject unknown fields and old action values. Diagnostic inventory can still report old shapes.

- [ ] **Step 4: Update gateway validation**

Gateway validation must compare action, ticket ID, target fields/sections, proposed change, expected fingerprint, and candidate identity before writing.

Map legacy gateway dispatch only at the internal engine boundary:

- candidate `done` and `wontfix` may dispatch to the retained internal close helper while normal response state remains target-shaped;
- candidate `correct` is an update or terminal correction with a `Corrects:` fact in Change History after Task 7;
- no normal candidate may expose `close`, `correction`, `reprioritize`, `blocker_edit`, `stale_cleanup`, or `refine`.

- [ ] **Step 5: Verify candidate-contract selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_candidate_discovery.py tests/test_mutation_identity.py tests/test_autonomy_runtime.py tests/test_autonomy.py tests/test_engine_gateway.py tests/test_autonomy_integration_v1.py -q
```

Expected: PASS.

## Task 6: Collapse Normal Result States

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_workflow.py` or delete if Task 8 removes it first.
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_response_models.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Add state-envelope tests**

Normal mutation results must use only:

- `ok`
- `blocked`
- `needs_discussion`
- `invalid_state`
- `no_change`

Old states such as `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `policy_blocked`, `need_fields`, `preflight_failed`, `dependency_blocked`, and `invalid_transition` may remain only in diagnostic/deprecated surfaces until those surfaces are removed.

Tests must also prove:

- `EngineResponse._OK_STATES` contains only `ok` for normal success after this task, or old ok states are isolated behind explicitly named diagnostic response classes;
- gateway normal output maps old internal success helpers to `ok`;
- old failure states map to `blocked`, `needs_discussion`, `invalid_state`, or `no_change`;
- `ticket_autonomy.py` no longer emits normal summary state `ticket_update_blocked`;
- `ticket_autonomy_runtime.py` no longer uses `RuntimeDecisionKind.TICKET_UPDATE_BLOCKED` as a normal public state. If a private internal decision remains, normal output must map it to `blocked`.

- [ ] **Step 2: Normalize gateway result envelopes**

Map old engine outcomes into target mechanical states at the normal product boundary. Preserve useful validation details in `data`, not in new semantic state names.

Do not leave old success names in `_OK_STATES` unless the old engine code is still constructing them before a gateway map. If old construction remains temporarily, the task must add a local translation helper and a test showing no normal CLI/gateway/autonomy surface returns the old state.

- [ ] **Step 3: Normalize autonomy and pending-summary state vocabulary**

Update `ticket_autonomy.py`, `ticket_autonomy_runtime.py`, and `ticket_turn_batch.py` so old public states are removed or private-only:

- `ticket_update_blocked` -> `blocked` in normal summaries;
- `discussion_required` -> `needs_discussion` in normal summaries;
- `skipped` with no write -> `no_change`;
- `applied`, `ticket_written`, and old ok variants -> `ok` at normal output boundaries.

Private pending-summary events may keep compact mechanical recovery facts only when they match the May 30 control doc's private operation-log facts. If a private token remains for recovery, document it in code as private and keep it out of normal response docs.

- [ ] **Step 4: Verify state selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_response_models.py tests/test_engine_gateway.py tests/test_autonomy_runtime.py tests/test_autonomy.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py -q
```

Expected: PASS.

Then run:

```bash
rg -n "ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|policy_blocked|need_fields|preflight_failed|dependency_blocked|invalid_transition|ticket_update_blocked|discussion_required|skipped" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: matches are absent from normal product surfaces or explicitly classified as diagnostic/private/deprecated in comments and tests.

## Task 7: Update Change History Grammar

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_change_history.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`

- [ ] **Step 1: Replace controlled label enum**

Delete `ChangeHistoryLabel`. Replace it with actor validation:

- `codex`
- `user-approved`
- `migration`

Allow other actor strings only if they are line-shaped and do not encode action labels. Reject known old labels `auto-create`, `auto-update`, `auto-blocker`, `auto-close`, `auto-reopen`, `correction`, and `discussion-approved`.

- [ ] **Step 2: Remove `prior_commit`**

Replace `prior_commit` rendering with optional `Corrects: <reference>.` support only.

- [ ] **Step 3: Update gateway/core entry construction**

Update `ticket_engine_gateway.py` and `ticket_engine_core.py` so autonomous writes construct target Change History entries without importing `ChangeHistoryLabel`.

Actor derivation:

- `codex` for autonomous `agent_primary` writes;
- `user-approved` only for `discussion_only` follow-up writes tied to a matching approved candidate identity;
- `migration` only for Task 2 ticket-file cutover entries.

Action names belong in the reason prose, not the actor. For example, autonomous create should render like:

```text
- 2026-06-02T00:00:00Z | codex | Created ticket from candidate evidence.
```

Corrections use ordinary actor grammar and optional `Corrects: <reference>.` prose:

```text
- 2026-06-02T00:00:00Z | codex | Corrected priority after stale evidence. Corrects: mutation abc123.
```

- [ ] **Step 4: Verify Change History selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_change_history.py tests/test_target_schema.py tests/test_engine_gateway.py tests/test_execute.py -q
```

Expected: PASS.

Then run:

```bash
rg -n "ChangeHistoryLabel|auto-create|auto-update|auto-blocker|auto-close|auto-reopen|discussion-approved|Prior commit|prior_commit" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: matches are absent except legacy/cutover rejection tests.

## Task 8: Remove Deprecated Workflow Mutation Paths

**Files:**

- Delete or narrow: `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- Delete or narrow: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Delete or narrow: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify/delete tests preserving prepare/execute behavior:
  - `tests/test_workflow.py`
  - `tests/test_workflow_cli.py`
  - `tests/test_workflow_execute.py`
  - `tests/test_workflow_recovery.py`
  - `tests/test_capture.py`
  - `tests/test_update_refinement.py`
  - `tests/test_entrypoints.py`
  - `tests/test_doctor.py`

- [ ] **Step 1: Re-run prepare/execute inventory**

Run:

```bash
rg -n "ready_to_execute|ticket_capture.py prepare|ticket_capture.py execute|ticket_update.py prepare|ticket_update.py execute|run_workflow\\(\"prepare\"|run_workflow\\(\"execute\"|retry_preview|cleanup_stale_preview|stale_plan" \
  plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills
```

Expected: every hit is assigned to deletion, diagnostic-only retention, or active docs update.

- [ ] **Step 2: Delete normal prepare/execute product paths**

Remove or make unavailable normal prepare/execute mutation paths. If a diagnostic stale-payload cleanup path remains, it must be reachable only from `ticket_doctor.py` or a clearly diagnostic command and must have a sunset condition.

- [ ] **Step 3: Add or apply the stale-payload sunset**

If `ticket_doctor.py clean-stale-payloads` remains, narrow it to diagnostic cleanup for old `.codex/ticket-tmp/` payload residue only and add a source-visible sunset. Use this exact boundary:

- normal Ticket mutation docs and skills must not present stale-payload cleanup as a current product workflow;
- the command may remain only as explicit maintenance for pre-cutover payload residue;
- once `ticket_capture.py`, `ticket_update.py`, and `ticket_workflow.py` normal prepare/execute paths are removed, `ticket_doctor.py diagnose` may report stale payload residue but must not recommend rerunning a prepare/execute workflow;
- `test_doctor.py` and `test_docs_contract.py` must fail if `cleanup_stale_preview`, `retry_preview`, or `ready_to_execute` appears in target/current product sections.

If the executor can prove no source path still creates old stale payloads, prefer deleting `clean-stale-payloads` in this task rather than preserving the diagnostic command.

- [ ] **Step 4: Keep read/query/report surfaces**

Do not delete `read-ticket`, backlog triage, doctor diagnostics, or explicit runtime activation unless they directly preserve deprecated mutation semantics.

- [ ] **Step 5: Verify old paths are not normal product behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py tests/test_hook.py tests/test_read.py tests/test_doctor.py tests/test_entrypoints.py -q
```

Expected: PASS.

## Task 9: Align Active Docs, Skills, And Tests

**Files:**

- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Patch active docs to match source**

Docs must say:

- current repo tickets are normalized;
- normal source surfaces reject non-normalized active tickets;
- normal writes persist ID-only `T-YYYYMMDD-NN.md` files with YAML frontmatter and target-only frontmatter keys;
- diagnostic/cutover inventory can inspect invalid old files;
- source exposes the target candidate mutation contract with actions exactly `create`, `update`, `done`, `wontfix`, `reopen`, and `correct`;
- source normal result envelopes expose only `ok`, `blocked`, `needs_discussion`, `invalid_state`, and `no_change`;
- Change History entries use actor prose grammar, not controlled labels;
- old prepare/execute workflow paths are removed or diagnostic-only with a sunset;
- installed runtime proof remains unclaimed.

- [ ] **Step 2: Strengthen docs-contract tests**

Add guards that fail if target/current sections present:

- fenced YAML as target ticket format;
- `medium`, `critical`, or `blocked` as target values;
- slug filenames, H1 title lines, `date`, `created_at`, `source`, `capture_confidence`, `component`, `contract_version`, `defer`, or `blocks` as target storage fields;
- `ticket_capture.py prepare`, `ticket_update.py prepare`, or `ready_to_execute` as normal product paths;
- `ok_create`, `ok_update`, `policy_blocked`, or `preflight_failed` as target result states;
- old Change History labels as valid target grammar.
- old candidate actions `close`, `correction`, `reprioritize`, `blocker_edit`, `stale_cleanup`, `refine`, `archive`, `delete`, or `history_repair` as normal candidate actions.

- [ ] **Step 3: Verify docs/static selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py -q
```

Expected: PASS.

## Task 10: Final Source/Repo Verification

**Files:**

- Verify: `docs/tickets/`
- Verify: `plugins/turbo-mode/ticket/`
- Verify: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Verify: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`

- [ ] **Step 1: Run Ticket suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff on changed Python paths**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
```

Expected: PASS.

- [ ] **Step 3: Run source/repo residue scans**

Run:

```bash
find docs -maxdepth 4 -type d -iname '*ticket*' -print
find docs/tickets -maxdepth 2 -type f -print
rg -n "ready_to_execute|ticket_capture.py prepare|ticket_capture.py execute|ticket_update.py prepare|ticket_update.py execute|retry_preview|cleanup_stale_preview|fenced YAML|capture_confidence|contract_version|ChangeHistoryLabel|auto-create|auto-update|auto-blocker|auto-close|auto-reopen|discussion-approved|ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|ticket_update_blocked|ticket_change_scope|commit_disposition" \
  docs/tickets plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills
rg -n "(^|[\"'`])component([\"'`]|:)" \
  docs/tickets plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills
rg -n "^```ya?ml|^# T-|^date:|^created_at:|^source:|^blocks:|^defer:|priority: (medium|critical)|status: blocked" \
  docs/tickets plugins/turbo-mode/ticket/tests/support
```

Expected: hits are either absent or explicitly classified as diagnostic/historical in active docs, diagnostic/cutover fixtures, or legacy rejection tests. No hit may present old behavior as target/current product authority. The final closeout must include the classified residue table when any match remains.

- [ ] **Step 4: Run markdown and diff checks**

Run:

```bash
git diff --check
git diff --stat
git status --short --branch
```

Expected: no whitespace errors; diff is scoped to the plan; no untracked generated residue except ignored local handoff/session state.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-06-02-ticket-adr-source-repo-satisfaction.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, with checkpoints after each commit boundary.

Before implementation, choose one execution option. Do not begin implementation edits from this plan without that cue.

## Self-Review

Spec coverage:

- Source/repo satisfaction is covered by Tasks 1 through 10.
- Runtime/cache proof is explicitly out of scope.
- Ticket normalization, strict normal-surface rejection, diagnostic inventory, write/persistence normalization, candidate contract, response envelope, Change History grammar, workflow removal, docs/tests, and final verification each have a task and stop conditions.

Placeholder scan:

- No placeholder tokens or unspecified test-writing steps remain.
- Where implementation must use the actual migration timestamp, the plan defines the actor and reason and validates ISO shape rather than hardcoding a stale timestamp.

Type consistency:

- `validate_target_ticket_file()` and `TargetTicketValidation` are introduced before use in docs-contract tests.
- Target ticket schema names match ADR 0006, and target candidate field/action names match the May 30 control doc.
- Result state names match the control doc.
