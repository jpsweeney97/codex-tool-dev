---
name: test-trust-audit
description: "Use when asking whether a green test suite can be trusted — before leaning on it for a refactor, upgrade, or release: sweep for skipped and quarantined growth, assertion-free and tautological tests, mocks asserting mocks, rubber-stamped snapshots, and coverage that executes without checking, optionally probing a sample with deliberate mutations. Read-only findings with citations, no score, no certificate. Not for fixing failures (keep-green), authoring tests (tdd), or reviewing a diff (implementation-review)."
---

# Test Trust Audit

The suite is green; this skill asks whether green means anything — an evidence-led sweep for the ways green lies, read-only by default, certifying nothing. Invocation: `/test-trust-audit` or `$test-trust-audit`.

A sweep over one existing green suite for the hollow-green patterns: skip and quarantine drift, assertion-free tests, tautological tests, mocks asserting mocks, snapshot rubber-stamping, and coverage that executes without checking — plus an optional, opt-in, strictly contained mutation probe that samples whether the suite catches a deliberate behavior change. The product is a findings list with file:line evidence, ordered by how badly each finding undermines trust. It fixes nothing, scores nothing, and certifies nothing.

## Shape — the sweep

Six classes, swept every run — each with its detection route and its judgment question:

- **Skip/quarantine drift.** Count and age the skipped, expected-fail, and disabled tests — `skip`, `xfail`, `todo`, `.skip`, quarantine lists (pytest `skip`/`xfail`, jest `.skip`/`.todo`, Go `t.Skip` are anchors of the class, not an exhaustive reference). A skip with no linked reason is a finding; an expected-fail that now passes (XPASS) is its own finding — the mark is stale and hides signal. Judgment: is this quarantine tracked debt or a graveyard?
- **Assertion-free tests.** Test bodies where no assertion is reached, or where the assertion checks a constant or the truthiness of an unconditional value. Ran ≠ checked: such a test proves the code doesn't crash and is silent about everything else.
- **Tautological tests.** The expected value is derived from the code under test — the test calls the same function to compute its expectation, or re-asserts what the mock was told to return. This is the same defect `tdd` names at authoring time: the test passes by construction because its expectation does not come from an independent source of truth (a known literal, a worked example, the spec). Detect it here; route prevention to `tdd`.
- **Mocks asserting mocks.** The assertion inspects only mock state while every collaborator that would exercise real code is mocked out — the test proves the mocking framework works. Judgment: a mocked boundary can be legitimate isolation; the finding is when nothing real runs between arrange and assert.
- **Snapshot rubber-stamping.** Bulk snapshot-update commits — many snapshots changed in one commit with no reviewable source change — and giant snapshots nobody could have read. Git history is the evidence route here: `git log` on the snapshot dirs, looking for update-everything commits. Judgment: a snapshot is a contract only if a human read it when it changed.
- **Coverage-without-assertion.** Where coverage data already exists, read the high-coverage files whose covering tests assert little — execution without checking. Coverage is a pointer to where to read, never the product: this skill never computes or reports a coverage number as a result.

## The mutation probe — opt-in, contained

Off by default. Run it only when the user opts in AND `git status --short` shows a clean working tree AND the test runner is confirmed working. It deliberately edits product code, so the containment protocol is the contract, not a suggestion:

1. Verify the tree is clean before the first mutation.
2. Pick 3–5 load-bearing, well-covered functions.
3. One site at a time: introduce ONE deliberate behavior mutation — flip a comparison, off-by-one a boundary, invert a branch.
4. Run only the covering tests, not the whole suite; record caught or survived.
5. Restore the site and PROVE restoration with `git diff --exit-code` (or `git checkout -- <file>` followed by that proof) before touching the next site.

A surviving mutation is a concrete finding: name the mutation and the tests that stayed green. Never commit a mutation; never leave one behind on any exit path, including a test-runner failure mid-probe; if restoration cannot be proven, say so as the first line of the report. Probe findings are sampled-and-said: "3 of 5 sampled mutations survived", never "the suite catches N% of bugs". The probe also stays a handful: the moment it wants more than a handful of sampled mutations, that is a mutation-testing framework's job — use a real tool and say so.

## Output

A findings list ordered by how badly each finding undermines trust. Every finding carries: its class, file:line, the evidence itself (the test body excerpt, the git log line, the surviving mutation), and one sentence on what the test falsely proves.

No score, no grade, no "trustworthy"/"untrustworthy" verdict — never a trust score or a health grade. The close names what was swept, what was sampled, and what was not inspected: the suite's worst lie may be in the tests nobody read. Route the fixes out: authoring-time fixes to `tdd`; per-finding tracker items to `/triage` (or `$triage`) where available; and when the sweep shows the suite cannot be trusted to guard an imminent refactor, upgrade, or migration, hand forward to `/characterization-tests` (or `$characterization-tests`) to author the net that work needs first.

## Modes and scope

- Default is the read-only static sweep; the mutation probe runs only on explicit opt-in.
- One suite or package per run. Pointed at a monorepo, narrow to the named suite — or the riskiest, and say so: this is a sweep with a boundary, not a repo audit.

## Fences

- Red suite → `keep-green`; this skill takes only green suites.
- Authoring-time prevention, and every authoring-shaped fix found here → `tdd`.
- A completed change against spec plus diff → `review-family:implementation-review` where available.
- A scored, ranked repo-wide backlog → `tech-debt-scan`; this is one suite, deliberately unscored.
- Coverage tooling: this reads what coverage points at, never certifies a number — a percentage is never a finding by itself.

## Done when

- All six static classes are swept, with the detection route named per class.
- Every finding carries file:line evidence and one sentence on what it falsely proves.
- The probe, if opted in, ran under the full containment protocol with restoration proven per site.
- The close names the sweep's boundaries — swept, sampled, not inspected — and renders no certificate.
- Nothing was fixed, committed, or pushed.
