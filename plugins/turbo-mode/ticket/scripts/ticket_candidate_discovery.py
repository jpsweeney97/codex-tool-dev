"""Deterministic Ticket autonomy candidate discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.ticket_autonomy_ids import sha256_fingerprint
from scripts.ticket_autonomy_runtime import (
    CandidateMutation,
    candidate_mapping_errors,
    candidate_mutation_from_mapping,
)
from scripts.ticket_mutation_identity import candidate_mutation_payload


def _value_error(operation: str, reason: str, value: object) -> ValueError:
    return ValueError(f"{operation} failed: {reason}. Got: {value!r:.100}")


@dataclass(frozen=True)
class InvalidCandidateMappingError:
    key: str
    index: int
    errors: tuple[str, ...]


class InvalidCandidateMutations(ValueError):
    def __init__(self, errors: Sequence[InvalidCandidateMappingError]) -> None:
        self.errors = tuple(errors)
        super().__init__(
            "candidate discovery failed: explicit candidate payload is invalid. "
            f"Got: {self.as_payload()!r:.100}"
        )

    def as_payload(self) -> list[dict[str, object]]:
        return [
            {"key": error.key, "index": error.index, "errors": list(error.errors)}
            for error in self.errors
        ]


def _candidate_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    return candidate_mutation_from_mapping(item)


def _append_candidate(
    candidates: list[CandidateMutation],
    seen: set[str],
    candidate: CandidateMutation,
) -> None:
    key = sha256_fingerprint(
        candidate_mutation_payload(
            ticket_id=candidate.ticket_id,
            action=candidate.action,
            target=candidate.target,
            proposed_change=candidate.proposed_change,
            expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
            evidence_summary=candidate.evidence_summary,
        )
    )
    if key in seen:
        return
    seen.add(key)
    candidates.append(candidate)


def _append_structured_candidates(
    candidates: list[CandidateMutation],
    seen: set[str],
    turn_context: Mapping[str, object],
) -> None:
    invalid: list[InvalidCandidateMappingError] = []
    valid: list[CandidateMutation] = []
    for key in ("candidate_mutations", "update_candidates", "capture_candidates"):
        raw_items = turn_context.get(key, [])
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            invalid.append(
                InvalidCandidateMappingError(
                    key=key,
                    index=-1,
                    errors=("candidate list must be an array",),
                )
            )
            continue
        for index, item in enumerate(raw_items):
            if not isinstance(item, Mapping):
                invalid.append(
                    InvalidCandidateMappingError(
                        key=key,
                        index=index,
                        errors=("candidate item must be an object",),
                    )
                )
                continue
            errors = tuple(candidate_mapping_errors(item))
            if errors:
                invalid.append(InvalidCandidateMappingError(key=key, index=index, errors=errors))
                continue
            candidate = _candidate_from_mapping(item)
            if candidate is None:
                invalid.append(
                    InvalidCandidateMappingError(
                        key=key,
                        index=index,
                        errors=("candidate item failed target shape construction",),
                    )
                )
                continue
            valid.append(candidate)
    if invalid:
        raise InvalidCandidateMutations(invalid)
    for candidate in valid:
        _append_candidate(candidates, seen, candidate)


def discover_candidate_mutations(
    turn_context: Mapping[str, object],
    tickets_dir: Path,
) -> tuple[CandidateMutation, ...]:
    """Extract deterministic Ticket mutation candidates from turn context.

    Args:
        turn_context: Strict turn context supplied by Codex/host runtime.
        tickets_dir: Active Ticket directory. Path-only signals are read-only
            hints in this migration slice and do not emit write candidates.

    Returns:
        Candidate mutations in deterministic discovery order.

    Raises:
        ValueError: If `turn_context` is not object-shaped.
        InvalidCandidateMutations: If explicit candidate arrays are malformed.
    """
    del tickets_dir
    if not isinstance(turn_context, Mapping):
        raise _value_error(
            "discover candidate mutations",
            "turn_context must be an object",
            turn_context,
        )

    candidates: list[CandidateMutation] = []
    seen: set[str] = set()
    _append_structured_candidates(candidates, seen, turn_context)
    return tuple(candidates)
