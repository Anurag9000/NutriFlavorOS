"""Runtime-verifiable implementation inventory for research methods."""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import Dict


def _component(
    module: str,
    symbol: str,
    *,
    status: str = "baseline_available",
    dependency: str = "core",
) -> dict:
    return {
        "module": module,
        "symbol": symbol,
        "status": status,
        "dependency": dependency,
    }


IMPLEMENTED_COMPONENTS: Dict[str, dict] = {
    "tfidf_retriever": _component(
        "backend.research.baselines", "TfidfRetriever"
    ),
    "bm25_retriever": _component(
        "backend.research.advanced_baselines", "BM25Retriever"
    ),
    "popularity_recommender": _component(
        "backend.research.baselines", "PopularityRecommender"
    ),
    "bayesian_popularity_recommender": _component(
        "backend.research.smoothed_popularity",
        "BayesianPopularityRecommender",
    ),
    "content_recommender": _component(
        "backend.research.baselines", "ContentPreferenceRanker"
    ),
    "item_knn_recommender": _component(
        "backend.research.item_knn", "ItemKNNRecommender"
    ),
    "matrix_factorization": _component(
        "backend.research.advanced_baselines",
        "MatrixFactorizationRecommender",
    ),
    "mmr_diversity_reranker": _component(
        "backend.research.mmr_reranker", "MMRDiversityReranker"
    ),
    "linucb": _component(
        "backend.research.advanced_baselines", "LinUCBPolicy"
    ),
    "thompson_sampling": _component(
        "backend.research.advanced_baselines",
        "BetaBernoulliThompsonPolicy",
    ),
    "pairwise_btl": _component(
        "backend.research.advanced_baselines",
        "BradleyTerryPreference",
    ),
    "ingredient_parser_rules": _component(
        "backend.domain.ingredients",
        "parse_ingredient_line",
        status="implemented",
    ),
    "instruction_dag_rules": _component(
        "backend.research.advanced_baselines", "InstructionDAGParser"
    ),
    "substitution_graph": _component(
        "backend.domain.substitutions", "suggest_substitutions"
    ),
    "beam_weekly_optimizer": _component(
        "backend.engines.weekly_optimizer",
        "WeeklyPlanOptimizer",
        status="implemented",
    ),
    "household_pantry_optimizer": _component(
        "backend.engines.household_optimizer",
        "optimize_household_horizon",
        status="implemented",
    ),
    "preparation_resource_scheduler": _component(
        "backend.engines.prep_resource_scheduler",
        "build_preparation_schedule",
        status="implemented",
    ),
    "preparation_profile_compiler": _component(
        "backend.services.preparation_evidence_service",
        "build_tasks_from_profiles",
        status="implemented",
    ),
    "pareto_optimizer": _component(
        "backend.research.solver_baselines", "pareto_enumeration"
    ),
    "robust_pareto_optimizer": _component(
        "backend.research.robust_planning", "robust_pareto_enumeration"
    ),
    "planner_scenario_stress_test": _component(
        "backend.research.robust_planning", "stress_test_selection"
    ),
    "cp_sat_optimizer": _component(
        "backend.research.solver_baselines",
        "cp_sat_optimize",
        status="baseline_available_if_dependency_installed",
        dependency="ortools",
    ),
    "milp_optimizer": _component(
        "backend.research.solver_baselines",
        "milp_optimize",
        status="baseline_available_if_dependency_installed",
        dependency="pulp",
    ),
    "moving_average": _component(
        "backend.research.baselines", "MovingAverageForecaster"
    ),
    "seasonal_naive": _component(
        "backend.research.forecasting_baselines",
        "SeasonalNaiveForecaster",
    ),
    "simple_exponential_smoothing": _component(
        "backend.research.forecasting_baselines",
        "SimpleExponentialSmoothingForecaster",
    ),
    "holt_linear": _component(
        "backend.research.forecasting_baselines", "HoltLinearForecaster"
    ),
    "croston": _component(
        "backend.research.baselines", "CrostonForecaster"
    ),
    "tsb_intermittent_demand": _component(
        "backend.research.forecasting_baselines", "TSBForecaster"
    ),
    "rolling_origin_backtest": _component(
        "backend.research.forecasting_baselines", "rolling_origin_backtest"
    ),
    "ridge_regression": _component(
        "backend.research.baselines", "RidgeRegressor"
    ),
    "mahalanobis_ood": _component(
        "backend.research.advanced_baselines", "MahalanobisOOD"
    ),
    "conformal_predictor": _component(
        "backend.research.advanced_baselines", "SplitConformalRegressor"
    ),
    "survival_expiry": _component(
        "backend.research.advanced_baselines", "KaplanMeierExpiry"
    ),
}


def _dependency_installed(name: str) -> bool:
    if name == "core":
        return True
    try:
        return find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def implementation_status() -> Dict[str, dict]:
    """Return capability status proven by imports and symbol lookup.

    `runtime_available` means the offline implementation can be imported in the
    current environment. It never means the method is production-enabled,
    trained, accurate, clinically validated, or approved for request-time use.
    """

    result: Dict[str, dict] = {}
    for identifier, raw in sorted(IMPLEMENTED_COMPONENTS.items()):
        dependency = str(raw["dependency"])
        dependency_installed = _dependency_installed(dependency)
        module_imported = False
        symbol_present = False
        symbol_callable = False
        implementation_error = None
        try:
            module = import_module(str(raw["module"]))
            module_imported = True
            symbol = getattr(module, str(raw["symbol"]))
            symbol_present = True
            symbol_callable = callable(symbol)
            if not symbol_callable:
                implementation_error = (
                    "Registered implementation symbol is not callable"
                )
        except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
            implementation_error = f"{type(exc).__name__}: {exc}"

        implementation_valid = (
            module_imported and symbol_present and symbol_callable
        )
        runtime_available = implementation_valid and dependency_installed
        if not implementation_valid:
            observed_status = "broken_registration"
        elif not dependency_installed:
            observed_status = "optional_dependency_missing"
        else:
            observed_status = str(raw["status"])

        result[identifier] = {
            **raw,
            "declared_status": raw["status"],
            "status": observed_status,
            "dependency_installed": dependency_installed,
            "module_imported": module_imported,
            "symbol_present": symbol_present,
            "symbol_callable": symbol_callable,
            "implementation_valid": implementation_valid,
            "runtime_available": runtime_available,
            "runtime_enabled": False,
            "implementation_error": implementation_error,
            "note": (
                "Offline callable availability is not production enablement, "
                "training evidence, benchmark quality, or clinical validation."
            ),
        }
    return result


def assert_core_capabilities_valid() -> None:
    """Fail validation when a declared core implementation is broken."""

    broken = {
        identifier: value
        for identifier, value in implementation_status().items()
        if value["dependency"] == "core"
        and not value["implementation_valid"]
    }
    if broken:
        details = "; ".join(
            f"{identifier}: {value['implementation_error']}"
            for identifier, value in sorted(broken.items())
        )
        raise RuntimeError(
            f"Broken core research capability registrations: {details}"
        )
