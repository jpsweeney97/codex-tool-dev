# Sora Promptify — JSONL Eval Harness

This folder holds **local evaluation artifacts** for iterating on the `sora-promptify` skill.

Goals (what we're optimizing for):

- Subject / identity continuity across shots
- Prop + wardrobe continuity
- Dialogue attribution continuity (avoid "wrong mouth" speaking)
- Lip-sync plausibility
- Temporal coherence and camera realism

## Files

- `briefs.jsonl`: input briefs (one per line) used to generate prompt variants.
- `variants.jsonl`: expanded prompt variants (A/B/C/...) derived from `briefs.jsonl`.
- `runs/`: run logs (human or model-graded) for produced videos / generations.
- `rubric.json`: rubric definition (used by graders and for consistent human scoring).

## Typical workflow

1. Add or edit briefs in `briefs.jsonl`.
2. Generate variants:

   - `python -m evals.sora_promptify.generate_variants`
   - A/B only: `python -m evals.sora_promptify.generate_variants --variants A,B`

3. Generate videos in Sora using each `sora_prompt` in `variants.jsonl`.
4. Log results by creating a new file under `runs/`:

   - `runs/2026-02-07_run01.jsonl` (date-based; any name is fine)

5. Score each variant using `rubric.json` and log a JSON object per line.

## Run log format

Each line in `runs/*.jsonl` is a single evaluation record:

- Required: `brief_id`, `variant_id`, `variant_key`
- Recommended: `generation_id`, `video_path`, `scores`, `fail_flags`, `notes`

Schema reference:

- `runs/run_log.schema.json`

Example:

- `runs/example_run.jsonl`

## Notes

- These eval artifacts intentionally live in this repo (`/Users/jp/Projects/active/codex-tool-dev`) so you can iterate without editing `$CODEX_HOME`.
- The harness is deterministic and does not call the network.
