---
name: tdd
description: "Use when the user wants to build a feature or fix a bug through test-driven development, red-green-refactor, tracer-bullet slices, or explicit test-first work. Do not use for adding tests after implementation, ordinary verification, test failure triage, broad test strategy, requests that merely mention integration tests, or fixing a bug whose cause is unclear, intermittent, or cross-component (`diagnose` finds the cause first)."
---

# Test-Driven Development

Build the change test-first, one behavior at a time.

- **One test, then its code.** Do not write all the tests first and all the implementation after. Write one failing test, write the minimal code that passes it, then take the next behavior. Each test responds to what the last cycle showed.
- **Watch every test fail first.** Run the new test before implementing. A test that passes at once is testing existing behavior; a test that errors for an unrelated reason needs fixing first. A test you never saw fail proves nothing.
- **Test through the public interface.** A test describes what the system does, not how it does it. A test that breaks when internals are renamed and behavior is unchanged was testing implementation.

Fixing a known-cause bug: the first failing test reproduces the defect through the existing public interface. When the cause is not yet understood, `/diagnose` or `$diagnose` finds it first.
