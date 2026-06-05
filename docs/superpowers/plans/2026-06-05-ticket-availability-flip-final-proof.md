# Ticket Availability Flip Final Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flip current-facing Ticket docs, skills, terms, and manifest from source-entrypoint-unavailable wording to source-truthful target-candidate availability, then prove the completed source migration.

**Architecture:** This slice is certification and source documentation only. It updates docs after source behavior is already green, then runs focused candidate-contract tests, residue/construction-site checks, the full Ticket suite, ruff, and `git diff --check`.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Parent And Successor Gates

- Parent index: `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md`.
- Required predecessors: source entrypoint spine, create idempotency binding, reopen/blocked cleanup semantics, and correction/recovery facts committed and green.
- Ends after Task 6 docs commit and Task 7 final verification. Commit the plan closeout only if this plan changes during execution.
- Installed runtime refresh, cache mutation, and app-server proof remain out of scope.

## Slice Scope

This plan owns Tasks 6-7 from the superseded monolith plus final acceptance checking from the parent index.

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
3A create-idempotency tests, Task 4 reopen/change-history tests, and Task 5
correction/recovery/integration tests pass, including
`plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`. Record the Plan 3
commit hash and the Task 4 Step 7 reopen/change-history selector output before
docs-contract RED/PASS or the docs availability commit.
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
git add docs/superpowers/plans/2026-06-05-ticket-availability-flip-final-proof.md docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md
git commit -m "docs(ticket): close candidate contract migration plan"
```

Expected: commit succeeds only if this plan or the parent index changed during execution. If neither changed, do not create an empty commit.

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

## Slice Handoff

After Task 7, report the focused test output, residue/construction-site classification, full Ticket suite result, ruff result, `git diff --check` result, final status, and final commit hash if a closeout commit was needed.
