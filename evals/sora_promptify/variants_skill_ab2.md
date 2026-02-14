# Sora Promptify — Skill-output mini-suite (A/B2, 2 replicates)

This file is a **manual run sheet** for generating prompts using the actual `sora-promptify` skill,
after promoting the explicit shot-design guidance into the skill rules.

For each case below:

- Run **A**: `speaker_binding=normal`
- Run **B2**: `speaker_binding=strict`
- Generate **2 replicates** for each variant (rep1, rep2) with identical settings.

Paste into the model along with the raw scene text, then copy only the `SORA_PROMPT` fenced ` ```text ` block into Sora.

Run log template:

- `evals/sora_promptify/runs/2026-02-07_run03.template.jsonl`

## Case `ms_0001` (source `bp_0007`) — Two-shot adversarial (both faces visible)

### A rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two roommates sit on a couch, both faces visible in a single medium two-shot. This is a stress test: keep turn-taking crystal clear so each line is attributed to the correct mouth. No cuts during lines. Preserve dialogue exactly.

Dialogue:
LEO: "If we clean for ten minutes, we can be messy guilt-free."
PRIYA: "That’s not how guilt works, but I admire your optimism."
```

### A rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two roommates sit on a couch, both faces visible in a single medium two-shot. This is a stress test: keep turn-taking crystal clear so each line is attributed to the correct mouth. No cuts during lines. Preserve dialogue exactly.

Dialogue:
LEO: "If we clean for ten minutes, we can be messy guilt-free."
PRIYA: "That’s not how guilt works, but I admire your optimism."
```

### B2 rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two roommates sit on a couch, both faces visible in a single medium two-shot. This is a stress test: keep turn-taking crystal clear so each line is attributed to the correct mouth. No cuts during lines. Preserve dialogue exactly.

Dialogue:
LEO: "If we clean for ten minutes, we can be messy guilt-free."
PRIYA: "That’s not how guilt works, but I admire your optimism."
```

### B2 rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two roommates sit on a couch, both faces visible in a single medium two-shot. This is a stress test: keep turn-taking crystal clear so each line is attributed to the correct mouth. No cuts during lines. Preserve dialogue exactly.

Dialogue:
LEO: "If we clean for ten minutes, we can be messy guilt-free."
PRIYA: "That’s not how guilt works, but I admire your optimism."
```

## Case `ms_0002` (source `bp_0003`) — Kitchen roles (chopping vs pouring)

### A rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two friends sit at a kitchen table. One (Jules) is chopping vegetables; the other (Rina) is pouring tea. Keep the framing cinematic medium/medium-close during dialogue and avoid fast cuts. Preserve dialogue exactly.

Dialogue:
JULES: "If I chop any slower, we’ll eat tomorrow."
RINA: "Good. Tomorrow me is hungrier."
```

### A rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two friends sit at a kitchen table. One (Jules) is chopping vegetables; the other (Rina) is pouring tea. Keep the framing cinematic medium/medium-close during dialogue and avoid fast cuts. Preserve dialogue exactly.

Dialogue:
JULES: "If I chop any slower, we’ll eat tomorrow."
RINA: "Good. Tomorrow me is hungrier."
```

### B2 rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two friends sit at a kitchen table. One (Jules) is chopping vegetables; the other (Rina) is pouring tea. Keep the framing cinematic medium/medium-close during dialogue and avoid fast cuts. Preserve dialogue exactly.

Dialogue:
JULES: "If I chop any slower, we’ll eat tomorrow."
RINA: "Good. Tomorrow me is hungrier."
```

### B2 rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two friends sit at a kitchen table. One (Jules) is chopping vegetables; the other (Rina) is pouring tea. Keep the framing cinematic medium/medium-close during dialogue and avoid fast cuts. Preserve dialogue exactly.

Dialogue:
JULES: "If I chop any slower, we’ll eat tomorrow."
RINA: "Good. Tomorrow me is hungrier."
```

## Case `ms_0003` (source `bp_0004`) — Similar silhouettes (coat + hat)

### A rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Realistic phone-footage look, but use cinematic coverage during dialogue (medium and medium-close), not selfie. Two coworkers stand under an awning outside a cafe during light rain. Both wear dark coats; one wears a black beanie, the other a hood. Keep only one mouth clearly visible while each line is spoken. Preserve dialogue exactly.

Dialogue:
SAM: "I swear the rain follows me."
TAYLOR: "Maybe it just likes your dramatic entrances."
```

### A rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Realistic phone-footage look, but use cinematic coverage during dialogue (medium and medium-close), not selfie. Two coworkers stand under an awning outside a cafe during light rain. Both wear dark coats; one wears a black beanie, the other a hood. Keep only one mouth clearly visible while each line is spoken. Preserve dialogue exactly.

Dialogue:
SAM: "I swear the rain follows me."
TAYLOR: "Maybe it just likes your dramatic entrances."
```

### B2 rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Realistic phone-footage look, but use cinematic coverage during dialogue (medium and medium-close), not selfie. Two coworkers stand under an awning outside a cafe during light rain. Both wear dark coats; one wears a black beanie, the other a hood. Keep only one mouth clearly visible while each line is spoken. Preserve dialogue exactly.

Dialogue:
SAM: "I swear the rain follows me."
TAYLOR: "Maybe it just likes your dramatic entrances."
```

### B2 rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Realistic phone-footage look, but use cinematic coverage during dialogue (medium and medium-close), not selfie. Two coworkers stand under an awning outside a cafe during light rain. Both wear dark coats; one wears a black beanie, the other a hood. Keep only one mouth clearly visible while each line is spoken. Preserve dialogue exactly.

Dialogue:
SAM: "I swear the rain follows me."
TAYLOR: "Maybe it just likes your dramatic entrances."
```

## Case `ms_0004` (source `bp_0009`) — Off-screen speaker trap

### A rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two friends at a street food stand at dusk. Keep both speakers on-screen when they speak; do not have an off-screen voice. Use medium/medium-close coverage and avoid cutting away to the food during lines. Preserve dialogue exactly.

Dialogue:
MILA: "Tell me you didn’t order the spiciest one."
DEV: "I ordered the spiciest one. For character development."
```

### A rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two friends at a street food stand at dusk. Keep both speakers on-screen when they speak; do not have an off-screen voice. Use medium/medium-close coverage and avoid cutting away to the food during lines. Preserve dialogue exactly.

Dialogue:
MILA: "Tell me you didn’t order the spiciest one."
DEV: "I ordered the spiciest one. For character development."
```

### B2 rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two friends at a street food stand at dusk. Keep both speakers on-screen when they speak; do not have an off-screen voice. Use medium/medium-close coverage and avoid cutting away to the food during lines. Preserve dialogue exactly.

Dialogue:
MILA: "Tell me you didn’t order the spiciest one."
DEV: "I ordered the spiciest one. For character development."
```

### B2 rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two friends at a street food stand at dusk. Keep both speakers on-screen when they speak; do not have an off-screen voice. Use medium/medium-close coverage and avoid cutting away to the food during lines. Preserve dialogue exactly.

Dialogue:
MILA: "Tell me you didn’t order the spiciest one."
DEV: "I ordered the spiciest one. For character development."
```

## Case `ms_0005` (source `bp_0010`) — Whisper lip-sync stress test

### A rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two friends in a quiet library corner. Dialogue is spoken softly; lip movements should be subtle and plausible. Use medium-close on the current speaker. No cuts during lines. Preserve dialogue exactly.

Dialogue:
KIM: "If we get kicked out, it’s on you."
OWEN: "I’m whispering. This is my quietest trouble."
```

### A rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two friends in a quiet library corner. Dialogue is spoken softly; lip movements should be subtle and plausible. Use medium-close on the current speaker. No cuts during lines. Preserve dialogue exactly.

Dialogue:
KIM: "If we get kicked out, it’s on you."
OWEN: "I’m whispering. This is my quietest trouble."
```

### B2 rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two friends in a quiet library corner. Dialogue is spoken softly; lip movements should be subtle and plausible. Use medium-close on the current speaker. No cuts during lines. Preserve dialogue exactly.

Dialogue:
KIM: "If we get kicked out, it’s on you."
OWEN: "I’m whispering. This is my quietest trouble."
```

### B2 rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two friends in a quiet library corner. Dialogue is spoken softly; lip movements should be subtle and plausible. Use medium-close on the current speaker. No cuts during lines. Preserve dialogue exactly.

Dialogue:
KIM: "If we get kicked out, it’s on you."
OWEN: "I’m whispering. This is my quietest trouble."
```

## Case `ms_0006` (source `bp_0008`) — Crossing movement + whiteboard

### A rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two people (Ari and Wen) stand at a whiteboard in an office. Wen steps forward to point at the board, briefly crossing in front of Ari. Keep dialogue staged so the current speaker’s mouth is visible; if someone crosses, pause speech until visibility returns. Preserve dialogue exactly.

Dialogue:
ARI: "So the plan is: we pretend this chart makes sense."
WEN: "And then we confidently nod until someone else speaks first."
```

### A rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=normal`

```text
Two people (Ari and Wen) stand at a whiteboard in an office. Wen steps forward to point at the board, briefly crossing in front of Ari. Keep dialogue staged so the current speaker’s mouth is visible; if someone crosses, pause speech until visibility returns. Preserve dialogue exactly.

Dialogue:
ARI: "So the plan is: we pretend this chart makes sense."
WEN: "And then we confidently nod until someone else speaks first."
```

### B2 rep1

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two people (Ari and Wen) stand at a whiteboard in an office. Wen steps forward to point at the board, briefly crossing in front of Ari. Keep dialogue staged so the current speaker’s mouth is visible; if someone crosses, pause speech until visibility returns. Preserve dialogue exactly.

Dialogue:
ARI: "So the plan is: we pretend this chart makes sense."
WEN: "And then we confidently nod until someone else speaks first."
```

### B2 rep2

`SORA_OPTIONS: physics_mode=grounded_real; style_preset=smartphone_real; dialogue_policy=preserve; shot_policy=single_shot; intensity=medium; coherence_mode=hybrid; prompt_density=balanced; speaker_binding=strict`

```text
Two people (Ari and Wen) stand at a whiteboard in an office. Wen steps forward to point at the board, briefly crossing in front of Ari. Keep dialogue staged so the current speaker’s mouth is visible; if someone crosses, pause speech until visibility returns. Preserve dialogue exactly.

Dialogue:
ARI: "So the plan is: we pretend this chart makes sense."
WEN: "And then we confidently nod until someone else speaks first."
```

