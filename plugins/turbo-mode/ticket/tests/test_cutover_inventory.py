"""Tests for read-only legacy ticket cutover inventory."""

from __future__ import annotations

import textwrap

import pytest
from scripts.ticket_cutover_inventory import inspect_legacy_ticket_for_cutover

from tests.support.builders import (
    make_gen1_ticket,
    make_gen4_ticket,
    make_legacy_ticket_for_cutover,
)


def test_inventory_reports_current_legacy_shape(tmp_tickets) -> None:
    path = make_legacy_ticket_for_cutover(
        tmp_tickets,
        filename="2026-03-02-legacy.md",
        id="T-20260302-01",
        status="deferred",
        priority="medium",
        extra_yaml='component: ticket\ncontract_version: "1.0"\n',
        extra_sections=textwrap.dedent(
            """\

            ## Acceptance Criteria
            - [ ] Normalize this ticket

            ## Key Files
            | File | Role |
            |------|------|
            | docs/tickets/old.md | Legacy |
            """
        ),
    )

    inventory = inspect_legacy_ticket_for_cutover(path)

    assert inventory.source_path == path
    assert inventory.current_id == "T-20260302-01"
    assert inventory.proposed_target_path.name == "T-20260302-01.md"
    assert inventory.metadata_container == "fenced_yaml"
    assert "component" in inventory.unknown_keys
    assert "contract_version" in inventory.unknown_keys
    assert inventory.status_mapping_needed == "deferred->open"
    assert inventory.priority_mapping_needed == "medium->normal"
    assert inventory.missing_required_sections == ("Next Action", "Change History")
    assert inventory.optional_sections_to_preserve == ("Acceptance Criteria", "Key Files")
    assert inventory.blocked_by == ()
    assert inventory.state == "ready_to_apply"


def test_inventory_proposes_id_from_legacy_date(tmp_tickets) -> None:
    path = make_gen1_ticket(tmp_tickets)

    inventory = inspect_legacy_ticket_for_cutover(path)

    assert inventory.current_id == "handoff-chain-viz"
    assert inventory.proposed_target_path.name == "T-20260115-01.md"
    assert inventory.metadata_container == "fenced_yaml"
    assert inventory.missing_required_sections == ("Next Action", "Change History")


def test_inventory_preserves_blocker_list(tmp_tickets) -> None:
    path = make_gen4_ticket(tmp_tickets)

    inventory = inspect_legacy_ticket_for_cutover(path)

    assert inventory.current_id == "T-20260301-01"
    assert inventory.proposed_target_path.name == "T-20260301-01.md"
    assert inventory.status_mapping_needed == "deferred->open"
    assert inventory.priority_mapping_needed == "medium->normal"
    assert inventory.blocked_by == ()


def test_inventory_rejects_missing_fenced_yaml(tmp_tickets) -> None:
    path = tmp_tickets / "not-a-ticket.md"
    path.write_text("# Not a legacy ticket\n", encoding="utf-8")

    with pytest.raises(ValueError, match="fenced YAML"):
        inspect_legacy_ticket_for_cutover(path)


def test_inventory_reports_blocked_without_derivable_id(tmp_tickets) -> None:
    path = tmp_tickets / "legacy-no-date.md"
    path.write_text(
        "# legacy: Legacy\n\n"
        "```yaml\n"
        "id: legacy-slug\n"
        "status: open\n"
        "priority: medium\n"
        "```\n\n"
        "## Problem\nSomething.\n",
        encoding="utf-8",
    )

    inventory = inspect_legacy_ticket_for_cutover(path)

    assert inventory.state == "blocked"
    assert inventory.proposed_target_path == path.parent


def test_inventory_maps_critical_priority_to_high(tmp_tickets) -> None:
    path = make_legacy_ticket_for_cutover(
        tmp_tickets,
        filename="2026-03-02-legacy.md",
        id="T-20260302-01",
        priority="critical",
    )

    inventory = inspect_legacy_ticket_for_cutover(path)

    assert inventory.priority_mapping_needed == "critical->high"


def test_inventory_preserves_populated_blocker_list(tmp_tickets) -> None:
    path = tmp_tickets / "2026-03-02-legacy.md"
    path.write_text(
        "# T-20260302-01: Legacy\n\n"
        "```yaml\n"
        "id: T-20260302-01\n"
        'date: "2026-03-02"\n'
        "status: open\n"
        "priority: medium\n"
        "blocked_by:\n"
        "  - T-20260301-01\n"
        "  - T-20260301-02\n"
        "```\n\n"
        "## Problem\nSomething.\n",
        encoding="utf-8",
    )

    inventory = inspect_legacy_ticket_for_cutover(path)

    assert inventory.blocked_by == ("T-20260301-01", "T-20260301-02")


def test_inventory_rejects_invalid_fenced_yaml(tmp_tickets) -> None:
    path = tmp_tickets / "bad-yaml.md"
    path.write_text(
        "# legacy: Legacy\n\n```yaml\nid: [unterminated\n```\n\n## Problem\nx\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid fenced YAML"):
        inspect_legacy_ticket_for_cutover(path)
