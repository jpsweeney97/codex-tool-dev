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

## Full Template

```markdown
## Scrutiny: [target name]

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

### Adversarial Perspectives Applied
[perspective -> exposure]

### Patterns And Root Causes
[shared causes or independent findings]

### Required Changes Before This Is Credible
[minimum bar]

### Verdict
`Reject` / `Major revision` / `Minor revision` / `Defensible`
[1-2 sentence synthesis]
```

If the user asks for a shorter answer, keep the same section order and compress the content rather than dropping sections.
