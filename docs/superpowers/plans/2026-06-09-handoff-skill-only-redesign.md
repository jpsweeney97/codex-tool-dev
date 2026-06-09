# Handoff Skill-Only Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Handoff plugin source with a skill-only session-continuity bundle that saves, loads, and searches Markdown handoffs without runtime helpers, hooks, validators, transaction state, or retired skill entry points.

**Architecture:** Keep Handoff as an installable Turbo Mode plugin, but make the artifact itself the state: three skill documents plus one short format reference. The only proof target is source shape and current-facing source behavior; installed plugin cache refresh, marketplace install, and runtime reload are explicitly separate work.

**Tech Stack:** Markdown skill docs, plugin JSON metadata, YAML skill frontmatter and `agents/openai.yaml`, `rg`, `python -m json.tool`, `uv run python` for source-contract parsing, `trash` for deletions. Branch: `feature/handoff-skill-only-redesign`.

**Source spec:** `docs/superpowers/specs/2026-06-09-handoff-skill-only-redesign.md`

---

## Agent-Facing Design Gate Result

This redesign removes machinery. The plan does not add a persistent validator, router, schema, helper script, or state protocol. It uses a temporary source-contract check during execution because the protected work product is the Handoff source bundle itself, and a stale extra skill or runtime path would directly contradict what future Codex sessions are told Handoff does.

## File Structure

Final approved source shape:

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

Responsibilities:

- `.codex-plugin/plugin.json`: plugin metadata for only saving, loading, and searching Markdown handoffs. Keeps `Interactive`, `Read`, and `Write`.
- `README.md`: current-facing user documentation for the skill-only plugin and explicit retired-behavior boundary.
- `PRIVACY.md` and `TERMS.md`: local-file behavior only; no summarizing, triage, distillation, hooks, or runtime claims.
- `skills/save-handoff/SKILL.md`: the only write-oriented skill; direct Markdown write to `<project_root>/.codex/handoffs/` using exclusive-create no-overwrite path selection.
- `skills/load-handoff/SKILL.md`: read-only selection and live-reality check before acting on handoff context.
- `skills/search-handoffs/SKILL.md`: read-only `rg` search over `.codex/handoffs/`.
- `skills/*/agents/openai.yaml`: display-name-only metadata.
- `references/handoff-format.md`: short format guidance, example, and evidence-not-truth boundary.
- `LICENSE`: unchanged MIT license.

Delete these source surfaces instead of wrapping or deprecating them in place:

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

## Source-Contract Check

Use this temporary check before edits to prove the current source fails the target shape, and after edits to prove the source shape and key behavior text. It is intentionally not committed.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

import yaml

root = Path("plugins/turbo-mode/handoff")
expected_files = {
    ".codex-plugin/plugin.json",
    "LICENSE",
    "PRIVACY.md",
    "README.md",
    "TERMS.md",
    "references/handoff-format.md",
    "skills/load-handoff/SKILL.md",
    "skills/load-handoff/agents/openai.yaml",
    "skills/save-handoff/SKILL.md",
    "skills/save-handoff/agents/openai.yaml",
    "skills/search-handoffs/SKILL.md",
    "skills/search-handoffs/agents/openai.yaml",
}
expected_dirs = {
    ".codex-plugin",
    "references",
    "skills",
    "skills/load-handoff",
    "skills/load-handoff/agents",
    "skills/save-handoff",
    "skills/save-handoff/agents",
    "skills/search-handoffs",
    "skills/search-handoffs/agents",
}

actual_files = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() and path.name != ".DS_Store"
}
actual_dirs = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_dir()
}

missing = sorted(expected_files - actual_files)
extra = sorted(actual_files - expected_files)
missing_dirs = sorted(expected_dirs - actual_dirs)
extra_dirs = sorted(actual_dirs - expected_dirs)
if missing or extra or missing_dirs or extra_dirs:
    raise SystemExit(
        "inventory mismatch\n"
        f"missing_files={missing}\n"
        f"extra_files={extra}\n"
        f"missing_dirs={missing_dirs}\n"
        f"extra_dirs={extra_dirs}"
    )

plugin = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
if plugin["version"] != "2.0.0":
    raise SystemExit(f"unexpected plugin version: {plugin['version']!r}")

plugin_text = json.dumps(plugin, sort_keys=True).lower()
for forbidden in (
    "distill",
    "quicksave",
    "summary",
    "durable learning",
    "chain state",
    "hook",
    "runtime helper",
):
    if forbidden in plugin_text:
        raise SystemExit(f"plugin metadata still advertises retired behavior: {forbidden}")

skills = sorted(path.name for path in (root / "skills").iterdir() if path.is_dir())
if skills != ["load-handoff", "save-handoff", "search-handoffs"]:
    raise SystemExit(f"unexpected skill directories: {skills!r}")

def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"missing frontmatter: {path}")
    _, raw, _ = text.split("---", 2)
    parsed = yaml.safe_load(raw) or {}
    if not isinstance(parsed, dict):
        raise SystemExit(f"frontmatter is not a mapping: {path}")
    return parsed

for name in skills:
    skill_path = root / "skills" / name / "SKILL.md"
    metadata = frontmatter(skill_path)
    if metadata.get("name") != name:
        raise SystemExit(f"{skill_path} name mismatch: {metadata!r}")
    if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
        raise SystemExit(f"{skill_path} missing description")

    agent_path = root / "skills" / name / "agents" / "openai.yaml"
    agent_metadata = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    expected_agent_metadata = {"interface": {"display_name": {
        "load-handoff": "Load Handoff",
        "save-handoff": "Save Handoff",
        "search-handoffs": "Search Handoffs",
    }[name]}}
    if agent_metadata != expected_agent_metadata:
        raise SystemExit(f"{agent_path} is not display-name-only: {agent_metadata!r}")

save_text = (root / "skills/save-handoff/SKILL.md").read_text(encoding="utf-8")
for snippet in (
    "exclusive-create",
    "session context",
    "project-arc context",
    "Do not call plugin helper scripts",
    "Handoff saved: <absolute path>",
):
    if snippet not in save_text:
        raise SystemExit(f"save-handoff missing required text: {snippet}")

load_text = (root / "skills/load-handoff/SKILL.md").read_text(encoding="utf-8")
for snippet in (
    "strictly read-only",
    "newest handoff whose frontmatter `branch` matches",
    "git branch --show-current",
    "git log -1 --oneline",
    "git status --short --branch --untracked-files=all",
    "resume pointer, not current truth",
):
    if snippet not in load_text:
        raise SystemExit(f"load-handoff missing required text: {snippet}")

search_text = (root / "skills/search-handoffs/SKILL.md").read_text(encoding="utf-8")
for snippet in (
    "read-only",
    "rg -n --context 3 --fixed-strings",
    "No handoffs directory found for this project.",
    "No handoffs matched `<query>`.",
):
    if snippet not in search_text:
        raise SystemExit(f"search-handoffs missing required text: {snippet}")

readme_text = (root / "README.md").read_text(encoding="utf-8")
for snippet in (
    "skill-only",
    "/quicksave`, `/summary`, and `/distill` are retired",
    "resume pointers, not live truth",
    "does not ship runtime modules, helper scripts, command hooks, validators",
):
    if snippet not in readme_text:
        raise SystemExit(f"README missing required text: {snippet}")

format_text = (root / "references/handoff-format.md").read_text(encoding="utf-8")
for snippet in (
    "<project_root>/.codex/handoffs/",
    "created_at:",
    "Could future Codex continue without wasting time",
    "evidence, not truth",
):
    if snippet not in format_text:
        raise SystemExit(f"handoff-format missing required text: {snippet}")

print("handoff skill-only source contract ok")
PY
```

## Task 0: Establish Execution Baseline

**Files:** none

- [ ] **Step 1: Confirm branch, HEAD, and worktree**

Run:

```bash
git status --short --branch --untracked-files=all
git branch --show-current
git log -1 --oneline
```

Expected: current branch and dirty state are understood before edits. If unrelated dirty files exist, preserve them and stage only Handoff redesign paths later.

- [ ] **Step 2: Create the execution branch when starting from `main`**

Run:

```bash
git switch -c feature/handoff-skill-only-redesign
```

Expected: new branch `feature/handoff-skill-only-redesign`. If already on that branch, stay there.

- [ ] **Step 3: Run the source-contract check before edits**

Run the full command from **Source-Contract Check**.

Expected: FAIL with `inventory mismatch` and extra files such as `turbo_mode_handoff_runtime/...`, `scripts/...`, `tests/...`, `skills/distill/...`, `skills/quicksave/...`, and `skills/save-summary/...`. This confirms the check detects the current old source shape.

## Task 1: Replace Plugin Metadata And Top-Level Docs

**Files:**
- Modify: `plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/handoff/README.md`
- Modify: `plugins/turbo-mode/handoff/PRIVACY.md`
- Modify: `plugins/turbo-mode/handoff/TERMS.md`
- Keep unchanged: `plugins/turbo-mode/handoff/LICENSE`

- [ ] **Step 1: Replace plugin metadata**

Write this exact JSON to `plugins/turbo-mode/handoff/.codex-plugin/plugin.json`:

```json
{
  "name": "handoff",
  "version": "2.0.0",
  "description": "Skill-only session continuity with Markdown handoffs",
  "author": {
    "name": "JP"
  },
  "license": "MIT",
  "keywords": [
    "handoff",
    "session",
    "context",
    "continuity",
    "markdown",
    "search"
  ],
  "skills": "./skills/",
  "interface": {
    "displayName": "Handoff",
    "shortDescription": "Save, load, and search Markdown handoffs",
    "longDescription": "Save Markdown handoffs for session continuity, load handoffs as read-only resume context, and search project handoffs with plain text search.",
    "developerName": "JP",
    "category": "Productivity",
    "capabilities": [
      "Interactive",
      "Read",
      "Write"
    ],
    "defaultPrompt": [
      "Save a handoff for this session",
      "Load the latest handoff",
      "Search handoffs for a decision"
    ],
    "websiteURL": "https://github.com/jpsweeney97/codex-tool-dev/tree/main/plugins/turbo-mode/handoff",
    "privacyPolicyURL": "https://github.com/jpsweeney97/codex-tool-dev/blob/main/plugins/turbo-mode/handoff/PRIVACY.md",
    "termsOfServiceURL": "https://github.com/jpsweeney97/codex-tool-dev/blob/main/plugins/turbo-mode/handoff/TERMS.md",
    "brandColor": "#2563EB",
    "screenshots": []
  }
}
```

- [ ] **Step 2: Replace README**

Write this exact Markdown to `plugins/turbo-mode/handoff/README.md`:

````markdown
# Handoff

Handoff is a skill-only Codex plugin for session continuity. It helps Codex save, load, and search Markdown handoffs under the current project's `.codex/handoffs/` directory.

Handoffs are resume pointers, not live truth. A future session should read the handoff, check the live repository or working directory, and then continue from what still matches reality.

## Installation

Bundled in the `turbo-mode` marketplace:

```bash
codex plugin marketplace update turbo-mode
codex plugin install handoff@turbo-mode
```

Or install directly from the development repo:

```bash
codex plugin install ./plugins/turbo-mode/handoff
```

## What It Does

| Skill | Purpose |
| --- | --- |
| `/save` | Writes a Markdown handoff with session context and project-arc context. |
| `/load` | Reads a handoff as context, then checks live repository or working-directory state before recommending action. |
| `/search` | Searches project handoffs with `rg`. Literal search is the default; regex is used only when requested. |

Handoff does not ship runtime modules, helper scripts, command hooks, validators, transaction state, chain state, archive-on-load behavior, recovery protocols, or durable learning extraction.

`/quicksave`, `/summary`, and `/distill` are retired behavior. They are not wrappers, aliases, or compatibility entry points in this source bundle.

## Storage

Primary storage is:

```text
<project_root>/.codex/handoffs/
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

Handoff filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

Writes use direct path selection with no hidden state:

1. Create `<project_root>/.codex/handoffs/` if needed.
2. Choose the timestamp path.
3. Write with an exclusive-create primitive.
4. If the path exists, append `-2`, `-3`, and so on before `.md` until a free path is found.
5. If the direct write fails for any other reason, stop and report the write failure plainly.

The plugin does not add gitignore rules, stage files, commit files, auto-prune files, or manage cross-machine continuity. Whether `.codex/handoffs/` is tracked or ignored remains host-repository policy.

## Handoff Format

Handoffs are Markdown files with minimal YAML frontmatter. See `references/handoff-format.md`.

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

`created_at`, `type`, `title`, and `project` should be present. Include `branch` and `commit` when available.

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

These headings are prompts, not a schema. The quality bar is the resumption test: could future Codex continue without wasting time, repeating avoidable exploration, or trusting a stale claim?

## Boundaries

- `/save` is the only write-oriented skill.
- `/load` and `/search` are read-only.
- Loading never archives, moves, copies, edits, deletes, marks consumed, or writes recovery metadata.
- Searching does not parse a custom schema, build an index, rank semantically, deduplicate, or mutate files.
- Source shape does not prove installed runtime behavior. Plugin install, local cache refresh, marketplace update, or current-thread runtime reload require separate explicit proof.
````

- [ ] **Step 3: Replace privacy policy**

Write this exact Markdown to `plugins/turbo-mode/handoff/PRIVACY.md`:

```markdown
# Handoff Privacy Policy

Handoff stores user-created Markdown handoffs in the local workspace paths documented by the plugin.

The plugin does not add telemetry, analytics, background network transmission, runtime helpers, command hooks, or hidden state files. It does not transmit handoff contents by itself.

Repository owners remain responsible for their own storage, retention, backup, sharing, and version-control policy for files created by Handoff.
```

- [ ] **Step 4: Replace terms**

Write this exact Markdown to `plugins/turbo-mode/handoff/TERMS.md`:

```markdown
# Handoff Terms of Service

Handoff is a local Codex plugin for saving, loading, and searching Markdown handoffs.

The plugin manifest declares the Handoff plugin under the MIT license. The plugin is provided without warranty.

Users are responsible for the content they create with Handoff and for following the repository, organization, and platform policies that apply to that content.
```

- [ ] **Step 5: Verify metadata parses and no retired capability is advertised**

Run:

```bash
python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json
rg -n "distill|quicksave|save-summary|durable learning|chain state|transaction|runtime helper|command hook|validator" plugins/turbo-mode/handoff/.codex-plugin/plugin.json plugins/turbo-mode/handoff/README.md plugins/turbo-mode/handoff/PRIVACY.md plugins/turbo-mode/handoff/TERMS.md
```

Expected:
- `python -m json.tool` prints formatted JSON and exits 0.
- `rg` matches only the README retired-behavior or non-capability notes, plus the explicit `runtime helpers`, `command hooks`, and `hidden state files` non-capability language in `PRIVACY.md`.

## Task 2: Replace The Three Surviving Skills

**Files:**
- Modify: `plugins/turbo-mode/handoff/skills/save-handoff/SKILL.md`
- Modify: `plugins/turbo-mode/handoff/skills/load-handoff/SKILL.md`
- Modify: `plugins/turbo-mode/handoff/skills/search-handoffs/SKILL.md`
- Keep unchanged: `plugins/turbo-mode/handoff/skills/save-handoff/agents/openai.yaml`
- Keep unchanged: `plugins/turbo-mode/handoff/skills/load-handoff/agents/openai.yaml`
- Keep unchanged: `plugins/turbo-mode/handoff/skills/search-handoffs/agents/openai.yaml`

- [ ] **Step 1: Confirm the old skills still reference retired machinery**

Run:

```bash
rg -n "session_state.py|load_transactions.py|active-writer|archive|transaction|chain|synthesis-guide|pyproject.toml|scripts/" plugins/turbo-mode/handoff/skills/save-handoff/SKILL.md plugins/turbo-mode/handoff/skills/load-handoff/SKILL.md plugins/turbo-mode/handoff/skills/search-handoffs/SKILL.md
```

Expected: matches in the old skill files. This is the failing source-contract evidence for the skill text.

- [ ] **Step 2: Replace `save-handoff`**

Write this exact Markdown to `plugins/turbo-mode/handoff/skills/save-handoff/SKILL.md`:

````markdown
---
name: save-handoff
description: Use when user says "/save", "wrap this up", "new session", "almost out of context", "save", "next session", or "handoff"; use when stopping work with context to preserve.
---

# Save Handoff

Create a Markdown handoff at `<project_root>/.codex/handoffs/` so a future Codex session can resume without avoidable re-exploration.

Use this for real session boundaries where there is useful context to preserve: decisions, changed files, current state, risks, open questions, or the next action.

Do not use this to resume prior work; use `load-handoff`.

## What To Capture

Every saved handoff should include both:

- session context: what happened in this session, what changed, what was decided, what is in flight
- project-arc context: where the broader project stands, why this session matters, what prior decisions are load-bearing, and what future Codex should not forget

Use `../../references/handoff-format.md` when you need the recommended frontmatter and section prompts.

## Storage

Primary storage is:

```text
<project_root>/.codex/handoffs/
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

Handoff filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

Use a short lowercase slug from the requested title or session topic. Replace spaces with hyphens and omit punctuation that is awkward in filenames.

## Direct Write Procedure

1. Gather current context, current working directory, and git branch/commit when available.
2. Create `<project_root>/.codex/handoffs/` if needed.
3. Choose the timestamp path.
4. Write the Markdown file with an exclusive-create primitive, such as an `Add File` patch or a file API opened in exclusive-create mode.
5. If the path exists, append `-2`, `-3`, and so on before `.md` until a free path is found.
6. If the direct write fails for any other reason, stop and report the file write failure plainly.
7. Reply only with:

```text
Handoff saved: <absolute path>
```

Do not reproduce the full handoff in chat.

## Boundaries

- Do not call plugin helper scripts.
- Do not create transaction state, active-write reservations, chain state, consumed markers, content hashes, recovery metadata, or `.session-state` files.
- Do not fall back to `docs/handoffs/`.
- Do not add gitignore rules, stage files, commit files, auto-prune files, or manage cross-machine continuity.
- Whether `.codex/handoffs/` is tracked or ignored remains host-repository policy.
````

- [ ] **Step 3: Replace `load-handoff`**

Write this exact Markdown to `plugins/turbo-mode/handoff/skills/load-handoff/SKILL.md`:

````markdown
---
name: load-handoff
description: Use when continuing from a previous session, when user runs `/load` to load the most recent handoff, or when user runs `/load <path>` for a specific handoff.
---

# Load Handoff

Load an existing Markdown handoff as read-only context. The handoff is a resume pointer, not current truth.

This skill never archives, moves, copies, edits, deletes, marks consumed, writes state, or creates recovery metadata.

## Use

- Use for `/load`, `/load <path>`, "continue from where we left off", or "pick up the latest handoff."
- If no handoff exists, report that plainly. Suggest `/save` only if there is current context worth preserving.
- If a provided path does not exist, report `Handoff not found at <path>` and stop.

## Selection

Default search scope for implicit `/load`:

```text
<project_root>/.codex/handoffs/*.md
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

For implicit `/load`, first determine the current branch when inside a git repository. Then choose the newest handoff whose frontmatter `branch` matches the current branch when both values are available. If no branch-matching handoff exists, choose the newest handoff by filename timestamp. File modification time is an acceptable fallback if filenames do not sort usefully.

This is deterministic selection, not semantic ranking or an index.

For explicit `/load <path>`, read exactly that path if it exists. Read an archived or legacy path only when the user explicitly provides that path. Do not automatically search legacy locations.

## Live-Reality Check

After reading the handoff, run a live-reality check before treating it as actionable.

Inside a git repository, run:

```bash
git branch --show-current
git log -1 --oneline
git status --short --branch --untracked-files=all
```

Outside a git repository, do not fail the load just because git state is unavailable. Report the current working directory and state that git state is unavailable because the directory is not a git repository.

If the selected handoff names a branch or commit that differs from live state, call out the mismatch before recommending action.

If the handoff names specific important files, read those live files before making claims that depend on them.

## Response Shape

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

Keep the response focused. Do not display the full handoff unless the user asks for the full text.
````

- [ ] **Step 4: Replace `search-handoffs`**

Write this exact Markdown to `plugins/turbo-mode/handoff/skills/search-handoffs/SKILL.md`:

````markdown
---
name: search-handoffs
description: Search across Markdown handoffs for decisions and context. Use when user says "search handoffs", "find in handoffs", "what did we decide about", or runs `/search <query>`.
---

# Search Handoffs

Search project Markdown handoffs as a read-only convenience. This skill does not parse a custom schema, build an index, rank semantically, deduplicate, or mutate files.

## Scope

Default search scope:

```text
<project_root>/.codex/handoffs/
```

Project root resolution:

1. Use `git rev-parse --show-toplevel` when the current directory is inside a git repository.
2. Otherwise use the current working directory.

If no `.codex/handoffs/` directory exists, report:

```text
No handoffs directory found for this project.
```

## Literal Search

Use literal search by default:

```bash
rg -n --context 3 --fixed-strings "<query>" "$PROJECT_ROOT/.codex/handoffs"
```

If there are no matches, report:

```text
No handoffs matched `<query>`.
```

## Regex Search

Use regex only when the user explicitly asks for regex:

```bash
rg -n --context 3 "<pattern>" "$PROJECT_ROOT/.codex/handoffs"
```

## Results

For a small number of matches, show the matching path, line number, and surrounding context.

For many matches, show a useful handful and offer to narrow. Suggest `/load <path>` when one result looks like the right continuation artifact.
````

- [ ] **Step 5: Verify surviving skill metadata**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run python - <<'PY'
from pathlib import Path

import yaml

root = Path("plugins/turbo-mode/handoff/skills")
for name in ("save-handoff", "load-handoff", "search-handoffs"):
    skill = root / name / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), skill
    _, raw, _ = text.split("---", 2)
    frontmatter = yaml.safe_load(raw)
    assert frontmatter["name"] == name, frontmatter
    assert isinstance(frontmatter["description"], str) and frontmatter["description"].strip()

    agent = yaml.safe_load((root / name / "agents/openai.yaml").read_text(encoding="utf-8"))
    assert set(agent) == {"interface"}, agent
    assert set(agent["interface"]) == {"display_name"}, agent

print("skill metadata ok")
PY
```

Expected: `skill metadata ok`.

## Task 3: Add Format Reference And Remove Retired Source Surfaces

**Files:**
- Create: `plugins/turbo-mode/handoff/references/handoff-format.md`
- Delete: `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/`
- Delete: `plugins/turbo-mode/handoff/scripts/`
- Delete: `plugins/turbo-mode/handoff/hooks/`
- Delete: `plugins/turbo-mode/handoff/tests/`
- Delete: `plugins/turbo-mode/handoff/pyproject.toml`
- Delete: `plugins/turbo-mode/handoff/uv.lock`
- Delete: `plugins/turbo-mode/handoff/CHANGELOG.md`
- Delete: `plugins/turbo-mode/handoff/CONTRIBUTING.md`
- Delete: `plugins/turbo-mode/handoff/references/ARCHITECTURE.md`
- Delete: `plugins/turbo-mode/handoff/references/handoff-contract.md`
- Delete: `plugins/turbo-mode/handoff/references/format-reference.md`
- Delete: `plugins/turbo-mode/handoff/references/skill-details.md`
- Delete: `plugins/turbo-mode/handoff/skills/save-handoff/synthesis-guide.md`
- Delete: `plugins/turbo-mode/handoff/skills/distill/`
- Delete: `plugins/turbo-mode/handoff/skills/quicksave/`
- Delete: `plugins/turbo-mode/handoff/skills/save-summary/`

- [ ] **Step 1: Add the new short format reference**

Write this exact Markdown to `plugins/turbo-mode/handoff/references/handoff-format.md`:

````markdown
# Handoff Format

Handoffs are Markdown notes under:

```text
<project_root>/.codex/handoffs/
```

Filenames use:

```text
YYYY-MM-DD_HH-MM-SS_<slug>.md
```

## Frontmatter

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

In practice, `created_at`, `type`, `title`, and `project` should be present. Include `branch` and `commit` when available.

Do not require `session_id`, `resumed_from`, or `files`.

## Body Prompts

Use the sections that make the next session successful:

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

These headings are prompts, not a schema. There is no line-count target, section-count validator, confidence field, evidence-level taxonomy, or required decision template.

## Compact Example

```markdown
---
created_at: "2026-06-09T14:30:00Z"
type: handoff
title: "Skill-only Handoff redesign"
project: codex-tool-dev
branch: feature/handoff-skill-only-redesign
commit: abc1234
---

# Handoff: Skill-only Handoff redesign

## Session Context

The Handoff source bundle was reduced to three skills and one format reference. Runtime helpers, hook metadata, tests, and retired skill entry points were removed from source.

## Project Arc

The broader goal is to keep Handoff plain: Codex writes a useful Markdown note, later reads it as context, checks live reality, and continues.

## Evidence Checked

- `git status --short --branch --untracked-files=all`
- `python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json`
- source inventory check for the approved bundle shape

## Current State

Source verification passed. Installed runtime was not refreshed or proven.

## Next Action

If runtime pickup matters, run a separate explicit plugin refresh and runtime inventory proof.
```

## Resumption Test

Could future Codex continue without wasting time, repeating avoidable exploration, or trusting a stale claim?

## Evidence Boundary

Handoffs are evidence, not truth. A future session should check the live branch, HEAD, worktree, and any important files before acting on a handoff claim.
````

- [ ] **Step 2: Delete retired files and directories with `trash`**

Run:

```bash
trash plugins/turbo-mode/handoff/turbo_mode_handoff_runtime
trash plugins/turbo-mode/handoff/scripts
trash plugins/turbo-mode/handoff/hooks
trash plugins/turbo-mode/handoff/tests
trash plugins/turbo-mode/handoff/pyproject.toml
trash plugins/turbo-mode/handoff/uv.lock
trash plugins/turbo-mode/handoff/CHANGELOG.md
trash plugins/turbo-mode/handoff/CONTRIBUTING.md
trash plugins/turbo-mode/handoff/references/ARCHITECTURE.md
trash plugins/turbo-mode/handoff/references/handoff-contract.md
trash plugins/turbo-mode/handoff/references/format-reference.md
trash plugins/turbo-mode/handoff/references/skill-details.md
trash plugins/turbo-mode/handoff/skills/save-handoff/synthesis-guide.md
trash plugins/turbo-mode/handoff/skills/distill
trash plugins/turbo-mode/handoff/skills/quicksave
trash plugins/turbo-mode/handoff/skills/save-summary
```

Expected: the files and directories are moved to Trash, and `git status --short plugins/turbo-mode/handoff` shows deletions for tracked retired surfaces.

- [ ] **Step 3: Run the source-contract check**

Run the full command from **Source-Contract Check**.

Expected:

```text
handoff skill-only source contract ok
```

- [ ] **Step 4: Inspect negative matches for retired concepts**

Run:

```bash
rg -n "distill|quicksave|save-summary|active-write|chain state|transaction|session_state.py|quality_check|turbo_mode_handoff_runtime" plugins/turbo-mode/handoff
```

Expected: matches are limited to short retired-behavior or non-capability notes in `README.md`, or no matches. There must be no positive or instructional mention of retired behavior.

- [ ] **Step 5: Verify source shape and whitespace**

Run:

```bash
git status --short --branch --untracked-files=all
python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json
git diff --check
```

Expected:
- status shows only the intended Handoff source changes
- JSON parses
- `git diff --check` exits 0

## Task 4: Check Adjacent Source References Without Expanding Scope

**Files:** none unless the check finds current-facing source that blocks the redesigned plugin source from being truthful

- [ ] **Step 1: Search adjacent tooling and docs for stale Handoff runtime assumptions**

Run:

```bash
rg -n "handoff/.*/skills/(save|load|search|quicksave|summary|distill)|save-summary|quicksave|distill|turbo_mode_handoff_runtime|session_state.py|load_transactions.py" plugins/turbo-mode/tools .agents .codex docs/superpowers/specs docs/superpowers/plans
```

Expected: matches may exist in historical docs, ignored local handoffs, and refresh tooling tests or fixtures. Do not edit historical docs or local handoffs. Do not mutate installed cache or personal plugin copies.

- [ ] **Step 2: Decide whether any adjacent source edit is required**

Use this decision rule:

```text
If a match is inside plugins/turbo-mode/handoff/, it is in scope and must be fixed.
If a match is a historical plan, spec, audit, or handoff outside plugins/turbo-mode/handoff/, leave it alone.
If a match is refresh tooling that only describes historical cache/runtime drift behavior, leave it alone for this source-only redesign and mention it as follow-up risk.
If a match is current-facing metadata that would cause the source Handoff plugin to advertise or ship retired behavior, stop and add a focused follow-up task before committing.
```

Expected: no extra edits for the approved source-only redesign. If this expectation is wrong, add only the smallest source edit needed to prevent current-facing false advertising, then rerun Task 3 Step 3 and Task 3 Step 5.

## Task 5: Commit The Source Redesign

**Files:**
- Stage Handoff plugin source changes only

- [ ] **Step 1: Review the final diff**

Run:

```bash
git diff --stat
git diff -- plugins/turbo-mode/handoff
```

Expected: the diff shows metadata/doc/skill replacements, one new `references/handoff-format.md`, and deletions of the retired runtime, scripts, hooks, tests, retired skills, old references, and package files.

- [ ] **Step 2: Run final source verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

import yaml

root = Path("plugins/turbo-mode/handoff")
expected_files = {
    ".codex-plugin/plugin.json",
    "LICENSE",
    "PRIVACY.md",
    "README.md",
    "TERMS.md",
    "references/handoff-format.md",
    "skills/load-handoff/SKILL.md",
    "skills/load-handoff/agents/openai.yaml",
    "skills/save-handoff/SKILL.md",
    "skills/save-handoff/agents/openai.yaml",
    "skills/search-handoffs/SKILL.md",
    "skills/search-handoffs/agents/openai.yaml",
}
expected_dirs = {
    ".codex-plugin",
    "references",
    "skills",
    "skills/load-handoff",
    "skills/load-handoff/agents",
    "skills/save-handoff",
    "skills/save-handoff/agents",
    "skills/search-handoffs",
    "skills/search-handoffs/agents",
}
actual_files = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file() and path.name != ".DS_Store"
}
actual_dirs = {
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_dir()
}
if actual_files != expected_files or actual_dirs != expected_dirs:
    raise SystemExit(
        "inventory mismatch\n"
        f"missing_files={sorted(expected_files - actual_files)}\n"
        f"extra_files={sorted(actual_files - expected_files)}\n"
        f"missing_dirs={sorted(expected_dirs - actual_dirs)}\n"
        f"extra_dirs={sorted(actual_dirs - expected_dirs)}"
    )

plugin = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
assert plugin["version"] == "2.0.0"
assert plugin["interface"]["capabilities"] == ["Interactive", "Read", "Write"]
plugin_text = json.dumps(plugin, sort_keys=True).lower()
assert "distill" not in plugin_text
assert "quicksave" not in plugin_text
assert "summary" not in plugin_text

for name in ("save-handoff", "load-handoff", "search-handoffs"):
    skill = root / "skills" / name / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    _, raw, _ = text.split("---", 2)
    metadata = yaml.safe_load(raw)
    assert metadata["name"] == name
    agent = yaml.safe_load((root / "skills" / name / "agents/openai.yaml").read_text(encoding="utf-8"))
    assert list(agent) == ["interface"]
    assert list(agent["interface"]) == ["display_name"]

assert "exclusive-create" in (root / "skills/save-handoff/SKILL.md").read_text(encoding="utf-8")
assert "strictly read-only" in (root / "skills/load-handoff/SKILL.md").read_text(encoding="utf-8")
assert "rg -n --context 3 --fixed-strings" in (root / "skills/search-handoffs/SKILL.md").read_text(encoding="utf-8")
assert "resume pointers, not live truth" in (root / "README.md").read_text(encoding="utf-8")
assert "evidence, not truth" in (root / "references/handoff-format.md").read_text(encoding="utf-8")
print("handoff skill-only source contract ok")
PY
python -m json.tool plugins/turbo-mode/handoff/.codex-plugin/plugin.json
git diff --check
```

Expected:

```text
handoff skill-only source contract ok
```

Then formatted JSON output, then no `git diff --check` output.

- [ ] **Step 3: Stage only Handoff redesign paths**

Run:

```bash
git add plugins/turbo-mode/handoff/.codex-plugin/plugin.json
git add plugins/turbo-mode/handoff/README.md
git add plugins/turbo-mode/handoff/PRIVACY.md
git add plugins/turbo-mode/handoff/TERMS.md
git add plugins/turbo-mode/handoff/references/handoff-format.md
git add plugins/turbo-mode/handoff/skills/save-handoff/SKILL.md
git add plugins/turbo-mode/handoff/skills/load-handoff/SKILL.md
git add plugins/turbo-mode/handoff/skills/search-handoffs/SKILL.md
git add -u plugins/turbo-mode/handoff
```

Expected: only Handoff plugin source redesign changes are staged.

- [ ] **Step 4: Review staged diff**

Run:

```bash
git diff --cached --stat
git diff --cached -- plugins/turbo-mode/handoff
```

Expected: staged diff matches Task 5 Step 1 and contains no local handoff artifacts, installed cache changes, or unrelated files.

- [ ] **Step 5: Commit**

Run:

```bash
git commit -m "refactor: simplify handoff to skill-only source"
```

Expected: commit succeeds on `feature/handoff-skill-only-redesign`.

## Task 6: Final Status Report

**Files:** none

- [ ] **Step 1: Capture final source status**

Run:

```bash
git status --short --branch --untracked-files=all
git log -1 --oneline
```

Expected: branch and HEAD are clear. Any unrelated pre-existing work remains unstaged and is named separately.

- [ ] **Step 2: Report proof boundaries**

Final response must state:

```text
Source verification performed:
- plugin inventory contains only the approved skill-only bundle shape
- plugin JSON parses
- surviving skill frontmatter and agents/openai.yaml parse
- source-contract snippets for save/load/search, README, and handoff-format pass
- git diff --check passed

Not proven:
- installed plugin cache refresh
- marketplace install
- current-thread runtime reload
- app-server runtime inventory
```

If adjacent refresh tooling or historical docs still contain old Handoff terms, name them as outside the source-redesign proof unless they were intentionally patched.

## Acceptance Coverage

- Approved bundle shape: Tasks 3 and 5.
- Direct Markdown `/save` with session and project-arc context: Task 2.
- Exclusive-create no-overwrite path selection: Task 2 and Task 5 verification.
- Read-only `/load` with branch-aware implicit selection and live-state check: Task 2 and Task 5 verification.
- Read-only `rg` search: Task 2 and Task 5 verification.
- Retired `distill`, `quicksave`, and `save-summary` removed: Task 3.
- Current-facing README and metadata do not advertise retired behavior: Task 1, Task 3 Step 4, Task 5 verification.
- Source/shape verification passes: Task 5.
- Installed runtime proof is separated: Task 6.
