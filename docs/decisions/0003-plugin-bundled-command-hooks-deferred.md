# ADR 0003 — Plugin-bundled command hooks deferred from 1.6.0

- **Status:** Accepted (back-fill record; reflects shipped 1.6.0/1.7.0 posture)
- **Scope:** `plugins/turbo-mode/handoff/1.6.0/hooks/`, `turbo_mode_handoff_runtime/quality_check.py`

## Context

Handoff has hook-compatible validation/cleanup code (e.g. `quality_check.py`,
`cleanup.py`) that could run as Codex command hooks. However, Codex did not yet
expose a documented, portable plugin-root launcher contract, so a bundled hook
command path could not be specified reliably across installs.

## Decision

Handoff does not ship plugin-bundled command hooks in this release.
`hooks/hooks.json` is intentionally empty. The hook-compatible scripts remain in
source as dormant, non-gating utilities (not wired into skill entrypoints).
Plugin-bundled command hooks are deferred until Codex provides a documented
portable launcher contract, or a separate generated-config architecture is
designed and proven.

## Consequences

- `quality_check.py` is non-gating in this release; its fail-closed broad-except
  behavior is correct only because nothing wires it as a gate.
- The empty `hooks/hooks.json` is a deliberate contract, not missing work, and
  must not be described as a debt or gap.
- Revisiting requires a documented launcher contract or an approved
  generated-config design; that change would re-open this ADR.
