"""Closed-loop offline evaluation from demand forecast to inventory outcomes.

The pipeline separates forecast metrics from operational outcomes. It does not
write purchase orders or mutate runtime inventory. All policies and realized
demand paths are explicit and reproducible.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Callable, Dict, List, Sequence

from backend.research.inventory_simulation import (
    DemandEvent,
    InventorySimulationResult,
    ReorderPolicy,
    SimulationLot,
    simulate_perishable_inventory,
)


ForecasterFactory = Callable[[], object]


@dataclass(frozen=True)
class ForecastMetrics:
    mae: float
    rmse: float
    smape: float
    horizon: int


@dataclass(frozen=True)
class ForecastInventoryEvaluation:
    method: str
    model_id: str
    deterministic: bool
    evaluation_fingerprint: str
    history: tuple[float, ...]
    forecast: tuple[float, ...]
    actual: tuple[float, ...]
    forecast_metrics: ForecastMetrics
    replenishment_policy: ReorderPolicy
    inventory_result: InventorySimulationResult
    warnings: tuple[str, ...]


def _nonnegative_series(values: Sequence[float], label: str) -> List[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValueError(f"{label} cannot be empty")
    if any(not math.isfinite(value) or value < 0 for value in result):
        raise ValueError(f"{label} must contain finite non-negative values")
    return result


def point_forecast_policy(
    *,
    sku: str,
    forecast: Sequence[float],
    lead_time_days: int,
    shelf_life_days: int,
    review_period_days: int = 1,
    safety_multiplier: float = 1.0,
) -> ReorderPolicy:
    """Translate an explicit point forecast into a fixed base-stock policy.

    The reorder point covers forecast demand during lead time. The order-up-to
    level additionally covers the review period. No service-level or variance
    claim is inferred from the safety multiplier.
    """

    values = _nonnegative_series(forecast, "forecast")
    if not sku.strip():
        raise ValueError("sku cannot be blank")
    if lead_time_days < 1:
        raise ValueError("lead_time_days must be at least 1")
    if review_period_days < 1:
        raise ValueError("review_period_days must be at least 1")
    if shelf_life_days < 1:
        raise ValueError("shelf_life_days must be at least 1")
    if not math.isfinite(safety_multiplier) or safety_multiplier <= 0:
        raise ValueError("safety_multiplier must be finite and positive")
    required = lead_time_days + review_period_days
    if len(values) < required:
        raise ValueError(
            "forecast horizon must cover lead_time_days + review_period_days"
        )
    reorder_point = sum(values[:lead_time_days]) * safety_multiplier
    order_up_to = sum(values[:required]) * safety_multiplier
    return ReorderPolicy(
        sku=sku,
        reorder_point=reorder_point,
        order_up_to=max(reorder_point, order_up_to),
        lead_time_days=lead_time_days,
        shelf_life_days=shelf_life_days,
    )


def forecast_metrics(
    forecast: Sequence[float],
    actual: Sequence[float],
) -> ForecastMetrics:
    predicted = _nonnegative_series(forecast, "forecast")
    observed = _nonnegative_series(actual, "actual")
    if len(predicted) != len(observed):
        raise ValueError("forecast and actual must have equal length")
    errors = [left - right for left, right in zip(predicted, observed)]
    mae = sum(abs(value) for value in errors) / len(errors)
    rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
    smape = sum(
        0.0
        if abs(left) + abs(right) <= 1e-12
        else 2 * abs(left - right) / (abs(left) + abs(right))
        for left, right in zip(predicted, observed)
    ) / len(errors)
    return ForecastMetrics(mae=mae, rmse=rmse, smape=smape, horizon=len(errors))


def evaluation_fingerprint(
    *,
    model_id: str,
    history: Sequence[float],
    actual: Sequence[float],
    initial_lots: Sequence[SimulationLot],
    lead_time_days: int,
    shelf_life_days: int,
    review_period_days: int,
    safety_multiplier: float,
) -> str:
    payload = {
        "model_id": model_id,
        "history": [float(value) for value in history],
        "actual": [float(value) for value in actual],
        "initial_lots": [
            asdict(value)
            for value in sorted(
                initial_lots,
                key=lambda item: (item.sku, item.expires_day, item.lot_id),
            )
        ],
        "lead_time_days": lead_time_days,
        "shelf_life_days": shelf_life_days,
        "review_period_days": review_period_days,
        "safety_multiplier": safety_multiplier,
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def evaluate_forecast_inventory_policy(
    *,
    model_id: str,
    forecaster_factory: ForecasterFactory,
    sku: str,
    history: Sequence[float],
    actual_future: Sequence[float],
    initial_lots: Sequence[SimulationLot],
    lead_time_days: int,
    shelf_life_days: int,
    review_period_days: int = 1,
    safety_multiplier: float = 1.0,
) -> ForecastInventoryEvaluation:
    history_values = _nonnegative_series(history, "history")
    actual_values = _nonnegative_series(actual_future, "actual_future")
    if not model_id.strip():
        raise ValueError("model_id cannot be blank")
    if any(value.sku != sku for value in initial_lots):
        raise ValueError("all initial lots must match the evaluation sku")

    model = forecaster_factory()
    fit = getattr(model, "fit", None)
    predict = getattr(model, "predict", None)
    if not callable(fit) or not callable(predict):
        raise TypeError("forecaster_factory must return fit/predict objects")
    fit(history_values)
    forecast = [float(value) for value in predict(len(actual_values))]
    forecast = _nonnegative_series(forecast, "model forecast")
    if len(forecast) != len(actual_values):
        raise ValueError("forecaster returned the wrong horizon length")

    policy = point_forecast_policy(
        sku=sku,
        forecast=forecast,
        lead_time_days=lead_time_days,
        shelf_life_days=shelf_life_days,
        review_period_days=review_period_days,
        safety_multiplier=safety_multiplier,
    )
    demand_events = [
        DemandEvent(day=index, sku=sku, quantity=value)
        for index, value in enumerate(actual_values)
    ]
    inventory = simulate_perishable_inventory(
        initial_lots,
        demand_events,
        [policy],
        horizon_days=len(actual_values),
    )
    metrics = forecast_metrics(forecast, actual_values)
    warnings = [
        "Forecast accuracy and inventory outcomes are separate objectives.",
        "The point-forecast safety multiplier is an explicit scenario parameter, not a calibrated service guarantee.",
        "This evaluation is offline and does not create runtime purchase orders.",
    ]
    return ForecastInventoryEvaluation(
        method="forecast_to_fefo_inventory_replay_v1",
        model_id=model_id,
        deterministic=True,
        evaluation_fingerprint=evaluation_fingerprint(
            model_id=model_id,
            history=history_values,
            actual=actual_values,
            initial_lots=initial_lots,
            lead_time_days=lead_time_days,
            shelf_life_days=shelf_life_days,
            review_period_days=review_period_days,
            safety_multiplier=safety_multiplier,
        ),
        history=tuple(history_values),
        forecast=tuple(forecast),
        actual=tuple(actual_values),
        forecast_metrics=metrics,
        replenishment_policy=policy,
        inventory_result=inventory,
        warnings=tuple(warnings),
    )


def compare_forecast_inventory_models(
    *,
    factories: Dict[str, ForecasterFactory],
    sku: str,
    history: Sequence[float],
    actual_future: Sequence[float],
    initial_lots: Sequence[SimulationLot],
    lead_time_days: int,
    shelf_life_days: int,
    review_period_days: int = 1,
    safety_multiplier: float = 1.0,
) -> Dict[str, ForecastInventoryEvaluation]:
    if not factories:
        raise ValueError("at least one forecasting model is required")
    return {
        model_id: evaluate_forecast_inventory_policy(
            model_id=model_id,
            forecaster_factory=factory,
            sku=sku,
            history=history,
            actual_future=actual_future,
            initial_lots=initial_lots,
            lead_time_days=lead_time_days,
            shelf_life_days=shelf_life_days,
            review_period_days=review_period_days,
            safety_multiplier=safety_multiplier,
        )
        for model_id, factory in sorted(factories.items())
    }
