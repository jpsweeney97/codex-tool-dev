---
name: markdown-reformat
description: Use when the user asks to turn rough text, plaintext notes, wrapped prose, or loosely structured content into proper Markdown without materially changing the content, wording, or voice. Trigger on requests like "format this as proper Markdown", "clean up these notes into Markdown", "normalize this draft", or "fix the headings and lists". Do not use for summarization, substantive rewriting, or general copyediting when the user is not asking for Markdown structure.
---

# Markdown Reformat

Turn rough text into clean Markdown while preserving meaning, wording, ordering, detail, and voice. Prefer structural cleanup over prose rewriting.

## Quick Start

- Read the full source before assigning heading levels.
- Preserve content and order unless the user asks to reorganize it.
- Infer the lightest structure that fits the source.
- Prefer conservative formatting when hierarchy is ambiguous.
- Fix broken wrapping and Markdown syntax, not the author's argument.
- Preserve spelling, capitalization, punctuation, and emphasis unless a change is required to make the Markdown valid or readable.
- If a label could be either a heading or a lead-in sentence, keep it as plain text or a bold lead-in unless the following block clearly belongs under it.
- If two plausible hierarchies would materially change meaning, ask one focused question. Otherwise choose the shallower structure.

## Use This Skill When

- A plaintext document needs real Markdown headings, lists, or spacing.
- Wrapped prose needs to be merged into readable paragraphs.
- A numbered outline should become a structured Markdown document.
- Mixed prose and snippets need inline code or fenced code blocks.
- Existing Markdown is present but poorly formatted or inconsistently structured.

## Do Not Use This Skill When

- The user wants a summary, rewrite, or stronger prose.
- The task is primarily proofreading or editorial cleanup.
- The requested output is another format such as `.docx`, HTML, or PDF.
- The structure is so ambiguous that choosing a hierarchy would change meaning. Ask a focused question in that case.

## Workflow

### 1. Identify the document shape

Classify the source before editing:

| Shape | Signals | Default behavior |
| ----- | ------- | ---------------- |
| Report or review with numbered sections | Title-like first line, numbered sections, severity labels, findings | Preserve numbering, keep headings shallow, preserve labels such as `Correctness` or `Operational` verbatim |
| Notes or outline | Fragmentary lines, bullets, short labels, uneven nesting | Prefer shallow headings and lists, do not invent transitions or merge unrelated fragments into prose |
| Instructions or checklist | Imperatives, steps, prerequisites, checkboxes, commands | Preserve execution order, keep procedural steps explicit, use task lists only when checkbox intent is already present |
| Mixed prose with embedded code, commands, or regexes | Commands, code-like indentation, prompts, patterns, config fragments | Isolate code-like blocks before reflow, keep literals intact, and never rewrap inside code-like content |

### 2. Normalize hierarchy

- Promote an obvious document title to a single `#` heading when the first non-empty line reads like a title rather than body text.
- Convert clear top-level sections into `##` headings.
- Use deeper heading levels only when the source clearly implies nesting.
- Preserve numbering in headings when the numbering carries meaning.
- Never skip heading levels.
- Convert a standalone label such as `Correctness` into a heading only when it clearly governs the following block. Otherwise keep it as a paragraph label or `**Correctness.**`.
- Keep prose as paragraphs. Do not convert paragraphs into bullets unless the source already behaves like a list.

### 3. Normalize Markdown syntax

- Use `-` for unordered lists unless a different marker is already meaningful.
- Use `1.` style numbering for ordered lists.
- Reflow hard-wrapped paragraphs into single paragraphs.
- Add blank lines between headings, paragraphs, lists, and fenced blocks.
- Use inline code for identifiers, file paths, commands, ticket IDs, regex fragments, environment variables, and literal placeholders.
- Fence multi-line code, commands, and regexes. Add an info string when it is obvious, such as `python`, `bash`, or `regex`.
- Do not reflow or reinterpret code-like blocks, tables, blockquotes, YAML frontmatter, HTML comments, or link reference definitions.
- Preserve existing fenced blocks. If the language is not obvious, keep or omit the info string rather than guessing.
- Keep existing task-list markers such as `- [ ]` intact. Only create task lists when the source clearly represents checkbox semantics.

### 4. Preserve semantics

- Keep all substantive claims, caveats, examples, and severity labels.
- Do not silently delete duplication if it might be intentional emphasis.
- Do not add conclusions, headings, or grouping that imply stronger certainty than the source supports.
- If two structures are plausible, choose the less committal one.
- Do not fix spelling, punctuation, capitalization, or title case unless the change is required to repair broken Markdown syntax.

### 5. Deliver the result

- If working on a file, rewrite it in place.
- If the user pasted text, return the Markdown directly.
- Mention any conservative choices only when they affect readability or interpretation.

## Common Conversions

- A top line that reads like a title becomes `# Title`.
- Numbered major sections such as `1. Assumptions Audit` become `## 1. Assumptions Audit`.
- Standalone labels inside a section such as `Correctness` or `Operational` become `###` headings only when they clearly introduce the block that follows. Otherwise keep them inline as labels.
- Single-line literals such as `rg pattern src/` stay inline unless the surrounding context makes them a block.
- Multi-line code, regexes, or shell snippets become fenced blocks.

## Defaults and Failure Modes

- If the source already is valid Markdown, make only the minimal cleanup needed.
- If the source mixes numbering and bullets inconsistently, preserve the author's intent rather than forcing uniformity everywhere.
- If a list item wraps across lines, merge it into one list item rather than splitting it.
- If formatting would require guessing omitted structure, stop at the highest-confidence cleanup and surface the ambiguity.
- If the source already contains tables, blockquotes, footnotes, or link reference definitions, preserve that structure and clean only obvious spacing or fence issues.
- If text could plausibly be either prose or code, preserve the original layout or use a neutral fenced block rather than guessing.
- If frontmatter is present at the top of the document, preserve it exactly unless the user asked for a format conversion that requires changing it.

## Done When

- No substantive content, caveat, example, or repeated emphasis has been removed.
- No new claims, conclusions, or section relationships have been introduced.
- Heading depth is consistent and does not skip levels.
- Code blocks, commands, regexes, and inline literals are formatted as Markdown without changing their content.
- Already-valid Markdown received only minimal cleanup.

## Anti-Patterns

| Pattern | Problem | Fix |
| ------- | ------- | --- |
| Rewriting for style | Changes voice and meaning | Limit edits to structure and obvious wrap repair |
| Inventing deep heading trees | Adds interpretation not present in the source | Use the shallowest hierarchy that fits |
| Fencing every literal | Makes prose noisy | Use inline code for short literals and fences only for blocks |
| Turning prose into lists | Fragments arguments and changes emphasis | Keep prose as paragraphs unless the source is list-shaped |
| Dropping repeated lines | Can remove deliberate emphasis or nuance | Preserve repetition unless the user asks for cleanup beyond formatting |

## Examples

**User:** "Format this as proper Markdown."

**Input:**

```text
Review Notes

1. Risks

- first issue
- second issue

Correctness

The current parser is too eager.
```

**Output:**

```markdown
# Review Notes

## 1. Risks

- first issue
- second issue

### Correctness

The current parser is too eager.
```

**Input:**

```text
Release Notes

This line wraps
because it came from email export
and should stay one paragraph.

Next steps
- verify staging
- ship
```

**Output:**

```markdown
# Release Notes

This line wraps because it came from email export and should stay one paragraph.

## Next steps

- verify staging
- ship
```

**Input:**

```text
Deploy checklist

Run:
npm test
npm run build

Regex
^feature/.+$
```

**Output:**

````markdown
# Deploy checklist

Run:

```bash
npm test
npm run build
```

## Regex

```regex
^feature/.+$
```
````
