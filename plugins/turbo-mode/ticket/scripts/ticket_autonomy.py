#!/usr/bin/env python3
"""Host-facing Ticket autonomy CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
from scripts.ticket_read import find_ticket_by_id  # noqa: E402
from scripts.ticket_turn_batch import (  # noqa: E402
    PENDING_SUMMARY_SCHEMA,
    PendingSummaryStore,
    VerifiedRepoContext,
    event_payload_fingerprint,
)

TURN_CONTEXT_SCHEMA = "codex.ticket.turn_context.v1"
SETUP_CHOICES = ["automatic", "ask_first"]


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
    if mode == AutomationMode.PREVIEW:
        _emit(
            {
                "state": "preview",
                "changed": False,
                "ticket_updates": [],
                "discussion_question": None,
            }
        )
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
    if decision.kind == RuntimeDecisionKind.PREVIEW_ONLY:
        status = "skipped"
        details: dict[str, object] = {
            "decision": RuntimeDecisionKind.PREVIEW_ONLY.value,
            "current_mode": current_mode.value,
            "evidence_kind": "runtime_context",
        }
        reason = "Preview-only Ticket mutation."
    elif decision.kind == RuntimeDecisionKind.SKIP_DUE_TO_CONFLICT:
        status = "skipped"
        details = {
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
) -> None:
    event = _event_payload(
        event_type="summary_receipt",
        status="summarized",
        action="summarize",
        ticket_id=None,
        mutation_id=None,
        thread_id=thread_id,
        turn_id=turn_id,
        repo_context=repo_context,
        reason="Apply-turn summary returned.",
        details={},
    )
    store.append_event(event)


def _ticket_state_fingerprints(candidates: tuple[Any, ...], tickets_dir: Path) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for candidate in candidates:
        ticket_id = candidate.ticket_id
        if not isinstance(ticket_id, str):
            continue
        ticket = find_ticket_by_id(tickets_dir, ticket_id, include_closed=True)
        if ticket is None:
            continue
        fingerprint = compute_target_fingerprint(Path(ticket.path))
        if fingerprint is not None:
            fingerprints[ticket_id] = fingerprint
    return fingerprints


def _summary_payload(
    *,
    applied: list[str],
    skipped: list[str],
    discussion: list[str],
    discussion_question: str | None,
) -> dict[str, Any]:
    if not applied and not skipped and not discussion and discussion_question is None:
        return _no_change_response()
    ticket_updates: dict[str, list[str]] = {}
    if applied:
        ticket_updates["Applied"] = applied
    if skipped:
        ticket_updates["Skipped"] = skipped
    if discussion:
        ticket_updates["Discussion required"] = discussion
    if applied:
        state = "applied"
    elif discussion:
        state = "discussion_required"
    else:
        state = "preview"
    return {
        "state": state,
        "changed": bool(applied),
        "ticket_updates": ticket_updates,
        "discussion_question": discussion_question,
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
    store = PendingSummaryStore(project_root)
    compaction = store.compact_correction_ready_events()
    if compaction.state == "paused":
        _emit(_paused_response(compaction.pause_reason or "pending_summary_unhealthy"))
        return 3
    events = store.read_events()
    _emit(
        {
            "state": "ok",
            "turn_id": args.turn_id,
            "can_proceed": True,
            "compaction_state": compaction.state,
            "event_count": len(events),
            "ticket_updates": None,
            "discussion_question": None,
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
    if setup_choice_value is not None:
        if setup_choice_value == AutomationMode.PREVIEW.value:
            return _invalid_args("preview is a manual-only config mode")
        try:
            setup_choice = SetupChoice(setup_choice_value)
        except ValueError:
            return _invalid_args("setup choice must be automatic or ask_first")

        unsafe = _local_state_setup_required(project_root)
        if unsafe is not None:
            return unsafe
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

    tickets_dir = project_root / "docs" / "tickets"
    candidates = discover_candidate_mutations(context, tickets_dir)
    if not candidates:
        if _has_candidate_changes(context):
            return _emit_mode_projection(mode, context)
        _emit(_no_change_response())
        return 0

    fingerprints = _ticket_state_fingerprints(candidates, tickets_dir)
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
    store = PendingSummaryStore(project_root)
    applied: list[str] = []
    skipped: list[str] = []
    discussion: list[str] = []
    discussion_question: str | None = None

    for decision in decisions:
        ticket_id = decision.candidate.ticket_id or "new ticket"
        if decision.kind == RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
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
            if response.state.startswith("ok_"):
                applied.append(ticket_id)
            else:
                discussion.append(ticket_id)
                discussion_question = discussion_question or response.message
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
        elif decision.kind == RuntimeDecisionKind.PREVIEW_ONLY:
            skipped.append(ticket_id)
        else:
            discussion.append(ticket_id)
            discussion_question = discussion_question or (
                "Review the proposed Ticket update before applying it."
            )

    _append_summary_receipt(
        store=store,
        thread_id=str(context["thread_id"]),
        turn_id=str(context["turn_id"]),
        repo_context=repo_context,
    )
    _emit(
        _summary_payload(
            applied=applied,
            skipped=skipped,
            discussion=discussion,
            discussion_question=discussion_question,
        )
    )
    return 0


def _run_doctor_ledger(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=False)
    if args.dry_run == args.confirm_repair:
        return _invalid_args("choose exactly one of --dry-run or --confirm-repair")

    store = PendingSummaryStore(project_root)
    events = store.read_events()
    _emit(
        {
            "state": "ok",
            "healthy": True,
            "changed": False,
            "repair_confirmed": bool(args.confirm_repair),
            "event_count": len(events),
        }
    )
    return 0


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
