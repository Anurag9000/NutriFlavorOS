"""Small deterministic offline baselines.

These implementations are deliberately dependency-light and may be used only
for offline benchmarking. They are not request-time personalization models.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())


@dataclass(frozen=True)
class RankedItem:
    item_id: str
    score: float


class TfidfRetriever:
    def __init__(self) -> None:
        self._documents: Dict[str, Counter[str]] = {}
        self._idf: Dict[str, float] = {}
        self._norms: Dict[str, float] = {}

    def fit(self, documents: Iterable[Tuple[str, str]]) -> "TfidfRetriever":
        docs = {str(item_id): Counter(tokenize(text)) for item_id, text in documents}
        if not docs:
            raise ValueError("At least one document is required")
        document_frequency: Counter[str] = Counter()
        for counts in docs.values():
            document_frequency.update(counts.keys())
        total = len(docs)
        self._idf = {term: math.log((1 + total) / (1 + frequency)) + 1.0 for term, frequency in document_frequency.items()}
        self._documents = docs
        self._norms = {item_id: math.sqrt(sum((count * self._idf.get(term, 0.0)) ** 2 for term, count in counts.items())) for item_id, counts in docs.items()}
        return self

    def rank(self, query: str, k: int = 10) -> List[RankedItem]:
        if not self._documents:
            raise RuntimeError("Retriever must be fit before rank")
        if k < 1:
            raise ValueError("k must be at least 1")
        query_counts = Counter(tokenize(query))
        query_weights = {term: count * self._idf.get(term, 0.0) for term, count in query_counts.items() if term in self._idf}
        query_norm = math.sqrt(sum(value * value for value in query_weights.values()))
        scored: List[RankedItem] = []
        for item_id, counts in self._documents.items():
            denominator = query_norm * self._norms[item_id]
            score = 0.0 if denominator <= 0 else sum(query_weight * counts.get(term, 0) * self._idf[term] for term, query_weight in query_weights.items()) / denominator
            scored.append(RankedItem(item_id=item_id, score=float(score)))
        return sorted(scored, key=lambda item: (-item.score, item.item_id))[:k]


class PopularityRecommender:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def fit(self, item_ids: Iterable[str]) -> "PopularityRecommender":
        self._counts = Counter(str(item_id) for item_id in item_ids)
        return self

    def rank(self, candidates: Iterable[str], k: int = 10) -> List[RankedItem]:
        values = [RankedItem(str(item_id), float(self._counts[str(item_id)])) for item_id in candidates]
        return sorted(values, key=lambda item: (-item.score, item.item_id))[:k]


class ContentPreferenceRanker:
    def rank(self, items: Mapping[str, str], *, liked_terms: Sequence[str], disliked_terms: Sequence[str], k: int = 10) -> List[RankedItem]:
        likes = [set(tokenize(term)) for term in liked_terms if tokenize(term)]
        dislikes = [set(tokenize(term)) for term in disliked_terms if tokenize(term)]
        scored = []
        for item_id, text in items.items():
            tokens = set(tokenize(text))
            positive = sum(1.0 for phrase in likes if phrase <= tokens)
            negative = sum(1.0 for phrase in dislikes if phrase <= tokens)
            scored.append(RankedItem(str(item_id), positive - 2.0 * negative))
        return sorted(scored, key=lambda item: (-item.score, item.item_id))[:k]


class MovingAverageForecaster:
    def __init__(self, window: int = 4):
        if window < 1:
            raise ValueError("window must be at least 1")
        self.window = window
        self._history: List[float] = []

    def fit(self, values: Sequence[float]) -> "MovingAverageForecaster":
        if not values:
            raise ValueError("values cannot be empty")
        self._history = [float(value) for value in values]
        return self

    def predict(self, horizon: int) -> List[float]:
        if not self._history:
            raise RuntimeError("Forecaster must be fit before predict")
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        history = list(self._history)
        predictions = []
        for _ in range(horizon):
            prediction = sum(history[-self.window :]) / min(self.window, len(history))
            predictions.append(prediction)
            history.append(prediction)
        return predictions


class CrostonForecaster:
    def __init__(self, alpha: float = 0.1):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self._forecast: float | None = None

    def fit(self, values: Sequence[float]) -> "CrostonForecaster":
        series = [float(value) for value in values]
        if not series:
            raise ValueError("values cannot be empty")
        if any(value < 0 for value in series):
            raise ValueError("Croston demand must be non-negative")
        nonzero_indices = [index for index, value in enumerate(series) if value > 0]
        if not nonzero_indices:
            self._forecast = 0.0
            return self
        first = nonzero_indices[0]
        size = series[first]
        interval = float(first + 1)
        last_nonzero = first
        for index in nonzero_indices[1:]:
            gap = float(index - last_nonzero)
            size = self.alpha * series[index] + (1 - self.alpha) * size
            interval = self.alpha * gap + (1 - self.alpha) * interval
            last_nonzero = index
        self._forecast = size / max(interval, 1e-12)
        return self

    def predict(self, horizon: int) -> List[float]:
        if self._forecast is None:
            raise RuntimeError("Forecaster must be fit before predict")
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        return [self._forecast] * horizon


class RidgeRegressor:
    def __init__(self, alpha: float = 1.0):
        if alpha < 0:
            raise ValueError("alpha cannot be negative")
        self.alpha = alpha
        self.coef_: np.ndarray | None = None
        self.intercept_: float | None = None

    def fit(self, x: Sequence[Sequence[float]], y: Sequence[float]) -> "RidgeRegressor":
        features = np.asarray(x, dtype=float)
        target = np.asarray(y, dtype=float)
        if features.ndim != 2 or target.ndim != 1 or features.shape[0] != target.shape[0]:
            raise ValueError("x must be 2D and align with one-dimensional y")
        design = np.column_stack([np.ones(features.shape[0]), features])
        regularizer = np.eye(design.shape[1]) * self.alpha
        regularizer[0, 0] = 0.0
        weights = np.linalg.pinv(design.T @ design + regularizer) @ design.T @ target
        self.intercept_ = float(weights[0])
        self.coef_ = weights[1:]
        return self

    def predict(self, x: Sequence[Sequence[float]]) -> List[float]:
        if self.coef_ is None or self.intercept_ is None:
            raise RuntimeError("Regressor must be fit before predict")
        features = np.asarray(x, dtype=float)
        if features.ndim != 2 or features.shape[1] != self.coef_.shape[0]:
            raise ValueError("x has incompatible shape")
        return (features @ self.coef_ + self.intercept_).astype(float).tolist()
