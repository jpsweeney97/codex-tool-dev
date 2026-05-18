"""Tests for ticket_stage_models.py — stage boundary input models."""
from __future__ import annotations

import pytest

from scripts.ticket_stage_models import (
    ClassifyInput,
    ExecuteInput,
    PayloadError,
    PlanInput,
    PreflightInput,
)


class TestPayloadError:
    def test_carries_code_and_state(self):
        exc = PayloadError("missing field: action", code="need_fields", state="need_fields")
        assert str(exc) == "missing field: action"
        assert exc.code == "need_fields"
        assert exc.state == "need_fields"

    def test_parse_error_variant(self):
        exc = PayloadError("args must be a dict", code="parse_error", state="escalate")
        assert exc.code == "parse_error"
        assert exc.state == "escalate"


class TestClassifyInput:
    def test_valid_payload(self):
        inp = ClassifyInput.from_payload({
            "action": "create",
            "args": {"ticket_id": "T-001"},
            "session_id": "sess-1",
        })
        assert inp.action == "create"
        assert inp.args == {"ticket_id": "T-001"}
        assert inp.session_id == "sess-1"

    def test_defaults(self):
        inp = ClassifyInput.from_payload({
            "action": "create",
            "session_id": "sess-1",
        })
        assert inp.args == {}

    def test_empty_defaults_for_missing_strings(self):
        """Preserves current _dispatch() behavior: missing action/session_id default to ''."""
        inp = ClassifyInput.from_payload({})
        assert inp.action == ""
        assert inp.session_id == ""
        assert inp.args == {}

    def test_args_wrong_type_raises_parse_error(self):
        with pytest.raises(PayloadError) as exc_info:
            ClassifyInput.from_payload({
                "action": "create",
                "args": "not a dict",
                "session_id": "sess-1",
            })
        assert exc_info.value.code == "parse_error"
        assert exc_info.value.state == "escalate"

    def test_extra_keys_ignored(self):
        inp = ClassifyInput.from_payload({
            "action": "create",
            "args": {},
            "session_id": "sess-1",
            "extra_field": "ignored",
            "hook_injected": True,
        })
        assert inp.action == "create"

    def test_frozen(self):
        inp = ClassifyInput.from_payload({"action": "create", "session_id": "s"})
        with pytest.raises(AttributeError):
            inp.action = "update"


class TestPlanInput:
    def test_valid_payload(self):
        inp = PlanInput.from_payload({
            "intent": "create",
            "fields": {"title": "Test"},
            "session_id": "sess-1",
        })
        assert inp.intent == "create"
        assert inp.fields == {"title": "Test"}
        assert inp.session_id == "sess-1"

    def test_intent_falls_back_to_action(self):
        inp = PlanInput.from_payload({
            "action": "update",
            "session_id": "sess-1",
        })
        assert inp.intent == "update"

    def test_intent_prefers_intent_over_action(self):
        inp = PlanInput.from_payload({
            "intent": "create",
            "action": "update",
            "session_id": "sess-1",
        })
        assert inp.intent == "create"

    def test_intent_ignores_malformed_action_when_intent_present(self):
        """Lazy fallback: non-string action is not validated when intent is present."""
        inp = PlanInput.from_payload({
            "intent": "create",
            "action": 42,
            "session_id": "sess-1",
        })
        assert inp.intent == "create"

    def test_defaults(self):
        inp = PlanInput.from_payload({})
        assert inp.intent == ""
        assert inp.fields == {}
        assert inp.session_id == ""

    def test_fields_wrong_type_raises_parse_error(self):
        with pytest.raises(PayloadError) as exc_info:
            PlanInput.from_payload({
                "intent": "create",
                "fields": ["not", "a", "dict"],
                "session_id": "sess-1",
            })
        assert exc_info.value.code == "parse_error"

    def test_frozen(self):
        inp = PlanInput.from_payload({"session_id": "s"})
        with pytest.raises(AttributeError):
            inp.intent = "update"


class TestPreflightInput:
    def test_valid_payload(self):
        inp = PreflightInput.from_payload({
            "action": "create",
            "ticket_id": "T-20260302-01",
            "session_id": "sess-1",
            "classify_confidence": 0.95,
            "classify_intent": "create",
            "dedup_fingerprint": "abc123",
            "target_fingerprint": "def456",
            "fields": {"title": "Test"},
            "duplicate_of": "T-20260301-01",
            "dedup_override": True,
            "dependency_override": True,
            "hook_injected": True,
        })
        assert inp.action == "create"
        assert inp.ticket_id == "T-20260302-01"
        assert inp.classify_confidence == 0.95
        assert inp.classify_intent == "create"
        assert inp.dedup_fingerprint == "abc123"
        assert inp.target_fingerprint == "def456"
        assert inp.fields == {"title": "Test"}
        assert inp.duplicate_of == "T-20260301-01"
        assert inp.dedup_override is True
        assert inp.dependency_override is True
        assert inp.hook_injected is True

    def test_defaults(self):
        inp = PreflightInput.from_payload({})
        assert inp.action == ""
        assert inp.ticket_id is None
        assert inp.session_id == ""
        assert inp.classify_confidence == 0.0
        assert inp.classify_intent == ""
        assert inp.dedup_fingerprint is None
        assert inp.target_fingerprint is None
        assert inp.fields is None
        assert inp.duplicate_of is None
        assert inp.dedup_override is False
        assert inp.dependency_override is False
        assert inp.hook_injected is False

    def test_classify_confidence_accepts_int(self):
        inp = PreflightInput.from_payload({"classify_confidence": 1})
        assert inp.classify_confidence == 1.0
        assert isinstance(inp.classify_confidence, float)

    def test_classify_confidence_wrong_type_raises(self):
        with pytest.raises(PayloadError) as exc_info:
            PreflightInput.from_payload({"classify_confidence": "high"})
        assert exc_info.value.code == "parse_error"

    def test_fields_wrong_type_raises(self):
        with pytest.raises(PayloadError) as exc_info:
            PreflightInput.from_payload({"fields": "not a dict"})
        assert exc_info.value.code == "parse_error"

    def test_frozen(self):
        inp = PreflightInput.from_payload({})
        with pytest.raises(AttributeError):
            inp.action = "update"


class TestExecuteInput:
    def test_valid_payload(self):
        inp = ExecuteInput.from_payload({
            "action": "update",
            "ticket_id": "T-20260302-01",
            "fields": {"priority": "high"},
            "session_id": "sess-1",
            "dedup_override": True,
            "dependency_override": True,
            "target_fingerprint": "abc123",
            "autonomy_config": {"mode": "auto_audit", "max_creates": 5},
            "hook_injected": True,
            "hook_request_origin": "user",
            "classify_intent": "update",
            "classify_confidence": 0.95,
            "dedup_fingerprint": "def456",
        })
        assert inp.action == "update"
        assert inp.ticket_id == "T-20260302-01"
        assert inp.fields == {"priority": "high"}
        assert inp.session_id == "sess-1"
        assert inp.dedup_override is True
        assert inp.dependency_override is True
        assert inp.target_fingerprint == "abc123"
        assert inp.autonomy_config_data == {"mode": "auto_audit", "max_creates": 5}
        assert inp.hook_injected is True
        assert inp.hook_request_origin == "user"
        assert inp.classify_intent == "update"
        assert inp.classify_confidence == 0.95
        assert inp.dedup_fingerprint == "def456"

    def test_defaults(self):
        inp = ExecuteInput.from_payload({})
        assert inp.action == ""
        assert inp.ticket_id is None
        assert inp.fields == {}
        assert inp.session_id == ""
        assert inp.dedup_override is False
        assert inp.dependency_override is False
        assert inp.target_fingerprint is None
        assert inp.autonomy_config_data is None
        assert inp.hook_injected is False
        assert inp.hook_request_origin is None
        assert inp.classify_intent is None
        assert inp.classify_confidence is None
        assert inp.dedup_fingerprint is None

    def test_classify_confidence_none_when_absent(self):
        """Execute uses None (not 0.0) for missing classify_confidence."""
        inp = ExecuteInput.from_payload({})
        assert inp.classify_confidence is None

    def test_classify_confidence_accepts_float(self):
        inp = ExecuteInput.from_payload({"classify_confidence": 0.95})
        assert inp.classify_confidence == 0.95

    def test_autonomy_config_non_dict_coerced_to_none(self):
        """Non-dict autonomy_config is silently ignored (preserves pre-A-002 behavior)."""
        inp = ExecuteInput.from_payload({"autonomy_config": "not a dict"})
        assert inp.autonomy_config_data is None

    def test_autonomy_config_list_coerced_to_none(self):
        inp = ExecuteInput.from_payload({"autonomy_config": [1, 2, 3]})
        assert inp.autonomy_config_data is None

    def test_fields_wrong_type_raises(self):
        with pytest.raises(PayloadError) as exc_info:
            ExecuteInput.from_payload({"fields": 42})
        assert exc_info.value.code == "parse_error"

    def test_frozen(self):
        inp = ExecuteInput.from_payload({})
        with pytest.raises(AttributeError):
            inp.action = "close"
