"""Shared test fixtures for ticket plugin tests."""
from __future__ import annotations

from pathlib import Path
import pytest


@pytest.fixture
def tmp_tickets(tmp_path: Path) -> Path:
    """Create a temporary docs/tickets/ directory with project root marker."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    return tickets_dir


@pytest.fixture
def tmp_audit(tmp_path: Path) -> Path:
    """Create a temporary docs/tickets/.audit/ directory."""
    audit_dir = tmp_path / "docs" / "tickets" / ".audit"
    audit_dir.mkdir(parents=True)
    return audit_dir
