"""Storage authority for Handoff runtime paths and state transitions."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from turbo_mode_handoff_runtime.active_writes import ActiveWriteReservation


from turbo_mode_handoff_runtime.storage_primitives import (
    read_json_object as _read_json_object_primitive,
    sha256_regular_file_or_none as _content_sha256,
    write_json_atomic as _write_json_atomic,
)


class StorageLocation(StrEnum):
    PRIMARY_ACTIVE = "primary_active"
    PRIMARY_ARCHIVE = "primary_archive"
    PRIMARY_STATE = "primary_state"
    LEGACY_ACTIVE = "legacy_active"
    LEGACY_ARCHIVE = "legacy_archive"
    LEGACY_STATE = "legacy_state"
    STATE_LIKE_RESIDUE = "state_like_residue"
    PREVIOUS_PRIMARY_HIDDEN_ARCHIVE = "previous_primary_hidden_archive"
    UNKNOWN = "unknown"


class SelectionEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED_POLICY_CONFLICT = "blocked-policy-conflict"
    BLOCKED_TRACKED_SOURCE = "blocked-tracked-source"
    INVALID = "invalid"
    SKIPPED = "skipped"
    NOT_ACTIVE_SELECTION_INPUT = "not-active-selection-input"
    NOT_EXPLICIT_PATH_INPUT = "not-explicit-path-input"
    NOT_HISTORY_SEARCH_INPUT = "not-history-search-input"
    NOT_STATE_BRIDGE_INPUT = "not-state-bridge-input"


class ChainStateDiagnosticError(RuntimeError):
    """Raised when chain-state selection requires explicit operator recovery."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        error = payload.get("error", {})
        if isinstance(error, dict):
            message = str(error.get("message", "chain-state recovery required"))
        else:
            message = "chain-state recovery required"
        super().__init__(message)


FILENAME_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2})_.+\.md$")
LEGACY_ACTIVE_OPT_IN_MANIFEST = (
    Path("docs")
    / "superpowers"
    / "plans"
    / "2026-05-13-handoff-storage-legacy-active-opt-ins.md"
)
LEGACY_CONSUMED_PREFIX = "MIGRATED:"
CHAIN_STATE_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class StorageLayout:
    project_root: Path
    primary_active_dir: Path
    primary_archive_dir: Path
    primary_state_dir: Path
    legacy_active_dir: Path
    legacy_archive_dir: Path
    legacy_state_dir: Path
    previous_primary_hidden_archive_dir: Path


@dataclass(frozen=True)
class HandoffCandidate:
    path: Path
    storage_location: StorageLocation
    artifact_class: str
    selection_eligibility: SelectionEligibility
    source_git_visibility: str
    source_fs_status: str
    filename_timestamp: str | None = None
    content_sha256: str | None = None
    document_profile: str | None = None
    skip_reason: str | None = None


@dataclass(frozen=True)
class HandoffInventory:
    project_root: Path
    scan_mode: str
    candidates: list[HandoffCandidate]


def get_storage_layout(project_root: Path) -> StorageLayout:
    """Return the post-cutover Handoff storage layout for a project root."""
    root = project_root.resolve()
    primary = root / ".codex" / "handoffs"
    legacy = root / "docs" / "handoffs"
    return StorageLayout(
        project_root=root,
        primary_active_dir=primary,
        primary_archive_dir=primary / "archive",
        primary_state_dir=primary / ".session-state",
        legacy_active_dir=legacy,
        legacy_archive_dir=legacy / "archive",
        legacy_state_dir=legacy / ".session-state",
        previous_primary_hidden_archive_dir=primary / ".archive",
    )


def begin_active_write(
    project_root: Path,
    *,
    project_name: str | None,
    operation: str,
    slug: str | None = None,
    run_id: str | None = None,
    created_at: str | None = None,
    lease_seconds: int = 1800,
) -> ActiveWriteReservation:
    """Reserve a primary active handoff write through the storage facade."""
    from turbo_mode_handoff_runtime.active_writes import begin_active_write as _begin_active_write

    return _begin_active_write(
        project_root,
        project_name=project_name,
        operation=operation,
        slug=slug,
        run_id=run_id,
        created_at=created_at,
        lease_seconds=lease_seconds,
    )


def allocate_active_path(
    project_root: Path,
    *,
    operation: str,
    slug: str,
    created_at: str | None = None,
) -> Path:
    """Allocate a primary active handoff path through the storage facade."""
    from turbo_mode_handoff_runtime.active_writes import allocate_active_path as _allocate_active_path

    return _allocate_active_path(
        project_root,
        operation=operation,
        slug=slug,
        created_at=created_at,
    )


def write_active_handoff(
    project_root: Path,
    *,
    operation_state_path: Path,
    content: str,
    content_sha256: str,
) -> dict[str, object]:
    """Write a reserved primary active handoff through the storage facade."""
    from turbo_mode_handoff_runtime.active_writes import write_active_handoff as _write_active_handoff

    return _write_active_handoff(
        project_root,
        operation_state_path=operation_state_path,
        content=content,
        content_sha256=content_sha256,
    )


def list_active_writes(
    project_root: Path,
    *,
    project_name: str,
    operation: str | None = None,
) -> list[dict[str, object]]:
    """List active write operation-state records through the storage facade."""
    from turbo_mode_handoff_runtime.active_writes import list_active_writes as _list_active_writes

    return _list_active_writes(
        project_root,
        project_name=project_name,
        operation=operation,
    )


def abandon_active_write(
    project_root: Path,
    *,
    operation_state_path: Path,
    reason: str,
) -> dict[str, object]:
    """Mark an active write abandoned through the storage facade."""
    from turbo_mode_handoff_runtime.active_writes import abandon_active_write as _abandon_active_write

    return _abandon_active_write(
        project_root,
        operation_state_path=operation_state_path,
        reason=reason,
    )


def recover_active_write_transaction(
    project_root: Path,
    *,
    operation_state_path: Path,
) -> dict[str, object]:
    """Recover an active write transaction through the storage facade."""
    from turbo_mode_handoff_runtime.active_writes import (
        recover_active_write_transaction as _recover_active_write_transaction,
    )

    return _recover_active_write_transaction(
        project_root,
        operation_state_path=operation_state_path,
    )


def chain_state_recovery_inventory(
    project_root: Path,
    *,
    project_name: str,
) -> dict[str, object]:
    """Return read-only chain-state recovery inventory for one project."""
    layout = get_storage_layout(project_root)
    candidates = [
        *[
            _chain_state_record(
                layout=layout,
                path=path,
                storage_location=StorageLocation.PRIMARY_STATE,
                source_root="primary",
                project_name=project_name,
            )
            for path in _state_candidate_paths(layout.primary_state_dir, project_name)
        ],
        *[
            _chain_state_record(
                layout=layout,
                path=path,
                storage_location=StorageLocation.LEGACY_STATE,
                source_root="legacy",
                project_name=project_name,
            )
            for path in _state_candidate_paths(layout.legacy_state_dir, project_name)
        ],
        *[
            _chain_state_record(
                layout=layout,
                path=path,
                storage_location=StorageLocation.STATE_LIKE_RESIDUE,
                source_root="legacy",
                project_name=project_name,
            )
            for path in _state_like_residue_paths(layout.legacy_active_dir, project_name)
        ],
    ]
    return {
        "project_root": str(layout.project_root),
        "project": project_name,
        "total": len(candidates),
        "candidates": sorted(
            candidates,
            key=lambda candidate: str(candidate["project_relative_state_path"]),
        ),
    }


def mark_chain_state_consumed(
    project_root: Path,
    *,
    project_name: str,
    state_path: str,
    expected_payload_sha256: str,
    reason: str,
) -> dict[str, object]:
    """Durably suppress one exact legacy/state-like chain-state candidate."""
    layout = get_storage_layout(project_root)
    inventory = chain_state_recovery_inventory(layout.project_root, project_name=project_name)
    candidate = _select_chain_state_candidate(
        inventory,
        selector=state_path,
    )
    if candidate["storage_location"] == StorageLocation.PRIMARY_STATE:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="primary-chain-state-not-consumable",
                message="mark-chain-state-consumed requires a legacy or state-like candidate.",
                candidate=candidate,
            )
        )
    if candidate["validation_status"] not in {"valid", "expired"}:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-candidate-invalid",
                message=(
                    "mark-chain-state-consumed requires a valid or expired chain-state candidate."
                ),
                candidate=candidate,
            )
        )
    if candidate["payload_sha256"] != expected_payload_sha256:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-payload-hash-mismatch",
                message="Selected chain-state payload hash does not match expected hash.",
                candidate=candidate,
            )
        )
    marker_path = layout.primary_state_dir / "markers" / "chain-state-consumed.json"
    transaction_id = uuid.uuid4().hex
    transaction_path = layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
    marked_at = datetime.now(UTC).isoformat()
    stable_key = _chain_state_stable_key(candidate)
    marker = _read_json_object(marker_path)
    entries = marker.get("entries")
    if not isinstance(entries, list):
        entries = []
    if not any(
        isinstance(entry, dict) and entry.get("stable_key") == stable_key
        for entry in entries
    ):
        entries.append({
            "stable_key": stable_key,
            "reason": reason,
            "marked_at": marked_at,
            "transaction_id": transaction_id,
            "lexical_path": candidate["lexical_path"],
            "resolved_path": candidate["resolved_path"],
        })
    marker = {
        "schema_version": 1,
        "entries": entries,
    }
    transaction = {
        "schema_version": 1,
        "transaction_id": transaction_id,
        "operation": "mark-chain-state-consumed",
        "status": "completed",
        "project": project_name,
        "stable_key": stable_key,
        "reason": reason,
        "marker_path": str(marker_path),
        "created_at": marked_at,
        "completed_at": marked_at,
    }
    _write_json_atomic(marker_path, marker)
    _write_json_atomic(transaction_path, transaction)
    return {
        "status": "consumed",
        "marker_path": str(marker_path),
        "transaction_path": str(transaction_path),
        "transaction_id": transaction_id,
        "stable_key": stable_key,
    }


def continue_chain_state(
    project_root: Path,
    *,
    project_name: str,
    state_path: str,
    expected_payload_sha256: str,
) -> dict[str, object]:
    """Continue from one exact legacy/state-like candidate into primary state."""
    layout = get_storage_layout(project_root)
    inventory = chain_state_recovery_inventory(layout.project_root, project_name=project_name)
    candidate = _select_chain_state_candidate(inventory, selector=state_path)
    if candidate["storage_location"] == StorageLocation.PRIMARY_STATE:
        return {
            "status": "continued",
            "state_path": candidate["resolved_path"],
            "transaction_path": None,
            "marker_path": None,
        }
    if candidate["validation_status"] not in {"valid", "expired"}:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-candidate-invalid",
                message="continue-chain-state requires a valid or expired chain-state candidate.",
                candidate=candidate,
            )
        )
    if candidate["payload_sha256"] != expected_payload_sha256:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-payload-hash-mismatch",
                message="Selected chain-state payload hash does not match expected hash.",
                candidate=candidate,
            )
        )
    resume_token = str(candidate["resume_token"] or uuid.uuid4().hex)
    primary_state_path = layout.primary_state_dir / f"handoff-{project_name}-{resume_token}.json"
    marker_path = layout.primary_state_dir / "markers" / "chain-state-consumed.json"
    transaction_id = uuid.uuid4().hex
    transaction_path = layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
    now = datetime.now(UTC).isoformat()
    stable_key = _chain_state_stable_key(candidate)
    primary_payload = {
        "state_path": str(primary_state_path),
        "project": project_name,
        "resume_token": resume_token,
        "archive_path": candidate["archive_path"],
        "created_at": now,
        "resumed_from": {
            **stable_key,
            "lexical_path": candidate["lexical_path"],
            "resolved_path": candidate["resolved_path"],
        },
    }
    marker = _read_json_object(marker_path)
    entries = marker.get("entries")
    if not isinstance(entries, list):
        entries = []
    if not any(
        isinstance(entry, dict) and entry.get("stable_key") == stable_key
        for entry in entries
    ):
        entries.append({
            "stable_key": stable_key,
            "reason": "continued into primary chain state",
            "marked_at": now,
            "transaction_id": transaction_id,
            "lexical_path": candidate["lexical_path"],
            "resolved_path": candidate["resolved_path"],
        })
    marker = {
        "schema_version": 1,
        "entries": entries,
    }
    transaction = {
        "schema_version": 1,
        "transaction_id": transaction_id,
        "operation": "continue-chain-state",
        "status": "completed",
        "project": project_name,
        "state_path": str(primary_state_path),
        "stable_key": stable_key,
        "marker_path": str(marker_path),
        "created_at": now,
        "completed_at": now,
    }
    _write_json_atomic(primary_state_path, primary_payload)
    _write_json_atomic(marker_path, marker)
    _write_json_atomic(transaction_path, transaction)
    return {
        "status": "continued",
        "state_path": str(primary_state_path),
        "marker_path": str(marker_path),
        "transaction_path": str(transaction_path),
        "transaction_id": transaction_id,
        "stable_key": stable_key,
    }


def abandon_primary_chain_state(
    project_root: Path,
    *,
    project_name: str,
    state_path: str,
    expected_payload_sha256: str,
    reason: str,
) -> dict[str, object]:
    """Move one exact primary chain-state file out of active primary lookup."""
    layout = get_storage_layout(project_root)
    inventory = chain_state_recovery_inventory(layout.project_root, project_name=project_name)
    candidate = _select_chain_state_candidate(inventory, selector=state_path)
    if candidate["storage_location"] != StorageLocation.PRIMARY_STATE:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-candidate-not-primary",
                message="abandon-primary-chain-state requires a primary state candidate.",
                candidate=candidate,
            )
        )
    if candidate["validation_status"] != "valid":
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-candidate-invalid",
                message="abandon-primary-chain-state requires a valid primary candidate.",
                candidate=candidate,
            )
        )
    if candidate["payload_sha256"] != expected_payload_sha256:
        raise ChainStateDiagnosticError(
            _operator_error(
                code="chain-state-payload-hash-mismatch",
                message="Selected primary chain-state payload hash does not match expected hash.",
                candidate=candidate,
            )
        )
    source_path = Path(str(candidate["resolved_path"]))
    transaction_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    abandoned_path = (
        layout.primary_state_dir
        / "abandoned"
        / f"{source_path.name}.{expected_payload_sha256[:12]}.json"
    )
    transaction_path = layout.primary_state_dir / "transactions" / f"{transaction_id}.json"
    abandoned_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source_path, abandoned_path)
    transaction = {
        "schema_version": 1,
        "transaction_id": transaction_id,
        "operation": "abandon-primary-chain-state",
        "status": "completed",
        "project": project_name,
        "source_state_path": str(source_path),
        "abandoned_path": str(abandoned_path),
        "source_state_sha256": expected_payload_sha256,
        "reason": reason,
        "created_at": now,
        "completed_at": now,
    }
    _write_json_atomic(transaction_path, transaction)
    return {
        "status": "abandoned",
        "state_path": str(source_path),
        "abandoned_path": str(abandoned_path),
        "transaction_path": str(transaction_path),
        "transaction_id": transaction_id,
    }


def read_chain_state(
    project_root: Path,
    *,
    project_name: str,
) -> dict[str, object]:
    """Read one unambiguous chain-state candidate or raise a recovery diagnostic."""
    inventory = chain_state_recovery_inventory(project_root, project_name=project_name)
    candidates = list(inventory["candidates"])
    valid = [candidate for candidate in candidates if candidate["validation_status"] == "valid"]
    expired = [
        candidate
        for candidate in candidates
        if candidate["validation_status"] == "expired"
        and candidate["marker_status"] != "consumed"
    ]
    primary = [
        candidate
        for candidate in valid
        if candidate["storage_location"] == StorageLocation.PRIMARY_STATE
    ]
    legacy = [
        candidate
        for candidate in valid
        if candidate["storage_location"]
        in {StorageLocation.LEGACY_STATE, StorageLocation.STATE_LIKE_RESIDUE}
        and candidate["marker_status"] != "consumed"
    ]
    if len(primary) > 1:
        raise ChainStateDiagnosticError(
            _chain_state_diagnostic(
                code="ambiguous-primary-chain-state",
                message="Multiple valid primary chain states require explicit operator recovery.",
                inventory=inventory,
                candidates=primary,
                recovery_choices=[
                    "continue-chain-state",
                    "abandon-primary-chain-state",
                    "abort",
                ],
            )
        )
    if len(primary) == 1 and legacy:
        raise ChainStateDiagnosticError(
            _chain_state_diagnostic(
                code="primary-chain-state-with-unresolved-legacy",
                message=(
                    "Valid primary chain state exists with unresolved legacy state candidates."
                ),
                inventory=inventory,
                candidates=[*primary, *legacy],
                recovery_choices=[
                    "mark-chain-state-consumed",
                    "abandon-primary-chain-state",
                    "abort",
                ],
            )
        )
    if len(primary) == 1:
        return {
            "status": "found",
            "source": "primary",
            "state": primary[0],
        }
    if len(legacy) > 1:
        raise ChainStateDiagnosticError(
            _chain_state_diagnostic(
                code="ambiguous-legacy-chain-state",
                message="Multiple valid legacy chain states require explicit operator recovery.",
                inventory=inventory,
                candidates=legacy,
                recovery_choices=[
                    "continue-chain-state",
                    "mark-chain-state-consumed",
                    "abort",
                ],
            )
        )
    if len(legacy) == 1:
        return {
            "status": "legacy-bridge-required",
            "source": "legacy",
            "state": legacy[0],
        }
    if expired:
        raise ChainStateDiagnosticError(
            _chain_state_diagnostic(
                code="expired-chain-state",
                message="Expired chain state requires explicit operator recovery.",
                inventory=inventory,
                candidates=expired,
                recovery_choices=[
                    "continue-chain-state",
                    "mark-chain-state-consumed",
                    "abort",
                ],
            )
        )
    return {
        "status": "absent",
        "source": None,
        "state": None,
    }


def _chain_state_diagnostic(
    *,
    code: str,
    message: str,
    inventory: dict[str, object],
    candidates: list[dict[str, object]],
    recovery_choices: list[str],
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "recovery_inventory_command": {
                "command": "chain-state-recovery-inventory",
                "args": {
                    "project_root": inventory["project_root"],
                    "project": inventory["project"],
                },
            },
            "recovery_choices": recovery_choices,
        },
        "candidates": sorted(
            candidates,
            key=lambda candidate: str(candidate["project_relative_state_path"]),
        ),
    }


def _operator_error(
    *,
    code: str,
    message: str,
    candidate: dict[str, object],
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "candidates": [candidate],
    }


def _select_chain_state_candidate(
    inventory: dict[str, object],
    *,
    selector: str,
) -> dict[str, object]:
    candidates = [
        candidate
        for candidate in inventory["candidates"]
        if isinstance(candidate, dict)
        and selector
        in {
            str(candidate["project_relative_state_path"]),
            str(candidate["lexical_path"]),
            str(candidate["resolved_path"]),
            str(candidate.get("resume_token") or ""),
        }
    ]
    if len(candidates) != 1:
        raise ChainStateDiagnosticError(
            _chain_state_diagnostic(
                code="chain-state-selector-ambiguous",
                message="Expected exactly one chain-state candidate for selector.",
                inventory=inventory,
                candidates=candidates,
                recovery_choices=["chain-state-recovery-inventory", "abort"],
            )
        )
    return candidates[0]


def _state_candidate_paths(root: Path, project_name: str) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    paths = [root / f"handoff-{project_name}"]
    paths.extend(sorted(root.glob(f"handoff-{project_name}-*.json")))
    return [path for path in paths if path.is_file()]


def _state_like_residue_paths(root: Path, project_name: str) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    paths = [root / f"handoff-{project_name}"]
    paths.extend(sorted(root.glob(f"handoff-{project_name}-*.json")))
    return [path for path in paths if path.is_file()]


def _chain_state_record(
    *,
    layout: StorageLayout,
    path: Path,
    storage_location: StorageLocation,
    source_root: str,
    project_name: str,
) -> dict[str, object]:
    detected_format = _chain_state_format(path)
    parsed = _parse_chain_state(path, project_name=project_name, detected_format=detected_format)
    age_seconds = _age_seconds(path)
    parsed = _apply_chain_state_ttl(
        parsed,
        age_seconds=age_seconds,
        storage_location=storage_location,
    )
    record = {
        "source_root": source_root,
        "storage_location": str(storage_location),
        "project_relative_state_path": _project_relative_path(layout.project_root, path),
        "lexical_path": str(path),
        "resolved_path": str(path.resolve()),
        "project": parsed["project"],
        "resume_token": parsed["resume_token"],
        "detected_format": detected_format,
        "archive_path": parsed["archive_path"],
        "created_at": parsed["created_at"],
        "age_seconds": age_seconds,
        "payload_sha256": _content_sha256(path),
        "validation_status": parsed["validation_status"],
        "validation_error": parsed["validation_error"],
        "source_git_visibility": _git_visibility(layout.project_root, path),
        "source_fs_status": _fs_status(path),
        "marker_status": "unmarked",
        "transaction_status": "none",
    }
    record["marker_status"] = _chain_state_marker_status(layout, record)
    return record


def _chain_state_marker_status(
    layout: StorageLayout,
    candidate: dict[str, object],
) -> str:
    if candidate["validation_status"] not in {"valid", "expired"}:
        return "unmarked"
    marker_path = layout.primary_state_dir / "markers" / "chain-state-consumed.json"
    if not marker_path.exists():
        return "unmarked"
    try:
        marker = _read_json_object(marker_path)
    except ChainStateDiagnosticError as exc:
        error = exc.payload.get("error", {})
        code = error.get("code") if isinstance(error, dict) else ""
        if code in {"chain-state-marker-unreadable", "chain-state-marker-malformed"}:
            return "marker-unreadable"
        raise
    entries = marker.get("entries")
    if not isinstance(entries, list):
        return "marker-unreadable"
    stable_key = _chain_state_stable_key(candidate)
    if any(
        isinstance(entry, dict) and entry.get("stable_key") == stable_key
        for entry in entries
    ):
        return "consumed"
    return "unmarked"


def _chain_state_stable_key(candidate: dict[str, object]) -> dict[str, object]:
    return {
        "source_root": candidate["source_root"],
        "storage_location": candidate["storage_location"],
        "project_relative_state_path": candidate["project_relative_state_path"],
        "project": candidate["project"],
        "resume_token": candidate["resume_token"],
        "detected_format": candidate["detected_format"],
        "payload_sha256": candidate["payload_sha256"],
    }


def _chain_state_format(path: Path) -> str:
    if path.suffix == ".json":
        return "tokenized-json"
    return "plain-state"


def _parse_chain_state(
    path: Path,
    *,
    project_name: str,
    detected_format: str,
) -> dict[str, object]:
    if detected_format == "tokenized-json":
        return _parse_tokenized_chain_state(path, project_name=project_name)
    return _parse_plain_chain_state(path, project_name=project_name)


def _apply_chain_state_ttl(
    parsed: dict[str, object],
    *,
    age_seconds: int | None,
    storage_location: StorageLocation,
) -> dict[str, object]:
    if parsed["validation_status"] != "valid":
        return parsed
    if storage_location == StorageLocation.PRIMARY_STATE:
        return parsed
    if age_seconds is None or age_seconds <= CHAIN_STATE_TTL_SECONDS:
        return parsed
    return {
        **parsed,
        "validation_status": "expired",
        "validation_error": "chain state TTL expired",
    }


def _parse_tokenized_chain_state(path: Path, *, project_name: str) -> dict[str, object]:
    token = _resume_token_from_state_filename(path, project_name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _invalid_chain_state(
            project=project_name,
            resume_token=token,
            validation_error=f"invalid tokenized JSON: {exc}",
        )
    if not isinstance(payload, dict):
        return _invalid_chain_state(
            project=project_name,
            resume_token=token,
            validation_error="tokenized state payload is not an object",
        )
    payload_project = str(payload.get("project", ""))
    payload_token = str(payload.get("resume_token", ""))
    if payload_project != project_name:
        return _invalid_chain_state(
            project=payload_project,
            resume_token=payload_token or token,
            archive_path=str(payload.get("archive_path", "")),
            created_at=str(payload.get("created_at", "")),
            validation_error="payload project does not match filename project",
        )
    if payload_token != token:
        return _invalid_chain_state(
            project=payload_project,
            resume_token=payload_token,
            archive_path=str(payload.get("archive_path", "")),
            created_at=str(payload.get("created_at", "")),
            validation_error="payload resume token does not match filename token",
        )
    return {
        "project": payload_project,
        "resume_token": payload_token,
        "archive_path": str(payload.get("archive_path", "")),
        "created_at": str(payload.get("created_at", "")),
        "validation_status": "valid",
        "validation_error": None,
    }


def _parse_plain_chain_state(path: Path, *, project_name: str) -> dict[str, object]:
    try:
        archive_path = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return _invalid_chain_state(
            project=project_name,
            resume_token=None,
            validation_error=f"plain state unreadable: {exc}",
        )
    if not archive_path:
        return _invalid_chain_state(
            project=project_name,
            resume_token=None,
            validation_error="plain state is empty",
        )
    if archive_path.startswith(LEGACY_CONSUMED_PREFIX):
        return {
            "project": project_name,
            "resume_token": None,
            "archive_path": None,
            "created_at": None,
            "validation_status": "consumed",
            "validation_error": None,
        }
    return {
        "project": project_name,
        "resume_token": None,
        "archive_path": archive_path,
        "created_at": None,
        "validation_status": "valid",
        "validation_error": None,
    }


def _invalid_chain_state(
    *,
    project: str,
    resume_token: str | None,
    validation_error: str,
    archive_path: str | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    return {
        "project": project,
        "resume_token": resume_token,
        "archive_path": archive_path,
        "created_at": created_at,
        "validation_status": "invalid",
        "validation_error": validation_error,
    }


def _resume_token_from_state_filename(path: Path, project_name: str) -> str:
    prefix = f"handoff-{project_name}-"
    if not path.name.startswith(prefix) or path.suffix != ".json":
        return ""
    return path.name.removeprefix(prefix).removesuffix(".json")


def _project_relative_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _age_seconds(path: Path) -> int | None:
    try:
        return max(0, int(time.time() - path.stat().st_mtime))
    except OSError:
        return None


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ChainStateDiagnosticError({
            "error": {
                "code": "chain-state-marker-unreadable",
                "message": f"chain-state marker unreadable: {path}",
            },
            "marker_path": str(path),
        }) from exc
    if not isinstance(payload, dict):
        raise ChainStateDiagnosticError({
            "error": {
                "code": "chain-state-marker-malformed",
                "message": f"chain-state marker malformed: {path}",
            },
            "marker_path": str(path),
        })
    return payload


def discover_handoff_inventory(
    project_root: Path,
    *,
    scan_mode: str,
    explicit_path: Path | None = None,
) -> HandoffInventory:
    """Discover Handoff markdown candidates for a read-only scan mode."""
    layout = get_storage_layout(project_root)
    candidates: list[HandoffCandidate] = []
    if scan_mode == "active-selection":
        roots = (
            (layout.primary_active_dir, StorageLocation.PRIMARY_ACTIVE),
            (layout.legacy_active_dir, StorageLocation.LEGACY_ACTIVE),
            (layout.legacy_archive_dir, StorageLocation.LEGACY_ARCHIVE),
        )
    elif scan_mode == "history-search":
        roots = (
            (layout.primary_active_dir, StorageLocation.PRIMARY_ACTIVE),
            (layout.primary_archive_dir, StorageLocation.PRIMARY_ARCHIVE),
            (layout.legacy_active_dir, StorageLocation.LEGACY_ACTIVE),
            (layout.legacy_archive_dir, StorageLocation.LEGACY_ARCHIVE),
            (
                layout.previous_primary_hidden_archive_dir,
                StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
            ),
        )
    elif scan_mode == "explicit-path":
        if explicit_path is None:
            raise ValueError(
                "discover_handoff_inventory failed: explicit path is required. Got: None"
            )
        candidates.append(
            _candidate_for_path(
                project_root=layout.project_root,
                path=explicit_path,
                location=_location_for_path(layout, explicit_path),
                scan_mode=scan_mode,
            )
        )
        return HandoffInventory(
            project_root=layout.project_root,
            scan_mode=scan_mode,
            candidates=candidates,
        )
    elif scan_mode == "state-bridge":
        roots = (
            (layout.primary_state_dir, StorageLocation.PRIMARY_STATE),
            (layout.legacy_state_dir, StorageLocation.LEGACY_STATE),
        )
    else:
        raise ValueError(
            f"discover_handoff_inventory failed: unsupported scan mode. Got: {scan_mode!r:.100}"
        )

    for root, location in roots:
        if scan_mode == "state-bridge":
            candidates.extend(
                _discover_state_files(
                    project_root=layout.project_root,
                    root=root,
                    location=location,
                    scan_mode=scan_mode,
                )
            )
        else:
            candidates.extend(
                _discover_markdown(
                    project_root=layout.project_root,
                    root=root,
                    location=location,
                    scan_mode=scan_mode,
                )
            )
    candidates = _dedup_candidates_by_path(candidates)
    candidates.sort(key=lambda candidate: str(candidate.path))
    return HandoffInventory(
        project_root=layout.project_root,
        scan_mode=scan_mode,
        candidates=candidates,
    )


def eligible_active_candidates(inventory: HandoffInventory) -> list[HandoffCandidate]:
    """Return active-selection candidates in implicit load/list/distill order."""
    candidates = [
        candidate
        for candidate in inventory.candidates
        if candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
        and candidate.filename_timestamp is not None
    ]
    ordered = sorted(candidates, key=lambda candidate: _absolute_path_key(candidate.path))
    ordered = sorted(
        ordered,
        key=lambda candidate: _source_precedence(candidate.storage_location),
        reverse=True,
    )
    return sorted(
        ordered,
        key=lambda candidate: candidate.filename_timestamp or "",
        reverse=True,
    )


def eligible_history_candidates(inventory: HandoffInventory) -> list[HandoffCandidate]:
    """Return history-search candidates after same-content source-tier dedup."""
    candidates = [
        candidate
        for candidate in inventory.candidates
        if candidate.selection_eligibility == SelectionEligibility.ELIGIBLE
    ]
    ordered = sorted(candidates, key=lambda candidate: _absolute_path_key(candidate.path))
    ordered = sorted(
        ordered,
        key=lambda candidate: _history_source_precedence(candidate.storage_location),
        reverse=True,
    )
    winners: dict[str, HandoffCandidate] = {}
    passthrough: list[HandoffCandidate] = []
    for candidate in ordered:
        if candidate.content_sha256 is None:
            passthrough.append(candidate)
            continue
        winners.setdefault(candidate.content_sha256, candidate)
    return list(winners.values()) + passthrough


def _dedup_candidates_by_path(candidates: list[HandoffCandidate]) -> list[HandoffCandidate]:
    winners: dict[Path, HandoffCandidate] = {}
    for candidate in candidates:
        current = winners.get(candidate.path)
        if current is None or _candidate_specificity(candidate) > _candidate_specificity(current):
            winners[candidate.path] = candidate
    return list(winners.values())


def _candidate_specificity(candidate: HandoffCandidate) -> int:
    location_specificity = {
        StorageLocation.PRIMARY_STATE: 60,
        StorageLocation.LEGACY_STATE: 60,
        StorageLocation.STATE_LIKE_RESIDUE: 60,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE: 50,
        StorageLocation.PRIMARY_ARCHIVE: 45,
        StorageLocation.LEGACY_ARCHIVE: 45,
        StorageLocation.PRIMARY_ACTIVE: 30,
        StorageLocation.LEGACY_ACTIVE: 30,
        StorageLocation.UNKNOWN: 0,
    }[candidate.storage_location]
    eligibility_bonus = 1 if candidate.selection_eligibility != SelectionEligibility.SKIPPED else 0
    return location_specificity + eligibility_bonus


def _discover_markdown(
    *,
    project_root: Path,
    root: Path,
    location: StorageLocation,
    scan_mode: str,
) -> list[HandoffCandidate]:
    if not root.exists() or not root.is_dir():
        return []
    return [
        _candidate_for_path(
            project_root=project_root,
            path=path,
            location=location,
            scan_mode=scan_mode,
        )
        for path in sorted(root.rglob("*.md"))
    ]


def _discover_state_files(
    *,
    project_root: Path,
    root: Path,
    location: StorageLocation,
    scan_mode: str,
) -> list[HandoffCandidate]:
    if not root.exists() or not root.is_dir():
        return []
    return [
        _state_candidate_for_path(
            project_root=project_root,
            root=root,
            path=path,
            location=location,
            scan_mode=scan_mode,
        )
        for path in sorted(root.iterdir())
    ]


def _candidate_for_path(
    *,
    project_root: Path,
    path: Path,
    location: StorageLocation,
    scan_mode: str,
) -> HandoffCandidate:
    git_visibility = _git_visibility(project_root, path)
    fs_status = _fs_status(path)
    filename_timestamp = _filename_timestamp(path)
    content_sha256 = _content_sha256(path)
    document_profile = _document_profile(path, location=location, scan_mode=scan_mode)
    skip_reason = _skip_reason(root_for_location(project_root, location), path, location)
    if skip_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="skipped-handoff-artifact",
            selection_eligibility=SelectionEligibility.SKIPPED,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            filename_timestamp=filename_timestamp,
            content_sha256=content_sha256,
            document_profile=document_profile,
            skip_reason=skip_reason,
        )
    invalid_reason = _invalid_reason(path=path, location=location, scan_mode=scan_mode)
    if invalid_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="invalid-handoff-artifact",
            selection_eligibility=SelectionEligibility.INVALID,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            filename_timestamp=filename_timestamp,
            content_sha256=content_sha256,
            document_profile=document_profile,
            skip_reason=invalid_reason,
        )
    artifact_class = _artifact_class(location=location, path=path, git_visibility=git_visibility)
    if (
        scan_mode == "active-selection"
        and location == StorageLocation.LEGACY_ACTIVE
        and content_sha256 is not None
    ):
        consumed_status = _consumed_legacy_active_status(project_root, path, content_sha256)
        if consumed_status == "consumed":
            return HandoffCandidate(
                path=path.resolve(),
                storage_location=location,
                artifact_class="consumed-legacy-active",
                selection_eligibility=SelectionEligibility.NOT_ACTIVE_SELECTION_INPUT,
                source_git_visibility=git_visibility,
                source_fs_status=fs_status,
                filename_timestamp=filename_timestamp,
                content_sha256=content_sha256,
                document_profile=document_profile,
                skip_reason="legacy active source already consumed",
            )
        if consumed_status.startswith("registry-unreadable"):
            detail = consumed_status.partition(": ")[2]
            skip_reason = "consumed legacy active registry unreadable"
            if detail:
                skip_reason = f"{skip_reason}: {detail}"
            return HandoffCandidate(
                path=path.resolve(),
                storage_location=location,
                artifact_class="consumed-legacy-active-registry-unreadable",
                selection_eligibility=SelectionEligibility.BLOCKED_POLICY_CONFLICT,
                source_git_visibility=git_visibility,
                source_fs_status=fs_status,
                filename_timestamp=filename_timestamp,
                content_sha256=content_sha256,
                document_profile=document_profile,
                skip_reason=skip_reason,
            )
    if (
        location == StorageLocation.LEGACY_ACTIVE
        and content_sha256 is not None
        and _reviewed_legacy_active_opt_in_matches(project_root, path, content_sha256)
    ):
        artifact_class = "reviewed-runtime-migration-opt-in"
    eligibility, reason = _eligibility(
        location=location,
        artifact_class=artifact_class,
        git_visibility=git_visibility,
        scan_mode=scan_mode,
    )
    return HandoffCandidate(
        path=path.resolve(),
        storage_location=location,
        artifact_class=artifact_class,
        selection_eligibility=eligibility,
        source_git_visibility=git_visibility,
        source_fs_status=fs_status,
        filename_timestamp=filename_timestamp,
        content_sha256=content_sha256,
        document_profile=document_profile,
        skip_reason=reason,
    )


def _state_candidate_for_path(
    *,
    project_root: Path,
    root: Path,
    path: Path,
    location: StorageLocation,
    scan_mode: str,
) -> HandoffCandidate:
    git_visibility = _git_visibility(project_root, path)
    fs_status = _fs_status(path)
    skip_reason = _state_skip_reason(root, path)
    if skip_reason is not None:
        return HandoffCandidate(
            path=path.resolve(),
            storage_location=location,
            artifact_class="skipped-state-artifact",
            selection_eligibility=SelectionEligibility.SKIPPED,
            source_git_visibility=git_visibility,
            source_fs_status=fs_status,
            content_sha256=_content_sha256(path),
            document_profile="state",
            skip_reason=skip_reason,
        )
    if location == StorageLocation.PRIMARY_STATE:
        artifact_class = "primary-state-artifact"
    elif location == StorageLocation.LEGACY_STATE:
        artifact_class = "legacy-state-artifact"
    else:
        artifact_class = "unknown-state-artifact"
    return HandoffCandidate(
        path=path.resolve(),
        storage_location=location,
        artifact_class=artifact_class,
        selection_eligibility=SelectionEligibility.ELIGIBLE,
        source_git_visibility=git_visibility,
        source_fs_status=fs_status,
        content_sha256=_content_sha256(path),
        document_profile="state",
        skip_reason=None,
    )


def root_for_location(project_root: Path, location: StorageLocation) -> Path:
    layout = get_storage_layout(project_root)
    if location == StorageLocation.PRIMARY_ACTIVE:
        return layout.primary_active_dir
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return layout.primary_archive_dir
    if location == StorageLocation.PRIMARY_STATE:
        return layout.primary_state_dir
    if location == StorageLocation.LEGACY_ACTIVE:
        return layout.legacy_active_dir
    if location == StorageLocation.LEGACY_ARCHIVE:
        return layout.legacy_archive_dir
    if location == StorageLocation.LEGACY_STATE:
        return layout.legacy_state_dir
    if location == StorageLocation.STATE_LIKE_RESIDUE:
        return layout.legacy_active_dir
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return layout.previous_primary_hidden_archive_dir
    return layout.project_root


def _location_for_path(layout: StorageLayout, path: Path) -> StorageLocation:
    resolved = path.resolve()
    roots = (
        (layout.primary_state_dir, StorageLocation.PRIMARY_STATE),
        (
            layout.previous_primary_hidden_archive_dir,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        ),
        (layout.primary_archive_dir, StorageLocation.PRIMARY_ARCHIVE),
        (layout.primary_active_dir, StorageLocation.PRIMARY_ACTIVE),
        (layout.legacy_state_dir, StorageLocation.LEGACY_STATE),
        (layout.legacy_archive_dir, StorageLocation.LEGACY_ARCHIVE),
        (layout.legacy_active_dir, StorageLocation.LEGACY_ACTIVE),
    )
    for root, location in roots:
        if _is_relative_to(resolved, root.resolve()):
            return location
    return StorageLocation.UNKNOWN


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _artifact_class(*, location: StorageLocation, path: Path, git_visibility: str) -> str:
    if location == StorageLocation.PRIMARY_ACTIVE and git_visibility == "tracked-conflict":
        return "tracked-primary-active-source"
    if location == StorageLocation.PRIMARY_ACTIVE:
        return "primary-active-handoff"
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return "primary-archive-handoff"
    if location == StorageLocation.LEGACY_ARCHIVE:
        return "legacy-operational-archive"
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return "previous-primary-hidden-archive"
    if location == StorageLocation.PRIMARY_STATE:
        return "primary-state-artifact"
    if location == StorageLocation.LEGACY_STATE:
        return "legacy-state-artifact"
    if location == StorageLocation.STATE_LIKE_RESIDUE:
        return "state-like-residue"
    if location == StorageLocation.LEGACY_ACTIVE:
        if git_visibility in {"ignored", "untracked"} and _looks_like_current_contract(path):
            return "policy-conflict-artifact"
        if git_visibility == "tracked-conflict":
            return "tracked-durable-handoff-artifact"
        return "policy-conflict-artifact"
    return "unknown"


def _eligibility(
    *,
    location: StorageLocation,
    artifact_class: str,
    git_visibility: str,
    scan_mode: str,
) -> tuple[SelectionEligibility, str | None]:
    if scan_mode == "explicit-path":
        if location == StorageLocation.UNKNOWN:
            return (
                SelectionEligibility.NOT_EXPLICIT_PATH_INPUT,
                "explicit path is outside supported handoff storage roots",
            )
        if location == StorageLocation.PRIMARY_ACTIVE and git_visibility == "tracked-conflict":
            return (
                SelectionEligibility.BLOCKED_TRACKED_SOURCE,
                "tracked primary runtime source must not be moved or suppressed",
            )
        if location in {
            StorageLocation.PRIMARY_ACTIVE,
            StorageLocation.PRIMARY_ARCHIVE,
            StorageLocation.LEGACY_ACTIVE,
            StorageLocation.LEGACY_ARCHIVE,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        }:
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.NOT_EXPLICIT_PATH_INPUT,
            "storage location is not explicit-path handoff input",
        )
    if scan_mode == "state-bridge":
        if location in {StorageLocation.PRIMARY_STATE, StorageLocation.LEGACY_STATE}:
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.NOT_STATE_BRIDGE_INPUT,
            "storage location is not state-bridge input",
        )
    if scan_mode == "history-search":
        if location in {
            StorageLocation.PRIMARY_ACTIVE,
            StorageLocation.PRIMARY_ARCHIVE,
            StorageLocation.LEGACY_ACTIVE,
            StorageLocation.LEGACY_ARCHIVE,
            StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
        }:
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.BLOCKED_POLICY_CONFLICT,
            "legacy active markdown lacks accepted external origin proof",
        )
    if location == StorageLocation.PRIMARY_ACTIVE:
        if git_visibility == "tracked-conflict":
            return (
                SelectionEligibility.BLOCKED_TRACKED_SOURCE,
                "tracked primary runtime source must not be moved or suppressed",
            )
        return SelectionEligibility.ELIGIBLE, None
    if location == StorageLocation.LEGACY_ACTIVE:
        if artifact_class == "reviewed-runtime-migration-opt-in":
            return SelectionEligibility.ELIGIBLE, None
        return (
            SelectionEligibility.BLOCKED_POLICY_CONFLICT,
            "legacy active markdown lacks accepted external origin proof",
        )
    return (
        SelectionEligibility.NOT_ACTIVE_SELECTION_INPUT,
        "storage location is not active-selection input",
    )


def _looks_like_current_contract(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---", 4)
    if end == -1:
        return False
    keys = set()
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            keys.add(line.split(":", 1)[0].strip())
    return {"project", "created_at", "session_id", "type"} <= keys


def _skip_reason(root: Path, path: Path, location: StorageLocation) -> str | None:
    if path.name.startswith("."):
        return "hidden_basename"
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "path_escape"
    if ".session-state" in relative.parts:
        return "state_directory"
    if path.is_symlink():
        return "symlink"
    if path.parent != root:
        return "nested_file"
    if location == StorageLocation.LEGACY_ARCHIVE:
        return None
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return None
    return None


def _state_skip_reason(root: Path, path: Path) -> str | None:
    if path.name.startswith("."):
        return "hidden_basename"
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "path_escape"
    if path.is_symlink():
        return "symlink"
    if path.parent != root or len(relative.parts) != 1:
        return "nested_file"
    if not path.name.startswith("handoff-") or path.suffix not in {"", ".json"}:
        return "not_state_artifact"
    return None


def _invalid_reason(*, path: Path, location: StorageLocation, scan_mode: str) -> str | None:
    if location == StorageLocation.UNKNOWN:
        return None
    if location in {StorageLocation.PRIMARY_STATE, StorageLocation.LEGACY_STATE}:
        return None
    if scan_mode == "active-selection" and _filename_timestamp(path) is None:
        return "invalid_filename_timestamp"
    if scan_mode in {"history-search", "explicit-path"} and _archive_history_location(location):
        return None
    if not _looks_like_current_contract(path):
        return "invalid_document"
    return None


def _archive_history_location(location: StorageLocation) -> bool:
    return location in {
        StorageLocation.PRIMARY_ARCHIVE,
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }


def _filename_timestamp(path: Path) -> str | None:
    match = FILENAME_TIMESTAMP_RE.match(path.name)
    if match is None:
        return None
    return match.group("timestamp")


def _source_precedence(location: StorageLocation) -> int:
    if location == StorageLocation.PRIMARY_ACTIVE:
        return 2
    if location == StorageLocation.LEGACY_ACTIVE:
        return 1
    return 0


def _history_source_precedence(location: StorageLocation) -> int:
    if location == StorageLocation.PRIMARY_ACTIVE:
        return 5
    if location == StorageLocation.PRIMARY_ARCHIVE:
        return 4
    if location == StorageLocation.LEGACY_ACTIVE:
        return 3
    if location == StorageLocation.LEGACY_ARCHIVE:
        return 2
    if location == StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE:
        return 1
    return 0


def _absolute_path_key(path: Path) -> str:
    return str(path.resolve())


def _document_profile(path: Path, *, location: StorageLocation, scan_mode: str) -> str | None:
    if location in {StorageLocation.PRIMARY_STATE, StorageLocation.LEGACY_STATE}:
        return "state"
    if _looks_like_current_contract(path):
        return "current_contract"
    if scan_mode in {"history-search", "explicit-path"} and _archive_history_location(location):
        return "historical_archive"
    return None


def _fs_status(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if not path.exists():
        return "missing"
    if path.is_file():
        return "regular-file"
    if path.is_dir():
        return "directory"
    return "non-regular"


def _git_visibility(project_root: Path, path: Path) -> str:
    if not _inside_git_worktree(project_root):
        return "not-git-repo"
    project = project_root.resolve()
    resolved = path.resolve()
    if not _is_relative_to(resolved, project):
        return "outside-project"
    rel = resolved.relative_to(project).as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode == 0:
        return "tracked-conflict"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", rel],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if ignored.returncode == 0:
        return "ignored"
    return "untracked"


def _reviewed_legacy_active_opt_in_matches(
    project_root: Path,
    path: Path,
    content_sha256: str,
) -> bool:
    manifest = project_root / LEGACY_ACTIVE_OPT_IN_MANIFEST
    for row in _read_markdown_table(manifest):
        if _row_cell(row, "project_relative_path") != path.relative_to(project_root).as_posix():
            continue
        if _row_cell(row, "raw_byte_sha256") != content_sha256:
            continue
        if _row_cell(row, "source_root") != "project_root":
            continue
        if _row_cell(row, "storage_location") != StorageLocation.LEGACY_ACTIVE:
            continue
        if not _row_cell(row, "reviewer") or not _row_cell(row, "reason"):
            continue
        return True
    return False


def _consumed_legacy_active_status(
    project_root: Path,
    path: Path,
    content_sha256: str,
) -> str:
    registry_path = (
        get_storage_layout(project_root).primary_state_dir / "consumed-legacy-active.json"
    )
    try:
        payload = _read_json_object_primitive(registry_path, missing={"entries": []})
    except (OSError, ValueError) as exc:
        return f"registry-unreadable: {exc!r}"
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return "registry-unreadable: ValueError('entries field is not a list')"
    expected = {
        "source_root": "project_root",
        "project_relative_source_path": path.relative_to(project_root).as_posix(),
        "storage_location": StorageLocation.LEGACY_ACTIVE,
        "source_content_sha256": content_sha256,
    }
    for entry in entries:
        if isinstance(entry, dict) and _registry_key(entry) == expected:
            return "consumed"
    return "not-consumed"


def _read_markdown_table(path: Path) -> list[dict[str, str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_clean_table_cell(cell) for cell in stripped.strip("|").split("|")]
        if headers is None:
            headers = cells
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def _clean_table_cell(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == "`" and stripped[-1] == "`":
        return stripped[1:-1]
    return stripped


def _row_cell(row: dict[str, str], key: str) -> str:
    return row.get(key, "").strip()


def _registry_key(entry: dict[str, object]) -> dict[str, str]:
    return {
        "source_root": str(entry.get("source_root", "")),
        "project_relative_source_path": str(entry.get("project_relative_source_path", "")),
        "storage_location": str(entry.get("storage_location", "")),
        "source_content_sha256": str(entry.get("source_content_sha256", "")),
    }


def _inside_git_worktree(project_root: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"
