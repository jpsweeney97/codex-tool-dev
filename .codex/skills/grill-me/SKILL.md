---
name: grill-me
description: Use when the user explicitly asks to be grilled, stress-tested interactively, challenged one question at a time, or interviewed about a plan, design, architecture, strategy, or decision. This is an interactive drill mode where each turn asks one high-leverage question and includes the agent's recommended direction. Do not trigger for incidental mentions of "grill me", meta-discussion of this skill, or requests for a complete critique/report unless the user explicitly wants an interactive grilling session.
---

# Grill Me

Interrogate the user's plan or design until the important decisions, assumptions, risks, and dependencies are clear.

## Core Behavior

- Ask exactly one question at a time.
- Include your recommended answer or recommended direction with each question.
- After asking the question and giving your leaning, stop and wait for the user's answer unless the user asked you to stop or summarize.
- Frame the leaning as tentative when user goals, values, or constraints are missing.
- Prefer the highest-leverage unresolved issue over a fixed checklist order.
- Challenge weak, vague, or inconsistent answers before moving to a new topic.
- Across turns, track resolved decisions, unresolved assumptions, and the current blocker.
- Inspect only enough to avoid asking for information already available. If inspection would become broad or unavailable, state the limitation and ask the next useful question.
- Artifact and codebase inspection is read-only unless the user explicitly asks for edits.

## Defaults

- If the target is unclear, ask one clarifying question about what plan, design, decision, or strategy to drill.
- If several targets are present, ask which target to drill first unless one target clearly blocks the others; if choosing, explain that choice in one sentence.
- If the user asks for a complete critique, report, or review, prefer the relevant review skill unless they explicitly asked for an interactive grilling session.
- If the user asks to stop, summarize the resolved decisions, remaining risks, and recommended next step.

## How to Choose the Next Question

Choose the next question based on what would most improve or threaten the plan:

- an unstated goal or non-goal
- a hidden dependency
- an architectural or sequencing choice
- a failure mode
- a tradeoff the user appears to be avoiding
- an assumption contradicted by evidence
- a missing verification or rollout path

Do not mechanically exhaust this list. Use it to guide judgment.

## Turn Shape

Use natural conversation, but make each turn contain:

- the question
- why it matters, when not obvious
- your recommended answer or leaning

Keep the format compact. Use explicit labels only when they improve clarity.

Illustrative shape, not a template:

```markdown
Question: What has to be true for the rollback path to work under production load?

Why it matters: If rollback only works in a clean test environment, the migration is not actually reversible.

My leaning: Treat rollback rehearsal as a release gate, not a nice-to-have.
```

## Stopping Point

Continue until the main decision path is chosen, the blocking assumption is named, the remaining risk is explicitly deferred, or the user stops the drill. When stopping, summarize the resolved decisions, remaining risks, and recommended next step.
