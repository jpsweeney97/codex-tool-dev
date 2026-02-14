---
name: sora-promptify
description: Transform raw scene text into a Sora app–optimized prompt for portrait 15s videos with camera/framing, DOF, causal beats, lighting/palette anchors, explicit audio intent, mitigations, and remix nudges. Use when asked to rewrite/optimize/convert text into Sora-ready prompts or produce variants.
---

# Purpose
Convert raw scene text into a collaborative, Sora-ready output with one of two modes:
- `CLARIFY`: ask multiple-choice questions first
- `FINAL`: generate the complete 4-section output

Collaboration-first intent:
- Treat the user like a creative partner, not a data-entry form.
- Default to `CLARIFY` with *one high-leverage* question per round (unless the user asks to bundle).
- Use short, warm language and reflect the user’s vibe back to them.
- Offer 1–2 concrete creative options (not endless menus), then let the user steer.
- Produce `FINAL` once the concept feels coherent enough to shoot.
- Respect “FINAL / no questions” when explicitly requested.
- If the user asks for a story/character-driven session, prioritize tone, stakes,
  timing, and character intent over technical camera talk.
- Include a “One good note” line in CLARIFY (see `references/clarify-policy.md`).

Default app assumptions:
- Orientation: Portrait (9:16)
- Duration: 15 seconds
- Audio intent: always included

## Inputs
Use `raw_text` plus optional `SORA_OPTIONS`:
- `physics_mode`: `grounded_real` | `heightened` | `mixed`
- `style_preset`: `smartphone_real` | `doc_16mm` | `cinematic_35mm` | `animation`
- `dialogue_policy`: `implied` | `remove` | `preserve`
- `shot_policy`: `single_shot` | `split_into_shots`
- `intensity`: `low` | `medium` | `high`
- `coherence_mode`: `reality_first` | `storyboard_first` | `hybrid`  (controls realism vs coverage emphasis)
- `prompt_density`: `minimal` | `balanced` | `max` (controls verbosity and structural detail)
- `speaker_binding`: `normal` | `strict` (bind preserved dialogue to one on-screen speaker)

Apply defaults when omitted:
- `physics_mode=grounded_real`
- `style_preset=smartphone_real`
- `dialogue_policy=implied`
- `shot_policy=single_shot`
- `intensity=high`
- `coherence_mode=hybrid`
- `prompt_density=balanced`
- `speaker_binding=normal`

Note: these defaults are applied in `FINAL` mode. In `CLARIFY` mode, ask
interactive questions instead of silently applying defaults.

## UX Mode Signals (Optional)
If the user explicitly signals a UX preference, honor it deterministically:
- `CHARACTER_FIRST: yes` or “character-first” or “focus on story”: prioritize story/character questions and wording (see `references/clarify-policy.md`).
- `DIRECTOR_FIRST: yes` or “director-mode” or “camera-first”: prioritize camera/coverage questions and wording.

## Interaction Shortcuts
- **Force `FINAL` (no questions):** user explicitly says “FINAL” / “no questions” / “just write the prompt”.
- **Force `CLARIFY`:** user says “ask me questions first” / “ask me options”.
- **Continue clarifying:** user says “more questions” / “keep clarifying”.
- **Proceed to `FINAL`:** user answers “Yes — generate FINAL now” to the confirmation question.
- **Quick / minimal `FINAL`:** user says “quick” / “short” / “minimal” / “minimum viable” / “tldr”
  (or similar) *and* indicates they want a paste-ready prompt now (e.g. “quick final”, “short final”).
  - Output mode remains `FINAL`, but set `prompt_density=minimal` deterministically.
  - Do not skip required sub-blocks; compress them.

## Output Contract
Produce exactly one mode.

### Mode A: CLARIFY
Output only:
- `CLARIFYING_QUESTIONS`

Rules:
- Ask 1–5 total questions (default to 1 question per round unless the user requests bundling).
- Make every question multiple-choice.
- Default UI pattern: **two curated directions + escape hatch**
  - Prefer presenting 2 strong, scene-appropriate options (A/B) plus `Other: …`.
  - Only present 4–5 options when the user asks for the full menu, or when the extra nuance is genuinely critical to the outcome.
- Start with a short state recap inside `CLARIFYING_QUESTIONS` using this exact structure:
  - `Locked so far:` bullet list (previous choices / explicit constraints; see “Locked State Canonical Keys” below).
  - `Still open:` bullet list (next 1–5 unknowns framed as upcoming creative decisions).
- Tone guidelines (keep it human):
  - Include a 1–2 sentence creative reflection before the question (e.g. what’s compelling / what you’re picturing).
  - Use natural phrasing; avoid reading out internal option names (e.g. say “phone-footage” not `smartphone_real`).
  - Offer choices that feel like creative directions, not survey answers.
- Prefer including an `Other: …` option so the user can override the menu.
- Include: `Answers: 1B 2A 3C ...`
- Always include a single-line reply example immediately after `Answers:`:
  - If 1 question: `Reply like: A`
  - If bundled: `Reply like: 1B 2A`
- Do not output final sections.

### Mode B: FINAL
Output sections in this exact order:
1. `SORA_APP_SETTINGS`
2. `SORA_PROMPT`
3. `MITIGATIONS`
4. `REMIX_NUDGES`

Use this template exactly: `assets/prompt_template.md`.
In `FINAL` mode, the contents of `SORA_PROMPT` must be wrapped in a fenced Markdown code block labeled `text` for easy copy/paste. Do not include other sections inside the code block.

## Sora Paste Guidance (FINAL Mode)
- **What you paste into Sora:** only the contents inside the `SORA_PROMPT` fenced ` ```text ` block.
- **What you do not paste:** `SORA_APP_SETTINGS`, `MITIGATIONS`, `REMIX_NUDGES`.
- **How to use `MITIGATIONS`:** as an internal checklist to simplify/clarify the prompt if generations become messy.
- **How to use `REMIX_NUDGES`:** pick one, apply that single change to the prompt, then paste the updated `SORA_PROMPT` for a variant.

## Workflow
1. Determine mode via interactive policy in `references/clarify-policy.md`.
2. If `CLARIFY`, select questions from `references/question-bank.md` (default: 1 per round).
3. Repeat CLARIFY rounds as needed, using prior answers from the conversation.
4. When ready to generate, ask “Proceed to FINAL?” confirmation (unless user requested `FINAL / no questions`).
5. If `FINAL`, transform using `references/transform-rules.md`.
6. Enforce core constraints before output:
   - 3–5 palette anchors
   - 3–6 beats (prefer 4–6 for 15s unless very simple)
   - remix nudges count 3–5
   - each remix nudge changes exactly one variable
7. Try to stay within the length budget before output:
   - Target: `SORA_PROMPT` (the contents inside the fenced ` ```text ` block, excluding the fences) is **<= 2000 characters total**.
   - If over budget, shorten in this order:
     1) tighten prose to 1 sentence
     2) drop optional beats (keep minimum 3)
     3) compress palette anchors to 3
     4) shorten cinematography/audio wording without removing required labels
     5) simplify mitigations wording (optional; does not affect budget)
   - Never remove required labeled sub-blocks from `SORA_PROMPT`.
8. Run a final section-order check and mode exclusivity check.

## Consistency Requirements
- Resolve contradictory camera directives to one primary setup.
- Preserve user-specified constraints.
- Infer missing details minimally; avoid named brands and copyrighted characters.

## Locked State Canonical Keys (CLARIFY)
In `CLARIFY`, the `Locked so far:` block must use a stable, human-readable set of keys (omit unknowns):
- `Format:` (only if not default: portrait 9:16, ~15s)
- `Look:` phone-footage | doc texture | cinematic polish | stylized/animated | other
- `Edit feel:` one-take | a few clean cuts | storyboard beats | other
- `Chaos dial:` low | medium | high | other
- `Dialogue:` implied | none | preserve 1–2 short lines | other
- `Physics:` grounded-real | heightened | mixed | other (only if relevant)
- `Safety / privacy / text:` safe default | controlled risk | user-specified

## Remix / Variant Commands (FINAL)
If the user provides a prior `FINAL` (or says “use the last one”) and asks for a variant, prefer these deterministic commands:
- `REMIX <n>`: re-output a full `FINAL` applying remix nudge #`n` (1-based) from the most recent `FINAL`.
  - If `n` is out of range, fail fast and ask for a valid index.
- `TWEAK: <instruction>`: re-output a full `FINAL` with all locked decisions preserved, applying only the tweak.
  - If the tweak would force multiple unrelated changes, ask 1 CLARIFY question to pick the priority.
- `VARIANTS x<k>`: only when explicitly requested; output `k` separate `FINAL` blocks (k must be 2–4) that differ by exactly one variable each.

## References
Load only what is needed:
- Clarify logic and canonical questions: `references/clarify-policy.md`
- Question bank for adaptive CLARIFY rounds: `references/question-bank.md`
- Final transformation rules: `references/transform-rules.md`

## Assets
- Output scaffold: `assets/prompt_template.md`
- Evaluation schema: `assets/output_schema.json`
- Golden regression tests: `assets/golden_tests.jsonl`
