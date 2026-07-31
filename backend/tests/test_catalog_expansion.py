from __future__ import annotations

from backend.research.capabilities import implementation_status
from backend.research.catalog import Readiness, RiskLevel, get_catalog


def test_expanded_catalog_counts_and_version_are_stable():
    catalog = get_catalog()
    assert catalog.version == "2026-08-01.1"
    assert catalog.summary()["tasks"]["total"] == 37
    assert catalog.summary()["datasets"]["total"] == 30
    assert catalog.summary()["models"]["total"] == 72
    assert catalog.summary()["experiments"]["total"] == 28
    assert catalog.summary()["features"]["total"] == 37


def test_new_architecture_families_are_present_with_truthful_readiness():
    catalog = get_catalog()
    models = {value.id: value for value in catalog.models}
    expected = {
        "preparation_resource_scheduler": Readiness.IMPLEMENTED,
        "preparation_profile_compiler": Readiness.IMPLEMENTED,
        "robust_pareto_optimizer": Readiness.BASELINE_AVAILABLE,
        "planner_scenario_stress_test": Readiness.BASELINE_AVAILABLE,
        "seasonal_naive": Readiness.BASELINE_AVAILABLE,
        "simple_exponential_smoothing": Readiness.BASELINE_AVAILABLE,
        "holt_linear": Readiness.BASELINE_AVAILABLE,
        "tsb_intermittent_demand": Readiness.BASELINE_AVAILABLE,
        "rolling_origin_backtest": Readiness.BASELINE_AVAILABLE,
        "bayesian_popularity_recommender": Readiness.BASELINE_AVAILABLE,
        "item_knn_recommender": Readiness.BASELINE_AVAILABLE,
        "mmr_diversity_reranker": Readiness.BASELINE_AVAILABLE,
        "capability_registry_validator": Readiness.IMPLEMENTED,
    }
    for identifier, readiness in expected.items():
        assert models[identifier].readiness == readiness
        assert models[identifier].default_enabled is False


def test_every_runtime_registered_component_has_a_catalog_model():
    catalog_ids = {value.id for value in get_catalog().models}
    status = implementation_status()
    assert set(status) <= catalog_ids
    broken_core = {
        identifier: value["implementation_error"]
        for identifier, value in status.items()
        if value["dependency"] == "core" and not value["implementation_valid"]
    }
    assert broken_core == {}


def test_every_catalogued_implemented_or_baseline_model_is_runtime_registered():
    catalog = get_catalog()
    registered = set(implementation_status())
    missing = {
        value.id
        for value in catalog.models
        if value.readiness in {
            Readiness.IMPLEMENTED,
            Readiness.BASELINE_AVAILABLE,
        }
        and value.id not in registered
    }
    assert missing == set()


def test_high_risk_experiments_require_human_review_and_are_not_defaults():
    catalog = get_catalog()
    for experiment in catalog.experiments:
        assert {"data_provenance", "reproducibility"} <= set(
            experiment.required_gates
        )
        if experiment.risk in {RiskLevel.HIGH, RiskLevel.CLINICAL}:
            assert "human_review" in experiment.required_gates
    for model in catalog.models:
        if model.risk in {RiskLevel.HIGH, RiskLevel.CLINICAL}:
            assert model.default_enabled is False


def test_new_datasets_experiments_and_features_are_connected():
    catalog = get_catalog()
    dataset_ids = {value.id for value in catalog.datasets}
    experiment_ids = {value.id for value in catalog.experiments}
    feature_ids = {value.id for value in catalog.features}

    assert {
        "internal_preparation_profiles",
        "synthetic_demand_series",
        "synthetic_planner_scenarios",
        "synthetic_ranking_interactions",
    } <= dataset_ids
    assert {
        "robust_planner_scenarios",
        "intermittent_demand_benchmark",
        "preparation_scheduler_benchmark",
        "preparation_evidence_coverage",
        "ranking_diversity_benchmark",
        "capability_registry_validation",
    } <= experiment_ids
    assert {
        "preparation_profiles",
        "preparation_task_compilation",
        "dependency_dag_scheduling",
        "robust_scenario_planning",
        "forecast_backtesting",
        "ranking_diversification",
        "runtime_capability_validation",
    } <= feature_ids
