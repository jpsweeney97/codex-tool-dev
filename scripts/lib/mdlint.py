from __future__ import annotations

from pathlib import Path


_SKILL_REQUIRED_HEADINGS = [
    "# ",
    "## Trigger / when to use",
    "## Inputs",
    "## Outputs",
    "## Procedure",
    "## Verification",
    "## Failure modes",
    "## Examples",
]


_AGENT_REQUIRED_HEADINGS = [
    "# ",
    "## Scope",
    "## Non-goals",
    "## Tool usage rules",
    "## Output format",
    "## Escalation and approval rules",
]


def lint_skills(skills_dir: Path, only_name: str | None = None) -> list[str]:
    failures: list[str] = []
    if not skills_dir.exists():
        return [f"lint_skills failed: missing skills dir. Got: {str(skills_dir)!r}"]

    for skill in skills_dir.iterdir():
        if only_name is not None and skill.name != only_name:
            continue
        if not skill.is_dir():
            continue
        skill_md = skill / "SKILL.md"
        if not skill_md.exists():
            failures.append(f"skill lint failed: missing SKILL.md. Got: {str(skill_md)!r}")
            continue
        text = skill_md.read_text(encoding="utf-8")
        for heading in _SKILL_REQUIRED_HEADINGS:
            if heading not in text:
                failures.append(
                    f"skill lint failed: missing required heading {heading!r}. Got: {str(skill_md)!r}"
                )
    return failures


def lint_agents(agents_dir: Path, only_name: str | None = None) -> list[str]:
    failures: list[str] = []
    if not agents_dir.exists():
        return [f"lint_agents failed: missing agents dir. Got: {str(agents_dir)!r}"]

    for agent_md in agents_dir.glob("*.md"):
        if only_name is not None and agent_md.stem != only_name:
            continue
        text = agent_md.read_text(encoding="utf-8")
        for heading in _AGENT_REQUIRED_HEADINGS:
            if heading not in text:
                failures.append(
                    f"agent lint failed: missing required heading {heading!r}. Got: {str(agent_md)!r}"
                )
    return failures

