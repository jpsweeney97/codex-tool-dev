# Sora Promptify Eval Runbook (A/B: speaker binding)

This runbook is for running the **A/B-only** evaluation:

- **A**: baseline prompt text
- **B**: same prompt text + strict speaker-binding constraints (to reduce “wrong mouth” dialogue)

Primary success metric:

- `FAIL: dialogue_ownership_split_across_mouths` (defined in `rubric.json` under `fail_flags`)

## Definitions (fields + rubric terms)

These terms appear in `runs/*.jsonl` and `rubric.json`.

- `brief_id`: The brief identifier (e.g. `bp_0007`). One brief has multiple variants.
- `variant_id`: The unique id for a specific prompt variant (e.g. `bp_0007_A`, `bp_0007_B`).
- `variant_key`: Which branch of the A/B test this is (`A` or `B`).
- `generation_id`: Optional id you record from Sora (or your own label) to trace back to the exact generation.
- `video_path`: Where you saved the exported video (relative or absolute path is fine).

Scored metrics (0–5 integers):

- `identity_continuity`: Does the same character remain the same person across cuts (face/hair/age/body type)?
- `wardrobe_prop_continuity`: Do wardrobe details and key props stay consistent across cuts unless the prompt changes them?
- `dialogue_attribution_continuity`: Do spoken lines come from the correct visible speaker (no “wrong mouth”)?
- `lip_sync_plausibility`: Do mouth shapes and timing plausibly match the speech (including low-amplitude whispers)?
- `temporal_coherence`: Do actions make causal sense without inexplicable teleporting/rewriting?
- `camera_realism`: Does camera motion/framing feel physically plausible for “phone footage + cinematic coverage”?

Qualitative fields:

- `fail_flags`: A list of string flags for hard failures. Use `[]` for none.
  - Allowed values (explicit enum):
    - `dialogue_ownership_split_across_mouths`: Dialogue switches to the wrong visible mouth mid-line, or a single intended speaker’s line is split across multiple mouths.
    - `dialogue_text_not_preserved`: The generated dialogue diverges materially from the prompt’s preserved dialogue (wrong words, missing key phrase, unintelligible for a required line, or swapped line content).
    - `dialogue_action_mismatch`: The spoken dialogue describes actions/objects/events that are not what’s visibly happening (e.g. “throwing a ball” while never throwing).
    - `dialogue_line_split_across_speakers`: A single speaker-labeled line is split across multiple speakers (e.g. one character says the first half of another character’s line).
    - `role_action_mismatch`: The wrong character performs a key action that the prompt assigns to a specific character (e.g. the non-chopper is chopping).
    - `physics_plausibility_break`: A major physical plausibility failure occurs (teleporting, phasing through solids, object interactions that ignore contact/constraints, “eating air”, tools actuating without being used).
    - `fourth_wall_break`: A character looks directly into the camera or performs to the viewer in a way that breaks the intended “captured moment” feel.
    - `audience_misalignment`: Dialogue/performance is delivered to the viewer/camera rather than between characters (e.g. side-by-side speaking into camera instead of to each other).
- `notes`: A short free-text explanation (1–2 sentences) of what happened, especially *where* a failure occurred.

## What to copy/paste into Sora

Use the Markdown prompt list:

- `evals/sora_promptify/variants_ab.md`

For each entry, copy only the contents inside the fenced ` ```text ` block.

## What to log

Run log file:

- `evals/sora_promptify/runs/2026-02-07_run01.jsonl`

Template you can fill:

- `evals/sora_promptify/runs/2026-02-07_run01.template.jsonl`

Schema reference:

- `evals/sora_promptify/runs/run_log.schema.json`

## File map (quick reference)

- Prompts to paste into Sora (A/B): `evals/sora_promptify/variants_ab.md`
- Underlying prompt JSONL (A/B): `evals/sora_promptify/variants_ab.jsonl`
- Prompts to paste into Sora (A/B2 with explicit shot design): `evals/sora_promptify/variants_ab2.md`
- Underlying prompt JSONL (A/B2): `evals/sora_promptify/variants_ab2.jsonl`
- Rubric (definitions + fail flags): `evals/sora_promptify/rubric.json`
- Run log (your scored outcomes): `evals/sora_promptify/runs/2026-02-07_run01.jsonl`
- Run log template (fillable): `evals/sora_promptify/runs/2026-02-07_run01.template.jsonl`
- Auto summary (generated): `evals/sora_promptify/runs/2026-02-07_run01.summary.json`
- Next run log (empty): `evals/sora_promptify/runs/2026-02-07_run02.jsonl`
- Next run log template (fillable): `evals/sora_promptify/runs/2026-02-07_run02.template.jsonl`
- Skill-output mini-suite run sheet: `evals/sora_promptify/variants_skill_ab2.md`
- Mini-suite inputs (skill raw text + shared options): `evals/sora_promptify/mini_suite.jsonl`
- Next mini-suite run log (empty): `evals/sora_promptify/runs/2026-02-07_run03.jsonl`
- Next mini-suite run log template (fillable): `evals/sora_promptify/runs/2026-02-07_run03.template.jsonl`

## Recommended trial procedure (per prompt)

For each prompt in `variants_ab.md`:

1. Paste the prompt into Sora.
2. Keep your Sora settings consistent across A vs B for the same brief.
3. Export/save the resulting video with a stable name like:
   - `videos/bp_0007_A.mp4`
4. Immediately score it (don’t batch-score later; it reduces consistency).

## Scoring checklist (fast + consistent)

Rubric source:

- `evals/sora_promptify/rubric.json`

Score each of these 0–5 (use whole integers):

- `identity_continuity`
- `wardrobe_prop_continuity`
- `dialogue_attribution_continuity`
- `lip_sync_plausibility`
- `temporal_coherence`
- `camera_realism`

Hard FAIL flag (use aggressively):

- Add `"dialogue_ownership_split_across_mouths"` to `fail_flags` if a single intended speaker’s line appears spoken by another visible mouth, or switches mouths mid-line.

Notes guidance (1–2 sentences is enough):

- Call out exactly where it failed: “Line 2 switches to other mouth after cut,” etc.
- Mention shot type when relevant: “two-shot,” “OTS,” “MCU,” “profile occlusion,” etc.

## Updating the run log

Option A (recommended): fill the template lines

1. Open `runs/2026-02-07_run01.template.jsonl`
2. Fill in:
   - `generation_id` (whatever Sora gives you, if any)
   - `video_path` (your saved path)
   - `scores` (integers 0–5)
   - `fail_flags` (empty `[]` or include the FAIL key)
   - `notes`
3. Paste filled lines back into this chat and I’ll append them to:
   - `runs/2026-02-07_run01.jsonl`

Option B: paste minimal results

If you’re in a hurry, you can paste just:

- `brief_id`, `variant_id`, `variant_key`, plus `fail_flags` and `notes`

And we can backfill numeric scores later.

## Summarizing results (A vs B)

After you paste a batch of results, I’ll regenerate:

- `evals/sora_promptify/runs/2026-02-07_run01.summary.json`

You can also run it locally:

- `python3 -m evals.sora_promptify.summarize_runs --run evals/sora_promptify/runs/2026-02-07_run01.jsonl`

What to look for:

- Lower FAIL rate in B vs A
- Higher `dialogue_attribution_continuity` mean in B vs A
- No major regressions in identity/temporal coherence

## Sanity checks (before you start)

- Generate prompts are up to date:
  - `python3 -m evals.sora_promptify.generate_variants --variants A,B`
- Markdown prompt list matches JSONL:
  - `evals/sora_promptify/variants_ab.md` should reflect the latest generation output.
- Variants JSONL validates:
  - `./scripts/validate_sora_evals --eval-root evals/sora_promptify`
