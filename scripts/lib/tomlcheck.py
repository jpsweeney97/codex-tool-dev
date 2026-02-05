from __future__ import annotations

from pathlib import Path

from tomlkit import parse

_REQUIRED_KEYS = {"name", "status", "rrule", "cwds", "prompt"}


def lint_automation_templates(templates_dir: Path, only_name: str | None = None) -> list[str]:
    failures: list[str] = []
    if not templates_dir.exists():
        return [
            "lint_automation_templates failed: missing templates dir. "
            f"Got: {str(templates_dir)!r}"
        ]

    for tmpl in templates_dir.glob("*.toml.tmpl"):
        stem_no_toml = tmpl.stem.replace(".toml", "")
        if only_name is not None and stem_no_toml != only_name and tmpl.stem != only_name:
            # Depending on naming, `.stem` may be "foo.toml" (because of .tmpl).
            # We accept both "foo" and "foo.toml" matches.
            continue
        raw = tmpl.read_text(encoding="utf-8")
        try:
            doc = parse(raw)
        except Exception as e:  # noqa: BLE001
            failures.append(f"automation lint failed: invalid TOML. Got: {str(tmpl)!r} ({e})")
            continue

        missing = sorted(_REQUIRED_KEYS - set(doc.keys()))
        if missing:
            failures.append(
                f"automation lint failed: missing keys {missing!r}. Got: {str(tmpl)!r}"
            )

        prompt = doc.get("prompt")
        if isinstance(prompt, str) and "FREQ=" in prompt:
            failures.append(
                f"automation lint failed: prompt contains RRULE-like schedule. Got: {str(tmpl)!r}"
            )

    return failures
