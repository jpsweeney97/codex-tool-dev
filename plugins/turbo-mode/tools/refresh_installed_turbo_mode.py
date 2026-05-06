#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.commit_safe import (  # noqa: E402
    build_commit_safe_summary,
    ensure_relevant_worktree_clean,
    sha256_file,
)
from refresh.evidence import evidence_payload, write_local_evidence  # noqa: E402
from refresh.models import RefreshError  # noqa: E402
from refresh.planner import plan_refresh  # noqa: E402
from refresh.validation import assert_commit_safe_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess Turbo Mode installed-cache drift without mutation."
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--plan-refresh", action="store_true")
    modes.add_argument("--refresh", action="store_true")
    modes.add_argument("--guarded-refresh", action="store_true")
    parser.add_argument("--smoke", choices=("light", "standard"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--run-id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--inventory-check", action="store_true")
    parser.add_argument("--record-summary", action="store_true")
    parser.add_argument("--require-terminal-status")
    parser.add_argument("--summary-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh or args.guarded_refresh:
        parser.error("--refresh and --guarded-refresh are outside non-mutating refresh planning")
    if args.smoke is not None:
        parser.error("--smoke is only accepted with rejected future command shapes")
    mode = "plan-refresh" if args.plan_refresh else "dry-run"
    run_id = args.run_id or uuid.uuid4().hex
    try:
        dirty_state = (
            ensure_relevant_worktree_clean(args.repo_root) if args.record_summary else None
        )
        result = plan_refresh(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            mode=mode,
            inventory_check=args.inventory_check,
        )
        if args.require_terminal_status is not None:
            terminal_status = result.terminal_status.value
            if terminal_status != args.require_terminal_status:
                raise RefreshError(
                    "required terminal status mismatch: "
                    f"expected {args.require_terminal_status!r}, got {terminal_status!r}"
                )
        evidence_path = write_local_evidence(result, run_id=run_id)
        published_summary_path = None
        candidate_summary_path = None
        final_summary_path = None
        if args.record_summary:
            assert dirty_state is not None
            published_summary_path = resolve_commit_safe_summary_output(
                repo_root=args.repo_root,
                run_id=run_id,
                requested=args.summary_output,
            )
            run_root = result.paths.local_only_root / run_id
            candidate_summary_path = run_root / "commit-safe.candidate.summary.json"
            final_summary_path = run_root / "commit-safe.final.summary.json"
            metadata_summary_path = run_root / "metadata-validation.summary.json"
            redaction_summary_path = run_root / "redaction.summary.json"
            redaction_final_scan_path = run_root / "redaction-final-scan.summary.json"
            candidate_payload = build_commit_safe_summary(
                result,
                run_id=run_id,
                local_summary_path=evidence_path,
                repo_head=git_rev_parse(args.repo_root, "HEAD"),
                repo_tree=git_rev_parse(args.repo_root, "HEAD^{tree}"),
                tool_path=Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"),
                tool_sha256=sha256_file(CURRENT_FILE),
                dirty_state=dirty_state,
                metadata_validation_summary_sha256=None,
                redaction_validation_summary_sha256=None,
            )
            assert_commit_safe_payload(candidate_payload)
            write_json_0600_exclusive(candidate_summary_path, candidate_payload)
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_run_metadata.py"),
                    "--mode",
                    "candidate",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--local-only-root",
                    str(run_root),
                    "--summary",
                    str(candidate_summary_path),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--summary-output",
                    str(metadata_summary_path),
                ]
            )
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_redaction.py"),
                    "--mode",
                    "candidate",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--scope",
                    "commit-safe-summary",
                    "--source",
                    "plan-05-cli",
                    "--summary",
                    str(candidate_summary_path),
                    "--local-only-root",
                    str(run_root),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--summary-output",
                    str(redaction_summary_path),
                    "--validate-own-summary",
                ]
            )
            final_payload = build_commit_safe_summary(
                result,
                run_id=run_id,
                local_summary_path=evidence_path,
                repo_head=git_rev_parse(args.repo_root, "HEAD"),
                repo_tree=git_rev_parse(args.repo_root, "HEAD^{tree}"),
                tool_path=Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"),
                tool_sha256=sha256_file(CURRENT_FILE),
                dirty_state=dirty_state,
                metadata_validation_summary_sha256=sha256_file(metadata_summary_path),
                redaction_validation_summary_sha256=sha256_file(redaction_summary_path),
            )
            assert_commit_safe_payload(final_payload)
            write_json_0600_exclusive(final_summary_path, final_payload)
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_run_metadata.py"),
                    "--mode",
                    "final",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--local-only-root",
                    str(run_root),
                    "--summary",
                    str(final_summary_path),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--candidate-summary",
                    str(candidate_summary_path),
                    "--existing-validation-summary",
                    str(metadata_summary_path),
                ]
            )
            run_validator(
                [
                    sys.executable,
                    str(REFRESH_PARENT / "refresh_validate_redaction.py"),
                    "--mode",
                    "final",
                    "--run-id",
                    run_id,
                    "--repo-root",
                    str(args.repo_root),
                    "--scope",
                    "commit-safe-summary",
                    "--source",
                    "plan-05-cli",
                    "--summary",
                    str(final_summary_path),
                    "--local-only-root",
                    str(run_root),
                    "--published-summary-path",
                    str(published_summary_path),
                    "--candidate-summary",
                    str(candidate_summary_path),
                    "--existing-validation-summary",
                    str(redaction_summary_path),
                    "--final-scan-output",
                    str(redaction_final_scan_path),
                ]
            )
            publish_json_0600_exclusive(final_summary_path, published_summary_path)
    except (RefreshError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = evidence_payload(result, run_id=run_id)
    payload["evidence_path"] = str(evidence_path)
    if candidate_summary_path is not None:
        payload["commit_safe_candidate_summary_path"] = str(candidate_summary_path)
    if final_summary_path is not None:
        payload["commit_safe_final_summary_path"] = str(final_summary_path)
    if published_summary_path is not None:
        payload["published_summary_path"] = str(published_summary_path)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode: {mode}")
        print(f"terminal_plan_status: {result.terminal_status.value}")
        print(f"evidence_path: {evidence_path}")
        if candidate_summary_path is not None:
            print(f"commit_safe_candidate_summary_path: {candidate_summary_path}")
        if final_summary_path is not None:
            print(f"commit_safe_final_summary_path: {final_summary_path}")
        if published_summary_path is not None:
            print(f"published_summary_path: {published_summary_path}")
        print(f"app_server_inventory_status: {result.app_server_inventory_status}")
        if result.app_server_inventory_failure_reason is not None:
            print(
                "app_server_inventory_failure_reason: "
                f"{result.app_server_inventory_failure_reason}"
            )
        if result.app_server_inventory is not None:
            print(f"app_server_inventory: {result.app_server_inventory.state}")
        print(f"mutation_command_available: {str(result.mutation_command_available).lower()}")
        if result.future_external_command is not None:
            print(f"future_external_command: {result.future_external_command}")
            print(f"requires_plan: {result.requires_plan}")
    return 0


def git_rev_parse(repo_root: Path, revision: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", revision],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def resolve_commit_safe_summary_output(
    *,
    repo_root: Path,
    run_id: str,
    requested: Path | None,
) -> Path:
    evidence_root = (repo_root / "plugins/turbo-mode/evidence/refresh").resolve(strict=False)
    requested_path = requested or evidence_root / f"{run_id}.summary.json"
    if not requested_path.is_absolute():
        requested_path = repo_root / requested_path
    final_path = requested_path.resolve(strict=False)
    if evidence_root != final_path.parent and evidence_root not in final_path.parents:
        raise ValueError(
            "resolve summary output failed: path must stay under evidence root. "
            f"Got: {str(requested_path)!r:.100}"
        )
    if final_path.name.endswith(".summary.json") is False:
        raise ValueError(
            "resolve summary output failed: file name must end with .summary.json. "
            f"Got: {final_path.name!r:.100}"
        )
    _reject_symlink_parents(final_path, stop_at=repo_root.resolve(strict=False).parent)
    try:
        existing_stat = final_path.lstat()
    except FileNotFoundError:
        return final_path
    if stat.S_ISDIR(existing_stat.st_mode):
        raise IsADirectoryError(
            "resolve summary output failed: output path is a directory. "
            f"Got: {str(final_path)!r:.100}"
        )
    raise FileExistsError(
        "resolve summary output failed: output path already exists. "
        f"Got: {str(final_path)!r:.100}"
    )


def _reject_symlink_parents(path: Path, *, stop_at: Path) -> None:
    current = path.parent
    parents = []
    while current != stop_at and current != current.parent:
        parents.append(current)
        current = current.parent
    for parent in reversed(parents):
        try:
            parent_stat = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(parent_stat.st_mode):
            raise ValueError(
                "validate summary output failed: symlink parent is not allowed. "
                f"Got: {str(parent)!r:.100}"
            )


def write_json_0600_exclusive(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ValueError(
            "write JSON failed: parent directory does not exist. "
            f"Got: {str(path.parent)!r:.100}"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def publish_json_0600_exclusive(source_payload_path: Path, final_path: Path) -> None:
    _reject_symlink_parents(final_path, stop_at=final_path.anchor and Path(final_path.anchor))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_parents(final_path, stop_at=final_path.anchor and Path(final_path.anchor))
    payload = json.loads(source_payload_path.read_text(encoding="utf-8"))
    write_json_0600_exclusive(final_path, payload)


def run_validator(command: list[str]) -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise RefreshError(
            "run validator failed: validator exited non-zero. "
            f"Got: {completed.stderr.strip() or completed.stdout.strip()!r:.100}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
