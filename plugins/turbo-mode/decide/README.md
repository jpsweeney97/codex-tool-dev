# Decide

Shape a want, widen the field, develop the options, choose honestly, and record the decision when it deserves a record. Eight skills covering one arc, from a still-muddy want to a defensible choice or an approved design, with optional capture of the decision made:

- `outcome-shaping` — help the user build a want they can stand behind through an interview-style shaping conversation: type why they cannot say it yet, keep their words in an evolving read, price at least one trade, and treat a dissolved want as a success.
- `ideate` — widen a clear-enough prompt into a deliberately un-ranked field of genuinely different options, de-clustered on mechanism, and stop before any ranking.
- `option-shaping` — develop a fixed field of sketch-level options to comparable resolution, question by question across every option, without ranking or choosing.
- `making-recommendations` — choose among serious, comparable options like an honest advisor: register the leans, filter on hard constraints, check dominance, compare genuine trades in words, pose the priced values question when the ranking turns on it, and give the runner-up its strongest case.
- `design-exploration` — turn a clear-enough outcome into compared approaches and an approved design before any implementation lane takes over.
- `deliberate` — run Generate, Prune, Shape, Recommend, and Contest on one decision without stopping to ask, each stage a fresh agent that reads the sibling skill it runs, and return the recommendation, a ledger of every cut with its revival condition, and a check of the cuts against the recommendation.
- `scope-cut` — partition an already-shaped scope into keep, defer, and cut under a binding constraint, keeping the slice coherent and preserving every removed item with a re-entry condition.
- `decision-record` — capture an already-made decision from any source (a live conversation, a transcript, a PR thread) as a numbered ADR in `docs/adr/`, and on a reversal set the superseded record's status to point at its replacement so the two never silently disagree.

The forward chain is `outcome-shaping` → `ideate` → `option-shaping` → `making-recommendations`; `design-exploration` takes a clear-enough outcome to an approved design and hands to the planning lane; `scope-cut` cuts a shaped scope when a constraint forces it smaller. Each member routes to its neighbors by name and stops at its boundary. `deliberate` runs the same chain autonomously, dispatching `ideate`, `option-shaping`, and `making-recommendations` from this plugin as fresh-agent stages, with its own Prune stage between the first two and its own Contest stage after the last. `decision-record` is optional capture after a decision is made, not a required end of the arc: many decisions should not become ADRs, and the skill right-sizes rather than requiring one.

Shared conventions: every skill is chat-first and read-only toward user-visible state by default; none implements, pushes, or publishes; `decision-record` is the one skill that writes and commits by contract, an ADR under `docs/adr/` with a local `docs(adr): ...` commit and never a push; and handoffs between lanes are named and asked, never silent. `deliberate` never fires from a cron job, hook, scheduled task, or another skill; a plain request for a whole deliberation can reach it, and it shows its setup before the first stage so the user can correct it.

## Installation

The canonical source lives at `~/.agents/plugins/decide/` and is listed in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the installed copy after source edits):

```bash
codex plugin add decide@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a symlink in `~/.claude/skills/` managed by `~/.agents/scripts/claude-skills-sync.sh`. On Claude the skills are namespaced (`/decide:outcome-shaping`, `/decide:making-recommendations`, and so on); on Codex the bare `$outcome-shaping`, `$making-recommendations`, and sibling tokens keep working.

## Storage

Each skill writes only where its own contract says:

| Skill | Writes |
| --- | --- |
| `outcome-shaping` | Nothing by default. Chat-only; a shaping brief (the capsule) only when the user explicitly asks, placed per repo convention and left uncommitted; a ticket or other durable artifact likewise only on an explicit ask. |
| `ideate` | Nothing. The un-ranked field is delivered in the response. |
| `option-shaping` | Nothing. The comparison surface is delivered in the response. |
| `making-recommendations` | Nothing. The close is delivered in the response. |
| `design-exploration` | A design document only when the user asks or approves, placed per repo convention; never committed automatically. |
| `deliberate` | Six Markdown files (`00-setup.md` through `05-contest.md`) in a fresh directory under the runtime's scratch or temp root, left in place so the user can read them and re-run from any stage. Nothing under the working tree. |
| `scope-cut` | Nothing itself. The deferred-not-dropped ledger is routed to `triage` (in the `plan-cycle` plugin where available), one item per finding, where every tracker mutation waits for approval; an inline list is the fallback when no tracker is reachable. |
| `decision-record` | `docs/adr/NNNN-slug.md` at the next number, created lazily; on a supersession, a `Status` line on the older record; on a narrowing that leaves the older record in force, a cross-reference in the new record's prose plus, where the repo's ADR convention carries dated amendment sections, one such section on the older record where that convention places it, its existing text unedited; then a local commit of only those files (`docs(adr): record NNNN <slug>`), skipped on a protected branch or amid unrelated dirty state. Never pushes, opens a PR, or publishes. |

Companions move with their skills: `outcome-shaping` ships `agents/openai.yaml` and `examples/interaction-examples.md`; `option-shaping` ships `agents/openai.yaml`; `making-recommendations` ships `agents/openai.yaml`, `examples/behavior-examples.md`, and `references/high-stakes.md`; `deliberate` ships `agents/openai.yaml` only: its Prune and Contest methods are inline in its `SKILL.md`, and it runs its sibling stages by having each fresh agent read the sibling's `SKILL.md`. The plugin also ships `references/ADR-FORMAT.md`, the ADR format `decision-record` follows; in the source repo `grill-with-docs` and `improve-codebase-architecture` read that same file through a symlink alias at `skills/grill-with-docs/ADR-FORMAT.md`, so a change to it is a release of this plugin. No hooks are registered and nothing runs unattended.

## Re-runs from the 1.x `deliberate`

The 1.x `deliberate` returned a re-run capsule validated by a bundled script. Version 2.0.0 removed the capsule, the validator, and the run-state store, so a 1.x capsule is not accepted. A 2.0 run leaves its stage outputs as readable Markdown files, and a re-run is a request in chat naming the cut to revive, the constraint to change, or the survivor to develop further; the run restarts from the stage that changes. The 1.x bundle is preserved unchanged at `skills-archive/deliberate-v1/` in the source repo.
