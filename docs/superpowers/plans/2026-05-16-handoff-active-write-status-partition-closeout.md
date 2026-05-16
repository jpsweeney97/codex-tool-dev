# Closeout — Active-write status-domain partition (2026-05-16)

Plan: `docs/superpowers/plans/2026-05-16-handoff-active-write-status-partition.md`
ADR: `docs/decisions/0004-active-write-status-domain-partition.md`
Branch: `feature/handoff-active-write-status-partition`

## Pyright probe — Stop Condition 2 measured delta (scope: `turbo_mode_handoff_runtime/active_writes.py`)

The pre-Task-2 baseline (Task 2 Step 1) and the post-annotation probe (Task 4 Step 3) use the **identical command and scope**. Introduced = post error count − baseline error count (a measured delta, not the a-priori expectation).

Pre-Task-2 baseline — `/tmp/handoff-partition-pyright-baseline.txt`:
- `pyright --version`: `pyright 1.1.409`
- Baseline exit status (`pyright baseline exit:` line): `1`
- `--stats` error / warning counts: `7` / `0`
- SC2 validity guard (`SC2 BASELINE VALID|INVALID` line): `VALID — package resolved via plugin pyproject.toml, real summary line present, no reportMissingImports`

Post-annotation probe — `/tmp/handoff-partition-pyright.txt`:
- `pyright --version`: `pyright 1.1.409`
- Probe exit status (`pyright probe exit:` line): `1`
- `--stats` error / warning counts: `7` / `0`
- SC2 validity guard (`SC2 POST VALID|INVALID` line): `VALID — package resolved, real summary line present, no reportMissingImports`

- **Introduced delta** (post errors − baseline errors): `0` new suppressions/errors
- Stop Condition 2 verdict: `PASS (both probes VALID, delta 0 ≤ ~3, Task 2 kept)`
- CI-surface context — NOT the SC2 measurement (scope `turbo_mode_handoff_runtime/`, deliberately broader, never differenced against the file-scoped pair): `n/a — see CI advisory logs (Task 5 step is informational, package-wide scope, never differenced)`
- Raw outputs transcribed below (baseline first, then post-probe).

```
Downloading pyright (6.1MiB)
 Downloaded pyright
Installed 3 packages in 95ms
pyright 1.1.409
Loading pyproject.toml file at /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/pyproject.toml
Loading pyproject.toml file at /Users/jp/Projects/active/codex-tool-dev/pyproject.toml
Auto-excluding **/node_modules
Auto-excluding **/__pycache__
Auto-excluding **/.*
Assuming Python version 3.14.2.final.0
Found 1 source file
pyright 1.1.409
/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:360:28 - error: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
    Type "object" is not assignable to type "ConvertibleToInt"
      "object" is not assignable to "str"
      "object" is incompatible with protocol "Buffer"
        "__buffer__" is not present
      "object" is incompatible with protocol "SupportsInt"
        "__int__" is not present
      "object" is incompatible with protocol "SupportsIndex"
        "__index__" is not present (reportArgumentType)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:370:53 - error: "object" is not iterable
    "__iter__" method not defined (reportGeneralTypeIssues)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:388:27 - error: No overloads for "__init__" match the provided arguments (reportCallIssue)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:388:27 - error: Argument of type "dict[bytes, bytes]" cannot be assigned to parameter "recovery_commands" of type "dict[str, object]" in function "__init__"
    "dict[bytes, bytes]" is not assignable to "dict[str, object]"
      Type parameter "_KT@dict" is invariant, but "bytes" is not the same as "str"
      Type parameter "_VT@dict" is invariant, but "bytes" is not the same as "object" (reportArgumentType)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:388:32 - error: Argument of type "object" cannot be assigned to parameter "iterable" of type "Iterable[list[bytes]]" in function "__init__"
    "object" is incompatible with protocol "Iterable[list[bytes]]"
      "__iter__" is not present (reportArgumentType)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:955:42 - error: "object" is not iterable
    "__iter__" method not defined (reportGeneralTypeIssues)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:1047:36 - error: "object" is not iterable
    "__iter__" method not defined (reportGeneralTypeIssues)
7 errors, 0 warnings, 0 informations
Completed in 0.513sec

Analysis stats
Total files parsed and bound: 49
Total files checked: 1

Timing stats
Find Source Files:    0sec
Read Source Files:    0.01sec
Tokenize:             0.03sec
Parse:                0.05sec
Resolve Imports:      0.01sec
Bind:                 0.05sec
Check:                0.2sec
Detect Cycles:        0sec
```

```
pyright 1.1.409
Loading pyproject.toml file at /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/pyproject.toml
Loading pyproject.toml file at /Users/jp/Projects/active/codex-tool-dev/pyproject.toml
Auto-excluding **/node_modules
Auto-excluding **/__pycache__
Auto-excluding **/.*
Assuming Python version 3.14.2.final.0
Found 1 source file
pyright 1.1.409
/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:360:28 - error: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
    Type "object" is not assignable to type "ConvertibleToInt"
      "object" is not assignable to "str"
      "object" is incompatible with protocol "Buffer"
        "__buffer__" is not present
      "object" is incompatible with protocol "SupportsInt"
        "__int__" is not present
      "object" is incompatible with protocol "SupportsIndex"
        "__index__" is not present (reportArgumentType)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:370:53 - error: "object" is not iterable
    "__iter__" method not defined (reportGeneralTypeIssues)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:388:27 - error: No overloads for "__init__" match the provided arguments (reportCallIssue)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:388:27 - error: Argument of type "dict[bytes, bytes]" cannot be assigned to parameter "recovery_commands" of type "dict[str, object]" in function "__init__"
    "dict[bytes, bytes]" is not assignable to "dict[str, object]"
      Type parameter "_KT@dict" is invariant, but "bytes" is not the same as "str"
      Type parameter "_VT@dict" is invariant, but "bytes" is not the same as "object" (reportArgumentType)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:388:32 - error: Argument of type "object" cannot be assigned to parameter "iterable" of type "Iterable[list[bytes]]" in function "__init__"
    "object" is incompatible with protocol "Iterable[list[bytes]]"
      "__iter__" is not present (reportArgumentType)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:955:42 - error: "object" is not iterable
    "__iter__" method not defined (reportGeneralTypeIssues)
  /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py:1047:36 - error: "object" is not iterable
    "__iter__" method not defined (reportGeneralTypeIssues)
7 errors, 0 warnings, 0 informations
Completed in 0.505sec

Analysis stats
Total files parsed and bound: 49
Total files checked: 1

Timing stats
Find Source Files:    0sec
Read Source Files:    0.01sec
Tokenize:             0.03sec
Parse:                0.05sec
Resolve Imports:      0.01sec
Bind:                 0.05sec
Check:                0.19sec
Detect Cycles:        0sec
```

## Gate results

- G0 plan committed: `9740428 (initial plan commit) + 6e80fb0 (round-4 revisions); tracked before Task 1`
- G1 alias + pin test green; full Handoff suite green; ruff clean: `PASS — 4 partition tests passed; full suite 630 passed; ruff clean; commit c8351f1`
- G2 pre-Task-2 pyright baseline captured (same scope as Task 4 probe, BEFORE the annotation) + annotation behavior-preserving (suite count identical to G1): `PASS — baseline 7 errors VALID; suite 630 (identical to G1); commit dccbf1a`
- G3 all 12 lifecycle scenarios + per-domain `test_observed_status_coverage` green: `PASS — 13 passed; full suite 643; commit 66cf796`
- G4 consistency test green; pyright introduced-count recorded as the measured delta (see Pyright probe section); `git diff` shows ZERO `session_state.py` change: `PASS — 5 passed; delta 0; session_state.py empty diff branch-wide; commit 8f82ae4`
- G5 workflow YAML parses; pyright step `continue-on-error: true`, no `|| true`: `PASS — YAML OK (7 steps); continue-on-error true; no || true; commit 474a5eb`

## Stop conditions

- SC1 domain-model tripwire: `not tripped — no TRIPWIRE assertion fired across the 12 lifecycle/recovery scenarios; committed stayed op-only, completed tx-only`
- SC2 noise threshold: `PASS — see Pyright probe verdict (measured delta 0, both probes VALID)`
- SC3 per-domain coverage gap: `not tripped — test_observed_status_coverage green; every runtime-reachable member observed in its own domain; only unreadable excepted (synthetic, static-pin-only)`
- SC4 repo-level cleanup/residue: `none — git status clean except intended Task 6 docs; git diff --check clean`
