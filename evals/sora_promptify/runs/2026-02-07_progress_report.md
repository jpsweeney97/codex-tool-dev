# Sora Promptify — Progress report (run01 → run02)

- Run01: `evals/sora_promptify/runs/2026-02-07_run01.summary.json` (A/B strict-binding v1)
- Run02: `evals/sora_promptify/runs/2026-02-07_run02.summary.json` (A/B2 explicit shot design)

## Primary FAIL rate (`dialogue_ownership_split_across_mouths`)

| Variant | Run01 | Run02 | Δ (Run02 − Run01) |
|---|---:|---:|---:|
| `A` | 0.0% | 6.7% | 6.7% |
| `B` | 6.7% | 0.0% | -6.7% |

## Mean scores (0–5)

### Variant A

| Metric | Run01 | Run02 | Δ |
|---|---:|---:|---:|
| `identity_continuity` | 5.00 | 5.00 | 0.00 |
| `wardrobe_prop_continuity` | 4.20 | 4.67 | 0.47 |
| `dialogue_attribution_continuity` | 5.00 | 4.33 | -0.67 |
| `lip_sync_plausibility` | 4.53 | 4.87 | 0.33 |
| `temporal_coherence` | 3.67 | 4.67 | 1.00 |
| `camera_realism` | 2.87 | 4.67 | 1.80 |

### Variant B / B2

| Metric | Run01 (B) | Run02 (B2) | Δ |
|---|---:|---:|---:|
| `identity_continuity` | 5.00 | 5.00 | 0.00 |
| `wardrobe_prop_continuity` | 4.80 | 5.00 | 0.20 |
| `dialogue_attribution_continuity` | 4.67 | 4.60 | -0.07 |
| `lip_sync_plausibility` | 4.87 | 4.67 | -0.20 |
| `temporal_coherence` | 3.73 | 5.00 | 1.27 |
| `camera_realism` | 3.13 | 5.00 | 1.87 |

## Within-run A→B deltas (B − A)

| Metric | Run01 Δ | Run02 Δ | Change (Run02Δ − Run01Δ) |
|---|---:|---:|---:|
| `identity_continuity` | 0.00 | 0.00 | 0.00 |
| `wardrobe_prop_continuity` | 0.60 | 0.33 | -0.27 |
| `dialogue_attribution_continuity` | -0.33 | 0.27 | 0.60 |
| `lip_sync_plausibility` | 0.33 | -0.20 | -0.53 |
| `temporal_coherence` | 0.07 | 0.33 | 0.27 |
| `camera_realism` | 0.27 | 0.33 | 0.07 |

## Fail flag counts (per variant)

### `A`

| Fail flag | Run01 | Run02 | Δ |
|---|---:|---:|---:|
| `dialogue_ownership_split_across_mouths` | 0 | 1 | +1 |
| `dialogue_text_not_preserved` | 1 | 0 | -1 |
| `dialogue_action_mismatch` | 0 | 2 | +2 |
| `role_action_mismatch` | 0 | 3 | +3 |
| `physics_plausibility_break` | 0 | 5 | +5 |

### `B`

| Fail flag | Run01 | Run02 | Δ |
|---|---:|---:|---:|
| `dialogue_ownership_split_across_mouths` | 1 | 0 | -1 |
| `dialogue_text_not_preserved` | 0 | 1 | +1 |
| `dialogue_action_mismatch` | 0 | 1 | +1 |
| `role_action_mismatch` | 0 | 1 | +1 |
| `physics_plausibility_break` | 0 | 2 | +2 |
