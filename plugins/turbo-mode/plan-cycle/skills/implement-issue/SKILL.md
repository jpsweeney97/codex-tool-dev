---
name: implement-issue
description: "Use when the user asks to implement, work, or pick up a tracker issue — `implement #42`, `work the next ready issue`, an agent-ready issue produced by `to-issues` or a triage agent brief. One issue per invocation, blockers verified first. Do not use for executing a plan document task-by-task (`execute-plan`), slicing a plan into issues (`to-issues`), issue labeling or brief-writing (`triage`), PR review loops, or merge/closeout lifecycle."
---

# Implement Issue

Consume one agent-ready tracker issue end to end: verify it is actually workable, implement exactly what it specifies, prove the acceptance criteria by behavior, and hand the result to the landing lane. This is the execution link between the issue producers (`to-issues`, `triage`) and the closeout/merge lanes that land the result.

## Select One Issue

- Given an issue reference (number, URL, or path), fetch its full body and comments from the tracker.
- Given "the next ready issue": list the issues carrying the agent-ready triage role, exclude any whose blockers are not all closed, and pick the oldest unblocked one — naming the pick and the candidates skipped. If two candidates are equally eligible and materially different, ask rather than guess.
- Never take a ready-for-human issue: its role says the work needs a human. Say so and stop.
- One issue per invocation. The next issue is a fresh invocation in a fresh context — slices are sized for exactly that. Do not chain into a second issue because the first went quickly.

## Verify It Is Workable

- Every blocker must be closed before work starts — native issue dependencies where the tracker has them, `Blocked by` text otherwise. An agent-ready label with open blockers is a contradiction: report it and stop, do not start.
- The issue body is the contract: its scope section bounds the work, and the acceptance criteria are the definition of done. Read all comments — later comments amend the body. Read the agent brief when triage attached one.
- If the issue under-specifies the work — a decision the body does not make, context no exploration recovers — stop and route back: report what is missing and suggest the needs-info role (`triage` owns label moves). Do not invent the missing scope.

## Implement

- Work on a working branch per repo convention; never start on a protected branch without explicit consent.
- Scope strictly to the issue. Work it reveals but does not contain — a neighboring bug, a refactor itch, a missing test elsewhere — is surfaced for the tracker (`triage`), never absorbed silently.
- Where the behavior is specifiable up front, build test-first — `/tdd` or `$tdd` where available.
- Record deviations from the issue body as you make them; they belong in the completion report and the issue thread, not only in the diff.

## Prove And Hand Off

- Walk the acceptance criteria one by one: each gets fresh behavioral evidence (the command run and its output) or an honest `not verified` with the reason. A passing suite alone does not satisfy a criterion the suite does not exercise.
- Report: issue reference, branch, per-criterion evidence, deviations, and surfaced out-of-scope items.
- Landing is the next lane, not this one: route to the repo's closeout/merge/PR lanes and stop.
- Tracker mutations are approval-gated: propose the closing or status comment with the evidence summary, and post or close only on the user's approval. Never close or modify the parent issue.
