from __future__ import annotations

import json

from scripts.evaluate_forecast_inventory import build_report, regression_failures


def _input(tmp_path):
    path = tmp_path / "forecast-inventory.json"
    path.write_text(
        json.dumps(
            {
                "sku": "rice",
                "history": [1, 2, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 2, 1],
                "actual_future": [1, 2, 1, 2],
                "initial_lots": [
                    {
                        "lot_id": "initial",
                        "sku": "rice",
                        "quantity": 2,
                        "expires_day": 4,
                    }
                ],
                "lead_time_days": 2,
                "review_period_days": 1,
                "shelf_life_days": 10,
                "models": ["moving_average", "seasonal_naive"],
                "forecast_configuration": {
                    "season_length": 7,
                    "moving_window": 7,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_closed_loop_cli_report_keeps_leaders_separate(tmp_path):
    report = build_report(_input(tmp_path))
    assert report["protocol_version"] == "forecast_to_inventory_replay_v1"
    assert report["model_count"] == 2
    assert set(report["models"]) == {"moving_average", "seasonal_naive"}
    assert report["best_forecast_by_mae"] in report["models"]
    assert report["best_inventory_by_fill_rate"] in report["models"]
    assert report["least_waste"] in report["models"]
    assert "no automatic procurement model" in report["selection_warning"]
    for value in report["models"].values():
        assert len(value["evaluation_fingerprint"]) == 64
        assert value["inventory_result"]["method"] == "deterministic_fefo_reorder_replay_v1"


def test_closed_loop_cli_regression_gates(tmp_path):
    report = build_report(_input(tmp_path))
    assert regression_failures(
        report,
        required_models=["moving_average", "seasonal_naive"],
        minimum_best_fill_rate=0,
        maximum_least_waste=100,
    ) == []
    failures = regression_failures(
        report,
        required_models=["missing"],
        minimum_best_fill_rate=1,
        maximum_least_waste=0,
    )
    assert any("required model" in value for value in failures)
