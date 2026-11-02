# Test Cycle Plugin Privacy Notice

This document describes the Test Cycle plugin source package in this repository. It does not certify what any installed Codex runtime or plugin cache currently loads.

The Test Cycle plugin provides instructions for taking failing behavior to a trusted green test suite: diagnosing an unclear cause (`diagnose`), test-first implementation (`tdd`), hunting a confirmed defect's twins (`bug-epidemiology`), driving a broken change back to green (`keep-green`), pinning untested code before a refactor (`characterization-tests`), and auditing whether a green suite can be trusted (`test-trust-audit`). It does not create background files, register hooks, run services, or intentionally transmit content to a separate service by itself.

Test Cycle requests may cause the runtime to read local repository files, test output, logs, and git state, and to write ordinary edits in the working repository: tests, probe code, fixes, and characterization test files, each under the skill's own contract. `diagnose` ships a shell template for a human-in-the-loop probe loop that runs only when the user runs it.

Codex, Claude, account handling, model requests, telemetry, synchronization, and any host application behavior are governed outside this local plugin document.

Review the edits a skill makes before committing them, especially probe code and instrumentation left behind by a diagnosis.
