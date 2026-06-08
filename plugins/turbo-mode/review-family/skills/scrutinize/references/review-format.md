# Scrutinize Review Format

Load this only when a scrutiny needs repeated finding fields or a reusable full-review template.

## Findings

Discrete issue fields:

1. Flaw
2. Impact
3. Failure path
4. Severity: `Critical`, `High`, `Medium`, or `Low`
5. Required change

Severity calibration rule: target-internal contradictions may be reported from the target alone. If a `Critical`, `High`, or verdict-driving claim depends on an external citation, read the cited resource or mark it `uncalibrated / citation not inspected`.

Systemic observation fields, only for pervasive patterns:

1. Pattern
2. Impact
3. Correct approach

Add `Adversarial Perspectives Applied` only when a lens materially changed
finding selection, severity, or required changes. Keep lenses internal for small
or straightforward reviews.

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

If the user asks for a shorter answer, keep the same section order and compress the content rather than dropping sections.

## Formal Stress Test Add-On

Use this only when the user asks for a formal stress test or the target is
high-stakes enough that hidden assumptions or quiet failures could materially
damage the work.

Add these sections explicitly:

1. `Assumptions Audit`: verdict-driving assumptions only, with assumption and
   evidence tags.
2. `Pre-Mortem`: most likely failure and most damaging quiet failure.
3. `Dimensional Critique`: explicit correctness and completeness coverage, plus
   relevant optional dimensions.
4. `Confidence Boundary`: prose summary of what was checked, what remains
   unverified, and what evidence would change the verdict.

Do not add a numeric confidence score unless the user asks for one.
