# Outcome Shaping Interaction Examples

Use these to calibrate behavior, not to add required fields to the main skill contract.

## Ambition Register (no transposition)

User: "I want my static-site generator to be the fastest one in the Rust ecosystem. Help me figure out what I actually want here."

Avoid (vigilance transposition):

```markdown
My read so far: You want users to stop worrying about build times.
```

Prefer:

```markdown
My read so far: You want to win — "fastest in the Rust ecosystem" sounds like a
benchmark crown, not a user complaint you're fixing. The part I'm not sure of:
fastest on whose measurement — a published benchmark others cite, or the feel of
a rebuild while someone is editing?
```

The want lives in ambition; keep it there unless the user moves it.

## Mud Re-Type (route to evidence)

User: "I can't decide what I want the plugin API to feel like."

After two turns of guessed-at answers:

```markdown
My read keeps moving because I think neither of us knows yet — this feels like a
question about how the API behaves in someone's hands, not one more question I
should ask you. Want to sketch a throwaway plugin against two candidate shapes
and see which one you hate? That's `prototype`'s lane.
```

Confident-sounding answers that keep dying under follow-ups are missing-information mud wearing missing-words clothing.

## Rival Reads Held (colliding wants)

```markdown
My read so far is two reads: You want the rewrite because the current code
offends you, and rewriting it is the version of this project you'd enjoy. You
also want to ship in March, and the rewrite probably eats March. Those collide
head-on. Which one is allowed to win?
```

Hold both until the user resolves the collision; do not merge them into one tidy sentence.

## Priced Trade

```markdown
My read so far: You want reviewers to trust the checks enough to skip re-reading
diffs. A trade to test it: if getting there costs a quarter of the CI budget and
two weeks of tuning, still worth it? If not, we've found the real bar — how much
trust is worth buying.
```

## Fixed Constraint, Remaining Flexibility

User: "The contract deadline is Friday. It cannot move. I need to work out what a responsible release looks like."

```markdown
My read so far: Friday is fixed; I won't ask whether missing it is worth the
trade. What can still move is scope against confidence. If the full scope means
only a cursory verification pass, would you rather cut scope or accept that
level of confidence?
```

Preserve the constraint the user declared fixed. Price the remaining flexibility rather than asking them to trade away the obligation.

## Testimony, Named Once

```markdown
You've said latency is secondary. The last month of merges says otherwise —
three of your five PRs were latency work. I'll name that once and leave it with
you: which one is the real priority?
```

One naming, then defer. Sustained pressure belongs in `grill-me`.

## Own-Words Close

```markdown
Before I call this settled — say back what we've landed on, in your words? If it
comes out different from my version, yours wins.
```

User: "I want cutting a release to be so boring I'd do it on a Friday."

That sentence — theirs, not yours — is the settled shape, and it goes into the capsule verbatim.

When the restatement adds something the read never held, the new part is unpriced. User: "I want releases boring enough for a Friday — and I want a new hire to be able to run one without me."

```markdown
The Friday part is what we priced. "Without me" is new — that's a runbook and
onboarding on top of the release work. Still worth it if it adds a week? If
yes, both go into the capsule as settled; if not, the new part rides along
marked unpriced.
```

Price the new part once; do not let a restatement carry unpriced content downstream as settled.

## Dissolution (success)

```markdown
My read so far: The dashboard was a way to feel in control of the migration, and
you just said the migration finishes next week. It sounds like the want
dissolved — nothing needs building. Want to leave it there?
```

Close warmly; do not manufacture a consolation deliverable.

## Flight Named Once

User, immediately after a hard trade question: "You know what, this is fine, just recommend something."

```markdown
Happy to — noting once that we're stopping at exactly the spot where it got
uncomfortable: whether craft-joy or the March date wins. That's the trade we
never priced, so my answer is the question, not a pick: if the rewrite costs
March and most of April, still worth it? My lean is ship in March and rewrite
after — and it's a lean, yours to overrule.
```

Name it once, gently, then comply — in place, as the priced values question with a labeled lean, never a pick. Routing an unpriced collision to `making-recommendations` only gets it bounced back.

## Anti-Patterns

- Transposing registers: rendering "fastest in its class" as "users stop worrying about latency" — a different want in your vocabulary.
- Assent-chaining: "Is that right?" → "yes" → "Is that right?" → "yes" — collecting agreement with your prose instead of the user's restatement.
- Trade-free utopia: a "settled" want that was never priced — "everything double-checked automatically" survives no honest trade.
- The ledger: "Decided X / Decided Y / Decided Z" — the read is one rewritten synthesis, never an accumulating log.
- Capture by fluency: a gorgeous read the user rubber-stamps. If your reads keep getting instant yeses, get suspicious, not proud.
