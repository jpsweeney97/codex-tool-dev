# Relay

Carry work between a session here and a session elsewhere by hand, without losing anything on the trip. Three skills covering one job. The human is the transport, and each skill owns a different destination:

- `courier` — the far side cannot read this disk: compose a self-contained paste packet (objective, context capsule, the artifact verbatim, a response contract), then adjudicate the reply against local evidence before composing the next leg.
- `relay-by-reference` — the far side shares this filesystem: stage each leg of a multi-leg exchange as a sha-stamped packet file under `~/scratch-workspace/relay/<run-slug>/`, so only a one-line pointer travels and the body never enters a chat.
- `stage-prompt` — the work leaves and does not come back: write a dated, self-contained commission prompt into `~/prompts`, commit it there, and push fast-forward to that repository's private remote.

The boundaries are cut on observables: who carries the payload (`courier` versus an automated driver such as `synapsis`, where available), whether the far side can read this disk (`courier` versus `relay-by-reference`), and whether a reply comes back (`courier` versus `stage-prompt`). Same-repo resume context belongs to the `handoff` plugin, not to this one.

## Installation

The canonical source lives at `~/.agents/plugins/relay/` and is listed in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the installed copy after source edits):

```bash
codex plugin add relay@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a symlink in `~/.claude/skills/` managed by `~/.agents/scripts/claude-skills-sync.sh`. On Claude the skills are namespaced (`/relay:courier`, `/relay:relay-by-reference`, `/relay:stage-prompt`); on Codex the bare `$courier`, `$relay-by-reference`, and `$stage-prompt` tokens keep working.

## Storage

Each skill writes outside the working repository, and only where its own contract says:

| Skill | Writes |
| --- | --- |
| `courier` | Nothing on disk; the packet is chat text the user copies. |
| `relay-by-reference` | `~/scratch-workspace/relay/<run-slug>/NN-<role>-<stage>.md`, append-only, disposable on the user's word. |
| `stage-prompt` | `~/prompts/YYYY-MM-DD-<target>-<purpose>-prompt.md`, committed and pushed in that repository; consumed prompts move to `~/prompts/archive/` on the user's word. |

No skill ships scripts, hooks, or runtime helpers. Nothing moves between sessions on its own: every leg is attended and carried by the user.
