"""Template-based markdown rendering and canonical YAML serialization for tickets."""
from __future__ import annotations

import json
import re
from typing import Any

import yaml


CANONICAL_FIELD_ORDER = [
    "id",
    "date",
    "created_at",
    "status",
    "priority",
    "effort",
    "source",
    "tags",
    "blocked_by",
    "blocks",
    "contract_version",
]

_FENCED_YAML_BLOCK_RE = re.compile(r"^```ya?ml\s*\n.*?^```", re.MULTILINE | re.DOTALL)
_PLAIN_YAML_SCALAR_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_YAML_RESERVED_SCALARS = frozenset(
    {"null", "~", "true", "false", "yes", "no", "on", "off"}
)
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _yaml_scalar(value: Any) -> str:
    """Render a scalar as safe YAML while preserving plain style when possible."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return json.dumps(str(value), ensure_ascii=False)

    if (
        value
        and "\n" not in value
        and "\r" not in value
        and "\t" not in value
        and value.strip() == value
        and _PLAIN_YAML_SCALAR_RE.match(value)
        and not value.startswith("-")
        and value.lower() not in _YAML_RESERVED_SCALARS
        and _INT_RE.match(value) is None
        and _FLOAT_RE.match(value) is None
        and _DATE_RE.match(value) is None
    ):
        return value
    return json.dumps(value, ensure_ascii=False)


def _yaml_value(value: Any) -> str:
    """Render a YAML value in flow style for lists and dicts."""
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        try:
            dumped = yaml.safe_dump(
                value,
                default_flow_style=True,
                allow_unicode=True,
                sort_keys=False,
            ).strip()
        except yaml.YAMLError as exc:
            raise ValueError(
                f"yaml serialization failed: {exc}. Got: {value!r:.100}"
            ) from exc
        if dumped.endswith("\n..."):
            dumped = dumped.rsplit("\n...", 1)[0]
        return dumped
    return _yaml_scalar(value)


def render_frontmatter(data: dict[str, Any]) -> str:
    """Render YAML frontmatter with controlled field order and quoting."""
    lines: list[str] = []
    for key in CANONICAL_FIELD_ORDER:
        if key not in data:
            continue
        value = data[key]
        if value is None:
            continue
        if key == "date":
            lines.append(f"{key}: {_yaml_scalar(str(value))}")
        elif key == "source" and isinstance(value, dict):
            lines.append("source:")
            for source_key, source_value in value.items():
                lines.append(f"  {source_key}: {_yaml_value(source_value)}")
        elif key == "contract_version":
            lines.append(f"{key}: {_yaml_scalar(value)}")
        else:
            lines.append(f"{key}: {_yaml_value(value)}")

    known_keys = set(CANONICAL_FIELD_ORDER) | {"defer"}
    for key, value in data.items():
        if key in known_keys or value is None:
            continue
        lines.append(f"{key}: {_yaml_value(value)}")

    if "defer" in data and data["defer"] is not None:
        lines.append("defer:")
        for defer_key, defer_value in data["defer"].items():
            lines.append(f"  {defer_key}: {_yaml_value(defer_value)}")

    return "\n".join(lines) + "\n"


def replace_fenced_yaml(text: str, data: dict[str, Any]) -> str:
    """Replace the first fenced YAML block with canonical frontmatter."""
    new_yaml = render_frontmatter(data)
    new_text, replacements = _FENCED_YAML_BLOCK_RE.subn(
        f"```yaml\n{new_yaml}```",
        text,
        count=1,
    )
    if replacements != 1:
        raise ValueError(
            f"yaml replacement failed: fenced YAML block not found. Got: {text!r:.100}"
        )
    return new_text


def render_ticket(
    *,
    id: str,
    title: str,
    date: str,
    status: str,
    priority: str,
    problem: str,
    created_at: str = "",
    effort: str = "",
    source: dict[str, str] | None = None,
    tags: list[str] | None = None,
    blocked_by: list[str] | None = None,
    blocks: list[str] | None = None,
    contract_version: str = "1.0",
    defer: dict[str, Any] | None = None,
    approach: str = "",
    acceptance_criteria: list[str] | None = None,
    verification: str = "",
    key_files: list[dict[str, str]] | None = None,
    key_file_paths: list[str] | None = None,
    context: str = "",
    prior_investigation: str = "",
    decisions_made: str = "",
    related: str = "",
) -> str:
    """Render a complete v1.0 ticket markdown file.

    Returns the full file content as a string.
    Section ordering follows the contract: Problem -> Context -> Prior Investigation ->
    Approach -> Decisions Made -> Acceptance Criteria -> Verification -> Key Files -> Related.
    """
    source = source or {"type": "ad-hoc", "ref": "", "session": ""}
    tags = tags or []
    blocked_by = blocked_by or []
    blocks = blocks or []

    # --- YAML frontmatter (render_frontmatter preserves canonical ordering and safe quoting) ---
    frontmatter: dict[str, Any] = {
        "id": id,
        "date": date,
    }
    if created_at:
        frontmatter["created_at"] = created_at
    frontmatter["status"] = status
    frontmatter["priority"] = priority
    if effort:
        frontmatter["effort"] = effort
    frontmatter["source"] = {
        "type": source["type"],
        "ref": source.get("ref", ""),
        "session": source.get("session", ""),
    }
    frontmatter["tags"] = tags
    frontmatter["blocked_by"] = blocked_by
    frontmatter["blocks"] = blocks

    if defer is not None:
        frontmatter["defer"] = {
            "active": defer.get("active", False),
            "reason": defer.get("reason", ""),
            "deferred_at": defer.get("deferred_at", ""),
        }

    frontmatter["contract_version"] = contract_version

    # Persist key_file_paths for future dedup scans (C-002).
    if key_file_paths:
        frontmatter["key_file_paths"] = sorted(key_file_paths)

    yaml_str = render_frontmatter(frontmatter).rstrip("\n")

    lines = [
        f"# {id}: {title}",
        "",
        "```yaml",
        yaml_str,
        "```",
        "",
    ]

    # --- Required sections ---
    lines.extend(["## Problem", problem, ""])

    # --- Optional sections (in contract order) ---
    if context:
        lines.extend(["## Context", context, ""])

    if prior_investigation:
        lines.extend(["## Prior Investigation", prior_investigation, ""])

    if approach:
        lines.extend(["## Approach", approach, ""])

    if decisions_made:
        lines.extend(["## Decisions Made", decisions_made, ""])

    # Acceptance criteria.
    if acceptance_criteria:
        lines.append("## Acceptance Criteria")
        for criterion in acceptance_criteria:
            lines.append(f"- [ ] {criterion}")
        lines.append("")

    # Verification.
    if verification:
        lines.extend([
            "## Verification",
            "```bash",
            verification,
            "```",
            "",
        ])

    # Key files.
    if key_files:
        lines.extend([
            "## Key Files",
            "| File | Role | Look For |",
            "|------|------|----------|",
        ])
        for kf in key_files:
            lines.append(f"| {kf.get('file', '')} | {kf.get('role', '')} | {kf.get('look_for', '')} |")
        lines.append("")

    if related:
        lines.extend(["## Related", related, ""])

    return "\n".join(lines)
