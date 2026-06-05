# Ticket Reopen Blocked Cleanup Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ticket reopen and blocked cleanup semantics match the visible target lifecycle contract.

**Architecture:** This slice removes normal target-write dependence on `reopen_reason` and `Reopen History`, allows terminal tickets to reopen to `open` or valid `blocked` shape, and requires explicit blocked cleanup for close/unblock paths before engine writes can hide mismatches.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Parent And Successor Gates

- Parent index: `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md`.
- Required predecessor: `docs/superpowers/plans/2026-06-05-ticket-create-idempotency-binding.md` committed and Task 3A focused tests green.
- Ends after Task 4 commit: `fix(ticket): migrate target reopen semantics`.
- Hands off to `docs/superpowers/plans/2026-06-05-ticket-correction-recovery-facts.md` with correction authorization and recovery facts still pending.

## Slice Scope

This plan owns Task 4 from the superseded monolith. Source-availability docs still wait for correction/recovery proof in the next plan.

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

## Slice Handoff

After Task 4, record the reopen/change-history selector output and commit hash. The final docs plan depends on this slice for truthful lifecycle prose, especially terminal reopen to `open` or `blocked`.
