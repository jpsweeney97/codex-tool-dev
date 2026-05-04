---
name: system-design-review
description: "Review system architecture through 8 design-lens categories and surface inherited defaults, underspecified decisions, tradeoffs, and cross-cutting tensions. Use when the user asks to review an architecture or system design, assess design gaps, stress-test an architecture, or evaluate a design doc, codebase, or verbal system description. Do not use for code-level bug review, incident post-mortems, debt prioritization, refactoring sequencing, or implementation-readiness audits."
---

# System Design Review

Review architectural decisions by walking the system through design lenses. Keep one question in view throughout the review:

**"Was this a conscious decision, or an inherited default?"**

Surface inherited defaults, underspecified decisions, explicit tradeoffs, cross-cutting tensions, and the sharpest next questions. Work at the architecture level, not the implementation-bug level.

## Quick start

- Choose exactly one scope level: `system`, `subsystem`, or `interface`.
- Infer the top 1-2 system archetypes and state confidence.
- Propose a stakes tier before going deep. Never silently downgrade risk.
- Screen all 8 categories with sentinel questions before producing findings.
- Deep-dive only the lenses that earned attention through archetype weighting, screening signals, or cross-category linkage.
- End with sharp questions, not a verdict.

## Defaults and failure modes

- If the user primarily wants incident reconstruction, debt prioritization, refactoring sequencing, implementation readiness, or code bug review, hand off immediately instead of forcing an architecture review.
- If the request mixes scope levels, ask which scope to review first.
- If the input is sparse, mark categories `insufficient evidence` instead of guessing.
- If 4 or more categories would be `insufficient evidence`, say so explicitly, ask whether to narrow scope, and label the review `reduced-depth` if you continue without clarification.
- If no material findings surface at the chosen depth, say so directly. Do not pad the review.

## Scope and handoffs

**In scope:** architectural diagnosis using the lens framework. Judge decision quality and system shape, not line-level implementation quality.

| Request | Handoff |
| ------- | ------- |
| Incident timeline or root-cause analysis | "This skill identifies which lenses likely failed. Use a post-mortem skill for timeline reconstruction." |
| Debt prioritization or remediation ordering | "This skill identifies strained lenses and hidden tradeoffs. Use a planning or tech-debt skill to prioritize fixes." |
| Refactoring sequencing | "This skill surfaces architectural gaps. Use a next-steps or refactoring-triage skill to sequence remediation." |
| Implementation-readiness audit | "This skill diagnoses architectural decisions. Use a design-review or readiness skill for implementation detail checks." |
| Code-level bug review | "This skill works at the architecture level. Use a code review skill for bug hunting." |

If the request mixes in-scope and out-of-scope work, perform the architecture diagnosis first, then state the handoff explicitly. Do not silently expand into adjacent workflows.

## Execution flow

`Frame -> Screen -> Deep Dive -> Deliver`

1. `Frame` - choose scope, infer archetypes, calibrate stakes
2. `Screen` - build an evidence map and run sentinel questions across all 8 categories
3. `Deep Dive` - analyze the lenses that earned attention, then assemble findings and tensions
4. `Deliver` - present staged checkpoints appropriate to the stakes tier

## 1. Frame

### Scope selection

Choose one scope level before starting. Do not mix scope levels in one run.

- `system` - the whole architecture at the top level
- `subsystem` - a bounded component or service
- `interface` - a specific boundary, contract, or integration point

If the user asks for both a system-level review and an interface deep dive, ask which one to review first.

### Archetype identification

Infer the top 1-2 archetypes from the input. State them with a confidence level and proceed unless ambiguity would materially change which lenses deserve deep attention.

Available archetypes:

- Internal tool or back-office
- User-facing API or SaaS
- Data pipeline or ETL
- Financial or regulated
- ML or research platform
- Event-driven or streaming

When the system does not map cleanly to the list, infer up to 2 archetypes, reduce weighting strength if confidence is low, and fall back to unweighted screening plus evidence-promoted lenses if no archetype fits.

Example framing:

```text
Archetype: User-facing API + event-driven (medium confidence)
If that's wrong, correct me now. It changes which lenses I prioritize.
```

### Stakes calibration

Propose stakes and proceed. Stakes control depth, finding count, and when to invite correction.

- `low` - reversible, narrow blast radius, internal-only
- `medium` - meaningful blast radius or partial irreversibility
- `high` - hard to reverse, external or shared impact, or meaningful trust, safety, or reliability exposure

Use this decision order:

1. Honor an explicit user depth request unless a higher-risk cue overrides it.
2. If any high-risk cue is present, propose `high`.
3. If all cues are low-risk, propose `low`.
4. Otherwise, propose `medium`.
5. If uncertain between two tiers, choose the higher tier.

High-risk cues:

- External user-facing API
- Auth, permissions, or trust boundary
- Payments, regulated data, or sensitive data handling
- Migration or irreversible data change
- SLO, SLA, or availability commitment
- Shared platform or infrastructure
- Multi-team blast radius
- Distributed consistency concerns

Fail-safe: never silently downgrade. If the user does not answer a stakes question, proceed at the higher plausible tier.

## 2. Screen

Build an evidence map from the input, then run one sentinel question per category.

### Sentinel questions

| Category | Sentinel |
| -------- | -------- |
| Structural | Can I name the main components and their boundaries at this scope? |
| Behavioral | Can I trace the main runtime path and name what happens under failure, retry, or overload? |
| Data | Can I trace one critical datum from entry to storage to exit and identify its source of truth? |
| Reliability | Are guarantees, recovery, and degradation behavior stated or visible? |
| Change | Is there a credible story for change, migration, rollback, or test isolation? |
| Cognitive | Could a new engineer find the responsibility and rationale without oral tradition? |
| Trust and Safety | Is there an explicit trust boundary, privilege boundary, or sensitive-data handling point? |
| Operational | Can I tell how this is deployed, configured, observed, and owned? |

### Category statuses

| Status | Meaning |
| ------ | ------- |
| `deep` | Selected for substantive analysis. Eligible to produce findings. |
| `screened` | Concrete check completed against anchored evidence. No material concern at screening depth. |
| `insufficient evidence` | Available evidence is too weak to classify responsibly. |
| `not applicable` | The category has no meaningful surface at the chosen scope. |

A category qualifies as `screened` only when all of these hold:

1. At least one concrete anchor exists.
2. The sentinel is answered in one sentence tied to that anchor.
3. The answer does not rely on guessing.

Promote `screened` to `deep` when the category is primary or secondary for the archetype, the sentinel surfaced a concern, or it connects to a finding from another category.

### Evidence bars by input type

**Design doc**

- Read the full document first.
- Treat sections, diagrams, tables, and named decisions as anchors.
- Require 1 anchored sentinel answer for `screened`.

**Codebase**

- Build a bounded architecture sample with at most 12 anchors total:
  - 2 entrypoints
  - 2 orchestration or control-flow anchors
  - 2 data or state anchors
  - 2 boundary anchors such as API, queue, or adapter
  - 2 config, deploy, or observability anchors
  - 2 test or validation anchors
- Require 1 primary and 1 corroborating anchor for `screened`.
- If the codebase is too large, ask to narrow scope or mark more categories `insufficient evidence`.

**Verbal description**

- Use only explicit user statements as anchors.
- Require a direct quoted claim or clearly stated mechanism for `screened`.
- If the signal is only implied, mark `insufficient evidence`.

After screening, record one line per category with: status, sentinel used, anchor, and one-line disposition.

### Global evidence floor

If 4 or more categories would be `insufficient evidence`, state this explicitly after screening and ask whether to continue at reduced depth or narrow scope before producing findings.

If the user does not respond, continue with a partial review limited to categories that cleared screening. Label the review `reduced-depth` in the snapshot and cap findings at 4.

### Deep lens selection

After screening, select 6-10 individual lenses for the deep dive. For narrow interface scope or sparse verbal input, 4-6 is acceptable if you state why fewer lenses were genuinely relevant.

Select lenses in this order:

1. Archetype weighting from the bundled reference
2. Screening promotion where sentinel answers surfaced a real concern
3. Cross-category links where one concern explains another

If no archetype fits cleanly, skip step 1 and rely on evidence-promoted lenses only.

## 3. Deep dive

Analyze only the selected deep lenses. Produce findings and optional tensions, then assemble the review.

### Output structure

Use 5 parts. Every section must earn its place. If a section has nothing meaningful, say so instead of padding it.

**1. Review Snapshot**

Use a compact table:

```md
| Signal | Count |
| ------ | ----- |
| High-priority findings | N |
| Total findings | N |
| Tensions identified | N |
| Categories screened only | N |
| Insufficient evidence | N |
```

**2. Focus and Coverage**

State:

- scope level
- input type
- archetype or archetypes plus confidence
- stakes tier
- named deep lenses
- one-line status per category with status, sentinel, anchor, and disposition

**3. Findings**

Use labels `F1`, `F2`, and so on. Each finding must include:

- `Lens`
- `Decision state`
- `Anchor`
- `Problem`
- `Impact`
- `Recommendation or question`

**4. Tension Map**

Use labels `T1`, `T2`, and so on only when a real tension exists. Each tension must include:

- `Tension`
- `What is being traded`
- `Why it hid`
- `Likely failure story`
- `Linked findings`

**5. Questions / Next Probes**

End with 2-4 sharp questions. Do not end with a verdict unless the user explicitly asked for one.

### Decision state taxonomy

| State | When to use |
| ----- | ----------- |
| `explicit tradeoff` | The design names both sides and makes a conscious choice. |
| `explicit decision` | A conscious choice is visible, but not framed as a tradeoff. |
| `default likely inherited` | No local rationale is visible and the choice matches a framework default or legacy pattern. |
| `underspecified` | The system must decide something here, but the choice is not defined. |
| `not enough evidence` | The input is too sparse to classify safely. |

Use `default likely inherited` only with positive evidence of a default. Lack of rationale alone is not enough. For codebase reviews, stay conservative: code shows what exists, not why.

### Tension inclusion rules

Tensions are optional. `0` is a valid count. Do not force one.

Include a tension only when all of these hold:

1. Both sides have concrete anchors in the input.
2. You can explain the tradeoff mechanism.
3. You can explain why the tradeoff was easy to miss.
4. The tension explains at least 1 concrete finding.
5. The wording is specific to this system, not generic architecture prose.

Before emitting a tension, verify all 6 lines:

1. Side A anchor
2. Side B anchor
3. The decision or default that pulled toward side A
4. The cost or blind spot that appeared on side B
5. Why a reviewer could miss this
6. Which finding or findings this tension explains

Use the bundled tensions table as a prompt source, not a required menu. Custom tensions are valid.

### Depth calibration

| Stakes | Finding target | Hard cap | Tension cap | Overflow handling |
| ------ | -------------- | -------- | ----------- | ----------------- |
| `low` | 3-5 | 6 | 0-1 | Drop minor items. |
| `medium` | 5-8 | 9 | 0-2 | Move lower-signal items to a deferred section. |
| `high` | 8-12 | 12, or 15 with appendix | 1-3 | Cluster by root cause and move overflow to an appendix. |

If you have more than 12 findings in the main reply, either cluster them by root cause or produce a saved artifact. Overflow findings, up to 15 total, go in a **Deferred Findings** appendix as one-line items with lens and decision state only.

### No-findings path

If no material findings surface, say so directly. A clean review at the current depth is a valid outcome.

## Delivery model

Use staged checkpoints. The user can redirect between stages.

| Checkpoint | Content | When to pause |
| ---------- | ------- | ------------- |
| `C0: Framing` | Scope, archetype, stakes, planned deep lenses | Pause only for high stakes with scope or archetype uncertainty. |
| `C1: First findings` | Snapshot, coverage, top 2-4 findings | For high stakes, invite reaction here before continuing. |
| `C2: Full review` | Remaining findings, tension map, questions | Do not pause unless the user redirects. |

Delivery defaults:

- `low` stakes: collapse into one message
- `medium` stakes: use one message unless scope or archetype is ambiguous, then invite correction at `C0`
- `high` stakes: invite reaction at `C0` if framing is uncertain, otherwise at `C1`

If the user does not respond, continue. Checkpoints are invitations, not gates.

## Anti-patterns

| Pattern | Problem | Fix |
| ------- | ------- | --- |
| Marking a category `screened` without a concrete anchor | It creates false coverage and hides evidence gaps. | If the anchor is vague, use `insufficient evidence`. |
| Copying a generic tension from a table | It sounds architecture-literate but explains nothing about this system. | Emit tensions only when all inclusion rules pass. |
| Claiming `default likely inherited` without evidence of a default | It overstates diagnosis when the evidence only shows missing rationale. | Use `not enough evidence` when unsure. |
| Walking all 40-plus lenses narratively | It buries signal in noise and exhausts the reader. | Screen broadly, then deep-dive selectively. |
| Ending with a verdict instead of questions | It closes the conversation too early. | End with questions that move the user's thinking forward. |
| Silently expanding into out-of-scope work | It blurs the skill boundary and makes every answer shallower. | State the handoff explicitly. |

## Example

**User:** "Review the architecture of our notification service. It handles email, SMS, and push via a single queue."

> **Review Snapshot**
>
> | Signal | Count |
> | ------ | ----- |
> | High-priority findings | 2 |
> | Total findings | 5 |
> | Tensions identified | 1 |
> | Categories screened only | 3 |
> | Insufficient evidence | 1 |
>
> **F1. Single queue for heterogeneous delivery channels**
>
> - Lens: Failure Containment
> - Decision state: `default likely inherited`
> - Anchor: Queue configuration in `notification-service/config.yaml`
> - Problem: SMS gateway timeouts block email delivery, so failure in one channel propagates to all channels.
> - Impact: A slow SMS provider degrades every notification type.
> - Recommendation: Evaluate per-channel queues or priority lanes.
>
> **T1. Simplicity vs. failure containment**
>
> - What is being traded: Single-queue simplicity vs. per-channel isolation
> - Why it hid: The system started with email only. SMS and push were added later without revisiting the original queue decision.
> - Likely failure story: An SMS provider has a 30-second timeout spike, the queue backs up, and users miss time-sensitive email.
> - Linked findings: F1, F3
>
> **Questions**
>
> 1. Was the single-queue design revisited when SMS was added, or was the email-era default simply carried forward?
> 2. What is the SLO for email delivery latency, and does the current design meet it during SMS degradation?

## Durable record

- If the user asks to save the review, or the workspace already uses `docs/audits/`, write `docs/audits/YYYY-MM-DD-<target-slug>.md`.
- Otherwise, keep the review in the reply.

## Reference

Read [`references/system-design-dimensions.md`](references/system-design-dimensions.md) when you need:

- the full list of named lenses within a category
- the weighting table for archetype-driven deep-lens selection
- the cross-cutting tensions table as a prompt source
- details on a specific lens the user names

Do not read the reference during screening. Sentinel questions are sufficient for that stage.
