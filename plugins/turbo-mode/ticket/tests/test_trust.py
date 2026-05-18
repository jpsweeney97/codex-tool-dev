"""Tests for shared execute trust validation helpers."""
from __future__ import annotations

from scripts.ticket_trust import collect_trust_triple_errors


class TestCollectTrustTripleErrors:
    def test_valid_trust_triple_returns_empty_list(self) -> None:
        assert collect_trust_triple_errors(True, "user", "session-123") == []

    def test_missing_hook_injected_reported(self) -> None:
        assert collect_trust_triple_errors(False, "user", "session-123") == [
            "hook_injected=False",
        ]

    def test_missing_hook_request_origin_reported(self) -> None:
        assert collect_trust_triple_errors(True, None, "session-123") == [
            "hook_request_origin missing",
        ]

    def test_empty_session_id_reported(self) -> None:
        assert collect_trust_triple_errors(True, "user", "") == [
            "session_id empty",
        ]

    def test_all_missing_errors_preserve_order(self) -> None:
        assert collect_trust_triple_errors(False, None, "") == [
            "hook_injected=False",
            "hook_request_origin missing",
            "session_id empty",
        ]
