"""Runtime-verifiable implementation inventory for research methods."""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import Dict


IMPLEMENTED_COMPONENTS: Dict[str, dict] = {
    "tfidf_retriever": {
        "module": "backend.research.baselines",
        "symbol": "TfidfRetriever",
        "status": "baseline_available",
        "dependency": "core",
    },
    "bm25_retriever": {
        "module": "backend.research.advanced_baselines",
        "symbol": "BM25Retriever",
        "status": "baseline_available",
        "dependency": "core",
    },
    "popularity_recommender": {
        "module": "backend.research.baselines",
        "symbol": "PopularityRecommender",
        "status": "baseline_available",
        "dependency": "core",
    },
    "content_recommender": {
        "module": "backend.research.baselines",
        "symbol": "ContentPreferenceRanker",
        "status": "baseline_available",
        "dependency": "core",
    },
    "matrix_factorization": {
        "module": "backend.research.advanced_baselines",
        "symbol": "MatrixFactorizationRecommender",
        "status": "baseline_available",
        "dependency": "core",
    },
    "linucb": {
        "module": "backend.research.advanced_baselines",
        "symbol": "LinUCBPolicy",
        "status": "baseline_available",
        "dependency": "core",
    },
    "thompson_sampling": {
        "module": "backend.research.advanced_baselines",
        "symbol": "BetaBernoulliThompsonPolicy",
        "status": "baseline_available",
        "dependency": "core",
    },
    "pairwise_btl": {
        "module": "backend.research.advanced_baselines",
        "symbol": "BradleyTerryPreference",
        "status": "baseline_available",
        "dependency": "core",
    },
    "ingredient_parser_rules": {
        "module": "backend.domain.ingredients",
        "symbol": "parse_ingredient_line",
        "status": "implemented",
        "dependency": "core",
    },
    "instruction_dag_rules": {
        "module": "backend.research.advanced_baselines",
        "symbol": "InstructionDAGParser",
        "status": "baseline_available",
        "dependency": "core",
    },
    "substitution_graph": {
        "module": "backend.domain.substitutions",
        "symbol": "suggest_substitutions",
        "status": "baseline_available",
        "dependency": "core",
    },
    "beam_weekly_optimizer": {
        "module": "backend.engines.weekly_optimizer",
        "symbol": "WeeklyPlanOptimizer",
        "status": "implemented",
        "dependency": "core",
    },
    "household_pantry_optimizer": {
        "module": "backend.engines.household_optimizer",
        "symbol": "optimize_household_horizon",
        "status": "implemented",
        "dependency": "core",
    },
    "pareto_optimizer": {
        "module": "backend.research.solver_baselines",
        "symbol": "pareto_enumeration",
        "status": "baseline_available",
        "dependency": "core",
    },
    "cp_sat_optimizer": {
        "module": "backend.research.solver_baselines",
        "symbol": "cp_sat_optimize",
        "status": "baseline_available_if_dependency_installed",
        "dependency": "ortools",
    },
    "milp_optimizer": {
        "module": "backend.research.solver_baselines",
        "symbol": "milp_optimize",
        "status": "baseline_available_if_dependency_installed",
        "dependency": "pulp",
    },
    "moving_average": {
        "module": "backend.research.baselines",
        "symbol": "MovingAverageForecaster",
        "status": "baseline_available",
        "dependency": "core",
    },
    "croston": {
        "module": "backend.research.baselines",
        "symbol": "CrostonForecaster",
        "status": "baseline_available",
        "dependency": "core",
    },
    "ridge_regression": {
        "module": "backend.research.baselines",
        "symbol": "RidgeRegressor",
        "status": "baseline_available",
        "dependency": "core",
    },
    "mahalanobis_ood": {
        "module": "backend.research.advanced_baselines",
        "symbol": "MahalanobisOOD",
        "status": "baseline_available",
        "dependency": "core",
    },
    "conformal_predictor": {
        "module": "backend.research.advanced_baselines",
        "symbol": "SplitConformalRegressor",
        "status": "baseline_available",
        "dependency": "core",
    },
    "survival_expiry": {
        "module": "backend.research.advanced_baselines",
        "symbol": "KaplanMeierExpiry",
        "status": "baseline_available",
        "dependency": "core",
    },
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
                implementation_error = "Registered implementation symbol is not callable"
        except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
            implementation_error = f"{type(exc).__name__}: {exc}"

        implementation_valid = module_imported and symbol_present and symbol_callable
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
        if value["dependency"] == "core" and not value["implementation_valid"]
    }
    if broken:
        details = "; ".join(
            f"{identifier}: {value['implementation_error']}"
            for identifier, value in sorted(broken.items())
        )
        raise RuntimeError(f"Broken core research capability registrations: {details}")
