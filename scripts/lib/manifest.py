from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tomlkit import document, dumps, parse


@dataclass
class InstallManifest:
    path: Path
    doc: object

    @classmethod
    def load_or_create(cls, path: Path) -> "InstallManifest":
        if path.exists():
            return cls(path=path, doc=parse(path.read_text(encoding="utf-8")))
        d = document()
        d["generated_at"] = datetime.now(timezone.utc).isoformat()
        d["items"] = {}
        return cls(path=path, doc=d)

    def record(self, key: str, value: dict[str, object]) -> None:
        items = self.doc["items"]
        value = dict(value)
        value["updated_at"] = datetime.now(timezone.utc).isoformat()
        items[key] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dumps(self.doc), encoding="utf-8")

