#!/usr/bin/env python3
"""Host-facing Ticket autonomy CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_autonomy_config import (  # noqa: E402
    WORKSPACE_RELATIVE_PATH,
    AutomationMode,
    LocalConfigState,
    SetupChoice,
    pause_workspace_automation,
    resolve_thread_mode,
    resume_workspace_automation,
    verify_local_state_paths,
    write_mode_snapshot,
)
from scripts.ticket_autonomy_ids import make_event_id  # noqa: E402
from scripts.ticket_autonomy_runtime import (  # noqa: E402
    AutonomyIntent,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
)
from scripts.ticket_candidate_discovery import discover_candidate_mutations  # noqa: E402
from scripts.ticket_change_history import plan_change_history_migration  # noqa: E402
from scripts.ticket_dedup import target_fingerprint as compute_target_fingerprint  # noqa: E402
from scripts.ticket_engine_gateway import GatewayMutation, apply_autonomous_mutation  # noqa: E402
from scripts.ticket_parse import parse_ticket  # noqa: E402
from scripts.ticket_read import InvalidTicketState, find_ticket_by_id  # noqa: E402
from scripts.ticket_turn_batch import (  # noqa: E402
    PENDING_SUMMARY_SCHEMA,
    PendingSummaryStore,
    RecoveryProjection,
    VerifiedRepoContext,
    event_payload_fingerprint,
    project_mutation_recovery,
)

TURN_CONTEXT_SCHEMA = "codex.ticket.turn_context.v1"
SETUP_CHOICES = ["automatic", "ask_first"]
REPAIR_PROJECTION_STATES = {
    "append_missing_ticket_written",
    "append_missing_terminal_status",
    "summary_ready",
}


@dataclass(frozen=True, slots=True)
class LedgerRecoveryItem:
    """One pending-summary mutation recovery projection."""

    projection: RecoveryProjection
    turn_id: str
    ticket_id: str | None


@dataclass(frozen=True, slots=True)
class TicketStateFingerprintCollection:
    """Source-context fingerprint collection result for candidate writes."""

    state: Literal["ok", "unhealthy"]
    fingerprints: dict[str, str]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TicketStateFingerprintProbe:
    """Synthetic candidate used to probe paused source-context health."""

    ticket_id: str
    action: str = "update"


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def _invalid_args(message: str) -> int:
    _emit({"state": "invalid_args", "message": message})
    return 2


def _text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _relative_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _git_output(project_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def build_repo_context(project_root: Path) -> VerifiedRepoContext:
    """Build verified live repository context for Ticket autonomy events."""
    resolved_root = project_root.resolve(strict=False)
    git_root_raw = _git_output(resolved_root, "rev-parse", "--show-toplevel")
    repo_root = Path(git_root_raw).resolve(strict=False) if git_root_raw else resolved_root
    branch = _git_output(resolved_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        branch = None
    head = _git_output(resolved_root, "rev-parse", "HEAD")
    fingerprint_payload = "|".join(
        [
            str(repo_root),
            str(resolved_root),
            branch or "",
            head or "",
        ]
    )
    repo_fingerprint = "sha256:" + hashlib.sha256(
        fingerprint_payload.encode("utf-8")
    ).hexdigest()
    return VerifiedRepoContext(
        repo_root=repo_root,
        worktree_root=resolved_root,
        repo_fingerprint=repo_fingerprint,
        branch=branch,
        head=head,
    )


def verify_turn_repo_context(
    *,
    project_root: Path,
    supplied_git: Mapping[str, object],
) -> VerifiedRepoContext:
    """Verify supplied turn-context git identity against live repo state."""
    live = build_repo_context(project_root)
    expected = live.as_event_payload()
    for key, expected_value in expected.items():
        if supplied_git.get(key) != expected_value:
            raise ValueError(
                f"verify repo context failed: {key} mismatch. Got: {supplied_git.get(key)!r:.100}"
            )
    return live


def _local_state_setup_required(project_root: Path) -> int | None:
    verification = verify_local_state_paths(project_root)
    if verification.ok:
        return None
    payload: dict[str, Any] = {
        "state": "setup_required",
        "reason": f"local_state_{verification.reason or 'invalid'}",
        "setup_choices": SETUP_CHOICES,
        "ticket_updates": None,
        "discussion_question": None,
    }
    if verification.path is not None:
        payload["path"] = _relative_path(project_root, verification.path)
    _emit(payload)
    return 3


def _pause_marker_path(project_root: Path) -> Path:
    return project_root / WORKSPACE_RELATIVE_PATH / "pause.json"


def _workspace_is_paused(project_root: Path) -> bool:
    return _pause_marker_path(project_root).is_file()


def _read_pause_reason(project_root: Path) -> str:
    try:
        data = json.loads(_pause_marker_path(project_root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "workspace_paused"
    if isinstance(data, dict) and isinstance(data.get("reason"), str):
        return data["reason"]
    return "workspace_paused"


def _pause_message(reason: str) -> str:
    messages = {
        "user_requested": "Ticket automation paused for this workspace.",
        "pending_summary_unhealthy": (
            "Ticket automation paused because pending-summary bookkeeping needs cleanup."
        ),
        "setup_required": "Ticket automation paused because setup is required.",
        "lock_timeout": "Ticket automation paused because pending-summary bookkeeping is locked.",
        "conflicting_event": (
            "Ticket automation paused because pending-summary bookkeeping conflicts."
        ),
        "repo_context_mismatch": "Ticket automation paused because repository context changed.",
        "repair": "Ticket automation paused for ledger repair.",
        "source_context_unhealthy": (
            "Ticket automation paused because source-context collection is unhealthy."
        ),
    }
    return messages.get(reason, "Ticket automation paused for this workspace.")


def _paused_response(reason: str) -> dict[str, Any]:
    return {
        "state": "paused",
        "pause_reason": reason,
        "message": _pause_message(reason),
        "ticket_updates": None,
        "discussion_question": None,
    }


def _no_change_response() -> dict[str, Any]:
    return {
        "state": "no_change",
        "changed": False,
        "ticket_updates": None,
        "discussion_question": None,
    }


def _setup_required_response(reason: str) -> dict[str, Any]:
    return {
        "state": "setup_required",
        "reason": reason,
        "setup_choices": SETUP_CHOICES,
        "ticket_updates": None,
        "discussion_question": None,
    }


def _load_turn_context(
    context_file: Path,
    *,
    turn_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(context_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(data, dict):
        return None, "invalid_shape"
    if data.get("schema") != TURN_CONTEXT_SCHEMA:
        return None, "invalid_schema"

    thread_id = data.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        return None, "thread_id_required"
    context_turn_id = data.get("turn_id")
    if not isinstance(context_turn_id, str) or not context_turn_id.strip():
        return None, "turn_id_required"
    if context_turn_id != turn_id:
        return None, "turn_id_mismatch"

    candidate_changes = data.get("candidate_changes")
    if candidate_changes is not None and not isinstance(candidate_changes, list):
        return None, "candidate_changes_invalid"
    return data, None


def _has_candidate_changes(context: dict[str, Any]) -> bool:
    candidate_changes = context.get("candidate_changes")
    return isinstance(candidate_changes, list) and bool(candidate_changes)


def _mode_from_setup_choice(choice: SetupChoice) -> AutomationMode:
    if choice == SetupChoice.AUTOMATIC:
        return AutomationMode.AGENT_PRIMARY
    if choice == SetupChoice.ASK_FIRST:
        return AutomationMode.DISCUSSION_ONLY
    raise ValueError(f"resolve setup choice failed: unsupported choice. Got: {choice!r:.100}")


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


def _event_payload(
    *,
    event_type: str,
    status: str,
    action: str,
    ticket_id: str | None,
    mutation_id: str | None,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    reason: str,
    details: Mapping[str, object],
) -> dict[str, object]:
    without_id = {
        "schema": PENDING_SUMMARY_SCHEMA,
        "thread_id": thread_id,
        "turn_id": turn_id,
        "event_type": event_type,
        "status": status,
        "action": action,
        "ticket_id": ticket_id,
        "mutation_id": mutation_id,
        "repo_context": repo_context.as_event_payload(),
        "reason": reason,
        "details": dict(details),
    }
    payload_fingerprint = event_payload_fingerprint(without_id)
    event_id = make_event_id(
        schema=PENDING_SUMMARY_SCHEMA,
        event_type=event_type,
        thread_id=thread_id,
        turn_id=turn_id,
        mutation_id=mutation_id,
        status=status,
        action=action,
        ticket_id=ticket_id,
        payload_fingerprint=payload_fingerprint,
    )
    return {"event_id": event_id, "timestamp": _now_z(), **without_id}


def _now_z() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_non_write_decision(
    *,
    store: PendingSummaryStore,
    decision: Any,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    current_mode: AutomationMode,
) -> None:
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
    event = _event_payload(
        event_type="mutation_attempt",
        status=status,
        action=decision.candidate.action,
        ticket_id=decision.candidate.ticket_id,
        mutation_id=decision.mutation_id,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason=reason,
        details=details,
    )
    store.append_event(event)


def _append_summary_receipt(
    *,
    store: PendingSummaryStore,
    thread_id: str,
    turn_id: str,
    repo_context: VerifiedRepoContext,
    mutation_ids: tuple[str, ...] = (),
) -> None:
    receipt_mutation_ids: tuple[str | None, ...] = tuple(dict.fromkeys(mutation_ids)) or (None,)
    for mutation_id in receipt_mutation_ids:
        event = _event_payload(
            event_type="summary_receipt",
            status="summarized",
            action="summarize",
            ticket_id=None,
            mutation_id=mutation_id,
            thread_id=thread_id,
            turn_id=turn_id,
            repo_context=repo_context,
            reason="Apply-turn summary returned.",
            details={},
        )
        store.append_event(event)


def _ticket_files_for_source_context(tickets_dir: Path) -> tuple[Path, ...]:
    if not tickets_dir.is_dir():
        return ()
    return tuple(sorted(tickets_dir.glob("*.md")))


def _ticket_state_fingerprints(
    candidates: tuple[Any, ...],
    tickets_dir: Path,
) -> TicketStateFingerprintCollection:
    ticket_ids = {
        candidate.ticket_id
        for candidate in candidates
        if getattr(candidate, "action", None) != "create"
        and isinstance(getattr(candidate, "ticket_id", None), str)
    }
    if not ticket_ids:
        return TicketStateFingerprintCollection("ok", {})

    parsed_by_id: dict[str, Any] = {}
    for ticket_file in _ticket_files_for_source_context(tickets_dir):
        try:
            ticket = parse_ticket(ticket_file)
        except InvalidTicketState:
            return TicketStateFingerprintCollection(
                "unhealthy",
                {},
                "source_context_unhealthy",
            )
        if ticket is None:
            return TicketStateFingerprintCollection(
                "unhealthy",
                {},
                "source_context_unhealthy",
            )
        parsed_by_id[ticket.id] = ticket

    fingerprints: dict[str, str] = {}
    for ticket_id in sorted(ticket_ids):
        ticket = parsed_by_id.get(ticket_id)
        if ticket is None:
            continue
        fingerprint = compute_target_fingerprint(Path(ticket.path))
        if fingerprint is None:
            return TicketStateFingerprintCollection(
                "unhealthy",
                {},
                "source_context_unhealthy",
            )
        fingerprints[ticket_id] = fingerprint

    return TicketStateFingerprintCollection("ok", fingerprints)


def _known_ticket_probe_collection(tickets_dir: Path) -> TicketStateFingerprintCollection:
    ticket_files = _ticket_files_for_source_context(tickets_dir)
    if not ticket_files:
        return TicketStateFingerprintCollection(
            "unhealthy",
            {},
            "source_context_unhealthy",
        )
    probes: list[TicketStateFingerprintProbe] = []
    for ticket_file in ticket_files:
        try:
            ticket = parse_ticket(ticket_file)
        except InvalidTicketState:
            return TicketStateFingerprintCollection(
                "unhealthy",
                {},
                "source_context_unhealthy",
            )
        if ticket is None:
            return TicketStateFingerprintCollection(
                "unhealthy",
                {},
                "source_context_unhealthy",
            )
        probes.append(TicketStateFingerprintProbe(ticket_id=ticket.id))
    return _ticket_state_fingerprints(tuple(probes), tickets_dir)


def _source_context_resume_collection(
    project_root: Path,
    context: dict[str, Any],
) -> TicketStateFingerprintCollection:
    tickets_dir = project_root / "docs" / "tickets"
    try:
        candidates = discover_candidate_mutations(context, tickets_dir)
    except InvalidTicketState:
        return TicketStateFingerprintCollection(
            "unhealthy",
            {},
            "source_context_unhealthy",
        )
    if candidates:
        return _ticket_state_fingerprints(candidates, tickets_dir)
    return _known_ticket_probe_collection(tickets_dir)


def _summary_payload(
    *,
    applied: list[str],
    skipped: list[str],
    blocked: list[str],
    discussion: list[str],
    discussion_question: str | None,
    blocked_reasons: dict[str, str],
) -> dict[str, Any]:
    if (
        not applied
        and not skipped
        and not blocked
        and not discussion
        and discussion_question is None
    ):
        return _no_change_response()
    ticket_updates: dict[str, list[str]] = {}
    if applied:
        ticket_updates["Applied"] = applied
    if skipped:
        ticket_updates["Skipped"] = skipped
    if blocked:
        ticket_updates["Blocked"] = blocked
    if discussion:
        ticket_updates["Discussion required"] = discussion
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
    payload: dict[str, Any] = {
        "state": state,
        "changed": bool(applied),
        "ticket_updates": ticket_updates,
        "discussion_question": discussion_question,
    }
    if blocked_reasons:
        payload["blocked_reasons"] = blocked_reasons
    return payload


def _ticket_label(candidate_ticket_id: str | None, response_ticket_id: str | None = None) -> str:
    if isinstance(response_ticket_id, str) and response_ticket_id:
        return response_ticket_id
    if isinstance(candidate_ticket_id, str) and candidate_ticket_id:
        return candidate_ticket_id
    return "new ticket"


def _summarizable_terminal_mutation_id(
    *,
    store: PendingSummaryStore,
    thread_id: str,
    mutation_id: str | None,
) -> str | None:
    if not isinstance(mutation_id, str):
        return None
    state = store.derive_mutation_state(thread_id=thread_id, mutation_id=mutation_id)
    if state == "status_recorded":
        return mutation_id
    return None


def _current_ticket_fingerprint_for_event(
    project_root: Path,
    event: Mapping[str, object],
) -> str | None:
    ticket_id = event.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        return None
    try:
        ticket = find_ticket_by_id(project_root / "docs" / "tickets", ticket_id)
    except InvalidTicketState:
        return None
    if ticket is None:
        return None
    return compute_target_fingerprint(Path(ticket.path))


def _mutation_recovery_items(
    *,
    project_root: Path,
    store: PendingSummaryStore,
    events: tuple[dict[str, object], ...],
    skip_turn_id: str | None = None,
) -> list[LedgerRecoveryItem]:
    seen: set[tuple[str, str]] = set()
    items: list[LedgerRecoveryItem] = []
    for event in events:
        thread_id = event.get("thread_id")
        mutation_id = event.get("mutation_id")
        turn_id = event.get("turn_id")
        if not isinstance(thread_id, str) or not isinstance(mutation_id, str):
            continue
        if not isinstance(turn_id, str) or turn_id == skip_turn_id:
            continue
        key = (thread_id, mutation_id)
        if key in seen:
            continue
        seen.add(key)
        projection = project_mutation_recovery(
            store=store,
            thread_id=thread_id,
            mutation_id=mutation_id,
            current_ticket_fingerprint=_current_ticket_fingerprint_for_event(project_root, event),
        )
        if projection.state == "healthy":
            continue
        ticket_id = event.get("ticket_id")
        items.append(
            LedgerRecoveryItem(
                projection=projection,
                turn_id=turn_id,
                ticket_id=ticket_id if isinstance(ticket_id, str) else None,
            )
        )
    return items


def _item_is_repairable(item: LedgerRecoveryItem) -> bool:
    return item.projection.state in REPAIR_PROJECTION_STATES and bool(
        item.projection.events_to_append
    )


def _ledger_item_payload(item: LedgerRecoveryItem) -> dict[str, object]:
    projection = item.projection
    payload: dict[str, object] = {
        "thread_id": projection.thread_id,
        "turn_id": item.turn_id,
        "mutation_id": projection.mutation_id,
        "ticket_id": item.ticket_id,
        "projection_state": projection.state,
        "events_to_append": len(projection.events_to_append),
        "current_ticket_fingerprint": projection.current_ticket_fingerprint,
        "expected_pre_write_fingerprint": projection.expected_pre_write_fingerprint,
        "expected_post_write_fingerprint": projection.expected_post_write_fingerprint,
    }
    if projection.reason is not None:
        payload["recovery_reason"] = projection.reason
    return payload


def _pending_summary_unhealthy() -> int:
    _emit(_paused_response("pending_summary_unhealthy"))
    return 3


def _recovery_paused_response(items: list[LedgerRecoveryItem]) -> dict[str, Any]:
    repairable = [item for item in items if _item_is_repairable(item)]
    reconciliation = [item for item in items if not _item_is_repairable(item)]
    payload = _paused_response("repair")
    payload.update(
        {
            "repairable_count": len(repairable),
            "reconciliation_count": len(reconciliation),
            "recoveries": [_ledger_item_payload(item) for item in items],
            "discussion_question": (
                "Run ticket_autonomy.py doctor-ledger --confirm-repair "
                "before new automatic writes."
            ),
        }
    )
    return payload


def _ledger_items_for_project(
    *,
    project_root: Path,
    store: PendingSummaryStore,
    skip_turn_id: str | None = None,
) -> tuple[tuple[dict[str, object], ...] | None, list[LedgerRecoveryItem]]:
    events = store.read_events_or_none()
    if events is None:
        return None, []
    return events, _mutation_recovery_items(
        project_root=project_root,
        store=store,
        events=events,
        skip_turn_id=skip_turn_id,
    )


def _ledger_blocks_resume(project_root: Path) -> bool:
    store = PendingSummaryStore(project_root)
    events, items = _ledger_items_for_project(project_root=project_root, store=store)
    return events is None or bool(items)


def _doctor_ledger_payload(
    *,
    events: tuple[dict[str, object], ...],
    items: list[LedgerRecoveryItem],
    repair_confirmed: bool,
    changed: bool,
    events_appended: int,
) -> dict[str, object]:
    repairable = [item for item in items if _item_is_repairable(item)]
    reconciliation = [item for item in items if not _item_is_repairable(item)]
    return {
        "state": "ok",
        "healthy": not items,
        "changed": changed,
        "repair_confirmed": repair_confirmed,
        "event_count": len(events),
        "repairable_count": len(repairable),
        "reconciliation_count": len(reconciliation),
        "events_appended": events_appended,
        "recoveries": [_ledger_item_payload(item) for item in items],
    }


def _run_migrate_change_history(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=False)
    if args.dry_run == args.apply:
        return _invalid_args("choose exactly one of --dry-run or --apply")

    plans = plan_change_history_migration(project_root / "docs" / "tickets")
    if args.dry_run:
        candidates = [_relative_path(project_root, plan.ticket_path) for plan in plans]
        _emit(
            {
                "state": "ok",
                "changed": False,
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )
        return 0

    updated: list[str] = []
    for plan in plans:
        try:
            current_text = plan.ticket_path.read_text(encoding="utf-8")
        except OSError as exc:
            _emit(
                {
                    "state": "blocked",
                    "changed": False,
                    "reason": "ticket_read_failed",
                    "path": _relative_path(project_root, plan.ticket_path),
                    "message": str(exc),
                }
            )
            return 1
        if _text_fingerprint(current_text) != plan.before_fingerprint:
            _emit(
                {
                    "state": "blocked",
                    "changed": False,
                    "reason": "ticket_changed_after_planning",
                    "path": _relative_path(project_root, plan.ticket_path),
                }
            )
            return 1
        try:
            plan.ticket_path.write_text(plan.after_text, encoding="utf-8")
        except OSError as exc:
            _emit(
                {
                    "state": "blocked",
                    "changed": bool(updated),
                    "reason": "ticket_write_failed",
                    "path": _relative_path(project_root, plan.ticket_path),
                    "message": str(exc),
                }
            )
            return 1
        updated.append(_relative_path(project_root, plan.ticket_path))

    _emit(
        {
            "state": "ok",
            "changed": bool(updated),
            "updated_count": len(updated),
            "updated": updated,
        }
    )
    return 0


def _run_pause(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=False)
    unsafe = _local_state_setup_required(project_root)
    if unsafe is not None:
        return unsafe

    pause_workspace_automation(project_root, reason=args.reason)
    unsafe = _local_state_setup_required(project_root)
    if unsafe is not None:
        return unsafe

    _emit(_paused_response(args.reason))
    return 0


def _run_recover(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=False)
    unsafe = _local_state_setup_required(project_root)
    if unsafe is not None:
        return unsafe

    store = PendingSummaryStore(project_root)
    compaction = store.compact_correction_ready_events()
    if compaction.state == "paused":
        _emit(_paused_response(compaction.pause_reason or "pending_summary_unhealthy"))
        return 3

    events, items = _ledger_items_for_project(
        project_root=project_root,
        store=store,
        skip_turn_id=args.turn_id,
    )
    if events is None:
        return _pending_summary_unhealthy()
    repairable = [item for item in items if _item_is_repairable(item)]
    reconciliation = [item for item in items if not _item_is_repairable(item)]
    can_proceed = not items
    _emit(
        {
            "state": "ok",
            "turn_id": args.turn_id,
            "can_proceed": can_proceed,
            "compaction_state": compaction.state,
            "event_count": len(events),
            "repairable_count": len(repairable),
            "reconciliation_count": len(reconciliation),
            "recoveries": [_ledger_item_payload(item) for item in items],
            "ticket_updates": None,
            "discussion_question": (
                None
                if can_proceed
                else (
                    "Run ticket_autonomy.py doctor-ledger --confirm-repair "
                    "before new automatic writes."
                )
            ),
        }
    )
    return 0


def _run_apply_turn(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=False)
    context, error = _load_turn_context(Path(args.context_file), turn_id=args.turn_id)
    if context is None:
        _emit({"state": "invalid_context", "reason": error or "invalid_context"})
        return 2

    supplied_git = context.get("git")
    if not isinstance(supplied_git, Mapping):
        _emit({"state": "invalid_context", "reason": "git_required"})
        return 2
    try:
        repo_context = verify_turn_repo_context(
            project_root=project_root,
            supplied_git=supplied_git,
        )
    except ValueError:
        _emit(_paused_response("repo_context_mismatch"))
        return 3

    if context.get("operation") == "pause_automation":
        unsafe = _local_state_setup_required(project_root)
        if unsafe is not None:
            return unsafe
        pause_workspace_automation(project_root, reason="user_requested")
        unsafe = _local_state_setup_required(project_root)
        if unsafe is not None:
            return unsafe
        _emit(_paused_response("user_requested"))
        return 0

    setup_choice_value = args.setup_choice
    if args.resume_paused and setup_choice_value is None:
        return _invalid_args("--resume-paused requires --setup-choice")
    if setup_choice_value is not None:
        try:
            setup_choice = SetupChoice(setup_choice_value)
        except ValueError:
            return _invalid_args("setup choice must be automatic or ask_first")

        unsafe = _local_state_setup_required(project_root)
        if unsafe is not None:
            return unsafe
        if _workspace_is_paused(project_root) and not args.resume_paused:
            _emit(_paused_response(_read_pause_reason(project_root)))
            return 3
        if args.resume_paused and _ledger_blocks_resume(project_root):
            _emit(_paused_response("repair"))
            return 3
        if args.resume_paused and _read_pause_reason(project_root) == "source_context_unhealthy":
            collection = _source_context_resume_collection(project_root, context)
            if collection.state == "unhealthy":
                _emit(_paused_response(collection.reason or "source_context_unhealthy"))
                return 3
        resume_workspace_automation(project_root, choice=setup_choice)
        mode = _mode_from_setup_choice(setup_choice)
        write_mode_snapshot(project_root, str(context["thread_id"]), mode)
        unsafe = _local_state_setup_required(project_root)
        if unsafe is not None:
            return unsafe
        return _run_apply_turn_with_mode(project_root, context, repo_context, mode)

    resolved = resolve_thread_mode(project_root, str(context["thread_id"]))
    if resolved.state == LocalConfigState.SETUP_REQUIRED or resolved.mode is None:
        if resolved.reason == "workspace_paused":
            _emit(_paused_response(_read_pause_reason(project_root)))
            return 3
        _emit(_setup_required_response(resolved.reason or "setup_required"))
        return 3

    unsafe = _local_state_setup_required(project_root)
    if unsafe is not None:
        return unsafe
    return _run_apply_turn_with_mode(project_root, context, repo_context, resolved.mode)


def _run_apply_turn_with_mode(
    project_root: Path,
    context: dict[str, Any],
    repo_context: VerifiedRepoContext,
    mode: AutomationMode,
) -> int:
    if _workspace_is_paused(project_root):
        _emit(_paused_response(_read_pause_reason(project_root)))
        return 3

    store = PendingSummaryStore(project_root)
    compaction = store.compact_correction_ready_events()
    if compaction.state == "paused":
        _emit(_paused_response(compaction.pause_reason or "pending_summary_unhealthy"))
        return 3

    events, items = _ledger_items_for_project(
        project_root=project_root,
        store=store,
        skip_turn_id=str(context["turn_id"]),
    )
    if events is None:
        return _pending_summary_unhealthy()
    if items:
        _emit(_recovery_paused_response(items))
        return 3

    tickets_dir = project_root / "docs" / "tickets"
    try:
        candidates = discover_candidate_mutations(context, tickets_dir)
    except InvalidTicketState:
        pause_workspace_automation(project_root, reason="source_context_unhealthy")
        _emit(_paused_response("source_context_unhealthy"))
        return 3
    if not candidates:
        if _has_candidate_changes(context):
            return _emit_mode_projection(mode, context)
        _emit(_no_change_response())
        return 0

    fingerprint_collection = _ticket_state_fingerprints(candidates, tickets_dir)
    if fingerprint_collection.state == "unhealthy":
        pause_workspace_automation(
            project_root,
            reason=fingerprint_collection.reason or "source_context_unhealthy",
        )
        _emit(_paused_response(fingerprint_collection.reason or "source_context_unhealthy"))
        return 3
    fingerprints = fingerprint_collection.fingerprints
    decisions = evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind="apply_ticket_mutations",
            candidates=candidates,
            source_context={"ticket_state_fingerprints": fingerprints},
        ),
        current_mode=mode.value,
        thread_id=str(context["thread_id"]),
        turn_id=str(context["turn_id"]),
    )
    applied: list[str] = []
    skipped: list[str] = []
    blocked: list[str] = []
    blocked_reasons: dict[str, str] = {}
    discussion: list[str] = []
    summary_mutation_ids: list[str] = []
    discussion_question: str | None = None

    for decision in decisions:
        ticket_id = _ticket_label(decision.candidate.ticket_id)
        if decision.kind in {
            RuntimeDecisionKind.APPLY_AUTONOMOUSLY,
            RuntimeDecisionKind.APPLY_CORRECTION,
        }:
            mutation = GatewayMutation(
                action=decision.candidate.action,
                ticket_id=decision.candidate.ticket_id,
                fields=dict(decision.candidate.proposed_change),
                tickets_dir=tickets_dir,
                target_fingerprint=(
                    fingerprints.get(decision.candidate.ticket_id)
                    if isinstance(decision.candidate.ticket_id, str)
                    else None
                ),
            )
            response = apply_autonomous_mutation(
                project_root=project_root,
                thread_id=str(context["thread_id"]),
                turn_id=str(context["turn_id"]),
                repo_context=repo_context,
                mutation=mutation,
                decision=decision,
                pending_summary=store,
            )
            ticket_id = _ticket_label(decision.candidate.ticket_id, response.ticket_id)
            summary_mutation_id = _summarizable_terminal_mutation_id(
                store=store,
                thread_id=str(context["thread_id"]),
                mutation_id=decision.mutation_id,
            )
            if summary_mutation_id is not None:
                summary_mutation_ids.append(summary_mutation_id)
            if response.state == "ok":
                applied.append(ticket_id)
            else:
                discussion.append(ticket_id)
                discussion_question = discussion_question or response.message
            continue

        if decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED:
            blocked.append(ticket_id)
            blocked_reasons[ticket_id] = decision.reason or "ticket_update_blocked"
            continue

        _append_non_write_decision(
            store=store,
            decision=decision,
            thread_id=str(context["thread_id"]),
            turn_id=str(context["turn_id"]),
            repo_context=repo_context,
            current_mode=mode,
        )
        if decision.kind == RuntimeDecisionKind.SKIP_DUE_TO_CONFLICT:
            skipped.append(ticket_id)
        else:
            discussion.append(ticket_id)
            discussion_question = discussion_question or (
                "Review the proposed Ticket update before applying it."
            )

    if summary_mutation_ids or skipped or discussion:
        _append_summary_receipt(
            store=store,
            thread_id=str(context["thread_id"]),
            turn_id=str(context["turn_id"]),
            repo_context=repo_context,
            mutation_ids=tuple(summary_mutation_ids),
        )
    _emit(
        _summary_payload(
            applied=applied,
            skipped=skipped,
            blocked=blocked,
            discussion=discussion,
            discussion_question=discussion_question,
            blocked_reasons=blocked_reasons,
        )
    )
    return 0


def _run_doctor_ledger(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=False)
    if args.dry_run == args.confirm_repair:
        return _invalid_args("choose exactly one of --dry-run or --confirm-repair")

    unsafe = _local_state_setup_required(project_root)
    if unsafe is not None:
        return unsafe

    store = PendingSummaryStore(project_root)
    events, items = _ledger_items_for_project(project_root=project_root, store=store)
    if events is None:
        return _pending_summary_unhealthy()
    if args.dry_run:
        _emit(
            _doctor_ledger_payload(
                events=events,
                items=items,
                repair_confirmed=False,
                changed=False,
                events_appended=0,
            )
        )
        return 0

    events_appended = 0
    for _pass in range(10):
        repairable = [item for item in items if _item_is_repairable(item)]
        reconciliation = [item for item in items if not _item_is_repairable(item)]
        if reconciliation:
            _emit(
                {
                    **_doctor_ledger_payload(
                        events=events,
                        items=items,
                        repair_confirmed=True,
                        changed=events_appended > 0,
                        events_appended=events_appended,
                    ),
                    "state": "paused",
                    "pause_reason": "repair",
                }
            )
            return 3
        if not repairable:
            _emit(
                _doctor_ledger_payload(
                    events=events,
                    items=[],
                    repair_confirmed=True,
                    changed=events_appended > 0,
                    events_appended=events_appended,
                )
            )
            return 0

        for item in repairable:
            for event in item.projection.events_to_append:
                result = store.append_event(event)
                if result.state == "paused":
                    _emit(_paused_response(result.pause_reason or "pending_summary_unhealthy"))
                    return 3
                if result.state == "appended":
                    events_appended += 1
        events, items = _ledger_items_for_project(project_root=project_root, store=store)
        if events is None:
            return _pending_summary_unhealthy()

    _emit(
        {
            **_doctor_ledger_payload(
                events=events,
                items=items,
                repair_confirmed=True,
                changed=events_appended > 0,
                events_appended=events_appended,
            ),
            "state": "paused",
            "pause_reason": "repair",
        }
    )
    return 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ticket autonomy operations")
    subparsers = parser.add_subparsers(dest="command")

    pause = subparsers.add_parser("pause")
    pause.add_argument("--project-root", required=True)
    pause.add_argument("--reason", required=True)

    recover = subparsers.add_parser("recover")
    recover.add_argument("--project-root", required=True)
    recover.add_argument("--turn-id", required=True)

    apply_turn = subparsers.add_parser("apply-turn")
    apply_turn.add_argument("--project-root", required=True)
    apply_turn.add_argument("--turn-id", required=True)
    apply_turn.add_argument("--context-file", required=True)
    apply_turn.add_argument("--setup-choice")
    apply_turn.add_argument("--resume-paused", action="store_true")

    doctor_ledger = subparsers.add_parser("doctor-ledger")
    doctor_ledger.add_argument("--project-root", required=True)
    doctor_ledger.add_argument("--dry-run", action="store_true")
    doctor_ledger.add_argument("--confirm-repair", action="store_true")

    migrate = subparsers.add_parser("migrate-change-history")
    migrate.add_argument("--project-root", required=True)
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Ticket autonomy CLI."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return _invalid_args("invalid command arguments")

    if args.command == "pause":
        return _run_pause(args)
    if args.command == "recover":
        return _run_recover(args)
    if args.command == "apply-turn":
        return _run_apply_turn(args)
    if args.command == "doctor-ledger":
        return _run_doctor_ledger(args)
    if args.command == "migrate-change-history":
        return _run_migrate_change_history(args)
    return _invalid_args("missing command")


if __name__ == "__main__":
    raise SystemExit(main())
