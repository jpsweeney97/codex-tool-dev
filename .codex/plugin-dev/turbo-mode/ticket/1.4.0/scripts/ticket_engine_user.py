#!/usr/bin/env python3
"""User entrypoint for the ticket engine.

Hardcodes request_origin="user". Called by ticket-ops skill.
Usage: python3 ticket_engine_user.py <subcommand> <payload_file>
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_engine_runner import run

if __name__ == "__main__":
    raise SystemExit(run("user", prog="ticket_engine_user.py"))
