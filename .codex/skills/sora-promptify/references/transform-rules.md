# Transformation Rules (FINAL Mode)

Apply these steps in order.

## 1) Parse Anchors
Extract:
- Subject anchors: 2–4 distinctive traits.
- Setting anchors: 2–5 stable landmarks.
- Core action intent: what changes over time.

Infer minimally when details are missing. Do not invent brands or copyrighted characters.

## 1.5) Coherence Mode (Reality vs Coverage)
If `coherence_mode` is unspecified, default to `hybrid`.

- `reality_first`: prioritize plausibility and phone-footage constraints over “coverage”. Keep descriptions simple and physical.
- `storyboard_first`: prioritize clarity/coverage of actions over strict minimalism. Make beats slightly more explicit and ensure causality is easy to follow.
- `hybrid`: keep phone-footage realism while making beats and camera constraints unambiguous (recommended default).

## 1.6) Prompt Density (Outcome vs Format)
If `prompt_density` is unspecified, default to `balanced`.

- `minimal`: prioritize “what you paste” brevity and concrete anchors; keep all required labeled sub-blocks, but compress each field to short phrases. Prefer 3 beats and 3 palette anchors. Avoid extra adjectives.
- `balanced`: keep the full structure with moderate detail (default).
- `max`: allow richer detail and nuance, but still obey the 2000-char `SORA_PROMPT` hard limit.

## 2) Choose Shot Structure
- `single_shot`: write one continuous shot.
- `split_into_shots`: write 2–3 shot blocks (max 3), keeping palette anchors consistent.

Each shot block must include exactly one camera setup, one primary action, one lighting recipe.

## 3) Cinematography Block
Always include:
- Camera framing (wide/medium/close + angle)
- Camera movement (static/handheld/slow pan/etc.)
- Depth of field (shallow/medium/deep)
- Mood (2–4 tone words)

Style defaults:
- `smartphone_real`: handheld, minor jitter, phone-like exposure behavior
- `doc_16mm`: handheld documentary feel, subtle grain cues, practical lighting
- `cinematic_35mm`: stabilized controlled movement, intentional composition
- `animation`: stylized motion, simplified textures, consistent outlines

## 4) Lighting + Palette
Always include:
- Lighting recipe: source(s) + quality + temperature vibe
- Palette anchors: exactly 3–5 items

Default for `smartphone_real`: naturalistic time-of-day lighting, practical sources, modest contrast.

## 5) Actions as Beats
Write 3–6 causal, time-ordered beats.
- One major action/reaction per beat.
- Prefer 4–6 beats for 15s unless scene is very simple.

For `coherence_mode=hybrid`:
- Make each beat unambiguous and physically grounded (who/what moves, what changes in frame).
- Prefer “camera-visible” beats over internal thoughts.

For `prompt_density=minimal`:
- Use exactly 3 beats unless the input clearly requires more.
- Keep each beat to one short clause.

For `prompt_density=max`:
- Prefer 4–6 beats when appropriate, but never at the expense of the 2000-char limit.

## 6) Physics Handling
- `grounded_real`: normalize extreme motion to plausible equivalents while preserving emotional intent.
- `heightened`: permit exaggeration; keep phone-footage texture unless style overrides.
- `mixed`: keep grounded overall; allow exactly one exaggerated moment.

## 7) Dialogue + Audio
Audio intent is mandatory.

Dialogue policies:
- `implied`: no quoted lines; use performance energy and nonverbal reactions.
- `remove`: no speech; only ambience/foley/reactions.
- `preserve`: include at most 2 short speaker-labeled lines.

Always include:
- ambience bed
- key foley
- optional music intent (no copyrighted lyrics)

### Speaker Binding (Preserved Dialogue)
If `dialogue_policy=preserve`, you must prevent “voice-to-mouth reassignment” by binding the dialogue to a single on-screen speaker.

If `speaker_binding` is unspecified, default to `normal`.

- `speaker_binding=normal`:
  - Prefer one clear primary speaker.
  - Avoid having multiple faces/mouths dominate frame during dialogue beats.

- `speaker_binding=strict`:
  - Dialogue must be staged so **only one character’s mouth can plausibly be speaking** during all dialogue lines.
  - During dialogue beats: keep other characters off-camera or visibly not speaking (closed mouths, backs turned, out of focus).
  - Avoid cuts during dialogue lines; prefer one continuous dialogue moment.
  - Prefer explicit shot design to reduce ambiguity: shot-reverse-shot with medium-close framing per line; avoid two-shots during spoken words.
  - No line splitting: each speaker-labeled line must be spoken start-to-finish by that same speaker (do not split a single line across multiple speakers).
  - Occlusion/crossing protocol: if the correct speaker’s mouth is occluded (someone crosses frame, turns away, or is blocked), pause speech and resume only when that speaker’s mouth is clearly visible again.
  - Fold 1–2 short “speaker binding” constraints into `SORA_PROMPT` (counts toward the 2000-char budget).

Default staging for `dialogue_policy=preserve` + `coherence_mode=hybrid` + `speaker_binding=strict`:
- Cinematic but controlled: medium/medium-close framing on the primary speaker (not a selfie talking head), with some environment visible.
- Ensure the primary speaker remains the only salient, in-focus mouth while speaking.

## 8) Mitigations
If no mitigations apply, output exactly `None.`

When applicable, include mitigation for:
- overlapping voices/many speakers
- complex collisions or pileups
- very rapid camera moves or whip pans
- contradictory camera constraints
- readable on-screen text (phone screens, menus, signs)

Prefer mitigations: fewer actors, simpler motion, fewer cuts, explicit camera constraints.

## 8.5) Fold-in Constraints (Hybrid Default)
If `coherence_mode=hybrid` (or if mitigations mention camera/continuity risks), fold the top 1–2 mitigations into `SORA_PROMPT` as short, concrete constraints, as long as the 2000-char prompt budget is still met.

Examples of fold-in constraints:
- “No whip pans; only minor handheld jitter.”
- “Keep cast to 1 employee arm + driver hand only.”
- “No readable logos or brand names.”
- “No readable on-screen text; phone screen content is blurred/unreadable.”

If `speaker_binding=strict`, treat “speaker binding” constraints as higher priority than other mitigations for fold-in.

## 8.6) Attention Topline (Hard Rule)
The very first sentence of the prose scene description must include:
- who/what (subject)
- where (setting)
- key motion/action (what changes)
- tone (2–4 mood words)

This sentence should front-load the most important anchors within the first ~300–500 characters when possible.

## 9) Remix Nudges
Provide 3–5 nudges.
Each must:
- start with `Keep everything the same except:`
- change exactly one variable
- avoid new characters unless explicitly adding one extra character

Allowed single-variable changes: lighting, lens/DOF, pacing, intensity, one prop/landmark.

## 10) Length Budget (Hard Constraint)
Hard limit: the combined character count of:
- `SORA_PROMPT` (the contents inside the fenced ` ```text ` block, excluding the fences themselves)

Must be `<= 2000` characters total.

If over budget, shorten **deterministically** in this order:
1) Prose scene description → 1 sentence max; remove adjectives first.
2) Beats → keep 3 beats minimum; drop beats from the end.
3) Palette anchors → reduce to exactly 3.
4) Cinematography + audio wording → shorten phrases but keep all required labels/fields present.
5) Mitigations → optional to shorten, but does not affect the length budget.

Never remove the required labeled sub-blocks from `SORA_PROMPT`.

## Output Shape
Top-level sections must be in this exact order:
1. `SORA_APP_SETTINGS`
2. `SORA_PROMPT`
3. `MITIGATIONS`
4. `REMIX_NUDGES`

`SORA_APP_SETTINGS` must include:
- Orientation: Portrait (9:16)
- Duration: 15s
- Style: `<none|style preset name>`

`SORA_PROMPT` must include labeled sub-blocks:
- Prose scene description (1–3 sentences)
- Cinematography
- Lighting + palette
- Actions (beats)
- Audio intent

No extra top-level sections.
