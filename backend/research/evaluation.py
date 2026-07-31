"""Deterministic offline evaluation metrics with explicit edge-case handling."""

from __future__ import annotations

import math
from typing import Callable, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


def _paired(actual: Sequence[float], predicted: Sequence[float]) -> Tuple[np.ndarray, np.ndarray]:
    y = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if y.ndim != 1 or p.ndim != 1 or y.shape != p.shape or y.size == 0:
        raise ValueError("actual and predicted must be non-empty aligned vectors")
    return y, p


def mae(actual: Sequence[float], predicted: Sequence[float]) -> float:
    y, p = _paired(actual, predicted)
    return float(np.mean(np.abs(y - p)))


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    y, p = _paired(actual, predicted)
    return float(np.sqrt(np.mean((y - p) ** 2)))


def wape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    y, p = _paired(actual, predicted)
    denominator = float(np.sum(np.abs(y)))
    return float(np.sum(np.abs(y - p)) / denominator) if denominator > 0 else 0.0


def r2(actual: Sequence[float], predicted: Sequence[float]) -> float:
    y, p = _paired(actual, predicted)
    denominator = float(np.sum((y - np.mean(y)) ** 2))
    if denominator <= 0:
        return 1.0 if np.allclose(y, p) else 0.0
    return float(1.0 - np.sum((y - p) ** 2) / denominator)


def pinball_loss(actual: Sequence[float], predicted: Sequence[float], quantile: float) -> float:
    if not 0 < quantile < 1:
        raise ValueError("quantile must be in (0, 1)")
    y, p = _paired(actual, predicted)
    error = y - p
    return float(np.mean(np.maximum(quantile * error, (quantile - 1) * error)))


def precision_at_k(relevant: Iterable[str], ranked: Sequence[str], k: int) -> float:
    if k < 1:
        raise ValueError("k must be at least 1")
    relevant_set = {str(value) for value in relevant}
    selected = [str(value) for value in ranked[:k]]
    return sum(value in relevant_set for value in selected) / k


def recall_at_k(relevant: Iterable[str], ranked: Sequence[str], k: int) -> float:
    relevant_set = {str(value) for value in relevant}
    if not relevant_set:
        return 0.0
    selected = {str(value) for value in ranked[:k]}
    return len(relevant_set & selected) / len(relevant_set)


def reciprocal_rank(relevant: Iterable[str], ranked: Sequence[str]) -> float:
    relevant_set = {str(value) for value in relevant}
    for index, value in enumerate(ranked, start=1):
        if str(value) in relevant_set:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevance: Mapping[str, float], ranked: Sequence[str], k: int) -> float:
    if k < 1:
        raise ValueError("k must be at least 1")
    def dcg(values: Sequence[float]) -> float:
        return sum((2**value - 1) / math.log2(index + 2) for index, value in enumerate(values))
    observed = [float(relevance.get(str(item), 0.0)) for item in ranked[:k]]
    ideal = sorted((float(value) for value in relevance.values()), reverse=True)[:k]
    denominator = dcg(ideal)
    return dcg(observed) / denominator if denominator > 0 else 0.0


def brier_score(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    y, p = _paired(labels, probabilities)
    if np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must be in [0, 1]")
    if np.any((y != 0) & (y != 1)):
        raise ValueError("labels must be binary")
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(labels: Sequence[int], probabilities: Sequence[float], bins: int = 10) -> float:
    if bins < 2:
        raise ValueError("bins must be at least 2")
    y, p = _paired(labels, probabilities)
    if np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must be in [0, 1]")
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y)
    ece = 0.0
    for index in range(bins):
        mask = (p >= edges[index]) & (p <= edges[index + 1]) if index == bins - 1 else (p >= edges[index]) & (p < edges[index + 1])
        if not np.any(mask):
            continue
        ece += float(np.sum(mask)) / total * abs(float(np.mean(p[mask])) - float(np.mean(y[mask])))
    return ece


def interval_coverage(actual: Sequence[float], lower: Sequence[float], upper: Sequence[float]) -> float:
    y, lo = _paired(actual, lower)
    _, hi = _paired(actual, upper)
    if np.any(hi < lo):
        raise ValueError("upper bounds cannot be below lower bounds")
    return float(np.mean((y >= lo) & (y <= hi)))


def mean_iou(true_mask: Sequence[Sequence[int]], predicted_mask: Sequence[Sequence[int]]) -> float:
    truth = np.asarray(true_mask)
    prediction = np.asarray(predicted_mask)
    if truth.shape != prediction.shape or truth.size == 0:
        raise ValueError("masks must have the same non-empty shape")
    classes = sorted(set(np.unique(truth).tolist()) | set(np.unique(prediction).tolist()))
    scores: List[float] = []
    for class_id in classes:
        true_pixels = truth == class_id
        predicted_pixels = prediction == class_id
        union = np.logical_or(true_pixels, predicted_pixels).sum()
        if union == 0:
            continue
        scores.append(float(np.logical_and(true_pixels, predicted_pixels).sum() / union))
    return float(np.mean(scores)) if scores else 0.0


def ips(rewards: Sequence[float], target_prob: Sequence[float], logging_prob: Sequence[float]) -> float:
    r, target = _paired(rewards, target_prob)
    _, logging = _paired(rewards, logging_prob)
    if np.any(logging <= 0) or np.any(target < 0):
        raise ValueError("logging probabilities must be positive and target probabilities non-negative")
    return float(np.mean(r * target / logging))


def snips(rewards: Sequence[float], target_prob: Sequence[float], logging_prob: Sequence[float]) -> float:
    r, target = _paired(rewards, target_prob)
    _, logging = _paired(rewards, logging_prob)
    weights = target / logging
    denominator = float(np.sum(weights))
    return float(np.sum(weights * r) / denominator) if denominator > 0 else 0.0


def bootstrap_interval(values: Sequence[float], statistic: Callable[[Sequence[float]], float] = lambda x: float(np.mean(x)), *, confidence: float = 0.95, samples: int = 1000, seed: int = 0) -> Tuple[float, float]:
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or data.size == 0:
        raise ValueError("values must be a non-empty vector")
    if not 0 < confidence < 1 or samples < 10:
        raise ValueError("invalid confidence or sample count")
    rng = np.random.default_rng(seed)
    estimates = [statistic(rng.choice(data, size=data.size, replace=True).tolist()) for _ in range(samples)]
    alpha = (1 - confidence) / 2
    return float(np.quantile(estimates, alpha)), float(np.quantile(estimates, 1 - alpha))
