"""Deterministic offline item-kNN recommendation baseline."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from backend.research.baselines import RankedItem


class ItemKNNRecommender:
    """Cosine item-kNN over implicit user-item interactions."""

    def __init__(self, neighbors: int = 20):
        if neighbors < 1:
            raise ValueError("neighbors must be at least 1")
        self.neighbors = neighbors
        self._users_by_item: Dict[str, set[str]] = {}
        self._items_by_user: Dict[str, set[str]] = {}
        self._similarities: Dict[str, List[Tuple[str, float]]] = {}

    def fit(self, interactions: Iterable[Tuple[str, str]]) -> "ItemKNNRecommender":
        users_by_item: Dict[str, set[str]] = defaultdict(set)
        items_by_user: Dict[str, set[str]] = defaultdict(set)
        for user_id, item_id in interactions:
            user = str(user_id)
            item = str(item_id)
            users_by_item[item].add(user)
            items_by_user[user].add(item)
        if not users_by_item:
            raise ValueError("at least one interaction is required")

        items = sorted(users_by_item)
        similarities: Dict[str, List[Tuple[str, float]]] = {}
        for item in items:
            scored = []
            left = users_by_item[item]
            for other in items:
                if other == item:
                    continue
                right = users_by_item[other]
                denominator = math.sqrt(len(left) * len(right))
                score = len(left & right) / denominator if denominator else 0.0
                if score > 0:
                    scored.append((other, score))
            similarities[item] = sorted(
                scored,
                key=lambda value: (-value[1], value[0]),
            )[: self.neighbors]

        self._users_by_item = dict(users_by_item)
        self._items_by_user = dict(items_by_user)
        self._similarities = similarities
        return self

    def recommend(
        self,
        user_id: str,
        candidates: Iterable[str] | None = None,
        k: int = 10,
    ) -> List[RankedItem]:
        if not self._similarities:
            raise RuntimeError("Recommender must be fit before recommend")
        if k < 1:
            raise ValueError("k must be at least 1")
        seen = self._items_by_user.get(str(user_id), set())
        allowed = (
            {str(value) for value in candidates}
            if candidates is not None
            else set(self._users_by_item)
        )
        scores: Dict[str, float] = defaultdict(float)
        for item in seen:
            for neighbor, similarity in self._similarities.get(item, []):
                if neighbor not in seen and neighbor in allowed:
                    scores[neighbor] += similarity
        values = [RankedItem(item, score) for item, score in scores.items()]
        return sorted(values, key=lambda value: (-value.score, value.item_id))[:k]
