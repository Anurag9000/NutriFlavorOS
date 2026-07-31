from __future__ import annotations

from scripts.benchmark_rankers import (
    benchmark_rankers,
    generate_ranking_fixture,
    regression_failures,
)


def test_seeded_ranking_fixture_and_report_are_reproducible():
    first_fixture = generate_ranking_fixture(
        seed=17,
        user_count=12,
        item_group_count=3,
        items_per_group=8,
        interactions_per_user=6,
    )
    second_fixture = generate_ranking_fixture(
        seed=17,
        user_count=12,
        item_group_count=3,
        items_per_group=8,
        interactions_per_user=6,
    )
    first = benchmark_rankers(first_fixture, k=5)
    second = benchmark_rankers(second_fixture, k=5)
    assert first == second
    assert first["protocol_version"] == "temporal_ranking_diversity_v1"
    assert len(first["fixture_fingerprint"]) == 64
    assert first["split"]["strategy"] == "per_user_temporal_leave_last_out"
    assert set(first["models"]) == {
        "popularity_recommender",
        "bayesian_popularity_recommender",
        "item_knn_recommender",
        "mmr_diversity_reranker",
    }
    assert first["accuracy_leader"] in first["models"]
    assert first["diversity_leader"] in first["models"]
    assert first["coverage_leader"] in first["models"]
    assert all(
        value["hard_violation_count"] == 0
        for value in first["models"].values()
    )


def test_ranking_benchmark_reports_group_and_catalog_metrics():
    report = benchmark_rankers(generate_ranking_fixture(seed=3), k=5)
    for value in report["models"].values():
        assert 0 <= value["recall_at_k"] <= 1
        assert 0 <= value["ndcg_at_k"] <= 1
        assert 0 <= value["catalog_coverage"] <= 1
        assert value["mean_novelty"] >= 0
        assert value["mean_intra_list_diversity"] >= 0
        assert value["per_group"]
        assert len(value["recommendation_fingerprint"]) == 64


def test_ranking_regression_gates_require_models_and_no_hard_violations():
    report = benchmark_rankers(generate_ranking_fixture(seed=5), k=5)
    assert regression_failures(
        report,
        required_models=[
            "bayesian_popularity_recommender",
            "item_knn_recommender",
            "mmr_diversity_reranker",
        ],
        minimum_best_recall=0,
        minimum_best_coverage=0,
        maximum_hard_violations=0,
    ) == []
    failures = regression_failures(
        report,
        required_models=["missing-ranker"],
        minimum_best_recall=1,
        minimum_best_coverage=1,
        maximum_hard_violations=0,
    )
    assert any("required model" in value for value in failures)


def test_ranking_fixture_rejects_insufficient_unseen_items():
    try:
        generate_ranking_fixture(
            seed=1,
            user_count=3,
            item_group_count=2,
            items_per_group=3,
            interactions_per_user=3,
        )
    except ValueError as exc:
        assert "unseen holdout" in str(exc)
    else:
        raise AssertionError("invalid ranking fixture was accepted")
