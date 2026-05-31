# Ticket Runtime-First Modes And Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove durable `preview` mode and automatic `agent_primary` approval envelopes from Ticket source while keeping deterministic gateway write safety.

**Architecture:** This is the first source implementation slice from the Ticket source-runtime drift ledger. It changes the local mode model, runtime evaluator, pending-summary validation, gateway validation, apply-turn projection, and integration expectations together so one producer is not removed while consumers still require it. Diagnostic dry-run remains a future explicit maintenance affordance; this slice removes durable/product `preview` but does not yet implement the target diagnostic dry-run path.

**Tech Stack:** Python >=3.11, pytest, dataclasses, strict JSON, append-only JSONL, existing Ticket scripts, bytecode-safe `uv run` verification.

---

## Scope Check

The drift ledger names six areas: `preview`, approval envelopes, `ticket_change_scope`, prepare/execute wrappers, pending-summary taxonomy, and `blocks`. This plan intentionally covers one coherent implementation slice: durable mode cleanup plus removal of automatic approvals from `agent_primary`.

Out of scope for this plan:

- `ticket_change_scope` removal from candidate identity, discovery, gateway fingerprints, autonomous apply, and commit disposition.
- Prepare/execute wrapper demotion in `ticket_capture.py` and `ticket_update.py`.
- Full pending-summary taxonomy collapse beyond removing new `preview_only` and automatic-approval requirements.
- Persisted `blocks` removal and reverse-blocker derived views.
- Installed cache refresh, `hooks/list`, `skills/list`, `plugin/read`, or other runtime inventory.

Write separate plans for those surfaces. Do not fold them into this slice unless this plan is explicitly revised.

Known remaining product drift after this slice:

- `ticket_change_scope` remains live and still influences commit-disposition behavior. The closeout must name this as remaining drift, not as target compliance.
- Diagnostic dry-run/preview remains unavailable as a target affordance. The closeout must name this as temporary non-compliance with the ADR/control diagnostic-preview requirement, not as a completed preview implementation.

## Authority And Current Source Facts

Source authority:

- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` says durable modes are exactly `agent_primary` and `discussion_only`, and `preview` is diagnostic only.
- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` removes automatic approval objects from `agent_primary`; explicit approval survives only for `discussion_only` follow-up.
- `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md` says hard stops include no persistent `preview` mode and no approval state in the private operation log.
- `docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md` is a source-only classification and inventory input, not runtime proof.

Current source touchpoints for this slice:

| Surface | Current drift |
|---|---|
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:29-34` | `AutomationMode.PREVIEW` is a durable config mode. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_config.py:102-108` | Tests assert manual durable preview config is valid. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:22-27` | `RuntimeDecisionKind.PREVIEW_ONLY` is a runtime decision kind. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:162-202` | `_make_approval()` creates automatic approval envelopes. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:479-488` | Runtime evaluator emits `PREVIEW_ONLY` for current mode `preview`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:531-550` | Runtime evaluator attaches approval envelopes to `APPLY_AUTONOMOUSLY`. |
| `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:154-188` | Gateway rejects autonomous writes without approval envelopes. |
| `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:619-645` | Gateway writes approval details and `approval_consumed` events. |
| `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:85-95` | Pending-summary accepts `preview_only` and `preview` as durable taxonomy. |
| `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:292-298` | Pending-summary requires `details.approval` for `apply_autonomously`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:273-286` | Apply-turn projects `preview` as a product state. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:345-361` | Apply-turn writes `preview_only` non-write events. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:821` | Apply-turn references `AutomationMode.PREVIEW.value` while validating `--setup-choice preview`. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:970` | Apply-turn treats `PREVIEW_ONLY` decisions as skipped product output. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py:113-125` | Integration tests expect new successful writes to record `approval_consumed`. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py:197-204` | Integration tests still write durable `AutomationMode.PREVIEW` and expect product `preview` output. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py:257` | Integration tests expect gateway attempt details to contain an approval object. |

## File Structure

Modify these files only in this plan:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py`
  - Owns strict local config modes and snapshots.
  - Remove durable `AutomationMode.PREVIEW`.
- `plugins/turbo-mode/ticket/tests/test_autonomy_config.py`
  - Covers config parsing, setup choices, pause/resume, and snapshots.
  - Rewrite preview config coverage to assert `preview` requires setup.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
  - Owns candidate decisions and mutation IDs.
  - Remove `PREVIEW_ONLY` and stop creating automatic approval envelopes.
- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
  - Covers evaluator behavior.
  - Rewrite approval and preview expectations.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
  - Owns pending-summary event validation and recovery projection.
  - Remove new `preview_only` taxonomy and automatic approval requirement. Keep `approval_consumed` readable as legacy recovery input until the later operation-log collapse plan removes it deliberately.
- `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
  - Covers pending-summary schema and validation.
  - Rewrite valid attempt fixtures and preview decision tests.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
  - Owns deterministic autonomous write validation and event recording.
  - Replace approval-envelope validation with decision/mutation validation.
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
  - Covers gateway write safety, event sequences, and recovery.
  - Rewrite approval tests and remove new-event expectations for `approval_consumed`.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
  - Owns apply-turn CLI projection and pending-summary append calls.
  - Remove product `preview` projection and `PREVIEW_ONLY` handling.
- `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
  - Covers apply-turn CLI behavior and recovery.
  - Rewrite preview setup-choice messaging and event sequences.
- `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
  - Covers end-to-end apply-turn orchestration.
  - Rewrite success event sequences, durable preview expectations, and forged approval assertions.

Do not modify docs, plugin manifests, cache files, or installed runtime state in this implementation slice unless a test cannot be made truthful without a source-contract note. If that happens, stop and revise this plan first.

## Stop Conditions

Stop before source edits if:

- `git status --short --branch` shows unrelated tracked changes in any file this plan touches.
- `docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md` has changed since this plan was written and now recommends a different first source slice.
- The implementation branch lacks ADR 0006 and the May 30 control doc.
- A change would mutate `/Users/jp/.codex/plugins/cache`, `.codex/ticket-workspace/`, `.codex/ticket.local.md`, or installed runtime state.

Stop during implementation if:

- A gateway write can proceed without a mutation ID, expected target fingerprint for non-create writes, or deterministic candidate/mutation match.
- Gateway validation accepts a mutation ID that does not match the ID recomputed from `thread_id`, `turn_id`, and `decision.candidate`.
- Any new pending-summary event writes `details.approval`, `approval_id`, `preview_only`, or `current_mode: preview`.
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

- [ ] **Step 2: Confirm this slice is still the ledger-recommended first source cut**

Run:

```bash
rg -n "preview|Approval envelopes|Recommended Next Steps|source-only" docs/audits/2026-05-31-ticket-source-runtime-drift-ledger.md
```

Expected: output still says the ledger is source-only and still names `preview` plus approval envelopes as drift needing source implementation.

- [ ] **Step 3: Confirm current source still has the drift this plan removes**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|approval_consumed|details\\.approval|approval_required|make_approval|codex\\.ticket\\.approval|decision\\.approval|approval_id" plugins/turbo-mode/ticket/scripts
```

Expected before implementation: matches in `ticket_autonomy_config.py`, `ticket_autonomy_runtime.py`, `ticket_autonomy.py`, `ticket_engine_gateway.py`, `ticket_turn_batch.py`, and `ticket_autonomy_ids.py`. `ticket_autonomy_ids.py` may still define `make_approval_id` until a later cleanup proves no callers remain.

- [ ] **Step 4: Confirm focused tests currently encode old behavior**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|\\\"preview\\\"|approval_consumed|decision\\.approval|details\\[\\\"approval\\\"\\]" plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
```

Expected before implementation: matches in the focused tests named by this plan.

## Task 1: Remove Durable `preview` From Local Config

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:29-34`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_config.py:29-108`

- [ ] **Step 1: Write the failing config tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_config.py`, replace the mode parametrization and preview test with this code:

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
```

- [ ] **Step 2: Run the config tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py::test_preview_config_requires_setup -q
```

Expected before implementation: FAIL because `preview` is still accepted as `AutomationMode.PREVIEW`.

- [ ] **Step 3: Remove `PREVIEW` from `AutomationMode`**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py`, replace the enum with:

```python
class AutomationMode(StrEnum):
    """Runtime-first automation modes for local Ticket setup."""

    DISCUSSION_ONLY = "discussion_only"
    AGENT_PRIMARY = "agent_primary"
```

Do not add a replacement enum member for diagnostic dry-run. Diagnostic dry-run is not durable config.

- [ ] **Step 4: Run focused config tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit durable-mode config cleanup**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py
git commit -m "fix(ticket): remove durable preview config mode"
```

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
    assert discussion.approval is None


def test_unsupported_preview_mode_requires_discussion_without_preview_decision() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate, mode="preview")[0]

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "unsupported_mode"
    assert decision.pending_summary_status == "discussion_required"
    assert decision.approval is None
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

In `_summary_payload()`, replace the final state selection with:

```python
    if applied:
        state = "applied"
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

- [ ] **Step 8: Commit runtime preview removal**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py
git commit -m "fix(ticket): remove preview runtime decision state"
```

## Task 3: Stop Creating Automatic `agent_primary` Approval Envelopes

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:1-202`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:525-550`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py:74-230`

- [ ] **Step 1: Rewrite evaluator approval tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, change the loop assertion in `test_ordinary_candidates_apply_autonomously_with_agent_primary_and_evidence` to:

```python
        assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
        assert decision.mutation_id is not None
        assert decision.approval is None
        assert decision.reason == "authorized"
```

Replace `test_approval_envelope_binds_decision_context_and_expires_within_ten_minutes` with:

```python
def test_agent_primary_decision_uses_mutation_id_without_approval_envelope() -> None:
    candidate = _candidate("update", evidence=_evidence("current_thread_reason"))

    decision = _decisions(candidate)[0]

    assert decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY
    assert decision.mutation_id is not None
    assert decision.mutation_id.startswith("mut_")
    assert decision.approval is None
    assert decision.engine_dispatch is not None
    assert decision.engine_dispatch.state == "ok"
    assert decision.reason == "authorized"
```

Change `test_ticket_change_scope_binds_mutation_identity_and_approval_fingerprint` to:

```python
def test_ticket_change_scope_still_binds_mutation_identity_until_scope_slice() -> None:
    current_branch = _decisions(
        _candidate("update", ticket_change_scope="current_branch"),
    )[0]
    unrelated_backlog = _decisions(
        _candidate("update", ticket_change_scope="unrelated_backlog"),
    )[0]

    assert current_branch.mutation_id != unrelated_backlog.mutation_id
    assert current_branch.approval is None
    assert unrelated_backlog.approval is None
```

The renamed test is intentionally temporary: it documents that `ticket_change_scope` survives only until its separate removal slice.

- [ ] **Step 2: Run evaluator approval tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py::test_agent_primary_decision_uses_mutation_id_without_approval_envelope -q
```

Expected before implementation: FAIL because evaluator still returns an approval envelope.

- [ ] **Step 3: Remove approval creation from runtime evaluator**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, remove `make_approval_id` from the import:

```python
from scripts.ticket_autonomy_ids import (
    make_mutation_id,
    sha256_fingerprint,
)
```

Delete the `_ticket_state_fingerprint()` function and `_make_approval()` function. They are automatic approval machinery in this file.

In `evaluate_autonomy_intent()`, replace the autonomous-apply tail with:

```python
        mutation_id, _mutation_fingerprint, _evidence_fingerprint = _mutation_id_for_candidate(
            candidate=candidate,
            thread_id=thread_id,
            turn_id=turn_id,
        )
        applied_counts[fanout_key] += 1
        decisions.append(
            _decision(
                candidate,
                RuntimeDecisionKind.APPLY_AUTONOMOUSLY,
                reason="authorized",
                pending_summary_status="pending",
                mutation_id=mutation_id,
                approval=None,
                engine_dispatch=dispatch,
            )
        )
```

Do not delete the `approval` field from `AutonomyDecision` in this slice. It remains available for the later explicit `discussion_only` user-approval fact.

- [ ] **Step 4: Run focused evaluator tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit evaluator approval removal**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py
git commit -m "fix(ticket): stop creating agent-primary approvals"
```

## Task 4: Replace Gateway Approval Validation With Decision Validation

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:76-188`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:230-245`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:610-650`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py:1-220`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py:240-270`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py:650-810`

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
            mutation_id=None,
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
    assert forged_mutation_id.error_code == "gateway_required"
    assert "mutation_id_mismatch" in forged_mutation_id.message
    assert "priority: high" in ticket_path.read_text(encoding="utf-8")
    assert _events(project_root) == []
```

- [ ] **Step 2: Run the gateway decision-validation test to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py::test_gateway_rejects_non_autonomous_or_mismatched_decisions -q
```

Expected before implementation: FAIL because gateway still requires approval envelopes.

- [ ] **Step 3: Replace approval validation helper**

In `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`, delete `_approval_ticket_id()` and `_parse_z()`. After this task, neither helper has a caller.

Add `_mutation_id_for_candidate` to the existing import from `scripts.ticket_autonomy_runtime`:

```python
from scripts.ticket_autonomy_runtime import (
    AutonomyDecision,
    CandidateMutation,
    EngineAction,
    EngineDispatch,
    RuntimeDecisionKind,
    _mutation_id_for_candidate,
    map_candidate_to_engine,
)
```

Replace `_approval_error()` with:

```python
def _decision_error(
    *,
    thread_id: str,
    turn_id: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    if decision.mutation_id is None:
        return "mutation_id_required"
    if decision.approval is not None:
        return "approval_unexpected"
    if decision.kind == RuntimeDecisionKind.APPLY_CORRECTION:
        if mutation.action != "correction" or decision.candidate.action != "correction":
            return "decision_mismatch"
    elif decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        return "autonomous_decision_required"
    if decision.candidate.ticket_id != mutation.ticket_id:
        return "ticket_mismatch"
    if decision.candidate.action != mutation.action:
        return "action_mismatch"
    if dict(decision.candidate.proposed_change) != dict(mutation.fields):
        return "mutation_fingerprint_mismatch"
    expected_mutation_id, _mutation_fingerprint, _evidence_fingerprint = (
        _mutation_id_for_candidate(
            candidate=decision.candidate,
            thread_id=thread_id,
            turn_id=turn_id,
        )
    )
    if decision.mutation_id != expected_mutation_id:
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

In `_apply_autonomous_mutation_locked()`, replace the mutation-attempt details block with:

```python
        details={
            "decision": decision.kind.value,
            "current_mode": "agent_primary",
            "evidence_kind": "runtime_context",
            **_fingerprint_details(mutation=mutation, decision=decision),
        },
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

Apply the same replacement in this file anywhere a new successful gateway write is expected. Do not change legacy recovery fixtures that intentionally append `approval_consumed` to model old pending-summary logs.

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

- [ ] **Step 6: Run focused gateway tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py::test_gateway_rejects_non_autonomous_or_mismatched_decisions tests/test_engine_gateway.py::test_gateway_applies_update_records_events_and_writes_change_history tests/test_engine_gateway.py::test_gateway_rechecks_pause_after_attempt_record_before_dispatch -q
```

Expected: PASS.

- [ ] **Step 7: Commit gateway approval removal**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py
git commit -m "fix(ticket): validate autonomous decisions without approvals"
```

## Task 5: Update Pending-Summary Validation For No New Approvals

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:45-95`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:280-300`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py:25-70`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py:170-275`

- [ ] **Step 1: Rewrite pending-summary fixtures and tests**

In `plugins/turbo-mode/ticket/tests/test_turn_batch.py`, replace the `details` dictionary in `valid_attempt_event()` with:

```python
    details: dict[str, object] = {
        "decision": "apply_autonomously",
        "current_mode": "agent_primary",
        "evidence_kind": "runtime_context",
    }
```

Replace `test_preview_records_use_skipped_status_with_preview_only_decision` with:

```python
def test_preview_only_decision_is_not_a_supported_pending_summary_decision() -> None:
    event = valid_attempt_event(
        status="skipped",
        details={"decision": "preview_only", "current_mode": "preview"},
    )

    assert_invalid(event, "decision")
```

Remove this tuple from `test_status_details_requirements`:

```python
(
    without_detail(valid_attempt_event(), "approval"),
    "approval",
),
```

Keep `valid_status_event("approval_consumed")` and the `approval_id` requirement for legacy recovery input in this slice.

- [ ] **Step 2: Run pending-summary tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py::test_preview_only_decision_is_not_a_supported_pending_summary_decision tests/test_turn_batch.py::test_status_details_requirements -q
```

Expected before implementation: FAIL because `preview_only` and `current_mode: preview` are still accepted, and `details.approval` is still required for `apply_autonomously`.

- [ ] **Step 3: Remove new preview and approval requirements from validation**

In `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`, replace `_DECISIONS` and `_MODES` with:

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

In `_validate_details()`, remove these checks:

```python
        if decision == "apply_autonomously" and not isinstance(details.get("approval"), Mapping):
            return _invalid("details.approval is required")
        if decision == "preview_only" and status != "skipped":
            return _invalid("preview_only decisions must use skipped status")
```

Do not remove `approval_consumed` from `_EVENT_STATUSES`, `required_by_status`, `derive_mutation_state()`, or `project_mutation_recovery()` in this task. Those branches are legacy recovery input and will be reviewed in the later operation-log collapse plan.

- [ ] **Step 4: Run focused pending-summary tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit pending-summary validation cleanup**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_turn_batch.py
git commit -m "fix(ticket): drop pending-summary approval requirement"
```

## Task 6: Update Apply-Turn Recovery And Integration Tests

**Files:**
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Inspect: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`

- [ ] **Step 1: Find remaining test expectations for new approval writes**

Run:

```bash
rg -n "approval_consumed|details\\[\\\"approval\\\"\\]|decision\\.approval|approval_id|AutomationMode\\.PREVIEW|preview_payload|\\\"preview\\\"" plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
```

Expected after Tasks 3-5: remaining matches should be either legacy recovery fixtures or tests that still need source-slice rewrite. New successful write paths must not expect `approval_consumed`; no test should write durable `AutomationMode.PREVIEW`.

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

Apply the same helper rewrite in `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`.

- [ ] **Step 3: Rewrite integration success event sequence**

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

- [ ] **Step 4: Rewrite integration preview test**

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

- [ ] **Step 5: Rewrite integration forged approval assertion**

In `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, update the final assertions in `test_apply_turn_consumes_adapter_candidate_keys_and_ignores_forged_approval` to:

```python
    events = _events(tmp_path)
    assert "approval" not in events[0]["details"]
    assert events[0]["mutation_id"] != "forged"
```

- [ ] **Step 6: Keep legacy `approval_consumed` fixtures marked as legacy**

For tests that append `valid_status_event("approval_consumed", ...)` to model an old partial log, add this local comment immediately before the append:

```python
# Legacy recovery input: new gateway writes no approval_consumed events.
```

Do not add new product behavior around `approval_consumed`.

- [ ] **Step 7: Confirm no new source writes approval envelopes or preview decisions**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|details\\.approval|approval_required|make_approval|codex\\.ticket\\.approval|decision\\.approval\\[|approval_consumed" plugins/turbo-mode/ticket/scripts
```

Expected after implementation:

- No matches for `AutomationMode.PREVIEW`, `RuntimeDecisionKind.PREVIEW_ONLY`, `preview_only`, `details.approval`, `approval_required`, `make_approval`, or `codex.ticket.approval` outside `ticket_autonomy_ids.py`.
- `approval_consumed` may still match only in `ticket_turn_batch.py` legacy recovery validation and projection.

- [ ] **Step 8: Run focused apply-turn, integration, and gateway suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py tests/test_engine_gateway.py tests/test_turn_batch.py tests/test_autonomy_runtime.py tests/test_autonomy_config.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit apply-turn and integration test cleanup**

Run:

```bash
git add plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py
git commit -m "test(ticket): update autonomy recovery expectations"
```

## Task 7: Final Verification And Closeout

**Files:**
- Verify all modified files from Tasks 1-6.

- [ ] **Step 1: Run source search guard**

Run:

```bash
rg -n "AutomationMode\\.PREVIEW|RuntimeDecisionKind\\.PREVIEW_ONLY|preview_only|details\\.approval|approval_required|make_approval|codex\\.ticket\\.approval|decision\\.approval\\[|current_mode\\\": \\\"preview\\\"" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: no matches, except `make_approval_id` may remain in `plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py` if no source caller uses it. If it remains unused, decide in this task whether to delete it with its tests or leave it for the later explicit `discussion_only` user-approval fact. If deleting it changes broad ID tests, keep deletion for a separate cleanup.

- [ ] **Step 2: Run focused source tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py tests/test_autonomy_runtime.py tests/test_turn_batch.py tests/test_engine_gateway.py tests/test_autonomy_cli.py tests/test_autonomy_integration_v1.py -q
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
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
```

Expected: PASS.

- [ ] **Step 5: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Review final diff**

Run:

```bash
BASE_COMMIT="$(cat /tmp/ticket-modes-approval-base.txt)"
git diff --stat "$BASE_COMMIT"..HEAD
git diff "$BASE_COMMIT"..HEAD -- plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: diff is limited to the mode, runtime evaluator, pending-summary, gateway, apply-turn, and focused tests named in this plan. No docs, cache, installed runtime, local workspace state, or handoff files are staged.

- [ ] **Step 7: Record remaining drift in closeout notes**

The implementation closeout message must include these exact proof-boundary facts:

```text
Remaining product drift: `ticket_change_scope` still exists in candidate identity, gateway fingerprints, autonomous apply, and commit-disposition behavior; it is intentionally deferred to a separate source slice.
Remaining product drift: diagnostic dry-run/preview is not implemented by this slice; this slice only removes durable/product `preview` mode and preview-only runtime states.
```

Do not claim full ADR 0006 runtime compliance from this slice.

- [ ] **Step 8: Record closeout commit if final cleanup changed files**

If Task 7 produces cleanup edits, run:

```bash
git add plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
git commit -m "chore(ticket): verify modes approval source slice"
```

Expected: commit includes only cleanup needed by verification.

## Self-Review Checklist

Spec coverage:

- Durable `preview` config is removed in Task 1.
- Runtime `PREVIEW_ONLY` decisions and apply-turn product preview projections are removed in Task 2.
- Automatic `agent_primary` approval envelope creation is removed in Task 3.
- Gateway approval validation and new `approval_consumed` writes are removed in Task 4.
- Pending-summary no longer requires automatic approval details or accepts new preview decisions in Task 5.
- Apply-turn integration expectations are updated in Task 6 so full-suite verification does not fail late on removed approval/preview behavior.
- Existing legacy `approval_consumed` recovery input is explicitly retained only until the later operation-log collapse plan, preventing this slice from silently widening into full pending-summary redesign.
- Closeout language explicitly names remaining `ticket_change_scope` and diagnostic-preview drift instead of claiming full ADR compliance.

Placeholder scan:

- The plan has no open-ended implementation placeholders. Every code-changing task includes concrete snippets and focused commands.

Type consistency:

- `AutomationMode` has only `DISCUSSION_ONLY` and `AGENT_PRIMARY` after Task 1.
- `RuntimeDecisionKind` has no `PREVIEW_ONLY` after Task 2.
- `AutonomyDecision.approval` remains `dict[str, object] | None` for future explicit `discussion_only` approval facts, but this plan requires it to be `None` for `agent_primary`.
- Gateway validation uses `AutonomyDecision`, `CandidateMutation`, `GatewayMutation`, `thread_id`, and `turn_id` fields already present in current source.
- Gateway validation recomputes the expected mutation ID from `thread_id`, `turn_id`, and `decision.candidate`; non-null mutation IDs are not treated as proof.

## Handoff Notes For Executors

- Use `superpowers:subagent-driven-development` for implementation unless the user chooses inline execution.
- Use a fresh branch or worktree for source implementation. If creating a worktree, use `superpowers:using-git-worktrees`.
- Commit after each task when tests pass. Do not squash during implementation; the task commits are useful review boundaries.
- Do not refresh installed runtime or cache state. Source tests are the proof class for this plan.
