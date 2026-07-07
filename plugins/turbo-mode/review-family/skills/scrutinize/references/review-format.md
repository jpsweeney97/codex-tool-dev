# Scrutinize Review Format

Load this only when a scrutiny needs repeated finding fields or a reusable full-review template.

## Findings

Discrete issue fields:

1. Flaw
2. Impact
3. Failure path
4. Severity: `Critical`, `High`, `Medium`, or `Low`
5. Required change

Severity/citation calibration is governed by the Citation calibration rule in SKILL.md (Guardrails): target-internal contradictions may stand on the target alone, but any high-severity or verdict-driving claim that depends on an external citation must read the cited resource or be downgraded to the `uncalibrated / citation not inspected` marker. SKILL.md holds the authoritative severity/verdict trigger scope.

Systemic observation fields, only for pervasive patterns:

1. Pattern
2. Impact
3. Correct approach

Emit the `Adversarial Perspectives` section only under the materiality gate in SKILL.md (Output and workflow step 8); that gate also covers keeping lenses internal for small or straightforward reviews.

## Full Template

```markdown
## Scrutiny: [target name]

### Target And Evidence
[target, inspected sources, skipped material, proof class, runtime/current-state checks]

### Premise Check
[right problem?]

### Critical Failures
[ranked findings or "none"]

### High-Risk Assumptions
[validated, weak, or missing assumptions]

### Real-World Breakpoints And Edge Cases
[where this fails outside ideal conditions]

### Hidden Dependencies Or Bottlenecks
[externalities, coordination risks, runtime dependencies]

### Patterns And Root Causes
[shared causes or independent findings]

### Required Changes Before This Is Credible
[minimum bar]

### Verdict
`Reject` / `Major revision` / `Minor revision` / `Defensible`
[1-2 sentence synthesis]
```

The verdict enum and severity scale restate the authoritative inline definition in SKILL.md (Workflow), which also governs verdict scope and the scoping-gloss form.

If the user asks for a shorter answer, keep the same section order and compress the content rather than dropping sections.

## Execution-Readiness Review

Use this when the user asks whether a plan, spec, handoff, rollout note, or artifact is ready to build from.

Replace `Verdict` with:

```markdown
### Execution Readiness Verdict
`Ready to Execute` / `Patch Before Implementation` / `Not Executable Yet` / `Partial Review Only`
[1-2 sentence action decision]
```

Readiness-finding shape and `Partial Review Only` usage follow SKILL.md (Execution-Readiness Reviews and Output).

## Formal Stress Test Add-On

Use this only when the user asks for a formal stress test or the target is high-stakes enough that hidden assumptions or quiet failures could materially damage the work.

Add these sections explicitly:

1. `Assumptions Audit`: verdict-driving assumptions only, with assumption and evidence tags.
2. `Pre-Mortem`: most likely failure and most damaging quiet failure.
3. `Dimensional Critique`: explicit correctness and completeness coverage, plus relevant optional dimensions.
4. `Confidence Boundary`: prose summary of what was checked, what remains unverified, and what evidence would change the verdict.

Numeric-confidence policy and combined stress-test + execution-readiness handling follow SKILL.md (Formal Stress Tests and Execution-Readiness Reviews).
