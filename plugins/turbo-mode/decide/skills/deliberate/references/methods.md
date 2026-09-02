# deliberate — the Prune and Contest methods

The only two methods `deliberate` owns; every other stage reads and executes a live constituent contract. The marker-wrapped texts below are behavior surfaces: the helper extracts them verbatim as the `method` packet item for Prune's and Contest's briefs, and they are part of the run's method identity — editing them changes the skill's behavior and, mid-run, is `method drift`.

Reload point: the orchestrator re-reads this file at the Prune and Contest stage boundaries.

## Prune

<!-- method:prune -->
You narrow the field decisively under delegated authority, in the labeled-lean form: cuts by confirmed filters, fact-established judgments, and disclosed judgment cuts — never scores or invented weights. Your packet is candidate-attached-lean-blind and value-aware: no authority note or soft preference reaches you, while stated values do, because the value-trade guard cannot tell a resolved trade from an unresolved one without them. Cuts must be defensible without knowing which candidate the user favors — never without the user's stated exchange rates.

**Independent cuts** — permitted regardless of budget — are exactly:

- Applications of echoed price-confirmed constraints (predicate application recorded as agent judgment).
- **Fact-established** mechanism-equivalence: a nameable shared failure reason. When equivalence holds between a user-supplied seed and a generated option, the generated option is the one cut — the seed's original wording is what the downstream authority packet preserves.
- **Fact-established** dominance at comparable resolution.

A contestable sketch-depth dominance impression never triggers a cut by itself — it may appear only as the disclosed rationale inside a budget-forced cut. There is no "retired non-serious" class: options that read as non-serious at sketch depth are exactly where anti-modal kills would launder, so they die only as fully recorded judgment cuts.

**Budget cuts**, when survivors still exceed the budget, carry two guards:

- **The value-trade guard:** each cut must be defensible without pricing an unresolved value trade. When the budget cannot be met without pricing one, do not invent the weight and do not die: **overflow the budget with disclosure** — carry the un-cuttable survivors forward so the trade can be posed priced — up to twice the echoed budget (a correctable default). Beyond that, exit with the honest terminal `survivor budget cannot be met without an unstated value trade`. Value boundary outranks capacity preference; the budget was explicitly capacity, not epistemics.
- **Honest disclosure wording:** every budget cut is disclosed as a low-confidence cut of a **distinct mechanism-level candidate whose seriousness was unresolved at sketch depth** — never "a distinct serious bet," which claims what sketch depth cannot establish.

**Floor of two:** only a cut whose predicate source is a direct user rule *and* whose epistemic status is fact-established may reduce the field below two; budget cuts never may.

**Order invariant:** survivors are an order-preserving subsequence of the input field — you cut, never reorder — and validation enforces the subsequence check mechanically.

**Seed protection** runs on the field's provenance flags, which carry identity, not preference: a user-supplied seed dies only on your ledger, by a recorded cut — anything else is the silent option-collision resolution the authority grant forbids.

Every exclusion is a compact labeled record — prose inside each value, the `evidence-provenance` and `evidence-warning` lines omitted when inapplicable, no scores:

```text
Option:                <complete original wording, provenance flag intact — validation rejects paraphrase>
Status:                active
Delegation:            <what the invocation authorized here>
Predicate source:      <direct user rule | agent-derived proposition>
Cut basis:             <constraint | equivalence | dominance | survivor budget>
Epistemic status:      <fact-established at comparable resolution | contestable sketch-depth judgment>
Reason:
Evidence provenance:   <source and retrieval time for each external fact the reason or epistemic status relies on>
Load-bearing premise:
Strongest case:        <written before the kill>
Revive if:
Evidence warning:
```

A budget cut the value-trade guard blocks is not an exclusion and never takes this shape: it is a **blocked-cut disclosure** — the candidate, the unpriced trade, why the cut was blocked — a separate artifact riding with the overflow disclosure, outside the ledger, because nothing was excluded.
<!-- /method:prune -->

Recommend's disposition records use the same template with the post-prune and rival cut bases (`post-prune filter`, `post-prune dominance`, `post-prune collapse`, `only-serious-option rival` — the last covers the rivals an `only one serious option` close sets aside); `Delegation` still names what the invocation authorized there, and `Revive if` is still mandatory. That instruction reaches Recommend through its brief's obliged-artifact shape, not through this method text.

## Contest

<!-- method:contest -->
You test the run's exclusions against the recommendation's actual logic — or, on a close-less terminal, against the `terminal-claim` your packet carries. Detection only: you identify, you never adjudicate, revive, or recommend.

- Identify every recorded exclusion premise or revival condition that the final logic or terminal claim makes live: a kill whose load-bearing premise the close also leans on, a revival condition the close's own reasoning satisfies or nearly satisfies, an exclusion whose stated reason the comparison surface undermines.
- On zero survivors: test whether any recorded premise being wrong would revive a candidate. On one survivor: test whether one would restore a rival to the named survivor.
- **An excluded candidate carrying a visible user preference is always a live challenge**, whether or not its kill premise is load-bearing in the final logic.
- Never compare unshaped exclusions to shaped survivors — an excluded option was never developed, and depth asymmetry is not evidence. Never substitute a recommendation.
- Whenever any live challenge exists, name the one most worth contesting.

Return exactly one exclusion-check line as your obliged artifact:

- `Exclusion check: no live recorded challenge found`
- `Exclusion check: live recorded challenges — <X, Y>, most worth contesting: <one>`
- `Exclusion check: not applicable — no exclusions recorded`
<!-- /method:contest -->
