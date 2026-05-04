---
name: making-recommendations
description: Use when the user asks for a recommendation, wants to compare alternatives, choose between approaches, or decide how to proceed under trade-offs. Trigger on requests like "what should I use", "which is better", "recommend", "help me decide", "what's the best way to", or "should I go with X or Y". Also use when an ongoing discussion surfaces a non-trivial decision point with multiple viable options. Do not use for purely factual questions or trivial, low-stakes, easily reversible choices.
---

# Structured Recommendations

Produce a structured recommendation for a non-trivial choice. Act as an analyst and recommender, not an advocate for the first plausible option.

## Quick start

- Extract the decision in one sentence and name the decision type.
- Calibrate stakes using reversibility and blast radius.
- Generate the full option set before evaluating any option. Always include the null option.
- Evaluate each option against criteria derived from this specific decision, not a generic checklist.
- Rank every option, then recommend one and label the result as `verifiably best` or `best available`.
- Verify unstable facts before ranking options when the recommendation depends on current pricing, product availability, laws, schedules, or other time-sensitive details.

## Defaults and failure modes

- If the decision is ambiguous, stop and ask a targeted clarifying question.
- If multiple decisions are tangled together, split them or ask which one to resolve first.
- If the option set collapses to one serious option plus the null option, say so explicitly instead of inventing fake alternatives.
- If the user asks for a quick answer, compress the analysis but still include ranked options, the recommendation, and the readiness signal.
- If a material information gap can be resolved before commitment, say how to resolve it. If it cannot be resolved in time, recommend under uncertainty and mark the result `best available`.

## Non-negotiables

- Always include the null option: do nothing, defer, or keep the current state. If it is non-viable, say why explicitly.
- Separate option generation from option evaluation.
- Present ranked options and trade-offs before the final recommendation.
- Make the recommendation follow from the ranking. If it does not, reconcile the discrepancy explicitly.
- Treat the job as done only when the recommendation is either `verifiably best` or clearly labeled `best available` with the blocking gaps named.

## Workflow

### 1. Extract the decision

State the decision in one precise sentence drawn from the conversation. Name the decision type, such as technical selection, architectural choice, process design, tooling, or prioritization.

### 2. Calibrate stakes

Assess two axes:

- `Reversibility`: easy to undo -> hard to undo
- `Blast radius`: affects one thing -> affects many things or many people

Assign a tier and state it in 1-2 sentences.

| Tier | Criteria | Required treatment |
| ---- | -------- | ------------------ |
| Low | Reversible and narrow blast radius | Skip Information Gaps and Sensitivity Analysis. Say that you are skipping them and why. |
| Medium | Partially reversible or meaningful blast radius | Run Information Gaps. Abbreviate Sensitivity Analysis to 1-2 realistic flips. |
| High | Hard to reverse or wide blast radius | Run the full workflow. Produce a durable record when appropriate. |

### 3. Generate options

List every candidate option, including:

- All options raised in the conversation
- Any materially distinct alternatives not yet raised
- The null option: do nothing, defer the decision, or accept the current state

Do not evaluate options here.

### 4. Identify information gaps

Required for Medium and High. Skip for Low and say why.

For each material gap:

- Name the unknown
- State which options it most affects
- State whether it can be resolved before committing and, if so, how
- State whether the decision must be made under uncertainty if the gap remains open

### 5. Evaluate options

Derive evaluation criteria from the decision context. Do not default to a generic checklist.

For each option, state:

- Key strengths
- Key weaknesses or risks
- Conditions under which it is the best choice

If you cannot state when an option is the best choice, keep analyzing before you rank it.

### 6. Run sensitivity analysis

Required for High. Abbreviate for Medium. Skip for Low.

For each non-recommended option, state what would have to be true about constraints, unknowns, or future conditions for it to become the better choice. If no realistic change flips the ranking, say so explicitly.

### 7. Rank options

Present all options in ranked order with a one-line trade-off summary for each.

1. **[Option]** - [trade-off summary]
2. **[Option]** - [trade-off summary]
3. **[Option]** - [trade-off summary]

### 8. Recommend

State the recommended option and the core reasoning in 2-3 sentences. Tie it directly back to the ranking.

### 9. Signal readiness

State whether the recommendation is `verifiably best` or `best available`.

| Signal | Meaning |
| ------ | ------- |
| `verifiably best` | The option space is complete, the information gaps are resolved or non-material, and the ranking is stable under sensitivity analysis. |
| `best available` | The recommendation is sound given current information, but named gaps or unresolved conditions could still flip the ranking. |

If the result is `best available`, list the specific conditions that would upgrade it to `verifiably best`.

## Durable record for high-stakes decisions

- If the user asks for a durable record, or the workspace already uses `docs/decisions/`, write `docs/decisions/YYYY-MM-DD-<decision-slug>.md`.
- If neither condition is true, keep the full analysis in the reply and say that no durable record was written.
- Include the 9 sections above plus any comparison tables or calculations that materially support the ranking.
- After writing a record, include this inline summary:

```markdown
**Recommendation:** [Selected option]
**Why:** [2-3 sentence summary]
**Trade-offs accepted:** [What is being sacrificed]
**Readiness:** verifiably best / best available - [one-line justification]
**Full analysis:** [link to decision record]
```

## Anti-patterns

| Pattern | Problem | Fix |
| ------- | ------- | --- |
| Recommending the familiar option | Familiarity is not a criterion for the user's problem. | Generate 3 or more alternatives when they exist, including at least one option you would not reach by habit. |
| Evaluating during generation | Early judgment anchors the entire recommendation. | Keep option generation and option evaluation separate. |
| Omitting the null option silently | It biases toward action when inaction may be the right choice. | Always include it and explain non-viability explicitly if needed. |
| Hiding uncertainty behind confidence | It erodes trust and makes trade-offs invisible. | Use the readiness signal honestly and name what could still change the outcome. |
| Reusing generic criteria | It produces shallow advice that misses the actual decision. | Derive criteria from the user's constraints, goals, and failure modes. |
| Inventing fake options for symmetry | It creates noise and weakens the ranking. | Say when only one serious option exists. Do not pad the list. |

## Example

**User:** "I need to add search to my documentation site. What should I use?"

> **1. Decision:** Which search implementation should a documentation site use? (Technical selection)
>
> **2. Stakes:** **Low**. Search is additive and reversible, and the blast radius is mostly limited to search UX. Skipping Information Gaps and Sensitivity Analysis.
>
> **3. Options:**
> - Algolia DocSearch
> - Pagefind
> - A built-in framework search feature, if the docs framework has one
> - Elasticsearch
> - **Null:** no search
>
> **5. Evaluate options:**
> - **Algolia DocSearch:** Strong hosted relevance and typo handling. Weak vendor dependency and approval requirements. Best when the site is public, content is stable, and managed search is worth the dependency.
> - **Pagefind:** Strong simplicity, zero backend, and static-site fit. Weak typo tolerance and fewer advanced ranking controls. Best when the docs site is static and operational simplicity matters.
> - **Framework search:** Strongest setup speed when the framework already ships a credible search layer. Weak feature depth. Best when search is useful but not product-critical.
> - **Elasticsearch:** Strongest flexibility. Weak operational cost and clear overkill for most docs sites. Best when search requirements already look like a product in their own right.
> - **Null:** Strong zero effort and zero maintenance. Weak discoverability. Best when the documentation is small enough to browse easily.
>
> **7. Ranked options:**
> 1. **Pagefind** - best simplicity-to-power ratio for a typical static docs site
> 2. **Framework search** - even simpler if it already exists, but usually less capable
> 3. **Algolia DocSearch** - stronger search quality, but at the cost of an external dependency
> 4. **Null** - viable only when the docs are small
> 5. **Elasticsearch** - most powerful, but operationally disproportionate here
>
> **8. Recommendation:** Use Pagefind unless the framework already includes a search feature that is good enough for the audience. It gives strong docs-scale search with almost no operational burden.
>
> **9. Readiness:** `best available`. Confirming the docs framework, expected content volume, and need for typo tolerance could still change the ranking.
