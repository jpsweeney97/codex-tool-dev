---
name: system-design-review
description: "Use when reviewing architecture or system design artifacts (design docs, codebases, verbal designs) for scoped design-lens gaps, inherited defaults, tradeoffs, and next probes. Do not use for code bug review, post-mortems, debt ranking, refactor sequencing, or readiness audits."
---

# System Design Review

Ask: **"Was this a conscious decision, or an inherited default?"** Stay at architecture level; surface underspecified decisions, defaults, tradeoffs, tensions, and next probes.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:system-design-review`.

- Use this skill for architecture and system design artifacts: design docs,
  codebases, verbal designs, subsystem/interface boundaries, runtime guarantees,
  data authority, trust surfaces, operational ownership, tradeoffs, and next
  probes.
- This skill wins over `scrutinize` when the requested lens is architecture or
  system design rather than general adversarial critique.
- Use `implementation-review` for completed code or artifacts against a
  plan/spec; use `scrutinize` for execution-readiness reviews before
  implementation.
- Use `review-reviewer` for explicit supplied-review adjudication,
  `review-claude-claims` for explicit itemized pasted-claim validation, and
  `request-claude-pr-review` for drafting a Claude PR-review prompt.
- If this skill is not the right review-family target, name the better skill
  and switch only when invocation rules allow it; otherwise ask one routing
  question.

## Workflow

1. **Frame** one scope: `system`, `subsystem`, or `interface`.
2. Infer 1-2 archetypes and stakes. Use `high` when external users, auth, sensitive data, migrations, SLO/SLA, distributed consistency, shared infrastructure, or multi-team blast radius are present.
3. **Screen** all 8 categories before findings: Structural, Behavioral, Data, Reliability, Change, Cognitive, Trust/Safety, Operational.
4. Load `references/system-design-dimensions.md` only after screening for lens names, archetype weighting, taxonomy, output contract, or tension prompts.
5. **Deep dive** only lenses promoted by archetype weighting, screening concerns, or cross-category linkage.
6. **Deliver** snapshot, coverage, findings, optional tensions, and 2-4 next probes.

## Boundaries

In scope: decision quality, boundaries, runtime guarantees, data authority, evolution, ownership, trust surfaces, and tradeoffs. Out of scope: code bugs, incident timelines, debt ranking, refactor sequencing, and implementation-readiness audits.

Use exactly one scope. If mixed scopes would change the review, ask one scope question and stop. If adjacent work is mixed in, do architecture first and state the handoff.

Default to read-only: do not edit files, create audit artifacts, stage, commit,
push, sync, publish, or implement fixes unless the user explicitly asks for
that separate action.

## Screening Rules

Use concrete anchors. A category is `screened` only when a specific anchor answers its sentinel without guessing; use `insufficient evidence` when evidence is weak.

Sentinels: Structural=components/boundaries; Behavioral=runtime under failure/retry/overload; Data=critical datum/source of truth; Reliability=guarantees/recovery/degradation; Change=migration/rollback/test isolation; Cognitive=responsibility/rationale discoverability; Trust/Safety=trust/privilege/sensitive-data boundary; Operational=deploy/config/observability/ownership.

Evidence floor: design docs need full-doc reading and section/diagram/table/decision anchors; codebases need up to 12 bounded anchors with primary plus corroborating evidence; verbal descriptions need explicit user claims.

Record one line per category: status, sentinel, anchor, disposition. Promote to `deep` when the category is archetype-primary/secondary, the sentinel finds concern, or it explains another concern.

## Stop Rules

Stop only for mixed scope, high-stakes framing ambiguity that changes lens selection, 4+ `insufficient evidence` categories without a best-effort request, or an explicit checkpoint.

Otherwise continue. For sparse but still useful evidence, label the review `reduced-depth`, use only evidence-backed categories, and cap findings at 4. Do not say "if you do not respond"; either ask one concrete question or continue.

## Deep Dive And Output

Select 6-10 lenses; 4-6 is enough for narrow interfaces or sparse input. Do not narrate every lens. Use the reference for decision states, finding caps, tension rules, and the output contract.

If no material findings surface, say so directly. End with 2-4 sharp questions, not a verdict, unless requested. Save to `docs/audits/YYYY-MM-DD-<target-slug>.md` only when explicitly asked; if the workspace already uses `docs/audits/`, suggest that path instead of writing it.
