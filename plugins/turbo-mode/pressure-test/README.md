# Pressure Test

Challenge a settled position before committing to it. Five skills covering one job, and none of them renders a verdict:

- `grill-me` — interrogate a plan, design, strategy, or decision one question at a time, exploring the codebase instead of asking when the code can answer, until the plan feels solid or further questions stop changing it.
- `assumption-check` — enumerate what must be true for the plan to work, rank each assumption by how much rides on it and how uncertain it is, and attach the cheapest confirm-or-kill probe to each, as a durable register.
- `premortem` — imagine the plan has already failed and write the accidental causes in the past tense, each with a pre-mitigation and a dated tripwire.
- `red-team` — model the motivated adversary from the defender's chair: named adversaries and goals, attack paths from entry through steps to payoff, ranked by ease times payoff, with raise-cost mitigations.
- `steelman` — build the strongest one-sided case for a position, usually the one the user is about to dismiss, with its assumptions made visible and an honest surviving-counter close.

The boundaries are cut on the kind of challenge: a dialogue is `grill-me`, a register of what must be true is `assumption-check`, accidental failure is `premortem`, intentional attack is `red-team`, and advocacy for one side is `steelman`. Forming or choosing the position belongs to the `decide` plugin; a verdict on readiness or soundness belongs to `scrutinize` in `review-family`; grilling a plan against a project's own domain language and ADRs is the standalone `grill-with-docs`; and challenging the agent's own claim under the user's pushback is the standalone `hold-or-fold`.

## Installation

The canonical source lives at `~/.agents/plugins/pressure-test/` and is listed in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the installed copy after source edits):

```bash
codex plugin add pressure-test@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a symlink in `~/.claude/skills/` managed by `~/.agents/scripts/claude-skills-sync.sh`. On Claude the skills are namespaced (`/pressure-test:grill-me`, `/pressure-test:assumption-check`, `/pressure-test:premortem`, `/pressure-test:red-team`, `/pressure-test:steelman`); on Codex the bare `$grill-me`, `$assumption-check`, `$premortem`, `$red-team`, and `$steelman` tokens are expected to keep working, on the precedent of the earlier plugins.

## Writes

| Skill | Writes |
| --- | --- |
| `grill-me` | Nothing; the interrogation is chat. |
| `assumption-check` | The assumption register, as a durable artifact where the user asks for it. |
| `premortem` | Nothing by default; the failure field and tripwires are chat unless the user asks for a file. |
| `red-team` | Nothing; advisory, nothing published. |
| `steelman` | Nothing; the brief is chat. |

## Companions

Every skill ships `agents/openai.yaml` for Codex and nothing else. No hooks are registered and nothing runs unattended.

## Provenance

Packaged on 2026-11-02 from five established standalone skills, per `docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo. No skill body changed in the move. All five have claude.ai exports under `exports/` in the source repo, repointed to the plugin paths in the same landing.
