# T-20260508-02: Classify and harden Turbo Mode migration tooling real-home paths

```yaml
id: T-20260508-02
date: "2026-05-08"
created_at: "2026-05-08T17:11:41Z"
status: open
priority: medium
effort: M
source:
  type: ad-hoc
  ref: ""
  session: codex-followup-pr5
tags: [turbo-mode, migration, safety, path-authority]
blocked_by: []
blocks: []
contract_version: "1.0"
```

## Problem
The migration toolchain under plugins/turbo-mode/tools/migration still contains hardcoded /Users/jp/.codex paths. Some may be historical one-shot evidence boundaries and some may be maintained runnable tools. Classify each script before changing behavior, then harden only maintained tooling so real-home assumptions do not silently bypass operator safety.

## Acceptance Criteria
- [ ] Inventory every migration script containing /Users/jp/.codex and classify it as maintained runnable tooling or historical one-shot evidence tooling.
- [ ] Maintained scripts derive codex_home, repo_root, and local-only roots from explicit CLI/env/default Path.home() based inputs rather than hardcoded /Users/jp paths.
- [ ] Historical scripts are clearly labeled archival and are not implied to satisfy current refresh safety invariants.
- [ ] Tests cover at least one non-jp operator home for maintained migration tooling.
- [ ] No changes claim fresh migration evidence, fresh live installed-cache proof, or current guarded-refresh source/cache alignment.
