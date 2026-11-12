---
name: implementation-planning
description: "Use when the user wants to turn a settled design, spec, PRD, or approved approach into a written implementation plan: ordered tasks, each with its check, that an executor with the repository and without this conversation can carry out. Also holds the optional acceptance-checks section for a settled source. Do not use for design exploration, tracker issue slicing, strategic sequencing of findings, ad hoc implementation, or executing the plan."
---

# Implementation Planning

Write an implementation plan that an executor with the repository in front of it, and without this conversation, can carry out: ordered tasks, each with the check that shows it worked. The plan document is the deliverable; executing it belongs to `execute-plan` or another executor.

## Trigger Boundaries

- Requires settled source material: an approved design, spec, PRD, or equivalent decision. If the design is still open, say so, name `design-exploration` where available, and ask before switching.
- Tracker issue slicing is `to-issues`; dependency-aware sequencing of findings is `/next-steps` or `$next-steps` where available, which the user must invoke explicitly. This lane owns the executable plan document.
- Writing the plan grants no execution authority. Do not start implementing.

## Plan Standards

- Ground the plan first: read the settled source in full, with any acceptance checks it already carries, and inspect the repo, so every path, pattern, and command the plan names is one you verified, not one you assumed.
- Read the source's seams. A design or shaping capsule that marks parts as the previous lane's compression, unpriced, unconfirmed, deferred, or accepted as offered has told you those parts are not settled: treat each as a gap under the rule below, never as a premise, and when a task would build on one that changes user-visible behavior or an interface, ask before writing it. A source that says only "settled" with no seam is read as if every part were accepted as offered, and the plan says so under `Planner decisions`.
- Number the tasks in the order the executor runs them. Each task is buildable and verifiable given only the tasks before it, and names the check that can run: a test, a validator, a diff, a rendered read.
- Exact file paths and exact commands. Write complete code only where the exact text matters: an interface, a schema, a migration, a tricky algorithm, wording a user reads. Elsewhere, say what the change is and how its check shows it worked.
- Measured against predicted. Code and expected output are predictions until they run. Where a command can run during planning, run it in a scratch copy — never on the target tree, since writing the plan grants no execution authority — and report what it produced; where it cannot, say the output is predicted. A measured output is stronger than a guessed one, and the plan should not hide the difference.
- Gaps in the source. The plan settles details the source never decided, and the executor will build those choices. Decide a gap yourself only when the choice is small, local, and easy to reverse, and list every such choice under a `Planner decisions` heading near the top of the plan, so the user can tell your calls from the source's. When a gap would change user-visible behavior or an interface, or would cross a scope line the source drew, ask the user before writing the tasks that depend on it.
- Before saving, check that every requirement in the source maps to a task. That check is the author's own pass, not an independent review; do not present it as one.

## Acceptance Checks (optional)

Add an `Acceptance checks` section to the plan when the user asks for acceptance checks, or when the source states an outcome that no task's own check would show. Each check has a stable ID (`AC-1`, `AC-2`), the behavior to observe, a `Passes when` clause, and a basis: `source-backed` (the source states it), `inferred` (needed to prove a stated outcome, with the reason), or `decision needed` (the source leaves it open). A `decision needed` check is not a requirement: it can neither pass nor fail until the user settles it, and the section says so. The checks derive from the source and never override it. Name the task whose verification runs each check.

## Artifact And Handoff

Save the plan to `docs/plans/YYYY-MM-DD-<topic>.md` unless the user or repo convention names another location; state the path and the planner decisions, or that there were none. Open the plan with the source path or issue reference it was derived from and the commit the repo was inspected at: that pin says what the paths and commands were verified against, not that the plan is fresh, so never make a task's proof depend on the source commit still being `HEAD` — the plan's own commits move it. Commit only per repo convention or user request. Then name the executor: `execute-plan` for in-session execution, or `to-issues` when the user wants tracker slices instead of a plan run. A push, a merge, or a pull request is not a task: landing belongs to the repository's landing lane, and `execute-plan` stops at a reviewed, committed branch. When the user wants the run to end in a PR or a merge, say so in one line at the top of the plan for the executor to settle at its Load And Review, never as a task step. The plan's authority ends where execution's record begins: once `execute-plan` runs it, corrections and divergences live in that run's record, and a plan rewritten after execution to match what was built says so at the top, as a record rather than a contract.
