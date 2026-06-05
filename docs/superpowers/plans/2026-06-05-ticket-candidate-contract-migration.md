# Ticket Candidate Contract Migration Implementation Plan

> **Superseded for execution:** This monolith is retained as historical source
> material only. Execute the split plan series through
> `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md`
> and its five child plans:
>
> 1. `docs/superpowers/plans/2026-06-05-ticket-candidate-source-entrypoint-spine.md`
> 2. `docs/superpowers/plans/2026-06-05-ticket-create-idempotency-binding.md`
> 3. `docs/superpowers/plans/2026-06-05-ticket-reopen-blocked-cleanup-semantics.md`
> 4. `docs/superpowers/plans/2026-06-05-ticket-correction-recovery-facts.md`
> 5. `docs/superpowers/plans/2026-06-05-ticket-availability-flip-final-proof.md`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors, because this plan has shared-state and commit-order dependencies. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose and enforce the literal Ticket target candidate mutation contract in source so autonomous create/update/close/reopen/correct writes use the same visible-board envelope documented by the May 30 control doc.

**Architecture:** Candidate shape becomes an explicit `action`, `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary` envelope. Runtime validation owns target-envelope shape and deterministic authorization; the gateway projects target fields/sections into existing engine primitives and records recovery facts. Engine rendering remains the write authority, with a narrow extension for exact level-2 target section updates.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Evidence Baseline

Live state checked before writing this plan, after the initial plan commit, after
the review hardening patch, after the correction-gate clarification, after the
source-entrypoint coverage patch, after the operation-log/exact-envelope patch,
and after the create-recovery plan patch:

- Branch/worktree at plan creation: `main...origin/main`, clean normal status,
  `HEAD` at `92cd4bed`.
- Branch/worktree after committing the initial plan: `main...origin/main [ahead 1]`,
  clean normal status, `HEAD` at `38537aa9`.
- Branch/worktree after the review hardening patch: `main...origin/main [ahead 2]`,
  clean normal status, `HEAD` at `69f44342`.
- Branch/worktree after the correction-gate clarification: `main...origin/main [ahead 3]`,
  clean normal status, `HEAD` at `6d7e1579`.
- Branch/worktree after the source-entrypoint coverage patch:
  `main...origin/main [ahead 4]`, clean normal status, `HEAD` at `d52a81ab`.
- Branch/worktree after the operation-log/exact-envelope patch:
  `main...origin/main [ahead 5]`, clean normal status, `HEAD` at `574e5cee`.
- Branch/worktree after the create-recovery plan patch:
  `main...origin/main [ahead 6]`, clean normal status, `HEAD` at `bed44541`.
- Branch/worktree after the correction-context and Task 3A verification review:
  `main...origin/main [ahead 13]`, clean normal status, `HEAD` at `d145ac2d`.
- Branch/worktree after the correction context producer patch:
  `main...origin/main [ahead 14]`, clean normal status, `HEAD` at `cf0d3d13`.
- Branch/worktree after the validation-gate hardening patch:
  `main...origin/main [ahead 15]`, clean normal status, `HEAD` at `8339751b`.
- Branch/worktree after the blocked-close and correction-gate plan patch:
  `main...origin/main [ahead 16]`, clean normal status, `HEAD` at `7dc5cb7d`.
- Branch/worktree after the authority-alignment plan patch:
  `main...origin/main [ahead 17]`, clean normal status, `HEAD` at `18d40178`.
- Active ticket inventory: seven files under `docs/tickets/`; all use ID-only filenames, frontmatter metadata, target statuses, required sections, no unknown frontmatter keys, and no blocked-shape defects.
- Active ticket statuses: six `open`, one `done`, no `status: in_progress`.
- Historical references: old-looking `T-20260527-001` examples only appear in `docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md`; placeholders such as `T-YYYYMMDD-NN` appear in ADR/control docs and are not active ticket IDs.
- Source gap: `CandidateMutation`, gateway dispatch, discovery, and mutation identity still use flat `proposed_change` plus `target_fingerprint`/evidence-link vocabulary.

This is a source/repo plan only. Do not claim installed runtime proof from this plan or from source tests. Installed proof requires a separate runtime inventory lane.

## File Structure

Modify these files:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
  - Owns `CandidateTarget`, target-shaped `CandidateMutation`, mapping validation, runtime decisions, fanout caps, and `EngineDispatch`.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
  - Converts explicit turn-context candidate mappings into target-shaped `CandidateMutation` objects and stops converting vague/path-only signals into write candidates.
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
  - Hashes canonical target candidate content, including `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
- `plugins/turbo-mode/ticket/scripts/ticket_dedup.py`
  - Keeps the existing mtime-sensitive `target_fingerprint()` for pre-write
    TOCTOU checks and adds a content-only target recovery fingerprint helper for
    expected post-write recovery facts that must be computed before a file write.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
  - Projects evaluated target candidates through the live `apply-turn` source
    entrypoint and constructs target-shaped `GatewayMutation` requests without
    repopulating expected fingerprints from the old `source_context` side
    channel. Projects prior-turn ledger recovery with the same pre-write and
    content-only post-write recovery facts as the gateway, including retained
    create allocation paths.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
  - Carries target-shaped `GatewayMutation`, recomputes mutation identity,
    validates expected fingerprints, binds retained create candidate identity to
    allocated target IDs, projects exact target sections into engine dispatch,
    and records bounded recovery facts.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
  - Extends update/close/reopen execution to accept or validate exact target
    section headings from the gateway without changing legacy direct
    `engine_execute()` field syntax, and provides the exact pre-write projection
    needed for recovery fingerprints.
- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
  - Removes current `Reopen History` insertion assumptions from normal reopen
    flow and keeps generated `Change History` grammar aligned with the May 30
    control doc.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
  - Separates retained target-candidate action facts from maintenance event
    validation on `mutation_attempt` and `mutation_status`/`ticket_written`
    events and removes durable decision-kind/evidence-kind/current-mode detail
    requirements from mutation attempt events.
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
  - Aligns field validation with gateway projection: permits source create-only
    `key_files` when `_plan_create()` and `_execute_create()` validate rendered
    create fields, keeps non-create target writes from accepting `key_files`, and
    removes `reopen_reason` from normal target write-field acceptance once
    `reopen` uses `evidence_summary`.
- `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
  - Align source-authority wording for non-create identity and deliberate
    correction authorization tightening after the source migration lands.
- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/TERMS.md`
- `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
  - Update source-availability prose, plugin metadata, and lifecycle docs after
    the live source entrypoint exists. Do not claim installed runtime
    availability.

Test these files:

- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
- `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
- `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
- `plugins/turbo-mode/ticket/tests/test_execute.py`
- `plugins/turbo-mode/ticket/tests/test_integration.py`
- `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- `plugins/turbo-mode/ticket/tests/test_review_findings.py`
- `plugins/turbo-mode/ticket/tests/test_change_history.py`
- `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

## Contract Decisions

- Migrate `reopen` fully in this slice. The May 30 control doc already states that the human reason belongs in `evidence_summary`, not `reopen_reason`, and that `reopen -> blocked` is valid when the blocked ticket shape is valid.
- Treat `correct` as the user-triggered correction lane for a recent Ticket
  write. A `correct` candidate follows the same content-change rules as the
  underlying target: active current tickets with active target status remain
  updates, terminal target status closes, and only terminal current tickets with
  active target status reopen. The gateway must admit `correct` only when the
  paired runtime decision is `RuntimeDecisionKind.APPLY_CORRECTION`; that
  decision kind is the approval boundary for any `correct -> reopen`.
- Do not let `correct` authorize itself from candidate content. `evidence_summary`
  explains the requested correction, but the runtime correction gate must require
  bounded recent-correction context from private pending-summary/source-context
  state outside the candidate envelope. If that mechanical context is absent,
  expired, compacted, or not tied to the current correction candidate, runtime
  must return `RuntimeDecisionKind.REQUIRE_USER_DISCUSSION` with
  `reason="correction_detail_missing"` and must not call the gateway.
- Enforce correction freshness in `evaluate_autonomy_intent()` itself, using the
  call-site `now` argument. The apply-turn producer may prefilter stale context,
  but runtime authorization must independently parse `retained_at`, reject
  unparseable or expired context, require an uncompacted/detail-retained marker,
  and compare canonical sorted target fields/sections.
- Deliberately tighten `correct` authorization in this slice: recent,
  uncompacted correction context is an authorization prerequisite for automatic
  `correct`, not only optional `Corrects:` metadata. The May 30 control doc
  phrases recent correction context more loosely today; Task 6 must update that
  authority wording before docs-contract PASS. Until that docs update lands,
  source implementation still treats absent, expired, compacted, or unmatched
  context as `correction_detail_missing`.
- Treat malformed explicit candidate arrays as visible invalid work, not as
  absence of work. If any object under `candidate_mutations`,
  `update_candidates`, or `capture_candidates` has missing, unknown, or
  wrong-typed target-candidate keys, apply-turn must emit an invalid/blocked
  result or a discussion-required result before mutation evaluation. It must not
  silently drop the item and fall through to `no_change`.
- Treat `invalid_candidate` as an outer `apply-turn` CLI/host response state for
  malformed explicit turn-context payloads before target mutation evaluation. It
  is not part of the target mutation result envelope, which remains limited to
  `ok`, `blocked`, `needs_discussion`, `invalid_state`, and `no_change`.
- Keep full `reconcile_board` implementation out of this slice. This migration may make the future wrapper possible, but it must not implement discovery ordering, caps, overflow, or broad board search.
- Keep operation-log work narrow. This slice may update candidate identity,
  expected pre-write recovery facts, expected post-write fingerprint, exact
  generated `Change History` metadata, evidence summary, target
  fields/sections, and write/summary flags. It must not add semantic ranking,
  evidence-kind taxonomies, approval-state taxonomies, or private workflow
  stages.
- Implement exact `create` idempotency before source-availability docs change.
  Ordinary duplicate detection is not the same guarantee. For `create`, the
  gateway must bind canonical pre-allocation candidate identity to the allocated
  target ID under a create-allocation-wide write lock before writing the file,
  and retry must use that retained binding while it exists.
- Treat retained create allocation, expected post-write recovery fingerprint,
  and exact generated `Change History` metadata as one atomic source boundary.
  Do not commit a create-recovery state that records only allocated ID/path and
  path-existence checks. A create retry may record completion from an existing
  allocated file only when the file's content-only post-write recovery
  fingerprint matches the retained expected post-write fingerprint.
- Keep fresh-create duplicate/current-state preflight separate from retained
  allocation recovery. A first create attempt still runs the ordinary
  `_plan_create()` duplicate check before recording an allocation; once a
  retained `mutation_attempt` exists for the same create candidate, retry uses
  the retained allocation binding and must not allocate a fresh ID.
- Treat the target candidate envelope as exact. Do not accept `conflict_reason`
  as a top-level candidate key, do not store it on target-shaped
  `CandidateMutation`, and do not include it in identity, gateway, result, or
  operation-log payloads. If live discovery sees conflicting evidence, it should
  block before constructing a write candidate or carry a short mechanical pause
  reason outside candidate content.
- Treat `target.fields` and `target.sections` as canonical unordered name sets
  at the identity boundary. Reject duplicate names inside either list, reject a
  name that appears in both `fields` and `sections`, and sort target names before
  hashing candidate identity or discovery dedupe keys.
- Require every target candidate to name at least one user-visible target field
  or section. An empty `target.fields` plus empty `target.sections` envelope is
  invalid for `create`, `update`, `done`, `wontfix`, `reopen`, and `correct`;
  generated `Change History` alone is a side effect and never satisfies target
  closure.
- Make close dispatch current-status-aware. If the current ticket is `blocked`,
  a `done` or `wontfix` target candidate must explicitly name `status`,
  `blocked_by`, and `Blocked On`, with `blocked_by=[]` and `Blocked On=None`;
  the gateway must not let `_execute_close()` clear visible blocker state that
  was not present in the candidate target envelope.
- Treat active unblocking as an exact target shape, not only a transition-policy
  side effect. If the current ticket is `blocked` and a target candidate moves it
  to `open`, the candidate must name `status`, `blocked_by`, `Blocked On`, and
  `Next Action` together; `blocked_by` must be `[]`, `Blocked On` must be
  `None`, and `Next Action` must carry the continuation step unless the
  authority docs are narrowed in the same commit.
- Treat `reopen -> open` and `reopen -> blocked` as separate target shapes.
  `reopen -> open` names only normal open-ticket shape and must not carry
  `blocked_by`, `Blocked On`, or other blocked-only target content. `reopen ->
  blocked` must name valid blocked-ticket shape.
- Validate raw mapping values before normalization. Non-string, non-null
  `ticket_id` and `expected_ticket_fingerprint` values are invalid; do not
  silently coerce them to `None`. Non-string `action` and `evidence_summary`
  values are invalid; do not coerce them to `""`.
- Remove vague `possible_candidates` and path-only candidates from write-candidate discovery. They are not target candidate mutations because they do not name a user-visible change. Future `reconcile_board` can reintroduce broad search as a wrapper that emits ordinary target candidates.
- Deduplicate explicit discovered candidates by canonical candidate content, not
  by a human evidence summary string. Two candidates for the same ticket/action
  with the same `evidence_summary` but different `target` or `proposed_change`
  must both survive discovery.
- Create target-section projection must cover every create section rendered by
  the source create engine, or this slice must narrow the authority docs in the
  same commit. Do not reject valid optional create sections such as `Context`,
  `Prior Investigation`, `Approach`, `Verification`, or `Key Files` while
  claiming the broader target contract is implemented. `ticket_validate.py` is
  part of this adapter boundary because live create validation currently runs
  before `_execute_create()` renders source-supported sections.
- Treat Tasks 1, 2, and 3 as the first runnable source commit group. Runtime
  identity calls start using the target-shaped identity helper before
  `test_autonomy_runtime.py` can be green, and gateway/apply-turn construction
  sites are not migrated until Task 3. Tasks 1 and 2 may be internal
  focused-green checkpoints, but do not commit either task before Task 3's
  gateway/source-entrypoint PASS gate succeeds.
- Treat intermediate task commits as focused-green boundaries, not full-suite
  green boundaries. Do not claim the full Ticket suite is green until Task 7.
  If a task removes source behavior that a focused selector covers, rewrite or
  remove the corresponding tests in that same task. Tests outside the task's
  focused selector remain assigned to their named later task and must not be
  dismissed as unrelated failures.
- Treat `expected_ticket_fingerprint` as candidate content supplied by explicit
  target candidate mappings. `ticket_autonomy.py` must pass
  `decision.candidate.expected_ticket_fingerprint` into `GatewayMutation`; it
  must not synthesize or override that value from `_ticket_state_fingerprints()`
  or `source_context`. The gateway still recomputes the current ticket
  fingerprint immediately before writing and rejects stale candidates.
- Resolve identity authority explicitly: for non-create target candidates,
  `expected_ticket_fingerprint` is the candidate-supplied copy of the live target
  fingerprint at discovery/evaluation time, and it participates in candidate
  identity. It is not an authoritative caller-supplied identity value; Ticket
  recomputes the current live target fingerprint at gateway write time and
  rejects any mismatch. For `create`, identity excludes
  `expected_ticket_fingerprint` because it is `None`. Task 6 must align the May
  30 control doc and `ticket-contract.md` wording so "live target fingerprint"
  and `expected_ticket_fingerprint` describe this same boundary.

## Migration Coverage Map

Before implementation, build the rename/blast-radius map from live source. Run
both commands:

```bash
rg -n "target_fingerprint|mutation\.fields|\.evidence|EvidenceLink|\"correction\"|conflict_reason|reopen_reason|Reopen History|evidence_kind|current_mode|\"decision\"|decision\.kind|RuntimeDecisionKind|reprioritize|stale_cleanup|blocker_edit|refine|archive|delete|history_repair|summarize|compact|pause_automation|codex\.ticket\.mutation\.v1|ticket_write|mutation_status|ticket_written|allocated_ticket_id|create_allocation|expected_post_write_fingerprint|post_write_fingerprint|ChangeHistoryEntry|change_history_timestamp|key_files" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
rg -n "GatewayMutation\(|CandidateMutation\(" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Assign every hit to one of these dispositions before claiming a task is green:

| Legacy surface | Target disposition | Must be covered in |
|---|---|---|
| `target_fingerprint` in candidate/gateway identity | Rename to `expected_ticket_fingerprint` for target candidate/gateway paths. Legacy direct engine plan/execute surfaces may keep `target_fingerprint` only when the task explicitly labels them outside the target candidate path. Calls to `scripts.ticket_dedup.target_fingerprint` may remain only as the helper that computes a current ticket fingerprint; import it as `compute_target_fingerprint` in changed tests when practical. | Tasks 1-3 and final residue check |
| Post-write recovery fingerprint helper | Do not use the mtime-sensitive `target_fingerprint()` as the pre-write expected post-state, because the post-write mtime is unknowable before the write. Add a content-only target recovery fingerprint helper in the create-idempotency boundary and use it only for expected/observed post-write recovery comparisons. | Task 3A and Task 5 |
| `mutation.fields` on `GatewayMutation` | Rename to `mutation.proposed_change`, including create dedup and test fakes. | Task 3 |
| `GatewayMutation(...)` construction sites | Rewrite every source/test construction to the target-shaped constructor. `ticket_autonomy.py` is the live apply-turn spine and must be migrated in Task 3, not left to final verification. | Task 3 |
| `CandidateMutation(...)` construction sites | Rewrite every source/test construction to the target-shaped constructor or remove the old test. Construction sites are not covered by vocabulary greps alone. | Tasks 1-5 and final construction-site check |
| `.evidence`, `EvidenceLink`, evidence-kind floors | Replace with one-line `evidence_summary`; remove evidence-kind classification from runtime/discovery/gateway mutation-attempt facts. | Tasks 1, 2, and 5 |
| `"correction"` candidate action | Rename target candidate action to `"correct"` in runtime, gateway, turn-batch validation, tests, and generated history reason. Task 1 owns runtime action groups and `evaluate_autonomy_intent()`; Task 3 owns gateway/source-entrypoint projection; Task 5 owns correction fixtures and operation-log recovery assertions. Keep `RuntimeDecisionKind.APPLY_CORRECTION` only as an internal decision kind. | Tasks 1, 3, 5, and final residue check |
| `conflict_reason` candidate content | Remove from accepted target candidate mappings and from `CandidateMutation`. Conflict evidence may stop candidate construction or produce a short mechanical pause reason outside the target candidate envelope, but it must not enter candidate identity, gateway validation, result data, or mutation-attempt details. | Tasks 1, 2, and final residue check |
| Wrong-type target candidate fields | Reject non-string, non-null `ticket_id` and `expected_ticket_fingerprint` before constructing `CandidateMutation`. Reject non-string `action` and `evidence_summary` before constructing `CandidateMutation`. Do not use `isinstance(..., str) else None` or `else ""` normalization for raw candidate mappings. | Task 1 |
| Discovery dedupe keys | Dedupe explicit structured candidates by canonical candidate payload fingerprint. Do not use `(ticket_id, action, evidence_summary)` because it can collapse two different target writes that share one honest reason line. | Task 2 |
| `key_files` create projection and validation | Treat `Key Files` as a valid source create section only when projected through the create adapter into `_plan_create()`/`_execute_create()`. Patch `ticket_validate.py` in the same task as the create projection test so `key_files` is not rejected before rendering; do not make `key_files` a valid non-create target write field. | Task 3 |
| Target list canonicalization | Reject duplicate names in `target.fields` or `target.sections`, reject overlap between the two target lists, and hash target names in sorted order so equivalent target envelopes do not produce different mutation identities solely from caller ordering. | Tasks 1 and 2 |
| Create candidate allocation binding | For `create`, allocate the target ID/path under a create-allocation-wide gateway lock, record the retained binding plus expected post-write recovery fingerprint and exact generated history metadata before file write, and make same-gateway retry reuse that binding. Ordinary `_plan_create()` duplicate detection is not a substitute. Prior-turn ledger projection must also understand the retained allocation path so an occupied allocated path can be matched against the retained expected post-write fingerprint without a fresh candidate. | Task 3A and Task 5 |
| Fresh create duplicate preflight | Preserve `_plan_create()` duplicate/current-state detection for fresh create attempts before recording an allocation. Retained allocation recovery applies only after an existing `mutation_attempt` for the same create candidate is present. | Task 3A |
| `reprioritize`, `stale_cleanup`, `blocker_edit`, `refine` action literals | These are not target candidate actions. Fold write behavior into ordinary `update` candidates, delete old runtime/gateway/test action branches, and keep `stale_cleanup` only as read-only review-hygiene output that candidate discovery no longer accepts as a write candidate. | Tasks 1, 2, 5, and final residue check |
| `reopen_reason` and `Reopen History` normal write behavior | Move human reason to `evidence_summary`, append ordinary generated `Change History`, and rewrite/remove tests or helpers that preserve `Reopen History` as target behavior. | Task 4 |
| `evidence_kind`, `current_mode`, `"decision"`, and `decision.kind` mutation-attempt details | Remove from target candidate operation-log event details unless a separate operation-log redesign explicitly keeps a bounded mechanical fact allowed by the control doc. Runtime mode inputs may keep `current_mode` only when they are not persisted mutation-attempt details. `RuntimeDecisionKind` values may remain internal branch logic, but must not be persisted in mutation-attempt details or result data. | Task 5 |
| `expected_post_write_fingerprint`, `post_write_fingerprint`, and generated `Change History` metadata | Mutation attempts must retain the expected post-write fingerprint and exact generated history metadata before the file write. `ticket_written` may still record the observed `post_write_fingerprint`, but it cannot be the only source for recovery after a crash between file write and `ticket_written`. Create writes get this boundary in Task 3A; non-create/correction recovery gets it in Task 5. | Task 3A and Task 5 |
| `archive`, `delete`, `history_repair`, `summarize`, `compact`, `pause_automation` action vocabulary | These are not target candidate actions. Keep maintenance vocabulary only in event-type-specific validation or hard discussion guards where the code is not recording a retained candidate action fact. Do not let these values validate a new `mutation_attempt` or `mutation_status`/`ticket_written` candidate action. | Task 5 and final residue check |
| `ticket_write` event wording | There is no live `ticket_write` operation-log event type in this source snapshot. Use `mutation_status` with status `ticket_written`, or explicitly add a new event type and schema/test coverage in the same task. This plan must not refer to `ticket_write` as an existing event boundary. | Task 5 |
| `codex.ticket.mutation.v1` candidate identity fixtures | Replace candidate-contract identity helpers and fixtures with `codex.ticket.mutation.v2`. Low-level `make_mutation_id()` tests may keep arbitrary v1 schema examples only when they are not candidate-contract fixtures. | Task 2 and final residue check |
| `EngineDispatch.sections` for close/reopen | Do not compute sections and drop them. Either pass them to engine execution or explicitly validate that the engine-owned side effect exactly matches the named target cleanup. | Tasks 3 and 4 |

Tests that encode deprecated architecture must be rewritten or removed in the
same task that removes the behavior. Do not defer them to Task 7 as
"pre-existing unrelated failures."

## Task 0: Preflight And Ticket Inventory Gate

**Files:**
- Read: `docs/tickets/*.md`
- Read: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `docs/superpowers/plans/2026-06-04-ticket-target-status-candidate-shape.md`
- Read: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Read: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Confirm clean source state**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
```

Expected at the last reviewed source baseline before the Task 1/2 boundary,
TERMS, and resume-path plan patch:

```text
## main...origin/main [ahead 17]
18d40178
```

If `HEAD` has advanced, run `git diff --stat 18d40178..HEAD` and re-check the
plan against the new diff before using the expected output as a gate. If the
only diff is this plan, record the live status and continue. If source files
changed, re-check the implementation steps against the new source before
continuing. If normal status is dirty before implementation, inspect the dirty
files and stop unless they are this plan or intentional implementation work for
the active task.

- [ ] **Step 2: Confirm authority surfaces still agree**

Read the May 30 control doc, ADR 0006, `ticket-contract.md`, and the
docs-contract lifecycle assertions before touching source. Confirm the active
status set is still `idea`, `open`, `blocked`, `done`, and `wontfix`, and that
this plan's source changes either update every conflicting lifecycle doc/test
assertion in the same slice or name an intentional deferral.

Record the exact current conflict before implementation:

```text
ticket-contract.md currently says `done` and `wontfix` reopen to `open`;
test_docs_contract.py currently asserts that sentence. Task 6 must update both
to document terminal reopen to `open` or `blocked` before final verification.
```

If ADR 0006, the May 30 control doc, `ticket-contract.md`, or
`test_docs_contract.py` disagree on target status/action/result vocabulary in a
way not already named by this plan, stop and patch the plan before source work.

- [ ] **Step 3: Re-run the active ticket inventory**

Run this read-only inventory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run python - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str((root / "plugins" / "turbo-mode" / "ticket").resolve()))

from scripts.ticket_read import list_tickets  # noqa: E402

tickets_dir = root / "docs" / "tickets"
tickets = sorted(list_tickets(tickets_dir), key=lambda ticket: ticket.id)
for ticket in tickets:
    path = Path(ticket.path)
    display = path.relative_to(root) if path.is_absolute() else path
    print(f"{display} status={ticket.status!r} invalid=[]")
PY
```

Expected:

```text
docs/tickets/T-20260508-01.md status='done' invalid=[]
docs/tickets/T-20260508-02.md status='open' invalid=[]
docs/tickets/T-20260516-01.md status='open' invalid=[]
docs/tickets/T-20260517-01.md status='open' invalid=[]
docs/tickets/T-20260518-01.md status='open' invalid=[]
docs/tickets/T-20260518-02.md status='open' invalid=[]
docs/tickets/T-20260526-01.md status='open' invalid=[]
```

- [ ] **Step 4: Stop if active ticket inventory is not clean**

If the command exits non-zero, if `list_tickets()` raises `InvalidTicketState`,
or if the active ticket list differs from the expected inventory, stop this plan
and create a separate diagnostic inventory or ticket-data migration plan. Do not
silently repair `docs/tickets/` inside this candidate-contract slice.

- [ ] **Step 5: Run the migration coverage and construction-site greps**

Run both `rg` commands from `Migration Coverage Map` and paste the hit summaries
into the active implementation notes. The output does not need to be clean at
Task 0; each hit needs an assigned task or an explicit "legacy direct
engine/diagnostic surface intentionally kept" disposition before source edits
start. Do not start Task 1 until `ticket_autonomy.py` and every
`GatewayMutation(...)` construction site have an assigned task.

- [ ] **Step 6: Commit Task 0 only if it changed this plan**

Task 0 normally makes no source changes and should not be committed by itself. If Task 0 is only a preflight run, continue to Task 1.

## Task 1: Add Target Candidate Runtime Shape

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Test: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`

- [ ] **Step 1: Write failing runtime shape tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, replace the
helper imports and helper constructors with target-shaped versions. Rewrite or
remove every old-contract test that depends on `EvidenceLink`, `evidence=`,
`blocker_edit`, `refine`, `reprioritize`, `stale_cleanup`,
`target_fingerprint`, `"correction"`, `conflict_reason`, or
`reopen_reason`. Keep only tests for target-contract invariants, mechanical
mode/fanout gates, destructive-action discussion gates, and target engine
dispatch. If conflicting evidence is still represented in source, it must block
before `CandidateMutation` construction or live outside candidate content.

Add these tests near the top of the file after `_decisions()`:

```python
from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    CandidateTarget,
    EngineAction,
    RuntimeDecisionKind,
    candidate_mapping_errors,
    candidate_mutation_from_mapping,
    evaluate_autonomy_intent,
    map_candidate_to_engine,
)


def _target(
    *,
    fields: tuple[str, ...] = ("priority",),
    sections: tuple[str, ...] = (),
) -> CandidateTarget:
    return CandidateTarget(fields=fields, sections=sections)


def _candidate(
    action: str,
    *,
    ticket_id: str | None = "T-20260527-01",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = "state-T-20260527-01",
    evidence_summary: str = "Current turn justifies this ticket change.",
) -> CandidateMutation:
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target or _target(),
        proposed_change={"priority": "low"} if proposed_change is None else proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def _intent(*candidates: CandidateMutation, **context: object) -> AutonomyIntent:
    source_context: dict[str, object] = {}
    source_context.update(context)
    return AutonomyIntent(
        action_kind=candidates[0].action if candidates else "update",
        candidates=tuple(candidates),
        source_context=source_context,
    )
```

Add these RED tests:

```python
def test_candidate_mapping_rejects_unknown_top_level_keys() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
            "legacy_reason": "old shape",
        }
    )

    assert errors == ["unknown candidate keys: ['legacy_reason']"]


def test_candidate_mapping_rejects_missing_top_level_keys() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
        }
    )

    assert errors == ["missing candidate keys: ['evidence_summary']"]


def test_candidate_mapping_rejects_conflict_reason_as_candidate_content() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
            "conflict_reason": "conflicting evidence",
        }
    )

    assert errors == ["unknown candidate keys: ['conflict_reason']"]


def test_candidate_mapping_requires_exact_target_closure() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": ["Next Action"]},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == [
        "proposed_change keys must exactly match target fields and sections; missing ['Next Action']; extra []"
    ]


@pytest.mark.parametrize("action", ("create", "update", "done", "wontfix", "reopen", "correct"))
def test_candidate_mapping_rejects_empty_target(action: str) -> None:
    ticket_id = None if action == "create" else "T-20260527-01"
    expected_ticket_fingerprint = None if action == "create" else "state-T-20260527-01"

    errors = candidate_mapping_errors(
        {
            "action": action,
            "ticket_id": ticket_id,
            "target": {"fields": [], "sections": []},
            "proposed_change": {},
            "expected_ticket_fingerprint": expected_ticket_fingerprint,
            "evidence_summary": "Current turn justifies this ticket change.",
        }
    )

    assert "target must name at least one field or section" in errors


def test_candidate_mapping_rejects_duplicate_target_names() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority", "priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == ["target.fields contains duplicate names: ['priority']"]


def test_candidate_mapping_rejects_field_section_overlap() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": ["priority"]},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == ["target names cannot appear in both fields and sections: ['priority']"]


def test_candidate_mapping_rejects_invalid_target_section_names() -> None:
    for section_name in ("Bad\nName", "Bad | Name", "### Bad"):
        errors = candidate_mapping_errors(
            {
                "action": "update",
                "ticket_id": "T-20260527-01",
                "target": {"fields": ["priority"], "sections": [section_name]},
                "proposed_change": {"priority": "high", section_name: "unsafe"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed after this turn.",
            }
        )

        assert errors == [
            f"target.sections contains invalid section names: {[section_name]!r}"
        ]


def test_create_allows_null_ticket_id_and_null_expected_fingerprint() -> None:
    candidate = candidate_mutation_from_mapping(
        {
            "action": "create",
            "ticket_id": None,
            "target": {"fields": ["title", "priority"], "sections": ["Problem", "Next Action"]},
            "proposed_change": {
                "title": "Add retry to publisher",
                "priority": "high",
                "Problem": "Publisher drops transient broker messages.",
                "Next Action": "Add retry around broker publish.",
            },
            "expected_ticket_fingerprint": None,
            "evidence_summary": "The user asked to track the publisher retry follow-up.",
        }
    )

    assert candidate is not None
    assert candidate.ticket_id is None
    assert candidate.target.fields == ("title", "priority")
    assert candidate.target.sections == ("Problem", "Next Action")
    assert candidate.expected_ticket_fingerprint is None


def test_create_rejects_wrong_type_ticket_id_and_expected_fingerprint() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "create",
            "ticket_id": 123,
            "target": {"fields": ["title"], "sections": ["Problem", "Next Action"]},
            "proposed_change": {
                "title": "Add retry to publisher",
                "Problem": "Publisher drops transient broker messages.",
                "Next Action": "Add retry around broker publish.",
            },
            "expected_ticket_fingerprint": 123,
            "evidence_summary": "The user asked to track the publisher retry follow-up.",
        }
    )

    assert errors == [
        "ticket_id must be a string or null",
        "expected_ticket_fingerprint must be a string or null",
    ]


def test_candidate_mapping_rejects_wrong_type_action_and_evidence_summary() -> None:
    errors = candidate_mapping_errors(
        {
            "action": ["update"],
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": {"reason": "Priority changed."},
        }
    )

    assert errors == [
        "action must be a string",
        "evidence_summary must be a string",
    ]


def test_non_create_requires_expected_ticket_fingerprint() -> None:
    decision = _decisions(
        _candidate("update", expected_ticket_fingerprint=None),
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "expected_ticket_fingerprint_required"
    assert decision.mutation_id is None


def test_reopen_uses_evidence_summary_not_reopen_reason() -> None:
    rejected = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open", "reopen_reason": "Regression recurred."},
        )
    )
    accepted = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
            evidence_summary="Regression recurred.",
        )
    )

    assert rejected.state == "policy_blocked"
    assert rejected.reason == "target_closure_failed"
    assert accepted.action == EngineAction.REOPEN
    assert accepted.fields == {"status": "open"}
```

- [ ] **Step 2: Run focused runtime tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py -q
```

Expected: fail with import errors for `CandidateTarget`, `candidate_mapping_errors`, or `candidate_mutation_from_mapping`.

- [ ] **Step 3: Implement the target candidate dataclasses and mapping helpers**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, replace `EvidenceLink` and `CandidateMutation` with this target-shaped model and helper block:

```python
@dataclass(frozen=True, slots=True)
class CandidateTarget:
    """User-visible fields and sections a candidate intends to change."""

    fields: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateMutation:
    """A proposed target Ticket mutation candidate."""

    ticket_id: str | None
    action: str
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    expected_ticket_fingerprint: str | None
    evidence_summary: str
```

Add these constants and helpers near the candidate model:

```python
from scripts.ticket_target_schema import validate_target_section_name


_TARGET_FRONTMATTER_FIELDS = frozenset(
    {"title", "status", "priority", "tags", "related_paths", "blocked_by"}
)
_ALLOWED_ACTIONS = frozenset({"create", "update", "done", "wontfix", "reopen", "correct"})
_ALLOWED_CANDIDATE_KEYS = frozenset(
    {
        "action",
        "ticket_id",
        "target",
        "proposed_change",
        "expected_ticket_fingerprint",
        "evidence_summary",
    }
)
_FORBIDDEN_TARGET_SECTIONS = frozenset({"Change History"})


def _string_tuple(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list | tuple):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item.strip() != item:
            return None
        result.append(item)
    return tuple(result)


def _target_from_mapping(value: object) -> CandidateTarget | None:
    if not isinstance(value, Mapping):
        return None
    if set(value) != {"fields", "sections"}:
        return None
    fields = _string_tuple(value.get("fields"))
    sections = _string_tuple(value.get("sections"))
    if fields is None or sections is None:
        return None
    return CandidateTarget(fields=fields, sections=sections)


def _line_shaped(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


def _target_keys(target: CandidateTarget) -> set[str]:
    return set(target.fields) | set(target.sections)


def _duplicate_names(values: tuple[str, ...]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _candidate_shape_errors(candidate: CandidateMutation) -> list[str]:
    errors: list[str] = []
    if candidate.action not in _ALLOWED_ACTIONS:
        errors.append(f"action must be one of {sorted(_ALLOWED_ACTIONS)!r}")
    if candidate.action == "create":
        if candidate.ticket_id is not None:
            errors.append("ticket_id must be null for create")
        if candidate.expected_ticket_fingerprint is not None:
            errors.append("expected_ticket_fingerprint must be null for create")
    else:
        if not isinstance(candidate.ticket_id, str) or not candidate.ticket_id:
            errors.append(f"ticket_id is required for {candidate.action}")
        if not isinstance(candidate.expected_ticket_fingerprint, str) or not candidate.expected_ticket_fingerprint:
            errors.append("expected_ticket_fingerprint is required for non-create writes")
    invalid_fields = sorted(field for field in candidate.target.fields if field not in _TARGET_FRONTMATTER_FIELDS)
    if invalid_fields:
        errors.append(f"target.fields contains invalid frontmatter fields: {invalid_fields!r}")
    duplicate_fields = _duplicate_names(candidate.target.fields)
    if duplicate_fields:
        errors.append(f"target.fields contains duplicate names: {duplicate_fields!r}")
    duplicate_sections = _duplicate_names(candidate.target.sections)
    if duplicate_sections:
        errors.append(f"target.sections contains duplicate names: {duplicate_sections!r}")
    invalid_sections = sorted(
        section
        for section in candidate.target.sections
        if not validate_target_section_name(section)
    )
    if invalid_sections:
        errors.append(f"target.sections contains invalid section names: {invalid_sections!r}")
    overlapping_names = sorted(set(candidate.target.fields) & set(candidate.target.sections))
    if overlapping_names:
        errors.append(f"target names cannot appear in both fields and sections: {overlapping_names!r}")
    forbidden_sections = sorted(set(candidate.target.sections) & _FORBIDDEN_TARGET_SECTIONS)
    if forbidden_sections:
        errors.append(f"target.sections cannot name kernel-owned sections: {forbidden_sections!r}")
    expected_keys = _target_keys(candidate.target)
    if not expected_keys:
        errors.append("target must name at least one field or section")
    actual_keys = set(candidate.proposed_change)
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        errors.append(
            "proposed_change keys must exactly match target fields and sections; "
            f"missing {missing!r}; extra {extra!r}"
        )
    if not _line_shaped(candidate.evidence_summary):
        errors.append("evidence_summary must be a non-empty single line")
    return errors


def candidate_mapping_errors(item: Mapping[str, object]) -> list[str]:
    unknown = sorted(set(item) - _ALLOWED_CANDIDATE_KEYS)
    if unknown:
        return [f"unknown candidate keys: {unknown!r}"]
    missing = sorted(_ALLOWED_CANDIDATE_KEYS - set(item))
    if missing:
        return [f"missing candidate keys: {missing!r}"]
    errors: list[str] = []
    action = item.get("action")
    ticket_id = item.get("ticket_id")
    expected_ticket_fingerprint = item.get("expected_ticket_fingerprint")
    evidence_summary = item.get("evidence_summary")
    if not isinstance(action, str):
        errors.append("action must be a string")
    if ticket_id is not None and not isinstance(ticket_id, str):
        errors.append("ticket_id must be a string or null")
    if expected_ticket_fingerprint is not None and not isinstance(expected_ticket_fingerprint, str):
        errors.append("expected_ticket_fingerprint must be a string or null")
    if not isinstance(evidence_summary, str):
        errors.append("evidence_summary must be a string")
    if errors:
        return errors
    target = _target_from_mapping(item.get("target"))
    if target is None:
        return ["target must contain exactly fields and sections lists"]
    proposed_change = item.get("proposed_change")
    if not isinstance(proposed_change, Mapping):
        return ["proposed_change must be an object"]
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )
    return _candidate_shape_errors(candidate)


def candidate_mutation_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    if candidate_mapping_errors(item):
        return None
    target = _target_from_mapping(item["target"])
    if target is None:
        return None
    proposed_change = item["proposed_change"]
    if not isinstance(proposed_change, Mapping):
        return None
    ticket_id = item["ticket_id"]
    action = item["action"]
    expected_ticket_fingerprint = item["expected_ticket_fingerprint"]
    evidence_summary = item["evidence_summary"]
    if not isinstance(action, str) or not isinstance(evidence_summary, str):
        return None
    if ticket_id is not None and not isinstance(ticket_id, str):
        return None
    if expected_ticket_fingerprint is not None and not isinstance(expected_ticket_fingerprint, str):
        return None
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )
```

- [ ] **Step 4: Update runtime dispatch to enforce target closure and target actions**

Replace `_requires_discussion`, `_close_fields_are_allowlisted`, and the reopen branch of `map_candidate_to_engine()` with target-shape checks:

```python
def _target_shape_valid(candidate: CandidateMutation) -> bool:
    return not _candidate_shape_errors(candidate)


def _close_target_is_valid(
    candidate: CandidateMutation,
    resolution: str,
    *,
    current_ticket_status: str | None = None,
) -> bool:
    target_fields = set(candidate.target.fields)
    target_sections = set(candidate.target.sections)
    open_close = target_fields == {"status"} and not target_sections
    blocked_close_cleanup = (
        target_fields == {"status", "blocked_by"}
        and target_sections == {"Blocked On"}
        and candidate.proposed_change.get("blocked_by") == []
        and candidate.proposed_change.get("Blocked On") is None
    )
    if candidate.proposed_change.get("status") != resolution:
        return False
    if current_ticket_status == "blocked":
        return blocked_close_cleanup
    return open_close or blocked_close_cleanup


def _nonempty_target_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _blocked_to_open_target_is_valid(
    candidate: CandidateMutation,
    *,
    current_ticket_status: str | None = None,
) -> bool:
    if current_ticket_status != "blocked" or candidate.proposed_change.get("status") != "open":
        return True
    return (
        set(candidate.target.fields) == {"status", "blocked_by"}
        and set(candidate.target.sections) == {"Blocked On", "Next Action"}
        and candidate.proposed_change.get("blocked_by") == []
        and candidate.proposed_change.get("Blocked On") is None
        and _nonempty_target_text(candidate.proposed_change.get("Next Action"))
    )


def _reopen_target_is_valid(candidate: CandidateMutation) -> bool:
    target_status = candidate.proposed_change.get("status")
    target_fields = set(candidate.target.fields)
    target_sections = set(candidate.target.sections)
    if target_status == "open":
        return target_fields == {"status"} and not target_sections
    if target_status == "blocked":
        return (
            target_fields == {"status", "blocked_by"}
            and target_sections == {"Blocked On"}
            and isinstance(candidate.proposed_change.get("blocked_by"), list)
            and _nonempty_target_text(candidate.proposed_change.get("Blocked On"))
        )
    return False


def map_candidate_to_engine(
    candidate: CandidateMutation,
    *,
    gateway_approved: bool = True,
    current_ticket_status: str | None = None,
) -> EngineDispatch:
    """Map one target-shaped candidate to deterministic engine dispatch."""
    if not _target_shape_valid(candidate):
        return EngineDispatch("policy_blocked", None, {}, reason="target_closure_failed")
    fields = {
        key: value
        for key, value in candidate.proposed_change.items()
        if key in candidate.target.fields
    }
    sections = {
        key: value
        for key, value in candidate.proposed_change.items()
        if key in candidate.target.sections
    }
    if candidate.action == "done":
        if not _close_target_is_valid(
            candidate,
            "done",
            current_ticket_status=current_ticket_status,
        ):
            return EngineDispatch("policy_blocked", None, {}, reason="close_target_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "done"}, sections=sections)
    if candidate.action == "wontfix":
        if not _close_target_is_valid(
            candidate,
            "wontfix",
            current_ticket_status=current_ticket_status,
        ):
            return EngineDispatch("policy_blocked", None, {}, reason="close_target_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "wontfix"}, sections=sections)
    if candidate.action == "reopen":
        if not gateway_approved:
            return EngineDispatch("policy_blocked", None, {}, reason="gateway_required")
        if fields.get("status") not in {"open", "blocked"}:
            return EngineDispatch("policy_blocked", None, {}, reason="reopen_status_required")
        if not _reopen_target_is_valid(candidate):
            return EngineDispatch("policy_blocked", None, {}, reason="reopen_target_not_allowlisted")
        return EngineDispatch("ok", EngineAction.REOPEN, fields, sections=sections)
    if candidate.action == "correct":
        if fields.get("status") in {"done", "wontfix"}:
            if not _close_target_is_valid(
                candidate,
                fields["status"],
                current_ticket_status=current_ticket_status,
            ):
                return EngineDispatch("policy_blocked", None, {}, reason="close_target_not_allowlisted")
            return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": fields["status"]}, sections=sections)
        if fields.get("status") in {"open", "blocked"}:
            if current_ticket_status in {"done", "wontfix"}:
                if not _reopen_target_is_valid(candidate):
                    return EngineDispatch("policy_blocked", None, {}, reason="reopen_target_not_allowlisted")
                return EngineDispatch("ok", EngineAction.REOPEN, fields, sections=sections)
            if not _blocked_to_open_target_is_valid(
                candidate,
                current_ticket_status=current_ticket_status,
            ):
                return EngineDispatch("policy_blocked", None, {}, reason="blocked_to_open_target_not_allowlisted")
            return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
        return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
    if candidate.action == "update":
        if not _blocked_to_open_target_is_valid(
            candidate,
            current_ticket_status=current_ticket_status,
        ):
            return EngineDispatch("policy_blocked", None, {}, reason="blocked_to_open_target_not_allowlisted")
        return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
    if candidate.action == "create":
        return EngineDispatch("ok", EngineAction.CREATE, fields, sections=sections)
    return EngineDispatch("policy_blocked", None, {}, reason="unsupported_action")
```

Add a runtime dispatch test for blocked close cleanup:

```python
def test_blocked_close_status_only_target_is_rejected() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "done",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "done"},
        ),
        current_ticket_status="blocked",
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "close_target_not_allowlisted"


def test_blocked_close_target_names_blocker_cleanup() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "done",
            target=_target(fields=("status", "blocked_by"), sections=("Blocked On",)),
            proposed_change={"status": "done", "blocked_by": [], "Blocked On": None},
        ),
        current_ticket_status="blocked",
    )

    assert dispatch.action == EngineAction.CLOSE
    assert dispatch.fields == {"resolution": "done"}
    assert dispatch.sections == {"Blocked On": None}


def test_correct_close_rejects_mixed_status_and_metadata_target() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status", "priority"), sections=()),
            proposed_change={"status": "done", "priority": "high"},
        )
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "close_target_not_allowlisted"


def test_correct_active_status_defaults_to_update_without_current_terminal_status() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status", "blocked_by"), sections=("Blocked On",)),
            proposed_change={
                "status": "blocked",
                "blocked_by": ["T-20260527-02"],
                "Blocked On": "Waiting for T-20260527-02.",
            },
        )
    )

    assert dispatch.action == EngineAction.UPDATE
    assert dispatch.fields == {
        "status": "blocked",
        "blocked_by": ["T-20260527-02"],
    }
    assert dispatch.sections == {"Blocked On": "Waiting for T-20260527-02."}


def test_correct_reopens_only_when_current_ticket_is_terminal() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
        ),
        current_ticket_status="done",
    )

    assert dispatch.action == EngineAction.REOPEN
    assert dispatch.fields == {"status": "open"}
```

Update `EngineDispatch` to carry target sections:

```python
@dataclass(frozen=True, slots=True)
class EngineDispatch:
    """Gateway-local dispatch projection for a candidate."""

    state: str
    action: EngineAction | None
    fields: dict[str, object]
    reason: str | None = None
    sections: dict[str, object] | None = None
```

Use keyword arguments for `reason=` and `sections=` in every new `EngineDispatch(...)` construction. Do not rely on the fourth positional argument after adding `sections`.

- [ ] **Step 5: Update identity calls to use expected fingerprint and evidence summary**

First update the identity helper in `ticket_mutation_identity.py` using Task 2
Step 4's target-shaped helper. This prevents the new runtime
`_identity_for_candidate()` call from raising `TypeError` while Task 1 is still
in progress.

Replace `_identity_for_candidate()` with:

```python
def _identity_for_candidate(
    *,
    candidate: CandidateMutation,
    thread_id: str,
    turn_id: str,
) -> CandidateMutationIdentity:
    return make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        target=candidate.target,
        proposed_change=candidate.proposed_change,
        expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
        evidence_summary=candidate.evidence_summary,
    )
```

Update evaluator branches so non-create writes block with reason
`expected_ticket_fingerprint_required` when
`candidate.expected_ticket_fingerprint is None`. Remove calls to
`_target_fingerprint_for_candidate()`, remove evidence-link floors that classify
evidence kinds, and replace any runtime `if candidate.action == "correction"`
branch with `if candidate.action == "correct"` in this task. Keep mode, fanout,
hard destructive-action, and correction-detail mechanical gates. Conflict facts
must not live on `CandidateMutation`; if current source still needs a conflict
boundary, handle it before target candidate construction or as a short
mechanical pause reason outside candidate content.

- [ ] **Step 6: Run focused runtime and identity tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py -q
```

Expected: the runtime and identity helper tests pass after Step 5. If discovery
tests still fail, continue to Task 2 before committing; Task 1 is not a
standalone green boundary.

- [ ] **Step 7: Do not commit Task 1 by itself**

Continue directly to Task 2. Do not commit Task 1 by itself, and do not commit
the Task 1/2 runtime/discovery boundary before Task 3 migrates the gateway and
live apply-turn construction sites.

## Task 2: Migrate Candidate Discovery And Commit Runtime Identity

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Test: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- Test: `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`

- [ ] **Step 1: Write or verify target identity tests**

If Task 1 has not already updated
`plugins/turbo-mode/ticket/tests/test_mutation_identity.py`, replace the payload
tests with:

```python
from scripts.ticket_autonomy_runtime import CandidateTarget
from scripts.ticket_mutation_identity import (
    candidate_mutation_payload,
    make_candidate_mutation_identity,
)


def _identity(
    *,
    expected_ticket_fingerprint: str | None = "ticket-state-a",
    evidence_summary: str = "Priority changed after this turn.",
):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def test_expected_fingerprint_binds_mutation_identity() -> None:
    first = _identity(expected_ticket_fingerprint="ticket-state-a")
    second = _identity(expected_ticket_fingerprint="ticket-state-b")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_evidence_summary_binds_mutation_identity() -> None:
    first = _identity(evidence_summary="Priority changed after this turn.")
    second = _identity(evidence_summary="Priority changed after user review.")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_candidate_payload_uses_target_contract_keys() -> None:
    payload = candidate_mutation_payload(
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority",), sections=("Next Action",)),
        proposed_change={"priority": "high", "Next Action": "Finish the migration."},
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )

    assert payload == {
        "ticket_id": "T-20260527-01",
        "action": "update",
        "target": {"fields": ["priority"], "sections": ["Next Action"]},
        "proposed_change": {
            "priority": "high",
            "Next Action": "Finish the migration.",
        },
        "expected_ticket_fingerprint": "ticket-state-a",
        "evidence_summary": "Priority changed after this turn.",
    }


def test_candidate_identity_canonicalizes_target_order() -> None:
    first = make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority", "tags"), sections=("Context", "Next Action")),
        proposed_change={
            "priority": "high",
            "tags": ["ticket"],
            "Context": "Important context.",
            "Next Action": "Finish the migration.",
        },
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )
    second = make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("tags", "priority"), sections=("Next Action", "Context")),
        proposed_change={
            "Next Action": "Finish the migration.",
            "Context": "Important context.",
            "tags": ["ticket"],
            "priority": "high",
        },
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )

    assert first.mutation_fingerprint == second.mutation_fingerprint
    assert first.mutation_id == second.mutation_id
```

- [ ] **Step 2: Write failing discovery tests**

In `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`, import
`InvalidCandidateMutations` from `scripts.ticket_candidate_discovery` and update
explicit candidate tests:

```python
def test_discovers_explicit_target_candidate_mutations(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Codex identified a clear priority update.",
            }
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 1
    assert candidates[0].ticket_id == "T-20260527-01"
    assert candidates[0].action == "update"
    assert candidates[0].target.fields == ("priority",)
    assert candidates[0].target.sections == ()
    assert candidates[0].proposed_change == {"priority": "high"}
    assert candidates[0].expected_ticket_fingerprint == "state-T-20260527-01"
    assert candidates[0].evidence_summary == "Codex identified a clear priority update."


def test_structured_candidates_reject_deprecated_ticket_change_scope(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed.",
                "ticket_change_scope": "unrelated_backlog",
            },
        ]
    )

    with pytest.raises(InvalidCandidateMutations) as exc_info:
        discover_candidate_mutations(context, tickets_dir)

    assert exc_info.value.as_payload() == [
        {
            "key": "candidate_mutations",
            "index": 0,
            "errors": ["unknown candidate keys: ['ticket_change_scope']"],
        }
    ]


@pytest.mark.parametrize(
    "context_key",
    ("candidate_mutations", "update_candidates", "capture_candidates"),
)
def test_malformed_explicit_candidate_arrays_raise_invalid_candidate(
    tmp_path: Path,
    context_key: str,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        **{
            context_key: [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": "state-T-20260527-01",
                },
            ]
        }
    )

    with pytest.raises(InvalidCandidateMutations) as exc_info:
        discover_candidate_mutations(context, tickets_dir)

    assert exc_info.value.as_payload() == [
        {
            "key": context_key,
            "index": 0,
            "errors": ["missing candidate keys: ['evidence_summary']"],
        }
    ]


def test_vague_and_path_only_signals_do_not_create_write_candidates(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-01",
        related_paths=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
    )
    context = _context(
        touched_files=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
        possible_candidates=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "reason": "Maybe later cleanup theme is too broad to apply automatically.",
            }
        ],
    )

    assert discover_candidate_mutations(context, tickets_dir) == ()


def test_discovery_keeps_distinct_target_candidates_with_same_summary(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Current turn justifies a ticket update.",
            },
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": [], "sections": ["Next Action"]},
                "proposed_change": {"Next Action": "Finish the exact contract migration."},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Current turn justifies a ticket update.",
            },
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 2
    assert candidates[0].proposed_change == {"priority": "high"}
    assert candidates[1].proposed_change == {
        "Next Action": "Finish the exact contract migration."
    }
```

Add one discovery test that `reprioritize`, `stale_cleanup`, `blocker_edit`, and
`refine` mappings are not accepted as target candidate actions. `stale_cleanup`
may remain read-only output from `ticket_review.py`, but
`discover_candidate_mutations()` must not convert `review_hygiene_findings` into
write candidates in this slice.

- [ ] **Step 3: Run identity and discovery tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py -q
```

Expected: before implementation, fail because identity still accepts
`target_fingerprint` and discovery still emits old flat candidates. If Task 1
already migrated identity, the remaining RED should be in discovery only.

- [ ] **Step 4: Update identity helper**

If Task 1 has not already updated the helper, replace
`candidate_mutation_payload()` and `make_candidate_mutation_identity()` in
`ticket_mutation_identity.py` with:

```python
from typing import Protocol


class CandidateTargetLike(Protocol):
    fields: tuple[str, ...]
    sections: tuple[str, ...]


def candidate_mutation_payload(
    *,
    ticket_id: str | None,
    action: str,
    target: CandidateTargetLike,
    proposed_change: Mapping[str, object],
    expected_ticket_fingerprint: str | None,
    evidence_summary: str,
) -> dict[str, object]:
    """Return the canonical target candidate payload used for mutation identity."""
    return {
        "ticket_id": ticket_id,
        "action": action,
        "target": {
            "fields": sorted(target.fields),
            "sections": sorted(target.sections),
        },
        "proposed_change": dict(proposed_change),
        "expected_ticket_fingerprint": expected_ticket_fingerprint,
        "evidence_summary": evidence_summary,
    }


def make_candidate_mutation_identity(
    *,
    thread_id: str,
    turn_id: str,
    ticket_id: str | None,
    action: str,
    target: CandidateTargetLike,
    proposed_change: Mapping[str, object],
    expected_ticket_fingerprint: str | None,
    evidence_summary: str,
) -> CandidateMutationIdentity:
    """Calculate deterministic identity for one target candidate mutation."""
    mutation_fingerprint = sha256_fingerprint(
        candidate_mutation_payload(
            ticket_id=ticket_id,
            action=action,
            target=target,
            proposed_change=proposed_change,
            expected_ticket_fingerprint=expected_ticket_fingerprint,
            evidence_summary=evidence_summary,
        )
    )
    evidence_fingerprint = sha256_fingerprint({"evidence_summary": evidence_summary})
    mutation_id = make_mutation_id(
        schema="codex.ticket.mutation.v2",
        thread_id=thread_id,
        turn_id=turn_id,
        action=action,
        ticket_id=ticket_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    return CandidateMutationIdentity(
        mutation_id=mutation_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
```

- [ ] **Step 5: Update candidate discovery to accept only explicit target candidates**

In `ticket_candidate_discovery.py`:

- Remove `EvidenceLink` import.
- Import `candidate_mapping_errors` and `candidate_mutation_from_mapping`.
- Import `sha256_fingerprint` from `ticket_autonomy_ids` and
  `candidate_mutation_payload` from `ticket_mutation_identity`.
- Replace `_candidate_from_mapping()` with:

```python
def _candidate_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    return candidate_mutation_from_mapping(item)
```

Add explicit invalid-candidate records before `_append_structured_candidates()`:

```python
@dataclass(frozen=True)
class InvalidCandidateMappingError:
    key: str
    index: int
    errors: tuple[str, ...]


class InvalidCandidateMutations(ValueError):
    def __init__(self, errors: Sequence[InvalidCandidateMappingError]) -> None:
        self.errors = tuple(errors)
        super().__init__(
            "candidate discovery failed: explicit candidate payload is invalid. "
            f"Got: {self.as_payload()!r:.100}"
        )

    def as_payload(self) -> list[dict[str, object]]:
        return [
            {"key": error.key, "index": error.index, "errors": list(error.errors)}
            for error in self.errors
        ]
```

Add the needed imports:

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
```

Replace `_append_structured_candidates()` with:

```python
def _append_structured_candidates(
    candidates: list[CandidateMutation],
    seen: set[str],
    turn_context: Mapping[str, object],
) -> None:
    invalid: list[InvalidCandidateMappingError] = []
    valid: list[CandidateMutation] = []
    for key in ("candidate_mutations", "update_candidates", "capture_candidates"):
        raw_items = turn_context.get(key, [])
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            invalid.append(
                InvalidCandidateMappingError(
                    key=key,
                    index=-1,
                    errors=("candidate list must be an array",),
                )
            )
            continue
        for index, item in enumerate(raw_items):
            if not isinstance(item, Mapping):
                invalid.append(
                    InvalidCandidateMappingError(
                        key=key,
                        index=index,
                        errors=("candidate item must be an object",),
                    )
                )
                continue
            errors = tuple(candidate_mapping_errors(item))
            if errors:
                invalid.append(InvalidCandidateMappingError(key=key, index=index, errors=errors))
                continue
            candidate = _candidate_from_mapping(item)
            if candidate is None:
                invalid.append(
                    InvalidCandidateMappingError(
                        key=key,
                        index=index,
                        errors=("candidate item failed target shape construction",),
                    )
                )
                continue
            valid.append(candidate)
    if invalid:
        raise InvalidCandidateMutations(invalid)
    for candidate in valid:
        _append_candidate(candidates, seen, candidate)
```

Replace `_append_candidate()` with:

```python
def _append_candidate(
    candidates: list[CandidateMutation],
    seen: set[str],
    candidate: CandidateMutation,
) -> None:
    key = sha256_fingerprint(
        candidate_mutation_payload(
            ticket_id=candidate.ticket_id,
            action=candidate.action,
            target=candidate.target,
            proposed_change=candidate.proposed_change,
            expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
            evidence_summary=candidate.evidence_summary,
        )
    )
    if key in seen:
        return
    seen.add(key)
    candidates.append(candidate)
```

Remove `_possible_candidate_from_mapping()`, `_path_refs()`, `_append_path_candidates()`, and the call to `_append_path_candidates()` from `discover_candidate_mutations()`. Keep `_ticket_metadata_paths()` only if another local function still uses it; otherwise remove it too.

- [ ] **Step 6: Run runtime, identity, and discovery tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py -q
```

Expected: all three files pass.

- [ ] **Step 7: Treat Tasks 1 and 2 as an internal checkpoint**

Do not run `git add` or `git commit` here. Record the Task 1/2 test output in
the active implementation notes and continue directly to Task 3.

Expected: runtime, identity, and discovery focused selectors pass, but this is
not a runnable source-correct boundary because `ticket_autonomy.py` and
`ticket_engine_gateway.py` still construct old-shaped gateway/runtime values
until Task 3. Task 3's commit stages the Task 1, Task 2, and Task 3 files
together.

## Task 3: Project Target Candidates Through Gateway, Entrypoint, And Engine

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`

- [ ] **Step 0: Write failing apply-turn invalid-candidate test**

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`, add this host-facing
regression test before the existing apply-turn mutation tests:

```python
def test_apply_turn_reports_invalid_explicit_candidate_without_no_change(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    context = _write_context(
        tmp_path,
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed.",
                "ticket_change_scope": "unrelated_backlog",
            },
        ],
    )

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    # Outer apply-turn host state; target mutation result vocabulary is not extended.
    assert payload == {
        "state": "invalid_candidate",
        "changed": False,
        "ticket_updates": None,
        "invalid_candidates": [
            {
                "key": "candidate_mutations",
                "index": 0,
                "errors": ["unknown candidate keys: ['ticket_change_scope']"],
            }
        ],
        "discussion_question": (
            "Fix the explicit Ticket candidate payload before automatic ticket mutation."
        ),
    }
```

Add the resume-paused source-context variant in the same file:

```python
def test_apply_turn_resume_source_context_pause_reports_invalid_candidate_and_keeps_pause(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    pause_workspace_automation(tmp_path, reason="source_context_unhealthy")
    context = _write_context(
        tmp_path,
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed.",
                "ticket_change_scope": "unrelated_backlog",
            },
        ],
    )

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
        "--setup-choice",
        "automatic",
        "--resume-paused",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "invalid_candidate"
    assert payload["changed"] is False
    assert payload["invalid_candidates"] == [
        {
            "key": "candidate_mutations",
            "index": 0,
            "errors": ["unknown candidate keys: ['ticket_change_scope']"],
        }
    ]
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()
```

- [ ] **Step 1: Write failing gateway tests for target update and create**

In `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`, update helpers to target shape:

```python
from scripts.ticket_autonomy_runtime import (
    AutonomyDecision,
    AutonomyIntent,
    CandidateMutation,
    CandidateTarget,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
)


def _target(
    *,
    fields: tuple[str, ...] = ("priority",),
    sections: tuple[str, ...] = (),
) -> CandidateTarget:
    return CandidateTarget(fields=fields, sections=sections)


def _decision_for(
    *,
    ticket_id: str | None,
    action: str = "update",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = "ticket-fp",
    evidence_summary: str = "Current turn justifies this ticket change.",
    turn_id: str = "turn-1",
):
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target or _target(),
        proposed_change=proposed_change or {"priority": "low"},
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind=action,
            candidates=(candidate,),
            source_context={},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id=turn_id,
        now=datetime.now(UTC),
    )[0]
```

Replace `_mutation()` with:

```python
def _mutation(
    tickets_dir: Path,
    ticket_path: Path,
    *,
    ticket_id: str = "T-20260527-01",
    action: str = "update",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
) -> GatewayMutation:
    expected = target_fingerprint(ticket_path)
    return GatewayMutation(
        action=action,
        ticket_id=ticket_id,
        target=target or _target(),
        proposed_change=proposed_change or {"priority": "low"},
        tickets_dir=tickets_dir,
        expected_ticket_fingerprint=expected,
        evidence_summary="Current turn justifies this ticket change.",
    )
```

Add this exact section update test:

```python
def test_gateway_applies_exact_target_section_update(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    target = CandidateTarget(fields=("priority",), sections=("Next Action",))
    proposed_change = {
        "priority": "low",
        "Next Action": "Finish the target candidate migration.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "priority: low" in text
    assert "## Next Action\nFinish the target candidate migration." in text
    assert "| codex | Updated ticket from candidate evidence." in text
```

Add this exact optional-section removal test. This must not use the special
`Blocked On` cleanup path:

```python
def test_gateway_removes_exact_optional_target_section(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    assert "## Verification" in ticket_path.read_text(encoding="utf-8")
    target = CandidateTarget(fields=(), sections=("Verification",))
    proposed_change = {"Verification": None}
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "## Verification" not in text
    assert "## Approach" in text
    assert "## Key Files" in text
    assert "| codex | Updated ticket from candidate evidence." in text
```

Add this blocked-to-open update test. This is the policy bridge guard: the
candidate names `Blocked On` as a target section, but update policy must still
see `blocked_on: null` before transition validation:

```python
def test_gateway_updates_blocked_ticket_to_open_with_target_section_cleanup(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(
        tmp_tickets,
        "one.md",
        id="T-20260527-01",
        status="blocked",
        blocked_by=["T-20260527-02"],
        blocked_on="Waiting for T-20260527-02.",
    )
    target = CandidateTarget(
        fields=("status", "blocked_by"),
        sections=("Blocked On", "Next Action"),
    )
    proposed_change = {
        "status": "open",
        "blocked_by": [],
        "Blocked On": None,
        "Next Action": "Continue the candidate-contract migration.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "status: open" in text
    assert "blocked_by: []" in text
    assert "## Blocked On" not in text
    assert "## Next Action\nContinue the candidate-contract migration." in text
    assert "| codex | Updated ticket from candidate evidence." in text
```

Add this blocked-to-open negative gateway test. It proves blocker cleanup alone
does not satisfy the visible unblocking contract when `Next Action` is missing:

```python
def test_gateway_rejects_blocked_to_open_without_next_action(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(
        tmp_tickets,
        "one.md",
        id="T-20260527-01",
        status="blocked",
        blocked_by=["T-20260527-02"],
        blocked_on="Waiting for T-20260527-02.",
    )
    target = CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",))
    proposed_change = {
        "status": "open",
        "blocked_by": [],
        "Blocked On": None,
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "policy_blocked"
    assert response.error_code == "policy_blocked"
    assert "blocked_to_open_target_not_allowlisted" in response.message
    assert "status: blocked" in text
    assert "blocked_by: [T-20260527-02]" in text
    assert "## Blocked On\nWaiting for T-20260527-02." in text
```

Add this blocked close negative gateway test. It proves the gateway passes the
current ticket status into runtime dispatch before `_execute_close()` can clear
blocker state:

```python
def test_gateway_rejects_status_only_close_for_blocked_ticket(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(
        tmp_tickets,
        "one.md",
        id="T-20260527-01",
        status="blocked",
        blocked_by=["T-20260527-02"],
        blocked_on="Waiting for T-20260527-02.",
    )
    target = CandidateTarget(fields=("status",), sections=())
    proposed_change = {"status": "done"}
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="done",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="done",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "blocked"
    assert "close_target_not_allowlisted" in response.message
    assert "status: blocked" in text
    assert "blocked_by: [T-20260527-02]" in text
    assert "## Blocked On\nWaiting for T-20260527-02." in text
```

Add this full create-section projection test so create projection matches every
section the source create renderer can emit, instead of only the four-section
helper:

```python
def test_gateway_create_accepts_every_source_supported_target_section(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    target = CandidateTarget(
        fields=("title", "status", "priority", "blocked_by"),
        sections=(
            "Problem",
            "Next Action",
            "Blocked On",
            "Captured Request",
            "Context",
            "Prior Investigation",
            "Approach",
            "Decisions Made",
            "Acceptance Criteria",
            "Verification",
            "Key Files",
            "Related",
        ),
    )
    proposed_change = {
        "title": "Add retry to publisher",
        "status": "blocked",
        "priority": "high",
        "blocked_by": ["T-20260605-02"],
        "Problem": "Publisher drops transient broker messages.",
        "Next Action": "Add retry around broker publish.",
        "Blocked On": "Waiting for T-20260605-02 to expose broker retry policy.",
        "Captured Request": "Track the publisher retry follow-up.",
        "Context": "Broker publishes sometimes fail transiently.",
        "Prior Investigation": "Logs show retryable broker timeouts.",
        "Approach": "Wrap publish in bounded retry.",
        "Decisions Made": "Use bounded retry instead of unbounded replay.",
        "Acceptance Criteria": [
            "Publisher retries transient broker failures.",
            "Permanent broker failures still surface clearly.",
        ],
        "Verification": "uv run pytest plugins/turbo-mode/ticket/tests/test_publish.py -q",
        "Key Files": [
            {
                "file": "plugins/turbo-mode/ticket/scripts/publisher.py",
                "role": "Publisher",
                "look_for": "retry around broker publish",
            }
        ],
        "Related": "T-20260605-02",
    }
    mutation = GatewayMutation(
        action="create",
        ticket_id=None,
        target=target,
        proposed_change=proposed_change,
        tickets_dir=tmp_tickets,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
    )
    decision = _decision_for(
        ticket_id=None,
        action="create",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "ok"
    ticket_path = Path(str(response.data["ticket_path"]))
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: blocked" in text
    assert "blocked_by: [T-20260605-02]" in text
    assert "## Blocked On\nWaiting for T-20260605-02 to expose broker retry policy." in text
    assert "## Captured Request\nTrack the publisher retry follow-up." in text
    assert "## Context\nBroker publishes sometimes fail transiently." in text
    assert "## Prior Investigation\nLogs show retryable broker timeouts." in text
    assert "## Approach\nWrap publish in bounded retry." in text
    assert "## Decisions Made\nUse bounded retry instead of unbounded replay." in text
    assert "## Acceptance Criteria\n- [ ] Publisher retries transient broker failures." in text
    assert "## Verification\n```bash\nuv run pytest" in text
    assert "| plugins/turbo-mode/ticket/scripts/publisher.py | Publisher | retry around broker publish |" in text
    assert "## Related\nT-20260605-02" in text
```

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py` and
`plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, update
apply-turn candidate fixtures to the target envelope. For existing-ticket writes,
fixtures must include `target`, `proposed_change`, `expected_ticket_fingerprint`
computed with `target_fingerprint(ticket_path)`, and `evidence_summary`. For
create, fixtures must use `ticket_id=None`, `expected_ticket_fingerprint=None`,
and target sections such as `Problem` and `Next Action`. Rewrite old
`evidence`/`reason` fixtures in the same task.

Also rewrite standalone positional `GatewayMutation(...)` constructions in
`test_engine_gateway.py`, including create tests and
`test_gateway_dispatch_maps_ticket_actions_and_rejects_archive_smuggling()`.
That dispatch test currently uses `blocker_edit` and `reopen_reason`; rewrite it
to target-shaped `update`, `reopen`, and close-smuggling cases rather than only
updating shared helpers.

- [ ] **Step 2: Run gateway tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_applies_exact_target_section_update plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_removes_exact_optional_target_section plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_updates_blocked_ticket_to_open_with_target_section_cleanup plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_rejects_blocked_to_open_without_next_action plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_rejects_status_only_close_for_blocked_ticket plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_create_accepts_every_source_supported_target_section plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_collector_unhealthy_pauses_without_mutation_or_health_events plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_reports_invalid_explicit_candidate_without_no_change plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_summarizes_applied_mutation_before_next_turn plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py::test_agent_primary_apply_turn_applies_update_through_gateway -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_resume_source_context_pause_reports_invalid_candidate_and_keeps_pause -q
```

Expected: fail because `GatewayMutation` has no `target`, `proposed_change`, or
`expected_ticket_fingerprint` fields, `ticket_autonomy.py` still constructs the
old `fields`/`target_fingerprint` gateway shape, and blocked-to-open target
sections are not yet projected into update policy or guarded for `Next Action`.
The
`source_context_unhealthy` collector test and outer `invalid_candidate`
host-state tests, including the resume-paused invalid-candidate test, must keep
passing throughout this task; a failure there means the health gate or explicit
invalid-candidate visibility was weakened while removing the fingerprint side
channel.

- [ ] **Step 3: Update GatewayMutation and decision validation**

In `ticket_engine_gateway.py`, replace `GatewayMutation` with:

```python
@dataclass(frozen=True, slots=True)
class GatewayMutation:
    """Gateway-owned target candidate mutation request."""

    action: str
    ticket_id: str | None
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    tickets_dir: Path
    expected_ticket_fingerprint: str | None
    evidence_summary: str
```

Update imports from `ticket_autonomy_runtime.py` to include `CandidateTarget`.

Replace `_mutation_fingerprint()` with:

```python
def _mutation_fingerprint(mutation: GatewayMutation) -> str:
    return sha256_fingerprint(
        {
            "ticket_id": mutation.ticket_id,
            "action": mutation.action,
            "target": {
                "fields": list(mutation.target.fields),
                "sections": list(mutation.target.sections),
            },
            "proposed_change": dict(mutation.proposed_change),
            "expected_ticket_fingerprint": mutation.expected_ticket_fingerprint,
            "evidence_summary": mutation.evidence_summary,
        }
    )
```

Near `_decision_error()`, add canonical target comparison so unordered target
sets are validated consistently with mutation identity:

```python
def _canonical_target(target: CandidateTarget) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (tuple(sorted(target.fields)), tuple(sorted(target.sections)))
```

In `_decision_error()`, replace field comparison and identity recomputation with:

```python
    if mutation.action == "correct":
        if decision.kind != RuntimeDecisionKind.APPLY_CORRECTION:
            return "decision_mismatch"
    elif decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        return "autonomous_decision_required"
    if decision.mutation_id is None:
        return "mutation_id_required"
    if decision.candidate.ticket_id != mutation.ticket_id:
        return "ticket_mismatch"
    if decision.candidate.action != mutation.action:
        return "action_mismatch"
    if _canonical_target(decision.candidate.target) != _canonical_target(mutation.target):
        return "target_mismatch"
    if dict(decision.candidate.proposed_change) != dict(mutation.proposed_change):
        return "mutation_fingerprint_mismatch"
    if decision.candidate.expected_ticket_fingerprint != mutation.expected_ticket_fingerprint:
        return "expected_ticket_fingerprint_mismatch"
    if decision.candidate.evidence_summary != mutation.evidence_summary:
        return "evidence_summary_mismatch"
    if mutation.action != "create" and mutation.expected_ticket_fingerprint is None:
        return "expected_ticket_fingerprint_required"
    identity = make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        ticket_id=decision.candidate.ticket_id,
        action=decision.candidate.action,
        target=decision.candidate.target,
        proposed_change=decision.candidate.proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
        evidence_summary=decision.candidate.evidence_summary,
    )
    if decision.mutation_id != identity.mutation_id:
        return "mutation_id_mismatch"
    return None
```

The `correct` gate above is intentional: `correct -> reopen` is allowed only
after the runtime selected the user-triggered correction decision kind. Also
remove `_candidate_evidence_payload()`. After this step, `_decision_error` must
not read `candidate.evidence`, `mutation.fields`, or `mutation.target_fingerprint`,
and must not reject semantically equivalent target envelopes solely because the
caller preserved a different field or section order.

- [ ] **Step 4: Update expected fingerprint validation**

Rename `_validate_target_fingerprint()` to
`_validate_expected_ticket_fingerprint()` and replace target-candidate gateway
references to `target_fingerprint` with `expected_ticket_fingerprint`:

```python
def _validate_expected_ticket_fingerprint(mutation: GatewayMutation) -> EngineResponse | None:
    if mutation.action == "create":
        return None
    if not mutation.ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {mutation.action}",
            error_code="need_fields",
        )
    if mutation.expected_ticket_fingerprint is None:
        return _policy_blocked(f"{mutation.action} requires expected_ticket_fingerprint")
    try:
        ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id)
    except InvalidTicketState as exc:
        return _invalid_state(
            "Ticket state is not target-normalized.",
            ticket_id=mutation.ticket_id,
            data={"reason": str(exc)},
        )
    if ticket is None:
        return _invalid_state(
            message=f"No ticket matching {mutation.ticket_id}",
            ticket_id=mutation.ticket_id,
            error_code="not_found",
        )
    current = compute_target_fingerprint(Path(ticket.path))
    if current != mutation.expected_ticket_fingerprint:
        return _invalid_state(
            message="Stale fingerprint - ticket was modified since validation.",
            ticket_id=mutation.ticket_id,
            error_code="stale_plan",
        )
    return None
```

Call `_validate_expected_ticket_fingerprint()` from `_apply_autonomous_mutation_locked()`.

Update `_expected_pre_write_fingerprint()` in the same step:

```python
def _expected_pre_write_fingerprint(
    *,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    del decision
    return mutation.expected_ticket_fingerprint
```

Do not defer this helper to Task 5. `_fingerprint_details()` is reached before
dispatch during gateway application, so leaving the old attribute read breaks
the first target gateway write.

- [ ] **Step 5: Update apply-turn gateway construction and fingerprint sourcing**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`, update
`_run_apply_turn_with_mode()` so the live source entrypoint passes target
candidate content through unchanged:

- Import `InvalidCandidateMutations` from `ticket_candidate_discovery`.
- Add this response helper near `_paused_response()`:

```python
def _invalid_candidate_response(error: InvalidCandidateMutations) -> dict[str, object]:
    return {
        # Outer apply-turn host state, not a target mutation result envelope state.
        "state": "invalid_candidate",
        "changed": False,
        "ticket_updates": None,
        "invalid_candidates": error.as_payload(),
        "discussion_question": (
            "Fix the explicit Ticket candidate payload before automatic ticket mutation."
        ),
    }
```

- In `_run_apply_turn_with_mode()`, catch malformed explicit candidate payloads
  immediately after the existing `InvalidTicketState` branch and before the
  no-candidate fallback:

```python
try:
    candidates = discover_candidate_mutations(context, tickets_dir)
except InvalidCandidateMutations as exc:
    _emit(_invalid_candidate_response(exc))
    return 2
except InvalidTicketState:
    pause_workspace_automation(project_root, reason="source_context_unhealthy")
    _emit(_paused_response("source_context_unhealthy"))
    return 3
```

- Add the same `InvalidCandidateMutations` catch in the `--resume-paused`
  source-context branch before `resume_workspace_automation()` runs. Let
  `_source_context_resume_collection()` keep calling
  `discover_candidate_mutations()`, and catch the error at the resume branch so
  the CLI can emit the same outer invalid-candidate host response while leaving
  the existing pause file intact:

```python
if args.resume_paused and _read_pause_reason(project_root) == "source_context_unhealthy":
    try:
        collection = _source_context_resume_collection(project_root, context)
    except InvalidCandidateMutations as exc:
        _emit(_invalid_candidate_response(exc))
        return 2
    if collection.state == "unhealthy":
        _emit(_paused_response(collection.reason or "source_context_unhealthy"))
        return 3
```

- Do not broaden `_has_candidate_changes()` to treat malformed target candidates
  as legacy mode-projection work. The new explicit arrays are either valid
  target candidates, an explicit invalid-candidate response, or empty.

Then construct target-shaped gateway mutations from accepted decisions:

```python
mutation = GatewayMutation(
    action=decision.candidate.action,
    ticket_id=decision.candidate.ticket_id,
    target=decision.candidate.target,
    proposed_change=dict(decision.candidate.proposed_change),
    tickets_dir=tickets_dir,
    expected_ticket_fingerprint=decision.candidate.expected_ticket_fingerprint,
    evidence_summary=decision.candidate.evidence_summary,
)
```

Keep a normal apply-turn source-context health pass before mutation evaluation.
It may continue to call `_ticket_state_fingerprints()` or may be renamed to
`_ticket_source_context_health()`, but its result must still pause automation on
malformed active ticket source context:

```python
source_context_health = _ticket_state_fingerprints(candidates, tickets_dir)
if source_context_health.state == "unhealthy":
    pause_workspace_automation(
        project_root,
        reason=source_context_health.reason or "source_context_unhealthy",
    )
    _emit(_paused_response(source_context_health.reason or "source_context_unhealthy"))
    return 3
```

Remove only the
`source_context={"ticket_state_fingerprints": fingerprints}` injection used to
populate candidate identity. Do not replace that injection with another hidden
fingerprint side channel:

```python
decisions = evaluate_autonomy_intent(
    AutonomyIntent(
        action_kind="apply_ticket_mutations",
        candidates=candidates,
        source_context={},
    ),
    current_mode=mode.value,
    thread_id=str(context["thread_id"]),
    turn_id=str(context["turn_id"]),
)
```

Missing or stale expected fingerprints are visible candidate or gateway
failures: runtime blocks missing non-create values, and the gateway recomputes
the current target fingerprint immediately before writing. The existing
`source_context_unhealthy` CLI tests remain part of this task because source
health and identity fingerprint sourcing are separate boundaries.

- [ ] **Step 6: Add exact target-section support to engine update**

In `ticket_engine_core.py`, add this helper near `_UPDATE_SECTION_HEADINGS`.
Target-section update, reopen, and create rendering must agree for structured
target sections such as `Acceptance Criteria` and `Key Files`; do not serialize
structured values with Python `repr`:

```python
def _render_key_files_section_value(value: Any) -> str:
    if not isinstance(value, list):
        raise ValueError("Key Files target section requires a list of row objects")
    rows = ["| File | Role | Look For |", "|------|------|----------|"]
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Key Files target section requires row objects")
        rows.append(
            "| "
            + " | ".join(
                str(item.get(key, ""))
                for key in ("file", "role", "look_for")
            )
            + " |"
        )
    return "\n".join(rows)


def _render_target_section_value(heading: str, value: Any) -> str | None:
    if value is None:
        return None
    if heading == "Acceptance Criteria":
        return _render_update_section_value("acceptance_criteria", value)
    if heading == "Key Files":
        return _render_key_files_section_value(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"{heading} does not support structured target values")
    return str(value)
```

Change `_execute_update()` signature to:

```python
def _execute_update(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    target_sections: Mapping[str, object] | None = None,
) -> EngineResponse:
```

After the existing `for key in section_fields:` block, add exact target-section updates:

```python
    policy_fields = dict(fields)
    if target_sections and "Blocked On" in target_sections:
        policy_fields["blocked_on"] = target_sections["Blocked On"]
    policy_error = _evaluate_update_policy(ticket_id, ticket, policy_fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    for heading, value in (target_sections or {}).items():
        if heading == "Change History" or not validate_target_section_name(heading):
            return EngineResponse(
                state="escalate",
                message=f"Update failed: invalid target section {heading!r}",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
        try:
            rendered = _render_target_section_value(heading, value)
        except ValueError as exc:
            return EngineResponse(
                state="need_fields",
                message=f"Update failed: {exc}",
                ticket_id=ticket_id,
                error_code="need_fields",
            )
        old_rendered = ticket.sections.get(heading, "")
        if rendered is None:
            if heading in ticket.sections:
                changes["sections_changed"].append(heading)
        elif old_rendered.strip() != rendered.strip():
            changes["sections_changed"].append(heading)
        sections[heading] = rendered
```

Move the existing `_evaluate_update_policy(ticket_id, ticket, fields,
tickets_dir)` call to this point, after section fields and exact target sections
have been projected into `policy_fields`. Do not leave an earlier policy call
that sees only `fields`; otherwise `blocked -> open` target candidates that name
`Blocked On: None` still fail the current `blocked_on: null` precondition.

Build targeted headings from both sources:

```python
    targeted_headings = tuple(_UPDATE_SECTION_HEADINGS[key] for key in section_fields) + tuple(
        (target_sections or {}).keys()
    )
```

Ensure `validate_target_section_name` and `Mapping` are imported in `ticket_engine_core.py`.

- [ ] **Step 7: Project gateway dispatch into engine fields and sections**

In `ticket_engine_gateway.py`, replace `build_engine_dispatch()` with:

```python
def build_engine_dispatch(mutation: GatewayMutation) -> EngineDispatch:
    """Build deterministic engine dispatch for a gateway target mutation."""
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        target=mutation.target,
        proposed_change=dict(mutation.proposed_change),
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
        evidence_summary=mutation.evidence_summary,
    )
    current_ticket_status: str | None = None
    if mutation.action != "create" and mutation.ticket_id is not None:
        ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id)
        if ticket is not None:
            current_ticket_status = ticket.status
    return map_candidate_to_engine(
        candidate,
        current_ticket_status=current_ticket_status,
    )
```

Do not scope the current-status lookup to `correct`. The Task 3 blocked-close
and blocked-to-open gateway tests depend on dispatch receiving the parsed current
status before `_execute_close()` or `_execute_update()` can clear blocker state.

Update `_execute_dispatch()` calls to pass target sections:

```python
target_sections = dispatch.sections or {}
```

For update:

```python
        return _execute_update(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
```

For close, extend `_execute_close()` with a keyword-only `target_sections`
argument and pass the dispatch sections:

```python
        return _execute_close(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
```

Inside `_execute_close()`, accept only the target cleanup section generated by
the target candidate contract:

```python
    if target_sections:
        if set(target_sections) != {"Blocked On"} or target_sections["Blocked On"] is not None:
            return EngineResponse(
                state="escalate",
                message="Close failed: invalid target section cleanup",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
```

Keep the existing engine-owned blocked-ticket cleanup. This check prevents the
gateway from computing close sections and dropping them silently.

For create, use one shared helper for create dispatch and create dedup. This
prevents `_validate_autonomous_create_dedup()` from reading the removed
`mutation.fields` attribute and prevents create dispatch from using a different
section map than dedup:

```python
_CREATE_SECTION_MAP = {
    "Problem": "problem",
    "Next Action": "next_action",
    "Blocked On": "blocked_on",
    "Captured Request": "captured_request",
    "Context": "context",
    "Prior Investigation": "prior_investigation",
    "Approach": "approach",
    "Decisions Made": "decisions_made",
    "Acceptance Criteria": "acceptance_criteria",
    "Verification": "verification",
    "Key Files": "key_files",
    "Related": "related",
}


def _create_fields_for_engine(mutation: GatewayMutation) -> tuple[dict[str, object], str | None]:
    fields = {
        key: value
        for key, value in mutation.proposed_change.items()
        if key in mutation.target.fields
    }
    for heading in mutation.target.sections:
        engine_key = _CREATE_SECTION_MAP.get(heading)
        if engine_key is None:
            return {}, f"Unsupported create target section: {heading}"
        fields[engine_key] = mutation.proposed_change[heading]
    return fields, None
```

Both `_validate_autonomous_create_dedup()` and the create branch of
`_execute_dispatch()` must call this helper. If the helper returns an error,
return `_policy_blocked(error)`. Do not omit optional sections that
`_execute_create()` can render; if a future section is intentionally unsupported,
patch `plugins/turbo-mode/ticket/references/ticket-contract.md` and the skill
examples in the same commit that narrows the source contract.

In `ticket_validate.py`, split normal target write validation from source create
field validation so Task 3 does not make `key_files` a non-create write field.
Add this helper:

```python
def validate_create_fields(fields: dict[str, Any]) -> list[str]:
    """Validate source create fields after gateway target-section projection."""
    errors = validate_fields(
        {key: value for key, value in fields.items() if key != "key_files"}
    )
    if "key_files" in fields:
        value = fields["key_files"]
        if not isinstance(value, list):
            errors.append(f"key_files must be a list, got {type(value).__name__}")
        elif not all(isinstance(item, Mapping) for item in value):
            errors.append("key_files must contain only objects")
        else:
            for index, item in enumerate(value):
                for key in ("file", "role", "look_for"):
                    if not isinstance(item.get(key), str) or not item[key].strip():
                        errors.append(f"key_files[{index}].{key} must be a non-empty string")
    return errors
```

Import `Mapping` from `collections.abc` in `ticket_validate.py`. In
`ticket_engine_core.py`, change `_plan_create()` and `_execute_create()` to call
`validate_create_fields(fields)` instead of `validate_fields(fields)`. Keep
`validate_fields({"key_files": [...]})` rejecting `key_files` for normal
non-create writes.

The gateway create test above must pass before Task 3 can commit.

For reopen, pass target sections in Task 4 after reopen support lands.

- [ ] **Step 8: Run gateway and source-entrypoint tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_applies_exact_target_section_update plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_removes_exact_optional_target_section plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_updates_blocked_ticket_to_open_with_target_section_cleanup plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_rejects_status_only_close_for_blocked_ticket plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_create_accepts_every_source_supported_target_section plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_collector_unhealthy_pauses_without_mutation_or_health_events plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_reports_invalid_explicit_candidate_without_no_change plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_summarizes_applied_mutation_before_next_turn plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py::test_agent_primary_apply_turn_applies_update_through_gateway -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_resume_source_context_pause_reports_invalid_candidate_and_keeps_pause -q
```

Expected: the gateway section update/removal/blocked-to-open/create tests and
the source-context health, invalid-candidate normal/resume, and apply-turn source
entrypoint tests pass.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_policy.py
git commit -m "fix(ticket): migrate target candidates through source entrypoints"
```

Expected: commit succeeds with runtime shape, identity, discovery, gateway,
engine, source-entrypoint, and directly affected validation/tests staged. This
is the first runnable target-candidate source boundary. Do not update
source-availability docs in this commit.

## Task 3A: Add Exact Create Idempotency Binding

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_dedup.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`

Precondition: do not start Task 3A until Task 3 has a target-shaped
`GatewayMutation` and create dispatch can project target fields/sections into
engine create fields. Task 3A must commit before Task 6 source-availability
docs. This task's commit must include the retained create allocation binding,
create-wide allocation serialization, expected post-write recovery fingerprint,
exact generated `Change History` metadata before file write, and turn-batch
validation for the bounded create-attempt detail shape that records those facts.
If those facts cannot be made green in one source boundary, stop and keep
source-availability docs in their unavailable/missing-proof state.

- [ ] **Step 1: Write failing create idempotency and create-attempt event tests**

In `plugins/turbo-mode/ticket/tests/test_turn_batch.py`, add these helpers and
tests near `valid_attempt_event()`:

```python
def valid_create_attempt_event(**overrides: object) -> dict[str, object]:
    timestamp = overrides.pop("timestamp", "2026-06-05T12:00:00Z")
    details: dict[str, object] = {
        "target": {"fields": ["title"], "sections": ["Problem", "Next Action"]},
        "evidence_summary": "The user asked to track the publisher retry follow-up.",
        "expected_post_write_fingerprint": "post-fp-before-write",
        "change_history_entry": {
            "timestamp": timestamp,
            "actor": "codex",
            "reason": "Created ticket from candidate evidence.",
            "corrects": None,
        },
        "create_allocation": {
            "allocated_ticket_id": "T-20260605-01",
            "allocated_ticket_path": "docs/tickets/T-20260605-01.md",
            "expected_pre_write_fact": "allocated_target_path_unused",
        },
    }
    details.update(overrides.pop("details", {}))
    data = valid_attempt_event(
        action="create",
        ticket_id=None,
        timestamp=timestamp,
        details={},
        **overrides,
    )
    data["details"] = details
    return data


def test_create_attempt_accepts_bounded_recovery_details_without_runtime_decision() -> None:
    event = valid_create_attempt_event()

    assert validate_pending_summary_event(event).ok is True
    assert "decision" not in event["details"]
    assert "current_mode" not in event["details"]
    assert "evidence_kind" not in event["details"]
    assert event["timestamp"] == event["details"]["change_history_entry"]["timestamp"]


@pytest.mark.parametrize("detail_key", ["decision", "current_mode", "evidence_kind"])
def test_create_attempt_rejects_runtime_details_when_recovery_facts_present(
    detail_key: str,
) -> None:
    event = valid_create_attempt_event(details={detail_key: "apply_autonomously"})

    assert_invalid(event, detail_key)


@pytest.mark.parametrize(
    "detail_key",
    ["target", "expected_post_write_fingerprint", "change_history_entry", "create_allocation"],
)
def test_create_attempt_requires_bounded_recovery_details(detail_key: str) -> None:
    event = valid_create_attempt_event()
    details = dict(event["details"])
    details.pop(detail_key)
    event["details"] = details

    assert_invalid(event, detail_key)


def test_legacy_create_attempt_remains_readable_for_blocking_recovery() -> None:
    event = valid_attempt_event(action="create", ticket_id=None)

    assert validate_pending_summary_event(event).ok is True
```

In `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`, add these tests
after the gateway create target-section test:

```python
from dataclasses import replace

import scripts.ticket_engine_gateway as gateway
from scripts.ticket_change_history import ChangeHistoryEntry
from scripts.ticket_dedup import (
    target_recovery_fingerprint,
    target_recovery_fingerprint_for_text,
)
from scripts.ticket_engine_core import TargetWritePreview, preview_target_write
from tests.test_turn_batch import valid_attempt_event, valid_create_attempt_event


def _create_target() -> CandidateTarget:
    return CandidateTarget(
        fields=("title", "priority"),
        sections=("Problem", "Next Action"),
    )


def _create_change() -> dict[str, object]:
    return {
        "title": "Add retry to publisher",
        "priority": "high",
        "Problem": "Publisher drops transient broker messages.",
        "Next Action": "Add retry around broker publish.",
    }


def _create_mutation(tmp_tickets: Path) -> GatewayMutation:
    return GatewayMutation(
        action="create",
        ticket_id=None,
        target=_create_target(),
        proposed_change=_create_change(),
        tickets_dir=tmp_tickets,
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
    )


def _create_decision() -> AutonomyDecision:
    return _decision_for(
        ticket_id=None,
        action="create",
        target=_create_target(),
        proposed_change=_create_change(),
        expected_ticket_fingerprint=None,
        evidence_summary="The user asked to track the publisher retry follow-up.",
    )


def _change_history_details() -> dict[str, object]:
    entry = _change_history_entry()
    return {
        "timestamp": entry.timestamp,
        "actor": entry.actor,
        "reason": entry.reason,
        "corrects": entry.corrects,
    }


def _change_history_entry() -> ChangeHistoryEntry:
    return ChangeHistoryEntry(
        timestamp="2026-06-05T12:00:00Z",
        actor="codex",
        reason="Created ticket from candidate evidence.",
        corrects=None,
    )


def _retained_create_attempt_event(
    *,
    event_id: str = "evt_create_attempt",
    mutation_id: str | None,
    allocation_id: str = "T-20260605-01",
    allocation_path: str = "docs/tickets/T-20260605-01.md",
    expected_post_write_fingerprint: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    bounded_details = {
        "target": {
            "fields": list(_create_target().fields),
            "sections": list(_create_target().sections),
        },
        "evidence_summary": "The user asked to track the publisher retry follow-up.",
        "expected_post_write_fingerprint": expected_post_write_fingerprint,
        "change_history_entry": _change_history_details(),
        "create_allocation": {
            "allocated_ticket_id": allocation_id,
            "allocated_ticket_path": allocation_path,
            "expected_pre_write_fact": "allocated_target_path_unused",
        },
    }
    if details:
        bounded_details.update(details)
    return valid_create_attempt_event(
        event_id=event_id,
        action="create",
        ticket_id=None,
        mutation_id=mutation_id,
        details=bounded_details,
    )


def test_create_gateway_lock_is_shared_across_create_candidates(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    first = _create_mutation(tmp_tickets)
    second = replace(
        first,
        proposed_change={
            **_create_change(),
            "title": "Add retry metrics to publisher",
            "Problem": "Publisher retry metrics are missing.",
        },
        evidence_summary="The user asked to track publisher retry metrics.",
    )

    assert gateway._gateway_lock_path(project_root, first) == gateway._gateway_lock_path(project_root, second)


def test_create_attempt_records_allocated_ticket_binding_before_dispatch(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    mutation = _create_mutation(tmp_tickets)
    decision = _create_decision()

    def fail_dispatch(**_kwargs: object) -> EngineResponse:
        return EngineResponse(
            state="escalate",
            message="simulated dispatch failure",
            error_code="simulated_failure",
        )

    monkeypatch.setattr(gateway, "_execute_dispatch", fail_dispatch)

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    events = _events(project_root)
    details = events[0]["details"]
    allocation = details["create_allocation"]
    assert response.error_code == "simulated_failure"
    assert events[0]["event_type"] == "mutation_attempt"
    assert "expected_post_write_fingerprint" in details
    assert details["change_history_entry"]["actor"] == "codex"
    assert "decision" not in details
    assert "current_mode" not in details
    assert "evidence_kind" not in details
    assert events[0]["timestamp"] == details["change_history_entry"]["timestamp"]
    assert allocation["allocated_ticket_id"].startswith("T-")
    assert allocation["allocated_ticket_path"].startswith("docs/tickets/T-")
    assert allocation["expected_pre_write_fact"] == "allocated_target_path_unused"
    assert not (project_root / str(allocation["allocated_ticket_path"])).exists()


def test_create_retry_reuses_retained_allocation_when_file_not_written(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    mutation = _create_mutation(tmp_tickets)
    decision = _create_decision()
    allocated_ticket_id = "T-20260605-01"
    allocated_ticket_path = "docs/tickets/T-20260605-01.md"
    dispatch = build_engine_dispatch(mutation)
    preview = preview_target_write(
        action=dispatch.action.value,
        ticket_id=mutation.ticket_id,
        fields=dict(dispatch.fields),
        target_sections=dispatch.sections or {},
        session_id="thread-1",
        request_origin="agent",
        tickets_dir=tmp_tickets,
        change_history_entry=_change_history_entry(),
        reserved_ticket_id=allocated_ticket_id,
    )
    assert isinstance(preview, TargetWritePreview)
    expected_post = preview.post_write_fingerprint
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            _retained_create_attempt_event(
                mutation_id=decision.mutation_id,
                allocation_id=allocated_ticket_id,
                allocation_path=allocated_ticket_path,
                expected_post_write_fingerprint=expected_post,
            )
        ).state
        == "appended"
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert response.state == "ok"
    assert response.ticket_id == allocated_ticket_id
    assert (project_root / allocated_ticket_path).is_file()
    assert sorted(path.name for path in tmp_tickets.glob("*.md")) == [
        "T-20260605-01.md"
    ]


def test_create_retry_blocks_allocation_path_that_does_not_match_allocated_id(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    mutation = _create_mutation(tmp_tickets)
    decision = _create_decision()
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            _retained_create_attempt_event(
                mutation_id=decision.mutation_id,
                allocation_id="T-20260605-01",
                allocation_path="docs/tickets/T-20260605-99.md",
                expected_post_write_fingerprint="unused-post-fingerprint",
            )
        ).state
        == "appended"
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert response.error_code == "gateway_required"
    assert response.data["recovery_state"] == "create_allocation_missing"


def test_create_retry_appends_missing_written_event_for_retained_allocation(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    mutation = _create_mutation(tmp_tickets)
    decision = _create_decision()
    allocated_ticket_id = "T-20260605-01"
    allocated_ticket_path = tmp_tickets / "T-20260605-01.md"
    dispatch = build_engine_dispatch(mutation)
    preview = preview_target_write(
        action=dispatch.action.value,
        ticket_id=mutation.ticket_id,
        fields=dict(dispatch.fields),
        target_sections=dispatch.sections or {},
        session_id="thread-1",
        request_origin="agent",
        tickets_dir=tmp_tickets,
        change_history_entry=_change_history_entry(),
        reserved_ticket_id=allocated_ticket_id,
    )
    assert isinstance(preview, TargetWritePreview)
    allocated_ticket_path.write_text(preview.rendered_text, encoding="utf-8")
    before = allocated_ticket_path.read_text(encoding="utf-8")
    expected_post = preview.post_write_fingerprint
    assert target_recovery_fingerprint(allocated_ticket_path) == expected_post
    assert target_recovery_fingerprint_for_text(before) == expected_post
    assert "Add retry around broker publish." in before
    assert "Created ticket from candidate evidence." in before
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            _retained_create_attempt_event(
                mutation_id=decision.mutation_id,
                expected_post_write_fingerprint=expected_post,
            )
        ).state
        == "appended"
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert response.error_code == "gateway_required"
    assert response.data["recovery_state"] == "append_missing_ticket_written"
    assert allocated_ticket_path.read_text(encoding="utf-8") == before
    assert [event["status"] for event in _events(project_root)] == [
        "pending",
        "ticket_written",
        "applied",
    ]


def test_create_retry_blocks_legacy_attempt_without_expected_write_facts(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    mutation = _create_mutation(tmp_tickets)
    decision = _create_decision()
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            valid_attempt_event(
                event_id="evt_legacy_create_attempt",
                action="create",
                ticket_id=None,
                mutation_id=decision.mutation_id,
            )
        ).state
        == "appended"
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert response.error_code == "gateway_required"
    assert response.data["recovery_state"] == "create_allocation_missing"
    assert list(tmp_tickets.glob("*.md")) == []


def test_create_retry_blocks_existing_allocation_with_wrong_post_fingerprint(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    mutation = _create_mutation(tmp_tickets)
    decision = _create_decision()
    allocated_ticket_id = "T-20260605-01"
    allocated_ticket_path = tmp_tickets / "T-20260605-01.md"
    make_ticket(
        tmp_tickets,
        "T-20260605-01.md",
        id=allocated_ticket_id,
        priority="low",
        title="Different retained file",
        problem="This is not the expected create candidate.",
    )
    store = PendingSummaryStore(project_root)
    assert (
        store.append_event(
            _retained_create_attempt_event(
                mutation_id=decision.mutation_id,
                allocation_id=allocated_ticket_id,
                expected_post_write_fingerprint="not-the-current-post-fingerprint",
            )
        ).state
        == "appended"
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=store,
    )

    assert response.state in {"blocked", "invalid_state"}
    assert response.data["recovery_state"] == "create_post_write_mismatch"
```

Keep `test_gateway_autonomous_create_stops_at_duplicate_candidate()` in
`test_engine_gateway.py` and update it to the target-shaped `GatewayMutation`
constructor if Task 3 has not already done so. Fresh create duplicate detection
is still a live pre-allocation gate; these Task 3A tests add retained allocation
recovery for interrupted attempts, not an override for duplicate candidates.

- [ ] **Step 2: Run create idempotency tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_create_attempt_accepts_bounded_recovery_details_without_runtime_decision plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_create_attempt_rejects_runtime_details_when_recovery_facts_present plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_create_attempt_requires_bounded_recovery_details plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_legacy_create_attempt_remains_readable_for_blocking_recovery plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_gateway_lock_is_shared_across_create_candidates plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_attempt_records_allocated_ticket_binding_before_dispatch plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_reuses_retained_allocation_when_file_not_written plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_blocks_allocation_path_that_does_not_match_allocated_id plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_appends_missing_written_event_for_retained_allocation plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_blocks_legacy_attempt_without_expected_write_facts plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_blocks_existing_allocation_with_wrong_post_fingerprint -q
```

Expected: fail because create writes still use mutation-specific gateway locks,
the gateway still relies on create duplicate preflight, `_execute_create()`
allocates internally without any retained allocation binding, and create
recovery does not yet retain expected post-write facts. The turn-batch tests
also fail because create `mutation_attempt` events still require old runtime
detail keys instead of the bounded recovery facts.

- [ ] **Step 3: Add retained create allocation helpers in the gateway**

In `ticket_dedup.py`, keep the existing mtime-sensitive `target_fingerprint()`
unchanged for pre-write TOCTOU checks, and add the content-only recovery helper
used for expected/observed post-write comparisons:

```python
def target_recovery_fingerprint_for_text(text: str) -> str:
    """Return a content-only fingerprint for post-write recovery comparison."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def target_recovery_fingerprint(path: Path) -> str | None:
    """Return a content-only fingerprint for a written target ticket."""

    if not path.is_file():
        return None
    try:
        return target_recovery_fingerprint_for_text(path.read_text(encoding="utf-8"))
    except OSError:
        return None
```

In `ticket_engine_gateway.py`, import `allocate_id` and `build_filename` from
`scripts.ticket_id`, import `target_recovery_fingerprint` from
`scripts.ticket_dedup`, import `ChangeHistoryEntry` from
`scripts.ticket_change_history`, and replace `_gateway_lock_path()` so all
create allocations for one ticket directory serialize through the same lock:

```python
def _gateway_lock_path(project_root: Path, mutation: GatewayMutation) -> Path:
    if mutation.action == "create":
        key = sha256_fingerprint(
            {
                "lock": "create_allocation",
                "tickets_dir": str(mutation.tickets_dir.resolve()),
            }
        )
    elif mutation.ticket_id:
        key = sha256_fingerprint({"ticket_id": mutation.ticket_id})
    else:
        key = _mutation_fingerprint(mutation)
    filename = f"gateway-write-{key.removeprefix('sha256:')}.lock"
    return project_root / WORKSPACE_RELATIVE_PATH / filename
```

Then add:

```python
@dataclass(frozen=True, slots=True)
class CreateAllocation:
    """Retained target ID/path allocation for one create candidate."""

    ticket_id: str
    ticket_path: Path


@dataclass(frozen=True, slots=True)
class ExpectedWriteFacts:
    """Recovery facts known before the ticket file write starts."""

    expected_post_write_fingerprint: str
    change_history_entry: dict[str, object]


@dataclass(frozen=True, slots=True)
class RetainedCreateAttempt:
    """Retained allocation plus exact expected create write facts."""

    allocation: CreateAllocation
    expected_write_facts: ExpectedWriteFacts


def _change_history_entry_details(entry: ChangeHistoryEntry) -> dict[str, object]:
    return {
        "timestamp": entry.timestamp,
        "actor": entry.actor,
        "reason": entry.reason,
        "corrects": entry.corrects,
    }


def _expected_write_facts_from_details(
    details: Mapping[str, object],
) -> ExpectedWriteFacts | None:
    expected_post = details.get("expected_post_write_fingerprint")
    raw_history = details.get("change_history_entry")
    if not isinstance(expected_post, str) or not expected_post:
        return None
    if not isinstance(raw_history, Mapping):
        return None
    timestamp = raw_history.get("timestamp")
    actor = raw_history.get("actor")
    reason = raw_history.get("reason")
    corrects = raw_history.get("corrects")
    if (
        not isinstance(timestamp, str)
        or not timestamp
        or not isinstance(actor, str)
        or not actor
        or not isinstance(reason, str)
        or not reason
        or (corrects is not None and not isinstance(corrects, str))
    ):
        return None
    return ExpectedWriteFacts(
        expected_post_write_fingerprint=expected_post,
        change_history_entry={
            "timestamp": timestamp,
            "actor": actor,
            "reason": reason,
            "corrects": corrects,
        },
    )


def _change_history_entry_from_expected_facts(
    facts: ExpectedWriteFacts,
) -> ChangeHistoryEntry:
    history = facts.change_history_entry
    return ChangeHistoryEntry(
        timestamp=str(history["timestamp"]),
        actor=str(history["actor"]),
        reason=str(history["reason"]),
        corrects=(
            str(history["corrects"])
            if history.get("corrects") is not None
            else None
        ),
    )


def _create_allocation_details(
    allocation: CreateAllocation,
    *,
    project_root: Path,
) -> dict[str, object]:
    return {
        "allocated_ticket_id": allocation.ticket_id,
        "allocated_ticket_path": str(allocation.ticket_path.relative_to(project_root)),
        "expected_pre_write_fact": "allocated_target_path_unused",
    }


def _create_allocation_from_details(
    details: Mapping[str, object],
    *,
    project_root: Path,
) -> CreateAllocation | None:
    raw = details.get("create_allocation")
    if not isinstance(raw, Mapping):
        return None
    ticket_id = raw.get("allocated_ticket_id")
    ticket_path = raw.get("allocated_ticket_path")
    pre_fact = raw.get("expected_pre_write_fact")
    if (
        not isinstance(ticket_id, str)
        or not isinstance(ticket_path, str)
        or pre_fact != "allocated_target_path_unused"
    ):
        return None
    path = project_root / ticket_path
    if path.parent != project_root / "docs" / "tickets":
        return None
    if path.name != f"{ticket_id}.md":
        return None
    return CreateAllocation(ticket_id=ticket_id, ticket_path=path)


def _allocate_create_target(
    mutation: GatewayMutation,
) -> tuple[CreateAllocation | None, EngineResponse | None]:
    title = mutation.proposed_change.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, _policy_blocked("create requires title before allocation")
    ticket_id = allocate_id(mutation.tickets_dir, datetime.now(UTC).date())
    try:
        filename = build_filename(ticket_id, title)
    except ValueError as exc:
        return None, _invalid_state(str(exc), error_code="invalid_state")
    ticket_path = mutation.tickets_dir / filename
    if ticket_path.exists():
        return None, _invalid_state(
            message="Create allocation path is already used.",
            ticket_id=ticket_id,
            error_code="create_allocation_conflict",
        )
    return CreateAllocation(ticket_id=ticket_id, ticket_path=ticket_path), None
```

The allocation helper must run while the create-allocation-wide gateway write
lock is held. It records only bounded recovery facts: allocated target ID,
allocated target path, the expected pre-write fact that the path was unused,
the expected post-write recovery fingerprint, and the exact generated
`Change History` metadata. Do not add decision kind, approval state, evidence
taxonomies, or copied ticket prose to this binding.

In `ticket_turn_batch.py`, add a narrow create-attempt validation branch before
the existing `details.decision` requirement. New bounded create attempts must not
carry old runtime detail keys, but legacy create attempts with the old decision
detail remain readable so retry can block on missing create recovery facts rather
than treating the attempted create as `no_attempt`:

```python
def _validate_create_attempt_details(details: Mapping[str, object]) -> ValidationResult:
    if "create_allocation" not in details:
        return _ok() if details.get("decision") in _DECISIONS else _invalid(
            "details.create_allocation is required"
        )
    for key in ("decision", "current_mode", "evidence_kind"):
        if key in details:
            return _invalid(f"details.{key} is not supported for create attempts")
    target = details.get("target")
    if not isinstance(target, Mapping):
        return _invalid("details.target is required")
    fields = target.get("fields")
    sections = target.get("sections")
    if not isinstance(fields, list) or not all(_nonempty_string(item) for item in fields):
        return _invalid("details.target.fields is required")
    if not isinstance(sections, list) or not all(_nonempty_string(item) for item in sections):
        return _invalid("details.target.sections is required")
    if not _nonempty_string(details.get("evidence_summary")):
        return _invalid("details.evidence_summary is required")
    if not _nonempty_string(details.get("expected_post_write_fingerprint")):
        return _invalid("details.expected_post_write_fingerprint is required")
    history = details.get("change_history_entry")
    if not isinstance(history, Mapping):
        return _invalid("details.change_history_entry is required")
    for key in ("timestamp", "actor", "reason"):
        if not _nonempty_string(history.get(key)):
            return _invalid(f"details.change_history_entry.{key} is required")
    if history.get("corrects") is not None and not _nonempty_string(history.get("corrects")):
        return _invalid("details.change_history_entry.corrects must be a string or null")
    allocation = details.get("create_allocation")
    if not isinstance(allocation, Mapping):
        return _invalid("details.create_allocation is required")
    allocated_ticket_id = allocation.get("allocated_ticket_id")
    allocated_ticket_path = allocation.get("allocated_ticket_path")
    if not _nonempty_string(allocated_ticket_id):
        return _invalid("details.create_allocation.allocated_ticket_id is required")
    expected_path = f"docs/tickets/{allocated_ticket_id}.md"
    if allocated_ticket_path != expected_path:
        return _invalid("details.create_allocation.allocated_ticket_path is invalid")
    if allocation.get("expected_pre_write_fact") != "allocated_target_path_unused":
        return _invalid("details.create_allocation.expected_pre_write_fact is invalid")
    return _ok()
```

```python
if event_type == "mutation_attempt":
    if action == "create":
        return _validate_create_attempt_details(details)
    if decision not in _DECISIONS:
        return _invalid("details.decision is required")
```

- [ ] **Step 4: Thread create allocation through mutation attempt details**

In `_apply_autonomous_mutation_locked()`, keep fresh create duplicate preflight
before allocation, then replace the old create retry branch with retained
allocation selection:

```python
create_allocation: CreateAllocation | None = None
retained_create_attempt: RetainedCreateAttempt | None = None
if mutation.action == "create":
    if existing_state == "no_attempt":
        create_error = _validate_autonomous_create_dedup(mutation, thread_id=thread_id)
        if create_error is not None:
            return create_error
        create_allocation, create_allocation_error = _allocate_create_target(mutation)
        if create_allocation_error is not None:
            return create_allocation_error
    else:
        retained_create_attempt = _retained_create_attempt(
            pending_summary=pending_summary,
            thread_id=thread_id,
            mutation_id=decision.mutation_id or "",
            project_root=project_root,
        )
        if retained_create_attempt is None:
            return _policy_blocked(
                "Create recovery failed: retained expected write facts missing",
                data={"recovery_state": "create_allocation_missing"},
            )
        create_allocation = retained_create_attempt.allocation
```

Remove the later unconditional `_validate_autonomous_create_dedup()` call for
create recovery retries. A retained create attempt must reuse the recorded
allocation instead of falling back to duplicate detection or fresh allocation.

In `ticket_engine_core.py`, extract render-before-write helpers from
`_execute_create()` so the gateway can preview the exact post-write content
before appending the `mutation_attempt` event. The helper must return the path
and content fingerprint without writing:

```python
@dataclass(frozen=True, slots=True)
class TargetWritePreview:
    """Rendered target ticket write used for pre-write recovery facts."""

    ticket_path: Path
    rendered_text: str
    post_write_fingerprint: str


def preview_target_write(
    *,
    action: str,
    ticket_id: str | None,
    fields: Mapping[str, Any],
    target_sections: Mapping[str, object],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    change_history_entry: ChangeHistoryEntry,
    reserved_ticket_id: str | None = None,
) -> EngineResponse | TargetWritePreview:
    """Render the exact target write without writing a ticket file."""
```

For Task 3A, `preview_target_write()` must support `create` with the same
validation, `ChangeHistoryEntry`, create target-section projection, and
`reserved_ticket_id` that `_execute_create()` will use. If create preview and
execute would diverge, stop and refactor the shared rendering helpers before
continuing; do not approximate the expected post fingerprint from candidate
fields.

Before appending `mutation_attempt`, build the create dispatch, retained
allocation, exact generated `ChangeHistoryEntry`, and expected post-write
preview. Use one timestamp for the attempt event and the generated history
entry:

```python
attempt_timestamp = change_history_timestamp or _now_z()
if retained_create_attempt is not None:
    change_history_entry = _change_history_entry_from_expected_facts(
        retained_create_attempt.expected_write_facts
    )
else:
    change_history_entry = _change_history_entry(
        mutation.action,
        timestamp=attempt_timestamp,
    )
preview = preview_target_write(
    action=dispatch.action.value,
    ticket_id=mutation.ticket_id,
    fields=dict(dispatch.fields),
    target_sections=dispatch.sections or {},
    session_id=thread_id,
    request_origin="agent",
    tickets_dir=mutation.tickets_dir,
    change_history_entry=change_history_entry,
    reserved_ticket_id=(
        create_allocation.ticket_id if create_allocation is not None else None
    ),
)
if isinstance(preview, EngineResponse):
    return preview
expected_write_facts = ExpectedWriteFacts(
    expected_post_write_fingerprint=preview.post_write_fingerprint,
    change_history_entry=_change_history_entry_details(change_history_entry),
)
if retained_create_attempt is not None:
    if (
        retained_create_attempt.expected_write_facts.expected_post_write_fingerprint
        != preview.post_write_fingerprint
    ):
        return _policy_blocked(
            "Create recovery failed: retained expected write facts changed",
            data={"recovery_state": "create_expected_write_facts_mismatch"},
        )
    expected_write_facts = retained_create_attempt.expected_write_facts
```

Update the `mutation_attempt` details call so a new create attempt records the
binding and expected post-write facts before dispatch:

```python
details=_fingerprint_details(
    mutation=mutation,
    project_root=project_root,
    expected_write_facts=expected_write_facts,
    create_allocation=create_allocation,
)
```

Update `_fingerprint_details()` so non-create writes still record
`expected_pre_write_fingerprint`, while create records `create_allocation` plus
expected post-write facts:

```python
def _fingerprint_details(
    *,
    mutation: GatewayMutation,
    project_root: Path,
    expected_write_facts: ExpectedWriteFacts,
    create_allocation: CreateAllocation | None = None,
) -> dict[str, object]:
    details: dict[str, object] = {
        "target": {
            "fields": list(mutation.target.fields),
            "sections": list(mutation.target.sections),
        },
        "evidence_summary": mutation.evidence_summary,
        "expected_post_write_fingerprint": (
            expected_write_facts.expected_post_write_fingerprint
        ),
        "change_history_entry": expected_write_facts.change_history_entry,
    }
    if mutation.action == "create":
        if create_allocation is not None:
            details["create_allocation"] = _create_allocation_details(
                create_allocation,
                project_root=project_root,
            )
        return details
    details["expected_pre_write_fingerprint"] = mutation.expected_ticket_fingerprint
    return details
```

This task removes old `decision`, `current_mode`, and `evidence_kind` details
from the create-recovery fixtures it touches. Task 5 removes the remaining
non-create/correction fixtures and must preserve this bounded
`create_allocation` plus expected post-write shape.

- [ ] **Step 5: Make engine create accept a retained allocation**

In `ticket_engine_core.py`, change `_execute_create()` to accept a reserved ID:

```python
def _execute_create(
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    reserved_ticket_id: str | None = None,
) -> EngineResponse:
```

Replace the allocation loop head with a deterministic reserved-ID branch:

```python
    attempts = 1 if reserved_ticket_id is not None else _CREATE_WRITE_RETRY_LIMIT
    for _attempt in range(attempts):
        ticket_id = reserved_ticket_id or allocate_id(tickets_dir, today)
```

If `_write_text_exclusive()` raises `FileExistsError` for a reserved ID, return
an `invalid_state` response with `error_code="create_allocation_conflict"`
instead of allocating a different ID:

```python
        except FileExistsError:
            if reserved_ticket_id is not None:
                return EngineResponse(
                    state="invalid_state",
                    message="Reserved create allocation path already exists.",
                    ticket_id=ticket_id,
                    error_code="create_allocation_conflict",
                )
            continue
```

In `ticket_engine_gateway.py`, change `_execute_dispatch()` so create receives
and passes the retained allocation:

```python
def _execute_dispatch(
    *,
    dispatch: EngineDispatch,
    mutation: GatewayMutation,
    thread_id: str,
    change_history_entry: ChangeHistoryEntry,
    create_allocation: CreateAllocation | None = None,
) -> EngineResponse:
```

```python
        return _execute_create(
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            reserved_ticket_id=(
                create_allocation.ticket_id if create_allocation is not None else None
            ),
        )
```

Update the `_execute_dispatch()` call site:

```python
response = _execute_dispatch(
    dispatch=dispatch,
    mutation=mutation,
    thread_id=thread_id,
    change_history_entry=change_history_entry,
    create_allocation=create_allocation,
)
```

- [ ] **Step 6: Update create recovery to use retained allocation and expected write facts**

Add `_retained_create_attempt()` in `ticket_engine_gateway.py`:

```python
def _retained_create_attempt(
    *,
    pending_summary: PendingSummaryStore,
    thread_id: str,
    mutation_id: str,
    project_root: Path,
) -> RetainedCreateAttempt | None:
    for event in reversed(pending_summary.read_events()):
        if event.get("thread_id") != thread_id or event.get("mutation_id") != mutation_id:
            continue
        if event.get("event_type") != "mutation_attempt":
            continue
        details = event.get("details")
        if not isinstance(details, Mapping):
            return None
        allocation = _create_allocation_from_details(details, project_root=project_root)
        expected_write_facts = _expected_write_facts_from_details(details)
        if allocation is None or expected_write_facts is None:
            return None
        return RetainedCreateAttempt(
            allocation=allocation,
            expected_write_facts=expected_write_facts,
        )
    return None
```

Update `_existing_mutation_recovery_response()` for `create` attempts:

- if the retained create attempt exists and the allocated file exists, compute
  the content-only post-write recovery fingerprint from that file, compare it to
  the retained `ExpectedWriteFacts.expected_post_write_fingerprint`, and append
  the missing `mutation_status`/`ticket_written` and `applied` events without
  writing a new ticket only when the fingerprints match;
- if the allocated file exists but its content-only post-write recovery
  fingerprint does not match the retained `expected_post_write_fingerprint`,
  return a blocked or `invalid_state` response with
  `data={"recovery_state": "create_post_write_mismatch"}` and do not append
  completion events;
- if the retained create attempt exists and the allocated file does not exist,
  return `None` so `_apply_autonomous_mutation_locked()` can retry the same
  mutation with the same reserved ID and the retained `ChangeHistoryEntry`;
- if the retained allocation, expected post-write fingerprint, or generated
  history metadata is missing or malformed, return a blocked response with
  `data={"recovery_state": "create_allocation_missing"}` and do not allocate a
  fresh ID;
- before retrying a missing file, recompute `preview_target_write()` for the same
  retained allocation and retained history metadata. If the recomputed preview's
  post-write fingerprint does not equal the retained
  `expected_post_write_fingerprint`, return a blocked response with
  `data={"recovery_state": "create_expected_write_facts_mismatch"}`. Do not
  approximate this check from candidate fields or from a generic ticket builder.

This recovery logic replaces the old create retry condition that treated
`expected_pre is None` plus `current_ticket_fingerprint is None` as sufficient.
That old condition can create duplicates after a crash between file write and
`ticket_written`.

Do not leave any successful retained-create retry fixture with a placeholder
post-write fingerprint. Shape-only turn-batch tests may use an opaque non-empty
fingerprint token, but any gateway test expecting the retry to write or recover
successfully must derive the retained `expected_post_write_fingerprint` from
`preview_target_write()` for the same allocation and generated
`ChangeHistoryEntry`.

- [ ] **Step 7: Run create idempotency tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_create_attempt_accepts_bounded_recovery_details_without_runtime_decision plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_create_attempt_rejects_runtime_details_when_recovery_facts_present plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_create_attempt_requires_bounded_recovery_details plugins/turbo-mode/ticket/tests/test_turn_batch.py::test_legacy_create_attempt_remains_readable_for_blocking_recovery plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_gateway_lock_is_shared_across_create_candidates plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_attempt_records_allocated_ticket_binding_before_dispatch plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_reuses_retained_allocation_when_file_not_written plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_blocks_allocation_path_that_does_not_match_allocated_id plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_appends_missing_written_event_for_retained_allocation plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_blocks_legacy_attempt_without_expected_write_facts plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_create_retry_blocks_existing_allocation_with_wrong_post_fingerprint plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_autonomous_create_stops_at_duplicate_candidate plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_applies_exact_target_section_update plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py::test_agent_primary_apply_turn_applies_update_through_gateway -q
```

Expected: all create idempotency tests, the existing duplicate-candidate test,
one non-create gateway target-section smoke, and one apply-turn update smoke
pass. Task 3A touches shared gateway, engine, and recovery plumbing; do not
commit it after create-only proof. If any idempotency test passes by ordinary
duplicate detection rather than retained `create_allocation` reuse, if two create
candidates do not share the same allocation lock, if old runtime detail keys are
still required or persisted for bounded create attempts, if legacy create
attempts without retained write facts can allocate a fresh ticket, if mismatched
post-write content is treated as applied, or if the non-create gateway/apply-turn
selectors fail, stop and fix the shared gateway/turn-batch recovery logic before
continuing.

- [ ] **Step 8: Commit Task 3A**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_dedup.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py
git commit -m "fix(ticket): bind create candidates to allocated tickets"
```

Expected: commit succeeds with only the recovery fingerprint helper, gateway,
engine core, the create-attempt validator split, and create idempotency/event
tests staged.

## Task 4: Migrate Reopen And Blocked Cleanup Semantics

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Test: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Test: `plugins/turbo-mode/ticket/tests/test_integration.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- Test: `plugins/turbo-mode/ticket/tests/test_review_findings.py`
- Test: `plugins/turbo-mode/ticket/tests/test_change_history.py`

- [ ] **Step 1: Write failing reopen gateway tests**

In `test_engine_gateway.py`, add:

```python
def test_gateway_reopens_terminal_ticket_to_blocked_with_visible_blocker_shape(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    target = CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",))
    proposed_change = {
        "status": "blocked",
        "blocked_by": ["T-20260527-02"],
        "Blocked On": "Waiting for T-20260527-02.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="reopen",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="reopen",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
        evidence_summary="The closed work is still blocked by T-20260527-02.",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "status: blocked" in text
    assert "blocked_by: [T-20260527-02]" in text
    assert "## Blocked On\nWaiting for T-20260527-02." in text
    assert "## Reopen History" not in text
    assert "| codex | Reopened ticket from candidate evidence." in text
```

Add the open reopen variant:

```python
def test_gateway_reopens_terminal_ticket_to_open_without_reopen_reason(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    target = CandidateTarget(fields=("status",), sections=())
    proposed_change = {"status": "open"}
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="reopen",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="reopen",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
        evidence_summary="The user asked to reopen the work.",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "status: open" in text
    assert "## Reopen History" not in text
    assert "reopen_reason" not in text
```

Add this open-reopen negative variant. It proves `reopen -> open` rejects
blocked-only target content before render-time cleanup can hide the mismatch:

```python
def test_gateway_rejects_reopen_to_open_with_blocker_target_content(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    target = CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",))
    proposed_change = {
        "status": "open",
        "blocked_by": [],
        "Blocked On": None,
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="reopen",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="reopen",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
        evidence_summary="The user asked to reopen the work.",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "policy_blocked"
    assert response.error_code == "policy_blocked"
    assert "reopen_target_not_allowlisted" in response.message
    assert "status: done" in text
    assert "## Blocked On" not in text
```

Rewrite or remove existing tests in `test_execute.py`, `test_integration.py`,
`test_engine_runner.py`, `test_review_findings.py`, and
`test_change_history.py` that preserve `reopen_reason` or `Reopen History` as
normal target reopen behavior. Keep tests that verify historical files can still
be parsed or repaired only when they are explicitly diagnostic/migration tests,
not ordinary `reopen` contract tests.

- [ ] **Step 2: Run reopen gateway tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_blocked_with_visible_blocker_shape plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_open_without_reopen_reason plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_rejects_reopen_to_open_with_blocker_target_content -q
```

Expected: fail because `_execute_reopen()` still requires `reopen_reason`, only
writes `status: open`, and does not yet reject blocked-only target content on
`reopen -> open`.

- [ ] **Step 3: Remove reopen_reason from target field validation**

In `ticket_validate.py`, remove `"reopen_reason"` from the string-field validation tuple. Keep `reopen_reason` out of normal target writes; the reason is now carried by `evidence_summary` and rendered through generated `Change History`.

Add or update a focused assertion in `test_engine_policy.py`:

```python
def test_validate_fields_rejects_reopen_reason_as_target_write_field() -> None:
    assert "reopen_reason is not a target write field" in validate_fields(
        {"reopen_reason": "Regression recurred."}
    )
```

If `validate_fields()` does not yet reject unknown non-target keys directly, add `reopen_reason` to `DEPRECATED_WRITE_FIELDS` in `ticket_validate.py`.

In `ticket_change_history.py`, remove any helper behavior that inserts or
special-cases `## Reopen History` for ordinary target reopen writes. If
historical `Reopen History` placement helpers remain for migration diagnostics,
label them diagnostic-only and keep their tests out of the normal reopen
contract.

- [ ] **Step 4: Update reopen policy to target status shape**

In `ticket_engine_core.py`, replace `_evaluate_reopen_policy()` with:

```python
def _evaluate_reopen_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Return the reopen-policy rejection response, or None when reopen may write."""
    target_status = fields.get("status")
    if target_status not in {"open", "blocked"}:
        return EngineResponse(
            state="need_fields",
            message="status must be open or blocked for reopen",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"missing_fields": ["status"]},
        )

    legacy_block = _check_legacy_gate(ticket)
    if legacy_block is not None:
        return legacy_block

    validation_errors = validate_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"validation_errors": validation_errors},
        )

    if ticket.status not in _TERMINAL_STATUSES:
        return EngineResponse(
            state="invalid_transition",
            message=f"Cannot reopen ticket with status {ticket.status} (must be done or wontfix)",
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                target_status,
                valid_recovery_statuses=[],
                requires_reopen=False,
            ),
        )

    if target_status == "blocked":
        blocked_on = fields.get("blocked_on")
        if not isinstance(blocked_on, str) or not blocked_on.strip():
            return EngineResponse(
                state="need_fields",
                message="Transition to 'blocked' requires blocked_on",
                error_code="blocked_on_required",
                ticket_id=ticket_id,
                data={"missing": ["blocked_on"]},
            )

    message, precondition_code, precondition_detail = _check_transition_preconditions_with_detail(
        ticket.status,
        target_status,
        ticket,
        tickets_dir,
        fields=fields,
    )
    if message is not None:
        return EngineResponse(
            state="invalid_transition",
            message=message,
            ticket_id=ticket_id,
            error_code=precondition_code,
            data=_transition_policy_data(
                ticket.status,
                target_status,
                valid_recovery_statuses=[target_status],
                requires_reopen=True,
                precondition_code=precondition_code,
                precondition_detail=precondition_detail,
            ),
        )

    return None
```

Update `_is_valid_transition()` reopen branch to:

```python
    if action == "reopen":
        return current in ("done", "wontfix") and target in {"open", "blocked"}
```

- [ ] **Step 5: Update reopen execution to write target status and sections**

Change `_execute_reopen()` signature to include target sections:

```python
def _execute_reopen(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    target_sections: Mapping[str, object] | None = None,
) -> EngineResponse:
```

Replace the old `reopen_reason` body with:

```python
    target_status = fields.get("status")
    if target_status not in {"open", "blocked"}:
        return EngineResponse(
            state="need_fields",
            message="status must be open or blocked for reopen",
            error_code="need_fields",
        )

    ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
    if invalid_state is not None:
        return invalid_state
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )

    policy_fields = dict(fields)
    if target_sections and "Blocked On" in target_sections:
        policy_fields["blocked_on"] = target_sections["Blocked On"]
    policy_error = _evaluate_reopen_policy(ticket_id, ticket, policy_fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    ticket_path = Path(ticket.path)
    original_text = ticket_path.read_text(encoding="utf-8")
    data = dict(ticket.frontmatter)
    sections = dict(ticket.sections)
    old_status = data.get("status", "")
    data["status"] = target_status
    if "blocked_by" in fields:
        data["blocked_by"] = fields["blocked_by"]
    if target_status == "open":
        data["blocked_by"] = []
        sections["Blocked On"] = None
    for heading, value in (target_sections or {}).items():
        if heading == "Change History" or not validate_target_section_name(heading):
            return EngineResponse(
                state="escalate",
                message=f"Reopen failed: invalid target section {heading!r}",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
        try:
            sections[heading] = _render_target_section_value(heading, value)
        except ValueError as exc:
            return EngineResponse(
                state="need_fields",
                message=f"Reopen failed: {exc}",
                ticket_id=ticket_id,
                error_code="need_fields",
            )
    targeted_headings = tuple((target_sections or {}).keys())
    if target_status == "open":
        targeted_headings = tuple(sorted(set(targeted_headings) | {"Blocked On"}))
    new_text = _render_target_ticket_text(
        data,
        sections,
        original_text=original_text,
        targeted_headings=targeted_headings,
    )
    if change_history_entry is not None:
        new_text = append_change_history_entry(new_text, change_history_entry)
```

Keep the existing invalid-render and write response pattern, but return changes for target status:

```python
    return EngineResponse(
        state="ok",
        message=f"Reopened {ticket_id} as {target_status}",
        ticket_id=ticket_id,
        data={
            "ticket_path": str(ticket_path),
            "changes": {"status": [old_status, target_status]},
        },
    )
```

- [ ] **Step 6: Pass target sections to reopen dispatch**

In `ticket_engine_gateway.py`, update the reopen branch in `_execute_dispatch()`:

```python
    if dispatch.action == EngineAction.REOPEN:
        return _execute_reopen(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
```

- [ ] **Step 7: Run reopen tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_blocked_with_visible_blocker_shape plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_open_without_reopen_reason plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_rejects_reopen_to_open_with_blocker_target_content plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py::test_reopen_uses_evidence_summary_not_reopen_reason plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_change_history.py -q
```

Expected: all listed reopen and change-history tests pass. Any failure still
asserting `reopen_reason` or `Reopen History` as normal target behavior belongs
to this task, not to Task 7.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_change_history.py plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_change_history.py
git commit -m "fix(ticket): migrate target reopen semantics"
```

Expected: commit succeeds with reopen semantics, change-history cleanup, and
the reopen-related tests only.

## Task 5: Migrate Correction And Recovery Facts

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Write failing target correction and recovery tests**

In `test_autonomy_corrections.py`, import `Mapping` from `collections.abc` and
update correction candidates to target shape:

```python
candidate = CandidateMutation(
    ticket_id="T-20260527-01",
    action="correct",
    target=CandidateTarget(fields=("priority",), sections=()),
    proposed_change={"priority": "high"},
    expected_ticket_fingerprint=target_fingerprint(ticket_path),
    evidence_summary="Prior mutation set priority too low.",
)
```

Update `_correction_decision()` so tests provide recent correction context from
`source_context`, not from candidate content. Include the same binding facts the
apply-turn producer will retain from pending-summary: source mutation ID,
freshness timestamp, target, proposed change, and expected ticket fingerprint.

```python
def _recent_correction_context(
    candidate: CandidateMutation,
    *,
    source_mutation_id: str = "mut-prior-correction",
    retained_at: str = "2026-06-05T12:00:00Z",
) -> dict[str, object]:
    assert candidate.ticket_id is not None
    assert candidate.expected_ticket_fingerprint is not None
    return {
        candidate.ticket_id: {
            "correction_ready": True,
            "correction_detail_retained": True,
            "source_mutation_id": source_mutation_id,
            "retained_at": retained_at,
            "expected_ticket_fingerprint": candidate.expected_ticket_fingerprint,
            "proposed_change": dict(candidate.proposed_change),
            "target": {
                "fields": list(candidate.target.fields),
                "sections": list(candidate.target.sections),
            },
        }
    }


def _correction_decision(
    candidate: CandidateMutation,
    *,
    ticket_path: Path | None = None,
    recent_correction_context: bool | Mapping[str, object] = True,
    now: datetime | None = None,
):
    source_context: dict[str, object] = {}
    if ticket_path is not None and candidate.ticket_id is not None:
        source_context["ticket_state_fingerprints"] = {
            candidate.ticket_id: target_fingerprint(ticket_path)
        }
    if isinstance(recent_correction_context, Mapping):
        source_context["recent_correction_context"] = dict(recent_correction_context)
    elif recent_correction_context and candidate.ticket_id is not None:
        source_context["recent_correction_context"] = _recent_correction_context(candidate)
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="correct_ticket_mutation",
            candidates=(candidate,),
            source_context=source_context,
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=now or datetime(2026, 6, 5, 12, 5, tzinfo=UTC),
    )[0]
```

Update `_apply_correction()` so correction tests use the same target-shaped
gateway request as normal apply-turn:

```python
def _apply_correction(
    *,
    project_root: Path,
    tickets_dir: Path,
    ticket_path: Path,
    candidate: CandidateMutation,
):
    decision = _correction_decision(candidate, ticket_path=ticket_path)
    mutation = GatewayMutation(
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        target=candidate.target,
        proposed_change=dict(candidate.proposed_change),
        tickets_dir=tickets_dir,
        expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
        evidence_summary=candidate.evidence_summary,
    )
    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )
    return decision, response
```

Add this assertion to `test_user_triggered_update_correction_applies_without_new_approval()`:

```python
assert "rewrite_change_history" not in events[0]["details"]
assert "decision" not in events[0]["details"]
assert "current_mode" not in events[0]["details"]
assert "evidence_kind" not in events[0]["details"]
assert events[0]["details"]["target"] == {"fields": ["priority"], "sections": []}
assert events[0]["details"]["evidence_summary"] == "Prior mutation set priority too low."
```

Add this negative authorization test. It must fail before implementation because
`evidence_summary` is line-shaped, but no recent correction context is present:

```python
def test_correction_without_recent_context_requires_discussion(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=False,
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"
```

Add this target/fingerprint binding test:

```python
def test_correction_context_must_match_target_and_expected_fingerprint(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )
    mismatched_context = {
        "recent_correction_context": {
            "T-20260527-01": {
                "correction_ready": True,
                "correction_detail_retained": True,
                "source_mutation_id": "mut-prior-correction",
                "retained_at": "2026-06-05T12:00:00Z",
                "expected_ticket_fingerprint": "different-fingerprint",
                "proposed_change": {"priority": "high"},
                "target": {"fields": ["priority"], "sections": []},
            }
        }
    }

    decision = evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="correct_ticket_mutation",
            candidates=(candidate,),
            source_context=mismatched_context,
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime(2026, 6, 5, 12, 5, tzinfo=UTC),
    )[0]

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"
```

Add this same-target/different-value authorization test. It proves retained
correction context binds the current correction candidate value, not just the
target name set and pre-write fingerprint:

```python
def test_correction_context_must_match_proposed_change(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )
    mismatched_context = _recent_correction_context(candidate)
    mismatched_context["T-20260527-01"]["proposed_change"] = {"priority": "normal"}

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=mismatched_context,
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"
```

Add these runtime-bounded context tests:

```python
def test_correction_context_expired_requires_discussion(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=_recent_correction_context(
            candidate,
            retained_at="2026-05-01T12:00:00Z",
        ),
        now=datetime(2026, 6, 5, 12, 5, tzinfo=UTC),
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_correction_context_unparseable_retained_at_requires_discussion(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=_recent_correction_context(
            candidate,
            retained_at="not-a-timestamp",
        ),
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_compacted_correction_context_requires_discussion(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )
    context = _recent_correction_context(candidate)
    retained = context["T-20260527-01"]
    retained.pop("correction_detail_retained")
    retained["correction_detail_compacted"] = True

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=context,
    )

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "correction_detail_missing"


def test_reordered_equivalent_correction_target_context_is_authorized(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("priority", "status"), sections=()),
        proposed_change={"priority": "high", "status": "open"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation set priority too low.",
    )
    context = _recent_correction_context(candidate)
    context["T-20260527-01"]["target"] = {
        "fields": ["status", "priority"],
        "sections": [],
    }

    decision = _correction_decision(
        candidate,
        ticket_path=ticket_path,
        recent_correction_context=context,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
```

Add this test:

```python
def test_correction_cannot_target_change_history(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=(), sections=("Change History",)),
        proposed_change={"Change History": "caller-owned rewrite"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Attempted unsafe correction.",
    )

    decision = _correction_decision(candidate, ticket_path=ticket_path)

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "target_closure_failed"
```

Add these active and terminal status-correction tests in the same file:

```python
def test_user_triggered_active_correction_to_blocked_uses_update_not_reopen(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", status="open")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",)),
        proposed_change={
            "status": "blocked",
            "blocked_by": ["T-20260527-02"],
            "Blocked On": "Waiting for T-20260527-02.",
        },
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation left the ticket open instead of blocked.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: blocked" in text
    assert "blocked_by: [T-20260527-02]" in text
    assert "## Blocked On\nWaiting for T-20260527-02." in text
    assert "## Reopen History" not in text
    assert " | codex | Corrected ticket from candidate evidence." in text


def test_user_triggered_active_correction_to_open_clears_blocker_without_reopen(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(
        tmp_tickets,
        "one.md",
        id="T-20260527-01",
        status="blocked",
        blocked_by=["T-20260527-02"],
        blocked_on="Waiting for T-20260527-02.",
    )
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(
            fields=("status", "blocked_by"),
            sections=("Blocked On", "Next Action"),
        ),
        proposed_change={
            "status": "open",
            "blocked_by": [],
            "Blocked On": None,
            "Next Action": "Continue the candidate-contract migration.",
        },
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation left a stale blocker on an open ticket.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: open" in text
    assert "blocked_by: []" in text
    assert "## Blocked On" not in text
    assert "## Next Action\nContinue the candidate-contract migration." in text
    assert "## Reopen History" not in text
    assert " | codex | Corrected ticket from candidate evidence." in text


def test_user_triggered_terminal_correction_to_open_uses_reopen_policy(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=("status",), sections=()),
        proposed_change={"status": "open"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Prior mutation closed the ticket by mistake.",
    )

    decision, response = _apply_correction(
        project_root=project_root,
        tickets_dir=tmp_tickets,
        ticket_path=ticket_path,
        candidate=candidate,
    )

    assert decision.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert response.state == "ok"
    text = ticket_path.read_text(encoding="utf-8")
    assert "status: open" in text
    assert "## Reopen History" not in text
    assert " | codex | Corrected ticket from candidate evidence." in text
```

In `test_autonomy_integration_v1.py`, replace the old
`test_agent_primary_apply_turn_applies_correction_through_gateway()` fixture.
It must no longer use `action: "correction"` or candidate-local
`evidence.kind == "correction_detail"`. Update imports to include:

```python
from datetime import UTC, datetime, timedelta

from scripts.ticket_dedup import target_fingerprint
from scripts.ticket_turn_batch import PendingSummaryStore

from tests.test_turn_batch import valid_status_event
```

Add this retained-context producer helper in the same file:

```python
def _append_retained_correction_context(
    project_root: Path,
    ticket_path: Path,
    *,
    target: dict[str, list[str]] | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = None,
    timestamp: str | None = None,
    compacted: bool = False,
) -> None:
    details: dict[str, object] = {
        "correction_ready": True,
        "target": target or {"fields": ["priority"], "sections": []},
        "proposed_change": proposed_change or {"priority": "high"},
        "expected_ticket_fingerprint": (
            expected_ticket_fingerprint or target_fingerprint(ticket_path) or ""
        ),
    }
    if compacted:
        details["correction_detail_compacted"] = True
    else:
        details["correction_detail_retained"] = True
        details["correction_detail"] = "Prior automatic mutation wrote the wrong priority."
    event = valid_status_event(
        "failed",
        event_id="evt_prior_correction",
        timestamp=timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        thread_id="thread-1",
        mutation_id="mut-prior-correction",
        ticket_id="T-20260527-01",
        error_code="policy_blocked",
        **details,
    )
    assert PendingSummaryStore(project_root).append_event(event).state == "appended"
```

Replace the old correction integration test with this target-shaped apply-turn
positive path:

```python
def test_agent_primary_apply_turn_applies_target_correction_from_retained_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(tmp_path, ticket)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "applied"
    assert payload["changed"] is True
    text = ticket.read_text(encoding="utf-8")
    assert "priority: high" in text
    assert " | codex | Corrected ticket from candidate evidence." in text
    events = _events(tmp_path)
    assert [event["status"] for event in events[-3:]] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert "decision" not in events[-3]["details"]
    assert "evidence_kind" not in events[-3]["details"]
```

Add these negative apply-turn paths in the same file:

```python
def test_agent_primary_apply_turn_blocks_correction_with_compacted_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(tmp_path, ticket, compacted=True)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_agent_primary_apply_turn_blocks_correction_with_expired_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    old_timestamp = (datetime.now(UTC) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _append_retained_correction_context(tmp_path, ticket, timestamp=old_timestamp)
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_agent_primary_apply_turn_blocks_correction_with_unmatched_context(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(
        tmp_path,
        ticket,
        expected_ticket_fingerprint="different-fingerprint",
    )
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")


def test_agent_primary_apply_turn_blocks_correction_with_proposed_change_mismatch(
    tmp_path: Path,
) -> None:
    tickets_dir = _init_ticket_project(tmp_path)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="low")
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    expected = target_fingerprint(ticket) or ""
    _append_retained_correction_context(
        tmp_path,
        ticket,
        proposed_change={"priority": "normal"},
    )
    context = _write_context(
        tmp_path,
        {
            "candidate_mutations": [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "correct",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": expected,
                    "evidence_summary": "Prior mutation set priority too low.",
                }
            ]
        },
    )

    result = _apply_turn(tmp_path, context)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "discussion_required"
    assert "priority: low" in ticket.read_text(encoding="utf-8")
```

In `test_engine_gateway.py`, add this non-create recovery-facts test:

```python
def test_update_attempt_records_expected_post_write_facts_before_dispatch(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    target = CandidateTarget(fields=("priority",), sections=("Next Action",))
    proposed_change = {
        "priority": "low",
        "Next Action": "Finish the target candidate migration.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    def fail_dispatch(**_kwargs: object) -> EngineResponse:
        return EngineResponse(
            state="escalate",
            message="simulated dispatch failure",
            error_code="simulated_failure",
        )

    monkeypatch.setattr(gateway, "_execute_dispatch", fail_dispatch)

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    details = _events(project_root)[0]["details"]
    history = details["change_history_entry"]
    assert response.error_code == "simulated_failure"
    assert details["expected_pre_write_fingerprint"] == mutation.expected_ticket_fingerprint
    assert isinstance(details["expected_post_write_fingerprint"], str)
    assert details["expected_post_write_fingerprint"]
    assert history == {
        "timestamp": _events(project_root)[0]["timestamp"],
        "actor": "codex",
        "reason": "Updated ticket from candidate evidence.",
        "corrects": None,
    }
    assert "decision" not in details
    assert "current_mode" not in details
    assert "evidence_kind" not in details
```

In `test_autonomy_recovery.py`, update `_event_with_bound_fingerprints()` so the
attempt details include exact generated history metadata:

```python
def _event_with_bound_fingerprints(
    event: dict[str, object],
    *,
    pre: str = "pre-fp",
    post: str = "post-fp",
) -> dict[str, object]:
    details = dict(event["details"])
    details["expected_pre_write_fingerprint"] = pre
    details["expected_post_write_fingerprint"] = post
    details["change_history_entry"] = {
        "timestamp": "2026-05-27T12:00:00Z",
        "actor": "codex",
        "reason": "Updated ticket from candidate evidence.",
        "corrects": None,
    }
    return {**event, "details": details}
```

Keep
`test_attempt_recorded_with_post_write_state_appends_missing_write_events()` in
`test_autonomy_recovery.py`; it is the focused non-create crash-window test for
an attempt record whose expected post state already matches the current ticket.
Do not defer this file to the full suite.

In `test_autonomy_cli.py`, import the content-only recovery fingerprint helper:

```python
from scripts.ticket_dedup import target_fingerprint, target_recovery_fingerprint
```

Add this helper near `_event_with_recovery_fingerprints()`:

```python
def _create_attempt_event_with_allocation(
    *,
    event_id: str = "evt_prior_create_attempt",
    mutation_id: str = "mut-create-recover",
    expected_post: str,
    allocation_id: str = "T-20260605-01",
    allocation_path: str = "docs/tickets/T-20260605-01.md",
) -> dict[str, object]:
    event = valid_attempt_event(
        event_id=event_id,
        action="create",
        ticket_id=None,
        turn_id="turn-old",
        mutation_id=mutation_id,
        details={},
    )
    details = dict(event["details"])
    details.clear()
    details.update(
        {
            "target": {
                "fields": ["title"],
                "sections": ["Problem", "Next Action"],
            },
            "evidence_summary": (
                "The user asked to track the publisher retry follow-up."
            ),
            "expected_post_write_fingerprint": expected_post,
            "change_history_entry": {
                "timestamp": event["timestamp"],
                "actor": "codex",
                "reason": "Created ticket from candidate evidence.",
                "corrects": None,
            },
            "create_allocation": {
                "allocated_ticket_id": allocation_id,
                "allocated_ticket_path": allocation_path,
                "expected_pre_write_fact": "allocated_target_path_unused",
            },
        }
    )
    return {**event, "details": details}
```

Add these apply-turn prior-turn recovery tests:

```python
def test_apply_turn_prior_turn_create_recovery_uses_retained_allocation(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    allocated = make_ticket(
        tickets_dir,
        "T-20260605-01.md",
        id="T-20260605-01",
        title="Add retry around broker publish",
        problem="Broker publish needs a retry path.",
    )
    expected_post = target_recovery_fingerprint(allocated) or ""
    store = PendingSummaryStore(tmp_path)
    assert (
        store.append_event(
            _create_attempt_event_with_allocation(expected_post=expected_post)
        ).state
        == "appended"
    )
    context = _write_context(
        tmp_path,
        turn_id="turn-new",
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "normal"},
                "expected_ticket_fingerprint": "current-turn-fingerprint",
                "evidence_summary": "Current turn has a separate candidate.",
            }
        ],
    )

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-new",
        "--context-file",
        str(context),
    )

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["state"] == "paused"
    assert payload["pause_reason"] == "repair"
    assert payload["repairable_count"] == 1
    assert payload["reconciliation_count"] == 0
    assert payload["recoveries"][0]["projection_state"] == "append_missing_ticket_written"
    assert payload["recoveries"][0]["ticket_id"] is None
    assert [event["event_id"] for event in PendingSummaryStore(tmp_path).read_events()] == [
        "evt_prior_create_attempt"
    ]


def test_apply_turn_prior_turn_create_recovery_reconciles_wrong_allocation_content(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    make_ticket(
        tickets_dir,
        "T-20260605-01.md",
        id="T-20260605-01",
        title="Different allocated ticket",
        problem="This file is not the retained create result.",
    )
    store = PendingSummaryStore(tmp_path)
    assert (
        store.append_event(
            _create_attempt_event_with_allocation(
                expected_post="not-the-current-post-fingerprint"
            )
        ).state
        == "appended"
    )
    context = _write_context(tmp_path, turn_id="turn-new", candidate_mutations=[])

    result = _run_autonomy(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-new",
        "--context-file",
        str(context),
    )

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["state"] == "paused"
    assert payload["pause_reason"] == "repair"
    assert payload["repairable_count"] == 0
    assert payload["reconciliation_count"] == 1
    assert payload["recoveries"][0]["projection_state"] == "pause_for_reconciliation"
    assert payload["recoveries"][0]["recovery_reason"] == "create_post_write_mismatch"
```

- [ ] **Step 2: Run correction and recovery tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_update_attempt_records_expected_post_write_facts_before_dispatch plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py::test_attempt_recorded_with_post_write_state_appends_missing_write_events plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_prior_turn_create_recovery_uses_retained_allocation plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_prior_turn_create_recovery_reconciles_wrong_allocation_content -q
```

Expected: fail because correction helpers, integration fixtures, gateway recovery
details, turn-batch validation, or the apply-turn ledger projection still use the
old `correction` action, flat fields, persisted decision/current-mode/evidence-kind
details, lack pre-write expected post recovery facts, or cannot project prior-turn
create recovery from retained allocation facts.

- [ ] **Step 3: Normalize correction action and unsafe correction checks**

In `ticket_autonomy_runtime.py`:

- Confirm Task 1 already replaced runtime action string `"correction"` with
  target action `"correct"` across runtime checks. Any remaining runtime hit is
  in scope here only if Task 1 missed it; do not leave the old action literal in
  runtime after this task.
- Keep `RuntimeDecisionKind.APPLY_CORRECTION` as the decision kind.
- Remove old target-candidate action literals from runtime action groups:
  `reprioritize`, `stale_cleanup`, `blocker_edit`, and `refine` are not target
  candidate actions. Any retained update behavior must flow through `action:
  "update"` plus explicit target fields or sections.
- Replace the correction branch shape check so it rejects kernel-owned sections through `_candidate_shape_errors()` rather than old proposed-change control keys:

```python
shape_errors = _candidate_shape_errors(candidate)
if shape_errors:
    decisions.append(
        _decision(
            candidate,
            RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
            reason="target_closure_failed",
            pending_summary_status="discussion_required",
        )
    )
    continue
```

Extend the runtime datetime import to `from datetime import UTC, datetime,
timedelta`. Replace `del now` in `evaluate_autonomy_intent()` with a retained
`runtime_now = now or datetime.now(UTC)` value. Then replace
`_correction_detail_available()` with a source-context gate. The helper must not
read `candidate.evidence_summary`; that text explains the correction but does
not authorize the privileged correction lane:

```python
_CORRECTION_CONTEXT_MAX_AGE = timedelta(days=14)


def _parse_z(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


def _canonical_target_key(target: CandidateTarget) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (tuple(sorted(target.fields)), tuple(sorted(target.sections)))


def _canonical_context_target(value: object) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    if not isinstance(value, Mapping):
        return None
    fields = value.get("fields")
    sections = value.get("sections")
    if not isinstance(fields, list) or not isinstance(sections, list):
        return None
    if not all(isinstance(field, str) for field in fields):
        return None
    if not all(isinstance(section, str) for section in sections):
        return None
    return (tuple(sorted(fields)), tuple(sorted(sections)))


def _correction_detail_available(
    candidate: CandidateMutation,
    source_context: Mapping[str, object],
    *,
    now: datetime,
    max_age: timedelta = _CORRECTION_CONTEXT_MAX_AGE,
) -> bool:
    contexts = source_context.get("recent_correction_context")
    if not isinstance(contexts, Mapping) or candidate.ticket_id is None:
        return False
    context = contexts.get(candidate.ticket_id)
    if not isinstance(context, Mapping):
        return False
    if context.get("correction_ready") is not True:
        return False
    if context.get("correction_detail_retained") is not True:
        return False
    if not isinstance(context.get("source_mutation_id"), str):
        return False
    retained_at = _parse_z(context.get("retained_at"))
    if retained_at is None:
        return False
    if retained_at < now - max_age:
        return False
    if context.get("expected_ticket_fingerprint") != candidate.expected_ticket_fingerprint:
        return False
    proposed_change = context.get("proposed_change")
    if not isinstance(proposed_change, Mapping):
        return False
    if dict(proposed_change) != dict(candidate.proposed_change):
        return False
    return _canonical_context_target(context.get("target")) == _canonical_target_key(
        candidate.target
    )
```

Call it from the correction branch with `intent.source_context` and
`runtime_now`:

```python
if not _correction_detail_available(
    candidate,
    intent.source_context,
    now=runtime_now,
):
    decisions.append(
        _decision(
            candidate,
            RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
            reason="correction_detail_missing",
            pending_summary_status="discussion_required",
        )
    )
    continue
```

In `ticket_turn_batch.py`, make the retained correction context producer
explicit. A `mutation_status` event with `status == "failed"` and
`details.correction_ready is True` is the only producer for automatic correction
authorization context in this slice. Keep `correction_detail` private, but
require these bounded mechanical details when `correction_ready` is true:

```python
{
    "correction_ready": True,
    "correction_detail": "Prior automatic mutation wrote the wrong priority.",
    "correction_detail_retained": True,
    "target": {"fields": ["priority"], "sections": []},
    "proposed_change": {"priority": "high"},
    "expected_ticket_fingerprint": "target-fingerprint-before-correction",
}
```

The event's top-level `mutation_id`, `ticket_id`, and `timestamp` are part of
the binding. Add turn-batch validation tests proving a newly appended
correction-ready failed status event is invalid when any of `correction_detail`,
`correction_detail_retained`, `target`, `proposed_change`, `expected_ticket_fingerprint`,
`ticket_id`, `mutation_id`, or parseable `timestamp` is missing or wrong-typed.
Compacted retained events may keep
`correction_ready` with `correction_detail_compacted is True`, but they must not
retain `correction_detail_retained` and are not authorization producers. Update
`_correction_ready_event()` in
`plugins/turbo-mode/ticket/tests/test_turn_batch.py` to carry `target` and
`expected_ticket_fingerprint`; keep its compaction tests proving old or overflow
events lose `correction_detail`.

In `ticket_autonomy.py`, derive `recent_correction_context` only from fresh,
bounded private pending-summary events that still retain uncompacted correction
detail. Extend the local datetime import to include `timedelta`, and add this
local timestamp parser near `_now_z()`:

```python
def _parse_z(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)
```

```python
def _recent_correction_context_from_events(
    events: Sequence[Mapping[str, object]],
    *,
    now: datetime | None = None,
    max_age_days: int = 14,
) -> dict[str, object]:
    current = now or datetime.now(UTC)
    age_floor = current - timedelta(days=max(max_age_days, 0))
    context: dict[str, object] = {}
    for event in events:
        ticket_id = event.get("ticket_id")
        mutation_id = event.get("mutation_id")
        timestamp = _parse_z(event.get("timestamp"))
        details = event.get("details")
        if (
            not isinstance(ticket_id, str)
            or not isinstance(mutation_id, str)
            or timestamp is None
            or timestamp < age_floor
            or not isinstance(details, Mapping)
        ):
            continue
        if details.get("correction_ready") is not True:
            continue
        if "correction_detail" not in details:
            continue
        if details.get("correction_detail_retained") is not True:
            continue
        target = details.get("target")
        if not isinstance(target, Mapping):
            continue
        fields = target.get("fields")
        sections = target.get("sections")
        proposed_change = details.get("proposed_change")
        expected_ticket_fingerprint = details.get("expected_ticket_fingerprint")
        if not isinstance(fields, list) or not isinstance(sections, list):
            continue
        if not isinstance(proposed_change, Mapping):
            continue
        if not isinstance(expected_ticket_fingerprint, str) or not expected_ticket_fingerprint:
            continue
        context[ticket_id] = {
            "correction_ready": True,
            "correction_detail_retained": True,
            "source_mutation_id": mutation_id,
            "retained_at": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expected_ticket_fingerprint": expected_ticket_fingerprint,
            "proposed_change": dict(proposed_change),
            "target": {"fields": fields, "sections": sections},
        }
    return context
```

When `evaluate_autonomy_intent()` is called for apply-turn candidates, pass
`{"recent_correction_context": context}` only when this helper returns a
non-empty mapping. Do not synthesize correction context from the candidate
envelope or from `evidence_summary`.

In `ticket_engine_gateway.py`:

- Replace the `_decision_error()` correction guard so it accepts target action
  `"correct"` while still requiring `RuntimeDecisionKind.APPLY_CORRECTION`.
- Confirm `build_engine_dispatch()` passes the current parsed ticket status to
  `map_candidate_to_engine()` for all non-create target mutations. Blocked
  `done`/`wontfix` candidates must be rejected unless they explicitly name
  `blocked_by=[]` and `Blocked On=None`; active current tickets corrected to
  `open` or `blocked` must dispatch as update; terminal current tickets
  corrected to `open` or `blocked` must dispatch as reopen.
- Update `_change_history_reason()` so `action == "correct"` returns the
  generated correction reason. No target candidate path should keep the old
  `"correction"` action literal.

In `ticket_turn_batch.py`, separate retained candidate-action validation from
maintenance event validation:

- Add `_TARGET_MUTATION_ACTIONS = frozenset({"create", "update", "done", "wontfix", "reopen", "correct"})`.
- Use `_TARGET_MUTATION_ACTIONS` for new `mutation_attempt` and
  `mutation_status` events with status `ticket_written` when those events record
  a retained target candidate action fact.
- Keep `summarize`, `compact`, and `pause_automation` valid only for their
  event-specific maintenance records if current operation-log validation still
  needs them. Prefer an `_EVENT_ACTIONS_BY_TYPE` map over one flat `_ACTIONS`
  set if that makes the boundary executable.
- Do not keep `reprioritize`, `stale_cleanup`, `blocker_edit`, `refine`,
  `archive`, `delete`, `history_repair`, or `"correction"` as valid new
  target candidate actions.
- Keep historical compaction status names only when they describe existing
  stored correction detail rather than new candidate action input.
  `ticket_review.py` may still emit `stale_cleanup` as read-only review-hygiene
  output, but candidate discovery must not accept it as a write candidate.

Add turn-batch tests proving both sides of the split:

- a new `mutation_attempt` or `mutation_status`/`ticket_written` event rejects
  `reprioritize`, `stale_cleanup`, `blocker_edit`, `refine`, `archive`,
  `delete`, `history_repair`, `summarize`, `compact`, `pause_automation`, and
  `"correction"` as candidate action values;
- existing maintenance event types still accept their own mechanical actions
  where those events are intentionally retained.

- [ ] **Step 4: Extend pre-write expected post recovery facts to non-create writes**

Task 3A already added `target_recovery_fingerprint_for_text()`,
`target_recovery_fingerprint()`, `ExpectedWriteFacts`, and create support for
`TargetWritePreview`/`preview_target_write()`. Do not redefine those helpers in
this task. In `ticket_engine_core.py`, extend `preview_target_write()` to cover
`update`, `done`, `wontfix`, and `reopen` with the same render path and
validation as the corresponding execute helper, including the same
`ChangeHistoryEntry`, target sections, blocked cleanup, and reopen shape.
Return an `EngineResponse` for the same validation failures execute would
return. If preview and execute would diverge for any action, stop and refactor
the shared rendering helpers before continuing; do not approximate the expected
post fingerprint from candidate fields. This preview/execute parity check is
the fingerprint trust boundary; a broader shared-rendering refactor is optional
unless this check finds divergence.

In `ticket_turn_batch.py`, update recovery state to compare both pre-write and
post-write facts. Pre-write comparison keeps the existing mtime-sensitive
current fingerprint; post-write comparison uses the content-only recovery
fingerprint:

```python
@dataclass(frozen=True, slots=True)
class CurrentRecoveryFingerprints:
    """Current ticket fingerprints for retry recovery comparisons."""

    pre_write_fingerprint: str | None
    post_write_fingerprint: str | None
```

Change `project_mutation_recovery()` to accept
`current_ticket_fingerprints: CurrentRecoveryFingerprints` instead of one
`current_ticket_fingerprint` value. In the `attempt_recorded` branch:

```python
if current_ticket_fingerprints.pre_write_fingerprint == expected_pre:
    return RecoveryProjection(
        "retry_with_same_mutation",
        thread_id,
        mutation_id,
        current_ticket_fingerprints.pre_write_fingerprint,
        expected_pre,
        expected_post,
    )
if expected_post is None:
    return _pause_projection(
        thread_id=thread_id,
        mutation_id=mutation_id,
        current_ticket_fingerprint=current_ticket_fingerprints.post_write_fingerprint,
        expected_pre_write_fingerprint=expected_pre,
        expected_post_write_fingerprint=expected_post,
        reason="missing_post_write_fingerprint",
    )
if current_ticket_fingerprints.post_write_fingerprint == expected_post:
    events_to_append = (
        _recovery_event(
            reference=reference,
            event_type="mutation_status",
            status="ticket_written",
            reason="Recovered missing autonomous Ticket write event.",
            details={"post_write_fingerprint": expected_post},
        ),
        _recovery_event(
            reference=reference,
            event_type="mutation_status",
            status="applied",
            reason="Recovered autonomous Ticket terminal status.",
            details={},
        ),
    )
    return RecoveryProjection(
        "append_missing_ticket_written",
        thread_id,
        mutation_id,
        current_ticket_fingerprints.post_write_fingerprint,
        expected_pre,
        expected_post,
        events_to_append,
    )
```

Update every caller, including `_existing_mutation_recovery_response()` and
`test_autonomy_recovery.py`, to pass both current fingerprints. Do not compare a
content-only post fingerprint to the old mtime-sensitive `target_fingerprint()`.

In the same `attempt_recorded` branch, handle `reference.get("action") ==
"create"` before the non-create pre-write comparison. Prior-turn create recovery
does not have a current candidate to retry, and create attempts have
`ticket_id=None`, so it must use retained `details.create_allocation` instead of
`find_ticket_by_id()`:

```python
if reference.get("action") == "create":
    if expected_post is None:
        return _pause_projection(
            thread_id=thread_id,
            mutation_id=mutation_id,
            current_ticket_fingerprint=(
                current_ticket_fingerprints.post_write_fingerprint
            ),
            expected_pre_write_fingerprint=expected_pre,
            expected_post_write_fingerprint=expected_post,
            reason="missing_post_write_fingerprint",
        )
    if current_ticket_fingerprints.post_write_fingerprint == expected_post:
        events_to_append = (
            _recovery_event(
                reference=reference,
                event_type="mutation_status",
                status="ticket_written",
                reason="Recovered missing autonomous Ticket write event.",
                details={"post_write_fingerprint": expected_post},
            ),
            _recovery_event(
                reference=reference,
                event_type="mutation_status",
                status="applied",
                reason="Recovered autonomous Ticket terminal status.",
                details={},
            ),
        )
        return RecoveryProjection(
            "append_missing_ticket_written",
            thread_id,
            mutation_id,
            current_ticket_fingerprints.post_write_fingerprint,
            expected_pre,
            expected_post,
            events_to_append,
        )
    if current_ticket_fingerprints.post_write_fingerprint is None:
        return _pause_projection(
            thread_id=thread_id,
            mutation_id=mutation_id,
            current_ticket_fingerprint=None,
            expected_pre_write_fingerprint=expected_pre,
            expected_post_write_fingerprint=expected_post,
            reason="create_allocation_unwritten",
        )
    return _pause_projection(
        thread_id=thread_id,
        mutation_id=mutation_id,
        current_ticket_fingerprint=current_ticket_fingerprints.post_write_fingerprint,
        expected_pre_write_fingerprint=expected_pre,
        expected_post_write_fingerprint=expected_post,
        reason="create_post_write_mismatch",
    )
```

In `ticket_autonomy.py`, replace `_current_ticket_fingerprint_for_event()` with a
helper that returns `CurrentRecoveryFingerprints`. For non-create events, compute
the existing mtime-sensitive pre-write fingerprint and the content-only
post-write recovery fingerprint for the found ticket. For create events, read
`details.create_allocation.allocated_ticket_path`, resolve it under
`project_root`, and compute only the content-only post-write recovery fingerprint
when that retained allocated path exists:

```python
def _current_recovery_fingerprints_for_event(
    project_root: Path,
    event: Mapping[str, object],
) -> CurrentRecoveryFingerprints:
    if event.get("action") == "create":
        details = event.get("details")
        allocation = details.get("create_allocation") if isinstance(details, Mapping) else None
        raw_path = allocation.get("allocated_ticket_path") if isinstance(allocation, Mapping) else None
        if not isinstance(raw_path, str) or not raw_path:
            return CurrentRecoveryFingerprints(None, None)
        path = project_root / raw_path
        if not path.is_file():
            return CurrentRecoveryFingerprints(None, None)
        return CurrentRecoveryFingerprints(
            pre_write_fingerprint=None,
            post_write_fingerprint=target_recovery_fingerprint(path),
        )

    ticket_id = event.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        return CurrentRecoveryFingerprints(None, None)
    try:
        ticket = find_ticket_by_id(project_root / "docs" / "tickets", ticket_id)
    except InvalidTicketState:
        return CurrentRecoveryFingerprints(None, None)
    if ticket is None:
        return CurrentRecoveryFingerprints(None, None)
    path = Path(ticket.path)
    return CurrentRecoveryFingerprints(
        pre_write_fingerprint=compute_target_fingerprint(path),
        post_write_fingerprint=target_recovery_fingerprint(path),
    )
```

Update `_mutation_recovery_items()` to pass that helper's result into
`project_mutation_recovery()`. Add `CurrentRecoveryFingerprints` to the
`ticket_turn_batch` imports and import `target_recovery_fingerprint` from
`ticket_dedup`. Do not leave the old single-fingerprint caller behind; otherwise
the Task 5 focused tests can pass while the live apply-turn prior-turn recovery
path is stale.

In `ticket_engine_gateway.py`, update `_fingerprint_details()` and the
`mutation_attempt` event details so target candidate mutation attempt events
include only bounded target facts and the retained recovery facts needed for an
interrupted write. Replace the whole `details={...}` block that currently adds
`decision`, `current_mode`, and `evidence_kind`; do not hide those fields
outside `_fingerprint_details()`. If Task 3A has already added
`create_allocation`, keep that nested mechanical fact for create attempts.

Reuse the Task 3A `_change_history_entry_details()` and `ExpectedWriteFacts`
helpers. Do not introduce a second recovery-facts type or a second history
metadata shape.

Before appending `mutation_attempt`, build the dispatch, create allocation, and
`ChangeHistoryEntry`, then call `preview_target_write()` for non-create writes
and fresh create attempts. For retained create retries, preserve Task 3A's
retained branch exactly: reuse the recorded allocation and retained
`ExpectedWriteFacts`, including the generated `ChangeHistoryEntry` details.
Do not reconstruct retained create history metadata from the current clock or a
fresh `_change_history_entry()` call.

Use one timestamp for the attempt event and generated history entry on fresh
attempts:

```python
attempt_timestamp = change_history_timestamp or _now_z()
if retained_create_attempt is not None:
    create_allocation = retained_create_attempt.allocation
    expected_write_facts = retained_create_attempt.expected_write_facts
    change_history_entry = _change_history_entry_from_expected_facts(
        retained_create_attempt.expected_write_facts
    )
    attempt_timestamp = change_history_entry.timestamp
else:
    change_history_entry = _change_history_entry(
        mutation.action,
        timestamp=attempt_timestamp,
    )
    preview = preview_target_write(
        action=dispatch.action.value,
        ticket_id=mutation.ticket_id,
        fields=dict(dispatch.fields),
        target_sections=dispatch.sections or {},
        session_id=thread_id,
        request_origin="agent",
        tickets_dir=mutation.tickets_dir,
        change_history_entry=change_history_entry,
        reserved_ticket_id=(
            create_allocation.ticket_id if create_allocation is not None else None
        ),
    )
    if isinstance(preview, EngineResponse):
        return preview
    expected_write_facts = ExpectedWriteFacts(
        expected_post_write_fingerprint=preview.post_write_fingerprint,
        change_history_entry=_change_history_entry_details(change_history_entry),
    )
```

Update `_base_event()` and `_append_gateway_event()` to accept an optional
`timestamp` argument so the new `mutation_attempt` event timestamp exactly
matches the generated `ChangeHistoryEntry.timestamp`. Do not generate two
independent timestamps for the same write attempt.

After `_execute_dispatch()` succeeds, compute `post_write_fingerprint` for the
`mutation_status`/`ticket_written` event with
`target_recovery_fingerprint(Path(ticket_path_raw))`, not with the
mtime-sensitive `compute_target_fingerprint()`. The observed
`post_write_fingerprint` and the retained `expected_post_write_fingerprint` must
be comparable recovery fingerprints.

```python
def _fingerprint_details(
    *,
    mutation: GatewayMutation,
    project_root: Path,
    expected_write_facts: ExpectedWriteFacts,
    create_allocation: CreateAllocation | None = None,
) -> dict[str, object]:
    details: dict[str, object] = {
        "target": {
            "fields": list(mutation.target.fields),
            "sections": list(mutation.target.sections),
        },
        "evidence_summary": mutation.evidence_summary,
        "expected_post_write_fingerprint": (
            expected_write_facts.expected_post_write_fingerprint
        ),
        "change_history_entry": expected_write_facts.change_history_entry,
    }
    if mutation.action == "create":
        if create_allocation is not None:
            details["create_allocation"] = _create_allocation_details(
                create_allocation,
                project_root=project_root,
            )
        return details
    details["expected_pre_write_fingerprint"] = mutation.expected_ticket_fingerprint
    return details
```

Use the helper as the full details value:

```python
details=_fingerprint_details(
    mutation=mutation,
    project_root=project_root,
    expected_write_facts=expected_write_facts,
    create_allocation=create_allocation,
)
```

Do not add confidence scores, evidence-kind lists, current-mode labels, runtime
decision kinds, approval states, Handoff metadata, private workflow stages, or
copied ticket content. `change_history_entry` is allowed only with `timestamp`,
`actor`, `reason`, and `corrects`. `create_allocation` is allowed only with
`allocated_ticket_id`, `allocated_ticket_path`, and
`expected_pre_write_fact="allocated_target_path_unused"`.

Task 3A already added the create-specific `valid_create_attempt_event()` helper
and create-attempt validation branch. In this task, update the remaining
non-create/correction fixtures so their `details` contain only `target`,
`evidence_summary`, `expected_pre_write_fingerprint`,
`expected_post_write_fingerprint`, and `change_history_entry`. If the general
`valid_attempt_event()` helper in
`plugins/turbo-mode/ticket/tests/test_turn_batch.py` still injects `decision`,
`current_mode`, or `evidence_kind` for non-create target attempts, update that
helper here and adjust existing tests to add only the status-specific details
they actually exercise. Do not reopen the Task 3A `create_allocation` shape.

- [ ] **Step 5: Run correction and gateway recovery tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py -q
```

Expected: all six files pass, including the target-shaped apply-turn correction
positive path and the compacted, expired, unmatched fingerprint, and mismatched
proposed-change correction-context block paths. Any failure still using
`"correction"` as a target candidate action,
narrowing maintenance event validation into candidate action validation,
expecting `decision`, `evidence_kind`, or `current_mode` mutation attempt
details, missing `expected_post_write_fingerprint`, authorizing correction from
candidate content instead of retained pending-summary context, or failing to
recover a missing `ticket_written` event from either the gateway retry path or
the apply-turn prior-turn ledger path belongs to this task.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
git commit -m "fix(ticket): migrate correction recovery facts"
```

Expected: commit succeeds with correction/recovery files, the live apply-turn
ledger caller, and directly affected operation-log tests only. The recovery
fingerprint helper should already be in the Task 3A commit.

## Task 6: Update Source Docs, Skills, Contract Availability, And Lifecycle Prose

**Files:**
- Modify: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/TERMS.md`
- Modify: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Test: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

Precondition: do not start Task 6 until the Task 3 source-entrypoint tests, Task
3A create-idempotency tests, and Task 5 correction/recovery/integration tests
pass, including `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`.
The docs must not claim that source exposes a target candidate mutation path
while `ticket_autonomy.py` still constructs old gateway mutations, while create
retry can still allocate a duplicate ticket instead of using a retained
allocation binding, or while non-create recovery lacks pre-write
`expected_post_write_fingerprint` and exact generated `Change History` metadata,
or while apply-turn prior-turn ledger recovery cannot interpret retained create
allocation facts. The docs, manifest-linked terms, and plugin manifest also must
not preserve old lifecycle prose that says terminal tickets only reopen to
`open` after Task 4 adds `reopen -> blocked` source behavior.

- [ ] **Step 1: Write failing docs-contract tests**

In `test_docs_contract.py`, add a source-availability contract test, add an
authority-alignment contract test for identity/correction wording, update the
lifecycle assertion for terminal reopen to `open` or `blocked`, and update every
existing assertion that currently requires `"temporarily unavailable"` for
capture/update write availability. This includes the capture skill frontmatter,
active create guidance, update active guidance, and update skill description
assertions. Do not leave old unavailable assertions for the source path while
adding a new absence-only test. Do not leave the old exact assertion that
terminal tickets reopen only to `open`.

Add:

```python
def test_ticket_write_docs_no_longer_claim_source_entrypoint_missing() -> None:
    paths = [
        Path("plugins/turbo-mode/ticket/README.md"),
        Path("plugins/turbo-mode/ticket/HANDBOOK.md"),
        Path("plugins/turbo-mode/ticket/references/ticket-contract.md"),
        Path("plugins/turbo-mode/ticket/TERMS.md"),
        Path("plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md"),
        Path("plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md"),
    ]
    manifest = json.loads(
        Path("plugins/turbo-mode/ticket/.codex-plugin/plugin.json").read_text(
            encoding="utf-8"
        )
    )
    text_sources = [(path, path.read_text(encoding="utf-8")) for path in paths]
    text_sources.append(
        (
            Path("plugins/turbo-mode/ticket/.codex-plugin/plugin.json"),
            manifest["interface"]["longDescription"],
        )
    )
    forbidden = (
        "temporarily unavailable until source exposes",
        "source exposes a live target-candidate entrypoint",
        "until Ticket exposes and documents a live source entrypoint",
        "write mutation is rebaselined",
        "rebaselined onto the target candidate contract",
    )
    for path, text in text_sources:
        for phrase in forbidden:
            assert phrase not in text, f"{path} still contains {phrase!r}"
```

Add:

```python
def test_authority_docs_align_identity_and_correction_context() -> None:
    control = _read_text(
        Path("docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md")
    )
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    combined = _normalize_whitespace(control + "\n" + contract)

    assert (
        "expected_ticket_fingerprint is the candidate-supplied copy of the live target fingerprint"
        in combined
    )
    assert (
        "Ticket recomputes the current live target fingerprint before writing"
        in combined
    )
    assert (
        "recent uncompacted correction context is required before automatic correct"
        in combined
    )
    assert "correction_detail_missing" in combined
```

Update the existing lifecycle test in the same file:

```python
def test_contract_documents_lifecycle_transitions() -> None:
    text = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    lifecycle = _section(text, "## Lifecycle Transitions", "\n## ")
    normalized = _normalize_whitespace(lifecycle)

    assert "`idea` may move only to `open`" in normalized
    assert "`open` may move to `blocked`" in normalized
    assert "`blocked` may move to `open`" in normalized
    assert "`open` and `blocked` may close to `done` or `wontfix`" in normalized
    assert "`done` and `wontfix` reopen to `open` or `blocked`" in normalized
    assert "`reopen -> blocked` requires valid `Blocked On`" in normalized
    assert "`blocked -> open` must clear `blocked_by: []` and `blocked_on: null`" in normalized
    assert "without `dependency_override`, closing as `done` is blocked" in normalized
    assert "closing as `wontfix` bypasses blocker resolution" in normalized
```

- [ ] **Step 2: Run full docs-contract test and verify RED**

Run after the Task 6 precondition is satisfied:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_docs_contract.py -q
```

Expected: fail on README/HANDBOOK/contract/TERMS/skills/manifest availability
wording, on the control-doc/contract identity and correction-context authority
wording, on the contract lifecycle sentence that still says terminal tickets
reopen only to `open`, and on any existing docs-contract assertion that still
requires the old unavailable source-write language.

- [ ] **Step 3: Update source docs availability language**

Replace "temporarily unavailable until source exposes a live target-candidate entrypoint" language with source-truthful wording:

```text
Source now exposes the target candidate mutation path. Installed-runtime availability still requires a separate cache refresh and runtime inventory before claiming the active Codex plugin can perform writes.
```

Use this boundary in README/HANDBOOK/contract/TERMS:

```text
Capture and update skills may describe and route target candidates through the source entrypoint when the installed Ticket runtime matches this source. Do not claim installed write availability from source files alone.
```

In `capture-ticket/SKILL.md` and `update-ticket/SKILL.md`, replace hard "temporarily unavailable" stop text with:

```text
Before mutating, confirm the installed Ticket runtime exposes the target candidate mutation path. If runtime proof is unavailable in the current turn, summarize the intended target candidate and say runtime write proof is missing. Do not write through legacy flat candidate paths.
```

Do not add cache refresh commands to skill procedures.

In `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`, replace the
`interface.longDescription` wording that says write mutation is still being
rebaselined with source-truthful manifest text that keeps runtime proof separate:

```json
"longDescription": "Read, validate, triage, diagnose, and route repo-local Ticket state through the source target candidate contract. Installed write availability still requires separate runtime proof."
```

In `plugins/turbo-mode/ticket/TERMS.md`, replace the manifest-linked source
rebaseline wording with source-truthful terms text that preserves the installed
runtime boundary:

```text
The plugin is provided as source for repo-local ticket reading, backlog triage,
capture/update candidate routing through the source target candidate contract,
and explicit maintenance diagnostics. Installed write availability still
requires separate runtime proof.
```

In `plugins/turbo-mode/ticket/references/ticket-contract.md`, replace the old
lifecycle sentence:

```text
`done` and `wontfix` reopen to `open`.
```

with:

```text
`done` and `wontfix` reopen to `open` or `blocked`. `reopen -> blocked`
requires valid blocked-ticket shape, including `Blocked On` and any visible
`blocked_by` ticket-ID dependencies.
```

Check README and HANDBOOK for duplicated lifecycle prose. If either repeats the
old open-only terminal reopen claim, update it in the same commit or add a
docs-contract assertion that forbids the stale phrase in that file.

In the May 30 control doc and `ticket-contract.md`, make the identity and
correction authorization wording explicit:

```text
For non-create writes, `expected_ticket_fingerprint` is the candidate-supplied
copy of the live target fingerprint at discovery/evaluation time and participates
in candidate identity. Ticket recomputes the current live target fingerprint
before writing and rejects stale candidates whose current fingerprint no longer
matches `expected_ticket_fingerprint`; callers do not supply authoritative
identity values.
```

```text
Automatic `correct` requires recent uncompacted correction context outside the
candidate envelope. If that context is absent, expired, compacted, or not bound
to the candidate target and `expected_ticket_fingerprint`, runtime returns
`correction_detail_missing` instead of emitting `APPLY_CORRECTION`.
```

- [ ] **Step 4: Run full docs-contract test and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_docs_contract.py -q
```

Expected: the full docs-contract file passes, including the updated lifecycle
assertion, identity/correction authority assertions, capture/update skill
availability assertions, plugin manifest availability assertion, and
manifest-linked `TERMS.md` availability assertion. This command proves
docs-contract coverage only; do not claim Task 3, Task 3A, or Task 5 source-test
proof from this docs-only selector. Those source-test gates are Task 6
preconditions and are rechecked by the final all-source verification command.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/TERMS.md plugins/turbo-mode/ticket/.codex-plugin/plugin.json plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "docs(ticket): update target candidate write availability"
```

Expected: commit succeeds with docs/terms/skill/manifest availability and
lifecycle contract files only.

## Task 7: Final Source Verification

**Files:**
- Verify all changed source, tests, docs, and skills.

- [ ] **Step 1: Run focused candidate-contract test set**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_change_history.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_docs_contract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run target-contract residue and construction-site checks**

Run:

```bash
rg -n "EvidenceLink|\.evidence|\"correction\"|conflict_reason|reopen_reason|Reopen History|evidence_kind|current_mode|\"decision\"|decision\.kind|RuntimeDecisionKind|mutation\.fields|target_fingerprint|reprioritize|stale_cleanup|blocker_edit|refine|archive|delete|history_repair|summarize|compact|pause_automation|codex\.ticket\.mutation\.v1|ticket_write|mutation_status|ticket_written|allocated_ticket_id|create_allocation|expected_post_write_fingerprint|post_write_fingerprint|ChangeHistoryEntry|change_history_timestamp|key_files" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
rg -n "GatewayMutation\(|CandidateMutation\(" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: every remaining hit is explicitly one of:

- legacy direct engine plan/execute syntax intentionally outside the target
  candidate path;
- calls to `scripts.ticket_dedup.target_fingerprint` used only to compute a
  current ticket fingerprint for `expected_ticket_fingerprint`;
- runtime mode inputs or tests that are not persisted mutation-attempt details;
- internal `RuntimeDecisionKind` branch logic, including
  `RuntimeDecisionKind.APPLY_CORRECTION`, that is not persisted in
  mutation-attempt details or result data;
- historical migration/diagnostic test data labeled as such;
- non-candidate correction-detail storage vocabulary retained for recent
  correction recovery;
- read-only review-hygiene output such as `ticket_review.py` `stale_cleanup`
  that candidate discovery does not accept as a write candidate;
- maintenance event validation for `summarize`, `compact`, or
  `pause_automation`, only where the code validates those event types rather
  than a target candidate action fact;
- `mutation_status`/`ticket_written` validation and event handling only where it
  names the actual operation-log event boundary, not a stale `ticket_write`
  pseudo-event;
- `create_allocation`, `allocated_ticket_id`, and `allocated_ticket_path` only
  as bounded retained create recovery facts for `create` attempts;
- `expected_post_write_fingerprint`, `post_write_fingerprint`, and
  `ChangeHistoryEntry` only as bounded recovery facts or helpers for
  comparing the expected and observed post-write target ticket;
- `change_history_timestamp` only as a local variable used to reuse the retained
  attempt timestamp for exact generated history recovery;
- `key_files` only in source create rendering/validation, ingest/envelope tests,
  historical examples, or target docs that describe create-supported optional
  sections; it must not be a valid non-create target write field;
- low-level `make_mutation_id()` tests that use `codex.ticket.mutation.v1` as
  arbitrary schema input and are not candidate-contract fixtures;
- target-shaped `CandidateMutation(...)` or `GatewayMutation(...)` constructions
  that include the new target envelope fields;
- user-facing text explaining removed/deprecated input.

Any remaining old-shaped target candidate runtime, gateway, discovery, identity,
source-entrypoint, operation-log, or normal reopen/correct test hit must be
fixed before continuing. In particular, no accepted target candidate mapping may
mention `conflict_reason`, no `mutation_attempt` details may persist
`"decision"` or a runtime decision kind, and no new mutation event may validate
maintenance action names as candidate actions. No plan or source residue may
refer to `ticket_write` as an existing operation-log event type.

- [ ] **Step 3: Run full Ticket suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: full Ticket suite passes. If failures appear outside the focused
candidate-contract set, inspect before deciding disposition. Failures involving
the coverage-map legacy surfaces are in scope for this migration unless the
residue check already classified them as intentionally retained.

- [ ] **Step 4: Run lint and diff checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

Expected: both commands pass.

- [ ] **Step 5: Check for generated residue**

Run:

```bash
git status --short --ignored
```

Expected: normal status shows only intended committed or staged source changes before commit. Ignored caches such as `.pytest_cache`, `.ruff_cache`, `.venv`, `.codex/handoffs/`, and `.codex/plugin-runtimes/` may exist; do not stage ignored runtime or handoff artifacts.

- [ ] **Step 6: Commit final verification-only doc adjustments if needed**

If verification required only wording or test-selector corrections, commit them:

```bash
git add docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration.md
git commit -m "docs(ticket): close candidate contract migration plan"
```

Expected: commit succeeds only if this plan changed during execution. If no plan changes occurred, do not create an empty commit.

## Acceptance Criteria

- `CandidateMutation` uses only the target envelope fields: `action`,
  `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and
  `evidence_summary`.
- Unknown or missing top-level candidate keys are rejected before mutation
  evaluation and surface through the outer apply-turn/CLI `invalid_candidate`
  host state or through discussion-required handling. Malformed explicit entries
  under `candidate_mutations`, `update_candidates`, or `capture_candidates` must
  not be silently dropped into `no_change`.
- Wrong-type `ticket_id`, `expected_ticket_fingerprint`, `action`, and
  `evidence_summary` mapping values are rejected before mutation evaluation; no
  invalid non-string value is coerced to `None` or `""`, and wrong-type explicit
  candidate entries also surface through the outer apply-turn/CLI
  `invalid_candidate` host state or through discussion-required handling.
- The target mutation result envelope itself does not gain `invalid_candidate`;
  target result vocabulary remains `ok`, `blocked`, `needs_discussion`,
  `invalid_state`, and `no_change`.
- `conflict_reason` is not accepted as target candidate input and does not enter
  target candidate identity, gateway validation, result data, or operation-log
  details.
- `target` has exactly `fields` and `sections`, at least one named field or
  section, and `proposed_change` keys exactly equal their union.
- `target.fields` and `target.sections` reject duplicate names and reject overlap
  between field and section names; `target.sections` also rejects names that
  fail `validate_target_section_name()` before runtime decisions or mutation IDs.
- Mutation identity and gateway decision validation canonicalize target name
  ordering so equivalent target envelopes do not produce different mutation IDs
  or target mismatches solely from caller order.
- Non-create writes require `expected_ticket_fingerprint`; create requires it to
  be `None`.
- Mutation identity includes `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
- For non-create writes, `expected_ticket_fingerprint` is the candidate-supplied
  copy of the live target fingerprint at discovery/evaluation time. It
  participates in candidate identity and is also the pre-write TOCTOU guard; the
  gateway recomputes the current live target fingerprint before writing and
  rejects stale candidates whose current fingerprint no longer matches.
- Discovery emits only explicit target-shaped candidates, does not turn
  vague/path-only signals into write candidates, and does not collapse distinct
  candidates that share one `ticket_id`, `action`, and `evidence_summary`.
- `ticket_autonomy.py` constructs target-shaped `GatewayMutation` values from
  `decision.candidate` and does not repopulate expected fingerprints through
  `source_context`.
- `ticket_autonomy.py` still runs a source-context health pass before apply-turn
  mutation evaluation and still pauses with `source_context_unhealthy` for
  malformed active ticket files; only the hidden fingerprint injection into
  runtime identity is removed.
- Gateway mutation validation compares target, proposed change, expected fingerprint, evidence summary, and mutation identity.
- Gateway validation preserves `mutation_id_required`, `ticket_mismatch`, and
  `mutation_id_mismatch` guards.
- Create allocation is serialized across distinct create candidates for the same
  ticket directory before selecting the next ID.
- Create retry reuses the retained canonical candidate identity to allocated
  ticket ID/path binding while that binding exists; a crash after the create file
  write but before `ticket_written` does not create a second ticket.
- Create recovery records completion from an occupied allocated path only when
  the current content-only post-write recovery fingerprint matches the retained
  `expected_post_write_fingerprint`; mismatched content pauses instead of being
  blessed as applied.
- Create target-section projection supports every source-rendered create section
  or narrows the source docs/skills in the same commit.
- Exact target sections can be updated or removed without caller-owned
  `Change History` rewrites; structured target sections such as
  `Acceptance Criteria` and `Key Files` render canonically or are rejected before
  write, never serialized through Python `repr`.
- `reopen` uses target `status` plus `evidence_summary`; `reopen_reason` is rejected as normal target write input.
- `reopen -> blocked` writes valid `Blocked On` and `blocked_by` shape.
- `reopen -> open` rejects `blocked_by`, `Blocked On`, and other blocked-only
  target content before render-time cleanup can hide the mismatch.
- Blocked-to-open update/correct candidates feed target-section
  `Blocked On: None` into the update policy as `blocked_on: null` before transition
  validation, active unblocking candidates name `Next Action` unless the
  authority docs are narrowed in the same commit, and missing `Next Action` is
  rejected before write.
- Current-facing docs and `test_docs_contract.py` agree that terminal tickets
  may reopen to `open` or `blocked`; no `ticket-contract.md` lifecycle assertion
  remains pinned to reopen only to `open`.
- Blocked `done`/`wontfix` candidates name `status`, `blocked_by`, and
  `Blocked On` cleanup, and the gateway does not silently drop the named
  cleanup section. Status-only close candidates for currently blocked tickets
  are rejected before `_execute_close()` can clear `blocked_by` or remove
  `Blocked On`.
- `correct` is an ordinary target-shaped mutation and appends generated
  correction history. Active current tickets corrected to `open` or `blocked`
  dispatch through update semantics; only terminal current tickets corrected to
  `open` or `blocked` dispatch through reopen semantics.
- `correct` requires recent correction context from private pending-summary or
  source-context state outside the candidate envelope. `evidence_summary` is not
  an authorization fact; without uncompacted recent correction context matching
  the current correction target, proposed change, and
  `expected_ticket_fingerprint`, with a retained source mutation ID and parseable
  fresh timestamp, runtime returns
  `correction_detail_missing` and does not emit
  `RuntimeDecisionKind.APPLY_CORRECTION`. Runtime correction authorization
  rejects expired, unparseable, and compacted contexts inside
  `evaluate_autonomy_intent()` itself and compares target fields/sections as
  canonical unordered sets.
- The May 30 control doc, current-facing ticket contract, and
  `test_docs_contract.py` agree on non-create identity wording and the deliberate
  `correct` authorization tightening before docs-contract PASS.
- Operation-log details retain only bounded recovery facts and do not add
  semantic ranking, current-mode labels, evidence taxonomies, runtime decision
  kinds, approval state, or private workflow stages. Non-create attempts retain
  the expected pre-write fingerprint, expected post-write recovery fingerprint,
  and exact generated `Change History` metadata before the file write starts.
  For create attempts, the bounded recovery facts may include only
  `create_allocation` with
  `allocated_ticket_id`, `allocated_ticket_path`, and
  `expected_pre_write_fact`, plus the same expected post-write recovery
  fingerprint and generated history metadata after allocation.
- Post-write recovery fingerprint comparisons use content-only target recovery
  fingerprints. The mtime-sensitive `target_fingerprint()` remains only the
  pre-write TOCTOU guard for `expected_ticket_fingerprint`.
- A non-create crash after file write but before `ticket_written` appends the
  missing `mutation_status`/`ticket_written` and `applied` events when the
  current post-write recovery fingerprint matches the retained
  `expected_post_write_fingerprint`.
- A prior-turn create crash after file write but before `ticket_written` projects
  recovery from retained `create_allocation.allocated_ticket_path`: matching
  content-only post-write fingerprint is repairable, mismatched occupied content
  pauses for reconciliation, and an unused allocation path does not allocate a
  fresh ticket without the same current candidate retry.
- Task 5 non-create recovery changes preserve Task 3A retained-create recovery:
  retained create retries reuse recorded allocation, expected post-write
  fingerprint, and generated `Change History` metadata instead of rebuilding
  those facts from the current clock or current candidate facts.
- `ticket_turn_batch.py` validates the six target actions for retained
  candidate action facts on `mutation_attempt` and
  `mutation_status`/`ticket_written` boundaries and keeps maintenance event
  actions only in event-specific validation.
- The final residue check has no unexplained target-candidate hits for old
  identity, evidence, action, correction, reopen, or gateway field names.
- The final residue check has no `ticket_write` reference that treats it as an
  existing operation-log event type.
- The final construction-site check has no old-shaped `CandidateMutation(...)`
  or `GatewayMutation(...)` calls in scripts or tests.
- Source docs, manifest-linked terms, skills, and plugin manifest stop claiming
  source entrypoint absence or ongoing source rebaseline after the source
  entrypoint lands, while preserving the source-vs-installed-runtime proof
  boundary.
- Focused candidate-contract tests, full Ticket suite, ruff, and `git diff --check` pass.

## Out Of Scope

- Installed runtime refresh, cache mutation, or app-server runtime proof.
- `reconcile_board` discovery ordering, caps, overflow, broad ticket search, or wrapper implementation.
- Broad `docs/tickets/` normalization. The current inventory is clean; any future dirty active ticket state gets a separate diagnostic/data migration lane.
- Historical spec example cleanup for old illustrative IDs unless a docs-contract test proves those examples now mislead current behavior.
- Private operation-log redesign beyond candidate identity, expected pre-write
  fingerprint, retained create allocation binding, content-only post-write
  recovery fingerprint, exact generated `Change History` metadata, evidence
  summary, target fields/sections, and write/summary completion facts.

## Execution Handoff

Plan authoring is complete when this file is committed or intentionally left
unstaged for review. Implementation is complete only after Tasks 0-7 finish,
their required commits exist, and the acceptance criteria plus final verification
commands are satisfied from the current checkout.

Primary implementation mode: sequential inline execution using
`superpowers:executing-plans`, with checkpoints after each task commit and after
the internal Task 1/2 test gate. Do not dispatch one primary worker per task:
Tasks 1-3 form the first runnable source commit group, Task 3A depends on Task
3, Task 5 depends on Task 3A recovery facts, and Task 6 depends on Tasks 3, 3A,
and 5.

Optional helpers: subagents may be used only for bounded read-only reviews,
grep/probe summaries, or isolated snippet sanity checks after the active
sequential worker has defined the exact question and file scope.

Do not start source edits from this plan without a fresh `git status --short --branch` and `git rev-parse --short HEAD` check.

`Expected:` blocks describe the observable state after completing the named
task. RED expectations must be reproduced before the corresponding GREEN patch.
GREEN expectations must be backed by command output from the current checkout;
do not carry aspirational expected output forward after live code contradicts
it.
