---
name: ideate
description: "Use when the user wants to GENERATE a wide field of genuinely different options before any narrowing: brainstorm broadly, widen the solution space, get unstuck from one idea, see what is possible. Produces a deliberately un-ranked field and stops there. Do not use to develop a fixed sketch-level field to comparable depth (`option-shaping`), pick among options already on the table (`making-recommendations`), shape or approve one design (`design-exploration`), clarify a still-muddy goal (`outcome-shaping`), or stress-test a settled plan (`grill-me`)."
---

# Ideate

Widen a clear-enough prompt into a deliberately un-narrowed field of genuinely different options, then stop before any ranking. Invocation: `/ideate` or `$ideate`.

ideate widens the solution space itself and hands the field off un-narrowed. It never ranks, scores, picks, or develops one option into a design.

## The moves — a rhythm, not a fill-in template

1. **Name the frame; confirm you can generate.** State in one line the frame the prompt assumes — its load-bearing assumption, implied unit, owner, or success metric. If the *goal* is too muddy to say what would even count as an option, hand to `outcome-shaping`; the only reframing ideate owns is of the solution space, never the goal.
2. **Generate widely from rotating provocations, held as private scratch.** Vary the core mechanism; relax, move, or invert a constraint assumed fixed (budget, deadline, must-reuse-X); walk the ambition ladder (tolerate → cheap patch → standard build → radical rebuild → buy-or-borrow); transplant a mechanism from a distant domain; restate the problem as a different frame and generate under it. Use the ones that bite; drop the rest. A provocation is a tool that produces an option, never a label on it. Admit the non-serious, won't-win, frame-breaking option — in this lane breadth is the deliverable, not a means to a pick.
3. **Run two anti-modal moves — mandatory.** The exact opposite of your first instinct, and the option you would be slightly embarrassed to propose. These are the divergence an eager model skips, and they are what make the field wider than `design-exploration`'s natural two or three. They land in the field described like any other option — no "opposite" or "embarrassing" tag survives to output.
4. **De-cluster on mechanism, not clothes.** Two options collapse to one if they would succeed or fail for the same reason — if they share the same load-bearing mechanism or assumption (Postgres and MySQL both bet on a single relational node: one option, not two). A different provocation that produced the same mechanism is still one option. Collapse only on a shared failure reason you can actually name; when you cannot name one, keep both — the collapse runs in private scratch where the reader cannot contest it, and a wrong collapse costs the product while a wrong keep costs a line. Where the *whole field* shares one hidden assumption, name it aloud and generate an option that violates it.
5. **Stop on a stable field, not a count.** Halt when another pass yields nothing mechanism-distinct and the frame-break plus both anti-modal moves are present. Quantity is a raw generation target, never the done-test. A stable field is a fact about your search, not about the space — which is why the close below claims so little.

## Output and the no-certificate rule

A flat, **un-ranked** field. Each option: a short handle, a one-line core idea, and the distinct bet or mechanism that sets it apart — descriptive, never evaluative. No per-option "source" or "lens" tag (it manufactures the surface difference the de-cluster exists to strip). No scores, no ordering by quality, no "I'd lean," no developing an option into a design. Generation order is not neutral either: your first instinct generated first, and the first slot reads as the favorite — order by an axis with no quality reading (cluster, or the constraint each option varies) and never lead with your first instinct. Then reread the handles and one-liners: if a reader could reconstruct your lean from wording alone, reword until they cannot — a stated lean is at least contestable; a favorite wearing the best handle is not. Cluster lightly only for scannability; clustering is presentation, never proof of coverage. Chat-first: the field is delivered in the response — no artifact by default.

Close with **one honest line naming which of the prompt's own fixed points the field still leaves untouched** — anchored to the prompt's stated constraints, not to axes you drew. That is the only coverage signal allowed.

**Never certify coverage over a frame you chose.** A coverage ledger, a per-option provenance tag, a gap-map, or a "stop at N" box-count all manufacture false confidence worse than honest ignorance — the field looks complete relative to a map you drew, exactly where that map is blindest. The two honest coverage signals are both externally anchored: the prompt-anchored frame-break, and the untouched-fixed-points line.

## Hard stop and handoff

Stop the instant a stable field exists — even when the same message asks "so which?" Crossing into evaluation is the failure this skill exists to prevent. Hand off by naming the lane and stopping, never silently continuing:

- **`option-shaping`** — the user wants generated options developed to comparable depth without a pick. Ask them to fix the candidate set before handoff; do not select a promising subset, carry the whole divergent field by default, or predefine its comparison questions.
- **`making-recommendations`** — the user wants to pick and the options are already serious enough to compare.
- **`design-exploration`** — the user wants a few approaches shaped and developed toward an approved design.
- **`outcome-shaping`** — generating revealed the goal itself is too muddy to know what counts as an option.

## When not to widen

- The options are already on the table and the user wants a pick → `making-recommendations`.
- The goal is still muddy — you cannot say what a good option would even do → `outcome-shaping`.
- The prompt has one right answer and a wide field is just noise → say so and stop; do not manufacture diversity. Knowing when *not* to widen is part of the skill.
