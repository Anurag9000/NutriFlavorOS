#!/usr/bin/env python3
"""Benchmark deterministic ranking baselines on leakage-safe synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from backend.research.baselines import PopularityRecommender, RankedItem
from backend.research.item_knn import ItemKNNRecommender
from backend.research.mmr_reranker import MMRDiversityReranker
from backend.research.ranking_evaluation import (
    RankingInteraction,
    RankingItem,
    evaluate_rankings,
    ranking_fixture_fingerprint,
    temporal_leave_last_out,
)
from backend.research.smoothed_popularity import BayesianPopularityRecommender


def generate_ranking_fixture(
    *,
    seed: int,
    user_count: int = 18,
    item_group_count: int = 3,
    items_per_group: int = 8,
    interactions_per_user: int = 6,
) -> dict:
    if user_count < 3:
        raise ValueError("user_count must be at least 3")
    if item_group_count < 2:
        raise ValueError("item_group_count must be at least 2")
    if items_per_group < interactions_per_user + 1:
        raise ValueError(
            "items_per_group must exceed interactions_per_user for unseen holdout"
        )
    if interactions_per_user < 2:
        raise ValueError("interactions_per_user must be at least 2")

    rng = random.Random(seed)
    items: List[RankingItem] = []
    by_group: Dict[int, List[str]] = {}
    for group in range(item_group_count):
        by_group[group] = []
        for index in range(items_per_group):
            item_id = f"group-{group}.item-{index}"
            feature = [0.0] * item_group_count
            feature[group] = 1.0
            feature.append(index / max(1, items_per_group - 1))
            items.append(
                RankingItem(
                    item_id=item_id,
                    features=tuple(feature),
                    tags=(f"group-{group}",),
                )
            )
            by_group[group].append(item_id)

    interactions: List[RankingInteraction] = []
    user_groups: Dict[str, str] = {}
    hard_exclusions: Dict[str, List[str]] = {}
    timestamp = 0
    for user_index in range(user_count):
        user_id = f"user-{user_index}"
        group = user_index % item_group_count
        user_groups[user_id] = f"preference-{group}"
        preferred = list(by_group[group])
        rng.shuffle(preferred)
        selected = preferred[:interactions_per_user]
        for item_id in selected:
            interactions.append(
                RankingInteraction(
                    user_id=user_id,
                    item_id=item_id,
                    timestamp=timestamp,
                )
            )
            timestamp += 1
        excluded_group = (group + 1) % item_group_count
        hard_exclusions[user_id] = [
            by_group[excluded_group][user_index % items_per_group]
        ]

    return {
        "items": items,
        "interactions": interactions,
        "user_groups": user_groups,
        "hard_exclusions": hard_exclusions,
        "configuration": {
            "seed": seed,
            "user_count": user_count,
            "item_group_count": item_group_count,
            "items_per_group": items_per_group,
            "interactions_per_user": interactions_per_user,
        },
    }


def _eligible_candidates(
    *,
    user_id: str,
    all_items: Sequence[str],
    seen: Mapping[str, set[str]],
    exclusions: Mapping[str, Sequence[str]],
) -> List[str]:
    blocked = set(exclusions.get(user_id, ()))
    return sorted(set(all_items) - seen.get(user_id, set()) - blocked)


def benchmark_rankers(fixture: dict, *, k: int = 5) -> dict:
    if k < 1:
        raise ValueError("k must be at least 1")
    items: List[RankingItem] = list(fixture["items"])
    interactions: List[RankingInteraction] = list(fixture["interactions"])
    user_groups: Dict[str, str] = dict(fixture["user_groups"])
    hard_exclusions: Dict[str, List[str]] = {
        key: list(value) for key, value in fixture["hard_exclusions"].items()
    }
    split = temporal_leave_last_out(interactions)
    all_item_ids = [value.item_id for value in items]
    feature_map = {value.item_id: value.features for value in items}
    seen: Dict[str, set[str]] = {}
    for value in split.train:
        seen.setdefault(value.user_id, set()).add(value.item_id)

    popularity = PopularityRecommender().fit(
        value.item_id for value in split.train
    )
    bayesian = BayesianPopularityRecommender().fit(
        (value.item_id, True) for value in split.train
    )
    item_knn = ItemKNNRecommender(neighbors=20).fit(
        (value.user_id, value.item_id) for value in split.train
    )
    mmr = MMRDiversityReranker(relevance_weight=0.7)

    recommendations: Dict[str, Dict[str, List[RankedItem]]] = {
        "popularity_recommender": {},
        "bayesian_popularity_recommender": {},
        "item_knn_recommender": {},
        "mmr_diversity_reranker": {},
    }
    for user_id in sorted(split.test_by_user):
        candidates = _eligible_candidates(
            user_id=user_id,
            all_items=all_item_ids,
            seen=seen,
            exclusions=hard_exclusions,
        )
        recommendations["popularity_recommender"][user_id] = popularity.rank(
            candidates,
            k=k,
        )
        bayesian_full = bayesian.rank(candidates, k=max(1, len(candidates)))
        recommendations["bayesian_popularity_recommender"][user_id] = (
            bayesian_full[:k]
        )
        recommendations["item_knn_recommender"][user_id] = item_knn.recommend(
            user_id,
            candidates,
            k=k,
        )
        relevance = {value.item_id: value.score for value in bayesian_full}
        recommendations["mmr_diversity_reranker"][user_id] = mmr.rerank(
            relevance,
            {identifier: feature_map[identifier] for identifier in candidates},
            k=k,
        )

    results = {
        model_id: evaluate_rankings(
            model_id=model_id,
            recommendations=values,
            split=split,
            items=items,
            user_groups=user_groups,
            hard_exclusions=hard_exclusions,
            k=k,
        )
        for model_id, values in sorted(recommendations.items())
    }
    serialized = {identifier: asdict(value) for identifier, value in results.items()}
    accuracy_leader = max(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["ndcg_at_k"],
            serialized[identifier]["recall_at_k"],
            identifier,
        ),
    )
    diversity_leader = max(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["mean_intra_list_diversity"],
            serialized[identifier]["catalog_coverage"],
            identifier,
        ),
    )
    coverage_leader = max(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["catalog_coverage"],
            serialized[identifier]["mean_novelty"],
            identifier,
        ),
    )
    return {
        "protocol_version": "temporal_ranking_diversity_v1",
        "fixture_fingerprint": ranking_fixture_fingerprint(
            items=items,
            interactions=interactions,
            user_groups=user_groups,
            hard_exclusions=hard_exclusions,
        ),
        "configuration": {**fixture.get("configuration", {}), "k": k},
        "split": {
            "train_interaction_count": len(split.train),
            "test_user_count": len(split.test_by_user),
            "strategy": "per_user_temporal_leave_last_out",
        },
        "models": serialized,
        "accuracy_leader": accuracy_leader,
        "diversity_leader": diversity_leader,
        "coverage_leader": coverage_leader,
        "selection_warning": (
            "Accuracy, diversity, novelty, and coverage leaders are separate; no runtime ranker is selected automatically."
        ),
    }


def regression_failures(
    report: dict,
    *,
    required_models: Sequence[str],
    minimum_best_recall: float | None,
    minimum_best_coverage: float | None,
    maximum_hard_violations: int,
) -> list[str]:
    failures = []
    models = report["models"]
    for identifier in sorted(set(required_models)):
        if identifier not in models:
            failures.append(f"required model {identifier} is absent")
    if maximum_hard_violations < 0:
        raise ValueError("maximum_hard_violations cannot be negative")
    total_violations = sum(
        int(value["hard_violation_count"]) for value in models.values()
    )
    if total_violations > maximum_hard_violations:
        failures.append(
            f"hard violation count {total_violations} exceeds {maximum_hard_violations}"
        )
    if minimum_best_recall is not None:
        if not 0 <= minimum_best_recall <= 1:
            raise ValueError("minimum_best_recall must be in [0, 1]")
        best = max(float(value["recall_at_k"]) for value in models.values())
        if best < minimum_best_recall:
            failures.append(
                f"best recall {best:.6f} is below {minimum_best_recall:.6f}"
            )
    if minimum_best_coverage is not None:
        if not 0 <= minimum_best_coverage <= 1:
            raise ValueError("minimum_best_coverage must be in [0, 1]")
        best = max(float(value["catalog_coverage"]) for value in models.values())
        if best < minimum_best_coverage:
            failures.append(
                f"best catalog coverage {best:.6f} is below {minimum_best_coverage:.6f}"
            )
    return failures


def _serialize_fixture(fixture: dict) -> dict:
    return {
        "items": [asdict(value) for value in fixture["items"]],
        "interactions": [asdict(value) for value in fixture["interactions"]],
        "user_groups": fixture["user_groups"],
        "hard_exclusions": fixture["hard_exclusions"],
        "configuration": fixture["configuration"],
    }


def _load_fixture(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ranking fixture must be an object")
    return {
        "items": [RankingItem(**value) for value in raw["items"]],
        "interactions": [
            RankingInteraction(**value) for value in raw["interactions"]
        ],
        "user_groups": dict(raw["user_groups"]),
        "hard_exclusions": {
            key: list(value) for key, value in raw["hard_exclusions"].items()
        },
        "configuration": dict(raw.get("configuration", {})),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark leakage-safe deterministic ranking baselines"
    )
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--generate-seed", type=int)
    parser.add_argument("--user-count", type=int, default=18)
    parser.add_argument("--item-group-count", type=int, default=3)
    parser.add_argument("--items-per-group", type=int, default=8)
    parser.add_argument("--interactions-per-user", type=int, default=6)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--require-model", action="append", default=[])
    parser.add_argument("--minimum-best-recall", type=float)
    parser.add_argument("--minimum-best-coverage", type=float)
    parser.add_argument("--maximum-hard-violations", type=int, default=0)
    parser.add_argument("--save-fixture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.input is not None and args.generate_seed is not None:
        parser.error("choose an input fixture or --generate-seed, not both")
    if args.input is None and args.generate_seed is None:
        parser.error("provide an input fixture or --generate-seed")

    try:
        fixture = (
            _load_fixture(args.input)
            if args.input is not None
            else generate_ranking_fixture(
                seed=args.generate_seed,
                user_count=args.user_count,
                item_group_count=args.item_group_count,
                items_per_group=args.items_per_group,
                interactions_per_user=args.interactions_per_user,
            )
        )
        report = benchmark_rankers(fixture, k=args.k)
        failures = regression_failures(
            report,
            required_models=args.require_model,
            minimum_best_recall=args.minimum_best_recall,
            minimum_best_coverage=args.minimum_best_coverage,
            maximum_hard_violations=args.maximum_hard_violations,
        )
        report["regression_failures"] = failures
        report["passed"] = not failures
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Ranking benchmark failed: {type(exc).__name__}: {exc}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if args.save_fixture:
        args.save_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.save_fixture.write_text(
            json.dumps(
                _serialize_fixture(fixture),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"output": str(args.output), "passed": not failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
