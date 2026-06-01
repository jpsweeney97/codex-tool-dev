# Ticket Runtime-First Modes And Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove durable `preview` mode and automatic `agent_primary` approval-envelope machinery from Ticket source while keeping deterministic gateway write safety and the minimum target-fingerprint binding needed for non-create writes.

**Architecture:** This is a narrow modes/approval source slice selected from the Ticket source-runtime drift ledger. It is not the ledger's complete recommended first runtime cut because end-to-end `ticket_change_scope` removal is intentionally deferred. While scope remains live, this slice must preserve its existing write-safety binding. Mutation identity must also include the Ticket-derived expected target fingerprint for non-create writes; removing approval envelopes cannot drop that target-state binding. A missing target fingerprint is a deterministic write-authority block, not a user-discussion state: runtime must report `ticket_update_blocked`, apply other candidates whose write authority is valid, and keep that blocked candidate turn-local. It must not append `autonomy_health`, mutation, recovery, or other private-log events for the blocked candidate. A collector-level fingerprint failure is different: apply-turn must pause autonomy with `source_context_unhealthy`, not `setup_required`, and normal future turns must not silently clear that pause. Promote mutation identity calculation to a neutral helper in this slice so runtime decision construction and gateway validation share the same deterministic identity function without private runtime imports. This slice changes the local mode model, runtime evaluator, pending-summary validation, gateway validation, apply-turn projection, and integration expectations together so one producer is not removed while consumers still require it. Runtime approval removal, gateway decision validation, pending-summary approval/preview deletion, and all gateway event-sequence rewrites are one atomic behavior boundary; do not commit a checkpoint where runtime no longer emits approvals while gateway or pending-summary still requires them. Diagnostic dry-run remains a future explicit maintenance affordance; this slice removes durable/product `preview` but does not implement or replace the target diagnostic dry-run path.

**Tech Stack:** Python >=3.11, pytest, dataclasses, strict JSON, append-only JSONL, existing Ticket scripts, bytecode-safe `uv run` verification.

---

## Scope Check

The drift ledger names six areas: `preview`, approval envelopes, `ticket_change_scope`, prepare/execute wrappers, pending-summary taxonomy, and `blocks`. This plan intentionally covers one coherent implementation slice: durable mode cleanup plus removal of automatic approvals from `agent_primary`.

Out of scope for this plan:

- End-to-end `ticket_change_scope` removal from candidate identity, discovery, gateway fingerprints, autonomous apply, and commit disposition.
- Prepare/execute wrapper demotion in `ticket_capture.py` and `ticket_update.py`.
- Full pending-summary taxonomy collapse beyond removing new `preview_only` and automatic-approval requirements.
- Persisted `blocks` removal and reverse-blocker derived views.
- Repeat-block tracking, `autonomy_health`, and automatic maintenance-ticket escalation for recurring target-fingerprint blocks.
- Installed cache refresh, `hooks/list`, `skills/list`, `plugin/read`, or other runtime inventory.

Write separate plans for those surfaces. Do not fold them into this slice unless this plan is explicitly revised.

This is a breaking-change source slice. It does not preserve removed Ticket behavior for compatibility. Current local verification found no project-local pending-summary logs in this checkout, so this slice deletes executable `approval_consumed` validation/recovery support instead of retaining a historical compatibility reader.

Still in scope for this slice:

- Gateway validation must reject mismatches between `decision.candidate.ticket_change_scope` and `GatewayMutation.ticket_change_scope` while scope remains live. Removing approval envelopes cannot also remove that binding.
- Mutation identity must bind the expected target fingerprint for non-create writes. Runtime decision construction may derive that fingerprint from Ticket-owned source context, and gateway validation must recompute identity with `GatewayMutation.target_fingerprint`. `create` candidates intentionally use `target_fingerprint=None` in the canonical identity payload; every non-create action must fail closed before runtime mutation ID creation and before gateway dispatch when the Ticket-derived target fingerprint is missing or mismatched.
- New autonomous gateway attempts must not accept, write, validate, recover, or branch on approval-shaped authorization fields such as `approval`, `approval_id`, `approval_consumed`, `details.approval`, `codex.ticket.approval`, or `make_approval_id`.
- Missing Ticket-derived target fingerprints must produce a turn-local `ticket_update_blocked` result for that candidate, not `discussion_required`. The apply-turn path must still apply other valid candidates in the same batch and report a partial result when both applied and blocked candidates exist.
- Partial-result user output must stay concise: applied ticket IDs, skipped ticket IDs, blocked ticket IDs, and blocker reasons such as `target_fingerprint_required`. Do not include proposed fields, fingerprints, mutation IDs, event IDs, health-event internals, or maintenance-ticket IDs in the end-of-turn report for this slice.
- A globally unhealthy fingerprint collector must pause Ticket autonomy with `pause_reason: "source_context_unhealthy"`. Classify by collector trust, not candidate count: explicit per-ticket misses from a trustworthy collection are per-candidate `ticket_update_blocked` results, while I/O errors, parse failures, lock or health failures, ambiguous ticket roots, or any inability to prove a complete map for the attempted candidate set are collector-level failures. Resume must be explicit and must prove source-context collection by rerunning the collector against the current candidate set or a fail-closed known-ticket probe before clearing the pause. The live pause authority is the workspace `pause.json` marker; do not add a one-off pending-summary `automation_pause` event unless implementation first proves runtime pauses are already recorded that way consistently.
- Existing mode snapshots that contain removed durable modes such as `preview` must fail closed with setup required. They must not be treated as missing snapshots and replaced from `agent_primary` config.

Known remaining product drift after this slice:

- `ticket_change_scope` remains live and still influences commit-disposition behavior. Gateway validation must temporarily bind candidate scope to gateway mutation scope. The closeout must name this as remaining drift, not as target compliance.
- Deferred diagnostic-preview affordance: diagnostic dry-run/preview remains unavailable after this slice. This slice must not add a replacement dry-run flag, command, event, or renamed preview path. The closeout must say durable preview is removed, diagnostic dry-run remains unimplemented, and diagnostic preview is intentionally deferred to a later maintenance/design slice.
- The full target candidate mutation contract remains drift. This slice only preserves and adds the narrower target-fingerprint identity binding; it does not make live `CandidateMutation` match the full `target.fields`, `target.sections`, `expected_ticket_fingerprint`, and `evidence_summary` contract shape.
- Private operation-log collapse remains drift, but approval-state validation/recovery support is removed now because no local pending-summary logs exist in this checkout.
- Repeat-block-to-maintenance-ticket escalation is split out. A separate design/control plan must authorize any future recurrence tracking, private-log bridge event, or automatic maintenance-ticket creation.

## Authority And Current Source Facts

Source authority:

- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` says durable modes are exactly `agent_primary` and `discussion_only`, and `preview` is diagnostic only.
- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` removes automatic approval objects from `agent_primary`; explicit approval survives only for `discussion_only` follow-up.
- `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md` says hard stops include no persistent `preview` mode and no approval state in the private operation log.
- `docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md` is a source-only classification and inventory input, not runtime proof.

Contract impact:

- `plugins/turbo-mode/ticket/references/ticket-contract.md:172-184` already states the target durable modes and diagnostic-preview boundary. No mode contract patch is expected for this slice unless execution finds conflicting language.
- `plugins/turbo-mode/ticket/references/ticket-contract.md:34-45` states the fuller target candidate mutation shape. Treat that as known remaining drift for this slice, not as a stop condition, unless it contradicts the narrower target-fingerprint identity binding this plan implements.
- `plugins/turbo-mode/ticket/references/ticket-contract.md:186-190` states Ticket owns candidate identity and callers do not supply authoritative identity values. This slice preserves that by computing mutation ID from canonical decision candidate content plus the Ticket-derived expected target fingerprint, then recomputing that ID in gateway validation with `GatewayMutation.target_fingerprint`. While `ticket_change_scope` remains live, gateway validation also temporarily binds candidate scope to gateway mutation scope.
- No contract patch is expected before source edits. If implementation finds conflicting contract text for approval envelopes, diagnostic preview, or scope binding, stop and patch this plan plus the contract before continuing.

Current source touchpoints for this slice:

| Surface | Current drift |
|---|---|
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:29-34` | `AutomationMode.PREVIEW` is a durable config mode. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:317-424` | Invalid mode snapshots return `None`, so stale `preview` snapshots can fall through to fresh config resolution. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_config.py:102-108` | Tests assert manual durable preview config is valid. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:22-27` | `RuntimeDecisionKind.PREVIEW_ONLY` is a runtime decision kind. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:339-356` | `_mutation_id_for_candidate()` does not include the expected target fingerprint in mutation identity. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:162-202` | `_make_approval()` creates automatic approval envelopes. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:479-488` | Runtime evaluator emits `PREVIEW_ONLY` for current mode `preview`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:531-550` | Runtime evaluator attaches approval envelopes to `APPLY_AUTONOMOUSLY`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:530-550` | Runtime evaluator does not yet distinguish missing target fingerprints as `ticket_update_blocked` instead of discussion. |
| `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:154-188` | Gateway rejects autonomous writes without approval envelopes. |
| `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:619-645` | Gateway writes approval details and `approval_consumed` events. |
| `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:85-95` | Pending-summary accepts `preview_only` and `preview` as durable taxonomy. |
| `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:292-298` | Pending-summary requires `details.approval` for `apply_autonomously`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:273-286` | Apply-turn projects `preview` as a product state. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:185-199` | Paused output has no `source_context_unhealthy` message. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:419-431` | `_ticket_state_fingerprints()` cannot distinguish per-candidate misses from collector-level failure. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:725-736` | Existing runtime pause command writes `pause.json` and paused output, not pending-summary `automation_pause` events. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:345-361` | Apply-turn writes `preview_only` non-write events. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:818-846` | `--resume-paused` clears pauses without proving source-context collection is healthy. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:821` | Apply-turn references `AutomationMode.PREVIEW.value` while validating `--setup-choice preview`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:970` | Apply-turn treats `PREVIEW_ONLY` decisions as skipped product output. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:434-459` | Apply-turn summary has no `Blocked` bucket or `partially_applied` / `ticket_update_blocked` states. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:434-459` | Apply-turn summary has no concise blocked-reason projection for partial results. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py:113-125` | Integration tests expect new successful writes to record `approval_consumed`. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py:197-204` | Integration tests still write durable `AutomationMode.PREVIEW` and expect product `preview` output. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py:257` | Integration tests expect gateway attempt details to contain an approval object. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py:41-52` | Correction integration helper builds decisions with empty source context, so target-fingerprint identity changes need a helper update before full-suite verification. |

## File Structure

Modify or add these files only in this plan:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py`
  - Owns strict local config modes and snapshots.
  - Remove durable `AutomationMode.PREVIEW`.
- `plugins/turbo-mode/ticket/tests/test_autonomy_config.py`
  - Covers config parsing, setup choices, pause/resume, and snapshots.
  - Rewrite preview config coverage to assert `preview` requires setup.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
  - Owns candidate decisions and runtime authorization policy.
  - Remove `PREVIEW_ONLY`, stop creating automatic approval envelopes, and call the shared mutation identity helper.
- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
  - Covers evaluator behavior.
  - Rewrite approval and preview expectations.
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
  - New neutral helper for canonical mutation identity calculation.
  - Keep it independent of runtime and gateway dataclasses; callers adapt their local types into primitive fields.
- `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
  - New focused tests for target-fingerprint and current `ticket_change_scope` identity binding.
- `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
  - Covers user-triggered correction decisions through the gateway.
  - Update correction helper source context so correction decisions include the Ticket-derived target fingerprint.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
  - Owns pending-summary event validation and recovery projection.
  - Remove `preview_only`, `current_mode: preview`, `details.approval`, `approval_consumed`, and `approval_id` from executable validation and recovery. Do not add `autonomy_health`, `ticket_update_blocked`, or any other blocked-candidate pending-summary event in this slice. Do not add `source_context_unhealthy` to pending-summary pause-reason validation unless a consistent runtime `automation_pause` event path is proven first.
- `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
  - Covers pending-summary schema and validation.
  - Rewrite valid attempt fixtures, neutralize approval-shaped helper defaults, and update preview/approval rejection tests.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
  - Owns deterministic autonomous write validation and event recording.
  - Replace approval-envelope validation with decision/mutation validation.
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
  - Covers gateway write safety, event sequences, and recovery.
  - Rewrite approval tests and remove new-event expectations for `approval_consumed`.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
  - Owns apply-turn CLI projection and pending-summary append calls.
  - Remove product `preview` projection and `PREVIEW_ONLY` handling. Add blocked-ticket summary buckets, partial-apply projection, source-context-unhealthy pause handling, and explicit resume proof. Do not write private blocked-candidate events or maintenance tickets in this slice.
- `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
  - Covers apply-turn CLI behavior and recovery.
  - Rewrite preview setup-choice messaging, event sequences, and blocked-ticket summary behavior.
- `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
  - Covers end-to-end apply-turn orchestration.
  - Rewrite success event sequences, durable preview expectations, approval-residue assertions, and partial apply with blocked candidates.
- `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
  - Covers pending-summary recovery projection.
  - Remove `approval_consumed` recovery fixtures and keep approval-free `ticket_written` recovery coverage. Delete (do not re-fixture) the post-write `approval_consumed` recovery test, whose projection state is unreachable after removal; correct the `_event_with_bound_fingerprints` helper (real name) by name. See the Consumer Inventory section.
- `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py`
  - Covers deterministic ID helpers (`make_mutation_id`, `make_event_id`, `make_approval_id`, `sha256_fingerprint`).
  - Deleting `make_approval_id` from source breaks this file's import at collection. Remove `make_approval_id` from the import, delete the two pure-approval tests, surgically edit the two mixed ID tests, and keep all mutation/event/fingerprint coverage. See the Consumer Inventory section. Add this file to Task 3's edits, the Task 5 commit, and every later selector/ruff list.

Do not modify docs, plugin manifests, cache files, or installed runtime state in this implementation slice unless Task 0's contract-impact checkpoint finds conflicting contract text. If that happens, stop and revise this plan first, then patch the contract deliberately.

## Removed-Machinery Consumer Inventory (Authoritative Affected-File Set)

The per-task `Files`, `git add`, selector, and ruff lists below were derived from a source-drift table that under-sampled **test** consumers. This section is the single source of truth for which files every removal touches. **Run the inventory grep before editing and assign every hit to the task boundary that owns that removal; then fold that file into the boundary's edits, staging, selector, and ruff list.** If a per-task list below omits a file named here that the task actually touches, this section governs and the per-task list must be widened to match.

Run before Task 1:

```bash
rg -n 'make_approval_id|codex\.ticket\.approval|decision\.approval|approval_consumed|approval_id|details\.approval|details\["approval"\]|AutomationMode\.PREVIEW|RuntimeDecisionKind\.PREVIEW_ONLY|preview_only|PREVIEW_ONLY|\bPREVIEW\s*=\s*"preview"|current_mode\s*==\s*"preview"|mode="preview"|"mode"\s*:\s*"preview"|"current_mode"\s*:\s*"preview"|_MODES.*"preview"|\["state"\]\s*==\s*"preview"|"state"\s*:\s*"preview"' plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Authoritative affected-file set (every file with a real hit must be assigned to the correct behavior boundary and every later verification selector; approval/gateway/pending-summary consumers must be in the atomic approval-boundary commit):

- Scripts: `ticket_autonomy_config.py`, `ticket_autonomy_runtime.py`, `ticket_autonomy_ids.py`, `ticket_mutation_identity.py` (new), `ticket_turn_batch.py`, `ticket_engine_gateway.py`, `ticket_autonomy.py`.
- Tests: `test_autonomy_config.py`, `test_autonomy_runtime.py`, `test_mutation_identity.py` (new), `test_autonomy_corrections.py`, `test_turn_batch.py`, `test_engine_gateway.py`, `test_autonomy_cli.py`, `test_autonomy_integration_v1.py`, `test_autonomy_recovery.py`, **`test_autonomy_ids.py`** (omitted by every per-task list in the original draft — see below).

Do not use a bare `"preview"` grep for this inventory. Ticket capture/update/workflow commands still have non-autonomy preview payloads outside this slice; those are not durable `AutomationMode.PREVIEW`, runtime `PREVIEW_ONLY`, pending-summary `preview_only`, or apply-turn product preview consumers. If a broader grep finds those unrelated surfaces, classify them as out of scope instead of widening this source slice.

Non-obvious per-file rewrites the grep will surface as sites but will not tell you how to fix. These are the judgment calls; a literal find-and-delete breaks the suite:

- **`test_autonomy_ids.py` (entirely unlisted in the original draft).** Imports `make_approval_id` (line 14) and exercises it. Deleting `make_approval_id` from source raises `ImportError` at collection, taking the whole suite red at the first unfiltered run. Remove `make_approval_id` from the import block (keep `canonical_json`, `make_event_id`, `make_mutation_id`, `sha256_fingerprint`). Delete the two pure-approval tests (`test_approval_id_uses_expected_prefix_and_digest` ~100-116; `test_approval_id_changes_when_inputs_change` ~188-215). **Surgically** edit the two mixed tests — `test_thread_id_scopes_ids_even_when_turn_id_matches` (drop the `approval_common` dict and the final `make_approval_id` assertion; keep the mutation/event halves) and `test_timestamp_is_not_an_id_input` (drop `make_approval_id` from the `(make_mutation_id, make_event_id, make_approval_id)` tuple). Delete every `codex.ticket.approval.v1` literal (lines 102/203/240). Keep all `make_mutation_id`/`make_event_id`/`sha256_fingerprint` coverage.
- **`test_autonomy_corrections.py:108`** asserts `decision.approval is None` — **outside** the plan's cited 41-80 range. After the slots-field deletion this raises `AttributeError`, not `None`. Delete line 108. Line 115 (`"approval" not in events[0]["details"]`) is a valid negative fixture and stays.
- **Recovery fingerprint helper name.** Task 6 Step 2's "apply the same rewrite in `test_autonomy_recovery.py`" is wrong on the name: the real helper is `_event_with_bound_fingerprints(event, *, pre="pre-fp", post="post-fp")`. Keep the real name **and** its defaults (no call site passes `pre=`/`post=`) and its `isinstance(approval, Mapping)` shape before stripping the approval branch.
- **`test_autonomy_recovery.py` is not "remove fixtures."** `project_mutation_recovery`'s `append_missing_ticket_written` post-write jump is gated **exclusively** on `state == "approval_consumed"` (ticket_turn_batch.py ~915), so after removal that recovery state is **unreachable** — the post-write `approval_consumed` test must be **deleted**, not re-fixtured. Strip the embedded `approval_consumed` step from the retained Step-8 test (`test_ticket_written_without_terminal_status_appends_outcome`) and the two derive-ladder tests. After edits, re-run ruff: confirm no now-unused imports (e.g. `from collections.abc import Mapping`) trigger F401.
- **`test_autonomy_cli.py` doctor-ledger contradiction.** `test_doctor_ledger_repairs_deterministic_recovery_gaps` (~1050-1056) asserts the repaired sequence **still contains** `approval_consumed`; rewrite that expected list (and the `evt_prior_approval` event_id assertion ~442-445). These corrected sequences are valid **only after** the Task 5 source change moves the `append_missing_ticket_written` repair from the `approval_consumed` state to `attempt_recorded` — they cannot be validated by editing the test file alone, so they belong in the atomic boundary. Keep the `consume-approval` CLI negative fixture (~947).
- **`test_engine_gateway.py` recovery test (~628-693) is unnamed by the draft.** Delete its `approval_consumed` seed (~659-673) and drop `approval_consumed` from the expected recovery list (~685-693), then re-confirm `recovery_state == "append_missing_ticket_written"` against the changed `project_mutation_recovery`. The new decision-validation test needs `from dataclasses import replace` (not currently imported).
- **`test_autonomy_integration_v1.py` reindex hazard (most likely missed break).** Dropping `approval_consumed` collapses the success sequence from 4 events to 3, so the index-based assertions `events[3]→events[2]` (~119-125) must be reindexed or they `IndexError`/assert the wrong event. Keep the line-11 `AutomationMode` import and the line-176 negative approval fixture (both stay valid).
- **Two distinct `_expected_pre_write_fingerprint` functions.** Besides the gateway one in Task 4 Step 4 (`*, mutation, decision`), `ticket_turn_batch.py` has a **module-level** `_expected_pre_write_fingerprint(events, ...)` (~753-763) that reads `details["approval"]["ticket_state_fingerprint"]`. Remove the approval branch from **both**. The `from collections.abc import Mapping` import in `ticket_turn_batch.py` **stays** (still used by other signatures). In `test_turn_batch.py`, the `without_detail` helper becomes unused once the approval row is deleted — flag, do not silently delete unless unused-symbol cleanup is in scope.

## Stop Conditions

Stop before source edits if:

- `git status --short --branch` shows unrelated tracked changes in any file this plan touches.
- `docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md` has changed since this plan was written and now recommends a different first source slice.
- The implementation branch lacks ADR 0006 and the May 30 control doc.
- A change would mutate `/Users/jp/.codex/plugins/cache`, `.codex/ticket-workspace/`, `.codex/ticket.local.md`, or installed runtime state.

Stop during implementation if:

- A gateway write can proceed without a mutation ID, expected target fingerprint for non-create writes, or deterministic candidate/mutation match.
- A `create` candidate is blocked only because `target_fingerprint` is `None`.
- A non-create candidate receives a runtime mutation ID or passes gateway validation without a Ticket-derived target fingerprint.
- A new autonomous gateway attempt accepts, ignores, consumes, serializes, or authorizes from approval-shaped fields such as `approval`, `approval_id`, or `details.approval` instead of rejecting them.
- Gateway validation accepts a mutation ID that does not match the ID recomputed from `thread_id`, `turn_id`, `decision.candidate`, and `GatewayMutation.target_fingerprint`.
- Gateway validation accepts a decision candidate whose `ticket_change_scope` differs from `GatewayMutation.ticket_change_scope` while scope remains live.
- Runtime mode resolution treats an existing invalid mode snapshot as missing and falls back to `agent_primary` config.
- Runtime classifies `target_fingerprint_required` as `discussion_required` or emits a discussion question for it.
- A missing target fingerprint for one candidate prevents other candidates with valid write authority from applying in the same turn.
- A blocked target-fingerprint candidate writes a `mutation_attempt`, `mutation_status`, mutation ID, proposed fields, gateway fingerprint, approval detail, preview payload, or second matching `autonomy_health` event.
- A partial-result response exposes proposed fields, fingerprints, mutation IDs, event IDs, health-event internals, or maintenance-ticket IDs instead of only ticket IDs and blocker reasons.
- A blocked target-fingerprint candidate appends `autonomy_health`, `ticket_update_blocked`, or any other private pending-summary event.
- This slice adds repeat-block tracking, automatic maintenance-ticket escalation, `MAINTENANCE_REPEAT_THRESHOLD`, `ticket_autonomy_maintenance.py`, or maintenance-ticket output fields.
- A collector-level fingerprint failure returns a normal turn-local blocked result instead of pausing with `source_context_unhealthy`.
- `--resume-paused` clears a `source_context_unhealthy` pause without rerunning and passing the source-context collector or the fail-closed known-ticket probe through the same collector path.
- `source_context_unhealthy` is reported as `setup_required` or reused for local config/mode setup failures.
- `source_context_unhealthy` adds a new pending-summary `automation_pause` write when runtime pauses are not otherwise recorded there consistently.
- Any pending-summary validation, recovery, fixture, or event write keeps accepting `details.approval`, `approval_id`, `approval_consumed`, `preview_only`, or `current_mode: preview`.
- Any implementation adds a replacement diagnostic dry-run flag, command, event, or renamed preview path in this slice.
- Any focused test requires preserving durable `preview` as a config mode to pass.
- Any focused test requires automatic `agent_primary` approvals to pass.

## Task 0: Preflight And Source-Boundary Check

**Files:**
- Read: `docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md`
- Read: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `plugins/turbo-mode/ticket/references/ticket-contract.md`

- [ ] **Step 1: Confirm branch and tracked status**

Run:

```bash
git status --short --branch
git rev-parse HEAD > /tmp/ticket-modes-approval-base.txt
```

Expected: branch is the intended implementation branch, no unrelated tracked changes appear in files named by this plan, and `/tmp/ticket-modes-approval-base.txt` contains the base commit for final diff review.

- [ ] **Step 2: Confirm this slice is still a valid narrowed ledger cut**

Run:

```bash
rg -n "preview|Approval envelopes|Recommended Next Steps|source-only" docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md
```

Expected: output still says the ledger is source-only and still names `preview` plus approval envelopes as drift needing source implementation. If the ledger now requires end-to-end `ticket_change_scope` removal before approval-envelope work, stop and revise this plan instead of executing it mechanically.

- [ ] **Step 3: Confirm current source still has the drift this plan removes**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|approval_consumed|details\\.approval|approval_required|make_approval|codex\\.ticket\\.approval|decision\\.approval|approval_id" plugins/turbo-mode/ticket/scripts
```

Expected before implementation: matches in `ticket_autonomy_config.py`, `ticket_autonomy_runtime.py`, `ticket_autonomy.py`, `ticket_engine_gateway.py`, `ticket_turn_batch.py`, and `ticket_autonomy_ids.py`. `ticket_autonomy_ids.py` may still define `make_approval_id`; this slice deletes it instead of preserving unused approval-envelope scaffolding.

- [ ] **Step 4: Confirm focused tests currently encode old behavior**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|\\\"preview\\\"|approval_consumed|decision\\.approval|details\\[\\\"approval\\\"\\]" plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
```

Expected before implementation: matches in the focused tests named by this plan.

- [ ] **Step 5: Confirm contract impact before source edits**

Run:

```bash
rg -n "Autonomy Model|Fingerprints And Write Safety|preview|approval|ticket_change_scope|expected_ticket_fingerprint|target fingerprint|candidate identity|authoritative identity" plugins/turbo-mode/ticket/references/ticket-contract.md
```

Expected: `ticket-contract.md` already matches the target durable-mode and target-fingerprint identity boundary and does not require a source-contract patch for this slice. Record that `plugins/turbo-mode/ticket/references/ticket-contract.md:172-190` remains the governing contract section for this slice. If the search also finds `plugins/turbo-mode/ticket/references/ticket-contract.md:34-45`, record it as known remaining target candidate-shape drift, not as a stop condition. Stop only if contract text conflicts with approval-envelope removal, durable-preview removal, target-fingerprint identity binding, or temporary scope binding.

- [ ] **Step 6: Confirm no local pending-summary logs need recovery compatibility**

Run:

```bash
find .codex -path '*/ticket.pending-summary.jsonl' -print
find .codex -path '*/ticket-workspace' -print
```

Expected before implementation: no output. If any current project-local pending-summary log exists, stop and decide whether to migrate it or retain a bounded reader before deleting `approval_consumed` validation/recovery. Historical handoff text does not count as a pending-summary log.

## Task 1: Remove Durable `preview` From Local Config

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:29-34`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_config.py:29-108`

- [ ] **Step 1: Write the failing config tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_config.py`, add this import:

```python
import json
```

Replace the mode parametrization and preview tests with this code:

```python
DURABLE_MODES = (
    AutomationMode.DISCUSSION_ONLY,
    AutomationMode.AGENT_PRIMARY,
)


@pytest.mark.parametrize("mode", DURABLE_MODES)
def test_valid_strict_json_config(tmp_path: Path, mode: AutomationMode) -> None:
    write_local_config(tmp_path, mode)

    result = read_local_config(tmp_path)

    assert result.state == LocalConfigState.VALID
    assert result.mode == mode
    assert result.reason is None
    assert result.path.read_text(encoding="utf-8") == (
        f'{{"schema":"codex.ticket.local.v1","mode":"{mode.value}"}}\n'
    )
```

Replace `test_preview_is_manual_only_config_mode` with:

```python
def test_preview_config_requires_setup(tmp_path: Path) -> None:
    path = tmp_path / ".codex" / "ticket.local.md"
    path.parent.mkdir()
    path.write_text(
        '{"schema":"codex.ticket.local.v1","mode":"preview"}\n',
        encoding="utf-8",
    )

    result = read_local_config(tmp_path)

    assert result.state == LocalConfigState.SETUP_REQUIRED
    assert result.mode is None
    assert result.reason == "invalid_mode"


def test_preview_mode_snapshot_requires_setup_instead_of_config_fallback(
    tmp_path: Path,
) -> None:
    _declare_workspace_ignored(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    snapshot_path = (
        tmp_path
        / ".codex"
        / "ticket-workspace"
        / "mode-snapshots"
        / f"{mode_snapshot_key(tmp_path, 'thread-1')}.json"
    )
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "schema": "codex.ticket.mode-snapshot.v1",
                "project_root": str(tmp_path.resolve(strict=False)),
                "thread_id": "thread-1",
                "mode": "preview",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    resolved = resolve_thread_mode(tmp_path, "thread-1")

    assert resolved.state == LocalConfigState.SETUP_REQUIRED
    assert resolved.mode is None
    assert resolved.source == "setup_required"
    assert resolved.path == snapshot_path
    assert resolved.reason == "invalid_snapshot_mode"
```

- [ ] **Step 2: Run the config tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py::test_preview_config_requires_setup tests/test_autonomy_config.py::test_preview_mode_snapshot_requires_setup_instead_of_config_fallback -q
```

Expected before implementation: FAIL because `preview` is still accepted as `AutomationMode.PREVIEW`, and a valid `preview` snapshot currently resolves as a writable snapshot instead of setup-required state.

- [ ] **Step 3: Remove `PREVIEW` from `AutomationMode`**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py`, replace the enum with:

```python
class AutomationMode(StrEnum):
    """Runtime-first automation modes for local Ticket setup."""

    DISCUSSION_ONLY = "discussion_only"
    AGENT_PRIMARY = "agent_primary"
```

Do not add a replacement enum member for diagnostic dry-run. Diagnostic dry-run is not durable config.

Then add an invalid-snapshot check before config fallback. Keep `read_mode_snapshot()` returning `ModeSnapshot | None` for callers that only need valid snapshots, but make `resolve_thread_mode()` distinguish a missing snapshot from a present invalid snapshot:

```python
def _mode_snapshot_error(project_root: Path, thread_id: str) -> tuple[Path, str] | None:
    if not thread_id.strip():
        return None
    path = _snapshot_path(project_root, thread_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, "invalid_snapshot"
    if not isinstance(data, dict):
        return path, "invalid_snapshot"
    if set(data) != {"schema", "project_root", "thread_id", "mode"}:
        return path, "invalid_snapshot"
    if data.get("schema") != MODE_SNAPSHOT_SCHEMA:
        return path, "invalid_snapshot"
    if data.get("project_root") != _normalized_project_root(project_root):
        return path, "invalid_snapshot"
    if data.get("thread_id") != thread_id:
        return path, "invalid_snapshot"
    if _parse_mode(data.get("mode")) is None:
        return path, "invalid_snapshot_mode"
    return None
```

In `resolve_thread_mode()`, call `_mode_snapshot_error()` after `read_mode_snapshot()` returns `None` and before `read_local_config()`. If it returns `(path, reason)`, return:

```python
        return ResolvedMode(
            LocalConfigState.SETUP_REQUIRED,
            None,
            "setup_required",
            path,
            reason,
        )
```

Do not silently delete, rewrite, or overwrite an invalid snapshot in this task. The setup/resume path already owns deliberate snapshot invalidation.

- [ ] **Step 4: Run focused config tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Keep durable-mode config cleanup uncommitted until Task 2**

Do not commit after Task 1. `AutomationMode.PREVIEW` still has live consumers in apply-turn until Task 2 removes runtime preview decisions and setup-choice handling. Leave the config changes in the working tree and continue directly to Task 2.

## Task 2: Remove Runtime `PREVIEW_ONLY` Decisions

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:20-27`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:470-488`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py:124-139`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:273-286`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:345-361`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:449-459`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:960-974`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py:843-866`

- [ ] **Step 1: Write the failing evaluator tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, replace `test_discussion_only_and_preview_modes_do_not_authorize_writes` with:

```python
def test_discussion_only_does_not_authorize_writes() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    discussion = _decisions(candidate, mode="discussion_only")[0]

    assert discussion.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert discussion.reason == "discussion_only"


def test_unsupported_preview_mode_requires_discussion_without_preview_decision() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate, mode="preview")[0]

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "unsupported_mode"
    assert decision.pending_summary_status == "discussion_required"
```

- [ ] **Step 2: Run the new evaluator test to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py::test_unsupported_preview_mode_requires_discussion_without_preview_decision -q
```

Expected before implementation: FAIL because `mode="preview"` returns `RuntimeDecisionKind.PREVIEW_ONLY`.

- [ ] **Step 3: Remove `PREVIEW_ONLY` from runtime decisions**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, replace `RuntimeDecisionKind` with:

```python
class RuntimeDecisionKind(StrEnum):
    """Runtime-first decision kinds."""

    APPLY_AUTONOMOUSLY = "apply_autonomously"
    APPLY_CORRECTION = "apply_correction"
    REQUIRE_USER_DISCUSSION = "require_user_discussion"
    SKIP_DUE_TO_CONFLICT = "skip_due_to_conflict"
    DEFER_UNTIL_RETRY_CONDITION = "defer_until_retry_condition"
    TICKET_UPDATE_BLOCKED = "ticket_update_blocked"
```

In `evaluate_autonomy_intent()`, replace the `current_mode == "preview"` branch with:

```python
        if current_mode != "agent_primary":
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
                    reason="unsupported_mode",
                    pending_summary_status="discussion_required",
                )
            )
            continue
```

This replacement belongs immediately after the existing `current_mode == "discussion_only"` branch.

- [ ] **Step 4: Remove apply-turn preview projection**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`, replace `_emit_mode_projection()` with:

```python
def _emit_mode_projection(mode: AutomationMode, context: dict[str, Any]) -> int:
    if not _has_candidate_changes(context) or mode == AutomationMode.AGENT_PRIMARY:
        _emit(_no_change_response())
        return 0
    _emit(
        {
            "state": "discussion_only",
            "changed": False,
            "ticket_updates": None,
            "discussion_question": "Ticket automation is set to ask before changing tickets.",
        }
    )
    return 0
```

In `_append_non_write_decision()`, remove the `RuntimeDecisionKind.PREVIEW_ONLY` branch and start the function with:

```python
    if decision.kind == RuntimeDecisionKind.SKIP_DUE_TO_CONFLICT:
        status = "skipped"
        details: dict[str, object] = {
            "decision": RuntimeDecisionKind.SKIP_DUE_TO_CONFLICT.value,
            "current_mode": current_mode.value,
            "evidence_kind": "runtime_context",
        }
        reason = decision.reason or "Skipped conflicting Ticket mutation."
    else:
        status = "discussion_required"
        details = {
            "decision": RuntimeDecisionKind.REQUIRE_USER_DISCUSSION.value,
            "current_mode": current_mode.value,
            "question": "Review the proposed Ticket update before applying it.",
            "evidence_kind": "runtime_context",
        }
        reason = decision.reason or "Ticket mutation requires discussion."
```

In `_summary_payload()`, preserve conflict skips as a real user-visible result and replace the final state selection with:

```python
    if applied:
        state = "applied"
    elif skipped:
        state = "skipped"
    elif discussion:
        state = "discussion_required"
    else:
        state = "no_change"
```

In the apply-turn decision loop, remove this branch:

```python
        elif decision.kind == RuntimeDecisionKind.PREVIEW_ONLY:
            skipped.append(ticket_id)
```

- [ ] **Step 5: Remove the setup-choice enum reference to preview**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`, replace the start of the setup-choice block with this code:

```python
    setup_choice_value = args.setup_choice
    if args.resume_paused and setup_choice_value is None:
        return _invalid_args("--resume-paused requires --setup-choice")
    if setup_choice_value is not None:
        try:
            setup_choice = SetupChoice(setup_choice_value)
        except ValueError:
            return _invalid_args("setup choice must be automatic or ask_first")
```

This deletes the `setup_choice_value == AutomationMode.PREVIEW.value` branch. After Task 1, `AutomationMode.PREVIEW` no longer exists, so this must be patched before running the CLI test in the next step.

- [ ] **Step 6: Update preview setup-choice CLI expectation**

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`, replace the expected message in `test_apply_turn_rejects_preview_setup_choice` with:

```python
    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "state": "invalid_args",
        "message": "setup choice must be automatic or ask_first",
    }
```

- [ ] **Step 7: Run focused runtime and CLI tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py::test_discussion_only_does_not_authorize_writes tests/test_autonomy_runtime.py::test_unsupported_preview_mode_requires_discussion_without_preview_decision tests/test_autonomy_cli.py::test_apply_turn_rejects_preview_setup_choice -q
```

Expected: PASS.

- [ ] **Step 8: Commit durable and runtime preview removal together**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py
git commit -m "fix(ticket): remove durable preview mode"
```

Expected: commit includes Task 1 config cleanup plus Task 2 runtime/apply-turn preview removal. Do not leave a commit where `AutomationMode.PREVIEW` is removed while apply-turn still references it.

## Task 3: Stop Creating Automatic `agent_primary` Approval Envelopes

**Files:**
- Add: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Add: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:1-202`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:390-445`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:525-550`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py:74-230`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py:41-80` (and delete the `assert decision.approval is None` at line 108 — outside this range but broken by the field deletion; see Consumer Inventory)
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py` (remove `make_approval_id` import + approval tests; surgically keep mutation/event/fingerprint coverage; see Consumer Inventory)

When this task deletes `make_approval_id` from `ticket_autonomy_ids.py`, `test_autonomy_ids.py` stops importing at collection. It must be edited in the same boundary, not discovered at final verification.

- [ ] **Step 1: Rewrite evaluator authorization tests and add identity-helper tests**

Create `plugins/turbo-mode/ticket/tests/test_mutation_identity.py` with focused calculation tests:

```python
from scripts.ticket_mutation_identity import make_candidate_mutation_identity


def _identity(
    *,
    target_fingerprint: str | None = "ticket-state-a",
    ticket_change_scope: str = "current_branch",
):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        proposed_change={"priority": "high"},
        ticket_change_scope=ticket_change_scope,
        target_fingerprint=target_fingerprint,
        evidence=(
            {"kind": "current_thread_reason", "ref": "test", "freshness": "fresh"},
        ),
    )


def test_target_fingerprint_binds_mutation_identity() -> None:
    first = _identity(target_fingerprint="ticket-state-a")
    second = _identity(target_fingerprint="ticket-state-b")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint
    assert first.evidence_fingerprint == second.evidence_fingerprint


def test_helper_hashes_missing_target_fingerprint_without_policy_decision() -> None:
    missing = _identity(target_fingerprint=None)
    present = _identity(target_fingerprint="ticket-state-a")

    assert missing.mutation_id != present.mutation_id
    assert missing.mutation_fingerprint != present.mutation_fingerprint


def test_ticket_change_scope_binds_identity_until_scope_slice() -> None:
    current_branch = _identity(ticket_change_scope="current_branch")
    unrelated_backlog = _identity(ticket_change_scope="unrelated_backlog")

    assert current_branch.mutation_id != unrelated_backlog.mutation_id
```

The helper test for missing target fingerprint must stay calculation-only. Runtime and gateway tests own the non-create hard stop. The `ticket_change_scope` test is intentionally temporary coverage for the existing live scope binding until the separate scope-removal slice.

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, change the loop assertion in `test_ordinary_candidates_apply_autonomously_with_agent_primary_and_evidence` to:

```python
        assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
        assert decision.mutation_id is not None
        assert decision.reason == "authorized"
```

Replace `test_approval_envelope_binds_decision_context_and_expires_within_ten_minutes` with:

```python
def test_agent_primary_decision_uses_mutation_id() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate)[0]

    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.mutation_id is not None
    assert decision.mutation_id.startswith("mut_")
    assert decision.engine_dispatch is not None
    assert decision.engine_dispatch.state == "ok"
    assert decision.reason == "authorized"
```

Add target-fingerprint identity coverage, and change `test_ticket_change_scope_binds_mutation_identity_and_approval_fingerprint` to:

```python
def test_target_fingerprint_binds_mutation_identity_for_non_create() -> None:
    candidate = _candidate("update")
    first = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-a"},
    )[0]
    second = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-b"},
    )[0]

    assert first.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert second.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert first.mutation_id != second.mutation_id


def test_non_create_candidate_requires_target_fingerprint_for_identity() -> None:
    decision = _decisions(
        _candidate("update"),
        ticket_state_fingerprints={},
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "target_fingerprint_required"
    assert decision.pending_summary_status == "ticket_update_blocked"
    assert decision.mutation_id is None


def test_correction_target_fingerprint_binds_mutation_identity() -> None:
    candidate = _candidate(
        "correction",
        proposed_change={"resolution": "done"},
        evidence=_evidence("correction_detail"),
    )
    first = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-a"},
    )[0]
    second = _decisions(
        candidate,
        ticket_state_fingerprints={candidate.ticket_id: "ticket-state-b"},
    )[0]

    assert first.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert second.kind == RuntimeDecisionKind.APPLY_CORRECTION
    assert first.mutation_id != second.mutation_id


def test_correction_requires_target_fingerprint_for_identity() -> None:
    decision = _decisions(
        _candidate(
            "correction",
            proposed_change={"resolution": "done"},
            evidence=_evidence("correction_detail"),
        ),
        ticket_state_fingerprints={},
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "target_fingerprint_required"
    assert decision.pending_summary_status == "ticket_update_blocked"
    assert decision.mutation_id is None


def test_ticket_change_scope_still_binds_mutation_identity_until_scope_slice() -> None:
    current_branch = _decisions(
        _candidate("update", ticket_change_scope="current_branch"),
    )[0]
    unrelated_backlog = _decisions(
        _candidate("update", ticket_change_scope="unrelated_backlog"),
    )[0]

    assert current_branch.mutation_id != unrelated_backlog.mutation_id
```

The renamed test is intentionally temporary: it documents that `ticket_change_scope` survives only until its separate removal slice.

In `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`, update `_correction_decision()` so correction integration tests pass the Ticket-derived target fingerprint through source context when a ticket path is available:

```python
def _correction_decision(candidate: CandidateMutation, *, ticket_path: Path | None = None):
    source_context: dict[str, object] = {}
    if ticket_path is not None and candidate.ticket_id is not None:
        source_context["ticket_state_fingerprints"] = {
            candidate.ticket_id: target_fingerprint(ticket_path)
        }
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="correct_ticket_mutation",
            candidates=(candidate,),
            source_context=source_context,
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime.now(UTC),
    )[0]
```

Then update `_apply_correction()` to pass the ticket path:

```python
    decision = _correction_decision(candidate, ticket_path=ticket_path)
```

Leave unsafe-correction and missing-detail tests without `ticket_path`; those branches must still fail before target-fingerprint identity is required.

- [ ] **Step 2: Add a tiny identity-helper stub, then run evaluator tests to verify behavioral failure**

Before running the RED tests, create the smallest importable stub at
`plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py` if the file does
not exist. The stub may define `CandidateMutationIdentity`,
`candidate_mutation_payload()`, and `make_candidate_mutation_identity()` with
placeholder behavior, but it must not satisfy the target identity tests. Do not
commit the stub by itself; it is part of the later approval-boundary commit.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_autonomy_runtime.py::test_agent_primary_decision_uses_mutation_id tests/test_autonomy_runtime.py::test_target_fingerprint_binds_mutation_identity_for_non_create tests/test_autonomy_runtime.py::test_non_create_candidate_requires_target_fingerprint_for_identity tests/test_autonomy_runtime.py::test_correction_target_fingerprint_binds_mutation_identity tests/test_autonomy_runtime.py::test_correction_requires_target_fingerprint_for_identity -q
```

Expected before implementation: FAIL on behavior, not collection. The helper may import, but mutation IDs do not yet bind the target fingerprint and the correction branch still calls the old helper signature.

- [ ] **Step 3: Add neutral identity helper and remove approval machinery from runtime evaluator**

Create `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`:

```python
"""Canonical mutation identity helpers for Ticket autonomy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from scripts.ticket_autonomy_ids import make_mutation_id, sha256_fingerprint


@dataclass(frozen=True, slots=True)
class CandidateMutationIdentity:
    """Deterministic identity for one candidate mutation."""

    mutation_id: str
    mutation_fingerprint: str
    evidence_fingerprint: str


def candidate_mutation_payload(
    *,
    ticket_id: str | None,
    action: str,
    proposed_change: Mapping[str, object],
    ticket_change_scope: str,
    target_fingerprint: str | None,
) -> dict[str, object]:
    """Return the canonical payload used for mutation identity."""
    return {
        "ticket_id": ticket_id,
        "action": action,
        "proposed_change": dict(proposed_change),
        "ticket_change_scope": ticket_change_scope,
        "target_fingerprint": target_fingerprint,
    }


def make_candidate_mutation_identity(
    *,
    thread_id: str,
    turn_id: str,
    ticket_id: str | None,
    action: str,
    proposed_change: Mapping[str, object],
    ticket_change_scope: str,
    target_fingerprint: str | None,
    evidence: object,
) -> CandidateMutationIdentity:
    """Calculate deterministic identity for one candidate mutation.

    This helper is calculation-only. It hashes the supplied target fingerprint
    but does not decide whether a missing target fingerprint is acceptable.
    Runtime and gateway callers own that policy.
    """
    mutation_fingerprint = sha256_fingerprint(
        candidate_mutation_payload(
            ticket_id=ticket_id,
            action=action,
            proposed_change=proposed_change,
            ticket_change_scope=ticket_change_scope,
            target_fingerprint=target_fingerprint,
        )
    )
    evidence_fingerprint = sha256_fingerprint(evidence)
    mutation_id = make_mutation_id(
        schema="codex.ticket.mutation.v1",
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

Do not import `CandidateMutation`, `GatewayMutation`, `AutonomyDecision`, or other runtime/gateway dataclasses into this helper. The helper must stay independent of runtime types.

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py`, delete `make_approval_id` and the `codex.ticket.approval.v1` schema constant or literal that only supports automatic approval envelopes. Keep `make_mutation_id` and `sha256_fingerprint`.

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, remove `make_approval_id`, `make_mutation_id`, and `sha256_fingerprint` from imports once no direct callers remain. Add:

```python
from scripts.ticket_mutation_identity import (
    CandidateMutationIdentity,
    make_candidate_mutation_identity,
)
```

Delete `_make_approval()`. Delete the `approval` field from `AutonomyDecision` and update `_decision()` plus all construction sites accordingly. Future explicit `discussion_only` approval is deferred design, not executable scaffolding in this slice.

Replace `_ticket_state_fingerprint()` with a target-fingerprint helper that only reads Ticket-owned source context; do not fall back to `candidate.proposed_change["ticket_state_fingerprint"]` because callers do not supply authoritative identity values:

```python
def _target_fingerprint_for_candidate(
    candidate: CandidateMutation,
    source_context: Mapping[str, object],
) -> str | None:
    if candidate.action == "create":
        return None
    fingerprints = source_context.get("ticket_state_fingerprints")
    if isinstance(fingerprints, Mapping) and isinstance(candidate.ticket_id, str):
        value = fingerprints.get(candidate.ticket_id)
        if isinstance(value, str) and value:
            return value
    return None
```

Delete `_candidate_payload()` and replace `_mutation_id_for_candidate()` with a runtime-local adapter around the neutral helper:

```python
def _identity_for_candidate(
    *,
    candidate: CandidateMutation,
    thread_id: str,
    turn_id: str,
    target_fingerprint: str | None,
) -> CandidateMutationIdentity:
    return make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        proposed_change=candidate.proposed_change,
        ticket_change_scope=candidate.ticket_change_scope,
        target_fingerprint=target_fingerprint,
        evidence=_evidence_payload(candidate),
    )
```

In the `candidate.action == "correction"` branch of `evaluate_autonomy_intent()`, after `dispatch.state == "ok"` and before computing `mutation_id`, add the same target-fingerprint identity requirement used by ordinary non-create writes:

```python
            target_fingerprint = _target_fingerprint_for_candidate(candidate, intent.source_context)
            if candidate.action != "create" and target_fingerprint is None:
                decisions.append(
                    _decision(
                        candidate,
                        RuntimeDecisionKind.TICKET_UPDATE_BLOCKED,
                        reason="target_fingerprint_required",
                        pending_summary_status="ticket_update_blocked",
                        mutation_id=None,
                        engine_dispatch=dispatch,
                    )
                )
                continue
            identity = _identity_for_candidate(
                candidate=candidate,
                thread_id=thread_id,
                turn_id=turn_id,
                target_fingerprint=target_fingerprint,
            )
```

In `evaluate_autonomy_intent()`, replace the autonomous-apply tail with:

```python
        target_fingerprint = _target_fingerprint_for_candidate(candidate, intent.source_context)
        if candidate.action != "create" and target_fingerprint is None:
            decisions.append(
                _decision(
                    candidate,
                    RuntimeDecisionKind.TICKET_UPDATE_BLOCKED,
                    reason="target_fingerprint_required",
                    pending_summary_status="ticket_update_blocked",
                    mutation_id=None,
                    engine_dispatch=dispatch,
                )
            )
            continue
        identity = _identity_for_candidate(
            candidate=candidate,
            thread_id=thread_id,
            turn_id=turn_id,
            target_fingerprint=target_fingerprint,
        )
        applied_counts[fanout_key] += 1
        decisions.append(
            _decision(
                candidate,
                RuntimeDecisionKind.APPLY_AUTONOMOUSLY,
                reason="authorized",
                pending_summary_status="pending",
                mutation_id=identity.mutation_id,
                engine_dispatch=dispatch,
            )
        )
```

For correction decisions, pass `identity.mutation_id` into `_decision()` in the same way. Runtime still owns the turn-local hard stop for non-create writes without a target fingerprint; it must use `TICKET_UPDATE_BLOCKED`, not `REQUIRE_USER_DISCUSSION`. `ticket_mutation_identity.py` must not enforce that policy.

Remove approval-only runtime leftovers in the same edit:

- Drop `timedelta` from the datetime import if no caller remains.
- Delete `_iso_z()` if `_make_approval()` was its only caller.
- Remove `decision_time = now or datetime.now(UTC)` if no branch uses it after approval creation is removed.
- Update the `now` docstring from approval creation wording to a neutral call-site note, or remove the parameter only if all call sites and tests are updated deliberately in this task.

- [ ] **Step 4: Run focused evaluator and correction tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_autonomy_runtime.py tests/test_autonomy_corrections.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py
```

Expected: PASS.

- [ ] **Step 5: Keep runtime approval removal uncommitted**

Do not commit after Task 3. A runtime-only commit would be a known broken checkpoint because gateway validation would still require approval envelopes. Leave the runtime and correction changes in the working tree, then continue directly to Task 4 and commit the combined runtime/gateway behavior only after both focused runtime and gateway tests pass.

## Task 4: Replace Gateway Approval Validation With Decision Validation

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:76-188`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:230-245`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:610-650`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:45-95`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:277-315`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py:1-220`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py:240-270`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py:650-810`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py:25-275`

- [ ] **Step 1: Add gateway decision-validation tests**

In `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`, add this import:

```python
from dataclasses import replace
```

Replace `test_gateway_rejects_missing_mismatched_reused_and_expired_approvals` and `test_gateway_rejects_approval_when_live_mutation_fingerprint_differs` with:

```python
def test_gateway_rejects_non_autonomous_or_mismatched_decisions(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    mutation = _mutation(tmp_tickets, ticket_path)
    decision = _decision_for(ticket_id="T-20260527-01", target_fp=mutation.target_fingerprint or "")
    store = PendingSummaryStore(project_root)

    discussion = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(
            decision,
            kind=RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
            reason="discussion_required",
            pending_summary_status="discussion_required",
        ),
        pending_summary=store,
    )
    mismatched_ticket = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(
            decision,
            candidate=CandidateMutation(
                ticket_id="T-20260527-99",
                action="update",
                proposed_change={"priority": "low"},
                evidence=(EvidenceLink("current_thread_reason", "test"),),
            ),
        ),
        pending_summary=store,
    )
    mismatched_fields = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(
            decision,
            candidate=CandidateMutation(
                ticket_id="T-20260527-01",
                action="update",
                proposed_change={"priority": "normal"},
                evidence=(EvidenceLink("current_thread_reason", "test"),),
            ),
        ),
        pending_summary=store,
    )
    mismatched_scope = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=replace(mutation, ticket_change_scope="unrelated_backlog"),
        decision=decision,
        pending_summary=store,
    )
    mismatched_target_fingerprint = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=replace(mutation, target_fingerprint="different-ticket-state"),
        decision=decision,
        pending_summary=store,
    )
    forged_mutation_id = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=replace(decision, mutation_id="mut_wrong"),
        pending_summary=store,
    )

    assert discussion.error_code == "gateway_required"
    assert "autonomous_decision_required" in discussion.message
    assert mismatched_ticket.error_code == "gateway_required"
    assert "ticket_mismatch" in mismatched_ticket.message
    assert mismatched_fields.error_code == "gateway_required"
    assert "mutation_fingerprint_mismatch" in mismatched_fields.message
    assert mismatched_scope.error_code == "gateway_required"
    assert "ticket_change_scope_mismatch" in mismatched_scope.message
    assert mismatched_target_fingerprint.error_code == "gateway_required"
    assert "mutation_id_mismatch" in mismatched_target_fingerprint.message
    assert forged_mutation_id.error_code == "gateway_required"
    assert "mutation_id_mismatch" in forged_mutation_id.message
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
    assert _events(project_root) == []
```

Also add the positive create-path counterpart. The Stop Conditions make "a `create` candidate blocked only because `target_fingerprint` is `None`" a hard invariant, but the only existing create gateway test stops at `duplicate_candidate` before identity recomputation matters. This proves a non-duplicate create with `target_fingerprint=None` passes `_decision_error` and writes, with the three-event sequence (no `approval_consumed`). It relies only on helpers already in this file (`_declare_ignored_workspace`, `_repo_context`, `_events`, the `tmp_tickets` fixture, and the existing top-of-file imports including `AutonomyIntent`/`evaluate_autonomy_intent`/`GatewayMutation`/`apply_autonomous_mutation`/`PendingSummaryStore`):

```python
def test_gateway_autonomous_create_writes_ticket_without_target_fingerprint(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    fields = {
        "title": "Add retry to publisher",
        "problem": "Publisher drops messages on transient broker errors.",
        "priority": "high",
        "key_file_paths": ["publisher.py"],
    }
    candidate = CandidateMutation(
        ticket_id=None,
        action="create",
        proposed_change=fields,
        evidence=(EvidenceLink("current_thread_reason", "discussed this turn"),),
    )
    decision = evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="create",
            candidates=(candidate,),
            source_context={},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id="turn-1",
        now=datetime.now(UTC),
    )[0]
    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.mutation_id is not None
    mutation = GatewayMutation("create", None, fields, tmp_tickets, None)

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    assert response.state == "ok_create"
    created = list(tmp_tickets.glob("*.md"))
    assert len(created) == 1
    ticket_text = created[0].read_text(encoding="utf-8")
    assert "Add retry to publisher" in ticket_text
    assert "auto-create" in ticket_text
    events = _events(project_root)
    assert [event["status"] for event in events] == [
        "pending",
        "ticket_written",
        "applied",
    ]
```

- [ ] **Step 2: Run the gateway decision-validation test to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py::test_gateway_rejects_non_autonomous_or_mismatched_decisions -q
```

Expected before implementation: FAIL because gateway still requires approval envelopes.

- [ ] **Step 3: Replace approval validation helper**

In `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`, delete `_approval_ticket_id()`. Do not delete `_parse_z()`; approval validation stops using it, but `_mutation_attempt_timestamp()` still needs it for recovery timestamp validation.

Keep the existing runtime imports limited to runtime dataclasses and dispatch helpers:

```python
from scripts.ticket_autonomy_runtime import (
    AutonomyDecision,
    CandidateMutation,
    EngineAction,
    EngineDispatch,
    RuntimeDecisionKind,
    map_candidate_to_engine,
)
```

Add a public helper import from the new neutral identity module:

```python
from scripts.ticket_mutation_identity import make_candidate_mutation_identity
```

Do not import `_identity_for_candidate`, `_evidence_payload`, or any other private runtime helper into the gateway. The gateway adapts `decision.candidate` into primitive fields and calls `make_candidate_mutation_identity()` directly.

Replace `_approval_error()` with:

```python
def _candidate_evidence_payload(candidate: CandidateMutation) -> list[dict[str, str]]:
    return [
        {"kind": evidence.kind, "ref": evidence.ref, "freshness": evidence.freshness}
        for evidence in candidate.evidence
    ]


def _decision_error(
    *,
    thread_id: str,
    turn_id: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    if decision.kind == RuntimeDecisionKind.APPLY_CORRECTION:
        if mutation.action != "correction" or decision.candidate.action != "correction":
            return "decision_mismatch"
    elif decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        return "autonomous_decision_required"
    if decision.mutation_id is None:
        return "mutation_id_required"
    if decision.candidate.ticket_id != mutation.ticket_id:
        return "ticket_mismatch"
    if decision.candidate.action != mutation.action:
        return "action_mismatch"
    if decision.candidate.ticket_change_scope != mutation.ticket_change_scope:
        return "ticket_change_scope_mismatch"
    if dict(decision.candidate.proposed_change) != dict(mutation.fields):
        return "mutation_fingerprint_mismatch"
    if mutation.action != "create" and mutation.target_fingerprint is None:
        return "target_fingerprint_required"
    identity = make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        ticket_id=decision.candidate.ticket_id,
        action=decision.candidate.action,
        proposed_change=decision.candidate.proposed_change,
        ticket_change_scope=decision.candidate.ticket_change_scope,
        target_fingerprint=mutation.target_fingerprint,
        evidence=_candidate_evidence_payload(decision.candidate),
    )
    if decision.mutation_id != identity.mutation_id:
        return "mutation_id_mismatch"
    return None
```

In `apply_autonomous_mutation()`, replace the approval check with:

```python
    decision_error = _decision_error(
        thread_id=thread_id,
        turn_id=turn_id,
        mutation=mutation,
        decision=decision,
    )
    if decision_error is not None:
        return _policy_blocked(f"Decision validation failed: {decision_error}")
```

Remove the second `decision.mutation_id is None` check immediately after it because `_decision_error()` covers that invariant.

- [ ] **Step 4: Stop writing approval details and `approval_consumed` events**

In `apply_autonomous_mutation()`, change the docstring from approval wording to neutral decision wording:

```python
    """Apply one autonomous mutation through the gateway."""
```

In `_apply_autonomous_mutation_locked()`, replace the mutation-attempt details block with:

```python
        details={
            "decision": decision.kind.value,
            "current_mode": "agent_primary",
            "evidence_kind": "runtime_context",
            **_fingerprint_details(mutation=mutation, decision=decision),
        },
```

In the same mutation-attempt event, replace the stale approval-shaped reason with neutral wording:

```python
        reason=(
            "Apply autonomous Ticket mutation."
            if decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
            else "Apply user-triggered autonomous Ticket correction."
        ),
```

Delete this whole block:

```python
    if decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        if decision.approval is None:
            return _policy_blocked("Approval validation failed: approval_required")
        consumed_error = _append_gateway_event(
            pending_summary=pending_summary,
            event_type="mutation_status",
            status="approval_consumed",
            mutation=mutation,
            decision=decision,
            thread_id=thread_id,
            turn_id=turn_id,
            repo_context=repo_context,
            reason="Autonomous approval consumed.",
            details={
                "approval_id": str(decision.approval["approval_id"]),
                **_fingerprint_details(mutation=mutation, decision=decision),
            },
        )
        if consumed_error is not None:
            return consumed_error
```

In `_expected_pre_write_fingerprint()`, replace the function with:

```python
def _expected_pre_write_fingerprint(
    *,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    del decision
    return mutation.target_fingerprint
```

- [ ] **Step 5: Rewrite gateway event sequence expectations**

In `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`, update gateway success expectations from:

```python
    assert [event["status"] for event in events] == [
        "pending",
        "approval_consumed",
        "ticket_written",
        "applied",
    ]
```

to:

```python
    assert [event["status"] for event in events] == [
        "pending",
        "ticket_written",
        "applied",
    ]
```

Apply the same replacement in this file anywhere a new successful gateway write is expected. Also update failed gateway write expectations, including `test_gateway_treats_success_without_ticket_path_as_failed_mutation`, from `["pending", "approval_consumed", "failed"]` to `["pending", "failed"]`.

In `test_gateway_rechecks_pause_after_approval_consumption_before_dispatch`, rename the test to:

```python
def test_gateway_rechecks_pause_after_attempt_record_before_dispatch(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
```

and change the final event-status assertion to:

```python
    assert [event["status"] for event in _events(project_root)] == ["pending"]
```

- [ ] **Step 6: Keep gateway changes uncommitted until pending-summary validation is updated**

Do not commit after Task 4. Gateway success paths append through pending-summary validation, so this boundary is runnable only after Task 5 removes approval/preview taxonomy from `ticket_turn_batch.py` and rewrites all affected gateway and turn-batch expectations.

## Task 5: Delete Pending-Summary Preview And Approval Support

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:45-95`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:280-300`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py:25-70`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py:170-275`

- [ ] **Step 1: Rewrite pending-summary fixtures and deletion tests**

In `plugins/turbo-mode/ticket/tests/test_turn_batch.py`, replace the `details`
dictionary in `valid_attempt_event()` with:

```python
    details: dict[str, object] = {
        "decision": "apply_autonomously",
        "current_mode": "agent_primary",
        "evidence_kind": "runtime_context",
    }
```

In the same helper, replace the default attempt reason:

```python
        "reason": "Apply autonomous Ticket mutation.",
```

Replace `test_preview_records_use_skipped_status_with_preview_only_decision`
with a rejection test for removed preview taxonomy:

```python
def test_preview_only_decision_is_not_a_supported_pending_summary_decision() -> None:
    event = valid_attempt_event(
        status="skipped",
        details={"decision": "preview_only", "current_mode": "preview"},
    )

    assert_invalid(event, "decision")
```

Add rejection coverage for removed approval state:

```python
def test_approval_consumed_status_is_not_supported() -> None:
    event = valid_status_event("ticket_written")
    event["status"] = "approval_consumed"
    event["details"] = {"approval_id": "old-approval"}

    assert_invalid(event, "status")
```

Remove approval-shaped detail requirement tests. Do not add `autonomy_health`,
`ticket_update_blocked`, or any other blocked-candidate event to pending-summary
validation in this slice.

In `test_valid_event_status_matrix`, keep `("automation_pause", "paused")`
valid and keep existing pause-reason validation focused on event shapes already
written today. Do not add `source_context_unhealthy` to pending-summary
pause-reason tests unless implementation first proves runtime pauses already
append `automation_pause` events consistently.

- [ ] **Step 2: Run pending-summary tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py::test_preview_only_decision_is_not_a_supported_pending_summary_decision tests/test_turn_batch.py::test_approval_consumed_status_is_not_supported tests/test_turn_batch.py::test_status_details_requirements -q
```

Expected before implementation: FAIL because `preview_only`,
`current_mode: preview`, `details.approval`, `approval_consumed`, and
`approval_id` are still accepted or required.

- [ ] **Step 3: Delete preview and approval taxonomy from validation and recovery**

In `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`, replace `_DECISIONS`
and `_MODES` with:

```python
_DECISIONS = frozenset(
    {
        "apply_autonomously",
        "apply_correction",
        "require_user_discussion",
        "skip_due_to_conflict",
        "defer_until_retry_condition",
    }
)
_MODES = frozenset({"discussion_only", "agent_primary"})
```

Remove `approval_consumed` from `_EVENT_STATUSES` and remove `approval_id` from
status-specific detail requirements. Remove these `_validate_details()` checks:

```python
        if decision == "apply_autonomously" and not isinstance(details.get("approval"), Mapping):
            return _invalid("details.approval is required")
        if decision == "preview_only" and status != "skipped":
            return _invalid("preview_only decisions must use skipped status")
```

Delete `approval_consumed` branches from `derive_mutation_state()`,
`project_mutation_recovery()`, compaction/recovery helpers, and tests. This
slice intentionally has no compatibility reader for old approval logs because
Task 0 verified no project-local pending-summary logs exist in this checkout.
If Task 0 found a current log, this step must not run until the migration/reader
decision is made.

Do not add `autonomy_health`, `ticket_update_blocked`, or other blocked-candidate
pending-summary event validation here. Missing target fingerprints are
turn-local output only in this slice.

- [ ] **Step 4: Run the atomic approval-boundary tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_autonomy_runtime.py tests/test_autonomy_corrections.py tests/test_engine_gateway.py tests/test_turn_batch.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_ids.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
```

Expected: the focused selector passes **and the whole suite (`pytest -q`) is green**. The atomic approval-boundary commit removes `make_approval_id`, `AutonomyDecision.approval`, the `approval_consumed` status, and durable `preview` from source — which breaks every consumer test in the Consumer Inventory, not just the five focused modules. The boundary is not actually verified until the whole suite collects and passes. Reaching green requires completing **all** removed-machinery consumer rewrites in this commit: `test_autonomy_ids.py` (whose import otherwise fails collection) and the approval/preview test cleanup physically described in Task 6 Steps 2, 5, 6, 7, and 8. Do those rewrites now, as part of this boundary. Task 6's **new** apply-turn behavior (Steps 3-4: blocked buckets, partial apply, `source_context_unhealthy`) is additive, does not gate this commit, and commits separately.

- [ ] **Step 5: Commit atomic approval-boundary removal**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_ids.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git commit -m "fix(ticket): remove agent-primary approval gate"
```

Expected: commit includes Task 3, Task 4, and Task 5 changes plus every removed-machinery consumer rewrite from the Consumer Inventory (including `test_autonomy_ids.py` and the Task 6 Steps 2/5/6/7/8 cleanup). The committed tree is whole-suite green. Do not create a Task 3-only or Task 4-only commit, and do not commit while `pytest -q` is red. The apply-turn source changes in `ticket_autonomy.py` (Task 6 Step 3) and their tests (Step 4) are intentionally **not** staged here; they commit in Task 6.

## Task 6: Update Apply-Turn Recovery And Integration Tests

**Files:**
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`

- [ ] **Step 1: Find remaining test expectations for new approval writes**

Run:

```bash
rg -n "approval_consumed|details\\[\\\"approval\\\"\\]|decision\\.approval|approval_id|AutomationMode\\.PREVIEW|preview_payload|\\\"preview\\\"" plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
```

Expected after Tasks 3-5: remaining matches should be deletion-only negative fixtures or tests that still need source-slice rewrite. No current write, validation, recovery, or event-sequence test should expect `approval_consumed`; no test should write durable `AutomationMode.PREVIEW`.

- [ ] **Step 2: Rewrite apply-turn recovery helper approval mutation**

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`, update `_event_with_recovery_fingerprints()` so it no longer edits nested approval details:

```python
def _event_with_recovery_fingerprints(
    event: dict[str, object],
    *,
    pre: str,
    post: str,
) -> dict[str, object]:
    details = dict(event["details"])
    details["expected_pre_write_fingerprint"] = pre
    details["expected_post_write_fingerprint"] = post
    return {**event, "details": details}
```

Apply the same body change in `plugins/turbo-mode/ticket/tests/test_engine_gateway.py` (the helper there is also named `_event_with_recovery_fingerprints`). In `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py` the helper has a **different name and signature**: `_event_with_bound_fingerprints(event, *, pre="pre-fp", post="post-fp")`. Keep that real name and its `pre`/`post` defaults (no call site passes them) — only strip the nested `approval`/`Mapping` branch so it sets just the two fingerprint keys. Do not paste the `cli` block verbatim into the recovery file.

- [ ] **Step 3: Add source-context health and blocked-ticket apply-turn projection**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`, add `source_context_unhealthy` to `_pause_message()`:

```python
        "source_context_unhealthy": (
            "Ticket automation paused because source-context collection is unhealthy."
        ),
```

Change `_ticket_state_fingerprints()` from returning a bare dictionary to returning a small result object:

```python
@dataclass(frozen=True, slots=True)
class TicketStateFingerprintCollection:
    """Source-context fingerprint collection result for candidate writes."""

    state: Literal["ok", "unhealthy"]
    fingerprints: dict[str, str]
    reason: str | None = None
```

Import `Literal` from `typing` if needed. The collector must classify by
collector trust, not by the number of candidates affected:

- If the collector successfully returns a trustworthy map plus explicit
  per-ticket misses, keep the collection `ok` and omit those candidates from
  `fingerprints`; runtime will later return `TICKET_UPDATE_BLOCKED` for those
  candidates.
- If source-context collection cannot prove the map is complete for the
  attempted candidate set because of an I/O error, parse failure, lock or health
  failure, ambiguous tickets root, or other collector-level uncertainty, return
  `TicketStateFingerprintCollection("unhealthy", {}, "source_context_unhealthy")`.

In `_run_apply_turn_with_mode()`, replace the bare fingerprint map use with a pause gate before `evaluate_autonomy_intent()`:

```python
    fingerprint_collection = _ticket_state_fingerprints(candidates, tickets_dir)
    if fingerprint_collection.state == "unhealthy":
        pause_workspace_automation(project_root, reason="source_context_unhealthy")
        _emit(_paused_response("source_context_unhealthy"))
        return 3
    fingerprints = fingerprint_collection.fingerprints
```

Do not write `autonomy_health`, `mutation_attempt`, `mutation_status`, `summary_receipt`, or a new pending-summary `automation_pause` event for this global failure. A collector-level source-context failure is a workspace pause, not a candidate result, and current runtime pause paths use `pause.json` plus the paused response as their authority. If an executor discovers an existing consistent runtime-pause-to-`automation_pause` event path before implementation, stop and revise this plan deliberately instead of adding a one-off event for `source_context_unhealthy`.

For `--resume-paused`, add a guard before `resume_workspace_automation()` when `_read_pause_reason(project_root) == "source_context_unhealthy"`. The guard must rerun source-context collection against the current candidate set if one exists, or a fail-closed known-ticket probe otherwise. If the probe cannot prove collection is healthy, keep the pause and emit `_paused_response("source_context_unhealthy")`.

The known-ticket probe is only a minimum liveness check for turns with no current
candidate set. It must find exactly one readable open Ticket-owned file through
the same tickets-root resolution path and compute a fingerprint through the same
collector helper. If there are zero tickets, multiple ambiguous roots, parse or
read errors, or the probe bypasses the collector helper, do not clear the pause;
report `source_context_unhealthy` so the user sees that explicit repair evidence
is missing.

Do not add a blocked-candidate pending-summary helper. A missing target
fingerprint is turn-local output only in this slice.

Update `_summary_payload()` to accept `blocked: list[str]` and
`blocked_reasons: dict[str, str]` arguments, add a `"Blocked"` bucket, preserve
conflict skips as `state: "skipped"` when all candidates are skipped, expose
only concise blocker reasons, and select states with partial-apply semantics:

```python
    if skipped:
        ticket_updates["Skipped"] = skipped
    if blocked:
        ticket_updates["Blocked"] = blocked
    if applied and (blocked or skipped):
        state = "partially_applied"
    elif applied:
        state = "applied"
    elif discussion:
        state = "discussion_required"
    elif blocked:
        state = "ticket_update_blocked"
    elif skipped:
        state = "skipped"
    else:
        state = "no_change"
```

After the payload dictionary is created, add only the concise reason map when blocked candidates exist:

```python
    if blocked_reasons:
        payload["blocked_reasons"] = blocked_reasons
```

Do not include a `discussion_question` for `ticket_update_blocked` unless another candidate independently requires discussion. Do not include proposed fields, fingerprints, mutation IDs, event IDs, health-event internals, or maintenance-ticket IDs in the summary payload.

In the apply-turn decision loop, add `blocked: list[str] = []` and `blocked_reasons: dict[str, str] = {}` beside the existing result buckets. Add this branch before the generic non-write branch:

```python
        elif decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED:
            blocked.append(ticket_id)
            blocked_reasons[ticket_id] = decision.reason or "ticket_update_blocked"
```

Pass `blocked=blocked` and `blocked_reasons=blocked_reasons` into `_summary_payload()`. This branch must not call `apply_autonomous_mutation()`, must not append any pending-summary event, and must not add a mutation ID to `summary_mutation_ids`.

- [ ] **Step 4: Add blocked-ticket apply-turn tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py` or `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, add focused coverage for a mixed batch where one update has a target fingerprint and one non-create candidate lacks one. Expected behavior:

```python
assert payload["state"] == "partially_applied"
assert payload["ticket_updates"]["Applied"] == ["T-20260527-01"]
assert payload["ticket_updates"]["Blocked"] == ["T-20260527-02"]
assert payload["blocked_reasons"] == {"T-20260527-02": "target_fingerprint_required"}
assert "discussion_question" not in payload or payload["discussion_question"] is None
assert "mutation_id" not in payload
assert "event_id" not in payload
assert "fingerprints" not in payload

events = _events(tmp_path)
blocked_events = [
    event
    for event in events
    if event.get("ticket_id") == "T-20260527-02"
]
assert blocked_events == []
```

Also add a single-candidate blocked case that returns
`state: "ticket_update_blocked"` and writes no pending-summary event for the
blocked candidate. If the easiest focused test is at the `_summary_payload()`
level, keep the integration test smaller but still prove the no-mutation-event
boundary.

Add source-context pause and resume tests:

- A collector-level failure pauses the workspace with `state: "paused"`, `pause_reason: "source_context_unhealthy"`, and writes no mutation or health events.
- The same collector-level failure creates or preserves the workspace `pause.json` marker and does not append a pending-summary `automation_pause` event unless the implementation has first proven all comparable runtime pauses already append one consistently.
- A trustworthy collection with explicit per-ticket misses produces per-candidate `ticket_update_blocked` decisions, writes no private event for those blocked candidates, and still allows other valid candidates to apply.
- A normal later `apply-turn` without `--resume-paused` remains paused with `source_context_unhealthy`; it must not silently clear the marker.
- `--resume-paused` for `source_context_unhealthy` fails closed when the current candidate-set collection or fail-closed known-ticket probe cannot prove source-context health through the same collector path.
- `--resume-paused` clears `source_context_unhealthy` only after the collector/probe succeeds, then continues through the normal mode-specific apply-turn path.

These are the slice's most safety-relevant new behaviors (a wrong resume silently clears a fail-closed pause), so write them as concrete tests, not prose. Because `apply-turn` runs as a subprocess, the collector cannot be reached by `monkeypatch`. **Fault-injection decision (make it consciously):** prefer triggering a *real* collector-level failure from a fixture (e.g. an unreadable or unparseable ticket file the Step-3 collector classifies as `unhealthy`) so the test exercises the real classification path. Only if a real fault is not reliably reproducible, fall back to a narrow test-only env seam wired into the Step-3 collector — and treat that seam as production surface the Development Tenet would scrutinize, not a free affordance. The bodies below use the env-seam form; convert to a real-fault fixture if feasible. Insert the four functions (and the `_run_autonomy_env` / `_source_context_candidate` / `FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV` helpers near `_run_autonomy`) into `test_autonomy_cli.py`:

```python
FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV = "TICKET_AUTONOMY_FORCE_SOURCE_CONTEXT_UNHEALTHY"


def _run_autonomy_env(
    project_root: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
        env=merged,
    )


def _source_context_candidate(ticket_id: str = "T-20260527-01") -> list[dict[str, object]]:
    return [
        {
            "ticket_id": ticket_id,
            "action": "update",
            "proposed_change": {"priority": "low"},
            "evidence": [{"kind": "current_thread_reason", "ref": "current turn"}],
        }
    ]


def test_apply_turn_collector_unhealthy_pauses_without_mutation_or_health_events(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="high")
    before_ticket = ticket.read_text(encoding="utf-8")
    context = _write_context(tmp_path, candidate_mutations=_source_context_candidate())

    result = _run_autonomy_env(
        tmp_path,
        "apply-turn",
        "--project-root",
        str(tmp_path),
        "--turn-id",
        "turn-1",
        "--context-file",
        str(context),
        env={FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV: "1"},
    )

    assert result.returncode == 3
    assert json.loads(result.stdout) == {
        "state": "paused",
        "pause_reason": "source_context_unhealthy",
        "message": "Ticket automation paused because source-context collection is unhealthy.",
        "ticket_updates": None,
        "discussion_question": None,
    }
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()
    assert PendingSummaryStore(tmp_path).read_events() == ()
    assert not (
        tmp_path / ".codex" / "ticket-workspace" / "ticket.pending-summary.jsonl"
    ).exists()
    assert ticket.read_text(encoding="utf-8") == before_ticket


def test_apply_turn_after_source_context_pause_stays_paused_without_resume_flag(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="high")
    context = _write_context(tmp_path, candidate_mutations=_source_context_candidate())

    paused = _run_autonomy_env(
        tmp_path, "apply-turn", "--project-root", str(tmp_path),
        "--turn-id", "turn-1", "--context-file", str(context),
        env={FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV: "1"},
    )
    assert paused.returncode == 3
    assert json.loads(paused.stdout)["pause_reason"] == "source_context_unhealthy"

    later_context = _write_context(
        tmp_path, turn_id="turn-2", candidate_mutations=_source_context_candidate(),
    )
    blocked = _run_autonomy(
        tmp_path, "apply-turn", "--project-root", str(tmp_path),
        "--turn-id", "turn-2", "--context-file", str(later_context),
    )

    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["pause_reason"] == "source_context_unhealthy"
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()
    assert "priority: high" in ticket.read_text(encoding="utf-8")
    assert PendingSummaryStore(tmp_path).read_events() == ()


def test_apply_turn_resume_paused_fails_closed_when_probe_cannot_prove_health(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="high")
    context = _write_context(tmp_path, candidate_mutations=_source_context_candidate())

    paused = _run_autonomy_env(
        tmp_path, "apply-turn", "--project-root", str(tmp_path),
        "--turn-id", "turn-1", "--context-file", str(context),
        env={FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV: "1"},
    )
    assert paused.returncode == 3

    resume_blocked = _run_autonomy_env(
        tmp_path, "apply-turn", "--project-root", str(tmp_path),
        "--turn-id", "turn-1", "--context-file", str(context),
        "--setup-choice", "automatic", "--resume-paused",
        env={FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV: "1"},
    )

    assert resume_blocked.returncode == 3
    assert json.loads(resume_blocked.stdout)["pause_reason"] == "source_context_unhealthy"
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()
    assert "priority: high" in ticket.read_text(encoding="utf-8")
    assert PendingSummaryStore(tmp_path).read_events() == ()


def test_apply_turn_resume_paused_clears_only_after_probe_passes(
    tmp_path: Path,
) -> None:
    _init_ticket_project(tmp_path)
    write_local_config(tmp_path, AutomationMode.AGENT_PRIMARY)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket = make_ticket(tickets_dir, "one.md", id="T-20260527-01", priority="high")
    context = _write_context(tmp_path, candidate_mutations=_source_context_candidate())

    paused = _run_autonomy_env(
        tmp_path, "apply-turn", "--project-root", str(tmp_path),
        "--turn-id", "turn-1", "--context-file", str(context),
        env={FORCE_SOURCE_CONTEXT_UNHEALTHY_ENV: "1"},
    )
    assert paused.returncode == 3
    assert (tmp_path / ".codex" / "ticket-workspace" / "pause.json").is_file()

    resumed = _run_autonomy(
        tmp_path, "apply-turn", "--project-root", str(tmp_path),
        "--turn-id", "turn-1", "--context-file", str(context),
        "--setup-choice", "automatic", "--resume-paused",
    )

    assert resumed.returncode == 0
    payload = json.loads(resumed.stdout)
    assert payload["state"] == "applied"
    assert payload["ticket_updates"]["Applied"] == ["T-20260527-01"]
    assert not (tmp_path / ".codex" / "ticket-workspace" / "pause.json").exists()
    assert "priority: low" in ticket.read_text(encoding="utf-8")
```

Confirm `_init_ticket_project`, `_write_context`, `_run_autonomy`, `SCRIPT`, `os`, `sys`, and `subprocess` are already imported/defined in `test_autonomy_cli.py`; adapt `_write_context`'s candidate-mutations argument name to the live helper. The per-candidate `ticket_update_blocked` and partial-apply assertions stay in the blocked-ticket payload coverage above; these four tests cover only the collector-level pause and resume gate.

Do not assert `state: "setup_required"` for source-context failures. `setup_required` remains local config or mode setup only.

- [ ] **Step 5: Rewrite integration success event sequence**

In `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, update `test_agent_primary_apply_turn_applies_update_through_gateway` so the success event assertions use the three-event sequence:

```python
    events = _events(tmp_path)
    assert [event["status"] for event in events[:3]] == [
        "pending",
        "ticket_written",
        "applied",
    ]
    assert events[2]["details"]["commit_disposition"] == "commit_recorded"
    assert events[2]["details"]["commit_hash"] == _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert payload["commit_dispositions"] == [
        {
            "ticket_id": "T-20260527-01",
            "disposition": "commit_recorded",
            "commit_hash": events[2]["details"]["commit_hash"],
        }
    ]
```

- [ ] **Step 6: Rewrite integration preview test**

In `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, rename `test_preview_and_discussion_modes_do_not_write_tickets` to:

```python
def test_invalid_preview_config_and_discussion_mode_do_not_write_tickets(tmp_path: Path) -> None:
```

Replace the preview block with:

```python
    preview_config = tmp_path / ".codex" / "ticket.local.md"
    preview_config.parent.mkdir(exist_ok=True)
    preview_config.write_text(
        '{"schema":"codex.ticket.local.v1","mode":"preview"}\n',
        encoding="utf-8",
    )
    preview = _apply_turn(tmp_path, context)
    assert preview.returncode == 3
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["state"] == "setup_required"
    assert preview_payload["reason"] == "invalid_mode"
    assert ticket.read_text(encoding="utf-8") == before
    assert _events(tmp_path) == []
```

Keep the existing `discussion_only` block after it. This asserts durable `preview` is invalid and does not implement diagnostic dry-run.

- [ ] **Step 7: Rewrite integration forged-authorization assertion**

In `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, rename
`test_apply_turn_consumes_adapter_candidate_keys_and_ignores_forged_approval`
to a neutral authorization-residue test. Keep the final assertion focused on the
mutation identity, without approval-shaped strings:

```python
    events = _events(tmp_path)
    assert events[0]["mutation_id"] != "forged"
```

- [ ] **Step 8: Keep approval-free recovery coverage**

In `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`,
`test_ticket_written_without_terminal_status_appends_outcome` must model the
current crash boundary with a `pending` attempt event followed by a
`ticket_written` event. Keep the expected projection:

```python
    assert projection.state == "append_missing_terminal_status"
    assert [event["status"] for event in projection.events_to_append] == ["applied"]
```

This proves a write-completed-before-terminal-event recovery path using only
current event states.

- [ ] **Step 9: Confirm no source writes approval envelopes, preview decisions, or blocked private events**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|details\\.approval|approval_required|make_approval|codex\\.ticket\\.approval|decision\\.approval|approval_consumed|approval_id" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
rg -n "target_fingerprint_required|ticket_update_blocked|autonomy_health|partially_applied|source_context_unhealthy|maintenance_tickets|MAINTENANCE_REPEAT_THRESHOLD|ticket_autonomy_maintenance" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected after Tasks 1-6:

- Every match for `AutomationMode.PREVIEW`, `RuntimeDecisionKind.PREVIEW_ONLY`, `preview_only`, `details.approval`, `approval_required`, `make_approval`, `codex.ticket.approval`, `decision.approval`, `approval_consumed`, or `approval_id` is classified before commit. Allowed matches are only negative rejection fixtures for removed values. There must be no executable source path, helper default, current write expectation, validation branch, recovery branch, or event-sequence expectation that still supports those removed values.
- `target_fingerprint_required` matches must use `RuntimeDecisionKind.TICKET_UPDATE_BLOCKED`, concise blocked-output assertions, or gateway policy-blocked validation. No match may classify missing target fingerprint as `discussion_required` or emit a discussion question.
- `autonomy_health`, `maintenance_tickets`, `MAINTENANCE_REPEAT_THRESHOLD`, and `ticket_autonomy_maintenance` must have no matches in executable source or active tests in this slice.
- `source_context_unhealthy` matches must be pause-marker/output handling, collector-level pause, or explicit resume-proof code. No match may report source-context failure as `setup_required`, clear the pause without a collector/probe pass, or add pending-summary pause-reason validation without a proven consistent `automation_pause` event path.
- `automation_pause` matches must remain validation or pre-existing pause behavior. A new source-context pause must not be the only runtime pause that writes an `automation_pause` pending-summary event.

- [ ] **Step 10: Run focused apply-turn, integration, recovery, and gateway suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py tests/test_autonomy_recovery.py tests/test_engine_gateway.py tests/test_turn_batch.py tests/test_autonomy_runtime.py tests/test_autonomy_corrections.py tests/test_autonomy_config.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit apply-turn and integration cleanup**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git commit -m "fix(ticket): update apply-turn modes approval output"
```

Expected: commit contains only apply-turn, CLI, integration, and recovery updates
needed after the preview/approval boundaries. It must not add maintenance
escalation, `autonomy_health`, or any blocked-candidate private event.

## Deferred Maintenance Escalation Design

Repeat-block tracking and maintenance-ticket escalation are intentionally split
out of this source slice. A future control plan must explicitly authorize any
recurrence tracking, `autonomy_health` bridge, repeat threshold, maintenance
helper, maintenance-ticket output, dedupe identity, recovery behavior, and tests.
This slice must keep missing target fingerprints turn-local: report the blocked
candidate, apply other valid candidates in the same batch, and write no mutation,
health, recovery, or pending-summary event for the blocked candidate.

## Task 7: Final Verification And Closeout

**Files:**
- Verify all modified files from Tasks 1-6 and this final closeout.

- [ ] **Step 1: Run boundary inventory guard**

Run:

```bash
rg -n 'AutomationMode\.PREVIEW|RuntimeDecisionKind\.PREVIEW_ONLY|preview_only|details\.approval|details\["approval"\]|approval_required|make_approval|codex\.ticket\.approval|decision\.approval|approval_consumed|approval_id|current_mode": "preview"|approved autonomous|gateway-approved decision|approved ticket update|Apply approved|target_fingerprint_required|ticket_update_blocked|autonomy_health|partially_applied|source_context_unhealthy|maintenance_tickets|MAINTENANCE_REPEAT_THRESHOLD|ticket_autonomy_maintenance' plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: every match is classified before closeout. Allowed matches are only:

- Negative rejection fixtures that prove removed values such as `preview_only` or `current_mode: "preview"` are rejected.
- Negative rejection fixtures that prove removed values such as `approval_consumed`, `approval_id`, or `details.approval` are rejected.
- Runtime and apply-turn branches that classify `target_fingerprint_required` as `ticket_update_blocked`, write no private event for the blocked candidate, and preserve partial apply for other valid candidates.
- Partial-result response tests that expose applied ticket IDs, skipped ticket IDs, blocked ticket IDs, and blocker reasons only.
- Pause and resume branches for `source_context_unhealthy` that require explicit source-context proof before clearing the pause, including the fail-closed known-ticket probe that uses the same collector path when no current candidates exist.
- Assertions that `source_context_unhealthy` uses `pause.json` as the live authority and does not introduce a one-off `automation_pause` event.

Any product/runtime support for durable `preview`, new `preview_only` events, replacement diagnostic dry-run flags/commands/events, automatic `agent_primary` approvals, approval-shaped event reasons or docstrings such as "approved autonomous" or "approved ticket update", `decision.approval` reads in executable write paths, `details.approval` requirements, retained `approval_consumed` or `approval_id` validation/recovery support, target-fingerprint blocks classified as discussion, non-create mutation IDs or gateway dispatch without a Ticket-derived target fingerprint, create mutations blocked only because `target_fingerprint` is `None`, `autonomy_health`, repeat-block tracking, maintenance-ticket escalation, partial-result responses that expose proposed fields/fingerprints/mutation IDs/event IDs, normal-turn clearing of `source_context_unhealthy` without explicit repair proof, a known-ticket probe that bypasses the collector path or clears a pause without exactly one readable open Ticket-owned probe file, or a one-off `automation_pause` event for `source_context_unhealthy` is a failure. Record the allowed-match list in the implementation closeout.

- [ ] **Step 2: Run focused source tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_autonomy_config.py tests/test_autonomy_runtime.py tests/test_autonomy_corrections.py tests/test_turn_batch.py tests/test_engine_gateway.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py tests/test_autonomy_recovery.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full Ticket tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: PASS. If failures occur outside the touched surfaces, classify them as pre-existing only after rerunning the same selector on the pre-task branch or commit.

- [ ] **Step 4: Run ruff on touched Python files**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py plugins/turbo-mode/ticket/tests/test_autonomy_ids.py
```

Expected: PASS.

- [ ] **Step 5: Run unconditional cleanliness and residue proof**

Run:

```bash
git status --short --branch
git diff --stat
git diff --cached --stat
git diff --check
git diff --cached --check
find plugins/turbo-mode/ticket \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .DS_Store \) -print
```

Expected: no diff-check output, no generated residue output, and no unstaged, staged, untracked, cache, installed-runtime, local workspace, or handoff files outside the intentional source slice. If generated residue exists, clean it when in scope or report it before closeout.

- [ ] **Step 6: Review final diff**

Run:

```bash
BASE_COMMIT="$(cat /tmp/ticket-modes-approval-base.txt)"
git diff --stat "$BASE_COMMIT"..HEAD
git diff "$BASE_COMMIT"..HEAD -- plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: diff is limited to mode cleanup, approval ID cleanup, mutation identity helper, runtime evaluator, pending-summary, gateway, apply-turn, and focused tests named in this plan. No maintenance helper, docs outside this control-plan revision, cache, installed runtime, local workspace state, or handoff files are staged.

- [ ] **Step 7: Record remaining drift in closeout notes**

The implementation closeout message must include these exact proof-boundary facts:

```text
Remaining product drift: `ticket_change_scope` still exists in candidate identity, gateway fingerprints, autonomous apply, and commit-disposition behavior; it is intentionally deferred to a separate source slice.
Temporary safety binding: while `ticket_change_scope` remains live, gateway validation rejects mismatches between `decision.candidate.ticket_change_scope` and `GatewayMutation.ticket_change_scope`.
Remaining product drift: the full target candidate mutation contract remains unsatisfied except for the narrower target-fingerprint identity binding implemented by this slice.
Deferred diagnostic-preview affordance: durable preview is removed; diagnostic dry-run remains unimplemented and intentionally deferred to a later maintenance/design slice. This slice adds no replacement dry-run flag, command, event, or renamed preview path.
Breaking-change posture: this source slice does not preserve removed Ticket behavior for compatibility.
Local pending-summary proof: no project-local `.codex/ticket-workspace/ticket.pending-summary.jsonl` existed at preflight; `approval_consumed` validation/recovery was deleted rather than retained.
Installed-runtime blast radius: this deletion is gated only on the current checkout having no pending-summary log. An installed runtime that still holds `approval_consumed` events would silently lose recovery for them after this slice; deciding whether installed runtimes need a one-time migration or bounded compatibility reader is named follow-up, not covered here.
Implemented safety boundary: `create` candidates intentionally use `target_fingerprint=None`; non-create candidates require a Ticket-derived target fingerprint before runtime mutation ID creation and before gateway dispatch.
Implemented approval boundary: executable approval envelope machinery is removed, including `make_approval_id`, `codex.ticket.approval`, `AutonomyDecision.approval`, gateway approval validation, `details.approval`, `approval_id`, and `approval_consumed` validation/recovery/tests.
Implemented turn-local block boundary: missing Ticket-derived target fingerprints are user-visible `ticket_update_blocked` results only, not user-discussion states or mutation attempts; other valid candidates in the same turn may still apply.
Implemented reporting boundary: end-of-turn output reports applied ticket IDs, skipped ticket IDs, blocked ticket IDs, and blocked reasons only; proposed fields, fingerprints, mutation IDs, event IDs, health-event internals, and maintenance ticket IDs stay out of the report.
Implemented skipped boundary: conflict-only skip remains `state: "skipped"` with a `Skipped` bucket; mixed applied plus skipped or blocked candidates reports `partially_applied`.
Implemented pause boundary: collector-level source-context failure pauses Ticket autonomy with `source_context_unhealthy`, not `setup_required`, uses `pause.json` as the live authority without adding a one-off `automation_pause` event, and resume requires a passing current-candidate collection or fail-closed known-ticket probe through the same collector path.
Deferred design required: recurring block maintenance escalation, `autonomy_health`, repeat thresholds, maintenance-ticket dedupe/output, and repeat-block tracking require a separate consciously authorized design before implementation.
```

Do not claim full ADR 0006 runtime compliance from this slice.

- [ ] **Step 8: Record closeout commit if final cleanup changed files**

If final verification produces cleanup edits, run:

```bash
git status --short --branch
git diff --stat -- \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py \
  plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy.py \
  plugins/turbo-mode/ticket/tests/test_mutation_identity.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_config.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_turn_batch.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_cli.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git diff -- \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py \
  plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy.py \
  plugins/turbo-mode/ticket/tests/test_mutation_identity.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_config.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_turn_batch.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_cli.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git add \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py \
  plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy.py \
  plugins/turbo-mode/ticket/tests/test_mutation_identity.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_config.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_turn_batch.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_cli.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git diff --cached --stat
git diff --cached -- \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py \
  plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy.py \
  plugins/turbo-mode/ticket/tests/test_mutation_identity.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_config.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_turn_batch.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_cli.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git commit -m "chore(ticket): verify modes approval source slice"
```

Expected: `git status --short --branch` does not show unrelated dirty work in the explicit file list. The staged diff includes only cleanup needed by verification. Do not stage whole directories.

- [ ] **Step 9: Re-review final diff after cleanup commit**

If Step 8 creates a cleanup commit, repeat the final diff review after that commit:

```bash
BASE_COMMIT="$(cat /tmp/ticket-modes-approval-base.txt)"
git diff --stat "$BASE_COMMIT"..HEAD
git diff "$BASE_COMMIT"..HEAD -- \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py \
  plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy.py \
  plugins/turbo-mode/ticket/tests/test_mutation_identity.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_config.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py \
  plugins/turbo-mode/ticket/tests/test_turn_batch.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_cli.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
```

Expected: diff is still limited to mode cleanup, approval ID cleanup, mutation identity helper, runtime evaluator, pending-summary, gateway, apply-turn, and focused tests named in this plan. No maintenance helper, docs outside this control-plan revision, cache, installed runtime, local workspace state, handoff files, or unrelated cleanup are included.

## Self-Review Checklist

Spec coverage:

- Durable `preview` config is removed in Task 1.
- Runtime `PREVIEW_ONLY` decisions and apply-turn product preview projections are removed in Task 2.
- No replacement diagnostic dry-run flag, command, event, or renamed preview path is added in this slice.
- Automatic `agent_primary` approval envelope creation is removed in Task 3, but Task 3 is not committed until Tasks 4 and 5 remove gateway and pending-summary approval consumers.
- Gateway write paths and pending-summary validation do not accept, branch on, recover, or write approval-shaped authorization fields.
- Correction integration tests pass target fingerprints through source context before expecting `APPLY_CORRECTION`.
- `ticket_mutation_identity.py` is calculation-only, independent of runtime/gateway dataclasses, and covered by focused helper tests.
- Runtime and gateway separately reject non-create writes without target fingerprints; `create` candidates intentionally use `target_fingerprint=None`; runtime classifies the per-candidate miss as `TICKET_UPDATE_BLOCKED`, not `REQUIRE_USER_DISCUSSION`, and the identity helper hashes missing target fingerprints but does not make that policy decision.
- Apply-turn handles `TICKET_UPDATE_BLOCKED` with no mutation attempt, no mutation status, no mutation ID, no pending-summary event, no health event, no discussion question, and partial-apply summary behavior when other candidates are valid.
- Partial-apply summary output includes applied ticket IDs, skipped ticket IDs, blocked ticket IDs, and blocker reasons only; it excludes proposed fields, fingerprints, mutation IDs, event IDs, health-event internals, and maintenance ticket IDs.
- Pending-summary deletes approval and preview acceptance without adding blocked-candidate event shapes.
- Repeat-block tracking, `autonomy_health`, maintenance-ticket escalation, repeat thresholds, and maintenance-ticket output are deferred to a separate authorized design.
- Apply-turn pauses collector-level source-context failures with `source_context_unhealthy` and does not classify them as `setup_required`.
- `--resume-paused` cannot clear `source_context_unhealthy` unless current-candidate collection or a fail-closed known-ticket probe through the same collector path proves source-context collection is healthy.
- `source_context_unhealthy` uses `pause.json` plus the paused response as the live proof; it does not add a unique pending-summary `automation_pause` event unless runtime pauses are proven to use that event path consistently.
- Gateway validation recomputes mutation identity through `make_candidate_mutation_identity()` and does not import private runtime identity helpers.
- Gateway approval validation and new `approval_consumed` writes are removed in Task 4.
- Pending-summary no longer requires automatic approval details or accepts new preview decisions in Task 5.
- Pending-summary no longer accepts `details.approval`, `approval_id`, `approval_consumed`, `preview_only`, or `current_mode: preview`.
- Apply-turn integration expectations are updated in Task 6 so full-suite verification does not fail late on removed approval/preview behavior.
- At least one approval-free `ticket_written` recovery test is updated in `test_autonomy_recovery.py`.
- Closeout language explicitly names remaining `ticket_change_scope`, target candidate-shape, diagnostic-preview, and private operation-log drift instead of claiming full ADR compliance.
- Closeout language includes the breaking-change posture, local pending-summary proof, turn-local block boundary, skipped boundary, and deferred maintenance-escalation design boundary.
- Mutation identity includes the Ticket-derived target fingerprint for non-create writes after Task 3, and gateway validation recomputes that identity with `GatewayMutation.target_fingerprint` after Task 4.
- Invalid durable-mode snapshots fail closed instead of falling back to writable config.
- The Consumer Inventory section is the authoritative affected-file set; every removed-machinery hit (run the inventory grep) is folded into the atomic-boundary commit, selectors, staging, and ruff lists — including `test_autonomy_ids.py`, which the original per-task lists omitted.
- The atomic approval-boundary commit (Task 5) is whole-suite green (`pytest -q`), not green-by-selector; it contains every removed-machinery consumer rewrite, and no checkpoint commits a `pytest -q`-red tree.
- A positive gateway test proves a non-duplicate `create` with `target_fingerprint=None` passes `_decision_error` and writes (Task 4), and the `source_context_unhealthy` pause/resume/known-ticket-probe behaviors have concrete test bodies (Task 6 Step 4), not prose.
- The recovery fingerprint helper is referenced by its real name `_event_with_bound_fingerprints` (with defaults preserved); the post-write `approval_consumed` recovery test is deleted as unreachable, not re-fixtured; the integration success sequence is reindexed from 4 to 3 events; both `_expected_pre_write_fingerprint` functions drop their approval reads.
- Follow-up named, not folded: de-duplicating `_mode_snapshot_error()` against `read_mode_snapshot()`'s validation, and any installed-runtime `approval_consumed` migration, are left as deferred work.

Placeholder scan:

- The plan has no open-ended implementation placeholders. Every code-changing task includes concrete snippets and focused commands. Future explicit `discussion_only` approval and recurring-block maintenance escalation are named only as deferred design work, not implemented behavior.

Type consistency:

- `AutomationMode` has only `DISCUSSION_ONLY` and `AGENT_PRIMARY` after Task 1.
- `RuntimeDecisionKind` has no `PREVIEW_ONLY` after Task 2.
- `RuntimeDecisionKind.TICKET_UPDATE_BLOCKED` is the only runtime decision kind for missing target fingerprints; `target_fingerprint_required` is not represented as discussion.
- `source_context_unhealthy` is not added to `_PAUSE_REASONS` unless a consistent runtime `automation_pause` event path is proven first; local config or mode setup continues to use setup-required paths.
- `AutonomyDecision.approval` is deleted in this slice; active docs may mention future explicit `discussion_only` approval only as deferred design, not as executable behavior.
- Gateway validation uses `AutonomyDecision`, `CandidateMutation`, `GatewayMutation`, `thread_id`, and `turn_id` fields already present in current source.
- Gateway validation recomputes the expected mutation ID from `thread_id`, `turn_id`, `decision.candidate`, and `GatewayMutation.target_fingerprint`; non-null mutation IDs are not treated as proof.
- `make_candidate_mutation_identity()` accepts primitive fields and JSON-compatible evidence, not runtime or gateway dataclasses.

## Handoff Notes For Executors

- Use `superpowers:subagent-driven-development` for implementation unless the user chooses inline execution.
- Use a fresh branch or worktree for source implementation. If creating a worktree, use `superpowers:using-git-worktrees`.
- Commit after each runnable behavior boundary when tests pass. Commit Tasks 1 and 2 together. Do not commit Task 3 by itself; the atomic approval-boundary commit (Task 5) bundles runtime approval removal, gateway decision validation, pending-summary approval/preview deletion, gateway event-sequence rewrites, **and every removed-machinery consumer test rewrite in the Consumer Inventory** (including `test_autonomy_ids.py` and the Task 6 Steps 2/5/6/7/8 cleanup). That commit must be whole-suite green (`pytest -q`), never green-by-selector. Task 6's **new** apply-turn behavior (Steps 3-4) commits separately after its focused tests. Recurring-block maintenance escalation is a separate future design.
- Do not refresh installed runtime or cache state. Source tests are the proof class for this plan.
