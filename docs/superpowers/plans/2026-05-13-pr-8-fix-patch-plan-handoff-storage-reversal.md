# PR #8 Critical Fix Patch — Handoff Storage Reversal

## Context

PR #8 (`feature/handoff-storage-reversal-main`, "Handoff storage reversal source repair") reverses handoff storage authority from `docs/handoffs/` to `.codex/handoffs/` and adds substantial supporting infrastructure (storage authority, active-writer reservations, load transactions, recovery flows). Branch HEAD is `a7f5350`.

A multi-agent review surfaced five critical defects that sit inside the PR's stated "source repaired" boundary and must land before merge:

1. **Lock liveness** — both `active-write.lock` and `load.lock` carry `created_at`/`timeout_seconds`/`pid`/`hostname` metadata (`active_writes.py:954-963`, `load_transactions.py:654-663`) that is never read. Any crash wedges the lock forever; recovery commands themselves take the lock, so users cannot self-recover.
2. **Cross-project pending-load recovery** — `_recover_pending_load` (`load_transactions.py:279-301`) walks every pending `load` transaction without filtering by project, so a stale recovery from another project silently substitutes for the requested load.
3. **Corruption-eats-state cascade** — four sites collapse `OSError|JSONDecodeError` into "no entries"/`False`/`continue`: `_read_json_object` (`storage_authority.py:953-960`), `_consumed_legacy_active_matches` (`storage_authority.py:1631-1644`), `_ensure_no_compatible_reservation` glob (`active_writes.py:336-339`), `_recover_pending_load` glob (`load_transactions.py:284-287`). Corrupt durable state silently becomes "no state."
4. **Chain-state guard test gap** — the four `ChainStateDiagnosticError` codes guarding primary-vs-legacy and stale-hash mistakes (`chain-state-payload-hash-mismatch`, `primary-chain-state-not-consumable`, `chain-state-candidate-not-primary`, `chain-state-selector-ambiguous`) have happy-path coverage only; a grep across `plugins/turbo-mode/handoff/1.6.0/tests/` returns zero matches for any of the four codes.
5. **Closeout evidence anchor is stale** — `docs/superpowers/plans/2026-05-13-handoff-storage-source-closeout.md:8` anchors evidence at `b337e0c`, but `5d9b0fe` and `a7f5350` land after, materially changing behavior.

Scope is intentionally narrow: state-record discipline (decorative `ActiveWriteReservation`, circular imports, helper deduplication, full type-annotation pass, docstring backfill) is deferred to follow-up.

## Change shape

```
Commit 1 ─ lock liveness + project filter ─┐
                                            ├─ Commit 3 ─ closeout + operator docs + preflight refresh
Commit 2 ─ fail-closed corrupt-JSON        ─┘
```

Commit 1 and Commit 2 are **conceptually separable but sequential** in `load_transactions.py` — both touch `_recover_pending_load` (Commit 1 changes signature/project filter at `:279`/`:79`; Commit 2 hardens corrupt-record handling at `:284-287`). Apply Commit 2 on top of Commit 1; do not parallelize. Commit 3 depends on both because it re-anchors evidence at the post-Commit-2 SHA. Each commit must pass the bytecode-safe verification commands in the **Verification** section below — running plain `uv run pytest` is not equivalent because it lets `__pycache__/*.pyc` leak into the source tree, which a residue-sensitive patch cannot tolerate.

**Supported environment / trust boundary.** This plan supports local filesystem state under the project worktree with a trusted local operator. It does **not** claim correctness for NFS/SMB/network/shared filesystems where `O_CREAT|O_EXCL` lockfile semantics may differ or degrade, and it does **not** harden against a hostile local process deliberately creating, replacing, or corrupting `.session-state` paths. Those environments require a different locking primitive or threat model and are out of scope for this PR-local critical-fix patch.

```
_acquire_lock(path, ...)
  │
  ├── O_EXCL on lock succeeds → write metadata → verify lock_id → done
  │
  └── FileExistsError → _try_recover_stale_lock(path, now=now)
        │
        ├── claim already exists → RAISE operator diagnostic
        │                          ("recovery claim file present; if no live
        │                           recoverer, `trash <claim_path>` and retry")
        │
        └── O_EXCL on claim succeeds → write claim forensic metadata
              │
              ├── lock vanished (FileNotFoundError) → release claim, return True
              ├── lock unreadable/malformed → release claim, RAISE
              ├── lock fresh (age ≤ timeout) → release claim, return False
              │                                → caller raises "lock is already held"
              ├── foreign host → release claim, RAISE
              └── stale + same host → unlink lock, release claim, return True
                  └── caller retries O_EXCL on lock:
                      ├── succeeds → write metadata → verify lock_id → done
                      └── FileExistsError (fresh acquirer won post-unlink) → RAISE
```

## Commit 1 — Lock and recovery correctness

### 1a. Add `_parse_created_at` helper in `load_transactions.py`

`active_writes.py:929` already has `_parse_created_at`. `load_transactions.py` does not. Add an identical local helper near the existing `_acquire_lock` (around `load_transactions.py:638`). Do **not** cross-import — keeps the duplicate-helper follow-up bounded.

### 1b. Stale-lock recovery — `_try_recover_stale_lock` with operator-mediated claim recovery

**Files:**
- `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py:939-965`
- `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py:640-665`

The recovery uses a per-lock **recovery-claim file** to serialize concurrent recoverers — without it, two recoverers can both pass the staleness check, both `unlink`, and the second `unlink` can delete a fresh lock the first recoverer just installed.

**Design decision: any existing claim is fail-closed with operator diagnostic; the claim itself is NOT auto-recovered.** An earlier draft tried to auto-recover stale claims via TTL, but that reproduces the same unlink race one level shallower — two recoverers can both see a stale claim, both unlink, and the second deletes the fresh claim the first just installed. The only safe boundaries are (a) an atomic CAS-style filesystem primitive (which POSIX does not provide) or (b) explicit operator recovery for the claim layer. We take (b): if the claim is present, the caller fails closed with an explicit `trash <claim_path>` instruction. The claim carries metadata (`pid`, `hostname`, `created_at`, `timeout_seconds`) **purely for the operator's forensic use** — to decide whether the holder is alive — not for automated decisions. The TTL is still meaningful as advisory: claims older than `_CLAIM_TIMEOUT_SECONDS` are reported as "stale" in the diagnostic message, but the code never unlinks the claim on the caller's behalf.

This trades a small operational cost (operator intervention when a recoverer crashes during the bounded I/O sequence) for total elimination of the multi-process unlink race. Crashes during recovery are rare; the recovery operation itself is rare; the diagnostic is explicit and one-command-fixable. Acceptable.

**Explicit acceptance criterion.** The bar this design meets is: **"ordinary stale locks self-recover; the recovery-claim crash window fails closed with explicit operator action."** It does NOT meet the stronger bar of "no crash, anywhere in the lock-or-claim stack, can wedge recovery without manual deletion." Reviewers evaluating the merge against the stronger bar will correctly find this design insufficient and should demand a different primitive (e.g., advisory `flock`/`fcntl`, or moving locking off the filesystem entirely). We chose the weaker-but-implementable bar because the stronger one has no POSIX-portable solution that survives concurrent unlink. If that tradeoff is unacceptable, this design must be re-litigated as a unit, not patched in review.

**Host identity caveat.** Same-host stale-lock recovery uses `socket.gethostname()` as an operational discriminator, not as a cryptographic or globally stable host identity. If the hostname changes between lock creation and recovery, or if the same machine is visible under multiple hostnames, stale locks may fail closed as "foreign host" and require operator review. This is intentional: false hard-stop is safer than auto-deleting a lock that may belong to another host.

Add the constant near each `_acquire_lock` definition:

```python
_CLAIM_TIMEOUT_SECONDS = 60  # advisory: claims older than this are reported "stale" in diagnostics
```

Add a private helper to each module (different exception class per module):

```python
def _write_claim_metadata(claim_fd: int) -> None:
    """Write minimal forensic metadata to a recovery-claim fd, then close it."""
    payload = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(UTC).isoformat(),
        "timeout_seconds": _CLAIM_TIMEOUT_SECONDS,
    }
    try:
        os.write(claim_fd, json.dumps(payload).encode("utf-8"))
        os.fsync(claim_fd)
    finally:
        os.close(claim_fd)


def _try_recover_stale_lock(path: Path, *, now: datetime) -> bool:
    """Try to recover a stale lock; serialize via a recovery-claim file.

    Returns True if the stale lock was unlinked (caller may retry O_EXCL).
    Returns False if the lock is fresh (after second read).
    Raises on:
      - any existing claim file (with operator recovery instructions)
      - unreadable / malformed lock metadata
      - foreign-host lock
    """
    claim_path = path.with_name(path.name + ".recovery")
    # (1) Acquire the recovery claim, OR fail closed with operator diagnostic.
    try:
        claim_fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        # Existing claim — never auto-unlink. Build the most informative diagnostic
        # we can from the claim's metadata (if readable) and surface the recovery command.
        claim_age_hint = ""
        try:
            claim_payload = json.loads(claim_path.read_text(encoding="utf-8"))
            if isinstance(claim_payload, dict):
                c_pid = claim_payload.get("pid")
                c_host = claim_payload.get("hostname")
                c_created = claim_payload.get("created_at")
                c_timeout = claim_payload.get("timeout_seconds")
                if isinstance(c_created, str):
                    try:
                        age = (now - _parse_created_at(c_created)).total_seconds()
                        if isinstance(c_timeout, (int, float)) and age > c_timeout:
                            claim_age_hint = f" (likely stale: pid={c_pid!r} host={c_host!r} age={age:.0f}s)"
                        else:
                            claim_age_hint = f" (live recoverer: pid={c_pid!r} host={c_host!r})"
                    except ValueError:
                        pass
        except (OSError, json.JSONDecodeError, ValueError):
            claim_age_hint = " (claim metadata unreadable)"
        raise <ModuleError>(
            f"<op> failed: recovery claim file present{claim_age_hint}; "
            f"if no process is actively recovering this lock, run `trash {claim_path}` and retry. "
            f"Got: {str(claim_path)!r:.100}"
        )
    # (2) Claim acquired — write metadata for forensics, then proceed with lock recovery.
    try:
        _write_claim_metadata(claim_fd)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return True  # lock vanished while we held the claim — caller retries
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise <ModuleError>(
                f"<op> failed: lock metadata unreadable; manual operator review required. "
                f"Got: {str(path)!r:.100}"
            ) from exc
        if not isinstance(payload, dict):
            raise <ModuleError>(f"<op> failed: lock metadata malformed; ...")
        created_at = payload.get("created_at")
        timeout = payload.get("timeout_seconds")
        hostname = payload.get("hostname")
        if not isinstance(created_at, str) or not isinstance(timeout, (int, float)) or not isinstance(hostname, str):
            raise <ModuleError>(f"<op> failed: lock metadata malformed; ...")
        try:
            created = _parse_created_at(created_at)
        except ValueError as exc:
            raise <ModuleError>(f"<op> failed: lock metadata malformed; ...") from exc
        if (now - created).total_seconds() <= timeout:
            return False
        if hostname != socket.gethostname():
            raise <ModuleError>(
                f"<op> failed: stale lock from another host; manual operator review required. "
                f"Got: {(hostname, str(path))!r:.100}"
            )
        os.unlink(path)
        return True
    finally:
        try:
            os.unlink(claim_path)
        except FileNotFoundError:
            pass
```

**Failure self-recovery boundary (honest disclosure).** The lock layer is fully automatic — stale locks are auto-recovered by the next operation. The claim layer is **explicitly operator-mediated** — a crashed recoverer leaves an orphaned claim that the next operation will refuse to clear automatically. This boundary is the cost of safety: there is no POSIX primitive that allows a process to unlink "this specific stale claim" atomically and reject "a fresh claim that replaced it during my read window." The operator-recovery path is documented in the diagnostic message and is a one-command fix (`trash <claim_path>`).

**Wire into `_acquire_lock`.** Replace the existing `except FileExistsError` branch with: call `_try_recover_stale_lock(path, now=datetime.now(UTC))`. If it returns `True`, retry `os.open(...O_EXCL...)` exactly once. On the retry's `FileExistsError` (a fresh acquirer won the post-unlink race — benign), raise the existing "lock is already held" error. If the helper returned `False` (lock is fresh-after-second-read), raise the existing "lock is already held" error. If the helper raised (claim present, unreadable lock, foreign host), propagate the diagnostic.

**Verify-after-write (kept as belt-and-suspenders).** After writing the new metadata, re-read the file and assert `payload["lock_id"] == transaction_id`. Mismatch → raise the standard "lock is already held" error. With the operator-mediated claim, only one recoverer is active at a time, so the dominant race is closed; this read is residual coverage against a fresh acquirer slipping in between our `O_EXCL` success and our metadata write (which `O_EXCL` actually rules out, but the check is cheap).

### 1c. Project-filtered `_recover_pending_load`

**File:** `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py:279-298` and caller at `:79`.

- Signature: `def _recover_pending_load(layout, *, project: str) -> LoadResult | None:`.
- In the glob body, after the parse, add `if record.get("project") != project: continue`.
- Caller at `:79`: `recovered = _recover_pending_load(layout, project=project)`. The caller already computes `project` at `:70`.

### 1d. `_release_lock` cleanup tweak

**Files:**
- `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py:973`
- `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py:673`

Change `for directory in (path.parent, path.parent.parent):` → `for directory in (path.parent,):` in both files. Stops the helper from tearing down `.session-state/`.

### 1e. Update tests broken by stricter lock parsing

Two existing tests seed lock content the new validator will reject and must be updated before any new tests are added:

- `tests/test_load_transactions.py:408` — `lock.write_text("busy", ...)`. Replace with a full valid lock metadata dict (`project`, `operation`, `transaction_id`, `lock_id`, `pid`, `hostname=socket.gethostname()`, `created_at=datetime.now(UTC).isoformat()`, `timeout_seconds=1800`) and keep the existing `match="lock is already held"` assertion (live lock now blocks correctly).
- `tests/test_active_writes.py:486-494` — the competing-writer JSON lacks `created_at`/`timeout_seconds`/`hostname`. Add them with `created_at=now` and `timeout_seconds=1800` so the test still proves the "lock-already-held during generation" path, not the new fail-closed path.

### 1f. New tests for Commit 1

**Lock-ownership assertion pattern.** `begin_active_write` and `load_handoff` release the lock in their `finally` blocks before returning (`active_writes.py:214`, `load_transactions.py:91`), so an "after the call, read the lock file" assertion is impossible. Use the existing pattern at `tests/test_load_transactions.py:417` (`test_load_lock_metadata_exists_during_mutation`): a monkeypatch spy installed inside the critical section captures the live lock metadata. After the public call returns, assert (a) the lock file is **absent** (clean release), and (b) the operation state/result is correct.

In `tests/test_active_writes.py` (target `active-write.lock`):
- `test_active_write_lock_blocks_within_timeout` — pre-stage valid metadata with `created_at=now` → expect `ActiveWriteError` matching "lock is already held"; lock file still present after.
- `test_active_write_lock_recovers_from_stale_lock_same_host_after_timeout` — pre-stage `created_at=(now - 2h)`, `hostname=socket.gethostname()`, `timeout_seconds=1800` → call succeeds; assert lock is absent after return; assert the reservation/state file reflects a new transaction id.
- `test_active_write_lock_fails_closed_on_unparseable_metadata` — pre-stage with `"not-json"` → `ActiveWriteError` matching "lock metadata unreadable"; lock file still present.
- `test_active_write_lock_fails_closed_on_malformed_json_metadata` — parameterize JSON-shaped malformed lock payloads: non-dict payload, missing `created_at`, missing `timeout_seconds`, missing `hostname`, wrong-type `created_at`, wrong-type `timeout_seconds`, wrong-type `hostname`, and unparsable `created_at`. Expect `ActiveWriteError` matching "lock metadata malformed"; lock file still present. This proves every malformed-lock branch in `_try_recover_stale_lock`, not just the unparseable-text branch.
- `test_active_write_lock_fails_closed_on_foreign_host` — pre-stage with `hostname: "different-host"`, `created_at=(now - 2h)` → `ActiveWriteError` matching "stale lock from another host"; lock file still present.
- `test_active_write_lock_records_new_owner_during_critical_section` — install monkeypatch spy inside the critical section (mirror the pattern at `test_load_transactions.py:417`); pre-stage stale-same-host metadata; assert the spy observed `lock_id == new transaction_id` and the captured metadata is the new payload (not the stale one).
- `test_active_write_lock_recovery_claim_present_fails_closed_with_live_hint` — pre-stage stale-same-host lock metadata; additionally pre-stage `active-write.lock.recovery` with valid claim metadata (`pid=os.getpid()`, `hostname=socket.gethostname()`, `created_at=now`, `timeout_seconds=60`). Call `begin_active_write`; expect `ActiveWriteError` matching "recovery claim file present" AND matching "(live recoverer:" AND matching `trash {claim_path}`. Both lock and claim still present.
- `test_active_write_lock_recovery_claim_present_fails_closed_with_stale_hint` — pre-stage stale-same-host lock metadata; pre-stage claim with `created_at=(now - 5m)` (older than `_CLAIM_TIMEOUT_SECONDS=60`). Expect `ActiveWriteError` matching "recovery claim file present" AND matching "(likely stale:" AND matching `trash {claim_path}`. Both files still present (the claim is NOT auto-removed). Proves the documented operator-mediated boundary: stale claim → diagnostic, not auto-recovery.
- `test_active_write_lock_recovery_claim_unparseable_fails_closed` — pre-stage stale-same-host lock metadata; pre-stage claim with `"not-json"`. Expect `ActiveWriteError` matching "recovery claim file present" AND matching "claim metadata unreadable" AND matching `trash`. Both files still present.
- `test_active_write_lock_recovery_claim_malformed_fails_closed` — pre-stage stale-same-host lock metadata; pre-stage claim with valid JSON but missing/wrong-type `created_at` or `timeout_seconds`. Expect `ActiveWriteError` matching "recovery claim file present" with the `trash` instruction; both files still present.
- `test_active_write_lock_recovery_claim_removed_then_operation_succeeds` — pre-stage stale-same-host lock; pre-stage stale claim; first call raises (per the test above); operator simulates the documented recovery by `claim_path.unlink()`; second call succeeds end-to-end, lock absent after, reservation/state correct. Proves the documented manual-recovery workflow is the one-command-fix the diagnostic advertises.
- `test_release_lock_preserves_session_state_dir` — acquire/release cycle; assert `.codex/handoffs/.session-state/` still exists.

In `tests/test_load_transactions.py` (target `load.lock`): the twelve tests parallel to the active-write set above (seven lock-staleness/malformed-metadata tests — `blocks_within_timeout`, `recovers_from_stale_lock_same_host_after_timeout`, `fails_closed_on_unparseable_metadata`, `fails_closed_on_malformed_json_metadata`, `fails_closed_on_foreign_host`, `records_new_owner_during_critical_section`, `release_lock_preserves_session_state_dir` — plus five claim-diagnostic tests — `recovery_claim_present_fails_closed_with_live_hint`, `recovery_claim_present_fails_closed_with_stale_hint`, `recovery_claim_unparseable_fails_closed`, `recovery_claim_malformed_fails_closed`, `recovery_claim_removed_then_operation_succeeds`), asserting on `LoadTransactionError` instead of `ActiveWriteError`. The malformed JSON lock metadata test must cover the same non-dict/missing-field/wrong-type/unparsable-created-at cases as the active-write version. Plus:
- `test_recover_pending_load_filters_by_project` — pre-stage `transactions/foreign.json` (`{project: "other-project", operation: "load", status: "pending", storage_location: "primary_archive", ...}` populated enough to pass the existing `record.get("storage_location") in {...}` filter at `:290-296`) and a primed `demo` source. Call `load_handoff(tmp_path, project_name="demo")`. Assert the returned `transaction_id` is for the demo flow, not the foreign record, and the foreign transaction file is untouched.

**Load subprocess smoke test** — one live `O_EXCL` contention smoke for the load lock. Add to `tests/test_load_transactions.py`:
- `test_load_lock_live_contention_with_subprocess` — Process A and Process B are both `uv run python -c "<code>"` subprocesses. Both code snippets must explicitly insert the plugin root onto `sys.path` before importing the private helpers, because `python -c` does not put the script's directory on `sys.path` and the existing inventory pattern (`tests/test_storage_authority_inventory.py:32-45`) runs a real script file rather than `-c`.

  **Same-lock-path requirement (critical for test validity).** The parent test MUST compute `lock_path_repr` from the **same layout/state directory that `load_handoff(tmp_path, project_name="demo")` derives internally** — otherwise Process A holds a lock on one path while Process B contends on a different one, and the test either fails for setup reasons or "passes" without proving public-path contention. Concretely: import the same layout helper used by `load_handoff` (or replicate its path-derivation logic against the same `tmp_path` and `project_name="demo"`) and use that to build `lock_path_repr`. Assert at test-setup time that `Path(lock_path_repr).parent` equals the lock parent that `load_handoff` would target, before spawning either subprocess.

  The Process A code string template:
  ```python
  import sys, json, os, socket, time
  from datetime import datetime, UTC
  from pathlib import Path
  PLUGIN_ROOT = {plugin_root_repr}  # absolute path to plugins/turbo-mode/handoff/1.6.0
  sys.path.insert(0, PLUGIN_ROOT)
  from scripts.load_transactions import _acquire_lock, _release_lock
  lock_path = Path({lock_path_repr})
  ready = Path({ready_marker_repr})
  release = Path({release_marker_repr})
  lock_path.parent.mkdir(parents=True, exist_ok=True)
  _acquire_lock(lock_path, project="demo", operation="load", transaction_id="A")
  ready.write_text("ready", encoding="utf-8")
  deadline = time.monotonic() + 30.0  # bounded wait, not infinite
  while not release.exists() and time.monotonic() < deadline:
      time.sleep(0.01)  # bounded polling, not semantic sleep-based orchestration
  if not release.exists():
      sys.exit(2)  # test orchestration failure — surface as non-zero exit
  _release_lock(lock_path)
  ```

  The Process B code string imports `load_handoff` (same `sys.path.insert` prelude) and calls it against the seeded `tmp_path` source; on failure exits non-zero with the exception message printed to stderr.

  Parent test orchestration: spawn A via `subprocess.Popen(["uv", "run", "python", "-c", code_a], stderr=PIPE)`. Poll `ready.exists()` with the **same bounded-deadline pattern** (`time.monotonic()` deadline, `time.sleep(0.01)` between checks; fail the test with a descriptive assert if the deadline passes). Spawn B via `subprocess.run([..., "-c", code_b], capture_output=True)`; assert non-zero exit and stderr matches "lock is already held". Write the `release` marker. Wait for A's zero exit (`A.wait(timeout=5)`). Re-spawn B; assert success. The ban is on **semantic** time-based orchestration ("wait one second for the lock to drain") — bounded polling with a monotonic deadline is not the same thing and is required to avoid pegging CI or hanging indefinitely if the test's invariants break. On timeout or unexpected subprocess exit, the failure message must include Process A stderr/stdout if captured, Process B stderr/stdout, `lock_path`, `ready_marker`, and `release_marker` so CI failures are diagnosable. This proves real `O_EXCL` contention AND that `_release_lock` actually releases (Process B succeeds only because A explicitly released, not because the lock went stale). Staleness logic is covered deterministically by the staged-file tests above.

**Active-write subprocess smoke test** — add one parallel smoke test for the duplicated `active_writes.py` lock implementation. The load subprocess smoke is not enough by itself because `_acquire_lock` is intentionally duplicated in `active_writes.py` and `load_transactions.py`; a future regression that drops `O_EXCL` from active writes would not be caught by load-only proof.
- `test_active_write_lock_live_contention_with_subprocess` — Process A imports `scripts.active_writes._acquire_lock` / `_release_lock` and holds the exact `active-write.lock` path that `begin_active_write(tmp_path, project_name="demo", ...)` derives internally. Process B imports and calls the public `begin_active_write` entrypoint against the same project root/name. Use the same `sys.path.insert(0, PLUGIN_ROOT)` prelude, same-lock-path setup assertion, bounded `time.monotonic()` polling, and release-marker orchestration as the load smoke. Assert B fails with "lock is already held" while A holds the lock, then succeeds after A explicitly releases. This proves live `O_EXCL` contention for both duplicated lock implementations.

As with the load subprocess smoke, active-write subprocess failures must print enough context to debug CI variance: both subprocess outputs, exact lock path, marker paths, and which phase timed out or returned an unexpected exit code.

## Commit 2 — Fail-closed corrupt-JSON handling

The `ChainStateDiagnosticError` payload shape requires `error.code`/`error.message`. The existing `_operator_error` helper requires a `candidate`, which corruption sites don't have, so construct the payload inline at each site.

### 2a. `_read_json_object` — preserve missing-vs-corrupt distinction

**File:** `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py:953-960`. Three callers (`:324`, `:420`, `:775`) unchanged.

Replace with:
- `FileNotFoundError` → `return {}` (markers legitimately absent on first write).
- `OSError | json.JSONDecodeError` → raise `ChainStateDiagnosticError({"error": {"code": "chain-state-marker-unreadable", "message": f"chain-state marker unreadable: {path}"}, "marker_path": str(path)})`.
- Non-dict payload → raise `ChainStateDiagnosticError({"error": {"code": "chain-state-marker-malformed", "message": f"chain-state marker malformed: {path}"}, "marker_path": str(path)})`.

### 2b. `_consumed_legacy_active_matches` — close BOTH fail-open paths

**File:** `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py:1631-1644`.

Three current fail-open paths to close:
1. `OSError | json.JSONDecodeError` at the `read_text`/`json.loads` boundary (`:1631-1634`).
2. Payload is not a dict (current code falls through `entries = payload.get("entries")` and the next isinstance check returns False — still fail-open).
3. `entries` is missing or not a `list` (`:1635` — same "corrupt state becomes unconsumed" class).

New behavior:
- `FileNotFoundError` → `return False` (registry legitimately absent on first run).
- `OSError | json.JSONDecodeError` → raise `ChainStateDiagnosticError({"error": {"code": "consumed-legacy-active-registry-unreadable", "message": f"consumed-legacy-active registry unreadable: {registry_path}"}, "registry_path": str(registry_path)})`.
- Non-dict payload OR missing/non-list `entries` → raise `ChainStateDiagnosticError({"error": {"code": "consumed-legacy-active-registry-malformed", "message": f"consumed-legacy-active registry malformed: {registry_path}"}, "registry_path": str(registry_path)})`.

### 2c. `_ensure_no_compatible_reservation`

**File:** `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py:336-339`. Replace `continue`:

```python
raise ActiveWriteError(
    f"begin-active-write failed: active-write record unreadable; manual operator review required. "
    f"Got: {str(path)!r:.100}"
) from exc
```

### 2d. `_recover_pending_load`

**File:** `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py:284-287`. Replace `continue`:

```python
raise LoadTransactionError(
    f"load-handoff failed: pending transaction record unreadable; manual operator review required. "
    f"Got: {str(transaction_path)!r:.100}"
) from exc
```

**Policy for unreadable transaction files.** Transaction records live in a shared `transactions/` directory and the project field is inside the JSON payload. If the JSON is unreadable, the code cannot safely prove that the corrupt record belongs to a different project, so the intended behavior is **global fail-closed**: any unreadable transaction record blocks `load_handoff` for every project using that state directory until an operator inspects or removes the corrupt record. This is intentionally conservative and must be reflected in tests and diagnostics. The error must include the exact corrupt `transaction_path`.

### 2e. `list_load_recovery_records`

**File:** `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py:208-212`. Do not continue to hide unreadable transaction files from the adjacent recovery-listing path. Replace the current `continue` with a visible recovery record shaped for operators, for example:

```python
except (OSError, json.JSONDecodeError) as exc:
    records.append(
        {
            "transaction_path": str(path),
            "status": "unreadable",
            "operation": "load",
            "error": f"pending transaction record unreadable: {path}",
        }
    )
    continue
```

Keep this non-throwing because list commands are visibility tools; they should surface corrupt state instead of failing before printing anything. The load path itself still fails closed per 2d.

### 2f. Chain-state diagnostic + corruption test coverage

In `tests/test_storage_authority.py` — six guard-coverage tests:

- `test_mark_chain_state_consumed_raises_payload_hash_mismatch` — stage a legacy candidate; call `mark_chain_state_consumed(..., expected_payload_sha256="0"*64)`; assert `exc.payload["error"]["code"] == "chain-state-payload-hash-mismatch"`.
- `test_continue_chain_state_raises_payload_hash_mismatch` — same pattern for `continue_chain_state`.
- `test_abandon_primary_chain_state_raises_payload_hash_mismatch` — same for `abandon_primary_chain_state` on a primary candidate.
- `test_mark_chain_state_consumed_raises_primary_chain_state_not_consumable` — pass a primary candidate → code `primary-chain-state-not-consumable` (guard at `storage_authority.py:294`).
- `test_abandon_primary_chain_state_raises_chain_state_candidate_not_primary` — pass a legacy candidate → code `chain-state-candidate-not-primary` (guard at `storage_authority.py:478`).
- `test_select_chain_state_candidate_raises_selector_ambiguous` — stage two candidates that resolve under the same selector; invoke any mutation function → code `chain-state-selector-ambiguous` (guard at `storage_authority.py:700`).

Plus corruption tests:
- `test_consumed_legacy_active_matches_fails_closed_on_corrupt_registry` (in `test_storage_authority.py`) — write truncated JSON to `<state>/consumed-legacy-active.json`; trigger a discovery that hits the registry; expect `ChainStateDiagnosticError` with code `consumed-legacy-active-registry-unreadable`.
- `test_consumed_legacy_active_matches_fails_closed_on_malformed_registry` — write valid JSON with `entries: "not-a-list"` (or with payload as a non-dict); expect `ChainStateDiagnosticError` with code `consumed-legacy-active-registry-malformed`. Covers the entries-not-list branch added in 2b.
- `test_read_json_object_fails_closed_on_corrupt_marker` (in `test_storage_authority.py`) — write garbage to `<state>/markers/chain-state-consumed.json`; call `mark_chain_state_consumed` (which goes through `_read_json_object`); expect `chain-state-marker-unreadable`.
- `test_ensure_no_compatible_reservation_fails_closed_on_corrupt_record` (in `test_active_writes.py`) — stage `<state>/active-writes/{project}/garbage.json` with non-JSON bytes; call `begin_active_write`; expect `ActiveWriteError` matching "active-write record unreadable".
- `test_recover_pending_load_fails_closed_on_corrupt_transaction` (in `test_load_transactions.py`) — stage `<state>/transactions/garbage.json` with non-JSON bytes; call `load_handoff`; expect `LoadTransactionError` matching "pending transaction record unreadable".
- `test_recover_pending_load_fails_closed_on_corrupt_foreign_transaction` (in `test_load_transactions.py`) — stage one corrupt transaction file that would have been "foreign" if readable, then call `load_handoff(..., project_name="demo")`; expect the same `LoadTransactionError` and assert the exact corrupt path appears in the message. This proves the declared global fail-closed policy for unreadable transaction state.
- `test_list_load_recovery_records_surfaces_corrupt_transaction` (in `test_load_transactions.py`) — stage `<state>/transactions/garbage.json` with non-JSON bytes; call `list_load_recovery_records`; assert a record with `status == "unreadable"` and the exact `transaction_path` is returned. This keeps the operator visibility path aligned with the load-time diagnostic.

## Commit 3 — Evidence refresh

### 3a. Closeout doc evidence-surface refresh

**File:** `docs/superpowers/plans/2026-05-13-handoff-storage-source-closeout.md:8`, `:14-37`, and residual-risk prose.

The closeout doc's full evidence surface must be refreshed, not just the SHA and pytest count. The current tracked closeout contains proof-table rows and verification commands that still use bare `python` / plain `uv run pytest`; that directly conflicts with this plan's bytecode-safe verification model. Commit 3 therefore updates the boundary lines, primitive proof table, verification command block, and residual-risk/operator-boundary prose together.

The closeout doc has SHA-touching lines whose semantics must be kept distinct. The **Commit-3 SHA itself MUST NOT appear inside any file committed by Commit 3** — a tracked file containing its own commit's SHA is a mathematical fixed-point that does not exist: changing the file to embed the SHA changes the tree, which changes the SHA. The closeout commit's identity lives only in `git log` and in artifacts written after push (PR body).

- **Line 8 — "Source repair evidence through:"** is the **implementation milestone** anchor. After Commits 1+2 land, this reads the **Commit-2 SHA + subject**. This intentionally does NOT equal PR HEAD after Commit 3, because Commit 3 updates evidence/operator documentation only — it doesn't change the implementation surface that line 8 anchors. Rename the field label to **"Implementation evidence through:"** for clarity (the word "repair" was ambiguous about which artifact was authoritative).
- **Primitive proof table (`:14-23`)** — refresh every row whose evidence string contains command shape, test count, or proof scope. At minimum:
  - `source storage authority repaired` must cite the bytecode-safe Handoff suite command, the actual post-Commit-2 pytest count, and the bounded lock-liveness claim: ordinary stale locks self-recover; orphaned recovery claims fail closed with explicit operator action.
  - `skill docs reconciled` must cite the load skill contract update plus `storage_authority_inventory.py --check` under the bytecode-safe env.
  - `refresh surfaces reconciled` must cite the bytecode-safe refresh pytest command and proof-map check.
  - Any row that still shows bare `python` or plain `uv run pytest` after Commit 3 is stale and fails this plan.
- **Verification command block (`:25-37`)** — replace bare `python` and plain `uv run pytest` with the bytecode-safe `env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" ...` forms used in this plan. Include the fail-closed residue gate from §Verification, not an informational scan.
- **Residual risk/operator-boundary prose** — preserve the installed-host/cache exclusions, and add the new local recovery caveats: local filesystem/trusted-operator scope only; NFS/SMB/shared filesystems are not certified; hostile local `.session-state` tampering is out of scope; unreadable transaction records are global fail-closed until operator repair; orphaned recovery claims require explicit operator cleanup; hostname mismatches fail closed and may require manual validation after host renames or multi-name environments.
- **Do NOT add** a `Closeout refresh committed in: <Commit-3 SHA>` line inside the tracked doc. The Commit-3 SHA is observable in `git log` (it's the commit that touched the closeout doc); placing it inside the doc creates a circular SHA-derivation. If a single canonical record is wanted, put the Commit-3 SHA in the **PR body only**, after push.

### 3b. Preflight + inventory + gate-proof validation

**What "evidence refresh" means here, precisely.** Commit 3's source-tree changes are documentation/operator-contract updates: the closeout doc and the load skill. The preflight scripts' `--write` outputs land in `.codex/handoffs/.session-state/preflight/*.json`, which is **gitignored**: those files are local validation artifacts demonstrating "these checks passed at this head right now," not source-of-truth evidence. The durable claim that Commit 3 makes is "checks succeeded at the Commit-2 SHA," substantiated by the validation run and tracked docs, not by committed local-preflight artifact contents.

The five scripts split into two categories:

**Evidence-writing scripts** (run with `--write` first to align local artifacts; outputs are gitignored):
- `residue_preflight.py` — writes `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json` (gitignored). Local handoff residue from development testing can cause `--check` to fail; refresh with `--write` before validation.
- `legacy_active_preflight.py` — writes `.codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json` (gitignored). Same consideration.
- `storage_authority_inventory.py` — `--check` validates against fixtures in `tests/fixtures/storage_authority_inventory.json`. No `--write` needed unless the inventory schema changed (it didn't in Commits 1+2).

**Doc-validating scripts** (only `--check`; the committed docs they validate against don't change in this patch):
- `hard_stop_matrix.py` — validates `2026-05-13-handoff-storage-hard-stop-closeout.md`.
- `gate_proof_map.py` — validates `2026-05-13-handoff-storage-gate-proof-map.md`.

**Precondition.** Before running `--check`, surface any handoff residue from local testing in `docs/handoffs/` or `.codex/handoffs/`. **`git status --porcelain` is insufficient** because both roots are gitignored — untracked-but-ignored artifacts (which is the exact class that already blocked `residue_preflight.py --check` once in this work) won't appear. Use `--ignored`:

If residue is present, EITHER (a) refresh evidence with `--write` (non-destructive — the affected evidence files are gitignored, so no commitable diff), OR (b) clean the residue manually. **Destructive cleanup requires explicit operator approval** before any `trash`/`rm` invocation against `docs/handoffs/` or `.codex/handoffs/` (those roots may contain real session state the operator wants to keep). The `--write` path is non-destructive and is the default.

**Sequence for Commit 3:**

The preflight invocations below import project modules and can emit `__pycache__/*.pyc` into the source tree on first run — exactly the residue the patch is designed to avoid. Run each Python command with the same bytecode-safe env used for pytest verification (§Verification); the residue scan at the end of the verification block is the cleanup gate, but it is cheaper to prevent the residue than to scan-and-clean it after.

```bash
# 1. Surface all local handoff residue, including gitignored files
git status --short --ignored docs/handoffs .codex/handoffs

# 2. Refresh evidence files whose contents legitimately changed
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py --project-root . --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json --write
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py --project-root . --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json --write

# 3. Validate everything with --check; all five must exit 0
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py --project-root . --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py --project-root . --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --hard-stop-matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md --map docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --check
```

The local preflight evidence files are gitignored, so refreshing them does not produce a commitable diff; the `--write` step is operational hygiene to align local artifacts with current implementation, not a source-tree change.

### 3c. PR body refresh

Update the `## Validation` block in the PR description to:
- Match the new pytest output count.
- Record `Implementation evidence through: <Commit-2 SHA>` (mirroring the closeout doc).
- Mirror the broadened closeout evidence surface: bytecode-safe command shapes, fail-closed residue gate, full closeout proof-table refresh, load skill contract update, local-filesystem/trusted-operator boundary, global unreadable-transaction fail-closed policy, hostname fail-closed caveat, and operator-mediated recovery-claim boundary.
- Optionally record `Closeout refresh committed in: <Commit-3 SHA>`. This is the **only** place the Commit-3 SHA appears — the PR body is post-push state, not tracked content, so circular SHA derivation does not apply.
- Note that the prior review thread items (the five P1s + closeout anchor) are addressed in commits 1–2.

## Critical files modified

- `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/skills/load/SKILL.md`
- `docs/superpowers/plans/2026-05-13-handoff-storage-source-closeout.md`

## Functions / utilities to reuse

- `_parse_created_at` (`active_writes.py:929`) — ISO UTC parser; duplicate the body into `load_transactions.py` rather than cross-importing.
- `_auto_expire_pre_output_reservation` (`active_writes.py:354-377`) — reference pattern for "stale resource adoption" (TTL check + atomic mutation); informs the lock-recovery design, no code reuse.
- `ChainStateDiagnosticError` (`storage_authority.py:46-56`) — typed exception with `.payload` access; callers branch on `exc.payload["error"]["code"]`. Construct payload inline at corruption sites (no candidate available, so `_operator_error` doesn't fit).
- Monkeypatch-during-critical-section pattern at `tests/test_load_transactions.py:417` (`test_load_lock_metadata_exists_during_mutation`) — the template for asserting lock ownership while the lock is held, since public APIs release the lock before returning.
- Subprocess test pattern at `tests/test_storage_authority_inventory.py:32-45` — `subprocess.run(["uv", "run", "python", ...])` for the live-contention smoke tests.
- `socket.gethostname()` (already imported in both `active_writes.py:8` and `load_transactions.py:8`).

## Verification

Per-commit, from repo root. Both env vars matter for a residue-sensitive patch: `PYTHONDONTWRITEBYTECODE=1` prevents `__pycache__/` from being written into the source tree by verification itself (the existing `-p no:cacheprovider` only disables pytest's own cache plugin, not Python bytecode), and `PYTHONPYCACHEPREFIX=/tmp/<dir>` redirects any leftover bytecode away from the tree.

```bash
# Must remain green throughout — env prevents verification from polluting the tree
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run pytest -p no:cacheprovider plugins/turbo-mode/tools/refresh/tests/test_classifier.py plugins/turbo-mode/tools/refresh/tests/test_planner.py plugins/turbo-mode/tools/refresh/tests/test_smoke.py
git diff --check

# After verification, scan for any tree-level residue that slipped through:
if git status --short --ignored | grep -E '__pycache__|\.pyc$'; then
  echo "verification failed: Python bytecode residue present" >&2
  exit 1
fi
```

Per-commit checkpoints:

- **Commit 1** — handoff suite green; the two updated lock-seed tests still pass; twelve new active-write tests (seven lock-staleness/malformed-metadata + five claim-diagnostic: live-claim-fails-closed-with-live-hint, stale-claim-fails-closed-with-stale-hint, unparseable-claim-fails-closed, malformed-claim-fails-closed, removed-claim-then-operation-succeeds) + twelve new load-transaction tests + cross-project filter test + release-cleanup test pass; both subprocess smoke tests pass with explicit `_release_lock` in Process A, exact same-lock-path setup assertions, explicit `sys.path` setup in the `-c` code, and bounded-polling `time.monotonic()` deadlines (no semantic time-based orchestration, but bounded polling is allowed and required).
- **Commit 2** — handoff suite green; six diagnostic-guard tests + seven corruption/operator-visibility tests (including malformed-registry coverage, cross-project corrupt-transaction global fail-closed coverage, and corrupt-transaction recovery-listing visibility) pass. If any pre-existing test seeds non-JSON into `transactions/`, `active-writes/{project}/`, or marker paths, that fixture was testing the wrong invariant — update it to seed valid JSON or remove it (none found in current grep, but verify during implementation).
- **Commit 3** — closeout doc line 8 cites the **Commit-2 SHA** under the **"Implementation evidence through:"** label; the Commit-3 SHA is **never embedded in the tracked doc** (see §3a — a tracked file containing its own commit's SHA is a fixed-point that does not exist); the primitive proof table and verification command block are refreshed to bytecode-safe command shapes and current counts; residual-risk/operator prose records local-filesystem/trusted-operator scope, no NFS/SMB/shared-filesystem certification, hostile local tampering out of scope, unreadable transaction global fail-closed behavior, hostname fail-closed caveat, and operator-mediated recovery-claim cleanup. The load skill distinguishes readable pending-load recovery from unreadable/corrupt transaction blocking with operator action, and includes an operator playbook for recovery claims, foreign-host stale locks, and corrupt transaction records. The Commit-3 SHA appears only in the PR body after push (see §3c). Local handoff residue inventoried via `git status --short --ignored`; preflight evidence files refreshed with `--write` for the two scripts that own writable artifacts; all five gates exit 0 under `--check`. The fail-closed residue gate exits non-zero if any `__pycache__/` or `*.pyc` appears in `git status --short --ignored` output. PR body validation block mirrors the broadened closeout evidence surface, the Commit-2 implementation anchor, and (post-push) the Commit-3 closeout anchor.

## Out of scope (defer to follow-up)

- `ActiveWriteReservation` state-machine refactor (`StrEnum` for `status`, `from_payload`/`transition_to`).
- Circular-import refactor between `storage_authority` and `active_writes`.
- Duplicate `_write_json_atomic` / `_acquire_lock` / `_parse_created_at` / `_sha256_*` helpers across modules.
- Bare-string closed vocabularies (`artifact_class`, `scan_mode`, `source_git_visibility`) → `StrEnum`.
- Unannotated `layout` parameter across helpers in `load_transactions.py`.
- Missing class docstrings.
- Misleading "read-only" module docstring at `storage_authority.py:1`.
- `clear-state` CLI ignoring `_trash_path=False` at `session_state.py:425`.
- `_state_candidate_paths` / `_state_like_residue_paths` duplication at `storage_authority.py:712`/`:720`.
- Misleading re-export comment at `search.py:15-16`.
