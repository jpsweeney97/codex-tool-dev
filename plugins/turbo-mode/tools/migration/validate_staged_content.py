from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

from migration_common import (
    MIGRATION_BASE_HEAD,
    committed_tool_sha256,
    fail,
    main_with_errors,
    read_sha256sums,
    should_ignore_generated,
    write_json,
)
from validate_redaction import validate_text

EXPECTED_MARKETPLACE = {
    "name": "turbo-mode",
    "interface": {"displayName": "Turbo Mode"},
    "plugins": [
        {
            "name": "handoff",
            "source": {"source": "local", "path": "./plugins/turbo-mode/handoff/1.6.0"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        },
        {
            "name": "ticket",
            "source": {"source": "local", "path": "./plugins/turbo-mode/ticket/1.4.0"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        },
    ],
}


def git_show(repo_root: str, spec: str) -> bytes:
    output = subprocess.run(["git", "show", spec], cwd=repo_root, capture_output=True, check=False)
    if output.returncode != 0:
        fail("read git object", output.stderr.decode("utf-8", errors="replace").strip(), spec)
    return output.stdout


def staged_names(repo_root: str) -> list[str]:
    output = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if output.returncode != 0:
        fail("list staged paths", output.stderr.strip(), repo_root)
    return [line for line in output.stdout.splitlines() if line]


def staged_manifest(repo_root: str, roots: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rel in staged_names(repo_root):
        if not any(rel.startswith(root.rstrip("/") + "/") for root in roots):
            continue
        rel_path = PurePosixPath(rel)
        if should_ignore_generated(rel_path):
            continue
        if "/evidence/" in rel or "/tools/migration/" in rel:
            continue
        result[rel] = hashlib.sha256(git_show(repo_root, f":{rel}")).hexdigest()
    return result


def validate_marketplace(repo_root: str, rel: str) -> None:
    actual = json.loads(git_show(repo_root, f":{rel}").decode("utf-8"))
    if actual != EXPECTED_MARKETPLACE:
        fail("validate marketplace", "marketplace contract mismatch", actual)


def validate_gitignore(repo_root: str, rel: str) -> None:
    text = git_show(repo_root, f":{rel}").decode("utf-8")
    for expected in (".codex/plugin-dev/", ".codex/plugins/"):
        if expected not in text.splitlines():
            fail("validate gitignore", "missing stale mirror ignore", expected)
    if ".codex/" in text.splitlines():
        fail("validate gitignore", "broad .codex ignore is not allowed", rel)


def validate_tool_hashes(repo_root: str, staged: list[str], tool_root: str) -> None:
    for rel in staged:
        if rel.startswith(tool_root.rstrip("/") + "/") and rel.endswith(".py"):
            current = hashlib.sha256(git_show(repo_root, f":{rel}")).hexdigest()
            phase0 = committed_tool_sha256(PathLike(repo_root), rel)
            if current != phase0:
                fail("validate tool hash", "staged tool differs from Phase 0 blob", rel)


class PathLike(str):
    """Small adapter so shared helpers can use subprocess cwd with a string path."""


def run_validation(args: argparse.Namespace) -> None:
    staged = staged_names(str(args.repo_root))
    allowed = [args.expected_staged_root.rstrip("/") + "/"] + args.expected_staged_file
    unexpected = [
        rel
        for rel in staged
        if not rel.startswith(args.expected_staged_root.rstrip("/") + "/")
        and rel not in args.expected_staged_file
    ]
    if unexpected:
        fail("validate staged paths", "unexpected staged paths", unexpected)
    stale_mirror_staged = any(
        rel.startswith(".codex/plugin-dev/") or rel.startswith(".codex/plugins/") for rel in staged
    )
    if stale_mirror_staged:
        fail("validate staged paths", "stale mirror paths are staged", staged)

    repo_root_path = Path(args.repo_root)
    source_manifest = read_sha256sums(repo_root_path / args.source_manifest)
    prefixed_expected = {
        rel: digest
        for rel, digest in source_manifest.items()
        if rel.startswith("plugins/turbo-mode/handoff/1.6.0/")
        or rel.startswith("plugins/turbo-mode/ticket/1.4.0/")
    }
    actual = staged_manifest(
        str(args.repo_root),
        ["plugins/turbo-mode/handoff/1.6.0", "plugins/turbo-mode/ticket/1.4.0"],
    )
    if actual and prefixed_expected and actual != prefixed_expected:
        fail(
            "validate staged source",
            "source manifest mismatch",
            {"expected": prefixed_expected, "actual": actual},
        )

    validate_marketplace(str(args.repo_root), args.marketplace)
    if ".gitignore" in args.expected_staged_file:
        validate_gitignore(str(args.repo_root), ".gitignore")

    redaction_failures = {}
    for rel in staged:
        text = git_show(str(args.repo_root), f":{rel}").decode("utf-8", errors="replace")
        issues = validate_text(rel, text)
        if issues:
            redaction_failures[rel] = issues
    if redaction_failures:
        fail("validate staged redaction", "redaction failures", redaction_failures)

    if args.local_only_output:
        write_json(
            args.local_only_output,
            {
                "run_id": args.run_id,
                "migration_base_head": MIGRATION_BASE_HEAD,
                "staged_path_count": len(staged),
                "staged_paths": staged,
                "allowed_prefixes_or_files": allowed,
            },
        )
    print("staged index content gate passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate staged migration content.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", required=True, type=PathLike)
    parser.add_argument("--source", choices=["index"], default="index")
    parser.add_argument("--expected-staged-root", required=True)
    parser.add_argument("--expected-staged-file", action="append", default=[])
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--local-only-output", type=Path)
    run_validation(parser.parse_args())


if __name__ == "__main__":
    main_with_errors(main)
