"""Tests for handoff_parsing.py — shared parsing module."""

from pathlib import Path

from scripts.handoff_parsing import (
    HandoffFile,
    Section,
    parse_frontmatter,
    parse_handoff,
    parse_sections,
)


class TestParseFrontmatter:
    """Tests for parse_frontmatter."""

    def test_extracts_key_value_pairs(self) -> None:
        text = '---\ntitle: "My Title"\ndate: 2026-02-27\n---\nBody text.'
        fm, remaining = parse_frontmatter(text)
        assert fm["title"] == "My Title"
        assert fm["date"] == "2026-02-27"
        assert remaining.strip() == "Body text."

    def test_strips_surrounding_quotes(self) -> None:
        text = "---\ntitle: \"Quoted\"\ntime: '12:30'\n---\n"
        fm, _ = parse_frontmatter(text)
        assert fm["title"] == "Quoted"
        assert fm["time"] == "12:30"

    def test_no_frontmatter_returns_empty(self) -> None:
        text = "No frontmatter here.\n## Section\nContent."
        fm, remaining = parse_frontmatter(text)
        assert fm == {}
        assert remaining == text

    def test_unclosed_frontmatter_returns_empty(self) -> None:
        text = "---\ntitle: Broken\nno closing\n## Section\n"
        fm, remaining = parse_frontmatter(text)
        assert fm == {}
        assert remaining == text

    def test_skips_multiline_yaml(self) -> None:
        text = "---\ntitle: Test\nfiles:\n  - a.py\n  - b.py\ndate: 2026-01-01\n---\n"
        fm, _ = parse_frontmatter(text)
        assert fm["title"] == "Test"
        assert fm["date"] == "2026-01-01"
        assert "files" not in fm


class TestParseSections:
    """Tests for parse_sections."""

    def test_splits_on_level2_headings(self) -> None:
        text = "## Goal\n\nThe goal.\n\n## Decisions\n\nWe chose A.\n"
        sections = parse_sections(text)
        assert len(sections) == 2
        assert sections[0].heading == "## Goal"
        assert "The goal." in sections[0].content
        assert sections[1].heading == "## Decisions"

    def test_subsections_included_in_parent(self) -> None:
        text = "## Decisions\n\n### Decision A\n\nChose A.\n\n### Decision B\n\nChose B.\n"
        sections = parse_sections(text)
        assert len(sections) == 1
        assert "Decision A" in sections[0].content
        assert "Decision B" in sections[0].content

    def test_backtick_fences_prevent_false_headings(self) -> None:
        text = "## Real\n\nContent.\n\n```\n## Fake\n```\n\nMore content.\n"
        sections = parse_sections(text)
        assert len(sections) == 1
        assert sections[0].heading == "## Real"

    def test_tilde_fences_prevent_false_headings(self) -> None:
        text = "## Real\n\nContent.\n\n~~~\n## Fake\n~~~\n\nMore content.\n"
        sections = parse_sections(text)
        assert len(sections) == 1
        assert sections[0].heading == "## Real"

    def test_mixed_fences(self) -> None:
        text = "## A\n\n~~~\n```\n## Fake\n```\n~~~\n\n## B\n\nReal.\n"
        sections = parse_sections(text)
        assert len(sections) == 2

    def test_fence_parity_close_on_same_type_only(self) -> None:
        """~~~ fence is NOT closed by ``` — only same marker type closes."""
        text = "## A\n\n~~~\n```\n## Fake\n```\n## Also Fake\n~~~\n\n## B\n\nReal.\n"
        sections = parse_sections(text)
        assert len(sections) == 2
        assert sections[0].heading == "## A"
        assert sections[1].heading == "## B"

    def test_empty_text_returns_empty(self) -> None:
        assert parse_sections("") == []


class TestParseHandoff:
    """Tests for parse_handoff — full pipeline."""

    def test_parses_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Goal\n\nDo something.\n\n## Decisions\n\nChose A.\n"
        )
        result = parse_handoff(f)
        assert isinstance(result, HandoffFile)
        assert result.frontmatter["title"] == "Test"
        assert len(result.sections) == 2
        assert result.path == str(f)
