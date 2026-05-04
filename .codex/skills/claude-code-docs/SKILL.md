---
name: claude-code-docs
description: "Search and cite official Claude Code documentation through the claude-code-docs MCP server. Use for Claude Code setup, commands, hooks, agents, plugins, MCP, settings, IDE/CI, troubleshooting, and changelog questions, including asks like PreToolUse schema, plugin marketplace install, /mcp settings, or Claude Code changelog. Do not use for Claude API, Anthropic SDK, general programming, or non-Claude-Code product questions."
---

# Claude Code Docs

Search indexed Claude Code documentation and answer from retrieved results only.

## When to Use

Use this skill when the user needs grounded, current Claude Code documentation, such as:

- Configuration syntax, field names, or schemas
- Setup and installation questions
- Claude Code commands, hooks, agents, plugins, MCP, settings, IDE/CI, troubleshooting, or changelog questions
- Requests that benefit from `chunk_id` citations or explicit documentation coverage checks

Trigger examples:

- `What does PreToolUse return in Claude Code hooks?`
- `How do I configure /mcp in Claude Code?`
- `What changed in the Claude Code changelog?`

## When Not to Use

Do not use this skill for:

- Claude API or Anthropic SDK questions
- General programming or debugging questions unrelated to Claude Code documentation
- Non-Claude-Code product questions

Non-trigger examples:

- `How do I use the Anthropic Python SDK?`
- `Help me debug this React component`

## Default Execution Path

1. Classify the question.
   - If it is a single focused Claude Code docs question, answer inline.
   - If it spans multiple documentation areas or will likely require 3 or more searches, delegate to the `claude-code-docs-researcher` agent.
2. Refresh the index first only when the user asks for the latest documented behavior or the initial results appear stale.
3. Run `mcp__claude-code-docs__search_docs` with a concrete query that names the feature, command, or concept.
4. If the first result set is weak or ambiguous, retry in this order:
   - canonical feature name
   - joined or split variant, such as `PreToolUse` and `pre tool use`
   - category refinement when the topic area is clear
5. Draft the answer from the top 1-3 relevant matches.
6. Cite the returned `chunk_id` for every material claim.
7. State explicitly when documentation is missing, partial, or weak.

## Query Strategy

- Translate vague asks into the documentation's vocabulary.
- Prefer exact feature names and noun-heavy queries, such as `PreToolUse JSON output`, `plugin marketplace install`, or `mcp stdio settings`.
- Try both joined and split variants, such as `PreToolUse` and `pre tool use`.
- Retry with close synonyms, such as `subagents` and `agents`, or `before tool` and `pre tool`.
- Shorten the query when results are sparse or off-topic.

Common categories:

- `hooks`
- `skills`
- `commands`
- `agents`
- `plugins`
- `plugin-marketplaces`
- `mcp`
- `settings`
- `memory`
- `overview`
- `getting-started`
- `cli`
- `best-practices`
- `interactive`
- `security`
- `providers`
- `ide`
- `ci-cd`
- `desktop`
- `integrations`
- `config`
- `operations`
- `troubleshooting`
- `changelog`

Aliases:

- `subagents` -> `agents`
- `sub-agents` -> `agents`
- `slash-commands` -> `commands`
- `claude-md` -> `memory`
- `configuration` -> `config`

## Failure Modes

If search returns no results:

1. Retry with the exact feature name.
2. Retry with CamelCase or spaced variants.
3. Retry with a category filter if the topic area is obvious.
4. If results are still empty, say: `The Claude Code documentation does not appear to cover this topic.`

If results are broad but relevant:

1. Add or refine the category filter.
2. Use a more specific query.
3. Focus the answer on the top 2-3 chunks instead of summarizing the whole result set.

If the question spans multiple documentation areas or needs 3 or more searches:

1. Delegate to the `claude-code-docs-researcher` agent.
2. Keep single-lookups inline. Do not delegate a question that one or two searches can answer directly.

If the MCP server appears unavailable:

1. Run `mcp__claude-code-docs__reload_docs`.
2. Retry the search.
3. If the tools are still unavailable, say: `I cannot provide authoritative Claude Code documentation right now because the claude-code-docs MCP server is inaccessible.`

If results appear stale:

1. Run `mcp__claude-code-docs__reload_docs`.
2. Re-run the search before answering.

## Response Contract

- Base the answer on retrieved documentation, not memory.
- Avoid inventing settings, flags, file formats, or behavior not present in results.
- Include `chunk_id` citations inline. Add `source_file` links only when the user asks for links.
- When documentation is incomplete, say so directly instead of inferring coverage.
- Label inference explicitly when the docs imply, but do not directly state, a conclusion.
  - Use `Documented:` for direct statements supported by the retrieved docs.
  - Use `Inference:` only for narrow conclusions drawn from documented facts.

## Quick Check

Before responding, verify all of the following:

- At least one search ran.
- Every material claim is backed by at least one `chunk_id`.
- Alternate query terms were tried if the first search failed.
- Missing coverage is stated explicitly instead of guessed.
- Any inference is labeled as inference.
