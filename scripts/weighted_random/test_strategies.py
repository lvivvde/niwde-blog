from __future__ import annotations

import math
import random
import unittest

from strategies import (
    DebtFeedbackSelector,
    RunStatistics,
    calibrate_initial_probability,
    doubling_hazard,
    expected_cycle_length,
    linear_hazard,
    long_run_hit_rate,
    normalize_weights,
)
from simulate import render_markdown, render_streak_svg, simulate_static


class ProbabilityTests(unittest.TestCase):
    def test_normalizes_arbitrary_weights(self) -> None:
        self.assertEqual(normalize_weights({"A": 3, "B": 3, "C": 4}), {
            "A": 0.3,
            "B": 0.3,
            "C": 0.4,
        })

    def test_rejects_invalid_weights(self) -> None:
        for weights in ({}, {"A": 0}, {"A": -1}, {"A": math.inf}):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                normalize_weights(weights)

    def test_quarter_half_one_example_has_8_over_17_long_run_rate(self) -> None:
        self.assertAlmostEqual(expected_cycle_length(0.25, doubling_hazard), 2.125)
        self.assertAlmostEqual(long_run_hit_rate(0.25, doubling_hazard), 8 / 17)

    def test_calibrates_linear_and_doubling_schedules(self) -> None:
        for hazard in (linear_hazard, doubling_hazard):
            with self.subTest(hazard=hazard.__name__):
                initial = calibrate_initial_probability(0.5, hazard)
                self.assertAlmostEqual(long_run_hit_rate(initial, hazard), 0.5, places=12)


class DebtFeedbackTests(unittest.TestCase):
    def test_debt_accounting_tracks_dynamic_expected_share(self) -> None:
        selector = DebtFeedbackSelector(("A", "B", "C"), 1.0)
        rng = random.Random(7).random
        counts = {label: 0 for label in selector.labels}
        expected = {label: 0.0 for label in selector.labels}
        schedules = [
            {"A": 30, "B": 30, "C": 40},
            {"A": 33, "B": 33, "C": 34},
            {"A": 10, "B": 20, "C": 70},
        ]

        for index in range(3_000):
            weights = schedules[index // 1_000]
            total = sum(weights.values())
            for label, weight in weights.items():
                expected[label] += weight / total
            counts[selector.draw(weights, rng)] += 1

        for label in selector.labels:
            self.assertAlmostEqual(counts[label] - expected[label], -selector.debts[label])

    def test_infinite_feedback_hits_exact_static_quota_at_full_cycles(self) -> None:
        selector = DebtFeedbackSelector(("A", "B", "C"), math.inf)
        rng = random.Random(11).random
        counts = {"A": 0, "B": 0, "C": 0}
        for _ in range(1_000):
            counts[selector.draw({"A": 30, "B": 30, "C": 40}, rng)] += 1
        self.assertEqual(counts, {"A": 300, "B": 300, "C": 400})

    def test_snapshot_restores_persistent_player_state(self) -> None:
        first = DebtFeedbackSelector(("A", "B", "C"), 2.0)
        rng = random.Random(13).random
        for _ in range(17):
            first.draw({"A": 30, "B": 30, "C": 40}, rng)

        restored = DebtFeedbackSelector(
            first.labels, first.feedback_strength, debts=first.snapshot()
        )
        self.assertEqual(restored.snapshot(), first.snapshot())


class RunStatisticsTests(unittest.TestCase):
    def test_counts_maximal_hit_and_boundary_miss_segments(self) -> None:
        stats = RunStatistics(("A", "B", "C"))
        for outcome in "AAAABBBAC":
            stats.observe(outcome)
        result = stats.finish()

        self.assertEqual(result["counts"], {"A": 5, "B": 3, "C": 1})
        self.assertEqual(result["longest_hit"], {"A": 4, "B": 3, "C": 1})
        self.assertEqual(result["hit_segments"]["A"], {3: 1, 5: 0})
        self.assertEqual(result["hit_segments"]["B"], {3: 1, 5: 0})
        self.assertEqual(result["longest_miss"], {"A": 3, "B": 4, "C": 8})
        self.assertEqual(result["miss_segments"]["C"], {3: 1, 5: 1})


class ReportTests(unittest.TestCase):
    def test_small_simulation_renders_markdown_and_svg(self) -> None:
        results = simulate_static(100, 17)
        payload = {
            "generated_on": "2026-09-12",
            "seed": 17,
            "draws": 100,
            "static": results,
            "binary": [],
            "dynamic": [],
            "calibration_table": [],
        }

        markdown = render_markdown(payload)
        svg = render_streak_svg(results)
        self.assertIn("静态 A/B/C：长期分布", markdown)
        self.assertIn("<svg", svg)
        self.assertIn("最长连出", svg)


if __name__ == "__main__":
    unittest.main()
