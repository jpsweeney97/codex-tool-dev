#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from turbo_mode_handoff_runtime.list_handoffs import main

if __name__ == "__main__":
    print(main())
    raise SystemExit(0)
