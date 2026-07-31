#!/usr/bin/env python3
"""Benchmark deterministic demand-forecasting baselines with rolling origins."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Dict, List, Sequence

from backend.research.baselines import CrostonForecaster, MovingAverageForecaster
from backend.research.forecasting_baselines import (
    HoltLinearForecaster,
    SeasonalNaiveForecaster,
    SimpleExponentialSmoothingForecaster,
    TSBForecaster,
    rolling_origin_backtest,
)


Factory = Callable[[], object]


def series_fingerprint(values: Sequence[float]) -> str:
    canonical = json.dumps(
        [float(value) for value in values],
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def generate_series(
    *,
    seed: int,
    length: int,
    season_length: int,
    intermittent_probability: float,
) -> List[float]:
    if length < max(8, season_length * 2):
        raise ValueError("length must cover at least two seasons and eight points")
    if season_length < 1:
        raise ValueError("season_length must be at least 1")
    if not 0 <= intermittent_probability < 1:
        raise ValueError("intermittent_probability must be in [0, 1)")
    rng = random.Random(seed)
    season = [2.0 + 3.0 * (index + 1) / season_length for index in range(season_length)]
    values = []
    for index in range(length):
        trend = 0.025 * index
        noise = rng.uniform(-0.4, 0.4)
        demand = max(0.0, season[index % season_length] + trend + noise)
        if rng.random() < intermittent_probability:
            demand = 0.0
        values.append(round(demand, 6))
    return values


def model_factories(
    *,
    season_length: int,
    moving_window: int,
) -> Dict[str, Factory]:
    return {
        "moving_average": lambda: MovingAverageForecaster(window=moving_window),
        "seasonal_naive": lambda: SeasonalNaiveForecaster(
            season_length=season_length
        ),
        "simple_exponential_smoothing": SimpleExponentialSmoothingForecaster,
        "holt_linear": HoltLinearForecaster,
        "croston": CrostonForecaster,
        "tsb_intermittent_demand": TSBForecaster,
    }


def benchmark_forecasters(
    values: Sequence[float],
    *,
    season_length: int,
    moving_window: int,
    minimum_train_size: int,
    horizon: int,
    step: int,
) -> dict:
    series = [float(value) for value in values]
    if any(not math.isfinite(value) or value < 0 for value in series):
        raise ValueError("demand series must contain finite non-negative values")
    results = {}
    for identifier, factory in sorted(
        model_factories(
            season_length=season_length,
            moving_window=moving_window,
        ).items()
    ):
        try:
            value = rolling_origin_backtest(
                factory,
                series,
                minimum_train_size=minimum_train_size,
                horizon=horizon,
                step=step,
                seasonal_period=season_length,
            )
            results[identifier] = {
                "status": "ok",
                "metrics": {
                    "mae": value.mae,
                    "rmse": value.rmse,
                    "smape": value.smape,
                    "mase": value.mase,
                    "evaluated_points": value.evaluated_points,
                },
                "predictions": list(value.predictions),
                "actuals": list(value.actuals),
                "origins": list(value.origins),
            }
        except (RuntimeError, TypeError, ValueError) as exc:
            results[identifier] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    successful = {
        identifier: value
        for identifier, value in results.items()
        if value["status"] == "ok"
    }
    best = (
        min(
            successful,
            key=lambda identifier: (
                successful[identifier]["metrics"]["mae"],
                successful[identifier]["metrics"]["rmse"],
                identifier,
            ),
        )
        if successful
        else None
    )
    return {
        "protocol_version": "forecast_rolling_origin_v1",
        "series_fingerprint": series_fingerprint(series),
        "series_length": len(series),
        "configuration": {
            "season_length": season_length,
            "moving_window": moving_window,
            "minimum_train_size": minimum_train_size,
            "horizon": horizon,
            "step": step,
        },
        "results": results,
        "successful_model_count": len(successful),
        "best_by_mae": best,
    }


def regression_failures(
    report: dict,
    *,
    require_models: Sequence[str],
    maximum_mae: float | None,
) -> List[str]:
    failures = []
    results = report["results"]
    for identifier in sorted(set(require_models)):
        value = results.get(identifier)
        if value is None:
            failures.append(f"required model {identifier} is not registered")
        elif value["status"] != "ok":
            failures.append(
                f"required model {identifier} failed: {value.get('error', 'unknown error')}"
            )
    if maximum_mae is not None:
        if maximum_mae < 0:
            raise ValueError("maximum_mae cannot be negative")
        best = report.get("best_by_mae")
        if best is None:
            failures.append("no successful forecast model exists")
        else:
            observed = float(results[best]["metrics"]["mae"])
            if observed > maximum_mae:
                failures.append(
                    f"best MAE {observed:.6f} exceeds maximum {maximum_mae:.6f}"
                )
    return failures


def _load_input(path: Path) -> tuple[List[float], dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [float(value) for value in raw], {}
    if not isinstance(raw, dict) or "series" not in raw:
        raise ValueError("input must be a numeric list or an object containing series")
    return [float(value) for value in raw["series"]], dict(raw.get("configuration", {}))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark deterministic forecasting baselines"
    )
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--generate-seed", type=int)
    parser.add_argument("--length", type=int, default=84)
    parser.add_argument("--season-length", type=int, default=7)
    parser.add_argument("--intermittent-probability", type=float, default=0.25)
    parser.add_argument("--moving-window", type=int, default=7)
    parser.add_argument("--minimum-train-size", type=int, default=28)
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--step", type=int, default=7)
    parser.add_argument("--require-model", action="append", default=[])
    parser.add_argument("--maximum-mae", type=float)
    parser.add_argument("--save-series", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.input is not None and args.generate_seed is not None:
        parser.error("choose an input file or --generate-seed, not both")
    if args.input is None and args.generate_seed is None:
        parser.error("provide an input file or --generate-seed")

    try:
        if args.input is not None:
            values, overrides = _load_input(args.input)
        else:
            values = generate_series(
                seed=args.generate_seed,
                length=args.length,
                season_length=args.season_length,
                intermittent_probability=args.intermittent_probability,
            )
            overrides = {}
        configuration = {
            "season_length": int(overrides.get("season_length", args.season_length)),
            "moving_window": int(overrides.get("moving_window", args.moving_window)),
            "minimum_train_size": int(
                overrides.get("minimum_train_size", args.minimum_train_size)
            ),
            "horizon": int(overrides.get("horizon", args.horizon)),
            "step": int(overrides.get("step", args.step)),
        }
        report = benchmark_forecasters(values, **configuration)
        failures = regression_failures(
            report,
            require_models=args.require_model,
            maximum_mae=args.maximum_mae,
        )
        report["regression_failures"] = failures
        report["passed"] = not failures
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Forecast benchmark failed: {type(exc).__name__}: {exc}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if args.save_series:
        args.save_series.parent.mkdir(parents=True, exist_ok=True)
        args.save_series.write_text(
            json.dumps(
                {"series": values, "configuration": configuration},
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
