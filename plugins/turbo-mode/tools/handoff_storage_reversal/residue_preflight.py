#!/usr/bin/env python3
"""Generate and check residue preflight evidence for docs/handoffs."""

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
    ALLOWED_SCOPE_VALUES,
    ToolError,
    fs_status,
    git_status_class,
    git_visibility_basis,
    iter_inventory,
    manifest_hash,
    parse_markdown_table,
    read_text,
    relative_to_root,
    section_body,
    sha256_file,
    write_text_if_changed,
)


LEGACY_EVIDENCE = Path(".codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json")
STATE_RE = re.compile(r"^handoff-(?P<project>.+)-(?P<token>[0-9a-f]{32})\.json$")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def directory_summary(project_root: Path, path: Path, artifact_class: str, disposition: str) -> dict[str, Any]:
    descendants = sorted(relative_to_root(project_root, item) for item in path.rglob("*"))
    rel = relative_to_root(project_root, path)
    return {
        "inventory_scope": "canonical-checkout",
        "lexical_path": str(path),
        "resolved_path": str(path.resolve(strict=False)),
        "project_relative_path": rel,
        "git_status_class": git_status_class(project_root, rel),
        "filesystem_status": fs_status(path),
        "artifact_class": artifact_class,
        "disposition": disposition,
        "descendant_count": len(descendants),
        "descendant_manifest_hash": manifest_hash(descendants),
        "covered_descendant_paths": descendants,
        "rationale": "Directory scope is represented by a manifest hash under the Gate 0r preflight contract.",
        "verification_command": "find docs/handoffs -mindepth 1 -print | sort",
        "scope": "local-preflight",
    }


def state_like_row(project_root: Path, path: Path) -> dict[str, Any]:
    rel = relative_to_root(project_root, path)
    sha = sha256_file(path) if path.is_file() else None
    match = STATE_RE.match(path.name)
    detected = "invalid state-like residue"
    project = None
    token = None
    if match and path.is_file():
        try:
            json.loads(path.read_text(encoding="utf-8"))
            detected = "tokenized state JSON"
            project = match.group("project")
            token = match.group("token")
        except json.JSONDecodeError:
            detected = "invalid state-like residue"
    return {
        "inventory_scope": "canonical-checkout",
        "lexical_path": str(path),
        "resolved_path": str(path.resolve(strict=False)),
        "project_relative_path": rel,
        "git_status_class": git_status_class(project_root, rel),
        "git_visibility_basis": git_visibility_basis(project_root, rel),
        "filesystem_status": fs_status(path),
        "raw_byte_sha256": sha,
        "detected_format": detected,
        "project": project,
        "resume_token": token,
        "artifact_class": "state-like-residue",
        "selection_eligibility": "not-active-selection-input",
        "disposition": "bridge-once-fresh" if detected == "tokenized state JSON" else "reject-diagnostic",
        "rationale": "Top-level state-like residue is bridge input only and is never handoff markdown active-selection input.",
        "verification_command": "python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py --project-root . --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json --check",
        "scope": "local-preflight",
    }


def non_handoff_row(project_root: Path, path: Path) -> dict[str, Any]:
    rel = relative_to_root(project_root, path)
    return {
        "inventory_scope": "canonical-checkout",
        "lexical_path": str(path),
        "resolved_path": str(path.resolve(strict=False)),
        "project_relative_path": rel,
        "git_status_class": git_status_class(project_root, rel),
        "filesystem_status": fs_status(path),
        "raw_byte_sha256": sha256_file(path) if path.is_file() else None,
        "artifact_class": "non-handoff-filesystem-residue",
        "selection_eligibility": "not-runtime-input",
        "disposition": "out-of-scope-preserve",
        "rationale": "Unsupported filesystem residue is inventoried for accounting only.",
        "verification_command": "find docs/handoffs -mindepth 1 -print | sort",
        "scope": "local-preflight",
    }


def delegated_legacy_row(project_root: Path, path: Path, legacy_payload: dict[str, Any] | None) -> dict[str, Any]:
    rel = relative_to_root(project_root, path)
    evidence_path = project_root / LEGACY_EVIDENCE
    return {
        "inventory_scope": "canonical-checkout",
        "lexical_path": str(path),
        "resolved_path": str(path.resolve(strict=False)),
        "project_relative_path": rel,
        "git_status_class": git_status_class(project_root, rel),
        "filesystem_status": fs_status(path),
        "raw_byte_sha256": sha256_file(path) if path.is_file() else None,
        "artifact_class": "delegated-legacy-active-markdown",
        "disposition": "delegated-legacy-active-preflight",
        "delegated_evidence_path": LEGACY_EVIDENCE.as_posix(),
        "delegated_evidence_sha256": sha256_file(evidence_path) if evidence_path.exists() else None,
        "delegated_match_count": legacy_payload.get("match_count") if legacy_payload else None,
        "selection_eligibility": "delegated-to-legacy-active-preflight",
        "rationale": "Top-level legacy active markdown classification is owned by legacy_active_preflight.py.",
        "verification_command": "python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py --project-root . --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json --check",
        "scope": "local-preflight",
    }


def discover_rows(project_root: Path) -> list[dict[str, Any]]:
    legacy_payload = load_json(project_root / LEGACY_EVIDENCE)
    rows: list[dict[str, Any]] = []
    for path in iter_inventory(project_root):
        rel = relative_to_root(project_root, path)
        if rel.startswith("docs/handoffs/archive/"):
            continue
        if rel.startswith("docs/handoffs/.session-state/"):
            continue
        if rel == "docs/handoffs/archive":
            rows.append(directory_summary(project_root, path, "legacy-operational-archive", "scope-owned-by-history-search"))
        elif rel == "docs/handoffs/.session-state":
            rows.append(directory_summary(project_root, path, "legacy-state-bridge-input", "scope-owned-by-state-bridge"))
        elif path.parent == project_root / "docs" / "handoffs" and path.suffix == ".md":
            rows.append(delegated_legacy_row(project_root, path, legacy_payload))
        elif path.parent == project_root / "docs" / "handoffs" and path.name.startswith("handoff-"):
            rows.append(state_like_row(project_root, path))
        else:
            rows.append(non_handoff_row(project_root, path))
    return rows


def build_payload(project_root: Path, plan: Path, evidence: Path) -> dict[str, Any]:
    rows = discover_rows(project_root)
    return {
        "run_id": "handoff-storage-residue-preflight-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "control_document": str(plan),
        "inventory_scope": "canonical-checkout",
        "checkout_root": str(project_root.resolve(strict=False)),
        "evidence_path": str(evidence),
        "inventory_command": "find docs/handoffs -mindepth 1 -print | sort",
        "match_count": len(iter_inventory(project_root)),
        "row_count": len(rows),
        "rows": rows,
    }


def validate_ledger(ledger_text: str) -> None:
    table = parse_markdown_table(section_body(ledger_text, "Ledger"))
    for row in table:
        scope = row.get("scope", "").strip("`")
        if scope not in ALLOWED_SCOPE_VALUES:
            raise ToolError(f"residue_preflight check failed: invalid ledger scope. Got: {scope!r}")
        if scope == "repo-authority" and "docs/handoffs/handoff-" in row.get("subject", ""):
            raise ToolError("residue_preflight check failed: local residue listed as repo-authority. Got: ledger row")
    policy_rows = [row for row in table if row.get("subject") == "`docs/handoffs/*.md` active legacy files"]
    if not policy_rows:
        raise ToolError("residue_preflight check failed: legacy active policy row missing. Got: ledger")
    policy_text = " ".join(policy_rows[0].values())
    required = ["provenance-backed ignored", "provenance-backed untracked", "storage_location=legacy_active", "raw-byte SHA256"]
    missing = [item for item in required if item not in policy_text]
    if missing:
        raise ToolError(f"residue_preflight check failed: stale ledger policy text. Got: missing={missing!r}")


def validate_payload(project_root: Path, payload: dict[str, Any]) -> None:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ToolError("residue_preflight check failed: rows missing. Got: invalid evidence")
    current = {relative_to_root(project_root, path) for path in iter_inventory(project_root)}
    covered: set[str] = set()
    for row in rows:
        rel = row.get("project_relative_path")
        if rel:
            covered.add(rel)
        covered.update(row.get("covered_descendant_paths", []))
        if row.get("scope") != "local-preflight":
            raise ToolError(f"residue_preflight check failed: invalid row scope. Got: {rel!r}")
        if "TBD" in json.dumps(row, sort_keys=True):
            raise ToolError(f"residue_preflight check failed: TBD evidence field. Got: {rel!r}")
        if row.get("disposition") == "bridge-once":
            raise ToolError(f"residue_preflight check failed: stale bridge-once disposition. Got: {rel!r}")
        if row.get("selection_eligibility") not in {None, "not-active-selection-input", "not-runtime-input", "delegated-to-legacy-active-preflight"}:
            raise ToolError(f"residue_preflight check failed: local evidence granted migration eligibility. Got: {rel!r}")
        path = project_root / str(rel)
        if row.get("raw_byte_sha256") and path.exists() and path.is_file() and row.get("raw_byte_sha256") != sha256_file(path):
            raise ToolError(f"residue_preflight check failed: hash drift. Got: {rel!r}")
    if current != covered:
        raise ToolError(f"residue_preflight check failed: inventory drift. Got: missing={sorted(current-covered)!r} extra={sorted(covered-current)!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        project_root = args.project_root.resolve(strict=False)
        evidence_path = (project_root / args.evidence).resolve(strict=False) if not args.evidence.is_absolute() else args.evidence
        if args.write:
            write_text_if_changed(evidence_path, json.dumps(build_payload(project_root, args.plan, evidence_path), indent=2, sort_keys=True) + "\n")
        validate_ledger(read_text(args.ledger))
        payload = json.loads(read_text(evidence_path))
        validate_payload(project_root, payload)
    except (ToolError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
