from __future__ import annotations

import pytest

from backend.research.baselines import RankedItem
from backend.research.ranking_evaluation import (
    RankingInteraction,
    RankingItem,
    evaluate_rankings,
    intra_list_diversity,
    ranking_fixture_fingerprint,
    temporal_leave_last_out,
)


def items():
    return [
        RankingItem("a", (1.0, 0.0), ("group-a",)),
        RankingItem("b", (0.9, 0.1), ("group-a",)),
        RankingItem("c", (0.0, 1.0), ("group-b",)),
        RankingItem("d", (0.1, 0.9), ("group-b",)),
    ]


def interactions():
    return [
        RankingInteraction("u1", "a", 1),
        RankingInteraction("u1", "b", 2),
        RankingInteraction("u2", "c", 1),
        RankingInteraction("u2", "d", 2),
    ]


def test_temporal_leave_last_out_has_no_user_item_leakage():
    split = temporal_leave_last_out(interactions())
    assert split.test_by_user == {"u1": "b", "u2": "d"}
    assert [(value.user_id, value.item_id) for value in split.train] == [
        ("u1", "a"),
        ("u2", "c"),
    ]
    assert not {
        (value.user_id, value.item_id) for value in split.train
    } & set(split.test_by_user.items())


def test_ranking_metrics_report_accuracy_diversity_and_groups():
    split = temporal_leave_last_out(interactions())
    result = evaluate_rankings(
        model_id="fixture",
        recommendations={
            "u1": [RankedItem("b", 1.0), RankedItem("c", 0.5)],
            "u2": [RankedItem("a", 1.0), RankedItem("d", 0.5)],
        },
        split=split,
        items=items(),
        user_groups={"u1": "one", "u2": "two"},
        hard_exclusions={"u1": ["d"], "u2": ["b"]},
        k=2,
    )
    assert result.recall_at_k == 1
    assert result.hit_rate_at_k == 1
    assert result.mrr_at_k == pytest.approx(0.75)
    assert result.ndcg_at_k == pytest.approx(
        (1 + 1 / __import__("math").log2(3)) / 2
    )
    assert result.catalog_coverage == 1
    assert result.hard_violation_count == 0
    assert result.per_group["one"]["recall_at_k"] == 1
    assert result.per_group["two"]["recall_at_k"] == 1
    assert len(result.recommendation_fingerprint) == 64


def test_evaluator_rejects_seen_excluded_unknown_and_duplicate_items():
    split = temporal_leave_last_out(interactions())
    common = {
        "model_id": "bad",
        "split": split,
        "items": items(),
        "user_groups": {},
        "hard_exclusions": {"u1": ["d"], "u2": []},
        "k": 3,
    }
    with pytest.raises(ValueError, match="duplicates"):
        evaluate_rankings(
            recommendations={
                "u1": [RankedItem("b", 1), RankedItem("b", 0.5)],
                "u2": [RankedItem("d", 1)],
            },
            **common,
        )
    with pytest.raises(ValueError, match="unknown"):
        evaluate_rankings(
            recommendations={
                "u1": [RankedItem("unknown", 1)],
                "u2": [RankedItem("d", 1)],
            },
            **common,
        )

    result = evaluate_rankings(
        recommendations={
            "u1": [RankedItem("a", 1), RankedItem("d", 0.5)],
            "u2": [RankedItem("d", 1)],
        },
        **common,
    )
    assert result.hard_violation_count == 2
    assert result.per_user[0].hard_violation_count == 2


def test_relevant_item_must_remain_eligible_after_hard_filter():
    split = temporal_leave_last_out(interactions())
    with pytest.raises(ValueError, match="ineligible"):
        evaluate_rankings(
            model_id="bad-filter",
            recommendations={"u1": [], "u2": []},
            split=split,
            items=items(),
            user_groups={},
            hard_exclusions={"u1": ["b"], "u2": []},
            k=2,
        )


def test_diversity_and_fixture_fingerprint_are_deterministic():
    feature_map = {value.item_id: value.features for value in items()}
    assert intra_list_diversity(["a", "c"], feature_map) == pytest.approx(1)
    first = ranking_fixture_fingerprint(
        items=items(),
        interactions=interactions(),
        user_groups={"u1": "one", "u2": "two"},
        hard_exclusions={"u1": ["d"], "u2": ["b"]},
    )
    second = ranking_fixture_fingerprint(
        items=list(reversed(items())),
        interactions=list(reversed(interactions())),
        user_groups={"u2": "two", "u1": "one"},
        hard_exclusions={"u2": ["b"], "u1": ["d"]},
    )
    assert first == second
    assert len(first) == 64
