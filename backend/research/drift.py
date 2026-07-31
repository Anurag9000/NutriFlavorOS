"""Dependency-light data and model drift diagnostics.

The functions return descriptive statistics only. They do not automatically
retrain, promote, or disable models. Thresholds must be established from a
versioned validation baseline for each deployed artifact.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, List, Sequence

import numpy as np
from pydantic import BaseModel, Field


class DriftMetric(BaseModel):
    name: str
    value: float
    threshold: float
    drifted: bool
    interpretation: str


class DriftReport(BaseModel):
    sample_count_reference: int = Field(ge=0)
    sample_count_current: int = Field(ge=0)
    metrics: List[DriftMetric]
    drifted: bool
    warnings: List[str] = Field(default_factory=list)


def _finite(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    return array[np.isfinite(array)]


def population_stability_index(reference: Sequence[float], current: Sequence[float], bins: int = 10) -> float:
    ref = _finite(reference)
    cur = _finite(current)
    if len(ref) == 0 or len(cur) == 0:
        raise ValueError("PSI requires non-empty finite reference and current samples")
    if bins < 2:
        raise ValueError("bins must be at least 2")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        span = max(1.0, abs(float(ref[0])) * 0.01)
        edges = np.array([float(ref[0]) - span, float(ref[0]), float(ref[0]) + span])
    edges[0], edges[-1] = -np.inf, np.inf
    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)
    epsilon = 1e-8
    ref_prob = np.clip(ref_counts / len(ref), epsilon, None)
    cur_prob = np.clip(cur_counts / len(cur), epsilon, None)
    return float(np.sum((cur_prob - ref_prob) * np.log(cur_prob / ref_prob)))


def two_sample_ks_statistic(reference: Sequence[float], current: Sequence[float]) -> float:
    ref = np.sort(_finite(reference))
    cur = np.sort(_finite(current))
    if len(ref) == 0 or len(cur) == 0:
        raise ValueError("KS statistic requires non-empty finite samples")
    points = np.sort(np.unique(np.concatenate([ref, cur])))
    ref_cdf = np.searchsorted(ref, points, side="right") / len(ref)
    cur_cdf = np.searchsorted(cur, points, side="right") / len(cur)
    return float(np.max(np.abs(ref_cdf - cur_cdf)))


def standardized_mean_shift(reference: Sequence[float], current: Sequence[float]) -> float:
    ref = _finite(reference)
    cur = _finite(current)
    if len(ref) == 0 or len(cur) == 0:
        raise ValueError("Mean shift requires non-empty finite samples")
    scale = float(np.std(ref, ddof=1)) if len(ref) > 1 else 0.0
    if scale <= 1e-12:
        return 0.0 if math.isclose(float(np.mean(ref)), float(np.mean(cur))) else float("inf")
    return abs(float(np.mean(cur) - np.mean(ref))) / scale


def categorical_total_variation(reference: Sequence[str], current: Sequence[str]) -> float:
    if not reference or not current:
        raise ValueError("Categorical drift requires non-empty samples")
    ref_counts, cur_counts = Counter(reference), Counter(current)
    keys = set(ref_counts) | set(cur_counts)
    return 0.5 * sum(abs(ref_counts[key] / len(reference) - cur_counts[key] / len(current)) for key in keys)


def numeric_drift_report(reference: Sequence[float], current: Sequence[float], *, psi_threshold: float = 0.20, ks_threshold: float = 0.20, mean_shift_threshold: float = 0.50) -> DriftReport:
    metrics = [
        DriftMetric(name="population_stability_index", value=population_stability_index(reference, current), threshold=psi_threshold, drifted=False, interpretation="Distribution-bin change relative to the reference sample."),
        DriftMetric(name="two_sample_ks", value=two_sample_ks_statistic(reference, current), threshold=ks_threshold, drifted=False, interpretation="Maximum difference between empirical cumulative distributions."),
        DriftMetric(name="standardized_mean_shift", value=standardized_mean_shift(reference, current), threshold=mean_shift_threshold, drifted=False, interpretation="Absolute mean shift measured in reference standard deviations."),
    ]
    for metric in metrics:
        metric.drifted = metric.value > metric.threshold
    return DriftReport(sample_count_reference=len(reference), sample_count_current=len(current), metrics=metrics, drifted=any(metric.drifted for metric in metrics), warnings=["Thresholds are defaults and must be calibrated for each registered artifact."])
