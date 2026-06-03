"""Shared schema validation for dedup inputs and writable ticket fields.

Validates field types and enum membership before dedup fingerprinting,
render_ticket(), or YAML replacement. Rejects invalid inputs; omitted
fields are not errors (defaults are applied by the engine, not the
validator).
"""

from __future__ import annotations

from typing import Any

from scripts.ticket_target_schema import TARGET_PRIORITIES, TARGET_STATUSES

VALID_PRIORITIES = frozenset(TARGET_PRIORITIES)
VALID_STATUSES = frozenset(TARGET_STATUSES)
VALID_RESOLUTIONS = frozenset({"done", "wontfix"})
VALID_CAPTURE_CONFIDENCE = frozenset({"low", "medium", "high"})
VALID_REFINEMENT_STATUSES = frozenset({"needs_refinement"})
DEPRECATED_WRITE_FIELDS = frozenset(
    {
        "date",
        "created_at",
        "effort",
        "source",
        "capture_confidence",
        "capture_source",
        "refinement_status",
        "component",
        "blocks",
        "contract_version",
        "defer",
        "key_file_paths",
        "key_files",
        "archive",
    }
)
CONTROLLED_CAPTURE_TAGS = frozenset(
    {
        "needs-refinement",
        "bug",
        "feature",
        "docs",
        "test",
        "maintenance",
        "security",
    }
)
CAPTURE_INPUT_FIELDS = frozenset(
    {
        "title",
        "captured_request",
        "problem",
        "next_action",
        "capture_confidence",
        "capture_source",
        "refinement_status",
        "component",
        "related_paths",
        "priority",
        "tags",
        "acceptance_criteria",
    }
)


def _validate_string_field(fields: dict[str, Any], key: str, errors: list[str]) -> None:
    """Append an error when an optional field is present but not a string."""
    if key not in fields:
        return
    value = fields[key]
    if not isinstance(value, str):
        errors.append(f"{key} must be a string, got {type(value).__name__}")


def validate_fields(fields: dict[str, Any]) -> list[str]:
    """Validate writable ticket fields. Returns list of error messages (empty = valid)."""
    errors: list[str] = []

    for key in sorted(DEPRECATED_WRITE_FIELDS & set(fields)):
        errors.append(f"{key} is not a target write field")

    # --- String fields ---
    for key in (
        "title",
        "problem",
        "reopen_reason",
        "captured_request",
        "next_action",
        "change_history_entry",
        "context",
        "prior_investigation",
        "approach",
        "decisions_made",
        "related",
    ):
        _validate_string_field(fields, key, errors)

    # --- Enum fields ---
    if "priority" in fields:
        v = fields["priority"]
        if not isinstance(v, str) or v not in VALID_PRIORITIES:
            errors.append(f"priority must be one of {sorted(VALID_PRIORITIES)}, got {v!r}")

    if "status" in fields:
        v = fields["status"]
        if not isinstance(v, str) or v not in VALID_STATUSES:
            errors.append(f"status must be one of {sorted(VALID_STATUSES)}, got {v!r}")

    if "resolution" in fields:
        v = fields["resolution"]
        if not isinstance(v, str) or v not in VALID_RESOLUTIONS:
            errors.append(f"resolution must be one of {sorted(VALID_RESOLUTIONS)}, got {v!r}")

    # --- List-of-string fields ---
    for key in ("tags", "blocked_by", "related_paths", "acceptance_criteria"):
        if key in fields:
            v = fields[key]
            if not isinstance(v, list):
                errors.append(f"{key} must be a list, got {type(v).__name__}")
            elif not all(isinstance(item, str) for item in v):
                errors.append(f"{key} must contain only strings")

    if (
        "acceptance_criteria" in fields
        and isinstance(fields["acceptance_criteria"], list)
        and any(item == "Needs refinement" for item in fields["acceptance_criteria"])
    ):
        errors.append("acceptance_criteria must be concrete; got Needs refinement")

    if (
        "tags" in fields
        and isinstance(fields["tags"], list)
        and "needs-refinement" in fields["tags"]
    ):
        errors.append("tag needs-refinement is not a target tag")

    return errors
