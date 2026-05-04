---
name: scrutinize
description: Use when the user explicitly wants a harsher-than-normal critical review of a plan, design, draft, argument, decision, or code artifact. Trigger on requests like "scrutinize this", "be brutal", "tear this apart", "assume this is wrong", "reject until proven otherwise", or "review this with maximum scrutiny". Challenge the premise first, then run two passes that search for flaws, omissions, weak assumptions, second-order effects, edge cases, and hidden dependencies. Do not use for routine code review, collaborative editing, or balanced feedback when the user did not ask for an adversarial stance.
---

# Scrutinize

Produce a reject-until-proven-credible review. Assume the target is not ready and your job is to find the reasons. Do not look for what works until you have exhausted the serious ways it could fail.

## Quick Start

- Identify the exact target before criticizing it.
- If the target is a file path or reference, read it first. If it is inline content, review it directly.
- Challenge whether the target is solving the right problem before reviewing execution quality.
- Run two passes:
  - `Pass 1` finds obvious flaws, contradictions, omissions, weak assumptions, and practical failure points.
  - `Pass 2` goes deeper into second-order effects, edge cases, scaling issues, incentive problems, hidden dependencies, and ideal-condition assumptions.
- In `Pass 2`, apply at least 3 adversarial perspectives that are genuinely relevant to the target. If a perspective does not expose anything new, replace it.
- If the target is large, prioritize the highest-risk areas and state what you did not review deeply.
- If the target survives scrutiny, say why it survives, then focus on residual risks and realistic failure scenarios.

## Defaults And Failure Modes

- If the target is unclear, ask a targeted question instead of scrutinizing the wrong artifact.
- If several artifacts are in play, ask which one to scrutinize first or split the review into named targets.
- If the target is incomplete, review what exists and treat missing information as a risk, not as permission to fill in the gaps.
- If the request mixes critique with implementation help, finish the scrutiny first. Only switch into collaborative mode after the review is complete.
- If you cannot inspect a dependency, runtime, or external behavior directly, record that uncertainty as a liability.
- If you do not find major flaws, say so directly. Do not pad the review with weak objections.

## Non-Negotiables

- Default stance: reject until the target earns a more favorable verdict through the absence of serious flaws.
- Treat ambiguity as a liability.
- Assume missing information is a risk, not a harmless omission.
- Prefer concrete criticism over generic advice.
- Do not mentally repair broken logic or missing details.
- Do not soften findings with hedging unless uncertainty is genuinely unavoidable.
- Do not stop at surface-level comments.

## Adapt The Scrutiny To The Target

### Plans

Attack sequencing, ownership, logistics, resourcing, dependencies, and contingency gaps. Find hidden prerequisites, coordination risks, bottlenecks, and single points of failure.

### Writing

Attack logic, clarity, structure, precision, evidence, credibility, and tone. Find contradictions, unsupported claims, bloated phrasing, weak transitions, and places where a skeptical reader would lose trust.

### Code

Attack correctness, security, data integrity, edge cases, failure handling, maintainability, and performance. Look for invalid state transitions, race conditions, silent failure paths, brittle abstractions, confusing control flow, and test gaps that leave behavior unproven.

### Strategy

Attack the thesis, assumptions, incentives, tradeoffs, execution path, and competitive reality. Find wishful thinking, weak differentiation, hidden dependency on ideal behavior, and second-order effects that were ignored.

## Workflow

### 1. Identify The Target

State what is being scrutinized in one sentence. If there is no clear target, stop and ask what to review.

### 2. Challenge The Premise

Before reviewing execution quality, ask whether the target is solving the right problem or answering the right question. If the goal is flawed, misframed, or answering the wrong question, say so before proceeding.

### 3. Run Pass 1

Find the obvious flaws, contradictions, omissions, weak assumptions, and practical failure points.

### 4. Run Pass 2

Go deeper. Look for second-order effects, edge cases, scaling problems, incentive issues, hidden dependencies, and places where the target works only under ideal conditions.

Name at least 3 adversarial perspectives that are relevant to the target, then inspect the target through each perspective. A perspective that does not surface anything new was the wrong perspective; replace it.

### 5. Synthesize The Findings

Decide whether the findings share a root cause or whether they are independent. Distinguish point defects from systemic patterns.

### 6. Issue The Verdict

Give the strongest defensible verdict based on the evidence:

- `Reject`
- `Major revision`
- `Minor revision`
- `Defensible`

## Finding Format

Use one of these two formats:

### Discrete Issues

1. The flaw
2. Why it matters
3. How it fails in practice
4. Severity: `Critical`, `High`, `Medium`, or `Low`
5. What would need to change to make it defensible

### Systemic Observations

Use this only for genuinely pervasive patterns, not as a substitute for naming specific issues.

1. The pattern
2. Its impact
3. The correct approach

## Output Format

Use this structure:

```markdown
## Scrutiny: [target name]

### Premise Check
[is this solving the right problem?]

### Critical Failures
[ranked findings or "none"]

### High-Risk Assumptions
[validated, weak, or missing assumptions]

### Real-World Breakpoints And Edge Cases
[where this fails outside ideal conditions]

### Hidden Dependencies Or Bottlenecks
[externalities, coordination risks, runtime dependencies]

### Adversarial Perspectives Applied
[perspective -> what it exposed]

### Patterns And Root Causes
[shared causes, or say the findings are independent]

### Required Changes Before This Is Credible
[minimum bar to raise the verdict]

### Verdict
`Reject` / `Major revision` / `Minor revision` / `Defensible`
[1-2 sentence synthesis]
```

If the user asks for a shorter answer, keep the same section order and compress the content rather than dropping sections.
