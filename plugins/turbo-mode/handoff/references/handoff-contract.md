# Handoff Contract

Shared contract for all handoff plugin skills. Loaded by save, quicksave, and load.

## Session IDs

Codex does not inject a stable skill-level session UUID. Instead:

- `save`, `quicksave`, and `summary` generate a fresh UUID when they write a handoff, checkpoint, or summary
- `load` uses a per-project resume state file rather than a per-session one

The `session_id` frontmatter field remains required and should always be a UUID generated at write time.

## Frontmatter Schema

All handoff files (checkpoints and full handoffs) use this frontmatter:

```yaml
---
date: YYYY-MM-DD                    # Required
time: "HH:MM"                       # Required (quoted for YAML)
created_at: "YYYY-MM-DDTHH:MM:SSZ"  # Required: ISO 8601 UTC
session_id: <UUID>                   # Required: generated at write time
resumed_from: <path>                 # Optional: archive path if resumed
project: <project-name>             # Required: git root or directory name
branch: <branch-name>               # Optional: current git branch
commit: <short-hash>                # Optional: short commit hash
title: <descriptive-title>          # Required
type: <handoff|checkpoint|summary>   # Required: distinguishes file type
files:
  - <key files touched>             # List of relevant files
---
```

**Type field:** `handoff` for full handoffs, `checkpoint` for checkpoints, `summary` for summaries. Existing files without a `type` field are treated as `handoff` for backwards compatibility.

**Title convention:** Checkpoint titles use `"Checkpoint: <title>"` prefix. Summary titles use `"Summary: <title>"` prefix. Full handoff titles have no prefix.

## Chain Protocol

The chain protocol enables `resumed_from` tracking across sessions. Three skills participate:

**Resume (load) — writes state:**
1. Archive the handoff to `<project_root>/.codex/handoffs/archive/<filename>`
2. Write archive state to `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`

**Save/Quicksave/Summary (save, quicksave, summary) — reads and cleans state:**
1. **Read:** Check `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json` — if exists, include the archive path as `resumed_from` in frontmatter
2. **Write:** Write the new handoff/checkpoint/summary through the active-writer reservation helper
3. **Cleanup:** Clear the consumed primary JSON state file and any matching legacy bridge after the new artifact is written. If cleanup warns, report it but do not block artifact creation — the 24-hour TTL will clean it up.

**Invariant:** State files are created by load; the next save/quicksave/summary reads them to populate `resumed_from`, then attempts cleanup via `trash`. Active writers may bridge one valid legacy state file and mark that source consumed without modifying legacy bytes. If cleanup fails, the file may persist until TTL pruning (24 hours). A state file that persists beyond 24 hours is stale.

## Storage

| Location | Format | Retention |
|----------|--------|-----------|
| `<project_root>/.codex/handoffs/` | `YYYY-MM-DD_HH-MM_<slug>.md` | No auto-prune |
| `<project_root>/.codex/handoffs/archive/` | Same | No auto-prune |
| `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json` | JSON resume state | 24 hours |

**Filename slug:** Lowercase, hyphens for spaces, no special characters. Checkpoints use `checkpoint-<slug>`, summaries use `summary-<slug>`, full handoffs use `<slug>` directly.

## Git Tracking

The plugin writes filesystem artifacts only. It does not add gitignore rules, stage files, or auto-commit files.
Whether `.codex/handoffs/` is tracked or ignored is host-repository policy, not a plugin invariant. Implications:

- `/save`, `/load`, and `/quicksave` write or move files on the filesystem only. No git operations fire.
- `/search` and `/distill` read via Python `open()` — gitignore status is invisible to them.
- Chain protocol (`resumed_from`, state files) is filesystem-based and unaffected by git tracking.

The plugin does not manage cross-machine continuity. If cross-machine continuity is needed, copy individual files manually or rely on the host repository's tracking policy.

## Project Root

The project root determines where handoff files are stored. Resolved by:
1. `git rev-parse --show-toplevel` (if in a git repo)
2. Current working directory (fallback)

The full project root path is used for storage resolution — handoff files live at `<project_root>/.codex/handoffs/`.

## Git Detection

If `.git/` exists in current or parent directories, include `branch` and `commit` in frontmatter. Otherwise omit them entirely (no placeholders).

## Write Permission

If `<project_root>/.codex/handoffs/` is not writable (or cannot be created), **STOP** and report the active-writer helper error. Do not write a manual fallback path unless the user explicitly directs a different storage location.

## Precedence

This contract is canonical for cross-skill invariants: frontmatter field definitions, type semantics, chain protocol, and storage/retention. `format-reference.md` is canonical for section content guidance, depth targets, quality calibration, and examples. If `format-reference.md` conflicts with this contract, **this contract wins**.

**Schema drift note:** Skills may contain partial field lists in Definition of Done tables and Verification checklists. These are non-canonical summaries — this contract governs. If a skill's field list diverges from this schema, update the skill to match the contract.

## Known Limitations

Three inherited issues from the current chain protocol design. These are pre-existing — not introduced by the checkpoint tier.

1. **Resume-crash recovery:** If a session resumes a handoff but crashes before creating a new one, the state file persists but no successor handoff references the archived file. The chain has a gap. No automated recovery — the archived file is intact and can be manually re-loaded. The orphaned state file is pruned by the 24-hour TTL.

2. **Archive-failure chain poisoning:** If archive creation fails but the state file is written, the `resumed_from` path in the next handoff/checkpoint points to a non-existent file. Skills should not fail on a missing `resumed_from` target — treat as informational metadata.

3. **State-file TTL race:** State files are pruned after 24 hours by cleanup.py. If a session spans >24 hours (rare), the state file may be pruned before the next save/quicksave reads it. Result: missing `resumed_from` in the next file. Not data loss — the chain link is skipped.
