# Changelog

All notable changes to the Review Family plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
