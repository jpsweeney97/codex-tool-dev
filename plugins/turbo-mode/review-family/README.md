# Review Family Plugin

Evidence-first Codex review, scrutiny, and review-adjudication skills for local
development workflows.

This directory is the source-authority package for the Review Family plugin.
Installed cache and runtime artifacts are separate proof surfaces and may
diverge until an explicit cache-refresh or runtime-proof lane verifies them.
Source edits here do not prove installed Codex behavior.

## Installation

Install via the Codex plugin system:

```bash
codex plugin marketplace update turbo-mode
codex plugin add review-family@turbo-mode
```

Or install directly from the development repo:

```bash
codex plugin install ./plugins/turbo-mode/review-family
```

No build step is required. The plugin ships skills only and has no runtime
package, hook, MCP, app, or script dependency.

## What It Does

| Capability | Skills | Description |
|------------|--------|-------------|
| **Adversarial artifact review** | `scrutinize`, `adversarial-review` | Challenge plans, designs, drafts, decisions, and broad artifacts with evidence-backed findings. |
| **Implementation review** | `implementation-review`, `pragmatic-review` | Review completed work against a plan, spec, diff, or execution-readiness criteria. |
| **System design review** | `system-design-review` | Review architecture and system design artifacts for scoped design-lens gaps and missing probes. |
| **Review adjudication** | `review-reviewer`, `review-claude-claims` | Check supplied reviews and pasted Claude claims against the target evidence before acting on them. |
| **Claude PR prompt drafting** | `request-claude-pr-review` | Generate a ready-to-send Claude Code PR-review prompt from current PR context. |

## Components

### Skills (8)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `adversarial-review` | Explicit adversarial, hostile, or failure-mode review of a concrete artifact | Read-only, evidence-first review that hunts for real ways the target can fail. |
| `implementation-review` | Completed implementation review against a plan, spec, PR, or known intended behavior | Compare implemented behavior to the stated contract and report ranked findings. |
| `pragmatic-review` | Execution-readiness, plan-readiness, rollout-readiness, or "can this work in practice?" review | Stress test whether a proposal is operationally executable with clear next steps. |
| `review-claude-claims` | Pasted Claude claims, review comments, or recommendations that need verification | Treat claims as allegations and verify them against source evidence before endorsing action. |
| `review-reviewer` | Supplied review, critique, audit, or reviewer output that needs adjudication | Separate current truth from reviewer disposition and identify which findings are valid, stale, or unproven. |
| `request-claude-pr-review` | Request for a Claude Code PR-review prompt or review brief | Draft a bounded prompt for Claude Code to review a GitHub pull request. |
| `scrutinize` | "Scrutinize", "tear this apart", "be brutal", or reject-until-proven review | Adversarially inspect a plan, design, argument, code change, or artifact without implementing fixes. |
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

### Adjudicate A Pasted Review

```text
Use review-reviewer on this review and tell me which findings are currently valid.
```

### Prepare A Claude PR Review Request

```text
Use request-claude-pr-review to draft a Claude Code prompt for this PR.
```

## Configuration

No configuration is required.

Review Family does not ship hooks, scripts, runtime services, or persistent
storage. Skills inspect the user-provided target, local files, git state, GitHub
state, or referenced artifacts only when the active request calls for that
evidence.

## Source Authority And Runtime Proof

`plugins/turbo-mode/review-family` is the development source package. Personal
plugin copies under `~/.codex/plugins/review-family` and Codex runtime plugin
state are downstream artifacts.

Use the Turbo Mode refresh workflow to plan and sync source into the personal
plugin directory. Treat marketplace metadata and copied files as setup evidence
only. To prove loaded runtime behavior, inspect the active Codex plugin and
skills inventory after refresh and restart.

## Privacy And Terms

- Privacy notice: `PRIVACY.md`
- Terms: `TERMS.md`
- Changelog: `CHANGELOG.md`
