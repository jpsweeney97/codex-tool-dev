# Handoff Format

Handoffs are Markdown notes under:

```text
<project_root>/.codex/handoffs/
```

Filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

## Frontmatter

Recommended frontmatter:

```yaml
---
created_at: "2026-06-09T14:30:00Z"
type: handoff
title: "Skill-only Handoff redesign"
project: codex-tool-dev
branch: main
commit: abc1234
---
```

In practice, `created_at`, `type`, `title`, and `project` should be present. Include `branch` and `commit` when available.

Do not require `session_id`, `resumed_from`, or `files`.

## Body Prompts

Use the sections that make the next session successful:

```markdown
# Handoff: <title>

## Session Context
## Project Arc
## Decisions
## Evidence Checked
## Current State
## Next Action
## Open Questions
## Risks
## References
```

These headings are prompts, not a schema. There is no line-count target, section-count validator, confidence field, evidence-level taxonomy, or required decision template.

## Compact Example

```markdown
---
created_at: "2026-06-09T14:30:00Z"
type: handoff
title: "Skill-only Handoff redesign"
project: codex-tool-dev
branch: feature/handoff-skill-only-redesign
commit: abc1234
---

# Handoff: Skill-only Handoff redesign

## Session Context

The Handoff source bundle was reduced to three skills and one format reference. Runtime helpers, hook metadata, tests, and retired skill entry points were removed from source.

## Project Arc

The broader goal is to keep Handoff plain: Codex writes a useful Markdown note, later reads it as context, checks live reality, and continues.

## Evidence Checked

- `git status --short --branch --untracked-files=all`
- `python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- source inventory check for the approved bundle shape

## Current State

Source verification passed. Installed runtime was not refreshed or proven.

## Next Action

If runtime pickup matters, run a separate explicit plugin refresh and runtime inventory proof.
```

## Resumption Test

Could future Codex continue without wasting time, repeating avoidable exploration, or trusting a stale claim?

## Evidence Boundary

Handoffs are evidence, not truth. A future session should check the live branch, HEAD, worktree, and any important files before acting on a handoff claim.
