---
name: implement-issue
description: "Use when the user asks to implement or pick up one agent-ready tracker issue or triaged pull request, including `implement #42` or `work the next ready issue`; verify blockers first. Do not use for plan execution (`execute-plan`), issue slicing (`to-issues`), triage labels or briefs (`triage`), PR review loops, or merge/closeout work."
---

# Implement Issue

Consume one agent-ready tracker issue or triaged pull request end to end: verify it is workable, implement exactly what its contract specifies, prove the acceptance criteria by behavior, and hand the result to the appropriate landing or pull-request lane. This is the execution link between the producers (`to-issues`, `triage`) and the lanes that publish the result.

Before any tracker-dependent read, confirm that the issue tracker and triage label vocabulary are configured. If either is missing, ask the user to run `/setup-matt-pocock-skills` where that user-invoked skill is available; otherwise ask the smallest setup question needed to read the item safely.

## Select One Issue

- Given an issue reference (number, URL, or path), fetch its full body and comments from the tracker.
- Given "the next ready issue": list the issues carrying the agent-ready triage role, exclude any whose blockers are not all closed, and pick the oldest unblocked one — naming the pick and the candidates skipped. If two candidates are equally eligible and materially different, ask rather than guess.
- Never take a ready-for-human issue: its role says the work needs a human. Say so and stop.
- One issue per invocation. The next issue is a fresh invocation in a fresh context — slices are sized for exactly that. Do not chain into a second issue because the first went quickly.
- Before starting work on an issue, inspect local branches and commits whose names or messages carry its identifier. If any exist, report that evidence and ask whether to resume the existing branch or start fresh; never re-implement silently.

## Verify It Is Workable

- Every blocker must be closed before work starts — native issue dependencies where the tracker has them, `Blocked by` text otherwise. An agent-ready label with open blockers is a contradiction: report it and stop, do not start.
- The issue body is the contract: its scope section bounds the work, and the acceptance criteria are the definition of done. Read all comments — later comments amend the body. Read the agent brief when triage attached one.
- If the issue under-specifies the work — a decision the body does not make, context no exploration recovers — stop and route back: report what is missing and suggest the needs-info role (`triage` owns label moves). Do not invent the missing scope.

## Implement

- Work on a working branch per repo convention; never start on a protected branch without explicit consent.
- Scope strictly to the issue. Work it reveals but does not contain — a neighboring bug, a refactor itch, a missing test elsewhere — is surfaced for the tracker (`triage`), never absorbed silently.
- Where the behavior is specifiable up front, build test-first — `/tdd` or `$tdd` where available.
- Record deviations from the issue body as you make them; they belong in the completion report and the issue thread, not only in the diff.

## Pull Request Mode

When the reference resolves to a pull request — a PR URL, or a bare number that the tracker configuration resolves to a PR — the agent brief and the PR's current diff are the contract, and the task is to finish what remains in that diff rather than start the feature again. Check out the PR head onto a local branch with `gh pr checkout <number>` on GitHub or the configured tracker's equivalent, then commit on top of the contributor's commits without rewriting them. If the head is in a fork that does not permit maintainer edits, stop and report that constraint. The same blocker, scope, and per-criterion proof rules apply. Hand off to the PR's ask-gated publish flow — `gh-pr-review-loop` where available — and push nothing from this skill.

## Prove And Hand Off

- Walk the acceptance criteria one by one: each gets fresh behavioral evidence (the command run and its output) or an honest `not verified` with the reason. A passing suite alone does not satisfy a criterion the suite does not exercise.
- Report: issue reference, branch, per-criterion evidence, deviations, and surfaced out-of-scope items.
- Landing is the next lane, not this one: route to the repo's closeout, merge, or PR lanes where available; otherwise report the proof boundary and stop before landing.
- Tracker mutations are approval-gated: propose the closing or status comment with the evidence summary, and post or close only on the user's approval. Never close or modify the parent issue.
