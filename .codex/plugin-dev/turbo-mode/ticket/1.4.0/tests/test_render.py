"""Tests for ticket_render.py — markdown ticket rendering."""
from __future__ import annotations


from scripts.ticket_parse import extract_fenced_yaml
from scripts.ticket_render import render_ticket


class TestRenderTicket:
    def test_basic_ticket(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Fix authentication timeout",
            date="2026-03-02",
            status="open",
            priority="high",
            effort="S",
            source={"type": "ad-hoc", "ref": "", "session": "test-session"},
            tags=["auth", "api"],
            problem="Auth handler times out for payloads >10MB.",
            approach="Make timeout configurable per route.",
            acceptance_criteria=["Timeout configurable per route", "Default remains 30s"],
            verification="uv run pytest tests/test_auth.py",
            key_files=[
                {"file": "handler.py:45", "role": "Timeout logic", "look_for": "hardcoded timeout"},
            ],
        )
        assert "# T-20260302-01: Fix authentication timeout" in result
        assert "id: T-20260302-01" in result
        assert 'status: open' in result
        assert "## Problem" in result
        assert "## Approach" in result
        assert "## Acceptance Criteria" in result
        assert "- [ ] Timeout configurable per route" in result
        assert "## Verification" in result
        assert "## Key Files" in result
        assert 'contract_version: "1.0"' in result

    def test_minimal_ticket(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Minimal ticket",
            date="2026-03-02",
            status="open",
            priority="medium",
            problem="Something needs fixing.",
        )
        assert "# T-20260302-01: Minimal ticket" in result
        assert "## Problem" in result
        # Optional sections absent
        assert "## Context" not in result
        assert "## Prior Investigation" not in result

    def test_optional_sections_included(self):
        result = render_ticket(
            id="T-20260302-01",
            title="With extras",
            date="2026-03-02",
            status="open",
            priority="high",
            problem="Issue.",
            context="Found during refactor.",
            prior_investigation="Checked handler.py — timeout hardcoded.",
            decisions_made="Configurable timeout over fixed increase.",
            related="T-20260301-03 (API config refactor)",
        )
        assert "## Context" in result
        assert "## Prior Investigation" in result
        assert "## Decisions Made" in result
        assert "## Related" in result

    def test_blocked_by_and_blocks(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Blocked ticket",
            date="2026-03-02",
            status="blocked",
            priority="high",
            problem="Waiting on dependency.",
            blocked_by=["T-20260302-02"],
            blocks=["T-20260302-03"],
        )
        assert "blocked_by: [T-20260302-02]" in result
        assert "blocks: [T-20260302-03]" in result

    def test_defer_field(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Deferred ticket",
            date="2026-03-02",
            status="open",
            priority="low",
            problem="Can wait.",
            defer={"active": True, "reason": "Waiting for v2 API", "deferred_at": "2026-03-02"},
        )
        assert "defer:" in result
        assert "active: true" in result

    def test_render_ticket_uses_canonical_frontmatter_shape(self):
        result = render_ticket(
            id="T-20260302-01",
            title="Canonical serializer",
            date="2026-03-02",
            status="open",
            priority="high",
            effort="S",
            source={"type": "ad-hoc", "ref": "", "session": "test-session"},
            tags=["auth", "api"],
            problem="Serializer shape should match mutation paths.",
        )
        assert extract_fenced_yaml(result) == (
            "id: T-20260302-01\n"
            'date: "2026-03-02"\n'
            "status: open\n"
            "priority: high\n"
            "effort: S\n"
            "source:\n"
            "  type: ad-hoc\n"
            '  ref: ""\n'
            "  session: test-session\n"
            "tags: [auth, api]\n"
            "blocked_by: []\n"
            "blocks: []\n"
            'contract_version: "1.0"\n'
        )


def test_render_ticket_yaml_injection_source_ref(tmp_path):
    """Adversarial source.ref with YAML-special characters round-trips safely."""
    from scripts.ticket_parse import parse_ticket

    result = render_ticket(
        id="T-20260303-01",
        title="Test injection",
        date="2026-03-03",
        status="open",
        priority="medium",
        source={"type": "ad-hoc", "ref": 'value: "nested" and: more', "session": "s1"},
        problem="Problem text.",
    )
    # Write to file so parse_ticket (which reads from Path) can parse it
    ticket_file = tmp_path / "T-20260303-01.md"
    ticket_file.write_text(result, encoding="utf-8")
    ticket = parse_ticket(ticket_file)
    assert ticket is not None
    assert ticket.source["ref"] == 'value: "nested" and: more'


def test_render_ticket_yaml_injection_tags(tmp_path):
    """Tags containing YAML-special characters render as valid YAML."""
    from scripts.ticket_parse import parse_ticket

    result = render_ticket(
        id="T-20260303-02",
        title="Test tag injection",
        date="2026-03-03",
        status="open",
        priority="medium",
        tags=["tag: with colon", "tag\nwith\nnewline"],
        problem="Problem text.",
    )
    ticket_file = tmp_path / "T-20260303-02.md"
    ticket_file.write_text(result, encoding="utf-8")
    ticket = parse_ticket(ticket_file)
    assert ticket is not None
    assert "tag: with colon" in ticket.tags
    assert "tag\nwith\nnewline" in ticket.tags
