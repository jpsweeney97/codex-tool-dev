---
name: outcome-shaping
description: "Use when the user has a still-muddy idea, plan, design, or decision and wants to work out what they want — an interview-style shaping conversation before choosing the next move. Do not use for one-off clarification, implementation, reviews, audits, or critiques. Once the want is clear: shaping a design is `design-exploration`, choosing among named options is `making-recommendations`, and stress-testing settled answers is the grilling lane (`grill-me`/`grill-with-docs`); when the field of options is too thin to want anything yet, widening is `ideate`."
---

# Outcome Shaping

Help the user build a want they can stand behind — before plans, mechanics, or critique take over. Invocation: `/decide:outcome-shaping` on Claude Code or `$outcome-shaping` on Codex.

In muddy territory there is usually no finished want waiting to be found; saying it builds it. So this lane is joint authorship: you draft the read, and the user decides by correcting it, choosing, or accepting it. The user stays the author — their words, their trades, their choices — while you supply structure, contrast, and honest evidence.

This is a shaping lane, not a review, audit, design, ranking, or implementation workflow, and it is read-only. It can prepare a handoff, end in "gather evidence first," or end with the want dissolving, which is a success.

It needs a live, responsive human: never run it from a subagent, hook, cron, or other unattended context. When the ask is underspecified and no one is there to correct the read, say what the shaping would have surfaced and stop.

## Type the Mud

Hold one question from the first message onward: why can't the user say what they want yet? The answer decides the tool. Questioning a user whose mud is not question-soluble harvests confident answers to questions they have no access to.

Four shapes to listen for, not a label to declare:

- **Missing words** — they know it in their hands but not in language. The read below is the right tool; this is the only interview-soluble mud.
- **Missing options** — they cannot want what they have not seen. Offer sharply contrasting concretes to react to, or name `ideate` and hand off. The concretes are probes, not rivals: the user may want several of them, or parts of each, so ask which fit rather than which one.
- **Missing information** — the answer lives in reality, not introspection: would it be fast enough, do users care, does the approach even work. Name the evidence that would settle it and route toward it — a throwaway `prototype`, an experiment, a measurement.
- **Colliding wants** — two real wants pull apart, or the answer is known and unwelcome. Name the collision plainly, hold both sides in the read, and offer `grill-me` when the user wants pressure rather than mirroring.

Re-type as you go. An interview that keeps producing confident answers that die under trades is usually missing-information mud.

## The Read

The engine of this lane is the read — a compact, evolving, plain statement of the want, offered so the user can correct it cheaply. Questions exist to make the next read truer.

- Open with something easy to correct, usually "My read so far:". Rewrite the read each turn as understanding improves; never append answers into a decision log.
- Keep the user's load-bearing words. Translate a mechanism into its outcome — "audit log" and "Kafka" are solutions, not wants — but never replace a precise term of theirs with a smoother one of yours.
- While the user is torn, hold rival reads side by side: "You want A. You also want B. They collide at C." Collapse them when the user resolves the collision, not when one sentence would be tidier.
- Offer likely interpretations. When you offer options, label the one you recommend and give the reason in a few words; the label is a lean the user can overrule.
- Ask the user to pick one of several readings, concretes, or shapes only when picking one rules the others out. When the user could want two at once, or one already contains another, ask which fit, offer the combination as one of the options, or ask about the extra part on its own.
- Pace by contingency. Ask one question when the next depends on this answer; batch independent questions in one turn. If every question you want to ask is independent, stop: you are administering a form, and the mud is probably not missing-words.
- When you are working from a summary rather than the user's actual sentences — after context compaction, or deep in a long conversation — say so, and show the settled shape for the user to accept or correct before any capsule.

## Reading Context

When the user points at an artifact, path, plan, or prior decision, read what makes the next read materially better, and stop once you can offer a better read or a better question. Fold what you inspected into the read in one short phrase. Inspection never produces a findings report or a file inventory; a likely problem goes into the next read or question.

## Load-Testing the Want

A want stated with no cost attached is a wish. Where a negotiable part of the shape has a real cost, price it once before treating it as settled: a cost ("still worth it if it costs a week? if it rules out Z? if nobody notices?") or a forced choice between two named shapes. A forced choice is a trade only when the two shapes collide, so that having one costs the other: name what makes them collide. When the user could have both, price each on its own cost instead. A price stated plainly inside an option the user picks counts as accepted with the option, and a part with no real cost to weigh settles by the user's acceptance. When the user holds an obligation or constraint fixed, preserve it and price only the flexibility that remains; if it is unclear what can move, ask. Read a trade answer for content, not for yes: it is where the user most often adds a part unasked.

Where artifacts can testify, let them. When the repo, recent decisions, or a record the user points at contradicts the stated want, name it plainly, once — "you said latency is secondary; you've merged three latency PRs this month" — then let the user resolve it. Sustained pressure is `grill-me`'s job, opt-in.

## Settled, Dissolved, or Routed

The user decides what is settled. A pick, a "yes", or a recommendation the user takes is a real decision. Never ask the user to say the want back in their own words, and never discount an answer because it came by number, by ticking an option, or by accepting text you offered.

Treat the shape as settled when the user has accepted it, the parts with a real cost have been priced, every explicitly fixed constraint is preserved, and no rival read is still live. Content the user adds that the read never held is a new part of the shape: price or confirm it, or carry it in the capsule marked as unpriced or unconfirmed.

Three other endings are successes, not failures:

- **Dissolved** — the want evaporates under shaping ("I don't actually want this"). Close warmly in a sentence or two; do not manufacture a consolation deliverable.
- **Routed** — the mud re-typed and the real need is options, evidence, or pressure. Name the lane and hand off (see Exits).
- **Parked** — the user is not ready. Name what would ripen it and stop.

When the user redirects before the shape is settled — asks for the next thing, switches lanes, pauses the session — comply, and mark whatever travels as your compression rather than as settled, naming the trade left unanswered if there is one. When the user stops at the exact moment the shaping got uncomfortable, say so once, gently, then comply with whatever they choose. If the user asks for a recommendation, give it in place: pose the trade they skipped as the priced values question, with your lean labeled as a lean. If the user takes the lean, that settles the trade.

## Exits

When the work shifts, name the move and let the user decline. Exits run in every direction, not just forward:

| The shaping has done its job when…                                   | Hand off to                         |
| -------------------------------------------------------------------- | ----------------------------------- |
| The want is clear and the user wants a design or spec                | `design-exploration`                |
| Criteria and two or more serious options are clear enough to compare | `making-recommendations`            |
| Two or more options are named but still sketch-level or uneven       | `option-shaping`                    |
| The field of options is too thin to want anything yet                | `ideate`                            |
| The answer lives in reality, not introspection                       | `prototype`, or gather the evidence |
| The blocking unknown is knowledge only one named person can close    | `to-questionnaire`                  |
| The user wants sustained pressure on weak answers                    | `grill-me`                          |
| The user asks for a complete critique, report, review, or audit      | the relevant review skill           |
| The want dissolved, parked, or needs no downstream lane              | conversational closure (no handoff) |

Some settled wants have no lane to go to: the next move is a small artifact — a sheet, a talk track, a short setup. Say that the shaping is over and the making is beginning.

When a receiving skill is user-invoked, give the human its token after the capsule — for `to-questionnaire`, `/to-questionnaire` on Claude Code or `$to-questionnaire` on Codex. When the receiver is unavailable, say so, return the capsule with the kind of work that remains, and stop.

When the user accepts a handoff, carry the capsule so the next lane starts from the settled shape, and carry its seam with it: what the user accepted, what is your compression, what is unpriced. A handoff to `option-shaping` needs the user to fix the candidate set first: concretes you offered them to react to are your probes, not their field.

## The Capsule

At a handoff point, or when the user asks to summarize, close with a short prose capsule — the closing read, not a decision log:

- what is settled, marking the seam: what the user accepted, by choosing, saying yes, or saying it themselves, versus what is still your compression that the user never saw and accepted
- what is still open, to be treated as live rather than decided
- the direction the user is leaning, only if one emerged
- the binding constraints and the trades the user already accepted
- what the shaping ruled out, where the user confirmed the exclusion
- the named next move, offered for the user to accept or decline

Omit any part with no real content. Briefs are chat-only: write a file, ticket, or durable artifact only when the user explicitly asks. When they do, the capsule is the brief: place it per repo convention, asking one path question if no convention is clear, and leave it uncommitted for the user to read. A narrow check needs only a sentence or two.

## Steering

Treat these as local conversation controls in ordinary language, not new trigger phrases:

- "Quick outcome check" — keep inspection and the read short; ask only the next useful question.
- "Read this first" — inspect the named artifact before the first question.
- "No direction yet" — offer interpretations without tentative recommendations.
- "Stay with this" — keep shaping the current uncertainty before any handoff.
- "Summarize where we are" — stop and produce the capsule.

## Restraints

- No findings reports, audit ledgers, file inventories, decision logs, or unrequested specs.
- No verdict or ranking on the want itself. A recommended option inside an ask is labelled as a lean.
- No filling parts to look complete; omit rather than manufacture.
- Keep reads plain. Prefer the user's clumsy sentence over your elegant one.

## Examples

Read [examples/interaction-examples.md](examples/interaction-examples.md) when mud re-typing, rival reads, trades, testimony, or closure shape is unclear — the examples are calibration, not extra required fields.
