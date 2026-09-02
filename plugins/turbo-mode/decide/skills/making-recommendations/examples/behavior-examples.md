# Recommendation Behavior Examples

Use these examples to calibrate routing, door depth, lean handling, exits, and close shape. They are illustrative, not templates.

## Clear Call

User asks:

```markdown
Should we keep the current Markdown parser or switch to `markdown-it` for this
small docs tool?
```

Expected behavior:

- Treat this as a recommendation request between two serious options; add the null option only if it is distinct from "keep the current parser."
- No filter applies and neither option dominates, so compare in words on what matters: maintenance burden, plugin support, compatibility, migration cost.
- If the trades point one way across any reasonable weighing, close `clear call` with the pick, the case against the loser, and what would flip it.
- Name unverified package-state facts (release cadence, open CVEs) as gaps in `What Would Flip It` rather than pretending they were checked.

## The Ranking Flips on a Values Trade

User asks:

```markdown
Should we use Postgres, MySQL, or SQLite for this new multi-tenant SaaS app?
Weigh cost, our team's ops familiarity, and scaling headroom.
```

Expected behavior:

- Compare criterion by criterion across all three options so no cell is skipped — cost for all three, then ops familiarity for all three, then scaling headroom for all three.
- With three criteria in play, lay the comparative facts out as a table — cells like "wash between Postgres and MySQL; SQLite far cheaper until concurrent writes arrive," never numeric scores, and no weighted total anywhere.
- Notice the outcome flips on an exchange rate: how much early scaling headroom the team's familiarity is worth. That is the user's values, not evidence.
- Close `conditional call` or `your call` with the trade posed priced: "if you would trade early headroom for shipping speed on familiar tooling, take X; if headroom rules, take Y" — adding which way you lean, labeled as a lean.
- Do not invent a weighting, announce it, and rank anyway.

## Two-Way Door

User asks:

```markdown
New repo, three people, no monorepo: npm or pnpm?
```

Expected behavior:

- Recognize a cheap, reversible choice: switching later is an afternoon.
- Recommend fast in a few sentences and say why fast is right — no table, no packet, no manufactured deliberation.
- Do not run the full close on a decision whose analysis would cost more than the mistake it prevents.

## Check First

User asks:

```markdown
Should we switch our docs search to the managed vector index, or keep the
current keyword index? Relevance complaints are up.
```

Expected behavior:

- Notice the deciding fact is cheaply measurable: an offline relevance comparison over real logged queries settles what argument can only estimate.
- Close `check first`: recommend the eval, with both branches stated — "if the vector index clearly wins on your real queries, switch; if it is a wash, the switch buys ops cost for nothing."
- Do not deliver a verdict from guesses when an afternoon of evidence is available.

## The User Is Leaning

User asks:

```markdown
I'm honestly pretty excited to move our docs off Docusaurus to a custom
Next.js site — the current thing feels clunky and I want the flexibility.
It'd take me about three weekends. The docs get maybe 200 visits a month,
mostly API reference lookups, and search works fine today. Should I do it?
```

Expected behavior:

- Register the visible lean (excitement, "clunky," flexibility framing) before comparing.
- Notice the stated facts land against the rewrite: low traffic, lookup-shaped usage, working search, three weekends of cost.
- Deliver the contrary call plainly — do not soften it into "either could work" because the user sounds invested.
- Price what would have to be true for the rewrite to win (docs becoming a product surface, concrete customization the current tool blocks) so the disagreement is contestable, not dismissive.

## One-Way Door With Unknowns

User asks:

```markdown
Should we migrate the production billing database this weekend or wait for the
next release window?
```

Expected behavior:

- Treat this as a one-way door: reversal is costly and the blast radius is broad. Read `references/high-stakes.md`; the close includes `Commitment Point` and `Rollback / Blast Radius`.
- If the load-bearing safety facts — backup validation, rollback rehearsal — are unconfirmed, the cheapest checks are the call: close `check first` on confirming them before any date is chosen.
- If the safety facts are known and the answer is controlled by appetite for weekend risk versus schedule pressure, close `your call` with both branches priced.
- Never silently drop the risk beats to keep the answer short; compress them into prose if asked for brevity.

## Only One Serious Option

User asks:

```markdown
Should we keep the current local-only workflow, or add a network service, if
the tool must keep working fully offline?
```

Expected behavior:

- Test the "must" once — is offline a confirmed constraint at its price, or a preference? — then apply it as a filter.
- With the constraint confirmed, the network service fails the gate: exit `only one serious option`, recommend the local-only workflow plainly, and say why the rival is not serious.
- Do not invent a weak third option to make the choice look deliberated; name the check that could surface a real second option (for example, whether a local-first sync layer meets the offline bar).

## Not Comparable

User asks:

```markdown
Should we optimize the docs site for polished marketing pages or for dense API
reference lookup?
```

Expected behavior:

- Do not rank options that optimize for different outcomes as if they shared one success criterion.
- Exit `options not comparable`: state the mismatch and ask which outcome the current decision is actually about — conversion, developer speed, support load.
- Stop; no partial ranking.

## Proceed on Stated Assumptions

User asks:

```markdown
We can only ship ONE of these two features this sprint, not both — should we
build the CSV export or the bulk-delete feature?
```

Expected behavior:

- Notice a defensible comparison exists in words even though the deciding business fact (which feature users need most right now) is missing: build effort, risk shape (bulk-delete is destructive and needs confirmation/undo/audit work; CSV export is additive and self-contained), failure severity.
- Do not exit `no basis yet` over one missing fact; state the assumption up front and compare on what is known.
- Close `conditional call` or `your call` — "if demand is roughly even, the export ships more value at less risk; bulk-delete wins only if it is the thing users are blocked on" — with the missing fact in `What Would Flip It`.

## Thin Field

User asks:

```markdown
CI is flaky. Should we auto-retry every failed test three times, or just delete
the flaky tests?
```

Expected behavior:

- Notice both named options are weak: blanket retries mask real failures, deletion buys silence with coverage. Ranking them would crown a weak winner.
- Say that plainly, name `ideate` (or the owning fix lane, such as `diagnose` for the flakiness itself) to widen the field, and ask before switching.
- Do not produce a ranking whose winner you would argue against if the user proposed it alone.

## Muddy Design Request

User asks:

```markdown
What's the best way to build a collaboration dashboard?
```

Expected behavior:

- Do not force a recommendation from this prompt; there are no serious options on the table yet.
- Name `outcome-shaping` if the desired outcome is unclear, or `design-exploration` if the outcome is clear but approaches need shaping; say why, ask before switching, and stop.
- Return here only once there are serious approaches to compare, such as server-rendered dashboard versus client-heavy dashboard versus embedded analytics.

## Descope Misread as Ranking

User asks:

```markdown
We're not going to hit the deadline with everything in this release. What
should we cut?
```

Expected behavior:

- Recognize this is not a pick-one choice among rivals — every feature is a candidate for keep, defer, or cut against the deadline, and more than one can survive.
- Name `scope-cut` as the owning lane: it partitions one scope under a binding constraint and preserves every cut item with a re-entry condition. Ask before switching, then stop.
- Use this lane instead only if the real ask is one slot with genuine rivals ("cut feature A or feature B, not both").
