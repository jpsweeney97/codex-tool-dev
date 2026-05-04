# Synthesis Guide

**YOU MUST read and follow this guide before filling any handoff section.**

## The Mindset Shift

You are not filling out a form. You are answering one question:

> "What would future-me need to continue this work without re-exploration?"

Every piece of information you capture must pass this test. If future Codex wouldn't need it to continue, don't include it. If future Codex would be stuck without it, it's mandatory.

**Form-filling produces:** "Used JWT for authentication"

**Future-me thinking produces:** "Chose JWT over sessions because user stated multi-region requirement (quote: 'needs to work across US and EU without shared state'). Sessions would require Redis replication — rejected as too complex for v1. Implication: refresh tokens need their own revocation strategy since we can't invalidate server-side."

The difference is not length. It's whether future Codex can continue the work or has to rediscover everything.

**Default to inclusion.** When unsure whether something belongs, include it. The cost of a slightly longer handoff is zero. The cost of a missing piece of context is an entire re-exploration cycle.

---

## Evidence Requirements

**Every claim requires evidence. No exceptions.**

| Claim source | Required evidence |
|--------------|-------------------|
| Codebase | File:line reference (e.g., `middleware.py:45`) |
| Conversation | Direct quote from user or discussion |
| External | URL, doc reference, or command output |

**Examples:**

❌ **Without evidence:** "The auth module uses a decorator pattern"

✅ **With evidence:** "Auth uses decorator pattern — see `@require_auth` at `middleware.py:45`"

---

❌ **Without evidence:** "We decided to prioritize speed over completeness"

✅ **With evidence:** "User stated: 'I'd rather ship something basic this week than perfect next month' — prioritizing speed"

---

❌ **Without evidence:** "Redis wasn't an option"

✅ **With evidence:** "Redis rejected — user said: 'We don't have Redis in prod and can't add infrastructure right now'"

---

**If you cannot provide evidence for a claim, mark it explicitly:**

> ⚠️ Unverified assumption: [claim] — could not locate evidence in conversation or codebase

---

## Synthesis Prompts

**Answer every applicable prompt below.** These are not optional. Skip only if genuinely not applicable to this session (e.g., no debugging occurred → skip Debugging State).

### Session Narrative

**Always include.** Even "pure execution" sessions have a story — what was the plan, what went smoothly, what required adaptation. The narrative is the single most valuable section for future Codex to understand the session arc.

1. **What was the starting state?**
   What knowledge, assumptions, and goals did the session begin with?

2. **What was explored and in what order?**
   The investigation path — which files, which components, which approaches, in what sequence.

3. **Where did pivots happen? What triggered each pivot?**
   What caused a change in direction? A user statement? A discovery in the code? A failed test?

4. **What were the key moments where understanding shifted?**
   When did something click? When did an assumption get overturned? When did the problem reframe?

5. **What was set aside for later and why?**
   What was intentionally deferred? What prompted the deferral?

**Depth target:** 60-100 lines in the final handoff. Render as a chronological narrative with sequence markers. Include quotes from key exchanges that shaped direction. Capture not just what happened but *why* — what prompted each exploration, what hypothesis was being tested, what the expected outcome was vs. what actually happened. A session narrative that reads as a bare list of actions ("read file X, then file Y, then wrote file Z") is incomplete — it must convey the reasoning thread that connected those actions.

Maps to: **Session Narrative** section in handoff.

---

### Decisions

For each significant decision made this session, answer ALL of these:

1. **What was decided?**
   State the choice clearly.

2. **What drove it?**
   Quote the user requirement, constraint, or context that made this the right choice.

3. **What alternatives were considered?**
   List at least one rejected alternative.

4. **Why were alternatives rejected?**
   Specific reason for each, with evidence.

5. **What are the implications?**
   What does this decision mean for future work? What's now easier or harder?

6. **What trade-offs were explicitly accepted?**
   What gets worse because of this choice? What was sacrificed and why?

7. **What's your confidence level and what's it based on?**
   Use evidence levels: E0 (assertion only), E1 (single source), E2 (two independent methods), E3 (triangulated + disconfirmation). Confidence cannot exceed evidence.

8. **What would change this decision?**
   What new information would make you reconsider? Under what conditions does this choice become wrong?

**Template:**

> **Decision:** [what was chosen]
> - **Driver:** [quote or evidence for why]
> - **Rejected:** [alternative] — [why rejected, with evidence]
> - **Implication:** [what this means going forward]
> - **Trade-offs:** [what gets worse because of this choice]
> - **Confidence:** [High/Medium/Low] ([E0-E3]) — [basis]
> - **Reversibility:** [High/Medium/Low] — [what's needed to change course]
> - **Change trigger:** [what would make you reconsider]

**Depth target:** 20-30 lines per decision in the final handoff. A decision entry without all 8 elements (choice, driver, alternatives, rejection reasons, trade-offs, confidence, reversibility, change triggers) is incomplete. Every decision should be defensible to a skeptical reader — if someone asks "but why not X?", the answer should already be in the entry.

**If no significant decisions were made this session, state:** "No significant decisions — session was [execution/exploration/debugging] only."

---

### In-Progress State

If work was ongoing when the session ended, answer ALL of these:

1. **What was actively being worked on?**
   Not "next steps" — what were you in the middle of?

2. **What approach was being used?**
   Not just "implementing X" — how? What pattern, strategy, or method?

3. **What state are things in?**
   Working? Broken? Partially complete? Be specific.

4. **What's working so far?**
   What parts are done and verified?

5. **What's not working or incomplete?**
   What's broken, missing, or uncertain?

6. **What open questions were in flight?**
   What were you unsure about? What were you about to figure out?

7. **What was the immediate next action?**
   Not the full roadmap — what were you literally about to do next?

**Template:**

> **In Progress:** [what was being worked on]
> - **Approach:** [how — pattern, strategy, method]
> - **State:** [working / broken / partial] — [specifics]
> - **Working:** [what's done]
> - **Not working:** [what's broken or incomplete]
> - **Open question:** [what was uncertain]
> - **Next action:** [immediate next step]

**Depth target:** 15-25 lines in the final handoff. An in-progress entry without the specific approach being used, current state with evidence, and immediate next action is incomplete. Future-Codex should be able to pick up exactly where you left off without any investigation.

**If work reached a clean stopping point, state:** "Clean stopping point — [what was completed], no work in flight."

---

### Codebase Learnings

For anything learned about how this codebase works that's relevant to continuing the task, answer:

1. **Patterns discovered**
   How does the codebase do things? Include file:line references.

2. **Conventions identified**
   Naming, structure, error handling, response formats — with examples.

3. **Gotchas encountered**
   What was surprising, non-obvious, or contrary to expectation?

4. **Connections mapped**
   How do components relate? What calls what? Where does data flow?

5. **Locations identified**
   Where do specific things live? Key files for the task at hand.

**Template:**

> **Patterns:**
> - [pattern description] — see `file.py:line`
>
> **Conventions:**
> - [convention] — example: `code snippet or reference`
>
> **Gotchas:**
> - [what was surprising] — discovered when [context]
>
> **Connections:**
> - [component A] → [component B] via [mechanism]
>
> **Key locations:**
> - [concept/function]: `path/to/file.py:line`

**Depth target:** 30-50 lines in the final handoff. A codebase learnings entry without file:line references for every pattern claim and concrete examples for conventions is incomplete. Every assertion about how the codebase works must be backed by a specific location.

**If no new codebase knowledge was gained, state:** "No new codebase learnings — session used existing knowledge only."

---

### Codebase Knowledge

**Always include.** Every session reads files and builds understanding. This section is a knowledge dump — everything the session learned about the codebase that would save future Codex from re-reading files.

1. **What files were read during this session? Why each one? What was found?**
   Not just a list — what prompted reading each file and what understanding it provided.

2. **What patterns were identified?**
   With file:line references and concrete examples showing the pattern in use.

3. **What architecture was mapped?**
   Component relationships, data flows, dependency chains. Render as tables or diagrams.

4. **What conventions were observed?**
   Naming, structure, error handling, testing patterns — with examples from the code.

5. **What was surprising or counter-intuitive? Why?**
   What violated expectations? What would mislead future Codex if not documented?

6. **What key locations should future Codex know about?**
   Entry points, configuration, hot paths, test fixtures, shared utilities.

7. **What does the dependency graph look like for the area of code touched?**
   What depends on what? What breaks if you change X?

8. **What related files exist that weren't modified but are relevant?**
   Files that inform how the modified files should behave.

**Depth target:** 60-100 lines in the final handoff. Use tables for architecture and relationships. Include file:line references for every pattern claim. A codebase knowledge section that merely lists files without patterns, architecture, and key locations is incomplete. The test: would future Codex need to re-read any file that was read this session? If yes, that file's content and patterns should be captured here.

Maps to: **Codebase Knowledge** section in handoff.

---

### Mental Model

How are you thinking about this problem? This is not what you did — it's the framing that makes everything else make sense.

1. **What kind of problem is this?**
   How did you categorize or frame it? (e.g., "This is a state machine problem", "This is really about data flow", "This is a permissions issue masquerading as a UI bug")

2. **What's the core insight?**
   What realization or understanding unlocked progress?

3. **What mental model are you using?**
   What abstraction, analogy, or framework helped you reason about this?

**Template:**

> **Framing:** [how the problem is being thought about]
> - **Core insight:** [the key realization]
> - **Mental model:** [abstraction/analogy being used]

**Example:**

> **Framing:** This is a cache invalidation problem, not a performance problem
> - **Core insight:** The slowness comes from stale data causing extra queries, not from query efficiency
> - **Mental model:** Thinking of the system as having "data freshness tiers" — some data can be stale, some must be real-time

**Depth target:** 10-20 lines in the final handoff. A mental model entry without the core insight or a framing analogy that future Codex can use to orient is incomplete. The framing should be transferable — future Codex should be able to adopt the same lens.

**If no particular framing emerged, state:** "No specific mental model — straightforward implementation of [what]."

---

### The Why

Why are we doing this task? Not what we're building — why it matters.

1. **What's the bigger picture?**
   What goal does this task serve? What happens if this isn't done?

2. **What's the context that future Codex won't see?**
   Deadlines, stakeholders, dependencies, business reasons — anything not in the code.

3. **Why now?**
   What made this the priority? What triggered this work?

**Template:**

> **Bigger picture:** [why this task matters]
> - **Context:** [deadlines, stakeholders, dependencies]
> - **Trigger:** [what made this a priority now]

**Example:**

> **Bigger picture:** API going public next month; auth is a compliance requirement for external access
> - **Context:** Compliance deadline is March 15. Security team must sign off before launch.
> - **Trigger:** User said: "We got the external API requirement confirmed yesterday, need to move on this now"

**Depth target:** 10-15 lines in the final handoff. A why entry without the bigger picture, relevant context, or the trigger that made this work a priority is incomplete. Future-Codex needs to understand not just what to build but why it matters to calibrate effort and trade-offs.

**If the why is self-evident from the task, state:** "Why is implicit — [brief statement, e.g., 'bug fix for production issue']."

---

### Failed Attempts

What was tried that didn't work? This prevents future Codex from repeating dead ends.

For each failed attempt:

1. **What was tried?**
   The approach, not just "tried X."

2. **Why did it fail?**
   Specific reason — error message, logical flaw, constraint violation.

3. **What was learned?**
   What does this failure teach about the problem?

**Template:**

> **Tried:** [approach attempted]
> - **Failed because:** [specific reason with evidence]
> - **Learned:** [insight gained from failure]

**Example:**

> **Tried:** Using in-memory rate limiting with a simple dict
> - **Failed because:** Doesn't work across multiple server instances — each instance has its own counter, so limits aren't enforced globally
> - **Learned:** Any rate limiting solution needs shared state; must use Redis or similar

**Depth target:** 10-20 lines per failed attempt in the final handoff. A failed attempt entry without the specific failure reason (with evidence) and what it taught about the problem is incomplete. Include why the approach seemed promising initially — this helps future Codex understand the reasoning that led to the dead end and why it won't work.

**If nothing was tried and failed, state:** "No failed attempts — [first approach worked / session was exploration only]."

---

### Debugging State

**Only applicable if session involved debugging or investigation.**

If you were debugging or investigating an issue, capture the investigation state:

1. **What's the symptom?**
   Observable behavior — what's wrong?

2. **What's the hypothesis?**
   What do you think is causing it?

3. **What's been ruled out?**
   Hypotheses tested and eliminated, with evidence.

4. **What's been narrowed to?**
   Where in the codebase/system does the problem live?

5. **Where was the investigation pointing?**
   What were you about to check or test next?

**Template:**

> **Symptom:** [observable problem]
> - **Hypothesis:** [current best guess]
> - **Ruled out:** [what's been eliminated] — [evidence/test that ruled it out]
> - **Narrowed to:** [subsystem/file/function]
> - **Next check:** [what to investigate next]

**Example:**

> **Symptom:** Tests pass locally but fail in CI with timeout on auth endpoints
> - **Hypothesis:** CI environment missing Redis connection, causing auth to hang waiting for session store
> - **Ruled out:** Network issues — other CI jobs with external calls succeed
> - **Ruled out:** Test flakiness — fails consistently on auth tests only
> - **Narrowed to:** Session initialization in `auth/session.py`
> - **Next check:** Add logging around Redis connection in CI, check if `REDIS_URL` env var is set

**Depth target:** 15-25 lines in the final handoff. A debugging state without the current hypothesis, what's been ruled out with evidence, and the specific next investigation step is incomplete. Future-Codex should not repeat any investigation already performed.

**If no debugging occurred, skip this section entirely.**

---

### User Priorities

What does the user care about that isn't visible in the code?

1. **Stated priorities**
   What did the user explicitly say matters or doesn't matter?

2. **Explicit trade-offs**
   What did the user say to optimize for? What did they say to deprioritize?

3. **Constraints mentioned**
   Time pressure, team dynamics, technical limitations, preferences.

4. **Scope boundaries**
   What did the user explicitly include or exclude?

**Template:**

> **Priorities:**
> - [what matters] — user said: "[quote]"
>
> **Trade-offs:**
> - Optimizing for [X] over [Y] — user said: "[quote]"
>
> **Constraints:**
> - [constraint] — user said: "[quote]"
>
> **Scope:**
> - Include: [what's in scope]
> - Exclude: [what's explicitly out of scope] — user said: "[quote]"

**Example:**

> **Priorities:**
> - Working code over perfect code — user said: "I'd rather have something that works than something elegant"
>
> **Trade-offs:**
> - Speed over edge cases — user said: "Don't worry about the multi-tenant case for now, that's v2"
>
> **Constraints:**
> - No new dependencies — user said: "We're in a dependency freeze until after the release"
>
> **Scope:**
> - Include: Basic auth flow, token refresh
> - Exclude: Admin impersonation — user said: "That's a separate ticket"

**Depth target:** 15-30 lines in the final handoff. A user priorities entry without verbatim quotes is incomplete — paraphrasing loses the nuance that makes preferences actionable. Include every correction and pushback as first-class data (corrections reveal preferences not stated explicitly).

**If no user priorities were stated, state:** "No explicit user priorities captured — task was well-defined, no trade-offs discussed."

---

### Conversation Dynamics

**Include for any session with meaningful dialogue.** The only skip condition is a fully autonomous session with zero user interaction.

1. **What key questions did the user ask?**
   What did their questions reveal about priorities?

2. **What key questions did Codex ask?**
   What did the answers clarify?

3. **What preferences did the user express — verbatim?**
   Working style, code style, communication, tool usage.

4. **Where did disagreement occur? How was it resolved?**
   Who conceded what, and why?

5. **What alignment was reached that isn't captured in decisions?**
   Methodology, pace, scope, working style.

6. **What would you tell future Codex about working with this user based on this session?**
   Communication patterns, decision-making style, what they value and deprioritize.

7. **What communication patterns emerged?**
   Does user prefer options, direct action, collaborative exploration?

8. **What corrections did the user make?**
   These reveal preferences not stated explicitly.

**Depth target:** 30-60 lines in the final handoff. Use verbatim quotes for user preferences — paraphrase loses nuance. Distinguish between explicit statements and inferred preferences. A conversation dynamics section that paraphrases instead of quoting, or that omits corrections and pushback, is incomplete. Corrections are first-class data — they reveal the gap between what was expected and what was delivered.

Maps to: **Conversation Highlights** and **User Preferences** sections in handoff.

**If no meaningful dialogue occurred, state:** "Autonomous session — no user interaction beyond initial request."

---

## Output Mapping

After completing the synthesis prompts above, map your answers to handoff sections. The synthesis prompts generate internal thinking; the handoff sections contain the **full substance** of that thinking — not a summary.

| Synthesis Prompt | Handoff Section | Transfer Guidance |
|------------------|-----------------|-------------------|
| Session Narrative | **Session Narrative** | Transfer the full chronological narrative. Use prose, not bullet points. Preserve sequence markers, quotes, and pivot triggers. Every paragraph of synthesis thinking should appear in the output. |
| Decisions | **Decisions** | Transfer all 8 elements per decision. Use structured format with bold labels. Include verbatim quotes for drivers and rejection evidence. Tables for trade-off matrices when comparing 3+ alternatives. |
| In-Progress State | **In Progress** | Transfer all 7 elements. Use structured format. Be specific about state — "partially complete" is not enough; say what's done and what remains. |
| Codebase Learnings | **Context** and/or **Learnings** | Split by type: patterns and conventions go to **Learnings** (with file:line), mental model goes to **Context**. Use both sections when material warrants it. |
| Codebase Knowledge | **Codebase Knowledge** | Transfer everything. Use tables for architecture and key locations. Use code-style diagrams for dependency graphs. Include every file:line reference. |
| Mental Model | **Context** | Transfer the framing, core insight, and analogy. Prose format. This often works well as an opening or closing paragraph in Context. |
| The Why | **Goal** | Transfer bigger picture, context, and trigger. The Goal section should open with the immediate objective, then expand to stakes, trigger, and project arc. |
| Failed Attempts | **Rejected Approaches** | Transfer full approach description, failure evidence, and lessons. Each rejected approach gets its own subsection with a heading. Include why it seemed promising. |
| Debugging State | **In Progress** or **Blockers** | Use **In Progress** if debugging is ongoing. Use **Blockers** if stuck. Transfer symptom, hypothesis, ruled-out list, and next check. |
| User Priorities | **User Preferences** | Transfer verbatim quotes for every preference. Use bold labels for categories. Include corrections and pushback. |
| Conversation Dynamics | **Conversation Highlights** and **User Preferences** | Key exchanges with quotes go to **Conversation Highlights**. Working style and preferences go to **User Preferences**. Communication patterns and corrections belong in both. |

**Key rule: transfer everything.** The synthesis prompts generate internal thinking; the handoff sections should contain the full substance of that thinking, not a summary. If your synthesis produced 30 lines of decision analysis, the handoff Decision entry should contain those 30 lines of substance — restructured for readability, not condensed for brevity.

**Remember:** Sections are OUTPUT. The synthesis prompts are THINKING. Don't skip the thinking and jump to filling sections.

---

## Completeness Self-Check

Before writing the final handoff, verify against these checks. Every "no" indicates likely undercapture — return to the relevant synthesis prompt.

1. **Line count check:** Is body content at least 300 lines? If not, re-examine the session for undercapture. Simple execution sessions produce 300+; sessions with decisions, exploration, or pivots produce 400-700+.

2. **Decision depth:** Does every decision have all 8 elements (choice, driver, alternatives, rejection reasons, trade-offs, confidence, reversibility, change triggers)? A decision missing any element is incomplete.

3. **Evidence density:** Does every factual claim link to file:line, quote, or output? Claims without evidence are assertions, not knowledge.

4. **Resumption test:** Could future Codex start working without asking "why did we..." or "what about..."? If any likely question isn't answered, add the answer.

5. **Codebase preservation:** Is the architecture understanding rendered in full (tables, relationships, key locations), not just referenced? Future-Codex should not need to re-read files explored this session.

6. **Conversation preservation:** Are user preferences captured with verbatim quotes? Paraphrased preferences lose the nuance that makes them actionable.

7. **Session narrative:** Is the exploration arc told as a story with pivots and triggers? A flat list of actions is not a narrative.

8. **Knowledge preservation:** Would future Codex need to re-read any file that was read this session? If yes, capture that file's content, patterns, and purpose in the Codebase Knowledge section.
