---
name: implementation-planning
description: "Use when the user wants to turn a settled design, spec, PRD, or approved approach into a written implementation plan: ordered tasks an executor with no codebase context could follow exactly. Do not use for design exploration, tracker issue slicing, acceptance-check mapping, strategic sequencing of findings, ad hoc implementation, or executing the plan."
---

# Implementation Planning

Write an implementation plan a skilled engineer with zero context for this codebase could execute without guessing. Assume they know their craft but nothing about this repo's toolset, domain, or conventions. The plan document is the deliverable; executing it belongs to `execute-plan` or another executor.

## Trigger Boundaries

- Requires settled source material: an approved design, spec, PRD, or equivalent decision. If the design is still open, name `design-exploration` and ask before switching.
- Tracker issue slicing is `to-issues`; observable acceptance checks are `acceptance-map`; dependency-aware sequencing of findings is `/next-steps` or `$next-steps`, which the user must invoke explicitly. This lane owns the executable plan document.
- Writing the plan grants no execution authority. Do not start implementing.

## Plan Standards

- Ground the plan first: read the settled source design, spec, or PRD in full, and inspect the actual repo — existing file layout, conventions, and the build/test commands — so every path, pattern, and command the plan names is one you verified, not one you assumed.
- If the source design covers multiple independent subsystems, flag it and split into one plan per subsystem; each plan should yield working, verifiable software on its own. The detection tells and the cycle test for whether a split is real live in `design-exploration`'s scope check — apply them there rather than re-deriving.
- Map the file structure before tasks: which files are created or modified and each one's single responsibility. Follow existing repo patterns.
- Number the tasks and order them so each is buildable and verifiable given only the tasks before it; when a task depends on earlier work, an earlier-numbered task must satisfy that dependency. The executor runs them in document order.
- Decompose into tasks that produce self-contained, verifiable changes. Four tells that a task is still too big — a break-it-down provocation, not a size ladder: it would take more than one focused session; its acceptance criteria will not fit in three or fewer bullets; it touches two or more independent subsystems; its title needs an "and" (that is two tasks). Within tasks, bite-sized steps — one action each: write the failing test, run it and watch it fail, implement minimally, run and watch it pass, commit. Keep test-shaped steps consistent with the `tdd` skill.
- Exact file paths always. Complete code in every code step. Exact commands with expected output.
- No placeholders. "TBD", "add appropriate error handling", "write tests for the above", and "similar to Task N" are plan failures: show the actual content, and repeat it rather than cross-referencing — the executor may read tasks out of order. Reference no type, function, or method that no task defines.

## Self-Review

After drafting, check the plan against the source material with fresh eyes:

1. Coverage: every requirement maps to a task. List gaps and add tasks.
2. Placeholder scan for the failure patterns above.
3. Consistency: names, signatures, and types match across tasks.

Fix issues inline and move on.

## Outside-View Pass

Self-Review checks the plan against its source material: the inside view, where every requirement maps to a task. But a decomposition that covers the spec still inherits the spec's blind spots — an inside-view plan feels complete and systematically under-scopes, because the spec and the breakdown both omit the work everyone knows but no one wrote down. This is the planning fallacy; the correction is the outside view (reference-class forecasting). After Self-Review, run it.

1. Name the reference class. What *kind* of change is this — a schema migration, an auth-provider integration, a new endpoint, a framework bump? The class, not this specific plan, carries the base rate.
2. Consult the base rate. Prefer this repo's own track record: find comparable past plans, PRs, or changes and read what they actually required; fall back to general knowledge of how that class behaves. The forcing question: *what do changes of this class reliably require that my decomposition left out?* A plan to add an auth provider, for instance, surfaces the token-refresh path, the migration of existing sessions, and the rate-limit handling that the "add OAuth login" spec never named.
3. Edit the plan in place. Add the missing tasks, widen the ones scoped too thin, and flag the steps this class reliably balloons — qualitatively; the plan stays a task list, not a schedule, so no clock estimates. The common omissions are a provocation to check against, never a checklist to complete: integration glue, data migration and backfill, config and secrets, error and retry paths, test fixtures and infrastructure, rollback, docs, observability, performance under real load. Which of these the reference class actually demands is the judgment; running the list to feel thorough is not. Whatever you add or widen holds to the same Plan Standards as the rest — exact paths, complete code, no placeholders — so the executor follows the new tasks as exactly as the original ones.

This is the reference-class completeness debias, not failure-imagination: consult what this class of work actually required, not what could newly go wrong. If you find yourself inventing novel, plan-specific failure scenarios or wanting dated tripwires, that is `premortem`, a separate pass — here you fix the plan in place. And it corrects under-scoping toward the base rate, not toward gold-plating: add what the class reliably needs, not every task it might conceivably want.

Close honestly. The reference class is one you drew, and a base rate is a prior, not a guarantee — this debiases the plan, it does not certify it complete. Name the class you compared against; do not stamp the plan comprehensive.

## Artifact And Handoff

Save the plan to `docs/plans/YYYY-MM-DD-<topic>.md` unless the user or repo convention names another location; state the path. Commit only per repo convention or user request. Then name the executor: `execute-plan` for in-session execution, or `to-issues` when the user wants tracker slices instead of a plan run.
