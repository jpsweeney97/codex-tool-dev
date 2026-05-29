---
name: turbo-plugin-refresh
description: Use when the user asks to plan, refresh, sync, update, or locally install Turbo Mode plugins from the codex-tool-dev repo into personal Codex plugin directories. Always start with a non-mutating plan and require a second explicit "sync now" instruction before copying plugin source.
---

# Turbo Plugin Refresh

Run the official local-plugin baseline for Turbo Mode plugins. The repo remains
source authority for the expected Turbo Mode plugin set: Handoff, Ticket, and
Review Family. The sync helper copies manifest-backed plugin directories under
`plugins/turbo-mode/` to the user's personal Codex plugin directories.

## Rules

- Use the repo at `/Users/jp/Projects/active/codex-tool-dev`.
- Expect at least these source packages: `handoff`, `ticket`, and
  `review-family`.
- Use npm scripts for the normal workflow.
- Always start with the non-mutating plan workflow.
- Do not run the sync command on the first turn, even if the user says
  "refresh", "update", "install", or "sync".
- Run sync only after a second explicit instruction containing `sync now`.
- If the working tree is dirty, say the sync will copy dirty source, then stop
  and wait for `sync now`.
- Treat marketplace writes as separate setup/configuration work, not normal
  refresh. Do not write `~/.agents/plugins/marketplace.json` unless the user
  explicitly asks for marketplace setup or configuration.
- Treat copying, marketplace availability, installed status, and loaded runtime
  state as separate proof surfaces.
- After a successful sync, run `codex plugin list` before saying what restart
  will accomplish.
- If an expected plugin is listed as `not installed`, say that sync made the
  source available but did not install it. For the default personal marketplace,
  install it with `codex plugin add <plugin>@turbo-mode`, then start a new
  thread or restart Codex so the runtime can load the newly installed plugin.
- Do not describe sync, marketplace metadata, or copied files as runtime proof.

## Plan Workflow

Run both commands with working directory
`/Users/jp/Projects/active/codex-tool-dev`:

```bash
git status --short --branch
npm run turbo:plan-personal-plugins
```

Report:

- current branch and whether the working tree is dirty
- the planned plugin copy operations from the npm output
- whether `handoff`, `ticket`, and `review-family` all appear in the planned
  copy operations
- the intended personal marketplace path and JSON from the npm output
- whether the user must say `sync now` to copy files

If `git status` shows uncommitted changes, state that `sync now` will copy dirty
source. Do not judge the dirty source as wrong unless the changed paths make the
requested workflow impossible.

Stop after reporting the plan.

## Sync Workflow

Use this workflow only when the user gives the second explicit instruction
`sync now`.

Rerun the preflight immediately before syncing:

```bash
git status --short --branch
npm run turbo:plan-personal-plugins
```

If either command fails, stop and report the blocker. If both commands succeed,
run:

```bash
npm run turbo:sync-personal-plugins
```

Report:

- whether the sync command succeeded
- any copied plugin paths shown by the helper
- whether dirty source was copied
- the `codex plugin list` status for `handoff`, `ticket`, and `review-family`
- whether any expected plugin still needs `codex plugin add <plugin>@turbo-mode`
- whether a restart or new thread is needed to load newly installed plugin
  skills and tools

Do not ask for a third confirmation after `sync now` unless the preflight fails,
the repo path is unavailable, the npm scripts are missing, or the user asks for
marketplace setup/configuration.

## Marketplace Setup

If the user asks to write or update `~/.agents/plugins/marketplace.json`, treat
that as a separate setup/configuration action.

First run the plan workflow and show the intended marketplace JSON. Then ask for
explicit confirmation to write the personal marketplace file. Do not combine this
with normal sync unless the user asks for both actions separately.
