"""Ticket reading, status normalization, and orphan detection for /triage skill.

Phase 0: read-only. Produces JSON report.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Literal, TypedDict


from turbo_mode_handoff_runtime.handoff_parsing import parse_frontmatter, parse_sections, section_name
from turbo_mode_handoff_runtime.project_paths import get_handoffs_dir, get_legacy_handoffs_dir, get_project_root
from turbo_mode_handoff_runtime.provenance import read_provenance, session_matches
from turbo_mode_handoff_runtime.storage_authority import (
    HandoffCandidate,
    StorageLocation,
    discover_handoff_inventory,
    eligible_history_candidates,
)
from turbo_mode_handoff_runtime.ticket_parsing import parse_ticket


class OpenTicket(TypedDict):
    id: str
    date: str
    priority: str
    status_raw: str
    status_normalized: str
    normalization_confidence: str
    summary: str
    path: str


class MatchResult(TypedDict):
    match_type: Literal["uid_match", "id_ref", "manual_review"]
    matched_ticket: str | None
    item: dict[str, Any]


class TriageReport(TypedDict):
    open_tickets: list[OpenTicket]
    orphaned_items: list[MatchResult]
    matched_items: list[MatchResult]
    match_counts: dict[str, int]
    skipped_prose_count: int
    legacy_warning: str | None


# 6-state enum
_CANONICAL_STATUSES = {"deferred", "open", "in_progress", "blocked", "done", "wontfix"}
_TERMINAL_STATUSES = {"done", "wontfix"}

_NORMALIZATION_MAP: dict[str, tuple[str, str]] = {
    "complete": ("done", "high"),
    "implemented": ("done", "high"),
    "closed": ("done", "medium"),
    "planning": ("open", "medium"),
    "implementing": ("in_progress", "high"),
}


def normalize_status(raw: str) -> tuple[str, str]:
    """Normalize a ticket status to the 6-state enum.

    Returns (normalized_status, confidence) where confidence is high/medium/low.
    """
    if raw in _CANONICAL_STATUSES:
        return raw, "high"
    if raw in _NORMALIZATION_MAP:
        return _NORMALIZATION_MAP[raw]
    warnings.warn(
        f"Unknown status {raw!r}, defaulting to 'open' (low confidence)",
        stacklevel=2,
    )
    return "open", "low"


def read_open_tickets(tickets_dir: Path) -> list[OpenTicket]:
    """Read all non-terminal tickets from a directory.

    Returns list of dicts with: id, date, priority, status_raw,
    status_normalized, normalization_confidence, summary, path.
    """
    if not tickets_dir.exists():
        return []

    results: list[OpenTicket] = []
    for path in sorted(tickets_dir.rglob("*.md")):
        ticket = parse_ticket(path)
        if ticket is None:
            continue

        fm = ticket.frontmatter
        raw_status = str(fm.get("status", "open"))
        norm_status, confidence = normalize_status(raw_status)

        if norm_status in _TERMINAL_STATUSES:
            continue

        results.append({
            "id": fm["id"],
            "date": fm.get("date", ""),
            "priority": fm.get("priority", "medium"),
            "status_raw": raw_status,
            "status_normalized": norm_status,
            "normalization_confidence": confidence,
            "summary": str(path.stem),
            "path": str(path),
        })

    return results


# Ticket ID patterns — union of new + legacy formats
_TICKET_ID_PATTERNS = [
    r"T-\d{8}-\d{2,}",     # new: T-20260228-01, T-20260228-100
    r"T-\d{3}",             # legacy numeric: T-004
    r"T-[A-F]",             # legacy alpha: T-A (P3-5: covers current A-F corpus only)
    r"handoff-[\w-]+",      # P1-11 fix: legacy noun — supports hyphens (handoff-quality-hook)
]
_TICKET_ID_RE = re.compile(r"\b(?:" + "|".join(_TICKET_ID_PATTERNS) + r")\b")

_LIST_ITEM_RE = re.compile(r"^[-*]\s+(.+)$|^(\d+)\.\s+(.+)$", re.MULTILINE)



def extract_handoff_items(
    handoff_text: str, handoff_filename: str
) -> tuple[list[dict[str, Any]], int]:
    """Extract structured list items from Open Questions and Risks sections.

    Returns (items, skipped_prose_count).
    Only extracts lines starting with - or numbered items.
    Skips prose paragraphs (counted via skipped_prose_count).
    Skips handoffs without these sections.

    Note: uid_match based on session_id is a session-level correlation signal,
    not an item-level match. All items from the same handoff share the same
    session_id, so a uid_match means "this handoff produced a ticket", not
    "this specific item was deferred." (P1-2)
    """
    # P0-1 fix: parse_frontmatter returns tuple[dict, str], not dict
    fm, body = parse_frontmatter(handoff_text)
    session_id = fm.get("session_id", "")

    # P0-1 fix: use body (frontmatter stripped) for parse_sections
    sections = parse_sections(body)
    target_sections = {"Open Questions", "Risks"}

    items: list[dict[str, Any]] = []
    skipped_prose_count = 0
    for section in sections:
        # P0-2 fix: strip '## ' prefix before comparison
        name = section_name(section.heading)
        if name not in target_sections:
            continue
        for line in section.content.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            m = _LIST_ITEM_RE.match(line)
            if m:
                text = m.group(1) or m.group(3) or ""
                text = text.strip()
                if text:
                    items.append({
                        "text": text,
                        "section": name,
                        "session_id": session_id,
                        "handoff": handoff_filename,
                    })
            else:
                # P1-4: count skipped prose lines
                skipped_prose_count += 1
    return items, skipped_prose_count


def _load_tickets_for_matching(tickets_dir: Path) -> list[dict[str, Any]]:
    """Load all tickets with their provenance for matching."""
    results: list[dict[str, Any]] = []
    if not tickets_dir.exists():
        return results

    for path in sorted(tickets_dir.rglob("*.md")):  # P2-10 fix: deterministic iteration order
        ticket = parse_ticket(path)
        if ticket is None:
            continue

        fm = ticket.frontmatter
        prov = read_provenance(
            provenance_yaml=fm.get("provenance"),
            body_text=ticket.body,
        )
        results.append({
            "id": fm["id"],
            "provenance": prov,
            "path": str(path),
        })
    return results


def match_orphan_item(
    item: dict[str, Any],
    tickets: list[dict[str, Any]],
) -> MatchResult:
    """Match a handoff item against existing tickets.

    Returns dict with match_type (uid_match, id_ref, manual_review)
    and matched_ticket (if matched).
    """
    # Strategy 1: UID match — session_id → provenance.source_session
    for ticket in tickets:
        prov = ticket.get("provenance")
        if prov and session_matches(prov.get("source_session"), item.get("session_id")):
            return {
                "match_type": "uid_match",
                "matched_ticket": ticket["id"],
                "item": item,
            }

    # Strategy 2: Ticket ID reference in item text
    found_ids = set(_TICKET_ID_RE.findall(item.get("text", "")))
    ticket_ids = {t["id"] for t in tickets}
    matched = found_ids & ticket_ids
    if matched:
        return {
            "match_type": "id_ref",
            "matched_ticket": sorted(matched)[0],  # P2-7 fix: deterministic alphabetic order
            "item": item,
        }

    # Strategy 3: Manual review
    return {
        "match_type": "manual_review",
        "matched_ticket": None,
        "item": item,
    }


_LOOKBACK_DAYS = 30  # P1-3: design requires 30-day scan window


def _scan_handoff_dirs(
    handoffs_dir: Path, *, archive_name: str = "archive",
) -> list[Path]:
    """Collect handoff files from active and archive directories.

    P1-3 fix: filters to files modified within the last _LOOKBACK_DAYS days.
    """
    cutoff = time.time() - (_LOOKBACK_DAYS * 86400)
    paths: list[Path] = []

    for search_dir in [handoffs_dir, handoffs_dir / archive_name]:
        if not search_dir.exists():
            continue
        for p in sorted(search_dir.glob("*.md")):
            try:
                if p.stat().st_mtime >= cutoff:
                    paths.append(p)
            except OSError as exc:
                warnings.warn(f"Cannot stat handoff file {p}: {exc}", stacklevel=2)
                continue
    return paths


def generate_report(
    tickets_dir: Path,
    handoffs_dir: Path,
) -> TriageReport:
    """Generate a triage report: open tickets + orphaned handoff items.

    Returns dict with: open_tickets, orphaned_items, matched_items,
    match_counts, skipped_prose_count.

    P1-1 fix: orphaned_items contains only manual_review items.
    Matched items (uid_match, id_ref) go to matched_items.

    Note: read_open_tickets and _load_tickets_for_matching both scan tickets_dir,
    parsing each file twice. Acceptable for current corpus size. (P3-6)
    """
    open_tickets = read_open_tickets(tickets_dir)
    tickets_for_matching = _load_tickets_for_matching(tickets_dir)

    # Scan handoffs
    all_items: list[dict[str, Any]] = []
    total_skipped_prose = 0
    for path in _scan_handoff_dirs(handoffs_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.warn(f"Cannot read handoff file {path}: {exc}", stacklevel=2)
            continue
        items, skipped = extract_handoff_items(text, path.name)
        all_items.extend(items)
        total_skipped_prose += skipped

    # Legacy fallback: also scan docs/handoffs/ for pre-cutover files.
    legacy_found = False
    try:
        legacy_dir = get_legacy_handoffs_dir()
        if legacy_dir.exists():
            for path in _scan_handoff_dirs(legacy_dir, archive_name="archive"):
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    warnings.warn(f"Cannot read handoff file {path}: {exc}", stacklevel=2)
                    continue
                items, skipped = extract_handoff_items(text, path.name)
                if items:
                    legacy_found = True
                all_items.extend(items)
                total_skipped_prose += skipped
    except OSError as exc:
        warnings.warn(f"Cannot scan legacy handoffs: {exc}", stacklevel=2)

    # Match each item — separate orphaned from matched (P1-1)
    orphaned: list[MatchResult] = []
    matched: list[MatchResult] = []
    counts = {"uid_match": 0, "id_ref": 0, "manual_review": 0}
    for item in all_items:
        result = match_orphan_item(item, tickets_for_matching)
        counts[result["match_type"]] += 1
        if result["match_type"] == "manual_review":
            orphaned.append(result)
        else:
            matched.append(result)

    legacy_warning = None
    if legacy_found:
        legacy_warning = (
            "Found handoffs at legacy location `docs/handoffs/`. "
            "Post-cutover writes use `.codex/handoffs/`; legacy matches are "
            "read-only compatibility input."
        )

    return {
        "open_tickets": open_tickets,
        "orphaned_items": orphaned,
        "matched_items": matched,
        "match_counts": counts,
        "skipped_prose_count": total_skipped_prose,
        "legacy_warning": legacy_warning,
    }


def generate_project_report(tickets_dir: Path, project_root: Path) -> TriageReport:
    """Generate triage report from storage-authority history candidates."""
    open_tickets = read_open_tickets(tickets_dir)
    tickets_for_matching = _load_tickets_for_matching(tickets_dir)

    inventory = discover_handoff_inventory(project_root, scan_mode="history-search")
    all_items: list[dict[str, Any]] = []
    total_skipped_prose = 0
    legacy_found = False
    for candidate in eligible_history_candidates(inventory):
        if not _within_lookback(candidate.path):
            continue
        try:
            text = candidate.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.warn(f"Cannot read handoff file {candidate.path}: {exc}", stacklevel=2)
            continue
        items, skipped = extract_handoff_items(text, candidate.path.name)
        for item in items:
            item.update(_candidate_provenance(candidate))
        if items and candidate.storage_location in {
            StorageLocation.LEGACY_ACTIVE,
            StorageLocation.LEGACY_ARCHIVE,
        }:
            legacy_found = True
        all_items.extend(items)
        total_skipped_prose += skipped

    orphaned: list[MatchResult] = []
    matched: list[MatchResult] = []
    counts = {"uid_match": 0, "id_ref": 0, "manual_review": 0}
    for item in all_items:
        result = match_orphan_item(item, tickets_for_matching)
        counts[result["match_type"]] += 1
        if result["match_type"] == "manual_review":
            orphaned.append(result)
        else:
            matched.append(result)

    legacy_warning = None
    if legacy_found:
        legacy_warning = (
            "Found handoffs at legacy location `docs/handoffs/`. "
            "Post-cutover writes use `.codex/handoffs/`; legacy matches are "
            "read-only compatibility input."
        )

    return {
        "open_tickets": open_tickets,
        "orphaned_items": orphaned,
        "matched_items": matched,
        "match_counts": counts,
        "skipped_prose_count": total_skipped_prose,
        "legacy_warning": legacy_warning,
    }


def _within_lookback(path: Path) -> bool:
    try:
        return path.stat().st_mtime >= time.time() - (_LOOKBACK_DAYS * 86400)
    except OSError as exc:
        warnings.warn(f"Cannot stat handoff file {path}: {exc}", stacklevel=2)
        return False


def _candidate_provenance(candidate: HandoffCandidate) -> dict[str, Any]:
    return {
        "source_path": str(candidate.path),
        "storage_location": candidate.storage_location,
        "artifact_class": candidate.artifact_class,
        "source_git_visibility": candidate.source_git_visibility,
        "source_fs_status": candidate.source_fs_status,
        "document_profile": candidate.document_profile,
        "content_sha256": candidate.content_sha256,
        "dedup_winner": True,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Outputs JSON triage report to stdout."""
    parser = argparse.ArgumentParser(description="Triage open tickets and orphaned items")
    parser.add_argument("--tickets-dir", type=Path, default=Path("docs/tickets"))
    parser.add_argument("--handoffs-dir", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.handoffs_dir is None:
        project_root = (
            args.project_root.resolve()
            if args.project_root is not None
            else get_project_root()[0]
        )
        report = generate_project_report(args.tickets_dir, project_root)
    else:
        report = generate_report(args.tickets_dir, args.handoffs_dir)
    json.dump(report, sys.stdout, indent=2)
    print()  # trailing newline
    return 0
