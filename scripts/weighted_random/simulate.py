#!/usr/bin/env python3
"""Run the reproducible million-draw experiments used by the blog article."""

from __future__ import annotations

import argparse
import html
import json
import math
import random
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from strategies import (
    HIT,
    MISS,
    DebtFeedbackSelector,
    PseudoRandomBinary,
    RunStatistics,
    calibrate_initial_probability,
    doubling_hazard,
    draw_dynamic_binary,
    draw_dynamic_weighted,
    draw_static_binary,
    draw_static_weighted,
    linear_hazard,
    normalize_weights,
)


LABELS = ("A", "B", "C")
BINARY_LABELS = (HIT, MISS)
STATIC_BINARY_PROBABILITY = 0.05
DYNAMIC_BINARY_PROBABILITIES = (0.05, 0.10, 0.15)
STATIC_WEIGHTS = {"A": 30.0, "B": 30.0, "C": 40.0}
DYNAMIC_WEIGHT_STAGES = (
    ("30/30/40", {"A": 30.0, "B": 30.0, "C": 40.0}),
    ("33/33/34", {"A": 33.0, "B": 33.0, "C": 34.0}),
    ("10/20/70", {"A": 10.0, "B": 20.0, "C": 70.0}),
)
DEFAULT_DRAWS = 1_000_000
DEFAULT_SEED = 20_260_912
CALIBRATION_TARGETS = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75)


def collect(labels: Sequence[str], draws: int, draw: Callable[[], str]) -> dict[str, Any]:
    stats = RunStatistics(labels)
    for _ in range(draws):
        stats.observe(draw())
    return stats.finish()


def _feedback_strategies(prefix: str) -> list[tuple[str, float]]:
    return [
        (f"{prefix}独立随机", 0.0),
        (f"{prefix}有限负反馈 λ=1", 1.0),
        (f"{prefix}最大欠账优先 λ=∞", math.inf),
    ]


def _strength_value(strength: float) -> float | str:
    return "infinity" if math.isinf(strength) else strength


def _first_hit_position(sequence: Sequence[str]) -> int | None:
    try:
        return sequence.index(HIT) + 1
    except ValueError:
        return None


def _binary_sample(
    probability: float,
    seed: int,
    hazard: Callable[[float, int], float] | None,
) -> dict[str, Any]:
    rng = random.Random(seed).random
    prd = PseudoRandomBinary(probability, hazard) if hazard is not None else None
    sequence = [
        HIT if draw_static_binary(probability, rng, prd=prd) else MISS
        for _ in range(100)
    ]
    stats = RunStatistics(BINARY_LABELS)
    for outcome in sequence:
        stats.observe(outcome)
    result = stats.finish()
    return {
        "sequence": [1 if outcome == HIT else 0 for outcome in sequence],
        "hit_count": result["counts"][HIT],
        "first_hit_position": _first_hit_position(sequence),
        "longest_miss": result["longest_miss"][HIT],
    }


def simulate_static_binary(draws: int, seed: int) -> list[dict[str, Any]]:
    configurations = [
        ("独立随机", None),
        ("线性递增 PRD", linear_hazard),
        ("倍增递增 PRD", doubling_hazard),
    ]
    results = []
    for name, hazard in configurations:
        rng = random.Random(seed).random
        prd = PseudoRandomBinary(STATIC_BINARY_PROBABILITY, hazard) if hazard else None
        stats = collect(
            BINARY_LABELS,
            draws,
            lambda: HIT
            if draw_static_binary(STATIC_BINARY_PROBABILITY, rng, prd=prd)
            else MISS,
        )
        expected_hits = draws * STATIC_BINARY_PROBABILITY
        results.append(
            {
                "name": name,
                "target_rate": STATIC_BINARY_PROBABILITY,
                "initial_probability": STATIC_BINARY_PROBABILITY if prd is None else prd.initial_probability,
                "expected_hits": expected_hits,
                "hit_error": stats["counts"][HIT] - expected_hits,
                "stats": stats,
                "first_100": _binary_sample(STATIC_BINARY_PROBABILITY, seed, hazard),
            }
        )
    return results


def simulate_dynamic_binary(draws: int, seed: int) -> list[dict[str, Any]]:
    results = []
    for name, strength in _feedback_strategies("动态"):
        rng = random.Random(seed).random
        selector = None if strength == 0 else DebtFeedbackSelector(BINARY_LABELS, strength)
        stats = RunStatistics(BINARY_LABELS)
        positions = [
            {"position": index + 1, "probability": probability, "draws": 0,
             "expected_hits": 0.0, "actual_hits": 0}
            for index, probability in enumerate(DYNAMIC_BINARY_PROBABILITIES)
        ]
        for index in range(draws):
            position = positions[index % len(positions)]
            probability = position["probability"]
            outcome = HIT if draw_dynamic_binary(probability, rng, selector=selector) else MISS
            stats.observe(outcome)
            position["draws"] += 1
            position["expected_hits"] += probability
            if outcome == HIT:
                position["actual_hits"] += 1
        finished = stats.finish()
        for position in positions:
            position["error"] = position["actual_hits"] - position["expected_hits"]
        expected_hits = math.fsum(row["expected_hits"] for row in positions)
        results.append(
            {
                "name": name,
                "feedback_strength": _strength_value(strength),
                "expected_hits": expected_hits,
                "hit_error": finished["counts"][HIT] - expected_hits,
                "stats": finished,
                "positions": positions,
                "final_debts": selector.snapshot() if selector else None,
            }
        )
    return results


def simulate_static_weighted(draws: int, seed: int) -> list[dict[str, Any]]:
    results = []
    expected = {
        label: probability * draws
        for label, probability in normalize_weights(STATIC_WEIGHTS).items()
    }
    for name, strength in _feedback_strategies(""):
        rng = random.Random(seed).random
        selector = None if strength == 0 else DebtFeedbackSelector(LABELS, strength)
        stats = collect(
            LABELS,
            draws,
            lambda: draw_static_weighted(STATIC_WEIGHTS, rng, selector=selector),
        )
        results.append(
            {
                "name": name,
                "feedback_strength": _strength_value(strength),
                "expected": expected,
                "error": {label: stats["counts"][label] - expected[label] for label in LABELS},
                "stats": stats,
                "final_debts": selector.snapshot() if selector else None,
            }
        )
    return results


def dynamic_weights(index: int, draws: int) -> tuple[str, Mapping[str, float]]:
    first_end = draws // 3
    second_end = 2 * draws // 3
    if index < first_end:
        return DYNAMIC_WEIGHT_STAGES[0]
    if index < second_end:
        return DYNAMIC_WEIGHT_STAGES[1]
    return DYNAMIC_WEIGHT_STAGES[2]


def simulate_dynamic_weighted(draws: int, seed: int) -> list[dict[str, Any]]:
    all_results = []
    for name, strength in _feedback_strategies("动态"):
        rng = random.Random(seed).random
        selector = None if strength == 0 else DebtFeedbackSelector(LABELS, strength)
        stats = RunStatistics(LABELS)
        stage_rows: list[dict[str, Any]] = []
        stage_name = ""
        stage_counts = {label: 0 for label in LABELS}
        stage_expected = {label: 0.0 for label in LABELS}
        stage_draws = 0

        def finish_stage() -> None:
            if stage_draws == 0:
                return
            stage_rows.append(
                {
                    "stage": stage_name,
                    "draws": stage_draws,
                    "counts": dict(stage_counts),
                    "expected": dict(stage_expected),
                    "error": {label: stage_counts[label] - stage_expected[label] for label in LABELS},
                }
            )

        for index in range(draws):
            current_stage, weights = dynamic_weights(index, draws)
            if current_stage != stage_name:
                finish_stage()
                stage_name = current_stage
                stage_counts = {label: 0 for label in LABELS}
                stage_expected = {label: 0.0 for label in LABELS}
                stage_draws = 0
            probabilities = normalize_weights(weights)
            for label in LABELS:
                stage_expected[label] += probabilities[label]
            outcome = draw_dynamic_weighted(weights, rng, selector=selector)
            stats.observe(outcome)
            stage_counts[outcome] += 1
            stage_draws += 1
        finish_stage()
        all_results.append(
            {
                "name": name,
                "feedback_strength": _strength_value(strength),
                "stats": stats.finish(),
                "stages": stage_rows,
                "final_debts": selector.snapshot() if selector else None,
            }
        )
    return all_results


# Keep the original names usable for readers of the first published version.
simulate_binary = simulate_static_binary
simulate_static = simulate_static_weighted
simulate_dynamic = simulate_dynamic_weighted


def percentage(value: float) -> str:
    return f"{value * 100:.4f}%"


def decimal(value: float) -> str:
    return f"{value:+.3f}"


def _append_binary_runs(lines: list[str], title: str, results: Sequence[Mapping[str, Any]]) -> None:
    lines.extend(["", f"### {title}", "", "| 策略 | 最长连续命中 | 命中 ≥3 / ≥5 段 | 最长连续未命中 | 未命中 ≥3 / ≥5 段 |", "|---|---:|---:|---:|---:|"])
    for result in results:
        stats = result["stats"]
        lines.append(
            f"| {result['name']} | {stats['longest_hit'][HIT]:,} | "
            f"{stats['hit_segments'][HIT][3]:,} / {stats['hit_segments'][HIT][5]:,} | "
            f"{stats['longest_miss'][HIT]:,} | {stats['miss_segments'][HIT][3]:,} / "
            f"{stats['miss_segments'][HIT][5]:,} |"
        )


def _append_weighted_runs(lines: list[str], title: str, results: Sequence[Mapping[str, Any]]) -> None:
    lines.extend(["", f"### {title}", "", "| 策略 | 类别 | 最长连出 | 连出 ≥3 / ≥5 段 | 最长未出 | 未出 ≥3 / ≥5 段 |", "|---|:---:|---:|---:|---:|---:|"])
    for result in results:
        stats = result["stats"]
        for label in LABELS:
            lines.append(
                f"| {result['name']} | {label} | {stats['longest_hit'][label]:,} | "
                f"{stats['hit_segments'][label][3]:,} / {stats['hit_segments'][label][5]:,} | "
                f"{stats['longest_miss'][label]:,} | {stats['miss_segments'][label][3]:,} / "
                f"{stats['miss_segments'][label][5]:,} |"
            )


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 概率负反馈：固定种子百万次实验", "",
        f"- 生成日期：{payload['generated_on']}", f"- 固定种子：`{payload['seed']}`",
        f"- 每种策略抽取次数：`{payload['draws']:,}`",
        "- 连续段按最大连续段计数，不重复统计重叠窗口；未出现段包含序列首尾。", "",
        "## 模型一：固定二元概率（5%）", "",
        "| 策略 | 校准起始概率 | 期望/实际命中 | 误差 | 前 100 次命中/首次命中/最长未中 |",
        "|---|---:|---:|---:|---:|",
    ]
    for result in payload["static_binary"]:
        stats = result["stats"]
        sample = result["first_100"]
        first = sample["first_hit_position"] if sample["first_hit_position"] else "无"
        lines.append(
            f"| {result['name']} | {percentage(result['initial_probability'])} | "
            f"{result['expected_hits']:,.3f} / {stats['counts'][HIT]:,} | {decimal(result['hit_error'])} | "
            f"{sample['hit_count']} / {first} / {sample['longest_miss']} |"
        )
    _append_binary_runs(lines, "固定二元概率的连续段", payload["static_binary"])
    lines.extend(["", "### 固定二元概率校准表", "", "此表由脚本按期望周期实时求解，不是厂商官方表。", "", "| 目标长期概率 | 线性递增起始概率 | 倍增递增起始概率 |", "|---:|---:|---:|"])
    for row in payload["calibration_table"]:
        lines.append(f"| {percentage(row['target_rate'])} | {percentage(row['linear_initial'])} | {percentage(row['doubling_initial'])} |")

    lines.extend(["", "## 模型二：业务动态二元概率（5%→10%→15% 循环）", "", "| 策略 | 期望命中 | 实际命中 | 总误差 |", "|---|---:|---:|---:|"])
    for result in payload["dynamic_binary"]:
        lines.append(f"| {result['name']} | {result['expected_hits']:,.3f} | {result['stats']['counts'][HIT]:,} | {decimal(result['hit_error'])} |")
    lines.extend(["", "| 策略 | 循环位置 | 本次基础概率 | 次数 | 期望/实际命中 | 误差 |", "|---|---:|---:|---:|---:|---:|"])
    for result in payload["dynamic_binary"]:
        for row in result["positions"]:
            lines.append(
                f"| {result['name']} | {row['position']} | {percentage(row['probability'])} | {row['draws']:,} | "
                f"{row['expected_hits']:,.3f} / {row['actual_hits']:,} | {decimal(row['error'])} |"
            )
    _append_binary_runs(lines, "动态二元概率的连续段", payload["dynamic_binary"])

    lines.extend(["", "## 模型三：固定多类别权重（30/30/40）", "", "| 策略 | A 次数/误差 | B 次数/误差 | C 次数/误差 |", "|---|---:|---:|---:|"])
    for result in payload["static_weighted"]:
        stats = result["stats"]
        cells = [f"{stats['counts'][label]:,} / {decimal(result['error'][label])}" for label in LABELS]
        lines.append(f"| {result['name']} | {cells[0]} | {cells[1]} | {cells[2]} |")
    _append_weighted_runs(lines, "固定多类别权重的连续段", payload["static_weighted"])

    lines.extend(["", "## 模型四：业务动态多类别权重", "", "| 策略 | 阶段权重 | 抽取数 | A 误差 | B 误差 | C 误差 |", "|---|:---:|---:|---:|---:|---:|"])
    for result in payload["dynamic_weighted"]:
        for stage in result["stages"]:
            errors = [decimal(stage["error"][label]) for label in LABELS]
            lines.append(f"| {result['name']} | {stage['stage']} | {stage['draws']:,} | {errors[0]} | {errors[1]} | {errors[2]} |")
    _append_weighted_runs(lines, "动态多类别权重的连续段", payload["dynamic_weighted"])
    return "\n".join(lines) + "\n"


def render_streak_svg(static_results: list[Mapping[str, Any]]) -> str:
    """Render a dependency-free summary of the worst hit and miss streaks."""
    rows = []
    for result in static_results:
        stats = result["stats"]
        rows.append((str(result["name"]), max(stats["longest_hit"].values()), max(stats["longest_miss"].values())))
    width, height = 1_000, 310
    chart_left, chart_width, chart_top, row_height = 275, 650, 105, 55
    maximum = max(value for _, hit, miss in rows for value in (hit, miss))
    scale = chart_width / maximum
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#101827" rx="18"/>',
        '<style>text{font-family:Inter,"Noto Sans SC",sans-serif;fill:#e5e7eb}.muted{fill:#9ca3af}.label{font-size:15px}.value{font-size:13px;font-weight:700}.title{font-size:23px;font-weight:700}</style>',
        '<text x="40" y="42" class="title">100 万次固定多类别抽取中的最长极端序列</text>',
        '<rect x="610" y="25" width="16" height="16" rx="3" fill="#60a5fa"/>', '<text x="634" y="39" class="label">最长连出</text>',
        '<rect x="750" y="25" width="16" height="16" rx="3" fill="#f59e0b"/>', '<text x="774" y="39" class="label">最长未出</text>',
    ]
    for tick in range(0, maximum + 1, 5):
        x = chart_left + tick * scale
        elements.append(f'<line x1="{x:.1f}" y1="76" x2="{x:.1f}" y2="270" stroke="#334155" stroke-width="1"/>')
        elements.append(f'<text x="{x:.1f}" y="292" text-anchor="middle" class="muted label">{tick}</text>')
    for index, (name, longest_hit, longest_miss) in enumerate(rows):
        y = chart_top + index * row_height
        elements.append(f'<text x="255" y="{y + 13}" text-anchor="end" class="label">{html.escape(name)}</text>')
        for offset, value, color in ((0, longest_hit, "#60a5fa"), (20, longest_miss, "#f59e0b")):
            bar_width = value * scale
            elements.append(f'<rect x="{chart_left}" y="{y + offset}" width="{bar_width:.1f}" height="14" rx="4" fill="{color}"/>')
            elements.append(f'<text x="{chart_left + bar_width + 7:.1f}" y="{y + offset + 12}" class="value">{value}</text>')
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("results"))
    parser.add_argument("--asset-dir", type=Path, default=Path(__file__).resolve().parents[2] / "src" / "assets" / "blog" / "weighted-random")
    args = parser.parse_args()
    if args.draws <= 0:
        parser.error("--draws must be positive")
    payload = {
        "generated_on": date.today().isoformat(), "seed": args.seed, "draws": args.draws,
        "static_binary_probability": STATIC_BINARY_PROBABILITY,
        "dynamic_binary_probabilities": DYNAMIC_BINARY_PROBABILITIES,
        "static_weights": STATIC_WEIGHTS, "dynamic_weight_stages": DYNAMIC_WEIGHT_STAGES,
        "static_binary": simulate_static_binary(args.draws, args.seed),
        "dynamic_binary": simulate_dynamic_binary(args.draws, args.seed),
        "static_weighted": simulate_static_weighted(args.draws, args.seed),
        "dynamic_weighted": simulate_dynamic_weighted(args.draws, args.seed),
        "calibration_table": [
            {"target_rate": target, "linear_initial": calibrate_initial_probability(target, linear_hazard), "doubling_initial": calibrate_initial_probability(target, doubling_hazard)}
            for target in CALIBRATION_TARGETS
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "million-draws.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(payload)
    (args.output_dir / "million-draws.md").write_text(markdown, encoding="utf-8")
    args.asset_dir.mkdir(parents=True, exist_ok=True)
    (args.asset_dir / "streak-extremes.svg").write_text(render_streak_svg(payload["static_weighted"]), encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
