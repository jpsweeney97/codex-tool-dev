# Ticket Create Idempotency Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind create candidates to retained target ID/path allocation and exact post-write recovery facts so retries cannot create duplicate tickets.

**Architecture:** This slice adds the content-only recovery fingerprint helper, create-allocation-wide gateway locking, retained allocation details, create write preview, reserved create IDs, and create-attempt event validation as one recovery boundary.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Parent And Successor Gates

- Parent index: `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md`.
- Required predecessor: `docs/superpowers/plans/2026-06-05-ticket-candidate-source-entrypoint-spine.md` committed and Task 3 focused tests green.
- Ends after Task 3A commit: `fix(ticket): bind create candidates to allocated tickets`.
- Hands off to `docs/superpowers/plans/2026-06-05-ticket-reopen-blocked-cleanup-semantics.md` with reopen/lifecycle semantics and correction/recovery still pending.

## Slice Scope

This plan owns Task 3A from the superseded monolith. Do not start source-availability docs from this plan alone.

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

## Slice Handoff

After Task 3A, record the create idempotency selector output and commit hash. The next plan may start only if retained allocation, expected post-write recovery fingerprint, exact generated `Change History` metadata, and bounded create-attempt detail validation are green.
