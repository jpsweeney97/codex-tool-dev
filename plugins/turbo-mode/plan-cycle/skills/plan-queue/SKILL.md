---
name: plan-queue
description: "Use when the user asks for a plan queue — the N highest-leverage pieces of work in a repo, written as executor-ready `PLAN-N-slug.md` files at the repo root — or drives an existing queue (`execute plan #N`, `next plan`). Owns the leverage sweep, the ranking, the filename-tracked queue, and the authorized burn-down that ends in a local fast-forward merge. Do not use for one plan from an already-settled design (`implementation-planning`), a single plan document outside a queue (`execute-plan`), tracker issue slicing (`to-issues`), or a debt-audit artifact (`tech-debt-scan`)."
---

# Plan Queue

A recurring loop, promoted from a mega-prompt retyped verbatim: sweep a repo for the work with the most leverage, write the top few as plans a weaker model could execute without asking a question, then burn the queue down one authorized plan at a time.

Invocation: `/plan-queue` or `$plan-queue`, though in practice a queue is driven in plain language — "plan queue", "the five highest-leverage things here", "execute plan #2".

**Queue state lives in filenames.** `PLAN-<rank>-<slug>.md` at the repository root, and nothing else: no queue document, no ledger, no status field. There is no second surface to drift out of sync with the plans, and `ls PLAN-*` is the whole queue.

## Two verbs, one authorization boundary

Generating a queue grants no authority to run any of it, and running one plan does not extend to the next. That boundary is most of the skill: the sweep is cheap and reversible, while the burn writes code and lands it on a branch the user has to live with.

## Generate

Trigger: a request for a queue, for a ranking of what to do next in this repo, or the classic long form.

1. Sweep for real, and degrade openly: open issues and TODOs, `.agents/handoffs/` and `THROUGHLINE.md`, git history and recent pull requests, and the code itself. Name any source that is absent rather than quietly working without it — a repo with no tracker gets a thinner sweep, not a failed one.
2. Surface more candidates than survive. Rank by leverage — impact per unit of effort given where this repo actually stands — and give each keeper a rationale citing what the sweep found. A leverage claim with no evidence behind it is a guess wearing a rank.
3. Keep the top N: default 5, or the number the user named.
4. Write each keeper as `PLAN-<rank>-<slug>.md` at the repository root, to `implementation-planning` standards — the goal, exact paths, ordered steps, the edge cases exploration turned up that a weaker model would miss, and acceptance criteria the user can verify. The executor has no repo context and no way to ask a question, so no placeholders and no cross-references to sibling plans.
5. Close with the ranking, each rationale, and which plan to run first.

Queue plans sit at the root because they are transient — visible, obviously temporary, trashed at queue end. A plan meant to outlive its queue belongs in `docs/plans/` under `implementation-planning` instead.

A branch-protection guard may refuse a write at the repository root while a protected branch is checked out: the queue is untracked scaffolding, but the guard only sees a write. Say so and hand the choice back — cut a working branch to hold the queue, or ask the user to run `update-config` to allowlist `PLAN-*.md` where that Claude Code built-in is available. When it is unavailable, hand the allowlist edit to the user. Never relocate the queue to slip past it; the filenames at the root *are* the queue.

If `PLAN-*` files already exist when a new queue is generated, ask whether the new queue replaces the old one, and `trash` the stale files before writing on a yes. Never leave two queues interleaved: the ranks collide and `#2` stops meaning anything.

## Burn

Trigger: `execute plan #N`, `next plan`, `start the top-ranked plan` — the user's own instruction, in this turn. That instruction authorizes the whole motion through the local landing and nothing past it. Never burn from a subagent, hook, or scheduled run, and never from an inference that the queue "should" continue.

1. Resolve `#N` by filename, and read the plan in full before drafting anything — acceptance criteria and any literal guard commands first.
2. Cut a working branch whose name carries the plan's rank and slug within the repo's own convention — a guard that enforces one will reject a bare slug. Execute under `execute-plan`'s contract: its review gates, its status protocol, its stop conditions. That skill owns the execution, and if it stops, its finding is the answer.
3. Verify at the plan's own stated gate and read the output. A plan that turns out wrong mid-burn goes back to the user — no silent redesign, no widening the plan to match what the code turned out to be.
4. Where `merge-branch` is available, land locally under its contract: fast-forward into the verified base branch, source branch retained. If it is unavailable, report the verified branch and stop before landing.
5. **Nothing is published here.** No push, no pull request, no release, no mirror sync. Publishing is `land`'s, on the user's word.
6. Report, then hold.

Hold means hold: after a plan lands, the report ends the turn and the next plan waits for the user to name it.

Resuming an interrupted burn: the plan in flight is the one whose rank and slug the branch name carries; re-derive it from that branch and git state rather than from the transcript, then hand back to `execute-plan`, which owns re-verifying the last task's actual state before anything re-runs. `Next plan` means the lowest-ranked plan whose rank-and-slug branch is absent or is not yet an ancestor of the verified base branch.

## Queue end

When the last plan lands, offer the closeout and execute it only on approval: `trash` the `PLAN-*` files (never `rm`), route branch pruning to `git-hygiene` where available, and save a handoff through `handoff:save-handoff` where available. If a companion is unavailable, report the unperformed cleanup or handoff and stop.

Do not offer it while any plan is still open, and never report it in a burn packet as something already done.

## Output

Generate:

```markdown
Queue: N plans at <repo root>
1. PLAN-1-<slug>.md — <what it changes> — <the leverage, and what in the sweep shows it>
...
Start with: #1. Say `execute plan #1`.
```

Burn:

```markdown
#N landed: <what changed, one clause>
Verified: <the plan's gate, and what it printed>
Merged: <branch → base, fast-forward>
Published: none — publishing is `land`'s
Next: #N+1 (<slug>) — say the word | queue empty — closeout offered
```
