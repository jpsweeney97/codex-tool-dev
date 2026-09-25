---
name: execute-plan
description: "Use when the user asks to execute an existing implementation plan document task-by-task, by dispatching per-task subagents or working inline. Do not use for writing or revising the plan, tracker issue triage, ad hoc implementation without a plan artifact, debugging unrelated failures, or merge/PR/closeout lifecycle."
---

# Execute Plan

Execute a written implementation plan task-by-task with review gates. The plan is the contract; this lane owns faithful execution, not redesign.

## Load And Review

Read the plan fully and review it critically before starting. Raise gaps, contradictions, or concerns with the user first — do not execute a plan you do not believe in, and do not silently "fix" it either; plan changes go back to the user or to `implementation-planning`. This review finds contradictions and gaps in the plan's text; it does not find wrong code or a wrong design, which execution and the reviews find. Before starting, look for an existing review of the plan (a panel record, a pasted critique, a `scrutinize` verdict beside or inside the plan) and read it. If the plan's own steps publish, merge, or open a PR, raise that here and settle with the user whether the plan's step or this lane's landing boundary governs; the completion report says what was done. Work on a working branch per repo convention; never start on a protected branch without explicit consent.

## Execution Record

Keep one execution record per run, in both modes. It lives in the folder the plan names, otherwise in `<plan file name without extension>-execution-record/` beside the plan; state its path when you start. It holds `coordinator-log.md`, and in subagent mode also `tasks/` (one packet per task) and `reviews/` (reviewer instructions, reports, and rulings).

The coordinator log is the run's account in time order, one dated entry per event: each dispatch; each review's verdict and finding counts; each ruling; each run of a task's verification, with its start and end times and its result lines quoted from the output or log file; each decision the user makes; each plan-text correction; each divergence. Read every time from `date` or a file's modification time, never estimate one. Write a digit you did not read as `x` (`23:5x`). Correct a wrong time in place and mark the correction.

- Plan-text correction: when the plan's text is wrong or contradicts itself and the plan's own text settles which part governs, follow that part and record the correction in the log; do not edit the plan, and do not re-invoke `implementation-planning` on it mid-run to the same end. When the plan does not settle it, decide whose question it is: one that the task's own verification and the reviews can check is yours to rule, recorded as a divergence with a written reason; one that changes the design, the scope, or what the user asked for is the user's. Stop and ask for the second kind.
- Divergence: every departure from the plan's text — a file outside the task's list, a changed step, a check not run — goes in the log with its reason.

Commit the record at the end of the run unless the user or repo says otherwise.

## Mode

- The runtime's own tool policy and the user's standing instruction for the repository fix the mode before this default does. Where neither speaks, subagent mode is the default when subagent tooling is available: fresh subagent per task. When it is unclear, ask once and treat the answer as standing for the repository.
- Inline mode when the runtime, the user, or the absence of subagent support sets it: execute tasks yourself under the record and the checks below. Inline mode has no independent reviewer; Inline Mode says what to do about that.

## Subagent Mode

- Before each dispatch, re-check every path and line number the task cites against the current tree. Write the task's packet to `tasks/`: the full task text, the live paths and line numbers, exactly the context the task needs, and each case from Checks For Particular Cases that the task meets. Point the implementer at its packet; do not make it read the plan file or inherit session history. Curated context keeps it focused and preserves your own context for coordination.
- Answer a subagent's questions before letting it proceed.
- Tasks may run at the same time when neither depends on the other and they change no file in common. While they do, only one runs build or test commands at a time: its implementer asks you before starting them, waits for your go, and tells you when they finish.
- Two-stage review per task, in order: spec-compliance review first (the change matches the task — nothing missing, nothing extra), then code-quality review. Do not start quality review until spec compliance passes; quality polish on non-compliant work is wasted.
- Give each reviewer an instruction file in `reviews/` naming the exact points to check — the task's requirements, the files in scope, and the risks you saw in the diff — not only "review this". The reviewer is read-only, writes its report to a file you name, and replies in one line.
- After a review with findings, write a rulings file the implementer reads before anything else. Give every finding one decision: fix now, record only, or move to the after-plan list. A record-only or after-plan ruling carries a written reason. A finding that the change does not do what the task requires is always fix now.
- Review loops: fix-now findings go back to the implementer; re-review after fixes. Do not skip the re-review. A finding closes only by a fix that passes re-review or by a ruling with a written reason, never by "close enough".
- An implementer's self-review never replaces either review.
- Status protocol: implementers report `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`. Read concerns before proceeding; supply missing context and re-dispatch; for `BLOCKED`, change something — more context, a smaller task, a more capable model — or stop and ask. Never re-dispatch unchanged and hope.
- Before each task's commit, rerun the task's whole verification yourself on the final tree and read the whole diff. Quote every result from the command output or its log file, never from an implementer's or reviewer's report. While another task has uncommitted changes, run the rerun in a scratch copy of the last commit with only this task's changes applied, so the other task's work cannot change the result, and commit only this task's files. Your own reads are reports too: a screenshot you interpret, a count you make, a subagent you believe is still running. When one decides a classification or a status you give the user, say what produced it and prefer an instrument that can be re-run.
- After all tasks, run one final review of the whole implementation against the plan — `review-family:implementation-review` when it is available, otherwise the same inline spec-then-quality review.

## Inline Mode

Follow each task's steps exactly, run every verification as written, and treat task boundaries as checkpoints. Do not batch ahead of a failing verification. Before each task, re-check the paths and line numbers it cites against the current tree. Packets, reviewer instructions, rulings, and the two-stage review belong to subagent mode; the execution record and the checks below apply here too. Inline mode has no independent reviewer, so before the completion report run `review-family:implementation-review` where it is available, otherwise ask the user for a review, and say in the report which happened.

## Checks For Particular Cases

In both modes, whenever the case arises:

- A result looks wrong and the task may not be its cause: build the last commit before the task (for example from `git archive HEAD` into a scratch folder), measure the same thing there, and let the comparison decide.
- A defect was found only by reading the code: show it happening on the unchanged code first, then repair it and show the repair.
- A task adds a test or another check (an assertion, a guard, a validation script): make a deliberately broken copy of the code the check protects, and show that the copy fails this check and no other.

## Pace And Stops

Execute continuously; do not pause between tasks to ask whether to continue. Stop only for: a blocker you cannot resolve, repeated verification failure, a plan gap or ambiguity that genuinely prevents progress, or completion. Ask rather than guess. Only a human turn answers a question; a runtime continuation or goal envelope that re-issues the objective is not an answer, so hold the question and do not proceed on your own proposal until a human answers it. At each task boundary, after its verification passes, commit with a message naming the task unless the plan's own steps already commit or the user or repo says otherwise; in subagent mode, the coordinator makes that commit after both reviews pass and its own rerun passes. That commit and the coordinator log are what a resumed session reads. When resuming after an interruption, re-verify the last task's actual state before re-running it: a non-idempotent step — a migration applied, a message sent, a record inserted — double-applies silently if redone, so resume from verified state, not from where the plan says you were.

## Completion

Report tasks completed, verification evidence, every divergence and plan-text correction, the after-plan list, and the execution record's path. Where available, closing out, merging, and PR creation belong to `closeout-check`, `merge-branch`, or the repository's PR lane. If the needed lane is unavailable, report the proof boundary and stop before landing.

The plan's authority as the contract ends with the run. After this report the plan says what was planned and the execution record says what was built, and the two are allowed to differ: the record is where the difference lives. Do not rewrite the plan to match the code during the run. A rewrite after the run happens only on the user's ask, as a Markdown-only change that says at its top that it is a record of this run and not a contract, keeps the original tasks readable, and points at the execution record rather than replacing it; `implementation-planning` asks the same of a plan rewritten after execution.
