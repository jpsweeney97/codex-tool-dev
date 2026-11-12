# Changelog

All notable changes to the Change Cycle plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 2.0.0 - 2026-11-12

Applies the 2026-11 skill library audit (`/Users/jp/skill-audit-2026-11/VERDICTS.md`, plugin `change-cycle`). JP chose to apply every action on 2026-11-12.

### Removed

- `add-an-x-by-example`: the skill is gone. In the audit's test run 12 a session without the skill touched all 5 places that the earlier commands touched, and the skill added a checklist block that restated them. The usage ledger shows 1 Claude load and 8 Codex reads. `co-change-radar`, the manifest, the README, and `PRIVACY.md` no longer name it.

## 1.0.0 - 2026-11-02

### Added

- Initial packaging of four established skills (`co-change-radar`, `add-an-x-by-example`, `contract-change-propagation`, `migration-campaign`) as one dual-runtime plugin, per the plugin bundles round 2 design (`docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo), which was reviewed by a single-model scrutiny pass and a 2-round cross-model review with Codex. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move, which was a rename in one landing. Each skill's `agents/openai.yaml` moved with it. No member has a claude.ai export.
