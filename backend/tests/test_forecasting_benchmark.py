from __future__ import annotations

from scripts.benchmark_forecasters import (
    benchmark_forecasters,
    generate_series,
    regression_failures,
    series_fingerprint,
)


def test_synthetic_series_and_report_are_seed_reproducible():
    first = generate_series(
        seed=17,
        length=56,
        season_length=7,
        intermittent_probability=0.2,
    )
    second = generate_series(
        seed=17,
        length=56,
        season_length=7,
        intermittent_probability=0.2,
    )
    assert first == second
    assert series_fingerprint(first) == series_fingerprint(second)

    report_a = benchmark_forecasters(
        first,
        season_length=7,
        moving_window=7,
        minimum_train_size=28,
        horizon=7,
        step=7,
    )
    report_b = benchmark_forecasters(
        second,
        season_length=7,
        moving_window=7,
        minimum_train_size=28,
        horizon=7,
        step=7,
    )
    assert report_a == report_b
    assert report_a["protocol_version"] == "forecast_rolling_origin_v1"
    assert report_a["successful_model_count"] == 6
    assert report_a["best_by_mae"] in report_a["results"]


def test_benchmark_reports_all_declared_metrics():
    series = [1, 2, 3, 4, 5, 6, 7] * 6
    report = benchmark_forecasters(
        series,
        season_length=7,
        moving_window=7,
        minimum_train_size=21,
        horizon=7,
        step=7,
    )
    for value in report["results"].values():
        assert value["status"] == "ok"
        assert {
            "mae",
            "rmse",
            "smape",
            "mase",
            "evaluated_points",
        } <= set(value["metrics"])


def test_regression_gate_requires_models_and_maximum_mae():
    series = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
    report = benchmark_forecasters(
        series,
        season_length=2,
        moving_window=2,
        minimum_train_size=4,
        horizon=2,
        step=2,
    )
    assert regression_failures(
        report,
        require_models=["seasonal_naive", "tsb_intermittent_demand"],
        maximum_mae=10,
    ) == []
    failures = regression_failures(
        report,
        require_models=["missing-model"],
        maximum_mae=0,
    )
    assert any("not registered" in value for value in failures)


def test_generation_rejects_invalid_configuration():
    try:
        generate_series(
            seed=1,
            length=5,
            season_length=7,
            intermittent_probability=0,
        )
    except ValueError as exc:
        assert "two seasons" in str(exc)
    else:
        raise AssertionError("invalid series configuration was accepted")
