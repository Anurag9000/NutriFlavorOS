#!/usr/bin/env python3
"""Evaluate forecasting baselines through typed perishable-inventory replay."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from backend.domain.benchmark_fixtures import ForecastInventoryBenchmarkFixture
from backend.research.forecast_baselines import (
    CrostonForecaster,
    DampedHoltForecaster,
    MovingAverageForecaster,
    SeasonalNaiveForecaster,
    SimpleExponentialSmoothingForecaster,
    TSBForecaster,
)
from backend.research.forecast_inventory_pipeline import (
    ForecastInventoryEvaluation,
    compare_forecast_inventory_models,
)


def load_document(path: Path) -> ForecastInventoryBenchmarkFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ForecastInventoryBenchmarkFixture.model_validate(raw)


def _factories(document: ForecastInventoryBenchmarkFixture) -> Dict[str, object]:
    configuration = document.forecast_configuration
    available = {
        "moving_average": lambda: MovingAverageForecaster(
            window=configuration.moving_window
        ),
        "seasonal_naive": lambda: SeasonalNaiveForecaster(
            season_length=configuration.season_length
        ),
        "simple_exponential_smoothing": SimpleExponentialSmoothingForecaster,
        "damped_holt": DampedHoltForecaster,
        "croston_intermittent_demand": CrostonForecaster,
        "tsb_intermittent_demand": TSBForecaster,
    }
    selected = document.models or list(available)
    missing = sorted(set(selected) - set(available))
    if missing:
        raise ValueError(
            "Unknown forecast model identifiers: " + ", ".join(missing)
        )
    return {identifier: available[identifier] for identifier in selected}


def _serialize(value: ForecastInventoryEvaluation) -> dict:
    return {
        "method": value.method,
        "model_id": value.model_id,
        "deterministic": value.deterministic,
        "evaluation_fingerprint": value.evaluation_fingerprint,
        "history": list(value.history),
        "forecast": list(value.forecast),
        "actual": list(value.actual),
        "forecast_metrics": asdict(value.forecast_metrics),
        "replenishment_policy": asdict(value.replenishment_policy),
        "inventory_result": {
            **{
                key: item
                for key, item in asdict(value.inventory_result).items()
                if key not in {"per_sku", "events"}
            },
            "per_sku": [asdict(item) for item in value.inventory_result.per_sku],
            "events": [asdict(item) for item in value.inventory_result.events],
        },
        "warnings": list(value.warnings),
    }


def build_report(path: Path) -> dict:
    document = load_document(path)
    evaluations = compare_forecast_inventory_models(
        factories=_factories(document),
        sku=document.sku,
        history=document.history,
        actual_future=document.actual_future,
        initial_lots=document.initial_lot_domain_values(),
        lead_time_days=document.lead_time_days,
        shelf_life_days=document.shelf_life_days,
        review_period_days=document.review_period_days,
        safety_multiplier=document.safety_multiplier,
    )
    serialized = {
        identifier: _serialize(value)
        for identifier, value in sorted(evaluations.items())
    }
    best_forecast = min(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["forecast_metrics"]["mae"],
            identifier,
        ),
    )
    best_inventory = max(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["inventory_result"]["fill_rate"],
            -serialized[identifier]["inventory_result"]["expired_units"],
            identifier,
        ),
    )
    least_waste = min(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["inventory_result"]["expired_units"],
            -serialized[identifier]["inventory_result"]["fill_rate"],
            identifier,
        ),
    )
    return {
        "protocol_version": "forecast_inventory_closed_loop_v1",
        "sku": document.sku,
        "model_count": len(serialized),
        "models": serialized,
        "best_forecast_by_mae": best_forecast,
        "best_inventory_by_fill_rate": best_inventory,
        "least_waste": least_waste,
        "limitations": [
            "This benchmark is offline and never places runtime purchase orders.",
            "Point forecasts are translated through an explicit fixed safety multiplier rather than a calibrated service-level guarantee.",
            "Forecast, service, and waste leaders are reported separately; no automatic procurement model is selected."
        ],
    }


def regression_failures(
    report: dict,
    *,
    required_models: list[str],
    minimum_best_fill_rate: float | None,
    maximum_least_waste: float | None,
) -> list[str]:
    failures = []
    models = report["models"]
    for identifier in sorted(set(required_models)):
        if identifier not in models:
            failures.append(f"required model {identifier} is absent")
    if minimum_best_fill_rate is not None:
        if not 0 <= minimum_best_fill_rate <= 1:
            raise ValueError("minimum_best_fill_rate must be in [0, 1]")
        identifier = report["best_inventory_by_fill_rate"]
        observed = float(models[identifier]["inventory_result"]["fill_rate"])
        if observed < minimum_best_fill_rate:
            failures.append(
                f"best fill rate {observed:.6f} is below {minimum_best_fill_rate:.6f}"
            )
    if maximum_least_waste is not None:
        if maximum_least_waste < 0:
            raise ValueError("maximum_least_waste cannot be negative")
        identifier = report["least_waste"]
        observed = float(models[identifier]["inventory_result"]["expired_units"])
        if observed > maximum_least_waste:
            failures.append(
                f"least waste {observed:.6f} exceeds {maximum_least_waste:.6f}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare forecast models through perishable inventory replay"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-model", action="append", default=[])
    parser.add_argument("--minimum-best-fill-rate", type=float)
    parser.add_argument("--maximum-least-waste", type=float)
    args = parser.parse_args()

    try:
        report = build_report(args.input)
        failures = regression_failures(
            report,
            required_models=args.require_model,
            minimum_best_fill_rate=args.minimum_best_fill_rate,
            maximum_least_waste=args.maximum_least_waste,
        )
        report["regression_failures"] = failures
        report["passed"] = not failures
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Forecast-inventory evaluation failed: {type(exc).__name__}: {exc}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "passed": not failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
