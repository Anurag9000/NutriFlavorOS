#!/usr/bin/env python3
"""Run deterministic perishable-inventory replay simulations from JSON."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, List

from backend.research.inventory_simulation import (
    DemandEvent,
    ReorderPolicy,
    SimulationLot,
    simulate_perishable_inventory,
)


def _list(raw: Any, key: str) -> List[dict]:
    value = raw.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of objects")
    return value


def load_simulation(path: Path) -> tuple[list, list, list, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("simulation input must be a JSON object")
    horizon = int(raw.get("horizon_days", 0))
    lots = [SimulationLot(**value) for value in _list(raw, "initial_lots")]
    demand = [DemandEvent(**value) for value in _list(raw, "demand_events")]
    policies = [ReorderPolicy(**value) for value in _list(raw, "policies")]
    return lots, demand, policies, horizon


def build_report(path: Path) -> dict:
    lots, demand, policies, horizon = load_simulation(path)
    result = simulate_perishable_inventory(
        lots,
        demand,
        policies,
        horizon_days=horizon,
    )
    return {
        **{
            key: value
            for key, value in asdict(result).items()
            if key not in {"per_sku", "events"}
        },
        "per_sku": [asdict(value) for value in result.per_sku],
        "events": [asdict(value) for value in result.events],
        "assumptions": {
            "allocation": "first_expire_first_out",
            "day_order": [
                "arrivals",
                "expiry",
                "demand",
                "reorder_decision",
                "end_of_day_inventory",
            ],
            "expiry_semantics": (
                "a lot with expires_day=d is unavailable from the start of day d"
            ),
            "replenishment": (
                "orders are placed after demand and arrive after the declared positive lead time"
            ),
            "runtime_inventory_mutation": False,
        },
    }


def regression_failures(
    report: dict,
    *,
    minimum_fill_rate: float | None,
    maximum_waste_units: float | None,
    maximum_stockout_units: float | None,
) -> list[str]:
    failures = []
    if minimum_fill_rate is not None:
        if not 0 <= minimum_fill_rate <= 1:
            raise ValueError("minimum_fill_rate must be in [0, 1]")
        if float(report["fill_rate"]) < minimum_fill_rate:
            failures.append(
                f"fill rate {report['fill_rate']:.6f} is below {minimum_fill_rate:.6f}"
            )
    for label, threshold, key in (
        ("waste", maximum_waste_units, "expired_units"),
        ("stockout", maximum_stockout_units, "stockout_units"),
    ):
        if threshold is not None:
            if threshold < 0:
                raise ValueError(f"maximum_{label}_units cannot be negative")
            observed = float(report[key])
            if observed > threshold:
                failures.append(
                    f"{label} units {observed:.6f} exceed {threshold:.6f}"
                )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic perishable inventory simulation"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-fill-rate", type=float)
    parser.add_argument("--maximum-waste-units", type=float)
    parser.add_argument("--maximum-stockout-units", type=float)
    args = parser.parse_args()

    try:
        report = build_report(args.input)
        failures = regression_failures(
            report,
            minimum_fill_rate=args.minimum_fill_rate,
            maximum_waste_units=args.maximum_waste_units,
            maximum_stockout_units=args.maximum_stockout_units,
        )
        report["regression_failures"] = failures
        report["passed"] = not failures
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Inventory simulation failed: {type(exc).__name__}: {exc}")
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
