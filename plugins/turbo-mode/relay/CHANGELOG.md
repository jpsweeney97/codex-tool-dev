# Changelog

All notable changes to the Relay plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.1.0 - 2026-10-21

### Changed

- `stage-prompt` copies the staged prompt file to the clipboard with `pbcopy` every time, without asking, and reports the copy in a new `Copied:` output line, so the user pastes it into the fresh session without opening `~/prompts`.
- `stage-prompt` writes the commission body only: the title line, paste instruction, and `---` separator are gone, because the whole file is pasted straight into the fresh session and the filename already records the date, target, and subject.

## 1.0.0 - 2026-09-02

### Added

- Initial packaging of three in-production hand-carry skills (`courier`, `relay-by-reference`, `stage-prompt`) as one coherent dual-runtime plugin, per the 2026-09-02 plugin-bundle assessment (`docs/plans/2026-09-02-plugin-bundle-candidates.md` in the source repo) and its cross-model deliberation certificate. Version 1.0.0 reflects established skills, not new ones; no skill body changed in the move. The three were chosen as the first bundle because they are the smallest, lowest-churn migration on which to prove the packaging procedure.
