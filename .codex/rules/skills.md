# Rules: Skills

These rules are **blocking**. Read them before creating or editing any file under `.codex/skills/`.

## Required file layout

- Each skill lives in `.codex/skills/<name>/SKILL.md`.
- Skill directory names use `kebab-case`.
- Do not edit `.codex/skills/_template/` directly except to improve the template.

## Required sections (minimum)

`SKILL.md` must include, in this order:

1. **Name**
2. **Trigger / when to use**
3. **Inputs**
4. **Outputs**
5. **Procedure**
6. **Verification**
7. **Failure modes**
8. **Examples**

## Determinism

- Use numbered steps for procedures.
- Include stop conditions (when to ask for clarification).
- Do not rely on implicit state (current directory, tool availability).

## Safety

- No destructive actions without explicit user approval.
- If the skill proposes destructive commands, it must provide a safer alternative and require confirmation.

## Quality bar

- Include at least one happy-path example and one edge-case example.
- Verification must be executable (commands or explicit checks).

## Recommended workflow

1. Copy `.codex/skills/_template/` to `.codex/skills/<new-skill-name>/`
2. Replace placeholders in `SKILL.md`
3. Add a scenario in `tests/scenarios/skills/`
4. Run `uv run scripts/validate skill <new-skill-name>`
