# Change Cycle

One code change, from radar to every site. Four skills covering one chain:

- `co-change-radar` — before a non-trivial edit to a tracked file, and again before declaring a multi-file change complete: mine the file's own commit history for habitual co-change partners and force a one-line disposition for every flagged partner the diff does not touch, the docs table, fixture, or parallel enum that grep, imports, and LSP cannot see.
- `contract-change-propagation` — when the edit changes a shared interface (an API, a signature, a schema, a config key, an event payload): classify each delta as breaking, additive, or behavior-preserving, enumerate the consumers, and recommend a versioning, deprecation, and rollout sequence before it lands.
- `migration-campaign` — when one decided mechanical change must be applied uniformly across many sites: partition into shards, pilot the riskiest first, track every site in a durable burndown, and verify each shard before marking it done.

The boundaries are cut on the kind of change: an edit to an existing file is `co-change-radar`, a change to a declared interface is `contract-change-propagation`, and the uniform application of an already-decided change is `migration-campaign`. Deciding what the change should be belongs to the `decide` plugin; slicing a plan into tracker issues belongs to `plan-cycle`; a defect's twins after a confirmed cause belong to `bug-epidemiology` in `test-cycle`, which routes a many-site sweep here.

## Installation

The canonical source lives at `~/.agents/plugins/change-cycle/` and is listed in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the installed copy after source edits):

```bash
codex plugin add change-cycle@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a symlink in `~/.claude/skills/` managed by `~/.agents/scripts/claude-skills-sync.sh`. On Claude the skills are namespaced (`/change-cycle:co-change-radar`, `/change-cycle:contract-change-propagation`, `/change-cycle:migration-campaign`); on Codex the bare `$co-change-radar`, `$contract-change-propagation`, and `$migration-campaign` tokens are expected to keep working, on the precedent of the earlier plugins.

## Writes

| Skill | Writes |
| --- | --- |
| `co-change-radar` | Nothing by itself; it mines `git log` read-only and the dispositions are chat text. The edit it precedes is the user's own. |
| `contract-change-propagation` | Nothing; advisory, the propagation map and rollout sequence are chat text or a document the user asks for. |
| `migration-campaign` | The edits across every site, and the burndown record the skill documents, in the working repository. |

## Companions

Every skill ships `agents/openai.yaml` for Codex and nothing else. No hooks are registered and nothing runs unattended.

## Provenance

Packaged on 2026-11-02 from four established standalone skills, per `docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo. No skill body changed in the move.
