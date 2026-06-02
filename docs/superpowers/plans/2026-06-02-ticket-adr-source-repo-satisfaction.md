# Ticket ADR Source/Repo Satisfaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the local source/repo Ticket lane into honest satisfaction of ADR 0006 and the May 30 state-kernel control doc, without claiming installed runtime proof.

**Architecture:** This is a source/repo cutover plan, not a cache-refresh or live-runtime plan. It normalizes repo ticket records first, then makes normal Ticket product surfaces reject non-normalized active ticket files while leaving explicit diagnostic/cutover inventory able to explain invalid legacy files. After the repo records and schema boundary are stable, it collapses the candidate contract, response envelope, Change History grammar, and deprecated workflow machinery in coherent source commits.

**Tech Stack:** Python >=3.11, PyYAML, dataclasses, Markdown/YAML parsing, existing Ticket scripts, pytest, ruff, `git mv`, bytecode-safe `uv run` verification.

---

## Scope Check

This plan covers the source/repo finish line only.

In scope:

- Normalize the seven current `docs/tickets/*.md` records into ADR 0006 target schema and ID-only filenames.
- Prove no noncanonical Ticket storage remains under `docs/`.
- Add deterministic target-ticket validation and make normal Ticket read/mutation/product surfaces reject non-normalized active tickets after cutover.
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
ADR 0006 and the May 30 control doc are satisfied for the local source/repo lane: current ticket records are normalized, normal source surfaces reject non-normalized active tickets, active docs/tests no longer preserve old Ticket architecture as current behavior, and remaining runtime/cache proof is a separate unclaimed lane.
```

Do not use this claim until every verification gate in this plan passes.

## Live Inventory From 2026-06-02

Baseline checked in this session:

- Branch: `chore/ticket-runtime-first-rebaseline-adr`
- HEAD: `9479a985`
- Tracked worktree before this plan file: clean
- Installed runtime: not inspected
- Cache state: not inspected

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

Current schema/parser drift:

- `plugins/turbo-mode/ticket/scripts/ticket_parse.py` parses fenced YAML, applies legacy generations, normalizes old statuses, applies legacy defaults, and still includes `blocked`, `blocks`, `capture_confidence`, `component`, and `contract_version`.
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py` allows `critical`, `medium`, and `blocked`, and validates old capture/refinement/component fields.
- `plugins/turbo-mode/ticket/scripts/ticket_render.py` renders fenced YAML and old field order including `date`, `created_at`, `effort`, `source`, `capture_confidence`, `component`, `blocks`, and `contract_version`.
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
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` still stores repo context with branch/head and old pending-summary states such as `skipped`, `discussion_required`, `ticket_written`, `applied`, and `ticket_update_blocked`, while already rejecting old `commit_disposition`, `commit_hash`, `commit_reason`, and `ticket_change_scope` details.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, `ticket_workflow.py`, and tests still use states such as `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `policy_blocked`, `need_fields`, `preflight_failed`, `dependency_blocked`, and `invalid_transition`.

Current Change History drift:

- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py` uses `ChangeHistoryLabel` values `auto-create`, `auto-update`, `auto-blocker`, `auto-close`, `auto-reopen`, `correction`, and `discussion-approved`.
- `ChangeHistoryEntry` still has `prior_commit`, which is not target grammar.

Docs/tests state:

- README and `references/ticket-contract.md` already describe the target schema, target candidate contract, target result envelope, and target Change History grammar.
- They also preserve old surfaces as deprecated/diagnostic source facts. That is acceptable only until source removal finishes; the final source/repo closeout must not leave old behavior usable as normal product authority.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` already guards many target-doc sections and should be extended from docs-only target claims into source/repo guards after implementation.

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
- Deprecated prepare/execute behavior remains as a usable normal product path without a narrow diagnostic label and sunset condition.
- Target docs claim installed runtime success or cache refresh.

## Commit Boundaries

Use coherent commits by surface:

1. `docs(ticket): plan adr source repo satisfaction`
2. `test(ticket): add target ticket schema guards`
3. `docs(ticket): normalize repo ticket records`
4. `fix(ticket): reject non-normalized active ticket files`
5. `fix(ticket): adopt target candidate mutation contract`
6. `fix(ticket): collapse ticket response states`
7. `fix(ticket): update change history grammar`
8. `fix(ticket): remove deprecated workflow mutation paths`
9. `docs(ticket): align active ticket docs with source repo cutover`

If a later task exposes that two adjacent boundaries cannot pass independently, merge the commit boundary and state why in the closeout.

## Task 0: Reconfirm Inventory Before Edits

**Files:**

- Read: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `docs/tickets/*.md`
- Read: `plugins/turbo-mode/ticket/scripts/*.py`
- Read: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

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
rg -n "fenced YAML|closed-tickets|capture_confidence|component|contract_version|ready_to_execute|prepare|execute|classify_confidence|ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|auto-create|auto-update|discussion-approved|ticket_update_blocked|commit_disposition|ticket_change_scope" \
  plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references
```

Expected: hits are assignable to this plan, diagnostic/historical docs, or already-accepted target guards.

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
- `TARGET_STATUSES = ("open", "in_progress", "done", "wontfix")`
- `TARGET_PRIORITIES = ("high", "normal", "low")`
- `validate_target_ticket_file(path: Path) -> TargetTicketValidation`
- `validate_target_ticket_text(path: Path, text: str) -> TargetTicketValidation`

Validation must be deterministic and mechanical. It must not score ticket semantics or decide priority.

- [ ] **Step 3: Run focused target-schema tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_target_schema.py -q
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
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_paths.py` if needed for path error plumbing.
- Create: `plugins/turbo-mode/ticket/scripts/ticket_cutover_inventory.py`
- Create: `plugins/turbo-mode/ticket/tests/test_cutover_inventory.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_read.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_parse.py`

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

- [ ] **Step 2: Make normal reads strict**

Change normal `list_tickets()` / `find_ticket_by_id()` behavior so active ticket files are target-validated by default. Invalid active files must produce an explicit invalid-state error that CLI entrypoints render as JSON with target state `invalid_state`.

Do not silently skip invalid active files.

- [ ] **Step 3: Preserve diagnostic parsing**

Keep legacy fenced-YAML parsing available only through diagnostic/cutover inventory helpers. Name the helper accordingly, for example `parse_legacy_ticket_for_cutover()`, so normal product surfaces cannot accidentally rely on it as valid ticket authority.

- [ ] **Step 4: Verify strict read behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_target_schema.py tests/test_cutover_inventory.py tests/test_read.py tests/test_parse.py -q
```

Expected: PASS.

## Task 4: Adopt Target Candidate Mutation Contract

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
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
- `ticket_id` is required except for create;
- `target.fields` and `target.sections` are lists of target field/section names;
- `proposed_change` keys match the target names;
- non-create writes require `expected_ticket_fingerprint`;
- `evidence_summary` is a one-line string;
- unknown fields reject with `invalid_state`.

- [ ] **Step 2: Update candidate dataclasses and identity**

Replace old `CandidateMutation` fields with target-shaped fields. Compute identity from canonical candidate content plus the live target fingerprint. Callers do not supply mutation IDs as authority.

- [ ] **Step 3: Update discovery**

`ticket_candidate_discovery.py` may continue to extract deterministic candidates from turn context, but normal structured candidates must reject unknown fields. Diagnostic inventory can still report old shapes.

- [ ] **Step 4: Update gateway validation**

Gateway validation must compare action, ticket ID, target fields/sections, proposed change, expected fingerprint, and candidate identity before writing.

- [ ] **Step 5: Verify candidate-contract selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_candidate_discovery.py tests/test_mutation_identity.py tests/test_autonomy_runtime.py tests/test_engine_gateway.py tests/test_autonomy_integration_v1.py -q
```

Expected: PASS.

## Task 5: Collapse Normal Result States

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_workflow.py` or delete if Task 7 removes it first.
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Modify: response-state tests under `plugins/turbo-mode/ticket/tests/`.

- [ ] **Step 1: Add state-envelope tests**

Normal mutation results must use only:

- `ok`
- `blocked`
- `needs_discussion`
- `invalid_state`
- `no_change`

Old states such as `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `policy_blocked`, `need_fields`, `preflight_failed`, `dependency_blocked`, and `invalid_transition` may remain only in diagnostic/deprecated surfaces until those surfaces are removed.

- [ ] **Step 2: Normalize gateway result envelopes**

Map old engine outcomes into target mechanical states at the normal product boundary. Preserve useful validation details in `data`, not in new semantic state names.

- [ ] **Step 3: Verify state selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_response_models.py tests/test_engine_gateway.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py -q
```

Expected: PASS.

## Task 6: Update Change History Grammar

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_change_history.py`
- Modify: any gateway/runtime write tests that assert old labels.

- [ ] **Step 1: Replace controlled label enum**

Delete `ChangeHistoryLabel`. Replace it with actor validation:

- `codex`
- `user-approved`
- `migration`

Allow other actor strings only if they are line-shaped and do not encode action labels. Reject known old labels `auto-create`, `auto-update`, `auto-blocker`, `auto-close`, `auto-reopen`, `correction`, and `discussion-approved`.

- [ ] **Step 2: Remove `prior_commit`**

Replace `prior_commit` rendering with optional `Corrects: <reference>.` support only.

- [ ] **Step 3: Verify Change History selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_change_history.py tests/test_target_schema.py -q
```

Expected: PASS.

## Task 7: Remove Deprecated Workflow Mutation Paths

**Files:**

- Delete or narrow: `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- Delete or narrow: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Delete or narrow: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify/delete tests preserving prepare/execute behavior:
  - `tests/test_workflow.py`
  - `tests/test_workflow_cli.py`
  - `tests/test_workflow_execute.py`
  - `tests/test_workflow_recovery.py`
  - `tests/test_capture.py`
  - `tests/test_update_refinement.py`
  - `tests/test_entrypoints.py`

- [ ] **Step 1: Re-run prepare/execute inventory**

Run:

```bash
rg -n "ready_to_execute|ticket_capture.py prepare|ticket_capture.py execute|ticket_update.py prepare|ticket_update.py execute|run_workflow\\(\"prepare\"|run_workflow\\(\"execute\"|retry_preview|cleanup_stale_preview|stale_plan" \
  plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills
```

Expected: every hit is assigned to deletion, diagnostic-only retention, or active docs update.

- [ ] **Step 2: Delete normal prepare/execute product paths**

Remove or make unavailable normal prepare/execute mutation paths. If a diagnostic stale-payload cleanup path remains, it must be reachable only from `ticket_doctor.py` or a clearly diagnostic command and must have a sunset condition.

- [ ] **Step 3: Keep read/query/report surfaces**

Do not delete `read-ticket`, backlog triage, doctor diagnostics, or explicit runtime activation unless they directly preserve deprecated mutation semantics.

- [ ] **Step 4: Verify old paths are not normal product behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py tests/test_hook.py tests/test_read.py tests/test_doctor.py -q
```

Expected: PASS.

## Task 8: Align Active Docs, Skills, And Tests

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
- diagnostic/cutover inventory can inspect invalid old files;
- source exposes the target candidate mutation contract;
- old prepare/execute workflow paths are removed or diagnostic-only with a sunset;
- installed runtime proof remains unclaimed.

- [ ] **Step 2: Strengthen docs-contract tests**

Add guards that fail if target/current sections present:

- fenced YAML as target ticket format;
- `medium`, `critical`, or `blocked` as target values;
- `capture_confidence`, `component`, `contract_version`, or `blocks` as target fields;
- `ticket_capture.py prepare`, `ticket_update.py prepare`, or `ready_to_execute` as normal product paths;
- `ok_create`, `ok_update`, `policy_blocked`, or `preflight_failed` as target result states;
- old Change History labels as valid target grammar.

- [ ] **Step 3: Verify docs/static selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py -q
```

Expected: PASS.

## Task 9: Final Source/Repo Verification

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
rg -n "ready_to_execute|ticket_capture.py prepare|ticket_update.py prepare|fenced YAML|capture_confidence|component|contract_version|auto-create|auto-update|discussion-approved|ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|ticket_update_blocked|ticket_change_scope|commit_disposition" \
  docs/tickets plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills
```

Expected: hits are either absent or explicitly classified as diagnostic/historical in active docs. No hit may present old behavior as target/current product authority.

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

- Source/repo satisfaction is covered by Tasks 1 through 9.
- Runtime/cache proof is explicitly out of scope.
- Ticket normalization, strict normal-surface rejection, diagnostic inventory, candidate contract, response envelope, Change History grammar, workflow removal, docs/tests, and final verification each have a task and stop conditions.

Placeholder scan:

- No placeholder tokens or unspecified "write tests for the above" steps remain.
- Where implementation must use the actual migration timestamp, the plan defines the actor and reason and validates ISO shape rather than hardcoding a stale timestamp.

Type consistency:

- `validate_target_ticket_file()` and `TargetTicketValidation` are introduced before use in docs-contract tests.
- Target candidate field names match ADR 0006 and the May 30 control doc.
- Result state names match the control doc.
