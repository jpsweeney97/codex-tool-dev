# Ticket Candidate Contract Migration Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sequence the Ticket target candidate contract migration through five cohesive child plans without using the original monolith as execution authority.

**Architecture:** This file is sequencing authority only. The child plans carry executable task detail for their slices, while this index preserves cross-plan order, predecessor gates, source-vs-installed-runtime boundaries, and final acceptance criteria.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Execution Authority

The original monolith is superseded for execution by these child plans, in this order:

1. `docs/superpowers/plans/2026-06-05-ticket-candidate-source-entrypoint-spine.md`
2. `docs/superpowers/plans/2026-06-05-ticket-create-idempotency-binding.md`
3. `docs/superpowers/plans/2026-06-05-ticket-reopen-blocked-cleanup-semantics.md`
4. `docs/superpowers/plans/2026-06-05-ticket-correction-recovery-facts.md`
5. `docs/superpowers/plans/2026-06-05-ticket-availability-flip-final-proof.md`

Do not execute from `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration.md`; it is retained as historical source material only.

## Sequence Gates

| Plan | Source tasks | Starts after | Ends with | Hands off |
|---|---:|---|---|---|
| 1 - Source Entrypoint Spine | 0-3 | Fresh live status, inventory, and blast-radius map | First runnable target-candidate source boundary | Create idempotency, reopen, correction/recovery, and docs availability still pending |
| 2 - Create Idempotency Binding | 3A | Plan 1 commit and Task 3 source-entrypoint tests green | Retained create allocation and create retry safety green | Reopen/lifecycle and correction/recovery still pending |
| 3 - Reopen & Blocked Cleanup Semantics | 4 | Plan 2 commit green | Reopen to `open`/`blocked`, blocked cleanup, and no normal `reopen_reason`/`Reopen History` green | Correction/recovery still pending |
| 4 - Correction & Recovery Facts | 5 | Plans 1, 2, and 3 green | Correction authorization and operation-log recovery facts green | Docs availability and final proof only |
| 5 - Availability Flip & Final Proof | 6-7 | Plans 1, 2, 3, and 4 green | Docs/skills/manifest source availability aligned and full source verification green | Installed runtime remains out of scope |

## Source And Runtime Boundary

This is a source/repo plan series only. Do not claim installed runtime proof from source files, local cache files, marketplace JSON, or source tests. Installed proof requires a separate runtime inventory lane.

Task 6 documentation changes must not start until the Task 3 source-entrypoint tests, Task 3A create-idempotency tests, Task 4 lifecycle tests, and Task 5 correction/recovery/integration tests pass in the current checkout.

## Split Baseline

- Split created from live checkout `main...origin/main [ahead 19]`, `HEAD` `c3328ffb`, with clean normal status before edits.
- The original monolith had last reviewed source baseline notes through `HEAD` `18d40178`; every child plan still requires fresh `git status --short --branch` and `git rev-parse --short HEAD` before execution.

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

## Parent Execution Handoff

Plan splitting is complete when this index, the five child plans, and the superseded monolith banner are committed. Implementation of the migration is complete only after all five child plans finish, their required commits exist, and the acceptance criteria plus final verification commands pass from the current checkout.
