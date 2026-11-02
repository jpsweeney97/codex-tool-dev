# Changelog

All notable changes to the Pressure Test plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.0.0 - 2026-11-02

### Added

- Initial packaging of five established skills (`grill-me`, `assumption-check`, `premortem`, `red-team`, `steelman`) as one dual-runtime plugin, per the plugin bundles round 2 design (`docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo), which was reviewed by a single-model scrutiny pass and a 2-round cross-model review with Codex. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move, which was a rename in one landing. Each skill's `agents/openai.yaml` moved with it. The five claude.ai exports were repointed to the plugin paths with no change to their bodies. `grill-with-docs` stays standalone: it names no member of this plugin and carries the ADR format alias owned by `decide`.
