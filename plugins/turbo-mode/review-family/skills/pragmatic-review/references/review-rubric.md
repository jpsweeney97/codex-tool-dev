# Pragmatic Review Rubric

Use only when the main workflow needs calibration.

## Review Lens

- Safe-sounding steps that are brittle, ambiguous, or permission-bound.
- Gates blocked by infrastructure, environment, permission, or process.
- Proof labels that blur source, runtime, docs, certification, or release state.
- Ambiguous scope, authority, or verification target.
- Missing manifests, ledgers, owners, preflights, rollback criteria, or residue.
- Control points in the wrong authority surface.
- Tests that prove too little, prove the wrong layer, or cannot run at the gate.
- Assumptions overfit to local state, stale history, one checkout, or one cache.
- Simpler contracts that preserve safety with less execution drag.

## Evidence Classes

- **Source Truth**: source tree, tracked files, committed artifacts, repo tests.
- **Runtime Truth**: installed packages, caches, apps, CLIs, hooks, live output.
- **Docs Readiness**: internal consistency and authority alignment.
- **Certification**: approval, release, signoff, or policy state.

## Severity Calibration

- `P0`: destructive, unsafe, or invalid execution.
- `P1`: not executable, blocks implementation, or creates false proof/release.
- `P2`: brittle assumptions, hidden scope, missing ownership, or weak gates.
- `P3`: minor ambiguity that can still waste implementer time.

## Residual Risk Prompts

Before **Ready to Execute**, name unverified runtime, CI/release, generated
artifacts, branch/environment, rollback, recovery, or residue assumptions.
