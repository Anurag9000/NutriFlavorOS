"""Deterministic offline ranking evaluation with hard candidate filtering.

The module evaluates already-fitted rankers on temporal leave-last-out fixtures.
Hard exclusions are applied before ranking and audited after ranking. Metrics
cover relevance, catalog exposure, novelty, diversity, and user groups.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from backend.research.baselines import RankedItem


@dataclass(frozen=True)
class RankingInteraction:
    user_id: str
    item_id: str
    timestamp: int

    def __post_init__(self) -> None:
        if not self.user_id.strip() or not self.item_id.strip():
            raise ValueError("user_id and item_id cannot be blank")


@dataclass(frozen=True)
class RankingItem:
    item_id: str
    features: Tuple[float, ...]
    tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id cannot be blank")
        if not self.features:
            raise ValueError("item features cannot be empty")
        if any(not math.isfinite(value) for value in self.features):
            raise ValueError("item features must be finite")


@dataclass(frozen=True)
class TemporalRankingSplit:
    train: Tuple[RankingInteraction, ...]
    test_by_user: Mapping[str, str]


@dataclass(frozen=True)
class UserRankingMetrics:
    user_id: str
    group: str
    relevant_item: str
    eligible_candidate_count: int
    recommendation_count: int
    hit: float
    reciprocal_rank: float
    ndcg: float
    novelty: float
    diversity: float
    hard_violation_count: int


@dataclass(frozen=True)
class RankingEvaluationResult:
    model_id: str
    k: int
    evaluated_users: int
    recall_at_k: float
    hit_rate_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    catalog_coverage: float
    mean_novelty: float
    mean_intra_list_diversity: float
    hard_violation_count: int
    per_group: Mapping[str, Mapping[str, float]]
    per_user: Tuple[UserRankingMetrics, ...]
    recommendation_fingerprint: str


def temporal_leave_last_out(
    interactions: Iterable[RankingInteraction],
    *,
    minimum_train_interactions: int = 1,
) -> TemporalRankingSplit:
    if minimum_train_interactions < 1:
        raise ValueError("minimum_train_interactions must be at least 1")
    by_user: Dict[str, List[RankingInteraction]] = defaultdict(list)
    for value in interactions:
        by_user[value.user_id].append(value)
    train: List[RankingInteraction] = []
    test: Dict[str, str] = {}
    for user_id, values in sorted(by_user.items()):
        ordered = sorted(values, key=lambda item: (item.timestamp, item.item_id))
        if len(ordered) <= minimum_train_interactions:
            continue
        train.extend(ordered[:-1])
        test[user_id] = ordered[-1].item_id
    if not test:
        raise ValueError("no user has enough interactions for leave-last-out")
    return TemporalRankingSplit(
        train=tuple(
            sorted(train, key=lambda item: (item.user_id, item.timestamp, item.item_id))
        ),
        test_by_user=test,
    )


def ranking_fixture_fingerprint(
    *,
    items: Sequence[RankingItem],
    interactions: Sequence[RankingInteraction],
    user_groups: Mapping[str, str],
    hard_exclusions: Mapping[str, Sequence[str]],
) -> str:
    payload = {
        "items": [
            asdict(value) for value in sorted(items, key=lambda item: item.item_id)
        ],
        "interactions": [
            asdict(value)
            for value in sorted(
                interactions,
                key=lambda item: (item.user_id, item.timestamp, item.item_id),
            )
        ],
        "user_groups": dict(sorted(user_groups.items())),
        "hard_exclusions": {
            user_id: sorted(set(values))
            for user_id, values in sorted(hard_exclusions.items())
        },
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return 0.0 if denominator <= 0 else float(np.dot(left, right) / denominator)


def intra_list_diversity(
    item_ids: Sequence[str],
    feature_map: Mapping[str, Sequence[float]],
) -> float:
    if len(item_ids) < 2:
        return 0.0
    distances = []
    for left_index in range(len(item_ids)):
        for right_index in range(left_index + 1, len(item_ids)):
            left = np.asarray(feature_map[item_ids[left_index]], dtype=float)
            right = np.asarray(feature_map[item_ids[right_index]], dtype=float)
            if left.shape != right.shape or left.ndim != 1:
                raise ValueError("feature vectors must be aligned one-dimensional arrays")
            distances.append(1.0 - _cosine(left, right))
    return sum(distances) / len(distances)


def _novelty(
    item_ids: Sequence[str],
    popularity: Mapping[str, int],
    total_events: int,
    catalog_size: int,
) -> float:
    if not item_ids:
        return 0.0
    denominator = total_events + catalog_size
    return sum(
        -math.log2((popularity.get(item_id, 0) + 1) / denominator)
        for item_id in item_ids
    ) / len(item_ids)


def evaluate_rankings(
    *,
    model_id: str,
    recommendations: Mapping[str, Sequence[RankedItem]],
    split: TemporalRankingSplit,
    items: Sequence[RankingItem],
    user_groups: Mapping[str, str],
    hard_exclusions: Mapping[str, Sequence[str]],
    k: int,
) -> RankingEvaluationResult:
    if not model_id.strip():
        raise ValueError("model_id cannot be blank")
    if k < 1:
        raise ValueError("k must be at least 1")
    item_map = {value.item_id: value for value in items}
    if len(item_map) != len(items):
        raise ValueError("item_id values must be unique")
    feature_map = {identifier: value.features for identifier, value in item_map.items()}
    popularity = Counter(value.item_id for value in split.train)
    seen_by_user: Dict[str, set[str]] = defaultdict(set)
    for value in split.train:
        seen_by_user[value.user_id].add(value.item_id)

    per_user: List[UserRankingMetrics] = []
    recommended_catalog = set()
    fingerprint_payload = {}
    for user_id, relevant_item in sorted(split.test_by_user.items()):
        if relevant_item not in item_map:
            raise ValueError(f"test item {relevant_item} is missing from item catalog")
        exclusions = set(hard_exclusions.get(user_id, ()))
        eligible = set(item_map) - seen_by_user.get(user_id, set()) - exclusions
        if relevant_item not in eligible:
            raise ValueError(
                f"relevant item {relevant_item} is ineligible for user {user_id}"
            )
        raw = list(recommendations.get(user_id, ()))[:k]
        identifiers = [value.item_id for value in raw]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"recommendations for {user_id} contain duplicates")
        unknown = sorted(set(identifiers) - set(item_map))
        if unknown:
            raise ValueError(
                f"recommendations for {user_id} reference unknown items: {unknown}"
            )
        violations = [value for value in identifiers if value not in eligible]
        rank = (
            identifiers.index(relevant_item) + 1
            if relevant_item in identifiers
            else None
        )
        hit = 1.0 if rank is not None else 0.0
        reciprocal_rank = 1.0 / rank if rank is not None else 0.0
        ndcg = 1.0 / math.log2(rank + 1) if rank is not None else 0.0
        recommended_catalog.update(identifiers)
        group = user_groups.get(user_id, "unassigned")
        per_user.append(
            UserRankingMetrics(
                user_id=user_id,
                group=group,
                relevant_item=relevant_item,
                eligible_candidate_count=len(eligible),
                recommendation_count=len(identifiers),
                hit=hit,
                reciprocal_rank=reciprocal_rank,
                ndcg=ndcg,
                novelty=_novelty(
                    identifiers,
                    popularity,
                    len(split.train),
                    len(item_map),
                ),
                diversity=intra_list_diversity(identifiers, feature_map),
                hard_violation_count=len(violations),
            )
        )
        fingerprint_payload[user_id] = [
            {"item_id": value.item_id, "score": float(value.score)} for value in raw
        ]

    if not per_user:
        raise ValueError("no users were evaluated")
    grouped: Dict[str, List[UserRankingMetrics]] = defaultdict(list)
    for value in per_user:
        grouped[value.group].append(value)
    per_group = {
        group: {
            "user_count": float(len(values)),
            "recall_at_k": sum(value.hit for value in values) / len(values),
            "mrr_at_k": sum(value.reciprocal_rank for value in values) / len(values),
            "ndcg_at_k": sum(value.ndcg for value in values) / len(values),
            "novelty": sum(value.novelty for value in values) / len(values),
            "diversity": sum(value.diversity for value in values) / len(values),
            "hard_violation_count": float(
                sum(value.hard_violation_count for value in values)
            ),
        }
        for group, values in sorted(grouped.items())
    }
    canonical = json.dumps(
        fingerprint_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    user_count = len(per_user)
    hard_violations = sum(value.hard_violation_count for value in per_user)
    return RankingEvaluationResult(
        model_id=model_id,
        k=k,
        evaluated_users=user_count,
        recall_at_k=sum(value.hit for value in per_user) / user_count,
        hit_rate_at_k=sum(value.hit for value in per_user) / user_count,
        mrr_at_k=sum(value.reciprocal_rank for value in per_user) / user_count,
        ndcg_at_k=sum(value.ndcg for value in per_user) / user_count,
        catalog_coverage=len(recommended_catalog) / max(1, len(item_map)),
        mean_novelty=sum(value.novelty for value in per_user) / user_count,
        mean_intra_list_diversity=(
            sum(value.diversity for value in per_user) / user_count
        ),
        hard_violation_count=hard_violations,
        per_group=per_group,
        per_user=tuple(per_user),
        recommendation_fingerprint=hashlib.sha256(canonical).hexdigest(),
    )
