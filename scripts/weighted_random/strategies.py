"""Random-selection strategies used by the weighted-random blog experiment.

The module deliberately depends only on Python's standard library so the article's
results can be reproduced with a stock Python installation.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar


Label = TypeVar("Label", bound=str)
RandomSource = Callable[[], float]
HIT = "hit"
MISS = "miss"


def validate_probability(probability: float) -> float:
    """Validate and return a binary-event probability."""

    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("probability must be finite and in [0, 1]")
    return probability


def normalize_weights(weights: Mapping[Label, float]) -> dict[Label, float]:
    """Return positive weights normalized to probabilities that sum to one."""

    if not weights:
        raise ValueError("weights must not be empty")
    if any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
        raise ValueError("weights must be finite and non-negative")

    total = math.fsum(weights.values())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    return {label: weight / total for label, weight in weights.items()}


def weighted_choice(weights: Mapping[Label, float], rng: RandomSource) -> Label:
    """Choose one label by cumulative weighted sampling."""

    probabilities = normalize_weights(weights)
    threshold = rng()
    cumulative = 0.0
    last_positive: Label | None = None
    for label, probability in probabilities.items():
        if probability <= 0:
            continue
        last_positive = label
        cumulative += probability
        if threshold < cumulative:
            return label

    # Protect against the final cumulative sum being 0.9999999999999999.
    assert last_positive is not None
    return last_positive


def linear_hazard(initial: float, attempt: int) -> float:
    """Linearly increase the conditional hit rate until it reaches 100%."""

    return min(1.0, initial * attempt)


def doubling_hazard(initial: float, attempt: int) -> float:
    """Double the conditional hit rate after every miss until it reaches 100%."""

    return min(1.0, math.ldexp(initial, attempt - 1))


Hazard = Callable[[float, int], float]


def expected_cycle_length(initial: float, hazard: Hazard) -> float:
    """Return the expected attempts between hits for a reset-on-hit schedule."""

    if not 0 < initial <= 1:
        raise ValueError("initial must be in (0, 1]")

    expected = 0.0
    survival = 1.0
    attempt = 1
    while survival > 0.0:
        expected += survival
        hit_probability = hazard(initial, attempt)
        if not 0 < hit_probability <= 1:
            raise ValueError("hazard must return a probability in (0, 1]")
        survival *= 1.0 - hit_probability
        if hit_probability >= 1.0:
            break
        attempt += 1
        if attempt > 1_000_000:
            raise RuntimeError("hazard did not converge to 1 within 1,000,000 attempts")
    return expected


def long_run_hit_rate(initial: float, hazard: Hazard) -> float:
    """Return the renewal-process long-run hit rate for a hazard schedule."""

    return 1.0 / expected_cycle_length(initial, hazard)


def calibrate_initial_probability(
    target_rate: float,
    hazard: Hazard,
    *,
    iterations: int = 80,
) -> float:
    """Solve for the initial probability whose long-run hit rate is target_rate."""

    if not 0 < target_rate <= 1:
        raise ValueError("target_rate must be in (0, 1]")
    if target_rate == 1:
        return 1.0

    low = 0.0
    high = 1.0
    for _ in range(iterations):
        middle = (low + high) / 2.0
        rate = long_run_hit_rate(middle, hazard)
        if rate < target_rate:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


@dataclass
class PseudoRandomBinary:
    """A calibrated reset-on-hit binary pseudo-random selector."""

    target_rate: float
    hazard: Hazard = linear_hazard
    misses: int = 0

    def __post_init__(self) -> None:
        self.initial_probability = calibrate_initial_probability(
            self.target_rate, self.hazard
        )

    def draw(self, rng: RandomSource) -> bool:
        hit_probability = self.hazard(self.initial_probability, self.misses + 1)
        hit = rng() < hit_probability
        self.misses = 0 if hit else self.misses + 1
        return hit


class DebtFeedbackSelector:
    """Stateful weighted selection driven by cumulative expected-share debt.

    Before each choice, category i accrues its current normalized probability p_i.
    The selected category then pays one unit. A finite feedback strength samples
    from p_i * exp(strength * debt_i); infinity selects the largest debt.
    """

    def __init__(
        self,
        labels: Sequence[Label],
        feedback_strength: float,
        *,
        debts: Mapping[Label, float] | None = None,
    ) -> None:
        if not labels:
            raise ValueError("labels must not be empty")
        if len(set(labels)) != len(labels):
            raise ValueError("labels must be unique")
        if math.isnan(feedback_strength) or feedback_strength < 0:
            raise ValueError("feedback_strength must be non-negative")

        self.labels = tuple(labels)
        self.feedback_strength = feedback_strength
        supplied = debts or {}
        unknown = set(supplied) - set(self.labels)
        if unknown:
            raise ValueError(f"debts contain unknown labels: {sorted(unknown)}")
        self.debts = {label: float(supplied.get(label, 0.0)) for label in self.labels}

    def draw(self, weights: Mapping[Label, float], rng: RandomSource) -> Label:
        if set(weights) != set(self.labels):
            raise ValueError("weights must contain exactly the selector labels")

        probabilities = normalize_weights(weights)
        for label, probability in probabilities.items():
            self.debts[label] += probability

        if math.isinf(self.feedback_strength):
            chosen = self._draw_largest_debt(probabilities, rng)
        else:
            chosen = self._draw_soft_feedback(probabilities, rng)

        self.debts[chosen] -= 1.0
        return chosen

    def snapshot(self) -> dict[Label, float]:
        """Return the small state object that can be persisted on a player."""

        return dict(self.debts)

    def _draw_largest_debt(
        self, probabilities: Mapping[Label, float], rng: RandomSource
    ) -> Label:
        eligible = [label for label in self.labels if probabilities[label] > 0]
        largest = max(self.debts[label] for label in eligible)
        tied = [
            label
            for label in eligible
            if math.isclose(self.debts[label], largest, rel_tol=0.0, abs_tol=1e-12)
        ]
        index = min(int(rng() * len(tied)), len(tied) - 1)
        return tied[index]

    def _draw_soft_feedback(
        self, probabilities: Mapping[Label, float], rng: RandomSource
    ) -> Label:
        log_scores = {
            label: math.log(probabilities[label])
            + self.feedback_strength * self.debts[label]
            for label in self.labels
            if probabilities[label] > 0
        }
        largest = max(log_scores.values())
        adjusted = {
            label: math.exp(score - largest) for label, score in log_scores.items()
        }
        return weighted_choice(adjusted, rng)


def draw_static_binary(
    probability: float,
    rng: RandomSource,
    *,
    prd: PseudoRandomBinary | None = None,
) -> bool:
    """Draw a fixed-probability binary event, optionally using calibrated PRD."""

    probability = validate_probability(probability)
    if prd is None:
        return rng() < probability
    if not math.isclose(prd.target_rate, probability, rel_tol=0.0, abs_tol=1e-15):
        raise ValueError("PRD target_rate must match the static probability")
    return prd.draw(rng)


def draw_dynamic_binary(
    current_probability: float,
    rng: RandomSource,
    *,
    selector: DebtFeedbackSelector | None = None,
) -> bool:
    """Draw a binary event whose base probability is supplied for this attempt."""

    current_probability = validate_probability(current_probability)
    if selector is None:
        return rng() < current_probability
    outcome = selector.draw(
        {HIT: current_probability, MISS: 1.0 - current_probability}, rng
    )
    return outcome == HIT


def draw_static_weighted(
    weights: Mapping[Label, float],
    rng: RandomSource,
    *,
    selector: DebtFeedbackSelector | None = None,
) -> Label:
    """Draw from a fixed multi-category weight map."""

    if selector is None:
        return weighted_choice(weights, rng)
    return selector.draw(weights, rng)


def draw_dynamic_weighted(
    current_weights: Mapping[Label, float],
    rng: RandomSource,
    *,
    selector: DebtFeedbackSelector | None = None,
) -> Label:
    """Draw from the multi-category weights supplied for this attempt."""

    if selector is None:
        return weighted_choice(current_weights, rng)
    return selector.draw(current_weights, rng)


class RunStatistics:
    """Collect maximal hit and miss runs without retaining the full sequence."""

    def __init__(self, labels: Sequence[Label], thresholds: Sequence[int] = (3, 5)):
        self.labels = tuple(labels)
        self.thresholds = tuple(sorted(set(thresholds)))
        if not self.labels or any(threshold <= 0 for threshold in self.thresholds):
            raise ValueError("labels and positive thresholds are required")

        self.total = 0
        self.counts = {label: 0 for label in self.labels}
        self.longest_hit = {label: 0 for label in self.labels}
        self.longest_miss = {label: 0 for label in self.labels}
        self.hit_segments = {
            label: {threshold: 0 for threshold in self.thresholds}
            for label in self.labels
        }
        self.miss_segments = {
            label: {threshold: 0 for threshold in self.thresholds}
            for label in self.labels
        }
        self._current_hit_label: Label | None = None
        self._current_hit_length = 0
        self._current_miss = {label: 0 for label in self.labels}
        self._finished = False

    def observe(self, outcome: Label) -> None:
        if self._finished:
            raise RuntimeError("cannot observe after finish")
        if outcome not in self.counts:
            raise ValueError(f"unknown outcome: {outcome}")

        self.total += 1
        self.counts[outcome] += 1

        if outcome == self._current_hit_label:
            self._current_hit_length += 1
        else:
            self._finish_hit_segment()
            self._current_hit_label = outcome
            self._current_hit_length = 1

        for label in self.labels:
            if label == outcome:
                self._finish_miss_segment(label)
                self._current_miss[label] = 0
            else:
                self._current_miss[label] += 1

    def finish(self) -> dict[str, object]:
        if not self._finished:
            self._finish_hit_segment()
            for label in self.labels:
                self._finish_miss_segment(label)
            self._finished = True

        return {
            "total": self.total,
            "counts": dict(self.counts),
            "shares": {
                label: self.counts[label] / self.total if self.total else 0.0
                for label in self.labels
            },
            "longest_hit": dict(self.longest_hit),
            "hit_segments": {
                label: dict(counts) for label, counts in self.hit_segments.items()
            },
            "longest_miss": dict(self.longest_miss),
            "miss_segments": {
                label: dict(counts) for label, counts in self.miss_segments.items()
            },
        }

    def _finish_hit_segment(self) -> None:
        if self._current_hit_label is None:
            return
        label = self._current_hit_label
        length = self._current_hit_length
        self.longest_hit[label] = max(self.longest_hit[label], length)
        for threshold in self.thresholds:
            if length >= threshold:
                self.hit_segments[label][threshold] += 1

    def _finish_miss_segment(self, label: Label) -> None:
        length = self._current_miss[label]
        if length <= 0:
            return
        self.longest_miss[label] = max(self.longest_miss[label], length)
        for threshold in self.thresholds:
            if length >= threshold:
                self.miss_segments[label][threshold] += 1
