#!/usr/bin/env python3
"""Run deterministic acceptance cases for minimal-change preparation repair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_repair import (
    PreparationRepairStrategy,
    PreparationScheduleRepairRequest,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import repair_preparation_schedule


def schedule_request(
    *,
    capacity: int,
    windows: list[tuple[int, int]] | None = None,
    task_count: int = 3,
) -> PreparationScheduleRequest:
    return PreparationScheduleRequest.model_validate(
        {
            "horizon_minutes": 180,
            "granularity_minutes": 5,
            "resources": [
                {
                    "resource_id": "person",
                    "label": "Available cook",
                    "capacity": capacity,
                    "availability_windows": [
                        {"start_minute": start, "end_minute": end}
                        for start, end in (windows or [(0, 180)])
                    ],
                }
            ],
            "tasks": [
                {
                    "task_id": f"task.{index + 1}",
                    "duration_minutes": 10,
                    "earliest_start_minute": 0,
                    "latest_finish_minute": 120,
                    "priority": 1,
                    "resource_demands": {"person": 1},
                    "dependencies": [],
                    "metadata": {"benchmark_index": index + 1},
                }
                for index in range(task_count)
            ],
        }
    )


def repair(
    previous: PreparationScheduleRequest,
    revised: PreparationScheduleRequest,
    *,
    strategy: PreparationRepairStrategy,
    immutable: list[str] | None = None,
    allow_partial: bool = False,
):
    previous_response = build_preparation_schedule(previous)
    if previous_response.unscheduled:
        raise RuntimeError("Benchmark previous schedule must be complete")
    return repair_preparation_schedule(
        PreparationScheduleRepairRequest(
            previous_request=previous,
            previous_response=previous_response,
            revised_request=revised,
            immutable_task_ids=immutable or [],
            strategy=strategy,
            allow_partial=allow_partial,
        )
    )


def objective(result) -> tuple[int, int, int, int]:
    value = result.objective
    return (
        value.unscheduled_task_count,
        value.changed_task_count,
        value.total_displacement_minutes,
        value.makespan_minutes,
    )


def run_case(
    case_id: str,
    description: str,
    execute: Callable[[], object],
    accept: Callable[[object], list[str]],
) -> dict:
    result = execute()
    failures = accept(result)
    payload = result.model_dump(mode="json")
    return {
        "case_id": case_id,
        "description": description,
        "passed": not failures,
        "failures": failures,
        "objective": payload["objective"],
        "preserved_task_ids": payload["preserved_task_ids"],
        "moved_tasks": payload["moved_tasks"],
        "added_task_ids": payload["added_task_ids"],
        "removed_task_ids": payload["removed_task_ids"],
        "unscheduled_task_ids": payload["unscheduled_task_ids"],
        "diagnostics": payload["diagnostics"],
        "hashes": {
            "previous_schedule": payload["previous_schedule_hash"],
            "revised_request": payload["revised_request_hash"],
            "repaired_response": payload["repaired_response_hash"],
        },
    }


def benchmark_report() -> dict:
    identity = schedule_request(capacity=1)
    capacity_previous = schedule_request(capacity=3)
    capacity_revised = schedule_request(capacity=1)
    window_previous = schedule_request(capacity=1)
    window_revised = schedule_request(capacity=1, windows=[(20, 180)])

    cases = [
        run_case(
            "identity-greedy",
            "No revised constraint changes; every task must remain at its prior placement.",
            lambda: repair(
                identity,
                identity,
                strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
            ),
            lambda result: [
                message
                for condition, message in [
                    (result.complete, "repair is incomplete"),
                    (len(result.preserved_task_ids) == 3, "not every task was preserved"),
                    (result.objective.changed_task_count == 0, "identity repair changed tasks"),
                    (result.objective.total_displacement_minutes == 0, "identity repair displaced tasks"),
                ]
                if not condition
            ],
        ),
        run_case(
            "capacity-reduction-greedy",
            "Capacity falls from three to one; exactly two tasks should move by the minimum total displacement.",
            lambda: repair(
                capacity_previous,
                capacity_revised,
                strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
            ),
            lambda result: [
                message
                for condition, message in [
                    (result.complete, "repair is incomplete"),
                    (len(result.preserved_task_ids) == 1, "unexpected preserved-task count"),
                    (len(result.moved_tasks) == 2, "unexpected moved-task count"),
                    (result.objective.total_displacement_minutes == 30, "minimum displacement should be 30 minutes"),
                ]
                if not condition
            ],
        ),
        run_case(
            "immutable-capacity-reduction",
            "One completed task is pinned while remaining tasks repair around it.",
            lambda: repair(
                capacity_previous,
                capacity_revised,
                strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
                immutable=["task.1"],
            ),
            lambda result: [
                message
                for condition, message in [
                    (result.complete, "repair is incomplete"),
                    ("task.1" in result.preserved_task_ids, "immutable task was not preserved"),
                    (all(value.task_id != "task.1" for value in result.moved_tasks), "immutable task moved"),
                ]
                if not condition
            ],
        ),
        run_case(
            "window-shift-greedy",
            "Availability begins later; all tasks move to the nearest feasible continuous window.",
            lambda: repair(
                window_previous,
                window_revised,
                strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
            ),
            lambda result: [
                message
                for condition, message in [
                    (result.complete, "repair is incomplete"),
                    (min(value.start_minute for value in result.response.scheduled) >= 20, "task remained outside revised window"),
                    (result.objective.changed_task_count == 3, "all tasks should move after window shift"),
                ]
                if not condition
            ],
        ),
    ]

    greedy = repair(
        capacity_previous,
        capacity_revised,
        strategy=PreparationRepairStrategy.GREEDY_MIN_CHANGE,
    )
    exact = repair(
        capacity_previous,
        capacity_revised,
        strategy=PreparationRepairStrategy.BOUNDED_EXACT_MIN_CHANGE,
    )
    exact_failures: list[str] = []
    if objective(exact) > objective(greedy):
        exact_failures.append(
            f"exact objective {objective(exact)} is worse than greedy {objective(greedy)}"
        )
    cases.append(
        {
            "case_id": "bounded-exact-comparator",
            "description": "Bounded exact repair must be lexicographically no worse than greedy on the same small instance.",
            "passed": not exact_failures,
            "failures": exact_failures,
            "greedy_objective": list(objective(greedy)),
            "exact_objective": list(objective(exact)),
            "exact_diagnostics": exact.diagnostics.model_dump(mode="json"),
            "hashes": {
                "greedy": greedy.repaired_response_hash,
                "exact": exact.repaired_response_hash,
            },
        }
    )

    passed = sum(value["passed"] for value in cases)
    return {
        "document_version": "preparation-repair-benchmark-report-v1",
        "deterministic": True,
        "case_count": len(cases),
        "passed_count": passed,
        "failed_case_ids": [
            value["case_id"] for value in cases if not value["passed"]
        ],
        "cases": cases,
        "limitations": [
            "Synthetic deterministic contract cases are not representative household performance evidence",
            "The bounded exact comparator is limited to small task sets",
            "No repair is persisted or accepted automatically",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark deterministic minimal-change preparation repair"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = benchmark_report()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not report["failed_case_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
