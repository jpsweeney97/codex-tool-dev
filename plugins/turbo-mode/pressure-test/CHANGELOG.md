# Changelog

All notable changes to the Pressure Test plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.1.0 - 2026-11-12

Applies the 2026-11 skill library audit (`/Users/jp/skill-audit-2026-11/VERDICTS.md`, plugin `pressure-test`). JP chose to apply every action on 2026-11-12.

### Changed

- `assumption-check`: a cheap, read-only local probe is now run and reported. Before, every probe waited for the user to ask, which disagreed with JP's standing rule to verify when a check is cheap.
- `red-team`: when the target is a repository, the skill reads the code the attack paths run through. Before, it "never greps secrets or inspects a repo". It still does not sweep a repository for secrets.
- `red-team`: attack paths on a designable surface are stated as must-deny or must-block rows in the reply. The hand-off to `authorization-design` and `injection-safe-inputs` is gone, because both skills were removed from the library.
- `premortem`: no longer names `deploy-plan`, which was removed from the library.

## 1.0.0 - 2026-11-02

### Added

- Initial packaging of five established skills (`grill-me`, `assumption-check`, `premortem`, `red-team`, `steelman`) as one dual-runtime plugin, per the plugin bundles round 2 design (`docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo), which was reviewed by a single-model scrutiny pass and a 2-round cross-model review with Codex. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move, which was a rename in one landing. Each skill's `agents/openai.yaml` moved with it. The five claude.ai exports were repointed to the plugin paths with no change to their bodies. `grill-with-docs` stays standalone: it names no member of this plugin and carries the ADR format alias owned by `decide`.
