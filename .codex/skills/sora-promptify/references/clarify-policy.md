# Clarify Policy

Goal: keep the flow interactive, warm, and collaborative — without silently assuming key creative decisions.

Default to an interactive, multi-round `CLARIFY` flow. Ask a small, high-impact
set of questions, apply the answers, then either ask the next set or produce
`FINAL` once the concept is coherent enough to shoot.

Tone intent:
- Sound like a creative partner ideating with the user.
- Keep each round light: a short reflection + one decision.
- Avoid “form energy”: do not dump many fields or enumerate every possible setting detail.

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
1) `What we’ve decided:` and `Next creative pick(s):` (brief).
2) A 1–2 sentence “creative reflection” (what you’re picturing; what’s strong).
3) One multiple-choice question (unless bundling was requested).

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
  - `What we’ve decided:` bullet list (only items that have been explicitly provided
    or chosen in earlier answers).
  - `Next creative pick(s):` bullet list (the next 2–5 important unknowns framed
    as upcoming creative decisions).
- Include reply hint exactly as: `Answers: 1B 2A 3C ...`
- Output only `CLARIFYING_QUESTIONS` section in CLARIFY mode.
