"""Tests for ticket_parsing.py — fenced-YAML ticket format parser."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

# --- Fixtures ---

MINIMAL_TICKET = """\
# T-20260228-01: Example ticket

```yaml
id: T-20260228-01
date: 2026-02-28
status: deferred
priority: medium
```

## Problem

Something is wrong.
"""

TICKET_WITH_LISTS = """\
# T-20260228-02: Ticket with lists

```yaml
id: T-20260228-02
date: 2026-02-28
status: open
priority: high
source_type: pr-review
source_ref: "PR #29"
branch: feature/knowledge-graduation
blocked_by: []
blocks: []
effort: XS
files:
  - path/to/file.py
  - path/to/other.py
provenance:
  source_session: "5136e38e-efc5-403f-ad5e-49516f47884b"
  source_type: pr-review
  created_by: defer-skill
```

## Problem

Something with lists.
"""

LEGACY_TICKET = """\
# T-A: Legacy ticket

```yaml
id: T-A
date: 2026-02-17
status: complete
priority: medium
blocked_by: []
blocks: []
related:
  - T-B
  - T-C
plugin: packages/plugins/handoff/
```

## Summary

Legacy content.
"""

NO_FENCED_YAML = """\
# No YAML here

## Problem

Just markdown, no fenced YAML block.
"""

MALFORMED_YAML = """\
# Bad YAML

```yaml
id: T-BAD
date: 2026-02-28
status: [invalid unclosed
```

## Problem

Broken YAML.
"""


class TestExtractFencedYaml:
    def test_minimal_ticket(self) -> None:
        from scripts.ticket_parsing import extract_fenced_yaml

        result = extract_fenced_yaml(MINIMAL_TICKET)
        assert result is not None
        assert "id: T-20260228-01" in result

    def test_ticket_with_lists(self) -> None:
        from scripts.ticket_parsing import extract_fenced_yaml

        result = extract_fenced_yaml(TICKET_WITH_LISTS)
        assert result is not None
        assert "files:" in result
        assert "provenance:" in result

    def test_no_fenced_yaml_returns_none(self) -> None:
        from scripts.ticket_parsing import extract_fenced_yaml

        result = extract_fenced_yaml(NO_FENCED_YAML)
        assert result is None

    def test_extracts_first_yaml_block_only(self) -> None:
        from scripts.ticket_parsing import extract_fenced_yaml

        text = "```yaml\nfirst: block\n```\n\n```yaml\nsecond: block\n```"
        result = extract_fenced_yaml(text)
        assert result is not None
        assert "first: block" in result
        assert "second" not in result


def extract_fenced_yaml_helper(text: str) -> str:
    """Helper to extract YAML for tests that need parsed YAML input."""
    from scripts.ticket_parsing import extract_fenced_yaml

    result = extract_fenced_yaml(text)
    assert result is not None
    return result


class TestParseYamlFrontmatter:
    def test_minimal_fields(self) -> None:
        from scripts.ticket_parsing import parse_yaml_frontmatter

        result = parse_yaml_frontmatter("id: T-20260228-01\ndate: 2026-02-28\nstatus: deferred")
        assert result["id"] == "T-20260228-01"
        assert result["status"] == "deferred"

    def test_date_normalized_to_string(self) -> None:
        """P0-3: yaml.safe_load converts unquoted dates to datetime.date objects."""
        from scripts.ticket_parsing import parse_yaml_frontmatter

        result = parse_yaml_frontmatter("id: T-20260228-01\ndate: 2026-02-28\nstatus: deferred")
        assert isinstance(result["date"], str), f"date must be str, got {type(result['date'])}"
        assert result["date"] == "2026-02-28"

    def test_list_fields_preserved(self) -> None:
        from scripts.ticket_parsing import parse_yaml_frontmatter

        yaml_text = extract_fenced_yaml_helper(TICKET_WITH_LISTS)
        result = parse_yaml_frontmatter(yaml_text)
        assert isinstance(result["files"], list)
        assert len(result["files"]) == 2
        assert isinstance(result["provenance"], dict)

    def test_malformed_yaml_returns_none(self) -> None:
        from scripts.ticket_parsing import parse_yaml_frontmatter

        result = parse_yaml_frontmatter("id: [invalid unclosed")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        from scripts.ticket_parsing import parse_yaml_frontmatter

        result = parse_yaml_frontmatter("")
        assert result is None


class TestValidateSchema:
    def test_valid_minimal(self) -> None:
        from scripts.ticket_parsing import validate_schema

        data = {"id": "T-20260228-01", "date": "2026-02-28", "status": "deferred"}
        errors = validate_schema(data)
        assert errors == []

    def test_missing_required_field(self) -> None:
        from scripts.ticket_parsing import validate_schema

        data = {"id": "T-20260228-01", "date": "2026-02-28"}  # missing status
        errors = validate_schema(data)
        assert any("status" in e for e in errors)

    def test_files_must_be_list(self) -> None:
        from scripts.ticket_parsing import validate_schema

        data = {"id": "T-1", "date": "2026-02-28", "status": "open", "files": "not-a-list"}
        errors = validate_schema(data)
        assert any("files" in e for e in errors)

    def test_provenance_must_be_dict(self) -> None:
        from scripts.ticket_parsing import validate_schema

        data = {"id": "T-1", "date": "2026-02-28", "status": "open", "provenance": "bad"}
        errors = validate_schema(data)
        assert any("provenance" in e for e in errors)

    def test_status_must_be_string(self) -> None:
        from scripts.ticket_parsing import validate_schema

        data = {"id": "T-1", "date": "2026-02-28", "status": 42}
        errors = validate_schema(data)
        assert any("status" in e for e in errors)


class TestParseTicket:
    def test_parse_minimal_ticket(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import TicketFile, parse_ticket

        ticket = tmp_path / "test.md"
        ticket.write_text(MINIMAL_TICKET)
        result = parse_ticket(ticket)
        assert isinstance(result, TicketFile)
        assert result.frontmatter["id"] == "T-20260228-01"
        assert result.frontmatter["status"] == "deferred"
        assert "## Problem" in result.body

    def test_parse_ticket_with_lists(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import parse_ticket

        ticket = tmp_path / "test.md"
        ticket.write_text(TICKET_WITH_LISTS)
        result = parse_ticket(ticket)
        assert isinstance(result.frontmatter["files"], list)
        assert len(result.frontmatter["files"]) == 2

    def test_parse_legacy_ticket(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import parse_ticket

        ticket = tmp_path / "test.md"
        ticket.write_text(LEGACY_TICKET)
        result = parse_ticket(ticket)
        assert result.frontmatter["id"] == "T-A"
        assert result.frontmatter["status"] == "complete"
        assert isinstance(result.frontmatter["related"], list)

    def test_parse_no_yaml_returns_none(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import parse_ticket

        ticket = tmp_path / "test.md"
        ticket.write_text(NO_FENCED_YAML)
        result = parse_ticket(ticket)
        assert result is None

    def test_parse_malformed_yaml_returns_none(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import parse_ticket

        ticket = tmp_path / "test.md"
        ticket.write_text(MALFORMED_YAML)
        result = parse_ticket(ticket)
        assert result is None

    def test_ticketfile_is_frozen(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import parse_ticket

        ticket = tmp_path / "test.md"
        ticket.write_text(MINIMAL_TICKET)
        result = parse_ticket(ticket)
        with pytest.raises(FrozenInstanceError):
            result.path = "other"  # type: ignore[misc]

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        from scripts.ticket_parsing import parse_ticket

        result = parse_ticket(tmp_path / "nonexistent.md")
        assert result is None


class TestParseTicketWarnings:
    """C3/C5: parse_ticket must emit warnings with diagnostic info for each failure mode."""

    def test_warns_on_unreadable_file(self, tmp_path: Path) -> None:
        import warnings

        from scripts.ticket_parsing import parse_ticket

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_ticket(tmp_path / "nonexistent.md")
        assert result is None
        assert len(w) == 1
        assert "Cannot read" in str(w[0].message)

    def test_warns_on_no_yaml_block(self, tmp_path: Path) -> None:
        import warnings

        from scripts.ticket_parsing import parse_ticket

        (tmp_path / "no-yaml.md").write_text("# Just text\n\nNo YAML here.")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_ticket(tmp_path / "no-yaml.md")
        assert result is None
        assert len(w) == 1
        assert "No fenced YAML" in str(w[0].message)

    def test_warns_on_malformed_yaml_with_detail(self, tmp_path: Path) -> None:
        import warnings

        from scripts.ticket_parsing import parse_ticket

        (tmp_path / "bad.md").write_text(MALFORMED_YAML)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_ticket(tmp_path / "bad.md")
        assert result is None
        # Exactly 2 warnings: one from parse_yaml_frontmatter (YAML detail),
        # one from parse_ticket (file path context). This double-warning is
        # intentional — see parse_ticket implementation comment.
        assert len(w) == 2, f"Expected exactly 2 warnings for malformed YAML, got {len(w)}"
        yaml_warns = [x for x in w if "YAML parse error" in str(x.message)]
        path_warns = [x for x in w if "bad.md" in str(x.message)]
        assert len(yaml_warns) == 1, "Should include YAML error detail"
        assert len(path_warns) == 1, "Should include file path context"

    def test_warns_on_schema_validation_with_errors(self, tmp_path: Path) -> None:
        import warnings

        from scripts.ticket_parsing import parse_ticket

        # Missing required 'status' field
        bad_schema = '# Bad\n\n```yaml\nid: T-1\ndate: 2026-02-28\n```\n\n## Problem\n\nNo status.'
        (tmp_path / "schema.md").write_text(bad_schema)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_ticket(tmp_path / "schema.md")
        assert result is None
        assert any("Schema validation failed for" in str(x.message) for x in w), "Should include schema error detail"
