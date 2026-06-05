"""Tests for target ticket field validation."""

from __future__ import annotations

from scripts.ticket_validate import validate_fields


class TestValidateFields:
    """Shared validation for target writable ticket fields."""

    def test_valid_priorities(self):
        for priority in ("high", "normal", "low"):
            assert validate_fields({"priority": priority}) == []

    def test_deprecated_priorities_rejected(self):
        for priority in ("critical", "medium"):
            assert any("priority" in error for error in validate_fields({"priority": priority}))

    def test_valid_statuses(self):
        for status in ("idea", "open", "blocked", "done", "wontfix"):
            assert validate_fields({"status": status}) == []

    def test_deprecated_in_progress_status_rejected(self):
        assert any("status" in error for error in validate_fields({"status": "in_progress"}))

    def test_blocked_on_none_is_valid_section_removal_input(self):
        assert validate_fields({"blocked_on": None}) == []

    def test_valid_resolutions(self):
        for resolution in ("done", "wontfix"):
            assert validate_fields({"resolution": resolution}) == []

    def test_invalid_resolution_rejected(self):
        assert any("resolution" in error for error in validate_fields({"resolution": "cancelled"}))

    def test_title_and_problem_types(self):
        assert any("title" in error for error in validate_fields({"title": 123}))
        assert any("problem" in error for error in validate_fields({"problem": ["x"]}))

    def test_target_list_fields(self):
        assert validate_fields({"tags": ["bug"], "blocked_by": [], "related_paths": []}) == []
        assert any("tags" in error for error in validate_fields({"tags": "bug"}))
        assert any("blocked_by" in error for error in validate_fields({"blocked_by": "T-1"}))
        assert any("related_paths" in error for error in validate_fields({"related_paths": "x"}))

    def test_blocked_by_entries_must_be_target_ticket_ids(self):
        errors = validate_fields({"blocked_by": ["not-a-ticket-id"]})

        assert any("blocked_by entries must be target ticket IDs" in error for error in errors)

    def test_deprecated_storage_fields_rejected(self):
        for key, value in {
            "date": "2026-06-02",
            "created_at": "2026-06-02T00:00:00Z",
            "effort": "M",
            "source": {"type": "ad-hoc", "ref": "", "session": "s"},
            "capture_confidence": "high",
            "capture_source": "conversation",
            "refinement_status": "needs_refinement",
            "component": "ticket",
            "blocks": ["T-20260302-01"],
            "contract_version": "1.0",
            "defer": {"active": True},
            "key_file_paths": ["src/main.py"],
            "key_files": [{"file": "src/main.py"}],
            "archive": True,
        }.items():
            assert any(key in error for error in validate_fields({key: value})), key

    def test_acceptance_criteria_is_section_input(self):
        assert validate_fields({"acceptance_criteria": ["criterion one", "criterion two"]}) == []
        assert any(
            "acceptance_criteria" in error
            for error in validate_fields({"acceptance_criteria": "criterion one"})
        )

    def test_empty_fields_valid(self):
        assert validate_fields({}) == []

    def test_target_string_section_inputs_valid(self):
        assert validate_fields(
            {
                "title": "Test",
                "problem": "Problem",
                "next_action": "Continue.",
                "context": "Context.",
                "prior_investigation": "Prior.",
                "approach": "Approach.",
                "decisions_made": "Decision.",
                "related": "Related.",
                "change_history_entry": "- 2026-06-02T00:00:00Z | codex | Updated ticket.",
            }
        ) == []
