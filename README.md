# codex-tool-dev

Monorepo for developing **Codex** extensions: skills, agents, automations, and MCP servers.

## Production target

This repo promotes validated artifacts into:

- `/Users/jp/.codex`

Dev artifacts live in this repo under `.codex/`. Promotion is the only operation that writes into the production target.

## Quickstart

### 1) Install tooling

- Node.js (for `packages/*`)
- Python + `uv` (for `scripts/*`)

### 2) Validate

```bash
./scripts/validate
```

### 2a) Run scenario tests

```bash
./scripts/test --kind all
```

Targeted validation:

```bash
./scripts/validate skill example-skill
./scripts/validate agent example-agent
./scripts/validate automation example-automation
```

### 3) Promote to `/Users/jp/.codex`

```bash
./scripts/promote skill example-skill
./scripts/promote agent example-agent
./scripts/promote automation example-automation
```

## Repo layout

```
.codex/
  skills/        # Skills (SKILL.md required)
  agents/        # Agents/subagents
  automations/   # Automation templates (repo-local)
  rules/         # Blocking rules (read before editing)

packages/
  mcp-servers/   # MCP servers (TypeScript/Node)

scripts/         # validate/promote utilities (Python via uv)
docs/            # frameworks, references, audits, plans
```

## Rules (blocking)

Before creating or editing any extension, read the relevant rule:

- Skills: `.codex/rules/skills.md`
- Agents: `.codex/rules/agents.md`
- Automations: `.codex/rules/automations.md`
- MCP servers: `.codex/rules/mcp-servers.md`

## Safety model

- Promotion validates first and fails fast.
- Promotion writes backups and a local install manifest under `/Users/jp/.codex`.
- No destructive actions without explicit user approval.
