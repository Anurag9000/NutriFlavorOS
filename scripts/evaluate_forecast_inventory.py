#!/usr/bin/env python3
"""Compare forecasting models through a common perishable-inventory replay."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from backend.research.forecast_inventory_pipeline import (
    compare_forecast_inventory_models,
)
from backend.research.inventory_simulation import SimulationLot
from scripts.benchmark_forecasters import model_factories


def _objects(raw: Any, key: str) -> list[dict]:
    values = raw.get(key, [])
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise ValueError(f"{key} must be a list of objects")
    return values


def load_evaluation(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evaluation input must be a JSON object")
    required = {
        "sku",
        "history",
        "actual_future",
        "lead_time_days",
        "shelf_life_days",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError("missing required fields: " + ", ".join(sorted(missing)))
    return raw


def build_report(path: Path) -> dict:
    raw = load_evaluation(path)
    configuration = dict(raw.get("forecast_configuration", {}))
    factories = model_factories(
        season_length=int(configuration.get("season_length", 7)),
        moving_window=int(configuration.get("moving_window", 7)),
    )
    requested = raw.get("models")
    if requested is not None:
        if not isinstance(requested, list) or any(not isinstance(value, str) for value in requested):
            raise ValueError("models must be a list of model identifiers")
        unknown = sorted(set(requested) - set(factories))
        if unknown:
            raise ValueError("unknown forecasting models: " + ", ".join(unknown))
        factories = {identifier: factories[identifier] for identifier in sorted(set(requested))}

    initial_lots = [
        SimulationLot(**value) for value in _objects(raw, "initial_lots")
    ]
    results = compare_forecast_inventory_models(
        factories=factories,
        sku=str(raw["sku"]),
        history=[float(value) for value in raw["history"]],
        actual_future=[float(value) for value in raw["actual_future"]],
        initial_lots=initial_lots,
        lead_time_days=int(raw["lead_time_days"]),
        shelf_life_days=int(raw["shelf_life_days"]),
        review_period_days=int(raw.get("review_period_days", 1)),
        safety_multiplier=float(raw.get("safety_multiplier", 1.0)),
    )
    serialized: Dict[str, dict] = {}
    for identifier, value in results.items():
        payload = asdict(value)
        serialized[identifier] = payload

    best_forecast = min(
        serialized,
        key=lambda identifier: (
            serialized[identifier]["forecast_metrics"]["mae"],
            serialized[identifier]["forecast_metrics"]["rmse"],
            identifier,
        ),
    )
    best_fill_rate = max(
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
            serialized[identifier]["inventory_result"]["stockout_units"],
            identifier,
        ),
    )
    return {
        "protocol_version": "forecast_to_inventory_replay_v1",
        "model_count": len(serialized),
        "models": serialized,
        "best_forecast_by_mae": best_forecast,
        "best_inventory_by_fill_rate": best_fill_rate,
        "least_waste": least_waste,
        "selection_warning": (
            "Forecast, service, and waste leaders are reported separately; no automatic procurement model is selected."
        ),
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
