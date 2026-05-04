"""Tests for provenance.py — defer-meta/distill-meta parsing and session matching."""
from __future__ import annotations

import pytest

# --- Fixtures ---

DEFER_META_COMMENT = '<!-- defer-meta {"v": 1, "source_session": "5136e38e-efc5-403f-ad5e-49516f47884b", "source_type": "pr-review", "source_ref": "PR #29", "created_by": "defer-skill"} -->'

DISTILL_META_COMMENT = '<!-- distill-meta {"v": 1, "source_uid": "sha256:abc123", "source_anchor": "## Decisions", "content_sha256": "def456", "distilled_at": "2026-02-27T12:00:00Z"} -->'

TICKET_BODY_WITH_META = f"""\
## Problem

Something is wrong.

## Acceptance Criteria

- [ ] Fix it

{DEFER_META_COMMENT}
"""

TICKET_BODY_NO_META = """\
## Problem

Something is wrong.

## Acceptance Criteria

- [ ] Fix it
"""

PROVENANCE_YAML = {
    "source_session": "5136e38e-efc5-403f-ad5e-49516f47884b",
    "source_type": "pr-review",
    "created_by": "defer-skill",
}


class TestParseDeferMeta:
    def test_parses_valid_comment(self) -> None:
        from scripts.provenance import parse_defer_meta

        result = parse_defer_meta(TICKET_BODY_WITH_META)
        assert result is not None
        assert result["source_session"] == "5136e38e-efc5-403f-ad5e-49516f47884b"
        assert result["source_type"] == "pr-review"
        assert result["v"] == 1

    def test_no_comment_returns_none(self) -> None:
        from scripts.provenance import parse_defer_meta

        result = parse_defer_meta(TICKET_BODY_NO_META)
        assert result is None

    def test_malformed_json_returns_none(self) -> None:
        from scripts.provenance import parse_defer_meta

        result = parse_defer_meta('<!-- defer-meta {bad json} -->')
        assert result is None


class TestParseDistillMeta:
    def test_parses_valid_comment(self) -> None:
        from scripts.provenance import parse_distill_meta

        result = parse_distill_meta(f"Some text\n{DISTILL_META_COMMENT}\n")
        assert result is not None
        assert result["source_uid"] == "sha256:abc123"

    def test_no_comment_returns_none(self) -> None:
        from scripts.provenance import parse_distill_meta

        result = parse_distill_meta("No meta here")
        assert result is None


class TestReadProvenance:
    def test_yaml_field_primary(self) -> None:
        from scripts.provenance import read_provenance

        result = read_provenance(
            provenance_yaml=PROVENANCE_YAML,
            body_text=TICKET_BODY_WITH_META,
        )
        assert result is not None
        assert result["source_session"] == "5136e38e-efc5-403f-ad5e-49516f47884b"
        assert result["source"] == "yaml"

    def test_comment_fallback_when_no_yaml(self) -> None:
        from scripts.provenance import read_provenance

        result = read_provenance(
            provenance_yaml=None,
            body_text=TICKET_BODY_WITH_META,
        )
        assert result is not None
        assert result["source_session"] == "5136e38e-efc5-403f-ad5e-49516f47884b"
        assert result["source"] == "comment"

    def test_no_provenance_returns_none(self) -> None:
        from scripts.provenance import read_provenance

        result = read_provenance(provenance_yaml=None, body_text=TICKET_BODY_NO_META)
        assert result is None

    def test_yaml_wins_when_both_exist_and_disagree(self) -> None:
        from scripts.provenance import read_provenance

        yaml_data = {"source_session": "aaaa-yaml-wins", "source_type": "codex", "created_by": "defer-skill"}
        result = read_provenance(provenance_yaml=yaml_data, body_text=TICKET_BODY_WITH_META)
        assert result["source_session"] == "aaaa-yaml-wins"
        assert result["source"] == "yaml"


class TestReadProvenanceFallback:
    """P1-7 regression: empty/None source_session in YAML must fall back to comment."""

    def test_yaml_with_empty_session_falls_back_to_comment(self) -> None:
        from scripts.provenance import read_provenance

        result = read_provenance(
            provenance_yaml={"source_session": "", "source_type": "pr-review", "created_by": "defer-skill"},
            body_text=TICKET_BODY_WITH_META,
        )
        assert result is not None
        assert result["source"] == "comment"
        assert result["source_session"] == "5136e38e-efc5-403f-ad5e-49516f47884b"

    def test_yaml_with_none_session_falls_back_to_comment(self) -> None:
        from scripts.provenance import read_provenance

        result = read_provenance(
            provenance_yaml={"source_session": None, "source_type": "pr-review", "created_by": "defer-skill"},
            body_text=TICKET_BODY_WITH_META,
        )
        assert result is not None
        assert result["source"] == "comment"
        assert result["source_session"] == "5136e38e-efc5-403f-ad5e-49516f47884b"


class TestSessionMatch:
    def test_exact_uuid_match(self) -> None:
        from scripts.provenance import session_matches

        assert session_matches("5136e38e-efc5-403f-ad5e-49516f47884b", "5136e38e-efc5-403f-ad5e-49516f47884b")

    def test_no_match(self) -> None:
        from scripts.provenance import session_matches

        assert not session_matches("5136e38e-efc5-403f-ad5e-49516f47884b", "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    def test_none_returns_false(self) -> None:
        from scripts.provenance import session_matches

        assert not session_matches(None, "5136e38e-efc5-403f-ad5e-49516f47884b")
        assert not session_matches("5136e38e-efc5-403f-ad5e-49516f47884b", None)

    def test_empty_string_returns_false(self) -> None:
        """P1-7 fix: empty strings must not match each other."""
        from scripts.provenance import session_matches

        assert not session_matches("", "")
        assert not session_matches("", "5136e38e-efc5-403f-ad5e-49516f47884b")
        assert not session_matches("5136e38e-efc5-403f-ad5e-49516f47884b", "")


class TestProvenanceWarnings:
    """I3: JSON parse failures must warn, not silently return None."""

    def test_warns_on_malformed_defer_meta_json(self) -> None:
        import warnings

        from scripts.provenance import parse_defer_meta

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_defer_meta('<!-- defer-meta {bad json} -->')
        assert result is None
        assert len(w) == 1
        assert "JSON" in str(w[0].message)

    def test_warns_on_malformed_distill_meta_json(self) -> None:
        import warnings

        from scripts.provenance import parse_distill_meta

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_distill_meta('<!-- distill-meta {bad} -->')
        assert result is None
        assert len(w) == 1
        assert "JSON" in str(w[0].message)
