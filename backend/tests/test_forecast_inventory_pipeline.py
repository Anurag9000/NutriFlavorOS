from __future__ import annotations

import pytest

from backend.research.forecast_inventory_pipeline import (
    compare_forecast_inventory_models,
    evaluate_forecast_inventory_policy,
    forecast_metrics,
    point_forecast_policy,
)
from backend.research.inventory_simulation import SimulationLot


class ConstantForecaster:
    def __init__(self, value: float):
        self.value = value

    def fit(self, values):
        if not values:
            raise ValueError("history required")
        return self

    def predict(self, horizon):
        return [self.value] * horizon


class WrongHorizonForecaster:
    def fit(self, values):
        return self

    def predict(self, horizon):
        return [1]


def test_point_forecast_policy_uses_explicit_lead_and_review_demand():
    policy = point_forecast_policy(
        sku="rice",
        forecast=[1, 2, 3, 4],
        lead_time_days=2,
        review_period_days=1,
        shelf_life_days=10,
        safety_multiplier=1.5,
    )
    assert policy.reorder_point == pytest.approx((1 + 2) * 1.5)
    assert policy.order_up_to == pytest.approx((1 + 2 + 3) * 1.5)
    assert policy.lead_time_days == 2
    with pytest.raises(ValueError, match="cover"):
        point_forecast_policy(
            sku="rice",
            forecast=[1, 2],
            lead_time_days=2,
            review_period_days=1,
            shelf_life_days=10,
        )


def test_forecast_metrics_keep_point_accuracy_separate():
    metrics = forecast_metrics([1, 3, 2], [1, 2, 4])
    assert metrics.mae == pytest.approx(1)
    assert metrics.rmse == pytest.approx((5 / 3) ** 0.5)
    assert metrics.horizon == 3


def test_closed_loop_evaluation_is_deterministic_and_non_mutating():
    initial = [SimulationLot("initial", "milk", 2, expires_day=5)]
    kwargs = {
        "model_id": "constant_one",
        "forecaster_factory": lambda: ConstantForecaster(1),
        "sku": "milk",
        "history": [1, 1, 1, 1],
        "actual_future": [1, 1, 1, 1],
        "initial_lots": initial,
        "lead_time_days": 1,
        "shelf_life_days": 3,
        "review_period_days": 1,
        "safety_multiplier": 1.0,
    }
    first = evaluate_forecast_inventory_policy(**kwargs)
    second = evaluate_forecast_inventory_policy(**kwargs)
    assert first == second
    assert first.method == "forecast_to_fefo_inventory_replay_v1"
    assert first.forecast_metrics.mae == 0
    assert first.inventory_result.method == "deterministic_fefo_reorder_replay_v1"
    assert len(first.evaluation_fingerprint) == 64
    assert initial == [SimulationLot("initial", "milk", 2, expires_day=5)]
    assert any("separate objectives" in value for value in first.warnings)


def test_model_comparison_uses_common_realized_demand_path():
    results = compare_forecast_inventory_models(
        factories={
            "perfect": lambda: ConstantForecaster(1),
            "overforecast": lambda: ConstantForecaster(3),
        },
        sku="yogurt",
        history=[1, 1, 1, 1],
        actual_future=[1, 1, 1, 1],
        initial_lots=[],
        lead_time_days=1,
        shelf_life_days=1,
        review_period_days=1,
    )
    assert set(results) == {"overforecast", "perfect"}
    assert results["perfect"].actual == results["overforecast"].actual
    assert results["perfect"].forecast_metrics.mae == 0
    assert results["overforecast"].forecast_metrics.mae == 2
    assert (
        results["overforecast"].inventory_result.ordered_units
        > results["perfect"].inventory_result.ordered_units
    )
    assert (
        results["overforecast"].inventory_result.expired_units
        >= results["perfect"].inventory_result.expired_units
    )


def test_closed_loop_rejects_wrong_horizon_and_cross_sku_lots():
    with pytest.raises(ValueError, match="wrong horizon"):
        evaluate_forecast_inventory_policy(
            model_id="bad",
            forecaster_factory=WrongHorizonForecaster,
            sku="rice",
            history=[1, 2, 3],
            actual_future=[1, 2, 3],
            initial_lots=[],
            lead_time_days=1,
            shelf_life_days=5,
        )
    with pytest.raises(ValueError, match="match"):
        evaluate_forecast_inventory_policy(
            model_id="bad-lot",
            forecaster_factory=lambda: ConstantForecaster(1),
            sku="rice",
            history=[1, 2, 3],
            actual_future=[1, 2, 3],
            initial_lots=[SimulationLot("milk", "milk", 1, expires_day=5)],
            lead_time_days=1,
            shelf_life_days=5,
        )
