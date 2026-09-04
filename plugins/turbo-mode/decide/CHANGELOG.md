# Changelog

All notable changes to the Decide plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 2.2.1 - 2026-09-03

### Fixed

- `deliberate`'s Prune method defines the second label on a cut record: `fact-established` only when the cut's stated reason settles it without interpretation and only a changed constraint or a new fact could revive it; when the record's own `Revive if` names a different reading of the same facts, including one Prune says it cannot make, the cut is `judgment call`. Before, the record template offered the two labels and defined neither, and a Prune agent labeled a constraint cut `fact-established` while its own reason said the deciding question was a legal reading it could not make; the evidence later established the opposite reading, and the cut option was the run's winner (`docs/plans/2026-09-03-t2-known-answer-check/case-06/02-prune.md` in the source repo; issue #21 there). The label matters because the close delivers the cut ledger as a compact table of option, cut, and revive-if, so the label is the only evidence-status signal that reaches the user. Patch, not minor: no new capability; the label now matches what the record's own reason and revive condition disclose. It does not make Prune see a reading it does not see: forward-tested on the case-06 field, two Opus runs on this text, one labeled the cut `judgment call` with the reading in its `Revive if`, the other disclosed no reading and kept `fact-established`, consistent with its own record (`docs/smoke-tests/2026-09-03_deliberate-2.2.1-prune-label-forward-test.md` in the source repo).

## 2.2.0 - 2026-09-03

### Changed

- `deliberate`'s Contest method says what to do when the close adopts a cut option's substance under another wording: the cut stays live, the challenge is to the recorded cut rather than to the recommendation, and Contest names the cut in the existing positive line form; Contest decides whether the added option and the cut option are substantively the same. Before, the method left that case unstated, and a Contest agent read "live challenge" as "still excluded": a run whose Recommend stage re-added a wrongly cut winner under its own field rule delivered a cut ledger saying the option was cut on a constraint, a close recommending the same change, and an exclusion-check line silent about it (`docs/plans/2026-09-03-t2-known-answer-check/case-06/` in the source repo). The 2.0 rebuild dropped the 1.x rule that kept an active cut from reappearing at Recommend; the method now says what Contest does when that happens. The three line forms and the delivered ledger are unchanged.
- `deliberate` states the Recommend handoff in its own text: Recommend follows the live `making-recommendations` contract, which may add an option to the shaped field; its brief tells it to name each addition as added in `04-close.md`; Contest checks additions against the Prune cuts. Minor, not patch: the run's delivered output changes (a cut the close adopted is now named in the exclusion check), and Recommend's brief carries an instruction it did not carry before. Deliberated cross-model on 2026-09-03 (`~/.synapsis/runs/2026-09-03-contest-recovered-cut/`); no certificate was earned, and the repair text itself was never refused. Prune's `fact-established` labeling on a cut that rests on a reading it cannot make is a separate defect, tracked as issue #21 in the source repo.

## 2.1.0 - 2026-09-03

### Added

- `deliberate` honors a model name as plain-language steering ("use Sonnet for the stages" sets the stage model), and the setup shown before the first dispatch names the model the stages will run on.

### Changed

- On Claude Code, `deliberate` dispatches every stage agent with `model: opus` unless the user names a model; on another runtime it uses that runtime's subagent model setting. Before, stages inherited the session model, so a run from a Fable session put five long dispatches on Fable. Minor, not patch: a steering phrase the run did not honor before, and a changed default the user sees in the setup and can override.

## 2.0.0 - 2026-09-03

### Changed

- `deliberate` is rebuilt as a light orchestrator. It keeps the five stages (Generate, Prune, Shape, Recommend, Contest), the principle that no winner is manufactured and all four `making-recommendations` close shapes are successes, the Prune and Contest methods (trimmed, now inline in `SKILL.md`), the cut ledger with a reason and a revival condition for every excluded option, and fresh-agent stages that withhold the user's lean from Generate, Prune, and Shape while Recommend receives it under its own contract. Stage outputs are now six Markdown files in a scratch directory; they are the compaction defense and the re-run mechanism, and the user re-runs by naming in chat the cut to revive, the constraint to change, or the survivor to develop further. The skill is model-invocable again: `disable-model-invocation` is removed from the frontmatter and the matching `policy.allow_implicit_invocation: false` from `agents/openai.yaml`, so a plain request for a whole deliberation can reach it. Invocation is the decision in a sentence or a file plus optional candidates, constraints, and lean; the eight-field contract (field mode, survivor budget, evidence authorization, pasted capsule with directives) is gone, replaced by three plain-language steering phrases ("don't add options", "keep six", "you may research"). Major, not minor: the invocation contract and the output changed, and a 1.x re-run capsule is not accepted. Per the 2026-09-03 shape assessment (`docs/reviews/2026-09-03-deliberate-shape-assessment.md` in the source repo): seven weeks with zero runs on a real decision and one misfire, all fifteen lifetime defects in the machinery and none in the judgment stages, and the shallow-prune experiment inconclusive at 322 dispatches. First run of the rebuilt skill, same day, on a real open question: `docs/smoke-tests/2026-09-03_deliberate-2.0-first-smoke.md` in the source repo, passed, 45 minutes.
- PRIVACY and TERMS describe `deliberate`'s new on-disk footprint (six stage files under the scratch or temporary root, left in place, never under the working tree) in place of the 1.x run-state store that was trashed at close and the on-request capsule file, and TERMS no longer says the skill runs only on explicit invocation.

### Removed

- `deliberate`'s run-state store, bundled validator (`scripts/deliberate-validate.py`, `scripts/_deliberate_shared.py`, and fixtures), test suite, `references/contract-data.yaml`, and the four reference documents (`schemas.md`, `stage-packets.md`, `capsule.md`, `methods.md`). The re-run capsule, content-identity pins, drift terminals, containment checks, and model-provenance fields go with them. The 1.x bundle is preserved unchanged at `skills-archive/deliberate-v1/` in the source repo.

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
