# Ticket Plugin Retirement Design

## Status

Approved for planning on 2026-06-06.

## Purpose

Retire the Ticket plugin and the ticket-backed Handoff workflow from the active
`codex-tool-dev` source tree.

After this retirement, Ticket should no longer be an installable Turbo Mode
plugin, an expected refresh/runtime surface, or the backing store for Handoff
deferred-work flows. Retired Ticket material should be preserved outside the
repo under `/Users/jp/archive/`, not kept in active source paths.

## Outcome

The active repo should stop presenting ticket-backed work tracking as current
behavior.

Remove these active surfaces:

- `plugins/turbo-mode/ticket/`
- `docs/tickets/`
- the `ticket` entry in `.agents/plugins/marketplace.json`
- repo-local refresh skill wording that lists Ticket as part of the expected
  Turbo Mode plugin set
- Handoff `/defer` and `/triage` skills as ticket-backed workflows
- Handoff runtime modules, scripts, tests, and documentation whose only purpose
  is ticket creation, ticket parsing, ticket provenance, or ticket backlog
  triage
- current-facing tests and fixtures that require Ticket to remain installable,
  refreshable, hook-backed, or callable

Keep historical documents as history unless they are current-facing development
instructions. Past specs, plans, closeouts, audits, and PR packages may still
mention Ticket when they are recording what happened at the time. If a
historical document has a current status section that names Ticket as an active
baseline, patch only that status section instead of rewriting the whole
historical artifact.

## Archive

Create a dated archive directory:

```text
/Users/jp/archive/codex-tool-dev-ticket-retired-2026-06-06/
```

The archive should contain:

- the retired `plugins/turbo-mode/ticket/` tree
- the retired `docs/tickets/` tree
- `RETIREMENT.md`

`RETIREMENT.md` should record:

- source repo path
- branch and commit used for the archive
- archive creation date
- source paths archived
- that installed runtime/cache state was not mutated by this source retirement
  unless a separate runtime retirement step says otherwise
- the verification commands run for the source retirement

Writing to `/Users/jp/archive/` is outside the normal repo edit surface and
requires explicit filesystem approval at implementation time.

## Handoff Shape

Handoff remains a session-continuity plugin.

Remove ticket-backed Handoff behavior:

- `/defer`
- `/triage`
- ticket envelope emission
- Ticket sibling-plugin resolution
- ticket parsing/provenance helpers
- docs that describe deferred work as ticket files under `docs/tickets/`

Do not replace Ticket with a new tracking system in this retirement slice.
Handoff may still preserve deferred work as prose inside handoff artifacts when
that already happens naturally during save or summary flows. A new active
tracking workflow would be a separate design.

## Turbo Mode Shape

Turbo Mode source authority should expect the active plugin set to be Handoff
and Review Family only.

Patch current-facing refresh and marketplace surfaces so they do not require,
install, sync, smoke, or certify Ticket. Refresh tooling may keep historical
fixtures that mention Ticket only when the fixture is explicitly testing old
migration behavior and cannot affect current expected plugin inventory.

## Runtime Boundary

This design is source retirement only.

Removing Ticket from this repo and archiving its source does not prove that the
currently installed Codex runtime stopped exposing Ticket. Installed runtime,
personal plugin copies, and local cache state are separate proof classes.

Do not mutate these paths as a side effect of source retirement:

- `/Users/jp/.codex/plugins/cache/`
- `/Users/jp/.codex/plugins/`
- `/Users/jp/.agents/`
- Codex app-server runtime/plugin state

If installed Ticket retirement is desired later, create a separate runtime plan
with live inventory before mutation and live inventory after mutation.

## Verification

The source-retirement implementation should prove:

- `.agents/plugins/marketplace.json` no longer contains `ticket`
- current-facing Turbo Mode refresh docs and tests no longer require Ticket as
  an expected plugin
- Handoff tests pass without `/defer`, `/triage`, or ticket helper modules
- refresh-tool tests that cover current plugin inventory pass with Handoff and
  Review Family only
- `git diff --check` passes
- the archive directory contains the retired source trees and `RETIREMENT.md`

Do not claim installed runtime success from this verification bundle.

## Non-Goals

- no installed runtime/cache mutation
- no personal plugin copy mutation
- no replacement backlog or issue-tracking workflow
- no broad rewrite of historical Ticket plans, specs, closeouts, or audits
- no deletion of unrelated handoff/session history
