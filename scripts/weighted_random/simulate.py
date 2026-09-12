#!/usr/bin/env python3
"""Run the reproducible million-draw experiment used by the blog article."""

from __future__ import annotations

import argparse
import html
import json
import math
import random
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from strategies import (
    DebtFeedbackSelector,
    PseudoRandomBinary,
    RunStatistics,
    calibrate_initial_probability,
    doubling_hazard,
    linear_hazard,
    weighted_choice,
)


LABELS = ("A", "B", "C")
STATIC_WEIGHTS = {"A": 30.0, "B": 30.0, "C": 40.0}
DEFAULT_DRAWS = 1_000_000
DEFAULT_SEED = 20_260_912
CALIBRATION_TARGETS = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75)


def collect(draws: int, draw: Callable[[], str]) -> dict[str, Any]:
    stats = RunStatistics(LABELS)
    for _ in range(draws):
        stats.observe(draw())
    return stats.finish()


def simulate_static(draws: int, seed: int) -> list[dict[str, Any]]:
    strategies: list[tuple[str, float]] = [
        ("独立加权随机", 0.0),
        ("有限负反馈 λ=0.25", 0.25),
        ("有限负反馈 λ=1", 1.0),
        ("有限负反馈 λ=4", 4.0),
        ("最大欠账优先 λ=∞", math.inf),
    ]
    results = []
    for name, strength in strategies:
        rng = random.Random(seed).random
        if strength == 0:
            stats = collect(draws, lambda: weighted_choice(STATIC_WEIGHTS, rng))
            debts = None
        else:
            selector = DebtFeedbackSelector(LABELS, strength)
            stats = collect(draws, lambda: selector.draw(STATIC_WEIGHTS, rng))
            debts = selector.snapshot()
        results.append(
            {
                "name": name,
                "feedback_strength": "infinity" if math.isinf(strength) else strength,
                "stats": stats,
                "final_debts": debts,
            }
        )
    return results


def simulate_binary(draws: int, seed: int) -> list[dict[str, Any]]:
    target = 0.5
    configurations = [
        ("独立 50%", None),
        ("线性递增 PRD", linear_hazard),
        ("倍增递增 PRD", doubling_hazard),
    ]
    results = []
    for name, hazard in configurations:
        rng = random.Random(seed).random
        if hazard is None:
            initial = target
            draw = lambda: "A" if rng() < target else "B"
        else:
            selector = PseudoRandomBinary(target, hazard)
            initial = selector.initial_probability
            draw = lambda selector=selector: "A" if selector.draw(rng) else "B"

        stats = RunStatistics(("A", "B"))
        for _ in range(draws):
            stats.observe(draw())
        results.append(
            {
                "name": name,
                "target_rate": target,
                "initial_probability": initial,
                "stats": stats.finish(),
            }
        )
    return results


def dynamic_weights(index: int, draws: int) -> tuple[str, Mapping[str, float]]:
    first_end = draws // 3
    second_end = 2 * draws // 3
    if index < first_end:
        return "30/30/40", {"A": 30.0, "B": 30.0, "C": 40.0}
    if index < second_end:
        return "33/33/34", {"A": 33.0, "B": 33.0, "C": 34.0}
    return "10/20/70", {"A": 10.0, "B": 20.0, "C": 70.0}


def simulate_dynamic(draws: int, seed: int) -> list[dict[str, Any]]:
    strategies: list[tuple[str, float]] = [
        ("动态独立随机", 0.0),
        ("动态有限负反馈 λ=1", 1.0),
        ("动态最大欠账优先 λ=∞", math.inf),
    ]
    all_results = []
    for name, strength in strategies:
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
                    "error": {
                        label: stage_counts[label] - stage_expected[label]
                        for label in LABELS
                    },
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

            total_weight = math.fsum(weights.values())
            for label in LABELS:
                stage_expected[label] += weights[label] / total_weight
            if selector is None:
                outcome = weighted_choice(weights, rng)
            else:
                outcome = selector.draw(weights, rng)
            stats.observe(outcome)
            stage_counts[outcome] += 1
            stage_draws += 1
        finish_stage()

        all_results.append(
            {
                "name": name,
                "feedback_strength": "infinity" if math.isinf(strength) else strength,
                "stats": stats.finish(),
                "stages": stage_rows,
                "final_debts": selector.snapshot() if selector is not None else None,
            }
        )
    return all_results


def percentage(value: float) -> str:
    return f"{value * 100:.4f}%"


def decimal(value: float) -> str:
    return f"{value:+.3f}"


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 加权随机负反馈：固定种子蒙特卡洛结果",
        "",
        f"- 生成日期：{payload['generated_on']}",
        f"- 固定种子：`{payload['seed']}`",
        f"- 每项抽取次数：`{payload['draws']:,}`",
        "- 连续段口径：按最大连续段计数，不重复计算重叠窗口；未出现段包含序列首尾边界。",
        "",
        "## 静态 A/B/C：长期分布",
        "",
        "| 策略 | A 次数/占比 | B 次数/占比 | C 次数/占比 | 最大占比误差 |",
        "|---|---:|---:|---:|---:|",
    ]
    targets = {"A": 0.3, "B": 0.3, "C": 0.4}
    for result in payload["static"]:
        stats = result["stats"]
        maximum_error = max(
            abs(stats["shares"][label] - targets[label]) for label in LABELS
        )
        cells = [
            f"{stats['counts'][label]:,} / {percentage(stats['shares'][label])}"
            for label in LABELS
        ]
        lines.append(
            f"| {result['name']} | {cells[0]} | {cells[1]} | {cells[2]} | {percentage(maximum_error)} |"
        )

    lines.extend(
        [
            "",
            "## 静态 A/B/C：连续出现",
            "",
            "| 策略 | 类别 | 最长连出 | 连出 ≥3 段数 | 连出 ≥5 段数 |",
            "|---|:---:|---:|---:|---:|",
        ]
    )
    for result in payload["static"]:
        stats = result["stats"]
        for label in LABELS:
            lines.append(
                f"| {result['name']} | {label} | {stats['longest_hit'][label]:,} | "
                f"{stats['hit_segments'][label][3]:,} | {stats['hit_segments'][label][5]:,} |"
            )

    lines.extend(
        [
            "",
            "## 静态 A/B/C：连续未出现",
            "",
            "| 策略 | 类别 | 最长未出 | 未出 ≥3 段数 | 未出 ≥5 段数 |",
            "|---|:---:|---:|---:|---:|",
        ]
    )
    for result in payload["static"]:
        stats = result["stats"]
        for label in LABELS:
            lines.append(
                f"| {result['name']} | {label} | {stats['longest_miss'][label]:,} | "
                f"{stats['miss_segments'][label][3]:,} | {stats['miss_segments'][label][5]:,} |"
            )

    lines.extend(
        [
            "",
            "## 静态二元 50%：独立、线性递增与倍增递增",
            "",
            "A 表示命中，B 表示未命中。两种递增曲线都先校准初始概率，使理论长期命中率为 50%。",
            "",
            "| 策略 | 校准初始概率 | A 实际占比 | 最长连续命中 | 最长连续未命中 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for result in payload["binary"]:
        stats = result["stats"]
        lines.append(
            f"| {result['name']} | {percentage(result['initial_probability'])} | "
            f"{percentage(stats['shares']['A'])} | {stats['longest_hit']['A']:,} | "
            f"{stats['longest_miss']['A']:,} |"
        )

    lines.extend(
        [
            "",
            "## 静态二元概率校准表",
            "",
            "下表由脚本中的期望周期方程和二分求解实时生成，并非厂商官方表格。",
            "",
            "| 目标长期概率 | 线性递增初始概率 | 倍增递增初始概率 |",
            "|---:|---:|---:|",
        ]
    )
    for row in payload["calibration_table"]:
        lines.append(
            f"| {percentage(row['target_rate'])} | "
            f"{percentage(row['linear_initial'])} | "
            f"{percentage(row['doubling_initial'])} |"
        )

    lines.extend(
        [
            "",
            "## 动态 A/B/C：分阶段累计误差",
            "",
            "| 策略 | 阶段权重 | 抽取数 | A 误差 | B 误差 | C 误差 |",
            "|---|:---:|---:|---:|---:|---:|",
        ]
    )
    for result in payload["dynamic"]:
        for stage in result["stages"]:
            errors = [decimal(stage["error"][label]) for label in LABELS]
            lines.append(
                f"| {result['name']} | {stage['stage']} | {stage['draws']:,} | "
                f"{errors[0]} | {errors[1]} | {errors[2]} |"
            )

    return "\n".join(lines) + "\n"


def render_streak_svg(static_results: list[Mapping[str, Any]]) -> str:
    """Render a dependency-free summary of the worst hit and miss streaks."""

    rows = []
    for result in static_results:
        stats = result["stats"]
        rows.append(
            (
                str(result["name"]),
                max(stats["longest_hit"].values()),
                max(stats["longest_miss"].values()),
            )
        )

    width = 1_000
    height = 390
    chart_left = 275
    chart_width = 650
    chart_top = 105
    row_height = 48
    maximum = max(value for _, hit, miss in rows for value in (hit, miss))
    scale = chart_width / maximum
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#101827" rx="18"/>',
        '<style>text{font-family:Inter,"Noto Sans SC",sans-serif;fill:#e5e7eb}.muted{fill:#9ca3af}.label{font-size:15px}.value{font-size:13px;font-weight:700}.title{font-size:23px;font-weight:700}</style>',
        '<text x="40" y="42" class="title">100 万次静态抽取中的最长极端序列</text>',
        '<rect x="610" y="25" width="16" height="16" rx="3" fill="#60a5fa"/>',
        '<text x="634" y="39" class="label">最长连出</text>',
        '<rect x="750" y="25" width="16" height="16" rx="3" fill="#f59e0b"/>',
        '<text x="774" y="39" class="label">最长未出</text>',
    ]

    for tick in range(0, maximum + 1, 5):
        x = chart_left + tick * scale
        elements.append(
            f'<line x1="{x:.1f}" y1="76" x2="{x:.1f}" y2="350" stroke="#334155" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{x:.1f}" y="370" text-anchor="middle" class="muted label">{tick}</text>'
        )

    for index, (name, longest_hit, longest_miss) in enumerate(rows):
        y = chart_top + index * row_height
        elements.append(
            f'<text x="255" y="{y + 13}" text-anchor="end" class="label">{html.escape(name)}</text>'
        )
        for offset, value, color in (
            (0, longest_hit, "#60a5fa"),
            (20, longest_miss, "#f59e0b"),
        ):
            bar_width = value * scale
            elements.append(
                f'<rect x="{chart_left}" y="{y + offset}" width="{bar_width:.1f}" height="14" rx="4" fill="{color}"/>'
            )
            elements.append(
                f'<text x="{chart_left + bar_width + 7:.1f}" y="{y + offset + 12}" class="value">{value}</text>'
            )

    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("results"),
    )
    parser.add_argument(
        "--asset-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "src"
        / "assets"
        / "blog"
        / "weighted-random",
    )
    args = parser.parse_args()
    if args.draws <= 0:
        parser.error("--draws must be positive")

    payload = {
        "generated_on": date.today().isoformat(),
        "seed": args.seed,
        "draws": args.draws,
        "static_weights": STATIC_WEIGHTS,
        "static": simulate_static(args.draws, args.seed),
        "binary": simulate_binary(args.draws, args.seed),
        "dynamic": simulate_dynamic(args.draws, args.seed),
        "calibration_table": [
            {
                "target_rate": target,
                "linear_initial": calibrate_initial_probability(target, linear_hazard),
                "doubling_initial": calibrate_initial_probability(
                    target, doubling_hazard
                ),
            }
            for target in CALIBRATION_TARGETS
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "million-draws.json"
    markdown_path = args.output_dir / "million-draws.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = render_markdown(payload)
    markdown_path.write_text(markdown, encoding="utf-8")
    args.asset_dir.mkdir(parents=True, exist_ok=True)
    (args.asset_dir / "streak-extremes.svg").write_text(
        render_streak_svg(payload["static"]), encoding="utf-8"
    )
    print(markdown)


if __name__ == "__main__":
    main()
