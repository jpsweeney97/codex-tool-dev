"""Chain-state inventory, diagnostics, read, and lifecycle operations."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from turbo_mode_handoff_runtime import storage_primitives as _storage_primitives

# StorageLocation is the intentional shared bridge type: storage_authority is the
# discovery authority that names locations, and chain_state consumes that
# classification. This one-way edge (chain_state -> storage_authority) is by
# design and must stay one-way — storage_authority must never import chain_state
# (that would re-introduce the cross-module cycle the reseam removed).
from turbo_mode_handoff_runtime.storage_authority import StorageLocation
from turbo_mode_handoff_runtime.storage_inspection import fs_status, git_visibility
from turbo_mode_handoff_runtime.storage_layout import StorageLayout, get_storage_layout
from turbo_mode_handoff_runtime.storage_primitives import (
    sha256_regular_file_or_none as _content_sha256,
)
from turbo_mode_handoff_runtime.storage_primitives import (
    write_json_atomic as _write_json_atomic,
)


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


_CHAIN_STATE_TTL_SECONDS = 24 * 60 * 60


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
        isinstance(entry, dict) and entry.get("stable_key") == stable_key for entry in entries
    ):
        entries.append(
            {
                "stable_key": stable_key,
                "reason": reason,
                "marked_at": marked_at,
                "transaction_id": transaction_id,
                "lexical_path": candidate["lexical_path"],
                "resolved_path": candidate["resolved_path"],
            }
        )
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
        isinstance(entry, dict) and entry.get("stable_key") == stable_key for entry in entries
    ):
        entries.append(
            {
                "stable_key": stable_key,
                "reason": "continued into primary chain state",
                "marked_at": now,
                "transaction_id": transaction_id,
                "lexical_path": candidate["lexical_path"],
                "resolved_path": candidate["resolved_path"],
            }
        )
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
        if candidate["validation_status"] == "expired" and candidate["marker_status"] != "consumed"
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
        "source_git_visibility": git_visibility(layout.project_root, path),
        "source_fs_status": fs_status(path),
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
    if any(isinstance(entry, dict) and entry.get("stable_key") == stable_key for entry in entries):
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
    if age_seconds is None or age_seconds <= _CHAIN_STATE_TTL_SECONDS:
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
    if archive_path.startswith(_storage_primitives.LEGACY_CONSUMED_PREFIX):
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
    # Deliberately NOT storage_primitives.read_json_object: chain-state marker
    # reads must fail as ChainStateDiagnosticError (an operator-recovery
    # contract), not ValueError, and a missing marker is normal (-> {}), not an
    # error. Do not "simplify" to the shared primitive: it would change the
    # error type and break the recovery contract.
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ChainStateDiagnosticError(
            {
                "error": {
                    "code": "chain-state-marker-unreadable",
                    "message": f"chain-state marker unreadable: {path}",
                },
                "marker_path": str(path),
            }
        ) from exc
    if not isinstance(payload, dict):
        raise ChainStateDiagnosticError(
            {
                "error": {
                    "code": "chain-state-marker-malformed",
                    "message": f"chain-state marker malformed: {path}",
                },
                "marker_path": str(path),
            }
        )
    return payload
