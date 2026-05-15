# Repository-local instructions for `/Users/jp/Projects/active/codex-tool-dev`.

These instructions supplement the user-level rules. If there is a conflict, follow
safety rules first, then the explicit user request, then user-level instructions,
then this file.

## Repository Purpose

This repository is the development workspace for Codex plugins, skills, and
supporting tools. Treat it as source-authority for the local Turbo Mode plugin
tree, not as proof that the installed Codex runtime already matches source.

Primary source surfaces:

- `plugins/turbo-mode/handoff/1.6.0/` - Handoff plugin source.
- `plugins/turbo-mode/ticket/1.4.0/` - Ticket plugin source.
- `plugins/turbo-mode/tools/` - migration, refresh, proof, and cache-update
  tooling for Turbo Mode plugin development.
- `.codex/skills/` - repo-local Codex skills used while working in this repo.
- `.agents/plugins/marketplace.json` - local marketplace descriptor for the
  Turbo Mode plugin source tree.
- `docs/superpowers/` and `docs/tickets/` - durable plans, closeouts, PR
  packages, and tracked tickets.

## Development Posture

This is a fast-iteration development repo. Aim for small, reversible,
evidence-backed changes that move the current plugin work forward. The bar is
real correctness for the touched behavior, not broad hardening against every
hypothetical environment.

- Prefer the smallest credible change that solves the current problem and leaves
  clear evidence.
- Scale process to blast radius. Runtime/cache mutation, hook trust, storage
  recovery, and publication evidence need explicit gates; docs wording, narrow
  source fixes, and local helper cleanup should not grow extra ceremony.
- Avoid speculative compatibility layers, generic frameworks, and broad rewrites
  unless live code, tests, or the user's request shows they are needed now.
- When a future concern is real but not required for the current slice, name it
  as follow-up work instead of folding it into the current patch.

## Authority And Evidence

- Read the live file before relying on a plan, handoff, summary, review packet,
  or prior conversation. Many historical docs are intentionally retained and may
  describe an older state.
- Separate proof classes in status reports:
  - `source`: code, docs, tests, and manifests in this checkout.
  - `installed runtime`: what Codex currently exposes through app-server
    surfaces such as `plugin/read`, `plugin/list`, `skills/list`, and
    `hooks/list`.
  - `local cache`: files under `/Users/jp/.codex/plugins/cache/...`.
  - `docs readiness`: plans, closeouts, and tickets that describe intended or
    completed work.
- Do not claim installed/runtime success from source file presence, cache file
  presence, or marketplace JSON alone. Use live runtime inventory when the claim
  is about installed behavior.
- If the user asks for an evaluation, review, or certification, make missing
  evidence explicit instead of treating it as a pass.

## Work Boundaries

- Keep source repair separate from installed-cache mutation. Updating source does
  not imply the installed plugin cache has been refreshed.
- Do not mutate `/Users/jp/.codex/plugins/cache`, `/Users/jp/.agents`, or other
  machine-local runtime state unless the user explicitly asks for an installed
  refresh, runtime proof, or local setup change.
- Do not run guarded refresh, cache refresh, plugin install, or live runtime
  mutation commands as a side effect of ordinary source edits.
- Use `trash <path>` for deletion. Never use `rm` or `rm -rf`.
- Preserve unrelated dirty work. If generated residue blocks verification, report
  it and remove it only when the cleanup is in scope or explicitly approved.
- Treat ignored handoff directories such as `.codex/handoffs/` and
  `docs/handoffs/` as local session history. Do not publish, stage, or delete
  those files unless the user explicitly makes them part of the task.

## Plugin-Specific Rules

### Handoff `1.6.0`

- Source root: `plugins/turbo-mode/handoff/1.6.0/`.
- Public behavior is primarily defined by `README.md`, `skills/*/SKILL.md`,
  `scripts/*.py`, `references/`, and `.codex-plugin/plugin.json`.
- `hooks/hooks.json` is intentionally empty for this release. Do not describe
  Handoff `1.6.0` as shipping plugin-bundled command hooks unless both the
  source manifest and installed runtime prove that changed.
- Handoff storage currently targets project-local `.codex/handoffs/` paths.
  Older `docs/handoffs/` artifacts can still exist as historical or ignored
  local state.
- The checkout has a root-level `scripts/` package. When changing Handoff helper
  imports, include direct-execution or repo-root smoke coverage so
  plugin-local `scripts.*` imports cannot be silently shadowed by the root
  package.

### Ticket `1.4.0`

- Source root: `plugins/turbo-mode/ticket/1.4.0/`.
- Ticket scripts live in `scripts/`; this is not a conventional installed Python
  package layout.
- Canonical plugin script launcher shape is:

  ```bash
  python3 -B <PLUGIN_ROOT>/scripts/<script>.py ...
  ```

- `PLUGIN_ROOT` is the plugin package root. `PROJECT_ROOT` is the active
  workspace root. Ticket files live under `<PROJECT_ROOT>/docs/tickets/`, not
  under the plugin package.
- Ticket mutation flows are trust-aware and confirmation-gated. Do not bypass
  `ticket_workflow.py`, the engine entrypoints, or the guard model just to make
  a mutation easier.
- `hooks/hooks.json` points at the installed cache hook path. Treat that file as
  source metadata; use `hooks/list` when proving live hook registration.

## Skills And Instruction Files

- When editing `SKILL.md`, `agents/*.yaml`, `agents/*.md`, `CLAUDE.md`, or
  instruction-style Markdown, apply the repo-local writing principles from
  `.codex/skills/writing-principles/`.
- Keep skills behavior-focused. Avoid meta commentary about how the skill was
  authored.
- If a skill behavior changes, check whether companion files under `agents/`,
  `references/`, tests, plugin manifests, or README content also need updates.
- For review-oriented skills and review requests, lead with findings, risks,
  regressions, and missing proof. Keep summaries secondary.

## Plans, Tickets, And Handoffs

- Treat `docs/superpowers/plans/` as execution control documents, not loose
  notes. If asked to revise one, make file paths, stop conditions, evidence
  gates, and commit boundaries concrete.
- Treat `docs/tickets/` as tracked project state. Preserve ticket schema and
  audit semantics when editing tickets by hand.
- When a user asks for a plan first, write or revise the plan and wait for an
  implementation cue before changing code.
- When a user invokes saved handoff context, re-check current branch, `HEAD`,
  worktree status, and the live files before trusting the handoff narrative.

## Verification

Choose the smallest verification set that proves the changed surface. Prefer
focused package tests over broad commands that collect unrelated work.

Use bytecode-safe Python test commands for this repo:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest <target> -q
```

Common targets:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket/1.4.0 pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check <changed-python-paths>
git diff --check
```

For refresh or installed-runtime work, add the relevant non-mutating planner or
inventory check before any mutation. Runtime proof should include app-server
inventory such as `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`.

For Handoff import or script-entrypoint changes, add a direct smoke such as:

```bash
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/installed_host_harness.py
```

Adjust the exact selector to the file being changed. If a command creates
`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.venv`, or
`.DS_Store` residue in plugin source paths, clean or report it before claiming a
clean closeout.

## Git And Cleanup

- Before edits, check `git status --short --branch`.
- Before staging or committing, review `git diff --stat` and the relevant diff.
- Use branch names that match the user-level branch policy when creating a
  branch from `main`: `feature/*`, `fix/*`, `hotfix/*`, or `chore/*`.
- Keep commits coherent by surface: docs-only, Handoff source, Ticket source,
  refresh tooling, runtime evidence, and cleanup should not be mixed without a
  reason.
- Do not stage ignored local runtime or handoff artifacts unless the user
  explicitly asks to publish them and the repository policy supports it.

## Communication

- State whether a conclusion is based on live files, tests, runtime inventory,
  or memory/history.
- For bug investigations with multiple plausible causes, use the required
  root-cause checkpoint before a deep dive.
- For code changes, report what changed, why it changed, verification performed,
  and remaining risks.
- If work is blocked by stale runtime state, generated residue, missing
  evidence, or a destructive cleanup decision, name the blocker and the decision
  needed.
