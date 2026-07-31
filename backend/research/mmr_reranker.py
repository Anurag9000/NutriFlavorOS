"""Deterministic maximal-marginal-relevance reranking."""

from __future__ import annotations

import math
from typing import List, Mapping, Sequence

import numpy as np

from backend.research.baselines import RankedItem


class MMRDiversityReranker:
    def __init__(self, relevance_weight: float = 0.7):
        if not 0 <= relevance_weight <= 1:
            raise ValueError("relevance_weight must be in [0, 1]")
        self.relevance_weight = relevance_weight

    @staticmethod
    def _cosine(left: np.ndarray, right: np.ndarray) -> float:
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        return 0.0 if denominator <= 0 else float(np.dot(left, right) / denominator)

    def rerank(
        self,
        relevance: Mapping[str, float],
        features: Mapping[str, Sequence[float]],
        k: int = 10,
    ) -> List[RankedItem]:
        if k < 1:
            raise ValueError("k must be at least 1")
        identifiers = sorted(set(relevance) & set(features))
        if not identifiers:
            return []
        vectors = {
            identifier: np.asarray(features[identifier], dtype=float)
            for identifier in identifiers
        }
        shapes = {value.shape for value in vectors.values()}
        shape = next(iter(shapes)) if shapes else ()
        if len(shapes) != 1 or len(shape) != 1 or shape[0] == 0:
            raise ValueError(
                "all feature vectors must be non-empty one-dimensional arrays of equal size"
            )
        if any(not np.isfinite(value).all() for value in vectors.values()):
            raise ValueError("feature vectors must contain only finite values")
        if any(not math.isfinite(float(value)) for value in relevance.values()):
            raise ValueError("relevance scores must be finite")

        remaining = list(identifiers)
        selected: List[str] = []
        output: List[RankedItem] = []
        while remaining and len(selected) < k:
            candidates = []
            for identifier in remaining:
                redundancy = max(
                    (
                        self._cosine(vectors[identifier], vectors[chosen])
                        for chosen in selected
                    ),
                    default=0.0,
                )
                score = (
                    self.relevance_weight * float(relevance[identifier])
                    - (1 - self.relevance_weight) * redundancy
                )
                candidates.append((score, identifier))
            score, chosen = sorted(
                candidates,
                key=lambda value: (-value[0], value[1]),
            )[0]
            selected.append(chosen)
            remaining.remove(chosen)
            output.append(RankedItem(chosen, float(score)))
        return output
