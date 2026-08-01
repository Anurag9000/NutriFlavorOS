#!/usr/bin/env python3
"""Run reproducible planner benchmarks and emit a machine-readable report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from backend.domain.benchmark_fixtures import PlannerBenchmarkFixture
from backend.research.planner_benchmarks import generate_problem, run_benchmark


def _load_or_generate(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> Dict[str, Any]:
    if args.problem is not None and args.generate_seed is not None:
        parser.error("Provide either a problem file or --generate-seed, not both")
    if args.problem is None and args.generate_seed is None:
        parser.error("Provide a problem file or --generate-seed")
    if args.problem is not None:
        raw = json.loads(args.problem.read_text(encoding="utf-8"))
        return PlannerBenchmarkFixture.model_validate(raw).to_problem()
    problem = PlannerBenchmarkFixture.model_validate(
        generate_problem(
            seed=args.generate_seed,
            slots=args.slots,
            options_per_slot=args.options_per_slot,
        )
    ).to_problem()
    if args.save_problem is not None:
        args.save_problem.parent.mkdir(parents=True, exist_ok=True)
        args.save_problem.write_text(
            json.dumps(problem, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return problem


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark Pareto, optional CP-SAT, and optional MILP planners with "
            "repeatability and selection-validity gates."
        )
    )
    parser.add_argument("problem", nargs="?", type=Path)
    parser.add_argument("--generate-seed", type=int)
    parser.add_argument("--slots", type=int, default=7)
    parser.add_argument("--options-per-slot", type=int, default=5)
    parser.add_argument("--save-problem", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/planner_benchmark.json"),
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-objective-gap", type=float)
    parser.add_argument(
        "--require-solver",
        action="append",
        default=[],
        choices=["pareto", "cp_sat", "milp"],
        help="Fail when this solver or its optional dependency is unavailable",
    )
    parser.add_argument(
        "--allow-gate-failures",
        action="store_true",
        help="Write the report but return zero even when regression gates fail",
    )
    args = parser.parse_args()

    try:
        problem = _load_or_generate(args, parser)
        report = run_benchmark(
            problem,
            repeats=args.repeats,
            max_objective_gap=args.max_objective_gap,
            require_available=args.require_solver,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Planner benchmark failed: {type(exc).__name__}: {exc}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    if not report["gate"]["passed"] and not args.allow_gate_failures:
        print("Planner benchmark regression gate failed:")
        for failure in report["gate"]["failures"]:
            print(f"- {failure}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
