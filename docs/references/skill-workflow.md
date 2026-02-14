# Skill Development Workflow

This repo is set up so skills are:

- Authored in-repo under `.codex/`
- Validated deterministically (`scripts/validate`)
- Smoke-tested via scenarios (`scripts/test`)
- Promoted into `/Users/jp/.codex` (`scripts/promote`)

## Create a new skill

1. Choose a `kebab-case` name, e.g. `log-triage`.
2. Copy the template:

   ```bash
   cp -R .codex/skills/_template .codex/skills/log-triage
   ```

3. Edit `.codex/skills/log-triage/SKILL.md`
   - Replace placeholders
   - Keep required headings
   - Add explicit verification and failure modes
4. Add a scenario:
   - `tests/scenarios/skills/log-triage.yaml`
5. Validate and test:

   ```bash
   ./scripts/validate skill log-triage
   ./scripts/test --kind skills
   ```

## Promote (install) a skill

Promote into production target `/Users/jp/.codex`:

```bash
./scripts/promote skill log-triage
```

Safe testing into a temporary home:

```bash
CODEX_HOME=/tmp/codex-home-test ./scripts/promote skill log-triage
```

## Conventions

- Directories under `.codex/skills/` starting with `_` are treated as templates and skipped by linters.
- Skills must include a `Verification` section with executable checks when possible.
