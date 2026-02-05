# Session Summary (2026-02-05)

This document records the work completed to scaffold `codex-tool-dev` and establish a robust foundation for Codex skill development.

## Outcomes

- Created a new repo `codex-tool-dev` with Codex-specific structure and documentation.
- Implemented deterministic validation and promotion scripts targeting `/Users/jp/.codex` (overrideable via `CODEX_HOME` for safe testing).
- Added a reusable skill template, basic scenario testing, strengthened linting, and documented the skill development workflow.
- Verified the new repo contains no Claude-specific language via repository-wide scans.

## Repositories and production target

- Repo path: `/Users/jp/Projects/active/codex-tool-dev`
- Production install target (default): `/Users/jp/.codex`
- Safe testing target: set `CODEX_HOME=/tmp/<dir>` when running promotion.

## Commits created

### `7921197` — Initial scaffold

Added the initial repo scaffold, including:

- Core docs:
  - `docs/frameworks/*`
  - `docs/references/writing-principles.md`
- Codex artifact scaffolding:
  - `.codex/rules/*`
  - `.codex/skills/example-skill/SKILL.md`
  - `.codex/agents/example-agent.md`
  - `.codex/automations/templates/example-automation.toml.tmpl`
- Scripts:
  - `scripts/validate` (static validation)
  - `scripts/promote` (promotion into `/Users/jp/.codex`)
  - `scripts/lib/*` helpers (manifest, fs backup, linters, TOML checks)
- Tests:
  - `tests/scenarios/*` (example scenario fixtures)

Promotion was smoke-tested by promoting into a temporary home:

- `CODEX_HOME=/tmp/codex-home-test uv run scripts/promote ...`

### `27496ae` — Strengthen skill development foundation

Added the “robust foundation” for skill development:

- Skill authoring template:
  - `.codex/skills/_template/SKILL.md`
  - `.codex/skills/_template/README.md`
- Skill workflow documentation:
  - `docs/references/skill-workflow.md`
- Scenario testing harness:
  - `scripts/test` (runner)
  - `scripts/lib/scenario_runner.py` (engine)
- Validation improvements:
  - `.codex/rules/skills.md` updated with recommended workflow
  - `scripts/lib/mdlint.py` skips underscore dirs like `_template`
  - `scripts/lib/mdlint.py` adds a minimal “destructive markers require explicit approval language” rule
- README updated to include scenario tests:
  - `README.md`

Quality checks run after these changes:

- `uv run scripts/validate all`
- `uv run scripts/test --kind all`
- `ruff check .`

## How to use what was built

### Validate artifacts

```bash
uv run scripts/validate all
uv run scripts/validate skill <skill-name>
uv run scripts/validate agent <agent-name>
uv run scripts/validate automation <template-name>
```

### Run scenario tests

```bash
uv run scripts/test --kind all
```

### Promote into production target

```bash
uv run scripts/promote skill <skill-name>
```

Safe promotion into a temp home:

```bash
CODEX_HOME=/tmp/codex-home-test uv run scripts/promote skill <skill-name>
```

## Guardrails added this session

- Repository-wide scan to avoid Claude-specific language in `codex-tool-dev` returned no matches.
- Promotion writes backups (`.bak-<timestamp>`) and records installs in an install manifest under the target CODEX_HOME.
- Linters enforce required sections for skills/agents and required keys for automation templates.

