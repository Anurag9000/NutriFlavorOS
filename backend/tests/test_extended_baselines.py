from __future__ import annotations

import json

import pytest

from backend.research.forecasting_baselines import (
    HoltLinearForecaster,
    SeasonalNaiveForecaster,
    SimpleExponentialSmoothingForecaster,
    TSBForecaster,
    rolling_origin_backtest,
)
from backend.research.item_knn import ItemKNNRecommender
from backend.research.mmr_reranker import MMRDiversityReranker
from backend.research.robust_planning import (
    PlannerScenario,
    robust_pareto_enumeration,
    scenario_fingerprint,
    stress_test_selection,
)
from backend.research.smoothed_popularity import BayesianPopularityRecommender
from backend.research.solver_baselines import PlannerOption, PlannerTargets


def test_seasonal_naive_replays_last_complete_season():
    model = SeasonalNaiveForecaster(season_length=3).fit([1, 2, 3, 4, 5, 6])
    assert model.predict(5) == [4, 5, 6, 4, 5]
    with pytest.raises(ValueError, match="complete season"):
        SeasonalNaiveForecaster(season_length=4).fit([1, 2, 3])


def test_exponential_smoothing_is_deterministic_and_validates_alpha():
    first = SimpleExponentialSmoothingForecaster().fit([2, 3, 4, 5])
    second = SimpleExponentialSmoothingForecaster().fit([2, 3, 4, 5])
    assert first.fitted_alpha_ == second.fitted_alpha_
    assert first.predict(3) == second.predict(3)
    with pytest.raises(ValueError):
        SimpleExponentialSmoothingForecaster(alpha=0)


def test_holt_and_tsb_preserve_nonnegative_demand_contracts():
    holt = HoltLinearForecaster(alpha=0.5, beta=0.5, damping=0.9).fit([2, 4, 6, 8])
    assert all(value >= 0 for value in holt.predict(4))
    with pytest.raises(ValueError, match="non-negative"):
        HoltLinearForecaster().fit([1, -1, 2])

    active = TSBForecaster(alpha=0.2, beta=0.2).fit([0, 5, 0, 0])
    later = TSBForecaster(alpha=0.2, beta=0.2).fit([0, 5, 0, 0, 0, 0])
    assert later.predict(1)[0] < active.predict(1)[0]


def test_rolling_origin_backtest_reports_reproducible_metrics():
    result = rolling_origin_backtest(
        lambda: SeasonalNaiveForecaster(season_length=2),
        [1, 2, 1, 2, 1, 2, 1, 2],
        minimum_train_size=4,
        horizon=2,
        step=2,
        seasonal_period=2,
    )
    assert result.evaluated_points == 4
    assert result.mae == 0
    assert result.rmse == 0
    assert result.smape == 0
    assert result.mase == 0


def test_backtest_rejects_wrong_horizon_and_nonfinite_outputs():
    class WrongLength:
        def fit(self, values):
            return self

        def predict(self, horizon):
            return [1]

    with pytest.raises(ValueError, match="wrong horizon"):
        rolling_origin_backtest(
            WrongLength,
            [1, 2, 3, 4, 5],
            minimum_train_size=3,
            horizon=2,
        )


def test_bayesian_popularity_smooths_low_count_items():
    model = BayesianPopularityRecommender(prior_alpha=1, prior_beta=1).fit(
        [("a", True), ("a", True), ("b", True), ("b", False)]
    )
    ranking = model.rank(["a", "b", "unseen"])
    assert [value.item_id for value in ranking] == ["a", "b", "unseen"]
    assert ranking[0].score == pytest.approx(0.75)
    assert ranking[-1].score == pytest.approx(0.5)


def test_item_knn_recommends_unseen_cooccurring_items_deterministically():
    model = ItemKNNRecommender(neighbors=5).fit(
        [
            ("u1", "a"),
            ("u1", "b"),
            ("u2", "a"),
            ("u2", "c"),
            ("u3", "b"),
            ("u3", "c"),
            ("target", "a"),
        ]
    )
    first = model.recommend("target")
    second = model.recommend("target")
    assert first == second
    assert {value.item_id for value in first} == {"b", "c"}
    assert all(value.item_id != "a" for value in first)


def test_mmr_trades_relevance_for_explicit_diversity():
    reranker = MMRDiversityReranker(relevance_weight=0.5)
    result = reranker.rerank(
        {"a": 1.0, "b": 0.95, "c": 0.8},
        {
            "a": [1.0, 0.0],
            "b": [0.99, 0.01],
            "c": [0.0, 1.0],
        },
        k=2,
    )
    assert [value.item_id for value in result] == ["a", "c"]
    with pytest.raises(ValueError, match="equal size"):
        reranker.rerank({"a": 1, "b": 1}, {"a": [1], "b": [1, 2]})


def planner_options():
    return [
        PlannerOption("breakfast", "a", 400, 20, 50, 12, 4, 0.8, 0.8, 0.8),
        PlannerOption("breakfast", "b", 450, 22, 55, 13, 3, 0.7, 0.7, 0.7),
        PlannerOption("dinner", "c", 600, 35, 65, 20, 6, 0.8, 0.8, 0.8),
        PlannerOption("dinner", "d", 650, 38, 70, 22, 5, 0.7, 0.7, 0.7),
    ]


def scenarios():
    return [
        PlannerScenario("nominal"),
        PlannerScenario("cost-up", cost_multiplier=1.2),
        PlannerScenario("nutrition-down", protein_multiplier=0.9),
    ]


def test_scenario_fingerprint_is_order_invariant_and_sha256():
    first = scenario_fingerprint(scenarios())
    second = scenario_fingerprint(list(reversed(scenarios())))
    assert first == second
    assert len(first) == 64
    int(first, 16)
    with pytest.raises(ValueError, match="unique"):
        scenario_fingerprint([PlannerScenario("same"), PlannerScenario("same")])


def test_stress_audit_and_robust_enumeration_are_deterministic():
    target = PlannerTargets(1000, 55, 115, 32, cost_limit=12)
    selected = [planner_options()[1], planner_options()[3]]
    audit = stress_test_selection(selected, target, scenarios())
    assert audit["scenario_fingerprint"] == scenario_fingerprint(scenarios())
    assert len(audit["scenarios"]) == 3

    first = robust_pareto_enumeration(planner_options(), target, scenarios())
    second = robust_pareto_enumeration(planner_options(), target, list(reversed(scenarios())))
    assert first.selected_ids == second.selected_ids
    assert first.objective == second.objective
    assert first.diagnostics["scenario_fingerprint"] == second.diagnostics["scenario_fingerprint"]
    parsed = json.loads(str(first.diagnostics["audit_json"]))
    assert parsed["all_cost_feasible"] is True


def test_robust_enumeration_rejects_scenario_infeasibility():
    target = PlannerTargets(1000, 55, 115, 32, cost_limit=1)
    with pytest.raises(ValueError, match="feasible in every declared scenario"):
        robust_pareto_enumeration(planner_options(), target, scenarios())
