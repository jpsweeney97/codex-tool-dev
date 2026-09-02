# Decide Plugin Terms

This document applies to local use of the Decide plugin source package in this repository. Source edits here do not prove that an installed plugin cache or running Codex runtime has been refreshed.

The plugin is provided as source for shaping wants, widening and developing option fields, making recommendations, settling designs, running autonomous deliberations, and cutting scope. It is provided without warranty. A recommendation, close, design, or cut produced with it is an argument, not a measurement: you are responsible for the decision you make on it, for what you approve into a document or tracker, and for anything you build afterward.

Decide actions are attended and read-only toward user-visible state by default: no skill implements, commits, pushes, opens a pull request, or publishes a release; a design document is written only on approval; `deliberate` runs only on explicit invocation, never from a cron job, hook, scheduled task, or another skill, and keeps no state beyond its run by default. Do not treat a recommendation, an approved design, a deliberation close, or a cut scope as review, release, security, compliance, legal, or operational approval without the appropriate human and project-specific verification.

Installed-runtime behavior, cache refresh, marketplace setup, and runtime proof are separate operational steps from editing this source tree.
