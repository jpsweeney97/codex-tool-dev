---
name: pragmatic-review
description: Explicit-only review skill for plans, specs, handoffs, and repo artifacts. Use when invoked as $pragmatic-review. Finds execution blockers, false proof labels, scope or authority drift, weak gates, and overfit assumptions. Review-only unless patching is requested.
---

# Pragmatic Review

Review the requested artifact for execution risk in the live repository. Stay
review-only unless the user explicitly asks for patches.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:pragmatic-review`.

- Use this skill only when explicitly invoked for execution blockers, false
  proof labels, weak gates, scope or authority drift, runtime/source mismatch,
  certification gaps, or implementation-readiness risk.
- Use `scrutinize` for broad natural-language adversarial critique when this
  skill was not invoked.
- Use `implementation-review` for completed code or artifacts against a
  plan/spec; use `system-design-review` for architecture tradeoffs and system
  boundaries.
- Use `review-reviewer` for explicit supplied-review adjudication,
  `review-claude-claims` for explicit itemized pasted-claim validation, and
  `request-claude-pr-review` for drafting a Claude PR-review prompt.
- If this skill is not the right review-family target, name the better skill
  and switch only when invocation rules allow it; otherwise ask one routing
  question.

## Workflow

1. Read the target artifact before judging it.
2. If the target is missing, ambiguous, unreadable, or outside accessible
   context, stop with a blocker and ask for one concrete path.
3. Check only named or adjacent context needed to verify material claims.
4. Find concrete failures: blockers, false proof/release labels, hidden scope,
   authority/runtime drift, weak gates, and local-state overfit.
5. Open `references/review-rubric.md` only for severity or proof-class
   calibration.
6. Return findings first, ordered by severity, then residual risks and verdict.

## Bounded Review Mode

Use bounded review mode when the artifact, repo context, runtime surface, or
proof chain is too large to inspect completely in one pass. State the reviewed
subset before findings, inspect the highest-risk execution gates first, mark
omitted proof classes `unverified`, and give the next slice needed for a
complete readiness verdict. Do not return **Ready to Execute** from a bounded
pass.

## Evidence

- Cite file and line evidence. If line anchors are impossible, say why and cite
  stable anchors.
- Separate source truth, runtime truth, docs readiness, and certification when
  proof classes are mixed.
- Missing or blocked proof is missing evidence, not a pass.

## Finding Format

Each finding must include `Severity`, `Failure mode`, `Evidence`, `Why it
Matters Pragmatically`, and `Smallest Credible Repair`.

## Verdict

End with exactly one verdict:

- **Ready to Execute**
- **Patch Before Implementation**
- **Not Executable Yet**
- **Partial Review Only**

Do not praise the artifact generally. If there are no material findings, say so
directly and name residual risks.

## Boundaries

Default to read-only: do not edit files, stage, commit, push, delete, sync,
publish, or implement fixes during the review. If asked to patch after the
review, fix only the smallest scope needed to resolve the findings.
