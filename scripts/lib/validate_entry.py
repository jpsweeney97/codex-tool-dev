from __future__ import annotations

import argparse
from pathlib import Path

from scripts.lib.mdlint import lint_agents, lint_skills
from scripts.lib.tomlcheck import lint_automation_templates


def validate(kind: str, name: str | None, repo_root: Path) -> list[str]:
    failures: list[str] = []
    if kind == "all":
        failures.extend(lint_skills(repo_root / ".codex" / "skills"))
        failures.extend(lint_agents(repo_root / ".codex" / "agents"))
        failures.extend(
            lint_automation_templates(
                repo_root / ".codex" / "automations" / "templates",
            )
        )
        return failures

    if kind == "skill":
        if name is None:
            raise ValueError(f"validate failed: missing skill name. Got: {name!r}")
        failures.extend(lint_skills(repo_root / ".codex" / "skills", only_name=name))
        return failures

    if kind == "agent":
        if name is None:
            raise ValueError(f"validate failed: missing agent name. Got: {name!r}")
        failures.extend(lint_agents(repo_root / ".codex" / "agents", only_name=name))
        return failures

    if kind == "automation":
        if name is None:
            raise ValueError(f"validate failed: missing automation name. Got: {name!r}")
        failures.extend(
            lint_automation_templates(
                repo_root / ".codex" / "automations" / "templates", only_name=name
            )
        )
        return failures

    raise ValueError(f"validate failed: unknown kind. Got: {kind!r}")


def parse_validate_args(argv: list[str]) -> tuple[str, str | None]:
    parser = argparse.ArgumentParser(prog="validate")
    sub = parser.add_subparsers(dest="kind")

    sub.add_parser("all", help="Validate all artifacts (default).")

    parser_skill = sub.add_parser("skill", help="Validate a single skill.")
    parser_skill.add_argument("name")

    parser_agent = sub.add_parser("agent", help="Validate a single agent.")
    parser_agent.add_argument("name")

    parser_automation = sub.add_parser("automation", help="Validate a single automation template.")
    parser_automation.add_argument("name")

    args = parser.parse_args(argv)
    kind = args.kind or "all"
    name = getattr(args, "name", None)
    return kind, name
