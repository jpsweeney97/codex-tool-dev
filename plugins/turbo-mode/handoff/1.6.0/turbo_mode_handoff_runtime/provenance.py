"""Provenance parsing and session matching for defer-meta and distill-meta.

Dual-read: YAML field (primary) > HTML comment (fallback).
"""
from __future__ import annotations

import json
import re
import warnings
from typing import Any

_DEFER_META_RE = re.compile(r"<!--\s*defer-meta\s+(\{.*?\})\s*-->")
_DISTILL_META_RE = re.compile(r"<!--\s*distill-meta\s+(\{.*?\})\s*-->")


def parse_defer_meta(text: str) -> dict[str, Any] | None:
    """Extract defer-meta JSON from an HTML comment in text."""
    m = _DEFER_META_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        warnings.warn(f"Malformed JSON in defer-meta comment: {exc}", stacklevel=2)
        return None


def parse_distill_meta(text: str) -> dict[str, Any] | None:
    """Extract distill-meta JSON from an HTML comment in text."""
    m = _DISTILL_META_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        warnings.warn(f"Malformed JSON in distill-meta comment: {exc}", stacklevel=2)
        return None


def render_defer_meta(
    source_session: str,
    source_type: str,
    source_ref: str,
) -> str:
    """Render a defer-meta HTML comment string."""
    payload = {
        "v": 1,
        "source_session": source_session,
        "source_type": source_type,
        "source_ref": source_ref,
        "created_by": "defer-skill",
    }
    return f"<!-- defer-meta {json.dumps(payload, separators=(',', ':'), sort_keys=True)} -->"


def read_provenance(
    provenance_yaml: dict[str, Any] | None,
    body_text: str,
) -> dict[str, Any] | None:
    """Read provenance from ticket. YAML field primary, comment fallback.

    Returns dict with source_session, source_type, plus 'source' key
    indicating where data came from ('yaml' or 'comment').
    Returns None if no provenance found.
    """
    # P1-7 fix: truthiness check — guard both None and empty string
    if provenance_yaml and provenance_yaml.get("source_session"):
        return {**provenance_yaml, "source": "yaml"}

    comment_data = parse_defer_meta(body_text)
    if comment_data and "source_session" in comment_data:
        return {**comment_data, "source": "comment"}

    return None


def session_matches(
    ticket_session: str | None,
    handoff_session: str | None,
) -> bool:
    """Check if a ticket's source_session matches a handoff's session_id.

    Full UUID comparison — no truncation.
    P1-7 fix: guard both None AND empty string to prevent false-positive
    uid_match when neither side has a session_id.
    """
    if not ticket_session or not handoff_session:
        return False
    return ticket_session == handoff_session
