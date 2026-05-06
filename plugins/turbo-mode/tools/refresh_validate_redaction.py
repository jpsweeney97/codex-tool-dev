#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.commit_safe import sha256_file, sha256_payload  # noqa: E402
from refresh.validation import (  # noqa: E402
    BROAD_ABSOLUTE_PATH_PATTERN,
    CONFIG_OR_TRANSCRIPT_PATTERNS,
    SENSITIVE_PATTERNS,
    assert_commit_safe_payload,
    assert_no_sensitive_values,
    load_json_object,
    projected_summary_for_validator_digest,
)

SCHEMA_VERSION = "turbo-mode-refresh-redaction-validation-plan-04"
FINAL_SCAN_SCHEMA_VERSION = "turbo-mode-refresh-redaction-final-scan-plan-04"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Turbo Mode refresh redaction.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("candidate", "final"), required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--local-only-root", type=Path, required=True)
    parser.add_argument("--published-summary-path", type=Path, required=True)
    parser.add_argument("--candidate-summary", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--existing-validation-summary", type=Path)
    parser.add_argument("--final-scan-output", type=Path)
    parser.add_argument("--validate-own-summary", action="store_true")
    return parser


def validate_candidate(args: argparse.Namespace) -> int:
    payload = load_json_object(args.summary)
    assert_commit_safe_payload(payload)
    sensitivity = scan_local_only_artifacts(
        args.local_only_root,
        phase="candidate",
        mode=str(payload["mode"]),
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "scope": args.scope,
        "source": args.source,
        "status": "passed",
        "validated_summary_path": str(args.summary),
        "published_summary_path": str(args.published_summary_path),
        "candidate_summary_sha256": sha256_file(args.summary),
        "validated_payload_projection_sha256": sha256_payload(
            projected_summary_for_validator_digest(payload)
        ),
        "local_only_sensitivity_scan": sensitivity,
    }
    if args.summary_output is None:
        raise ValueError(
            "validate redaction failed: summary output is required in candidate mode. Got: None"
        )
    if args.validate_own_summary:
        assert_no_sensitive_values(summary)
    write_summary(args.summary_output, summary)
    return 0


def validate_final(args: argparse.Namespace) -> int:
    payload = load_json_object(args.summary)
    assert_commit_safe_payload(payload)
    if args.existing_validation_summary is None:
        raise ValueError(
            "validate redaction failed: existing validation summary is required "
            "in final mode. Got: None"
        )
    if args.candidate_summary is None:
        raise ValueError(
            "validate redaction failed: candidate summary is required in final mode. Got: None"
        )
    existing = load_json_object(args.existing_validation_summary)
    expected_fields = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "status": "passed",
        "validated_summary_path": str(args.candidate_summary),
        "published_summary_path": str(args.published_summary_path),
    }
    for key, expected in expected_fields.items():
        if existing.get(key) != expected:
            raise ValueError(
                "validate redaction failed: validator summary field mismatch. "
                f"Got: {key!r:.100}"
            )
    projected_digest = sha256_payload(projected_summary_for_validator_digest(payload))
    if existing.get("validated_payload_projection_sha256") != projected_digest:
        raise ValueError(
            "validate redaction failed: projected summary digest mismatch. "
            "Got: validated_payload_projection_sha256"
        )
    if existing.get("candidate_summary_sha256") != sha256_file(args.candidate_summary):
        raise ValueError(
            "validate redaction failed: candidate summary digest mismatch. "
            "Got: candidate_summary_sha256"
        )
    if payload.get("redaction_validation_summary_sha256") != sha256_file(
        args.existing_validation_summary
    ):
        raise ValueError(
            "validate redaction failed: redaction validator digest mismatch. "
            "Got: redaction_validation_summary_sha256"
        )
    if existing.get("local_only_sensitivity_scan", {}).get("status") != "completed":
        raise ValueError(
            "validate redaction failed: local-only sensitivity scan missing. "
            "Got: local_only_sensitivity_scan"
        )
    if args.final_scan_output is None:
        raise ValueError(
            "validate redaction failed: final scan output is required in final mode. Got: None"
        )
    sensitivity = scan_local_only_artifacts(
        args.local_only_root,
        phase="final",
        mode=str(payload["mode"]),
    )
    final_scan = {
        "schema_version": FINAL_SCAN_SCHEMA_VERSION,
        "run_id": args.run_id,
        "validator_mode": "final-scan",
        "status": "passed",
        "validated_summary_path": str(args.summary),
        "published_summary_path": str(args.published_summary_path),
        "validated_payload_projection_sha256": projected_digest,
        "local_only_sensitivity_scan": sensitivity,
    }
    assert_no_sensitive_values(final_scan)
    write_summary(args.final_scan_output, final_scan)
    return 0


def scan_local_only_artifacts(root: Path, *, phase: str, mode: str) -> dict[str, object]:
    if not root.is_dir():
        raise ValueError(
            "scan local-only artifacts failed: run directory is not a directory. "
            f"Got: {str(root)!r:.100}"
        )
    artifact_names = expected_local_only_artifacts(root, phase=phase, mode=mode)
    findings: list[dict[str, object]] = []
    for name in artifact_names:
        path = root / name
        if not path.is_file():
            raise ValueError(
                "scan local-only artifacts failed: expected artifact missing. "
                f"Got: {name!r:.100}"
            )
        text = path.read_text(encoding="utf-8", errors="replace")
        finding = scan_text(path.name, text)
        if finding is not None:
            findings.append(finding)
    return {
        "status": "completed",
        "phase": phase,
        "artifact_count": len(artifact_names),
        "expected_artifacts": artifact_names,
        "finding_count": sum(int(item["match_count"]) for item in findings),
        "affected_artifacts": [str(item["artifact"]) for item in findings],
        "findings": findings,
    }


def scan_text(artifact_name: str, text: str) -> dict[str, object] | None:
    examples: list[str] = []
    count = 0
    classes: set[str] = set()
    pattern_groups = (
        ("secret-like", SENSITIVE_PATTERNS),
        ("config-shaped", CONFIG_OR_TRANSCRIPT_PATTERNS),
        ("broad-absolute-path", (BROAD_ABSOLUTE_PATH_PATTERN,)),
    )
    for label, patterns in pattern_groups:
        for pattern in patterns:
            for match in pattern.finditer(text):
                count += 1
                classes.add(label)
                if len(examples) < 3:
                    examples.append(pattern.sub("[REDACTED]", match.group(0)))
    if not count:
        return None
    return {
        "artifact": artifact_name,
        "match_count": count,
        "classes": sorted(classes),
        "redacted_examples": examples,
    }


def expected_local_only_artifacts(root: Path, *, phase: str, mode: str) -> list[str]:
    base = [
        f"{mode}.summary.json",
        "commit-safe.candidate.summary.json",
        "metadata-validation.summary.json",
    ]
    local_summary = load_json_object(root / f"{mode}.summary.json")
    if _local_summary_requires_transcript(local_summary):
        base.append("app-server-readonly-inventory.transcript.json")
    if phase == "candidate":
        return base
    if phase == "final":
        return [*base, "commit-safe.final.summary.json", "redaction.summary.json"]
    raise ValueError(f"scan local-only artifacts failed: invalid phase. Got: {phase!r:.100}")


def _local_summary_requires_transcript(local_summary: dict[str, object]) -> bool:
    return local_summary.get("app_server_inventory_status") in {"collected", "requested-failed"}


def write_summary(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ValueError(
            "write validation summary failed: parent directory does not exist. "
            f"Got: {str(path.parent)!r:.100}"
        )
    parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
    if parent_mode != 0o700:
        raise PermissionError(
            "write validation summary failed: parent directory must be 0700. "
            f"Got: {oct(parent_mode)!r:.100}"
        )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "candidate":
            return validate_candidate(args)
        return validate_final(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
