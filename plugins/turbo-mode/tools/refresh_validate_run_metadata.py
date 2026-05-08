#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.commit_safe import (  # noqa: E402
    build_current_run_identity_from_paths,
    project_commit_safe_fields_from_local_summary,
    sha256_file,
    sha256_payload,
)
from refresh.validation import (  # noqa: E402
    ALLOWED_DIRTY_RELEVANT_PATHS,
    EXPECTED_COMMIT_SAFE_SCHEMA_VERSION,
    EXPECTED_DIRTY_STATE_POLICY,
    EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION,
    EXPECTED_TOOL_PATH,
    assert_commit_safe_payload,
    load_json_object,
    projected_summary_for_validator_digest,
)

SCHEMA_VERSION = "turbo-mode-refresh-metadata-validation-plan-04"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Turbo Mode refresh metadata.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--source-code-root", type=Path)
    parser.add_argument("--execution-repo-root", type=Path)
    parser.add_argument("--mode", choices=("candidate", "final"), required=True)
    parser.add_argument("--local-only-root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--published-summary-path", type=Path, required=True)
    parser.add_argument("--candidate-summary", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--existing-validation-summary", type=Path)
    return parser


def validate_metadata_payload(args: argparse.Namespace) -> tuple[dict[str, object], str]:
    payload = load_json_object(args.summary)
    assert_commit_safe_payload(payload)
    if payload.get("run_id") != args.run_id:
        raise ValueError(
            f"validate run metadata failed: run id mismatch. Got: {payload.get('run_id')!r:.100}"
        )
    if payload.get("mode") == "guarded-refresh":
        return validate_guarded_refresh_metadata_payload(args, payload)
    if args.repo_root is None:
        raise ValueError("validate run metadata failed: --repo-root is required. Got: None")
    local_summary = args.local_only_root / f"{payload['mode']}.summary.json"
    local_payload = load_json_object(local_summary)
    _assert_top_level_metadata_contract(
        args=args,
        payload=payload,
        local_payload=local_payload,
        local_summary=local_summary,
    )
    if payload.get("local_only_summary_sha256") != sha256_file(local_summary):
        raise ValueError(
            "validate run metadata failed: local summary digest mismatch. "
            "Got: local_only_summary_sha256"
        )
    if local_payload.get("schema_version") != "turbo-mode-refresh-plan-03":
        raise ValueError(
            "validate run metadata failed: local summary schema mismatch. "
            f"Got: {local_payload.get('schema_version')!r:.100}"
        )
    if local_payload.get("run_id") != args.run_id:
        raise ValueError(
            "validate run metadata failed: local summary run id mismatch. "
            f"Got: {local_payload.get('run_id')!r:.100}"
        )
    if local_payload.get("mode") != payload.get("mode"):
        raise ValueError(
            "validate run metadata failed: local summary mode mismatch. "
            f"Got: {local_payload.get('mode')!r:.100}"
        )
    tool_path = args.repo_root / str(payload["tool_path"])
    if payload.get("tool_sha256") != sha256_file(tool_path):
        raise ValueError("validate run metadata failed: tool digest mismatch. Got: tool_sha256")
    repo_head = git(args.repo_root, "rev-parse", "HEAD")
    repo_tree = git(args.repo_root, "rev-parse", "HEAD^{tree}")
    if payload.get("repo_head") != repo_head:
        actual = payload.get("repo_head")
        raise ValueError(
            f"validate run metadata failed: repo head mismatch. Got: {actual!r:.100}"
        )
    if payload.get("repo_tree") != repo_tree:
        actual = payload.get("repo_tree")
        raise ValueError(
            f"validate run metadata failed: repo tree mismatch. Got: {actual!r:.100}"
        )
    projected_fields = project_commit_safe_fields_from_local_summary(local_payload)
    for key, expected in projected_fields.items():
        if payload.get(key) != expected:
            raise ValueError(
                f"validate run metadata failed: projected field mismatch. Got: {key!r:.100}"
            )
    current_identity = build_current_run_identity_from_paths(
        repo_root=args.repo_root,
        codex_home=Path(str(local_payload["codex_home"])),
        run_id=args.run_id,
        local_summary=local_payload,
    )
    if payload.get("current_run_identity") != current_identity:
        raise ValueError(
            "validate run metadata failed: current run identity mismatch. Got: current_run_identity"
        )
    _assert_runtime_identity_fields_match_current(payload, current_identity)
    return payload, sha256_payload(projected_summary_for_validator_digest(payload))


def _assert_top_level_metadata_contract(
    *,
    args: argparse.Namespace,
    payload: dict[str, object],
    local_payload: dict[str, object],
    local_summary: Path,
) -> None:
    expected = {
        "schema_version": EXPECTED_COMMIT_SAFE_SCHEMA_VERSION,
        "source_local_summary_schema_version": EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION,
        "dirty_state_policy": EXPECTED_DIRTY_STATE_POLICY,
        "tool_path": EXPECTED_TOOL_PATH,
        "local_only_evidence_root": str(args.local_only_root),
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(
                "validate run metadata failed: top-level metadata mismatch. "
                f"Got: {key!r:.100}"
            )
    if local_payload.get("schema_version") != payload.get("source_local_summary_schema_version"):
        raise ValueError(
            "validate run metadata failed: source local summary schema mismatch. "
            "Got: source_local_summary_schema_version"
        )
    if local_summary.parent != args.local_only_root:
        raise ValueError(
            "validate run metadata failed: local summary path mismatch. "
            f"Got: {str(local_summary)!r:.100}"
        )
    if args.repo_root is None:
        raise ValueError("validate run metadata failed: repo_root is required. Got: None")
    _assert_recomputed_dirty_state(
        args.repo_root,
        payload.get("dirty_state"),
        mode=args.mode,
        published_summary_path=args.published_summary_path,
        allowed_published_summary_path=None,
    )


def validate_guarded_refresh_metadata_payload(
    args: argparse.Namespace,
    payload: dict[str, object],
) -> tuple[dict[str, object], str]:
    if args.source_code_root is None or args.execution_repo_root is None:
        raise ValueError(
            "validate run metadata failed: guarded-refresh validation requires "
            "--source-code-root and --execution-repo-root. Got: split-root-args"
        )
    if args.repo_root is not None:
        raise ValueError(
            "validate run metadata failed: --repo-root is legacy-only for guarded-refresh. "
            "Got: --source-code-root"
        )
    source_code_root = args.source_code_root
    execution_repo_root = args.execution_repo_root
    expected = {
        "schema_version": EXPECTED_COMMIT_SAFE_SCHEMA_VERSION,
        "dirty_state_policy": EXPECTED_DIRTY_STATE_POLICY,
        "tool_path": EXPECTED_TOOL_PATH,
        "local_only_evidence_root": str(args.local_only_root),
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(
                "validate run metadata failed: top-level metadata mismatch. "
                f"Got: {key!r:.100}"
            )
    tool_path = source_code_root / str(payload["tool_path"])
    if payload.get("tool_sha256") != sha256_file(tool_path):
        raise ValueError("validate run metadata failed: tool digest mismatch. Got: tool_sha256")
    _assert_rehearsal_proof_capture_manifest(
        args.local_only_root,
        payload=payload,
    )
    source_head = git(source_code_root, "rev-parse", "HEAD")
    source_tree = git(source_code_root, "rev-parse", "HEAD^{tree}")
    execution_head = git(execution_repo_root, "rev-parse", "HEAD")
    execution_tree = git(execution_repo_root, "rev-parse", "HEAD^{tree}")
    if payload.get("certification_mode") == "retained-run":
        _assert_retained_certification_identity(
            payload,
            certification_source_head=source_head,
            certification_source_tree=source_tree,
            certification_execution_head=execution_head,
            certification_execution_tree=execution_tree,
        )
        allowed_dirty = args.published_summary_path if args.mode == "final" else None
        _assert_no_conflicting_failed_summary(args.published_summary_path)
        _assert_recomputed_dirty_state(
            execution_repo_root,
            payload.get("dirty_state"),
            mode=args.mode,
            published_summary_path=args.published_summary_path,
            allowed_published_summary_path=allowed_dirty,
        )
        return payload, sha256_payload(projected_summary_for_validator_digest(payload))
    if payload.get("source_implementation_commit") != source_head:
        raise ValueError(
            "validate run metadata failed: source implementation commit mismatch. "
            f"Got: {payload.get('source_implementation_commit')!r:.100}"
        )
    if payload.get("source_implementation_tree") != source_tree:
        raise ValueError(
            "validate run metadata failed: source implementation tree mismatch. "
            f"Got: {payload.get('source_implementation_tree')!r:.100}"
        )
    if payload.get("execution_head") != execution_head:
        raise ValueError(
            "validate run metadata failed: execution head mismatch. "
            f"Got: {payload.get('execution_head')!r:.100}"
        )
    if payload.get("execution_tree") != execution_tree:
        raise ValueError(
            "validate run metadata failed: execution tree mismatch. "
            f"Got: {payload.get('execution_tree')!r:.100}"
        )
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            str(payload["source_implementation_commit"]),
            execution_head,
        ],
        cwd=execution_repo_root,
        check=False,
    )
    if ancestor.returncode != 0:
        raise ValueError(
            "validate run metadata failed: source implementation is not execution ancestor. "
            f"Got: {payload.get('source_implementation_commit')!r:.100}"
        )
    allowed_dirty = args.published_summary_path if args.mode == "final" else None
    _assert_no_conflicting_failed_summary(args.published_summary_path)
    _assert_recomputed_dirty_state(
        execution_repo_root,
        payload.get("dirty_state"),
        mode=args.mode,
        published_summary_path=args.published_summary_path,
        allowed_published_summary_path=allowed_dirty,
    )
    return payload, sha256_payload(projected_summary_for_validator_digest(payload))


def _assert_rehearsal_proof_capture_manifest(
    local_only_root: Path,
    *,
    payload: dict[str, object],
) -> None:
    manifest_path = local_only_root / "rehearsal-proof-capture/capture-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            "validate run metadata failed: captured rehearsal proof manifest missing. "
            f"Got: {str(manifest_path)!r:.100}"
        )
    manifest = load_json_object(manifest_path)
    if manifest.get("schema_version") != "turbo-mode-refresh-rehearsal-capture-v1":
        raise ValueError(
            "validate run metadata failed: captured rehearsal proof manifest schema mismatch. "
            f"Got: {manifest.get('schema_version')!r:.100}"
        )
    if payload.get("rehearsal_proof_capture_manifest_sha256") != sha256_file(manifest_path):
        raise ValueError(
            "validate run metadata failed: captured rehearsal proof manifest digest mismatch. "
            "Got: rehearsal_proof_capture_manifest_sha256"
        )
    if manifest.get("rehearsal_proof_sha256") != payload.get("rehearsal_proof_sha256"):
        raise ValueError(
            "validate run metadata failed: captured rehearsal proof digest mismatch. "
            "Got: rehearsal_proof_sha256"
        )


def _assert_no_conflicting_failed_summary(published_summary_path: Path) -> None:
    sibling_failed = _failed_summary_path(published_summary_path)
    if published_summary_path.exists() and sibling_failed.exists():
        raise ValueError(
            "validate run metadata failed: published and failed summary paths coexist. "
            f"Got: {str(published_summary_path)!r:.100}"
        )


def _failed_summary_path(published_summary_path: Path) -> Path:
    name = published_summary_path.name
    if name.endswith(".retained.summary.json"):
        return published_summary_path.with_name(
            name.removesuffix(".retained.summary.json") + ".retained.summary.failed.json"
        )
    if name.endswith(".summary.json"):
        return published_summary_path.with_name(
            name.removesuffix(".summary.json") + ".summary.failed.json"
        )
    raise ValueError(
        "validate run metadata failed: invalid published summary suffix. "
        f"Got: {name!r:.100}"
    )


def _assert_retained_certification_identity(
    payload: dict[str, object],
    *,
    certification_source_head: str,
    certification_source_tree: str,
    certification_execution_head: str,
    certification_execution_tree: str,
) -> None:
    expected = {
        "certification_source_commit": certification_source_head,
        "certification_source_tree": certification_source_tree,
        "certification_execution_head": certification_execution_head,
        "certification_execution_tree": certification_execution_tree,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(
                "validate run metadata failed: retained certification identity mismatch. "
                f"Got: {key!r:.100}"
            )


def _assert_recomputed_dirty_state(
    repo_root: Path,
    dirty_state: object,
    *,
    mode: str,
    published_summary_path: Path,
    allowed_published_summary_path: Path | None,
) -> None:
    if not isinstance(dirty_state, dict):
        raise ValueError(
            f"validate run metadata failed: dirty state is not an object. Got: {dirty_state!r:.100}"
        )
    expected_paths = sorted(ALLOWED_DIRTY_RELEVANT_PATHS)
    expected = {
        "status": "clean-relevant-paths",
        "relevant_paths_checked": expected_paths,
        "post_commit_binding": False,
    }
    if dirty_state != expected:
        raise ValueError(
            f"validate run metadata failed: dirty state mismatch. Got: {dirty_state!r:.100}"
        )
    status_paths = list(expected_paths)
    published_relative = _repo_relative_path(repo_root, published_summary_path)
    if published_relative is not None:
        status_paths.append(published_relative)
    completed = subprocess.run(
        ["git", "status", "--short", "--", *status_paths],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    dirty_paths = _parse_dirty_paths(completed.stdout)
    allowed_relative = (
        _repo_relative_path(repo_root, allowed_published_summary_path)
        if allowed_published_summary_path is not None
        else None
    )
    if dirty_paths and not (
        mode == "final" and allowed_relative is not None and dirty_paths == [allowed_relative]
    ):
        raise ValueError(
            "validate run metadata failed: relevant paths dirty. "
            f"Got: {completed.stdout.strip()!r:.100}"
        )


def _repo_relative_path(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve(strict=False).relative_to(repo_root.resolve(strict=False)).as_posix()
    except ValueError:
        return None


def _parse_dirty_paths(stdout: str) -> list[str]:
    paths: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        paths.append(line[3:].strip())
    return sorted(paths)


def _assert_runtime_identity_fields_match_current(
    payload: dict[str, object],
    current_identity: dict[str, object],
) -> None:
    runtime_identity = current_identity.get("runtime_identity")
    if runtime_identity is None:
        return
    if not isinstance(runtime_identity, dict):
        raise ValueError(
            "validate run metadata failed: runtime identity is not an object. Got: runtime_identity"
        )
    mapping = {
        "codex_version": "codex_version",
        "codex_executable_path": "codex_executable_path",
        "codex_executable_sha256": "codex_executable_sha256",
        "codex_executable_hash_unavailable_reason": "codex_executable_hash_unavailable_reason",
        "app_server_server_info": "app_server_server_info",
        "app_server_protocol_capabilities": "app_server_protocol_capabilities",
        "app_server_parser_version": "app_server_parser_version",
        "app_server_response_schema_version": "app_server_response_schema_version",
    }
    for payload_key, identity_key in mapping.items():
        if payload.get(payload_key) != runtime_identity.get(identity_key):
            raise ValueError(
                "validate run metadata failed: runtime identity field mismatch. "
                f"Got: {payload_key!r:.100}"
            )


def validate_candidate(args: argparse.Namespace) -> int:
    payload, projected_digest = validate_metadata_payload(args)
    if payload.get("mode") == "guarded-refresh":
        summary = {
            "schema_version": SCHEMA_VERSION,
            "run_id": args.run_id,
            "validator_mode": "candidate",
            "status": "passed",
            "summary_path": str(args.summary),
            "published_summary_path": str(args.published_summary_path),
            "candidate_summary_sha256": sha256_file(args.summary),
            "validated_payload_projection_sha256": projected_digest,
            "tool_sha256": payload["tool_sha256"],
            "source_implementation_commit": payload["source_implementation_commit"],
            "source_implementation_tree": payload["source_implementation_tree"],
            "execution_head": payload["execution_head"],
            "execution_tree": payload["execution_tree"],
            "source_code_root_role": "validator-and-source",
            "execution_repo_root_role": "runtime-and-dirty-state",
        }
        if payload.get("certification_mode") == "retained-run":
            summary.update(
                {
                    "certification_mode": "retained-run",
                    "certification_source_commit": payload["certification_source_commit"],
                    "certification_source_tree": payload["certification_source_tree"],
                    "certification_execution_head": payload["certification_execution_head"],
                    "certification_execution_tree": payload["certification_execution_tree"],
                    "original_run_final_status": payload["original_run_final_status"],
                    "retained_summary_path": payload["retained_summary_path"],
                }
            )
        if args.summary_output is None:
            raise ValueError(
                "validate run metadata failed: summary output is required in candidate mode. "
                "Got: None"
            )
        write_summary(args.summary_output, summary)
        return 0
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "status": "passed",
        "summary_path": str(args.summary),
        "published_summary_path": str(args.published_summary_path),
        "candidate_summary_sha256": sha256_file(args.summary),
        "validated_payload_projection_sha256": projected_digest,
        "local_summary_sha256": payload["local_only_summary_sha256"],
        "tool_sha256": payload["tool_sha256"],
        "repo_head": payload["repo_head"],
        "repo_tree": payload["repo_tree"],
        "current_run_identity": payload["current_run_identity"],
    }
    if args.summary_output is None:
        raise ValueError(
            "validate run metadata failed: summary output is required in candidate mode. Got: None"
        )
    write_summary(args.summary_output, summary)
    return 0


def validate_final(args: argparse.Namespace) -> int:
    payload, projected_digest = validate_metadata_payload(args)
    if args.existing_validation_summary is None:
        raise ValueError(
            "validate run metadata failed: existing validation summary is required "
            "in final mode. Got: None"
        )
    if args.candidate_summary is None:
        raise ValueError(
            "validate run metadata failed: candidate summary is required in final mode. Got: None"
        )
    existing = load_json_object(args.existing_validation_summary)
    if payload.get("mode") == "guarded-refresh":
        expected_fields = {
            "schema_version": SCHEMA_VERSION,
            "run_id": args.run_id,
            "validator_mode": "candidate",
            "status": "passed",
            "summary_path": str(args.candidate_summary),
            "published_summary_path": str(args.published_summary_path),
            "tool_sha256": payload["tool_sha256"],
            "source_implementation_commit": payload["source_implementation_commit"],
            "source_implementation_tree": payload["source_implementation_tree"],
            "execution_head": payload["execution_head"],
            "execution_tree": payload["execution_tree"],
            "source_code_root_role": "validator-and-source",
            "execution_repo_root_role": "runtime-and-dirty-state",
        }
        if payload.get("certification_mode") == "retained-run":
            expected_fields.update(
                {
                    "certification_mode": "retained-run",
                    "certification_source_commit": payload["certification_source_commit"],
                    "certification_source_tree": payload["certification_source_tree"],
                    "certification_execution_head": payload["certification_execution_head"],
                    "certification_execution_tree": payload["certification_execution_tree"],
                    "original_run_final_status": payload["original_run_final_status"],
                    "retained_summary_path": payload["retained_summary_path"],
                }
            )
        for key, expected in expected_fields.items():
            if existing.get(key) != expected:
                raise ValueError(
                    "validate run metadata failed: validator summary field mismatch. "
                    f"Got: {key!r:.100}"
                )
        if existing.get("validated_payload_projection_sha256") != projected_digest:
            raise ValueError(
                "validate run metadata failed: projected summary digest mismatch. "
                "Got: validated_payload_projection_sha256"
            )
        if existing.get("candidate_summary_sha256") != sha256_file(args.candidate_summary):
            raise ValueError(
                "validate run metadata failed: candidate summary digest mismatch. "
                "Got: candidate_summary_sha256"
            )
        if payload.get("metadata_validation_summary_sha256") != sha256_file(
            args.existing_validation_summary
        ):
            raise ValueError(
                "validate run metadata failed: metadata validator digest mismatch. "
                "Got: metadata_validation_summary_sha256"
            )
        return 0
    expected_fields = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "status": "passed",
        "summary_path": str(args.candidate_summary),
        "published_summary_path": str(args.published_summary_path),
        "local_summary_sha256": payload["local_only_summary_sha256"],
        "tool_sha256": payload["tool_sha256"],
        "repo_head": payload["repo_head"],
        "repo_tree": payload["repo_tree"],
        "current_run_identity": payload["current_run_identity"],
    }
    for key, expected in expected_fields.items():
        if existing.get(key) != expected:
            raise ValueError(
                "validate run metadata failed: validator summary field mismatch. "
                f"Got: {key!r:.100}"
            )
    if existing.get("validated_payload_projection_sha256") != projected_digest:
        raise ValueError(
            "validate run metadata failed: projected summary digest mismatch. "
            "Got: validated_payload_projection_sha256"
        )
    if existing.get("candidate_summary_sha256") != sha256_file(args.candidate_summary):
        raise ValueError(
            "validate run metadata failed: candidate summary digest mismatch. "
            "Got: candidate_summary_sha256"
        )
    if payload.get("metadata_validation_summary_sha256") != sha256_file(
        args.existing_validation_summary
    ):
        raise ValueError(
            "validate run metadata failed: metadata validator digest mismatch. "
            "Got: metadata_validation_summary_sha256"
        )
    return 0


def git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


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
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
