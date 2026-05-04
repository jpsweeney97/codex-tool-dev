---
name: next-steps
description: Use when the user wants to turn findings, review output, audit results, brainstorming notes, retrospective outcomes, or other analysis into a dependency-aware strategic action plan. Trigger on requests like "what do we do about this", "plan this out", "what's the sequence here", "how should we tackle these findings", "action plan", "create an action plan", or "what's the plan of attack". Use for strategic tasks where done means the approach is agreed and ready for a focused follow-up session. Do not use for session-sized implementation planning, step-by-step coding plans, or direct execution work.
---

# Action Plan

Produce a dependency-aware, gated plan of high-level strategic tasks from existing findings or analysis. Turn a pile of issues into an ordered plan for what to resolve first, what can run in parallel, and where decisions can change the path.

## Quick start

- Identify the findings, problems, or themes that the plan is meant to address.
- Separate strategic tasks from implementation tasks. Keep this plan at the "what and why" level, not the "how" level.
- Build a dependency map before sequencing phases.
- Surface decision gates explicitly instead of pretending the plan is linear when it is not.
- Derive the critical path from the dependency map, then name the single highest-risk task.
- Park non-critical items instead of bloating the immediate plan.

## Defaults and failure modes

- If there is no clear set of findings to plan from, ask what artifact or discussion should be turned into a plan.
- If the analysis contains only one obvious next step, say so directly instead of fabricating a multi-phase plan.
- If the work is already implementation-ready, say that this skill is the wrong level and switch to normal implementation planning.
- If several independent problem areas are mixed together, separate them into named strategic tasks instead of blending them into one vague item.
- If sequencing is uncertain, state what missing information would resolve the ordering instead of guessing.

## Non-negotiables

- Stay strategic. Each task must name what should change and why it matters, not how to implement it.
- Define task completion as `approach agreed`, `question resolved`, or `ready for a focused follow-up session`.
- Keep the task list as small as reality allows. Do not pad the plan.
- Surface dependencies explicitly. If two tasks can start now, say so.
- Prefer the order that resolves blocking decisions earliest, not the order that feels easiest.

## Workflow

### 1. Summarize the current state

Write one short paragraph that states:

- What findings or themes are being acted on
- What is being parked for later
- Any hard constraints, dependencies, or scope boundaries already known

### 2. Build the dependency map

List every discrete strategic task needed to address the active findings.

Use short task IDs such as `T1`, `T2`, and `T3`.

For each task, state:

- The task itself
- What it depends on, or `none - can start now`

Use this format:

- `T1: <task> - depends on: none`
- `T2: <task> - depends on: T1`
- `T3: <task> - depends on: none (parallel to T1)`

### 3. Sequence the plan

Group tasks into phases derived from the dependency map.

- Tasks in the same phase are parallelizable.
- A later phase must only contain tasks blocked on earlier phases.

For each task, include a `done when` clause that stays at the strategic level.

Use this format:

```markdown
**Phase 1** (can start now):
- T1: <task> - done when: <approach agreed / question resolved / ready for follow-up session>
- T3: <task> - done when: <approach agreed / question resolved / ready for follow-up session>

**Phase 2** (after Phase 1):
- T2: <task> - done when: <approach agreed / question resolved / ready for follow-up session>
```

### 4. Call out decision gates

State where the plan branches based on an outcome.

Use this format:

- `After T1: if <condition>, then <path A>; otherwise <path B>`

If there are no meaningful decision points, say: `None - all tasks have a single forward path.`

### 5. Identify the critical path

State the longest dependency chain, such as `T1 -> T3 -> T5`.

Then name the single highest-risk task and state:

- Which task it is
- The likelihood it stalls the plan
- The impact if it does
- Whether it is on the critical path
- Why it deserves priority

Recommend starting there unless another task must precede it.

### 6. Park out-of-scope items

List findings worth revisiting later but not required for the immediate goal. Keep this to 3-5 items max.

## Output format

Use this structure:

```markdown
### 1. Current State
[one paragraph]

### 2. Dependency Map
- T1: <task> - depends on: none
- T2: <task> - depends on: T1

### 3. Sequenced Plan
**Phase 1** (can start now):
- T1: <task> - done when: <strategic completion condition>

**Phase 2** (after Phase 1):
- T2: <task> - done when: <strategic completion condition>

### 4. Decision Gates
- After T1: if <condition>, then <path A>; otherwise <path B>

### 5. Critical Path
**Scheduling:** <critical path chain>

**Highest-risk task:** <task> - likelihood: <low/medium/high>; impact: <low/medium/high>; on critical path: <yes/no>; why: <reason>

### 6. Out of Scope (Parked)
- <item>
- <item>
```

Before finalizing, verify that the critical path is derivable from the dependency map. Every link in the chain must correspond to a declared dependency.

## Anti-patterns

| Pattern | Problem | Fix |
| ------- | ------- | --- |
| Turning the plan into implementation steps | It makes the plan brittle and too detailed for this stage. | Stay at the level of strategic tasks and follow-up sessions. |
| Listing tasks without dependencies | It hides sequencing and parallelism. | Make every dependency explicit, including `none - can start now`. |
| Sequencing by comfort | Easy work first can delay the real blocker. | Order the plan around decision resolution and dependency removal. |
| Treating all tasks as equal | It obscures the real schedule driver. | Name the critical path and highest-risk task explicitly. |
| Padding the plan | It dilutes signal and slows execution. | Keep only the tasks required to move from findings to an agreed approach. |
| Hiding uncertainty | A fake linear plan creates rework later. | Use decision gates and state what could branch the plan. |

## Example

**User:** "We just finished a security review and a reliability audit. What should we tackle first?"

> ### 1. Current State
> The active findings are weak service-to-service trust boundaries, incomplete rollback procedures, and unclear ownership of incident recovery. Cosmetic cleanup items and low-value documentation improvements are parked. The main constraint is that production changes cannot proceed until the trust and rollback approach is agreed.
>
> ### 2. Dependency Map
> - T1: define the target trust-boundary model for service-to-service calls - depends on: none
> - T2: define the rollback and recovery strategy for high-risk deployments - depends on: none
> - T3: assign ownership and escalation paths for incident recovery - depends on: T2
> - T4: decide whether the current rollout plan can continue or must be re-scoped - depends on: T1, T2
>
> ### 3. Sequenced Plan
> **Phase 1** (can start now):
> - T1: define the target trust-boundary model for service-to-service calls - done when: the security model is agreed and ready for focused design work
> - T2: define the rollback and recovery strategy for high-risk deployments - done when: the rollback approach is agreed and ready for operational planning
>
> **Phase 2** (after Phase 1):
> - T3: assign ownership and escalation paths for incident recovery - done when: ownership is agreed and escalation gaps are closed
> - T4: decide whether the current rollout plan can continue or must be re-scoped - done when: the go/no-go criteria are agreed
>
> ### 4. Decision Gates
> - After T1 and T2: if the security model or rollback plan requires architectural change, then re-scope the rollout; otherwise continue with focused implementation planning.
>
> ### 5. Critical Path
> **Scheduling:** T2 -> T3
>
> **Highest-risk task:** T2 - likelihood: high; impact: high; on critical path: yes; why: the plan cannot safely move forward without a credible rollback and recovery strategy.
>
> ### 6. Out of Scope (Parked)
> - clean up non-critical internal docs
> - standardize low-risk dashboard naming
