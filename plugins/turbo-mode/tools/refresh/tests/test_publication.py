from __future__ import annotations

import json
from pathlib import Path

import pytest
from refresh.models import RefreshError
from refresh.publication import PublicationReplayPaths, publish_and_replay_commit_safe_summary


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def publication_paths(tmp_path: Path) -> PublicationReplayPaths:
    repo_root = tmp_path / "repo"
    run_root = tmp_path / ".codex/local-only/turbo-mode-refresh/run-1"
    return PublicationReplayPaths(
        candidate=run_root / "commit-safe.candidate.summary.json",
        final=run_root / "commit-safe.final.summary.json",
        metadata=run_root / "metadata-validation.summary.json",
        redaction=run_root / "redaction.summary.json",
        redaction_final=run_root / "redaction-final-scan.summary.json",
        published=repo_root / "plugins/turbo-mode/evidence/refresh/run-1.summary.json",
        failed=repo_root / "plugins/turbo-mode/evidence/refresh/run-1.summary.failed.json",
    )


def test_publication_candidate_failure_leaves_no_repo_summary(tmp_path: Path) -> None:
    paths = publication_paths(tmp_path)

    with pytest.raises(RefreshError, match="candidate failed"):
        publish_and_replay_commit_safe_summary(
            operation="publish live guarded refresh summary",
            paths=paths,
            build_candidate_payload=lambda: {"status": "candidate"},
            build_final_payload=lambda _metadata, _redaction: {"status": "final"},
            validate_payload=lambda _payload: None,
            run_candidate_validation=lambda _paths: (_ for _ in ()).throw(
                RefreshError("candidate failed")
            ),
            run_final_validation=lambda _paths: None,
        )

    assert paths.candidate.is_file()
    assert not paths.final.exists()
    assert not paths.published.exists()
    assert not paths.failed.exists()


def test_publication_final_failure_demotes_summary_without_overwrite(
    tmp_path: Path,
) -> None:
    paths = publication_paths(tmp_path)

    def run_candidate_validation(active_paths: PublicationReplayPaths) -> None:
        write_json(active_paths.metadata, {"status": "passed"})
        write_json(active_paths.redaction, {"status": "passed"})

    with pytest.raises(RefreshError, match="forced final failure") as excinfo:
        publish_and_replay_commit_safe_summary(
            operation="publish live guarded refresh summary",
            paths=paths,
            build_candidate_payload=lambda: {"status": "candidate"},
            build_final_payload=lambda metadata_sha, redaction_sha: {
                "status": "final",
                "metadata": metadata_sha,
                "redaction": redaction_sha,
            },
            validate_payload=lambda _payload: None,
            run_candidate_validation=run_candidate_validation,
            run_final_validation=lambda _paths: (_ for _ in ()).throw(
                RefreshError("forced final failure")
            ),
        )

    assert getattr(excinfo.value, "demoted_summary_path") == str(paths.failed)
    assert paths.final.is_file()
    assert not paths.published.exists()
    assert paths.failed.is_file()


def test_publication_rejects_coexisting_summary_and_failed_paths(tmp_path: Path) -> None:
    paths = publication_paths(tmp_path)
    write_json(paths.published, {"status": "published"})
    write_json(paths.failed, {"status": "failed"})

    with pytest.raises(RefreshError, match="coexist"):
        publish_and_replay_commit_safe_summary(
            operation="publish live guarded refresh summary",
            paths=paths,
            build_candidate_payload=lambda: {"status": "candidate"},
            build_final_payload=lambda _metadata, _redaction: {"status": "final"},
            validate_payload=lambda _payload: None,
            run_candidate_validation=lambda _paths: None,
            run_final_validation=lambda _paths: None,
        )


def test_publication_rejects_existing_failed_summary_before_publish(tmp_path: Path) -> None:
    paths = publication_paths(tmp_path)
    write_json(paths.failed, {"status": "failed"})

    with pytest.raises(RefreshError, match="failed summary already exists"):
        publish_and_replay_commit_safe_summary(
            operation="publish live guarded refresh summary",
            paths=paths,
            build_candidate_payload=lambda: {"status": "candidate"},
            build_final_payload=lambda _metadata, _redaction: {"status": "final"},
            validate_payload=lambda _payload: None,
            run_candidate_validation=lambda _paths: None,
            run_final_validation=lambda _paths: None,
        )
