# Changelog

All notable changes to the Review Family plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.3.9 - 2026-06-14

### Changed

- `scrutinize`: de-duplicate four cross-file drift hazards between `SKILL.md`
  and `references/review-format.md`. The citation/severity-calibration rule, the
  Adversarial Perspectives emit gate, the `Partial Review Only` + readiness-finding
  shape, and the no-numeric-confidence + combined stress-test/readiness rules were
  each maintained in both files, and several had already drifted (e.g. `High-Risk`
  vs `High`; `Adversarial Perspectives` vs `Adversarial Perspectives Applied`).
  Each rule is now single-homed in the always-loaded `SKILL.md` — unioning both
  copies' scope so nothing narrows — and the conditionally-loaded reference's
  restatements collapse to back-pointers. No behavior change: every obligation is
  preserved (verified by a 10-skeptic adversarial preservation pass). The
  reference's additive scaffolding (finding-field schemas, the Full Template and
  its sole-home normal-scrutiny verdict enum, the compress-don't-drop rule, the
  verdict fences, and the stress-test checklist) is untouched.

## 0.3.8 - 2026-06-14

### Changed

- `scrutinize-skill`: de-Codex the `agents/openai.yaml` companion. Its
  short_description and default_prompt named "Codex skills" / "a Codex behavior
  contract" while the runtime-neutral `SKILL.md` (and every sibling companion)
  reviews an "agent skill"; the companion now reads "agent skills" / "an agent
  behavior contract" to match.
- `review-reviewer`: de-duplicate the disposition list. The five dispositions
  (`act`/`narrow`/`reject`/`verify-first`/`defer`) were defined near-verbatim in
  both the Current Claim Check section and `Verdicts And Dispositions`, a drift
  hazard. The Current Claim Check section now references the single canonical
  definition in `Verdicts And Dispositions`; both modes and both output packets
  are otherwise unchanged.

## 0.3.7 - 2026-06-13

### Fixed

- `review-reviewer`: re-key the `Do Not Act On` output bucket on the `reject`
  disposition instead of the `Invalid` classification alone. A `Partially valid`
  claim dispositioned `reject` was previously homeless — not `Invalid` (so absent
  from Do Not Act On), not `act`/`narrow` (so absent from Act On Now), not
  `Unverified`, not `defer` — and fell through every action bucket. Keying on the
  disposition subsumes `Invalid` (always dispositioned `reject`) and captures the
  partially-valid rejects too.

## 0.3.6 - 2026-06-13

### Changed

- `implementation-review`: behavior-preserving lean pass over the accreted
  contract. Split the two run-on paragraphs in Attack Changed Areas into
  scannable bullet lists — the base failure modes plus the error-suppression,
  test-adequacy, comment-accuracy, and resource-cap checks; and the security
  attacker/victim refutation with its SSRF/data-exposure/agent-capability-gate
  carve-outs and the off-diff stricter bar — with no obligation text changed.
  Consolidated the two divergent per-finding field lists (Write Findings step vs
  Output Format) to a single superset (location, finding type, severity, and the
  rest), resolving a latent inconsistency where each list omitted a field the
  other required. No obligations added, removed, or weakened.

## 0.3.5 - 2026-06-13

### Added

- `implementation-review`: two security-review disciplines folded into Attack
  Changed Areas from the mined `security-guidance@claude-plugins-official`
  plugin (charter pass 10). (1) Resource-cap-defeat: report resource exhaustion
  only when a change defeats an existing size/time/count cap (wrong accumulator,
  dead timeout, unclamped arithmetic, amplification at flush), not for volumetric
  load alone. (2) Privilege-boundary refutation for security findings: name the
  attacker and victim, refute when attacker equals victim on their own
  machine/data, keep when impact reaches other users/tenants/shared infra, hold
  off-diff sinks to a stricter bar, and never apply attacker-equals-victim to
  SSRF/outbound sinks, data-exposure findings, or agent capability gates.

## 0.3.4 - 2026-06-13

### Added

- `implementation-review`: false-positive exclusions in Attack Changed Areas —
  apply the evidence burden to findings, not only to compliance. Folded from the
  mined `code-review@claude-plugins-official` plugin (charter pass 9): do not
  raise findings for correct code that resembles a bug, for
  linter/typechecker/compiler/CI-catchable issues, or for repo-instruction
  violations explicitly silenced in code.

## 0.2.0 - 2026-06-09

### Changed

- Unified the plugin source for Claude Code and Codex: single
  `.claude-plugin/plugin.json` manifest, canonical source at
  `~/.agents/plugins/review-family/`, runtime-neutral skill text that names
  both invocation token forms (`/skill` or `$skill`).

## Unreleased (pre-0.2.0)

### Added

- `scrutinize` formal stress-test guidance for explicit assumptions audits,
  pre-mortems, dimensional critiques, and confidence boundaries when requested
  or warranted by high-stakes targets.
- `scrutinize-skill` for adversarial review of Codex skills as behavior
  contracts, including skill-target routing from natural-language scrutiny
  requests, UX, composability, overlap, and proof gaps.
- Source package documentation for README, privacy notice, terms, and changelog.
- Source manifest readiness URLs for website, privacy policy, and terms of
  service. This is source metadata only, not installed runtime proof.

### Removed

- `adversarial-review` as a separate skill. Use `scrutinize` and ask for a
  formal stress test when the heavier review packet is needed.
- `pragmatic-review` as a separate skill. Use `scrutinize` and ask for an
  execution-readiness review when the question is whether a plan, spec, handoff,
  or rollout note is ready to implement.
- `review-claude-claims` as a separate skill. Use `review-reviewer` and ask it
  to check these claims when pasted review claims need current-evidence
  validation before action.
- `request-claude-pr-review` from Review Family. It was a prompt-drafting
  workflow helper, not a Codex-performed review or adjudication lane.

## 0.1.0 - 2026-05-29

### Added

- Initial Review Family Turbo Mode plugin source package.
- Bundled review skills: `adversarial-review`, `implementation-review`,
  `pragmatic-review`, `review-claude-claims`, `review-reviewer`,
  `request-claude-pr-review`, `scrutinize`, and `system-design-review`.
