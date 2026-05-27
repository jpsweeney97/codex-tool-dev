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

from scripts.ticket_change_history import plan_change_history_migration  # noqa: E402


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ticket autonomy operations")
    subparsers = parser.add_subparsers(dest="command")

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

    if args.command == "migrate-change-history":
        return _run_migrate_change_history(args)
    return _invalid_args("missing command")


if __name__ == "__main__":
    raise SystemExit(main())
