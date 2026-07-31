from __future__ import annotations

from backend.research.planner_benchmarks import generate_problem, run_benchmark
from backend.research.solver_baselines import (
    OptionalSolverUnavailable,
    SolverResult,
    pareto_enumeration,
)


PROBLEM = {
    "schema_version": 1,
    "targets": {
        "calories": 900,
        "protein": 50,
        "carbs": 120,
        "fat": 30,
        "cost_limit": 15,
    },
    "options": [
        {
            "slot": "breakfast",
            "option_id": "b1",
            "calories": 400,
            "protein": 20,
            "carbs": 55,
            "fat": 12,
            "cost": 5,
            "taste": 0.8,
            "variety": 0.7,
            "pantry": 0.9,
        },
        {
            "slot": "breakfast",
            "option_id": "b2",
            "calories": 600,
            "protein": 15,
            "carbs": 90,
            "fat": 20,
            "cost": 9,
            "taste": 0.6,
            "variety": 0.6,
            "pantry": 0.1,
        },
        {
            "slot": "dinner",
            "option_id": "d1",
            "calories": 500,
            "protein": 30,
            "carbs": 65,
            "fat": 18,
            "cost": 7,
            "taste": 0.85,
            "variety": 0.8,
            "pantry": 0.7,
        },
        {
            "slot": "dinner",
            "option_id": "d2",
            "calories": 350,
            "protein": 25,
            "carbs": 45,
            "fat": 10,
            "cost": 4,
            "taste": 0.65,
            "variety": 0.9,
            "pantry": 0.5,
        },
    ],
}


def test_generated_problem_is_seeded_and_contains_no_user_data():
    first = generate_problem(seed=17, slots=3, options_per_slot=4)
    second = generate_problem(seed=17, slots=3, options_per_slot=4)
    different = generate_problem(seed=18, slots=3, options_per_slot=4)

    assert first == second
    assert first != different
    assert first["generator"]["contains_user_data"] is False
    assert len(first["options"]) == 12


def test_pareto_benchmark_is_valid_repeatable_and_fingerprinted():
    report = run_benchmark(
        PROBLEM,
        repeats=3,
        solvers={"pareto": pareto_enumeration},
        max_objective_gap=0,
    )

    assert report["gate"]["passed"] is True
    assert len(report["problem_fingerprint"]) == 64
    result = report["results"]["pareto"]
    assert result["status"] == "completed"
    assert result["deterministic"] is True
    assert result["valid"] is True
    assert result["representative"]["audit"]["issues"] == []
    assert result["timing_ms"]["minimum"] >= 0


def test_nondeterministic_solver_is_a_gate_failure():
    call_count = 0

    def alternating_solver(_options, _targets):
        nonlocal call_count
        call_count += 1
        selected = ("b1", "d1") if call_count % 2 else ("b1", "d2")
        return SolverResult(
            method="alternating_test_solver",
            selected_ids=selected,
            objective=0.5,
            diagnostics={},
        )

    report = run_benchmark(
        PROBLEM,
        repeats=3,
        solvers={"alternating": alternating_solver},
    )

    assert report["gate"]["passed"] is False
    assert "alternating:nondeterministic" in report["gate"]["failures"]


def test_invalid_selection_is_reported_with_missing_slots():
    def invalid_solver(_options, _targets):
        return SolverResult(
            method="invalid_test_solver",
            selected_ids=("b1",),
            objective=1.0,
            diagnostics={},
        )

    report = run_benchmark(
        PROBLEM,
        repeats=1,
        solvers={"invalid": invalid_solver},
    )

    audit = report["results"]["invalid"]["representative"]["audit"]
    assert audit["valid"] is False
    assert audit["missing_slots"] == ["dinner"]
    assert "invalid:invalid_selection" in report["gate"]["failures"]


def test_required_optional_solver_unavailability_fails_the_gate():
    def unavailable(_options, _targets):
        raise OptionalSolverUnavailable("dependency missing")

    report = run_benchmark(
        PROBLEM,
        repeats=1,
        solvers={"optional": unavailable},
        require_available=["optional"],
    )

    assert report["results"]["optional"]["status"] == "dependency_unavailable"
    assert report["gate"]["passed"] is False
    assert "optional:required_dependency_unavailable" in report["gate"]["failures"]
