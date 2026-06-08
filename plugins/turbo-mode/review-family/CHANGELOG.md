# Changelog

All notable changes to the Review Family plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

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

## 0.1.0 - 2026-05-29

### Added

- Initial Review Family Turbo Mode plugin source package.
- Bundled review skills: `adversarial-review`, `implementation-review`,
  `pragmatic-review`, `review-claude-claims`, `review-reviewer`,
  `request-claude-pr-review`, `scrutinize`, and `system-design-review`.
