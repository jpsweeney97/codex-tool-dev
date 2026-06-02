"""Tests for deterministic autonomy IDs and fingerprints."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

import pytest
from scripts.ticket_autonomy_ids import (
    canonical_json,
    make_event_id,
    make_mutation_id,
    sha256_fingerprint,
)

HEX32 = re.compile(r"^[0-9a-f]{32}$")


def _digest32(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:32]


def test_canonical_json_uses_sorted_keys_compact_separators_and_ascii() -> None:
    value = {"z": "é", "a": 1, "nested": {"b": True, "a": None}}

    assert canonical_json(value) == '{"a":1,"nested":{"a":null,"b":true},"z":"\\u00e9"}'
    assert json.loads(canonical_json(value)) == value


def test_canonical_json_normalizes_path_like_strings_with_forward_slashes() -> None:
    value = {
        "path": "plugins\\turbo-mode\\ticket\\scripts",
        "paths": ["docs\\tickets\\T-1.md"],
    }

    assert canonical_json(value) == (
        '{"path":"plugins/turbo-mode/ticket/scripts","paths":["docs/tickets/T-1.md"]}'
    )


def test_canonical_json_rejects_unsupported_inputs() -> None:
    with pytest.raises(ValueError, match="canonical json failed"):
        canonical_json({"path": Path("docs/tickets")})

    with pytest.raises(ValueError, match="canonical json failed"):
        canonical_json({"items": {"not", "json"}})


def test_sha256_fingerprint_uses_full_canonical_json_digest() -> None:
    value = {"b": 2, "a": "docs\\tickets"}

    expected = hashlib.sha256(
        b'{"a":"docs/tickets","b":2}'
    ).hexdigest()

    assert sha256_fingerprint(value) == expected
    assert len(sha256_fingerprint(value)) == 64


def test_mutation_id_uses_expected_prefix_and_digest() -> None:
    payload = {
        "schema": "codex.ticket.mutation.v1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "mutation_fingerprint": "mutfp",
        "evidence_fingerprint": "evfp",
    }

    mutation_id = make_mutation_id(**payload)

    assert mutation_id == f"mut_{_digest32(payload)}"
    assert HEX32.fullmatch(mutation_id.removeprefix("mut_"))


def test_event_id_uses_expected_prefix_and_digest() -> None:
    payload = {
        "schema": "codex.ticket.event.v1",
        "event_type": "ticket_written",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "mutation_id": "mut_abc",
        "status": "applied",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "payload_fingerprint": "payloadfp",
    }

    event_id = make_event_id(**payload)

    assert event_id == f"evt_{_digest32(payload)}"
    assert HEX32.fullmatch(event_id.removeprefix("evt_"))


def test_ids_are_reproducible_for_same_inputs() -> None:
    kwargs = {
        "schema": "codex.ticket.mutation.v1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "action": "create",
        "ticket_id": None,
        "mutation_fingerprint": "mutfp",
        "evidence_fingerprint": "evfp",
    }

    assert make_mutation_id(**kwargs) == make_mutation_id(**kwargs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("thread_id", "thread-2"),
        ("turn_id", "turn-2"),
        ("action", "close"),
        ("ticket_id", "T-20260527-02"),
        ("mutation_fingerprint", "mutfp-2"),
        ("evidence_fingerprint", "evfp-2"),
    ],
)
def test_mutation_id_changes_when_inputs_change(field: str, value: str) -> None:
    base = {
        "schema": "codex.ticket.mutation.v1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "mutation_fingerprint": "mutfp",
        "evidence_fingerprint": "evfp",
    }
    changed = dict(base, **{field: value})

    assert make_mutation_id(**base) != make_mutation_id(**changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("thread_id", "thread-2"),
        ("turn_id", "turn-2"),
        ("mutation_id", "mut_other"),
        ("status", "failed"),
        ("action", "close"),
        ("ticket_id", "T-20260527-02"),
        ("payload_fingerprint", "payloadfp-2"),
    ],
)
def test_event_id_changes_when_inputs_change(field: str, value: str) -> None:
    base = {
        "schema": "codex.ticket.event.v1",
        "event_type": "mutation_attempt",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "mutation_id": "mut_abc",
        "status": "applied",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "payload_fingerprint": "payloadfp",
    }
    changed = dict(base, **{field: value})

    assert make_event_id(**base) != make_event_id(**changed)


def test_thread_id_scopes_ids_even_when_turn_id_matches() -> None:
    common = {
        "schema": "codex.ticket.mutation.v1",
        "turn_id": "turn-1",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "mutation_fingerprint": "mutfp",
        "evidence_fingerprint": "evfp",
    }
    mutation_1 = make_mutation_id(thread_id="thread-1", **common)
    mutation_2 = make_mutation_id(thread_id="thread-2", **common)

    event_common = {
        "schema": "codex.ticket.event.v1",
        "event_type": "mutation_attempt",
        "turn_id": "turn-1",
        "status": "applied",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "payload_fingerprint": "payloadfp",
    }
    assert mutation_1 != mutation_2
    assert make_event_id(thread_id="thread-1", mutation_id=mutation_1, **event_common) != (
        make_event_id(thread_id="thread-2", mutation_id=mutation_2, **event_common)
    )


def test_timestamp_is_not_an_id_input() -> None:
    for func in (make_mutation_id, make_event_id):
        assert "timestamp" not in inspect.signature(func).parameters
