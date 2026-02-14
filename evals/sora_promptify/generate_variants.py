from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class VariantSpec:
    key: str
    prompt_density: str
    coherence_mode: str
    speaker_binding: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _eval_root() -> Path:
    return _repo_root() / "evals" / "sora_promptify"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"read jsonl failed: missing file. Got: {str(path)!r}")
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"read jsonl failed: invalid json on line {idx}. Got: {line[:100]!r}"
            ) from e
        if not isinstance(obj, dict):
            raise ValueError(
                f"read jsonl failed: expected object on line {idx}. Got: {line[:100]!r}"
            )
        rows.append(obj)
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def _variant_specs(include_d: bool) -> list[VariantSpec]:
    specs = [
        VariantSpec(
            key="A",
            prompt_density="balanced",
            coherence_mode="hybrid",
            speaker_binding="normal",
        ),
        VariantSpec(
            key="B",
            prompt_density="balanced",
            coherence_mode="hybrid",
            speaker_binding="strict",
        ),
        VariantSpec(
            key="C",
            prompt_density="minimal",
            coherence_mode="hybrid",
            speaker_binding="strict",
        ),
    ]
    if include_d:
        specs.append(
            VariantSpec(
                key="D",
                prompt_density="minimal",
                coherence_mode="storyboard_first",
                speaker_binding="strict",
            )
        )
    return specs


def _render_sora_prompt(brief: dict[str, Any], spec: VariantSpec) -> str:
    brief_id = brief.get("brief_id")
    if not isinstance(brief_id, str) or not brief_id.strip():
        raise ValueError(f"render prompt failed: missing brief_id. Got: {brief_id!r}")
    brief_text = brief.get("brief")
    if not isinstance(brief_text, str) or not brief_text.strip():
        raise ValueError(
            f"render prompt failed: missing brief text. Got: {str(brief_id)!r}"
        )

    dialogue_policy = brief.get("dialogue_policy")
    if dialogue_policy not in ("preserve", "none"):
        dialogue_policy = "preserve" if "Dialogue:" in brief_text else "none"

    speaker_binding_anchor = ""
    if dialogue_policy == "preserve" and spec.speaker_binding == "strict":
        speaker_binding_anchor = (
            "Speaker binding: only the current speaker’s mouth is clearly visible while speaking; "
            "no cuts during spoken lines; cinematic medium/medium-close coverage."
        )

    continuity_anchors = [
        "Identity consistency (face, hair, body type) across cuts.",
        "Wardrobe/props consistent unless explicitly changed.",
    ]
    if dialogue_policy == "preserve":
        continuity_anchors.append(
            "Dialogue attribution: each line is spoken by the correct visible speaker."
        )
    if speaker_binding_anchor:
        continuity_anchors.append(speaker_binding_anchor)

    # Follow the sora-promptify output style: prompt-only text that belongs inside
    # the SORA_PROMPT fenced ```text block. Do not include internal option metadata.
    topline = (
        "Realistic phone-footage look; clear causal beats; grounded tone."
        if spec.coherence_mode in ("reality_first", "hybrid")
        else "Storyboard-first coverage with clear causal beats; still grounded and physically plausible."
    )

    # For strict speaker binding, prefer explicit shot design that removes ambiguity:
    # shot-reverse-shot (MCU) per line; avoid two-shots during spoken words.
    if dialogue_policy == "preserve" and spec.speaker_binding == "strict":
        camera_framing = (
            "shot-reverse-shot coverage: medium-close on the current speaker for each line; "
            "the listener is off-camera or turned away (mouth not visible) while the line is spoken"
        )
    elif dialogue_policy == "preserve":
        camera_framing = "cinematic medium and medium-close during dialogue (not selfie)"
    else:
        camera_framing = "handheld phone-style medium shots"
    camera_movement = "handheld phone footage: micro-jitter, slight sway; no whip pans"
    dof = "phone-like focus behavior: occasional autofocus hunting, natural shallow DOF in medium-close"
    mood = "grounded, intimate"
    pacing = "medium"
    lighting_recipe = "motivated practicals; soft fill; avoid harsh flicker; realistic exposure"
    palette = "warm neutrals, soft skin tones, muted blues, natural greens"

    beats = [
        "Establish the location and subjects with realistic handheld framing.",
        "Introduce the core action with clear cause-and-effect.",
        "Resolve the moment cleanly, maintaining continuity and realism.",
    ]
    if dialogue_policy == "preserve":
        beats[1] = "Stage the dialogue with unambiguous turn-taking and stable coverage."
        beats[2] = "Land the reaction beat after the final line; no mid-line cuts."

    ambience = (
        "room tone / street ambience; subtle cloth movement; footsteps; slight handling noise; "
        "realistic phone mic perspective"
    )

    optional_dialogue = ""
    if dialogue_policy == "preserve":
        dialogue_idx = brief_text.find("Dialogue:")
        if dialogue_idx != -1:
            dialogue_block = brief_text[dialogue_idx:].strip()
            optional_dialogue = (
                "\n- Dialogue (preserve verbatim):\n  "
                + dialogue_block.replace("\n", "\n  ")
            )

    prompt_lines = [
        topline,
        "",
        "Cinematography:",
        f"- Camera framing: {camera_framing}",
        f"- Camera movement: {camera_movement}",
        f"- Depth of field: {dof}",
        f"- Mood: {mood}",
        f"- Continuity anchors: {'; '.join(continuity_anchors)}",
        f"- Pacing: {pacing}",
        "",
        "Lighting + palette:",
        f"- Lighting recipe: {lighting_recipe}",
        f"- Palette anchors: {palette}",
        "",
        "Actions (beats):",
        f"- Beat 1: {beats[0]}",
        f"- Beat 2: {beats[1]}",
        f"- Beat 3: {beats[2]}",
        "",
        "Audio intent:",
        f"- Ambience + key sounds: {ambience}{optional_dialogue}",
    ]

    rendered = "\n".join(prompt_lines)
    rendered = rendered.strip()
    if len(rendered) > 2000:
        raise ValueError(
            f"render prompt failed: exceeded 2000 char limit. Got: {len(rendered)!r}"
        )
    return rendered


def build_variants(
    briefs: list[dict[str, Any]], include_d: bool, variant_keys: set[str]
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for brief in briefs:
        brief_id = brief.get("brief_id")
        if not isinstance(brief_id, str) or not brief_id.strip():
            raise ValueError(f"build variants failed: missing brief_id. Got: {brief_id!r}")

        for spec in _variant_specs(include_d=include_d):
            if spec.key not in variant_keys:
                continue
            variant_id = f"{brief_id}_{spec.key}"
            sora_prompt = _render_sora_prompt(brief=brief, spec=spec)
            variants.append(
                {
                    "brief_id": brief_id,
                    "variant_id": variant_id,
                    "variant_key": spec.key,
                    "options": {
                        "prompt_density": spec.prompt_density,
                        "coherence_mode": spec.coherence_mode,
                        "speaker_binding": spec.speaker_binding,
                    },
                    "sora_prompt": sora_prompt,
                }
            )
    return variants


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.sora_promptify.generate_variants")
    parser.add_argument(
        "--briefs",
        type=Path,
        default=_eval_root() / "briefs.jsonl",
        help="Path to briefs.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_eval_root() / "variants.jsonl",
        help="Output path for variants.jsonl",
    )
    parser.add_argument(
        "--include-d",
        action="store_true",
        help="Include variant D (storyboard_first + minimal + strict).",
    )
    parser.add_argument(
        "--variants",
        type=str,
        default="A,B,C",
        help="Comma-separated variant keys to emit (e.g., 'A,B'). Default: A,B,C",
    )
    args = parser.parse_args(argv)

    variant_keys = {k.strip() for k in args.variants.split(",") if k.strip()}
    allowed = {"A", "B", "C", "D"}
    unknown = sorted(variant_keys - allowed)
    if unknown:
        raise ValueError(f"generate variants failed: unknown variant keys. Got: {unknown!r}")
    if "D" in variant_keys and not args.include_d:
        raise ValueError(
            "generate variants failed: variant D requested but --include-d not set. Got: 'D'"
        )

    briefs = _read_jsonl(args.briefs)
    variants = build_variants(
        briefs=briefs, include_d=args.include_d, variant_keys=variant_keys
    )
    _write_jsonl(args.out, variants)
    print(f"wrote variants: {args.out} ({len(variants)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
