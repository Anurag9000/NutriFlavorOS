"""Validated additive extensions for the governed research catalog.

The historical base declaration remains readable. This module reconstructs the
full Pydantic catalog so duplicate IDs, references, feature dependencies, risk
gates, and prohibited defaults are validated on the effective current catalog.
"""

from __future__ import annotations

import backend.research.catalog as base


CURRENT_EXTENDED_VERSION = "2026-08-01.3"
EXPECTED_BASE_VERSION = "2026-08-01.1"


def _append_unique(values: list, value) -> list:
    if value.id in {item.id for item in values}:
        return values
    return [*values, value]


def apply_catalog_extensions() -> None:
    catalog = base.CATALOG
    if catalog.version == CURRENT_EXTENDED_VERSION:
        return
    if catalog.version != EXPECTED_BASE_VERSION:
        raise RuntimeError(
            "Catalog extension expected base version "
            f"{EXPECTED_BASE_VERSION}; observed {catalog.version}"
        )

    exact_scheduler = base.ModelSpec(
        id="exact_preparation_scheduler",
        name="Exact Preparation Scheduler",
        family="exact_scheduling",
        tasks=["preparation_scheduling"],
        readiness=base.Readiness.BASELINE_AVAILABLE,
        risk=base.RiskLevel.MODERATE,
        default_enabled=False,
        prerequisites=[],
        notes=(
            "Bounded aligned-start branch-and-bound comparator; not a "
            "product-scale scheduling claim."
        ),
    )
    inventory_simulator = base.ModelSpec(
        id="fefo_inventory_simulator",
        name="FEFO Perishable Inventory Simulator",
        family="operations_simulation",
        tasks=["inventory_simulation", "demand_forecasting"],
        readiness=base.Readiness.BASELINE_AVAILABLE,
        risk=base.RiskLevel.MODERATE,
        default_enabled=False,
        prerequisites=[],
        notes=(
            "Deterministic offline replay with explicit lots, expiry, demand, "
            "lead times, and reorder rules; never mutates household inventory."
        ),
    )
    forecast_inventory = base.ModelSpec(
        id="forecast_inventory_pipeline",
        name="Forecast to Inventory Evaluation Pipeline",
        family="closed_loop_evaluation",
        tasks=["demand_forecasting", "forecast_backtesting", "inventory_simulation"],
        readiness=base.Readiness.BASELINE_AVAILABLE,
        risk=base.RiskLevel.MODERATE,
        default_enabled=False,
        prerequisites=["fefo_inventory_simulator"],
        notes=(
            "Offline comparison that reports forecast and operational outcomes "
            "separately and never selects a procurement policy automatically."
        ),
    )

    models = list(catalog.models)
    for value in (exact_scheduler, inventory_simulator, forecast_inventory):
        models = _append_unique(models, value)

    experiments = []
    for experiment in catalog.experiments:
        if experiment.id == "preparation_scheduler_benchmark":
            experiment = experiment.model_copy(
                update={
                    "models": sorted(
                        set(experiment.models) | {"exact_preparation_scheduler"}
                    ),
                    "readiness": base.Readiness.BASELINE_AVAILABLE,
                    "primary_metrics": sorted(
                        set(experiment.primary_metrics)
                        | {"optimal_makespan_gap", "exact_search_nodes"}
                    ),
                }
            )
        elif experiment.id == "inventory_simulation_replay":
            experiment = experiment.model_copy(
                update={
                    "models": sorted(
                        set(experiment.models) | {"fefo_inventory_simulator"}
                    ),
                    "readiness": base.Readiness.BASELINE_AVAILABLE,
                    "primary_metrics": sorted(
                        set(experiment.primary_metrics)
                        | {"fill_rate", "expired_units", "stockout_units"}
                    ),
                }
            )
        experiments.append(experiment)

    experiments = _append_unique(
        experiments,
        base.ExperimentSpec(
            id="forecast_inventory_closed_loop",
            name="Forecast Inventory Closed Loop",
            tasks=[
                "demand_forecasting",
                "forecast_backtesting",
                "inventory_simulation",
            ],
            datasets=["synthetic_demand_series", "internal_inventory"],
            models=[
                "seasonal_naive",
                "croston",
                "tsb_intermittent_demand",
                "fefo_inventory_simulator",
                "forecast_inventory_pipeline",
            ],
            split_strategy="fixed historical/future boundary with common realized demand path",
            primary_metrics=[
                "mae",
                "fill_rate",
                "stockout_units",
                "expired_units",
            ],
            readiness=base.Readiness.BASELINE_AVAILABLE,
            risk=base.RiskLevel.MODERATE,
            required_gates=["data_provenance", "reproducibility"],
        ),
    )

    features = []
    for feature in catalog.features:
        if feature.id == "inventory_simulator":
            feature = feature.model_copy(
                update={
                    "readiness": base.Readiness.BASELINE_AVAILABLE,
                    "dependencies": sorted(
                        set(feature.dependencies) | {"fefo_inventory_simulator"}
                    ),
                    "safety_notes": (
                        "Offline non-mutating replay only; not procurement automation."
                    ),
                }
            )
        features.append(feature)
    features = _append_unique(
        features,
        base.FeatureSpec(
            id="exact_preparation_benchmark",
            category="research",
            name="Exact Preparation Benchmark",
            readiness=base.Readiness.BASELINE_AVAILABLE,
            risk=base.RiskLevel.MODERATE,
            dependencies=[
                "exact_preparation_scheduler",
                "preparation_resource_scheduler",
            ],
            safety_notes=(
                "Optimality applies only to bounded aligned-start fixtures and "
                "the configured search budget."
            ),
        ),
    )
    features = _append_unique(
        features,
        base.FeatureSpec(
            id="forecast_inventory_evaluation",
            category="research",
            name="Forecast Inventory Evaluation",
            readiness=base.Readiness.BASELINE_AVAILABLE,
            risk=base.RiskLevel.MODERATE,
            dependencies=[
                "forecast_inventory_pipeline",
                "fefo_inventory_simulator",
                "rolling_origin_backtest",
            ],
            safety_notes=(
                "Forecast, service, stockout, and waste leaders remain separate; "
                "no automatic procurement selection."
            ),
        ),
    )

    base.CATALOG = base.ResearchCatalog(
        version=CURRENT_EXTENDED_VERSION,
        tasks=list(catalog.tasks),
        datasets=list(catalog.datasets),
        models=models,
        experiments=experiments,
        features=features,
    )
