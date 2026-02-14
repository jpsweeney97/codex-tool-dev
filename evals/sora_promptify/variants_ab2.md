# Sora Promptify — A/B2 Prompts (explicit shot design)

Source: `evals/sora_promptify/variants_ab2.jsonl`

Copy/paste each fenced block into Sora.

## 01. `bp_0001_A` (bp_0001 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  ALEX: "Wait—this is yours. We have the same bag."
  MAYA: "No way. Okay, you’re definitely getting the one with the leaky umbrella."
```

## 02. `bp_0001_B` (bp_0001 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  ALEX: "Wait—this is yours. We have the same bag."
  MAYA: "No way. Okay, you’re definitely getting the one with the leaky umbrella."
```

## 03. `bp_0002_A` (bp_0002 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: handheld phone-style medium shots
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Introduce the core action with clear cause-and-effect.
- Beat 3: Resolve the moment cleanly, maintaining continuity and realism.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
```

## 04. `bp_0002_B` (bp_0002 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: handheld phone-style medium shots
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Introduce the core action with clear cause-and-effect.
- Beat 3: Resolve the moment cleanly, maintaining continuity and realism.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
```

## 05. `bp_0003_A` (bp_0003 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  JULES: "If I chop any slower, we’ll eat tomorrow."
  RINA: "Good. Tomorrow me is hungrier."
```

## 06. `bp_0003_B` (bp_0003 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  JULES: "If I chop any slower, we’ll eat tomorrow."
  RINA: "Good. Tomorrow me is hungrier."
```

## 07. `bp_0004_A` (bp_0004 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  SAM: "I swear the rain follows me." 
  TAYLOR: "Maybe it just likes your dramatic entrances."
```

## 08. `bp_0004_B` (bp_0004 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  SAM: "I swear the rain follows me." 
  TAYLOR: "Maybe it just likes your dramatic entrances."
```

## 09. `bp_0005_A` (bp_0005 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  NORA: "You keep buying cookbooks like they’re going to cook for you." 
  ELI: "They inspire the version of me who has free time."
```

## 10. `bp_0005_B` (bp_0005 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  NORA: "You keep buying cookbooks like they’re going to cook for you." 
  ELI: "They inspire the version of me who has free time."
```

## 11. `bp_0006_A` (bp_0006 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  CASEY: "Did you move my mug again?" 
  MORGAN: "No. The mug moved itself. It’s evolving."
```

## 12. `bp_0006_B` (bp_0006 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  CASEY: "Did you move my mug again?" 
  MORGAN: "No. The mug moved itself. It’s evolving."
```

## 13. `bp_0007_A` (bp_0007 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  LEO: "If we clean for ten minutes, we can be messy guilt-free." 
  PRIYA: "That’s not how guilt works, but I admire your optimism."
```

## 14. `bp_0007_B` (bp_0007 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  LEO: "If we clean for ten minutes, we can be messy guilt-free." 
  PRIYA: "That’s not how guilt works, but I admire your optimism."
```

## 15. `bp_0008_A` (bp_0008 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  ARI: "So the plan is: we pretend this chart makes sense." 
  WEN: "And then we confidently nod until someone else speaks first."
```

## 16. `bp_0008_B` (bp_0008 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  ARI: "So the plan is: we pretend this chart makes sense." 
  WEN: "And then we confidently nod until someone else speaks first."
```

## 17. `bp_0009_A` (bp_0009 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  MILA: "Tell me you didn’t order the spiciest one." 
  DEV: "I ordered the spiciest one. For character development."
```

## 18. `bp_0009_B` (bp_0009 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  MILA: "Tell me you didn’t order the spiciest one." 
  DEV: "I ordered the spiciest one. For character development."
```

## 19. `bp_0010_A` (bp_0010 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  KIM: "If we get kicked out, it’s on you." 
  OWEN: "I’m whispering. This is my quietest trouble."
```

## 20. `bp_0010_B` (bp_0010 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  KIM: "If we get kicked out, it’s on you." 
  OWEN: "I’m whispering. This is my quietest trouble."
```

## 21. `bp_0011_A` (bp_0011 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  HARPER: "I tried jogging once. My body filed a complaint." 
  ROWAN: "Valid. Your body knows its rights."
```

## 22. `bp_0011_B` (bp_0011 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  HARPER: "I tried jogging once. My body filed a complaint." 
  ROWAN: "Valid. Your body knows its rights."
```

## 23. `bp_0012_A` (bp_0012 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  JAE: "We could label it 'draft' and hope no one reads it." 
  LUCA: "Or label it 'final' and guarantee everyone reads it."
```

## 24. `bp_0012_B` (bp_0012 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  JAE: "We could label it 'draft' and hope no one reads it." 
  LUCA: "Or label it 'final' and guarantee everyone reads it."
```

## 25. `bp_0013_A` (bp_0013 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  SASHA: "If you drink my tea, you inherit my problems." 
  BEN: "Tempting. I could use new problems."
```

## 26. `bp_0013_B` (bp_0013 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  SASHA: "If you drink my tea, you inherit my problems." 
  BEN: "Tempting. I could use new problems."
```

## 27. `bp_0014_A` (bp_0014 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: cinematic medium and medium-close during dialogue (not selfie)
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  AVA: "I can’t tell if this is 'polished' or 'trying too hard.'" 
  NOAH: "It’s polished. 'Trying too hard' would include glitter."
```

## 28. `bp_0014_B` (bp_0014 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: shot-reverse-shot coverage: medium-close on the current speaker for each line; the listener is off-camera or turned away (mouth not visible) while the line is spoken
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.; Dialogue attribution: each line is spoken by the correct visible speaker.; Speaker binding: only the current speaker’s mouth is clearly visible while speaking; no cuts during spoken lines; cinematic medium/medium-close coverage.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Stage the dialogue with unambiguous turn-taking and stable coverage.
- Beat 3: Land the reaction beat after the final line; no mid-line cuts.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
- Dialogue (preserve verbatim):
  Dialogue:
  AVA: "I can’t tell if this is 'polished' or 'trying too hard.'" 
  NOAH: "It’s polished. 'Trying too hard' would include glitter."
```

## 29. `bp_0015_A` (bp_0015 / A)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=normal`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: handheld phone-style medium shots
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Introduce the core action with clear cause-and-effect.
- Beat 3: Resolve the moment cleanly, maintaining continuity and realism.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
```

## 30. `bp_0015_B` (bp_0015 / B)
- Options (eval-only metadata): `prompt_density=balanced` `coherence_mode=hybrid` `speaker_binding=strict`

```text
Realistic phone-footage look; clear causal beats; grounded tone.

Cinematography:
- Camera framing: handheld phone-style medium shots
- Camera movement: handheld phone footage: micro-jitter, slight sway; no whip pans
- Depth of field: phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close
- Mood: grounded, intimate
- Continuity anchors: Identity consistency (face, hair, body type) across cuts.; Wardrobe/props consistent unless explicitly changed.
- Pacing: medium

Lighting + palette:
- Lighting recipe: motivated practicals; soft fill; avoid harsh flicker; realistic exposure
- Palette anchors: warm neutrals, soft skin tones, muted blues, natural greens

Actions (beats):
- Beat 1: Establish the location and subjects with realistic handheld framing.
- Beat 2: Introduce the core action with clear cause-and-effect.
- Beat 3: Resolve the moment cleanly, maintaining continuity and realism.

Audio intent:
- Ambience + key sounds: room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; realistic phone mic perspective
```
