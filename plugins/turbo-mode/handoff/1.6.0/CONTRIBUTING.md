# Contributing to Handoff

Handoff source lives under `plugins/turbo-mode/handoff/1.6.0/`.

## Source Authority

This checkout is source authority for Handoff source files. It is not proof that the installed Codex runtime or local plugin cache has been refreshed.

## Setup

```bash
cd plugins/turbo-mode/handoff/1.6.0
uv sync
```

## Test

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

For release metadata and docs-only changes:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_release_metadata.py tests/test_skill_docs.py -q -p no:cacheprovider
```

## Regenerating the Storage-Authority Inventory Fixture

`tests/test_storage_authority_inventory.py` pins a content fixture
(`tests/fixtures/storage_authority_inventory.json`) that hashes the tracked
storage-authority documentation surfaces. When you intentionally change a tracked
surface (e.g. `README.md`, `references/ARCHITECTURE.md`), that test fails with
`fixture drift`. Regenerate the fixture with the module's own `--write` path
(runtime modules are import-only with no `__main__` guard, so invoke `main`
explicitly):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 python -c "import sys; from turbo_mode_handoff_runtime.storage_authority_inventory import main; sys.argv=['storage_authority_inventory','--write']; raise SystemExit(main())"
```

Review the resulting one-file diff to confirm only intended hash rows changed,
then commit the fixture with the doc change.

## Runtime Boundaries

Implementation modules live in `turbo_mode_handoff_runtime/`.
The `scripts/` directory contains executable CLI facades only. Do not add new `scripts.*` import dependencies.

- `storage_primitives.py`: filesystem primitives, locking protocol, and atomic write helpers. Stdlib-only base layer with no internal imports.
- `storage_layout.py`: storage paths.
- `storage_inspection.py`: filesystem and git inspection helpers.
- `storage_authority.py`: handoff discovery and selection authority.
- `chain_state.py`: chain-state inventory, diagnostics, read, and lifecycle.
- `scripts/`: executable CLI facades only.

`storage_primitives.py` is the zero-internal-import foundation: never add a `turbo_mode_handoff_runtime` import to it (that would re-create the cycle the storage reseam removed). Imports flow one way, lowest to highest.

Installed-runtime claims require runtime inventory. Source tests alone prove source behavior only.

## Decision Records

Durable architectural decisions are recorded as ADRs in the repository's
`docs/decisions/` directory (storage path move, runtime module extraction and the
stdlib-only seam, hook deferral). Add a new numbered ADR when making a decision
that future contributors would otherwise have to reconstruct from commit history.

## Versioning and Install Path

The `1.6.0/` directory name is the **frozen marketplace install path** for this
install slot. It does not track the manifest version. Only the `version` field
in `.codex-plugin/plugin.json`, `pyproject.toml`, and `uv.lock` advances on a
release (currently `1.7.0`). Do **not** rename the directory to match the
version: `tests/test_release_metadata.py` intentionally asserts both the
`1.7.0` version and the literal `plugins/turbo-mode/handoff/1.6.0` path strings,
and the `plugin.json` `websiteURL`/`privacyPolicyURL`/`termsOfServiceURL` fields
intentionally embed the frozen `1.6.0` path. A version bump updates only the
three version fields and the CHANGELOG — never the directory name or those URLs.
