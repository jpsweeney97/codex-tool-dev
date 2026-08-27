# Changelog

All notable changes to the Review Family plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.16.0 - 2026-08-27

### Changed

- `system-design-review` conditions its verdict license (gap review 2026-08-26, finding 12; decision D6, option 1 — the report's lean). "End with 2-4 sharp questions, not a verdict, unless requested" carried the only verdict mention in the whole skill — no enum, severity scale, clearance condition, or verdict slot in either output contract — licensing the skill to answer in chat what its own routing block sends to `scrutinize`, worst under the `reduced-depth` path where sparse evidence caps findings but nothing barred an unscoped clearance answer. The license is now conditioned: a requested readiness or pass/fail call routes to `scrutinize`; a requested design-soundness judgment is answered here in the reference's decision states. This preserves the no-verdict design while fixing the verifier's objection to a blunter routing-only draft — the in-scope list leads with decision quality, so "does this design hold up?" is squarely in scope and must not route away. Companion surfaces carry no verdict vocabulary and are unchanged. Minor, not patch: the review contract changed behavior on a request class it previously left unbounded. Forward-tested with two fresh `claude -p` trials against the new text: "pass or fail — is this ready to build from?" was routed to `scrutinize` with no verdict rendered here; "does this design hold up?" was answered in place through the decision states with no misroute and no invented clearance token.

## 0.15.1 - 2026-08-27

### Fixed

- `scrutinize`'s description routes "pragmatic review" requests (gap review 2026-08-26, finding 9; decision D5, the report's lean). `pragmatic-review` was retired pre-0.2.0 with its replacement — `scrutinize`'s execution-readiness mode — documented only in README, a surface neither runtime reads at skill selection, and the review reproduced the gap: "Run a pragmatic review of this plan" fired no skill at all (2/2) while the execution-readiness control fired `scrutinize`. The description now reads "a pragmatic or execution-readiness review", bound so the phrase inherits the execution-readiness sense rather than reading as practical-and-proportionate feedback — the misroute the verifier flagged — with the existing "balanced feedback" non-use keeping that boundary; companion surfaces carry no pragmatic terms and are unchanged. Patch, not minor: routing wording for behavior the skill already had. Forward-tested twice: a pre-land routing proxy over the five family descriptions (pragmatic → `scrutinize`, execution-readiness control → `scrutinize`, proportionate-feedback → none), and the report's own single-variable test live post-land — "Run a pragmatic review of the plan in plan.md" fired `review-family:scrutinize` in 2/2 fresh `claude -p` sessions.

## 0.15.0 - 2026-08-27

### Changed

- `implementation-review` governs the re-reviews it mandates (gap review 2026-08-26, finding 5; decision D4, the report's lean). A new `Re-Review` section names the second passes the verdicts themselves create — `Blocked` → fix → second pass, `Split required` → restructure → re-review per split unit, or any requested second look — and fixes the cross-pass discipline: a re-review is a fresh evidence pass over the live artifact, not an audit of the fix description; claimed fixes are verified against the artifact and its diff; prior findings and ledger rows are hypotheses to re-earn, and a `satisfied` row carried forward keeps its status only after its code evidence is re-verified against the live artifact, reverting to `unverified` when the evidence no longer holds — closing the hole where a fix commit moves or invalidates the lines a pass-1 row cites while the spec-derived ledger looks complete either way; the pass hunts defects the fix introduced and credits what held. Evidence Gate item 2 defers to the section for carried-forward rows instead of restating it. Scoped per the report: no `scrutinize-skill` change (0.9.0's route to `behavior-smoke-test` stands) and no `system-design-review` change. Minor, not patch: the review contract changed behavior. Forward-tested with three fresh `claude -p` trials against the new text: a stale carried row whose cited lines a "tidy" fix commit had moved and broken was re-earned against the live artifact and flipped to `violated` (`Blocked`, blocker count 1); a clean-carry control kept `satisfied` only after re-earning it with a live evidence pointer (blocker count 0); the first control run's fixture carried an unintended defect, which the trial reviewer correctly caught by the same rule before the repaired fixture re-ran.

## 0.14.0 - 2026-08-27

### Changed

- `scrutinize` and `scrutinize-skill` anchor their verdict expiry (gap review 2026-08-26, finding 4; decision D3). `Target And Evidence` and `Target And Surface` now require the anchor the verdict binds to — commit, version, or date, stated explicitly when none is determinable — the datum by which a later reader can tell whether the artifact has changed since a clearance verdict that "expires when the artifact changes" was rendered; previously the expiry was declared with no datum by which anyone could judge it. `scrutinize-skill` is included beyond the report's D3 lean because 0.12.0 canonised the same expiry gloss into it, creating the same anchorless-expiry defect there. `references/review-format.md`'s Target And Evidence template placeholder is aligned. Minor, not patch: the verdict contract changed behavior.
- `review-reviewer` step 5 closes its unpinned non-PR hole (finding 4, second half): for a review naming no commit, version, or date, attempt snapshot recovery from available non-mutating evidence — git history, document version markers, and any anchor the review itself records — and if the snapshot stays unrecoverable, defer to the snapshot-unavailable rule in `Verdicts And Dispositions` (historical truth claims stay `unverified`; current evidence informs only the disposition) instead of leaving the case to inference. Forward-tested with two fresh `claude -p` trials against the new text: a git-target scrutiny recorded the commit anchor unprompted and a pasted memo stated none determinable; an unpinned non-PR claim rendered `unverified` with a current-state-only disposition.

## 0.13.0 - 2026-08-27

### Changed

- `implementation-review` resolves its bounded-mode blocker conflict (gap review 2026-08-26, finding 2; decision D2, option 1 — qualify the severity, keep the precedence). The `blocker` severity is qualified: a requirement unverified only because bounded review mode omitted it from the reviewed subset carries `unverified` status (in the ledger and `Unverified Areas`), not a `blocker` finding — closing the route by which the unqualified clause manufactured blockers from omissions and reached `Blocked` around the verdict enum's deliberate "in a full review" qualification. The precedence line gains the carve-out — a `blocker` found in the reviewed slice of a bounded pass renders `Blocked`, scoped to the slice, and is never hidden behind an incomplete-pass label — and the Output Format bounded line and the bounded-mode section now defer to the precedence order instead of mandating `Partial review only` unconditionally, mirroring 0.12.0's D1 form in `scrutinize`. `examples/review-findings.md`'s Bounded Review Shape re-teaches both branches: omission-only renders blocker count 0 / `Partial review only` (it previously taught blocker count 1 under `Partial review only`, a state the precedence order forbids); a genuine in-slice blocker renders `Blocked` scoped to the slice. Minor, not patch: the verdict contract changed behavior. Forward-tested with two fresh `claude -p` trials against the new text: an in-slice blocker rendered `Blocked` scoped to the slice with the omissions explicitly not counted as blockers; an omission-only pass rendered `Partial review only` with blocker count 0.

## 0.12.0 - 2026-08-27

### Changed

- `scrutinize` resolves its bounded ordinary verdict (gap review 2026-08-26, finding 1; decision D1, option 1 — mirror `implementation-review`). `Partial review only` joins the ordinary enum at last, with its definition (bounded review mode was used: the reviewed subset was judged, the full target was not) and a precedence order — `Reject`, `Major revision`, `Partial review only`, `Minor revision`, `Defensible` — so a disqualifying finding in the reviewed slice renders its verdict, scoped to the slice, and is never hidden behind an incomplete-pass label; the readiness enum gains the matching precedence order (`Not Executable Yet`, `Patch Before Implementation`, `Partial Review Only`, `Ready to Execute`); the Output line's unconditional "write `Verdict: Partial review only`" becomes the carve-out form, and the bounded-mode guardrail points at the precedence orders instead of resolving the question a third way. This closes the suppression path where a Critical in-slice finding was relabeled as an incomplete pass — the review's 8/8 live trials showed the old text ordered exactly that. `references/review-format.md`'s verdict fence carries the fifth token. Minor, not patch: the verdict contract changed behavior. Forward-tested with two fresh `claude -p` trials against the new text: Critical-in-slice rendered `Reject` scoped to the slice; a Low-only bounded pass rendered `Partial review only`.
- `scrutinize-skill` states the `Defensible` scope-and-expiry gloss inline (finding 6): a clearance verdict claims serious search was exhausted without a disqualifying find — it does not certify soundness, and it expires when the artifact changes. The skills load independently, so the definition must travel with the enum; previously only `scrutinize` carried it. `implementation-review`'s `Ship` stays exempt per refutation 11 — its target is snapshot-identified by construction.
- `check-review-family.sh` (repo-side canary, not shipped in the plugin) gains a third CANON block asserting the shared expiry gloss across the two `Defensible` skills, and a within-skill check that every `###` heading `review-format.md`'s templates emit is declared in `scrutinize`'s `SKILL.md` — the drift class 0.11.1 repaired by hand. Verdict enums themselves stay per-skill by design and are not canonised; both new detectors were negative-tested (doctored gloss and bogus heading each fail the check).

## 0.11.1 - 2026-08-27

### Fixed

- Documentation and metadata repairs from the 0.11.0 gap review (`docs/reviews/2026-08-26-review-family-gap-review.md` — five review dimensions over all twenty surfaces, one refute-default adversarial verifier per finding, 14 confirmed of 28). No skill behavior contract changed: both CANON cores, all five frontmatter descriptions, every verdict vocabulary, and `plugin.json`'s starter list are deliberately untouched. Four items. (1) README's `review-reviewer` Trigger cell now leads with the explicit-only invocation gate it was the sole surface omitting (finding 7); the Description cell at `:29` is left alone, because it makes no firing claim. (2) `PRIVACY.md` and `TERMS.md` de-Codexed at exactly the four defective mentions, with `plugins/git-cycle` as the neutral wording model (finding 8); `PRIVACY` para 1 and `TERMS` para 1 stay verbatim, because only Codex has a versioned install cache and neutralizing those would assert a falsehood. (3) `scrutinize`'s `references/review-format.md` Full Template now emits the nine section names `SKILL.md:80` declares, with the dropped scope moved into each bracketed gloss (finding 10) — single-sourcing hygiene against dual-maintenance staleness, not a routing fix, since nothing string-matches these headings. (4) `scrutinize-skill`'s `agents/openai.yaml` starter prompt gains its `$` token, the sole outlier among all 34 `default_prompt` values across the repo, and README's usage examples at `:50` and `:78` likewise (finding 11); `plugin.json`'s starter list is untouched, because four of its six entries are bare by design and only `review-reviewer`'s two carry a token — tracking that it is explicit-only and unreachable by natural language.

### Removed

- Four stray `.DS_Store` files from the source tree (plugin root, `skills/`, `skills/scrutinize/`, `skills/system-design-review/`). They were gitignored and untracked, so git history is unaffected, but `codex plugin add` had copied them into the install cache; this release's republish clears them from it.

## 0.11.0 - 2026-07-18

### Added

- `review-reviewer` gains ownership of its own success, briefed by the methodology-and-philosophy critique at `docs/reviews/2026-07-18-review-reviewer-methodology-critique.md` (the arc's fourteenth hold, sixteenth treatment, on its second-largest corpus — ~150 fires across 145 sessions, seven venues, both runtimes; the critique found the stance, the three-lane evidence discipline, the packet, and the explicit-only boundary earning their keep, and the defect one meta-level up: the Review Judgment's knowledge-claim outruns its method, the packet authors its own authorization, and the discipline's observed boundary failures were unnamed). Six repairs, honesty and naming, no new machinery: (1) the Review Judgment scoped as a fact about this adjudication's bounded search at this snapshot — it expires when the target or review moves, and `reliable` does not certify that nothing was missed — with the label-follows-findings rule (a confirmed materially missed issue or a wrong load-bearing claim caps the review at `partially reliable`); (2) the packet owns its own fallibility — the adjudication is a single-pass argued judgment, and Missed Issues are bounded-hunt results, not exhaustive clearance; (3) Recommended Next Step written as the executable work order the record shows it becomes — carrying the Verification Gaps that gate action, with the honest no-action null blessed; (4) self-authorship named in the anchoring vocabulary — the fires' own invented disclosure ("the conflict runs deeper than anchoring") given residence, with declared extra skepticism on Missed-Issues absence claims; (5) the loop-momentum packet obligation — a token-present round in a multi-round adjudication loop still owes the selected packet, and skipping it deliberately must be said aloud; (6) the fires' convergent snapshot-coincidence check blessed as the commit-pinned non-PR default, canonical backticked-lowercase judgment labels, and empty Current Claim Check buckets stated rather than omitted. The frontmatter description, both CANON cores (read-only core byte-identical, `check-review-family.sh` green), packet order, verdict vocabularies, two-packet split, explicit-only boundary, and `agents/openai.yaml` are all deliberately unchanged. Validated by the structural ladder plus seven blind Sonnet proxy probes (one per changed instrument, plus the bucket rule): 7/7 quoted-clause passes — uptake evidence only; the expiry clause remains untested by proxy.

## 0.10.0 - 2026-07-16

### Added

- `scrutinize` gains a continued-investment handoff on re-scrutiny: when a valid re-scrutiny finding opens a new structural repair class, mainly polices machinery earlier repairs added, or would change the target's category, the re-scrutiny paragraph now names `recheck-investment` (where available) as the next move before prescribing another hardening cycle — this review keeps owning whether the finding is real; that check owns only whether continued investment needs renewed human authorization. One sentence appended to the re-scrutiny paragraph; both CANON cores, routing frontmatter, verdict vocabulary, and every other organ unchanged. The seam is slice 2 of the `recheck-investment` caller integrations (the skill born from the cross-model slim-control retirement, that repo's ADR-0034), landed alongside the sibling `plan-panel-loop` seam and behavior-proven by a blind five-fixture proxy suite (machinery-policing re-scrutiny routes; an ordinary unfixed defect does not). This release is the authorized publish: the Codex cache moves 0.9.0 → 0.10.0, folding in 0.9.1's deferred conciseness campaign and clearing the standing expected `DRIFT`.

## 0.9.1 - 2026-07-13

### Changed

- Conciseness campaign (2026-07-13 audit dispositions), obligation-preserving refactor. `implementation-review`: the nine surface-lens protocols move to `references/review-lenses.md` behind a mandatory load trigger at the attack step, leaving a one-line-per-lens index; Evidence Gate items now name and reference their owning sections instead of restating them, and the Ship gate points to Verdict Taxonomy for the `Ship` conditions (body 3,368 → 2,752 words). All five skills compress Review-Family Routing to a wins-statement plus one-line redirects (766 → 490 words family-wide; each deleted bullet's unique scope carried into its surviving home — `review-reviewer`'s packet-selection rule single-homed in Boundaries, gaining "stale"); `scrutinize`'s steelman handoff tightened. No trigger, verdict-vocabulary, CANON-core, or proof-discipline changes; frontmatter untouched; `check-review-family.sh` green. Publish deferred until explicitly authorized; the Codex cache stays at 0.9.0 and `codex-plugins-sync.sh --check` reporting DRIFT is the expected state.

## 0.9.0 - 2026-07-12

### Added

- `scrutinize-skill` gains a post-review handoff exit: when a review's required changes have been applied and the open claim becomes "the changed contract is now followed," the Output section now routes proving that to `behavior-smoke-test` (`/behavior-smoke-test` or `$behavior-smoke-test` where available) instead of a re-review. One paragraph in the Output section, seeded as part of the skill-use composition data layer (design: `docs/plans/2026-07-11-skill-use-contract-design.md`, §2); both CANON cores, routing frontmatter, verdict vocabulary, and every other organ unchanged. Class-B publish (Codex republish, mirror) deferred until explicitly authorized; until then the Codex cache stays at 0.8.0 and `codex-plugins-sync.sh --check` reporting `NOT-INSTALLED: review-family@0.9.0` is the expected state.

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
