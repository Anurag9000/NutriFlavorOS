"""Offline Bayesian-smoothed popularity baseline."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Tuple

from backend.research.baselines import RankedItem


class BayesianPopularityRecommender:
    """Rank items by a Beta-Bernoulli posterior mean."""

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        if prior_alpha <= 0 or prior_beta <= 0:
            raise ValueError("prior parameters must be positive")
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self._positive: Counter[str] = Counter()
        self._total: Counter[str] = Counter()

    def fit(self, events: Iterable[Tuple[str, bool]]) -> "BayesianPopularityRecommender":
        self._positive.clear()
        self._total.clear()
        for item_id, positive in events:
            identifier = str(item_id)
            self._total[identifier] += 1
            if bool(positive):
                self._positive[identifier] += 1
        return self

    def rank(self, candidates: Iterable[str], k: int = 10) -> List[RankedItem]:
        if k < 1:
            raise ValueError("k must be at least 1")
        values = []
        for candidate in candidates:
            identifier = str(candidate)
            score = (
                self.prior_alpha + self._positive[identifier]
            ) / (
                self.prior_alpha
                + self.prior_beta
                + self._total[identifier]
            )
            values.append(RankedItem(identifier, float(score)))
        return sorted(values, key=lambda value: (-value.score, value.item_id))[:k]
