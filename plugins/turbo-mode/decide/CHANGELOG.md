# Changelog

All notable changes to the Decide plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.3.0 - 2026-09-03

The fix batch from the 2026-09-03 gap review of `outcome-shaping` (`docs/reviews/2026-09-03-outcome-shaping-gap-review.md` in the source repo, every verdict in its companion `-verdicts.json`): 21 raw findings, 16 after dedup, 6 confirmed and all reproduced by blind proxy or by grep, 10 refuted. Three of the fixes were JP's decisions among options the record keeps. Every behavior fix was forward-tested against the patched text with the verifiers' own proxy prompts before landing: the re-price rule on Codex twice (the runtime where it failed), the flight case, the compaction case, and the option-shaping route on Sonnet. Minor, not patch: the lane gains an exit and an in-lane answer it could not give before; nothing is removed, and the calendar change narrows a permission rather than an interface.

### Added

- `outcome-shaping` gains the Exits row it was missing between `making-recommendations` and `ideate`: two or more options named but still sketch-level or uneven route to `option-shaping`, with the user asked to fix the candidate set first, since concretes the lane offered for reaction are the agent's probes, not the user's field. The lane could put such a field on the table itself and had nowhere to send it except a lane whose own contract bounces it; a blind run handed off to `making-recommendations` while noting the options were still one-line sketches. (F1)

### Changed

- `outcome-shaping` settle test: a restatement that carries content the read never held has added an unpriced part to the shape, and the lane prices it once before treating the restatement as settled, or carries it in the capsule marked unpriced. Before this, an own-words restatement that added content satisfied the settle conjunction while the new content bypassed the priced-trade invariant; reproduced twice on Codex, where the capsule then re-attributed the earlier price to the new content. The Own-Words Close example now shows the re-price. (F13)
- `outcome-shaping` flight case: when the user quits a hard trade and asks for a recommendation anyway, the lane answers in place as the priced values question with a lean labeled as a lean, never a pick, naming the skipped trade in the same turn. Core Behavior, Restraints, and the Flight Named Once example previously disagreed about what complying meant, and the example produced an unguarded settled pick in a blind run. Chosen over an unconditional hand-off to `making-recommendations`, whose field-readiness stop would bounce an unpriced collision straight back. (F4, JP's decision)
- `outcome-shaping` Core Behavior carries a compaction rule: when working from a summary rather than the user's actual sentences, say so, re-confirm the settled shape in their words before any capsule, and mark anything unsourceable as compression. Without it a post-compaction agent asserted "you confirmed this in your own words" over a summarizer's paraphrase and once fabricated a quoted attribution. First compaction clause in a conversational judgment skill in the source library; the rule sits in Core Behavior so skill-body truncation after compaction cannot drop it. (F10)
- `outcome-shaping`'s calendar witness is conditioned on the user pointing at it; the repo and the last three decisions stay unconditional witnesses. The prior grant authorized reading a personal calendar the user never named, which PRIVACY's read disclosure did not cover; a blind agent given a calendar tool treated the unprompted search as a normal in-lane move. (F15, JP's decision)
- `outcome-shaping` says what a user-requested brief is: the capsule, placed per repo convention with one path question if none is clear, left uncommitted for the user, matching `design-exploration`'s artifact rule. README's Writes row says the same. (F2, JP's decision)
- PRIVACY and TERMS disclose `outcome-shaping`'s on-request brief, so PRIVACY's "nothing else on disk" is true by the plugin's own contracts again, and both notices name the dated amendment section `decision-record` may add to an older record it narrows, which 1.2.0 introduced without updating either notice. PRIVACY's off-machine sentence no longer carries a path count to maintain. (F2)

## 1.2.0 - 2026-09-02

### Changed

- `decision-record`'s mutation boundary now names the one append it allows: where the repo's own ADR convention carries dated amendment or addendum sections on older records, a dated section pointing at the new record may be added to an older record where that convention places such sections; the existing text is never edited, and without such a convention the cross-reference stays in the new record's prose. The status bullet it qualifies names the same allowance, and the README's Writes row does too. Before this, "match the repo's existing ADR convention" and "a settled record's body is never rewritten" conflicted in any repo with that convention; the 2026-09-02 behavior trial (`docs/smoke-tests/2026-09-02_decision-record-first-real-fire.md` in the source repo, stage 2b) watched a fresh agent choose the convention and disclose the choice with no rule to cite, and the fold was tested against the same scenario before landing (stage 3 there). Minor, not patch: the skill may now append to an older record, which it could not do before. Deliberately not changed, parked with a reopen trigger in the source repo's `docs/agents/skill-lifecycle-notes.md`: the call between a new record that replaces an older one it restates (supersede) and one that narrows it (cross-reference).

## 1.1.0 - 2026-09-02

### Added

- `decision-record` joins the plugin from its standalone home at `skills/decision-record/`: capture an already-made decision from any source as a numbered ADR in `docs/adr/`, and on a reversal point the superseded record at its replacement. Skill body byte-unchanged except the one paragraph that named the format file's location; on Claude its token becomes `/decide:decision-record`, on Codex `$decision-record` keeps working. The ADR format it follows moves with it: `references/ADR-FORMAT.md` is now this plugin's shared reference (moved from `skills/grill-with-docs/ADR-FORMAT.md` in the source repo, history preserved), and the old path became a git-tracked symlink to it so the two standalone consumers there (`grill-with-docs`, `improve-codebase-architecture`) keep reading one file; a change to the format is now a release of this plugin. Per `docs/plans/2026-09-02-adr-format-home.md` and its cross-model deliberation certificate (`~/.synapsis/runs/2026-09-02-adr-format-home/`), which revised the 1.0.0 packaging decision that had left `decision-record` standalone because its format file could not cross the plugin boundary. Minor, not patch: the plugin delivers a skill it did not deliver before; no existing plugin skill changed, so nothing breaks.

## 1.0.0 - 2026-09-02

### Added

- Initial packaging of seven in-production decision skills (`outcome-shaping`, `ideate`, `option-shaping`, `making-recommendations`, `design-exploration`, `deliberate`, `scope-cut`) as one coherent dual-runtime plugin, per the 2026-09-02 plugin-bundle assessment (`docs/plans/2026-09-02-plugin-bundle-candidates.md` in the source repo) and its cross-model deliberation certificate, which settled the bundle at seven with `decision-record` and `decision-owner-map` left standalone. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move. Companion files moved with their skills: `agents/openai.yaml` for `outcome-shaping`, `option-shaping`, `making-recommendations`, and `deliberate`; the `examples/` of `outcome-shaping` and `making-recommendations` and the `references/` of `making-recommendations`; and `deliberate`'s five behavior references, bundled validator with its fixtures, and test suite. Built third and last in the settled order, after `relay` and `plan-cycle`.

### Changed

- `deliberate` re-run capsules minted before this release do not continue unchanged. Its constituent skills now resolve under this plugin's `skills/` directory, and the validator compares prior and current constituent pins as whole path-plus-identifier entries, so importing an older capsule classifies all three constituent pins as changed and restarts the re-run at Generate (Prune under `closed-to-widening`). Verified at packaging by importing the fixture capsule against the packaged validator with post-move pins carrying unchanged identifiers: earliest stage `generate`, three `constituent pin changed` reasons; the same import with pre-move pins reported no pin-derived restart, so the behavior is the pin comparison, not a validator change.
