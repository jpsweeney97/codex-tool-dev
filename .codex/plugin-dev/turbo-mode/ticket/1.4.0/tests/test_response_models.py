"""Tests for EngineResponse — engine output envelope invariants."""
from __future__ import annotations

import pytest

from scripts.ticket_engine_core import EngineResponse


class TestEngineResponseInvariant:
    """EngineResponse enforces error_code on non-success states."""

    _OK_STATES = frozenset({
        "ok", "ok_create", "ok_update", "ok_close", "ok_close_archived", "ok_reopen",
    })

    def test_success_state_allows_no_error_code(self):
        for state in self._OK_STATES:
            resp = EngineResponse(state=state, message="ok")
            assert resp.error_code is None

    def test_success_state_rejects_error_code(self):
        with pytest.raises(ValueError, match="error_code must be None"):
            EngineResponse(state="ok", message="ok", error_code="intent_mismatch")

    def test_non_success_state_requires_error_code(self):
        with pytest.raises(ValueError, match="error_code is required"):
            EngineResponse(state="escalate", message="bad")

    def test_non_success_state_accepts_error_code(self):
        resp = EngineResponse(state="escalate", message="bad", error_code="intent_mismatch")
        assert resp.error_code == "intent_mismatch"

    def test_need_fields_state_requires_error_code(self):
        resp = EngineResponse(state="need_fields", message="missing", error_code="need_fields")
        assert resp.error_code == "need_fields"

    def test_duplicate_candidate_state_requires_error_code(self):
        resp = EngineResponse(state="duplicate_candidate", message="dup", error_code="duplicate_candidate")
        assert resp.error_code == "duplicate_candidate"
