"""Tests for ticket field schema validation."""
from __future__ import annotations

from scripts.ticket_validate import validate_fields


class TestValidateFields:
    """Shared validation for writable ticket fields."""

    # --- priority ---
    def test_valid_priorities(self):
        for p in ("critical", "high", "medium", "low"):
            errors = validate_fields({"priority": p})
            assert not errors, f"priority={p} should be valid"

    def test_invalid_priority_rejected(self):
        errors = validate_fields({"priority": "urgent"})
        assert any("priority" in e for e in errors)

    def test_priority_wrong_type_rejected(self):
        errors = validate_fields({"priority": 1})
        assert any("priority" in e for e in errors)

    # --- status ---
    def test_valid_statuses(self):
        for s in ("open", "in_progress", "blocked", "done", "wontfix"):
            errors = validate_fields({"status": s})
            assert not errors, f"status={s} should be valid"

    def test_invalid_status_rejected(self):
        errors = validate_fields({"status": "pending"})
        assert any("status" in e for e in errors)

    # --- resolution ---
    def test_valid_resolutions(self):
        for r in ("done", "wontfix"):
            errors = validate_fields({"resolution": r})
            assert not errors, f"resolution={r} should be valid"

    def test_invalid_resolution_rejected(self):
        errors = validate_fields({"resolution": "cancelled"})
        assert any("resolution" in e for e in errors)

    # --- title/problem ---
    def test_title_wrong_type_rejected(self):
        errors = validate_fields({"title": 123})
        assert any("title" in e for e in errors)

    def test_problem_wrong_type_rejected(self):
        errors = validate_fields({"problem": ["not", "a", "string"]})
        assert any("problem" in e for e in errors)

    # --- tags ---
    def test_valid_tags(self):
        errors = validate_fields({"tags": ["bug", "urgent"]})
        assert not errors

    def test_tags_scalar_rejected(self):
        errors = validate_fields({"tags": "bug"})
        assert any("tags" in e for e in errors)

    def test_tags_non_string_elements_rejected(self):
        errors = validate_fields({"tags": ["bug", 42]})
        assert any("tags" in e for e in errors)

    # --- blocked_by ---
    def test_valid_blocked_by(self):
        errors = validate_fields({"blocked_by": ["T-20260302-01"]})
        assert not errors

    def test_blocked_by_scalar_rejected(self):
        errors = validate_fields({"blocked_by": "T-20260302-01"})
        assert any("blocked_by" in e for e in errors)

    # --- blocks ---
    def test_valid_blocks(self):
        errors = validate_fields({"blocks": ["T-20260302-02"]})
        assert not errors

    def test_blocks_scalar_rejected(self):
        errors = validate_fields({"blocks": "T-20260302-02"})
        assert any("blocks" in e for e in errors)

    # --- source ---
    def test_valid_source(self):
        errors = validate_fields({"source": {"type": "ad-hoc", "ref": "", "session": "s"}})
        assert not errors

    def test_source_non_dict_rejected(self):
        errors = validate_fields({"source": "ad-hoc"})
        assert any("source" in e for e in errors)

    def test_source_non_string_values_rejected(self):
        errors = validate_fields({"source": {"type": 123, "ref": "", "session": "s"}})
        assert any("source" in e for e in errors)

    # --- defer ---
    def test_valid_defer(self):
        errors = validate_fields({"defer": {"active": True, "reason": "blocked on X", "deferred_at": "2026-03-10"}})
        assert not errors

    def test_defer_non_dict_rejected(self):
        errors = validate_fields({"defer": "yes"})
        assert any("defer" in e for e in errors)

    # --- key_files ---
    def test_valid_key_files(self):
        errors = validate_fields({"key_files": [{"file": "src/main.py", "role": "entry point", "look_for": "main"}]})
        assert not errors

    def test_key_files_non_list_rejected(self):
        errors = validate_fields({"key_files": "src/main.py"})
        assert any("key_files" in e for e in errors)

    def test_key_files_non_dict_elements_rejected(self):
        errors = validate_fields({"key_files": ["src/main.py"]})
        assert any("key_files" in e for e in errors)

    # --- key_file_paths ---
    def test_valid_key_file_paths(self):
        errors = validate_fields({"key_file_paths": ["src/main.py", "tests/test_main.py"]})
        assert not errors

    def test_key_file_paths_non_list_rejected(self):
        errors = validate_fields({"key_file_paths": "src/main.py"})
        assert any("key_file_paths" in e for e in errors)

    def test_key_file_paths_non_string_elements_rejected(self):
        errors = validate_fields({"key_file_paths": ["src/main.py", 42]})
        assert any("key_file_paths" in e for e in errors)

    # --- C-005: source shape enforcement ---
    def test_source_missing_ref_rejected(self):
        """C-005: source must have type, ref, and session per contract §3."""
        errors = validate_fields({"source": {"type": "ad-hoc"}})
        assert any("ref" in e for e in errors)

    def test_source_missing_session_rejected(self):
        """C-005: source must have type, ref, and session per contract §3."""
        errors = validate_fields({"source": {"type": "ad-hoc", "ref": "x"}})
        assert any("session" in e for e in errors)

    # --- C-005: defer shape enforcement ---
    def test_defer_missing_reason_rejected(self):
        """C-005: defer must have active, reason, deferred_at per contract §3."""
        errors = validate_fields({"defer": {"active": True}})
        assert any("reason" in e or "deferred_at" in e for e in errors)

    def test_defer_missing_deferred_at_rejected(self):
        """C-005: defer must have active, reason, deferred_at per contract §3."""
        errors = validate_fields({"defer": {"active": True, "reason": "blocked"}})
        assert any("deferred_at" in e for e in errors)

    # --- C-005: key_files row shape enforcement ---
    def test_key_files_row_missing_role_rejected(self):
        """C-005: key_files rows must have file, role, look_for per contract §3."""
        errors = validate_fields({"key_files": [{"file": "foo.py"}]})
        assert any("role" in e or "look_for" in e for e in errors)

    def test_key_files_row_missing_look_for_rejected(self):
        """C-005: key_files rows must have file, role, look_for per contract §3."""
        errors = validate_fields({"key_files": [{"file": "foo.py", "role": "entry"}]})
        assert any("look_for" in e for e in errors)

    def test_key_files_row_missing_file_rejected(self):
        """C-005: key_files rows must have file, role, look_for per contract §3."""
        errors = validate_fields({"key_files": [{"role": "entry", "look_for": "main"}]})
        assert any("file" in e for e in errors)

    def test_valid_full_source_passes(self):
        """Regression: fully-specified source should pass."""
        errors = validate_fields({"source": {"type": "user", "ref": "session-1", "session": "abc"}})
        assert errors == []

    def test_valid_full_defer_passes(self):
        """Regression: fully-specified defer should pass."""
        errors = validate_fields({"defer": {"active": True, "reason": "blocked", "deferred_at": "2026-03-10"}})
        assert errors == []

    def test_valid_full_key_files_passes(self):
        """Regression: fully-specified key_files should pass."""
        errors = validate_fields({"key_files": [{"file": "foo.py", "role": "entry", "look_for": "main"}]})
        assert errors == []

    # --- omitted fields are fine ---
    def test_empty_fields_valid(self):
        errors = validate_fields({})
        assert not errors

    def test_unknown_fields_ignored(self):
        errors = validate_fields({"title": "Test", "problem": "Problem"})
        assert not errors
