# Changelog

All notable changes to the Plan Cycle plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.2.0 - 2026-09-22

### Added

- `execute-plan` keeps an execution record per run: a coordinator log with one dated entry per event (dispatches, review verdicts, rulings, verification runs quoted from their output, user decisions, plan-text corrections, divergences), with every time read from the clock or a file, plus per-task packets and reviewer files in subagent mode. The record is committed at the end of the run.
- `execute-plan` subagent mode may run tasks at the same time when neither depends on the other and they share no file, with one build or test run at a time through the coordinator.
- `execute-plan` subagent mode adds written reviewer instructions naming the points to check, a rulings file giving every finding fix now, record only, or after-plan (the last two with a written reason; a requirements gap is always fix now), and the coordinator's own rerun and full diff read before each task commit, run in a scratch copy of the last commit when another task has uncommitted changes.
- `execute-plan` adds three checks for particular cases in both modes: compare against a build of the last commit before the task when a result looks wrong, show a defect found by reading on the unchanged code before repairing it, and prove each new check with a deliberately broken copy that fails only that check.

### Changed

- `execute-plan` re-checks cited paths and line numbers against the current tree before each task, records plan-text corrections instead of editing the plan when the plan settles which part governs, and reports divergences, corrections, the after-plan list, and the record's path at completion.

## 1.1.0 - 2026-09-04

### Added

- Add explicit pull-request continuation to `implement-issue`, preserving contributor commits and routing completed work to the pull request's ask-gated publication flow.
- Add committed `docs/reconciliations/` direction records to `spec-drift-reconcile`, including resume lookup, per-artifact repair modes, and supersession as the default for forward-create-only artifacts.

### Changed

- Require approved category and state roles for issue slices, detect malformed triage roles, read tracker mutations back, and preserve partial multi-write progress for safe resumption.
- Bind plan-queue branches to plan rank and slug, check for existing issue work before implementation, commit verified plan tasks at task boundaries, condition optional companion routes on availability, and align the plugin documentation and triage templates with these contracts.

## 1.0.0 - 2026-09-02

### Added

- Initial packaging of nine in-production spec-to-execution skills (`to-prd`, `to-issues`, `acceptance-map`, `implementation-planning`, `execute-plan`, `implement-issue`, `triage`, `plan-queue`, `spec-drift-reconcile`) as one coherent dual-runtime plugin, per the 2026-09-02 plugin-bundle assessment (`docs/plans/2026-09-02-plugin-bundle-candidates.md` in the source repo) and its cross-model deliberation certificate. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move. `triage` ships its two companion files (`AGENT-BRIEF.md`, `OUT-OF-SCOPE.md`) and `acceptance-map` its `agents/openai.yaml`; the protected-set drift check in the source repo now reads `acceptance-map` at its plugin path. Built second, after `relay`, in the settled order.
