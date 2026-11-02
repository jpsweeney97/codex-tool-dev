# Test Cycle

From failing behavior to trusted green. Six skills covering one chain, with tests as the proof instrument in every member:

- `diagnose` — find the cause of a problem that is unclear, intermittent, hard to reproduce, resistant to a fix, or spread across components; stops at cause-known.
- `tdd` — build a feature or lock a fix through test-driven development: red, green, refactor, in tracer-bullet slices.
- `bug-epidemiology` — at the moment a cause is confirmed, hunt the defect's twins: reduce it to a structural signature, probe at escalating abstraction, render a confirmed/cleared table; past three trivial twins the sweep goes to `migration-campaign` or `triage`.
- `keep-green` — a change you just made broke lint or tests: bounded fix attempts, same-failure and oscillation detection, escalation of cause-unknown failures; stops at green.
- `characterization-tests` — working code has no tests and a refactor is about to touch it: pin what the code does now, bugs flagged, then prove the net by making a deliberate mutation fail it.
- `test-trust-audit` — before leaning on a green suite for a refactor, upgrade, or release: sweep for skipped growth, assertion-free and tautological tests, mocks asserting mocks, rubber-stamped snapshots; read-only findings, no score.

The boundaries are cut on what is known: an unclear cause is `diagnose`, a known cause locked in test-first is `tdd`, a confirmed cause's population is `bug-epidemiology`, a known-good change that broke the build is `keep-green`. Before a change to untested code, `characterization-tests` builds the net and `test-trust-audit` says whether an existing net can be trusted. None of the six commits, merges, or decides that work is done; that belongs to the `git-cycle` plugin.

## Installation

The canonical source lives at `~/.agents/plugins/test-cycle/` and is listed in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the installed copy after source edits):

```bash
codex plugin add test-cycle@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a symlink in `~/.claude/skills/` managed by `~/.agents/scripts/claude-skills-sync.sh`. On Claude the skills are namespaced (`/test-cycle:diagnose`, `/test-cycle:tdd`, `/test-cycle:bug-epidemiology`, `/test-cycle:keep-green`, `/test-cycle:characterization-tests`, `/test-cycle:test-trust-audit`); on Codex the bare `$diagnose`, `$tdd`, `$bug-epidemiology`, `$keep-green`, `$characterization-tests`, and `$test-trust-audit` tokens are expected to keep working, on the precedent of the earlier plugins.

## Writes

Every write is an ordinary edit in the working repository, under the skill's own contract:

| Skill | Writes |
| --- | --- |
| `diagnose` | Probe code and instrumentation while the cause is unknown; the fix itself is handed to `tdd`. |
| `tdd` | Tests and the code that makes them pass. |
| `bug-epidemiology` | Inline fixes for up to three trivial twins; beyond that it stops and routes. |
| `keep-green` | Fix edits until lint and tests pass; no commit. |
| `characterization-tests` | Characterization test files and the deliberate mutation used to prove them, reverted. |
| `test-trust-audit` | Nothing; read-only findings with citations. |

## Companions

`tdd` ships five reference documents read on demand: `tests.md`, `mocking.md`, `refactoring.md`, `interface-design.md`, `deep-modules.md`. `diagnose` ships `references/hands-on-probes.md` and `scripts/hitl-loop.template.sh`, a human-in-the-loop probe loop template. Every skill ships `agents/openai.yaml` for Codex. No hooks are registered and nothing runs unattended.

## Provenance

Packaged on 2026-11-02 from six established standalone skills, per `docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo. No skill body changed in the move.
