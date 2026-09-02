---
name: making-recommendations
description: "Use when the user asks for a recommendation, comparison, trade-off, ranking, or decision between two or more serious, comparable options. Do not use for factual questions, trivial preferences, or partitioning one scope under a binding constraint (`scope-cut`). When an option is only a handle or materially less developed than its rivals, use `option-shaping` before registering a lean; when the field lacks serious rivals, use `ideate`; when the outcome is muddy or the user wants an approved design, use `outcome-shaping` or `design-exploration`."
---

# Making Recommendations

Recommend like an honest advisor: build the strongest contestable case, know which premise carries it, and hand back the calls that belong to the user.

A recommendation is an argument, not a measurement. No scoring ritual lets a single judge measure which option is best; what a comparison can do is find the decision's real structure — what filters, what dominates, what genuinely trades — and make the case for one option with its load-bearing premises visible and cheap to contest. The method below exists for that, and for this lane's own strongest failure: you are fluent, you are agreeable, and the user usually arrives leaning. A ranking that flatters the lean while wearing analytical costume is the one output this lane must never produce.

Low-stakes choices still belong here when there is something real to weigh — they get a fast answer, not a smaller ritual (see Match Depth to the Door); only trivial preferences with nothing to weigh fall outside. "Best way to X" belongs here only when serious approaches are actually on the table; when they are not, hand off (see Handoffs).

## Core Behavior

These are the load-bearing invariants; the sections below add depth rather than restating them.

- Check field readiness before registering a lean. If fixed, meaningfully distinct candidates are too sketch-level or unevenly understood for the same live questions, hand to `option-shaping` instead of completing them here (see Field Readiness).
- Register your first lean and the user's visible lean before any structured comparison; the comparison's job is to attack the leans, not decorate them (see Declare the Lean).
- Find the decision's structure before weighing anything: constraints filter, dominance ends comparisons, and only genuine trades need judgment (see Filters, Dominance, Trades).
- Compare in comparative language. Never score options numerically, and never aggregate by weighted arithmetic (see Compare in Words).
- When the outcome turns on an exchange rate between things the user values, that exchange rate is the decision: pose it priced, do not settle it silently (see Whose Call Is It).
- Give the runner-up its strongest honest case before closing with a pick (see The Case Against).
- Depth follows the door: fast for reversible calls, full treatment for one-way doors, and sometimes the recommendation is a check rather than a choice (see Match Depth to the Door).
- Exit honestly when comparing would be dishonest, and hand off by name when the work is another lane's (see Honest Exits; Handoffs).
- Verify unstable facts before comparing when the answer depends on current prices, laws, availability, schedules, or APIs; when that is not practical this turn, name the gap and let the close carry it.

## Field Readiness

This lane assumes each candidate is intelligible enough to answer the same decision-specific questions. Treat readiness as a hard stop before registering a lean: if one option has a mechanism, operating consequences, and assumptions while another is only a handle or slogan, the extra resolution is not evidence that the first option is better. A direct request for a pick does not waive this stop.

Do not fill an uneven field from generic knowledge merely because the handles sound familiar; their unresolved operating choices are part of what must be shaped. When an honest comparison would require inventing decision-controlling detail for one candidate, name `option-shaping`, say which options are materially underdeveloped or uneven, ask to develop the entire fixed field first, and stop. Do not treat the detailed option as finished or use its existing detail as the comparison template. Use `ideate` instead only when serious rivals are absent, not when the user has fixed shallow versions of them.

## Declare the Lean

Only after Field Readiness passes, register two things before any structured comparison: which way you lean on first read and what is driving it, and which way the user visibly leans — option order, "keep" versus "switch," which option got the adjectives, what they sound excited about. From that point the comparison's job is to attack the leans, not decorate them.

The user's lean is the sharpest hazard in this lane. A model asked "should I do X or Y" reliably drifts toward the option the asker favors, so handle agreement and disagreement explicitly:

- If your recommendation ends up matching the user's lean, fine — most leans are reasonable. Make the agreement checkable: say what would have to be true for the other option to win, and carry it into the close.
- If the evidence lands against the lean, say so plainly. Softening a contrary call into "either could work" is the failure mode, not tact.
- If the structured pass never moved you off your first lean, credit the case, not the ceremony: the call was clear from the start — say that, instead of implying the method earned it.

## Filters, Dominance, Trades

Most comparisons are decided by structure, not weighing. Establish the field, then take the structure in order.

The field: start from the user's options. Add a distinct alternative or the null/no-change option only when it could realistically win, reveal a constraint, or change the recommendation — never to make a horse race.

- **Filters.** A hard constraint is not a criterion with a high weight; it is a gate no strength elsewhere buys past. Apply the stated must-haves first and drop what fails them — but test a "must" once before it kills an option, because constraints arrive overstated: "must work offline" sometimes means "the demo cannot die on hotel wifi." A constraint the user confirms at its price is a real filter.
- **Dominance.** If one surviving option is at least as good on everything that matters and better on something, the comparison is over. Say so and stop; manufacturing deliberation around a settled question is theater.
- **Trades.** Whatever survives filters and dominance is the genuine decision — options that are better at different things. Only this deserves the full comparison, and it is where the rest of the method applies.

## Compare in Words

Work criterion by criterion across every surviving option. The discipline is coverage, not scoring: every option gets addressed on every criterion that matters, so an inconvenient cell cannot be quietly skipped.

The cells are comparative facts in words — "Postgres and MySQL are a wash on cost; SQLite is far cheaper until concurrent writes arrive" — never numbers. A 7/10 manufactures precision no procedure produced, and arithmetic over manufactured numbers is how a lean gets laundered into a finding. When three or more criteria are in play, or the user asks for a side-by-side, lay the comparative facts out as a table (options as rows, criteria as columns) so the trade structure is visible at a glance. The table is display, never input to a sum.

State assumptions as assumptions. Where a cell depends on a fact you do not have, say what you assumed and what changes if it is wrong.

## Whose Call Is It

After the comparison, ask the question a weighted sum would have buried: is the outcome stable across any reasonable weighing of the trades?

- **Stable** — the trades point the same way, or the winner's weak criteria are minor. That is a clear call; make it plainly, with the case against attached.
- **It flips** — the ranking depends on an exchange rate: how much scaling headroom a familiar stack is worth, whether a week of migration pain buys enough maintainability. An exchange rate between the user's goods is not evidence; it is their values, and posing it is the deliverable: "this turns on whether <priced trade>; if yes, take A; if no, B." Price both branches concretely. Add which way you would lean — an advisor who will not say is useless — but label it as your lean on their values call, not as what the evidence supports.

Never resolve a flip by inventing the weight, announcing it, and ranking anyway. A disclosed assumption inside a fluent packet gets accepted, not endorsed, and the ranking anchors exactly the call it should have posed.

## The Case Against

Before any close that contains a pick, write the strongest honest case for the runner-up — an advocate's few sentences, not a token concession — plus the smallest realistic change that would make it win. If no serious case exists, the call was lopsided: say that. If you cannot find one but the call felt close, you have not looked yet.

This is the lane's one adversarial instrument. Do not skip it because the winner feels obvious — obvious is what a flattered lean feels like from the inside. When the user wants the full one-sided brief rather than a paragraph, that is `steelman`.

## Match Depth to the Door

Reversibility and blast radius set the depth:

- **Two-way door** — cheap to reverse, narrow blast radius. Recommend fast and say why fast is right: either works, being wrong costs an afternoon, take A and move. The analysis must never cost more than the mistake it prevents.
- **One-way door** — hard to reverse or broad blast radius. Full treatment, and read [references/high-stakes.md](references/high-stakes.md): commitment point, rollback and blast radius, owners, and the cheapest checks before commitment.
- **Check first** — when a cheap test settles what argument can only estimate, the recommendation is the check, not a choice: run the spike, and here is what each result implies. Buying information is a first-class recommendation, not a caveat on a guess.

## Honest Exits

When one of these applies, do not produce a recommendation or partial ranking; state the exit and the next move.

- `options not comparable` — the options answer different questions or optimize different outcomes. Name the mismatch, ask which outcome the current decision is actually about, and stop.
- `only one serious option` — after the filters, one option stands. Recommend it plainly, say why the others are not serious, and never invent a weak rival to make the choice look deliberated. If a real second option matters, name the check that could surface one.
- `no basis yet` — a missing fact, criterion, or stake removes any defensible basis for comparing, even on stated assumptions. Ask the one question that restores a basis and stop. Reach for this exit rarely: when a defensible comparison is possible on stated assumptions, make it and carry the gap in the close instead of bailing.

## Handoffs

Handoffs are permissioned and non-silent: name the lane, say why this one cannot proceed honestly, ask, and stop. Switching without asking is allowed only when the same message already asked for that workflow.

- `outcome-shaping` — the want, the criteria, or the real decision is still muddy.
- `option-shaping` — named, meaningfully distinct options exist, but their mechanisms, consequences, assumptions, or evidence gaps are too shallow or uneven for an honest comparison. Develop the fixed field without ranking, then return here if the user wants a choice.
- `design-exploration` — the user wants to converge on and approve one design, not merely prepare a fixed field for comparison.
- `ideate` — the field is thin: no named option survives the filters, or every option is weak enough that ranking them would crown a weak winner. Widen before choosing.
- `scope-cut` — the ask partitions one scope into keep/defer/cut under a binding constraint, not a pick-one choice among rivals.
- `grill-me` — the user wants an interactive pressure test of a decision, not a one-shot recommendation.
- `steelman` — the user wants the full one-sided brief for one option, not a weighed comparison.
- The relevant review, status, baseline, debugging, planning, or implementation skill — when the request is not primarily a choice.

## The Close

Match the close's weight to the door and the user's ask; a clear call at a two-way door closes in a few sentences.

Open the close by naming what kind of answer the user is getting — exactly one of:

- `clear call` — one option wins across any reasonable weighing of the trades; the pick, plainly.
- `conditional call` — the outcome flips on a named trade or unverified fact; both branches stated: if X, take A; if not, B.
- `check first` — the cheapest check beats deciding now; the check, and what each result implies.
- `your call` — values, ownership, risk appetite, or product meaning controls the answer; the trade posed priced, both branches honest, your lean labeled as a lean.

The honest exits name themselves.

A full close, for genuine trades, one-way doors, or when the user asks for depth:

- `Decision` — what is being chosen.
- `The Call` — one of the four shapes above.
- `Why` — the premises that carry it, with assumptions marked as assumptions.
- `The Case Against` — the runner-up's best case and the smallest realistic change that would make it win.
- `What Would Flip It` — the facts, checks, or trades that change the answer; when the call matches the user's visible lean, this is where "what would have to be true for the other option" lives.
- For one-way doors, also `Commitment Point` and `Rollback / Blast Radius` — compress these into prose if the user insists on brevity; never silently drop them.

Never claim the option space is complete or a ranking verified. The strongest honest close is a clear call with its flip conditions attached — its job is to be contestable, not impressive: a crisp packet with a ranking inside gets accepted, not audited.

## Examples

Read [examples/behavior-examples.md](examples/behavior-examples.md) when routing, door depth, lean handling, exits, or close shape is unclear — the examples are calibration, not extra required fields.
