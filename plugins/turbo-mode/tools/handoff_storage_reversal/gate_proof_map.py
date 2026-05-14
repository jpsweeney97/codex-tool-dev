#!/usr/bin/env python3
"""Generate and check the Handoff storage reversal gate proof map."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from _common import (
    ToolError,
    markdown_bullets,
    markdown_table,
    normalize_text,
    parse_markdown_table,
    read_text,
    section_body,
    sha256_text,
    subsection_body,
    write_text_if_changed,
)

sys.dont_write_bytecode = True


HEADERS = [
    "requirement_id",
    "source_reference",
    "requirement_sha256",
    "first_enforcing_gate",
    "proof_owner",
    "proof_command_or_artifact",
    "split_trigger",
    "status",
]

BUDGETS = {
    "gate-1a-discovery-read-only-slice": 40,
    "gate-1b-reader-history-slice": 28,
    "gate-1c-load-transaction-slice": 45,
    "gate-1d-active-writer-operation-state-slice": 45,
    "gate-1e-state-bridge-and-recovery-slice": 40,
    "gate-1f-installed-host-harness-slice": 24,
    "gate-1g-active-writer-bridge-integration-slice": 18,
    "gate-2-skill-docs-release-docs": 30,
    "gate-3-refresh-and-stale-text": 34,
    "gate-4-source-closeout": 30,
    "gate-5-installed-certification": 18,
}
STORAGE_AUTHORITY_INVENTORY = Path(
    "plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json"
)


def gate_for(text: str, req_id: str) -> tuple[str, str, str, str, str]:
    lower = text.lower()
    if req_id.startswith("IH-") or "installed-host smoke" in lower:
        return (
            "gate-5-installed-certification",
            "installed-harness",
            "installed-host behavior proof; excluded from source repaired",
            "Gate 5 budget applies if certification is claimed",
            "not-claimed",
        )
    if "source-harness" in lower or "gate 1f" in lower:
        return (
            "gate-1f-installed-host-harness-slice",
            "installed-harness",
            "source-harness isolation pytest selector",
            "Gate 1f split trigger from capacity model",
            "pending",
        )
    if any(
        term in lower
        for term in (
            "active-writer",
            "save/summary/quicksave",
            "begin-active-write",
            "write-active-handoff",
            "allocate-active-path",
        )
    ):
        return (
            "gate-1d-active-writer-operation-state-slice",
            "active-writer",
            "active-writer operation-state tests",
            "Gate 1d split trigger from capacity model",
            "pending",
        )
    if any(
        term in lower
        for term in (
            "legacy state",
            "state bridge",
            "chain-state",
            "resume token",
            "state-like residue",
        )
    ):
        return (
            "gate-1e-state-bridge-and-recovery-slice",
            "state-recovery",
            "state bridge and recovery tests",
            "Gate 1e split trigger from capacity model",
            "pending",
        )
    if any(
        term in lower
        for term in ("load", "transaction", "registry", "archive copy", "copied legacy")
    ):
        return (
            "gate-1c-load-transaction-slice",
            "load-transaction",
            "load transaction pytest selector",
            "Gate 1c split trigger from capacity model",
            "pending",
        )
    if any(
        term in lower
        for term in (
            "list",
            "search",
            "triage",
            "distill",
            "history",
            "previous-primary",
            "no-frontmatter",
        )
    ):
        return (
            "gate-1b-reader-history-slice",
            "reader-history",
            "reader/history pytest selectors",
            "Gate 1b split trigger from capacity model",
            "pending",
        )
    if any(term in lower for term in ("skill docs", "launcher", "readme", "changelog")):
        return (
            "gate-2-skill-docs-release-docs",
            "skill-docs",
            "skill-doc and release-doc tests",
            "Gate 2 split trigger from capacity model",
            "pending",
        )
    if any(
        term in lower
        for term in (
            "refresh",
            "storage_authority_inventory",
            "stale-text",
            "gate_proof_map",
        )
    ):
        return (
            "gate-3-refresh-and-stale-text",
            "refresh",
            "refresh and stale-text checks",
            "Gate 3 split trigger from capacity model",
            "pending",
        )
    if req_id.startswith("HS-"):
        return (
            "gate-4-source-closeout",
            "closeout",
            "hard-stop closeout matrix evidence",
            "Gate 4 split trigger from capacity model",
            "pending",
        )
    return (
        "gate-1a-discovery-read-only-slice",
        "storage-discovery",
        "storage discovery pytest selector",
        "Gate 1a split trigger from capacity model",
        "pending",
    )


def required_tests(plan_text: str) -> list[tuple[str, str, str]]:
    bullets = markdown_bullets(section_body(plan_text, "Required Tests"))
    return [
        (f"RT-{index:03d}", "Required Tests", bullet)
        for index, bullet in enumerate(bullets, start=1)
    ]


def installed_host_rows(plan_text: str) -> list[tuple[str, str, str]]:
    table_rows = parse_markdown_table(
        subsection_body(plan_text, "Installed Host Repo Policy Matrix")
    )
    rows: list[tuple[str, str, str]] = []
    for index, row in enumerate(table_rows, start=1):
        rows.append(
            (
                f"IH-{index:03d}",
                "Installed Host Repo Policy Matrix",
                normalize_text(f"{row['Host shape']}: {row['Required behavior']}"),
            )
        )
    return rows


def compatibility_rows(plan_text: str) -> list[tuple[str, str, str]]:
    rows = parse_markdown_table(section_body(plan_text, "API And CLI Compatibility Ledger"))
    kept = {"preserved", "added", "wrapper-preserved", "deprecated with diagnostic"}
    output: list[tuple[str, str, str]] = []
    for row in rows:
        decision = row.get("Decision", "").strip("`")
        if decision in kept:
            index = len(output) + 1
            output.append(
                (
                    f"CL-{index:03d}",
                    "API And CLI Compatibility Ledger",
                    normalize_text(
                        f"{row['Surface']}: {decision}: {row['Required behavior']}"
                    ),
                )
            )
    return output


def hard_stop_rows(matrix_text: str) -> list[tuple[str, str, str]]:
    rows = parse_markdown_table(matrix_text)
    return [
        (row["stop_id"], "Hard Stop Closeout Matrix", normalize_text(row["stop_condition"]))
        for row in rows
    ]


def stale_text_rows() -> list[tuple[str, str, str]]:
    if not STORAGE_AUTHORITY_INVENTORY.exists():
        return [
            (
                "ST-BOOTSTRAP",
                "Generated Stale-Text Gate",
                "Create storage_authority_inventory.py, the storage authority inventory "
                "fixture, and a no-write --check contract in Gate 3; generated stale-text "
                "rows are not Gate 0r inputs.",
            )
        ]
    inventory = json.loads(STORAGE_AUTHORITY_INVENTORY.read_text(encoding="utf-8"))
    rows: list[tuple[str, str, str]] = []
    for index, row in enumerate(inventory.get("rows", []), start=1):
        text = normalize_text(
            f"{row['path']}: required={row.get('required', [])}; "
            f"forbidden={row.get('forbidden', [])}"
        )
        rows.append((f"ST-{index:03d}", "Generated Stale-Text Gate", text))
    if not rows:
        raise ToolError(
            "gate_proof_map check failed: storage authority inventory has no rows. Got: []"
        )
    return rows


def build_rows(plan_text: str, matrix_text: str) -> list[dict[str, str]]:
    sources = []
    sources.extend(required_tests(plan_text))
    sources.extend(hard_stop_rows(matrix_text))
    sources.extend(installed_host_rows(plan_text))
    sources.extend(compatibility_rows(plan_text))
    sources.extend(stale_text_rows())
    rows: list[dict[str, str]] = []
    for req_id, source, text in sources:
        gate, owner, proof, split, status = gate_for(text, req_id)
        rows.append(
            {
                "requirement_id": req_id,
                "source_reference": source,
                "requirement_sha256": sha256_text(text),
                "first_enforcing_gate": gate,
                "proof_owner": owner,
                "proof_command_or_artifact": proof,
                "split_trigger": split,
                "status": status,
            }
        )
    return rows


def render(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["first_enforcing_gate"] for row in rows)
    summary = "\n".join(f"- `{gate}`: {count} rows" for gate, count in sorted(counts.items()))
    return (
        "# Handoff Storage Gate Proof Map\n\n"
        "Generated from `docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md` "
        "and the checked hard-stop matrix.\n"
        "Normalize rule: collapse all whitespace in each source requirement before hashing.\n\n"
        "## Gate Row Counts\n\n"
        f"{summary}\n\n"
        "## Map\n\n"
        + markdown_table(HEADERS, rows)
        + "\n"
    )


def check_rows(plan_text: str, matrix_text: str, map_text: str) -> None:
    expected = build_rows(plan_text, matrix_text)
    actual_section = map_text.split("## Map", 1)[-1]
    actual = parse_markdown_table(actual_section)
    expected_by_id = {row["requirement_id"]: row for row in expected}
    actual_by_id = {row["requirement_id"]: row for row in actual}
    if set(expected_by_id) != set(actual_by_id):
        missing = sorted(set(expected_by_id) - set(actual_by_id))
        extra = sorted(set(actual_by_id) - set(expected_by_id))
        raise ToolError(
            f"gate_proof_map check failed: id drift. Got: missing={missing!r} "
            f"extra={extra!r}"
        )
    for req_id, expected_row in expected_by_id.items():
        actual_row = actual_by_id[req_id]
        if actual_row.get("requirement_sha256") != expected_row["requirement_sha256"]:
            raise ToolError(f"gate_proof_map check failed: requirement hash drift. Got: {req_id!r}")
        for column in HEADERS:
            if column not in actual_row:
                raise ToolError(f"gate_proof_map check failed: missing column. Got: {column!r}")
        if actual_row.get("first_enforcing_gate") not in BUDGETS:
            raise ToolError(
                "gate_proof_map check failed: unknown gate. "
                f"Got: {actual_row.get('first_enforcing_gate')!r}"
            )
        if not actual_row.get("proof_command_or_artifact"):
            raise ToolError(f"gate_proof_map check failed: missing proof. Got: {req_id!r}")
    counts = Counter(row["first_enforcing_gate"] for row in actual)
    for gate, count in counts.items():
        over_budget = count > BUDGETS[gate]
        if over_budget:
            rows = [row for row in actual if row["first_enforcing_gate"] == gate]
            if not all(row.get("split_trigger") for row in rows):
                raise ToolError(
                    "gate_proof_map check failed: over budget without split trigger. "
                    f"Got: {gate!r} count={count!r}"
                )
    hard_stop_hashes = {
        row["stop_id"]: row["stop_condition_sha256"]
        for row in parse_markdown_table(matrix_text)
    }
    for req_id, matrix_hash in hard_stop_hashes.items():
        actual_hash = actual_by_id.get(req_id, {}).get("requirement_sha256")
        if actual_hash != matrix_hash:
            raise ToolError(
                f"gate_proof_map check failed: hard-stop hash mismatch. Got: {req_id!r}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--hard-stop-matrix", required=True, type=Path)
    parser.add_argument("--map", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        plan_text = read_text(args.plan)
        matrix_text = read_text(args.hard_stop_matrix)
        if args.write:
            write_text_if_changed(args.map, render(build_rows(plan_text, matrix_text)))
        map_text = read_text(args.map)
        check_rows(plan_text, matrix_text, map_text)
    except ToolError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
