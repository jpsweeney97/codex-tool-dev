from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from migration_common import (
    CACHE_ROOTS,
    CONFIG_PATH,
    MARKETPLACE_PATH,
    MIGRATION_BASE_HEAD,
    MIGRATION_BASE_KIND,
    MIGRATION_BASE_REF,
    SOURCE_ROOTS,
    committed_tool_sha256,
    fail,
    main_with_errors,
    plan_sha256,
    read_json_bytes,
    repo_head,
)

REQUIRED_FIELDS = {
    "run_id",
    "generated_at_utc",
    "plan_path",
    "plan_sha256",
    "repo_root",
    "repo_head",
    "migration_base_head",
    "migration_base_ref",
    "migration_base_kind",
    "tool_path",
    "tool_sha256",
    "mode",
    "source_roots",
    "cache_roots",
    "config_path",
    "marketplace_path",
}


def git_index_files(repo_root: Path, prefix: str) -> list[str]:
    output = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", prefix],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if output.returncode != 0:
        fail("list staged files", output.stderr.strip(), prefix)
    return [line for line in output.stdout.splitlines() if line]


def read_source_bytes(repo_root: Path, rel: str, source: str) -> bytes:
    if source == "worktree":
        return (repo_root / rel).read_bytes()
    output = subprocess.run(
        ["git", "show", f":{rel}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if output.returncode != 0:
        fail("read staged evidence", output.stderr.decode("utf-8", errors="replace").strip(), rel)
    return output.stdout


def evidence_files(repo_root: Path, evidence_root: Path, source: str) -> list[str]:
    root_rel = evidence_root.as_posix()
    if source == "worktree":
        root = repo_root / evidence_root
        return [
            path.relative_to(repo_root).as_posix()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]
    return sorted(git_index_files(repo_root, root_rel))


def metadata_for(repo_root: Path, rel: str, source: str) -> tuple[dict[str, Any], str]:
    data = read_source_bytes(repo_root, rel, source)
    if rel.endswith(".json"):
        parsed = read_json_bytes(data, source=rel)
        if "run_metadata" in parsed:
            return parsed["run_metadata"], rel
    sidecar = rel + ".metadata.json"
    parsed = read_json_bytes(read_source_bytes(repo_root, sidecar, source), source=sidecar)
    if "run_metadata" not in parsed:
        fail("validate metadata", "sidecar lacks run_metadata", sidecar)
    return parsed["run_metadata"], sidecar


def validate_metadata(metadata: dict[str, Any], *, args: argparse.Namespace, rel: str) -> None:
    missing = sorted(REQUIRED_FIELDS - set(metadata))
    if missing:
        fail("validate metadata", "missing required fields", {"file": rel, "missing": missing})
    expected = {
        "run_id": args.run_id,
        "plan_path": str(args.plan),
        "plan_sha256": plan_sha256(args.plan),
        "repo_root": str(args.repo_root),
        "repo_head": repo_head(args.repo_root),
        "migration_base_head": MIGRATION_BASE_HEAD,
        "migration_base_ref": MIGRATION_BASE_REF,
        "migration_base_kind": MIGRATION_BASE_KIND,
        "source_roots": [str(path) for path in SOURCE_ROOTS],
        "cache_roots": [str(path) for path in CACHE_ROOTS],
        "config_path": str(CONFIG_PATH),
        "marketplace_path": str(MARKETPLACE_PATH),
    }
    mismatches = {
        key: {"expected": value, "actual": metadata.get(key)}
        for key, value in expected.items()
        if metadata.get(key) != value
    }
    if mismatches:
        fail("validate metadata", "metadata mismatch", {"file": rel, "mismatches": mismatches})
    tool_path = metadata["tool_path"]
    if isinstance(tool_path, str) and not tool_path.startswith("manual-shell:"):
        expected_tool_sha = committed_tool_sha256(args.repo_root, tool_path)
        if metadata["tool_sha256"] != expected_tool_sha:
            fail(
                "validate metadata",
                "tool sha256 does not match committed blob",
                {"file": rel, "tool_path": tool_path},
            )


def run_validation(args: argparse.Namespace) -> None:
    files = evidence_files(args.repo_root, args.evidence_root, args.source) if args.scan_all else []
    for required in args.require:
        rel = (args.evidence_root / required).as_posix()
        if rel not in files:
            files.append(rel)
    files = sorted(set(files))
    sidecars = {path for path in files if path.endswith(".metadata.json")}
    validated: set[str] = set()
    for rel in files:
        if rel.endswith("README.md"):
            continue
        if rel.endswith(".metadata.json"):
            target = rel.removesuffix(".metadata.json")
            if target not in files and args.scan_all:
                fail("validate metadata", "unpaired metadata sidecar", rel)
            continue
        metadata, metadata_rel = metadata_for(args.repo_root, rel, args.source)
        validate_metadata(metadata, args=args, rel=rel)
        validated.add(rel)
        if metadata_rel != rel:
            sidecars.discard(metadata_rel)
    unpaired = sorted(sidecars - {rel + ".metadata.json" for rel in validated})
    if unpaired and args.scan_all:
        fail("validate metadata", "unpaired sidecars", unpaired)
    print(f"current-run metadata gate passed ({len(validated)} artifacts scanned)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate current-run evidence metadata.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--source", choices=["worktree", "index"], default="worktree")
    parser.add_argument("--scan-all", action="store_true")
    parser.add_argument("--require", action="append", default=[])
    run_validation(parser.parse_args())


if __name__ == "__main__":
    main_with_errors(main)
