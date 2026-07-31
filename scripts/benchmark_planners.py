#!/usr/bin/env python3
"""Benchmark Pareto, CP-SAT, and MILP planner baselines on a JSON problem."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.research.solver_baselines import (
    OptionalSolverUnavailable,
    PlannerOption,
    PlannerTargets,
    cp_sat_optimize,
    milp_optimize,
    pareto_enumeration,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("problem", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/planner_benchmark.json"))
    args = parser.parse_args()

    raw = json.loads(args.problem.read_text(encoding="utf-8"))
    options = [PlannerOption(**value) for value in raw["options"]]
    targets = PlannerTargets(**raw["targets"])
    results = {}
    for name, function in (
        ("pareto", pareto_enumeration),
        ("cp_sat", cp_sat_optimize),
        ("milp", milp_optimize),
    ):
        try:
            result = function(options, targets)
            results[name] = {
                "status": "completed",
                "result": {
                    "method": result.method,
                    "selected_ids": list(result.selected_ids),
                    "objective": result.objective,
                    "diagnostics": result.diagnostics,
                },
            }
        except OptionalSolverUnavailable as exc:
            results[name] = {"status": "dependency_unavailable", "message": str(exc)}
        except Exception as exc:
            results[name] = {"status": "failed", "message": str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
