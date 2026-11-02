---
name: assumption-check
description: "Use when a plan, design, or decision is settled enough to act on and you want its load-bearing assumptions surfaced before building: enumerate what must be true for the plan to work, rank each by how load-bearing and how uncertain it is, and attach the cheapest confirm-or-kill probe to each, as a durable artifact. Forward and non-adversarial; renders no verdict on the plan. Do not use for adversarial review of an artifact (scrutiny lanes), imagining completed failure (premortem), attacker modeling (red-team), or one-question-at-a-time interrogation (grill-me)."
---

# Assumption Check

Surface what a settled plan needs to be true before effort is spent on it: enumerate the assumptions the plan is standing on — including the ones it never states — rank them by how load-bearing and how uncertain each is, and attach the cheapest confirm-or-kill probe to each, as a durable artifact. Invocation: `/assumption-check` or `$assumption-check`.

The plan is already chosen; this lane does not critique it, re-decide it, or judge its readiness — it reasons forward from the plan as written and plans confirmations, so the beliefs the plan depends on get tested cheaply before the build tests them expensively.

## The moves — a rhythm, not a fill-in template

1. **Pin the plan and say where the artifact will land.** State in one line the plan, design, or decision being checked and confirm it is settled enough to act on, then name the artifact path up front so the user can redirect it early. If the plan is still being shaped, this is the wrong lane — shaping is `design-exploration`, a muddy goal is `outcome-shaping`, picking between rivals is `making-recommendations`.
2. **Enumerate — explicit and implicit.** Surface every assumption the plan needs to be true, then hunt the ones it never states: technical (the API behaves as remembered, the data is the shape we think), environmental (capacity, versions, access, tooling parity), human (the team knows X, the stakeholder meant Y, someone will be available), sequencing (step 3 really can start before step 5 finishes), and "someone else already solved this" (the library/pattern/doc we're leaning on actually covers our case). The stated plan text is the floor, not the field.
3. **Rank in words, not numbers.** Order the assumptions by how load-bearing each is crossed with how uncertain it is — the structural-and-unverified ones first — as an ordered list with a one-clause reason per item. No numeric scores, no weight formulas, no likelihood-impact matrices: "(load-bearing × uncertainty)" names a judgment to make, not a quantity to compute, and the reasons are where the judgment shows.
4. **Attach the cheapest confirm-or-kill probe to each.** For every ranked assumption, the cheapest observable test that would settle it: a command to run, a file or doc to read, a 10-minute spike, a question to a named person. Each probe names both sides — what evidence would confirm the assumption and what would kill it. A probe with no kill condition is a reassurance ritual, not a probe.

## The artifact

In a git repo, write the register to the consuming project's planning-docs convention (per its `AGENTS.md` or `CLAUDE.md`), defaulting to `docs/plans/YYYY-MM-DD-<topic>-assumptions.md` and creating `docs/plans/` if absent. Outside a repo, or on ask ("chat only"), deliver it in chat instead. Each entry carries the assumption, its rank reason, its probe with confirm and kill evidence, and a status the human can fill in as probes run — `unprobed` / `confirmed` / `killed`. The statuses are the artifact's vocabulary for the human's own tracking, not workflow states any agent maintains, audits, or enforces.

## The close — no verdict, no certificate

The run ends when the artifact is written and every ranked assumption has a probe. Then:

- **Render no verdict.** assumption-check never concludes the plan is safe, ready, de-risked, low-risk, or approved — and it gates nothing: no "do not proceed until" language, ever. Readiness calls belong to the scrutiny lanes when available; the deliverable here is the register, and "three load-bearing assumptions, none yet confirmed" is a complete, honest output.
- **Offer probe execution; run probes only on ask.** Many probes are the human's to run (a question to a colleague, a check against prod access the agent doesn't have). Executing any probe — even a cheap local command — is a follow-up the user opts into, not part of the run.
- **Close with one honest line reporting what was enumerated and what remains unprobed.** Never certify coverage: the assumptions most likely to sink a plan are the ones nobody listed, and a register that looks exhaustive is blindest exactly where its author was.

## When not to use

- You want the plan judged, stress-tested, or given a readiness verdict → the scrutiny lanes (when `review-family:scrutinize` is available).
- You want failure imagined from the future looking back → `premortem`.
- The threat is a motivated adversary → `red-team`.
- You want to be interrogated about your plan, one question at a time → `grill-me`.
- The plan is not settled yet → `design-exploration` (shape it), `making-recommendations` (pick it), or `outcome-shaping` (find the want).
