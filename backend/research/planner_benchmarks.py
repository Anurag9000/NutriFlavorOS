"""Reproducible planner benchmark scenarios, execution, and regression gates."""

from __future__ import annotations

import hashlib
import json
import platform
import random
import statistics
import sys
from dataclasses import asdict
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from backend.research.solver_baselines import (
    OptionalSolverUnavailable,
    PlannerOption,
    PlannerTargets,
    SolverResult,
    cp_sat_optimize,
    evaluate_selection,
    milp_optimize,
    pareto_enumeration,
)


Solver = Callable[[Iterable[PlannerOption], PlannerTargets], SolverResult]
DEFAULT_SOLVERS: Dict[str, Solver] = {
    "pareto": pareto_enumeration,
    "cp_sat": cp_sat_optimize,
    "milp": milp_optimize,
}


def canonical_fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def generate_problem(
    *,
    seed: int,
    slots: int = 7,
    options_per_slot: int = 5,
) -> Dict[str, Any]:
    """Generate a deterministic synthetic benchmark without user data."""

    if not 1 <= slots <= 50:
        raise ValueError("slots must be from 1 to 50")
    if not 2 <= options_per_slot <= 20:
        raise ValueError("options_per_slot must be from 2 to 20")
    rng = random.Random(seed)
    options = []
    for slot_index in range(slots):
        slot = f"slot_{slot_index + 1:02d}"
        for option_index in range(options_per_slot):
            calories = rng.uniform(250, 750)
            protein = rng.uniform(8, 55)
            carbs = rng.uniform(20, 110)
            fat = rng.uniform(5, 35)
            options.append(
                {
                    "slot": slot,
                    "option_id": f"{slot}_option_{option_index + 1:02d}",
                    "calories": round(calories, 4),
                    "protein": round(protein, 4),
                    "carbs": round(carbs, 4),
                    "fat": round(fat, 4),
                    "cost": round(rng.uniform(1.5, 12.0), 4),
                    "taste": round(rng.uniform(0.25, 1.0), 4),
                    "variety": round(rng.uniform(0.25, 1.0), 4),
                    "pantry": round(rng.uniform(0.0, 1.0), 4),
                }
            )
    return {
        "schema_version": 1,
        "generator": {
            "name": "deterministic_synthetic_planner_problem_v1",
            "seed": seed,
            "slots": slots,
            "options_per_slot": options_per_slot,
            "contains_user_data": False,
        },
        "targets": {
            "calories": round(slots * 500.0, 4),
            "protein": round(slots * 30.0, 4),
            "carbs": round(slots * 65.0, 4),
            "fat": round(slots * 20.0, 4),
            "cost_limit": round(slots * 7.0, 4),
        },
        "options": options,
    }


def parse_problem(raw: Mapping[str, Any]) -> tuple[list[PlannerOption], PlannerTargets]:
    if not isinstance(raw.get("options"), list) or not raw["options"]:
        raise ValueError("problem.options must be a non-empty list")
    if not isinstance(raw.get("targets"), Mapping):
        raise ValueError("problem.targets must be an object")
    options = [PlannerOption(**value) for value in raw["options"]]
    targets = PlannerTargets(**raw["targets"])
    identifiers = [option.option_id for option in options]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("option_id values must be unique")
    slots = {option.slot for option in options}
    if not slots:
        raise ValueError("at least one slot is required")
    return options, targets


def _selection_audit(
    result: SolverResult,
    options: Sequence[PlannerOption],
    targets: PlannerTargets,
) -> Dict[str, Any]:
    by_id = {option.option_id: option for option in options}
    expected_slots = sorted({option.slot for option in options})
    unknown = sorted(set(result.selected_ids) - set(by_id))
    duplicates = sorted(
        identifier
        for identifier in set(result.selected_ids)
        if result.selected_ids.count(identifier) > 1
    )
    selected = [by_id[identifier] for identifier in result.selected_ids if identifier in by_id]
    selected_slots = [option.slot for option in selected]
    missing_slots = sorted(set(expected_slots) - set(selected_slots))
    duplicate_slots = sorted(
        slot for slot in set(selected_slots) if selected_slots.count(slot) > 1
    )
    common_objective = None
    metrics: Dict[str, float] = {}
    if not unknown and not duplicates and not missing_slots and not duplicate_slots:
        common_objective, metrics = evaluate_selection(selected, targets)
    cost_violation = 0.0
    if targets.cost_limit is not None and metrics:
        cost_violation = max(0.0, metrics["cost"] - targets.cost_limit)
    issues = []
    if unknown:
        issues.append("unknown_selected_ids")
    if duplicates:
        issues.append("duplicate_selected_ids")
    if missing_slots:
        issues.append("missing_slots")
    if duplicate_slots:
        issues.append("duplicate_slots")
    if cost_violation > 1e-8:
        issues.append("cost_limit_violation")
    return {
        "valid": not issues,
        "issues": issues,
        "unknown_selected_ids": unknown,
        "duplicate_selected_ids": duplicates,
        "missing_slots": missing_slots,
        "duplicate_slots": duplicate_slots,
        "common_objective": round(common_objective, 8) if common_objective is not None else None,
        "reported_objective": result.objective,
        "reported_objective_delta": (
            round(abs(result.objective - common_objective), 8)
            if common_objective is not None
            else None
        ),
        "metrics": {key: round(value, 8) for key, value in metrics.items()},
        "cost_limit_violation": round(cost_violation, 8),
    }


def run_benchmark(
    raw_problem: Mapping[str, Any],
    *,
    repeats: int = 3,
    solvers: Mapping[str, Solver] | None = None,
    max_objective_gap: float | None = None,
    require_available: Iterable[str] = (),
) -> Dict[str, Any]:
    if not 1 <= repeats <= 50:
        raise ValueError("repeats must be from 1 to 50")
    if max_objective_gap is not None and max_objective_gap < 0:
        raise ValueError("max_objective_gap cannot be negative")
    options, targets = parse_problem(raw_problem)
    solver_map = dict(solvers or DEFAULT_SOLVERS)
    required = set(require_available)
    unknown_required = sorted(required - set(solver_map))
    if unknown_required:
        raise ValueError(f"Unknown required solvers: {', '.join(unknown_required)}")

    results: Dict[str, Any] = {}
    gate_failures: list[str] = []
    for name, solver in sorted(solver_map.items()):
        runs = []
        try:
            for repeat in range(repeats):
                started = perf_counter()
                result = solver(list(options), targets)
                elapsed_ms = (perf_counter() - started) * 1000.0
                audit = _selection_audit(result, options, targets)
                runs.append(
                    {
                        "repeat": repeat,
                        "elapsed_ms": round(elapsed_ms, 6),
                        "method": result.method,
                        "selected_ids": list(result.selected_ids),
                        "objective": result.objective,
                        "diagnostics": result.diagnostics,
                        "audit": audit,
                    }
                )
        except OptionalSolverUnavailable as exc:
            results[name] = {
                "status": "dependency_unavailable",
                "message": str(exc),
                "required": name in required,
            }
            if name in required:
                gate_failures.append(f"{name}:required_dependency_unavailable")
            continue
        except Exception as exc:
            results[name] = {
                "status": "failed",
                "message": f"{type(exc).__name__}: {exc}",
            }
            gate_failures.append(f"{name}:execution_failed")
            continue

        signatures = {
            (tuple(run["selected_ids"]), run["objective"])
            for run in runs
        }
        deterministic = len(signatures) == 1
        valid = all(run["audit"]["valid"] for run in runs)
        elapsed = [run["elapsed_ms"] for run in runs]
        results[name] = {
            "status": "completed",
            "deterministic": deterministic,
            "valid": valid,
            "repeat_count": repeats,
            "timing_ms": {
                "minimum": round(min(elapsed), 6),
                "median": round(statistics.median(elapsed), 6),
                "maximum": round(max(elapsed), 6),
            },
            "representative": runs[0],
            "runs": runs,
        }
        if not deterministic:
            gate_failures.append(f"{name}:nondeterministic")
        if not valid:
            gate_failures.append(f"{name}:invalid_selection")

    completed = {
        name: value
        for name, value in results.items()
        if value.get("status") == "completed"
        and value.get("valid")
        and value["representative"]["audit"]["common_objective"] is not None
    }
    best_objective = max(
        (
            value["representative"]["audit"]["common_objective"]
            for value in completed.values()
        ),
        default=None,
    )
    comparisons = {}
    for name, value in completed.items():
        objective = value["representative"]["audit"]["common_objective"]
        gap = round(best_objective - objective, 8) if best_objective is not None else None
        comparisons[name] = {
            "common_objective": objective,
            "gap_to_best": gap,
        }
        if max_objective_gap is not None and gap is not None and gap > max_objective_gap:
            gate_failures.append(f"{name}:objective_gap_exceeded")

    slots = sorted({option.slot for option in options})
    report = {
        "schema_version": 2,
        "problem_fingerprint": canonical_fingerprint(raw_problem),
        "problem": {
            "slot_count": len(slots),
            "option_count": len(options),
            "options_per_slot": {
                slot: sum(option.slot == slot for option in options) for slot in slots
            },
            "targets": asdict(targets),
            "generator": raw_problem.get("generator"),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "repeats": repeats,
        "results": results,
        "comparisons": {
            "best_common_objective": best_objective,
            "solvers": comparisons,
            "maximum_allowed_gap": max_objective_gap,
        },
        "gate": {
            "passed": not gate_failures,
            "failures": sorted(set(gate_failures)),
        },
    }
    return report
