# Acceptance Map: Handoff Skill-Only Redesign

Source: [2026-06-09-handoff-skill-only-redesign.md](2026-06-09-handoff-skill-only-redesign.md)
Authority: Derived companion unless explicitly promoted
Outcome: Handoff source is replaced by a three-skill Markdown-only bundle, with runtime machinery and retired entry points removed, and with closeout proof bounded to source shape rather than installed runtime behavior.

## Check Index

| ID | Acceptance Check | Basis | Decision Gap |
| -- | ---------------- | ----- | ------------ |
| A1 | Approved source inventory only | source-backed | none |
| A2 | Retired source surfaces removed | source-backed | none |
| A3 | Plugin metadata advertises only save, load, and search | source-backed | none |
| A4 | Current-facing docs state skill-only behavior and proof boundaries | source-backed | none |
| A5 | Save skill writes direct Markdown handoffs without helper state | source-backed | none |
| A6 | Load skill is read-only and reality-checks before action | source-backed | none |
| A7 | Search skill delegates to read-only `rg` search | source-backed | none |
| A8 | Format reference is minimal and evidence-bounded | source-backed | none |
| A9 | Source-contract verification passes | source-backed | none |
| A10 | Retired concepts have no positive current-facing instructions | source-backed | none |
| A11 | Adjacent references are inspected without expanding source scope | source-backed | none |
| A12 | Git hygiene and final report preserve source/runtime proof separation | source-backed | none |

## Acceptance Checks

### A1. Approved Source Inventory Only

Passes when:
`plugins/turbo-mode/handoff/` contains exactly the approved skill-only file and directory shape: plugin JSON, README, privacy, terms, license, three skill directories with display-name-only agent metadata, and `references/handoff-format.md`.

Evidence to inspect:
- `find plugins/turbo-mode/handoff -maxdepth 3 -type d -o -type f | sort`
- The source-contract inventory check output: `handoff skill-only source contract ok`
- `git diff -- plugins/turbo-mode/handoff`

Verification ideas:
- Run the plan's source-contract check and confirm both `expected_files` and `expected_dirs` match the final tree.
- Inspect `git diff --stat -- plugins/turbo-mode/handoff` for only the intended replacements, additions, and deletions.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 21-56, 79-158, 987-1081

Non-goals:
This check does not prove the plugin is installed, enabled, cached, or loaded in the current Codex runtime.

### A2. Retired Source Surfaces Removed

Passes when:
The runtime package, scripts, hooks, tests, old package files, old reference docs, save synthesis guide, and retired skill directories are gone from Handoff source.

Evidence to inspect:
- `git status --short plugins/turbo-mode/handoff`
- `git diff --name-status -- plugins/turbo-mode/handoff`
- The source-contract inventory check output

Verification ideas:
- Confirm deleted paths include `turbo_mode_handoff_runtime/`, `scripts/`, `hooks/`, `tests/`, `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `CONTRIBUTING.md`, old reference docs, `skills/distill/`, `skills/quicksave/`, and `skills/save-summary/`.
- Confirm no compatibility layer, wrapper, or replacement runtime path remains under the plugin.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 58-77, 760-908, 1158-1168

Non-goals:
This check does not require deleting historical plans, specs, audits, ignored handoffs, installed cache files, or personal plugin copies outside `plugins/turbo-mode/handoff/`.

### A3. Plugin Metadata Advertises Only Save, Load, And Search

Passes when:
`.codex-plugin/plugin.json` describes Handoff as skill-only session continuity for saving, loading, and searching Markdown handoffs; keeps `Interactive`, `Read`, and `Write`; uses version `2.0.0`; and contains no metadata advertising distillation, quicksave, summary, durable learning, chain state, hooks, or runtime helpers as supported behavior.

Evidence to inspect:
- `python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- Source-contract check assertions against plugin version, capabilities, and forbidden metadata terms
- `rg -n "distill|quicksave|summary|durable learning|chain state|hook|runtime helper" plugins/turbo-mode/handoff/.codex-plugin/plugin.json`

Verification ideas:
- Confirm `description`, `shortDescription`, `longDescription`, and `defaultPrompt` only name save/load/search Markdown-handoff behavior.
- Confirm forbidden terms do not appear in plugin metadata.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 48-50, 281-340, 478-489, 1002-1048

### A4. Current-Facing Docs State Skill-Only Behavior And Proof Boundaries

Passes when:
`README.md`, `PRIVACY.md`, and `TERMS.md` describe local Markdown save/load/search behavior, state that `/quicksave`, `/summary`, and `/distill` are retired, and avoid positive or instructional claims about runtime modules, helper scripts, command hooks, validators, chain state, transactions, archives, recovery protocols, durable learning extraction, installed runtime, or cache refresh.

Evidence to inspect:
- `plugins/turbo-mode/handoff/README.md`
- `plugins/turbo-mode/handoff/PRIVACY.md`
- `plugins/turbo-mode/handoff/TERMS.md`
- Retired-concept `rg` output reviewed as non-capability or retired-behavior notes only

Verification ideas:
- Run the plan's metadata/doc retired-term search and inspect every match.
- Confirm README includes the source/runtime proof boundary and does not imply installed runtime success.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 342-489, 920-928, 1137-1156

### A5. Save Skill Writes Direct Markdown Handoffs Without Helper State

Passes when:
`skills/save-handoff/SKILL.md` makes `/save` the only write-oriented behavior, captures session context plus project-arc context, writes directly under `<project_root>/.codex/handoffs/`, uses exclusive-create no-overwrite path selection, reports write failure plainly, and replies only `Handoff saved: <absolute path>` after success.

Evidence to inspect:
- `plugins/turbo-mode/handoff/skills/save-handoff/SKILL.md`
- Source-contract check snippets for `exclusive-create`, `session context`, `project-arc context`, `Do not call plugin helper scripts`, and `Handoff saved: <absolute path>`

Verification ideas:
- Confirm the save skill contains no active-writer protocol, transaction state, content hashes, chain state, consumed markers, recovery metadata, helper script calls, `docs/handoffs/` fallback, gitignore edits, staging, commits, or pruning.
- Confirm frontmatter parses and `agents/openai.yaml` remains display-name-only.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 51, 491-558, 1160-1162

### A6. Load Skill Is Read-Only And Reality-Checks Before Action

Passes when:
`skills/load-handoff/SKILL.md` is strictly read-only; implicit load prefers the newest current-branch handoff when frontmatter branch metadata exists; explicit load reads exactly the requested path; no automatic legacy search occurs; and the skill requires live git or non-git state reporting before acting on handoff claims.

Evidence to inspect:
- `plugins/turbo-mode/handoff/skills/load-handoff/SKILL.md`
- Source-contract check snippets for `strictly read-only`, branch-aware selection, git commands, and `resume pointer, not current truth`

Verification ideas:
- Confirm the load skill never archives, moves, copies, edits, deletes, marks consumed, writes state, or creates recovery metadata.
- Confirm required git commands are present: `git branch --show-current`, `git log -1 --oneline`, and `git status --short --branch --untracked-files=all`.
- Confirm non-git behavior reports CWD and unavailable git state instead of failing the load.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 52, 564-642, 1163

### A7. Search Skill Delegates To Read-Only `rg` Search

Passes when:
`skills/search-handoffs/SKILL.md` searches `<project_root>/.codex/handoffs/` with literal `rg --fixed-strings` by default, uses regex only when explicitly requested, reports missing directory and no-match cases plainly, and does not parse schemas, build indexes, rank semantically, deduplicate, or mutate files.

Evidence to inspect:
- `plugins/turbo-mode/handoff/skills/search-handoffs/SKILL.md`
- Source-contract check snippets for `read-only`, `rg -n --context 3 --fixed-strings`, `No handoffs directory found for this project.`, and `No handoffs matched <query>.`

Verification ideas:
- Confirm command shapes exactly include:
  - `rg -n --context 3 --fixed-strings "<query>" "$PROJECT_ROOT/.codex/handoffs"`
  - `rg -n --context 3 "<pattern>" "$PROJECT_ROOT/.codex/handoffs"`
- Confirm frontmatter parses and `agents/openai.yaml` remains display-name-only.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 53, 648-704, 1164

### A8. Format Reference Is Minimal And Evidence-Bounded

Passes when:
`references/handoff-format.md` documents storage path, filename convention, minimal frontmatter, optional branch/commit, recommended prompts, one compact example, the resumption test, and the "evidence, not truth" boundary without recreating the old contract, format reference, skill details, synthesis guide, schema, validator, line-count target, confidence field, taxonomy, or required template.

Evidence to inspect:
- `plugins/turbo-mode/handoff/references/handoff-format.md`
- Source-contract check snippets for storage path, `created_at:`, resumption test, and `evidence, not truth`

Verification ideas:
- Confirm the file is short and behavior-guiding rather than schema-like.
- Confirm old reference files are deleted and not reintroduced under new names.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 54-55, 760-880

### A9. Source-Contract Verification Passes

Passes when:
The temporary source-contract check exits successfully with `handoff skill-only source contract ok`, proving final file inventory, directory inventory, plugin metadata, surviving skill frontmatter, display-name-only agent metadata, and required behavior snippets.

Evidence to inspect:
- Terminal output from the source-contract check
- The check body in the plan
- `python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- `git diff --check`

Verification ideas:
- Run the source-contract check after final edits.
- Run `python -m json.tool` and `git diff --check` after the source-contract check.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 79-247, 910-920, 987-1081

Non-goals:
This check is temporary execution evidence, not a new committed validator or persistent proof framework.

### A10. Retired Concepts Have No Positive Current-Facing Instructions

Passes when:
Current-facing Handoff source has no positive or instructional references to retired concepts. Any remaining matches for retired terms are limited to short retired-behavior or non-capability notes.

Evidence to inspect:
- `rg -n "distill|quicksave|save-summary|active-write|chain state|transaction|session_state.py|quality_check|turbo_mode_handoff_runtime" plugins/turbo-mode/handoff`
- `README.md`, skill files, plugin metadata, privacy, terms, and format reference around each match

Verification ideas:
- Inspect every match rather than treating the search exit status alone as proof.
- Confirm `/quicksave`, `/summary`, and `/distill` are named only as retired behavior, not supported wrappers.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 373, 478-489, 920-928, 1165-1166

### A11. Adjacent References Are Inspected Without Expanding Source Scope

Passes when:
Adjacent tooling, specs, plans, `.agents`, `.codex`, and historical docs are searched for stale Handoff runtime assumptions; implementation fixes only current-facing source that would make the Handoff plugin advertise or ship retired behavior; historical artifacts, ignored handoffs, installed cache, and personal plugin copies are left untouched unless separately requested.

Evidence to inspect:
- Output from the Task 4 adjacent-reference `rg` command
- Any notes in the final status report about out-of-scope historical or refresh-tooling matches
- Absence of unrelated changes outside the accepted source scope unless justified by current-facing false advertising

Verification ideas:
- Run the Task 4 search and classify matches by the plan's decision rule.
- If adjacent source is patched, rerun source-contract and whitespace checks.
- Confirm no installed cache or personal plugin copy paths were edited.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 945-970, 1156

### A12. Git Hygiene And Final Report Preserve Source/Runtime Proof Separation

Passes when:
Final staged and committed changes are limited to the Handoff redesign source scope; final status is captured; the final report lists source verification performed and explicitly lists installed cache refresh, marketplace install, current-thread runtime reload, and app-server inventory as not proven.

Evidence to inspect:
- `git diff --stat`
- `git diff --cached --stat`
- `git diff --cached -- plugins/turbo-mode/handoff`
- `git status --short --branch --untracked-files=all`
- `git log -1 --oneline`
- Final response text

Verification ideas:
- Confirm no local handoff artifacts, installed cache changes, or unrelated files are staged.
- Confirm final response names the source-only proof boundary and does not imply installed runtime success.

Source basis:
- Basis: source-backed
- Source: `2026-06-09-handoff-skill-only-redesign.md` lines 972-1120, 1122-1156, 1167-1168

## Suggested Extra Checks

These are non-authoritative unless later accepted into the source plan or explicitly requested.

- After a separate refresh or install request, use runtime inventory surfaces such as `plugin/list`, `plugin/read`, `skills/list`, and `hooks/list` to prove installed behavior.
- Run refresh-tooling tests only if implementation changes refresh tooling or if stale Handoff source assumptions block the source redesign in practice.
- In a fresh Codex thread, smoke the installed `/save`, `/load`, and `/search` behavior only after source-to-cache/runtime pickup is intentionally performed.
