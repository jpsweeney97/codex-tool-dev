# Ticket Runtime-First Autonomy PR #22 Review Repair Closeout

Date: 2026-05-28
Branch: `feature/ticket-runtime-first-autonomy-v1`
Scope: source-only PR #22 repair; no installed runtime or cache refresh proof.

## Verified Repair Summary

The pre-merge repair set addressed the verified action items from the Claude
review synthesis and Codex source verification:

- C1: `APPLY_CORRECTION` now routes through `apply-turn` and the runtime-first
  gateway instead of being recorded as discussion-only.
- C2: `recover` now projects pending-summary recovery state, reports whether
  new autonomous writes can proceed, and points repairable gaps to
  `doctor-ledger --confirm-repair`.
- C4: autonomous create checks duplicate candidates before writing.
- C5: gateway approval validation rebinds the approval to the live
  `GatewayMutation` fingerprint.
- C6: automatic `## Change History` is built into the engine's single ticket
  write instead of being appended by a second gateway rewrite.
- C7: gateway writes run under a per-ticket or per-create write lock that covers
  fingerprint validation, pause checks, approval consumption, dispatch, and
  post-write fingerprint capture.
- C8: pause is checked before attempt bookkeeping and again immediately before
  dispatch after approval consumption.
- C11: successful engine responses without a string `ticket_path` are treated as
  failed gateway mutations, not as applied writes.
- C13: `doctor-ledger` now performs deterministic dry-run inspection and
  confirmed repair for projection gaps.
- C15: README and HANDBOOK now list the host-facing autonomy command set.

C3 is qualified rather than accepted as a critical bug as originally worded:
`--setup-choice` remains the setup path, but clearing a pause now requires the
explicit `--resume-paused` signal and ledger/local-state checks.

C14 is documented as "undocumented rather than proven absent." This closeout
records the Development Tenet Test 4 result below.

## Development Tenet Test 4

Trigger: PR #22 grew the Ticket Codex-facing autonomy surface by more than the
~50% review threshold called out in `AGENTS.md`. The review therefore covers the
full current Ticket autonomy surface, not only the newly repaired lines.

Test 1 - Whose failure is it?

- Keep: ticket metadata, candidate mutation fields, Change History entries,
  pending-summary events, approvals, and mode snapshots. Wrong values here can
  mislead the work product, lose recovery evidence, or authorize the wrong
  Ticket mutation.
- Watch: mutation IDs, approval IDs, event IDs, and recovery projection states.
  These are machinery fields, but they preserve cross-turn recovery and one-use
  write authorization. They are justified only while Python owns their
  construction.

Test 2 - Tooling or thinking?

- The current surface is tooling-heavy. That is acceptable for this source slice
  because Python adapters construct the strict JSON payloads and ledger records.
- The merge boundary is: Codex-facing skills must not ask Codex to manually fill
  pending-summary, approval, or recovery-projection machinery fields. If a
  future skill exposes those fields directly to Codex, this Test 4 result no
  longer holds and the surface must be redesigned or narrowed.

Test 3 - Could Codex do this inline?

- Keep deterministic mechanics in code: field allowlists, destructive-action
  denylists, duplicate detection, fingerprint comparison, pause gates, ledger
  projection, and commit disposition recording.
- Review later: evidence-floor and fanout heuristics remain semantic workflow
  decisions. They are not expanded in this repair. Before installed runtime
  activation, either document why they remain as bounded judgment support or
  move the decision back to Codex-facing prose.

Test 4 conclusion:

PR #22 remains mergeable as a source-only repair after the verified blocker set
is fixed and tests pass. Installed runtime activation remains blocked until a
separate proof lane verifies the source/cache/runtime boundary and revisits any
Codex-facing skill that would directly construct strict autonomy payloads.

