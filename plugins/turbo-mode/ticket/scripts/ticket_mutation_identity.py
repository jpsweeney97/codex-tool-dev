"""Canonical mutation identity helpers for Ticket autonomy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from scripts.ticket_autonomy_ids import make_mutation_id, sha256_fingerprint


@dataclass(frozen=True, slots=True)
class CandidateMutationIdentity:
    """Deterministic identity for one candidate mutation."""

    mutation_id: str
    mutation_fingerprint: str
    evidence_fingerprint: str


def candidate_mutation_payload(
    *,
    ticket_id: str | None,
    action: str,
    proposed_change: Mapping[str, object],
    ticket_change_scope: str,
    target_fingerprint: str | None,
) -> dict[str, object]:
    """Return the canonical payload used for mutation identity."""
    return {
        "ticket_id": ticket_id,
        "action": action,
        "proposed_change": dict(proposed_change),
        "ticket_change_scope": ticket_change_scope,
        "target_fingerprint": target_fingerprint,
    }


def make_candidate_mutation_identity(
    *,
    thread_id: str,
    turn_id: str,
    ticket_id: str | None,
    action: str,
    proposed_change: Mapping[str, object],
    ticket_change_scope: str,
    target_fingerprint: str | None,
    evidence: object,
) -> CandidateMutationIdentity:
    """Calculate deterministic identity for one candidate mutation.

    This helper is calculation-only. It hashes the supplied target fingerprint
    but does not decide whether a missing target fingerprint is acceptable.
    Runtime and gateway callers own that policy.
    """
    mutation_fingerprint = sha256_fingerprint(
        candidate_mutation_payload(
            ticket_id=ticket_id,
            action=action,
            proposed_change=proposed_change,
            ticket_change_scope=ticket_change_scope,
            target_fingerprint=target_fingerprint,
        )
    )
    evidence_fingerprint = sha256_fingerprint(evidence)
    mutation_id = make_mutation_id(
        schema="codex.ticket.mutation.v1",
        thread_id=thread_id,
        turn_id=turn_id,
        action=action,
        ticket_id=ticket_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    return CandidateMutationIdentity(
        mutation_id=mutation_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
