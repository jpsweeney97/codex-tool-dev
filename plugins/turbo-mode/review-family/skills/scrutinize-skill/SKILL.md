---
name: scrutinize-skill
description: "Use when the target of an adversarial review is an agent skill, skill directory, SKILL.md, agents/openai.yaml, skill reference, example, or proposed skill contract, including explicit `review-family:scrutinize-skill`, `/scrutinize-skill`, `$scrutinize-skill`, or natural-language requests like `scrutinize this skill`. Do not use for routine skill editing, implementation, general artifact review, completed-code review, or non-adversarial skill UX/design work."
---

# Scrutinize Skill

Review an agent skill as a behavior contract. Ask whether the skill will make the agent behave well after it triggers, not only whether the bundle is structurally valid.

## Review-Family Routing

Explicit review-family invocation wins (`review-family:scrutinize-skill`; `/scrutinize-skill` or `$scrutinize-skill` where skill mentions are available). When the review target is an agent skill or skill-support file — a skill directory, `SKILL.md`, `agents/openai.yaml`, behavior-shaping reference, example, or proposed skill contract — this skill also wins over generic `scrutinize`, even under natural-language scrutiny wording.

- Broad adversarial artifact critique, formal stress tests, or execution-readiness reviews where this skill was not invoked → `scrutinize`.
- Completed code or artifacts against a plan/spec → `implementation-review`; architecture or system-boundary review → `system-design-review`.
- Supplied-review adjudication or pasted-claim checks → `review-reviewer`.
- Otherwise-wrong lane: name the better skill; if invocation rules bar switching, ask one routing question.

## Scope

Primary question: will the right skill behave poorly once triggered?

Review these failure modes first:

- the skill gives weak next-step guidance after triggering
- muddled instructions make the agent improvise important behavior
- the user experience is awkward, heavy, vague, or missing closure
- the skill silently becomes another workflow instead of handing off
- overlapping skills make routing unclear, duplicate, or fragmented
- validation claims prove structure while implying behavior
- a judgment skill is so over-ruled — fixed output shapes, exhaustive rules, sections filled to feel done — that the agent performs the contract instead of thinking
- a judgment skill provokes nothing — no forcing function, no counter-pressure — so it adds nothing over the bare agent, or provokes too weakly — a forcing function present but dulled, hedged, or softened (an adversarial posture reframed as collaborative) so it no longer creates real counter-pressure (the *provoke* half of the bar, failed by absence or by dilution rather than by over-ruling)
- a trust skill is so rigidly ruled it does the wrong thing in an unforeseen case (a crude gate dead-ending legitimate work), or reimplements machinery copied from siblings instead of sharing it
- the skill performs an epistemology its method cannot deliver — measurement, discovery, or verification claims that a single pass or a single judge cannot produce, restraints dressed up as a method — a class this review can detect but not adjudicate: raise it and route to `methodology-check` — the cheap text-and-census methodology adjudicator, which escalates to the fire-tested `methodology-critique` when how the skill fires in real transcripts is the crux — rather than clearing the premise

Out of scope: routine skill editing, implementation, source sync, installed runtime proof, broad plugin audits, completed-code review, and marketplace publishing unless the user explicitly asks for that separate work.

## Evidence Floor

Inspect the exact target before judging it.

If the target is a file inside a skill bundle, such as `SKILL.md`, `agents/*.yaml`, `agents/*.md`, `references/*`, `examples/*`, or another behavior-shaping file, treat the containing skill directory as the target; when the user explicitly narrows the request to that file only, inspect only that file and run the pass as a bounded review of the skill (see Verdict), not a clearance of the bundle.

For an existing skill bundle, inspect:

- `SKILL.md`
- `agents/*.yaml` or `agents/*.md` when present
- behavior-shaping files directly referenced by the skill
- examples or references only when they affect invocation, instructions, evidence rules, expected output, validation, or handoff behavior

For a proposed skill contract, state which normal bundle surfaces do not exist yet and review the available contract as proposed behavior.

Compare overlap against the whole available skill set. Start with skill names and descriptions, then read only likely overlaps deeply enough to decide which skill should win, whether routing needs clarification, or whether skills should merge or split. Do not bulk-read unrelated skills just to appear exhaustive. For source-bundle reviews, default to session-visible skill descriptions plus a source sibling scan. Add installed cache or runtime inventory only when the user asks about downstream installed or loaded behavior, or when the overlap claim depends on that proof class. Report the overlap coverage and skill-set source used: session-visible skill descriptions, source sibling scan, installed cache scan, or runtime inventory. Include likely overlaps deep-read, and mark omitted or unavailable skill surfaces `unverified`. If the source is not runtime inventory, do not imply loaded-skill state.

Separate proof classes:

- `structural`: parseable frontmatter, valid YAML, expected files, references that exist
- `behavioral`: realistic dry runs, observed transcripts, or worked examples that show the agent behaving correctly when the skill is triggered
- `reasoned`: a prediction argued from the contract text alone — legitimate evidence and the review's most common kind, but simulation, not observation; never file it as `behavioral`, and when a reasoned claim drives the verdict, name the cheapest check that would settle it (a dry run, a blind proxy, a smoke test)
- `runtime`: installed plugin or loaded skill state observed through the active runtime

Do not claim runtime installation, activation, hook behavior, marketplace sync, or loaded-skill state from source files, cache files, or marketplace metadata alone.

## The Review

Lead the reply with the verdict, then the findings that carry it, most severe first. Lead each finding with the user-visible behavior: wrong amount of friction, unclear first move, poor handoff, generic output, missing stop condition, false proof, or ambiguous overlap. Name the exact target, the anchor the verdict binds to (commit, version, or date; state when none is determinable), what you inspected, and what you left unread that could change the review. Give the review no fixed section list, and leave out a part that has no finding.

Judge each part against its bar: a part whose value is the agent thinking better is held to whether it protects and provokes thinking; a part whose value is reliable execution is held to reliability and single-sourced machinery (see `agent-facing-design`, Two Kinds of Skill).

For each overlapping skill that matters, say which applies: `target wins`, `other skill wins`, `routing clarification needed`, `merge candidate`, `split candidate`, or `no material overlap`.

A finding's severity follows the bar. On a judgment part, internal-conformance divergence drops or downgrades, but a thinking or provoke-side defect — structure that strangles thinking, a part that provokes nothing (no forcing function, no counter-pressure), or a forcing function dulled, hedged, or softened until it no longer creates real counter-pressure — keeps or escalates, exactly as a trust defect would. On a trust part, duplication, drift, or overreach keeps or escalates. Severity also weighs the reviewed skill's blast radius: the same defect is graver in a contract that wields mutating or irreversible effects than in one whose output stays read-only. Delivery hygiene (invocation tokens, naming, budget, parseability) is uniform — judged the same for both. Dropping conformance noise is the goal; going toothless on a real judgment defect is the opposite failure, not leniency rewarded as success.

These judgment failure modes are examples, not a checklist to complete. Do not add a bar-keyed required step, fixed section, or score to this review — that is itself the over-ruling the lens exists to prevent, and it applies to this rubric too.

Each finding must include a compact evidence pointer: file/line, command output, observed behavior, or `unverified` with the exact missing check. Do not make location-free findings when the target is file-backed.

Findings are argued hypotheses until something independent of the arguing tests them; the recorded failures run both directions — raw findings over-claim under independent verification, and a review re-refuting its own finding has killed a real defect. Re-arguing, for a finding or against it, is not verification. Present the required changes as what the findings warrant if they hold, and when one finding carries the verdict, prefer the cheapest disconfirming check over more argument.

When the review's required changes have been applied and the open claim becomes "the changed contract is now followed," proving that is `behavior-smoke-test`'s job (`/behavior-smoke-test` or `$behavior-smoke-test` where available), not a re-review.

## Verdict

Use exactly one of `Reject`, `Major revision`, `Partial review only`, `Minor revision`, or `Defensible`. `Partial review only` means bounded review mode was used: the reviewed subset was judged, the full target was not. If more than one verdict could apply, choose the first matching in this order: `Reject`, `Major revision`, `Partial review only`, `Minor revision`, `Defensible` — a disqualifying finding in the reviewed slice renders its verdict, scoped to the slice, and is never hidden behind an incomplete-pass label. The verdict grades the behavior contract as written — execution altitude. It does not certify that the skill's underlying method or premise is true: a contract can execute cleanly on a false premise, and structure can pass the provoke test while claiming knowledge the method cannot produce. When the premise itself is the doubt, raise it as a finding and route to `methodology-check` (which escalates to `methodology-critique` when the crux is behavioral); do not clear it from a contract pass. `Defensible` is a clearance verdict, and a clearance verdict claims serious search was exhausted without a disqualifying find — it does not certify soundness, and it expires when the artifact changes.

Use bounded review mode when the target or skill set comparison is too large to inspect completely in one pass. In bounded mode, state the reviewed subset before findings, review the highest-risk surface first, mark omitted areas `unverified`, give the next slice needed for a complete review, and do not issue a full-clearance verdict for the full target (do not use `Defensible`; choose the verdict by the precedence order above — `Partial review only` unless a disqualifying in-slice finding renders `Reject` or `Major revision`, scoped to the slice). A review whose scope was narrowed externally — a caller-restricted scope, an assigned lens or panel seat, or sampled coverage — is also a bounded review: state the subset, scope the verdict to it, and leave `Defensible` unissued.

## Guardrails

- Stay read-only: do not edit files, stage, commit, push, delete, sync, publish, or implement fixes unless the user explicitly asks for that separate action after the review; the same gate covers installing, refreshing plugin caches, and mutating runtime state.
- Do not mentally repair weak instructions. Review the behavior contract that exists, not the one the author probably intended.
- Self-authored target: if you authored the target — this session or otherwise — disclose it, and treat your own absence claims (`no material overlap`, a `Defensible` clearance) with declared extra skepticism.
- Do not pad with generic writing advice. Every finding must identify a concrete failure path or user-visible weakness.
- If overlap with a non-review-family skill matters, read enough of that skill to justify the routing or merge/split recommendation before making it verdict-driving.
