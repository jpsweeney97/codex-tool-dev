from __future__ import annotations

import argparse
import hashlib
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
POST_COMMIT_CLOSEOUT = "post-commit-closeout.summary.json"


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


def git_tree(repo_root: Path, rev: str) -> str:
    output = subprocess.run(
        ["git", "rev-parse", f"{rev}^{{tree}}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if output.returncode != 0:
        fail("read git tree", output.stderr.strip(), rev)
    return output.stdout.strip()


def closeout_rel(args: argparse.Namespace) -> str:
    return (args.evidence_root / POST_COMMIT_CLOSEOUT).as_posix()


def load_post_commit_context(
    args: argparse.Namespace,
    files: list[str],
) -> dict[str, Any] | None:
    rel = closeout_rel(args)
    if rel not in files:
        return None
    parsed = read_json_bytes(read_source_bytes(args.repo_root, rel, args.source), source=rel)
    source_migration_commit = parsed.get("source_migration_commit")
    source_migration_tree = parsed.get("source_migration_tree")
    if not isinstance(source_migration_commit, str) or not source_migration_commit:
        fail("validate metadata", "post-commit closeout lacks source_migration_commit", rel)
    if not isinstance(source_migration_tree, str) or not source_migration_tree:
        fail("validate metadata", "post-commit closeout lacks source_migration_tree", rel)
    actual_tree = git_tree(args.repo_root, source_migration_commit)
    if actual_tree != source_migration_tree:
        fail(
            "validate metadata",
            "source migration tree mismatch",
            {"expected": actual_tree, "actual": source_migration_tree},
        )

    evidence_head = getattr(args, "accepted_evidence_head", None) or parsed.get(
        "evidence_generation_commit"
    )
    if not isinstance(evidence_head, str) or not evidence_head:
        evidence_head = parsed.get("phase0_tooling_commit")
    if not isinstance(evidence_head, str) or not evidence_head:
        fail("validate metadata", "post-commit closeout lacks evidence-generation head", rel)

    closeout_head = getattr(args, "closeout_repo_head", None) or parsed.get(
        "closeout_tooling_commit"
    )
    if not isinstance(closeout_head, str) or not closeout_head:
        closeout_head = repo_head(args.repo_root)
    return {
        "closeout_rel": rel,
        "evidence_head": evidence_head,
        "closeout_head": closeout_head,
    }


def expected_repo_head(
    *,
    args: argparse.Namespace,
    rel: str,
    post_commit_context: dict[str, Any] | None,
) -> str:
    if post_commit_context is None:
        return getattr(args, "accepted_evidence_head", None) or repo_head(args.repo_root)
    if rel == post_commit_context["closeout_rel"]:
        return post_commit_context["closeout_head"]
    return post_commit_context["evidence_head"]


def validate_metadata(
    metadata: dict[str, Any],
    *,
    args: argparse.Namespace,
    rel: str,
    post_commit_context: dict[str, Any] | None,
) -> None:
    missing = sorted(REQUIRED_FIELDS - set(metadata))
    if missing:
        fail("validate metadata", "missing required fields", {"file": rel, "missing": missing})
    expected = {
        "run_id": args.run_id,
        "plan_path": str(args.plan),
        "plan_sha256": plan_sha256(args.plan),
        "repo_root": str(args.repo_root),
        "repo_head": expected_repo_head(
            args=args,
            rel=rel,
            post_commit_context=post_commit_context,
        ),
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
        expected_tool_sha = committed_tool_sha256_at(
            args.repo_root,
            metadata["repo_head"],
            tool_path,
        )
        if metadata["tool_sha256"] != expected_tool_sha:
            fail(
                "validate metadata",
                "tool sha256 does not match committed blob",
                {"file": rel, "tool_path": tool_path},
            )


def committed_tool_sha256_at(repo_root: Path, rev: str, tool_path: str) -> str:
    output = subprocess.run(
        ["git", "show", f"{rev}:{tool_path}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if output.returncode != 0:
        fail(
            "read committed tool",
            output.stderr.decode("utf-8", errors="replace").strip(),
            tool_path,
        )
    return hashlib.sha256(output.stdout).hexdigest()


def run_validation(args: argparse.Namespace) -> None:
    files = evidence_files(args.repo_root, args.evidence_root, args.source) if args.scan_all else []
    for required in args.require:
        rel = (args.evidence_root / required).as_posix()
        if rel not in files:
            files.append(rel)
    files = sorted(set(files))
    sidecars = {path for path in files if path.endswith(".metadata.json")}
    post_commit_context = load_post_commit_context(args, files)
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
        validate_metadata(metadata, args=args, rel=rel, post_commit_context=post_commit_context)
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
    parser.add_argument("--accepted-evidence-head")
    parser.add_argument("--closeout-repo-head")
    run_validation(parser.parse_args())


if __name__ == "__main__":
    main_with_errors(main)
