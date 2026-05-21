#!/usr/bin/env python3
"""Private activation-smoke entrypoint for contained Ticket runtime proofing.

This path exists only for runtime-readiness bootstrap flows. It is not a
supported user-facing mutation surface.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_engine_runner import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run("user", prog="ticket_engine_activation_smoke.py"))
