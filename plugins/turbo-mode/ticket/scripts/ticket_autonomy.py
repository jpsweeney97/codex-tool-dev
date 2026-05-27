#!/usr/bin/env python3
"""Host-facing Ticket autonomy CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from scripts.ticket_change_history import plan_change_history_migration  # noqa: E402
from scripts.ticket_turn_batch import PendingSummaryStore  # noqa: E402

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
    events = store.read_events()
    _emit(
        {
            "state": "ok",
            "turn_id": args.turn_id,
            "can_proceed": True,
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
        return _emit_mode_projection(mode, context)

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
    return _emit_mode_projection(resolved.mode, context)


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
