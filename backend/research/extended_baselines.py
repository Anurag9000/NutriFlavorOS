"""Dependency-light forecasting, ranking, and robust-planning baselines.

All implementations are deterministic and intended for offline evaluation. They
are not production-enabled personalization, procurement, nutrition, or safety
systems.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from itertools import product
from typing import Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from backend.research.baselines import RankedItem
from backend.research.solver_baselines import (
    PlannerOption,
    PlannerTargets,
    SolverResult,
    evaluate_selection,
)


def _series(values: Sequence[float], *, nonnegative: bool = False) -> List[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValueError("values cannot be empty")
    if not all(math.isfinite(value) for value in result):
        raise ValueError("values must be finite")
    if nonnegative and any(value < 0 for value in result):
        raise ValueError("values must be non-negative")
    return result


class SeasonalNaiveForecaster:
    def __init__(self, season_length: int = 7):
        if season_length < 1:
            raise ValueError("season_length must be at least 1")
        self.season_length = season_length
        self._history: List[float] = []

    def fit(self, values: Sequence[float]) -> "SeasonalNaiveForecaster":
        self._history = _series(values)
        if len(self._history) < self.season_length:
            raise ValueError("history must contain at least one complete season")
        return self

    def predict(self, horizon: int) -> List[float]:
        if not self._history:
            raise RuntimeError("Forecaster must be fit before predict")
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        season = self._history[-self.season_length :]
        return [season[index % self.season_length] for index in range(horizon)]


class SimpleExponentialSmoothingForecaster:
    def __init__(self, alpha: float | None = None):
        if alpha is not None and not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self.fitted_alpha_: float | None = None
        self.level_: float | None = None

    @staticmethod
    def _fit_alpha(values: Sequence[float], alpha: float) -> tuple[float, float]:
        level = float(values[0])
        squared_error = 0.0
        for value in values[1:]:
            squared_error += (float(value) - level) ** 2
            level = alpha * float(value) + (1 - alpha) * level
        return level, squared_error

    def fit(self, values: Sequence[float]) -> "SimpleExponentialSmoothingForecaster":
        series = _series(values)
        candidates = [self.alpha] if self.alpha is not None else [value / 20 for value in range(1, 21)]
        scored = [
            (*self._fit_alpha(series, float(alpha)), float(alpha))
            for alpha in candidates
        ]
        level, _error, alpha = min(scored, key=lambda item: (item[1], item[2]))
        self.level_ = level
        self.fitted_alpha_ = alpha
        return self

    def predict(self, horizon: int) -> List[float]:
        if self.level_ is None:
            raise RuntimeError("Forecaster must be fit before predict")
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        return [self.level_] * horizon


class HoltLinearForecaster:
    def __init__(
        self,
        alpha: float = 0.3,
        beta: float = 0.1,
        damping: float = 1.0,
        nonnegative: bool = True,
    ):
        if not 0 < alpha <= 1 or not 0 < beta <= 1:
            raise ValueError("alpha and beta must be in (0, 1]")
        if not 0 < damping <= 1:
            raise ValueError("damping must be in (0, 1]")
        self.alpha = alpha
        self.beta = beta
        self.damping = damping
        self.nonnegative = nonnegative
        self.level_: float | None = None
        self.trend_: float | None = None

    def fit(self, values: Sequence[float]) -> "HoltLinearForecaster":
        series = _series(values, nonnegative=self.nonnegative)
        level = series[0]
        trend = series[1] - series[0] if len(series) > 1 else 0.0
        for value in series[1:]:
            previous_level = level
            level = self.alpha * value + (1 - self.alpha) * (level + self.damping * trend)
            trend = self.beta * (level - previous_level) + (1 - self.beta) * self.damping * trend
        self.level_ = level
        self.trend_ = trend
        return self

    def predict(self, horizon: int) -> List[float]:
        if self.level_ is None or self.trend_ is None:
            raise RuntimeError("Forecaster must be fit before predict")
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        predictions = []
        damping_sum = 0.0
        for step in range(1, horizon + 1):
            damping_sum += self.damping**step
            value = self.level_ + damping_sum * self.trend_
            predictions.append(max(0.0, value) if self.nonnegative else value)
        return predictions


class TSBForecaster:
    """Teunter-Syntetos-Babai intermittent-demand baseline."""

    def __init__(self, alpha: float = 0.1, beta: float = 0.1):
        if not 0 < alpha <= 1 or not 0 < beta <= 1:
            raise ValueError("alpha and beta must be in (0, 1]")
        self.alpha = alpha
        self.beta = beta
        self.probability_: float | None = None
        self.size_: float | None = None

    def fit(self, values: Sequence[float]) -> "TSBForecaster":
        series = _series(values, nonnegative=True)
        first_nonzero = next((value for value in series if value > 0), 0.0)
        probability = 1.0 if series[0] > 0 else 0.0
        size = first_nonzero
        for value in series:
            occurrence = 1.0 if value > 0 else 0.0
            probability = probability + self.beta * (occurrence - probability)
            if occurrence:
                size = size + self.alpha * (value - size)
        self.probability_ = probability
        self.size_ = size
        return self

    def predict(self, horizon: int) -> List[float]:
        if self.probability_ is None or self.size_ is None:
            raise RuntimeError("Forecaster must be fit before predict")
        if horizon < 1:
            raise ValueError("horizon must be at least 1")
        return [self.probability_ * self.size_] * horizon


@dataclass(frozen=True)
class ForecastBacktestResult:
    predictions: Tuple[float, ...]
    actuals: Tuple[float, ...]
    origins: Tuple[int, ...]
    mae: float
    rmse: float
    smape: float
    mase: float | None
    evaluated_points: int


def rolling_origin_backtest(
    factory: Callable[[], object],
    values: Sequence[float],
    *,
    minimum_train_size: int,
    horizon: int = 1,
    step: int = 1,
    seasonal_period: int = 1,
) -> ForecastBacktestResult:
    series = _series(values)
    if minimum_train_size < 2:
        raise ValueError("minimum_train_size must be at least 2")
    if horizon < 1 or step < 1 or seasonal_period < 1:
        raise ValueError("horizon, step, and seasonal_period must be positive")
    if minimum_train_size + horizon > len(series):
        raise ValueError("series is too short for the requested backtest")

    predictions: List[float] = []
    actuals: List[float] = []
    origins: List[int] = []
    for origin in range(minimum_train_size, len(series) - horizon + 1, step):
        model = factory()
        fit = getattr(model, "fit", None)
        predict = getattr(model, "predict", None)
        if not callable(fit) or not callable(predict):
            raise TypeError("factory must produce objects with fit and predict methods")
        fit(series[:origin])
        forecast = [float(value) for value in predict(horizon)]
        if len(forecast) != horizon:
            raise ValueError("forecaster returned the wrong horizon length")
        predictions.extend(forecast)
        actuals.extend(series[origin : origin + horizon])
        origins.extend([origin] * horizon)

    errors = [prediction - actual for prediction, actual in zip(predictions, actuals)]
    mae = sum(abs(value) for value in errors) / len(errors)
    rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
    smape_terms = [
        0.0 if abs(prediction) + abs(actual) == 0 else 2 * abs(prediction - actual) / (abs(prediction) + abs(actual))
        for prediction, actual in zip(predictions, actuals)
    ]
    smape = sum(smape_terms) / len(smape_terms)
    naive_errors = [
        abs(series[index] - series[index - seasonal_period])
        for index in range(seasonal_period, minimum_train_size)
    ]
    scale = sum(naive_errors) / len(naive_errors) if naive_errors else 0.0
    mase = None if scale <= 1e-12 else mae / scale
    return ForecastBacktestResult(
        predictions=tuple(predictions),
        actuals=tuple(actuals),
        origins=tuple(origins),
        mae=mae,
        rmse=rmse,
        smape=smape,
        mase=mase,
        evaluated_points=len(errors),
    )


class BayesianPopularityRecommender:
    """Beta-Bernoulli smoothed popularity for binary positive feedback."""

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        if prior_alpha <= 0 or prior_beta <= 0:
            raise ValueError("prior parameters must be positive")
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self._positive: Counter[str] = Counter()
        self._total: Counter[str] = Counter()

    def fit(self, events: Iterable[Tuple[str, bool]]) -> "BayesianPopularityRecommender":
        self._positive.clear()
        self._total.clear()
        for item_id, positive in events:
            identifier = str(item_id)
            self._total[identifier] += 1
            if bool(positive):
                self._positive[identifier] += 1
        return self

    def rank(self, candidates: Iterable[str], k: int = 10) -> List[RankedItem]:
        if k < 1:
            raise ValueError("k must be at least 1")
        values = []
        for candidate in candidates:
            identifier = str(candidate)
            score = (
                self.prior_alpha + self._positive[identifier]
            ) / (
                self.prior_alpha
                + self.prior_beta
                + self._total[identifier]
            )
            values.append(RankedItem(identifier, float(score)))
        return sorted(values, key=lambda value: (-value.score, value.item_id))[:k]


class ItemKNNRecommender:
    """Deterministic cosine item-kNN over implicit user-item interactions."""

    def __init__(self, neighbors: int = 20):
        if neighbors < 1:
            raise ValueError("neighbors must be at least 1")
        self.neighbors = neighbors
        self._users_by_item: Dict[str, set[str]] = {}
        self._items_by_user: Dict[str, set[str]] = {}
        self._similarities: Dict[str, List[Tuple[str, float]]] = {}

    def fit(self, interactions: Iterable[Tuple[str, str]]) -> "ItemKNNRecommender":
        users_by_item: Dict[str, set[str]] = defaultdict(set)
        items_by_user: Dict[str, set[str]] = defaultdict(set)
        for user_id, item_id in interactions:
            user = str(user_id)
            item = str(item_id)
            users_by_item[item].add(user)
            items_by_user[user].add(item)
        if not users_by_item:
            raise ValueError("at least one interaction is required")
        items = sorted(users_by_item)
        similarities: Dict[str, List[Tuple[str, float]]] = {}
        for item in items:
            scored = []
            left = users_by_item[item]
            for other in items:
                if other == item:
                    continue
                right = users_by_item[other]
                denominator = math.sqrt(len(left) * len(right))
                score = len(left & right) / denominator if denominator else 0.0
                if score > 0:
                    scored.append((other, score))
            similarities[item] = sorted(scored, key=lambda value: (-value[1], value[0]))[: self.neighbors]
        self._users_by_item = dict(users_by_item)
        self._items_by_user = dict(items_by_user)
        self._similarities = similarities
        return self

    def recommend(self, user_id: str, candidates: Iterable[str] | None = None, k: int = 10) -> List[RankedItem]:
        if not self._similarities:
            raise RuntimeError("Recommender must be fit before recommend")
        if k < 1:
            raise ValueError("k must be at least 1")
        seen = self._items_by_user.get(str(user_id), set())
        allowed = set(str(value) for value in candidates) if candidates is not None else set(self._users_by_item)
        scores: Dict[str, float] = defaultdict(float)
        for item in seen:
            for neighbor, similarity in self._similarities.get(item, []):
                if neighbor not in seen and neighbor in allowed:
                    scores[neighbor] += similarity
        values = [RankedItem(item, score) for item, score in scores.items()]
        return sorted(values, key=lambda value: (-value.score, value.item_id))[:k]


class MMRDiversityReranker:
    """Maximal marginal relevance reranking with explicit feature vectors."""

    def __init__(self, relevance_weight: float = 0.7):
        if not 0 <= relevance_weight <= 1:
            raise ValueError("relevance_weight must be in [0, 1]")
        self.relevance_weight = relevance_weight

    @staticmethod
    def _cosine(left: np.ndarray, right: np.ndarray) -> float:
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        return 0.0 if denominator <= 0 else float(np.dot(left, right) / denominator)

    def rerank(
        self,
        relevance: Mapping[str, float],
        features: Mapping[str, Sequence[float]],
        k: int = 10,
    ) -> List[RankedItem]:
        if k < 1:
            raise ValueError("k must be at least 1")
        identifiers = sorted(set(relevance) & set(features))
        if not identifiers:
            return []
        vectors = {identifier: np.asarray(features[identifier], dtype=float) for identifier in identifiers}
        dimensions = {value.shape for value in vectors.values()}
        if len(dimensions) != 1 or next(iter(dimensions))[0] == 0:
            raise ValueError("all feature vectors must be non-empty and have equal shape")
        selected: List[str] = []
        while identifiers and len(selected) < k:
            candidates = []
            for identifier in identifiers:
                redundancy = max(
                    (self._cosine(vectors[identifier], vectors[chosen]) for chosen in selected),
                    default=0.0,
                )
                score = (
                    self.relevance_weight * float(relevance[identifier])
                    - (1 - self.relevance_weight) * redundancy
                )
                candidates.append((score, identifier))
            score, chosen = max(candidates, key=lambda value: (value[0], tuple(reversed(value[1]))))
            selected.append(chosen)
            identifiers.remove(chosen)
        return [
            RankedItem(identifier, float(
                self.relevance_weight * float(relevance[identifier])
                - (1 - self.relevance_weight) * max(
                    (
                        self._cosine(vectors[identifier], vectors[previous])
                        for previous in selected[:index]
                    ),
                    default=0.0,
                )
            ))
            for index, identifier in enumerate(selected)
        ]


@dataclass(frozen=True)
class PlannerScenario:
    scenario_id: str
    calories_multiplier: float = 1.0
    protein_multiplier: float = 1.0
    carbs_multiplier: float = 1.0
    fat_multiplier: float = 1.0
    cost_multiplier: float = 1.0
    taste_offset: float = 0.0
    variety_offset: float = 0.0
    pantry_offset: float = 0.0

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id cannot be blank")
        for field in (
            "calories_multiplier",
            "protein_multiplier",
            "carbs_multiplier",
            "fat_multiplier",
            "cost_multiplier",
        ):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")


def _scenario_option(value: PlannerOption, scenario: PlannerScenario) -> PlannerOption:
    return replace(
        value,
        calories=value.calories * scenario.calories_multiplier,
        protein=value.protein * scenario.protein_multiplier,
        carbs=value.carbs * scenario.carbs_multiplier,
        fat=value.fat * scenario.fat_multiplier,
        cost=value.cost * scenario.cost_multiplier,
        taste=max(0.0, min(1.0, value.taste + scenario.taste_offset)),
        variety=max(0.0, min(1.0, value.variety + scenario.variety_offset)),
        pantry=max(0.0, min(1.0, value.pantry + scenario.pantry_offset)),
    )


def stress_test_selection(
    selected: Sequence[PlannerOption],
    targets: PlannerTargets,
    scenarios: Sequence[PlannerScenario],
) -> Dict[str, object]:
    if not selected:
        raise ValueError("selected cannot be empty")
    if not scenarios:
        raise ValueError("scenarios cannot be empty")
    results = []
    for scenario in sorted(scenarios, key=lambda value: value.scenario_id):
        transformed = [_scenario_option(value, scenario) for value in selected]
        objective, metrics = evaluate_selection(transformed, targets)
        cost_violation = max(
            0.0,
            metrics["cost"] - targets.cost_limit,
        ) if targets.cost_limit is not None else 0.0
        results.append(
            {
                "scenario_id": scenario.scenario_id,
                "objective": objective,
                "metrics": metrics,
                "cost_violation": cost_violation,
            }
        )
    objectives = [float(value["objective"]) for value in results]
    return {
        "scenarios": results,
        "worst_objective": min(objectives),
        "mean_objective": sum(objectives) / len(objectives),
        "best_objective": max(objectives),
        "all_cost_feasible": all(float(value["cost_violation"]) <= 1e-9 for value in results),
    }


def robust_pareto_enumeration(
    options: Iterable[PlannerOption],
    targets: PlannerTargets,
    scenarios: Sequence[PlannerScenario],
    *,
    maximum_combinations: int = 250_000,
) -> SolverResult:
    grouped: Dict[str, List[PlannerOption]] = defaultdict(list)
    identifiers = set()
    for value in options:
        if value.option_id in identifiers:
            raise ValueError(f"duplicate option_id: {value.option_id}")
        identifiers.add(value.option_id)
        grouped[value.slot].append(value)
    if not grouped:
        raise ValueError("at least one option is required")
    if not scenarios:
        raise ValueError("at least one scenario is required")
    ordered = [(slot, sorted(values, key=lambda value: value.option_id)) for slot, values in sorted(grouped.items())]
    combinations = math.prod(len(values) for _, values in ordered)
    if combinations > maximum_combinations:
        raise ValueError(
            f"Robust enumeration would inspect {combinations} combinations; limit is {maximum_combinations}"
        )

    feasible = []
    for selection in product(*(values for _, values in ordered)):
        audit = stress_test_selection(selection, targets, scenarios)
        if not audit["all_cost_feasible"]:
            continue
        signature = tuple(value.option_id for value in selection)
        feasible.append(
            (
                float(audit["worst_objective"]),
                float(audit["mean_objective"]),
                signature,
                selection,
                audit,
            )
        )
    if not feasible:
        raise ValueError("No complete selection is feasible in every declared scenario")
    worst, mean, signature, _selection, audit = max(
        feasible,
        key=lambda value: (value[0], value[1], tuple(reversed(value[2]))),
    )
    return SolverResult(
        method="robust_worst_case_enumeration_v1",
        selected_ids=signature,
        objective=round(worst, 8),
        diagnostics={
            "worst_objective": round(worst, 8),
            "mean_objective": round(mean, 8),
            "scenario_count": len(scenarios),
            "combinations_inspected": combinations,
            "robust_feasible_combinations": len(feasible),
            "scenario_fingerprint": str(hash(tuple(
                (
                    value.scenario_id,
                    value.calories_multiplier,
                    value.protein_multiplier,
                    value.carbs_multiplier,
                    value.fat_multiplier,
                    value.cost_multiplier,
                    value.taste_offset,
                    value.variety_offset,
                    value.pantry_offset,
                )
                for value in sorted(scenarios, key=lambda item: item.scenario_id)
            ))),
            "audit": str(audit),
        },
    )
