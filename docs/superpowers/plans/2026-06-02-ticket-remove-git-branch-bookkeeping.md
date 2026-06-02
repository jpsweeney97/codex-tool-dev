# Ticket Git/Branch Bookkeeping Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Ticket's git/branch bookkeeping residue from source mutation paths so Ticket writes ticket state only, while naming the remaining ADR 0006 drift explicitly.

**Architecture:** This is a source-only ADR-drift slice. It removes `ticket_change_scope`, commit coordination side effects, `commit_disposition` private-log facts, and `commit_dispositions` success output from the autonomous gateway/apply-turn path and the transitional manual/source surfaces that still preserve the behavior. It keeps deterministic ticket-file recovery facts such as pre/post fingerprints and summary receipts, and it does not implement the full target candidate contract, ticket-file cutover, diagnostic dry-run, or Change History grammar slice. ADR 0006 and the May 30 control doc name a read-only `docs/tickets/` cutover inventory as the next cutover step; this plan intentionally takes an orthogonal source-deprecation slice before that inventory because the targeted source behavior is already deprecated and no ticket-file normalization or runtime cache mutation is required. Because `ticket_change_scope` crosses candidate discovery, runtime identity, gateway validation, apply-turn dispatch, and commit coordination, Tasks 1 through 4 are one atomic source behavior boundary: do not commit a checkpoint where producers no longer expose scope while consumers still require it.

**Tech Stack:** Python >=3.11, dataclasses, pytest, ruff, existing Ticket scripts, bytecode-safe `uv run` verification.

---

## Scope Check

This plan covers one coherent subsystem: Ticket git/branch bookkeeping inside the Ticket source package.

In scope:

- Remove `ticket_change_scope` from `CandidateMutation`, candidate discovery, mutation identity payloads, gateway mutation validation, apply-turn dispatch, tests, and active source-authority docs if any active doc still presents it as current behavior.
- Remove `ticket_commit_coordinator.py` and its feature tests because commit coordination is deprecated behavior, not compatibility surface.
- Remove `record_ticket_commit_disposition()` call paths from autonomous gateway writes.
- Remove `commit_disposition`, `commit_hash`, `commit_reason`, and `commit_dispositions` from pending-summary validation/recovery, gateway events, response data, CLI output, and tests.
- Keep ticket-file write recovery facts: candidate identity, action, ticket ID, target fields/sections when already available, expected pre-write fingerprint, post-write fingerprint, write-completed state, summary-emitted state, pause/failure reason, timestamp, and bounded correction detail.
- Treat active README/HANDBOOK/contract content as source authority and patch only active target/current-behavior sections that still present commit coordination or branch scope as current behavior.

Out of scope:

- Installed plugin cache refresh or runtime inventory. Do not mutate `/Users/jp/.codex/plugins/cache`.
- Full target candidate mutation contract enforcement, including rejecting every unknown candidate field. For this slice, deprecated `ticket_change_scope` in input is ignored and does not affect runtime state; full unknown-field rejection remains a later candidate-contract slice.
- Ticket-file normalization, cutover inventory, status/priority migration, and canonical path enforcement.
- Diagnostic dry-run or preview replacement.
- `Change History` grammar cleanup, including whether `prior_commit` in `ticket_change_history.py` remains valid. Do not edit `ticket_change_history.py` for `prior_commit` in this slice.
- Historical rewrites of superseded specs or completed plans. `docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md` and `docs/superpowers/plans/2026-05-31-ticket-runtime-first-modes-approval.md` may keep historical references if they are clearly subordinate to ADR 0006 and the May 30 control doc.

Closeout claim for this plan:

```text
This specific ADR drift is removed: Ticket no longer tracks branch scope, commit coordination, or commit disposition in source mutation paths. Remaining ADR drift includes the full target candidate contract, ticket-file cutover/normalization, diagnostic dry-run, response-envelope cleanup beyond this source slice, Change History grammar, and old workflow architecture not touched by this slice.
```

## Authority And Current Source Facts

Primary authority:

- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` says Ticket is a deterministic state kernel and "does not track git commit disposition."
- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` deprecates `commit-disposition` and `ticket_change_scope` fields, plus permanent compatibility tests/docs for old architecture.
- `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md` says the private operation log must not retain commit disposition or `ticket_change_scope`.
- ADR 0006 and the May 30 control doc prescribe a read-only `docs/tickets/` cutover inventory as the next cutover step. They do not require source git/branch bookkeeping removal to wait for that inventory.
- The same control doc says older README, handbook, contract text, source comments, and tests must be patched or superseded when they conflict with ADR 0006.

Current source inventory from 2026-06-02:

```bash
rg -n "ticket_change_scope|commit_disposition|commit_hash|commit_reason|record_ticket_commit_disposition|ticket_commit_coordinator|commit coordination|commit_dispositions|commit_recorded|commit_bundled_with_work|commit_deferred" \
  plugins/turbo-mode/ticket docs/decisions docs/superpowers/specs docs/audits docs/superpowers/plans
```

Important live source hits:

- `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py` stages and commits ticket files.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py` imports commit coordinator symbols, stores `ticket_change_scope` on `GatewayMutation`, validates scope matches, calls `record_ticket_commit_disposition()`, and appends applied events with commit-disposition details.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py` collects `commit_dispositions` for success output and passes `ticket_change_scope` into gateway mutations.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` accepts finite commit-disposition values, requires `commit_disposition` on applied mutation statuses, and generates recovery events containing `commit_disposition`.
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py` hashes `ticket_change_scope` into candidate mutation identity.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` stores `ticket_change_scope` on `CandidateMutation`.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py` reads structured candidate `ticket_change_scope`.
- `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py` is a default-reliant
  live correction-flow consumer: it constructs `CandidateMutation` and
  `GatewayMutation` without deprecated kwargs, then drives
  `apply_autonomous_mutation()` with `action="correction"`. It will not appear in
  simple removed-token greps but belongs in the affected selectors.
- `plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py` preserves commit coordination as a feature and should be deleted.

Expected side effect:

- Removing `ticket_change_scope` from the canonical mutation payload changes
  mutation fingerprints and mutation IDs for current candidate shapes. Gateway
  write-lock filenames can also change for `create` mutations, and for any
  malformed non-create mutation that reaches lock acquisition without a ticket ID,
  because those lock keys fall back to the mutation fingerprint. This is accepted
  in this slice because no tests pin literal mutation IDs or lock filenames, and
  valid non-create write safety still depends on Ticket-derived target
  fingerprints.

## File Structure

Modify:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
  - Remove `TicketChangeScope` and the `CandidateMutation.ticket_change_scope` field.
  - Keep target-fingerprint identity binding for non-create writes.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
  - Stop reading `ticket_change_scope`.
  - Ignore deprecated input fields by omission; do not add full unknown-field rejection here.
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
  - Remove `ticket_change_scope` from `candidate_mutation_payload()` and `make_candidate_mutation_identity()`.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
  - Remove commit-coordinator imports, scope validation, scope payload fields, and commit-disposition recording.
  - Keep deterministic decision/mutation matching by ticket ID, action, proposed change, mutation ID, and target fingerprint.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
  - Reject prohibited git/branch bookkeeping details.
  - Stop requiring commit disposition for `applied`.
  - Generate recovery `applied` events with empty details.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
  - Stop collecting `commit_dispositions`.
  - Keep success output ticket-centered: affected ticket IDs only.
- `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
  - Replace positive `ticket_change_scope` coverage with deprecated-input-ignore coverage.
- `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
  - Replace scope-binding coverage with "payload excludes branch scope" coverage.
- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
  - Remove `TicketChangeScope` imports/helper arguments and temporary "until scope slice" tests.
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
  - Remove scope mismatch and commit-disposition tests.
  - Add negative proof that gateway no longer imports commit coordination.
- `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
  - Remove commit-disposition fixtures as valid events.
  - Add prohibited-detail rejection coverage.
- `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
  - Remove `commit_dispositions` success-output assertions.
- `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
  - Remove event/output commit-disposition assertions.
- `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
  - Include in the atomic and focused verification selectors as a default-reliant
    correction gateway consumer. Do not edit it unless the selector exposes a
    real correction-flow break.
- `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
  - Replace recovery commit-disposition assertions with empty applied-detail assertions.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
  - Add active-doc negative coverage only if active docs need it for this slice.

Delete:

- `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py`
- `plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py`

Do not modify:

- `/Users/jp/.codex/plugins/cache`
- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py` for `prior_commit`
- `docs/tickets/`
- Historical handoffs

## Atomic Source Boundary

Tasks 1 through 4 remove one shared runtime surface. They may be executed as
separate TDD work blocks, but they must be committed as one source behavior
commit after the full affected selector in Task 4 passes.

Do not create separate commits after Task 1, Task 2, or Task 3. Those
intermediate states are intentionally incomplete because later consumers still
depend on fields or behavior removed earlier in the task order. In particular:

- Removing `CandidateMutation.ticket_change_scope` and the identity-helper
  parameter in Task 1 must land in the same commit as the gateway and apply-turn
  consumer updates in Tasks 2 and 4.
- Removing gateway commit coordination in Task 2 must land in the same commit as
  pending-summary validation changes in Task 3 and integration-test output
  rewrites in Task 4, because Task 2 changes gateway `applied` events to
  `details={}` while the old pending-summary validator still rejects applied
  events without `commit_disposition`.
- Removing pending-summary commit-disposition validation in Task 3 must land in
  the same commit as gateway/apply-turn output removal, so recovery, event
  validation, and user output agree.

Task 5 remains a separate docs/static-guard commit unless Task 4 uncovers an
active authority-doc contradiction that must be patched before source execution
continues.

## Stop Conditions

Stop before source edits if:

- `git status --short --branch` shows tracked dirty files outside this plan.
- ADR 0006 or the May 30 control doc no longer deprecates `commit-disposition`,
  `ticket_change_scope`, or commit-coordination facts, or now makes source
  bookkeeping removal contingent on the read-only `docs/tickets/` cutover
  inventory landing first.
- The inventory shows active non-Ticket code depends on `record_ticket_commit_disposition()`.
- Any needed operation would mutate installed plugin cache or live runtime state.

Stop during implementation if:

- A non-create gateway write can pass without a target fingerprint.
- Removing `ticket_change_scope` also removes target-fingerprint identity binding.
- A blocked missing-target-fingerprint candidate writes a private mutation event.
- A gateway write still stages files, creates commits, shells out to `git commit`, or imports `ticket_commit_coordinator`.
- Pending-summary validation still accepts `commit_disposition`, `commit_hash`, `commit_reason`, or `ticket_change_scope` in event details.
- Success output includes file paths, fingerprints, mutation IDs, event IDs, commit hashes, commit disposition, or write mechanics instead of affected ticket IDs.
- Failure output loses useful repair evidence such as path, validation detail, candidate identity, or fingerprints where existing tests require it.
- The implementation tries to solve full target candidate shape, cutover normalization, diagnostic dry-run, or `Change History` grammar as part of this slice.

## Task 0: Preflight Inventory And Baseline

**Files:**

- Read: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`

- [ ] **Step 1: Confirm branch and cleanliness**

Run:

```bash
git status --short --branch
```

Expected: current branch is `chore/ticket-runtime-first-rebaseline-adr` or the execution branch created for this plan, with no unrelated tracked dirty files.

- [ ] **Step 2: Re-read authority docs**

Run:

```bash
sed -n '1,220p' docs/decisions/0006-ticket-runtime-first-state-kernel.md
sed -n '1,260p' docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md
```

Expected: ADR 0006 still says Ticket does not track git commit disposition, and the control doc still prohibits private-log `commit_disposition` and `ticket_change_scope`.

- [ ] **Step 3: Run the source inventory**

Run:

```bash
rg -n "ticket_change_scope|commit_disposition|commit_hash|commit_reason|record_ticket_commit_disposition|ticket_commit_coordinator|commit coordination|commit_dispositions|commit_recorded|commit_bundled_with_work|commit_deferred" \
  plugins/turbo-mode/ticket docs/decisions docs/superpowers/specs docs/audits docs/superpowers/plans
```

Expected: hits are assignable to source behavior, tests preserving deprecated behavior, active authority docs, historical/superseded docs, historical/superseded plans, historical audits, or this plan. If a new active source path outside the files listed in this plan appears, add it to the relevant task before editing.

- [ ] **Step 4: Run a narrow baseline selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_candidate_discovery.py tests/test_autonomy_runtime.py tests/test_engine_gateway.py tests/test_turn_batch.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py tests/test_autonomy_corrections.py tests/test_autonomy_recovery.py -q
```

Expected: PASS on current source. If it fails, stop and diagnose before making this slice look responsible for pre-existing failures.

## Task 1: Remove `ticket_change_scope` From Candidate And Identity State

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`

- [ ] **Step 1: Write failing identity tests**

In `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`, replace the helper and scope-binding test with:

```python
from scripts.ticket_mutation_identity import (
    candidate_mutation_payload,
    make_candidate_mutation_identity,
)


def _identity(*, target_fingerprint: str | None = "ticket-state-a"):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        proposed_change={"priority": "high"},
        target_fingerprint=target_fingerprint,
        evidence=(
            {"kind": "current_thread_reason", "ref": "test", "freshness": "fresh"},
        ),
    )


def test_candidate_payload_excludes_branch_scope() -> None:
    payload = candidate_mutation_payload(
        ticket_id="T-20260527-01",
        action="update",
        proposed_change={"priority": "high"},
        target_fingerprint="ticket-state-a",
    )

    assert payload == {
        "ticket_id": "T-20260527-01",
        "action": "update",
        "proposed_change": {"priority": "high"},
        "target_fingerprint": "ticket-state-a",
    }
```

Keep the existing target-fingerprint tests, updated to call `_identity()` without `ticket_change_scope`.

- [ ] **Step 2: Write failing candidate discovery/runtime tests**

In `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`, update
`test_discovers_explicit_candidate_mutations()` by replacing the old branch-scope
assertion:

```python
    assert candidates[0].ticket_change_scope == "current_branch"
```

with:

```python
    assert not hasattr(candidates[0], "ticket_change_scope")
```

Replace `test_structured_candidates_may_supply_bounded_ticket_change_scope()` with:

```python
def test_structured_candidates_ignore_deprecated_ticket_change_scope(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "proposed_change": {"priority": "high"},
                "ticket_change_scope": "unrelated_backlog",
            }
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 1
    assert candidates[0].ticket_id == "T-20260527-01"
    assert candidates[0].proposed_change == {"priority": "high"}
    assert not hasattr(candidates[0], "ticket_change_scope")
```

In `test_matches_related_paths_against_ticket_metadata()`, replace the final
branch-scope assertion:

```python
    assert {candidate.ticket_change_scope for candidate in candidates} == {"current_branch"}
```

with:

```python
    assert not any(hasattr(candidate, "ticket_change_scope") for candidate in candidates)
```

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, remove
`TicketChangeScope` from the import block and rewrite `_candidate()` so it no
longer accepts or passes `ticket_change_scope`:

```python
def _candidate(
    action: str,
    *,
    ticket_id: str = "T-20260527-01",
    proposed_change: dict[str, object] | None = None,
    evidence: tuple[EvidenceLink, ...] | None = None,
    conflict_reason: str | None = None,
) -> CandidateMutation:
    change = {"field": "value"} if proposed_change is None else proposed_change
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=change,
        evidence=evidence or _evidence("current_thread_reason"),
        conflict_reason=conflict_reason,
    )
```

Replace `test_ticket_change_scope_still_binds_mutation_identity_until_scope_slice()` with:

```python
def test_candidate_mutation_has_no_ticket_change_scope_field() -> None:
    candidate = _candidate("update")

    assert not hasattr(candidate, "ticket_change_scope")
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_candidate_discovery.py tests/test_autonomy_runtime.py -q
```

Expected: FAIL before source edits because the identity helper still requires `ticket_change_scope` and `CandidateMutation` still exposes `ticket_change_scope`.

- [ ] **Step 4: Remove scope from runtime and identity source**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, remove `TicketChangeScope` and define `CandidateMutation` as:

```python
@dataclass(frozen=True, slots=True)
class CandidateMutation:
    """A proposed Ticket mutation candidate."""

    ticket_id: str | None
    action: str
    proposed_change: Mapping[str, object]
    evidence: tuple[EvidenceLink, ...]
    conflict_reason: str | None = None
```

Update `_identity_for_candidate()` to:

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
        target_fingerprint=target_fingerprint,
        evidence=_evidence_payload(candidate),
    )
```

In `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`, replace the two public helpers with:

```python
def candidate_mutation_payload(
    *,
    ticket_id: str | None,
    action: str,
    proposed_change: Mapping[str, object],
    target_fingerprint: str | None,
) -> dict[str, object]:
    """Return the canonical payload used for mutation identity."""
    return {
        "ticket_id": ticket_id,
        "action": action,
        "proposed_change": dict(proposed_change),
        "target_fingerprint": target_fingerprint,
    }


def make_candidate_mutation_identity(
    *,
    thread_id: str,
    turn_id: str,
    ticket_id: str | None,
    action: str,
    proposed_change: Mapping[str, object],
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

- [ ] **Step 5: Stop reading scope in candidate discovery**

In `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`, remove `TicketChangeScope` from the import, delete `_ticket_change_scope()`, delete the local `ticket_change_scope = ...` assignment, and construct candidates without the field:

```python
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=normalized_change,
        evidence=evidence,
        conflict_reason=conflict_reason if isinstance(conflict_reason, str) else None,
    )
```

- [ ] **Step 6: Run the Task 1 selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_candidate_discovery.py tests/test_autonomy_runtime.py -q
```

Expected: PASS for the Task 1-local selector. Do not commit yet. Gateway and
apply-turn consumers still depend on the removed field until Tasks 2 and 4 land
in the same atomic source behavior commit.

- [ ] **Step 7: Checkpoint Task 1 without committing**

Run:

```bash
git diff -- plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py
```

Expected: diff shows only Task 1 edits. Leave the worktree dirty and continue
to Task 2.

## Task 2: Remove Gateway Commit Coordination And Delete The Coordinator

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Delete: `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py`
- Delete: `plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py`

- [ ] **Step 1: Write failing gateway tests**

In `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`, remove `TicketChangeScope` imports and helper parameters. Update `_decision_for()` and `_mutation()` so neither accepts nor passes `ticket_change_scope`.

In `test_gateway_rejects_non_autonomous_or_mismatched_decisions()`, delete the mismatched-scope case and keep the ticket, action, fields, fingerprint, and forged-ID assertions.

Add this negative import test near the other gateway tests:

```python
def test_gateway_does_not_import_commit_coordination() -> None:
    source = Path(gateway.__file__).read_text(encoding="utf-8")

    assert "ticket_commit_coordinator" not in source
    assert "record_ticket_commit_disposition" not in source
    assert "CommitDispositionRecord" not in source
```

In `test_gateway_applies_update_records_events_and_writes_change_history()`, replace commit-disposition assertions with:

```python
    assert events[-1]["details"] == {}
    assert "commit_disposition" not in response.data
    assert "commit_hash" not in response.data
    assert "commit_reason" not in response.data
```

Delete `test_gateway_passes_ticket_change_scope_to_commit_disposition()`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py -q
```

Expected: FAIL before source edits because gateway still imports commit coordination and still writes commit-disposition details.

- [ ] **Step 3: Remove scope and commit coordination from gateway source**

In `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`, delete the import block for `scripts.ticket_commit_coordinator`.

Replace `GatewayMutation` with:

```python
@dataclass(frozen=True, slots=True)
class GatewayMutation:
    """Gateway-owned mutation request."""

    action: str
    ticket_id: str | None
    fields: Mapping[str, object]
    tickets_dir: Path
    target_fingerprint: str | None
```

Replace `_mutation_fingerprint()` with:

```python
def _mutation_fingerprint(mutation: GatewayMutation) -> str:
    return sha256_fingerprint(
        {
            "ticket_id": mutation.ticket_id,
            "action": mutation.action,
            "proposed_change": dict(mutation.fields),
        }
    )
```

Replace `build_engine_dispatch()` with:

```python
def build_engine_dispatch(mutation: GatewayMutation) -> EngineDispatch:
    """Build deterministic engine dispatch for a gateway mutation."""
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        proposed_change=dict(mutation.fields),
        evidence=(),
    )
    return map_candidate_to_engine(candidate)
```

In `_decision_error()`, remove the `ticket_change_scope_mismatch` block and call identity without scope:

```python
    identity = make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        ticket_id=decision.candidate.ticket_id,
        action=decision.candidate.action,
        proposed_change=decision.candidate.proposed_change,
        target_fingerprint=mutation.target_fingerprint,
        evidence=_candidate_evidence_payload(decision.candidate),
    )
```

Delete `_record_commit_disposition()` and `_commit_disposition_details()`.

After `ticket_written_error`, replace the commit-recording block and `applied` append with:

```python
    applied_error = _append_gateway_event(
        pending_summary=pending_summary,
        event_type="mutation_status",
        status="applied",
        mutation=mutation,
        decision=decision,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason="Autonomous Ticket mutation applied.",
        details={},
    )
    if applied_error is not None:
        return applied_error

    return response
```

- [ ] **Step 4: Delete deprecated coordinator files**

Run:

```bash
trash plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py
```

Expected: files move to Trash and `git status --short` shows them as deleted.

- [ ] **Step 5: Run the Task 2 interim selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py -q
```

Expected: FAIL after Task 2 source edits because `tests/test_engine_gateway.py`
now expects the gateway to append `applied` events with `details={}`, while
`plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` still requires
`details.commit_disposition` until Task 3. Do not treat this as a blocker, and
do not weaken the gateway assertion. Leave the worktree dirty and continue to
Task 3, where the combined gateway/pending-summary selector becomes green.

- [ ] **Step 6: Checkpoint Task 2 without committing**

Run:

```bash
git diff -- plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py
git status --short plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py
```

Expected: diff shows Task 2 gateway/test edits, and `git status --short` shows
the coordinator source and test as deleted. Leave the worktree dirty and
continue to Task 3.

## Task 3: Remove Commit Disposition From Pending-Summary Validation And Recovery

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`

- [ ] **Step 1: Write failing pending-summary tests**

In `plugins/turbo-mode/ticket/tests/test_turn_batch.py`, change the applied fixture from the current commit-disposition-bearing row:

```python
        "applied": {"commit_disposition": "commit_deferred"},
```

to:

```python
    details_by_status: dict[str, dict[str, object]] = {
        "ticket_written": {"post_write_fingerprint": "post-fp"},
        "applied": {},
        "discussion_required": {"question": "Which ticket should be updated?"},
        "deferred": {"retry_condition": "branch is clean"},
        "failed": {"error_code": "policy_blocked"},
    }
```

Delete the old `test_finite_values()` row that treats `commit_disposition` as a
finite value:

```python
        ("details", {"commit_disposition": "unknown"}, "commit_disposition"),
```

Delete the old `test_status_details_requirements()` row that treats
`commit_disposition` as required applied-event detail:

```python
        (valid_status_event("applied", commit_disposition=""), "commit_disposition"),
```

In the same edit, add this dedicated prohibited-detail test. Do not split this
test from the fixture change above: while the old applied fixture still injects
`commit_disposition`, the `commit_hash`, `commit_reason`, and
`ticket_change_scope` rows can fail on the old injected detail instead of the row
key being tested.

```python
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("commit_disposition", "commit_deferred"),
        ("commit_hash", "abc123"),
        ("commit_reason", "Containing work commit was not supplied."),
        ("ticket_change_scope", "current_branch"),
    ],
)
def test_git_branch_bookkeeping_details_are_not_supported(
    key: str,
    value: object,
) -> None:
    event = valid_status_event("applied", **{key: value})

    assert_invalid(event, key)
```

- [ ] **Step 2: Write failing recovery tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`, replace assertions that expect recovered applied details to include `commit_disposition` with:

```python
    assert projection.events_to_append[1]["details"] == {}
```

For terminal-status recovery from `ticket_written`, assert:

```python
    assert projection.events_to_append[0]["details"] == {}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py tests/test_autonomy_recovery.py -q
```

Expected: FAIL before source edits. The `commit_disposition` row fails because
validation still requires and finite-checks commit-disposition details, while
the `commit_hash`, `commit_reason`, and `ticket_change_scope` rows fail because
the validator does not yet reject those prohibited details. Recovery assertions
also fail because recovery still emits commit-disposition details.

- [ ] **Step 4: Remove commit-disposition validation from pending summary**

In `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`, delete `_COMMIT_DISPOSITIONS`.

Add this constant near `_PAUSE_REASONS`:

```python
_PROHIBITED_DETAILS = frozenset(
    {
        "commit_disposition",
        "commit_hash",
        "commit_reason",
        "ticket_change_scope",
    }
)
```

Replace `_validate_finite_details()` with:

```python
def _validate_finite_details(details: Mapping[str, object]) -> ValidationResult:
    for key in _PROHIBITED_DETAILS:
        if key in details:
            return _invalid(f"{key} is not supported")
    finite_checks = (
        ("decision", _DECISIONS),
        ("current_mode", _MODES),
        ("evidence_kind", _EVIDENCE_KINDS),
        ("pause_reason", _PAUSE_REASONS),
    )
    for key, allowed in finite_checks:
        if key in details and details[key] not in allowed:
            return _invalid(f"{key} is not supported")
    return _ok()
```

In `_validate_details()`, delete the whole `if status == "applied" and action in _ACTIONS:` block.

- [ ] **Step 5: Remove commit-disposition recovery details**

In `project_mutation_recovery()`, change both recovered `applied` events to use empty details:

```python
                _recovery_event(
                    reference=reference,
                    event_type="mutation_status",
                    status="applied",
                    reason="Recovered autonomous Ticket terminal status.",
                    details={},
                ),
```

- [ ] **Step 6: Run the Task 2+3 selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py tests/test_turn_batch.py tests/test_autonomy_recovery.py -q
```

Expected: PASS for the combined Task 2+3 selector. This is the first checkpoint
where Task 2's gateway `details={}` assertion can be green because Task 3 has
removed the old pending-summary `commit_disposition` requirement. Do not commit
yet. Gateway, pending-summary recovery, and apply-turn output must land together
in the Task 4 atomic source behavior commit.

- [ ] **Step 7: Checkpoint Task 3 without committing**

Run:

```bash
git diff -- plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
```

Expected: diff shows only Task 3 pending-summary/recovery edits. Leave the
worktree dirty and continue to Task 4.

## Task 4: Remove Commit Disposition From Apply-Turn Output And Integration Fixtures

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Test only: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`

- [ ] **Step 1: Write failing output tests**

In
`plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py::test_agent_primary_apply_turn_applies_update_through_gateway`,
replace the old commit-disposition and git-commit assertions:

```python
    assert events[2]["details"]["commit_disposition"] == "commit_recorded"
    assert events[2]["details"]["commit_hash"] == _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert payload["commit_dispositions"] == [
        {
            "ticket_id": "T-20260527-01",
            "disposition": "commit_recorded",
            "commit_hash": events[2]["details"]["commit_hash"],
        }
    ]
    assert _git(tmp_path, "show", "--name-only", "--format=", "HEAD").stdout.splitlines() == [
        "docs/tickets/one.md"
    ]
```

with:

```python
    assert events[2]["status"] == "applied"
    assert events[2]["details"] == {}
    assert payload["ticket_updates"] == {"Applied": ["T-20260527-01"]}
    assert "commit_dispositions" not in payload
```

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`, replace any assertion that indexes `payload["commit_dispositions"]` with:

```python
    assert "commit_dispositions" not in payload
```

After the integration assertion rewrite, delete the now-unused `_git()` helper
from `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`:

```python
def _git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py -q
```

Expected: FAIL before source edits after Tasks 1 through 3 have already changed
the shared types and gateway. The likely first failure is an attribute error or
constructor mismatch from the old apply-turn code still passing
`ticket_change_scope=decision.candidate.ticket_change_scope` into
`GatewayMutation`; after that call site is removed, the output assertions stay
red until `commit_dispositions` collection and emission are deleted.

- [ ] **Step 3: Remove commit-disposition output code**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`, change `_summary_payload()` signature to remove `commit_dispositions`:

```python
def _summary_payload(
    *,
    applied: list[str],
    skipped: list[str],
    blocked: list[str],
    discussion: list[str],
    discussion_question: str | None,
    blocked_reasons: dict[str, str],
) -> dict[str, Any]:
```

Inside `_summary_payload()`, delete:

```python
    if commit_dispositions:
        payload["commit_dispositions"] = commit_dispositions
```

Delete `_commit_disposition_summary()`.

In `_run_apply_turn_with_mode()`, delete:

```python
    commit_dispositions: list[dict[str, object]] = []
```

When constructing `GatewayMutation`, remove `ticket_change_scope=decision.candidate.ticket_change_scope`.

Inside the existing successful gateway response branch, delete only the
`commit_summary` lines:

```python
                commit_summary = _commit_disposition_summary(ticket_id, response.data)
                if commit_summary is not None:
                    commit_dispositions.append(commit_summary)
```

Keep the surrounding `if` and `else` flow intact:

```python
            if response.state.startswith("ok_"):
                applied.append(ticket_id)
            else:
                discussion.append(ticket_id)
                discussion_question = discussion_question or response.message
```

When emitting summary payload, call:

```python
        _summary_payload(
            applied=applied,
            skipped=skipped,
            blocked=blocked,
            discussion=discussion,
            discussion_question=discussion_question,
            blocked_reasons=blocked_reasons,
        )
```

- [ ] **Step 4: Run the atomic source boundary selector**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_candidate_discovery.py tests/test_autonomy_runtime.py tests/test_engine_gateway.py tests/test_turn_batch.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py tests/test_autonomy_corrections.py tests/test_autonomy_recovery.py -q
```

Expected: PASS. This is the first source behavior commit gate for Tasks 1
through 4; do not commit before this selector is green.

- [ ] **Step 5: Commit Tasks 1 through 4 atomically**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py
git add plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git add -u plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py
git commit -m "fix(ticket): remove git branch bookkeeping from mutation paths"
```

Expected: one atomic source behavior commit succeeds. The commit contains Tasks
1 through 4 only: source mutation-path changes, focused tests, and deletion of
the deprecated commit coordinator source/test.

## Task 5: Patch Active Source Authority And Static Contract Tests

**Files:**

- Modify if needed: `plugins/turbo-mode/ticket/README.md`
- Modify if needed: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify if needed: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Inventory active authority docs**

Run:

```bash
rg -n "ticket_change_scope|commit_disposition|commit_hash|commit_reason|commit_dispositions|commit coordination|commit_recorded|commit_bundled_with_work|commit_deferred" \
  plugins/turbo-mode/ticket/README.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/references \
  plugins/turbo-mode/ticket/skills
```

Expected: no active target/current-behavior doc presents branch scope or commit coordination as supported behavior. If a hit appears in `Deprecated Source Drift`, `Legacy Cutover Input`, `Historical Changelog`, or `Maintenance And Diagnostics`, classify it as historical/diagnostic and leave it unless the wording presents old behavior as current target behavior.

Known gap to classify, not silently ignore: active target-candidate docs may
still say unknown fields are invalid while this source slice intentionally only
ignores deprecated `ticket_change_scope` input and defers full unknown-field
rejection. If those docs remain otherwise current, mention this as part of the
remaining full target candidate contract drift instead of expanding this slice.

- [ ] **Step 2: Add static active-doc negative coverage**

In `plugins/turbo-mode/ticket/tests/test_docs_contract.py`, remove the
`ticket_change_scope` entry from `OLD_SCHEMA_TERMS` and add a separate
git/branch-bookkeeping term list:

```python
GIT_BRANCH_BOOKKEEPING_TERMS = (
    "`ticket_change_scope`",
    "`commit_disposition`",
    "`commit_hash`",
    "`commit_reason`",
    "`commit_dispositions`",
    "commit coordination",
    "commit_recorded",
    "commit_bundled_with_work",
    "commit_deferred",
)


def test_core_docs_do_not_present_git_branch_bookkeeping_as_target_behavior() -> None:
    for path in CORE_AUTHORITY_DOCS:
        text = _read_text(path)
        target = _target_sections(text)
        normalized_target = _normalize_whitespace(target)
        for term in GIT_BRANCH_BOOKKEEPING_TERMS:
            assert term not in normalized_target
```

If this test fails because an active target section contains an old term, edit that active doc section to remove the target/current-behavior claim. Do not rewrite superseded historical specs.

- [ ] **Step 3: Run docs tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
```

Expected: PASS after any active-doc patch.

- [ ] **Step 4: Commit Task 5**

If only the static test changed, run:

```bash
git add plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "test(ticket): guard against git branch bookkeeping docs drift"
```

If active docs also changed, run:

```bash
git add plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "docs(ticket): remove git branch bookkeeping authority"
```

Expected: exactly one Task 5 commit succeeds.

## Task 6: Boundary Inventory, Full Verification, And Closeout

**Files:**

- Read: all changed files
- No new source files unless a focused test failure identifies a missing consumer

- [ ] **Step 1: Run residue inventory**

Run:

```bash
rg -n "ticket_change_scope|commit_disposition|commit_hash|commit_reason|record_ticket_commit_disposition|ticket_commit_coordinator|commit coordination|commit_dispositions|commit_recorded|commit_bundled_with_work|commit_deferred" \
  plugins/turbo-mode/ticket docs/decisions docs/superpowers/specs docs/audits docs/superpowers/plans
```

Expected:

- No hits in `plugins/turbo-mode/ticket/scripts` except the deliberate
  `_PROHIBITED_DETAILS` guard literals in
  `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`: the literal strings
  `commit_disposition`, `commit_hash`, `commit_reason`, and
  `ticket_change_scope`.
- No feature-preserving hits in `plugins/turbo-mode/ticket/tests`. Expected
  allowed test hits are limited to:
  - `plugins/turbo-mode/ticket/tests/test_turn_batch.py`, in the negative
    `test_git_branch_bookkeeping_details_are_not_supported` coverage and
    supporting prohibited-detail literals.
  - `plugins/turbo-mode/ticket/tests/test_docs_contract.py`, in the
    `GIT_BRANCH_BOOKKEEPING_TERMS` static guard.
  - `plugins/turbo-mode/ticket/tests/test_change_history.py`, for the
    out-of-scope `test_helper_does_not_write_containing_commit_hash` helper
    behavior that this slice intentionally leaves alone.
- Allowed hits only in ADR/control docs, this plan, superseded historical docs,
  historical audits, completed plans, or deliberate negative tests.

- [ ] **Step 2: Run focused Ticket selectors**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_mutation_identity.py tests/test_candidate_discovery.py tests/test_autonomy_runtime.py tests/test_engine_gateway.py tests/test_turn_batch.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py tests/test_autonomy_corrections.py tests/test_autonomy_recovery.py tests/test_docs_contract.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full Ticket suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: PASS. If warning counts remain, report them without claiming they are new unless the output proves they are new.

- [ ] **Step 4: Run ruff on changed Python files**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py \
  plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py \
  plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py \
  plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py \
  plugins/turbo-mode/ticket/scripts/ticket_autonomy.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py \
  plugins/turbo-mode/ticket/tests/test_candidate_discovery.py \
  plugins/turbo-mode/ticket/tests/test_mutation_identity.py \
  plugins/turbo-mode/ticket/tests/test_engine_gateway.py \
  plugins/turbo-mode/ticket/tests/test_turn_batch.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_cli.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py \
  plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py
```

Expected: PASS.

- [ ] **Step 5: Run diff and residue checks**

Run:

```bash
git diff --check
git diff --cached --check
find plugins/turbo-mode/ticket -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .DS_Store
```

Expected: diff checks pass. Residue command prints nothing. If the residue command prints `plugins/turbo-mode/ticket/.pytest_cache`, run `trash plugins/turbo-mode/ticket/.pytest_cache` and re-run the residue command. If it prints any other path, stop and add the exact cleanup path to this plan before continuing.

- [ ] **Step 6: Review final diff**

Run:

```bash
git diff --stat HEAD
git diff HEAD -- plugins/turbo-mode/ticket docs/superpowers/plans/2026-06-02-ticket-remove-git-branch-bookkeeping.md
```

Expected: diff shows only this source slice and this plan. No installed cache, handoff, or ticket-file mutation appears.

- [ ] **Step 7: Final commit boundary**

Expected: Task 6 makes no source changes, so there is no Task 6 commit. If Task 6 reveals a missed consumer or cleanup path beyond `plugins/turbo-mode/ticket/.pytest_cache`, stop and patch this plan before adding another commit.

## Final Reporting Requirements

The implementation closeout must include:

- Source proof only. Do not claim installed runtime/cache behavior.
- Exact commit range for this slice.
- Verification commands and pass/fail results.
- Residue inventory result, with allowed historical hits named.
- Explicit statement that Ticket no longer performs commit coordination, records commit disposition, or binds branch scope in source mutation paths.
- Explicit remaining ADR drift list: full target candidate contract, including
  unknown-field rejection versus this slice's deprecated-field ignore behavior,
  ticket-file cutover/normalization, diagnostic dry-run, response-envelope
  cleanup beyond this source slice, Change History grammar, and old workflow
  architecture not touched by this slice.

## Self-Review

Spec coverage:

- User request to remove `ticket_change_scope`, `commit_disposition`, and all commit coordination is covered by Tasks 1 through 4.
- User request to include older/manual transitional paths is covered by the source inventory and active gateway/direct-engine boundary check. Current direct engine execution does not import commit coordination; gateway is the live side-effect path.
- User request to delete feature-preserving tests/docs is covered by deleting `test_ticket_commit_coordinator.py` and patching active docs/static tests only when they present old behavior as target behavior.
- User request for quiet success output is covered by Task 4.
- User allowance for repair evidence is preserved by keeping pending-summary fingerprints, recovery projection data, and failure data.

Placeholder scan:

- This plan contains no deferred implementation placeholders and no references to undefined helper names in code snippets.

Type consistency:

- `ticket_change_scope` is removed from `CandidateMutation`, `GatewayMutation`, `candidate_mutation_payload()`, and `make_candidate_mutation_identity()` together.
- `commit_disposition` is removed from gateway response data, pending-summary validation, recovery-generated events, and apply-turn summary output together.
