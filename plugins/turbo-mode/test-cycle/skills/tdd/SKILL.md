---
name: tdd
description: "Use when the user wants to build a feature or fix a bug through test-driven development, red-green-refactor, tracer-bullet slices, or explicit test-first work. Do not use for adding tests after implementation, ordinary verification, test failure triage, broad test strategy, requests that merely mention integration tests, or fixing a bug whose cause is unclear, intermittent, or cross-component (`diagnose` finds the cause first)."
---

# Test-Driven Development

## Philosophy

**Core principle**: Tests should verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs. They describe _what_ the system does, not _how_ it does it. A good test reads like a specification - "user can checkout with valid cart" tells you exactly what capability exists. These tests survive refactors because they don't care about internal structure.

**Bad tests** are coupled to implementation. They mock internal collaborators, test private methods, or verify through external means (like querying a database directly instead of using the interface). The warning sign: your test breaks when you refactor, but behavior hasn't changed. If you rename an internal function and tests fail, those tests were testing implementation, not behavior. A second failure mode is the tautological test: the assertion recomputes the expected value the same way the code does, so it passes by construction — expected values must come from an independent source of truth (a known literal, a worked example, the spec).

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation.** This is "horizontal slicing" - treating RED as "write all tests" and GREEN as "write all code."

This produces **crap tests**:

- Tests written in bulk test _imagined_ behavior, not _actual_ behavior
- You end up testing the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests become insensitive to real changes - they pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: Vertical slices via tracer bullets. One test → one implementation → repeat. Each test responds to what you learned from the previous cycle. Because you just wrote the code, you know exactly what behavior matters and how to verify it.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```

## Workflow

### 1. Planning

When exploring the codebase, use the project's domain glossary so that test names and interface vocabulary match the project's language, and respect ADRs in the area you're touching.

**Fixing a known-cause bug?** The first move is different: write ONE failing test that reproduces the defect through the existing public interface - that reproduction is your RED. A bug fix usually keeps the interface and changes behavior behind it, so skip the interface-design and deep-module planning below unless the fix genuinely changes the surface. (Cause not yet understood? Stop - `/diagnose` or `$diagnose` finds it first, then hands the fix back here to lock in test-first.)

Before writing any code:

- [ ] Confirm with user what interface changes are needed
- [ ] Confirm with user which behaviors to test (prioritize)
- [ ] Identify opportunities for [deep modules](deep-modules.md) (small interface, deep implementation)
- [ ] Design interfaces for [testability](interface-design.md)
- [ ] List the behaviors to test (not implementation steps)
- [ ] Resolve this repo's real focused-test and full-suite commands — `keep-green`'s resolution rule (caller input first, else repo convention) owns how; prefer checked-in wrappers (`./gradlew`, `make test`, a repo script) over globally installed tools — and use those commands for every RED, GREEN, and closure run, never a default like `npm test`
- [ ] Get user approval on the plan

Ask: "What should the public interface look like? Which behaviors are most important to test?"

If running unattended with no user to confirm, do not stall: record the interface and behavior assumptions you are making explicitly, proceed on them, and surface them for review rather than treating the plan as approved silently.

**You can't test everything.** Confirm with the user exactly which behaviors matter most. Focus testing effort on critical paths and complex logic, not every possible edge case.

### 2. Tracer Bullet

Write ONE test that confirms ONE thing about the system:

```
RED:   Write test for first behavior → test fails
GREEN: Write minimal code to pass → test passes
```

This is your tracer bullet - proves the path works end-to-end.

### 3. Incremental Loop

For each remaining behavior:

```
RED:   Write next test → fails
GREEN: Minimal code to pass → passes
```

Rules:

- One test at a time
- Run the new test and watch it fail before implementing. A test that passes immediately is testing existing behavior; a test that errors for an unrelated reason needs fixing first. A test you never saw fail proves nothing.
- Only enough code to pass current test
- After implementing, run the tests and watch them pass with clean output before starting the next cycle
- Don't anticipate future tests
- Keep tests focused on observable behavior

**Stuck RED?** If a test won't go green after a few focused attempts and you can't explain why, stop - don't thrash or pile on speculative code to force it. A test failing for a reason you don't understand is a signal the cause needs finding, not more attempts: hand off to `/diagnose` (or `$diagnose`) when the cause is unclear, or step back to a RED you understand. Bounded, deliberate cycles beat a long red thrash.

### 4. Refactor

After all tests pass, look for [refactor candidates](refactoring.md):

- [ ] Extract duplication
- [ ] Deepen modules (move complexity behind simple interfaces)
- [ ] Apply SOLID principles where natural
- [ ] Consider what new code reveals about existing code
- [ ] Run tests after each refactor step

**Never refactor while RED.** Get to GREEN first.

### 5. Closure

When every planned behavior is implemented, tested, and refactored:

- [ ] Run the FULL suite, not just this cycle's tests, and watch it pass with clean output. Per-cycle runs only prove the behavior you just added; a late refactor can silently break a behavior covered in an earlier cycle, and only the whole suite catches it.
- [ ] If the full-suite run is red from your changes and the fix is not simply the current RED→GREEN cycle, hand off to `/keep-green` (or `$keep-green`) to drive it back to green without thrashing.
- [ ] Confirm you built the behaviors the plan named - and nothing speculative crept in.
- [ ] Don't silently roll on. State that the change is ready, what it covers, and any interface or behavior assumptions you made unattended. Hand off to your completion-check and commit lane (e.g. `/closeout-check` or `$closeout-check`, if available) rather than declaring done yourself.

## Checklist Per Cycle

```
[ ] Test describes behavior, not implementation
[ ] Watched the test fail for the expected reason before implementing
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
```
