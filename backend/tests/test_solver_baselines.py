from backend.research.solver_baselines import OptionalSolverUnavailable, PlannerOption, PlannerTargets, cp_sat_optimize, milp_optimize, pareto_enumeration


def options():
    return [
        PlannerOption("breakfast", "a1", 400, 20, 50, 12, 4, 0.8, 0.9, 0.8),
        PlannerOption("breakfast", "a2", 500, 25, 55, 15, 5, 0.7, 0.2, 0.1),
        PlannerOption("dinner", "b1", 600, 40, 65, 20, 7, 0.7, 0.8, 0.7),
        PlannerOption("dinner", "b2", 700, 35, 75, 25, 8, 0.9, 0.1, 0.1),
    ]


def test_pareto_solver_is_deterministic_and_feasible():
    target = PlannerTargets(1000, 60, 115, 32, 20)
    first = pareto_enumeration(options(), target)
    second = pareto_enumeration(options(), target)
    assert first.selected_ids == second.selected_ids
    assert len(first.selected_ids) == 2
    assert first.diagnostics["combinations_inspected"] == 4


def test_optional_solvers_match_contract_when_installed():
    target = PlannerTargets(1000, 60, 115, 32, 20)
    for solver in (cp_sat_optimize, milp_optimize):
        try:
            result = solver(options(), target)
        except OptionalSolverUnavailable:
            continue
        assert len(result.selected_ids) == 2
