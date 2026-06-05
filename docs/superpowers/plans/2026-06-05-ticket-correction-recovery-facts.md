# Ticket Correction Recovery Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential implementation with checkpoints. Subagents may be used only as bounded review/probe helpers for an already-scoped step, not as primary task executors. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `correct` authorization and operation-log recovery facts onto target candidates without preserving old runtime decision/evidence taxonomies in mutation attempts.

**Architecture:** This slice makes recent uncompacted correction context the authorization boundary for automatic `correct`, extends pre-write expected post recovery facts to non-create writes, and teaches apply-turn prior-turn recovery to interpret retained create allocation facts.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Parent And Successor Gates

- Parent index: `docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration-index.md`.
- Required predecessors: source entrypoint spine, create idempotency binding, and reopen/blocked cleanup semantics committed and green.
- Ends after Task 5 commit: `fix(ticket): migrate correction recovery facts`.
- Hands off to `docs/superpowers/plans/2026-06-05-ticket-availability-flip-final-proof.md` with only docs/availability and final verification remaining.

## Slice Scope

This plan owns Task 5 from the superseded monolith. It must preserve Task 3A retained-create recovery while adding non-create/correction recovery facts.

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

## Slice Handoff

After Task 5, record the correction/recovery selector output and commit hash. The next plan may flip source availability only if apply-turn correction positives and compacted, expired, unmatched, proposed-change mismatch, non-create recovery, and prior-turn create recovery paths are green.
