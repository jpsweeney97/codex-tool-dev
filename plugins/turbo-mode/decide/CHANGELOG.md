# Changelog

All notable changes to the Decide plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.1.0 - 2026-09-02

### Added

- `decision-record` joins the plugin from its standalone home at `skills/decision-record/`: capture an already-made decision from any source as a numbered ADR in `docs/adr/`, and on a reversal point the superseded record at its replacement. Skill body byte-unchanged except the one paragraph that named the format file's location; on Claude its token becomes `/decide:decision-record`, on Codex `$decision-record` keeps working. The ADR format it follows moves with it: `references/ADR-FORMAT.md` is now this plugin's shared reference (moved from `skills/grill-with-docs/ADR-FORMAT.md` in the source repo, history preserved), and the old path became a git-tracked symlink to it so the two standalone consumers there (`grill-with-docs`, `improve-codebase-architecture`) keep reading one file; a change to the format is now a release of this plugin. Per `docs/plans/2026-09-02-adr-format-home.md` and its cross-model deliberation certificate (`~/.synapsis/runs/2026-09-02-adr-format-home/`), which revised the 1.0.0 packaging decision that had left `decision-record` standalone because its format file could not cross the plugin boundary. Minor, not patch: the plugin delivers a skill it did not deliver before; no existing plugin skill changed, so nothing breaks.

## 1.0.0 - 2026-09-02

### Added

- Initial packaging of seven in-production decision skills (`outcome-shaping`, `ideate`, `option-shaping`, `making-recommendations`, `design-exploration`, `deliberate`, `scope-cut`) as one coherent dual-runtime plugin, per the 2026-09-02 plugin-bundle assessment (`docs/plans/2026-09-02-plugin-bundle-candidates.md` in the source repo) and its cross-model deliberation certificate, which settled the bundle at seven with `decision-record` and `decision-owner-map` left standalone. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move. Companion files moved with their skills: `agents/openai.yaml` for `outcome-shaping`, `option-shaping`, `making-recommendations`, and `deliberate`; the `examples/` of `outcome-shaping` and `making-recommendations` and the `references/` of `making-recommendations`; and `deliberate`'s five behavior references, bundled validator with its fixtures, and test suite. Built third and last in the settled order, after `relay` and `plan-cycle`.

### Changed

- `deliberate` re-run capsules minted before this release do not continue unchanged. Its constituent skills now resolve under this plugin's `skills/` directory, and the validator compares prior and current constituent pins as whole path-plus-identifier entries, so importing an older capsule classifies all three constituent pins as changed and restarts the re-run at Generate (Prune under `closed-to-widening`). Verified at packaging by importing the fixture capsule against the packaged validator with post-move pins carrying unchanged identifiers: earliest stage `generate`, three `constituent pin changed` reasons; the same import with pre-move pins reported no pin-derived restart, so the behavior is the pin comparison, not a validator change.
