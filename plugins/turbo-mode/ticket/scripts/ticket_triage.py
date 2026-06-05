"""Ticket triage — read-only analysis of ticket health and audit activity."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_paths import discover_project_root, resolve_tickets_dir  # noqa: E402
from scripts.ticket_payloads import (  # noqa: E402
    DEFAULT_STALE_PAYLOAD_TTL,
    TicketPayloadPathError,
    stale_payloads,
)
from scripts.ticket_target_schema import (  # noqa: E402
    TARGET_ACTIVE_STATUSES,
    TARGET_TERMINAL_STATUSES,
)

_TERMINAL_STATUSES = TARGET_TERMINAL_STATUSES
_ACTIVE_STATUSES = TARGET_ACTIVE_STATUSES
_DOCTOR_MAX_FILES = 5000
_DOCTOR_MAX_BYTES = 100 * 1024 * 1024

# Ticket ID patterns for id_ref matching.
_TICKET_ID_PATTERNS = [
    re.compile(r"T-\d{8}-\d{2,}"),  # v1.0: T-YYYYMMDD-NN
    re.compile(r"T-\d{3}"),  # Gen 3: T-NNN
    re.compile(r"T-[A-F]"),  # Gen 2: T-X
]


class DoctorInputError(ValueError):
    """Raised when doctor arguments would expand the diagnostic trust boundary."""


@dataclass(frozen=True)
class HookCommandManifest:
    """Expected hook commands parsed from hooks.json."""

    commands: frozenset[str]
    manifest_error: str | None = None


def _script_plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _expected_cache_root() -> Path | None:
    """Return the installed cache root for this plugin version, or None.

    Derived from the user home and the manifest version so the doctor trust
    boundary is portable across machines and tracks the plugin version, rather
    than pinning a hardcoded absolute path.
    """
    manifest = _script_plugin_root() / ".codex-plugin" / "plugin.json"
    try:
        version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(version, str) or not version.strip():
        return None
    return Path.home() / ".codex" / "plugins" / "cache" / "turbo-mode" / "ticket" / version


def _validate_doctor_roots(plugin_root: Path, cache_root: Path) -> tuple[Path, Path]:
    """Resolve and constrain doctor roots before any recursive walk."""
    script_root = _script_plugin_root().resolve()
    try:
        resolved_plugin = plugin_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DoctorInputError(
            f"doctor plugin_root failed: path does not exist. Got: {str(plugin_root)!r:.100}"
        ) from exc
    if resolved_plugin != script_root:
        raise DoctorInputError(
            "doctor plugin_root failed: must equal the running plugin root. "
            f"Got: {str(plugin_root)!r:.100}"
        )

    try:
        resolved_cache = cache_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DoctorInputError(
            f"doctor cache_root failed: path does not exist. Got: {str(cache_root)!r:.100}"
        ) from exc
    allowed_cache_roots = {script_root}
    expected_cache = _expected_cache_root()
    if expected_cache is not None:
        allowed_cache_roots.add(expected_cache.resolve(strict=False))
    if resolved_cache not in allowed_cache_roots:
        raise DoctorInputError(
            "doctor cache_root failed: must equal the running plugin root or the expected "
            "Ticket cache root. "
            f"Got: {str(cache_root)!r:.100}"
        )
    return resolved_plugin, resolved_cache


def _tree_manifest(
    root: Path,
    *,
    max_files: int = _DOCTOR_MAX_FILES,
    max_bytes: int = _DOCTOR_MAX_BYTES,
) -> dict[str, str]:
    """Return an exact tree manifest for source/cache comparison."""
    result: dict[str, str] = {}
    if not root.is_dir():
        return result
    file_count = 0
    hashed_bytes = 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[rel] = f"symlink:{path.readlink()}"
            continue
        if path.is_dir():
            result[rel] = "dir:"
            continue
        if path.is_file():
            file_count += 1
            if file_count > max_files:
                raise DoctorInputError(
                    "doctor tree manifest failed: file count limit exceeded. "
                    f"Got: {file_count!r:.100}"
                )
            size = path.stat().st_size
            hashed_bytes += size
            if hashed_bytes > max_bytes:
                raise DoctorInputError(
                    "doctor tree manifest failed: hashed bytes limit exceeded. "
                    f"Got: {hashed_bytes!r:.100}"
                )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[rel] = f"file:{digest}"
            continue
        result[rel] = f"special:{path.stat().st_mode}"
    return result


def _generated_residue(root: Path, *, label: str) -> list[str]:
    """Return generated residue paths that must be removed before final diff."""
    residue_parts = {"__pycache__", ".pytest_cache"}
    residue_names = {".DS_Store"}
    if not root.is_dir():
        return []
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.exists():
            continue
        if path.name in residue_names or any(part in residue_parts for part in path.parts):
            found.append(f"{label}:{path.relative_to(root).as_posix()}")
    return found


def _runtime_probe_status(probe_output: Path | None, plugin_root: Path) -> dict[str, Any]:
    """Classify app-server plugin/read and hooks/list output when provided."""
    command_manifest = _expected_hook_commands_from_manifest(plugin_root)
    expected_source = f"{plugin_root}/hooks/hooks.json"
    if probe_output is None:
        result = {
            "live_hook_probe": "not_run",
            "expected_hook": "Ticket preToolUse / Bash / ticket_engine_guard.py",
        }
        if command_manifest.manifest_error is not None:
            result["manifest_error"] = command_manifest.manifest_error
        return result
    if not probe_output.is_file():
        result = {
            "live_hook_probe": "blocked",
            "reason": f"runtime probe output not found: {probe_output}",
            "expected_hook": "Ticket preToolUse / Bash / ticket_engine_guard.py",
        }
        if command_manifest.manifest_error is not None:
            result["manifest_error"] = command_manifest.manifest_error
        return result
    if command_manifest.manifest_error is not None:
        return {
            "live_hook_probe": "blocked",
            "manifest_error": command_manifest.manifest_error,
            "expected_hook": "Ticket preToolUse / Bash / ticket_engine_guard.py",
        }

    plugin_enabled = False
    matching_hooks: list[dict[str, Any]] = []
    probe_parse_errors = 0
    for line in probe_output.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            probe_parse_errors += 1
            continue
        result = message.get("result", {})
        plugin = result.get("plugin", {})
        summary = plugin.get("summary", {}) if isinstance(plugin, dict) else {}
        if summary.get("id") == "ticket@turbo-mode":
            plugin_enabled = bool(summary.get("enabled") and summary.get("installed"))
        entries = result.get("data", [])
        if isinstance(entries, list):
            for entry in entries:
                if entry.get("warnings") or entry.get("errors"):
                    continue
                hooks = entry.get("hooks", [])
                if not isinstance(hooks, list):
                    continue
                for hook in hooks:
                    if (
                        hook.get("pluginId") == "ticket@turbo-mode"
                        and hook.get("eventName") == "preToolUse"
                        and hook.get("matcher") == "Bash"
                        and hook.get("command") in command_manifest.commands
                        and hook.get("sourcePath") == expected_source
                    ):
                        matching_hooks.append(hook)

    return {
        "live_hook_probe": "proven" if plugin_enabled and len(matching_hooks) == 1 else "blocked",
        "ticket_plugin_enabled": plugin_enabled,
        "ticket_hook_count": len(matching_hooks),
        "probe_parse_errors": probe_parse_errors,
        "expected_hook": "Ticket preToolUse / Bash / ticket_engine_guard.py",
    }


def _expected_hook_commands_from_manifest(plugin_root: Path) -> HookCommandManifest:
    hooks_json = plugin_root / "hooks" / "hooks.json"
    try:
        manifest = json.loads(hooks_json.read_text(encoding="utf-8"))
    except OSError as exc:
        return HookCommandManifest(
            commands=frozenset(),
            manifest_error=f"cannot read hooks.json: {exc}",
        )
    except json.JSONDecodeError as exc:
        return HookCommandManifest(
            commands=frozenset(),
            manifest_error=f"cannot parse hooks.json: {exc}",
        )
    hooks_root = manifest.get("hooks", {})
    if not isinstance(hooks_root, dict):
        return HookCommandManifest(
            commands=frozenset(),
            manifest_error="hooks.json hooks field must be an object",
        )
    pre_tool_entries = hooks_root.get("PreToolUse", [])
    if not isinstance(pre_tool_entries, list):
        return HookCommandManifest(
            commands=frozenset(),
            manifest_error="hooks.json hooks.PreToolUse field must be a list",
        )
    commands: set[str] = set()
    for entry in pre_tool_entries:
        if not isinstance(entry, dict) or entry.get("matcher") != "Bash":
            continue
        hooks = entry.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict) or hook.get("type") != "command":
                continue
            command = hook.get("command")
            if isinstance(command, str) and command:
                commands.add(command)
    if not commands:
        return HookCommandManifest(
            commands=frozenset(),
            manifest_error="hooks.json has no Bash command hooks",
        )
    return HookCommandManifest(commands=frozenset(commands))


def _runtime_proof_status(project_root: Path) -> dict[str, Any]:
    """Return a lightweight diagnostic summary of the saved runtime proof.

    This powers doctor/diagnose reporting only. Execute-readiness remains
    governed by verify_installed_ticket_runtime_readiness_for_execute.
    """
    proof_path = project_root / ".codex" / "ticket-runtime-proof.json"
    if not proof_path.is_file():
        return {
            "proof_path": str(proof_path),
            "exists": False,
            "status": "missing",
        }
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "proof_path": str(proof_path),
            "exists": True,
            "status": "invalid",
            "error": str(exc),
        }
    raw_status = str(proof.get("status", "unknown"))
    expires_at = proof.get("expires_at")
    status = raw_status
    error_code = None
    error = None
    if raw_status == "activated":
        parsed_expires_at = None
        if isinstance(expires_at, str) and expires_at:
            try:
                parsed_expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                parsed_expires_at = None
        if (
            parsed_expires_at is None
            or parsed_expires_at.tzinfo is None
            or parsed_expires_at.utcoffset() is None
        ):
            status = "invalid"
            error_code = "proof_invalid"
            error = "Runtime proof expires_at is invalid"
        elif parsed_expires_at <= datetime.now(UTC):
            status = "stale"
            error_code = "stale_proof"
    result = {
        "proof_path": str(proof_path),
        "exists": True,
        "status": status,
        "raw_status": raw_status,
        "schema_version": proof.get("schema_version"),
        "expires_at": expires_at,
    }
    if error_code is not None:
        result["error_code"] = error_code
    if error is not None:
        result["error"] = error
    return result


def _source_cache_report(plugin_root: Path, cache_root: Path) -> dict[str, Any]:
    """Return exact source/cache diagnostics after roots have been authorized."""
    source_fp = _tree_manifest(plugin_root)
    cache_fp = _tree_manifest(cache_root)
    raw_mismatches = sorted(
        rel for rel in set(source_fp) | set(cache_fp) if source_fp.get(rel) != cache_fp.get(rel)
    )
    mismatches = [
        rel
        for rel in raw_mismatches
        if not (source_fp.get(rel) == "dir:" or cache_fp.get(rel) == "dir:")
        or not any(other.startswith(f"{rel}/") for other in raw_mismatches)
    ]
    hooks_json = plugin_root / "hooks" / "hooks.json"
    return {
        "plugin_root": str(plugin_root),
        "plugin_root_exists": plugin_root.is_dir(),
        "cache_root": str(cache_root),
        "cache_exists": cache_root.is_dir(),
        "source_cache_equal": (
            plugin_root.is_dir() and cache_root.is_dir() and source_fp == cache_fp
        ),
        "source_cache_mismatches": mismatches,
        "generated_residue": _generated_residue(plugin_root, label="source")
        + _generated_residue(cache_root, label="cache"),
        "hooks_json": str(hooks_json),
        "hooks_json_exists": hooks_json.is_file(),
    }


def ticket_doctor(
    tickets_dir: Path,
    *,
    plugin_root: Path,
    cache_root: Path,
    runtime_probe_output: Path | None = None,
) -> dict[str, Any]:
    """Build a static ticket plugin diagnostic report."""
    plugin_root, cache_root = _validate_doctor_roots(plugin_root, cache_root)
    project_root = discover_project_root(tickets_dir)
    if project_root is None:
        raise DoctorInputError(
            "doctor project_root failed: no .codex/ or .git/ marker found. "
            f"Got: {str(tickets_dir)!r:.100}"
        )
    config_path = project_root / ".codex" / "ticket.local.md"
    try:
        stale_payload_rows = [
            {
                "path": str(item.path),
                "age_seconds": item.age_seconds,
                "size_bytes": item.size_bytes,
                "modified_at": item.modified_at,
            }
            for item in stale_payloads(project_root)
        ]
    except TicketPayloadPathError as exc:
        raise DoctorInputError(str(exc)) from exc
    return {
        "project": {
            "project_root": str(project_root),
            "tickets_dir": str(tickets_dir),
            "tickets_dir_exists": tickets_dir.is_dir(),
            "config_path": str(config_path),
            "config_exists": config_path.is_file(),
        },
        "plugin": _source_cache_report(plugin_root, cache_root),
        "runtime": _runtime_probe_status(runtime_probe_output, plugin_root),
        "runtime_proof": _runtime_proof_status(project_root),
        "payloads": {
            "tmp_dir": str(project_root / ".codex" / "ticket-tmp"),
            "stale_after_hours": int(DEFAULT_STALE_PAYLOAD_TTL.total_seconds() // 3600),
            "stale_count": len(stale_payload_rows),
            "stale": stale_payload_rows,
        },
    }


def triage_dashboard(tickets_dir: Path) -> dict[str, Any]:
    """Generate a triage dashboard with ticket counts and alerts.

    Filters to non-terminal statuses (excludes done/wontfix).
    list_tickets returns all tickets in the active directory regardless of
    status field — filtering by status is our job.
    Returns dict with: counts, total, stale, blocked_chains, size_warnings.
    """
    from scripts.ticket_read import list_tickets

    all_tickets = list_tickets(tickets_dir)
    # Filter to actionable tickets (non-terminal status).
    tickets = [t for t in all_tickets if t.status not in _TERMINAL_STATUSES]
    ticket_map = {t.id: t for t in tickets}

    counts: dict[str, int] = {status: 0 for status in _ACTIVE_STATUSES}
    priority_counts: dict[str, int] = {"high": 0, "normal": 0, "low": 0}
    active_ticket_rows: list[dict[str, Any]] = []
    stale: list[dict[str, str]] = []
    blocked_chains: list[dict[str, Any]] = []
    size_warnings: list[dict[str, str]] = []

    for ticket in tickets:
        if ticket.status in counts:
            counts[ticket.status] += 1
        if ticket.priority in priority_counts:
            priority_counts[ticket.priority] += 1
        active_ticket_rows.append(
            {
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status,
                "priority": ticket.priority,
                "blocked_by": ticket.blocked_by,
                "date": ticket.date,
            }
        )

        if _is_stale(ticket):
            stale.append(
                {
                    "id": ticket.id,
                    "title": ticket.title,
                    "status": ticket.status,
                    "date": ticket.date,
                }
            )

        if ticket.blocked_by:
            root_blockers = _find_root_blockers(ticket, ticket_map)
            blocked_chains.append(
                {
                    "id": ticket.id,
                    "title": ticket.title,
                    "root_blockers": root_blockers,
                }
            )

        warning = _check_doc_size(ticket)
        if warning:
            size_warnings.append({"id": ticket.id, "title": ticket.title, "warning": warning})

    return {
        "counts": counts,
        "priority_counts": priority_counts,
        "total": len(tickets),
        "active_tickets": active_ticket_rows,
        "stale": stale,
        "blocked_chains": blocked_chains,
        "next_actions": _next_actions(active_ticket_rows),
        "suggested_capture_prompts": _suggested_capture_prompts(active_ticket_rows),
        "size_warnings": size_warnings,
    }


def _next_actions(active_ticket_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Recommend next actions from dashboard rows only."""
    actions: list[dict[str, str]] = []
    for row in active_ticket_rows:
        if row["priority"] == "high" and row["status"] == "open":
            actions.append(
                {
                    "action": "start_or_assign_high",
                    "ticket_id": row["id"],
                    "reason": "High-priority ticket is open and ready to start or assign",
                }
            )
    for row in active_ticket_rows:
        if row["status"] == "blocked":
            actions.append(
                {
                    "action": "resolve_blocker",
                    "ticket_id": row["id"],
                    "reason": "Blocked ticket needs blocker resolution",
                }
            )
    return actions[:5]


def _suggested_capture_prompts(active_ticket_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return capture prompts for target tickets.

    Target tickets do not carry refinement metadata, so normal review does not
    infer capture follow-up prompts from frontmatter.
    """
    del active_ticket_rows
    return []


def _is_stale(ticket: Any, cutoff_days: int = 7) -> bool:
    """Check if ticket is stale (open/blocked >7 days by ticket date).

    Returns True for unparseable dates (fail toward visibility).
    """
    if ticket.status not in ("open", "blocked"):
        return False
    try:
        ticket_date = datetime.strptime(ticket.date, "%Y-%m-%d").replace(tzinfo=UTC)
        return (datetime.now(UTC) - ticket_date).days > cutoff_days
    except ValueError:
        return True


def _find_root_blockers(ticket: Any, ticket_map: dict[str, Any]) -> list[str]:
    """Follow blocked_by chains to find root blockers."""
    visited: set[str] = set()
    roots: list[str] = []

    def _walk(tid: str) -> None:
        if tid in visited:
            return
        visited.add(tid)
        t = ticket_map.get(tid)
        if t is None or not t.blocked_by:
            roots.append(tid)
            return
        for bid in t.blocked_by:
            _walk(bid)

    for bid in ticket.blocked_by:
        _walk(bid)
    return roots


def _check_doc_size(ticket: Any) -> str | None:
    """Check ticket document size, return warning string if large or unreadable."""
    try:
        size = Path(ticket.path).stat().st_size
    except OSError:
        return "error: file unreadable"
    if size >= 32768:
        return f"strong_warn: {size // 1024}KB (>32KB)"
    if size >= 16384:
        return f"warn: {size // 1024}KB (>16KB)"
    return None


def triage_audit_report(tickets_dir: Path, days: int = 7) -> dict[str, Any]:
    """Summarize recent autonomous actions from audit trail.

    Reads .audit/YYYY-MM-DD/<session_id>.jsonl files within the lookback window.
    Returns dict with: total_entries, by_action, by_result, sessions,
    skipped_lines, read_errors.
    """
    audit_base = tickets_dir / ".audit"
    if not audit_base.is_dir():
        return {
            "total_entries": 0,
            "by_action": {},
            "by_result": {},
            "sessions": 0,
            "skipped_lines": 0,
            "read_errors": 0,
        }

    now = datetime.now(UTC)
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    entries: list[dict[str, Any]] = []
    session_ids: set[str] = set()
    skipped_lines = 0
    read_errors = 0

    for date_dir in sorted(audit_base.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            continue
        if dir_date < cutoff:
            continue
        for jsonl_file in date_dir.glob("*.jsonl"):
            session_ids.add(jsonl_file.stem)
            try:
                for line in jsonl_file.read_text(encoding="utf-8").strip().split("\n"):
                    if not line.strip():
                        continue
                    try:
                        entries.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        skipped_lines += 1
            except OSError:
                read_errors += 1

    by_action: dict[str, int] = {}
    by_result: dict[str, int] = {}
    for entry in entries:
        action = entry.get("action", "unknown")
        by_action[action] = by_action.get(action, 0) + 1
        result = entry.get("result")
        if result is not None:
            by_result[str(result)] = by_result.get(str(result), 0) + 1

    return {
        "total_entries": len(entries),
        "by_action": by_action,
        "by_result": by_result,
        "sessions": len(session_ids),
        "skipped_lines": skipped_lines,
        "read_errors": read_errors,
    }


def triage_orphan_detection(
    tickets_dir: Path,
    handoffs_dir: Path,
) -> dict[str, Any]:
    """Detect orphaned handoff items not linked to any ticket.

    Matching strategies:
    1. id_ref: handoff text contains a ticket ID
    2. manual_review: no deterministic match
    """
    from scripts.ticket_read import list_tickets

    tickets = list_tickets(tickets_dir)
    ticket_ids = {t.id for t in tickets}
    matched: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []
    read_errors: list[str] = []

    if not handoffs_dir.is_dir():
        return {
            "matched": matched,
            "orphaned": orphaned,
            "total_items": 0,
            "read_errors": read_errors,
        }

    for hf in sorted(handoffs_dir.glob("*.md")):
        try:
            text = hf.read_text(encoding="utf-8")
        except OSError:
            read_errors.append(hf.name)
            continue

        item: dict[str, str] = {"file": hf.name, "path": str(hf)}
        match_found = False

        # Strategy 1: id_ref -- ticket ID referenced in handoff text.
        for pattern in _TICKET_ID_PATTERNS:
            refs = pattern.findall(text)
            for ref in refs:
                if ref in ticket_ids:
                    matched.append({"match_type": "id_ref", "matched_ticket": ref, "item": item})
                    match_found = True
                    break
            if match_found:
                break

        if match_found:
            continue

        # Strategy 2: manual_review -- no deterministic match.
        orphaned.append({"match_type": "manual_review", "matched_ticket": None, "item": item})

    return {
        "matched": matched,
        "orphaned": orphaned,
        "total_items": len(matched) + len(orphaned),
        "read_errors": read_errors,
    }


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Ticket triage operations")
    subparsers = parser.add_subparsers(dest="subcommand")

    dash_p = subparsers.add_parser("dashboard")
    dash_p.add_argument("tickets_dir", type=Path)

    audit_p = subparsers.add_parser("audit")
    audit_p.add_argument("tickets_dir", type=Path)
    audit_p.add_argument("--days", type=int, default=7)

    doctor_p = subparsers.add_parser("doctor")
    doctor_p.add_argument("tickets_dir", type=Path)
    doctor_p.add_argument("--plugin-root", type=Path, required=True)
    doctor_p.add_argument("--cache-root", type=Path, required=True)
    doctor_p.add_argument("--runtime-probe-output", type=Path, default=None)

    args = parser.parse_args()

    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        sys.exit(1)

    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        print(
            json.dumps(
                {
                    "state": "policy_blocked",
                    "message": "Cannot find project root (no .git or .codex marker in ancestors)",
                    "error_code": "policy_blocked",
                }
            )
        )
        sys.exit(1)
    tickets_dir, path_error = resolve_tickets_dir(args.tickets_dir, project_root=project_root)
    if path_error is not None or tickets_dir is None:
        print(
            json.dumps(
                {
                    "state": "policy_blocked",
                    "message": path_error or "tickets_dir validation failed",
                    "error_code": "policy_blocked",
                }
            )
        )
        sys.exit(1)

    if args.subcommand == "dashboard":
        result = triage_dashboard(tickets_dir)
        print(json.dumps({"state": "ok", "data": result}))

    elif args.subcommand == "audit":
        result = triage_audit_report(tickets_dir, days=args.days)
        print(json.dumps({"state": "ok", "data": result}))

    elif args.subcommand == "doctor":
        try:
            result = ticket_doctor(
                tickets_dir,
                plugin_root=args.plugin_root,
                cache_root=args.cache_root,
                runtime_probe_output=args.runtime_probe_output,
            )
        except DoctorInputError as exc:
            print(
                json.dumps(
                    {
                        "state": "escalate",
                        "message": str(exc),
                        "error_code": "invalid_doctor_root",
                    }
                )
            )
            sys.exit(1)
        print(json.dumps({"state": "ok", "data": result}))


if __name__ == "__main__":
    main()
