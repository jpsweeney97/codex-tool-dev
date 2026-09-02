# Plan Cycle

Turn a settled spec into published issues, executor-ready plans, and executed work. Nine skills covering one arc, from settled intent to implemented code that is ready for the landing lane:

- `to-prd` — synthesize the current conversation and repo context into a PRD and, on approval, publish it to the project issue tracker under the `needs-triage` role.
- `to-issues` — slice an existing plan, spec, PRD, or approved design into independently grabbable tracer-bullet issues and, on approval, publish them in dependency order with native parent and blocked-by links.
- `acceptance-map` — turn a settled PRD, plan, issue, design, or review finding into a durable Markdown map of observable acceptance checks, each with a source basis, before implementation starts.
- `implementation-planning` — write a dated implementation plan an executor with no codebase context could follow exactly, then run a reference-class completeness pass over it.
- `execute-plan` — work an existing plan document task by task, inline or through per-task subagents with spec-compliance review before quality review.
- `implement-issue` — consume one agent-ready tracker issue per invocation: verify its blockers are closed, implement exactly its scope, prove each acceptance criterion by behavior, and hand off to the landing lane.
- `triage` — move issues, and inbound external PRs where the repo treats them as requests, through the triage role state machine: labels, comments, agent briefs, ready-for-human work, and wontfix handling.
- `plan-queue` — sweep a repo for its highest-leverage work, write the keepers as `PLAN-<rank>-<slug>.md` at the repo root, and burn the queue down one authorized plan at a time, each ending in a local fast-forward merge.
- `spec-drift-reconcile` — when intent changed mid-arc, surface each stale artifact with two-sided evidence and blast radius, record the human's direction decision, then drive the fix through the owning skills.

The forward chain is `to-prd` → `acceptance-map` → `implementation-planning` → `to-issues` → `execute-plan` or `implement-issue`; each member routes to its neighbors by name and stops at the boundary. `triage` and `implement-issue` are the tracker side of the same arc. `plan-queue` is the repo-sweep variant that needs no tracker. `spec-drift-reconcile` is the reconciliation path the forward-only chain otherwise lacks.

Shared conventions: every tracker mutation waits for the user's approval; no skill starts work on a protected branch without explicit consent; and landing is not this plugin's job. Closeout, merge, push, and pull requests belong to the `git-cycle` plugin where available. The one local landing here is `plan-queue`'s fast-forward merge of a plan the user told it to execute in the current turn.

## Installation

The canonical source lives at `~/.agents/plugins/plan-cycle/` and is listed in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the installed copy after source edits):

```bash
codex plugin add plan-cycle@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a symlink in `~/.claude/skills/` managed by `~/.agents/scripts/claude-skills-sync.sh`. On Claude the skills are namespaced (`/plan-cycle:to-prd`, `/plan-cycle:triage`, and so on); on Codex the bare `$to-prd`, `$triage`, and sibling tokens keep working.

## Tracker Setup

The tracker skills (`to-prd`, `to-issues`, `triage`, `implement-issue`) expect the project's issue tracker and its triage-label vocabulary to be configured. Where `setup-matt-pocock-skills` is available it provides both; otherwise each skill asks the smallest setup question it needs before mutating anything.

## Storage

Each skill writes only where its own contract says:

| Skill | Writes |
| --- | --- |
| `to-prd` | One PRD issue in the configured tracker, on approval. Nothing on disk. |
| `to-issues` | Implementation issues in the tracker with labels and native links, on approval. Never closes or edits the parent. Nothing on disk. |
| `acceptance-map` | `<source-stem>.acceptance-map.md` beside the source, or the repo's acceptance-doc convention; committed locally by default; a link added to a local Markdown source. |
| `implementation-planning` | `docs/plans/YYYY-MM-DD-<topic>.md` unless the repo names another location; committed only per repo convention or user request. |
| `execute-plan` | Code changes and per-task commits on a working branch. No merge, push, or PR. |
| `implement-issue` | Code changes and commits on a working branch; a proposed closing or status comment posted only on approval. Never closes the parent. |
| `triage` | Tracker labels, comments, created issues, and closures, on approval; `.out-of-scope/*.md` records for rejected requests. Never deletes. |
| `plan-queue` | `PLAN-<rank>-<slug>.md` at the repo root; on an authorized `execute plan #N`, code on a branch and a local fast-forward merge; the plan files are trashed at queue end on approval. |
| `spec-drift-reconcile` | Its own direction decision record; every artifact fix is dispatched to that artifact's owning skill after the record exists. |

`triage` ships two companion references, `AGENT-BRIEF.md` and `OUT-OF-SCOPE.md`, and `acceptance-map` ships `agents/openai.yaml`. No skill ships scripts, hooks, or runtime helpers, and nothing runs unattended.
