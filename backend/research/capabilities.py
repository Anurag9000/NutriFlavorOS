"""Runtime-readable implementation inventory for catalogued research methods."""
from __future__ import annotations
from importlib.util import find_spec
from typing import Dict

IMPLEMENTED_COMPONENTS: Dict[str, dict] = {
    "tfidf_retriever":{"module":"backend.research.baselines","status":"baseline_available","dependency":"core"},
    "bm25_retriever":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "popularity_recommender":{"module":"backend.research.baselines","status":"baseline_available","dependency":"core"},
    "content_recommender":{"module":"backend.research.baselines","status":"baseline_available","dependency":"core"},
    "matrix_factorization":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "linucb":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "thompson_sampling":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "pairwise_btl":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "ingredient_parser_rules":{"module":"backend.domain.ingredients","status":"implemented","dependency":"core"},
    "instruction_dag_rules":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "substitution_graph":{"module":"backend.domain.substitutions","status":"baseline_available","dependency":"core"},
    "beam_weekly_optimizer":{"module":"backend.engines.weekly_optimizer","status":"implemented","dependency":"core"},
    "household_pantry_optimizer":{"module":"backend.engines.household_optimizer","status":"implemented","dependency":"core"},
    "pareto_optimizer":{"module":"backend.research.solver_baselines","status":"baseline_available","dependency":"core"},
    "cp_sat_optimizer":{"module":"backend.research.solver_baselines","status":"baseline_available_if_dependency_installed","dependency":"ortools"},
    "milp_optimizer":{"module":"backend.research.solver_baselines","status":"baseline_available_if_dependency_installed","dependency":"pulp"},
    "moving_average":{"module":"backend.research.baselines","status":"baseline_available","dependency":"core"},
    "croston":{"module":"backend.research.baselines","status":"baseline_available","dependency":"core"},
    "ridge_regression":{"module":"backend.research.baselines","status":"baseline_available","dependency":"core"},
    "mahalanobis_ood":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "conformal_predictor":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
    "survival_expiry":{"module":"backend.research.advanced_baselines","status":"baseline_available","dependency":"core"},
}

def implementation_status() -> Dict[str, dict]:
    result={}
    for identifier,raw in sorted(IMPLEMENTED_COMPONENTS.items()):
        dependency=raw["dependency"]
        installed=True if dependency=="core" else find_spec(dependency) is not None
        result[identifier]={**raw,"dependency_installed":installed,"runtime_enabled":False,"note":"Offline baseline availability is not production enablement."}
    return result
