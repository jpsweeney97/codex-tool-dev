# AGENTS.md

Repository-local instructions for `/Users/jp/Projects/active/codex-tool-dev`.

## Repository Purpose

This repository is the development workspace for Codex plugins, skills, and
supporting tools. Treat it as source-authority for the local Turbo Mode plugin
tree, not as proof that the installed Codex runtime already matches source.

Primary source surfaces:

- `plugins/turbo-mode/handoff/` - Handoff plugin source.
- `plugins/turbo-mode/ticket/` - Ticket plugin source.
- `plugins/turbo-mode/tools/` - migration, refresh, proof, and cache-update
  tooling for Turbo Mode plugin development.
- `.codex/skills/` - repo-local Codex skills used while working in this repo.
- `.agents/plugins/marketplace.json` - local marketplace descriptor for the
  Turbo Mode plugin source tree.
- `docs/superpowers/` and `docs/tickets/` - durable plans, closeouts, PR
  packages, and tracked tickets.

## Communication

### Chat Communication Style

Default to outcome-oriented framing: lead with the user-visible behavior, experience, or decision, then map to technical choices. Treat chat as requirements alignment — confirm what the user wants before framing how to build it.

Match the user's register — if they ask in technical terms, respond in technical terms.

This framing applies to conversation, not to authored artifacts.

### Plain Language

- Use plain, accessible language when explaining things in conversation.
- Prefer concrete analogies and direct statements over jargon-heavy summaries and formal report structure.
- Save the formal structure for artifacts that need it: tickets, specs, handoffs, commit messages.
- Code and documents should still be precise — this applies to how you talk about them, not how you write them.

## Development Tenet

This repo builds Codex-facing systems (plugins, skills, hooks, agents,
commands, MCP servers, prompts Codex reads at runtime). For these systems,
prefer giving Codex judgment-supporting context over encoding behavior in
rule machinery. Before adding a structured field, status enum, workflow
stage, validation rule, or imperative decision logic to a Codex-facing
system, run four tests:

**Test 1 — Whose failure is it?** If Codex populates this wrong, does the
**work product** (the artifact a non-plugin reader consumes) suffer, or
does **only the plugin's own machinery** (validators, internal pipelines,
audit trails, derived caches) break? A field counts as ontology if Codex
has to know about it *anywhere* — schema, contract, pipeline stage, audit
log, engine interface. "Derive at runtime" only removes a field from the
ontology when the value is computed on demand AND discarded; it does not
help when the value is computed once and passed forward between stages.
"Move to audit logs" does not help when Codex must populate the logs
correctly. Fields whose only consumer is the plugin's pipeline (internal
state classifications, confidence scores between stages, derived hashes
that couple pipeline steps, override flags, version stamps for contract
checking) are over-fit ontology — remove them, demote them to truly
transient runtime values, or acknowledge that they are over-fit and count
them in Test 2.

**Test 2 — Tooling or thinking?** Separate fields that help Codex reason
(small, bounded, content-shaped — the things a human reader of the output
would also reference) from fields that exist for tooling (queries, audits,
downstream automation). Thinking fields stay roughly proportionate to the
concept's complexity; tooling fields multiply without limit if unchecked.
When tooling fields outnumber thinking fields, the artifact has inverted
its purpose: the plugin is the customer, not the work. Apply per-addition
AND on the full set at Test 4's cadence.

**Test 3 — Could Codex do this work inline?** Before writing a script
that classifies, triages, validates with semantic judgment, scores,
decides, or routes within plugin/skill/agent workflows, ask: given the
same context the script will consume, could a thinking Codex produce the
same decision in prose? If yes, the script is replacing judgment with
code. Move the decision back to Codex; keep only the deterministic
mechanics in code (file I/O, schema parsing, persistence, idempotent state
mutations).

*Exempt from Test 3: infrastructure code.* (a) Hooks running synchronously
on every Codex tool invocation; (b) security/policy guards (credential
scanners, destructive-action blockers, branch protection); (c)
deterministic computational machinery (search ranking, indexing, parsing,
encoding, hashing) where the algorithm itself is the value, not the
decision the algorithm produces. The "unacceptable latency / token cost /
fail-open risk" argument applies only *within* (a), (b), or (c) — it is
not a freestanding exemption, and it does not exempt semantic decisions
(classifying, triaging, scoring) even when called at high frequency.
Infrastructure code is justified by stakes and operational constraints
rather than by its decision shape.

Within workflow contexts, imperative code that pre-decides for Codex is
the form of rule machinery that hides best — it passes Tests 1 and 2
because it isn't a field — but it produces exactly the harm the tenet
exists to prevent.

**Test 4 — Re-test the whole artifact, not just additions.** Tests 1-3
fire per-addition. Re-run all three on the full Codex-facing surface
(every field, every script, every line of prose) at any of these triggers,
whichever first:

- **Deterministic floor:** after every ~25 commits touching the artifact's
  directory, or whenever its Codex-facing surface has grown by ~50% since
  last review (numbers are calibration, not a contract).
- **Subjective signal:** when adding the next item makes you hesitate.

The deterministic floor exists because momentum-driven development
suppresses the hesitation signal exactly when re-evaluation is most
needed. Balanced incrementalism — adding one thinking field per tooling
field — passes per-addition checks indefinitely while accumulating into a
heavy ontology; only periodic full-surface re-evaluation catches it.

If the artifact's Codex-facing surface feels disproportionate to the work
it does — compared to lighter plugins in this repo like `handoff` or
`context-metrics` — that is the redesign signal. Responsibility for Test 4
falls on whoever next adds to the artifact; if you can't tell when it last
ran, run it now.

### Illustrative shapes

| Shape | Verdict | Why |
|---|---|---|
| A document artifact with `title`, `body`, `priority`, `tags` | Keep | A non-plugin reader uses each field; passes Test 1 and Test 2 |
| The same artifact also carrying internal pipeline fields (process-stage enum, derived hash persisted across stages, classification-confidence float, contract version stamp, hook-origin marker) | Over-fit | Only the plugin's machinery cares; "derived at runtime" does not save it because the value crosses stages; "in audit logs" does not save it because Codex must populate them |
| A script that classifies user intent into N categories then routes to one of N handlers within a plugin workflow | Over-fit (Test 3) | A thinking Codex given the same input could pick a category in prose; the script is making Codex's decision for it |
| A hook that scans files for credentials and blocks egress | Hard rule, Test 3 exempt | Runs synchronously on every tool call; latency-sensitive; security-critical. Semantically a "classifier" but exempt because infrastructure |
| A hook that blocks edits to protected branches (multi-state state machine + env-var configuration) | Hard rule, justified | Wrong = real branch/data damage; failure lands in the work. Codex's role here is one decision (edit/don't), not navigating a taxonomy |
| A skill that lays out a fixed N-stage workflow Codex must walk in order regardless of situation | Over-fit | Cases needing 1 stage and cases needing N are both forced through N |
| A skill that exposes a checklist Codex consults but isn't forced to walk | Keep | Structure offered as context, not imposed as workflow; Codex decides which items apply |
| A session-state plugin with `session_id`, `timestamp`, `branch`, `summary` persisted to disk | Keep | Fields are content-shaped (a non-plugin reader uses them); the plugin's existence is justified by an otherwise-unsolvable problem (cross-session memory); Test 1 passes because a wrong field = wrong handoff = wrong work |

### Supporting frame

Codex-facing systems support judgment; they do not replace it with rule
machinery. The four tests above are how that stance becomes a filter at
design time. Hard rules remain appropriate where a mistake degrades the
work itself — safety, destructive actions, data integrity, recovery
guarantees, stale state. Everywhere else, prefer giving Codex durable
context, clear boundaries, recoverable state, and structured evidence,
then trust the judgment that follows.

This tenet sits alongside `/Users/jp/.codex/tenets.md` and does
not override it. The methodology tenets are broader: they cover code
design (Deterministic over Heuristic, Explicit over Silent), problem-
solving approach (counteract capability-first thinking), and risk
awareness for irreversible actions. This tenet is narrower: it covers the
design of Codex-facing artifacts in this repo specifically. The two are
mostly compatible — code-design tenets apply to the runtime behavior under
a Codex-facing artifact while this tenet applies to the surface above.
Where they directly conflict, the more specific tenet (this one, for the
Codex-facing surface) governs.

A good implementation makes Codex more capable without making normal work
feel heavy. The tests bind themselves by that constraint: apply them to
the design as a whole, not as a per-keystroke ritual. If running them
takes longer than the artifact deserves, the artifact is probably too
small to need any of them — but Test 4's periodic full-surface check is
the floor, not a ceiling.

## Development Posture

This is a fast-iteration development repo. Aim for small, reversible,
evidence-backed changes that move the current plugin work forward. The bar is
real correctness for the touched behavior, not broad hardening against every
hypothetical environment.

- Prefer the smallest credible change that solves the current problem and leaves
  clear evidence.
- Scale process to blast radius. Runtime/cache mutation, hook trust, storage
  recovery, and publication evidence need explicit gates; docs wording, narrow
  source fixes, and local helper cleanup should not grow extra ceremony.
- Avoid speculative compatibility layers, generic frameworks, and broad rewrites
  unless live code, tests, or the user's request shows they are needed now.
- When a future concern is real but not required for the current slice, name it
  as follow-up work instead of folding it into the current patch.

## Authority And Evidence

- Read the live file before relying on a plan, handoff, summary, review packet,
  or prior conversation. Many historical docs are intentionally retained and may
  describe an older state.
- Separate proof classes in status reports:
  - `source`: code, docs, tests, and manifests in this checkout.
  - `installed runtime`: what Codex currently exposes through app-server
    surfaces such as `plugin/read`, `plugin/list`, `skills/list`, and
    `hooks/list`.
  - `local cache`: files under `/Users/jp/.codex/plugins/cache/...`.
  - `docs readiness`: plans, closeouts, and tickets that describe intended or
    completed work.
- Do not claim installed/runtime success from source file presence, cache file
  presence, or marketplace JSON alone. Use live runtime inventory when the claim
  is about installed behavior.
- If the user asks for an evaluation, review, or certification, make missing
  evidence explicit instead of treating it as a pass.

## Work Boundaries

- Keep source repair separate from installed-cache mutation. Updating source does
  not imply the installed plugin cache has been refreshed.
- Do not mutate `/Users/jp/.codex/plugins/cache`, `/Users/jp/.agents`, or other
  machine-local runtime state unless the user explicitly asks for an installed
  refresh, runtime proof, or local setup change.
- Do not run guarded refresh, cache refresh, plugin install, or live runtime
  mutation commands as a side effect of ordinary source edits.
- Use `trash <path>` for deletion. Never use `rm` or `rm -rf`.
- Preserve unrelated dirty work. If generated residue blocks verification, report
  it and remove it only when the cleanup is in scope or explicitly approved.
- Treat ignored handoff directories such as `.codex/handoffs/` and
  `docs/handoffs/` as local session history. Do not publish, stage, or delete
  those files unless the user explicitly makes them part of the task.

## Plugin-Specific Rules

### Handoff

- Source root: `plugins/turbo-mode/handoff/`.
- Public behavior is primarily defined by `README.md`, `skills/*/SKILL.md`,
  `scripts/*.py`, `references/`, and `.codex-plugin/plugin.json`.
- `hooks/hooks.json` is intentionally empty. Do not describe Handoff as
  shipping plugin-bundled command hooks unless both the source manifest and
  installed runtime prove that changed.
- Handoff storage currently targets project-local `.codex/handoffs/` paths.
  Older `docs/handoffs/` artifacts can still exist as historical or ignored
  local state.
- The checkout has a root-level `scripts/` package. When changing Handoff helper
  imports, include direct-execution or repo-root smoke coverage so
  plugin-local `scripts.*` imports cannot be silently shadowed by the root
  package.

### Ticket

- Source root: `plugins/turbo-mode/ticket/`.
- Ticket scripts live in `scripts/`; this is not a conventional installed Python
  package layout.
- Canonical plugin script launcher shape is:

  ```bash
  uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...
  ```

- `PLUGIN_ROOT` is the plugin package root. `PROJECT_ROOT` is the active
  workspace root. Ticket files live under `<PROJECT_ROOT>/docs/tickets/`, not
  under the plugin package.
- Ticket mutation flows are trust-aware and confirmation-gated. Do not bypass
  `ticket_workflow.py`, the engine entrypoints, or the guard model just to make
  a mutation easier.
- `hooks/hooks.json` points at the installed cache hook path. Treat that file as
  source metadata; use `hooks/list` when proving live hook registration.

## Skills And Instruction Files

- When editing `SKILL.md`, `agents/*.yaml`, `agents/*.md`, `CLAUDE.md`, or
  instruction-style Markdown, apply the writing principles from
  `/Users/jp/.agents/skills/writing-principles/`.
- Keep skills behavior-focused. Avoid meta commentary about how the skill was
  authored.
- If a skill behavior changes, check whether companion files under `agents/`,
  `references/`, tests, plugin manifests, or README content also need updates.
- For review-oriented skills and review requests, lead with findings, risks,
  regressions, and missing proof. Keep summaries secondary.

## Plans, Tickets, And Handoffs

- Treat `docs/superpowers/plans/` as execution control documents, not loose
  notes. If asked to revise one, make file paths, stop conditions, evidence
  gates, and commit boundaries concrete.
- Treat `docs/tickets/` as tracked project state. Preserve ticket schema and
  audit semantics when editing tickets by hand.
- When a user asks for a plan first, write or revise the plan and wait for an
  implementation cue before changing code.
- When a user invokes saved handoff context, re-check current branch, `HEAD`,
  worktree status, and the live files before trusting the handoff narrative.

## Verification

Choose the smallest verification set that proves the changed surface. Prefer
focused package tests over broad commands that collect unrelated work.

Use bytecode-safe Python test commands for this repo:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest <target> -q
```

Common targets:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check <changed-python-paths>
git diff --check
```

For refresh or installed-runtime work, add the relevant non-mutating planner or
inventory check before any mutation. Runtime proof should include app-server
inventory such as `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`.

For Handoff import or script-entrypoint changes, add a direct smoke such as:

```bash
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/scripts/installed_host_harness.py
```

Adjust the exact selector to the file being changed. If a command creates
`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.venv`, or
`.DS_Store` residue in plugin source paths, clean or report it before claiming a
clean closeout.

## Git And Cleanup

- Before edits, check `git status --short --branch`.
- Before staging or committing, review `git diff --stat` and the relevant diff.
- For completed file-changing work in this repo, create a local commit by
  default after focused verification when a coherent commit can be made.
- Do not create the automatic local commit if the user asked not to commit, the
  turn was review-only or exploratory, verification is failing or blocked, the
  work is incomplete, or unrelated/overlapping dirty files make safe staging
  ambiguous.
- Keep publishing explicit. Do not push commits, create pull requests, or
  otherwise publish changes unless the user asks for that.
- Use branch names that match the user-level branch policy when creating a
  branch from `main`: `feature/*`, `fix/*`, `hotfix/*`, or `chore/*`.
- Keep commits coherent by surface: docs-only, Handoff source, Ticket source,
  refresh tooling, runtime evidence, and cleanup should not be mixed without a
  reason.
- Do not stage ignored local runtime or handoff artifacts unless the user
  explicitly asks to publish them and the repository policy supports it.

## Communication

- State whether a conclusion is based on live files, tests, runtime inventory,
  or memory/history.
- For bug investigations with multiple plausible causes, use the required
  root-cause checkpoint before a deep dive.
- For code changes, report what changed, why it changed, verification performed,
  and remaining risks.
- If work is blocked by stale runtime state, generated residue, missing
  evidence, or a destructive cleanup decision, name the blocker and the decision
  needed.
