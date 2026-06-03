# Ticket ADR Source/Repo Satisfaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Task 0 and Task 1 may be handled as separate setup/checkpoint work. Tasks 2-9 are one source/repo cutover execution unit unless a full Ticket-suite gate proves a smaller boundary is independently green. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the local source/repo Ticket lane into honest satisfaction of ADR 0006 and the May 30 state-kernel control doc, without claiming installed runtime proof.

**Architecture:** This is a source/repo cutover plan, not a cache-refresh or live-runtime plan. It adds target schema guards first, then normalizes repo ticket records and source behavior together. Tasks 2-9 run as one atomic source/repo cutover band unless an intermediate boundary passes the full Ticket suite and residue gates; Task 2 cannot be a standalone commit because it rewrites repo tickets to frontmatter before Task 3 teaches normal readers that shape. Shared ticket records, read/write, candidate, result-state, Change History, hook-guard, ingest, and workflow surfaces are too coupled for narrow per-task green claims.

**Tech Stack:** Python >=3.11, PyYAML, dataclasses, Markdown/YAML parsing, existing Ticket scripts, pytest, ruff, `git mv`, bytecode-safe `uv run` verification.

---

## Scope Check

This plan covers the source/repo finish line only.

In scope:

- Normalize the seven current `docs/tickets/*.md` records into ADR 0006 target schema and ID-only filenames.
- Prove no noncanonical Ticket storage remains under `docs/`.
- Add deterministic target-ticket validation and make normal Ticket read/mutation/product surfaces reject non-normalized active tickets after cutover.
- Normalize read/write/persistence surfaces so `ParsedTicket.date` is derived from the target ID, `validate_fields()`, `render_ticket()`, ID filename helpers, engine create/update/defaults, gateway create defaults, and envelope-to-ticket mapping cannot persist old ticket shapes.
- Keep explicit diagnostic/cutover inventory able to inspect invalid files and report why they are invalid during the cutover, with an explicit sunset for legacy-generation parsing after normalized records and strict target validation are in place.
- Move the live source candidate contract toward `action`, `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`, with unknown-field rejection.
- Collapse normal result states toward `ok`, `blocked`, `needs_discussion`, `invalid_state`, and `no_change`.
- Replace controlled `Change History` labels with the target dated prose grammar.
- Delete deprecated prepare/execute/workflow architecture unless a narrow diagnostic/cutover use remains with a sunset condition.
- Tighten hook allowlists, low-level stage/runner retention, `ingest`, and read-only hygiene candidate surfaces so removed mutation vocabulary cannot survive as source drift.
- Remove or explicitly demote `closed-tickets/` archive writes so closed tickets stay canonical under `docs/tickets/`.
- Update active README, contract, changelog, plugin metadata, skills, and docs-contract tests so old behavior is not presented as target authority.

Out of scope:

- Installed cache refresh under `/Users/jp/.codex/plugins/cache`.
- Runtime inventory through `plugin/read`, `plugin/list`, `skills/list`, `hooks/list`, or live hook smokes.
- Publishing, pushing, or PR creation.
- Updating external references to old ticket paths outside `docs/tickets/`; this plan reports them for a separate explicit follow-up.
- Long-term archival policy beyond proving closed tickets stay canonical while represented as `status: done` or `status: wontfix`.

Closeout claim for this plan:

```text
ADR 0006 and the May 30 control doc are satisfied for the local source/repo lane: current ticket records are normalized, normal source surfaces reject non-normalized active tickets, normal writes persist only target-shaped ID-only records, hook and runner source no longer preserve removed mutation workflow as normal behavior, active docs/tests no longer preserve old Ticket architecture as current behavior, and remaining runtime/cache proof is a separate unclaimed lane.
```

Do not use this claim until every verification gate in this plan passes.

## Live Inventory From 2026-06-02

Baseline checked in this session:

- Branch: `chore/ticket-runtime-first-rebaseline-adr`
- HEAD before this revision: `7a664b69`
- Tracked worktree before this plan file: clean
- Installed runtime: not inspected
- Cache state: not inspected
- Plan revision source: `docs/reviews/2026-06-02-ticket-adr-source-repo-satisfaction-plan-review.md`, review-reviewer adjudication against current HEAD `26b1c130`, and a second review-reviewer pass against current HEAD `7a664b69`. The first review confirmed the revised plan still under-scoped shared-surface blast radius, `ingest`, hook guard ownership, `ticket_review.py` stale-cleanup emission, stage-model sunset ownership, and commit-boundary honesty. The second review confirmed remaining gaps around derived read dates, dedup after `key_file_paths` removal, omitted result/error vocabulary, bare-form `correction` residue, archive writes, Task 2 guard execution, runtime-readiness/triage residue ownership, `DeferredWorkEnvelope`, and mutation identity inputs.

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
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` exposes `ingest`, sanitizes old state/recovery hints, and maps old `ok_*` states in `_exit_code()`.
- `plugins/turbo-mode/ticket/scripts/ticket_read.py` silently skips unparseable files, scans `closed-tickets` when requested, sorts by `ParsedTicket.date`, and returns old fields such as `date`, `blocks`, `capture.confidence`, and `capture.component`. After cutover, any exposed `date` value must be derived from `T-YYYYMMDD-NN`, not stored frontmatter.
- `plugins/turbo-mode/ticket/scripts/ticket_dedup.py` currently fingerprints `problem_text` plus `key_file_paths`; after `key_file_paths` is removed from frontmatter, dedup must use the target ticket shape instead of regex-scraping old prose.
- `plugins/turbo-mode/ticket/tests/support/builders.py` also contains `expected_canonical_yaml()`, a legacy expected-output emitter that must be migrated or restricted to legacy rejection tests.

Current candidate/runtime drift:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` defines `CandidateMutation(ticket_id, action, proposed_change, evidence, conflict_reason)` rather than the target `target`, `expected_ticket_fingerprint`, and `evidence_summary` shape.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py` extracts known old structured fields and ignores unknown fields instead of rejecting them.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py` still adapts old candidate/runtime structures into gateway writes.

Current workflow/response drift:

- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` is still a `classify | plan | preflight | execute` pipeline and `engine_execute()` still requires classifier and plan-stage fields.
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py` still models classify/plan/preflight/execute inputs and `IngestInput`.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`, `plugins/turbo-mode/ticket/scripts/ticket_update.py`, `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`, and related tests still preserve prepare/execute saved-preview behavior.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` still dispatches low-level stage commands for compatibility/debug surfaces.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` still stores repo context with branch/head and old pending-summary states such as `skipped`, `discussion_required`, `ticket_written`, and `applied`, while already rejecting old `commit_disposition`, `commit_hash`, `commit_reason`, and `ticket_change_scope` details.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py` and `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` still emit or validate `ticket_update_blocked`; this token is not emitted by `ticket_turn_batch.py`.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, `ticket_workflow.py`, and tests still use states and error vocabulary such as `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `policy_blocked`, `need_fields`, `preflight_failed`, `dependency_blocked`, `invalid_transition`, `escalate`, `duplicate_candidate`, `not_found`, and `gateway_required`.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` still supports `_execute_close(..., archive=True)` moving tickets into `closed-tickets/`, and reopen/dedup helpers still account for archived tickets as normal lifecycle storage.
- `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py` and `tests/test_runtime_readiness.py` preserve installed-runtime fixture vocabulary such as old priorities and `runtime_readiness_required`; this may remain only as runtime-proof fixture history and must be classified in final residue.
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py` still uses old priority buckets such as `critical` and `medium` plus `refinement_status` rows; Task 6/9 must decide whether these are removed, mapped, or diagnostic-only.
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py` still allowlists `ticket_workflow.py`, `ticket_capture.py`, and `ticket_update.py` prepare/execute/recover commands.
- `plugins/turbo-mode/ticket/scripts/ticket_review.py` still emits `"action": "stale_cleanup"` in read-only hygiene candidates.

Current Change History drift:

- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py` uses `ChangeHistoryLabel` values `auto-create`, `auto-update`, `auto-blocker`, `auto-close`, `auto-reopen`, `correction`, and `discussion-approved`.
- `ChangeHistoryEntry` still has `prior_commit`, which is not target grammar.

Docs/tests state:

- README and `references/ticket-contract.md` already describe the target schema, target candidate contract, target result envelope, and target Change History grammar.
- `references/ticket-contract.md` Section 11 `DeferredWorkEnvelope` still presents old envelope fields, `suggested_priority: medium`, `key_file_paths`, and `defer.active` behavior as current authority and must be patched or explicitly superseded.
- They also preserve old surfaces as deprecated/diagnostic source facts. That is acceptable only until source removal finishes; the final source/repo closeout must not leave old behavior usable as normal product authority.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` already guards many target-doc sections and should be extended from docs-only target claims into source/repo guards after implementation.
- `plugins/turbo-mode/ticket/tests/support/builders.py` emits legacy fenced-YAML tickets by default, so strict reads require a builder migration plus explicit legacy/cutover fixtures.
- `plugins/turbo-mode/ticket/tests/test_migration.py` asserts direct `parse_ticket()` acceptance of legacy generations; after strict reads it must be repointed to diagnostic/cutover parsing or deleted with equivalent cutover coverage.
- `plugins/turbo-mode/ticket/tests/test_ingest.py`, `test_audit.py`, `test_turn_batch.py`, `test_integration.py`, `test_triage.py`, `test_preflight.py`, `test_engine_runner.py`, `test_find_review_doctor.py`, `test_autonomy_ids.py`, `test_autonomy_recovery.py`, `test_hook.py`, `test_hook_integration.py`, `test_classify.py`, `test_stage_models.py`, and `test_runner.py` are live shared-surface consumers and cannot be omitted from the cutover ownership model.

## Stop Conditions

Stop before implementation edits if:

- `git status --short --branch` shows tracked dirty files unrelated to this plan.
- ADR 0006 or the May 30 control doc no longer defines this source/repo finish line.
- A ticket record has a non-date-shaped ID, ambiguous target path, ambiguous status, or ambiguous priority mapping.
- A noncanonical Ticket storage directory appears under `docs/` and deterministic mapping is unclear.
- The implementation would need to mutate installed cache, runtime state, or `/Users/jp/.codex/plugins/cache`.

Stop during implementation if:

- Normal ticket readers would silently skip invalid active ticket files instead of returning `invalid_state` or an equivalent explicit block.
- Diagnostic/cutover inventory can no longer inspect invalid old files before its sunset, or legacy-generation parsing remains in the plugin runtime path after normalized records and strict target validation are in place.
- Ticket normalization would carry old metadata forward as opaque comments, appendices, or runtime-significant fields.
- A non-create write can pass without `expected_ticket_fingerprint`.
- Unknown candidate fields are accepted on normal mutation paths after the candidate-contract task.
- Normal create or update can persist fenced YAML, slug filenames, H1 title lines, `priority: medium`, `priority: critical`, `status: blocked`, `blocks`, `source`, `date`, `created_at`, `contract_version`, `capture_confidence`, `component`, `defer`, or other non-target storage fields.
- Normal reads expose a stored `date` field rather than deriving read-only date/sort output from `T-YYYYMMDD-NN`.
- Dedup either depends on persisted `key_file_paths` or silently falls back to regex-scraped old prose after target tickets no longer store `key_file_paths`.
- `build_filename()` or the engine create path can produce anything other than `T-YYYYMMDD-NN.md` after write-path normalization.
- Strict-read changes leave `tests/support/builders.py` generating invalid normal tickets by default or leave `test_migration.py` asserting direct normal parsing of legacy tickets.
- A changed shared surface has unassigned live consumers. Shared surfaces include `make_ticket()`, `expected_canonical_yaml()`, `render_ticket()`, `validate_fields()`, `CandidateMutation`, result-state strings, `ingest`, hook allowlists, and low-level stage models.
- `ingest` can still map old envelope fields into target frontmatter, return old normal result states, or use old recovery hints as current product guidance.
- `ChangeHistoryLabel` is deleted before `ticket_engine_gateway.py` and gateway tests are updated to the actor grammar.
- `ticket_review.py` or any normal candidate source can still emit old action values such as `stale_cleanup`, `correction`, `close`, `refine`, `archive`, `delete`, or `history_repair`.
- Normal close/update paths can still move active tickets into `closed-tickets/` through `archive=True`, or normal reopen/dedup/id allocation treats `closed-tickets/` as current lifecycle storage instead of diagnostic legacy residue.
- Deprecated prepare/execute behavior remains as a usable normal product path without a narrow diagnostic label and sunset condition.
- `hooks/ticket_engine_guard.py` still allowlists removed prepare/execute scripts as normal mutation commands.
- `ticket_stage_models.py`, `ticket_engine_runner.py` stage dispatch, or the stage tests are retained without an explicit diagnostic/debug label and sunset condition.
- Tasks 2-9 are committed as independent source commits without either full Ticket-suite proof at each intermediate boundary or an explicit atomic cutover-band closeout.
- Target docs claim installed runtime success or cache refresh.

## Commit Boundaries

Use coherent commits by proof boundary. Tasks 2-9 are one atomic source/repo cutover band by default because their shared surfaces are non-adjacent: repo ticket normalization affects current read/query behavior, strict reads affect builder callers, target write validation affects capture/workflow/ingest, candidate shape affects corrections and Change History, result-state collapse affects runner/audit/ingest/autonomy, and workflow removal affects hook allowlists and docs.

1. `docs(ticket): plan adr source repo satisfaction`
2. `test(ticket): add target ticket schema guards`
3. Atomic cutover band, committed only after Tasks 2-9 pass their selectors, full Ticket suite, ruff, diff checks, and residue scans:
   - `fix(ticket): complete adr source repo cutover`
4. Optional closeout/docs-only follow-up only if Task 9 documentation changes are intentionally split after a full green cutover:
   - `docs(ticket): close adr source repo cutover`

Do not create separate commits for Tasks 2, 3, 4, 5, 6, 7, 8, or 9 unless the proposed boundary has already passed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

If an executor chooses to keep local work checkpoints during Tasks 2-9, leave them uncommitted or clearly label them as uncommitted work. The closeout must not claim intermediate commits are independently bisectable unless the full gate above passed at that exact boundary.

### Cutover Band Execution Rule

Tasks 2-9 are a single execution unit. In subagent-driven mode, assign Tasks 2-9 to one cutover worker or to coordinated workers that share one uncommitted branch state and one final full-suite gate. Do not dispatch a fresh independent subagent per task inside this band and ask it to prove a green task-local commit.

The verification commands inside Tasks 2-9 are progress selectors. They are useful for finding remaining work owned by the band, but a selector PASS is not a commit boundary and a selector FAIL may be expected until adjacent in-band changes land. A smaller boundary is independently committable only after it passes:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

Any closeout for Tasks 2-9 must say whether the band was committed atomically or name the exact smaller boundaries that passed the full gate above.

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
- Read: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_review.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Read: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Read: `plugins/turbo-mode/ticket/tests/test_ingest.py`
- Read: `plugins/turbo-mode/ticket/tests/test_audit.py`
- Read: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- Read: `plugins/turbo-mode/ticket/tests/test_integration.py`
- Read: `plugins/turbo-mode/ticket/tests/test_triage.py`
- Read: `plugins/turbo-mode/ticket/tests/test_preflight.py`
- Read: `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- Read: `plugins/turbo-mode/ticket/tests/test_find_review_doctor.py`
- Read: `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py`
- Read: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- Read: `plugins/turbo-mode/ticket/tests/test_hook.py`
- Read: `plugins/turbo-mode/ticket/tests/test_hook_integration.py`
- Read: `plugins/turbo-mode/ticket/tests/test_classify.py`
- Read: `plugins/turbo-mode/ticket/tests/test_stage_models.py`
- Read: `plugins/turbo-mode/ticket/tests/test_runner.py`
- Read: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
- Read: `plugins/turbo-mode/ticket/CHANGELOG.md`
- Read: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Read: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`

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
rg -n "fenced YAML|closed-tickets|archive=True|archive\": (true|True)|capture_confidence|component|contract_version|build_filename|expected_canonical_yaml|suggested_priority|DeferredWorkEnvelope|key_file_paths|ready_to_execute|prepare|execute|ingest|IngestInput|retry_preview|stale_cleanup|correction|classify_confidence|ticket_stage_models|ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|policy_blocked|need_fields|preflight_failed|dependency_blocked|invalid_transition|escalate|duplicate_candidate|gateway_required|not_found|runtime_readiness_required|auto-create|auto-update|discussion-approved|ChangeHistoryLabel|ticket_update_blocked|commit_disposition|ticket_change_scope|refinement_status|priority_counts" \
  plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/hooks plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/.codex-plugin/plugin.json
```

Expected: hits are assignable to this plan, diagnostic/historical docs, or already-accepted target guards. In particular:

- `ticket_validate.py`, `ticket_render.py`, `ticket_id.py`, `ticket_engine_core.py`, `ticket_engine_gateway.py`, `ticket_envelope.py`, `ticket_dedup.py`, and archive/closed-ticket write helpers are assigned to Task 4.
- `ticket_read.py` `date` sorting/output is assigned to Task 3, with `date` derived from target IDs rather than persisted frontmatter.
- `tests/support/builders.py`, `expected_canonical_yaml()`, every `make_ticket()` caller, and `test_migration.py` are assigned to Task 3.
- `ticket_engine_runner.py`, `ticket_stage_models.py`, and `test_ingest.py` ingest/write-shape hits are assigned to Tasks 4, 6, and 8 as specified below.
- `ticket_autonomy.py`, `ticket_autonomy_runtime.py`, `ticket_turn_batch.py`, `ticket_engine_runner.py`, `ticket_stage_models.py`, `ticket_runtime_readiness.py`, `ticket_triage.py`, and state-asserting tests are assigned to Task 6.
- `ticket_engine_gateway.py` Change History hits are assigned to Task 7.
- `hooks/ticket_engine_guard.py`, `ticket_doctor.py`, low-level stage dispatch, and stale-payload cleanup hits are assigned to Task 8.
- `ticket_review.py` `stale_cleanup`, candidate-action docs, `CHANGELOG.md`, `references/ticket-contract.md` Section 11, and plugin metadata hits are assigned to Tasks 5 and 9.

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
- `validate_target_section_name(name: str) -> bool`
- `TARGET_STATUSES = ("open", "in_progress", "done", "wontfix")`
- `TARGET_PRIORITIES = ("high", "normal", "low")`
- `TARGET_CANDIDATE_ACTIONS = ("create", "update", "done", "wontfix", "reopen", "correct")`
- `validate_target_ticket_file(path: Path) -> TargetTicketValidation`
- `validate_target_ticket_text(path: Path, text: str) -> TargetTicketValidation`

Validation must be deterministic and mechanical. It must not score ticket semantics or decide priority.

Do not define an exhaustive optional-section enum. ADR 0006 leaves optional Markdown sections open as human prose. `TARGET_SECTIONS_REQUIRED` names the required sections only. `validate_target_section_name()` should accept a non-empty, line-shaped level-2 section name and reject malformed names; non-create candidate validation later decides whether an optional section may be targeted by checking the live ticket's actual sections or an explicit create candidate.

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

- [ ] **Step 4: Verify normalized records and no noncanonical Ticket storage remains**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_target_schema.py -q
find docs -maxdepth 4 -type d -iname '*ticket*' -print
find docs/tickets -maxdepth 2 -type f -print
```

Expected: pytest PASS, only `docs/tickets` for Ticket storage, and seven ID-only `docs/tickets/T-*.md` files.

This is a record-shape progress check inside the Tasks 2-9 cutover band, not a commit boundary. Do not commit after Task 2 alone unless normal readers already understand target frontmatter and the full Ticket-suite gate in `Commit Boundaries` passes at this exact boundary.

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
- Modify every read-path-coupled test that uses `make_ticket()`, `expected_canonical_yaml()`, `list_tickets()`, `find_ticket_by_id()`, or `parse_ticket()` with normal fixtures:
  - `plugins/turbo-mode/ticket/tests/test_autonomy.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
  - `plugins/turbo-mode/ticket/tests/test_blocker_resolution.py`
  - `plugins/turbo-mode/ticket/tests/test_capture.py`
  - `plugins/turbo-mode/ticket/tests/test_capture_contract.py`
  - `plugins/turbo-mode/ticket/tests/test_dedup_persistence.py`
  - `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
  - `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
  - `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
  - `plugins/turbo-mode/ticket/tests/test_execute.py`
  - `plugins/turbo-mode/ticket/tests/test_find_review_doctor.py`
  - `plugins/turbo-mode/ticket/tests/test_id.py`
  - `plugins/turbo-mode/ticket/tests/test_integration.py`
  - `plugins/turbo-mode/ticket/tests/test_migration.py`
  - `plugins/turbo-mode/ticket/tests/test_parse.py`
  - `plugins/turbo-mode/ticket/tests/test_plan.py`
  - `plugins/turbo-mode/ticket/tests/test_preflight.py`
  - `plugins/turbo-mode/ticket/tests/test_read.py`
  - `plugins/turbo-mode/ticket/tests/test_render.py`
  - `plugins/turbo-mode/ticket/tests/test_review_findings.py`
  - `plugins/turbo-mode/ticket/tests/test_triage.py`
  - `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
  - `plugins/turbo-mode/ticket/tests/test_ux.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow_cli.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow_execute.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow_recovery.py`

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
- replace or delete `expected_canonical_yaml()` as a normal expected-output helper. If it remains, rename it to `expected_legacy_canonical_yaml_for_cutover()` and use it only in diagnostic/cutover or legacy-rejection tests.

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

- [ ] **Step 4: Derive read-only date from target ID**

Remove persisted `date` from the normal parsed ticket contract. If existing `ParsedTicket` callers still need a `date` attribute or JSON payload field for sorting/display, derive it from the target ID:

```python
def date_from_ticket_id(ticket_id: str) -> str:
    match = re.fullmatch(r"T-(\d{4})(\d{2})(\d{2})-\d{2}", ticket_id)
    if not match:
        raise ValueError(
            f"date derivation failed: invalid target ticket id. Got: {ticket_id!r:.100}"
        )
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"
```

Tests must prove:

- target frontmatter containing `date:` is invalid;
- `list_tickets()` sort order uses the derived date and ID;
- `_ticket_to_dict()` may expose `"date"` only as a derived compatibility display value, not as persisted frontmatter;
- invalid IDs fail with `invalid_state` instead of silently sorting as an empty or stale date.

- [ ] **Step 5: Preserve diagnostic parsing**

Keep legacy fenced-YAML parsing available only through diagnostic/cutover inventory helpers. Name the helper accordingly, for example `parse_legacy_ticket_for_cutover()`, so normal product surfaces cannot accidentally rely on it as valid ticket authority.

Add an explicit sunset next to the helper and inventory entrypoint. Use this boundary:

- before Tasks 2-9 finish, legacy parsing may exist only to inventory and explain pre-cutover files;
- at Task 10 closeout, either remove `ticket_cutover_inventory.py` and legacy generation helpers from the plugin runtime path, or move/archive them outside normal plugin runtime code with a source-visible reason;
- after normalized repo tickets and strict target validation pass, permanent diagnosis should use target validation errors, not Gen 1-4 conversion parsing.

- [ ] **Step 6: Resolve migration-suite ownership**

Repoint `test_migration.py` to the diagnostic/cutover parser or delete obsolete direct-normal-parser assertions and replace them with equivalent `test_cutover_inventory.py` coverage. The retained tests must prove legacy generations can be inventoried and mapped, not that `parse_ticket()` accepts them as normal active tickets.

Expected assertion shape:

```python
inventory = inspect_legacy_ticket_for_cutover(path)
assert inventory.current_id == "handoff-chain-viz"
assert inventory.metadata_container == "fenced_yaml"
assert inventory.proposed_target_path.name.startswith("T-")
```

- [ ] **Step 7: Verify strict read behavior and fixture blast radius**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_target_schema.py \
  tests/test_cutover_inventory.py \
  tests/test_read.py \
  tests/test_parse.py \
  tests/test_migration.py \
  tests/test_autonomy.py \
  tests/test_autonomy_cli.py \
  tests/test_autonomy_corrections.py \
  tests/test_autonomy_integration_v1.py \
  tests/test_blocker_resolution.py \
  tests/test_capture.py \
  tests/test_capture_contract.py \
  tests/test_dedup_persistence.py \
  tests/test_engine_gateway.py \
  tests/test_engine_policy.py \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_find_review_doctor.py \
  tests/test_id.py \
  tests/test_integration.py \
  tests/test_plan.py \
  tests/test_preflight.py \
  tests/test_render.py \
  tests/test_review_findings.py \
  tests/test_triage.py \
  tests/test_update_refinement.py \
  tests/test_ux.py \
  tests/test_workflow.py \
  tests/test_workflow_cli.py \
  tests/test_workflow_execute.py \
  tests/test_workflow_recovery.py \
  -q
```

Expected at the end of the Tasks 2-9 cutover band: PASS. During an in-band checkpoint, failures that point to Tasks 4-9 shared surfaces are expected remaining work, not proof that Task 3 should be committed or scoped independently.

Then run:

```bash
rg -n "```ya?ml|contract_version|priority: medium|status: blocked|^date:|^# T-|expected_canonical_yaml" plugins/turbo-mode/ticket/tests/support plugins/turbo-mode/ticket/tests/test_read.py plugins/turbo-mode/ticket/tests/test_parse.py plugins/turbo-mode/ticket/tests/test_migration.py plugins/turbo-mode/ticket/tests/test_integration.py
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
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_dedup.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- Delete or narrow old-field writers in same cutover band: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Delete or narrow old-field writers in same cutover band: `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_validate.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_render.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_id.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_envelope.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ingest.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_dedup_persistence.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_blocker_resolution.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_plan.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_review_findings.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_capture_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- Modify/delete coupled prepare/execute tests if the capture/workflow path is made unavailable here:
  - `plugins/turbo-mode/ticket/tests/test_capture.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow_cli.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow_execute.py`
  - `plugins/turbo-mode/ticket/tests/test_workflow_recovery.py`
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
- `ingest` routes envelope-originated creates through the target render path, writes an ID-only file, does not persist `defer`, `source`, `effort`, `key_file_paths`, or `key_files` as frontmatter, and returns target-shaped normal result states after Task 6 mapping.
- dedup fingerprints use normalized `Problem` plus sorted target `related_paths` only; they do not read persisted `key_file_paths` or regex-scrape optional prose sections.
- old envelope `key_file_paths`, when accepted for a migration/ingest compatibility input, is either rejected as non-target input or deterministically mapped to target `related_paths` with tests proving no `key_file_paths` frontmatter is persisted.
- old direct `render_ticket(date=..., source=..., capture_confidence=..., component=...)` tests in `test_capture_contract.py` and `test_update_refinement.py` are either rewritten as legacy-rejection tests or removed with equivalent target-render coverage.

Expected assertion shape:

```python
response = _execute_create(
    {"title": "Target create", "problem": "Target create problem."},
    session_id="test-session",
    request_origin="user",
    tickets_dir=tmp_tickets,
)
assert response.state == "ok"
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

- [ ] **Step 5: Resolve validator coupling before tightening commits**

Do not leave any normal source path that self-injects a key rejected by `validate_fields()`. In this same cutover band, choose one of these implementation shapes and make the tests match it:

1. remove or make unavailable `ticket_capture.py` / `ticket_workflow.py` normal prepare/execute mutation paths before `validate_fields()` rejects old fields; or
2. rewrite those paths so they pass only target write fields and optional prose-section inputs to `validate_fields()`.

The first shape is preferred because Task 8 removes deprecated prepare/execute behavior. If the first shape is used, the old prepare/execute tests move to Task 8 deletion/narrowing and no Task 4 checkpoint may claim those product paths still work.

- [ ] **Step 6: Implement target rendering and ID-only filenames**

Change `render_ticket()` so normal persistence:

- emits YAML frontmatter between `---` fences, not fenced YAML;
- omits duplicated H1 headings;
- writes only target frontmatter keys;
- writes `## Problem`, `## Next Action`, and `## Change History` in order;
- preserves optional prose sections only when supplied;
- requires a Change History entry string or a `ChangeHistoryEntry` render result from Task 7-compatible helpers.

Change `build_filename()` to return `f"{ticket_id}.md"` for target IDs. If the target file exists, return an `invalid_state`/validation failure through the caller instead of appending a suffix.

Change `allocate_id()` scanning so it can read target YAML frontmatter for current tickets and may use the cutover helper for legacy diagnostic scans only.

- [ ] **Step 7: Implement engine/gateway/envelope/ingest create defaults**

Change engine and gateway create paths so:

- default priority is `normal`;
- create passes target-shaped fields to `render_ticket()`;
- persisted target path is ID-only;
- `ticket_envelope.py` accepts only `high`, `normal`, and `low` in `suggested_priority`;
- envelope default priority is `normal`;
- envelope mapping does not carry old `source`, `defer`, `effort`, `key_files`, or `key_file_paths` into target frontmatter. If those facts remain useful, place them in optional prose sections or diagnostic output, not persisted target frontmatter.
- `IngestInput` and `_dispatch_ingest()` do not require or preserve old ticket storage fields as normal frontmatter; if the envelope contains old metadata, expose it only in diagnostic output or optional prose.
- `_sanitize_user_facing_ingest_response()` must not emit `retry_preview` or `stale_plan` as current product guidance after prepare/execute removal. Map those cases to target states and target recovery copy.

- [ ] **Step 8: Implement target dedup and remove normal archive storage**

Change dedup behavior so the post-cutover fingerprint source is:

```python
payload = normalize(problem_text) + "|" + ",".join(sorted(related_paths))
```

where `related_paths` comes only from target frontmatter/input. Do not derive dedup inputs from `key_file_paths`, `key_files`, or regex-scraped optional prose after cutover. Update `test_dedup_persistence.py` so it proves:

- created tickets do not persist `key_file_paths`;
- `related_paths` round trips when supplied as target frontmatter;
- duplicate detection distinguishes matching problems by target `related_paths`;
- optional `Key Files` prose, if preserved, does not affect the dedup fingerprint.

Remove or make unavailable normal archive lifecycle writes:

- `_execute_close(..., archive=True)` must not move files into `closed-tickets/`;
- normal close with an `archive` field returns `invalid_state` or rejects the field through `validate_fields()`;
- reopen no longer treats `closed-tickets/` as normal lifecycle storage;
- ID allocation and dedup no longer scan `closed-tickets/` as current storage. If diagnostic inventory still scans `closed-tickets/`, name it as legacy inventory only.

Update `test_execute.py`, `test_engine_gateway.py`, `test_blocker_resolution.py`, `test_plan.py`, `test_id.py`, and `test_review_findings.py` to delete archive-as-normal assertions or replace them with archive-rejection/diagnostic-inventory assertions.

- [ ] **Step 9: Verify write-path normalization**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_validate.py \
  tests/test_render.py \
  tests/test_id.py \
  tests/test_execute.py \
  tests/test_engine_gateway.py \
  tests/test_envelope.py \
  tests/test_ingest.py \
  tests/test_dedup_persistence.py \
  tests/test_blocker_resolution.py \
  tests/test_plan.py \
  tests/test_review_findings.py \
  tests/test_capture_contract.py \
  tests/test_update_refinement.py \
  tests/test_capture.py \
  tests/test_workflow.py \
  tests/test_workflow_cli.py \
  tests/test_workflow_execute.py \
  tests/test_workflow_recovery.py \
  tests/test_target_schema.py \
  tests/test_docs_contract.py \
  -q
```

Expected at the end of the Tasks 2-9 cutover band: PASS. During an in-band checkpoint, failures that point to Tasks 5-9 shared surfaces are expected remaining work, not proof that Task 4 should be committed or scoped independently.

Then run:

```bash
rg -n "priority: (medium|critical)|status: blocked|^blocks:|^source:|^date:|^created_at:|^contract_version:|^capture_confidence:|^component:|^defer:|key_file_paths|key_files|closed-tickets|archive=True|archive\": (true|True)|```ya?ml|^# T-" plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_render.py plugins/turbo-mode/ticket/tests/test_id.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_envelope.py plugins/turbo-mode/ticket/tests/test_ingest.py plugins/turbo-mode/ticket/tests/test_dedup_persistence.py plugins/turbo-mode/ticket/tests/test_blocker_resolution.py plugins/turbo-mode/ticket/tests/test_plan.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_capture_contract.py plugins/turbo-mode/ticket/tests/test_update_refinement.py plugins/turbo-mode/ticket/tests/test_capture.py plugins/turbo-mode/ticket/tests/test_workflow.py plugins/turbo-mode/ticket/tests/test_workflow_cli.py plugins/turbo-mode/ticket/tests/test_workflow_execute.py plugins/turbo-mode/ticket/tests/test_workflow_recovery.py
```

Expected: matches appear only in tests proving legacy rejection or diagnostic/cutover behavior.

## Task 5: Adopt Target Candidate Mutation Contract

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_review.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py`

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

`CandidateTarget` should hold only `fields: tuple[str, ...]` and `sections: tuple[str, ...]`. Validate field names against `TARGET_FRONTMATTER_FIELDS`. Validate section names with `validate_target_section_name()` from `ticket_target_schema.py`, then check operation-specific targetability against the live ticket or explicit create payload. Do not treat optional sections as a closed enum.

Update `ticket_mutation_identity.py` so the canonical mutation payload includes exactly:

- `action`;
- `ticket_id`;
- `target.fields` and `target.sections`, canonicalized as sorted tuples or lists;
- `proposed_change`, canonicalized with stable key order;
- `expected_ticket_fingerprint`;
- the runtime-resolved live target fingerprint used for stale-write protection;
- `evidence_summary`.

Tests in `test_mutation_identity.py` and `test_autonomy_ids.py` must prove changing any of `target`, `expected_ticket_fingerprint`, or `evidence_summary` changes the identity, and that callers cannot supply an authoritative mutation ID or omit the live fingerprint for non-create writes.

- [ ] **Step 3: Update discovery**

`ticket_candidate_discovery.py` may continue to extract deterministic candidates from turn context, but normal structured candidates must reject unknown fields and old action values. Diagnostic inventory can still report old shapes.

Update `ticket_review.py` so read-only hygiene output does not emit old candidate actions such as `stale_cleanup`. If stale-ticket observations remain useful, expose them as read-only findings with prose fields, not as normal candidate mutations.

- [ ] **Step 4: Update gateway validation**

Gateway validation must compare action, ticket ID, target fields/sections, proposed change, expected fingerprint, and candidate identity before writing.

Map legacy gateway dispatch only at the internal engine boundary:

- candidate `done` and `wontfix` may dispatch to the retained internal close helper while normal response state remains target-shaped;
- candidate `correct` is an update or terminal correction with a `Corrects:` fact in Change History after Task 7;
- no normal candidate may expose `close`, `correction`, `reprioritize`, `blocker_edit`, `stale_cleanup`, or `refine`.

Correction flow is a first-class write consumer. Update `test_autonomy_corrections.py` in this task, not later, so `action="correct"` and the new `CandidateTarget` / `evidence_summary` shape are covered before gateway validation is considered done. If `_change_history_label()` still branches on `correction` before Task 7, do not commit this task separately; it remains inside the atomic Tasks 2-9 band.

- [ ] **Step 5: Verify candidate-contract selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_candidate_discovery.py \
  tests/test_mutation_identity.py \
  tests/test_autonomy_runtime.py \
  tests/test_autonomy.py \
  tests/test_engine_gateway.py \
  tests/test_autonomy_integration_v1.py \
  tests/test_autonomy_corrections.py \
  tests/test_autonomy_ids.py \
  -q
```

Expected at the end of the Tasks 2-9 cutover band: PASS. During an in-band checkpoint, failures that point to Tasks 6-9 shared surfaces are expected remaining work, not proof that Task 5 should be committed or scoped independently.

Then run:

```bash
rg -n "\"action\": \"(close|correction|reprioritize|blocker_edit|stale_cleanup|refine|archive|delete|history_repair)\"|action=\"correction\"|stale_cleanup|CandidateMutation\\(" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
rg -n "\b(close|correction|reprioritize|blocker_edit|stale_cleanup|refine|archive|delete|history_repair)\b" \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_review.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_candidate_discovery.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_review_findings.py
```

Expected: old actions are absent from normal candidate producers and appear only in explicit legacy-rejection tests or internal comments naming removed behavior. Every `CandidateMutation(` construction uses the target dataclass shape. Bare `correction` forms in `frozenset`, equality comparisons, branch labels, or review hygiene payloads are blockers unless explicitly confined to legacy-rejection tests.

## Task 6: Collapse Normal Result States

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_workflow.py` or delete if Task 8 removes it first.
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- Modify/classify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify/classify diagnostic-only state surfaces:
  - `plugins/turbo-mode/ticket/scripts/ticket_read.py`
  - `plugins/turbo-mode/ticket/scripts/ticket_review.py`
  - `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
  - `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_response_models.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Modify state-asserting tests and helpers:
  - `plugins/turbo-mode/ticket/tests/test_execute.py`
  - `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
  - `plugins/turbo-mode/ticket/tests/test_ingest.py`
  - `plugins/turbo-mode/ticket/tests/test_audit.py`
  - `plugins/turbo-mode/ticket/tests/test_dedup_persistence.py`
  - `plugins/turbo-mode/ticket/tests/test_migration.py`
  - `plugins/turbo-mode/ticket/tests/test_envelope.py`
  - `plugins/turbo-mode/ticket/tests/test_read.py`
  - `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
  - `plugins/turbo-mode/ticket/tests/test_review_findings.py`
  - `plugins/turbo-mode/ticket/tests/test_integration.py`
  - `plugins/turbo-mode/ticket/tests/test_runner.py`
  - `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
  - `plugins/turbo-mode/ticket/tests/test_entrypoints.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
  - `plugins/turbo-mode/ticket/tests/test_autonomy_integration.py`
  - `plugins/turbo-mode/ticket/tests/test_preflight.py`
  - `plugins/turbo-mode/ticket/tests/test_stage_models.py`
  - `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
  - `plugins/turbo-mode/ticket/tests/support/workflow.py`

- [ ] **Step 1: Add state-envelope tests**

Normal mutation results must use only:

- `ok`
- `blocked`
- `needs_discussion`
- `invalid_state`
- `no_change`

Old states or normal-response error vocabulary such as `ok_create`, `ok_update`, `ok_close`, `ok_close_archived`, `ok_reopen`, `policy_blocked`, `need_fields`, `preflight_failed`, `dependency_blocked`, `invalid_transition`, `escalate`, `duplicate_candidate`, `not_found`, `gateway_required`, and `runtime_readiness_required` may remain only in diagnostic/deprecated surfaces until those surfaces are removed.

Tests must also prove:

- `EngineResponse._OK_STATES` contains only `ok` for normal success after this task, or old ok states are isolated behind explicitly named diagnostic response classes;
- gateway normal output maps old internal success helpers to `ok`;
- old failure states map to `blocked`, `needs_discussion`, `invalid_state`, or `no_change`;
- mapping is explicit for the omitted live vocabulary:
  - `escalate` -> `blocked` unless the surface is an explicit diagnostic parser/stage result;
  - `duplicate_candidate` -> `needs_discussion` for normal create candidates, with duplicate details in `data`;
  - `not_found` -> `invalid_state`;
  - `gateway_required` -> `blocked` as an internal error/reason, not a public state;
  - `runtime_readiness_required` remains only in installed-runtime readiness fixtures, not normal source/repo mutation output;
- `ticket_engine_runner._exit_code()` treats only `ok` as normal success after boundary mapping; old `ok_*` values remain only in diagnostic/legacy fixture handling when explicitly classified;
- `IngestInput`, `_dispatch_ingest()`, and `_sanitize_user_facing_ingest_response()` return or translate target result states and do not expose `retry_preview`, `stale_plan`, `need_fields`, or `policy_blocked` as normal mutation states;
- `ticket_autonomy.py` no longer emits normal summary state `ticket_update_blocked`;
- `ticket_autonomy_runtime.py` no longer uses `RuntimeDecisionKind.TICKET_UPDATE_BLOCKED` as a normal public state. If a private internal decision remains, normal output must map it to `blocked`.
- `ticket_triage.py` removes old `critical`/`medium` priority buckets and `refinement_status` as current target concepts, or labels them diagnostic-only with docs/tests proving they do not shape normal mutation behavior.
- `ticket_runtime_readiness.py` and `test_runtime_readiness.py` classify old state/priority strings only as installed-runtime fixture history; those strings must not be cited by README, skills, contract, or normal source tests as target behavior.

- [ ] **Step 2: Normalize gateway result envelopes**

Map old engine outcomes into target mechanical states at the normal product boundary. Preserve useful validation details in `data`, not in new semantic state names.

Do not leave old success names in `_OK_STATES` unless the old engine code is still constructing them before a gateway map. If old construction remains temporarily, the task must add a local translation helper and a test showing no normal CLI/gateway/autonomy surface returns the old state.

If `ticket_stage_models.py` is retained for diagnostic stage dispatch until Task 8, its response-state vocabulary must be explicitly documented as diagnostic/private and excluded from normal product output. Otherwise, delete or narrow the old stage models in Task 8.

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_response_models.py \
  tests/test_engine_gateway.py \
  tests/test_autonomy_runtime.py \
  tests/test_autonomy.py \
  tests/test_autonomy_cli.py \
  tests/test_autonomy_integration_v1.py \
  tests/test_execute.py \
  tests/test_turn_batch.py \
  tests/test_ingest.py \
  tests/test_audit.py \
  tests/test_dedup_persistence.py \
  tests/test_migration.py \
  tests/test_envelope.py \
  tests/test_read.py \
  tests/test_engine_policy.py \
  tests/test_review_findings.py \
  tests/test_integration.py \
  tests/test_runner.py \
  tests/test_engine_runner.py \
  tests/test_entrypoints.py \
  tests/test_autonomy_ids.py \
  tests/test_autonomy_recovery.py \
  tests/test_autonomy_integration.py \
  tests/test_preflight.py \
  tests/test_stage_models.py \
  tests/test_runtime_readiness.py \
  -q
```

Expected at the end of the Tasks 2-9 cutover band: PASS. During an in-band checkpoint, failures that point to Tasks 7-9 shared surfaces are expected remaining work, not proof that Task 6 should be committed or scoped independently.

Then run:

```bash
rg -n "ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|policy_blocked|need_fields|preflight_failed|dependency_blocked|invalid_transition|escalate|duplicate_candidate|not_found|gateway_required|runtime_readiness_required|ticket_update_blocked|discussion_required|skipped|priority_counts|refinement_status" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
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

Expected at the end of the Tasks 2-9 cutover band: PASS. During an in-band checkpoint, failures that point to Tasks 8-9 shared surfaces are expected remaining work, not proof that Task 7 should be committed or scoped independently.

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
- Delete, narrow, or mark retained-with-sunset: `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Modify/delete tests preserving prepare/execute behavior:
  - `tests/test_workflow.py`
  - `tests/test_workflow_cli.py`
  - `tests/test_workflow_execute.py`
  - `tests/test_workflow_recovery.py`
  - `tests/test_capture.py`
  - `tests/test_update_refinement.py`
  - `tests/test_entrypoints.py`
  - `tests/test_doctor.py`
  - `tests/test_hook.py`
  - `tests/test_hook_integration.py`
- Modify/delete low-level stage dispatch tests if stage machinery is removed or retained as diagnostic-only:
  - `tests/test_classify.py`
  - `tests/test_preflight.py`
  - `tests/test_stage_models.py`
  - `tests/test_runner.py`
  - `tests/test_engine_runner.py`

- [ ] **Step 1: Re-run prepare/execute inventory**

Run:

```bash
rg -n "ready_to_execute|ticket_capture.py prepare|ticket_capture.py execute|ticket_update.py prepare|ticket_update.py execute|ticket_workflow.py prepare|ticket_workflow.py execute|run_workflow\\(\"prepare\"|run_workflow\\(\"execute\"|retry_preview|cleanup_stale_preview|stale_plan|VALID_WORKFLOW_SUBCOMMANDS|VALID_CAPTURE_SUBCOMMANDS|VALID_UPDATE_SUBCOMMANDS|ticket_stage_models|classify_confidence" \
  plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/hooks plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/.codex-plugin/plugin.json
```

Expected: every hit is assigned to deletion, diagnostic-only retention, or active docs update.

- [ ] **Step 2: Delete normal prepare/execute product paths**

Remove or make unavailable normal prepare/execute mutation paths. If a diagnostic stale-payload cleanup path remains, it must be reachable only from `ticket_doctor.py` or a clearly diagnostic command and must have a sunset condition.

Update `hooks/ticket_engine_guard.py` in the same task:

- remove allowlist support for `ticket_capture.py prepare|execute`;
- remove allowlist support for `ticket_update.py prepare|execute`;
- remove allowlist support for `ticket_workflow.py prepare|execute|recover` unless a retained diagnostic command has an explicit name and tests;
- keep canonical engine user/agent `execute` and `ingest` handling only when those commands map to the target result envelope and target write persistence.

Old allowlist tests must flip from "allowed" to "denied" or be deleted when the corresponding script path is removed. A passing `test_hook.py` is not meaningful if the guard still allows ghost prepare/execute scripts.

- [ ] **Step 3: Add or apply the stale-payload sunset**

If `ticket_doctor.py clean-stale-payloads` remains, narrow it to diagnostic cleanup for old `.codex/ticket-tmp/` payload residue only and add a source-visible sunset. Use this exact boundary:

- normal Ticket mutation docs and skills must not present stale-payload cleanup as a current product workflow;
- the command may remain only as explicit maintenance for pre-cutover payload residue;
- once `ticket_capture.py`, `ticket_update.py`, and `ticket_workflow.py` normal prepare/execute paths are removed, `ticket_doctor.py diagnose` may report stale payload residue but must not recommend rerunning a prepare/execute workflow;
- `test_doctor.py` and `test_docs_contract.py` must fail if `cleanup_stale_preview`, `retry_preview`, or `ready_to_execute` appears in target/current product sections.

If the executor can prove no source path still creates old stale payloads, prefer deleting `clean-stale-payloads` in this task rather than preserving the diagnostic command.

- [ ] **Step 4: Decide low-level stage retention**

The four-stage `classify | plan | preflight | execute` machinery may remain only as narrow diagnostic/debug scaffolding under ADR 0006's temporary-retention allowance. In this task, choose one of these implementation shapes:

1. delete or make unavailable low-level stage dispatch and remove/update `ticket_stage_models.py`, `test_classify.py`, `test_preflight.py`, `test_stage_models.py`, `test_runner.py`, and affected `test_engine_runner.py` cases; or
2. retain it behind an explicit diagnostic/debug label with a source-visible sunset condition, plus tests proving normal product docs, skills, hook allowlists, and gateway/autonomy paths do not present it as current product architecture.

If shape 2 is used, add a comment near the retained dispatch that names the sunset trigger: remove the stage dispatch once Tasks 2-9 source/repo cutover is merged and no source test requires stage-specific compatibility fixtures.

- [ ] **Step 5: Keep read/query/report surfaces**

Do not delete `read-ticket`, backlog triage, doctor diagnostics, or explicit runtime activation unless they directly preserve deprecated mutation semantics.

- [ ] **Step 6: Verify old paths are not normal product behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_docs_contract.py \
  tests/test_static_autonomy_boundaries.py \
  tests/test_hook.py \
  tests/test_hook_integration.py \
  tests/test_read.py \
  tests/test_doctor.py \
  tests/test_entrypoints.py \
  tests/test_workflow.py \
  tests/test_workflow_cli.py \
  tests/test_workflow_execute.py \
  tests/test_workflow_recovery.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_classify.py \
  tests/test_preflight.py \
  tests/test_stage_models.py \
  tests/test_runner.py \
  tests/test_engine_runner.py \
  -q
```

Expected at the end of the Tasks 2-9 cutover band: PASS. During an in-band checkpoint, failures that point to Task 9 docs/static alignment are expected remaining work, not proof that Task 8 should be committed or scoped independently.

## Task 9: Align Active Docs, Skills, And Tests

**Files:**

- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/CHANGELOG.md`
- Modify: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py`

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
- `ingest`, if retained, is described as target-write envelope ingestion rather than a legacy read-validate-map-plan-preflight-execute pipeline;
- `references/ticket-contract.md` Section 11 `DeferredWorkEnvelope` is either rewritten to target vocabulary or explicitly superseded. It must not present `suggested_priority: medium`, `critical`, `key_file_paths`, `defer.active`, or read-validate-map-plan-preflight-execute ingestion as current target authority.
- low-level stage dispatch, if retained, is described only as diagnostic/debug scaffolding with a sunset, not product architecture;
- installed runtime proof remains unclaimed.

- [ ] **Step 2: Strengthen docs-contract tests**

Add guards that fail if target/current sections present:

- fenced YAML as target ticket format;
- `medium`, `critical`, or `blocked` as target values;
- slug filenames, H1 title lines, `date`, `created_at`, `source`, `capture_confidence`, `component`, `contract_version`, `defer`, or `blocks` as target storage fields;
- `ticket_capture.py prepare`, `ticket_update.py prepare`, or `ready_to_execute` as normal product paths;
- `ticket_workflow.py prepare`, `ticket_workflow.py execute`, `retry_preview`, `cleanup_stale_preview`, or `stale_plan` as current product workflow guidance;
- `ok_create`, `ok_update`, `policy_blocked`, or `preflight_failed` as target result states;
- old Change History labels as valid target grammar.
- old candidate actions `close`, `correction`, `reprioritize`, `blocker_edit`, `stale_cleanup`, `refine`, `archive`, `delete`, or `history_repair` as normal candidate actions.
- the old `ingest` changelog description as current target behavior.
- `DeferredWorkEnvelope` sections that preserve `medium`, `critical`, `key_file_paths`, or `defer.active` without an explicit deprecated/historical label.

- [ ] **Step 3: Verify docs/static selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py -q
rg -n "capture_confidence|capture_source|ticket_capture.py prepare|ticket_update.py prepare|ticket_workflow.py prepare|ready_to_execute|retry_preview|cleanup_stale_preview|stale_plan|ok_create|ok_update|preflight_failed|stale_cleanup|DeferredWorkEnvelope|suggested_priority|key_file_paths|defer\.active|read-validate-map-plan-preflight-execute" plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/.codex-plugin/plugin.json
```

Expected at the end of the Tasks 2-9 cutover band: pytest PASS. The `rg` command has no matches in current/target sections; historical changelog matches are allowed only when immediately labeled as historical and not current behavior. Do not commit Task 9 separately unless the full Ticket-suite gate in `Commit Boundaries` also passes at this exact boundary.

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
rg -n "ready_to_execute|ticket_capture.py prepare|ticket_capture.py execute|ticket_update.py prepare|ticket_update.py execute|ticket_workflow.py prepare|ticket_workflow.py execute|retry_preview|cleanup_stale_preview|stale_plan|stale_cleanup|correction|fenced YAML|capture_confidence|contract_version|ChangeHistoryLabel|auto-create|auto-update|auto-blocker|auto-close|auto-reopen|discussion-approved|ok_create|ok_update|ok_close|ok_close_archived|ok_reopen|policy_blocked|need_fields|preflight_failed|dependency_blocked|invalid_transition|escalate|duplicate_candidate|not_found|gateway_required|runtime_readiness_required|ticket_update_blocked|ticket_written|discussion_required|skipped|ticket_change_scope|commit_disposition|ticket_stage_models|classify_confidence|priority_counts|refinement_status|DeferredWorkEnvelope|suggested_priority|key_file_paths|defer\.active|read-validate-map-plan-preflight-execute|ticket_cutover_inventory|parse_legacy_ticket_for_cutover|make_gen[1-4]_ticket" \
  docs/tickets plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/hooks plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/.codex-plugin/plugin.json
rg -n "\b(close|correction|reprioritize|blocker_edit|stale_cleanup|refine|archive|delete|history_repair)\b" \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_review.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_candidate_discovery.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_review_findings.py
rg -n "(^|[\"'`])component([\"'`]|:)" \
  docs/tickets plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/hooks plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/.codex-plugin/plugin.json
rg -n "^```ya?ml|^# T-|^date:|^created_at:|^source:|^blocks:|^defer:|priority: (medium|critical)|status: blocked|closed-tickets" \
  docs/tickets plugins/turbo-mode/ticket/tests/support
```

Expected: hits are either absent or explicitly classified as diagnostic/historical in active docs, diagnostic/cutover fixtures, or legacy rejection tests. No hit may present old behavior as target/current product authority. The final closeout must include the classified residue table when any match remains.

The residue table must include these columns:

| Token/path | Location | Classification | Owner task | Why allowed or removed |
|---|---|---|---|---|

Any unclassified match is a blocker.

- [ ] **Step 4: Run markdown and diff checks**

Run:

```bash
git diff --check
git diff --stat
git status --short --branch
```

Expected: no whitespace errors; diff is scoped to the source/repo Ticket cutover plus current repo ticket records and docs; no untracked generated residue except ignored local handoff/session state.

## Known Limitations And Residual Risks

- Tasks 2-9 are intentionally one atomic source/repo cutover band unless a full Ticket-suite gate proves an intermediate boundary is independently green. The closeout must say whether the band was committed atomically or which intermediate boundaries passed full-suite proof.
- Installed runtime and local plugin cache are still out of scope. Source success does not prove that the active Codex thread or `/Users/jp/.codex/plugins/cache` exposes the new Ticket behavior.
- Temporary cutover inventory and legacy generation parsing may remain only for the Tasks 2-9 cutover. The closeout must either remove `ticket_cutover_inventory.py` and legacy helpers from the plugin runtime path, or name the non-runtime archive/tooling location and removal trigger.
- Low-level `classify | plan | preflight | execute` machinery may remain only as diagnostic/debug scaffolding with a sunset. If retained, the closeout must name the exact retained files, tests, diagnostic label, and removal trigger.
- Historical `CHANGELOG.md` entries may retain old vocabulary only when clearly historical. They must not be cited by README, skills, plugin metadata, or contract docs as current behavior.
- Runtime-readiness scripts and tests may keep old state strings as installed-runtime fixture history only when classified in the final residue table. They do not prove installed runtime behavior in this source/repo lane and must not leak into current source/repo authority docs.
- `DeferredWorkEnvelope` compatibility text may remain only when explicitly labeled historical or superseded; current contract sections must use target priorities, target result states, target write paths, and no `defer.active` persistence.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-06-02-ticket-adr-source-repo-satisfaction.md`. Two execution options:

1. Subagent-Driven (recommended) - use one cutover worker for Tasks 2-9, or coordinated workers sharing one uncommitted branch state and one final full-suite gate. Task 0 and Task 1 may be reviewed separately.
2. Inline Execution - execute Tasks 2-9 in this session using executing-plans, with checkpoints after the schema-guard commit and after the atomic cutover commit.

Before implementation, choose one execution option. Do not begin implementation edits from this plan without that cue.

## Self-Review

Spec coverage:

- Source/repo satisfaction is covered by Tasks 1 through 10.
- Runtime/cache proof is explicitly out of scope.
- Ticket normalization, strict normal-surface rejection, derived read dates, diagnostic inventory, write/persistence normalization, target dedup, archive-write removal, candidate contract and identity, response envelope, Change History grammar, hook guard, `ingest`, runtime-readiness/triage residue, `ticket_review.py` stale cleanup, low-level stage retention, workflow removal, docs/tests, and final verification each have explicit task ownership and stop conditions after this revision.
- Tasks 2-9 are not claimed as independently committable unless the executor runs and records full Ticket-suite proof at that boundary.

Placeholder scan:

- No placeholder tokens or unspecified test-writing steps remain.
- Where implementation must use the actual migration timestamp, the plan defines the actor and reason and validates ISO shape rather than hardcoding a stale timestamp.

Type consistency:

- `validate_target_ticket_file()` and `TargetTicketValidation` are introduced before use in docs-contract tests.
- Target ticket schema names match ADR 0006, and target candidate field/action names match the May 30 control doc.
- Result state names match the control doc, and the plan now explicitly maps or classifies live legacy vocabulary including `escalate`, `duplicate_candidate`, `not_found`, `gateway_required`, and `runtime_readiness_required`.
