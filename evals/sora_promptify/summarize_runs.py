from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _eval_root() -> Path:
    return _repo_root() / "evals" / "sora_promptify"


def _format_error(operation: str, reason: str, got: object) -> str:
    return f"{operation} failed: {reason}. Got: {got!r:.100}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(_format_error("read jsonl", "missing file", str(path)))
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                _format_error("read jsonl", f"invalid json on line {idx}", line[:100])
            ) from e
        if not isinstance(obj, dict):
            raise ValueError(
                _format_error("read jsonl", f"expected object on line {idx}", line[:100])
            )
        rows.append(obj)
    return rows


@dataclass(frozen=True)
class ScoreAgg:
    count: int
    mean: float | None


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def summarize_run(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fail_key = "dialogue_ownership_split_across_mouths"

    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row.get("variant_key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(_format_error("summarize", "missing variant_key", row.get("variant_key")))
        by_variant.setdefault(key, []).append(row)

    def _is_fail(row: dict[str, Any]) -> bool:
        flags = row.get("fail_flags")
        if flags is None:
            return False
        if not isinstance(flags, list):
            return False
        return fail_key in [f for f in flags if isinstance(f, str)]

    def _flag_counts(items: list[dict[str, Any]]) -> dict[str, int]:
        allowed = {
            "audience_misalignment",
            "dialogue_ownership_split_across_mouths",
            "dialogue_text_not_preserved",
            "dialogue_action_mismatch",
            "dialogue_line_split_across_speakers",
            "fourth_wall_break",
            "role_action_mismatch",
            "physics_plausibility_break",
        }
        counts: dict[str, int] = {k: 0 for k in sorted(allowed)}
        for it in items:
            flags = it.get("fail_flags")
            if not isinstance(flags, list):
                continue
            for f in flags:
                if isinstance(f, str) and f in counts:
                    counts[f] += 1
        return counts

    def _score_value(row: dict[str, Any], score_key: str) -> int | None:
        scores = row.get("scores")
        if not isinstance(scores, dict):
            return None
        value = scores.get(score_key)
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None

    score_keys = [
        "identity_continuity",
        "wardrobe_prop_continuity",
        "dialogue_attribution_continuity",
        "lip_sync_plausibility",
        "temporal_coherence",
        "camera_realism",
    ]

    summary: dict[str, Any] = {
        "schema": "sora-promptify-run-summary-v1",
        "rows": len(rows),
        "fail_key": fail_key,
        "by_variant": {},
    }

    for key, items in sorted(by_variant.items()):
        fail_count = sum(1 for it in items if _is_fail(it))
        score_aggs: dict[str, ScoreAgg] = {}
        for sk in score_keys:
            values = [
                float(v)
                for v in (_score_value(it, sk) for it in items)
                if v is not None and 0 <= v <= 5
            ]
            score_aggs[sk] = ScoreAgg(count=len(values), mean=_mean_or_none(values))
        summary["by_variant"][key] = {
            "rows": len(items),
            "fail_count": fail_count,
            "fail_rate": (fail_count / len(items)) if items else None,
            "fail_flag_counts": _flag_counts(items),
            "scores": {
                sk: {"count": agg.count, "mean": agg.mean} for sk, agg in score_aggs.items()
            },
        }

    # If we have A and B, compute a quick delta table.
    if "A" in by_variant and "B" in by_variant:
        def _mean_for(vkey: str, sk: str) -> float | None:
            block = summary["by_variant"][vkey]["scores"][sk]
            return block["mean"]

        deltas: dict[str, float | None] = {}
        for sk in score_keys:
            a = _mean_for("A", sk)
            b = _mean_for("B", sk)
            deltas[sk] = (b - a) if (a is not None and b is not None) else None
        summary["A_to_B"] = {
            "fail_count_delta": summary["by_variant"]["B"]["fail_count"]
            - summary["by_variant"]["A"]["fail_count"],
            "score_mean_deltas": deltas,
        }

    return summary


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.sora_promptify.summarize_runs")
    parser.add_argument(
        "--run",
        type=Path,
        default=_eval_root() / "runs" / "2026-02-07_run01.jsonl",
        help="Path to a runs/*.jsonl file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write summary JSON to this path (default: alongside run file, with .summary.json).",
    )
    args = parser.parse_args(argv)

    rows = _read_jsonl(args.run)
    summary = summarize_run(rows)

    out_path = args.out
    if out_path is None:
        out_path = args.run.with_suffix(".summary.json")

    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote summary: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
