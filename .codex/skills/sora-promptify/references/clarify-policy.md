# Clarify Policy

Goal: keep the flow interactive, warm, and collaborative — without silently assuming key creative decisions.

Default to an interactive, multi-round `CLARIFY` flow. Ask a small, high-impact
set of questions, apply the answers, then either ask the next set or produce
`FINAL` once the concept is coherent enough to shoot.

Tone intent:
- Sound like a creative partner ideating with the user.
- Keep each round light: a short reflection + one decision.
- Avoid “form energy”: do not dump many fields or enumerate every possible setting detail.

## UX Track: Story / Character-First (Selected)
When the user preference is “story/character-driven”, bias CLARIFY questions and
wording toward:
- character intent and emotional turn
- stakes (even small ones) and social dynamics
- comedic/tension timing
- a clean ending beat / button

De-emphasize:
- lens jargon, DOF jargon, stabilization jargon (unless user asked)
- “settings panel” recaps

Hard constraint: still ensure the scene is filmable and coherent (no silent
assumptions that would change the story).

### Deterministic Activation (Signals)
Treat the user as requesting story/character-first UX if they include any of:
- `CHARACTER_FIRST: yes`
- “character-first”
- “focus on story”
- “less camera talk”
- “collaborative ideation” / “ideating session” (when they explicitly contrast it with technical settings)

### Writers' Room Micro-Pitches (Hard Requirement)
In story/character-first UX, each CLARIFY round must include exactly two
micro-pitches immediately before the multiple-choice options:

- `Take A:` 1–2 sentences (max 240 characters)
- `Take B:` 1–2 sentences (max 240 characters)

Rules:
- Takes must differ by a story variable (tone, intent, social dynamic, timing,
  ending button). They must not differ primarily by camera tech.
- Each take must reference at least one concrete detail from the user’s raw text.
- If dialogue is present/central, each take should imply a different delivery
  style or comedic/tension button.
- Do not introduce new major characters, brands, or copyrighted references.

Then ask one question of the form:
- “Which take is closer?” with A/B + `Other: …`

## Canonical Questions (Ordered)
Q1 Physics mode:
- A) Grounded-real (plausible distances/forces) [default]
- B) Heightened (bigger-than-life, still phone footage)
- C) Mixed (mostly grounded with one exaggerated moment)

Q2 Shot plan:
- A) Single continuous shot [default]
- B) 2–3 simple cuts (wide → medium → close)
- C) Storyboard-like beats (explicit time jumps)

Q3 Dialogue policy:
- A) Implied (no intelligible lines; performance energy only) [default]
- B) None (no speech; only ambience + reactions)
- C) Preserve (≤2 short speaker-labeled lines total)

Q4 Style preset:
- A) Smartphone-real [default]
- B) Doc 16mm (documentary texture)
- C) Cinematic 35mm (controlled, polished)
- D) Animation/stylized

Q5 Intensity:
- A) Low (subtle)
- B) Medium [default]
- C) High (chaotic escalation, still coherent)

Q6 Coherence mode:
- A) Reality-first (physical plausibility and phone-footage constraints)
- B) Storyboard-first (coverage clarity; more explicit beats)
- C) Hybrid (realistic phone footage + clear causal beats) [default]

## Deterministic Mode Choice (Multi-Round)

Choose `FINAL` only if either:
- The user explicitly asks for no questions / “just write the prompt” / “FINAL”.
- OR the user has explicitly confirmed “Proceed to FINAL” in the immediately
  prior CLARIFY round.

Otherwise: choose `CLARIFY` for the next round (including when you believe you
have enough information; in that case, the next CLARIFY round should be the
confirmation question).

## Deterministic Ask Policy (Adaptive Packs)
Ask **one** multiple-choice question per CLARIFY round by default (maximum
adaptability and less “form-like”).

If the user explicitly asks to bundle questions (e.g. “ask me everything at once”),
you may ask up to 5 in one message.

Pick questions using `references/question-bank.md`:
- Prefer questions that change the shot plan, camera, dialogue, style, pacing, or
  physics (high leverage).
- Ask fewer, better questions instead of forcing the user through a rigid form.
- Only ask questions that are still unanswered in the conversation.
- Prefer questions with an explicit “Other: …” escape hatch so the user is never
  forced into your menu.

### Story / Character-First Deterministic Gates (Less Scripted, Still Reliable)
In story/character-first UX, avoid rigid question scripts. Instead, use
deterministic gates: ask a question only when ambiguity/risk is present, and
skip it when the user has already made it clear.

Hard priority: if any guardrails are missing (privacy/faces, readable text/logos,
safety/content boundaries), ask a guardrail gate first.
- Use the narrative templates in `references/question-bank.md` under:
  - `Character-First Guardrail Phrasing (Templates)`

Then, for the remaining questions, evaluate gates in this order and ask the
first gate that is triggered:

Gate 1 — Consent to invent:
- Trigger if the raw text is evocative but underspecified (you would otherwise
  need to invent 2+ story specifics: who exactly, what exactly happens next, or
  what the button ending is).
- Ask: `Consent to invent`

Gate 2 — Tone / genre mix:
- Trigger if tone is not explicit or could plausibly read two ways (funny vs
  tense vs earnest).
- Ask: `Tone / genre mix`

Gate 3 — Audience POV:
- Trigger if the premise contains social judgment/cringe potential or a moral
  stance (complaining, public ranting, awkward confession, petty escalation,
  confrontation), and the viewer alignment is not explicit.
- Ask: `Audience POV`

Gate 4 — Primary subject of attention:
- Trigger if it’s unclear whether the clip should live on performance, hands,
  the place, or crowd reactions.
- Ask: `Primary subject of attention`

Gate 5 — Self-awareness / performance for camera:
- Trigger if it’s unclear whether the character is aware they’re being filmed,
  or if that awareness changes the comedy/drama.
- Ask: `Self-awareness / performance for camera`

Gate 6 — Ending beat:
- Trigger if the ending/button is not implied, or if the premise needs a clear
  “landing” to feel authored.
- Ask: `Ending beat`

Gate 7 — Dialogue intent:
- Trigger if speech is central and it’s unclear whether we should avoid clear
  words, go silent, or preserve 1–2 lines; or if it’s unclear what the speech is
  about.
- Ask: `Dialogue policy` and/or `What is the preserved dialogue about`

Gate 8 — Shot plan (pacing tool, not tech):
- Trigger if timing depends on structure (awkward build vs punchy cut timing),
  and the user hasn’t implied one-take vs cuts.
- Ask: `Shot plan` phrased as pacing/timing

Gate 9 — Look (supporting vibe):
- Trigger if the desired vibe could be phone-viral vs doc vs cinematic, and the
  user hasn’t implied a look.
- Ask: `Style preset` phrased as vibe/texture

Tie-break (deterministic):
- If multiple gates are triggered equally, prefer asking `Tone / genre mix`
  unless the “Consent to invent” gate is triggered (in that case ask consent first).

## Option Presentation Policy (Two Directions by Default)
To avoid the CLARIFY flow feeling like a form, do **not** present the full option
menu most of the time.

Default pattern:
- Curate the bank into **two scene-appropriate directions** (A/B) that feel meaningfully different.
- Add `Other: …` as an escape hatch (C).

Only present 4–5 options when:
- The user explicitly asks for the full menu (“give me all the options”), or
- The nuance is the point (e.g., multiple distinct looks the user might realistically want), or
- You are asking a dedicated guardrail question where the “high-risk” option must be clearly offered.

How to curate:
- Pick one “safe/robust” direction and one “spicier/more stylized” direction.
- If the bank has a recommended choice, prefer including it as one of the two.
- If the user’s raw text strongly implies an option, include that option and make it the default.
- Avoid including niche options unless the scene calls for them (e.g., don’t offer “storyboard time jumps” unless the idea needs it).

Stop asking and produce `FINAL` when:
- The “core controls” are set (style, shot plan, intensity/pacing, dialogue policy,
  and physics mode) **or** are clearly irrelevant (e.g. physics mode for a static,
  quiet typing scene).
- The subject + setting + core action are clear enough to write 3–6 beats without
  inventing major story elements.
- If `dialogue_policy=preserve` and multiple people are visible/active, treat
  dialogue staging/speaker binding as high-risk; ask a speaker-binding question
  before proceeding to FINAL.

Additional readiness constraints (to avoid silent assumptions):
- If `dialogue_policy=preserve`, do not treat the scene as “ready” until you have
  clarified at least:
  - filming perspective (who holds the camera),
  - how it’s filmed (start/end framing; zoom/stability when relevant),
  - main character look (even if generic-by-choice),
  - voice/performance style for delivery,
  - what the dialogue is about (or the exact preserved line(s)),
  - on-screen text/logos policy for screen/signage visibility.

When you would otherwise produce `FINAL`, ask the confirmation question
(`Proceed to FINAL?`) from `references/question-bank.md` instead, unless the user
explicitly requested `FINAL / no questions`.

If the user provides `SORA_OPTIONS`, treat them as strong signals but still
confirm any option that materially changes the result (e.g. `shot_policy`,
`style_preset`, `dialogue_policy`, `physics_mode`, `intensity`).

## Conversational UX (Hard Guidance)
Within `CLARIFYING_QUESTIONS`, structure each round like:
1) `Locked so far:` and `Still open:` (brief; follow canonical keying).
2) A 1–2 sentence “creative reflection” (what you’re picturing; what’s strong).
3) One multiple-choice question (unless bundling was requested).
4) Close with `Answers:` and `Reply like:` lines (see below).

### One Good Note (Hard Requirement)
In `CLARIFY`, include exactly one optional “note” line before the question. This
should feel like a director/actor note from a creative partner.

Format (exact label):
- `One good note:` <one sentence>

Constraints:
- Must be one sentence (no semicolons; no lists).
- Must be actionable and small (timing, performance, intention, social dynamic,
  or ending button).
- Must not introduce new requirements, new characters, or new locations.
- Must not mention technical camera settings unless the user explicitly asked
  for technical guidance.

Examples:
- `One good note: Let the laugh catch them off-guard before they try again, so it feels like a real private moment.`
- `One good note: Keep the pettiness escalating in tiny steps so the riders’ reactions can build into the button.`

### Reflection Checklist (Hard)
The creative reflection must include all of the following, in 1–2 sentences:
- 1 concrete detail from the user’s raw text (a setting, prop, action, or line)
- 1 character/relationship inference framed as a suggestion (use “feels like” /
  “we could” / “I’m seeing”)
- 1 timing/stakes note (what escalates, what turns, or what lands at the end)

Avoid in story/character-first mode:
- lens/DOF terms unless user asked
- “schema”/“policy”/“mode”/“SORA_OPTIONS” meta-talk

### Reply Friction Rules (Hard)
To keep replies effortless (especially on mobile), the end of every CLARIFY round
must include:
- An `Answers:` hint line.
- A concrete `Reply like:` example.

Formatting:
- If 1 question was asked:
  - End with `Answers: A` (or `Answers: A/B/C`) and then `Reply like: A`
- If multiple questions were bundled:
  - End with `Answers: 1B 2A 3C ...` and then `Reply like: 1B 2A`

Acceptable user replies:
- Just the letter(s) (preferred), e.g. `A` or `1B 2A`
- The full option text (still accept, but normalize to letter internally)

## Delivery Script (Use This For Any Question)
Goal: make each question feel like a collaborative creative beat — not a bank lookup.

Use this 2–3 sentence pattern immediately before the multiple-choice options:
1) **Reflect:** “Here’s what I’m picturing so far…” + one vivid, concrete image tied to the user’s intent.
2) **Offer two directions:** “We can go either (A) ___ or (B) ___” (name the *creative difference*, not the schema field).
3) **Ask + nudge:** “Which direction should we lock in?” Optionally add a gentle recommendation in one clause (“I’d lean A if you want ___.”).

Keep it tight:
- 2–3 sentences total (max ~300 characters) before the option list.
- No meta-talk (“from my question bank…”, “select an option…”, “SORA_OPTIONS…”).
- Make it feel like you’re co-directing: talk in camera/scene language.

Examples (swap in the current question’s topic):
- “I’m seeing this as a candid phone moment that escalates fast, with one clean camera idea we can execute. We can either keep it as a single one-take that feels real, or do a couple simple cuts for punchier emphasis. Which way should we lock it in? (I’d lean one-take for authenticity.)”
- “This already has a strong vibe — I just want to tune the ‘chaos dial’ so it stays readable. We can keep it clean and safe, or allow one tiny harmless mishap for comedy. What feels right?”

## Locked State Canonical Keys (CLARIFY)
In `Locked so far:`, use stable human-readable keys so users can refer back to
them conversationally (“keep everything, switch Look to doc texture”).

Canonical keys (omit unknowns; keep order when present):
1) `Format:`
2) `Look:`
3) `Edit feel:`
4) `Chaos dial:`
5) `Dialogue:`
6) `Physics:` (only when relevant)
7) `Safety / privacy / text:`

Value vocabulary (use these phrases):
- Look: `phone-footage`, `doc texture`, `cinematic polish`, `stylized/animated`, `other`
- Edit feel: `one-take`, `a few clean cuts`, `storyboard beats`, `other`
- Chaos dial: `low`, `medium`, `high`, `other`
- Dialogue: `implied`, `none`, `preserve 1–2 short lines`, `other`
- Safety / privacy / text: `safe default`, `controlled risk`, `user-specified`

Do not include internal identifiers (e.g. `smartphone_real`) in this recap.

## Curation Recipes (How to Collapse Menus Into Two Directions)
Use these when a question bank entry has 4–5 options, but you want to present a simple A/B + `Other` experience.

### Recipe 1: Shot plan → “real” vs “edited”
Source pool: `Shot plan (almost always)`.

Default presentation (most scenes):
- A) One-take (single continuous shot; feels real). [default]
- B) A couple clean cuts (wide → medium → close; simple coverage).
- C) Other: (describe your shot structure)
Recommended: A — One-takes feel authentic and are easiest to keep coherent.

When to include “storyboard beats” explicitly:
- Only if the user’s concept clearly implies time jumps, cutaways, flashbacks, montage, or “beat-by-beat” structure.
- In that case, either:
  - swap B to “Storyboard beats”, or
  - keep A/B and set `Other` suggestion text to mention storyboard as an example.

### Recipe 2: Style preset → “phone-real” vs “intentional look”
Source pool: `Style preset (almost always)`.

Default presentation (most scenes):
- A) Phone footage (handheld, imperfect, real). [default]
- B) Doc 16mm (observational texture; subtle grain; practical light).
- C) Other: (describe the look/texture)
Recommended: A — It forgives imperfections; artifacts read like “camera chaos.”

When the user asks for polish:
- If they explicitly want “cinematic / polished / composed”, swap B to:
  - B) Cinematic 35mm (polished, composed, intentional movement).

When the concept is not live-action:
- If the user wants “animated / stylized / illustration”, swap B to:
  - B) Stylized / animated (art direction forward; less realism).

### Recipe 3: Guardrails → “safe default” vs “intentional high-risk”
Sources: `On-screen text / logo policy`, `Screen/UI depiction`, `Faces / privacy policy`, `Boundaries`.

Default presentation pattern:
- A) Safe/robust (default; avoids common failure modes). [default]
- B) Intentional high-risk (only if it’s the point; user supplies specifics). (High risk)
- C) Other: (describe constraints)
Recommended: A — Robust defaults keep iterations fast.

Concrete examples:
- On-screen text/logos:
  - A) No readable text/logos (screens + signage blurred/unreadable). [default]
  - B) Readable text matters (I’ll specify exact text). (High risk)
  - C) Other: (describe text/logo requirements)
- Faces/privacy:
  - A) Privacy-safe (avoid identifiable faces: backs of heads / out of focus). [default]
  - B) Faces are fine (normal crowd visibility).
  - C) Other: (describe privacy constraints)

Do:
- Keep options phrased as creative directions (“messy phone clip” vs “polished cinematic coverage”).
- Offer 1–2 gently opinionated suggestions when it helps (“I’d lean A for this vibe…”), but keep the user in control.
- If the user’s raw text already implies an answer, include it as the default and say why in one short clause.

Avoid:
- Listing internal variable names or explaining the entire schema.
- Asking low-leverage specifics (wardrobe, props, exact lens) before the big creative decisions are set.
- Cold/robotic phrasing like “Select one” or “Provide input”.

## CLARIFY Output Rules
- Ask 1 question by default (up to 5 only if user requests bundling).
- Use multiple-choice format for every question.
- If bundling: ask all questions in one message and keep a stable, readable order
  (core controls first, then anchors, then optional refinements).
- Start each CLARIFY round by recapping the current state **inside**
  `CLARIFYING_QUESTIONS`:
  - `Locked so far:` bullet list (only items that have been explicitly provided
    or chosen in earlier answers; use the canonical keys).
  - `Still open:` bullet list (the next 1–5 important unknowns framed as upcoming
    creative decisions).
- Include reply hint exactly as: `Answers: 1B 2A 3C ...`
- Immediately after `Answers:`, include: `Reply like: 1B 2A`
- Output only `CLARIFYING_QUESTIONS` section in CLARIFY mode.
