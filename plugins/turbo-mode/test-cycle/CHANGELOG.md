# Changelog

All notable changes to the Test Cycle plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 2.0.0 - 2026-11-12

Applies the 2026-11 skill library audit (`/Users/jp/skill-audit-2026-11/VERDICTS.md`, plugin `test-cycle`). JP chose to apply every action on 2026-11-12.

### Removed

- `tdd`: the 5 reference files `tests.md`, `mocking.md`, `refactoring.md`, `interface-design.md`, and `deep-modules.md`, and the planning checklist that asked the user for 3 confirmations before any code. In the audit's test run 19 and in the 1 clear real session the model skipped those confirmations.

### Changed

- `tdd`: reduced from about 1,150 words to about 200. It keeps 3 rules: one test and then its code, never all tests first; watch every test fail before implementing; test through the public interface. It keeps the known-cause bug path and the pointer to `diagnose`.
- `diagnose`: reduced from about 2,970 words to about 1,200. It keeps the redaction rule, the non-software section with its safety boundary and triage, the rule to build a repeatable reproduction before any hypothesis or fix, the stop after about 3 failed fixes, and the search for the same defect elsewhere. The 6 phases, the list of 11 ways to build a loop, the flakiness table, the performance notes, and the emphatic lines are gone.
- `characterization-tests`: points to the `Acceptance checks` section of `implementation-planning`, because `acceptance-map` was removed in plan-cycle 2.0.0.

## 1.0.0 - 2026-11-02

### Added

- Initial packaging of six established skills (`diagnose`, `tdd`, `bug-epidemiology`, `keep-green`, `characterization-tests`, `test-trust-audit`) as one dual-runtime plugin, per the plugin bundles round 2 design (`docs/plans/2026-11-01-plugin-bundles-round-2.md` in the source repo), which was reviewed by a single-model scrutiny pass and a 2-round cross-model review with Codex. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move, which was a rename in one landing. Companions moved with their skills: `tdd`'s five reference documents, `diagnose`'s `references/` and `scripts/`, and every `agents/openai.yaml`.
