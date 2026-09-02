---
name: execute-plan
description: "Use when the user asks to execute an existing implementation plan document task-by-task, by dispatching per-task subagents or working inline. Do not use for writing or revising the plan, tracker issue triage, ad hoc implementation without a plan artifact, debugging unrelated failures, or merge/PR/closeout lifecycle."
---

# Execute Plan

Execute a written implementation plan task-by-task with review gates. The plan is the contract; this lane owns faithful execution, not redesign.

## Load And Review

Read the plan fully and review it critically before starting. Raise gaps, contradictions, or concerns with the user first — do not execute a plan you do not believe in, and do not silently "fix" it either; plan changes go back to the user or to `implementation-planning`. Work on a working branch per repo convention; never start on a protected branch without explicit consent.

## Mode

- Subagent mode is the default when subagent tooling is available: fresh subagent per task.
- Inline mode when no subagent support exists or the user prefers it: execute tasks yourself under the same gates.

## Subagent Mode

- Give each subagent the full task text plus exactly the context the task needs. Do not make it read the plan file or inherit session history; curated context keeps it focused and preserves your own context for coordination.
- Answer a subagent's questions before letting it proceed.
- Two-stage review per task, in order: spec-compliance review first (the change matches the task — nothing missing, nothing extra), then code-quality review. Do not start quality review until spec compliance passes; quality polish on non-compliant work is wasted.
- Review loops: findings go back to the implementer; re-review after fixes. Do not skip the re-review or accept "close enough".
- An implementer's self-review never replaces either review.
- Status protocol: implementers report `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`. Read concerns before proceeding; supply missing context and re-dispatch; for `BLOCKED`, change something — more context, a smaller task, a more capable model — or stop and ask. Never re-dispatch unchanged and hope.
- After all tasks, run one final review of the whole implementation against the plan — `review-family:implementation-review` when it is available, otherwise the same inline spec-then-quality review.

## Inline Mode

Follow each task's steps exactly, run every verification as written, and treat task boundaries as checkpoints. Do not batch ahead of a failing verification.

## Pace And Stops

Execute continuously; do not pause between tasks to ask whether to continue. Stop only for: a blocker you cannot resolve, repeated verification failure, a plan gap or ambiguity that genuinely prevents progress, or completion. Ask rather than guess. When resuming after an interruption, re-verify the last task's actual state before re-running it: a non-idempotent step — a migration applied, a message sent, a record inserted — double-applies silently if redone, so resume from verified state, not from where the plan says you were.

## Completion

Report tasks completed, verification evidence, and any divergences from the plan. Closing out, merging, and PR creation belong to `closeout-check`, `merge-branch`, or the PR lane — name the next move and stop.
