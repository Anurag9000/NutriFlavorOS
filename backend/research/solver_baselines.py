"""Optional exact and Pareto planner baselines for offline comparison.

The runtime application does not depend on OR-Tools or PuLP. These adapters are
offline research baselines loaded only when their optional dependencies are
installed. The pure-Python Pareto baseline is always available.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Sequence, Tuple


class OptionalSolverUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannerOption:
    slot: str
    option_id: str
    calories: float
    protein: float
    carbs: float
    fat: float
    cost: float
    taste: float
    variety: float
    pantry: float


@dataclass(frozen=True)
class PlannerTargets:
    calories: float
    protein: float
    carbs: float
    fat: float
    cost_limit: float | None = None


@dataclass(frozen=True)
class SolverResult:
    method: str
    selected_ids: Tuple[str, ...]
    objective: float
    diagnostics: Dict[str, float | int | str]


def _closeness(actual: float, target: float) -> float:
    if target <= 0:
        return 1.0 if actual <= 0 else 0.0
    return max(0.0, 1.0 - abs(actual - target) / target)


def evaluate_selection(
    values: Sequence[PlannerOption], targets: PlannerTargets
) -> Tuple[float, Dict[str, float]]:
    calories = sum(value.calories for value in values)
    protein = sum(value.protein for value in values)
    carbs = sum(value.carbs for value in values)
    fat = sum(value.fat for value in values)
    cost = sum(value.cost for value in values)
    taste = sum(value.taste for value in values) / max(1, len(values))
    variety = sum(value.variety for value in values) / max(1, len(values))
    pantry = sum(value.pantry for value in values) / max(1, len(values))
    nutrition = (
        _closeness(calories, targets.calories) * 0.40
        + _closeness(protein, targets.protein) * 0.25
        + _closeness(carbs, targets.carbs) * 0.20
        + _closeness(fat, targets.fat) * 0.15
    )
    cost_penalty = 0.0
    if targets.cost_limit is not None and cost > targets.cost_limit:
        cost_penalty = (cost - targets.cost_limit) / max(1.0, targets.cost_limit)
    objective = (
        nutrition * 0.56
        + taste * 0.18
        + variety * 0.12
        + pantry * 0.10
        - cost_penalty * 0.30
        - cost * 0.001
    )
    return objective, {
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "cost": cost,
        "taste": taste,
        "variety": variety,
        "pantry": pantry,
        "nutrition_match": nutrition,
    }


def _group(options: Iterable[PlannerOption]) -> List[Tuple[str, List[PlannerOption]]]:
    grouped: Dict[str, List[PlannerOption]] = {}
    seen_ids: set[str] = set()
    for value in options:
        if value.option_id in seen_ids:
            raise ValueError(f"duplicate option_id: {value.option_id}")
        seen_ids.add(value.option_id)
        grouped.setdefault(value.slot, []).append(value)
    if not grouped:
        raise ValueError("at least one option is required")
    result = []
    for slot in sorted(grouped):
        values = sorted(grouped[slot], key=lambda item: item.option_id)
        if not values:
            raise ValueError(f"slot {slot} has no options")
        result.append((slot, values))
    return result


def pareto_enumeration(
    options: Iterable[PlannerOption],
    targets: PlannerTargets,
    *,
    maximum_combinations: int = 250_000,
) -> SolverResult:
    """Enumerate bounded problems under the same hard budget as exact solvers."""

    grouped = _group(options)
    combinations = 1
    for _, values in grouped:
        combinations *= len(values)
    if combinations > maximum_combinations:
        raise ValueError(
            f"Pareto enumeration would inspect {combinations} combinations; "
            f"limit is {maximum_combinations}"
        )

    frontier: List[Tuple[Tuple[float, float, float, float], Tuple[PlannerOption, ...]]] = []
    inspected = 0
    feasible = 0
    skipped_budget = 0
    for selection in product(*(values for _, values in grouped)):
        inspected += 1
        objective, metrics = evaluate_selection(selection, targets)
        if (
            targets.cost_limit is not None
            and metrics["cost"] > targets.cost_limit + 1e-9
        ):
            skipped_budget += 1
            continue
        feasible += 1
        vector = (
            metrics["nutrition_match"],
            metrics["taste"],
            metrics["variety"],
            metrics["pantry"] - metrics["cost"] * 0.001,
        )
        dominated = False
        survivors = []
        for old_vector, old_selection in frontier:
            old_dominates = all(a >= b for a, b in zip(old_vector, vector)) and any(
                a > b for a, b in zip(old_vector, vector)
            )
            new_dominates = all(a >= b for a, b in zip(vector, old_vector)) and any(
                a > b for a, b in zip(vector, old_vector)
            )
            if old_dominates:
                dominated = True
                break
            if not new_dominates:
                survivors.append((old_vector, old_selection))
        if not dominated:
            survivors.append((vector, selection))
            frontier = survivors

    if not frontier:
        budget = (
            f" under cost limit {targets.cost_limit}"
            if targets.cost_limit is not None
            else ""
        )
        raise ValueError(f"No complete slot selection is feasible{budget}")

    scored = []
    for _, selection in frontier:
        objective, metrics = evaluate_selection(selection, targets)
        signature = tuple(item.option_id for item in selection)
        scored.append((objective, signature, selection, metrics))
    objective, signature, _selection, metrics = max(
        scored, key=lambda item: (item[0], tuple(reversed(item[1])))
    )
    return SolverResult(
        method="pure_python_pareto_enumeration_v2",
        selected_ids=signature,
        objective=round(objective, 8),
        diagnostics={
            **{key: round(value, 8) for key, value in metrics.items()},
            "combinations_inspected": inspected,
            "feasible_combinations": feasible,
            "budget_infeasible_combinations": skipped_budget,
            "pareto_frontier_size": len(frontier),
        },
    )


def cp_sat_optimize(
    options: Iterable[PlannerOption],
    targets: PlannerTargets,
    *,
    time_limit_seconds: float = 30.0,
) -> SolverResult:
    try:
        from ortools.sat.python import cp_model
    except ImportError as exc:
        raise OptionalSolverUnavailable(
            "Install backend/requirements-research.txt to run the CP-SAT baseline"
        ) from exc

    grouped = _group(options)
    flat = [value for _, values in grouped for value in values]
    model = cp_model.CpModel()
    variables = {
        value.option_id: model.new_bool_var(f"select_{index}")
        for index, value in enumerate(flat)
    }
    for _slot, values in grouped:
        model.add_exactly_one(variables[value.option_id] for value in values)

    scale = 1000
    if targets.cost_limit is not None:
        model.add(
            sum(round(value.cost * scale) * variables[value.option_id] for value in flat)
            <= round(targets.cost_limit * scale)
        )

    totals = {}
    for name in ("calories", "protein", "carbs", "fat"):
        totals[name] = sum(
            round(getattr(value, name) * scale) * variables[value.option_id]
            for value in flat
        )
    target_values = {
        "calories": targets.calories,
        "protein": targets.protein,
        "carbs": targets.carbs,
        "fat": targets.fat,
    }
    deviations = {}
    upper = max(10**9, sum(round(value.calories * scale) for value in flat))
    for name, expression in totals.items():
        deviation = model.new_int_var(0, upper, f"{name}_absolute_deviation")
        model.add_abs_equality(
            deviation, expression - round(target_values[name] * scale)
        )
        deviations[name] = deviation

    benefits = sum(
        round(
            (
                value.taste * 0.35
                + value.variety * 0.25
                + value.pantry * 0.25
                - value.cost * 0.005
            )
            * scale
        )
        * variables[value.option_id]
        for value in flat
    )
    deviation_penalty = (
        deviations["calories"] * 4
        + deviations["protein"] * 3
        + deviations["carbs"] * 2
        + deviations["fat"] * 2
    )
    model.maximize(benefits * scale - deviation_penalty)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, time_limit_seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(f"CP-SAT did not find a feasible plan; status={status}")

    selected = tuple(
        value for value in flat if solver.value(variables[value.option_id]) == 1
    )
    objective, metrics = evaluate_selection(selected, targets)
    return SolverResult(
        method="ortools_cp_sat_v1",
        selected_ids=tuple(value.option_id for value in selected),
        objective=round(objective, 8),
        diagnostics={
            **{key: round(value, 8) for key, value in metrics.items()},
            "solver_status": int(status),
            "wall_time_seconds": round(solver.wall_time, 6),
        },
    )


def milp_optimize(
    options: Iterable[PlannerOption],
    targets: PlannerTargets,
) -> SolverResult:
    try:
        import pulp
    except ImportError as exc:
        raise OptionalSolverUnavailable(
            "Install backend/requirements-research.txt to run the MILP baseline"
        ) from exc

    grouped = _group(options)
    flat = [value for _, values in grouped for value in values]
    problem = pulp.LpProblem("nutriflavos_weekly_plan", pulp.LpMaximize)
    variables = {
        value.option_id: pulp.LpVariable(
            f"select_{index}", lowBound=0, upBound=1, cat=pulp.LpBinary
        )
        for index, value in enumerate(flat)
    }
    for slot, values in grouped:
        problem += (
            pulp.lpSum(variables[value.option_id] for value in values) == 1,
            f"one_{slot}",
        )
    if targets.cost_limit is not None:
        problem += (
            pulp.lpSum(value.cost * variables[value.option_id] for value in flat)
            <= targets.cost_limit,
            "cost_limit",
        )

    deviations = {}
    for name, target in (
        ("calories", targets.calories),
        ("protein", targets.protein),
        ("carbs", targets.carbs),
        ("fat", targets.fat),
    ):
        positive = pulp.LpVariable(f"{name}_dev_pos", lowBound=0)
        negative = pulp.LpVariable(f"{name}_dev_neg", lowBound=0)
        total = pulp.lpSum(
            getattr(value, name) * variables[value.option_id] for value in flat
        )
        problem += total - target == positive - negative
        deviations[name] = positive + negative

    benefits = pulp.lpSum(
        (
            value.taste * 0.35
            + value.variety * 0.25
            + value.pantry * 0.25
            - value.cost * 0.005
        )
        * variables[value.option_id]
        for value in flat
    )
    penalties = (
        deviations["calories"] / max(1.0, targets.calories) * 0.40
        + deviations["protein"] / max(1.0, targets.protein) * 0.25
        + deviations["carbs"] / max(1.0, targets.carbs) * 0.20
        + deviations["fat"] / max(1.0, targets.fat) * 0.15
    )
    problem += benefits - penalties
    status = problem.solve(pulp.PULP_CBC_CMD(msg=False, threads=1))
    if pulp.LpStatus[status] not in {"Optimal", "Feasible"}:
        raise ValueError(f"MILP did not find a feasible plan: {pulp.LpStatus[status]}")

    selected = tuple(
        value
        for value in flat
        if float(pulp.value(variables[value.option_id]) or 0.0) >= 0.5
    )
    objective, metrics = evaluate_selection(selected, targets)
    return SolverResult(
        method="pulp_cbc_milp_v1",
        selected_ids=tuple(value.option_id for value in selected),
        objective=round(objective, 8),
        diagnostics={
            **{key: round(value, 8) for key, value in metrics.items()},
            "solver_status": pulp.LpStatus[status],
        },
    )
