---
name: outcome-shaping
description: "Use when the user has a still-muddy idea, plan, design, or decision and wants to work out what they want — an interview-style shaping conversation before choosing the next move. Do not use for one-off clarification, implementation, reviews, audits, or critiques. Once the want is clear: shaping a design is `design-exploration`, choosing among named options is `making-recommendations`, and stress-testing settled answers is the grilling lane (`grill-me`/`grill-with-docs`); when the field of options is too thin to want anything yet, widening is `ideate`."
---

# Outcome Shaping

Help the user build a want they can stand behind — before plans, mechanics, or critique take over. Invocation: `/decide:outcome-shaping` on Claude Code or `$outcome-shaping` on Codex.

In genuinely muddy territory there is usually no finished want waiting to be excavated; articulation constructs it. That makes this lane joint authorship, and it makes you a hazard: your read is a draft the user may sign because it is fluent, not because it is theirs. The method exists to keep the user the author — their words, their trades, their restatement — while you supply structure, contrast, and honest evidence.

This is a shaping lane, not a review, audit, design, ranking, or implementation workflow. It can prepare a handoff, end in "gather evidence first," or end with the want dissolving. That last one is a success, not a failure.

## Core Behavior

These are the load-bearing invariants; the sections below add depth rather than restating them.

- Before interviewing, judge why the user can't say it yet; only one kind of mud is question-soluble (see Type the Mud).
- The engine is the read, not the questions: one compact, evolving statement of the want, offered for correction, usually opened "My read so far:". Rewrite it as understanding improves; never append a ledger.
- Keep the user's load-bearing words, and never transpose the want into a different register than the one it lives in (see The Read).
- Pace by contingency: serialize questions only when the next depends on the answer to the last; batch independent ones in a single turn (see The Read).
- Nothing negotiable is settled until it has survived at least one priced trade; preserve a constraint the user explicitly holds fixed and price the flexibility that remains (see Load-Testing the Want).
- Convergence is the user restating the want in their own words; assent to your text is weak evidence (see Settled, Dissolved, or Routed).
- When you are working from a summary rather than the user's actual sentences — after context compaction, or deep in a long conversation — say so, and re-confirm the settled shape in their words before any capsule. Anything you cannot source to their words is your compression, and the capsule marks it that way.
- Keep the lane read-only, and hand off by name when the work shifts (see Exits).
- This method needs a live, responsive human: never run it from a subagent, hook, cron, or other unattended context. When the ask is underspecified and no one is there to correct the read, say what the shaping would have surfaced and stop — report the underspecification rather than interviewing an absent user and treating your own read as their want.

## Type the Mud

Hold one question from the first message onward: why can't the user say what they want yet? The answer decides the tool, and questioning a user whose mud is not question-soluble harvests confabulation — people generate confident answers to questions they have no access to, and a fluent mirror will lovingly stabilize those answers into a fake want.

Four shapes to listen for, not a label to declare:

- **Missing words** — they know it in their hands but not in language. The mirror loop below is the right tool; this is the only interview-soluble mud.
- **Missing options** — they cannot want what they have not seen. Offer two or three sharply contrasting concretes to react to, or name `ideate` and hand off; no interview conjures a want from an empty field.
- **Missing information** — the answer lives in reality, not introspection: would it be fast enough, do users care, does the approach even work. Name the evidence that would settle it and route toward it — a throwaway `prototype`, an experiment, a measurement — instead of asking questions the user can only answer by guessing.
- **Colliding wants** — two real wants pull apart, or the answer is known and unwelcome. Name the collision plainly, hold both sides in the read (see The Read), and offer `grill-me` when the user wants pressure rather than mirroring.

Re-type as you go. Mud changes shape mid-conversation, and an interview that keeps producing confident answers that die under trades is usually missing-information mud wearing missing-words clothing.

## The Read

The engine of this lane is the read — a compact, evolving, plain statement of the want, offered so the user can correct it cheaply. Questions exist to make the next read truer; recognition beats recall, and a user who cannot state their want can instantly say "no, not that."

- Open with something easy to correct, usually "My read so far:". Rewrite the read each turn as understanding improves; never append answers into a decision log.
- Keep the user's load-bearing words. Translate mechanism-smuggling into outcomes — "audit log" and "Kafka" are solutions wearing want-clothing — but never flatten a precise term into folksy paraphrase the user must re-audit, and never replace their words with your elegant ones just because yours are smoother.
- Listen for the register the want lives in — relief (stop checking, stop worrying), ambition (fastest, best, first), curiosity (learn, see, find out), craft (clean, right, beautiful), identity (be someone who shipped it), obligation (owed to someone else), optionality (keep the door open) — and never transpose silently. An ambition rendered as relief ("you want users to stop worrying about latency") is a different want wearing your vocabulary.
- While the user is torn, hold rival reads side by side: "You want A. You also want B. They collide at C." Collapse them when the user resolves the collision, not when one sentence would be tidier.
- Offer likely interpretations before direction; add tentative direction only when it helps the user answer the live question, and make it easy to correct.
- Pace by contingency. Ask one question when the next depends on this answer — that is most of the time in real mud. Batch independent questions in one turn instead of serializing them theatrically. If every question you want to ask is independent, stop: you are administering a form, and the mud is probably not missing-words.

## Reading Context

When the user points at an artifact, path, plan, or prior decision, read what makes the next read materially better — before the first question when asking blind would be performative, or mid-interview when an answer reveals that context would clarify more than another question would. Follow relevance, not a file cap, and stop once you can offer a better read or a better question.

Fold silently-inspected scope into the read in one short phrase so the user can correct the inference without receiving a file inventory. Narrate inspection only when it will take a noticeable detour or the target is unclear.

Inspection serves the shaping — and artifacts are witnesses, not just background (see Load-Testing the Want). It never produces a findings report, audit ledger, source inventory, or file-by-file explanation. If inspection reveals a likely problem, carry it into the next read or question rather than reporting it as a finding.

## Load-Testing the Want

A want elicited in a cost vacuum is a wish. Preferences are demand curves, not points: "I want X" at cost one and "absolutely not X" at cost ten are the same person. Before treating a negotiable part of the shape as settled, price it at least once — "still worth it if it costs a week? if it rules out Z? if nobody notices?" When the user explicitly holds an obligation or constraint fixed, preserve it and price only the flexibility that remains; if it is unclear what can move, ask. When nothing can move, record the fixed constraint and let the other settlement or parking rules decide the close rather than asking the user to surrender it for the method's sake. A negotiable want that dies under its first honest trade was not the want; what survives, and what the user gave up to keep it, is the shape.

Where artifacts can testify, let them. Stated and revealed wants diverge, and the repo, the last three decisions, and any calendar or record the user points you at are witnesses this lane is allowed to call. When the evidence contradicts the stated want, name it plainly, once — "you said latency is secondary; you've merged three latency PRs this month" — then let the user resolve it. One naming, then defer; sustained pressure is `grill-me`'s job, opt-in.

## Settled, Dissolved, or Routed

Your fluency is a hazard at exactly this point: fatigue, politeness, and a well-written summary all produce assent, and assent is what a capture machine collects. The test of a built want is the user saying it back in words you did not supply, and the restatement surviving.

Treat the shape as settled only when the user has restated it in their own words, every negotiable part has survived at least one priced trade, every explicitly fixed constraint is preserved, and no rival read is still live. A restatement that carries content the read never held has added a new part to the shape: price it when it is negotiable, or confirm and preserve it when the user holds it fixed, before treating the restatement as settled; otherwise carry it in the capsule marked as unpriced or unconfirmed. Watch for unprompted restatement — it is the strongest signal you get. When stakes warrant and it has not happened, ask for it: "say back what we've landed on, in your words." A fast "yes, exactly" to your own prose is noise.

Three other endings are successes, not failures:

- **Dissolved** — the want evaporates under shaping ("I don't actually want this"). Close warmly in a sentence or two; do not manufacture a consolation deliverable.
- **Routed** — the mud re-typed and the real need is options, evidence, or pressure. Name the lane and hand off (see Exits).
- **Parked** — the user is not ready. Name what would ripen it and stop.

When the user quits at the exact moment the shaping got uncomfortable, say so once, gently — "we're stopping right where it got hard; want to leave it there?" — then comply with whatever they choose. Deference with eyes open. If what they choose is a recommendation, give it in place rather than routing an unpriced collision into a lane that must bounce it: pose the trade they skipped as the priced values question, with your lean labeled as a lean, never a pick.

## Exits

This lane prepares; it does not design, decide, critique, or implement. When the work shifts, name the move and let the user decline — but exits run in every direction, not just forward:

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

Destinations outside the Decide plugin are optional. When an external receiver is available and model-invocable, name the handoff normally. When it is user-invoked, give the human its supported token after the capsule — for `to-questionnaire`, `/to-questionnaire` on Claude Code or `$to-questionnaire` on Codex — and do not treat the route as an operative invocation. When the receiver is unavailable, say so, return the short capsule with the kind of work that remains, and stop; do not perform the missing skill's work in this lane.

When the user accepts a handoff, carry the capsule (below) so the next lane starts from the settled shape instead of re-interviewing it. A handoff to `option-shaping` needs the user to fix the candidate set first: concretes you offered them to react to are your probes, not their field.

## The Capsule

At a handoff point, or when the user asks to summarize, close with a short prose capsule — the closing read, not a decision log:

- what is settled, marking the seam honestly: what the user confirmed in their own words versus what is still your compression
- what is still open, to be treated as live rather than decided
- the direction the user is leaning, only if one actually emerged
- the binding constraints and the trades the user already accepted
- what the shaping ruled out — exclusions the user actually confirmed, since silent disagreement about what is *not* being pursued is a large share of downstream misalignment
- the named next move, offered for the user to accept or decline

Omit any beat with no real content rather than manufacture one. The capsule carries no authority the shaping never earned, and briefs are chat-only: write a file, ticket, or durable artifact only when the user explicitly asks. When they do, the capsule is the brief: place it per repo convention, asking one path question if no convention is clear, and leave it uncommitted for the user to read.

A narrow check needs less — a sentence or two of plain shape and the remaining uncertainty is a complete closure.

## Steering

Treat these as local conversation controls in ordinary language, not new trigger phrases:

- "Quick outcome check" — keep inspection and the read short; ask only the next useful question.
- "Read this first" — inspect the named artifact before the first question.
- "No direction yet" — offer interpretations without tentative recommendations.
- "Stay with this" — keep shaping the current uncertainty before any handoff.
- "Summarize where we are" — stop and produce the capsule.

## Restraints

These are not epistemology; they are controls on what a language model over-produces when facing a confused user:

- No findings reports, audit ledgers, file inventories, decision logs, or unrequested specs — the model's strongest gravitational pull is dumping structure on mud.
- No verdicts, rankings, or settled recommendations; this lane prepares those moves and hands them off by name. Exception: the user who quits a hard trade and asks for a recommendation anyway (see Settled, Dissolved, or Routed) is answered in place, as the priced values question with a labeled lean, never a pick.
- No filling beats to look complete; omit rather than manufacture.
- Fluency is a hazard, not an asset. A crisp wrong read is more convincing than a true muddy one; prefer the user's clumsy sentence over your elegant one.

## Examples

Read [examples/interaction-examples.md](examples/interaction-examples.md) when register handling, mud re-typing, rival reads, trades, testimony, or closure shape is unclear — the examples are calibration, not extra required fields.
