#!/usr/bin/env python3
"""Standalone audit maintenance utilities for ticket JSONL logs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_paths import discover_project_root, resolve_tickets_dir


def _response(state: str, message: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"state": state, "message": message, "data": data}


def _empty_data() -> dict[str, Any]:
    return {
        "files_scanned": 0,
        "corrupt_files": 0,
        "repaired_files": [],
        "backup_paths": [],
        "issues": [],
    }


def _parse_args(argv: list[str]) -> tuple[str | None, str | None, bool, str | None]:
    dry_run = True  # Default: safe mode (report only)
    args = list(argv)
    if "--fix" in args:
        dry_run = False
        args.remove("--fix")
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    if len(args) != 2 or args[0] != "repair":
        return None, None, True, "Usage: ticket_audit.py repair <tickets_dir> [--fix | --dry-run]"
    return args[0], args[1], dry_run, None


def _iter_audit_files(tickets_dir: Path) -> list[Path]:
    audit_root = tickets_dir / ".audit"
    if not audit_root.exists():
        return []
    return sorted(
        path
        for path in audit_root.rglob("*.jsonl")
        if path.is_file() and ".bak-" not in path.name
    )


def _scan_audit_file(audit_file: Path) -> tuple[str, list[str], list[int]]:
    try:
        original_text = audit_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(
            f"audit repair failed: cannot read {audit_file}: {exc}. Got: {str(audit_file)!r:.100}"
        ) from exc

    valid_lines: list[str] = []
    corrupt_lines: list[int] = []
    for line_number, raw_line in enumerate(original_text.splitlines(), start=1):
        try:
            parsed = json.loads(raw_line)
        except json.JSONDecodeError:
            corrupt_lines.append(line_number)
            continue
        if not isinstance(parsed, dict):
            corrupt_lines.append(line_number)
            continue
        valid_lines.append(raw_line)
    return original_text, valid_lines, corrupt_lines


def _write_backup_and_repair(
    audit_file: Path,
    *,
    original_text: str,
    valid_lines: list[str],
    timestamp: str,
) -> Path:
    backup_path = audit_file.parent / f"{audit_file.name}.bak-{timestamp}"
    repaired_text = "\n".join(valid_lines)
    if repaired_text:
        repaired_text += "\n"

    try:
        backup_path.write_text(original_text, encoding="utf-8")
        audit_file.write_text(repaired_text, encoding="utf-8")
    except OSError as exc:
        raise OSError(
            f"audit repair failed: cannot write repair output for {audit_file}: {exc}. Got: {str(audit_file)!r:.100}"
        ) from exc
    return backup_path


def repair_audit_logs(*, tickets_dir: Path, dry_run: bool) -> tuple[dict[str, Any], int]:
    data = _empty_data()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        audit_files = _iter_audit_files(tickets_dir)
        data["files_scanned"] = len(audit_files)

        for audit_file in audit_files:
            original_text, valid_lines, corrupt_lines = _scan_audit_file(audit_file)
            if not corrupt_lines:
                continue

            data["corrupt_files"] += 1
            data["issues"].append(
                {
                    "path": str(audit_file),
                    "corrupt_lines": corrupt_lines,
                    "valid_lines": len(valid_lines),
                }
            )

            if dry_run:
                continue

            backup_path = _write_backup_and_repair(
                audit_file,
                original_text=original_text,
                valid_lines=valid_lines,
                timestamp=timestamp,
            )
            data["repaired_files"].append(str(audit_file))
            data["backup_paths"].append(str(backup_path))
    except OSError as exc:
        return _response("error", str(exc), data), 1

    if dry_run:
        if data["corrupt_files"]:
            message = f"Dry run found corruption in {data['corrupt_files']} audit file(s)."
        else:
            message = "Dry run found no audit corruption."
    else:
        if data["repaired_files"]:
            message = f"Repaired {len(data['repaired_files'])} audit file(s)."
        else:
            message = "No audit corruption found."
    return _response("ok", message, data), 0


def main(argv: list[str] | None = None) -> int:
    command, raw_tickets_dir, dry_run, error = _parse_args(list(sys.argv[1:] if argv is None else argv))
    data = _empty_data()
    if error is not None or command is None or raw_tickets_dir is None:
        print(json.dumps(_response("error", error or "Invalid arguments", data)))
        return 1

    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        print(json.dumps(_response("error", "Cannot find project root (no .git or .codex marker in ancestors)", data)))
        return 1
    tickets_dir, path_error = resolve_tickets_dir(raw_tickets_dir, project_root=project_root)
    if path_error is not None or tickets_dir is None:
        print(json.dumps(_response("error", path_error or "tickets_dir validation failed", data)))
        return 1

    response, exit_code = repair_audit_logs(tickets_dir=tickets_dir, dry_run=dry_run)
    print(json.dumps(response))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
