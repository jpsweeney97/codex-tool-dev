from __future__ import annotations

from pathlib import Path

import yaml


def _read_yaml(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"scenario read failed: expected mapping. Got: {str(path)!r}")
    return data


def _normalize_prompt(text: str) -> str:
    return " ".join(text.split())


def _check_contains(text: str, required: list[str]) -> list[str]:
    failures: list[str] = []
    for item in required:
        if item not in text:
            failures.append(f"scenario failed: missing required text {item!r}")
    return failures


def run_scenarios(scenarios_root: Path, kinds: list[str]) -> list[str]:
    failures: list[str] = []
    for kind in kinds:
        kind_dir = scenarios_root / kind
        if not kind_dir.exists():
            continue
        for scenario_file in sorted(kind_dir.glob("*.yaml")):
            data = _read_yaml(scenario_file)
            prompt = data.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                failures.append(
                    f"scenario failed: missing prompt. Got: {str(scenario_file)!r}"
                )
                continue

            expect = data.get("expect")
            if not isinstance(expect, dict):
                failures.append(
                    f"scenario failed: missing expect mapping. Got: {str(scenario_file)!r}"
                )
                continue

            # For v1, scenarios are "static expectations" against the artifact text,
            # not full model execution. This provides fast, deterministic checks.
            if kind == "skills":
                name = data.get("name")
                if not isinstance(name, str) or not name.strip():
                    failures.append(
                        f"scenario failed: missing skill name. Got: {str(scenario_file)!r}"
                    )
                    continue
                skill_md = scenarios_root.parents[1] / ".codex" / "skills" / name / "SKILL.md"
                if not skill_md.exists():
                    failures.append(
                        f"scenario failed: missing skill SKILL.md. Got: {str(skill_md)!r}"
                    )
                    continue
                text = skill_md.read_text(encoding="utf-8")
                must_sections = expect.get("must_include_sections")
                if isinstance(must_sections, list):
                    failures.extend(
                        [
                            f"{scenario_file.name}: {msg}"
                            for msg in _check_contains(text, must_sections)
                        ]
                    )

            if kind == "agents":
                name = data.get("name")
                if not isinstance(name, str) or not name.strip():
                    failures.append(
                        f"scenario failed: missing agent name. Got: {str(scenario_file)!r}"
                    )
                    continue
                agent_md = scenarios_root.parents[1] / ".codex" / "agents" / f"{name}.md"
                if not agent_md.exists():
                    failures.append(
                        f"scenario failed: missing agent file. Got: {str(agent_md)!r}"
                    )
                    continue
                text = agent_md.read_text(encoding="utf-8")
                must = expect.get("must_include")
                if isinstance(must, list):
                    failures.extend(
                        [f"{scenario_file.name}: {msg}" for msg in _check_contains(text, must)]
                    )

            _ = _normalize_prompt(prompt)
    return failures
