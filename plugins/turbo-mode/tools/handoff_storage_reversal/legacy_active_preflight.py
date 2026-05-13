#!/usr/bin/env python3
"""Generate and check legacy active markdown preflight evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from _common import (
    ToolError,
    fs_status,
    git_status_class,
    git_visibility_basis,
    normalize_text,
    read_text,
    relative_to_root,
    sha256_file,
    write_text_if_changed,
)


REQUIRED_FIELDS = {"project", "created_at", "session_id", "type"}
FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_.+\.md$")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def document_profile(frontmatter: dict[str, str], basename: str) -> str:
    if not FILENAME_RE.match(basename):
        return "invalid_filename_timestamp"
    if REQUIRED_FIELDS <= set(frontmatter):
        return "current_contract"
    return "invalid_current_contract"


def discover_rows(project_root: Path) -> list[dict[str, Any]]:
    base = project_root / "docs" / "handoffs"
    rows: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.md")):
        rel_path = relative_to_root(project_root, path)
        status = git_status_class(project_root, rel_path)
        text = read_text(path)
        frontmatter = parse_frontmatter(text)
        profile = document_profile(frontmatter, path.name)
        readable_hash = sha256_file(path) if path.is_file() else None
        origin_fields = [field for field in ("project", "created_at", "session_id", "type", "branch", "commit", "resumed_from", "files") if field in frontmatter]
        if status in {"ignored", "untracked"} and profile == "current_contract":
            artifact_class = "policy-conflict-artifact"
            selection = "blocked-policy-conflict"
            external_origin = "none"
            missing = [
                "plugin-origin-runtime-marker-provenance",
                "legacy-active-preflight-runtime-provenance-with-external-origin",
                "reviewed-runtime-migration-opt-in",
            ]
        else:
            artifact_class = "tracked-durable-handoff-artifact" if status == "tracked" else "policy-conflict-artifact"
            selection = "blocked-policy-conflict"
            external_origin = "none"
            missing = ["not an eligible ignored or untracked current-contract legacy active file"]
        rows.append(
            {
                "inventory_scope": "canonical-checkout",
                "lexical_path": str(path),
                "resolved_path": str(path.resolve(strict=False)),
                "project_relative_path": rel_path,
                "git_status_class": status,
                "git_visibility_basis": git_visibility_basis(project_root, rel_path),
                "filesystem_status": fs_status(path),
                "raw_byte_sha256": readable_hash,
                "filename_timestamp_parseable": bool(FILENAME_RE.match(path.name)),
                "document_profile": profile,
                "frontmatter_fields_present": sorted(frontmatter),
                "external_origin_source": external_origin,
                "origin_evidence_fields": origin_fields,
                "missing_or_rejected_provenance_fields": missing,
                "artifact_class": artifact_class,
                "selection_eligibility": selection,
                "rationale": "Ordinary handoff frontmatter is runtime-shaped content, not external plugin-origin proof.",
                "verification_command": "python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py --project-root . --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json --check",
                "scope": "legacy-active-preflight",
            }
        )
    return rows


def build_payload(project_root: Path, evidence_path: Path) -> dict[str, Any]:
    rows = discover_rows(project_root)
    return {
        "run_id": "handoff-storage-legacy-active-preflight-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "inventory_scope": "canonical-checkout",
        "checkout_root": str(project_root.resolve(strict=False)),
        "evidence_path": str(evidence_path),
        "inventory_command": "find docs/handoffs -maxdepth 1 -name '*.md' -print | sort",
        "match_count": len(rows),
        "rows": rows,
    }


def validate_payload(project_root: Path, payload: dict[str, Any]) -> None:
    current = {relative_to_root(project_root, path) for path in sorted((project_root / "docs" / "handoffs").glob("*.md"))}
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ToolError("legacy_active_preflight check failed: rows missing. Got: invalid evidence")
    seen: set[str] = set()
    required_fields = {
        "artifact_class",
        "selection_eligibility",
        "raw_byte_sha256",
        "external_origin_source",
        "origin_evidence_fields",
        "missing_or_rejected_provenance_fields",
    }
    for row in rows:
        rel = row.get("project_relative_path")
        if rel in seen:
            raise ToolError(f"legacy_active_preflight check failed: duplicate row. Got: {rel!r}")
        seen.add(rel)
        missing = sorted(required_fields - set(row))
        if missing:
            raise ToolError(f"legacy_active_preflight check failed: missing fields. Got: {rel!r} {missing!r}")
        if any(row.get(field) == "TBD" for field in required_fields):
            raise ToolError(f"legacy_active_preflight check failed: TBD field. Got: {rel!r}")
        if row.get("selection_eligibility") != "blocked-policy-conflict" and row.get("external_origin_source") == "none":
            raise ToolError(f"legacy_active_preflight check failed: eligible row without external origin. Got: {rel!r}")
        path = project_root / str(rel)
        if path.exists() and row.get("raw_byte_sha256") != sha256_file(path):
            raise ToolError(f"legacy_active_preflight check failed: hash drift. Got: {rel!r}")
    if current != seen:
        raise ToolError(f"legacy_active_preflight check failed: inventory drift. Got: missing={sorted(current-seen)!r} extra={sorted(seen-current)!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        project_root = args.project_root.resolve(strict=False)
        evidence_path = (project_root / args.evidence).resolve(strict=False) if not args.evidence.is_absolute() else args.evidence
        if args.write:
            write_text_if_changed(evidence_path, json.dumps(build_payload(project_root, evidence_path), indent=2, sort_keys=True) + "\n")
        payload = json.loads(read_text(evidence_path))
        validate_payload(project_root, payload)
    except (ToolError, json.JSONDecodeError) as exc:
        print(normalize_text(str(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
