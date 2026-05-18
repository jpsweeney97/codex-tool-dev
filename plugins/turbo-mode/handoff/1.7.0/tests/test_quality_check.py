"""Tests for quality_check.py — hook-compatible quality validation helper."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from turbo_mode_handoff_runtime.quality_check import (
    CHECKPOINT_MAX_LINES,
    CHECKPOINT_MIN_LINES,
    CONTENT_REQUIRED_SECTIONS,
    HANDOFF_MIN_LINES,
    REQUIRED_CHECKPOINT_SECTIONS,
    REQUIRED_HANDOFF_SECTIONS,
    REQUIRED_SUMMARY_SECTIONS,
    SUMMARY_MAX_LINES,
    SUMMARY_MIN_LINES,
    VALID_TYPES,
    Issue,
    count_body_lines,
    format_output,
    is_handoff_path,
    main,
    parse_frontmatter,
    parse_sections,
    validate,
    validate_frontmatter,
    validate_line_count,
    validate_sections,
)

# --- Test helpers ---


def _make_frontmatter(
    overrides: dict[str, str] | None = None,
    *,
    omit: list[str] | None = None,
) -> dict[str, str]:
    """Build a valid frontmatter dict with optional overrides/omissions."""
    base = {
        "date": "2026-02-26",
        "time": "16:00",
        "created_at": "2026-02-26T16:00:00Z",
        "session_id": "test-session-id",
        "project": "test-project",
        "title": "Test Handoff",
        "type": "handoff",
    }
    if overrides:
        base.update(overrides)
    if omit:
        for key in omit:
            base.pop(key, None)
    return base


def _make_content(
    *,
    frontmatter: dict[str, str] | None = None,
    sections: list[str] | None = None,
    lines_per_section: int = 30,
    empty_sections: list[str] | None = None,
) -> str:
    """Build a synthetic handoff/checkpoint document.

    Default: valid handoff with all 13 required sections, ~450 lines.
    """
    if frontmatter is None:
        frontmatter = _make_frontmatter()
    if sections is None:
        sections = list(REQUIRED_HANDOFF_SECTIONS)

    lines = ["---"]
    for key, value in frontmatter.items():
        if key in ("time", "created_at", "title"):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("# Test Document")
    lines.append("")

    empty = set(empty_sections or [])
    for section in sections:
        lines.append(f"## {section}")
        lines.append("")
        if section not in empty:
            for i in range(lines_per_section):
                lines.append(f"Content line {i + 1} for {section}.")
            lines.append("")

    return "\n".join(lines)


def _run_main(input_data: dict) -> tuple[int, str]:
    """Run main() with mock stdin and capture stdout."""
    with (
        patch("sys.stdin", io.StringIO(json.dumps(input_data))),
        patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
    ):
        result = main()
    return result, mock_stdout.getvalue()


def _make_hook_input(file_path: str, content: str) -> dict:
    """Build a PostToolUse hook input dict for Write tool."""
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
        "tool_response": {"filePath": file_path, "success": True},
        "hook_event_name": "PostToolUse",
    }


HANDOFF_PATH = str(Path("/tmp/test-project") / ".codex" / "handoffs" / "2026-02-26_16-00_test.md")


# --- Frontmatter parsing ---


class TestParseFrontmatter:
    """Tests for parse_frontmatter — YAML extraction."""

    def test_extracts_fields(self) -> None:
        content = _make_content()
        fm = parse_frontmatter(content)
        assert fm["date"] == "2026-02-26"
        assert fm["type"] == "handoff"
        assert fm["title"] == "Test Handoff"

    def test_strips_quotes(self) -> None:
        content = "---\ntitle: \"Quoted Value\"\nother: 'single'\n---\n"
        fm = parse_frontmatter(content)
        assert fm["title"] == "Quoted Value"
        assert fm["other"] == "single"

    def test_no_frontmatter(self) -> None:
        assert parse_frontmatter("# Just a heading\nContent.") == {}

    def test_unclosed_frontmatter(self) -> None:
        assert parse_frontmatter("---\ndate: 2026-01-01\n# No closing") == {}

    def test_value_with_colons(self) -> None:
        """Values containing colons (e.g., timestamps) are preserved."""
        content = "---\ncreated_at: 2026-02-26T16:00:00Z\n---\n"
        fm = parse_frontmatter(content)
        assert fm["created_at"] == "2026-02-26T16:00:00Z"


# --- Frontmatter validation ---


class TestValidateFrontmatter:
    """Tests for validate_frontmatter — field presence and value checks."""

    def test_valid_handoff(self) -> None:
        assert validate_frontmatter(_make_frontmatter(), "handoff") == []

    def test_missing_field(self) -> None:
        issues = validate_frontmatter(_make_frontmatter(omit=["session_id"]), "handoff")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "session_id" in issues[0].message

    def test_multiple_missing_fields(self) -> None:
        issues = validate_frontmatter(_make_frontmatter(omit=["date", "time"]), "handoff")
        assert len(issues) == 1  # Single error listing both fields
        assert "date" in issues[0].message
        assert "time" in issues[0].message

    def test_checkpoint_title_missing_prefix(self) -> None:
        fm = _make_frontmatter(overrides={"type": "checkpoint", "title": "No Prefix"})
        issues = validate_frontmatter(fm, "checkpoint")
        assert any("Checkpoint:" in i.message for i in issues)

    def test_checkpoint_title_valid(self) -> None:
        fm = _make_frontmatter(overrides={"type": "checkpoint", "title": "Checkpoint: Valid"})
        assert validate_frontmatter(fm, "checkpoint") == []

    def test_blank_value_rejected(self) -> None:
        """Key present but value is empty string."""
        fm = _make_frontmatter(overrides={"title": ""})
        issues = validate_frontmatter(fm, "handoff")
        assert any(
            i.severity == "error" and "title" in i.message and "Blank" in i.message for i in issues
        )

    def test_whitespace_only_value_rejected(self) -> None:
        """Key present but value is whitespace-only."""
        fm = _make_frontmatter(overrides={"session_id": "   "})
        issues = validate_frontmatter(fm, "handoff")
        assert any(i.severity == "error" and "session_id" in i.message for i in issues)

    def test_multiple_blank_values_single_error(self) -> None:
        """Multiple blank fields reported in one error."""
        fm = _make_frontmatter(overrides={"title": "", "project": ""})
        issues = validate_frontmatter(fm, "handoff")
        blank_issues = [i for i in issues if "Blank" in i.message]
        assert len(blank_issues) == 1
        assert "title" in blank_issues[0].message
        assert "project" in blank_issues[0].message

    def test_summary_title_missing_prefix(self) -> None:
        fm = _make_frontmatter(overrides={"type": "summary", "title": "No Prefix"})
        issues = validate_frontmatter(fm, "summary")
        assert any("Summary:" in i.message for i in issues)

    def test_summary_title_valid(self) -> None:
        fm = _make_frontmatter(overrides={"type": "summary", "title": "Summary: Valid Title"})
        assert validate_frontmatter(fm, "summary") == []


# --- Section parsing ---


class TestParseSections:
    """Tests for parse_sections — ## heading extraction."""

    def test_extracts_sections(self) -> None:
        content = _make_content(sections=["Goal", "Next Steps"], lines_per_section=3)
        sections = parse_sections(content)
        assert len(sections) == 2
        assert sections[0]["heading"] == "Goal"
        assert sections[1]["heading"] == "Next Steps"

    def test_content_between_headings(self) -> None:
        content = _make_content(sections=["Goal"], lines_per_section=3)
        sections = parse_sections(content)
        assert "Content line 1 for Goal." in sections[0]["content"]

    def test_ignores_h3_subheadings(self) -> None:
        content = "---\ntype: handoff\n---\n## Goal\nContent\n### Sub\nMore"
        sections = parse_sections(content)
        assert len(sections) == 1
        assert "Sub" not in sections[0]["heading"]
        assert "More" in sections[0]["content"]

    def test_no_frontmatter(self) -> None:
        content = "## Section One\nContent\n## Section Two\nMore"
        sections = parse_sections(content)
        assert len(sections) == 2

    def test_ignores_headings_inside_code_fences(self) -> None:
        """## Heading inside a code block is not a section boundary."""
        content = (
            "---\ntype: handoff\n---\n"
            "## Real Section\n"
            "Some content\n"
            "```markdown\n"
            "## Fake Section\n"
            "This is inside a code fence\n"
            "```\n"
            "More content after fence\n"
            "## Another Real Section\n"
            "Final content"
        )
        sections = parse_sections(content)
        assert len(sections) == 2
        assert sections[0]["heading"] == "Real Section"
        assert sections[1]["heading"] == "Another Real Section"
        assert "Fake Section" not in [s["heading"] for s in sections]
        assert "inside a code fence" in sections[0]["content"]

    def test_ignores_headings_inside_indented_code_fences(self) -> None:
        """Indented fences (1-3 spaces) are valid per CommonMark."""
        content = (
            "---\ntype: handoff\n---\n"
            "## Real Section\n"
            "Some content\n"
            "   ```\n"
            "## Fake Inside Indented Fence\n"
            "   ```\n"
            "## Another Real Section\n"
            "Final content"
        )
        sections = parse_sections(content)
        assert len(sections) == 2
        headings = [s["heading"] for s in sections]
        assert "Fake Inside Indented Fence" not in headings
        assert "Real Section" in headings
        assert "Another Real Section" in headings

    def test_ignores_headings_inside_tilde_fences(self) -> None:
        """~~~ fences are valid per CommonMark — headings inside are ignored."""
        content = (
            "---\ntype: handoff\n---\n"
            "## Real Section\n"
            "Some content\n"
            "~~~\n"
            "## Fake Inside Tilde Fence\n"
            "~~~\n"
            "## Another Real Section\n"
            "Final content"
        )
        sections = parse_sections(content)
        headings = [s["heading"] for s in sections]
        assert len(sections) == 2
        assert "Fake Inside Tilde Fence" not in headings
        assert "Real Section" in headings
        assert "Another Real Section" in headings

    def test_parse_sections_does_not_close_backtick_fence_with_tilde_fence(self) -> None:
        content = "\n".join(
            [
                "---",
                "type: handoff",
                "---",
                "## A",
                "```",
                "~~~",
                "## inside",
                "```",
                "## B",
                "body",
                "",
            ]
        )

        sections = parse_sections(content)

        assert [section["heading"] for section in sections] == ["A", "B"]

    def test_four_space_indent_not_a_fence(self) -> None:
        """4+ space indent is NOT a valid fence — headings inside should parse."""
        content = (
            "---\ntype: handoff\n---\n"
            "## Real Section\n"
            "Some content\n"
            "    ```\n"
            "## Should Be Parsed\n"
            "    ```\n"
            "## Another Real Section\n"
            "Final content"
        )
        sections = parse_sections(content)
        headings = [s["heading"] for s in sections]
        assert "Should Be Parsed" in headings


# --- Section validation ---


class TestValidateSections:
    """Tests for validate_sections — required sections and empty checks."""

    def test_all_handoff_sections_present(self) -> None:
        sections = [{"heading": s, "content": "text"} for s in REQUIRED_HANDOFF_SECTIONS]
        assert validate_sections(sections, "handoff") == []

    def test_missing_section(self) -> None:
        sections = [
            {"heading": s, "content": "text"} for s in REQUIRED_HANDOFF_SECTIONS if s != "Goal"
        ]
        issues = validate_sections(sections, "handoff")
        assert any("Goal" in i.message for i in issues)

    def test_all_checkpoint_sections_present(self) -> None:
        sections = [{"heading": s, "content": "text"} for s in REQUIRED_CHECKPOINT_SECTIONS]
        assert validate_sections(sections, "checkpoint") == []

    def test_empty_section_warned(self) -> None:
        sections = [{"heading": "Goal", "content": ""}]
        issues = validate_sections(sections, "handoff")
        assert any(i.severity == "warning" and "Goal" in i.message for i in issues)

    def test_whitespace_only_is_empty(self) -> None:
        sections = [{"heading": "Goal", "content": "   \n  \n  "}]
        issues = validate_sections(sections, "handoff")
        assert any(i.severity == "warning" and "Empty" in i.message for i in issues)

    def test_extra_sections_allowed(self) -> None:
        sections = [{"heading": s, "content": "text"} for s in REQUIRED_HANDOFF_SECTIONS]
        sections.append({"heading": "Conversation Highlights", "content": "text"})
        assert validate_sections(sections, "handoff") == []

    def test_hollow_handoff_guardrail(self) -> None:
        """All 13 sections present but Decisions/Changes/Learnings all empty."""
        sections = []
        for s in REQUIRED_HANDOFF_SECTIONS:
            if s in CONTENT_REQUIRED_SECTIONS:
                sections.append({"heading": s, "content": "No changes."})
            else:
                sections.append({"heading": s, "content": "text"})
        # Replace content-required sections with placeholder-only
        for i, sec in enumerate(sections):
            if sec["heading"] in CONTENT_REQUIRED_SECTIONS:
                sections[i] = {"heading": sec["heading"], "content": ""}
        issues = validate_sections(sections, "handoff")
        assert any(i.severity == "error" and "Decisions" in i.message for i in issues)

    def test_hollow_handoff_passes_with_one_content_section(self) -> None:
        """Guardrail passes when at least one of {Decisions, Changes, Learnings} has content."""
        sections = []
        for s in REQUIRED_HANDOFF_SECTIONS:
            if s == "Decisions":
                sections.append({"heading": s, "content": "Chose X over Y."})
            elif s in CONTENT_REQUIRED_SECTIONS:
                sections.append({"heading": s, "content": ""})
            else:
                sections.append({"heading": s, "content": "text"})
        issues = validate_sections(sections, "handoff")
        # Should have empty-section warnings but no guardrail error
        assert not any("Decisions, Changes, Learnings" in i.message for i in issues)

    def test_hollow_guardrail_not_applied_to_checkpoints(self) -> None:
        """Hollow-handoff guardrail is handoff-only."""
        sections = [{"heading": s, "content": ""} for s in REQUIRED_CHECKPOINT_SECTIONS]
        issues = validate_sections(sections, "checkpoint")
        assert not any("Hollow" in i.message for i in issues)

    def test_hollow_guardrail_skipped_when_sections_absent(self) -> None:
        """When content-required sections are entirely absent, only missing-sections fires."""
        sections = [
            {"heading": s, "content": "text"}
            for s in REQUIRED_HANDOFF_SECTIONS
            if s not in CONTENT_REQUIRED_SECTIONS
        ]
        issues = validate_sections(sections, "handoff")
        # Missing-sections error should fire
        assert any("Missing required sections" in i.message for i in issues)
        # Hollow-handoff guardrail should NOT fire (sections absent, not empty)
        assert not any("Hollow handoff" in i.message for i in issues)

    def test_all_summary_sections_present(self) -> None:
        sections = [{"heading": s, "content": "text"} for s in REQUIRED_SUMMARY_SECTIONS]
        assert validate_sections(sections, "summary") == []

    def test_summary_missing_section(self) -> None:
        sections = [
            {"heading": s, "content": "text"}
            for s in REQUIRED_SUMMARY_SECTIONS
            if s != "Project Arc"
        ]
        issues = validate_sections(sections, "summary")
        assert any("Project Arc" in i.message for i in issues)

    def test_hollow_summary_guardrail(self) -> None:
        """All 8 sections present but Decisions/Changes/Learnings all empty."""
        sections = []
        for s in REQUIRED_SUMMARY_SECTIONS:
            if s in CONTENT_REQUIRED_SECTIONS:
                sections.append({"heading": s, "content": ""})
            else:
                sections.append({"heading": s, "content": "text"})
        issues = validate_sections(sections, "summary")
        assert any(i.severity == "error" and "Hollow" in i.message for i in issues)


# --- Line count validation ---


class TestValidateLineCount:
    """Tests for validate_line_count — range enforcement."""

    def test_handoff_above_minimum(self) -> None:
        content = "\n".join(["line"] * 450)
        assert validate_line_count(content, "handoff") == []

    def test_handoff_below_minimum(self) -> None:
        content = "\n".join(["line"] * 200)
        issues = validate_line_count(content, "handoff")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "200" in issues[0].message

    def test_handoff_at_exact_minimum(self) -> None:
        content = "\n".join(["line"] * HANDOFF_MIN_LINES)
        assert validate_line_count(content, "handoff") == []

    def test_checkpoint_within_range(self) -> None:
        content = "\n".join(["line"] * 50)
        assert validate_line_count(content, "checkpoint") == []

    def test_checkpoint_below_minimum(self) -> None:
        content = "\n".join(["line"] * 15)
        issues = validate_line_count(content, "checkpoint")
        assert len(issues) == 1
        assert "15" in issues[0].message

    def test_checkpoint_above_maximum(self) -> None:
        content = "\n".join(["line"] * 100)
        issues = validate_line_count(content, "checkpoint")
        assert len(issues) == 1
        assert "100" in issues[0].message

    def test_checkpoint_at_exact_boundaries(self) -> None:
        at_min = "\n".join(["line"] * CHECKPOINT_MIN_LINES)
        at_max = "\n".join(["line"] * CHECKPOINT_MAX_LINES)
        assert validate_line_count(at_min, "checkpoint") == []
        assert validate_line_count(at_max, "checkpoint") == []

    def test_summary_within_range(self) -> None:
        content = "\n".join(["line"] * 180)
        assert validate_line_count(content, "summary") == []

    def test_summary_below_minimum(self) -> None:
        content = "\n".join(["line"] * 80)
        issues = validate_line_count(content, "summary")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "80" in issues[0].message

    def test_summary_above_maximum(self) -> None:
        content = "\n".join(["line"] * 300)
        issues = validate_line_count(content, "summary")
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "300" in issues[0].message

    def test_summary_at_exact_boundaries(self) -> None:
        at_min = "\n".join(["line"] * SUMMARY_MIN_LINES)
        at_max = "\n".join(["line"] * SUMMARY_MAX_LINES)
        assert validate_line_count(at_min, "summary") == []
        assert validate_line_count(at_max, "summary") == []


# --- Body line counting ---


class TestCountBodyLines:
    """Tests for count_body_lines — frontmatter-aware line counting."""

    def test_with_frontmatter(self) -> None:
        content = "---\ntype: handoff\ndate: 2026-01-01\n---\nLine 1\nLine 2\nLine 3"
        assert count_body_lines(content) == 3

    def test_without_frontmatter(self) -> None:
        content = "Line 1\nLine 2\nLine 3"
        assert count_body_lines(content) == 3

    def test_trailing_newline(self) -> None:
        """Trailing newline should not inflate the count."""
        with_newline = "---\ntype: handoff\n---\nLine 1\nLine 2\n"
        without_newline = "---\ntype: handoff\n---\nLine 1\nLine 2"
        assert count_body_lines(with_newline) == count_body_lines(without_newline)

    def test_unclosed_frontmatter(self) -> None:
        """Unclosed frontmatter means all lines are body."""
        content = "---\ntype: handoff\nLine 1\nLine 2"
        assert count_body_lines(content) == 4

    def test_empty_string(self) -> None:
        """Empty string has 0 body lines."""
        assert count_body_lines("") == 0

    def test_trailing_newline_does_not_inflate(self) -> None:
        """Trailing newline with frontmatter doesn't inflate count (splitlines contract)."""
        content = "---\ntype: handoff\n---\n" + "x\n" * 400
        assert count_body_lines(content) == 400


# --- Top-level validate ---


class TestValidate:
    """Tests for validate — full document validation."""

    def test_valid_handoff(self) -> None:
        assert validate(_make_content()) == []

    def test_valid_checkpoint(self) -> None:
        content = _make_content(
            frontmatter=_make_frontmatter(
                overrides={
                    "type": "checkpoint",
                    "title": "Checkpoint: Test",
                }
            ),
            sections=list(REQUIRED_CHECKPOINT_SECTIONS),
            lines_per_section=5,
        )
        assert validate(content) == []

    def test_no_frontmatter(self) -> None:
        issues = validate("# No frontmatter\n## Goal\nContent")
        assert len(issues) == 1
        assert "frontmatter" in issues[0].message.lower()

    def test_defaults_to_handoff_when_type_missing(self) -> None:
        """Missing type field is an error but doc still validates as handoff."""
        content = _make_content(frontmatter=_make_frontmatter(omit=["type"]))
        issues = validate(content)
        assert any("type" in i.message for i in issues)

    def test_invalid_type_errors(self) -> None:
        """type: foo should produce an error and stop — no section/line-count errors."""
        content = _make_content(
            frontmatter=_make_frontmatter(overrides={"type": "foo"}),
        )
        issues = validate(content)
        assert len(issues) == 1, (
            f"Expected exactly 1 issue (type error), got {len(issues)}: {issues}"
        )
        assert issues[0].severity == "error"
        assert "foo" in issues[0].message
        assert all(t in issues[0].message for t in sorted(VALID_TYPES))

    def test_accumulates_multiple_issues(self) -> None:
        content = _make_content(
            frontmatter=_make_frontmatter(omit=["session_id"]),
            sections=["Goal", "Next Steps"],
            lines_per_section=5,
        )
        issues = validate(content)
        # Missing field + missing sections + under line count
        assert len(issues) >= 3

    def test_valid_summary(self) -> None:
        content = _make_content(
            frontmatter=_make_frontmatter(
                overrides={
                    "type": "summary",
                    "title": "Summary: Test Session",
                }
            ),
            sections=list(REQUIRED_SUMMARY_SECTIONS),
            lines_per_section=15,
        )
        assert validate(content) == []

    def test_invalid_type_error_lists_all_types(self) -> None:
        """Error message for invalid type should list all valid types including summary."""
        content = _make_content(
            frontmatter=_make_frontmatter(overrides={"type": "bogus"}),
        )
        issues = validate(content)
        assert len(issues) == 1
        assert "summary" in issues[0].message
        assert "handoff" in issues[0].message
        assert "checkpoint" in issues[0].message


class TestSummaryConstants:
    """Tests for summary type constants and basic type acceptance."""

    def test_summary_in_valid_types(self) -> None:
        assert "summary" in VALID_TYPES

    def test_summary_sections_defined(self) -> None:
        assert len(REQUIRED_SUMMARY_SECTIONS) == 8
        assert "Project Arc" in REQUIRED_SUMMARY_SECTIONS
        assert "Goal" in REQUIRED_SUMMARY_SECTIONS
        assert "Session Narrative" in REQUIRED_SUMMARY_SECTIONS
        assert "Decisions" in REQUIRED_SUMMARY_SECTIONS
        assert "Changes" in REQUIRED_SUMMARY_SECTIONS
        assert "Codebase Knowledge" in REQUIRED_SUMMARY_SECTIONS
        assert "Learnings" in REQUIRED_SUMMARY_SECTIONS
        assert "Next Steps" in REQUIRED_SUMMARY_SECTIONS

    def test_summary_line_count_constants(self) -> None:
        assert SUMMARY_MIN_LINES == 120
        assert SUMMARY_MAX_LINES == 250


# --- Path filtering ---


class TestIsHandoffPath:
    """Tests for is_handoff_path — file path detection."""

    def test_valid_active_handoff(self) -> None:
        assert is_handoff_path(HANDOFF_PATH) is True

    def test_valid_any_project_root(self) -> None:
        path = "/Users/jp/Projects/myproject/.codex/handoffs/2026-02-26_test.md"
        assert is_handoff_path(path) is True

    def test_valid_archived_handoff(self) -> None:
        path = "/tmp/proj/.codex/handoffs/archive/test.md"
        assert is_handoff_path(path) is True

    def test_non_handoff_directory(self) -> None:
        assert is_handoff_path("/tmp/random/file.md") is False

    def test_non_md_file(self) -> None:
        path = "/tmp/proj/.codex/handoffs/file.txt"
        assert is_handoff_path(path) is False

    def test_nested_too_deep(self) -> None:
        """File nested under a subdirectory of handoffs/ is rejected."""
        path = "/tmp/proj/.codex/handoffs/subdir/deep/file.md"
        assert is_handoff_path(path) is False

    def test_no_docs_parent_rejected(self) -> None:
        """handoffs/ without docs/ parent is not a valid handoff path."""
        path = "/tmp/handoffs/file.md"
        assert is_handoff_path(path) is False

    def test_handoffs_without_file_rejected(self) -> None:
        """Path ending at handoffs/ directory itself is rejected."""
        path = "/tmp/proj/.codex/handoffs/"
        assert is_handoff_path(path) is False

    def test_handoffs_variant_rejected(self) -> None:
        """handoffs-v2 is not handoffs."""
        path = "/tmp/proj/.codex/handoffs-v2/foo.md"
        assert is_handoff_path(path) is False

    def test_other_docs_variant_rejected(self) -> None:
        """other-docs is not docs."""
        path = "/tmp/proj/other-docs/handoffs/foo.md"
        assert is_handoff_path(path) is False

    def test_legacy_path_rejected(self) -> None:
        """Legacy docs/handoffs/ path should not match current quality hook."""
        path = "/tmp/proj/docs/handoffs/test.md"
        assert is_handoff_path(path) is False


# --- Output formatting ---


class TestFormatOutput:
    """Tests for format_output — message generation."""

    def test_errors_and_warnings(self) -> None:
        issues = [
            Issue("error", "Missing field: date"),
            Issue("warning", "Empty section: Goal"),
        ]
        msg = format_output(issues)
        assert "1 error(s)" in msg
        assert "1 warning(s)" in msg
        assert "Missing field: date" in msg
        assert "Empty section: Goal" in msg

    def test_errors_only(self) -> None:
        issues = [Issue("error", "Test error")]
        msg = format_output(issues)
        assert "Errors:" in msg
        assert "Warnings:" not in msg
        assert "Fix the errors" in msg

    def test_warnings_only_no_fix_instruction(self) -> None:
        """Warnings-only output should NOT say 'Fix the errors and rewrite'."""
        issues = [Issue("warning", "Test warning")]
        msg = format_output(issues)
        assert "Warnings:" in msg
        assert "Errors:" not in msg
        assert "Fix the errors" not in msg
        assert "review" in msg.lower()  # Softer language for warnings


# --- Hook integration ---


class TestMain:
    """Tests for main — PostToolUse hook entry point."""

    def test_non_handoff_path_silent(self) -> None:
        """Non-handoff file produces no output."""
        result, output = _run_main(_make_hook_input("/tmp/test.py", "print('hello')"))
        assert result == 0
        assert output == ""

    def test_valid_handoff_silent(self) -> None:
        """Valid handoff produces no output."""
        result, output = _run_main(_make_hook_input(HANDOFF_PATH, _make_content()))
        assert result == 0
        assert output == ""

    def test_invalid_handoff_outputs_context(self) -> None:
        """Invalid handoff produces additionalContext JSON with correct contract."""
        content = "---\ntype: handoff\n---\n## Goal\nShort."
        result, output = _run_main(_make_hook_input(HANDOFF_PATH, content))
        assert result == 0
        parsed = json.loads(output)
        hook_output = parsed["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "PostToolUse"
        assert "error" in hook_output["additionalContext"].lower()

    def test_malformed_json_silent(self) -> None:
        """Malformed stdin JSON produces no output, exit 0."""
        with (
            patch("sys.stdin", io.StringIO("not json")),
            patch("sys.stdout", new_callable=io.StringIO) as mock_stdout,
        ):
            result = main()
        assert result == 0
        assert mock_stdout.getvalue() == ""

    def test_empty_content_silent(self) -> None:
        """Empty content field produces no output."""
        result, output = _run_main(_make_hook_input(HANDOFF_PATH, ""))
        assert result == 0
        assert output == ""

    def test_archive_path_validates(self) -> None:
        """Archive path IS validated (is_handoff_path matches it)."""
        archive_path = str(Path("/tmp/test-project") / "docs" / "handoffs" / "archive" / "old.md")
        content = _make_content()
        result, output = _run_main(_make_hook_input(archive_path, content))
        assert result == 0
        # Valid content → no output (silent success)
        assert output == ""

    def test_missing_tool_input_key_silent(self) -> None:
        """Hook payload with no tool_input key produces no output."""
        result, output = _run_main({"hook_event_name": "PostToolUse"})
        assert result == 0
        assert output == ""

    def test_tool_input_none_silent(self) -> None:
        """Hook payload with tool_input: null doesn't crash."""
        result, output = _run_main({"tool_input": None})
        assert result == 0
        assert output == ""

    def test_content_none_silent(self) -> None:
        """Hook payload with content: null doesn't crash."""
        result, output = _run_main(
            {
                "tool_input": {"file_path": HANDOFF_PATH, "content": None},
            }
        )
        assert result == 0
        assert output == ""

    def test_file_path_none_silent(self) -> None:
        """Hook payload with file_path: null doesn't crash."""
        result, output = _run_main(
            {
                "tool_input": {"file_path": None, "content": "test"},
            }
        )
        assert result == 0
        assert output == ""

    def test_tool_input_non_dict_truthy_silent(self) -> None:
        """tool_input as truthy non-dict (e.g., string) doesn't crash."""
        result, output = _run_main({"tool_input": "Write"})
        assert result == 0
        assert output == ""

    def test_validate_exception_swallowed(self) -> None:
        """Internal validation crash is caught — hook exits 0, no stdout."""
        with patch(
            "turbo_mode_handoff_runtime.quality_check.validate", side_effect=RuntimeError("boom")
        ):
            result, output = _run_main(
                _make_hook_input(HANDOFF_PATH, "---\ntype: handoff\n---\ncontent")
            )
        assert result == 0
        assert output == ""

    def test_malformed_json_logs_to_stderr(self) -> None:
        """Malformed stdin JSON logs diagnostic to stderr."""
        with (
            patch("sys.stdin", io.StringIO("not json")),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
        ):
            result = main()
        assert result == 0
        assert "stdin parse failed" in mock_stderr.getvalue()

    def test_validate_exception_logs_to_stderr(self) -> None:
        """Validation exception logs diagnostic to stderr with type name."""
        with (
            patch(
                "sys.stdin",
                io.StringIO(
                    json.dumps(_make_hook_input(HANDOFF_PATH, "---\ntype: handoff\n---\ncontent"))
                ),
            ),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as mock_stderr,
            patch(
                "turbo_mode_handoff_runtime.quality_check.validate",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = main()
        assert result == 0
        assert "validation failed" in mock_stderr.getvalue()
        assert "RuntimeError" in mock_stderr.getvalue()

    def test_valid_checkpoint_end_to_end_silent(self) -> None:
        """Valid checkpoint through full main() pipeline produces no output."""
        content = _make_content(
            frontmatter=_make_frontmatter(
                overrides={
                    "type": "checkpoint",
                    "title": "Checkpoint: Test",
                }
            ),
            sections=list(REQUIRED_CHECKPOINT_SECTIONS),
            lines_per_section=5,
        )
        result, output = _run_main(_make_hook_input(HANDOFF_PATH, content))
        assert result == 0
        assert output == ""

    def test_valid_summary_end_to_end_silent(self) -> None:
        """Valid summary through full main() pipeline produces no output."""
        content = _make_content(
            frontmatter=_make_frontmatter(
                overrides={
                    "type": "summary",
                    "title": "Summary: Test Session",
                }
            ),
            sections=list(REQUIRED_SUMMARY_SECTIONS),
            lines_per_section=15,
        )
        result, output = _run_main(_make_hook_input(HANDOFF_PATH, content))
        assert result == 0
        assert output == ""
