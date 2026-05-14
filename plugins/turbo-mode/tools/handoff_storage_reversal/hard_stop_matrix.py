#!/usr/bin/env python3
"""Generate and check the Handoff storage reversal hard-stop matrix."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from _common import (
    ToolError,
    markdown_bullets,
    markdown_table,
    normalize_text,
    parse_markdown_table,
    read_text,
    section_body,
    sha256_text,
    write_text_if_changed,
)


HEADERS = [
    "stop_id",
    "stop_condition",
    "stop_condition_sha256",
    "authority_owner",
    "enforcing_gate",
    "proof_type",
    "proof_command_or_artifact",
    "closeout_status",
]


def classify_stop(text: str) -> tuple[str, str, str, str]:
    lower = text.lower()
    if any(term in lower for term in ("installed-host", "installed host", "installed-cache", "source checkout")):
        return ("installed-host", "gate-5-installed-certification", "smoke", "installed-host behavior proof or source-harness isolation evidence")
    if any(term in lower for term in ("skill docs", "/summary", "launcher class")):
        return ("skill-docs", "gate-2-skill-docs-release-docs", "static-scan", "skill-doc tests and storage authority inventory")
    if any(term in lower for term in ("refresh", "storage_authority_inventory", "gate_proof_map")):
        return ("refresh", "gate-3-refresh-and-stale-text", "static-scan", "generated stale-text or proof-map check")
    if any(term in lower for term in ("preflight", "ledger", "gate 0r", "hard-stop", "legacy-active")):
        return ("plan", "gate-0r-review-reanchor-and-preflight-refresh", "ledger-check", "Gate 0r control-map and preflight checks")
    if any(term in lower for term in ("closeout", "proof label", "claim")):
        return ("closeout", "gate-4-source-closeout", "manual-review", "closeout evidence packet")
    return ("source", "gate-1a-through-gate-1g-runtime-slices", "unit-test", "focused source test selector")


def build_rows(plan_text: str) -> list[dict[str, str]]:
    bullets = markdown_bullets(section_body(plan_text, "Hard Stop Conditions"))
    rows: list[dict[str, str]] = []
    for index, bullet in enumerate(bullets, start=1):
        owner, gate, proof_type, proof = classify_stop(bullet)
        rows.append(
            {
                "stop_id": f"HS-{index:03d}",
                "stop_condition": normalize_text(bullet),
                "stop_condition_sha256": sha256_text(bullet),
                "authority_owner": owner,
                "enforcing_gate": gate,
                "proof_type": proof_type,
                "proof_command_or_artifact": proof,
                "closeout_status": "pending",
            }
        )
    return rows


def render(rows: list[dict[str, str]]) -> str:
    return (
        "# Handoff Storage Hard Stop Closeout Matrix\n\n"
        "Generated from `docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md`.\n"
        "Normalize rule: collapse all whitespace in each hard-stop bullet before hashing.\n\n"
        + markdown_table(HEADERS, rows)
        + "\n"
    )


def check_matrix(plan_text: str, matrix_text: str) -> None:
    expected = build_rows(plan_text)
    actual = parse_markdown_table(matrix_text)
    expected_by_id = {row["stop_id"]: row for row in expected}
    actual_by_id = {row["stop_id"]: row for row in actual}
    if set(expected_by_id) != set(actual_by_id):
        missing = sorted(set(expected_by_id) - set(actual_by_id))
        extra = sorted(set(actual_by_id) - set(expected_by_id))
        raise ToolError(f"hard_stop_matrix check failed: id drift. Got: missing={missing!r} extra={extra!r}")
    for stop_id, expected_row in expected_by_id.items():
        actual_row = actual_by_id[stop_id]
        for column in ("stop_condition", "stop_condition_sha256"):
            if actual_row.get(column) != expected_row[column]:
                raise ToolError(f"hard_stop_matrix check failed: {column} drift. Got: {stop_id!r}")
        for column in HEADERS:
            if column not in actual_row:
                raise ToolError(f"hard_stop_matrix check failed: missing column. Got: {column!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--matrix", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        plan_text = read_text(args.plan)
        if args.write:
            write_text_if_changed(args.matrix, render(build_rows(plan_text)))
        matrix_text = read_text(args.matrix)
        check_matrix(plan_text, matrix_text)
    except ToolError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
