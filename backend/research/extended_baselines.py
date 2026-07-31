"""Compatibility exports for dependency-light extended baselines.

Implementations live in focused modules so forecasting, ranking, diversification,
and robust-planning contracts can be tested and reviewed independently.
"""

from backend.research.forecasting_baselines import (
    ForecastBacktestResult,
    HoltLinearForecaster,
    SeasonalNaiveForecaster,
    SimpleExponentialSmoothingForecaster,
    TSBForecaster,
    rolling_origin_backtest,
)
from backend.research.item_knn import ItemKNNRecommender
from backend.research.mmr_reranker import MMRDiversityReranker
from backend.research.robust_planning import (
    PlannerScenario,
    robust_pareto_enumeration,
    scenario_fingerprint,
    stress_test_selection,
)
from backend.research.smoothed_popularity import BayesianPopularityRecommender


__all__ = [
    "BayesianPopularityRecommender",
    "ForecastBacktestResult",
    "HoltLinearForecaster",
    "ItemKNNRecommender",
    "MMRDiversityReranker",
    "PlannerScenario",
    "SeasonalNaiveForecaster",
    "SimpleExponentialSmoothingForecaster",
    "TSBForecaster",
    "rolling_origin_backtest",
    "robust_pareto_enumeration",
    "scenario_fingerprint",
    "stress_test_selection",
]
