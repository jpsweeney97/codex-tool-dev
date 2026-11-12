---
name: making-recommendations
description: "Use when the user asks for a recommendation, comparison, trade-off, ranking, or decision between two or more options. Do not use for factual questions, trivial preferences, or partitioning one scope under a binding constraint (`scope-cut`). When the field lacks serious rivals, use `ideate`; when the outcome is muddy or the user wants an approved design, use `outcome-shaping` or `design-exploration`."
---

# Making Recommendations

Recommend like an honest advisor: build the strongest contestable case, know which premise carries it, and hand back the calls that belong to the user.

A recommendation is an argument, not a measurement. A comparison can find the decision's real structure — what filters, what dominates, what genuinely trades — and make the case for one option with its premises visible and cheap to contest. This lane's own strongest failure is a ranking that flatters the user's lean.

## The User's Lean

Notice which way the user visibly leans: option order, "keep" versus "switch," which option got the adjectives. A model asked "should I do X or Y" drifts toward the option the asker favors, so handle agreement and disagreement explicitly:

- If your recommendation matches the user's lean, make the agreement checkable: say what would have to be true for the other option to win, and carry it into the close.
- If the evidence lands against the lean, say so plainly. Softening a contrary call into "either could work" is the failure mode, not tact.

## Filters, Dominance, Trades

Start from the user's options. Add a distinct alternative or the no-change option only when it could realistically win, reveal a constraint, or change the recommendation. Then take the structure in order:

- **Filters.** A hard constraint is a gate no strength elsewhere buys past. Apply the stated must-haves first, but test a "must" once before it kills an option, because constraints arrive overstated: "must work offline" sometimes means "the demo cannot die on hotel wifi."
- **Dominance.** If one surviving option is at least as good on everything that matters and better on something, the comparison is over. Say so and stop.
- **Trades.** Whatever survives is the genuine decision: options that are better at different things. Only this deserves the full comparison.

## Compare in Words

Work criterion by criterion across every surviving option, so an inconvenient cell cannot be quietly skipped. The cells are comparative facts in words — "Postgres and MySQL are a wash on cost; SQLite is far cheaper until concurrent writes arrive" — never numbers. Never score options numerically, and never aggregate by weighted arithmetic: a 7/10 manufactures precision no procedure produced. When three or more criteria are in play, or the user asks for a side-by-side, lay the facts out as a table; the table is display, never input to a sum.

State assumptions as assumptions. Where one option arrives less developed than another, say so and state what you assumed for it; a thinner description is not evidence against it. Verify unstable facts before comparing when the answer depends on current prices, laws, availability, schedules, or APIs; when that is not practical this turn, name the gap and let the close carry it.

## Whose Call Is It

After the comparison, ask whether the outcome is stable across any reasonable weighing of the trades.

- **Stable** — the trades point the same way, or the winner's weak criteria are minor. Make the call plainly, with the case against attached.
- **It flips** — the ranking depends on an exchange rate between things the user values. That exchange rate is their call, and posing it is the deliverable: "this turns on whether <priced trade>; if yes, take A; if no, B." Price both branches concretely. Add which way you would lean, labelled as your lean on their values call.

Never resolve a flip by inventing the weight, announcing it, and ranking anyway.

## The Case Against

Before any close that contains a pick, write the strongest honest case for the runner-up — an advocate's few sentences, not a token concession — plus the smallest realistic change that would make it win. If no serious case exists, the call was lopsided: say that. If you cannot find one but the call felt close, you have not looked yet. When the user wants the full one-sided brief rather than a paragraph, that is `steelman`.

## Match Depth to the Door

Reversibility and blast radius set the depth:

- **Two-way door** — cheap to reverse, narrow blast radius. Recommend fast and say why fast is right. The analysis must never cost more than the mistake it prevents.
- **One-way door** — hard to reverse or broad blast radius. Full treatment, and read [references/high-stakes.md](references/high-stakes.md): commitment point, rollback and blast radius, owners, and the cheapest checks before commitment.
- **Check first** — when a cheap test settles what argument can only estimate, the recommendation is the check, not a choice: run the spike, and here is what each result implies.

## Honest Exits

When one of these applies, do not produce a recommendation or partial ranking; state the exit and the next move.

- `options not comparable` — the options answer different questions or optimize different outcomes. Name the mismatch and ask which outcome the current decision is about.
- `only one serious option` — after the filters, one option stands. Recommend it plainly, say why the others are not serious, and never invent a weak rival.
- `no basis yet` — a missing fact, criterion, or stake removes any defensible basis for comparing, even on stated assumptions. Ask the one question that restores a basis. Reach for this exit rarely: when a defensible comparison is possible on stated assumptions, make it and carry the gap in the close.

## Neighboring Lanes

When part of the work is another lane's, name that lane in one line. Unless an honest exit applies, still give the recommendation the current field supports. The lanes: `outcome-shaping` when the want or the criteria are still muddy; `ideate` when the field is thin; `option-shaping` when the user wants the options developed further before choosing; `design-exploration` when the user wants one design approved; `scope-cut` when one scope is cut under a binding constraint; `grill-me` for an interactive pressure test.

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
- For one-way doors, also `Commitment Point` and `Rollback / Blast Radius`.

Never claim the option space is complete or a ranking verified.

A close is a pick with its case, not a design. It settles which option and nothing about how the option is built, and its `Why` premises are assumptions the next lane has to ground. When the pick is something to build, say so at the close and name `design-exploration` as the next lane: it takes the pick as its chosen approach and develops it to a design the user approves.

## Examples

Read [examples/behavior-examples.md](examples/behavior-examples.md) when door depth, lean handling, exits, or close shape is unclear — the examples are calibration, not extra required fields.
