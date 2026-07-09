# Throughline Format

The throughline is one derived Markdown document per project:

```text
<project_root>/.agents/handoffs/THROUGHLINE.md
```

The capital filename signals "not a session handoff" in directory listings.

## Frontmatter

```yaml
---
type: throughline
updated_at: "2026-06-10T14:30:00Z"
project: fixture-project
covers_through: "2026-06-10_01-19-11_plan-patched-inline-execution-ready.md"
sources_folded: 47
---
```

`covers_through` holds the basename of the newest source handoff folded in. It is a high-water mark of what was folded, not proof of complete coverage. `sources_folded` holds the total count of source files folded; together the pair lets a refresh detect drift below the water line.

The detection class is count drift — files appearing or vanishing — not in-place content edits of same-named files: handoffs are write-once by contract, and content-edit staleness is handled by the rebuild recovery path, not by detection.

## Body Prompts

```markdown
# Throughline: <project>

## Project Narrative
## Decisions That Hold
## Abandoned Paths
## Frontier (as of <updated_at>)
```

These headings are prompts, not a schema.

- **Project Narrative** — the eras: what each phase was about, how we got here.
- **Decisions That Hold** — settled choices and load-bearing constraints; the "don't relitigate this" layer. Only truly project-level settled choices belong here; side-branch decisions stay branch-scoped.
- **Abandoned Paths** — what was tried and dropped, and why.
- **Frontier (as of `<updated_at>`)** — open threads at last refresh, explicitly deferring to the newest handoff and live state for current truth.

## Size

Under ~32KB (~8k tokens): load-handoff reads the document in full every session, so size is a recurring per-session cost. Over budget, compress oldest-first — pre-frontier eras to era-cluster summaries, settled do-nots to decision-plus-pointer — keeping "Decisions That Hold" and the frontier richest. The budget number is fixed; what to compress is judgment, and no validator enforces it.

## Evidence Boundary

The throughline is derived evidence, not authority: on conflict, the underlying handoffs and live state win.
