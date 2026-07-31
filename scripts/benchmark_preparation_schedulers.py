#!/usr/bin/env python3
"""Benchmark the product preparation heuristic against an exact small solver."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from backend.domain.preparation import PreparationScheduleRequest
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.research.exact_preparation_scheduler import (
    ExactPreparationInfeasible,
    ExactPreparationSearchLimit,
    exact_preparation_schedule,
)


def request_fingerprint(request: PreparationScheduleRequest) -> str:
    raw = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _schedule_summary(value) -> dict:
    return {
        "method": value.method,
        "scheduled_count": len(value.scheduled),
        "unscheduled_count": len(value.unscheduled),
        "scheduled": [item.model_dump(mode="json") for item in value.scheduled],
        "unscheduled": [item.model_dump(mode="json") for item in value.unscheduled],
        "makespan_minutes": value.makespan_minutes,
        "resource_utilization": value.resource_utilization,
        "resource_peak_usage": value.resource_peak_usage,
        "diagnostics": value.diagnostics,
    }


def benchmark_preparation_schedulers(
    request: PreparationScheduleRequest,
    *,
    heuristic_repeats: int = 3,
    maximum_tasks: int = 10,
    maximum_nodes: int = 1_000_000,
) -> dict:
    if heuristic_repeats < 1:
        raise ValueError("heuristic_repeats must be at least 1")

    heuristic_runs = []
    heuristic_times = []
    for _ in range(heuristic_repeats):
        started = time.perf_counter()
        value = build_preparation_schedule(request)
        heuristic_times.append(time.perf_counter() - started)
        heuristic_runs.append(value)
    deterministic = all(value == heuristic_runs[0] for value in heuristic_runs[1:])
    heuristic = heuristic_runs[0]

    exact_started = time.perf_counter()
    exact_status = "ok"
    exact_error = None
    exact = None
    try:
        exact = exact_preparation_schedule(
            request,
            maximum_tasks=maximum_tasks,
            maximum_nodes=maximum_nodes,
        )
    except ExactPreparationInfeasible as exc:
        exact_status = "infeasible"
        exact_error = str(exc)
    except ExactPreparationSearchLimit as exc:
        exact_status = "search_limit"
        exact_error = str(exc)
    exact_seconds = time.perf_counter() - exact_started

    heuristic_complete = (
        len(heuristic.scheduled) == len(request.tasks)
        and len(heuristic.unscheduled) == 0
    )
    exact_complete = exact is not None
    gap = (
        heuristic.makespan_minutes - exact.optimal_makespan_minutes
        if heuristic_complete and exact_complete
        else None
    )
    ratio = (
        heuristic.makespan_minutes / exact.optimal_makespan_minutes
        if heuristic_complete
        and exact_complete
        and exact.optimal_makespan_minutes > 0
        else None
    )

    return {
        "protocol_version": "preparation_scheduler_exact_comparison_v1",
        "input_fingerprint": request_fingerprint(request),
        "configuration": {
            "heuristic_repeats": heuristic_repeats,
            "maximum_tasks": maximum_tasks,
            "maximum_nodes": maximum_nodes,
            "task_count": len(request.tasks),
            "resource_count": len(request.resources),
            "horizon_minutes": request.horizon_minutes,
            "granularity_minutes": request.granularity_minutes,
        },
        "heuristic": {
            "deterministic": deterministic,
            "elapsed_seconds": heuristic_times,
            "minimum_elapsed_seconds": min(heuristic_times),
            "maximum_elapsed_seconds": max(heuristic_times),
            "mean_elapsed_seconds": sum(heuristic_times) / len(heuristic_times),
            "complete": heuristic_complete,
            "schedule": _schedule_summary(heuristic),
        },
        "exact": {
            "status": exact_status,
            "error": exact_error,
            "elapsed_seconds": exact_seconds,
            "complete": exact_complete,
            "optimal_makespan_minutes": (
                exact.optimal_makespan_minutes if exact else None
            ),
            "total_start_minutes": exact.total_start_minutes if exact else None,
            "nodes_visited": exact.nodes_visited if exact else None,
            "complete_schedules_evaluated": (
                exact.complete_schedules_evaluated if exact else None
            ),
            "schedule": _schedule_summary(exact.schedule) if exact else None,
        },
        "comparison": {
            "makespan_gap_minutes": gap,
            "makespan_ratio": ratio,
            "heuristic_no_worse_than_exact": gap is not None and gap <= 0,
        },
        "limitations": [
            "Exact optimality is proven only for the aligned-start contract and configured search bounds.",
            "The exact baseline requires a complete schedule and is intended only for bounded fixtures.",
            "Synthetic or small-fixture parity is not evidence of product-scale optimality.",
        ],
    }


def regression_failures(
    report: dict,
    *,
    require_heuristic_complete: bool,
    require_exact_optimal: bool,
    maximum_gap_minutes: int | None,
    maximum_exact_nodes: int | None,
) -> list[str]:
    failures = []
    heuristic = report["heuristic"]
    exact = report["exact"]
    comparison = report["comparison"]
    if not heuristic["deterministic"]:
        failures.append("heuristic output is nondeterministic")
    if require_heuristic_complete and not heuristic["complete"]:
        failures.append("heuristic did not produce a complete schedule")
    if require_exact_optimal and exact["status"] != "ok":
        failures.append(
            f"exact solver did not prove an optimum: {exact['status']} {exact['error'] or ''}".strip()
        )
    if maximum_gap_minutes is not None:
        if maximum_gap_minutes < 0:
            raise ValueError("maximum_gap_minutes cannot be negative")
        observed = comparison["makespan_gap_minutes"]
        if observed is None:
            failures.append("makespan gap is unavailable")
        elif observed > maximum_gap_minutes:
            failures.append(
                f"heuristic makespan gap {observed} exceeds {maximum_gap_minutes} minutes"
            )
    if maximum_exact_nodes is not None:
        if maximum_exact_nodes < 1:
            raise ValueError("maximum_exact_nodes must be at least 1")
        observed = exact["nodes_visited"]
        if observed is None:
            failures.append("exact node count is unavailable")
        elif observed > maximum_exact_nodes:
            failures.append(
                f"exact search visited {observed} nodes; limit is {maximum_exact_nodes}"
            )
    return failures


def load_request(path: Path) -> PreparationScheduleRequest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PreparationScheduleRequest.model_validate(raw)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare deterministic preparation heuristic to exact search"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--heuristic-repeats", type=int, default=3)
    parser.add_argument("--maximum-tasks", type=int, default=10)
    parser.add_argument("--maximum-nodes", type=int, default=1_000_000)
    parser.add_argument("--require-heuristic-complete", action="store_true")
    parser.add_argument("--require-exact-optimal", action="store_true")
    parser.add_argument("--maximum-gap-minutes", type=int)
    parser.add_argument("--maximum-exact-nodes", type=int)
    args = parser.parse_args()

    try:
        request = load_request(args.input)
        report = benchmark_preparation_schedulers(
            request,
            heuristic_repeats=args.heuristic_repeats,
            maximum_tasks=args.maximum_tasks,
            maximum_nodes=args.maximum_nodes,
        )
        failures = regression_failures(
            report,
            require_heuristic_complete=args.require_heuristic_complete,
            require_exact_optimal=args.require_exact_optimal,
            maximum_gap_minutes=args.maximum_gap_minutes,
            maximum_exact_nodes=args.maximum_exact_nodes,
        )
        report["regression_failures"] = failures
        report["passed"] = not failures
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Preparation scheduler benchmark failed: {type(exc).__name__}: {exc}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "passed": not failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
