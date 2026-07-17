---
name: release-cut
description: "Use when cutting a release for a versioned unit: derive the next semver from the real landed change class, bump the authoritative manifest (plugin.json/package.json — never a git tag), and write a dated CHANGELOG section in lockstep, stopping at a staged local bump. Do not use to decide whether work is done or make the final commit (`closeout-check`), land a branch (`merge-branch`), author a PR body (`pr-description`), or push/tag/publish (gated)."
---

# Release Cut

Cut the release artifacts for one versioned unit from what **actually landed**: the next version and a dated changelog entry, derived from the real change set, staged into the working tree and stopped before anything outward. Once one judgment is made, the rest is mechanical.

**The judgment is the change class, and you read it from the diff — not the commit labels.** The next version follows from whether what landed is breaking, a feature, or a fix/chore. Two failures matter, one at each boundary: shipping an under-tagged **breaking** change as a patch because a `fix:` commit hid it, and over-bumping a **fix to a minor** because a change that only documents or normalizes an existing capability *looks* additive. So read the diff and answer two forcing questions, in order:

> 1. **Break? (major ↔ rest)** Is there a breaking change here that no commit labelled `feat`/`fix` announced? If you cannot rule one out, the bump is **major**.
> 2. **Feature, or just documenting one? (minor ↔ patch)** Does this let a user *do something they could not do before* — a new capability, command, flag, or skill? Or does it only **document, normalize, rename-for-consistency, fix, or restate** something that already worked? A genuinely new ability is **minor**; adding tokens, aliases, examples, or wording that describes behavior the unit *already had* is **patch**. When the diff only edits descriptions/docs of existing behavior, default to **patch**.
>
> And for every changelog line and the version itself — can I point to the landed change it comes from?

Everything downstream of these two answers is mechanical, sourced from facts, never invented.

## 1. Scope one release unit, and gather the facts

A release unit is one independently-versioned thing — here a single `plugins/<name>/` plugin; elsewhere a package or repo root. Cut **exactly one per invocation**.

Run this skill's bundled, read-only fact reporter (it writes nothing):

```
scripts/release-cut-facts.sh <release-unit-dir> [<base>..HEAD]
```

It lives in this skill's own `scripts/` directory — invoke it by its full installed path. It reports the authoritative manifest and current version (presence-ordered: `plugin.json` → `package.json` → `pyproject.toml` → `Cargo.toml`), the CHANGELOG state, manifest↔changelog lockstep, and — given a commit range — which units the range touched. If it reports more than one plugin changed, cut each separately; do not bump one and forget the other.

The version source is the **manifest, never a git tag**. A repo can have zero tags and real versions; the manifest version is the release signal the runtime cache and any distribution mirror read. A tag, if ever cut, is a downstream label derived from the manifest, not consulted here.

## 2. Decide the next version from the change class

Read the real landed diff for this unit's paths and answer both forcing questions. Then apply semver to the current manifest version:

- breaking change → **major**
- new backward-compatible capability → **minor**
- fix or chore only → **patch**

The bump is your reasoned decision, not a tool's output and not a commit-type lookup. State the one-line reason, including both the breaking-change check and the feature-vs-documentation check.

## 3. Write the manifest and CHANGELOG in lockstep

- Write the new version into the manifest.
- Add a new dated section to `CHANGELOG.md` keyed to the **same** version string — Keep a Changelog style (`## <version> - <YYYY-MM-DD>`, with Added/Changed/Fixed/Removed as they apply) — above the previous top section. Never rewrite prior dated sections; append above them.
- Assemble the section from the real landed changes for this unit. Every line points at something that landed; never invent an entry.
- If `CHANGELOG.md` is **absent** (some units deliberately keep none), surface the choice — create it with the Keep a Changelog header plus the first section, or record a deliberate no-changelog decision — rather than silently degrading to a manifest-only bump.
- The manifest version and the top CHANGELOG heading must end **byte-identical**. Re-run the fact reporter to confirm; if it already reports `AGREE` on the target version, the cut is done — do not double-bump.

## 4. Stage, and stop before publishing

This skill **stages** a release. It does not commit by default and never publishes.

- **Stage** the manifest and CHANGELOG edits into the working tree, and by default leave them staged so the commit that lands the work carries them — this repo folds the version bump and changelog into the **same** commit as the change, not a separate bump-only commit. Make a standalone bump commit only when the work is already committed and you are cutting the release as a follow-up; for that, hand the commit to `closeout-check` or `merge-branch`, which own the commit and its protected-branch gate. All edits happen on a work branch, never `main` or a protected branch.
- **Name, but do not fire, the outward publish train.** Print the exact gated next steps for the user to authorize and run none of them. For a distributed plugin this is, in order: land the branch → republish the plugin to its runtime cache → update any distribution mirror → push. Publishing, tagging, pushing, republishing, and mirroring are outward acts that happen only on explicit authority.

## Boundaries

In scope: choosing the next version from the landed change class, and writing the manifest version and a dated CHANGELOG section in lockstep — staged, and stopped.

Out of scope — route instead:

- deciding whether the work is **done** or making the final commit → `closeout-check`; **cutting a release is not deciding readiness.**
- landing or merging a branch → `merge-branch`.
- authoring a PR title and body → `pr-description`.
- shaping commits or cleaning local state → `git-hygiene`.
- the outward acts — push, tag, open/merge a PR, republish the runtime cache, copy into a mirror → gated and explicit; never by default.

This skill does not own a git tag (the manifest is authoritative), a marketplace manifest's version, or any republish/mirror step. It is not a release-readiness scorer: the one judgment is the bump magnitude.

## Output

1. **Version decision** — the new version and the one-line change-class reason, with the breaking-change check explicit.
2. **Edits** — the manifest and CHANGELOG paths changed, staged, with the byte-identical version confirmed.
3. **Sourcing note** — the commit range the changelog was derived from, and what you could **not** source (intent unstated, a change you could not attribute) — the same honesty the changelog carries.
4. **Next steps** — the named, copy-pasteable gated publish train, run by no one until authorized; `staged (not committed)` by default, or the standalone bump commit when that path applied.
