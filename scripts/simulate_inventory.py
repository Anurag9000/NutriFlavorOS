#!/usr/bin/env python3
"""Run deterministic perishable-inventory replay from a typed JSON fixture."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.domain.benchmark_fixtures import InventoryBenchmarkFixture
from backend.research.inventory_simulation import simulate_perishable_inventory


def load_document(path: Path) -> InventoryBenchmarkFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return InventoryBenchmarkFixture.model_validate(raw)


def build_report(path: Path) -> dict:
    document = load_document(path)
    result = simulate_perishable_inventory(
        [value.to_domain() for value in document.initial_lots],
        [value.to_domain() for value in document.demand_events],
        [value.to_domain() for value in document.policies],
        horizon_days=document.horizon_days,
    )
    return {
        "method": result.method,
        "deterministic": result.deterministic,
        "horizon_days": result.horizon_days,
        "input_fingerprint": result.input_fingerprint,
        "demand_units": result.demand_units,
        "fulfilled_units": result.fulfilled_units,
        "stockout_units": result.stockout_units,
        "expired_units": result.expired_units,
        "ordered_units": result.ordered_units,
        "ending_units": result.ending_units,
        "fill_rate": result.fill_rate,
        "demand_service_level": result.demand_service_level,
        "average_on_hand": result.average_on_hand,
        "stockout_event_count": result.stockout_event_count,
        "order_count": result.order_count,
        "per_sku": [asdict(value) for value in result.per_sku],
        "events": [asdict(value) for value in result.events],
        "limitations": [
            "This is an offline deterministic replay and never mutates household inventory.",
            "Demand, lead times, reorder policy, and shelf life are explicit scenario inputs rather than learned guarantees.",
            "Fill rate and waste are reported separately; no automatic procurement policy is selected."
        ],
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
