"""Ticket file builders and YAML assertion helpers for tests."""
from __future__ import annotations

import textwrap
from pathlib import Path


def make_ticket(
    tickets_dir: Path,
    filename: str,
    *,
    id: str = "T-20260302-01",
    date: str = "2026-03-02",
    created_at: str = "",
    status: str = "open",
    priority: str = "high",
    effort: str = "S",
    source_type: str = "ad-hoc",
    source_ref: str = "",
    session: str = "test-session",
    tags: list[str] | None = None,
    blocked_by: list[str] | None = None,
    blocks: list[str] | None = None,
    contract_version: str = "1.0",
    title: str = "Test ticket",
    problem: str = "Test problem description.",
    extra_yaml: str = "",
    extra_sections: str = "",
) -> Path:
    """Create a v1.0 format ticket file for testing.

    Returns the path to the created file.
    """
    tags = tags or []
    blocked_by = blocked_by or []
    blocks = blocks or []

    created_at_line = f'created_at: "{created_at}"\n        ' if created_at else ""
    content = textwrap.dedent(f"""\
        # {id}: {title}

        ```yaml
        id: {id}
        date: "{date}"
        {created_at_line}status: {status}
        priority: {priority}
        effort: {effort}
        source:
          type: {source_type}
          ref: "{source_ref}"
          session: "{session}"
        tags: {tags}
        blocked_by: {blocked_by}
        blocks: {blocks}
        contract_version: "{contract_version}"
        {extra_yaml}```

        ## Problem
        {problem}

        ## Approach
        Fix the issue.

        ## Acceptance Criteria
        - [ ] Issue resolved

        ## Verification
        ```bash
        echo "verified"
        ```

        ## Key Files
        | File | Role | Look For |
        |------|------|----------|
        | test.py | Test | Test code |
        {extra_sections}
    """)
    path = tickets_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def make_gen1_ticket(tickets_dir: Path, filename: str = "handoff-chain-viz.md") -> Path:
    """Gen 1 (hand-authored): slug ID, `plugin` field, `related` flat list."""
    content = textwrap.dedent("""\
        # handoff-chain-viz: Visualize handoff chains

        ```yaml
        id: handoff-chain-viz
        date: "2026-01-15"
        status: open
        plugin: handoff
        related: [handoff-search, handoff-quality-hook]
        ```

        ## Summary
        Build a visualization for handoff dependency chains.
    """)
    path = tickets_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def make_gen2_ticket(tickets_dir: Path, filename: str = "T-A-test.md") -> Path:
    """Gen 2 (letter IDs): T-[A-F] ID, `branch`, free-text `effort`."""
    content = textwrap.dedent("""\
        # T-A: Refactor analytics pipeline

        ```yaml
        id: T-A
        date: "2026-02-01"
        status: open
        priority: high
        effort: "S (1-2 sessions)"
        branch: feature/analytics-refactor
        blocked_by: []
        blocks: [T-B]
        ```

        ## Summary
        The analytics pipeline needs refactoring.

        ## Rationale
        Current design is too coupled.

        ## Design
        Decouple the pipeline stages.

        ## Risks
        Breaking existing consumers.
    """)
    path = tickets_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def make_gen3_ticket(tickets_dir: Path, filename: str = "T-003-test.md") -> Path:
    """Gen 3 (numeric IDs): T-NNN, `branch`, varied sections."""
    content = textwrap.dedent("""\
        # T-003: Fix session counting

        ```yaml
        id: T-003
        date: "2026-02-15"
        status: in_progress
        priority: medium
        branch: fix/session-counting
        blocked_by: []
        blocks: []
        ```

        ## Summary
        Session counting is off by one.

        ## Prerequisites
        Requires access to audit trail.

        ## Findings
        The counter increments before validation.

        ## Verification
        ```bash
        uv run pytest tests/test_sessions.py
        ```

        ## References
        - Related to handoff plugin session tracking
    """)
    path = tickets_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def make_gen4_ticket(tickets_dir: Path, filename: str = "2026-03-01-auth-timeout.md") -> Path:
    """Gen 4 (defer output): T-YYYYMMDD-NN, `source_type`, `provenance`, `status: deferred`."""
    content = textwrap.dedent("""\
        # T-20260301-01: Fix authentication timeout

        ```yaml
        id: T-20260301-01
        date: "2026-03-01"
        status: deferred
        priority: medium
        source_type: handoff
        source_ref: session-xyz
        provenance:
          created_by: defer.py
          session_id: xyz-123
          handoff_file: 2026-03-01_handoff.md
        tags: [auth, api]
        blocked_by: []
        blocks: []
        ```

        ## Problem
        Auth handler times out for large payloads.

        ## Source
        Found during API refactor session.

        ## Proposed Approach
        Make timeout configurable per route.

        ## Acceptance Criteria
        - [ ] Timeout configurable per route
    """)
    path = tickets_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def write_autonomy_config(tickets_dir: Path, text: str) -> Path:
    """Write .codex/ticket.local.md for tests using tmp_tickets."""
    project_root = tickets_dir.parent.parent
    codex_dir = project_root / ".codex"
    codex_dir.mkdir(exist_ok=True)
    config_path = codex_dir / "ticket.local.md"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def expected_canonical_yaml(
    *,
    ticket_id: str,
    date: str,
    status: str,
    priority: str,
    effort: str,
    source_type: str,
    source_ref: str,
    session: str,
    tags: list[str],
    blocked_by: list[str],
    blocks: list[str],
    created_at: str = "",
    contract_version: str = "1.0",
) -> str:
    """Build the expected canonical YAML block for assertion in execute tests."""
    created_at_line = f'created_at: "{created_at}"\n' if created_at else ""
    return (
        f"id: {ticket_id}\n"
        f'date: "{date}"\n'
        f"{created_at_line}"
        f"status: {status}\n"
        f"priority: {priority}\n"
        f"effort: {effort}\n"
        "source:\n"
        f"  type: {source_type}\n"
        f'  ref: "{source_ref}"\n'
        f"  session: {session}\n"
        f"tags: [{', '.join(tags)}]\n"
        f"blocked_by: [{', '.join(blocked_by)}]\n"
        f"blocks: [{', '.join(blocks)}]\n"
        f'contract_version: "{contract_version}"\n'
    )
