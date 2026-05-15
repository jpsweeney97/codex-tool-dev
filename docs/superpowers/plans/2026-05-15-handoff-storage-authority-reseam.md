# Handoff Storage Authority Reseam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `storage_authority.py` into testable storage-layout and chain-state units without changing Handoff runtime behavior.

**Architecture:** Extract the lowest-risk layout/path arithmetic first, then chain-state lifecycle helpers. Keep candidate discovery and public CLI contracts green after every commit.

**Tech Stack:** Python 3.11+, standard library, existing Handoff pytest suite.

---

## Required Preconditions

- Handoff CI exists and passes.
- Active-write proxy facade has been removed or intentionally enforced.
- `LEGACY_CONSUMED_PREFIX` is shared from `storage_primitives.py`.
- Contributor architecture docs exist.

## Slice Order

1. Extract `storage_layout.py` with `StorageLayout`, `get_storage_layout()`, and path arithmetic only.
2. Move duplicated path/git/lock helpers only when tests prove the ownership boundary.
3. Extract chain-state marker/selection lifecycle after layout extraction is green.
4. Refactor `write_active_handoff` complexity only inside the active-write ownership boundary.
5. Split `session_state.py main()` only after storage reseam is complete and CLI behavior has regression tests.

## Hard Stops

- Stop if any slice requires installed-cache mutation to prove source behavior.
- Stop if a slice changes JSON payload schemas without updating tests and skill/reference docs in the same commit.
- Stop if a task cannot run the full Handoff suite green before commit.
