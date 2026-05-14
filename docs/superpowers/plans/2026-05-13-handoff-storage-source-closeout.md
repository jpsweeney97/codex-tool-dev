# Handoff Storage Source Closeout

Gate 4 source closeout for `feature/handoff-storage-reversal-main`.

## Boundary

- Branch: `feature/handoff-storage-reversal-main`
- Implementation evidence through: `22a81e6 fix: fail-closed corrupt-JSON handling at four durable-state sites`
- Composite evidence status: `source repaired`
- Explicitly not claimed: `refresh-ready but not mutated`, `installed host matrix certified`, `installed cache certified`

This closeout proves source-tree repair only. It does not prove real installed-cache currency, app-server-installed source proof, or installed-host behavior matrix coverage.

## Primitive Proof Labels

| Label | Status | Evidence |
|---|---|---|
| `source storage authority repaired` | proved | `env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests` -> 540 passed, 8 expected warnings. Lock liveness: ordinary stale locks self-recover; orphaned recovery claims fail closed with explicit operator action. |
| `skill docs reconciled` | proved | Load skill operator contract distinguishes readable pending-load recovery from unreadable/corrupt transaction blocking, recovery-claim cleanup, and foreign-host stale-lock review; proved by full Handoff suite plus `env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --check` |
| `refresh surfaces reconciled` | proved | `env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run pytest -p no:cacheprovider plugins/turbo-mode/tools/refresh/tests/test_classifier.py plugins/turbo-mode/tools/refresh/tests/test_planner.py plugins/turbo-mode/tools/refresh/tests/test_smoke.py` -> 140 passed; proof map check passed |
| `source-harness-isolation-proof` | proved | Full Handoff suite includes `plugins/turbo-mode/handoff/1.6.0/tests/test_installed_host_harness.py` |
| `installed-host behavior proof` | not-claimed | Gate 5 was not run; installed-host matrix certification is explicitly excluded |
| `installed cache certified` | not-claimed | No real installed-cache mutation or app-server-installed certification was run |

## Verification Commands

```bash
# Bytecode-safe env prevents __pycache__ from polluting the source tree
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py --project-root . --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py --project-root . --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md --hard-stop-matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md --map docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md --check
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run pytest -p no:cacheprovider plugins/turbo-mode/tools/refresh/tests/test_classifier.py plugins/turbo-mode/tools/refresh/tests/test_planner.py plugins/turbo-mode/tools/refresh/tests/test_smoke.py
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run python plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --check
ruff check plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority_inventory.py plugins/turbo-mode/tools/refresh/smoke.py plugins/turbo-mode/tools/refresh/tests/test_smoke.py plugins/turbo-mode/tools/refresh/tests/test_classifier.py plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py
git diff --check

# Fail-closed residue gate
if git status --short --ignored | grep -E '__pycache__|\.pyc$'; then
  echo "verification failed: Python bytecode residue present" >&2
  exit 1
fi
```

## Source Ignore Policy

`git check-ignore -v` was run for the required source-repo paths. The source repo ignores:

- `.codex/handoffs/example.md`
- `.codex/handoffs/archive/example.md`
- `.codex/handoffs/.session-state/example.json`
- `.codex/handoffs/.session-state/locks/example.lock`
- `.codex/handoffs/.session-state/transactions/example.json`
- `.codex/handoffs/.session-state/markers/example`
- `.codex/handoffs/archive/.tmp-example`
- `.codex/handoffs/archive/example.tmp`
- `docs/handoffs/example.md`
- `docs/handoffs/archive/example.md`
- `docs/handoffs/.session-state/example.json`

The ignored local preflight files remain ignored runtime evidence:

```text
!! .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json
!! .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json
```

## Residual Risk

Installed-host behavior matrix certification remains Gate 5 work. The Gate 5 decision record is
`docs/superpowers/plans/2026-05-13-handoff-storage-gate-5-decision.md`.
Do not describe this closeout as installed-cache certified or installed-host certified.

### Operator-Boundary Caveats

- **Local filesystem / trusted operator only.** Lock and claim recovery assumes POSIX `O_CREAT|O_EXCL` semantics on a local filesystem. NFS, SMB, and shared network filesystems where `O_EXCL` may differ or degrade are not certified. Hostile local processes deliberately corrupting `.session-state` paths are out of scope.
- **Unreadable transaction records are global fail-closed.** Transaction files live in a shared `transactions/` directory; if the JSON payload is unreadable, the code cannot prove the record belongs to a different project. Any unreadable transaction blocks `load_handoff` for every project using that state directory until operator repair.
- **Hostname changes fail closed.** Same-host stale-lock recovery uses `socket.gethostname()` as an operational discriminator. If the hostname changes between lock creation and recovery, or the same machine is visible under multiple hostnames, stale locks may fail closed as "foreign host" and require operator review.
- **Orphaned recovery claims require explicit cleanup.** A recovery-claim crash during the bounded I/O sequence leaves an orphaned `.recovery` claim file. The next operation will refuse to clear it automatically and will surface an explicit `trash <claim_path>` diagnostic. This is the intentional operator-mediated boundary.
