"""Deterministic forecasting baselines and rolling-origin evaluation.

These implementations are dependency-light, offline-only comparators. They do
not trigger procurement, inventory changes, or request-time personalization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple


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
        candidates = (
            [float(self.alpha)]
            if self.alpha is not None
            else [value / 20 for value in range(1, 21)]
        )
        scored = [
            (*self._fit_alpha(series, alpha), alpha)
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
            level = self.alpha * value + (1 - self.alpha) * (
                level + self.damping * trend
            )
            trend = self.beta * (level - previous_level) + (
                1 - self.beta
            ) * self.damping * trend
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
            probability += self.beta * (occurrence - probability)
            if occurrence:
                size += self.alpha * (value - size)
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
        if not all(math.isfinite(value) for value in forecast):
            raise ValueError("forecaster returned non-finite values")
        predictions.extend(forecast)
        actuals.extend(series[origin : origin + horizon])
        origins.extend([origin] * horizon)

    errors = [prediction - actual for prediction, actual in zip(predictions, actuals)]
    mae = sum(abs(value) for value in errors) / len(errors)
    rmse = math.sqrt(sum(value * value for value in errors) / len(errors))
    smape_terms = [
        0.0
        if abs(prediction) + abs(actual) == 0
        else 2
        * abs(prediction - actual)
        / (abs(prediction) + abs(actual))
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
