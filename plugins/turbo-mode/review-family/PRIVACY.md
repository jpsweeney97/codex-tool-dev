# Review Family Plugin Privacy Notice

This document describes the Review Family plugin source package in this repository. It does not certify what any installed Codex runtime or plugin cache currently loads.

The Review Family plugin provides Codex review instructions. It does not create background files, maintain persistent plugin storage, register hooks, run services, or intentionally transmit reviewed content to a separate service.

Review requests may cause Codex to inspect local repository files, git state, GitHub pull request context, pasted review text, or other artifacts that the user asks it to evaluate. Review outputs may include file paths, quoted snippets, claim assessments, recommended repairs, and residual-risk notes.

Codex, OpenAI account handling, model requests, telemetry, synchronization, GitHub access, and any host application behavior are governed outside this local plugin document.

Review targets and findings before sharing or publishing them, especially when a review may include private project details, file paths, customer data, credentials, or other sensitive information.
