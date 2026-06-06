# Ticket Candidate Source Entrypoint Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the target candidate envelope through runtime shape, discovery, identity, gateway projection, engine projection, and the live `apply-turn` source entrypoint.

**Architecture:** This slice establishes the first runnable target-candidate source boundary. Tasks 1 and 2 are internal focused-green checkpoints only; Task 3 commits them together with gateway, engine, and apply-turn construction-site migration.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Parent And Successor Gates

- Parent index: `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md`.
- Superseded source material: `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration.md`.
- Starts after a fresh source status, ticket inventory, and coverage map.
- Ends after Task 3 commit: `fix(ticket): migrate target candidates through source entrypoints`.
- Hands off to `docs/superpowers/plans/2026-06-05-ticket-create-idempotency-binding.md` with create idempotency, reopen semantics, correction/recovery, docs availability, and final verification still pending.

## Slice Scope

This plan owns Tasks 0-3 from the superseded monolith. Do not update source-availability docs in this slice.

## Contract Decisions

- Preserve the target shape and section plumbing needed by later reopen work.
  Full reopen lifecycle semantics, including `reopen -> blocked`,
  `reopen_reason` removal, and normal `Reopen History` removal, land in
  `docs/superpowers/plans/2026-06-05-ticket-reopen-blocked-cleanup-semantics.md`.
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

## Slice Handoff

After Task 3, record the focused test output and commit hash in the implementation notes. Do not claim full Ticket suite green or source availability; those are later child-plan gates.
