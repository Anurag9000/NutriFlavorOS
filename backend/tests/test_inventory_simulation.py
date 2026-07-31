from __future__ import annotations

import pytest

from backend.research.inventory_simulation import (
    DemandEvent,
    ReorderPolicy,
    SimulationLot,
    simulate_perishable_inventory,
    simulation_fingerprint,
)


def test_fefo_allocation_uses_earliest_expiring_lot_first():
    result = simulate_perishable_inventory(
        [
            SimulationLot("later", "milk", 5, expires_day=5),
            SimulationLot("sooner", "milk", 3, expires_day=2),
        ],
        [DemandEvent(day=0, sku="milk", quantity=4)],
        [],
        horizon_days=3,
    )

    fulfilled = [
        value
        for value in result.events
        if value.event_type == "demand_fulfilled"
    ]
    assert [(value.lot_id, value.quantity) for value in fulfilled] == [
        ("sooner", 3),
        ("later", 1),
    ]
    assert result.fulfilled_units == 4
    assert result.stockout_units == 0
    assert result.ending_units == 4


def test_expiry_waste_is_recorded_before_same_day_demand():
    result = simulate_perishable_inventory(
        [SimulationLot("expires-day-1", "yogurt", 2, expires_day=1)],
        [DemandEvent(day=1, sku="yogurt", quantity=1)],
        [],
        horizon_days=2,
    )

    assert result.expired_units == 2
    assert result.stockout_units == 1
    assert result.fill_rate == 0
    assert [value.event_type for value in result.events] == [
        "expiry",
        "stockout",
    ]


def test_reorder_policy_accounts_for_pending_inventory_and_lead_time():
    result = simulate_perishable_inventory(
        [SimulationLot("start", "rice", 2, expires_day=20)],
        [
            DemandEvent(day=0, sku="rice", quantity=2),
            DemandEvent(day=1, sku="rice", quantity=1),
            DemandEvent(day=2, sku="rice", quantity=3),
        ],
        [
            ReorderPolicy(
                sku="rice",
                reorder_point=1,
                order_up_to=5,
                lead_time_days=2,
                shelf_life_days=10,
            )
        ],
        horizon_days=4,
    )

    orders = [value for value in result.events if value.event_type == "order_placed"]
    arrivals = [value for value in result.events if value.event_type == "arrival"]
    assert len(orders) == 1
    assert orders[0].day == 0
    assert orders[0].quantity == 5
    assert arrivals[0].day == 2
    assert result.ordered_units == 5
    assert result.stockout_units == 1
    assert result.fulfilled_units == 5
    assert result.ending_units == 2


def test_deterministic_replay_and_fingerprint_are_order_invariant():
    lots = [
        SimulationLot("a", "beans", 2, expires_day=4),
        SimulationLot("b", "beans", 3, expires_day=5),
    ]
    demands = [
        DemandEvent(day=1, sku="beans", quantity=2),
        DemandEvent(day=0, sku="beans", quantity=1),
    ]
    policies = [
        ReorderPolicy("beans", 1, 4, lead_time_days=1, shelf_life_days=5)
    ]
    first = simulate_perishable_inventory(
        lots,
        demands,
        policies,
        horizon_days=4,
    )
    second = simulate_perishable_inventory(
        list(reversed(lots)),
        list(reversed(demands)),
        policies,
        horizon_days=4,
    )
    assert first == second
    assert first.input_fingerprint == simulation_fingerprint(
        lots,
        demands,
        policies,
        4,
    )
    assert len(first.input_fingerprint) == 64


def test_service_level_and_per_sku_metrics_are_explicit():
    result = simulate_perishable_inventory(
        [SimulationLot("apple-lot", "apple", 1, expires_day=4)],
        [
            DemandEvent(day=0, sku="apple", quantity=1),
            DemandEvent(day=1, sku="apple", quantity=1),
            DemandEvent(day=1, sku="banana", quantity=2),
        ],
        [],
        horizon_days=3,
    )
    assert result.demand_units == 4
    assert result.fulfilled_units == 1
    assert result.stockout_event_count == 2
    assert result.demand_service_level == pytest.approx(1 / 3)
    by_sku = {value.sku: value for value in result.per_sku}
    assert by_sku["apple"].fill_rate == pytest.approx(0.5)
    assert by_sku["banana"].fill_rate == 0


def test_invalid_inputs_are_rejected_before_simulation():
    with pytest.raises(ValueError, match="unique"):
        simulate_perishable_inventory(
            [
                SimulationLot("same", "rice", 1, 2),
                SimulationLot("same", "rice", 1, 3),
            ],
            [],
            [],
            horizon_days=2,
        )
    with pytest.raises(ValueError, match="outside"):
        simulate_perishable_inventory(
            [],
            [DemandEvent(day=2, sku="rice", quantity=1)],
            [],
            horizon_days=2,
        )
    with pytest.raises(ValueError, match="one replenishment policy"):
        simulate_perishable_inventory(
            [],
            [],
            [
                ReorderPolicy("rice", 1, 2, 1, 5),
                ReorderPolicy("rice", 2, 3, 1, 5),
            ],
            horizon_days=2,
        )
