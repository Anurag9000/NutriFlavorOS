from __future__ import annotations

import json

from scripts.simulate_inventory import build_report, regression_failures


def test_inventory_simulation_cli_report_is_machine_readable(tmp_path):
    input_path = tmp_path / "simulation.json"
    input_path.write_text(
        json.dumps(
            {
                "horizon_days": 4,
                "initial_lots": [
                    {
                        "lot_id": "start",
                        "sku": "rice",
                        "quantity": 2,
                        "expires_day": 10,
                    }
                ],
                "demand_events": [
                    {"day": 0, "sku": "rice", "quantity": 2},
                    {"day": 1, "sku": "rice", "quantity": 1},
                    {"day": 2, "sku": "rice", "quantity": 3},
                ],
                "policies": [
                    {
                        "sku": "rice",
                        "reorder_point": 1,
                        "order_up_to": 5,
                        "lead_time_days": 2,
                        "shelf_life_days": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    first = build_report(input_path)
    second = build_report(input_path)
    assert first == second
    assert first["method"] == "deterministic_fefo_reorder_replay_v1"
    assert first["assumptions"]["runtime_inventory_mutation"] is False
    assert first["events"][0]["event_type"] == "demand_fulfilled"
    assert len(first["input_fingerprint"]) == 64


def test_inventory_simulation_regression_gates_are_explicit(tmp_path):
    input_path = tmp_path / "simulation.json"
    input_path.write_text(
        json.dumps(
            {
                "horizon_days": 2,
                "initial_lots": [],
                "demand_events": [
                    {"day": 0, "sku": "milk", "quantity": 2}
                ],
                "policies": [],
            }
        ),
        encoding="utf-8",
    )
    report = build_report(input_path)
    failures = regression_failures(
        report,
        minimum_fill_rate=0.9,
        maximum_waste_units=0,
        maximum_stockout_units=0,
    )
    assert any("fill rate" in value for value in failures)
    assert any("stockout units" in value for value in failures)
    assert not any("waste" in value for value in failures)
