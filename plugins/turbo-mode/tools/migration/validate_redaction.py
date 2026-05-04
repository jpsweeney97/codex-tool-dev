from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from migration_common import base_run_metadata, fail, main_with_errors, write_json

TOOL_PATH = "plugins/turbo-mode/tools/migration/validate_redaction.py"

SECRET_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
]
FORBIDDEN_SNIPPETS = [
    "raw app-server transcript",
    '"jsonrpc"',
    "ps -axo pid,command",
    "[profiles.",
    "[model_providers.",
]
ALLOWED_LOCAL_PATHS = [
    "/Users/jp/Projects/active/codex-tool-dev",
    "/Users/jp/.codex/local-only/turbo-mode-source-migration",
    "/Users/jp/.codex/docs/plans",
    "/Users/jp/.codex/plugins/cache/turbo-mode",
    "/Users/jp/.codex/config.toml",
    "/Users/jp/.codex/dist",
    "/private/tmp/turbo-mode",
]
FORBIDDEN_LOCAL_PATHS = [
    "/Users/jp/.codex/plugins/plugin-dev",
    "/Users/jp/.agents/plugins/marketplace.json",
]
FORBIDDEN_FILENAMES = [
    "config.before.toml",
    "config.after.toml",
    "app-server-transcript",
    "process-list",
    "ps-axo",
]


def staged_files(repo_root: Path, includes: list[str]) -> list[str]:
    files: list[str] = []
    for include in includes:
        output = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--", include],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if output.returncode != 0:
            fail("list staged files", output.stderr.strip(), include)
        files.extend(output.stdout.splitlines())
    return sorted(set(files))


def worktree_files(repo_root: Path, includes: list[str]) -> list[Path]:
    result: list[Path] = []
    for include in includes:
        path = repo_root / include
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(sorted(child for child in path.rglob("*") if child.is_file()))
    return sorted(set(result))


def read_staged(repo_root: Path, rel: str) -> str:
    output = subprocess.run(
        ["git", "show", f":{rel}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if output.returncode != 0:
        fail("read staged file", output.stderr.decode("utf-8", errors="replace").strip(), rel)
    return output.stdout.decode("utf-8", errors="replace")


def validate_text(rel: str, text: str) -> list[str]:
    issues: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append(f"secret-like token matched {pattern.pattern}")
    for snippet in FORBIDDEN_SNIPPETS:
        if snippet in text:
            issues.append(f"forbidden raw snippet {snippet!r}")
    for path in FORBIDDEN_LOCAL_PATHS:
        if path in text:
            issues.append(f"forbidden local path {path}")
    for raw_path in re.findall(r"/Users/jp/[^\s\"'<>),]+", text):
        if not any(raw_path.startswith(allowed) for allowed in ALLOWED_LOCAL_PATHS):
            issues.append(f"unapproved local path {raw_path}")
    if any(name in Path(rel).name for name in FORBIDDEN_FILENAMES):
        issues.append("forbidden raw/local-only filename")
    return issues


def run_validation(args: argparse.Namespace) -> None:
    if args.source == "worktree":
        files = worktree_files(args.repo_root, args.include)
        text_items = [
            (
                path.relative_to(args.repo_root).as_posix(),
                path.read_text(encoding="utf-8", errors="replace"),
            )
            for path in files
        ]
    else:
        rels = staged_files(args.repo_root, args.include)
        text_items = [(rel, read_staged(args.repo_root, rel)) for rel in rels]

    rejected: dict[str, list[str]] = {}
    for rel, text in text_items:
        issues = validate_text(rel, text)
        if issues:
            rejected[rel] = issues
    summary = {
        "run_metadata": base_run_metadata(
            run_id=args.run_id,
            mode=f"redaction-{args.scope}-{args.source}",
            tool_path=TOOL_PATH,
            repo_root=args.repo_root,
            plan_path=args.plan,
        ),
        "scope": args.scope,
        "source": args.source,
        "scanned_file_count": len(text_items),
        "rejected_file_count": len(rejected),
        "allowed_local_path_exceptions": ALLOWED_LOCAL_PATHS,
        "rejections": rejected,
    }
    if args.summary_output:
        write_json(args.summary_output, summary)
        if args.validate_own_summary:
            own_issues = validate_text(
                args.summary_output.relative_to(args.repo_root).as_posix()
                if args.summary_output.is_relative_to(args.repo_root)
                else str(args.summary_output),
                args.summary_output.read_text(encoding="utf-8"),
            )
            if own_issues:
                fail("validate redaction summary", "summary fails redaction rules", own_issues)
    if rejected:
        fail("validate redaction", "redaction violations present", rejected)
    print(f"{args.scope.replace('-', ' ')} redaction gate passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate commit-safe redaction boundaries.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--source", choices=["worktree", "index"], default="worktree")
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--evidence-root")
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--validate-own-summary", action="store_true")
    args = parser.parse_args()
    if args.evidence_root and not args.include:
        args.include = [args.evidence_root]
    run_validation(args)


if __name__ == "__main__":
    main_with_errors(main)
