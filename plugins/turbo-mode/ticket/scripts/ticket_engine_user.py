#!/usr/bin/env python3
"""User entrypoint for the ticket engine.

Hardcodes request_origin="user" for user-confirmed Ticket operations.
Launcher: uv run python -B <PLUGIN_ROOT>/scripts/ticket_engine_user.py <subcommand> <payload_file>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

# Add parent to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_engine_runner import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run("user", prog="ticket_engine_user.py"))
