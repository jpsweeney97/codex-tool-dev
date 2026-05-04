"""Tests for distill.py — knowledge graduation extraction."""

import json
from pathlib import Path

import pytest
from scripts.distill import (
    CandidateDict,
    DedupStatus,
    DurabilityHint,
    ErrorCode,
    ExtractionResultDict,
    Subsection,
    classify_durability,
    determine_dedup_status,
    extract_candidates,
    extract_signals,
    parse_subsections,
    check_exact_dup_content,
    check_exact_dup_source,
    compute_content_hash,
    compute_source_uid,
    make_distill_meta,
    main as distill_main,
)


class TestParseSubsections:
    """Tests for parse_subsections — ### splitting within a ## section."""

    def test_splits_on_level3_headings(self) -> None:
        content = (
            "### Decision A\n\n"
            "**Choice:** Chose A.\n\n"
            "**Driver:** Speed.\n\n"
            "### Decision B\n\n"
            "**Choice:** Chose B.\n\n"
            "**Driver:** Cost.\n"
        )
        subs = parse_subsections(content)
        assert len(subs) == 2
        assert subs[0].heading == "Decision A"
        assert "**Choice:** Chose A." in subs[0].raw_markdown
        assert subs[1].heading == "Decision B"
        assert "**Choice:** Chose B." in subs[1].raw_markdown

    def test_no_subsections_returns_whole_content(self) -> None:
        content = "Just a paragraph of text with no ### headings."
        subs = parse_subsections(content)
        assert len(subs) == 1
        assert subs[0].heading == ""
        assert subs[0].raw_markdown == content

    def test_leading_text_before_first_subsection(self) -> None:
        content = (
            "Some intro text.\n\n"
            "### Sub A\n\n"
            "Content A.\n"
        )
        subs = parse_subsections(content)
        assert len(subs) == 2
        assert subs[0].heading == ""
        assert "Some intro text." in subs[0].raw_markdown
        assert subs[1].heading == "Sub A"

    def test_backtick_fences_do_not_split(self) -> None:
        content = (
            "### Real\n\n"
            "```\n### Fake\n```\n\n"
            "More content.\n"
        )
        subs = parse_subsections(content)
        assert len(subs) == 1
        assert subs[0].heading == "Real"
        assert "### Fake" in subs[0].raw_markdown

    def test_tilde_fences_do_not_split(self) -> None:
        content = (
            "### Real\n\n"
            "~~~\n### Fake\n~~~\n\n"
            "More content.\n"
        )
        subs = parse_subsections(content)
        assert len(subs) == 1
        assert subs[0].heading == "Real"
        assert "### Fake" in subs[0].raw_markdown

    def test_level4_headings_stay_in_parent(self) -> None:
        """#### headings are NOT split — they remain inside the ### parent.

        Extraction granularity is ### only. #### is typically file-inventory
        or sub-detail content that belongs with its parent subsection.
        """
        content = (
            "### Decision A\n\n"
            "**Choice:** Chose A.\n\n"
            "#### Supporting detail\n\n"
            "Some detail.\n\n"
            "#### Another detail\n\n"
            "More detail.\n\n"
            "### Decision B\n\n"
            "**Choice:** Chose B.\n"
        )
        subs = parse_subsections(content)
        assert len(subs) == 2
        assert subs[0].heading == "Decision A"
        assert "#### Supporting detail" in subs[0].raw_markdown
        assert "#### Another detail" in subs[0].raw_markdown
        assert subs[1].heading == "Decision B"

    def test_empty_content_returns_empty(self) -> None:
        subs = parse_subsections("")
        assert len(subs) == 1
        assert subs[0].heading == ""
        assert subs[0].raw_markdown == ""

    def test_unterminated_fence_suppresses_splits(self) -> None:
        """An unclosed fence suppresses all subsequent ### splits (fail-safe)."""
        content = (
            "### Real\n\n"
            "```\n"
            "### Suppressed by unclosed fence\n"
            "text inside fence\n"
        )
        subs = parse_subsections(content)
        assert len(subs) == 1
        assert subs[0].heading == "Real"
        assert "### Suppressed" in subs[0].raw_markdown


class TestClassifyDurability:
    """Tests for classify_durability — keyword heuristic for Codebase Knowledge."""

    def test_pattern_is_likely_durable(self) -> None:
        assert classify_durability("Plugin hook naming pattern", "") == "likely_durable"

    def test_convention_is_likely_durable(self) -> None:
        assert classify_durability("Test file naming convention", "") == "likely_durable"

    def test_gotcha_is_likely_durable(self) -> None:
        assert classify_durability("Heredoc gotcha in zsh", "") == "likely_durable"

    def test_architecture_is_likely_ephemeral(self) -> None:
        assert classify_durability("Plugin architecture overview", "") == "likely_ephemeral"

    def test_key_locations_is_likely_ephemeral(self) -> None:
        assert classify_durability("Key code locations", "") == "likely_ephemeral"

    def test_unknown_heading(self) -> None:
        assert classify_durability("Miscellaneous notes", "") == "unknown"

    def test_content_keywords_override_heading(self) -> None:
        """Content with 'pattern' or 'convention' can upgrade unknown heading."""
        hint = classify_durability(
            "Something else",
            "This is a recurring pattern across all scripts.",
        )
        assert hint == "likely_durable"

    def test_ephemeral_keywords_in_content_do_not_trigger_ephemeral(self) -> None:
        """Content ephemeral keywords intentionally do NOT trigger likely_ephemeral.
        Only heading keywords trigger ephemeral classification."""
        hint = classify_durability(
            "Miscellaneous notes",
            "Describes the architecture overview and key locations.",
        )
        assert hint == "unknown"

    def test_content_ephemeral_asymmetry_lock(self) -> None:
        """Content keywords can upgrade to durable but NOT to ephemeral.
        This is intentional — heading is a stronger ephemerality signal."""
        # "architecture" is an ephemeral heading keyword — but in content it should NOT trigger
        hint = classify_durability(
            "Miscellaneous notes",
            "The architecture overview shows a pipeline pattern.",
        )
        assert hint != "likely_ephemeral", "Content ephemeral keywords must not trigger ephemeral"


class TestProvenance:
    """Tests for provenance computation."""

    def test_source_uid_deterministic(self) -> None:
        uid1 = compute_source_uid("session-abc-123", "Decisions", "Token bucket", heading_ix=0)
        uid2 = compute_source_uid("session-abc-123", "Decisions", "Token bucket", heading_ix=0)
        assert uid1 == uid2
        assert uid1.startswith("sha256:")

    def test_source_uid_differs_by_section(self) -> None:
        uid1 = compute_source_uid("session-abc-123", "Decisions", "Sub A", heading_ix=0)
        uid2 = compute_source_uid("session-abc-123", "Learnings", "Sub A", heading_ix=0)
        assert uid1 != uid2

    def test_source_uid_uses_identity_not_path(self) -> None:
        """source_uid is driven by document_identity, not filesystem path."""
        uid1 = compute_source_uid("session-abc-123", "Decisions", "Sub A", heading_ix=0)
        uid2 = compute_source_uid("session-abc-123", "Decisions", "Sub A", heading_ix=0)
        uid_different = compute_source_uid("different-session", "Decisions", "Sub A", heading_ix=0)
        assert uid1 == uid2
        assert uid1 != uid_different

    def test_content_hash_deterministic(self) -> None:
        h1 = compute_content_hash("Some content here.")
        h2 = compute_content_hash("Some content here.")
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_content_hash_normalizes_whitespace(self) -> None:
        h1 = compute_content_hash("  content  \n\n  here  ")
        h2 = compute_content_hash("content here")
        assert h1 == h2

    def test_source_uid_disambiguates_duplicate_headings(self) -> None:
        uid0 = compute_source_uid("session-abc", "Decisions", "Sub A", heading_ix=0)
        uid1 = compute_source_uid("session-abc", "Decisions", "Sub A", heading_ix=1)
        assert uid0 != uid1

    def test_source_uid_canonical_json_is_deterministic(self) -> None:
        uid1 = compute_source_uid("sess-1", "Decisions", "Sub A", heading_ix=0)
        uid2 = compute_source_uid("sess-1", "Decisions", "Sub A", heading_ix=0)
        assert uid1 == uid2
        assert uid1.startswith("sha256:")

    def test_distill_meta_format(self) -> None:
        meta = make_distill_meta(
            source_uid="sha256:abc123",
            source_anchor="handoff.md#decisions/token-bucket",
            content_sha256="sha256:def456",
        )
        assert meta.startswith("<!-- distill-meta ")
        assert meta.endswith(" -->")
        assert '"v": 1' in meta
        assert '"source_uid": "sha256:abc123"' in meta


class TestDocumentIdentity:
    """Tests for _document_identity — session_id enforcement."""

    def test_returns_session_id(self) -> None:
        from scripts.distill import _document_identity
        assert _document_identity({"session_id": "abc-123"}) == "abc-123"

    def test_strips_whitespace(self) -> None:
        from scripts.distill import _document_identity
        assert _document_identity({"session_id": "  abc-123  "}) == "abc-123"

    def test_rejects_missing_session_id(self) -> None:
        from scripts.distill import _document_identity
        with pytest.raises(ValueError, match="No session_id"):
            _document_identity({})

    def test_rejects_blank_session_id(self) -> None:
        from scripts.distill import _document_identity
        with pytest.raises(ValueError, match="No session_id"):
            _document_identity({"session_id": "  "})


class TestExactDedup:
    """Tests for exact deduplication checks."""

    def test_source_dup_detected(self) -> None:
        uid = "sha256:abc123"
        learnings = (
            "### 2026-02-27 [test]\n\n"
            "Some learning.\n"
            f'<!-- distill-meta {{"v": 1, "source_uid": "{uid}"}} -->\n'
        )
        assert check_exact_dup_source(uid, learnings) is True

    def test_source_no_dup(self) -> None:
        learnings = (
            "### 2026-02-27 [test]\n\n"
            "Some learning.\n"
            '<!-- distill-meta {"v": 1, "source_uid": "sha256:other"} -->\n'
        )
        assert check_exact_dup_source("sha256:abc123", learnings) is False

    def test_content_dup_detected(self) -> None:
        h = "sha256:def456"
        learnings = (
            "### 2026-02-27 [test]\n\n"
            "Some learning.\n"
            f'<!-- distill-meta {{"v": 1, "content_sha256": "{h}"}} -->\n'
        )
        assert check_exact_dup_content(h, learnings) is True

    def test_content_no_dup(self) -> None:
        learnings = "### 2026-02-27 [test]\n\nSome learning.\n"
        assert check_exact_dup_content("sha256:def456", learnings) is False

    def test_empty_learnings(self) -> None:
        assert check_exact_dup_source("sha256:abc", "") is False
        assert check_exact_dup_content("sha256:abc", "") is False

    def test_prose_containing_json_not_false_positive(self) -> None:
        """Only content inside <!-- distill-meta ... --> comments counts."""
        learnings = (
            "### 2026-02-27 [test]\n\n"
            'The check uses `"source_uid": "sha256:abc123"` for matching.\n'
        )
        assert check_exact_dup_source("sha256:abc123", learnings) is False

    def test_prefix_uid_not_false_positive(self) -> None:
        """A source_uid that is a prefix of another should not match."""
        learnings = (
            "### 2026-02-27 [test]\n\n"
            "Some learning.\n"
            '<!-- distill-meta {"v": 1, "source_uid": "sha256:abc123full"} -->\n'
        )
        assert check_exact_dup_source("sha256:abc123", learnings) is False


class TestDetermineDedup:
    """Tests for determine_dedup_status — per-record correlated dedup."""

    def test_same_row_exact_dup(self) -> None:
        learnings = '<!-- distill-meta {"v": 1, "source_uid": "sha256:src_A", "content_sha256": "sha256:content_A"} -->\n'
        assert determine_dedup_status("sha256:src_A", "sha256:content_A", learnings) == "EXACT_DUP_SOURCE"

    def test_source_match_content_differs_is_updated(self) -> None:
        learnings = '<!-- distill-meta {"v": 1, "source_uid": "sha256:src_A", "content_sha256": "sha256:old"} -->\n'
        assert determine_dedup_status("sha256:src_A", "sha256:new", learnings) == "UPDATED_SOURCE"

    def test_content_only_match(self) -> None:
        learnings = '<!-- distill-meta {"v": 1, "source_uid": "sha256:other", "content_sha256": "sha256:content_A"} -->\n'
        assert determine_dedup_status("sha256:src_A", "sha256:content_A", learnings) == "EXACT_DUP_CONTENT"

    def test_no_matches_is_new(self) -> None:
        learnings = '<!-- distill-meta {"v": 1, "source_uid": "sha256:other", "content_sha256": "sha256:other"} -->\n'
        assert determine_dedup_status("sha256:src_A", "sha256:content_A", learnings) == "NEW"

    def test_empty_learnings_is_new(self) -> None:
        assert determine_dedup_status("sha256:src", "sha256:content", "") == "NEW"

    def test_cross_row_source_and_content_not_conflated(self) -> None:
        """When source_uid matches entry A and content_sha256 matches entry B,
        source identity takes precedence: UPDATED_SOURCE (not EXACT_DUP_SOURCE)."""
        learnings = (
            '<!-- distill-meta {"v": 1, "source_uid": "sha256:src_A", "content_sha256": "sha256:old_content"} -->\n'
            '<!-- distill-meta {"v": 1, "source_uid": "sha256:src_B", "content_sha256": "sha256:new_content"} -->\n'
        )
        status = determine_dedup_status("sha256:src_A", "sha256:new_content", learnings)
        assert status == "UPDATED_SOURCE"


class TestCrossRowDedupIntegration:
    """Integration test: cross-row misclassification prevented in extract_candidates."""

    def test_cross_row_does_not_produce_false_exact_dup(self, tmp_path: Path) -> None:
        """A candidate whose source matches entry A and content matches entry B
        must be UPDATED_SOURCE, not EXACT_DUP_SOURCE."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: cross-row-1\n---\n\n"
            "## Decisions\n\n### Chose Python\n\n**Choice:** Python for new reasons.\n\n"
        )
        uid = compute_source_uid("cross-row-1", "Decisions", "Chose Python", heading_ix=0)
        candidate_hash = compute_content_hash("**Choice:** Python for new reasons.")
        # Entry A: same source, old content. Entry B: different source, same content.
        learnings = (
            f'<!-- distill-meta {{"v": 1, "source_uid": "{uid}", "content_sha256": "sha256:old_content"}} -->\n'
            f'<!-- distill-meta {{"v": 1, "source_uid": "sha256:unrelated", "content_sha256": "{candidate_hash}"}} -->\n'
        )
        result = extract_candidates(str(handoff), learnings)
        assert result["candidates"][0]["dedup_status"] == "UPDATED_SOURCE"


class TestExtractSignals:
    """Tests for extract_signals — best-effort field extraction."""

    def test_extracts_confidence(self) -> None:
        md = "**Choice:** Chose A.\n\n**Confidence:** High (E2) — prototyped all three."
        signals = extract_signals(md)
        assert signals["confidence"] == "High (E2) — prototyped all three."

    def test_extracts_reversibility(self) -> None:
        md = "**Choice:** Chose A.\n\n**Reversibility:** Medium — can swap module."
        signals = extract_signals(md)
        assert signals["reversibility"] == "Medium — can swap module."

    def test_missing_fields_omitted(self) -> None:
        md = "**Choice:** Chose A.\n\n**Driver:** Speed."
        signals = extract_signals(md)
        assert signals == {}

    def test_multiline_value_takes_first_line(self) -> None:
        md = "**Confidence:** High (E2) — verified by tests.\nMore detail on next line."
        signals = extract_signals(md)
        assert signals["confidence"] == "High (E2) — verified by tests."


class TestExtractCandidates:
    """Tests for extract_candidates — full extraction pipeline."""

    def test_extracts_decisions_and_learnings(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Decisions\n\n"
            "### Chose Python\n\n"
            "**Choice:** Python over Rust.\n\n"
            "**Confidence:** High (E1).\n\n"
            "## Learnings\n\n"
            "### Token bucket smooths bursts\n\n"
            "**Mechanism:** Tokens refill at constant rate.\n\n"
            "**Evidence:** Prototype comparison.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert result["handoff_date"] == "2026-02-27"
        assert len(result["candidates"]) == 2
        assert result["candidates"][0]["source_section"] == "Decisions"
        assert result["candidates"][0]["subsection_heading"] == "Chose Python"
        assert result["candidates"][0]["dedup_status"] == "NEW"
        assert result["candidates"][1]["source_section"] == "Learnings"

    def test_codebase_knowledge_gets_durability_hint(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Codebase Knowledge\n\n"
            "### Plugin hook naming pattern\n\n"
            "Hooks use `mcp__plugin_<name>__<tool>` format.\n\n"
            "### Current plugin architecture\n\n"
            "The plugin has 3 scripts.\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) == 2
        assert result["candidates"][0].get("durability_hint") == "likely_durable"
        assert result["candidates"][1].get("durability_hint") == "likely_ephemeral"

    def test_exact_dup_detected(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-session-123\n---\n\n"
            "## Decisions\n\n"
            "### Chose Python\n\n"
            "**Choice:** Python.\n\n"
        )
        from scripts.distill import compute_source_uid, compute_content_hash
        uid = compute_source_uid("test-session-123", "Decisions", "Chose Python", heading_ix=0)
        chash = compute_content_hash("**Choice:** Python.")
        learnings = f'<!-- distill-meta {{"v": 1, "source_uid": "{uid}", "content_sha256": "{chash}"}} -->\n'
        result = extract_candidates(str(handoff), learnings)
        assert result["candidates"][0]["dedup_status"] == "EXACT_DUP_SOURCE"

    def test_heading_only_subsection_with_no_body_is_skipped(self, tmp_path: Path) -> None:
        """A subsection with a heading but empty/whitespace body produces no candidate."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: skip-1\n---\n\n"
            "## Decisions\n\n### Empty Decision\n\n### Real Decision\n\n**Choice:** Chose A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        headings = [c["subsection_heading"] for c in result["candidates"]]
        assert "Real Decision" in headings
        assert "Empty Decision" not in headings, "Empty subsections should be skipped"

    def test_empty_sections_produce_no_candidates(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Decisions\n\n"
            "## Learnings\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) == 0


class TestRoundTripIdempotence:
    """Extract → write meta → re-extract must produce EXACT_DUP_SOURCE."""

    def test_extract_write_reextract_is_exact_dup(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: round-trip-1\n---\n\n"
            "## Decisions\n\n### Chose Python\n\n**Choice:** Python.\n\n"
        )
        result1 = extract_candidates(str(handoff), "")
        candidate = result1["candidates"][0]
        assert candidate["dedup_status"] == "NEW"
        meta = make_distill_meta(
            source_uid=candidate["source_uid"],
            source_anchor=candidate["source_anchor"],
            content_sha256=candidate["content_sha256"],
            distilled_at="2026-02-27",
        )
        learnings = f"### 2026-02-27 [architecture]\n\nSynthesized.\n{meta}\n"
        result2 = extract_candidates(str(handoff), learnings)
        assert result2["candidates"][0]["dedup_status"] == "EXACT_DUP_SOURCE"


class TestOutputContract:
    """Verify the script/skill interface contract."""

    def test_required_top_level_keys(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: contract-1\n---\n\n"
            "## Decisions\n\n### Sub\n\n**Choice:** A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        required = {"handoff_path", "handoff_date", "handoff_title",
                     "candidates", "error", "output_version", "error_code", "warnings"}
        assert required.issubset(result.keys())
        assert result["output_version"] == 1

    def test_candidate_required_keys(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: contract-2\n---\n\n"
            "## Decisions\n\n### Sub\n\n**Choice:** A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        candidate = result["candidates"][0]
        required = {"source_section", "subsection_heading", "raw_markdown", "signals",
                     "source_uid", "content_sha256", "source_anchor", "dedup_status"}
        assert required.issubset(candidate.keys())

    def test_dedup_status_is_known_enum(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: contract-3\n---\n\n"
            "## Decisions\n\n### Sub\n\n**Choice:** A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        allowed = {"NEW", "EXACT_DUP_SOURCE", "EXACT_DUP_CONTENT", "UPDATED_SOURCE"}
        for c in result["candidates"]:
            assert c["dedup_status"] in allowed


class TestDistillCLI:
    """Integration tests for the CLI entry point."""

    def test_json_output(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Decisions\n\n"
            "### Chose A\n\n"
            "**Choice:** A over B.\n\n"
        )
        output = distill_main([str(handoff)])
        result = json.loads(output)
        assert result["handoff_path"] == str(handoff)
        assert len(result["candidates"]) == 1

    def test_with_learnings_file(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Learnings\n\n"
            "### Important thing\n\n"
            "**Mechanism:** Works like this.\n\n"
        )
        learnings = tmp_path / "learnings.md"
        learnings.write_text("# Learnings\n\nNo distill-meta comments.\n")
        output = distill_main([str(handoff), "--learnings", str(learnings)])
        result = json.loads(output)
        assert result["candidates"][0]["dedup_status"] == "NEW"

    def test_missing_handoff_returns_error(self) -> None:
        output = distill_main(["/nonexistent/path.md"])
        result = json.loads(output)
        assert result["error"] is not None
        assert result["error_code"] == "HANDOFF_NOT_FOUND"

    def test_unreadable_learnings_returns_error(self, tmp_path: Path) -> None:
        """Note: chmod(0o000) does not block root. Guard with skipif if flaky on CI."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        learnings = tmp_path / "learnings.md"
        learnings.write_text("content")
        learnings.chmod(0o000)
        try:
            output = distill_main([str(handoff), "--learnings", str(learnings)])
            result = json.loads(output)
            assert result["error"] is not None
            assert result["error_code"] == "LEARNINGS_UNREADABLE"
            assert "Failed to read" in result["error"]
        finally:
            learnings.chmod(0o644)

    def test_error_response_includes_warnings_key(self) -> None:
        """Error responses must include warnings key to prevent KeyError in callers."""
        output = distill_main(["/nonexistent/file.md"])
        result = json.loads(output)
        assert "warnings" in result
        assert isinstance(result["warnings"], list)

    def test_learnings_unreadable_includes_warnings_key(self, tmp_path: Path) -> None:
        """LEARNINGS_UNREADABLE error must include warnings key."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: warn-3\n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        bad_learnings = tmp_path / "learnings.md"
        bad_learnings.write_text("content")
        bad_learnings.chmod(0o000)
        try:
            output = distill_main([str(handoff), "--learnings", str(bad_learnings)])
            result = json.loads(output)
            assert "warnings" in result
            assert isinstance(result["warnings"], list)
        finally:
            bad_learnings.chmod(0o644)


class TestNoDocumentIdentity:
    """Integration: extract_candidates returns NO_DOCUMENT_IDENTITY for missing session_id."""

    def test_missing_session_id_returns_error(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert result["error_code"] == "NO_DOCUMENT_IDENTITY"
        assert result["error"] is not None
        assert len(result["candidates"]) == 0

    def test_blank_session_id_returns_error(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\nsession_id:   \n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert result["error_code"] == "NO_DOCUMENT_IDENTITY"


class TestEdgeCases:
    """Edge case tests from evaluative review."""

    def test_no_heading_subsection_is_candidate(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: edge-1\n---\n\n"
            "## Learnings\n\nStandalone learning without a ### heading.\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["subsection_heading"] == ""

    def test_malformed_distill_meta_does_not_crash(self) -> None:
        from scripts.distill import _extract_distill_metas
        learnings = (
            '<!-- distill-meta {broken json here -->\n'
            '<!-- distill-meta {"v": 1, "source_uid": "sha256:good"} -->\n'
            '<!-- distill-meta not-even-braces -->\n'
        )
        metas = _extract_distill_metas(learnings)
        assert len(metas) == 1
        assert metas[0]["source_uid"] == "sha256:good"

    def test_malformed_distill_meta_returns_warning(self) -> None:
        from scripts.distill import _extract_distill_metas_detailed
        # Regex requires {…} — use valid braces with invalid JSON inside
        metas, warnings = _extract_distill_metas_detailed(
            '<!-- distill-meta {broken json} -->'
        )
        assert len(metas) == 0
        assert len(warnings) == 1
        assert "malformed distill-meta skipped" in warnings[0]

    def test_detailed_returns_valid_metas_alongside_warnings(self) -> None:
        from scripts.distill import _extract_distill_metas_detailed
        content = (
            '<!-- distill-meta {"source_uid": "sha256:abc"} -->\n'
            '<!-- distill-meta {broken json} -->\n'
            '<!-- distill-meta {"source_uid": "sha256:def"} -->'
        )
        metas, warnings = _extract_distill_metas_detailed(content)
        assert len(metas) == 2
        assert len(warnings) == 1


class TestSourceUidDeterminism:
    """Golden-vector test: fixed input -> fixed output hash."""

    def test_golden_vector(self) -> None:
        uid = compute_source_uid(
            document_identity="test-session-123",
            section_name="Decisions",
            subsection_heading="Chose A over B",
            heading_ix=0,
        )
        # Pin the exact digest. If this changes, all existing provenance
        # data in learnings.md is orphaned (dedup breaks silently).
        assert uid == "sha256:dd731e5655b29e2d71dea5bfe2897cf9e4cb1db312a099bac373825bdaa5607c"


class TestNoAutodropInvariant:
    """Dedup status is a LABEL, not a filter. All candidates are returned."""

    def test_exact_dup_source_still_in_output(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: abc-123\n---\n\n"
            "## Decisions\n\n### Chose Python\n\n**Choice:** Python.\n\n"
        )
        from scripts.distill import compute_source_uid, compute_content_hash
        uid = compute_source_uid("abc-123", "Decisions", "Chose Python", heading_ix=0)
        chash = compute_content_hash("**Choice:** Python.")
        learnings = f'<!-- distill-meta {{"v": 1, "source_uid": "{uid}", "content_sha256": "{chash}"}} -->\n'
        result = extract_candidates(str(handoff), learnings)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["dedup_status"] == "EXACT_DUP_SOURCE"

    def test_exact_dup_content_still_in_output(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Decisions\n\n### Chose Python\n\n**Choice:** Python.\n\n"
        )
        from scripts.distill import compute_content_hash
        h = compute_content_hash("**Choice:** Python.")
        learnings = f'<!-- distill-meta {{"v": 1, "content_sha256": "{h}"}} -->\n'
        result = extract_candidates(str(handoff), learnings)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["dedup_status"] == "EXACT_DUP_CONTENT"


class TestUpdatedSource:
    """UPDATED_SOURCE: same source_uid, different content_sha256."""

    def test_updated_source_detected(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: update-test\n---\n\n"
            "## Decisions\n\n### Chose Python\n\n**Choice:** Python for speed.\n\n"
        )
        from scripts.distill import compute_source_uid
        uid = compute_source_uid("update-test", "Decisions", "Chose Python", heading_ix=0)
        learnings = f'<!-- distill-meta {{"v": 1, "source_uid": "{uid}", "content_sha256": "sha256:old_hash"}} -->\n'
        result = extract_candidates(str(handoff), learnings)
        assert result["candidates"][0]["dedup_status"] == "UPDATED_SOURCE"


class TestGotchasExtraction:
    """Gotchas section should be extracted as candidates."""

    def test_gotchas_extracted(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: test-sess\n---\n\n"
            "## Gotchas\n\n"
            "### Heredoc substitution unreliable\n\n"
            "zsh heredoc fails silently.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["source_section"] == "Gotchas"


class TestPreambleMerge:
    """Preamble (leading text before first ###) is merged into first headed subsection."""

    def test_preamble_merged_into_first_subsection(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: preamble-1\n---\n\n"
            "## Decisions\n\n"
            "Some introductory context about decisions.\n\n"
            "### Chose A\n\n**Choice:** A over B.\n\n"
            "### Chose C\n\n**Choice:** C over D.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) == 2
        assert "Some introductory context" in result["candidates"][0]["raw_markdown"]
        assert result["candidates"][0]["subsection_heading"] == "Chose A"

    def test_no_preamble_no_change(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: preamble-2\n---\n\n"
            "## Decisions\n\n"
            "### Chose A\n\n**Choice:** A.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) == 1
        assert "Some introductory" not in result["candidates"][0]["raw_markdown"]


class TestIncludeSection:
    """--include-section adds extra sections to extraction scope."""

    def test_context_section_extracted_when_included(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: context-1\n---\n\n"
            "## Context\n\n### Environment setup\n\nRun on Python 3.11.\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        result_default = extract_candidates(str(handoff), "")
        sections = {c["source_section"] for c in result_default["candidates"]}
        assert "Context" not in sections
        result_include = extract_candidates(str(handoff), "", extra_sections=("Context",))
        sections = {c["source_section"] for c in result_include["candidates"]}
        assert "Context" in sections
        assert len(result_include["candidates"]) == 2

    def test_include_section_cli(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: context-2\n---\n\n"
            "## Context\n\n### Setup\n\nDetails.\n\n"
        )
        output = distill_main([str(handoff), "--include-section", "Context"])
        result = json.loads(output)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["source_section"] == "Context"


class TestHandoffReadError:
    """extract_candidates handles OSError/UnicodeDecodeError from parse_handoff."""

    def test_unreadable_handoff_returns_error(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text("content")
        handoff.chmod(0o000)
        try:
            result = extract_candidates(str(handoff), "")
            assert result["error"] is not None
            assert result["error_code"] == "HANDOFF_UNREADABLE"
        finally:
            handoff.chmod(0o644)

    def test_binary_handoff_returns_error(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_bytes(b'\x80\x81\x82\xff' * 100)
        result = extract_candidates(str(handoff), "")
        assert result["error"] is not None
        assert result["error_code"] == "HANDOFF_UNREADABLE"


class TestLearningsWarning:
    """--learnings with nonexistent path warns instead of silent dedup disable."""

    def test_nonexistent_learnings_still_runs(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: warn-1\n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        output = distill_main([str(handoff), "--learnings", "/nonexistent/path.md"])
        result = json.loads(output)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["dedup_status"] == "NEW"

    def test_nonexistent_learnings_adds_warning_to_json(self, tmp_path: Path) -> None:
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: warn-2\n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        output = distill_main([str(handoff), "--learnings", "/nonexistent/path.md"])
        result = json.loads(output)
        assert any("Dedup checking disabled" in w for w in result.get("warnings", []))


class TestPathIndependence:
    """Integration test: source_uid is stable across filesystem paths."""

    def test_same_handoff_different_paths_same_uid(self, tmp_path: Path) -> None:
        content = (
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: stable-uid-test\n---\n\n"
            "## Decisions\n\n### Chose A\n\n**Choice:** A.\n\n"
        )
        path_a = tmp_path / "handoff.md"
        path_b = tmp_path / "archive" / "handoff.md"
        path_b.parent.mkdir()
        path_a.write_text(content)
        path_b.write_text(content)
        result_a = extract_candidates(str(path_a), "")
        result_b = extract_candidates(str(path_b), "")
        assert result_a["candidates"][0]["source_uid"] == result_b["candidates"][0]["source_uid"]


class TestPreambleMergeHashStability:
    """Preamble merge must not change content hashes — dedup depends on it."""

    def test_preamble_merge_preserves_content_hash(self, tmp_path: Path) -> None:
        """A handoff with preamble text before the first ### heading should
        produce the same content_sha256 whether or not frozen dataclasses
        are used — the whitespace semantics must be identical."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: hash-1\n---\n\n"
            "## Decisions\n\n"
            "Some preamble text before the first subsection.\n\n"
            "### Chose A over B\n\n**Choice:** A is better.\n\n"
        )
        result = extract_candidates(str(handoff), "")
        assert len(result["candidates"]) >= 1
        first_hash = result["candidates"][0]["content_sha256"]

        # Run again — hash must be identical (deterministic)
        result2 = extract_candidates(str(handoff), "")
        assert result2["candidates"][0]["content_sha256"] == first_hash

    def test_preamble_merge_round_trip_dedup(self, tmp_path: Path) -> None:
        """Extracting the same handoff twice with learnings from the first
        extraction should produce EXACT_DUP_SOURCE, not UPDATED_SOURCE.
        This gates the preamble merge refactor."""
        handoff = tmp_path / "test.md"
        handoff.write_text(
            "---\ntitle: Test\ndate: 2026-02-27\ntype: handoff\nsession_id: hash-2\n---\n\n"
            "## Decisions\n\n"
            "Preamble context.\n\n"
            "### Chose X\n\n**Choice:** X wins.\n\n"
        )
        # First extraction — no learnings
        result1 = extract_candidates(str(handoff), "")
        assert len(result1["candidates"]) >= 1
        c = result1["candidates"][0]

        # Build synthetic learnings with distill-meta from first extraction
        learnings_with_meta = (
            f"## Extracted\n\n### {c['subsection_heading']}\n\n"
            f"{c['raw_markdown']}\n\n"
            f"<!-- distill-meta {{"
            f'"source_uid": "{c["source_uid"]}", '
            f'"content_sha256": "{c["content_sha256"]}", '
            f'"source_anchor": "{c["source_anchor"]}"'
            f"}} -->\n"
        )

        # Second extraction — with learnings
        result2 = extract_candidates(str(handoff), learnings_with_meta)
        c2 = [x for x in result2["candidates"] if x["subsection_heading"] == c["subsection_heading"]][0]
        assert c2["dedup_status"] == "EXACT_DUP_SOURCE", (
            f"Preamble merge changed content hash! Expected EXACT_DUP_SOURCE, got {c2['dedup_status']}"
        )


class TestMakeAnchorEdgeCases:
    """Edge cases for _make_anchor."""

    def test_empty_heading_produces_valid_anchor(self) -> None:
        from scripts.distill import _make_anchor
        anchor = _make_anchor("handoff.md", "Decisions", "")
        assert anchor == "handoff.md#decisions/"
