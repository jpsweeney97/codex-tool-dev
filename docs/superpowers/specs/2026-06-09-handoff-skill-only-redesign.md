# Handoff Skill-Only Redesign

## Status

Approved for implementation planning on 2026-06-09. Amended after design
reviews on 2026-06-09.

## Purpose

Replace the current Handoff plugin with a skill-only session-continuity bundle.

The current plugin has grown runtime code, transaction ledgers, chain state,
validators, helper scripts, and knowledge-extraction workflows around a simple
work product: a Markdown note that lets a future Codex session resume without
avoidable re-exploration.

This redesign removes that machinery. Handoff should help Codex write, read,
and search useful Markdown handoffs. The handoff artifact itself is the state.

## Outcome

Handoff remains an installable Turbo Mode plugin, but its shipped behavior is
only:

- save a Markdown handoff
- load a Markdown handoff as read-only context
- search Markdown handoffs with plain text search

Handoff no longer ships or describes:

- Python runtime modules
- CLI helper scripts
- command hooks
- validators
- active-write reservations
- load transactions
- chain-state files
- consumed markers
- recovery claims
- durable learning extraction
- quicksave or summary as separate skills
- legacy migration machinery

The user-visible result should feel plain: Codex leaves a useful note, reads it
later, checks live reality, and continues.

## Bundle Shape

Keep this plugin shape:

```text
plugins/turbo-mode/handoff/
  .codex-plugin/plugin.json
  README.md
  PRIVACY.md
  TERMS.md
  LICENSE
  skills/
    save-handoff/
      SKILL.md
      agents/openai.yaml
    load-handoff/
      SKILL.md
      agents/openai.yaml
    search-handoffs/
      SKILL.md
      agents/openai.yaml
  references/
    handoff-format.md
```

The `agents/openai.yaml` files are part of the approved skill-only surface. They
should stay display-name-only unless a concrete UI or discovery need requires
more metadata. If prompt text is added, it must not introduce triggers, steps,
storage behavior, retired-command language, or any other behavior contract that
is absent from the corresponding `SKILL.md`.

Remove these active source surfaces:

```text
plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/
plugins/turbo-mode/handoff/scripts/
plugins/turbo-mode/handoff/hooks/
plugins/turbo-mode/handoff/tests/
plugins/turbo-mode/handoff/pyproject.toml
plugins/turbo-mode/handoff/uv.lock
plugins/turbo-mode/handoff/CHANGELOG.md
plugins/turbo-mode/handoff/CONTRIBUTING.md
plugins/turbo-mode/handoff/references/ARCHITECTURE.md
plugins/turbo-mode/handoff/references/handoff-contract.md
plugins/turbo-mode/handoff/references/format-reference.md
plugins/turbo-mode/handoff/references/skill-details.md
plugins/turbo-mode/handoff/skills/save-handoff/synthesis-guide.md
plugins/turbo-mode/handoff/skills/distill/
plugins/turbo-mode/handoff/skills/quicksave/
plugins/turbo-mode/handoff/skills/save-summary/
```

Do not keep a compatibility layer, deprecated runtime path, or retained helper
code. The redesign is an in-place replacement, not a transitional wrapper.

## Plugin Metadata

Update `.codex-plugin/plugin.json` so it describes only the remaining behavior.

The description and interface text should say Handoff saves, loads, and searches
Markdown handoffs for session continuity. Current-facing metadata must not
advertise distillation, durable learning extraction, chain state, hooks, runtime
helpers, archived load behavior, or retired entry points as supported behavior.
Short non-capability or retirement notes are allowed when they make clear that
the behavior no longer exists. `/save` is the only save path. `/quicksave`,
`/summary`, and `/distill` are retired behavior, not wrappers or compatibility
aliases.

The plugin may keep `Interactive`, `Read`, and `Write` capabilities because
`save-handoff` writes files and the other skills read files.

Versioning is not the core design issue. The implementation plan can decide the
exact version bump according to current repo release practice.

## Storage

Primary storage is:

```text
<project_root>/.codex/handoffs/
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a
   git repository.
2. Otherwise use the current working directory.

Handoff filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

Writes must not silently overwrite an existing handoff. Use this deterministic
direct-write mechanic:

1. Create `<project_root>/.codex/handoffs/` if needed.
2. Choose the timestamp path.
3. Write with an exclusive-create primitive, such as an `Add File` style patch or
   file API mode that refuses to overwrite an existing path.
4. If the path exists, append `-2`, `-3`, and so on before `.md` until a free path
   is found.
5. If the direct write fails for any other reason, stop and report the write
   failure plainly.

This is path selection only, not reservation, a state file, a recovery protocol,
or an active-writer protocol.

The plugin does not add gitignore rules, stage files, commit files, auto-prune
files, or manage cross-machine continuity. Whether `.codex/handoffs/` is tracked
or ignored remains host-repository policy.

No hidden state is written under `.codex/handoffs/`. There is no `.session-state`
contract in the redesigned plugin.

## Handoff Format

Handoff files are Markdown with minimal YAML frontmatter.

Recommended frontmatter:

```yaml
---
created_at: "2026-06-09T14:30:00Z"
type: handoff
title: "Skill-only Handoff redesign"
project: codex-tool-dev
branch: main
commit: abc1234
---
```

In practice, `created_at`, `type`, `title`, and `project` should be present.
`branch` and `commit` should be included when available. Do not require
`session_id`, `resumed_from`, or `files`.

Recommended body prompts:

```markdown
# Handoff: <title>

## Session Context
## Project Arc
## Decisions
## Evidence Checked
## Current State
## Next Action
## Open Questions
## Risks
## References
```

These headings are prompts, not a schema. The save skill should choose the
sections that make the next session successful. There is no line-count target,
section-count validator, confidence field, evidence-level taxonomy, or required
decision template.

The quality bar is the resumption test:

> Could future Codex continue without wasting time, repeating avoidable
> exploration, or trusting a stale claim?

## Save Skill

`save-handoff` is the only write-oriented skill.

It handles `/save`, `/save <title>`, "wrap this up", "new session", "handoff",
and similar session-boundary requests.

Every saved handoff should include both:

- session context: what happened in this session, what changed, what was
  decided, what is in flight
- project-arc context: where the broader project stands, why this session
  matters, what prior decisions are load-bearing, and what future Codex should
  not forget

The skill writes Markdown directly under `<project_root>/.codex/handoffs/`.
It may use ordinary filesystem operations such as creating the handoff directory
and writing the Markdown file with the exclusive-create mechanic above. It must
not call plugin helper scripts, create transaction state, reserve active paths,
compute content hashes, or use an active-writer protocol.

The skill follows the storage filename and no-overwrite path selection rules.

If writing fails, report the file write failure plainly. Do not fall back to
`docs/handoffs/` and do not create a separate recovery protocol.

The chat response after a successful save should be brief:

```text
Handoff saved: <absolute path>
```

Do not reproduce the full handoff in chat.

## Load Skill

`load-handoff` is strictly read-only.

It handles `/load`, `/load <path>`, "continue from where we left off", and
"pick up the latest handoff."

The skill never archives, moves, copies, edits, deletes, marks consumed, writes
state, or creates recovery metadata.

Default selection:

```text
<project_root>/.codex/handoffs/*.md
```

For implicit `/load`, first determine the current branch when inside a git
repository. Then choose the newest handoff whose frontmatter `branch` matches the
current branch when both values are available. If no branch-matching handoff
exists, choose the newest handoff by filename timestamp. File modification time
is an acceptable fallback if filenames do not sort usefully.

This is a deterministic selection rule, not semantic ranking or an index. If the
selected handoff names a branch or commit that differs from live state, call out
the mismatch before recommending action.

For explicit `/load <path>`, read exactly that path if it exists. The skill may
read an archived or legacy path only when the user explicitly provides that path.
There is no automatic legacy search.

After reading the handoff, the skill must run a live-reality check before
treating the handoff as actionable.

Inside a git repository, run:

```bash
git branch --show-current
git log -1 --oneline
git status --short --branch --untracked-files=all
```

Outside a git repository, do not fail the load just because git state is
unavailable. Report the current working directory and state that git state is
unavailable because the directory is not a git repository.

If the handoff names specific important files, the skill should read those live
files before making claims that depend on them. The handoff is a resume pointer,
not current truth.

Recommended response shape:

```markdown
Loaded: <path>

Current live state:
- CWD: <path>
- Git: <branch/HEAD/worktree summary, or "unavailable: not a git repository">

Handoff says:
- <goal/current state>
- <key decisions>
- <next action>

Reality check:
- <what matches>
- <what is stale or unverified>

Recommended next move:
- <one concrete continuation>
```

If no handoff exists, report that plainly. Suggest `/save` only if there is
current context worth preserving.

## Search Skill

`search-handoffs` is a tiny read-only convenience skill.

It handles `/search <query>`, "search handoffs", "find in handoffs", and "what
did we decide about X?"

It does not parse a custom schema, build an index, rank semantically,
deduplicate, or mutate files.

Default search scope:

```text
<project_root>/.codex/handoffs/
```

Literal search command shape:

```bash
rg -n --context 3 --fixed-strings "<query>" "$PROJECT_ROOT/.codex/handoffs"
```

Regex search command shape when the user explicitly asks for regex:

```bash
rg -n --context 3 "<pattern>" "$PROJECT_ROOT/.codex/handoffs"
```

If no `.codex/handoffs/` directory exists, report "No handoffs directory found
for this project." If there are no matches, report "No handoffs matched
`<query>`."

For many matches, show a useful handful and offer to narrow. The skill may
suggest `/load <path>` when one result looks like the right continuation
artifact.

## Documentation

Rewrite `README.md` around the final source behavior:

- Handoff is skill-only.
- `/save` is the only save path; `/quicksave`, `/summary`, and `/distill` were
  retired.
- Handoffs are Markdown notes under `.codex/handoffs/`.
- `/load` and `/search` are read-only.
- Handoffs are resume pointers, not live truth.
- The plugin does not manage git, archives, chain state, learnings, hooks,
  validators, runtime scripts, or installed runtime state. These may appear only
  as a short non-capability note, not as positive or instructional behavior.

`references/handoff-format.md` should be short. It should include:

- the storage path convention
- the minimal frontmatter example
- recommended body prompts
- one compact example handoff
- the resumption test
- the "handoffs are evidence, not truth" boundary

Do not recreate the old `handoff-contract.md`, `format-reference.md`,
`skill-details.md`, or `synthesis-guide.md` under new names.

## Verification

The implementation should prove source shape, not installed runtime behavior.

Run:

```bash
git status --short --branch --untracked-files=all
python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json
git diff --check
```

Also verify the final plugin inventory contains only the approved source files
and directories.

Perform a small positive source-contract check:

- exactly three skill directories exist: `save-handoff`, `load-handoff`, and
  `search-handoffs`
- each surviving `SKILL.md` frontmatter parses
- each surviving `agents/openai.yaml` parses and remains display-name-only unless
  a concrete UI or discovery need justifies more metadata
- `save-handoff` states direct Markdown writing, project-arc plus session
  context, and exclusive-create no-overwrite path selection
- `load-handoff` states read-only behavior, branch-aware implicit selection, and
  git-aware or non-git live-state checks before action
- `search-handoffs` states read-only behavior and literal `rg` search by default
- `README.md` and `references/handoff-format.md` agree with those behavior
  boundaries

Run negative checks for retired concepts in current-facing Handoff source. At
minimum, inspect matches for these terms and remove current-facing references
unless they are part of a short retired-behavior or non-capability note. The rule
is no positive or instructional mentions of retired behavior. Historical
documents outside the plugin source may still contain older descriptions.

```text
distill
quicksave
save-summary
active-write
chain state
transaction
session_state.py
quality_check
turbo_mode_handoff_runtime
```

Parse edited skill frontmatter as YAML if the repo has an existing helper for
that. A small one-off structural check is enough if no helper remains after test
removal.

Do not claim installed-runtime success from this verification bundle. Plugin
install, marketplace refresh, local cache mutation, or current-thread runtime
reload would require a separate explicit runtime proof step.

## Non-Goals

- no runtime package
- no helper scripts
- no hooks
- no validators
- no chain protocol
- no archiving on load
- no legacy auto-discovery
- no durable learning extraction
- no ticket or deferred-work tracking
- no installed cache or runtime mutation
- no personal plugin copy mutation
- no compatibility bridge for old Handoff internals
- no retired-command wrappers for `/quicksave`, `/summary`, or `/distill`

## Acceptance Criteria

The source redesign is complete when:

- Handoff source contains only the approved skill-only bundle shape.
- `save-handoff` writes direct Markdown handoffs with session and project-arc
  context, using exclusive-create no-overwrite path selection.
- `load-handoff` is read-only, prefers current-branch handoffs for implicit
  loads when branch metadata exists, and requires git-aware or non-git live-state
  checks before acting on a handoff.
- `search-handoffs` is read-only and delegates search to `rg`.
- `distill`, `quicksave`, and `save-summary` are no longer shipped Handoff
  skills.
- Current-facing Handoff README states that `/quicksave`, `/summary`, and
  `/distill` were retired instead of preserving wrappers; metadata must not
  advertise them as supported behavior.
- Current-facing Handoff docs and metadata contain no positive or instructional
  mentions of runtime code, chain state, transactions, hooks, validators, or
  durable learning extraction. Only short retired-behavior or non-capability
  notes are allowed.
- Source/shape verification passes.
- The final status report separates source verification from installed runtime
  proof.
