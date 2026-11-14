"""Explicit descriptive statistics used by the demonstration models."""
from __future__ import annotations

import math
from statistics import median
from typing import Sequence


def quantile(values: Sequence[float], probability: float) -> float | None:
    if not 0 <= probability <= 1:
        raise ValueError("Quantile probability must be between zero and one")
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def empirical_percentile(values: Sequence[float], value: float) -> float | None:
    if not values:
        return None
    below = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return round(100 * (below + 0.5 * equal) / len(values), 6)


def ols_slope_per_decade(points: Sequence[tuple[int, float]]) -> float | None:
    if len(points) < 2:
        return None
    ordered = sorted(points)
    mean_x = math.fsum(x for x, _ in ordered) / len(ordered)
    mean_y = math.fsum(y for _, y in ordered) / len(ordered)
    denominator = math.fsum((x - mean_x) ** 2 for x, _ in ordered)
    if denominator == 0:
        return None
    numerator = math.fsum((x - mean_x) * (y - mean_y) for x, y in ordered)
    return round(10 * numerator / denominator, 6)


def theil_sen_per_decade(points: Sequence[tuple[int, float]]) -> float | None:
    ordered = sorted(points)
    slopes = [(yb - ya) / (xb - xa) for i, (xa, ya) in enumerate(ordered)
              for xb, yb in ordered[i + 1:] if xb != xa]
    return round(10 * median(slopes), 6) if slopes else None


def calibration_agreement(observed: Sequence[float], predicted: Sequence[float]) -> dict:
    if len(observed) != len(predicted):
        raise ValueError("Calibration series must contain the same number of pairs")
    count = len(observed)
    if not count:
        return {"sample_count": 0, "r2": None, "efficiency": None, "rmse": None, "mean_bias": None}
    mean_o, mean_p = math.fsum(observed) / count, math.fsum(predicted) / count
    variance_o = math.fsum((x - mean_o) ** 2 for x in observed)
    variance_p = math.fsum((x - mean_p) ** 2 for x in predicted)
    covariance = math.fsum((x - mean_o) * (y - mean_p) for x, y in zip(observed, predicted))
    squared_error = math.fsum((x - y) ** 2 for x, y in zip(observed, predicted))
    r2 = min(1.0, max(0.0, covariance ** 2 / (variance_o * variance_p))) if variance_o > 0 and variance_p > 0 else None
    return {"sample_count": count, "r2": round(r2, 6) if r2 is not None else None,
            "efficiency": round(1 - squared_error / variance_o, 6) if variance_o > 0 else None,
            "rmse": round(math.sqrt(squared_error / count), 6),
            "mean_bias": round(mean_p - mean_o, 6)}


def season_phenology(profile: Sequence[float | None]) -> dict:
    """Shortest cyclic dekad window containing 90% of positive baseline activity.

    Missing, zero, and flat profiles do not establish a fire season. This is a
    descriptive window, not an ecological or operational season prediction.
    """
    if len(profile) != 36:
        raise ValueError("Season profiles must contain 36 dekads")
    empty = {"season_defined": False, "season_onset_dekad": None,
             "season_peak_dekad": None, "season_cessation_dekad": None,
             "season_duration_dekads": None, "season_activity_share": None,
             "definition": "shortest cyclic window containing 90% of baseline activity"}
    if any(value is None for value in profile):
        return {**empty, "reason": "incomplete_baseline"}
    weights = [max(0.0, float(value)) for value in profile]
    total = math.fsum(weights)
    if total == 0 or max(weights) == min(weights):
        return {**empty, "reason": "no_seasonal_concentration"}
    target = 0.9 * total
    candidates = []
    for start in range(36):
        subtotal = 0.0
        for duration in range(1, 37):
            subtotal += weights[(start + duration - 1) % 36]
            if subtotal >= target - 1e-12:
                candidates.append((duration, start, subtotal))
                break
    duration, start, subtotal = min(candidates)
    return {**empty, "season_defined": True, "season_onset_dekad": start + 1,
            "season_peak_dekad": weights.index(max(weights)) + 1,
            "season_cessation_dekad": (start + duration - 1) % 36 + 1,
            "season_duration_dekads": duration,
            "season_activity_share": round(subtotal / total, 6)}
