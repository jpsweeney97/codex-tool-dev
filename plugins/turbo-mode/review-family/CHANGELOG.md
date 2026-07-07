# Changelog

All notable changes to the Review Family plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.8.0 - 2026-07-07

### Changed

- `scrutinize-skill`'s premise lens now routes detected epistemology/premise doubts to the new `methodology-check` skill — the cheap, dual-runtime, single-agent text-and-census methodology adjudicator — instead of a generic "dedicated methodology-and-philosophy critique." `methodology-check` adjudicates the premise on the skill's text plus a fire census, and itself escalates to the fire-tested `methodology-critique` when how the skill fires in its real transcripts is the load-bearing question. This gives the detect-but-don't-adjudicate lens a real adjudicator to hand to on *both* runtimes: the only methodology treatment previously named was `methodology-critique`, which is Claude-only, so on Codex the route pointed at a skill that does not exist. Two spots changed — the Scope failure-mode bullet and the Verdict clause; both CANON cores (read-only, bounded-review), the routing frontmatter, the materiality gate, and every other organ are unchanged.

## 0.7.0 - 2026-07-03

### Added

- `scrutinize` gains verdict honesty and the codification of its own best observed behavior, briefed by the methodology-and-philosophy critique at `docs/reviews/2026-07-03-scrutinize-methodology-critique.md` (the arc's ninth hold, on its largest fire corpus — ~200 sessions over two runtimes; the critique found the stance, evidence architecture, floor, and both modes earning their keep, and the defect in the contract's self-understanding: a verdict is a fact about a search, and the text presented it as a fact about the artifact, while the method's dominant real uses — a convergence loop and caller-scoped panels — ran on discipline the text never wrote down). Five repairs, all prose, no new machinery: (1) verdict scope stated inline — `Defensible`/`Ready to Execute` claim serious search exhausted without a disqualifying find, not certified soundness, and expire when the artifact changes — plus the restored founding survives-clause (say why a surviving target survives, then pivot to residual risks; cut at the 05-28 compression, recovered from the 2026-04-02 ur-prompt); (2) a re-scrutiny paragraph codifying the loop's observed folk discipline (re-read live, verify fixes against the artifact and diff never the description, prior findings re-earned as hypotheses, hunt new defects, credit what held); (3) a bounded-review rider extending the discipline to externally-narrowed scope (caller-restricted, assigned lens/panel seat, or sampled) — the CANON bounded core stays byte-identical; (4) the normal verdict enum and severity scale homed in the always-loaded body with token-plus-scoping-gloss blessed (closes the 06-16 kept "verdict-vocab unreachable" defect and brings the layout under the 06-17 inline-vocabulary doctrine; review-format.md keeps the template with a back-pointer); (5) a mode-honesty clause — when the reviewer, not the user, chose the register, say so. Routing, both CANON cores, the premise check, the materiality gate, both mode organs, and `agents/openai.yaml` deliberately unchanged.

## 0.6.0 - 2026-07-02

### Added

- `scrutinize-skill` gains altitude honesty, briefed by the methodology-and-philosophy critique at `docs/reviews/2026-07-02-scrutinize-skill-methodology-critique.md` (the same treatment that rebuilt `outcome-shaping` and `making-recommendations`; here the critique found the philosophy substantially sound — restraint engineering that admits to being restraint engineering — and warranted repairs, not an inversion). Four changes, one thought: (1) a new failure-mode lens for the defect class the method previously blessed — a skill performing an epistemology its method cannot deliver (measurement/discovery/verification claims a single pass or single judge cannot produce) — which a scrutiny detects and routes to a dedicated methodology critique, never adjudicates or clears (observed miss driving this: the 2026-07-01 seven-lens scrutiny cleared MAP as a "legitimate forcing function" one day before the methodology critique showed it was bias in measurement costume); (2) the verdict is scoped to execution altitude — `Defensible` clears the contract as written, never the truth of the target's method; (3) a fourth proof class `reasoned` splits argued predictions out of `behavioral`, ending the "or reasoning" hatch that filed simulation as observation, with verdict-driving reasoned claims naming the cheapest settling check; (4) findings are named as argued hypotheses until independently tested — the recorded fires over-claim under verification (both 48-sweep systemic findings refuted) and over-refute their own real findings (the twice-refuted mrec9 defect) — so `Required Changes` is presented as what findings warrant if they hold, and re-arguing is named as not-verification. Plus one severity input: the reviewed skill's blast radius (a defect is graver in a mutating/irreversible contract than a read-only one). The judgment-vs-trust bar lens, both CANON cores (read-only, bounded-review), the workflow shape, the output sections, the verdict vocabulary, and the frontmatter routing description are all deliberately unchanged; `agents/openai.yaml` realigned to the new instruments.

## 0.5.0 - 2026-06-29

### Added

- `implementation-review` gains a `Split required` verdict and a mutation-adequacy heuristic, closing capability-growth review upgrade #2 (the strongest open §4 row). The verdict is reached from Bounded Review Mode when a change bundles genuinely independent concerns whose interleaving defeats reliable review as a unit — a diff mixing a refactor, a behavior change, and a migration, say — and it names concrete split seams cut along real boundaries (concern, requirement, risk surface, dependency layer) so the author can restructure into independently-reviewable units. It is sharply distinct from `Partial review only` by downstream action: `Partial` is a coherent target the reviewer will keep reviewing slice by slice; `Split required` is a mis-shaped target where no clearance verdict is trustworthy until the author splits it and re-submits. The trigger is seam-gated on distinct concerns, not size — a uniform codemod, a rename, or one cohesive feature is a single reviewable unit however large and stays `Partial review only` — so the new verdict cannot cannibalize the ordinary `Partial` case. Verdict ordering is now `Blocked` > `Split required` > `Partial review only` > `Ship`, and a `Split Required Shape` example is added. The mutation-adequacy heuristic deepens the Step-3 test-adequacy check: judge tests by mutation rather than coverage — pick a plausible break in the changed logic that would change observable behavior (flip a boundary, negate or drop a condition, alter a constant, no-op a side effect) and ask whether some test would go red; a mutation that survives every test means the suite pins the code's presence, not its behavior, however high the line coverage, and that surviving mutation is named as the missing test. Built via the hand-author + 8-lens adversarial-review tier: the verdict-vs-redundant-with-`Partial` design question was attacked by two independent lenses and survived (the subtract/fold case was refuted on verification), every finding was default-to-refute verified, and a forward-test confirmed codemod / cohesive-large changes route to `Partial` while genuinely bundled diffs route to `Split required`. The byte-frozen read-only and bounded-review cores are unchanged, and routing metadata (`description`, `agents/openai.yaml`) is deliberately unchanged — the change is internal review behavior, not a new routing surface.

## 0.4.1 - 2026-06-28

### Added

- `scrutinize` gains a `steelman` handoff from its reject stance: when scrutiny rejects a contested *position, decision, or argument* (not a code or plan defect) that the user may still want to weigh, it now names `steelman` (or `$steelman`) as the advocacy counterpart that builds the strongest honest case *for* the rejected position. Closes the one-sided reference flagged as upgrade #12 in the 2026-06-26 capability-growth review — `steelman` already named `scrutinize` as its inverse (attack vs build), but `scrutinize` never pointed back. Additive prose only; it reinforces (does not change) scrutinize's attack-and-never-advocate boundary and read-only stop, and leaves the canonized read-only and bounded-review cores byte-identical.

## 0.4.0 - 2026-06-26

### Added

- `implementation-review` gains five surface-triggered review lenses folded inline into the existing Step-3 attack list (the resource-cap bullet is the template), each a terse "where the change touches X" conditional that deepens the review where a diff touches that surface and stays silent otherwise: performance (N+1 / unbounded fetch / super-linear work under ordinary load, fenced against the resource-cap exhaustion check), SQL and data access (injection as structure-not-bound-value plus query/migration footguns; deepens the trust-boundary base mode and routes injection into the existing attacker/victim test), concurrency (diff-introduced races / deadlocks / lost updates; deepens the state/concurrency base mode and hands static whole-codebase shared-state audits to `tech-debt-scan`), and accessibility (accessible name / keyboard operability / text alternatives / state-beyond-color on changed UI). Decided fold-over-standalone (zero new routing surface; rides the skill's existing fire-rate) and inline-over-reference-menu (a five-file dispatch menu was designed and rejected as over-machinery that manufactures a did-I-load-the-right-lens failure the inline form lacks). Routing metadata (`description`, `agents/openai.yaml`) deliberately unchanged.
- `implementation-review` gains a supply-chain provenance check for agent-authored diffs that introduce a new external dependency. It is grounded in provenance ("should this dependency belong?"), not resolution ("does it resolve?") — the latter is correctly left to CI and stays excluded — because a typosquatted or hallucinated package resolves cleanly once declared while its install-time code runs before any test. It defaults to silence for a spec-justified or already-used dependency, otherwise raises a non-blocking `note` routed to `/triage` for human supply-chain confirmation (never a malice claim from unfamiliarity, never a verdict-gating `unverified`), and where a safe read-only probe is cheap (registry age/downloads, edit-distance to a well-known name) cites it and lets the evidence set the severity via the existing model-as-attacker case. The line-106 resolution exclusion is unchanged but for a cross-reference distinguishing "does it resolve" (excluded) from "does it belong" (this check).
- `implementation-review` gains two guards against the lenses becoming a coverage ceiling: a "clean ≠ discharged" clause stating the lenses never replace the open hunt for the bespoke / business-logic / auth bug, and a Red Flag for running the lenses, finding nothing, and shipping without the open base-failure-mode attack. The Evidence Gate is unchanged — no per-lens checkbox, because the lenses are an honest depth pull, not a gate-enforced floor.

## 0.3.13 - 2026-06-21

### Added

- The three plugin reviewers (`implementation-review`, `scrutinize`, `system-design-review`) gain a findings→`triage` tail pointer, completing the family-wide set begun in the local-skill build (`tech-debt-scan`, `baseline`). Closes the Era-12 capability-growth review finding #5 connective-tissue gap — reviewers emitted findings/verdicts that died in chat with no tracker handoff. Each pointer names the trigger (a finding or verdict worth tracking rather than only living in the review), names the lane as `/triage` or `$triage` (dual-runtime tokens, one issue per finding classified there), and reaffirms the reviewer's own read-only/stop boundary — it does not open issues itself. Routes to `triage` (creates and classifies one issue per finding), not `to-issues` (which slices a plan/PRD, the wrong shape for ad-hoc review findings). The pointer does not change that reviewers stop — they are already read-only; it changes the default path when the user then asks to track findings, routing through triage's AI-disclaimer + maintainer-approval gate rather than ad-hoc tracker mutation. Lightweight name-the-lane pointer only (no "export findings" machinery); additive prose that leaves the canonized read-only and bounded-review cores byte-identical.

## 0.3.12 - 2026-06-21

### Added

- `implementation-review` now reads back an `acceptance-map` artifact as a first-class governing spec: the precondition spec-source list names "acceptance map", and the Requirements Ledger treats each acceptance check as a ready-made requirement (carry its check ID; treat its `Passes when` clause as the satisfaction criterion). Closes the one-directional wiring gap — `acceptance-map` already named `implementation-review` as its downstream verifier; the consumer now recognizes the producer's artifact. Self-guarding ("when the spec is an acceptance-map artifact"), no new ledger machinery, no dependency on `acceptance-map` being installed.

## 0.3.11 - 2026-06-18

### Changed

- Drift-detection across the five independently-loaded review skills (issue #11): the read-only / protected-action boundary and the bounded-review contract are normalized to a shared CORE carried verbatim inline by each skill, with per-skill riders and verdict vocabulary kept explicit. New `scripts/check-review-family.sh` asserts the read-only core across all 5 skills and the bounded-review core across the 3 adversarial skills (scrutinize, scrutinize-skill, implementation-review), wired into the SessionStart canary in both runtimes.
- `scrutinize-skill` is now reachable as a redirect target from `implementation-review`, `system-design-review`, and `review-reviewer` routing (previously only `scrutinize` named it).
- One unverified-marker token across the family: `review-reviewer`'s truth-verdict scale is now `confirmed` / `challenged` / `unverified` (was `needs-verification`) and `scrutinize`'s Assumptions-Audit evidence tag uses `unverified`; `review-reviewer`'s Current-Claim-Check ↔ truth-verdict cross-walk is removed. `system-design-review`'s `insufficient evidence` screening status is a distinct verdict scale and is left unchanged.

## 0.3.10 - 2026-06-15

### Added

- `scrutinize-skill`: apply the judgment-vs-trust bar. Two new failure modes (a judgment skill over-ruled into performing the contract; a judgment skill that provokes nothing or only weakly — a dulled or softened forcing function), a bar-classification step in the review workflow (judgment vs trust, per part for mixed skills), and severity-by-bar guidance. The distinction is single-sourced in `agent-facing-design` (`## Two Kinds of Skill`) and anchored in `AGENTS.md`. No skill class field — a lens applied per part.

## 0.3.9 - 2026-06-14

### Changed

- `scrutinize`: de-duplicate four cross-file drift hazards between `SKILL.md` and `references/review-format.md`. The citation/severity-calibration rule, the Adversarial Perspectives emit gate, the `Partial Review Only` + readiness-finding shape, and the no-numeric-confidence + combined stress-test/readiness rules were each maintained in both files, and several had already drifted (e.g. `High-Risk` vs `High`; `Adversarial Perspectives` vs `Adversarial Perspectives Applied`). Each rule is now single-homed in the always-loaded `SKILL.md` — unioning both copies' scope so nothing narrows — and the conditionally-loaded reference's restatements collapse to back-pointers. No behavior change: every obligation is preserved (verified by a 10-skeptic adversarial preservation pass). The reference's additive scaffolding (finding-field schemas, the Full Template and its sole-home normal-scrutiny verdict enum, the compress-don't-drop rule, the verdict fences, and the stress-test checklist) is untouched.

## 0.3.8 - 2026-06-14

### Changed

- `scrutinize-skill`: de-Codex the `agents/openai.yaml` companion. Its short_description and default_prompt named "Codex skills" / "a Codex behavior contract" while the runtime-neutral `SKILL.md` (and every sibling companion) reviews an "agent skill"; the companion now reads "agent skills" / "an agent behavior contract" to match.
- `review-reviewer`: de-duplicate the disposition list. The five dispositions (`act`/`narrow`/`reject`/`verify-first`/`defer`) were defined near-verbatim in both the Current Claim Check section and `Verdicts And Dispositions`, a drift hazard. The Current Claim Check section now references the single canonical definition in `Verdicts And Dispositions`; both modes and both output packets are otherwise unchanged.

## 0.3.7 - 2026-06-13

### Fixed

- `review-reviewer`: re-key the `Do Not Act On` output bucket on the `reject` disposition instead of the `Invalid` classification alone. A `Partially valid` claim dispositioned `reject` was previously homeless — not `Invalid` (so absent from Do Not Act On), not `act`/`narrow` (so absent from Act On Now), not `Unverified`, not `defer` — and fell through every action bucket. Keying on the disposition subsumes `Invalid` (always dispositioned `reject`) and captures the partially-valid rejects too.

## 0.3.6 - 2026-06-13

### Changed

- `implementation-review`: behavior-preserving lean pass over the accreted contract. Split the two run-on paragraphs in Attack Changed Areas into scannable bullet lists — the base failure modes plus the error-suppression, test-adequacy, comment-accuracy, and resource-cap checks; and the security attacker/victim refutation with its SSRF/data-exposure/agent-capability-gate carve-outs and the off-diff stricter bar — with no obligation text changed. Consolidated the two divergent per-finding field lists (Write Findings step vs Output Format) to a single superset (location, finding type, severity, and the rest), resolving a latent inconsistency where each list omitted a field the other required. No obligations added, removed, or weakened.

## 0.3.5 - 2026-06-13

### Added

- `implementation-review`: two security-review disciplines folded into Attack Changed Areas from the mined `security-guidance@claude-plugins-official` plugin (charter pass 10). (1) Resource-cap-defeat: report resource exhaustion only when a change defeats an existing size/time/count cap (wrong accumulator, dead timeout, unclamped arithmetic, amplification at flush), not for volumetric load alone. (2) Privilege-boundary refutation for security findings: name the attacker and victim, refute when attacker equals victim on their own machine/data, keep when impact reaches other users/tenants/shared infra, hold off-diff sinks to a stricter bar, and never apply attacker-equals-victim to SSRF/outbound sinks, data-exposure findings, or agent capability gates.

## 0.3.4 - 2026-06-13

### Added

- `implementation-review`: false-positive exclusions in Attack Changed Areas — apply the evidence burden to findings, not only to compliance. Folded from the mined `code-review@claude-plugins-official` plugin (charter pass 9): do not raise findings for correct code that resembles a bug, for linter/typechecker/compiler/CI-catchable issues, or for repo-instruction violations explicitly silenced in code.

## 0.2.0 - 2026-06-09

### Changed

- Unified the plugin source for Claude Code and Codex: single `.claude-plugin/plugin.json` manifest, canonical source at `~/.agents/plugins/review-family/`, runtime-neutral skill text that names both invocation token forms (`/skill` or `$skill`).

## Unreleased (pre-0.2.0)

### Added

- `scrutinize` formal stress-test guidance for explicit assumptions audits, pre-mortems, dimensional critiques, and confidence boundaries when requested or warranted by high-stakes targets.
- `scrutinize-skill` for adversarial review of Codex skills as behavior contracts, including skill-target routing from natural-language scrutiny requests, UX, composability, overlap, and proof gaps.
- Source package documentation for README, privacy notice, terms, and changelog.
- Source manifest readiness URLs for website, privacy policy, and terms of service. This is source metadata only, not installed runtime proof.

### Removed

- `adversarial-review` as a separate skill. Use `scrutinize` and ask for a formal stress test when the heavier review packet is needed.
- `pragmatic-review` as a separate skill. Use `scrutinize` and ask for an execution-readiness review when the question is whether a plan, spec, handoff, or rollout note is ready to implement.
- `review-claude-claims` as a separate skill. Use `review-reviewer` and ask it to check these claims when pasted review claims need current-evidence validation before action.
- `request-claude-pr-review` from Review Family. It was a prompt-drafting workflow helper, not a Codex-performed review or adjudication lane.

## 0.1.0 - 2026-05-29

### Added

- Initial Review Family Turbo Mode plugin source package.
- Bundled review skills: `adversarial-review`, `implementation-review`, `pragmatic-review`, `review-claude-claims`, `review-reviewer`, `request-claude-pr-review`, `scrutinize`, and `system-design-review`.
