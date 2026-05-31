# Ticket Docs Authority Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADR 0006 and the May 30 control doc the visible authority for Ticket docs/tests without claiming current source, ticket files, installed cache, or live runtime already enforce the target model.

**Architecture:** This is a docs/tests authority-boundary patch. Target architecture, current source compatibility, cutover inventory, and installed-runtime proof stay separate. Old behavior may be mentioned only as narrow current-source compatibility, cutover input, or historical changelog context.

**Tech Stack:** Markdown docs, Codex `SKILL.md` instruction files, Python `pytest` static docs tests.

---

## Context

ADR 0006 is accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface.

This slice is docs/tests only. It does not satisfy the ADR/control read-only
`docs/tickets/` cutover inventory gate, normalize ticket files, refresh the
installed plugin cache, or prove live runtime behavior.

The implementation must prevent old architecture from surviving by relabeling.
Compatibility sections may not become a second contract for the old pipeline.

## Surface Matrix

| Surface | Required Treatment |
|---|---|
| `plugins/turbo-mode/ticket/references/ticket-contract.md` | Add authority boundary; make target post-cutover schema primary; move old schema into narrow cutover/current-source compatibility notes only. |
| `plugins/turbo-mode/ticket/README.md` | Add authority boundary; stop presenting fenced YAML, preview mode, three mutation surfaces, and four-stage pipeline as current product authority. |
| `plugins/turbo-mode/ticket/HANDBOOK.md` | Add authority boundary; keep runnable current commands only as transitional source-operation notes. Remove pipeline diagrams as product architecture. |
| `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md` | Patch payload vocabulary, preview/execute wording, priority values, component/refinement fields, and command flow authority. |
| `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md` | Patch status/priority filters and refinement-status output rules so old values are current-source compatibility only. |
| `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md` | Patch supported fields, lifecycle vocabulary, `blocks`, `component`, `refinement_status`, `acceptance_criteria`, and preview-first wording. |
| `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md` | Inspect and patch stale/blocked-chain wording only where it implies persisted `blocked` status or `blocks` reverse edges as target schema. |
| `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` | Inspect and patch preview/audit/activation wording only where it implies current target authority. |
| `plugins/turbo-mode/ticket/PRIVACY.md` | Inspect; patch only current-facing contradictions. |
| `plugins/turbo-mode/ticket/TERMS.md` | Inspect; patch only current-facing contradictions. |
| `plugins/turbo-mode/ticket/CHANGELOG.md` | Fix current/unreleased skill-name mismatch to live names. Keep historical entries historical. |
| `plugins/turbo-mode/ticket/.codex-plugin/plugin.json` | Inspect interface text; patch only if it advertises old architecture as current product behavior. |
| `plugins/turbo-mode/ticket/tests/test_docs_contract.py` | Replace old-positive docs assertions with authority-boundary tests. |
| `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py` | Replace old-positive autonomy docs assertions with authority-boundary tests. |

## Acceptance Rules

- Target schema sections must describe ID-only filenames, YAML frontmatter,
  closed keys `id`, `title`, `status`, `priority`, `tags`, `related_paths`,
  and `blocked_by`, statuses `open`, `in_progress`, `done`, and `wontfix`,
  priorities `high`, `normal`, and `low`, and required `Problem`,
  `Next Action`, and `Change History`.
- Old fields or shapes may appear only in sections explicitly named for current
  source compatibility, legacy cutover input, or historical changelog. Those
  sections must include an ADR/control pointer and must not use normative target
  verbs such as "must", "canonical", "single source of truth", "supported", or
  "required" for old shapes.
- Approval language must be split:
  - Banned as target: automatic approval objects for `agent_primary`.
  - Permitted as target: `discussion_only` user-approval facts tied to candidate
    identity.
- Preview language must be split:
  - Banned as target: persistent `preview` mode or durable config.
  - Permitted: diagnostic dry-run/preview and transitional confirmation UX,
    clearly labeled.
- Four-stage pipeline, prepare/execute wrappers, machine-state taxonomy, commit
  disposition, `ticket_change_scope`, controlled Change History labels, and old
  error-code taxonomy must not appear as current product architecture.
- The closeout must explicitly say this slice did not perform the read-only
  `docs/tickets/` cutover inventory gate.

## Tasks

### Task 1: Update tests first

**Files:**

- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py`

- [ ] Replace the three mutation-surface tests with authority-boundary tests:
  `test_readme_states_supported_high_level_mutation_surfaces`,
  `test_handbook_states_supported_high_level_mutation_surfaces`, and
  `test_contract_states_supported_high_level_mutation_surfaces`.
- [ ] Replace `test_readme_ticket_schema_matches_yaml_contract_boundary` with a
  target-schema test that checks the ADR 0006 fields/statuses/priorities and a
  section-scoped negative check against old schema values.
- [ ] Replace old-positive tests that bless autonomy CLI/ledger command
  authority where they preserve approval-object or old pending-summary framing:
  `test_contract_names_host_facing_autonomy_cli_surface`,
  `test_contract_separates_core_runtime_and_activation_error_codes`,
  `test_response_envelope_docs_point_to_error_code_taxonomy`, and
  `test_contract_documents_recovery_hint_schema_and_codes`.
- [ ] Rewrite capture skill tests that require `medium`, `critical`,
  `component`, `refinement_status`, compact preview as target contract, or old
  refinement metadata.
- [ ] Rewrite read/update skill tests that require `refinement_status`,
  preview-first execution, old focused backend fields, `component`, `blocks`,
  or `acceptance_criteria` as target contract.
- [ ] Rewrite handbook tests that require capture preview smoke as target
  workflow, old focused update backend authority, workflow-runner authority, or
  capture-first five-skill language that still embeds old schema vocabulary.
- [ ] Update
  `test_static_autonomy_boundaries.py::test_current_facing_docs_pin_runtime_first_modes_without_legacy_yaml_guidance`
  so durable modes are exactly `agent_primary` and `discussion_only`, with
  `preview` allowed only in diagnostic/transitional sections.
- [ ] Inspect pending-summary fixture assertions that mention `approval`. Keep
  only tests that protect source compatibility or the permitted
  `discussion_only` user-approval fact tied to candidate identity.

Suggested helper structure:

```python
CORE_AUTHORITY_DOCS = (
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
)
SKILL_AUTHORITY_DOCS = (
    PLUGIN_ROOT / "skills" / "capture-ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "read-ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "update-ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "ticket-backlog-triage" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "ticket-doctor" / "SKILL.md",
)
ADJACENT_DOCS = (
    PLUGIN_ROOT / "PRIVACY.md",
    PLUGIN_ROOT / "TERMS.md",
    PLUGIN_ROOT / "CHANGELOG.md",
    PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
)
```

Suggested test approach:

```python
def _section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, maxsplit=1)[1]
    return body if end is None else body.split(end, maxsplit=1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())
```

Use section-scoped assertions rather than broad word bans. Old terms may remain
in compatibility/cutover/historical sections only when the section points to ADR
0006 and the control doc, and does not make old shapes normative target
authority.

### Task 2: Patch core docs

**Files:**

- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`

- [ ] Add an authority boundary near the top of each file:
  - ADR 0006 is accepted architecture authority.
  - The May 30 control doc is implementation/cutover control.
  - This source document is not runtime proof.
  - This docs/tests slice does not perform cutover inventory or normalization.
- [ ] Replace "single source of truth" contract wording with "current
  source-facing reference subordinate to ADR 0006/control doc" or equivalent.
- [ ] Make target post-cutover schema primary, qualified as architecture/cutover
  authority rather than current runtime enforcement.
- [ ] Move old fenced-YAML schema, old statuses/priorities, slug filenames,
  archived closed lifecycle, and old metadata fields into narrow
  compatibility/cutover notes.
- [ ] Replace four-stage/product-pipeline prose with state-kernel and candidate
  mutation prose.
- [ ] Remove pipeline diagrams as product architecture. If a diagram remains, it
  must be labeled current-source compatibility and cannot be under an
  "Architecture" heading without an ADR/control warning.
- [ ] Split approval language into banned automatic approval objects for
  `agent_primary` and permitted `discussion_only` user-approval facts tied to
  candidate identity.
- [ ] Split preview language into diagnostic dry-run/preview versus persistent
  `preview` mode. Persistent `preview` must not be documented as a durable mode.

### Task 3: Patch skill docs

**Files:**

- Modify: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`

- [ ] Apply local writing-principles guidance for `SKILL.md` edits.
- [ ] Add a short authority note where behavior-shaping instructions otherwise
  look like contract authority: ADR 0006/control doc own the target model; current
  command paths are transitional source behavior until implementation/cutover.
- [ ] Keep current backend command examples only when needed for current
  execution, and label them transitional source paths.
- [ ] Remove or qualify old payload fields and examples: `component`, `blocks`,
  `refinement_status`, `acceptance_criteria`, `blocked`, `critical`, `medium`,
  and persistent preview.
- [ ] For `read-ticket`, label `blocked`, `critical`, and `medium` filters as
  current-source compatibility if they remain in command examples.
- [ ] Preserve usable instructions where source still needs current commands, but
  do not present those commands as the target state-kernel contract.

### Task 4: Patch adjacent docs

**Files:**

- Inspect: `plugins/turbo-mode/ticket/PRIVACY.md`
- Inspect: `plugins/turbo-mode/ticket/TERMS.md`
- Modify if needed: `plugins/turbo-mode/ticket/CHANGELOG.md`
- Inspect: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`

- [ ] Fix the current/unreleased changelog skill-name mismatch to the live names:
  `capture-ticket`, `read-ticket`, `update-ticket`, `ticket-backlog-triage`, and
  `ticket-doctor`.
- [ ] Keep older changelog entries historical. Do not rewrite old release
  history just because it describes past architecture.
- [ ] Patch PRIVACY, TERMS, and manifest only for current-facing old-architecture
  claims. Leave accurate privacy, terms, and historical artifact wording intact.

### Task 5: Verify and close out

**Files:**

- Verify all changed docs/tests.

- [ ] Run focused docs/static tests.
- [ ] Run `ruff check` for the changed test files.
- [ ] Run `git diff --check`.
- [ ] Run a fence checker that fails on unbalanced fences for every changed
  Markdown file.
- [ ] Report whether ignored residue remains, especially
  `plugins/turbo-mode/ticket/.venv/` and
  `plugins/turbo-mode/ticket/.pytest_cache/`.
- [ ] State explicitly in closeout that this docs/tests slice did not perform the
  read-only `docs/tickets/` cutover inventory gate.

## Verification Commands

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py
git diff --check
```

Fence check, passing the changed Markdown files explicitly:

```bash
PYTHONDONTWRITEBYTECODE=1 python -c 'import sys; bad=[]; [bad.append(f"{p}: unbalanced fences") for p in sys.argv[1:] if sum(1 for line in open(p, encoding="utf-8") if line.startswith("```")) % 2]; print("\n".join(bad)); raise SystemExit(1 if bad else 0)' <changed-markdown-files>
```

## Commit Guidance

Make one coherent docs/tests commit after verification passes:

```bash
git add plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/PRIVACY.md plugins/turbo-mode/ticket/TERMS.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/.codex-plugin/plugin.json plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py
git commit -m "docs(ticket): align docs with state-kernel authority"
```

Adjust the `git add` set to include only files actually changed.

## Assumptions

- No runtime source implementation in this slice.
- No mutation of `docs/tickets/`.
- No installed cache refresh or live runtime inventory proof.
- Current source compatibility can remain documented only where needed to keep
  existing commands understandable and usable before runtime rebaseline.
