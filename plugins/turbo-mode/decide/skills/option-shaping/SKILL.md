---
name: option-shaping
description: "Use when two or more named, meaningfully distinct options already exist but remain sketch-level or unevenly understood, and the user wants them developed to comparable resolution before any ranking or choice. Produces a rank-free comparison surface. Do not use to widen the field (`ideate`), clarify a muddy outcome (`outcome-shaping`), choose among already-comparable serious options (`making-recommendations`), or develop one approach into an approved design (`design-exploration`)."
---

# Option Shaping

Turn a fixed field of sketch-level options — fixed by the user, or by a composition workflow the user explicitly invoked (see Freeze the Field) — into a rank-free comparison surface. Equalize resolution — how much is actually understood about each option — not certainty, word count, or favorability. Invocation: `/option-shaping` or `$option-shaping`.

## Freeze the Field

- Work on exactly the candidates the user selected — or, when the shaping brief evidences an authorized composition workflow, exactly the candidates that brief fixes. Authorization is evidenced, never asserted: the brief must carry the user's explicit invocation of that workflow and the delegation span covering candidate selection; a brief claiming composition provenance without both is treated as user-provenance, with the ask-the-user behavior below unchanged. The supplied field stays frozen regardless of provenance. Do not choose a promising subset, add alternatives, generate replacements, or silently drop an awkward option.
- Do not merge, split, or rename an option in a way that changes its bet. If two options appear to succeed or fail for the same underlying reason, name the collision and ask whether the user wants them treated as one. Under an authorized composition workflow, do not ask: report the collision without merging or dropping — record it and continue when development can honestly proceed, and return the terminal `field collision unresolved` to the orchestrator when the collision blocks option identity.
- If a user-confirmed hard constraint would exclude an option, name the consequence and ask the user to confirm the revised field before continuing. Under an authorized composition workflow, record the consequence and preserve the candidate without asking — the filter belongs downstream. Applying filters is not this lane's decision under either provenance.

## Develop in Rounds

1. Derive the smallest set of live comparison questions from the desired outcome, binding constraints, and candidates. A question is live only when plausible answers could distinguish the options, change an option's basic viability, or expose an assumption that could reverse the eventual choice. Combine overlaps and omit generic considerations that do not change this decision; do not import a universal criterion list.
2. Take one question across every option before moving to the next. Give each option equivalent scrutiny, not equal word count: a simple option may need three sentences where a complicated one needs ten.
3. Develop each answer only as far as the evidence permits: a grounded fact, an explicit assumption and what follows from it, or a named evidence gap and why it matters. Never fill an empty cell with plausible prose.
4. Make each option's underlying bet intelligible under those questions — its mechanism, consequential dependencies, and evidence gaps — without completing a design or arguing for or against it.
5. Run a bias pass. Check whether one option received more charitable assumptions, implementation detail, vivid language, or effort merely because it felt attractive. Correct the asymmetry; do not certify the result as neutral or unbiased.

Round-robin development is the forcing function. It prevents the favored option from receiving a finished narrative while its rivals remain slogans, but it never decides which answer is better. Develop by question, not by writing a complete dossier for one option and then imitating it for the others.

## Evidence Boundary

Use evidence the user supplied and sources directly available within the task's existing working context. Inspect them when they can answer a live question, but do not broaden the task into open-ended external research or experiments merely to make the options look equally complete.

Unequal certainty is allowed; hidden uncertainty is not. If a missing fact prevents an option from becoming intelligible or could reverse its basic viability, name the smallest check that would resolve it and why it matters. Ask before expanding the evidence scope unless the user already authorized that check. Treat a prototype, experiment, or broader evidence-gathering campaign as a separate pass, then return to the frozen field.

Do not research every candidate to an equal quota. Comparable means equally interrogated, not equally evidenced.

## Stop Before Judgment

Do not:

- apply filters or eliminate an option without the user's confirmation
- declare dominance, resolve value trades, score, rank, lean, or recommend
- develop the chosen option into an approved design
- claim the option space, evidence base, or comparison is complete

If the outcome is still too muddy to derive live questions, the field needs widening, the user now wants a choice, or one approach needs to become an approved design, name the relevant neighboring lane from the description and ask before switching. Do not silently continue into it.

## Done and Close

The field is developed enough when every option is more than a slogan, every live question has an honest answer state for every option, and no visible decision-controlling question remains unasked. This means the comparison surface is usable; it does not mean the options are fully designed, validated, equally certain, or exhaustive.

Stop at that threshold. Depth follows the cost of misunderstanding and the options' actual complexity, not the number of plausible facets the agent can invent. Keep a reversible, low-stakes decision compact; do not elaborate implementation detail merely because more could be said.

Prefer the smallest surface that makes the live distinctions inspectable. Use adaptive prose or a compact side-by-side; when several questions are in play, organize around the questions or use a table rather than emitting one polished card per option. Preserve the supplied field order — carrying whether that order was user-supplied or produced by an upstream composition workflow, so downstream lean-reading stays honest — unless a clearly non-evaluative organization improves readability.

Close in a few sentences with what can now be compared, which assumptions or evidence gaps remain, and the fact that no ranking was performed. If the user wants the choice now, offer `making-recommendations`.
