from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from backend.domain.benchmark_fixtures import (
    ForecastInventoryBenchmarkFixture,
    InventoryBenchmarkFixture,
    PlannerBenchmarkFixture,
)


def planner_fixture() -> dict:
    return {
        "options": [
            {
                "slot": "day-1",
                "option_id": "meal-a",
                "calories": 500,
                "protein": 25,
                "carbs": 50,
                "fat": 15,
                "cost": 5,
                "taste": 0.8,
                "variety": 0.7,
                "pantry": 0.6,
            }
        ],
        "targets": {
            "calories": 500,
            "protein": 25,
            "carbs": 50,
            "fat": 15,
            "cost_limit": 6,
        },
    }


def inventory_fixture() -> dict:
    return {
        "horizon_days": 3,
        "initial_lots": [
            {
                "lot_id": "lot-1",
                "sku": "milk",
                "quantity": 2,
                "expires_day": 2,
            }
        ],
        "demand_events": [
            {"day": 0, "sku": "milk", "quantity": 1},
            {"day": 1, "sku": "milk", "quantity": 1},
        ],
        "policies": [
            {
                "sku": "milk",
                "reorder_point": 1,
                "order_up_to": 2,
                "lead_time_days": 1,
                "shelf_life_days": 3,
            }
        ],
    }


def forecast_fixture() -> dict:
    return {
        "sku": "milk",
        "history": [1, 2, 1, 2, 1, 2, 1],
        "actual_future": [1, 1, 2],
        "initial_lots": [
            {
                "lot_id": "lot-1",
                "sku": "milk",
                "quantity": 2,
                "expires_day": 2,
            }
        ],
        "lead_time_days": 1,
        "shelf_life_days": 3,
        "review_period_days": 1,
        "safety_multiplier": 1,
        "forecast_configuration": {
            "season_length": 7,
            "moving_window": 3,
        },
        "models": ["seasonal_naive", "moving_average"],
    }


def test_planner_fixture_rejects_duplicate_ids_nonfinite_and_extra_fields():
    duplicate = planner_fixture()
    duplicate["options"].append(dict(duplicate["options"][0]))
    with pytest.raises(ValidationError, match="globally unique"):
        PlannerBenchmarkFixture.model_validate(duplicate)

    nonfinite = planner_fixture()
    nonfinite["options"][0]["cost"] = math.inf
    with pytest.raises(ValidationError):
        PlannerBenchmarkFixture.model_validate(nonfinite)

    extra = planner_fixture()
    extra["targets"]["fictional_target"] = 1
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PlannerBenchmarkFixture.model_validate(extra)


def test_inventory_fixture_rejects_duplicate_lots_bad_policy_and_outside_demand():
    duplicate = inventory_fixture()
    duplicate["initial_lots"].append(dict(duplicate["initial_lots"][0]))
    with pytest.raises(ValidationError, match="lot_id values must be unique"):
        InventoryBenchmarkFixture.model_validate(duplicate)

    bad_policy = inventory_fixture()
    bad_policy["policies"][0]["order_up_to"] = 0.5
    with pytest.raises(ValidationError, match="order_up_to cannot be below"):
        InventoryBenchmarkFixture.model_validate(bad_policy)

    outside = inventory_fixture()
    outside["demand_events"].append({"day": 3, "sku": "milk", "quantity": 1})
    with pytest.raises(ValidationError, match="outside horizon_days"):
        InventoryBenchmarkFixture.model_validate(outside)


def test_forecast_inventory_fixture_rejects_sku_horizon_history_and_model_drift():
    mismatch = forecast_fixture()
    mismatch["initial_lots"][0]["sku"] = "bread"
    with pytest.raises(ValidationError, match="must match the evaluation sku"):
        ForecastInventoryBenchmarkFixture.model_validate(mismatch)

    short_future = forecast_fixture()
    short_future["lead_time_days"] = 2
    short_future["review_period_days"] = 2
    with pytest.raises(ValidationError, match="must cover lead_time_days"):
        ForecastInventoryBenchmarkFixture.model_validate(short_future)

    short_history = forecast_fixture()
    short_history["history"] = [1, 2]
    with pytest.raises(ValidationError, match="at least season_length"):
        ForecastInventoryBenchmarkFixture.model_validate(short_history)

    duplicate_models = forecast_fixture()
    duplicate_models["models"] = ["seasonal_naive", "seasonal_naive"]
    with pytest.raises(ValidationError, match="must be unique"):
        ForecastInventoryBenchmarkFixture.model_validate(duplicate_models)

    negative = forecast_fixture()
    negative["actual_future"][0] = -1
    with pytest.raises(ValidationError, match="must be non-negative"):
        ForecastInventoryBenchmarkFixture.model_validate(negative)
