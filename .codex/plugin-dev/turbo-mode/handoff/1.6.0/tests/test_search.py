"""Tests for search.py — handoff search script."""

import json
from pathlib import Path
from unittest.mock import patch

from scripts.search import main as search_main, parse_handoff, search_handoffs


def test_search_module_reexports_parse_handoff() -> None:
    """Verify parse_handoff is importable from scripts.search (backward compat)."""
    from scripts.search import parse_handoff  # noqa: F811
    assert callable(parse_handoff)


class TestParseHandoff:
    """Tests for parse_handoff — markdown parsing."""

    def test_extracts_frontmatter(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\n"
            'title: "My Handoff"\n'
            "date: 2026-02-25\n"
            "type: handoff\n"
            "---\n"
            "\n"
            "# My Handoff\n"
            "\n"
            "## Goal\n"
            "\n"
            "Do something.\n"
        )
        result = parse_handoff(handoff)
        assert result.frontmatter["title"] == "My Handoff"
        assert result.frontmatter["date"] == "2026-02-25"
        assert result.frontmatter["type"] == "handoff"

    def test_splits_sections(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\n---\n"
            "\n"
            "## Goal\n"
            "\n"
            "The goal.\n"
            "\n"
            "## Decisions\n"
            "\n"
            "### Decision A\n"
            "\n"
            "We chose A.\n"
            "\n"
            "### Decision B\n"
            "\n"
            "We chose B.\n"
            "\n"
            "## Next Steps\n"
            "\n"
            "Do more.\n"
        )
        result = parse_handoff(handoff)
        assert len(result.sections) == 3
        assert result.sections[0].heading == "## Goal"
        assert "The goal." in result.sections[0].content
        assert result.sections[1].heading == "## Decisions"
        assert "Decision A" in result.sections[1].content
        assert "Decision B" in result.sections[1].content
        assert result.sections[2].heading == "## Next Steps"

    def test_no_sections(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text("---\ntitle: Minimal\n---\n\nJust some text.\n")
        result = parse_handoff(handoff)
        assert result.sections == []
        assert result.frontmatter["title"] == "Minimal"

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text("## Goal\n\nDo something.\n")
        result = parse_handoff(handoff)
        assert result.frontmatter == {}
        assert len(result.sections) == 1
        assert result.sections[0].heading == "## Goal"

    def test_path_stored(self, tmp_path: Path) -> None:
        handoff = tmp_path / "2026-02-25_22-34_test.md"
        handoff.write_text("---\ntitle: Test\n---\n")
        result = parse_handoff(handoff)
        assert result.path == str(handoff)

    def test_headings_inside_code_fences_ignored(self, tmp_path: Path) -> None:
        """A3 (handoff-search-implementation): ## lines inside fenced code blocks must not create sections."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\n---\n"
            "\n"
            "## Real Section\n"
            "\n"
            "Some content.\n"
            "\n"
            "```markdown\n"
            "## Fake Section Inside Fence\n"
            "\n"
            "This should not be a section.\n"
            "```\n"
            "\n"
            "More content in real section.\n"
        )
        result = parse_handoff(handoff)
        assert len(result.sections) == 1
        assert result.sections[0].heading == "## Real Section"
        assert "Fake Section Inside Fence" in result.sections[0].content

    def test_unclosed_frontmatter_treated_as_no_frontmatter(self, tmp_path: Path) -> None:
        """Opening --- with no closing --- is treated as no frontmatter."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\n"
            "title: Broken\n"
            "no closing delimiter\n"
            "\n"
            "## Goal\n"
            "\n"
            "Do something.\n"
        )
        result = parse_handoff(handoff)
        assert result.frontmatter == {}
        assert len(result.sections) == 1
        assert result.sections[0].heading == "## Goal"

    def test_unterminated_fence_does_not_crash(self, tmp_path: Path) -> None:
        """A8 (handoff-search-implementation): Unterminated fence suppresses subsequent sections (graceful degradation)."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\n---\n"
            "\n"
            "## Before Fence\n"
            "\n"
            "Content before.\n"
            "\n"
            "```python\n"
            "# unclosed fence\n"
            "\n"
            "## Suppressed Section\n"
            "\n"
            "This section is invisible.\n"
        )
        result = parse_handoff(handoff)
        # Only the section before the unterminated fence is found.
        # The suppressed section is absorbed — graceful degradation, not crash.
        assert len(result.sections) == 1
        assert result.sections[0].heading == "## Before Fence"

    def test_backtick_fence_prevents_section_split(self, tmp_path: Path) -> None:
        """Fence regression: backtick fences must not create false sections."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Real Section\n\nContent.\n\n"
            "```\n## Fake Section\n```\n\nMore content.\n"
        )
        results = search_handoffs(tmp_path, "content")
        sections_found = {r["section_heading"] for r in results}
        assert "## Fake Section" not in sections_found

    def test_unterminated_fence_behavior(self, tmp_path: Path) -> None:
        """Fence regression: unterminated fence suppresses subsequent sections."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Before\n\nContent.\n\n"
            "```\n## Suppressed\n\nStill suppressed.\n"
        )
        results = search_handoffs(tmp_path, "content")
        sections_found = {r["section_heading"] for r in results}
        assert "## Suppressed" not in sections_found


def _make_handoff(path: Path, title: str, date: str, content: str) -> Path:
    """Helper: create a synthetic handoff file."""
    handoff = path / f"{date}_00-00_{title.lower().replace(' ', '-')}.md"
    handoff.write_text(
        f"---\n"
        f'title: "{title}"\n'
        f"date: {date}\n"
        f"type: handoff\n"
        f"---\n\n"
        f"{content}"
    )
    return handoff


class TestSearchHandoffs:
    """Tests for search_handoffs — search logic."""

    def test_literal_match_case_insensitive(self, tmp_path: Path) -> None:
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Decisions\n\nWe chose Regular Merge.\n"
        )
        results = search_handoffs(tmp_path, "regular merge")
        assert len(results) == 1
        assert results[0]["section_heading"] == "## Decisions"
        assert "Regular Merge" in results[0]["section_content"]

    def test_regex_match(self, tmp_path: Path) -> None:
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Decisions\n\nChose option A over B.\n"
        )
        results = search_handoffs(tmp_path, r"option [AB]", regex=True)
        assert len(results) == 1

    def test_no_matches_returns_empty(self, tmp_path: Path) -> None:
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Goal\n\nBuild something.\n"
        )
        results = search_handoffs(tmp_path, "nonexistent_xyz")
        assert results == []

    def test_match_in_heading(self, tmp_path: Path) -> None:
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Codebase Knowledge\n\nSome details.\n"
        )
        results = search_handoffs(tmp_path, "codebase knowledge")
        assert len(results) == 1
        assert results[0]["section_heading"] == "## Codebase Knowledge"

    def test_multiple_files_sorted_by_date_descending(self, tmp_path: Path) -> None:
        _make_handoff(
            tmp_path, "Old", "2026-01-01",
            "## Decisions\n\nDecision about merging.\n"
        )
        _make_handoff(
            tmp_path, "New", "2026-02-25",
            "## Decisions\n\nDecision about merging.\n"
        )
        results = search_handoffs(tmp_path, "merging")
        assert len(results) == 2
        assert results[0]["date"] == "2026-02-25"
        assert results[1]["date"] == "2026-01-01"

    def test_multiple_sections_in_same_file(self, tmp_path: Path) -> None:
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Goal\n\nSearch feature.\n\n## Learnings\n\nSearch is useful.\n"
        )
        results = search_handoffs(tmp_path, "search")
        assert len(results) == 2

    def test_searches_archive_subdirectory(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        _make_handoff(
            archive, "Archived", "2026-01-15",
            "## Decisions\n\nOld decision about caching.\n"
        )
        results = search_handoffs(tmp_path, "caching")
        assert len(results) == 1
        assert results[0]["archived"] is True

    def test_skips_non_md_files(self, tmp_path: Path) -> None:
        txt = tmp_path / "notes.txt"
        txt.write_text("## Decisions\n\nSomething about merging.\n")
        results = search_handoffs(tmp_path, "merging")
        assert results == []

    def test_regex_is_case_sensitive(self, tmp_path: Path) -> None:
        """Regex mode is case-sensitive (flags=0), unlike literal mode."""
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Decisions\n\nChose Regular Merge.\n"
        )
        # Literal: case-insensitive — matches
        assert len(search_handoffs(tmp_path, "regular merge")) == 1
        # Regex: case-sensitive — lowercase doesn't match titlecase
        assert len(search_handoffs(tmp_path, "regular merge", regex=True)) == 0
        # Regex: exact case — matches
        assert len(search_handoffs(tmp_path, "Regular Merge", regex=True)) == 1

    def test_literal_escapes_regex_metacharacters(self, tmp_path: Path) -> None:
        """Literal search escapes regex metacharacters via re.escape()."""
        _make_handoff(
            tmp_path, "Test", "2026-02-25",
            "## Decisions\n\nChose option (A) over option (B).\n"
        )
        results = search_handoffs(tmp_path, "option (A)")
        assert len(results) == 1

    def test_unreadable_file_reported_in_skipped(self, tmp_path: Path) -> None:
        """Unreadable files are reported via skipped parameter, not silently dropped."""
        _make_handoff(
            tmp_path, "Good", "2026-02-25",
            "## Goal\n\nSearchable content.\n"
        )
        bad_file = tmp_path / "2026-02-24_00-00_bad.md"
        bad_file.write_bytes(b"---\ntitle: Bad\n---\n\n## Goal\n\n\xff\xfe invalid\n")

        skipped: list[dict] = []
        results = search_handoffs(tmp_path, "content", skipped=skipped)
        assert len(results) == 1
        assert len(skipped) == 1
        assert "bad.md" in skipped[0]["file"]
        assert skipped[0]["reason"]  # Non-empty reason string

    def test_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        results = search_handoffs(tmp_path / "nonexistent", "anything")
        assert results == []


class TestSkippedDefault:
    """search_handoffs should track skipped files internally even without explicit skipped param."""

    def test_skipped_defaults_to_internal_tracking(self, tmp_path: Path) -> None:
        """Calling without skipped= should not raise when files are unreadable.
        Create one good + one unreadable file, assert only the good file returns."""
        good_file = tmp_path / "2026-01-01_00-00_good.md"
        good_file.write_text(
            "---\ntitle: Good\ndate: 2026-01-01\ntype: handoff\n"
            "session_id: good-1\n---\n\n## Decisions\n\nfindme keyword\n"
        )
        bad_file = tmp_path / "2026-01-01_00-00_bad.md"
        bad_file.write_text("content")
        bad_file.chmod(0o000)
        try:
            results = search_handoffs(tmp_path, "findme")
            assert isinstance(results, list)
            assert len(results) == 1, f"Expected 1 result (good file only), got {len(results)}"
        finally:
            bad_file.chmod(0o644)


class TestSearchCLI:
    """Integration tests for the CLI entry point."""

    def test_end_to_end_json_output(self, tmp_path: Path) -> None:
        """Full pipeline: create handoffs, run search, verify JSON."""
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        _make_handoff(
            handoffs_dir, "Session One", "2026-02-20",
            "## Decisions\n\n### Chose Python\n\nPython over Rust for speed of dev.\n"
        )
        archive = handoffs_dir / "archive"
        archive.mkdir()
        _make_handoff(
            archive, "Old Session", "2026-01-15",
            "## Learnings\n\nPython parsing is fast enough.\n"
        )

        with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
            output = search_main(["Python"])

        result = json.loads(output)
        assert result["query"] == "Python"
        assert result["total_matches"] == 2
        assert result["results"][0]["date"] == "2026-02-20"
        assert result["results"][1]["archived"] is True
        assert result["error"] is None

    def test_no_results(self, tmp_path: Path) -> None:
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()

        with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
            output = search_main(["nonexistent_query"])

        result = json.loads(output)
        assert result["total_matches"] == 0
        assert result["results"] == []

    def test_invalid_regex_returns_error(self, tmp_path: Path) -> None:
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()

        with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
            output = search_main(["[invalid", "--regex"])

        result = json.loads(output)
        assert result["error"] is not None
        assert "Invalid regex" in result["error"]

    def test_regex_flag(self, tmp_path: Path) -> None:
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        _make_handoff(
            handoffs_dir, "Test", "2026-02-25",
            "## Decisions\n\nChose option-A over option-B.\n"
        )

        with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
            output = search_main([r"option-[AB]", "--regex"])

        result = json.loads(output)
        assert result["total_matches"] == 1

    def test_skipped_files_in_json_output(self, tmp_path: Path) -> None:
        """JSON output includes skipped field."""
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()

        with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
            output = search_main(["anything"])

        result = json.loads(output)
        assert "skipped" in result
        assert result["skipped"] == []

    def test_missing_directory_reports_error(self, tmp_path: Path) -> None:
        """Missing handoffs directory reports error, not silent empty results."""
        nonexistent = tmp_path / "nonexistent"

        with patch("scripts.search.get_handoffs_dir", return_value=nonexistent):
            output = search_main(["anything"])

        result = json.loads(output)
        assert result["error"] is not None
        assert "not found" in result["error"].lower()
        assert str(nonexistent) in result["error"]
        assert result["total_matches"] == 0

    def test_project_source_git(self, tmp_path: Path) -> None:
        """JSON output includes project_source when resolved via git."""
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()

        with patch("scripts.search.get_project_name", return_value=("test", "git")):
            with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
                output = search_main(["anything"])

        result = json.loads(output)
        assert result["project_source"] == "git"

    def test_project_source_cwd_fallback(self, tmp_path: Path) -> None:
        """JSON output shows project_source='cwd' when git fails."""
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()

        with patch("scripts.search.get_project_name", return_value=("test", "cwd")):
            with patch("scripts.search.get_handoffs_dir", return_value=handoffs_dir):
                output = search_main(["anything"])

        result = json.loads(output)
        assert result["project_source"] == "cwd"

    def test_direct_execution_via_subprocess(self) -> None:
        """A9 (handoff-search-implementation): Verify __main__ path works under direct script execution."""
        import subprocess

        script = Path(__file__).parent.parent / "scripts" / "search.py"
        result = subprocess.run(
            ["python3", str(script), "nonexistent_query_xyz"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "total_matches" in output
        assert "error" in output
        assert "project_source" in output
