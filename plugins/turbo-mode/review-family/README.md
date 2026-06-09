# Review Family Plugin

Evidence-first review, scrutiny, and review-adjudication skills for Claude Code
and Codex local development workflows.

This directory is the source-authority package for the Review Family plugin.
Installed cache and runtime artifacts are separate proof surfaces and may
diverge until an explicit cache-refresh or runtime-proof lane verifies them.
Source edits here do not prove installed runtime behavior.

## Installation

The canonical source lives at `~/.agents/plugins/review-family/` and is listed
in the personal `turbo-mode` marketplace (`~/.agents/plugins/marketplace.json`).

Codex installs from that marketplace (re-run the same command to refresh the
installed copy after source edits):

```bash
codex plugin add review-family@turbo-mode
```

Claude Code loads the same source in place as a skills-directory plugin via a
symlink in `~/.claude/skills/` managed by
`~/.agents/scripts/claude-skills-sync.sh`.

No build step is required. The plugin ships skills only and has no runtime
package, hook, MCP, app, or script dependency.

## What It Does

| Capability | Skills | Description |
|------------|--------|-------------|
| **Adversarial artifact review** | `scrutinize` | Challenge plans, designs, drafts, decisions, and broad artifacts with evidence-backed findings. Ask for a formal stress test when you want an explicit assumptions audit, pre-mortem, dimensional critique, and confidence boundary; ask for an execution-readiness review when you need to know whether a plan is ready to build from. |
| **Skill behavior review** | `scrutinize-skill` | Review agent skills as behavior contracts for execution quality, UX, composability, overlap, and proof gaps. Skill targets route here even when the user says "scrutinize". |
| **Implementation review** | `implementation-review` | Review completed work against a plan, spec, diff, or known intended behavior. |
| **System design review** | `system-design-review` | Review architecture and system design artifacts for scoped design-lens gaps and missing probes. |
| **Review adjudication** | `review-reviewer` | Check supplied reviews and pasted review claims against target evidence before acting on them. |

## Components

### Skills (5)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `implementation-review` | Completed implementation review against a plan, spec, PR, or known intended behavior | Compare implemented behavior to the stated contract and report ranked findings. |
| `review-reviewer` | Supplied review, critique, audit, reviewer output, or pasted claims that need checking | Separate current truth from reviewer disposition and identify which findings or claims are valid, stale, or unproven. |
| `scrutinize` | "Scrutinize", "tear this apart", "be brutal", reject-until-proven review, formal stress test, or execution-readiness review for non-skill targets | Adversarially inspect a plan, design, argument, code change, or broad artifact without implementing fixes. |
| `scrutinize-skill` | Adversarial review of an agent skill or proposed skill contract | Review whether the skill will guide agent behavior well once triggered, including UX, overlap, composability, and proof gaps. |
| `system-design-review` | Architecture or system design review of docs, verbal designs, or codebase structure | Review design tradeoffs, defaults, interfaces, operations, and next probes. |

The plugin is intentionally review-only. These skills may recommend repairs,
verification, or escalation, but they do not edit files, stage changes, commit,
sync, publish, or run cleanup unless the user explicitly widens the task after
the review.

## Usage Patterns

### Review A Completed Implementation

```text
Use implementation-review to check this branch against docs/plans/plan.md.
```

### Challenge A Plan Before Work Starts

```text
Scrutinize this migration plan. Assume the plan is wrong until the evidence says otherwise.
```

### Check Execution Readiness

```text
Use $scrutinize for an execution-readiness review of this handoff. Tell me whether it is ready to execute.
```

`pragmatic-review` has been retired as a separate skill. Use `$scrutinize` and
ask for an execution-readiness review when you need to know whether a plan,
spec, handoff, or rollout note is ready to implement.

### Request A Formal Stress Test

```text
Use $scrutinize to run a formal stress test of this proposal, including an assumptions audit, pre-mortem, dimensional critique, and confidence boundary.
```

`adversarial-review` has been retired as a separate skill. Use `$scrutinize` and
ask for a formal stress test when you want the heavier review packet.

### Review A Skill Contract

```text
Use scrutinize-skill to review this skill as a behavior contract.
```

### Adjudicate A Pasted Review

```text
Use $review-reviewer to adjudicate this review, including reliability, missed issues, and what I should act on.
```

### Check Pasted Claims

```text
Use $review-reviewer to check these claims against the current repo before I act.
```

`review-claude-claims` has been retired as a separate skill. Use
`$review-reviewer` and ask it to check these claims when you need itemized
current-evidence claim validation without the broader review-adjudication packet.

`request-claude-pr-review` has been retired from Review Family. It was a
prompt-drafting workflow helper, not a Codex-performed review or adjudication
lane. There is no active replacement inside Review Family.

## Configuration

No configuration is required.

Review Family does not ship hooks, scripts, runtime services, or persistent
storage. Skills inspect the user-provided target, local files, git state, GitHub
state, or referenced artifacts only when the active request calls for that
evidence.

## Source Authority And Runtime Proof

`~/.agents/plugins/review-family/` is the canonical source. Downstream
artifacts are the Codex install cache
(`~/.codex/plugins/cache/turbo-mode/review-family/<version>/`, refreshed by
`codex plugin add review-family@turbo-mode`) and the GitHub release mirror in
`codex-tool-dev` (updated only at explicit publish time). Claude Code reads the
canonical source in place through its skills-directory symlink, so no Claude
copy exists.

Treat marketplace metadata and copied files as setup evidence only. To prove
loaded runtime behavior, inspect the active runtime's plugin and skills
inventory after refresh and restart.

## Privacy And Terms

- Privacy notice: `PRIVACY.md`
- Terms: `TERMS.md`
- Changelog: `CHANGELOG.md`
