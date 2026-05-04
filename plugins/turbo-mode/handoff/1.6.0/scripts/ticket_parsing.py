"""Parse fenced-YAML ticket format used in docs/tickets/.

Existing tickets use ```yaml ... ``` blocks (NOT --- frontmatter).
handoff_parsing.py cannot parse this format. This module uses PyYAML
for full YAML support including multiline values (files: arrays, etc.).
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Match the first ```yaml ... ``` block in a markdown file.
_FENCED_YAML_RE = re.compile(
    r"^```ya?ml\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)


def extract_fenced_yaml(text: str) -> str | None:
    """Extract the YAML text from the first fenced yaml block.

    Returns None if no fenced yaml block is found.
    """
    m = _FENCED_YAML_RE.search(text)
    return m.group(1) if m else None


def _normalize_yaml_scalars(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize yaml.safe_load auto-conversions back to strings.

    PyYAML converts unquoted date-like values (e.g., 2026-02-28) to
    datetime.date objects. This normalizes top-level string fields back to str.

    Note: Does not recurse into nested dicts (e.g., provenance subdict).
    Ticket schema only uses date-like values at top level. (P1-8)
    """
    import datetime

    for key, value in data.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            data[key] = str(value)
    return data


def parse_yaml_frontmatter(yaml_text: str) -> dict[str, Any] | None:
    """Parse a YAML string into a dict using yaml.safe_load.

    Returns None if the YAML is empty or malformed.
    Normalizes datetime.date/datetime values back to str (P0-3 fix).
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
    return _normalize_yaml_scalars(result)


# --- Schema validation and ticket parsing ---

_REQUIRED_FIELDS = ("id", "date", "status")
_LIST_FIELDS = ("files", "blocked_by", "blocks", "related")
_DICT_FIELDS = ("provenance",)
_STRING_FIELDS = ("id", "date", "status", "priority", "source_type", "source_ref", "branch", "effort")


@dataclass(frozen=True)
class TicketFile:
    """Parsed ticket with typed frontmatter and markdown body.

    Note: frozen prevents field reassignment but the frontmatter dict
    is mutable at runtime. All production code constructs TicketFile
    via parse_ticket() which validates schema. Direct construction
    (e.g., in tests) bypasses validation.
    """

    path: str
    frontmatter: dict[str, Any]
    body: str


def validate_schema(data: dict[str, Any]) -> list[str]:
    """Validate ticket frontmatter schema. Returns list of error messages (empty = valid)."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")
    for field in _STRING_FIELDS:
        if field in data and not isinstance(data[field], str):
            errors.append(f"{field} must be string, got {type(data[field]).__name__}")
    for field in _LIST_FIELDS:
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be list, got {type(data[field]).__name__}")
    for field in _DICT_FIELDS:
        if field in data and not isinstance(data[field], dict):
            errors.append(f"{field} must be dict, got {type(data[field]).__name__}")
    return errors


def parse_ticket(path: Path) -> TicketFile | None:
    """Parse a ticket markdown file into a TicketFile.

    Returns None if:
    - File doesn't exist or can't be read
    - No fenced YAML block found
    - YAML is malformed
    - Required fields missing (id, date, status)

    Emits warnings with diagnostic detail for each failure mode.
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

    frontmatter = parse_yaml_frontmatter(yaml_text)
    if frontmatter is None:
        # Intentional double-warning design: parse_yaml_frontmatter warns with
        # stacklevel=2 (blames parse_ticket), this second warning warns with
        # stacklevel=2 (blames the caller). Two warnings, two different frames.
        # Callers see exactly 2 warnings for malformed YAML (tested explicitly).
        warnings.warn(f"Cannot parse frontmatter in {path}", stacklevel=2)
        return None

    errors = validate_schema(frontmatter)
    if errors:
        warnings.warn(
            f"Schema validation failed for {path}: {'; '.join(errors)}",
            stacklevel=2,
        )
        return None

    # Body is everything after the fenced YAML block's closing ```
    m = _FENCED_YAML_RE.search(text)
    body = text[m.end() :].strip() if m else ""

    return TicketFile(path=str(path), frontmatter=frontmatter, body=body)
