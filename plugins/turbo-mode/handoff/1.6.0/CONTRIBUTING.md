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

## Runtime Boundaries

Implementation modules live in `turbo_mode_handoff_runtime/`.
The `scripts/` directory contains executable CLI facades only. Do not add new `scripts.*` import dependencies.

Installed-runtime claims require runtime inventory. Source tests alone prove source behavior only.
