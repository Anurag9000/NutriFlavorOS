"""Deterministic scenario stress testing and worst-case plan enumeration."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from itertools import product
from typing import Dict, Iterable, List, Sequence

from backend.research.solver_baselines import (
    PlannerOption,
    PlannerTargets,
    SolverResult,
    evaluate_selection,
)


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
            value = float(getattr(self, field))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{field} must be finite and positive")
        for field in ("taste_offset", "variety_offset", "pantry_offset"):
            if not math.isfinite(float(getattr(self, field))):
                raise ValueError(f"{field} must be finite")


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


def scenario_fingerprint(scenarios: Sequence[PlannerScenario]) -> str:
    if not scenarios:
        raise ValueError("scenarios cannot be empty")
    identifiers = [value.scenario_id for value in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("scenario_id values must be unique")
    payload = [
        asdict(value)
        for value in sorted(scenarios, key=lambda item: item.scenario_id)
    ]
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def stress_test_selection(
    selected: Sequence[PlannerOption],
    targets: PlannerTargets,
    scenarios: Sequence[PlannerScenario],
) -> Dict[str, object]:
    if not selected:
        raise ValueError("selected cannot be empty")
    fingerprint = scenario_fingerprint(scenarios)
    results = []
    for scenario in sorted(scenarios, key=lambda value: value.scenario_id):
        transformed = [_scenario_option(value, scenario) for value in selected]
        objective, metrics = evaluate_selection(transformed, targets)
        cost_violation = (
            max(0.0, metrics["cost"] - targets.cost_limit)
            if targets.cost_limit is not None
            else 0.0
        )
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
        "scenario_fingerprint": fingerprint,
        "scenarios": results,
        "worst_objective": min(objectives),
        "mean_objective": sum(objectives) / len(objectives),
        "best_objective": max(objectives),
        "all_cost_feasible": all(
            float(value["cost_violation"]) <= 1e-9 for value in results
        ),
    }


def robust_pareto_enumeration(
    options: Iterable[PlannerOption],
    targets: PlannerTargets,
    scenarios: Sequence[PlannerScenario],
    *,
    maximum_combinations: int = 250_000,
) -> SolverResult:
    if maximum_combinations < 1:
        raise ValueError("maximum_combinations must be at least 1")
    scenario_hash = scenario_fingerprint(scenarios)
    grouped: Dict[str, List[PlannerOption]] = defaultdict(list)
    identifiers = set()
    for value in options:
        if value.option_id in identifiers:
            raise ValueError(f"duplicate option_id: {value.option_id}")
        identifiers.add(value.option_id)
        grouped[value.slot].append(value)
    if not grouped:
        raise ValueError("at least one option is required")
    ordered = [
        (slot, sorted(values, key=lambda value: value.option_id))
        for slot, values in sorted(grouped.items())
    ]
    combinations = math.prod(len(values) for _, values in ordered)
    if combinations > maximum_combinations:
        raise ValueError(
            f"Robust enumeration would inspect {combinations} combinations; "
            f"limit is {maximum_combinations}"
        )

    feasible = []
    for selection in product(*(values for _, values in ordered)):
        audit = stress_test_selection(selection, targets, scenarios)
        if not bool(audit["all_cost_feasible"]):
            continue
        signature = tuple(value.option_id for value in selection)
        feasible.append(
            (
                float(audit["worst_objective"]),
                float(audit["mean_objective"]),
                signature,
                audit,
            )
        )
    if not feasible:
        raise ValueError("No complete selection is feasible in every declared scenario")
    worst, mean, signature, audit = sorted(
        feasible,
        key=lambda value: (-value[0], -value[1], value[2]),
    )[0]
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
            "scenario_fingerprint": scenario_hash,
            "audit_json": json.dumps(
                audit,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        },
    )
