#!/usr/bin/env python3
"""Agent entrypoint for the ticket engine.

Hardcodes request_origin="agent" for guarded Ticket engine operations. Direct
execute is not an autonomous write route; source autonomous writes enter through
ticket_autonomy.py apply-turn and the runtime-first gateway.
Launcher: uv run python -B <PLUGIN_ROOT>/scripts/ticket_engine_agent.py <subcommand> <payload_file>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

# Add parent to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_engine_runner import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run("agent", prog="ticket_engine_agent.py"))
