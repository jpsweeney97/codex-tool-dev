from __future__ import annotations

from pathlib import Path

import turbo_mode_handoff_runtime.chain_state as chain_state
from turbo_mode_handoff_runtime.chain_state import read_chain_state


def test_read_chain_state_reports_absent_when_no_candidates(tmp_path: Path) -> None:
    payload = read_chain_state(tmp_path, project_name="demo")

    assert payload["status"] == "absent"
    assert payload["source"] is None
    assert payload["state"] is None


def test_chain_state_does_not_export_legacy_consumed_prefix() -> None:
    assert not hasattr(chain_state, "LEGACY_CONSUMED_PREFIX")
