# Pressure Test Plugin Privacy Notice

This document describes the Pressure Test plugin source package in this repository. It does not certify what any installed Codex runtime or plugin cache currently loads.

The Pressure Test plugin provides instructions for challenging a settled plan, design, or decision before committing to it: one-question-at-a-time interrogation (`grill-me`), an assumption register with probes (`assumption-check`), a past-tense failure field (`premortem`), attacker modeling (`red-team`), and a committed one-sided brief (`steelman`). It does not create background files, register hooks, run services, or intentionally transmit content to a separate service by itself.

Pressure Test requests may cause the runtime to read local repository files, documents, and the plan or decision under challenge, and to write only what the user asks for, such as an assumption register file. Attack paths named by `red-team` are advisory descriptions, never executed.

Codex, Claude, account handling, model requests, telemetry, synchronization, and any host application behavior are governed outside this local plugin document.

Review a register, brief, or attack map before sharing it, especially when it names real systems, people, or credentials.
