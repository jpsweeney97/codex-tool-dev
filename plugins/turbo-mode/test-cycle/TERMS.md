# Test Cycle Plugin Terms

This document applies to local use of the Test Cycle plugin source package in this repository. Source edits here do not prove that an installed plugin cache or running Codex runtime has been refreshed.

The plugin is provided as source for test-centered development work: diagnosis of unclear causes, test-first implementation, twin hunting after a confirmed cause, driving a change back to green, characterization nets before a refactor, and test-suite trust audits. It is provided without warranty. You are responsible for reading the tests and edits a skill produces, for deciding what to commit, and for what the codebase does afterwards.

Test Cycle actions are attended: every edit happens in the working repository in front of the user, no skill commits or merges, and `keep-green` stops at green rather than at done. Do not treat a green suite, a cleared twin table, or a trust-audit finding as release, security, compliance, legal, or operational approval without the appropriate human and project-specific verification.

Installed-runtime behavior, cache refresh, marketplace setup, and runtime proof are separate operational steps from editing this source tree.
