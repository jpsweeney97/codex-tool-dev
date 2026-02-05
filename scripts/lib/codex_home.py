from __future__ import annotations

import os
from pathlib import Path


def codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError(f"codex_home failed: CODEX_HOME must be absolute. Got: {override!r}")
        return path

    # Explicit production target for this repo.
    return Path("/Users/jp/.codex")

