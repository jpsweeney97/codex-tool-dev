"""Ticket engine core — classify | plan | preflight | execute pipeline.

All mutation and policy-enforcement logic lives here. Entrypoints
(ticket_engine_user.py, ticket_engine_agent.py) set request_origin
and delegate to this module.

Subcommand contract: each function returns an EngineResponse with
{state, ticket_id, message, data}.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from scripts.ticket_id import allocate_id, build_filename
from scripts.ticket_parse import (
    ParsedTicket,
    extract_fenced_yaml,
    parse_yaml_block,
)
from scripts.ticket_paths import discover_project_root
from scripts.ticket_render import render_ticket, replace_fenced_yaml
from scripts.ticket_trust import collect_trust_triple_errors
from scripts.ticket_validate import validate_fields


# --- Helpers ---


def _list_tickets_with_closed(tickets_dir: Path) -> list[ParsedTicket]:
    """List all tickets including archived (closed-tickets/).

    Used by blocker resolution and dedup scanning. Single source of truth
    to prevent C-003 regression (archived tickets invisible to dependency checks).
    """
    from scripts.ticket_read import list_tickets

    return list_tickets(tickets_dir, include_closed=True)


_V10_GENERATION = 10  # v1.0 tickets have generation=10; legacy is 1-4.
_CONTRACT_VERSION = "1.0"  # Current contract version; stamped on every write.


def _check_legacy_gate(ticket: ParsedTicket) -> EngineResponse | None:
    """Reject writes to legacy-format tickets (generation < 10).

    Contract §8: Read-only for legacy formats. Conversion on update
    (with user confirmation). Until confirm-and-convert is implemented,
    all non-create writes to legacy tickets are rejected.

    Returns EngineResponse if blocked, None if allowed.
    """
    if ticket.generation < _V10_GENERATION:
        return EngineResponse(
            state="policy_blocked",
            message=(
                f"Legacy ticket (generation {ticket.generation}) is read-only. "
                f"Contract §8 requires conversion with user confirmation before mutation. "
                f"Use 'ticket migrate {ticket.id}' when available (v1.1)."
            ),
            ticket_id=ticket.id,
            error_code="policy_blocked",
        )
    return None


# --- Response envelope ---


@dataclass
class EngineResponse:
    """Common response envelope for all engine subcommands.

    state: machine state (15 total: 14 emittable + 1 reserved)
    error_code: machine-readable error code (12 defined codes, or None on success)
    ticket_id: affected ticket ID or None
    message: human-readable description
    data: subcommand-specific output
    """

    state: str
    message: str
    error_code: str | None = None
    ticket_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    _OK_STATES: frozenset[str] = field(
        default=frozenset({
            "ok", "ok_create", "ok_update", "ok_close", "ok_close_archived", "ok_reopen",
        }),
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.state in self._OK_STATES:
            if self.error_code is not None:
                raise ValueError(
                    f"error_code must be None for success state {self.state!r}, "
                    f"got {self.error_code!r}"
                )
        else:
            if self.error_code is None:
                raise ValueError(
                    f"error_code is required for non-success state {self.state!r}. "
                    f"Message: {self.message!r:.100}"
                )

    def to_dict(self) -> dict[str, Any]:
        d = {
            "state": self.state,
            "ticket_id": self.ticket_id,
            "message": self.message,
            "data": self.data,
        }
        if self.error_code is not None:
            d["error_code"] = self.error_code
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# Sentinel for audit read failures.
AUDIT_UNAVAILABLE = object()

AutonomyMode = Literal["suggest", "auto_audit", "auto_silent"]
_VALID_AUTONOMY_MODES = frozenset({"suggest", "auto_audit", "auto_silent"})


@dataclass(frozen=True)
class AutonomyConfig:
    """Autonomy configuration parsed from .codex/ticket.local.md.

    Frozen and self-validating: invalid mode/max_creates are self-healed
    to safe defaults in __post_init__. Immutable after construction to
    prevent TOCTOU mutations between preflight and execute.

    mode: "suggest" (default) | "auto_audit" | "auto_silent"
    max_creates: per-session create cap (default 5, 0 = disable agent creates)
    warnings: parsing/validation warnings (empty tuple if clean)
    """

    mode: AutonomyMode = "suggest"
    max_creates: int = 5
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        extra_warnings: list[str] = []
        if self.mode not in _VALID_AUTONOMY_MODES:
            extra_warnings.append(f"Invalid mode {self.mode!r}, defaulted to 'suggest'")
            object.__setattr__(self, "mode", "suggest")
        if not isinstance(self.max_creates, int) or self.max_creates < 0:
            extra_warnings.append(f"Invalid max_creates {self.max_creates!r}, defaulted to 5")
            object.__setattr__(self, "max_creates", 5)
        if extra_warnings:
            object.__setattr__(self, "warnings", self.warnings + tuple(extra_warnings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "max_creates": self.max_creates,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomyConfig:
        """Reconstruct from dict (snapshot deserialization).

        Validates through __post_init__ — invalid values are self-healed
        to safe defaults with warnings appended.
        """
        return cls(
            mode=data.get("mode", "suggest"),
            max_creates=data.get("max_creates", 5),
            warnings=tuple(data.get("warnings", ())),
        )


# --- Valid actions and origins ---

VALID_ACTIONS = frozenset({"create", "update", "close", "reopen"})
VALID_ORIGINS = frozenset({"user", "agent"})


# --- classify ---


def engine_classify(
    *,
    action: str,
    args: dict[str, Any],
    session_id: str,
    request_origin: str,
) -> EngineResponse:
    """Classify the caller's intent and validate the action.

    Input action (from first-token routing) is authoritative. Classify validates
    but does not remap. If classify's intent disagrees -> intent_mismatch -> escalate.

    Returns EngineResponse with state="ok" on success, or error state on failure.
    """
    # Fail closed on unknown origin.
    if request_origin not in VALID_ORIGINS:
        return EngineResponse(
            state="escalate",
            message=f"Cannot determine caller identity: request_origin={request_origin!r}",
            error_code="origin_mismatch",
        )

    # Validate action.
    if action not in VALID_ACTIONS:
        return EngineResponse(
            state="escalate",
            message=f"Unknown action: {action!r}. Valid: {', '.join(sorted(VALID_ACTIONS))}",
            error_code="intent_mismatch",
        )

    # Resolve ticket ID from args (for non-create actions).
    resolved_ticket_id = args.get("ticket_id") if action != "create" else None

    # Confidence: high for explicit invocations (first-token routing provides strong signal).
    # This is a provisional default — calibration on labeled corpus required pre-GA.
    confidence = 0.95

    return EngineResponse(
        state="ok",
        message=f"Classified as {action}",
        data={
            "intent": action,
            "confidence": confidence,
            "classify_intent": action,
            "classify_confidence": confidence,
            "resolved_ticket_id": resolved_ticket_id,
        },
    )


# --- plan ---

# Required fields for create.
_CREATE_REQUIRED = ("title", "problem", "priority")

# Dedup window.
_DEDUP_WINDOW_HOURS = 24


def engine_plan(
    *,
    intent: str,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    ticket_id: str | None = None,
) -> EngineResponse:
    """Plan stage: validate fields, check duplicates, compute fingerprints.

    For create: validates required fields, computes dedup fingerprint,
    scans for duplicates within 24h window.
    For other intents: resolves ticket and computes target_fingerprint
    for TOCTOU protection in execute.

    Args:
        ticket_id: Top-level ticket_id from payload (for update/close/reopen).
    """
    if intent == "create":
        return _plan_create(fields, session_id, request_origin, tickets_dir)

    # Non-create: resolve ticket and compute target_fingerprint.
    resolved_id = ticket_id or fields.get("ticket_id")
    computed_fp: str | None = None
    if resolved_id:
        from scripts.ticket_dedup import target_fingerprint as compute_fp
        from scripts.ticket_read import find_ticket_by_id

        ticket = find_ticket_by_id(tickets_dir, resolved_id)
        if ticket is not None:
            computed_fp = compute_fp(Path(ticket.path))

    return EngineResponse(
        state="ok",
        message=f"Plan pass-through for {intent}",
        data={
            "dedup_fingerprint": None,
            "target_fingerprint": computed_fp,
            "duplicate_of": None,
            "missing_fields": [],
            "action_plan": {"intent": intent},
        },
    )


def _plan_create(
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
) -> EngineResponse:
    """Plan stage for create: field validation + dedup."""
    from scripts.ticket_dedup import dedup_fingerprint

    # Check required fields.
    missing = [f for f in _CREATE_REQUIRED if not fields.get(f)]
    if missing:
        return EngineResponse(
            state="need_fields",
            message=f"Missing required fields: {', '.join(missing)}",
            error_code="need_fields",
            data={"missing_fields": missing},
        )

    validation_errors = validate_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            data={"missing_fields": [], "validation_errors": validation_errors},
        )

    # Compute dedup fingerprint.
    problem_text = fields["problem"]
    key_file_paths = fields.get("key_file_paths", [])
    fp = dedup_fingerprint(problem_text, key_file_paths)

    # Scan for duplicates within 24h window.
    duplicate_of = None
    dup_target_fp = None
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=_DEDUP_WINDOW_HOURS)

    existing = _list_tickets_with_closed(tickets_dir)
    for ticket in existing:
        # Check if ticket is within dedup window.
        # Primary: created_at (ISO 8601 UTC, second-level precision).
        # Fallback: date field (day-level) treated as end-of-day (23:59:59 UTC)
        # for maximum inclusivity — never misses a near-midnight duplicate.
        # No filesystem dependency (mtime) — immune to git checkout/clone.
        if ticket.created_at:
            try:
                ticket_time = datetime.strptime(
                    ticket.created_at, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                ticket_time = None
        else:
            ticket_time = None

        if ticket_time is None:
            try:
                day = datetime.strptime(ticket.date, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                # End-of-day: assume latest possible creation time on that date.
                ticket_time = day.replace(hour=23, minute=59, second=59)
            except (ValueError, TypeError):
                continue

        if ticket_time < cutoff:
            continue

        # Compute fingerprint for this ticket's problem text.
        ticket_problem = ticket.sections.get("Problem", "")
        # Prefer persisted key_file_paths (v1.0+) over regex extraction.
        ticket_key_file_paths: list[str] = ticket.frontmatter.get("key_file_paths", [])
        if not ticket_key_file_paths:
            # Fallback: extract from rendered Key Files section.
            key_files_section = ticket.sections.get("Key Files", "")
            if key_files_section:
                for match in re.finditer(r"^\| ([^|]+) \|", key_files_section, re.MULTILINE):
                    cell = match.group(1).strip()
                    if cell and cell != "File" and not cell.startswith("-"):
                        ticket_key_file_paths.append(cell)

        existing_fp = dedup_fingerprint(ticket_problem, ticket_key_file_paths)
        if existing_fp == fp:
            from scripts.ticket_dedup import target_fingerprint

            duplicate_of = ticket.id
            dup_target_fp = target_fingerprint(Path(ticket.path))
            break

    if duplicate_of:
        return EngineResponse(
            state="duplicate_candidate",
            message=f"Potential duplicate of {duplicate_of}",
            ticket_id=duplicate_of,
            error_code="duplicate_candidate",
            data={
                "dedup_fingerprint": fp,
                "target_fingerprint": dup_target_fp,
                "duplicate_of": duplicate_of,
                "missing_fields": [],
                "action_plan": {"intent": "create", "duplicate_candidate": True},
            },
        )

    return EngineResponse(
        state="ok",
        message="Plan complete, no duplicates found",
        data={
            "dedup_fingerprint": fp,
            "target_fingerprint": None,
            "duplicate_of": None,
            "missing_fields": [],
            "action_plan": {"intent": "create"},
        },
    )


# --- preflight ---

# Confidence thresholds (provisional — calibrate pre-GA).
_T_BASE = 0.5
_ORIGIN_MODIFIER: dict[str, float] = {"user": 0.0, "agent": 0.15}

# Terminal statuses for dependency resolution.
_TERMINAL_STATUSES = frozenset({"done", "wontfix"})


def read_autonomy_config(tickets_dir: Path) -> AutonomyConfig:
    """Read autonomy config from .codex/ticket.local.md YAML frontmatter.

    Project root discovery reuses the same marker-based lookup as the
    entrypoints (.codex/, .git/, or .git worktree file).

    Fail-closed: returns AutonomyConfig(mode="suggest") on any error.
    Emits warnings to stderr for malformed/unknown values.
    """
    warnings: list[str] = []
    project_root = discover_project_root(tickets_dir)
    if project_root is None:
        return AutonomyConfig()

    config_path = project_root / ".codex" / "ticket.local.md"
    if not config_path.is_file():
        return AutonomyConfig()

    try:
        import yaml

        text = config_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            warnings.append("ticket.local.md: file exists but has no valid frontmatter (missing --- delimiters)")
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)
            return AutonomyConfig(warnings=tuple(warnings))
        parts = text.split("---", 2)
        if len(parts) < 3:
            warnings.append("ticket.local.md: file exists but has no valid frontmatter (incomplete --- delimiters)")
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)
            return AutonomyConfig(warnings=tuple(warnings))
        data = yaml.safe_load(parts[1])
        if not isinstance(data, dict):
            warnings.append("ticket.local.md: frontmatter is not a dict")
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)
            return AutonomyConfig(warnings=tuple(warnings))
    except (OSError, ValueError) as exc:
        warnings.append(f"ticket.local.md: failed to parse YAML: {exc}")
        print(f"WARNING: {warnings[-1]}", file=sys.stderr)
        return AutonomyConfig(warnings=tuple(warnings))
    except Exception as exc:
        # yaml.YAMLError doesn't share a base with OSError/ValueError.
        # Keep unexpected non-YAML exceptions visible.
        if "yaml" in type(exc).__module__.lower():
            warnings.append(f"ticket.local.md: failed to parse YAML: {exc}")
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)
            return AutonomyConfig(warnings=tuple(warnings))
        raise

    # Parse mode.
    mode = data.get("autonomy_mode", "suggest")
    if mode not in _VALID_AUTONOMY_MODES:
        warnings.append(
            f"ticket.local.md: unknown autonomy_mode {mode!r}, defaulting to 'suggest'"
        )
        print(f"WARNING: {warnings[-1]}", file=sys.stderr)
        mode = "suggest"

    # Parse max_creates.
    max_creates = data.get("max_creates_per_session", 5)
    if not isinstance(max_creates, int) or max_creates < 0:
        warnings.append(
            f"ticket.local.md: invalid max_creates_per_session {max_creates!r}, defaulting to 5"
        )
        print(f"WARNING: {warnings[-1]}", file=sys.stderr)
        max_creates = 5

    return AutonomyConfig(mode=mode, max_creates=max_creates, warnings=tuple(warnings))


def engine_preflight(
    *,
    ticket_id: str | None,
    action: str,
    session_id: str,
    request_origin: str,
    classify_confidence: float,
    classify_intent: str,
    dedup_fingerprint: str | None,
    target_fingerprint: str | None,
    fields: dict[str, Any] | None = None,
    duplicate_of: str | None = None,
    dedup_override: bool = False,
    dependency_override: bool = False,
    hook_injected: bool = False,
    tickets_dir: Path,
) -> EngineResponse:
    """Preflight: single enforcement point for all mutating operations.

    Checks in order: origin, action, autonomy policy, confidence, intent match,
    dedup, ticket existence, dependency integrity, TOCTOU fingerprint.
    """
    checks_passed: list[str] = []
    checks_failed: list[dict[str, str]] = []
    preflight_fields = fields or {}

    # --- Origin check ---
    if request_origin not in VALID_ORIGINS:
        return EngineResponse(
            state="escalate",
            message=f"Cannot determine caller identity: request_origin={request_origin!r}",
            error_code="origin_mismatch",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "origin", "reason": "unknown origin"}],
            },
        )
    checks_passed.append("origin")

    # --- Action validation (Codex finding 3: defense-in-depth) ---
    if action not in VALID_ACTIONS:
        return EngineResponse(
            state="escalate",
            message=f"Unknown action: {action!r}. Valid: {', '.join(sorted(VALID_ACTIONS))}",
            error_code="intent_mismatch",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "action", "reason": "unknown action"}],
            },
        )
    checks_passed.append("action")

    # --- Autonomy policy (Codex finding 5: agent checks before confidence) ---
    config = read_autonomy_config(tickets_dir)
    notification: str | None = None

    if request_origin == "agent":
        # Action exclusions: reopen is user-only in v1.0.
        if action == "reopen":
            return EngineResponse(
                state="policy_blocked",
                message="Reopen is user-only in v1.0",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "agent_action_exclusion", "reason": "reopen is user-only"}],
                    "autonomy_config": config.to_dict(),
                },
            )

        # Override rejection: agents cannot use dedup_override or dependency_override.
        if dedup_override:
            return EngineResponse(
                state="policy_blocked",
                message="Agents cannot use dedup_override",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "agent_override_rejection", "reason": "dedup_override not allowed for agents"}],
                    "autonomy_config": config.to_dict(),
                },
            )
        if dependency_override:
            return EngineResponse(
                state="policy_blocked",
                message="Agents cannot use dependency_override",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "agent_override_rejection", "reason": "dependency_override not allowed for agents"}],
                    "autonomy_config": config.to_dict(),
                },
            )

        # Autonomy mode enforcement.
        if config.mode == "suggest":
            return EngineResponse(
                state="policy_blocked",
                message=f"Autonomy mode 'suggest': agent {action} requires user approval",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "autonomy_mode", "reason": "suggest mode blocks agents"}],
                    "autonomy_config": config.to_dict(),
                },
            )

        if config.mode == "auto_silent":
            return EngineResponse(
                state="policy_blocked",
                message="Autonomy mode 'auto_silent' is not available in v1.0",
                error_code="policy_blocked",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "autonomy_mode", "reason": "auto_silent gated in v1.0"}],
                    "autonomy_config": config.to_dict(),
                },
            )

        # auto_audit: check session cap for create actions.
        if config.mode == "auto_audit" and action == "create":
            count = engine_count_session_creates(session_id, tickets_dir)
            if count is AUDIT_UNAVAILABLE:
                return EngineResponse(
                    state="policy_blocked",
                    message="Cannot verify session create count (audit trail unavailable)",
                    error_code="policy_blocked",
                    data={
                        "checks_passed": checks_passed,
                        "checks_failed": [{"check": "session_cap", "reason": "audit unavailable"}],
                        "autonomy_config": config.to_dict(),
                    },
                )
            if count >= config.max_creates:
                return EngineResponse(
                    state="policy_blocked",
                    message=f"Session create cap reached: {count}/{config.max_creates}",
                    error_code="policy_blocked",
                    data={
                        "checks_passed": checks_passed,
                        "checks_failed": [{"check": "session_cap", "reason": f"{count}/{config.max_creates}"}],
                        "autonomy_config": config.to_dict(),
                    },
                )
            notification = f"Auto-audit: agent {action} approved (session creates: {count}/{config.max_creates})"
        elif config.mode == "auto_audit":
            notification = f"Auto-audit: agent {action} approved"

    checks_passed.append("autonomy_policy")

    # --- Confidence gate ---
    modifier = _ORIGIN_MODIFIER.get(request_origin, 0.0)
    threshold = _T_BASE + modifier
    if classify_confidence < threshold:
        return EngineResponse(
            state="preflight_failed",
            error_code="preflight_failed",
            message=f"Low confidence classification: {classify_confidence:.2f} "
            f"(threshold: {threshold:.2f}). Rephrase or specify the operation.",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "confidence", "reason": f"below threshold {threshold}"}],
            },
        )
    checks_passed.append("confidence")

    # --- Intent match ---
    if classify_intent != action:
        return EngineResponse(
            state="escalate",
            message=f"Intent_mismatch: classify returned {classify_intent!r} but action is {action!r}",
            error_code="intent_mismatch",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "intent_match", "reason": "mismatch"}],
            },
        )
    checks_passed.append("intent_match")

    # --- Dedup enforcement (create action) ---
    if action == "create" and dedup_override and not duplicate_of:
        # C-008: dedup_override must be bound to a specific duplicate candidate.
        return EngineResponse(
            state="need_fields",
            message="dedup_override requires duplicate_of identifying the specific duplicate candidate",
            error_code="need_fields",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "dedup_binding", "reason": "dedup_override without duplicate_of"}],
                "missing_fields": ["duplicate_of"],
            },
        )
    if action == "create" and duplicate_of and not dedup_override:
        return EngineResponse(
            state="duplicate_candidate",
            message=f"Duplicate of {duplicate_of} detected in plan stage. "
            "Pass dedup_override=True to proceed.",
            error_code="duplicate_candidate",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "dedup", "reason": f"duplicate_of={duplicate_of}"}],
            },
        )
    if action == "create":
        checks_passed.append("dedup")

    # --- Ticket ID required for non-create ---
    if action != "create" and not ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {action}",
            error_code="need_fields",
            data={
                "checks_passed": checks_passed,
                "checks_failed": [{"check": "ticket_id", "reason": "missing for non-create"}],
            },
        )

    # --- Ticket existence check (non-create) ---
    if action != "create" and ticket_id:
        from scripts.ticket_read import find_ticket_by_id

        ticket = find_ticket_by_id(tickets_dir, ticket_id)
        if ticket is None:
            return EngineResponse(
                state="not_found",
                message=f"No ticket found matching {ticket_id}",
                ticket_id=ticket_id,
                error_code="not_found",
                data={
                    "checks_passed": checks_passed,
                    "checks_failed": [{"check": "ticket_exists", "reason": "not found"}],
                },
            )
        checks_passed.append("ticket_exists")

        # --- Dependency check (close action) ---
        if action == "close" and ticket.blocked_by:
            resolution = preflight_fields.get("resolution", "done")
            if resolution == "wontfix":
                checks_passed.append("dependencies_not_required_for_wontfix")
            else:
                all_tickets = _list_tickets_with_closed(tickets_dir)
                ticket_map = {t.id: t for t in all_tickets}
                missing, unresolved = _classify_blockers(ticket.blocked_by, ticket_map)
                if missing or unresolved:
                    if dependency_override:
                        checks_passed.append("dependencies_overridden")
                    else:
                        return EngineResponse(
                            state="dependency_blocked",
                            message=_format_blocker_message(
                                unresolved=unresolved,
                                missing=missing,
                                include_override=True,
                            ),
                            ticket_id=ticket_id,
                            error_code="dependency_blocked",
                            data={
                                "checks_passed": checks_passed,
                                "checks_failed": [{
                                    "check": "dependencies",
                                    "reason": f"unresolved={unresolved}, missing={missing}",
                                }],
                                "blocking_ids": unresolved + missing,
                                "unresolved_blockers": unresolved,
                                "missing_blockers": missing,
                            },
                        )
                else:
                    checks_passed.append("dependencies")

        # --- TOCTOU fingerprint check ---
        if target_fingerprint is not None:
            from scripts.ticket_dedup import target_fingerprint as compute_fp

            current_fp = compute_fp(Path(ticket.path))
            if current_fp != target_fingerprint:
                return EngineResponse(
                    state="preflight_failed",
                    message="Stale fingerprint — ticket was modified since read. "
                    "Re-run to get a fresh plan.",
                    ticket_id=ticket_id,
                    error_code="stale_plan",
                    data={
                        "checks_passed": checks_passed,
                        "checks_failed": [{"check": "target_fingerprint", "reason": "stale"}],
                    },
                )
            checks_passed.append("target_fingerprint")

    response_data: dict[str, Any] = {
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "autonomy_config": config.to_dict(),
    }
    if notification:
        response_data["notification"] = notification
    return EngineResponse(
        state="ok",
        message="All preflight checks passed",
        data=response_data,
    )


# --- execute ---

# Supported YAML frontmatter fields for update.
_UPDATE_FRONTMATTER_KEYS = frozenset({
    "id",
    "date",
    "status",
    "priority",
    "effort",
    "source",
    "tags",
    "blocked_by",
    "blocks",
    "defer",
})
_UPDATE_SECTION_FIELDS = frozenset({
    "problem",
    "context",
    "prior_investigation",
    "approach",
    "decisions_made",
    "acceptance_criteria",
    "verification",
    "key_files",
    "related",
})
_UPDATE_IGNORED_FIELDS = frozenset({"ticket_id", "id"})

# Valid status transitions for update action (from -> set of valid to statuses).
# done/wontfix are terminal — only reopen (separate action) can transition out.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "blocked", "wontfix"},
    "in_progress": {"open", "blocked", "done", "wontfix"},
    "blocked": {"open", "in_progress", "wontfix"},
    "done": set(),       # Terminal — reopen action required.
    "wontfix": set(),    # Terminal — reopen action required.
}

# Bounds archive collision search to avoid infinite loops in pathological trees.
_MAX_ARCHIVE_COLLISION_SUFFIX = 1000
_CREATE_WRITE_RETRY_LIMIT = 3

# Transitions that require preconditions.
# Pair-keyed: specific (current, target) combinations.
_TRANSITION_PRECONDITIONS: dict[tuple[str, str], str] = {
    ("open", "blocked"): "blocked_by_required",
    ("in_progress", "blocked"): "blocked_by_required",
    ("blocked", "open"): "blockers_resolved_required",
    ("blocked", "in_progress"): "blockers_resolved_required",
}
# Target-keyed: preconditions that apply regardless of current status.
_TARGET_PRECONDITIONS: dict[str, str] = {
    "done": "acceptance_criteria_required",
}


def _transition_policy_data(
    current: str,
    requested: str,
    *,
    valid_recovery_statuses: list[str],
    requires_reopen: bool,
    precondition_code: str = "none",
    precondition_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build machine-readable transition policy context for workflow recovery."""
    return {
        "current_status": current,
        "requested_status": requested,
        "valid_recovery_statuses": valid_recovery_statuses,
        "requires_reopen": requires_reopen,
        "precondition_code": precondition_code,
        "precondition_detail": precondition_detail,
    }


def _check_transition_preconditions_with_detail(
    current: str,
    target: str,
    ticket: Any,
    tickets_dir: Path,
    fields: dict[str, Any] | None = None,
) -> tuple[str | None, str, dict[str, Any] | None]:
    """Check transition preconditions and return message plus machine context."""
    _fields = fields or {}

    target_precondition = _TARGET_PRECONDITIONS.get(target)
    if target_precondition == "acceptance_criteria_required":
        ac = ticket.sections.get("Acceptance Criteria", "")
        if not ac.strip():
            return (
                "Transition to 'done' requires acceptance criteria section",
                "missing_acceptance_criteria",
                {"missing": ["acceptance_criteria"]},
            )

    key = (current, target)
    precondition = _TRANSITION_PRECONDITIONS.get(key)
    if precondition is None:
        return (None, "none", None)

    if precondition == "blocked_by_required":
        blocked_by = _fields.get("blocked_by", ticket.blocked_by)
        if not blocked_by:
            return (
                "Transition to 'blocked' requires non-empty blocked_by",
                "blocked_by_required",
                {"missing": ["blocked_by"]},
            )
        return (None, "none", None)

    if precondition == "blockers_resolved_required":
        if ticket.blocked_by:
            all_tickets = _list_tickets_with_closed(tickets_dir)
            ticket_map = {t.id: t for t in all_tickets}
            missing, unresolved = _classify_blockers(ticket.blocked_by, ticket_map)
            if missing or unresolved:
                return (
                    _format_blocker_message(
                        unresolved=unresolved,
                        missing=missing,
                        include_override=False,
                    ),
                    "dependency_blocked",
                    {
                        "blocking_ids": unresolved + missing,
                        "unresolved_blockers": unresolved,
                        "missing_blockers": missing,
                    },
                )
        return (None, "none", None)

    return (None, "none", None)


def _classify_update_fields(
    fields: dict[str, Any],
    ticket_id: str,
) -> tuple[dict[str, Any], list[str], list[str], bool]:
    """Split update payload keys into supported vs invalid categories."""
    frontmatter_updates: dict[str, Any] = {}
    section_fields: list[str] = []
    unknown_fields: list[str] = []
    ticket_id_mismatch = False

    for key, value in fields.items():
        if key in _UPDATE_IGNORED_FIELDS:
            if key == "ticket_id" and value != ticket_id:
                ticket_id_mismatch = True
            continue
        if key in _UPDATE_FRONTMATTER_KEYS:
            frontmatter_updates[key] = value
        elif key in _UPDATE_SECTION_FIELDS:
            section_fields.append(key)
        else:
            unknown_fields.append(key)

    return (
        frontmatter_updates,
        sorted(section_fields),
        sorted(unknown_fields),
        ticket_id_mismatch,
    )


def _is_valid_transition(current: str, target: str, action: str) -> bool:
    """Check if a status transition is valid per the contract."""
    if action == "close":
        if current in _TERMINAL_STATUSES:
            return False
        return target in ("done", "wontfix")
    if action == "reopen":
        return current in ("done", "wontfix") and target == "open"
    # Update: follow transition table.
    valid = _VALID_TRANSITIONS.get(current, set())
    return target in valid


def _classify_blockers(
    blocked_by: list[str],
    ticket_map: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Split blocker references into missing vs unresolved IDs."""
    missing: list[str] = []
    unresolved: list[str] = []
    for bid in blocked_by:
        blocker = ticket_map.get(bid)
        if blocker is None:
            missing.append(bid)
        elif blocker.status not in _TERMINAL_STATUSES:
            unresolved.append(bid)
    return missing, unresolved


def _format_blocker_message(
    *,
    unresolved: list[str],
    missing: list[str],
    include_override: bool,
) -> str:
    """Build a blocker message that distinguishes missing references."""
    parts: list[str] = []
    if unresolved:
        parts.append(f"Ticket has open blockers: {unresolved}.")
    if missing:
        parts.append(f"Ticket has missing blocker references: {missing}.")
    if include_override:
        parts.append("Resolve blockers, remove stale references, or pass dependency_override: true.")
    else:
        parts.append("Resolve open blockers and remove stale/missing blocker references before changing status.")
    return " ".join(parts)


def _autonomy_policy_fingerprint(config: AutonomyConfig) -> tuple[str, int]:
    """Return the policy-relevant autonomy fields."""
    return (config.mode, config.max_creates)


def _check_transition_preconditions(
    current: str, target: str, ticket: Any, tickets_dir: Path,
    fields: dict[str, Any] | None = None,
) -> str | None:
    """Check transition preconditions. Returns error message or None if OK."""
    message, _code, _detail = _check_transition_preconditions_with_detail(
        current,
        target,
        ticket,
        tickets_dir,
        fields=fields,
    )
    return message


def _sanitize_session_id(session_id: str) -> str:
    """Sanitize session_id for safe use as a filename component.

    Strips path separators and null bytes to prevent path traversal.
    Logs a warning to stderr if sanitization changes the value.
    """
    sanitized = session_id.replace("/", "_").replace("\\", "_").replace("\0", "_")
    if sanitized != session_id:
        print(f"WARNING: session_id sanitized: {session_id!r} -> {sanitized!r}", file=sys.stderr)
    return sanitized


def _audit_append(session_id: str, tickets_dir: Path, entry: dict[str, Any]) -> bool:
    """Append a JSONL audit entry for the given session.

    Location: <tickets_dir>/.audit/YYYY-MM-DD/<session_id>.jsonl
    Returns True on success, False on failure. Logs failures to stderr.
    """
    try:
        safe_id = _sanitize_session_id(session_id)
        date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_dir = tickets_dir / ".audit" / date_dir
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{safe_id}.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return True
    except Exception as exc:
        print(f"AUDIT WRITE FAILED: {exc}", file=sys.stderr)
        return False


def engine_count_session_creates(
    session_id: str,
    tickets_dir: Path,
    request_origin: str = "agent",
) -> int | object:
    """Count successful or gap create actions in a session's audit files.

    Uses attempt_started entries (written before mutation, fail-closed) minus
    known-failed results to compute the count. This ensures:
    - Successful creates are counted.
    - Gap creates (result audit write failed) are conservatively counted.
    - Failed creates (execution error) are NOT counted.

    Falls back to counting ok_create result entries for backward compatibility
    with audit files written before attempt_started carried the intent field.

    Args:
        request_origin: Only count creates from this origin. Defaults to
            "agent" so user creates don't consume the agent budget.

    Returns:
        int: count of creates (0 if no audit files exist)
        AUDIT_UNAVAILABLE: on permission error reading an audit file
    """
    safe_id = _sanitize_session_id(session_id)
    audit_base = tickets_dir / ".audit"
    if not audit_base.is_dir():
        return 0

    # Session-scoped pairing state: pending_create tracks whether the most
    # recent attempt_started (create) has been matched to a result. Carried
    # across date-directory boundaries so a create spanning midnight pairs
    # correctly (attempt_started on day N, result on day N+1).
    attempts = 0
    non_ok = 0
    legacy_ok = 0
    pending_create = False

    for date_dir in sorted(audit_base.iterdir()):
        if not date_dir.is_dir():
            continue
        audit_file = date_dir / f"{safe_id}.jsonl"
        if not audit_file.exists():
            continue
        try:
            text = audit_file.read_text(encoding="utf-8")
        except OSError:
            return AUDIT_UNAVAILABLE

        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                print(f"WARNING: corrupt audit line in {audit_file}: {line[:100]!r}", file=sys.stderr)
                continue
            if entry.get("request_origin") != request_origin:
                continue
            # New format: attempt_started with intent field.
            if (
                entry.get("action") == "attempt_started"
                and entry.get("intent") == "create"
            ):
                pending_create = True
                attempts += 1
            # Create result entry — pair with preceding attempt_started if any.
            elif entry.get("action") == "create" and isinstance(entry.get("result"), str):
                if pending_create:
                    pending_create = False
                    if not entry["result"].startswith("ok_"):
                        non_ok += 1
                elif entry["result"].startswith("ok_"):
                    # Unpaired ok_create: legacy format (no preceding attempt_started).
                    legacy_ok += 1

    # New-format creates: attempts minus known failures (gap-safe).
    return max(0, attempts - non_ok) + legacy_ok


def engine_execute(
    *,
    action: str,
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    dedup_override: bool,
    dependency_override: bool,
    tickets_dir: Path,
    target_fingerprint: str | None = None,
    autonomy_config: AutonomyConfig | None = None,
    hook_injected: bool = False,
    hook_request_origin: str | None = None,
    classify_intent: str | None = None,
    classify_confidence: float | None = None,
    dedup_fingerprint: str | None = None,
    duplicate_of: str | None = None,
) -> EngineResponse:
    """Execute the mutation: create, update, close, or reopen.

    Assumes preflight has already passed. Writes ticket files.
    Wraps dispatch with JSONL audit trail.
    """
    if request_origin not in VALID_ORIGINS:
        return EngineResponse(
            state="escalate",
            message=f"Cannot determine caller identity: request_origin={request_origin!r}",
            error_code="origin_mismatch",
        )

    snapshot_config = autonomy_config
    if request_origin == "agent":
        config = read_autonomy_config(tickets_dir)
        if (
            snapshot_config is not None
            and _autonomy_policy_fingerprint(snapshot_config)
            != _autonomy_policy_fingerprint(config)
        ):
            policy_changed_data: dict[str, Any] = {"live_mode": config.mode}
            if config.warnings:
                policy_changed_data["live_warnings"] = list(config.warnings)
            return EngineResponse(
                state="policy_blocked",
                message="Autonomy policy changed since preflight. Rerun from preflight.",
                error_code="policy_blocked",
                data=policy_changed_data,
            )
    else:
        config = snapshot_config or AutonomyConfig()

    # --- Transport-layer trust triple (defense-in-depth for all origins) ---
    if hook_request_origin is not None and hook_request_origin != request_origin:
        return EngineResponse(
            state="escalate",
            message=f"origin_mismatch: request_origin={request_origin!r}, hook_request_origin={hook_request_origin!r}",
            error_code="origin_mismatch",
        )
    trust_errors = collect_trust_triple_errors(
        hook_injected,
        hook_request_origin,
        session_id,
    )
    if trust_errors:
        return EngineResponse(
            state="policy_blocked",
            message=f"Execute requires verified hook provenance: {', '.join(trust_errors)}",
            error_code="policy_blocked",
        )

    # --- Structural stage prerequisites ---
    # classify_intent: must match action.
    if classify_intent is None:
        return EngineResponse(
            state="policy_blocked",
            message="Execute requires classify_intent (run classify stage first)",
            error_code="policy_blocked",
        )
    if classify_intent != action:
        return EngineResponse(
            state="escalate",
            message=f"intent_mismatch: classify_intent={classify_intent!r} but action={action!r}",
            error_code="intent_mismatch",
        )

    # classify_confidence: must be present and above threshold.
    if classify_confidence is None:
        return EngineResponse(
            state="policy_blocked",
            message="Execute requires classify_confidence (run classify stage first)",
            error_code="policy_blocked",
        )
    modifier = _ORIGIN_MODIFIER.get(request_origin, 0.0)
    threshold = _T_BASE + modifier
    if classify_confidence < threshold:
        return EngineResponse(
            state="preflight_failed",
            message=f"Low confidence: {classify_confidence:.2f} (threshold: {threshold:.2f})",
            error_code="preflight_failed",
        )

    # dedup_fingerprint: required for create, must match recomputed value.
    if action == "create":
        if dedup_fingerprint is None:
            return EngineResponse(
                state="policy_blocked",
                message="Create execute requires dedup_fingerprint (run plan stage first)",
                error_code="policy_blocked",
            )
        validation_errors = validate_fields(fields)
        if validation_errors:
            return EngineResponse(
                state="need_fields",
                message=f"Field validation failed: {'; '.join(validation_errors)}",
                error_code="need_fields",
                data={"validation_errors": validation_errors},
            )
        from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp

        expected_fp = compute_dedup_fp(
            fields.get("problem", ""),
            fields.get("key_file_paths", []),
        )
        if dedup_fingerprint != expected_fp:
            return EngineResponse(
                state="preflight_failed",
                message="dedup_fingerprint mismatch — create fields changed since plan",
                error_code="stale_plan",
            )

    # target_fingerprint: required for non-create actions.
    if action != "create" and target_fingerprint is None:
        return EngineResponse(
            state="policy_blocked",
            message=f"{action} execute requires target_fingerprint (run plan stage first)",
            error_code="policy_blocked",
        )

    # autonomy_config: required for agent-origin (snapshot from preflight).
    if request_origin == "agent" and autonomy_config is None:
        return EngineResponse(
            state="policy_blocked",
            message="Agent execute requires autonomy_config snapshot (rerun from preflight)",
            error_code="policy_blocked",
        )

    # --- Autonomy defense-in-depth (self-contained allowlist) ---
    if request_origin == "agent":
        if action == "reopen":
            return EngineResponse(
                state="policy_blocked",
                message="Defense-in-depth: reopen is user-only in v1.0",
                error_code="policy_blocked",
            )
        if dedup_override:
            return EngineResponse(
                state="policy_blocked",
                message="Defense-in-depth: agents cannot use dedup_override",
                error_code="policy_blocked",
            )
        if dependency_override:
            return EngineResponse(
                state="policy_blocked",
                message="Defense-in-depth: agents cannot use dependency_override",
                error_code="policy_blocked",
            )
        if config.mode != "auto_audit":
            dind_data: dict[str, Any] = {"live_mode": config.mode}
            if config.warnings:
                dind_data["live_warnings"] = list(config.warnings)
            return EngineResponse(
                state="policy_blocked",
                message=f"Defense-in-depth: autonomy mode {config.mode!r} blocks agent mutations",
                error_code="policy_blocked",
                data=dind_data,
            )
        if action == "create":
            count = engine_count_session_creates(session_id, tickets_dir)
            if count is AUDIT_UNAVAILABLE or (isinstance(count, int) and count >= config.max_creates):
                return EngineResponse(
                    state="policy_blocked",
                    message=f"Defense-in-depth: session create cap ({config.max_creates})",
                    error_code="policy_blocked",
                )

    # C-008: dedup_override must be bound to a specific duplicate candidate.
    if action == "create" and dedup_override and not duplicate_of:
        return EngineResponse(
            state="need_fields",
            message="dedup_override requires duplicate_of identifying the specific duplicate candidate",
            error_code="need_fields",
            data={"missing_fields": ["duplicate_of"]},
        )

    # Defense-in-depth dedup check for direct execute(create) calls.
    if action == "create":
        create_fields = dict(fields)
        create_fields.setdefault("priority", "medium")
        plan_resp = _plan_create(create_fields, session_id, request_origin, tickets_dir)
        if plan_resp.state not in {"ok", "duplicate_candidate"}:
            return plan_resp
        if plan_resp.state == "duplicate_candidate" and not dedup_override:
            duplicate_of = plan_resp.data.get("duplicate_of")
            return EngineResponse(
                state="duplicate_candidate",
                message=f"Duplicate of {duplicate_of} detected in execute stage. Pass dedup_override=True to proceed.",
                error_code="duplicate_candidate",
                ticket_id=duplicate_of if isinstance(duplicate_of, str) else None,
                data={
                    "duplicate_of": duplicate_of,
                    "dedup_fingerprint": plan_resp.data.get("dedup_fingerprint"),
                    "target_fingerprint": plan_resp.data.get("target_fingerprint"),
                },
            )

    # Optional stale-plan defense-in-depth for non-create actions.
    if action != "create" and target_fingerprint is not None:
        if not ticket_id:
            return EngineResponse(
                state="need_fields",
                message=f"ticket_id required for {action}",
                error_code="need_fields",
            )
        from scripts.ticket_dedup import target_fingerprint as compute_fp
        from scripts.ticket_read import find_ticket_by_id

        target_ticket = find_ticket_by_id(tickets_dir, ticket_id)
        if target_ticket is None:
            return EngineResponse(
                state="not_found",
                message=f"No ticket matching {ticket_id}",
                ticket_id=ticket_id,
                error_code="not_found",
            )
        current_fp = compute_fp(Path(target_ticket.path))
        if current_fp != target_fingerprint:
            return EngineResponse(
                state="preflight_failed",
                message="Stale fingerprint — ticket was modified since read. Re-run to get a fresh plan.",
                ticket_id=ticket_id,
                error_code="stale_plan",
            )

    # Audit: attempt_started (fail-closed for agents — audit is a security gate).
    # "intent" records the action being attempted so counting can use attempt_started
    # entries when result writes fail (seals the create cap).
    base_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": "attempt_started",
        "intent": action,
        "ticket_id": ticket_id,
        "session_id": session_id,
        "request_origin": request_origin,
        "autonomy_mode": config.mode,
        "result": None,
        "changes": None,
    }
    if not _audit_append(session_id, tickets_dir, base_entry) and request_origin == "agent":
        return EngineResponse(
            state="policy_blocked",
            message="Audit trail write failed — agent mutation blocked (fail-closed)",
            error_code="policy_blocked",
        )

    # Dispatch
    try:
        if action == "create":
            resp = _execute_create(fields, session_id, request_origin, tickets_dir)
        elif action == "update":
            resp = _execute_update(ticket_id, fields, session_id, request_origin, tickets_dir)
        elif action == "close":
            resp = _execute_close(
                ticket_id,
                fields,
                session_id,
                request_origin,
                tickets_dir,
                dependency_override=dependency_override,
            )
        elif action == "reopen":
            resp = _execute_reopen(ticket_id, fields, session_id, request_origin, tickets_dir)
        else:
            resp = EngineResponse(
                state="escalate",
                message=f"Unknown action: {action!r}",
                error_code="intent_mismatch",
            )
    except Exception as exc:
        # Audit: error entry
        error_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "ticket_id": ticket_id,
            "session_id": session_id,
            "request_origin": request_origin,
            "autonomy_mode": config.mode,
            "result": f"error:{type(exc).__name__}",
            "changes": None,
        }
        _audit_append(session_id, tickets_dir, error_entry)
        raise

    # Audit: attempt_result. The create cap is sealed by attempt_started (which
    # carries intent), so a failed result write doesn't bypass the cap. But we
    # still escalate for agents because a missing result entry means the non-ok
    # subtraction won't work if this create failed — conservatively over-counting.
    result_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "ticket_id": resp.ticket_id if resp.ticket_id else ticket_id,
        "session_id": session_id,
        "request_origin": request_origin,
        "autonomy_mode": config.mode,
        "result": resp.state,
        "changes": resp.data.get("changes") if resp.data else None,
    }
    if not _audit_append(session_id, tickets_dir, result_entry) and request_origin == "agent":
        succeeded = isinstance(resp.state, str) and resp.state.startswith("ok_")
        outcome = "succeeded" if succeeded else f"returned {resp.state}"
        return EngineResponse(
            state="escalate",
            message=f"Audit result write failed — agent {action} {outcome} but result entry "
            "is missing. Cap is sealed via attempt_started; manual audit review recommended.",
            ticket_id=resp.ticket_id if resp.ticket_id else ticket_id,
            error_code="io_error",
            data=resp.data,
        )

    return resp


# --- Execute sub-functions ---


def _write_text_exclusive(ticket_path: Path, content: str) -> None:
    """Write a new ticket file exclusively and fsync before returning."""
    encoded = content.encode("utf-8")
    fd = os.open(ticket_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    write_succeeded = False
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError(
                    f"exclusive write failed: short write. Got: {str(ticket_path)!r:.100}"
                )
            view = view[written:]
        os.fsync(fd)
        write_succeeded = True
    finally:
        os.close(fd)
        if not write_succeeded:
            try:
                os.unlink(ticket_path)
            except OSError:
                pass


def _execute_create(
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
) -> EngineResponse:
    """Create a new ticket file with all required contract fields."""
    missing = []
    if not fields.get("title"):
        missing.append("title")
    if not fields.get("problem"):
        missing.append("problem")
    if missing:
        return EngineResponse(
            state="need_fields",
            message=f"Missing required fields for create: {missing}",
            error_code="need_fields",
        )

    validation_errors = validate_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            data={"validation_errors": validation_errors},
        )

    tickets_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    today = now.date()
    title = fields.get("title", "Untitled")

    source = dict(fields.get("source", {"type": "ad-hoc", "ref": "", "session": session_id}))
    if "session" not in source:
        source["session"] = session_id

    for _attempt in range(_CREATE_WRITE_RETRY_LIMIT):
        ticket_id = allocate_id(tickets_dir, today)
        filename = build_filename(ticket_id, title, tickets_dir)
        ticket_path = tickets_dir / filename
        content = render_ticket(
            id=ticket_id,
            title=title,
            date=today.isoformat(),
            created_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            status="open",
            priority=fields.get("priority", "medium"),
            effort=fields.get("effort", ""),
            source=source,
            tags=fields.get("tags", []),
            problem=fields.get("problem", ""),
            approach=fields.get("approach", ""),
            acceptance_criteria=fields.get("acceptance_criteria"),
            verification=fields.get("verification", ""),
            key_files=fields.get("key_files"),
            key_file_paths=fields.get("key_file_paths"),
            context=fields.get("context", ""),
            prior_investigation=fields.get("prior_investigation", ""),
            decisions_made=fields.get("decisions_made", ""),
            related=fields.get("related", ""),
            contract_version=_CONTRACT_VERSION,
            defer=fields.get("defer"),
        )
        try:
            _write_text_exclusive(ticket_path, content)
        except FileExistsError:
            continue
        except OSError as exc:
            return EngineResponse(
                state="escalate",
                message=f"create failed: {exc}. Got: {str(ticket_path)!r:.100}",
                error_code="io_error",
            )
        return EngineResponse(
            state="ok_create",
            message=f"Created {ticket_id} at {ticket_path}",
            ticket_id=ticket_id,
            data={"ticket_path": str(ticket_path), "changes": None},
        )

    return EngineResponse(
        state="escalate",
        message=(
            "create failed: exclusive write retry budget exhausted after "
            f"{_CREATE_WRITE_RETRY_LIMIT} attempts. Got: {title!r:.100}"
        ),
        error_code="io_error",
    )


def _evaluate_update_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Return the update-policy rejection response, or None when update may write."""
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

    new_status = fields.get("status")
    if new_status and new_status != ticket.status:
        valid_recovery_statuses = [] if ticket.status in _TERMINAL_STATUSES else sorted(
            _VALID_TRANSITIONS.get(ticket.status, set())
        )
        requires_reopen = ticket.status in _TERMINAL_STATUSES
        if not _is_valid_transition(ticket.status, new_status, "update"):
            return EngineResponse(
                state="invalid_transition",
                message=f"Cannot transition from {ticket.status} to {new_status} via update"
                + (" (use reopen action)" if requires_reopen else ""),
                ticket_id=ticket_id,
                error_code="invalid_transition",
                data=_transition_policy_data(
                    ticket.status,
                    new_status,
                    valid_recovery_statuses=valid_recovery_statuses,
                    requires_reopen=requires_reopen,
                ),
            )
        precondition_error, precondition_code, precondition_detail = _check_transition_preconditions_with_detail(
            ticket.status,
            new_status,
            ticket,
            tickets_dir,
            fields=fields,
        )
        if precondition_error:
            return EngineResponse(
                state="invalid_transition",
                message=precondition_error,
                ticket_id=ticket_id,
                error_code=(
                    "dependency_blocked"
                    if precondition_code == "dependency_blocked"
                    else "invalid_transition"
                ),
                data=_transition_policy_data(
                    ticket.status,
                    new_status,
                    valid_recovery_statuses=valid_recovery_statuses,
                    requires_reopen=requires_reopen,
                    precondition_code=precondition_code,
                    precondition_detail=precondition_detail,
                ),
            )

    text = Path(ticket.path).read_text(encoding="utf-8")
    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None:
        return EngineResponse(
            state="escalate",
            message="Cannot parse ticket YAML",
            ticket_id=ticket_id,
            error_code="parse_error",
        )

    data = parse_yaml_block(yaml_text)
    if data is None:
        return EngineResponse(
            state="escalate",
            message="Cannot parse ticket YAML",
            ticket_id=ticket_id,
            error_code="parse_error",
        )

    (
        _frontmatter_updates,
        section_fields,
        unknown_fields,
        ticket_id_mismatch,
    ) = _classify_update_fields(fields, ticket_id)
    if ticket_id_mismatch:
        return EngineResponse(
            state="escalate",
            message=f"Update failed: fields.ticket_id must match top-level ticket_id. Got: {fields.get('ticket_id')!r:.100}",
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )
    if section_fields or unknown_fields:
        parts: list[str] = []
        if section_fields:
            parts.append(
                f"section fields not supported by update: {', '.join(section_fields)}"
            )
        if unknown_fields:
            parts.append(f"unknown fields: {', '.join(unknown_fields)}")
        return EngineResponse(
            state="escalate",
            message=f"Update failed: {'; '.join(parts)}",
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )

    return None


def _execute_update(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
) -> EngineResponse:
    """Update an existing ticket's frontmatter fields."""
    if not ticket_id:
        return EngineResponse(state="need_fields", message="ticket_id required for update", error_code="need_fields")

    from scripts.ticket_read import find_ticket_by_id

    ticket = find_ticket_by_id(tickets_dir, ticket_id)
    if ticket is None:
        return EngineResponse(state="not_found", message=f"No ticket matching {ticket_id}", ticket_id=ticket_id, error_code="not_found")

    policy_error = _evaluate_update_policy(ticket_id, ticket, fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    ticket_path = Path(ticket.path)
    text = ticket_path.read_text(encoding="utf-8")

    # Update frontmatter fields.
    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None:
        return EngineResponse(state="escalate", message="Cannot parse ticket YAML", ticket_id=ticket_id, error_code="parse_error")

    data = parse_yaml_block(yaml_text)
    if data is None:
        return EngineResponse(state="escalate", message="Cannot parse ticket YAML", ticket_id=ticket_id, error_code="parse_error")

    (
        frontmatter_updates,
        section_fields,
        unknown_fields,
        ticket_id_mismatch,
    ) = _classify_update_fields(fields, ticket_id)
    if ticket_id_mismatch:
        return EngineResponse(
            state="escalate",
            message=f"Update failed: fields.ticket_id must match top-level ticket_id. Got: {fields.get('ticket_id')!r:.100}",
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )
    if section_fields or unknown_fields:
        parts: list[str] = []
        if section_fields:
            parts.append(
                f"section fields not supported by update: {', '.join(section_fields)}"
            )
        if unknown_fields:
            parts.append(f"unknown fields: {', '.join(unknown_fields)}")
        return EngineResponse(
            state="escalate",
            message=f"Update failed: {'; '.join(parts)}",
            ticket_id=ticket_id,
            error_code="intent_mismatch",
        )

    changes: dict[str, Any] = {"frontmatter": {}, "sections_changed": []}
    for key, value in frontmatter_updates.items():
        if key in data and data[key] != value:
            changes["frontmatter"][key] = [data[key], value]
        data[key] = value

    data["contract_version"] = _CONTRACT_VERSION  # C-004: engine-owned, always latest.

    try:
        new_text = replace_fenced_yaml(text, data)
    except ValueError as exc:
        return EngineResponse(
            state="escalate",
            message=str(exc),
            ticket_id=ticket_id,
            error_code="parse_error",
        )
    ticket_path.write_text(new_text, encoding="utf-8")

    return EngineResponse(
        state="ok_update",
        message=f"Updated {ticket_id}",
        ticket_id=ticket_id,
        data={"ticket_path": str(ticket_path), "changes": changes},
    )


def _evaluate_close_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
    *,
    dependency_override: bool = False,
) -> EngineResponse | None:
    """Return the close-policy rejection response, or None when close may write."""
    resolution = fields.get("resolution", "done")

    legacy_block = _check_legacy_gate(ticket)
    if legacy_block is not None:
        return legacy_block

    close_fields = dict(fields)
    close_fields["resolution"] = resolution
    validation_errors = validate_fields(close_fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"validation_errors": validation_errors},
        )

    valid_recovery_statuses = [] if ticket.status in _TERMINAL_STATUSES else ["done", "wontfix"]
    requires_reopen = ticket.status in _TERMINAL_STATUSES

    if ticket.blocked_by and resolution != "wontfix":
        all_tickets = _list_tickets_with_closed(tickets_dir)
        ticket_map = {item.id: item for item in all_tickets}
        missing, unresolved = _classify_blockers(ticket.blocked_by, ticket_map)
        if (missing or unresolved) and not dependency_override:
            blocker_detail = {
                "blocking_ids": unresolved + missing,
                "unresolved_blockers": unresolved,
                "missing_blockers": missing,
            }
            return EngineResponse(
                state="dependency_blocked",
                message=_format_blocker_message(
                    unresolved=unresolved,
                    missing=missing,
                    include_override=True,
                ),
                ticket_id=ticket_id,
                error_code="dependency_blocked",
                data={
                    **_transition_policy_data(
                        ticket.status,
                        resolution,
                        valid_recovery_statuses=valid_recovery_statuses,
                        requires_reopen=requires_reopen,
                        precondition_code="dependency_blocked",
                        precondition_detail=blocker_detail,
                    ),
                    **blocker_detail,
                },
            )

    if not _is_valid_transition(ticket.status, resolution, "close"):
        return EngineResponse(
            state="invalid_transition",
            message=f"Cannot close with resolution {resolution!r} (must be 'done' or 'wontfix')"
            + (f" from terminal status {ticket.status!r}" if requires_reopen else ""),
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                resolution,
                valid_recovery_statuses=valid_recovery_statuses,
                requires_reopen=requires_reopen,
            ),
        )

    precondition_error, precondition_code, precondition_detail = _check_transition_preconditions_with_detail(
        ticket.status, resolution, ticket, tickets_dir, fields=fields,
    )
    if precondition_error:
        return EngineResponse(
            state="invalid_transition",
            message=precondition_error,
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                resolution,
                valid_recovery_statuses=valid_recovery_statuses,
                requires_reopen=requires_reopen,
                precondition_code=precondition_code,
                precondition_detail=precondition_detail,
            ),
        )

    text = Path(ticket.path).read_text(encoding="utf-8")
    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None or parse_yaml_block(yaml_text) is None:
        return EngineResponse(
            state="escalate",
            message="Cannot parse ticket YAML",
            ticket_id=ticket_id,
            error_code="parse_error",
        )

    return None


def _close_readiness_data(
    ticket: ParsedTicket,
    *,
    resolution: str,
    ready: bool,
    error_code: str | None = None,
    missing: list[str] | None = None,
    unresolved_blockers: list[str] | None = None,
    missing_blockers: list[str] | None = None,
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Build the read-only close-readiness payload."""
    unresolved = unresolved_blockers or []
    missing_refs = missing_blockers or []
    return {
        "ready": ready,
        "resolution": resolution,
        "status": ticket.status,
        "error_code": error_code,
        "missing": missing or [],
        "blocking_ids": unresolved + missing_refs,
        "unresolved_blockers": unresolved,
        "missing_blockers": missing_refs,
        "allowed_actions": allowed_actions or ([f"close as {resolution}"] if ready else ["keep current status"]),
    }


def _close_readiness_from_policy_error(
    ticket: ParsedTicket,
    *,
    resolution: str,
    policy_error: EngineResponse,
) -> dict[str, Any]:
    """Translate the shared close-policy response into read-only UX hints."""
    data = dict(policy_error.data or {})
    precondition_detail = data.get("precondition_detail")
    missing = (
        list(precondition_detail.get("missing", []))
        if isinstance(precondition_detail, dict)
        else []
    )
    if policy_error.error_code == "policy_blocked":
        allowed_actions = ["migrate ticket before close", "keep current status"]
    elif policy_error.error_code == "dependency_blocked":
        allowed_actions = ["resolve blockers", "close as wontfix", "keep current status"]
    elif policy_error.error_code == "need_fields":
        allowed_actions = ["choose done or wontfix", "keep current status"]
    elif ticket.status in _TERMINAL_STATUSES:
        allowed_actions = ["reopen before closing", "keep current status"]
    elif missing:
        allowed_actions = ["add acceptance criteria", "close as wontfix", "keep current status"]
    else:
        allowed_actions = ["choose done or wontfix", "keep current status"]
    readiness = _close_readiness_data(
        ticket,
        resolution=resolution,
        ready=False,
        error_code=policy_error.error_code,
        missing=missing,
        unresolved_blockers=data.get("unresolved_blockers", []),
        missing_blockers=data.get("missing_blockers", []),
        allowed_actions=allowed_actions,
    )
    if "validation_errors" in data:
        readiness["validation_errors"] = data["validation_errors"]
    return readiness


def engine_close_readiness(
    ticket: ParsedTicket,
    tickets_dir: Path,
    *,
    resolution: str = "done",
) -> EngineResponse:
    """Return whether the shared close-policy evaluator would allow this close."""
    fields = {"resolution": resolution}
    policy_error = _evaluate_close_policy(ticket.id, ticket, fields, tickets_dir)
    if policy_error is not None:
        return EngineResponse(
            state=policy_error.state,
            message=policy_error.message,
            ticket_id=ticket.id,
            error_code=policy_error.error_code,
            data=_close_readiness_from_policy_error(
                ticket,
                resolution=resolution,
                policy_error=policy_error,
            ),
        )

    return EngineResponse(
        state="ok",
        message=f"Ticket {ticket.id} is ready to close as {resolution}",
        ticket_id=ticket.id,
        data=_close_readiness_data(ticket, resolution=resolution, ready=True),
    )


def _evaluate_workflow_policy(
    action: str,
    ticket_id: str | None,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Apply read-only execute policy checks for workflow prepare."""
    if action == "create":
        return None
    if not ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {action}",
            error_code="need_fields",
            data={"missing_fields": ["ticket_id"]},
        )

    from scripts.ticket_read import find_ticket_by_id

    ticket = find_ticket_by_id(tickets_dir, ticket_id)
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )
    if action == "update":
        return _evaluate_update_policy(ticket_id, ticket, fields, tickets_dir)
    if action == "close":
        return _evaluate_close_policy(ticket_id, ticket, fields, tickets_dir)
    if action == "reopen":
        return _evaluate_reopen_policy(ticket_id, ticket, fields, tickets_dir)
    return EngineResponse(
        state="escalate",
        message=f"Unknown workflow action: {action!r}",
        error_code="intent_mismatch",
    )


def _evaluate_reopen_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Return the reopen-policy rejection response, or None when reopen may write."""
    reopen_reason = fields.get("reopen_reason", "")
    if not reopen_reason:
        return EngineResponse(
            state="need_fields",
            message="reopen_reason required for reopen",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"missing_fields": ["reopen_reason"]},
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

    if not _is_valid_transition(ticket.status, "open", "reopen"):
        return EngineResponse(
            state="invalid_transition",
            message=f"Cannot reopen ticket with status {ticket.status} (must be done or wontfix)",
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                "open",
                valid_recovery_statuses=[],
                requires_reopen=False,
            ),
        )

    text = Path(ticket.path).read_text(encoding="utf-8")
    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None or parse_yaml_block(yaml_text) is None:
        return EngineResponse(
            state="escalate",
            message="Cannot parse ticket YAML",
            ticket_id=ticket_id,
            error_code="parse_error",
        )

    return None


def _execute_close(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    dependency_override: bool = False,
) -> EngineResponse:
    """Close a ticket (set status to done or wontfix, optionally archive).

    Validates transitions with action='close', which allows done/wontfix
    from any non-terminal status.
    """
    if not ticket_id:
        return EngineResponse(state="need_fields", message="ticket_id required for close", error_code="need_fields")

    resolution = fields.get("resolution", "done")
    archive = fields.get("archive", False)

    from scripts.ticket_read import find_ticket_by_id

    ticket = find_ticket_by_id(tickets_dir, ticket_id)
    if ticket is None:
        return EngineResponse(state="not_found", message=f"No ticket matching {ticket_id}", ticket_id=ticket_id, error_code="not_found")

    policy_error = _evaluate_close_policy(
        ticket_id,
        ticket,
        fields,
        tickets_dir,
        dependency_override=dependency_override,
    )
    if policy_error is not None:
        return policy_error

    ticket_path = Path(ticket.path)
    text = ticket_path.read_text(encoding="utf-8")
    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None:
        return EngineResponse(state="escalate", message="Cannot parse ticket YAML", ticket_id=ticket_id, error_code="parse_error")

    data = parse_yaml_block(yaml_text)
    if data is None:
        return EngineResponse(state="escalate", message="Cannot parse ticket YAML", ticket_id=ticket_id, error_code="parse_error")

    old_status = data.get("status", "")
    data["status"] = resolution
    data["contract_version"] = _CONTRACT_VERSION  # C-004: engine-owned, always latest.
    try:
        new_text = replace_fenced_yaml(text, data)
    except ValueError as exc:
        return EngineResponse(
            state="escalate",
            message=str(exc),
            ticket_id=ticket_id,
            error_code="parse_error",
        )
    ticket_path.write_text(new_text, encoding="utf-8")

    changes = {"frontmatter": {"status": [old_status, resolution]}}

    # Archive if requested.
    if archive:
        closed_dir = tickets_dir / "closed-tickets"
        closed_dir.mkdir(exist_ok=True)
        dst = closed_dir / ticket_path.name
        # Collision-safe: suffix with -2, -3, etc. if a file with the same
        # name already exists (e.g., ticket A closed, ticket B created with
        # same date+slug, then B closed).
        if dst.exists():
            stem = ticket_path.stem
            suffix = ticket_path.suffix
            for n in range(2, _MAX_ARCHIVE_COLLISION_SUFFIX + 2):
                candidate = closed_dir / f"{stem}-{n}{suffix}"
                if not candidate.exists():
                    dst = candidate
                    break
            else:
                return EngineResponse(
                    state="escalate",
                    message=f"archive collision resolution failed: exhausted suffix search. Got: {ticket_path.name!r:.100}",
                    ticket_id=ticket_id,
                    error_code="io_error",
                )
        try:
            ticket_path.rename(dst)
        except OSError as exc:
            return EngineResponse(
                state="escalate",
                message=f"archive rename failed: {exc}. Got: {str(dst)!r:.100}",
                ticket_id=ticket_id,
                error_code="io_error",
            )
        return EngineResponse(
            state="ok_close_archived",
            message=f"Closed and archived {ticket_id} to closed-tickets/",
            ticket_id=ticket_id,
            data={"ticket_path": str(dst), "changes": changes},
        )

    return EngineResponse(
        state="ok_close",
        message=f"Closed {ticket_id} (status: {resolution})",
        ticket_id=ticket_id,
        data={"ticket_path": str(ticket_path), "changes": changes},
    )


def _execute_reopen(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
) -> EngineResponse:
    """Reopen a done/wontfix ticket."""
    if not ticket_id:
        return EngineResponse(state="need_fields", message="ticket_id required for reopen", error_code="need_fields")

    reopen_reason = fields.get("reopen_reason", "")
    if not reopen_reason:
        return EngineResponse(state="need_fields", message="reopen_reason required for reopen", error_code="need_fields")

    from scripts.ticket_read import find_ticket_by_id

    ticket = find_ticket_by_id(tickets_dir, ticket_id)
    if ticket is None:
        return EngineResponse(state="not_found", message=f"No ticket matching {ticket_id}", ticket_id=ticket_id, error_code="not_found")

    policy_error = _evaluate_reopen_policy(ticket_id, ticket, fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    # Write status change.
    ticket_path = Path(ticket.path)
    text = ticket_path.read_text(encoding="utf-8")
    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None:
        return EngineResponse(state="escalate", message="Cannot parse ticket YAML", ticket_id=ticket_id, error_code="parse_error")

    data = parse_yaml_block(yaml_text)
    if data is None:
        return EngineResponse(state="escalate", message="Cannot parse ticket YAML", ticket_id=ticket_id, error_code="parse_error")

    old_status = data.get("status", "")
    data["status"] = "open"
    data["contract_version"] = _CONTRACT_VERSION  # C-004: engine-owned, always latest.
    try:
        new_text = replace_fenced_yaml(text, data)
    except ValueError as exc:
        return EngineResponse(
            state="escalate",
            message=str(exc),
            ticket_id=ticket_id,
            error_code="parse_error",
        )

    # Append to Reopen History section (newest-last).
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reopen_entry = f"\n\n## Reopen History\n- **{now}**: {reopen_reason} (by {request_origin})"

    if "## Reopen History" in new_text:
        rh_match = re.search(r"## Reopen History\n", new_text)
        if rh_match:
            next_heading = re.search(r"\n## ", new_text[rh_match.end():])
            if next_heading:
                insert_pos = rh_match.end() + next_heading.start()
            else:
                insert_pos = len(new_text)
            entry = f"- **{now}**: {reopen_reason} (by {request_origin})\n"
            new_text = new_text[:insert_pos].rstrip() + "\n" + entry + new_text[insert_pos:]
    else:
        new_text += reopen_entry

    # Un-archive first: move before writing status change to prevent
    # "open but invisible" state if the rename fails.
    archived_from: Path | None = None
    closed_dir = tickets_dir / "closed-tickets"
    if ticket_path.parent == closed_dir:
        dst = tickets_dir / ticket_path.name
        if dst.exists():
            stem = ticket_path.stem
            suffix = ticket_path.suffix
            for n in range(2, _MAX_ARCHIVE_COLLISION_SUFFIX + 2):
                candidate = tickets_dir / f"{stem}-{n}{suffix}"
                if not candidate.exists():
                    dst = candidate
                    break
            else:
                return EngineResponse(
                    state="escalate",
                    message=f"un-archive collision resolution failed: exhausted suffix search. Got: {ticket_path.name!r:.100}",
                    ticket_id=ticket_id,
                    error_code="io_error",
                )
        try:
            ticket_path.rename(dst)
        except OSError as exc:
            return EngineResponse(
                state="escalate",
                message=f"un-archive rename failed: {exc}. Got: {str(dst)!r:.100}",
                ticket_id=ticket_id,
                error_code="io_error",
            )
        archived_from = ticket_path
        ticket_path = dst

    try:
        ticket_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        # Roll back the rename so ticket stays in closed-tickets/ with old status.
        rollback_failed = False
        if archived_from is not None:
            try:
                ticket_path.rename(archived_from)
            except OSError:
                rollback_failed = True
        msg = f"reopen write failed: {exc}. Got: {str(ticket_path)!r:.100}"
        if rollback_failed:
            msg += f" ROLLBACK ALSO FAILED: ticket is at {str(ticket_path)!r:.100} with old status, needs manual fix"
        return EngineResponse(
            state="escalate",
            message=msg,
            ticket_id=ticket_id,
            error_code="io_error",
        )

    return EngineResponse(
        state="ok_reopen",
        message=f"Reopened {ticket_id}. Reason: {reopen_reason}",
        ticket_id=ticket_id,
        data={"ticket_path": str(ticket_path), "changes": {"status": [old_status, "open"]}},
    )
