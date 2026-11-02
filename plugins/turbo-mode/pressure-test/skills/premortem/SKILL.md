---
name: premortem
description: "Use when a plan, design, or decision is settled-or-nearly-settled and committed, and you want prospective failure-imagination before execution — 'premortem this', 'imagine it's six months later and it flopped, why', 'what could make this fail'. Generates a wide field of past-tense accidental failure-causes with pre-mitigations and dated tripwires, and renders no verdict. Not for re-deciding go/no-go or readiness (`scrutinize`), an adversary's intentional attack (`red-team`), or widening the solution space (`ideate`)."
---

# Premortem

Stand in a future where the committed plan has already failed, and work backward to the accidental causes — so the failure modes commitment optimism hides get named while there is still time to mitigate them. Invocation: `/premortem` or `$premortem`.

premortem does not re-decide the plan — the plan is already chosen — and it does not adjudicate readiness. Its product is a wide field of how-this-could-die, each turned toward a mitigation, handed off without a verdict. The debiasing engine is the past tense: asserting the failure as *already true* ("it is N months later and this failed") loosens what "what are the risks?" leaves stuck under the momentum of a decision already made.

## The moves — a rhythm, not a fill-in template

1. **Pin the committed plan; confirm it is chosen.** State in one line the plan, design, or decision being premortemed and that it is settled enough to fail. If the plan is *not yet chosen*, premortem is the wrong lane — widening options is `ideate`, picking among them is `making-recommendations`, shaping one is `design-exploration`. If the *goal itself* is too muddy to say what "failed" would mean, hand to `outcome-shaping`. premortem assumes a commitment and hardens it; it never re-opens the choice.
2. **Assert the failure as accomplished fact — the debiasing engine.** Write it in the past tense, concretely: "it is N months later; this shipped and failed." Pick a horizon that fits the plan (weeks for a launch, months for a strategy). Stating the failure as already-true is the whole mechanism — do not soften it back into "it might not work," which surrenders the prospective-hindsight effect.
3. **Generate the field of past-tense accidental causes, from rotating provocations.** Work backward: *what had to have gone wrong for this to be the outcome?* Rotate the lenses an eager model skips — a load-bearing assumption turned out false; a dependency drifted, broke, or was slower than assumed; the plan contradicted itself under load; the people changed, left, or were never aligned; the context or market moved; the thing everyone assumed someone else owned; the slow erosion no single day caused. Indifferent universe only — never an attacker (that is `red-team`). Use the provocations that bite; drop the rest.
4. **De-cluster on mechanism, not clothes.** Two causes collapse to one if they would fire for the same underlying reason — same load-bearing assumption or failed dependency. Where the *whole field* shares one hidden assumption, name it aloud and surface the cause that violates it. A different provocation that produced the same mechanism is still one cause.
5. **Turn each surviving cause toward a mitigation and, where one genuinely leads, a dated tripwire.** For each cause: the pre-mitigation that would prevent or blunt it, and — only where a real early signal exists — a dated leading-indicator tripwire (the observable that says "this cause is materializing, act now"), tagged prevention / detection / mitigation. Not every cause has a tripwire; inventing one where no signal leads is the trap. These are strategic indicators across the plan's life, distinct from `deploy-plan`'s frozen one-ship abort thresholds.

## The close — no verdict, no certificate

Stop the instant another pass yields nothing mechanism-distinct (the stable-field halt, not a count). Then:

- **Render no verdict.** premortem does not conclude "go," "no-go," "ready," or "not ready" — the plan stays chosen; the deliverable is mitigated failure modes, not a re-decision. A go/no-go or readiness call is `scrutinize`'s execution-readiness review; if you catch yourself concluding "so this isn't ready," you have left premortem for `scrutinize`.
- **Route the durable items.** Owned, dated mitigations and tripwires file to `/triage` (or `$triage`), one issue per finding — by reference, never re-minting tracker machinery. Keep owner and date inline as the explicitly weaker fallback if no tracker is reachable. Chat-first: no artifact beyond these routed items by default.
- **Close with one honest residual line, externally anchored.** Name which of the *plan's own stated assumptions or fixed points* the field still leaves untouched — never a self-drawn coverage map. **Never certify coverage:** no "all failure modes captured," no likelihood×impact matrix presented as complete or precise. A field that looks exhaustive relative to a map you drew is most blind exactly where that map is. The honest signal is the plan-anchored residual, not a box-count.

## When not to premortem

- The plan is not chosen yet → `ideate` (widen), `making-recommendations` (pick), or `design-exploration` (shape).
- The user wants a go/no-go or readiness verdict, or a formal adversarial stress test → `scrutinize`.
- The threat is a motivated adversary, not accident → `red-team`.
- A real incident already happened → not premortem (before, imagined); the retrospective after the fact is a different job.
- The goal is too muddy to say what "failed" means → `outcome-shaping`.
