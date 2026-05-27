"""Deterministic Ticket autonomy candidate discovery."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.ticket_autonomy_runtime import CandidateMutation, EvidenceLink
from scripts.ticket_read import list_tickets

_TICKET_ID_RE = re.compile(r"\bT-\d{8}-\d{2,}\b")


def _value_error(operation: str, reason: str, value: object) -> ValueError:
    return ValueError(f"{operation} failed: {reason}. Got: {value!r:.100}")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def _ticket_metadata_paths(ticket: Any) -> set[str]:
    paths: set[str] = set()
    key_file_paths = ticket.frontmatter.get("key_file_paths")
    for path in _string_list(key_file_paths):
        paths.add(_normalize_path(path))
    for path in ticket.related_paths:
        if isinstance(path, str):
            paths.add(_normalize_path(path))
    return paths


def _explicit_ticket_ids(*texts: object) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for text in texts:
        if not isinstance(text, str):
            continue
        for match in _TICKET_ID_RE.finditer(text):
            ticket_id = match.group(0)
            if ticket_id in seen:
                continue
            seen.add(ticket_id)
            ids.append(ticket_id)
    return ids


def _append_candidate(
    candidates: list[CandidateMutation],
    seen: set[tuple[str | None, str, str, str]],
    candidate: CandidateMutation,
) -> None:
    evidence = candidate.evidence[0] if candidate.evidence else EvidenceLink("none", "none")
    key = (candidate.ticket_id, candidate.action, evidence.kind, evidence.ref)
    if key in seen:
        return
    seen.add(key)
    candidates.append(candidate)


def _candidate_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    ticket_id = item.get("ticket_id")
    action = item.get("action", "update")
    proposed_change = item.get("proposed_change", {})
    reason = item.get("reason")
    conflict_reason = item.get("conflict_reason")
    if ticket_id is not None and not isinstance(ticket_id, str):
        return None
    if not isinstance(action, str) or not action:
        return None
    if not isinstance(proposed_change, Mapping):
        return None
    evidence_ref = reason if isinstance(reason, str) and reason else "candidate_mutations"
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change=dict(proposed_change),
        evidence=(EvidenceLink(kind="codex_candidate", ref=evidence_ref),),
        conflict_reason=conflict_reason if isinstance(conflict_reason, str) else None,
    )


def _possible_candidate_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    ticket_id = item.get("ticket_id")
    action = item.get("action", "update")
    reason = item.get("reason")
    if ticket_id is not None and not isinstance(ticket_id, str):
        return None
    if not isinstance(action, str) or not action:
        return None
    if not isinstance(reason, str) or not reason:
        reason = "Codex supplied a possible candidate that needs discussion."
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        proposed_change={"requires_discussion": True, "reason": reason},
        evidence=(EvidenceLink(kind="codex_possible_candidate", ref=reason),),
    )


def _append_structured_candidates(
    candidates: list[CandidateMutation],
    seen: set[tuple[str | None, str, str, str]],
    turn_context: Mapping[str, object],
) -> None:
    for item in turn_context.get("candidate_mutations", []):
        if isinstance(item, Mapping):
            candidate = _candidate_from_mapping(item)
            if candidate is not None:
                _append_candidate(candidates, seen, candidate)
    for item in turn_context.get("possible_candidates", []):
        if isinstance(item, Mapping):
            candidate = _possible_candidate_from_mapping(item)
            if candidate is not None:
                _append_candidate(candidates, seen, candidate)


def _append_text_id_candidates(
    candidates: list[CandidateMutation],
    seen: set[tuple[str | None, str, str, str]],
    turn_context: Mapping[str, object],
) -> None:
    for ticket_id in _explicit_ticket_ids(
        turn_context.get("user_request"),
        turn_context.get("assistant_work_summary"),
    ):
        _append_candidate(
            candidates,
            seen,
            CandidateMutation(
                ticket_id=ticket_id,
                action="update",
                proposed_change={},
                evidence=(EvidenceLink(kind="explicit_ticket_id", ref=ticket_id),),
            ),
        )


def _path_refs(turn_context: Mapping[str, object]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for key, evidence_kind in (
        ("touched_files", "related_path"),
        ("diff_files", "diff_path"),
        ("test_files", "test_path"),
    ):
        for path in _string_list(turn_context.get(key)):
            refs.append((_normalize_path(path), evidence_kind))
    return refs


def _append_path_candidates(
    candidates: list[CandidateMutation],
    seen: set[tuple[str | None, str, str, str]],
    turn_context: Mapping[str, object],
    tickets_dir: Path,
) -> None:
    tickets = sorted(list_tickets(tickets_dir, include_closed=True), key=lambda ticket: ticket.id)
    ticket_paths = {ticket.id: _ticket_metadata_paths(ticket) for ticket in tickets}
    tickets_by_id = {ticket.id: ticket for ticket in tickets}
    for path, evidence_kind in _path_refs(turn_context):
        for ticket_id in sorted(tickets_by_id):
            if path not in ticket_paths[ticket_id]:
                continue
            _append_candidate(
                candidates,
                seen,
                CandidateMutation(
                    ticket_id=ticket_id,
                    action="update",
                    proposed_change={},
                    evidence=(EvidenceLink(kind=evidence_kind, ref=path),),
                ),
            )


def discover_candidate_mutations(
    turn_context: Mapping[str, object],
    tickets_dir: Path,
) -> tuple[CandidateMutation, ...]:
    """Extract deterministic Ticket mutation candidates from turn context.

    Args:
        turn_context: Strict turn context supplied by Codex/host runtime.
        tickets_dir: Active Ticket directory used for metadata path matching.

    Returns:
        Candidate mutations in deterministic discovery order.

    Raises:
        ValueError: If `turn_context` is not object-shaped.
    """
    if not isinstance(turn_context, Mapping):
        raise _value_error(
            "discover candidate mutations",
            "turn_context must be an object",
            turn_context,
        )

    candidates: list[CandidateMutation] = []
    seen: set[tuple[str | None, str, str, str]] = set()
    _append_structured_candidates(candidates, seen, turn_context)
    _append_text_id_candidates(candidates, seen, turn_context)
    _append_path_candidates(candidates, seen, turn_context, tickets_dir)
    return tuple(candidates)
