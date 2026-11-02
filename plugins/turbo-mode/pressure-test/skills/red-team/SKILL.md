---
name: red-team
description: "Use when a system, feature, plan, or asset could be attacked by a motivated adversary and you want attacker-intent modeling from the defender's chair — 'red-team this', 'how would someone abuse this', 'think like an attacker', 'what's the abuse surface'. Names adversaries and goals, traces attack paths (entry → step → payoff), ranks them by ease × payoff, and proposes raise-cost mitigations — no verdict. Not a secret/repo scan or `security-audit` reopen, not an artifact flaw-hunt (`scrutinize`), not a trust-boundary screen (`system-design-review`), not accidental failure (`premortem`)."
---

# Red Team

Become the adversary who wants this to fail, and find the cheapest path to their payoff — so the abuse surface invisible from the builder's chair gets named while it can still be hardened. Invocation: `/red-team` or `$red-team`.

You built it, so you reason from intended use and cannot see the goal-directed attacker; red-team forces the optimizing-adversary posture and asks not "is this boundary well-placed" but "here is the adversary, and here is the cheapest path through it to a payoff." Its product is a ranked field of attack paths, each turned toward a raise-cost mitigation, handed off without a verdict. It is **not a scan**: it reasons about adversary intent and attack economics; it never greps secrets or inspects a repo.

## The moves — a rhythm, not a fill-in template

1. **Pin the target; declare the threat scope up front.** Name in one line what is being red-teamed (a system, feature, plan, or asset), and — before generating anything — declare which adversary classes and capabilities you are modeling and which you are treating as out of scope (e.g. "modeling an unauthenticated external attacker and a low-privilege insider; not modeling a nation-state with supply-chain access or physical access"). This declaration is the firm move that makes the honest close possible: the residual is measured against it. When the target includes an LLM or agent surface, declare the LLM adversary classes in or out of scope by name: prompt injection (untrusted text in the context window carrying instructions — the system prompt is not a security boundary, so permissions the attack must not cross are enforced in code, never in the prompt), excessive agency (tool or agent permissions wider than the task, destructive actions without confirmation), system-prompt or cross-tenant leakage into the context window, and unbounded consumption (missing token, rate, or recursion limits).
2. **Name the plausible adversaries and their goals.** Not "a hacker" — concrete actors and the payoff each wants: money, data exfiltration, disruption/denial, competitive advantage, account takeover, or simple griefing. Include the non-obvious within scope: the malicious insider, the competitor, the automated bot, the bored or incentivized user. Drop adversaries outside the declared scope.
3. **Trace attack paths: entry → step → payoff.** For the cheapest and highest-payoff adversary-goals, walk the concrete path — an entry point, the steps through the system, the payoff at the end. Reason as the attacker *optimizing for the cheapest path*, not as the defender reasoning from intended use; the cheapest real path is the one that matters, not the most sophisticated.
4. **Order by ease × payoff — a hardening sequence, not a matrix.** Rank the paths you found by how cheap they are to execute against how much they yield, to produce the order to harden in. This is a prioritization of the paths you *found*; it is explicitly **not** a claim that the surface is fully enumerated. Do not present it as a precise or complete likelihood×impact grid.
5. **Propose raise-cost mitigations aimed at the cheapest paths.** The goal is not "eliminate the risk" but raise the attacker's cost above their payoff — make the cheapest path expensive enough that the economics stop working. Aim mitigations at the top of the hardening order first.

## The close — no verdict, no certificate, no scan

Stop when another pass over the in-scope adversaries yields nothing mechanism-distinct. Then:

- **Render no verdict.** red-team never concludes "the system is secure" or "this is safe." **Finding no path is not proof of safety** — it is the absence of a found path within a declared scope, nothing more.
- **Close with the residual, anchored to the declared scope.** Name the adversary capability you assumed bounded and what falls outside the threat scope you declared up front — never a self-drawn coverage map presented as exhaustive. The member of this lane most tempted to stamp "attack surface fully enumerated"; that stamp is forbidden.
- **Route durable hardening items** (owner + date) to `/triage` (or `$triage`), one per finding, by reference. Keep them inline as the weaker fallback if no tracker is reachable. Chat-first: no artifact beyond these routed items by default.
- **Compose forward when paths land on a designable surface.** Hand attack paths to `/authorization-design` (or `$authorization-design`) as must-deny rows and to `/injection-safe-inputs` (or `$injection-safe-inputs`) as must-block rows — one or both as the findings warrant, sequentially or concurrently; composition is not a license for subagent fan-out.
- **Residual check for LLM surfaces.** When the declared scope included an LLM or agent surface, glance at the OWASP Top 10 for LLM Applications while naming the residual — a checklist for spotting adversary classes the declaration missed, never a sweep to run in the moves and never a coverage map to present.
- **Stay non-scan.** If the work actually needed is grepping for secrets, scanning dependencies, or auditing a diff, that is `/security-review` or the `security-audit` park — name it and stop; do not improvise a scan.

## When not to red-team

- There is no plausible motivated adversary — the thing fails by accident, not attack → `premortem`.
- You want a secret/dependency/diff *scan* of a repo → `/security-review` or the `security-audit` park.
- You want an artifact reviewed for flaws with a readiness verdict → `scrutinize`.
- You want written code reviewed against a spec and a diff → `implementation-review`.
- You want to know whether a trust boundary is well-placed (architecture quality, not attack paths) → `system-design-review`.
