from __future__ import annotations

from pathlib import Path

TURBO_MODE_ROOT = Path(__file__).resolve().parents[3]
TICKET_HOOKS_JSON = TURBO_MODE_ROOT / "ticket/1.4.0/hooks/hooks.json"


def test_ticket_hook_manifest_uses_installed_writer_serialization() -> None:
    text = TICKET_HOOKS_JSON.read_text(encoding="utf-8")

    assert "\\u2014" in text
    assert " — " not in text
