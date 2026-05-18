"""Fenced-YAML ticket parsing with legacy format support.

Parses ticket markdown files from docs/tickets/. Supports 4 legacy
generations plus v1.0 format. Applies field defaults, section renames,
and status normalization on read (never writes back).

Based on handoff plugin's ticket_parsing.py with additions:
section extraction, legacy detection, status normalization.
"""
from __future__ import annotations

import copy
import datetime
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Match the first ```yaml or ```yml block in markdown.
_FENCED_YAML_RE = re.compile(
    r"^```ya?ml\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)

# Match ## headings (level 2 only — ### and deeper are section content).
_SECTION_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_H1_HEADING_RE = re.compile(r"^# (.+)$", re.MULTILINE)

# Legacy section renames (3-tier: exact → near-equivalent → preserve).
SECTION_RENAMES: dict[str, str] = {
    # Exact renames
    "Summary": "Problem",
    "Findings": "Prior Investigation",
    "Proposed Approach": "Approach",
    "Files Affected": "Key Files",
    "Files to Create/Modify": "Key Files",
    # Near-equivalents
    "Scope": "Context",
    "Risks": "Context",
}

# Canonical statuses (v1.0).
CANONICAL_STATUSES = frozenset({"open", "in_progress", "blocked", "done", "wontfix"})

# Legacy status normalization map.
_STATUS_MAP: dict[str, str] = {
    "planning": "open",
    "implementing": "in_progress",
    "complete": "done",
    "closed": "done",
    "deferred": "open",
}

# Required YAML fields for parse-level schema validation.
# Only 3 of 6 contract-required fields (id, date, status) are enforced here.
# The remaining 3 (priority, source, contract_version) are applied as defaults
# by _apply_field_defaults() for legacy tickets. Enforcing all 6 at parse time
# would reject all legacy tickets (Gen 1-4 lack these fields).
# Full 6-field validation happens at create time in engine_execute.
_REQUIRED_FIELDS = ("id", "date", "status")

# Field defaults for legacy tickets (applied on read, not written back).
_FIELD_DEFAULTS: dict[str, Any] = {
    "priority": "medium",
    "source": {"type": "legacy", "ref": "", "session": ""},
    "effort": "",
    "tags": [],
    "blocked_by": [],
    "blocks": [],
}

# ID pattern matchers for generation detection.
_GEN2_ID_RE = re.compile(r"^T-[A-F]$")
_GEN3_ID_RE = re.compile(r"^T-\d{1,3}$")
_DATE_ID_RE = re.compile(r"^T-\d{8}-\d{2}$")


@dataclass(frozen=True)
class ParsedTicket:
    """A parsed ticket with normalized fields and extracted sections.

    All legacy field mapping and status normalization is applied.
    The `generation` field indicates which format was detected (1-4, or 10 for v1.0).
    """

    path: str
    id: str
    title: str
    date: str
    status: str
    priority: str
    source: dict[str, str]
    generation: int
    frontmatter: dict[str, Any]
    sections: dict[str, str]
    created_at: str = ""
    effort: str = ""
    tags: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    contract_version: str = ""
    defer: dict[str, Any] | None = None
    body: str = ""


def extract_fenced_yaml(text: str) -> str | None:
    """Extract YAML text from the first fenced yaml block. Returns None if not found."""
    m = _FENCED_YAML_RE.search(text)
    return m.group(1) if m else None


def parse_yaml_block(yaml_text: str) -> dict[str, Any] | None:
    """Parse a YAML string into a dict. Returns None if empty or malformed.

    Normalizes datetime.date values back to str (PyYAML auto-converts unquoted dates).
    """
    if not yaml_text.strip():
        return None
    try:
        result = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        warnings.warn(f"YAML parse error: {exc}", stacklevel=2)
        return None
    if not isinstance(result, dict):
        warnings.warn(
            f"YAML parsed as {type(result).__name__}, expected dict",
            stacklevel=2,
        )
        return None
    # Normalize date objects back to strings.
    for key, value in result.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            result[key] = str(value)
    return result


def extract_sections(body: str) -> dict[str, str]:
    """Extract ## sections from markdown body into a dict.

    Keys are section names (without ##). Values are the section content
    (everything between this heading and the next ## heading or end of text).
    ### subheadings and deeper are included in their parent section.
    Content before the first ## heading is discarded.
    """
    if not body.strip():
        return {}

    sections: dict[str, str] = {}
    matches = list(_SECTION_HEADING_RE.finditer(body))

    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections[name] = content

    return sections


def extract_title(text: str, ticket_id: str) -> str:
    """Extract title text from the first H1 heading."""
    match = _H1_HEADING_RE.search(text)
    if match is None:
        return ""

    heading = match.group(1).strip()
    if not heading:
        return ""

    prefix = f"{ticket_id}:"
    if heading.startswith(prefix):
        return heading[len(prefix):].strip()
    return heading


def detect_generation(frontmatter: dict[str, Any]) -> int:
    """Detect ticket generation from frontmatter fields.

    Returns: 1 (slug), 2 (T-[A-F]), 3 (T-NNN), 4 (defer output), 10 (v1.0).
    """
    ticket_id = str(frontmatter.get("id", ""))

    # v1.0: has contract_version or source (not provenance)
    if "contract_version" in frontmatter or (
        "source" in frontmatter and "provenance" not in frontmatter
    ):
        return 10

    # Gen 4: date-based ID with provenance dict
    if _DATE_ID_RE.match(ticket_id) and "provenance" in frontmatter:
        return 4

    # Gen 2: letter IDs
    if _GEN2_ID_RE.match(ticket_id):
        return 2

    # Gen 3: numeric IDs
    if _GEN3_ID_RE.match(ticket_id):
        return 3

    # Gen 1: slug IDs (anything that doesn't match the above)
    return 1


def normalize_status(raw_status: str) -> tuple[str, dict[str, Any] | None]:
    """Normalize a raw status to canonical + optional defer info.

    Returns (canonical_status, defer_info_or_none).
    Unknown statuses pass through unchanged (mutation paths fail closed).
    """
    if raw_status in CANONICAL_STATUSES:
        return (raw_status, None)

    canonical = _STATUS_MAP.get(raw_status, raw_status)

    defer_info = None
    if raw_status == "deferred":
        defer_info = {"active": True, "reason": "", "deferred_at": ""}

    return (canonical, defer_info)


def _apply_section_renames(sections: dict[str, str]) -> dict[str, str]:
    """Apply section renames per the 3-tier strategy. Returns new dict."""
    renamed: dict[str, str] = {}
    for name, content in sections.items():
        new_name = SECTION_RENAMES.get(name, name)
        # If target already exists (e.g., ticket has both Summary and Problem),
        # append rather than overwrite.
        if new_name in renamed:
            renamed[new_name] += "\n\n" + content
        else:
            renamed[new_name] = content
    return renamed


def _apply_field_defaults(frontmatter: dict[str, Any], generation: int) -> dict[str, Any]:
    """Apply field defaults for legacy tickets. Returns modified frontmatter.

    Uses deepcopy for mutable defaults (dicts, lists) to prevent shared state
    leaking across tickets parsed in the same process.
    """
    for field_name, default in _FIELD_DEFAULTS.items():
        if field_name not in frontmatter:
            frontmatter[field_name] = copy.deepcopy(default)
    return frontmatter


def _map_gen4_fields(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Map Gen 4 (defer output) fields to v1.0 equivalents.

    provenance → source, source_type/source_ref → source.type/source.ref
    """
    provenance = frontmatter.pop("provenance", {})
    source_type = frontmatter.pop("source_type", provenance.get("created_by", "defer"))
    source_ref = frontmatter.pop("source_ref", "")
    session = provenance.get("session_id", "")

    frontmatter["source"] = {
        "type": source_type if source_type != "defer.py" else "defer",
        "ref": source_ref,
        "session": session,
    }
    return frontmatter


def parse_ticket(path: Path) -> ParsedTicket | None:
    """Parse a ticket file into a ParsedTicket with full normalization.

    Supports v1.0 and 4 legacy generations. Returns None on read/parse failure.
    Applies: field defaults, section renames, status normalization, field mapping.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        warnings.warn(f"Cannot read ticket {path}: {exc}", stacklevel=2)
        return None

    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None:
        warnings.warn(f"No fenced YAML block in {path}", stacklevel=2)
        return None

    frontmatter = parse_yaml_block(yaml_text)
    if frontmatter is None:
        warnings.warn(f"Cannot parse frontmatter in {path}", stacklevel=2)
        return None

    # Validate required fields.
    missing = [f for f in _REQUIRED_FIELDS if f not in frontmatter]
    if missing:
        warnings.warn(
            f"Ticket {path} missing required fields: {', '.join(missing)}",
            stacklevel=2,
        )
        return None

    # Coerce id to string (YAML may parse bare integers as int).
    frontmatter["id"] = str(frontmatter["id"])

    # Detect generation.
    generation = detect_generation(frontmatter)

    # Map Gen 4 fields before applying defaults.
    if generation == 4:
        frontmatter = _map_gen4_fields(frontmatter)

    # Apply field defaults for legacy tickets.
    if generation < 10:
        frontmatter = _apply_field_defaults(frontmatter, generation)

    # Normalize status.
    raw_status = frontmatter["status"]
    canonical_status, defer_info = normalize_status(raw_status)
    frontmatter["status"] = canonical_status

    # If status was "deferred" and ticket has existing defer field, preserve it.
    if defer_info is not None and "defer" not in frontmatter:
        frontmatter["defer"] = defer_info

    # Extract body (everything after the closing ``` of the YAML block).
    m = _FENCED_YAML_RE.search(text)
    body = text[m.end():].strip() if m else ""

    # Extract and rename sections.
    sections = extract_sections(body)
    if generation < 10:
        sections = _apply_section_renames(sections)

    # Build source dict (copy default to prevent shared mutable state).
    source = frontmatter.get("source") or copy.deepcopy(_FIELD_DEFAULTS["source"])
    title = extract_title(text, frontmatter["id"])

    return ParsedTicket(
        path=str(path),
        id=frontmatter["id"],
        title=title,
        date=frontmatter.get("date", ""),
        status=canonical_status,
        priority=frontmatter.get("priority", "medium"),
        source=source,
        generation=generation,
        frontmatter=frontmatter,
        sections=sections,
        created_at=frontmatter.get("created_at", ""),
        effort=frontmatter.get("effort", ""),
        tags=frontmatter.get("tags", []),
        blocked_by=frontmatter.get("blocked_by", []),
        blocks=frontmatter.get("blocks", []),
        contract_version=frontmatter.get("contract_version", ""),
        defer=frontmatter.get("defer"),
        body=body,
    )
