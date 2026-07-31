"""Deterministic offline perishable-inventory replay simulation.

The simulator never mutates household inventory. It evaluates explicit demand,
initial lots, and replenishment policies using first-expire-first-out allocation.
Every assumption is represented in the input and every state transition is
recorded in a reproducible event ledger.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class SimulationLot:
    lot_id: str
    sku: str
    quantity: float
    expires_day: int

    def __post_init__(self) -> None:
        if not self.lot_id.strip() or not self.sku.strip():
            raise ValueError("lot_id and sku cannot be blank")
        if not math.isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("lot quantity must be finite and positive")
        if self.expires_day < 1:
            raise ValueError("expires_day must be at least 1")


@dataclass(frozen=True)
class DemandEvent:
    day: int
    sku: str
    quantity: float

    def __post_init__(self) -> None:
        if self.day < 0:
            raise ValueError("demand day cannot be negative")
        if not self.sku.strip():
            raise ValueError("demand sku cannot be blank")
        if not math.isfinite(self.quantity) or self.quantity < 0:
            raise ValueError("demand quantity must be finite and non-negative")


@dataclass(frozen=True)
class ReorderPolicy:
    sku: str
    reorder_point: float
    order_up_to: float
    lead_time_days: int
    shelf_life_days: int

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ValueError("policy sku cannot be blank")
        for name in ("reorder_point", "order_up_to"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.order_up_to < self.reorder_point:
            raise ValueError("order_up_to cannot be below reorder_point")
        if self.lead_time_days < 1:
            raise ValueError("lead_time_days must be at least 1")
        if self.shelf_life_days < 1:
            raise ValueError("shelf_life_days must be at least 1")


@dataclass(frozen=True)
class InventorySimulationEvent:
    day: int
    event_type: str
    sku: str
    quantity: float
    lot_id: str | None = None
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class SKUInventoryMetrics:
    sku: str
    demand_units: float
    fulfilled_units: float
    stockout_units: float
    expired_units: float
    ordered_units: float
    ending_units: float
    fill_rate: float
    stockout_event_count: int
    order_count: int
    average_on_hand: float


@dataclass(frozen=True)
class InventorySimulationResult:
    method: str
    deterministic: bool
    horizon_days: int
    input_fingerprint: str
    demand_units: float
    fulfilled_units: float
    stockout_units: float
    expired_units: float
    ordered_units: float
    ending_units: float
    fill_rate: float
    demand_service_level: float
    average_on_hand: float
    stockout_event_count: int
    order_count: int
    per_sku: Tuple[SKUInventoryMetrics, ...]
    events: Tuple[InventorySimulationEvent, ...]


@dataclass
class _MutableLot:
    lot_id: str
    sku: str
    quantity: float
    expires_day: int


@dataclass(frozen=True)
class _PendingOrder:
    order_id: str
    sku: str
    quantity: float
    arrival_day: int
    shelf_life_days: int


def simulation_fingerprint(
    initial_lots: Sequence[SimulationLot],
    demand_events: Sequence[DemandEvent],
    policies: Sequence[ReorderPolicy],
    horizon_days: int,
) -> str:
    payload = {
        "horizon_days": horizon_days,
        "initial_lots": [
            asdict(value)
            for value in sorted(
                initial_lots,
                key=lambda item: (item.sku, item.expires_day, item.lot_id),
            )
        ],
        "demand_events": [
            asdict(value)
            for value in sorted(
                demand_events,
                key=lambda item: (item.day, item.sku, item.quantity),
            )
        ],
        "policies": [
            asdict(value)
            for value in sorted(policies, key=lambda item: item.sku)
        ],
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_inputs(
    initial_lots: Sequence[SimulationLot],
    demand_events: Sequence[DemandEvent],
    policies: Sequence[ReorderPolicy],
    horizon_days: int,
) -> None:
    if horizon_days < 1 or horizon_days > 3650:
        raise ValueError("horizon_days must be between 1 and 3650")
    lot_ids = [value.lot_id for value in initial_lots]
    if len(lot_ids) != len(set(lot_ids)):
        raise ValueError("initial lot_id values must be unique")
    policy_skus = [value.sku for value in policies]
    if len(policy_skus) != len(set(policy_skus)):
        raise ValueError("at most one replenishment policy is allowed per sku")
    outside = [value for value in demand_events if value.day >= horizon_days]
    if outside:
        raise ValueError("demand events cannot fall outside the simulation horizon")


def simulate_perishable_inventory(
    initial_lots: Iterable[SimulationLot],
    demand_events: Iterable[DemandEvent],
    policies: Iterable[ReorderPolicy],
    *,
    horizon_days: int,
) -> InventorySimulationResult:
    lots_input = list(initial_lots)
    demand_input = list(demand_events)
    policy_input = list(policies)
    _validate_inputs(lots_input, demand_input, policy_input, horizon_days)
    fingerprint = simulation_fingerprint(
        lots_input,
        demand_input,
        policy_input,
        horizon_days,
    )

    lots: Dict[str, List[_MutableLot]] = {}
    for value in lots_input:
        lots.setdefault(value.sku, []).append(
            _MutableLot(
                lot_id=value.lot_id,
                sku=value.sku,
                quantity=float(value.quantity),
                expires_day=value.expires_day,
            )
        )
    policies_by_sku = {value.sku: value for value in policy_input}
    demands_by_day: Dict[int, List[DemandEvent]] = {}
    for value in demand_input:
        demands_by_day.setdefault(value.day, []).append(value)

    pending: List[_PendingOrder] = []
    events: List[InventorySimulationEvent] = []
    totals: Dict[str, Dict[str, float]] = {}
    stockout_counts: Dict[str, int] = {}
    order_counts: Dict[str, int] = {}
    inventory_area: Dict[str, float] = {}
    known_skus = sorted(
        set(lots) | set(policies_by_sku) | {value.sku for value in demand_input}
    )
    for sku in known_skus:
        totals[sku] = {
            "demand": 0.0,
            "fulfilled": 0.0,
            "stockout": 0.0,
            "expired": 0.0,
            "ordered": 0.0,
        }
        stockout_counts[sku] = 0
        order_counts[sku] = 0
        inventory_area[sku] = 0.0

    for day in range(horizon_days):
        arrivals = sorted(
            [value for value in pending if value.arrival_day == day],
            key=lambda value: (value.sku, value.order_id),
        )
        pending = [value for value in pending if value.arrival_day != day]
        for order in arrivals:
            lot_id = f"{order.order_id}.arrival"
            lot = _MutableLot(
                lot_id=lot_id,
                sku=order.sku,
                quantity=order.quantity,
                expires_day=day + order.shelf_life_days,
            )
            lots.setdefault(order.sku, []).append(lot)
            events.append(
                InventorySimulationEvent(
                    day=day,
                    event_type="arrival",
                    sku=order.sku,
                    quantity=order.quantity,
                    lot_id=lot_id,
                    metadata={"order_id": order.order_id},
                )
            )

        for sku in known_skus:
            survivors = []
            for lot in sorted(
                lots.get(sku, []),
                key=lambda value: (value.expires_day, value.lot_id),
            ):
                if lot.expires_day <= day and lot.quantity > 0:
                    totals[sku]["expired"] += lot.quantity
                    events.append(
                        InventorySimulationEvent(
                            day=day,
                            event_type="expiry",
                            sku=sku,
                            quantity=lot.quantity,
                            lot_id=lot.lot_id,
                        )
                    )
                elif lot.quantity > 1e-12:
                    survivors.append(lot)
            lots[sku] = survivors

        for demand in sorted(
            demands_by_day.get(day, []),
            key=lambda value: (value.sku, value.quantity),
        ):
            sku = demand.sku
            quantity = float(demand.quantity)
            totals[sku]["demand"] += quantity
            remaining = quantity
            for lot in sorted(
                lots.get(sku, []),
                key=lambda value: (value.expires_day, value.lot_id),
            ):
                if remaining <= 1e-12:
                    break
                used = min(lot.quantity, remaining)
                lot.quantity -= used
                remaining -= used
                totals[sku]["fulfilled"] += used
                if used > 0:
                    events.append(
                        InventorySimulationEvent(
                            day=day,
                            event_type="demand_fulfilled",
                            sku=sku,
                            quantity=used,
                            lot_id=lot.lot_id,
                        )
                    )
            lots[sku] = [
                value for value in lots.get(sku, []) if value.quantity > 1e-12
            ]
            if remaining > 1e-12:
                totals[sku]["stockout"] += remaining
                stockout_counts[sku] += 1
                events.append(
                    InventorySimulationEvent(
                        day=day,
                        event_type="stockout",
                        sku=sku,
                        quantity=remaining,
                    )
                )

        for sku, policy in sorted(policies_by_sku.items()):
            on_hand = sum(value.quantity for value in lots.get(sku, []))
            on_order = sum(
                value.quantity for value in pending if value.sku == sku
            )
            inventory_position = on_hand + on_order
            if inventory_position <= policy.reorder_point + 1e-12:
                quantity = max(0.0, policy.order_up_to - inventory_position)
                if quantity > 1e-12:
                    order_counts[sku] += 1
                    order_id = f"order.{sku}.{day}.{order_counts[sku]}"
                    pending.append(
                        _PendingOrder(
                            order_id=order_id,
                            sku=sku,
                            quantity=quantity,
                            arrival_day=day + policy.lead_time_days,
                            shelf_life_days=policy.shelf_life_days,
                        )
                    )
                    totals[sku]["ordered"] += quantity
                    events.append(
                        InventorySimulationEvent(
                            day=day,
                            event_type="order_placed",
                            sku=sku,
                            quantity=quantity,
                            metadata={
                                "order_id": order_id,
                                "arrival_day": day + policy.lead_time_days,
                                "inventory_position": inventory_position,
                            },
                        )
                    )

        for sku in known_skus:
            inventory_area[sku] += sum(
                value.quantity for value in lots.get(sku, [])
            )

    per_sku = []
    for sku in known_skus:
        values = totals[sku]
        ending = sum(value.quantity for value in lots.get(sku, []))
        demand = values["demand"]
        fill_rate = 1.0 if demand <= 1e-12 else values["fulfilled"] / demand
        per_sku.append(
            SKUInventoryMetrics(
                sku=sku,
                demand_units=values["demand"],
                fulfilled_units=values["fulfilled"],
                stockout_units=values["stockout"],
                expired_units=values["expired"],
                ordered_units=values["ordered"],
                ending_units=ending,
                fill_rate=fill_rate,
                stockout_event_count=stockout_counts[sku],
                order_count=order_counts[sku],
                average_on_hand=inventory_area[sku] / horizon_days,
            )
        )

    demand_units = sum(value.demand_units for value in per_sku)
    fulfilled_units = sum(value.fulfilled_units for value in per_sku)
    stockout_events = sum(value.stockout_event_count for value in per_sku)
    demand_event_count = sum(
        1 for value in demand_input if value.quantity > 1e-12
    )
    return InventorySimulationResult(
        method="deterministic_fefo_reorder_replay_v1",
        deterministic=True,
        horizon_days=horizon_days,
        input_fingerprint=fingerprint,
        demand_units=demand_units,
        fulfilled_units=fulfilled_units,
        stockout_units=sum(value.stockout_units for value in per_sku),
        expired_units=sum(value.expired_units for value in per_sku),
        ordered_units=sum(value.ordered_units for value in per_sku),
        ending_units=sum(value.ending_units for value in per_sku),
        fill_rate=1.0 if demand_units <= 1e-12 else fulfilled_units / demand_units,
        demand_service_level=(
            1.0
            if demand_event_count == 0
            else (demand_event_count - stockout_events) / demand_event_count
        ),
        average_on_hand=sum(value.average_on_hand for value in per_sku),
        stockout_event_count=stockout_events,
        order_count=sum(value.order_count for value in per_sku),
        per_sku=tuple(per_sku),
        events=tuple(events),
    )
