"""Strict reusable contracts for canonical offline benchmark fixtures."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.research.inventory_simulation import (
    DemandEvent,
    ReorderPolicy,
    SimulationLot,
)


class StrictFixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PlannerOptionFixture(StrictFixtureModel):
    slot: str = Field(min_length=1, max_length=200)
    option_id: str = Field(min_length=1, max_length=300)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)
    cost: float = Field(ge=0)
    taste: float = Field(ge=0, le=1)
    variety: float = Field(ge=0, le=1)
    pantry: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def normalize_identifiers(self):
        self.slot = " ".join(self.slot.strip().split())
        self.option_id = self.option_id.strip()
        if not self.slot or not self.option_id:
            raise ValueError("planner option identifiers cannot be blank")
        return self


class PlannerTargetsFixture(StrictFixtureModel):
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)
    cost_limit: Optional[float] = Field(default=None, ge=0)


class PlannerBenchmarkFixture(StrictFixtureModel):
    options: List[PlannerOptionFixture] = Field(min_length=1, max_length=100000)
    targets: PlannerTargetsFixture

    @model_validator(mode="after")
    def validate_options(self):
        identifiers = [value.option_id for value in self.options]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("planner option_id values must be globally unique")
        slots = {value.slot for value in self.options}
        if not slots:
            raise ValueError("planner fixture must contain at least one slot")
        return self

    def to_problem(self) -> dict:
        return self.model_dump(mode="json")


class SimulationLotFixture(StrictFixtureModel):
    lot_id: str = Field(min_length=1, max_length=300)
    sku: str = Field(min_length=1, max_length=300)
    quantity: float = Field(gt=0)
    expires_day: int = Field(ge=1, le=36500)

    @model_validator(mode="after")
    def normalize_identifiers(self):
        self.lot_id = self.lot_id.strip()
        self.sku = self.sku.strip()
        if not self.lot_id or not self.sku:
            raise ValueError("lot_id and sku cannot be blank")
        return self

    def to_domain(self) -> SimulationLot:
        return SimulationLot(**self.model_dump())


class DemandEventFixture(StrictFixtureModel):
    day: int = Field(ge=0, le=36500)
    sku: str = Field(min_length=1, max_length=300)
    quantity: float = Field(ge=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("demand sku cannot be blank")
        return normalized

    def to_domain(self) -> DemandEvent:
        return DemandEvent(**self.model_dump())


class ReorderPolicyFixture(StrictFixtureModel):
    sku: str = Field(min_length=1, max_length=300)
    reorder_point: float = Field(ge=0)
    order_up_to: float = Field(ge=0)
    lead_time_days: int = Field(ge=1, le=3650)
    shelf_life_days: int = Field(ge=1, le=36500)

    @model_validator(mode="after")
    def validate_policy(self):
        self.sku = self.sku.strip()
        if not self.sku:
            raise ValueError("policy sku cannot be blank")
        if self.order_up_to < self.reorder_point:
            raise ValueError("order_up_to cannot be below reorder_point")
        return self

    def to_domain(self) -> ReorderPolicy:
        return ReorderPolicy(**self.model_dump())


class InventoryBenchmarkFixture(StrictFixtureModel):
    horizon_days: int = Field(ge=1, le=3650)
    initial_lots: List[SimulationLotFixture] = Field(default_factory=list, max_length=100000)
    demand_events: List[DemandEventFixture] = Field(default_factory=list, max_length=1000000)
    policies: List[ReorderPolicyFixture] = Field(default_factory=list, max_length=100000)

    @model_validator(mode="after")
    def validate_document(self):
        lot_ids = [value.lot_id for value in self.initial_lots]
        if len(lot_ids) != len(set(lot_ids)):
            raise ValueError("initial lot_id values must be unique")
        policy_skus = [value.sku for value in self.policies]
        if len(policy_skus) != len(set(policy_skus)):
            raise ValueError("at most one reorder policy is allowed per sku")
        outside = [value.day for value in self.demand_events if value.day >= self.horizon_days]
        if outside:
            raise ValueError("demand events cannot fall outside horizon_days")
        return self


class ForecastConfigurationFixture(StrictFixtureModel):
    season_length: int = Field(default=7, ge=1, le=3650)
    moving_window: int = Field(default=7, ge=1, le=3650)


class ForecastInventoryBenchmarkFixture(StrictFixtureModel):
    sku: str = Field(min_length=1, max_length=300)
    history: List[float] = Field(min_length=1, max_length=100000)
    actual_future: List[float] = Field(min_length=1, max_length=100000)
    initial_lots: List[SimulationLotFixture] = Field(default_factory=list, max_length=100000)
    lead_time_days: int = Field(ge=1, le=3650)
    shelf_life_days: int = Field(ge=1, le=36500)
    review_period_days: int = Field(default=1, ge=1, le=3650)
    safety_multiplier: float = Field(default=1.0, gt=0)
    forecast_configuration: ForecastConfigurationFixture = Field(
        default_factory=ForecastConfigurationFixture
    )
    models: Optional[List[str]] = Field(default=None, min_length=1, max_length=1000)

    @field_validator("history", "actual_future")
    @classmethod
    def nonnegative_series(cls, values: List[float]) -> List[float]:
        if any(value < 0 for value in values):
            raise ValueError("forecast fixture series must be non-negative")
        return values

    @model_validator(mode="after")
    def validate_document(self):
        self.sku = self.sku.strip()
        if not self.sku:
            raise ValueError("sku cannot be blank")
        mismatched = sorted({value.sku for value in self.initial_lots if value.sku != self.sku})
        if mismatched:
            raise ValueError(
                "all initial lots must match the evaluation sku; observed "
                + ", ".join(mismatched)
            )
        required_horizon = self.lead_time_days + self.review_period_days
        if len(self.actual_future) < required_horizon:
            raise ValueError(
                "actual_future must cover lead_time_days + review_period_days"
            )
        if len(self.history) < self.forecast_configuration.season_length:
            raise ValueError("history must contain at least season_length values")
        if self.models is not None:
            normalized = [value.strip() for value in self.models]
            if any(not value for value in normalized):
                raise ValueError("forecast model identifiers cannot be blank")
            if len(normalized) != len(set(normalized)):
                raise ValueError("forecast model identifiers must be unique")
            self.models = normalized
        return self

    def initial_lot_domain_values(self) -> List[SimulationLot]:
        return [value.to_domain() for value in self.initial_lots]
