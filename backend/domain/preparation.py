"""Explicit preparation-task and appliance-capacity contracts.

The platform never infers duration, appliance requirements, dependencies, or
capacity from a recipe title. Callers must provide those values from reviewed
recipe metadata or human input. Unschedulable tasks remain explicit.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class PreparationResource(BaseModel):
    resource_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    capacity: int = Field(default=1, ge=1, le=1000)
    available_from_minute: int = Field(default=0, ge=0, le=10080)
    available_until_minute: Optional[int] = Field(default=None, ge=1, le=10080)
    label: Optional[str] = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_window(self):
        if (
            self.available_until_minute is not None
            and self.available_until_minute <= self.available_from_minute
        ):
            raise ValueError("available_until_minute must be after available_from_minute")
        return self


class PreparationTask(BaseModel):
    task_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:-]+$")
    duration_minutes: int = Field(ge=1, le=1440)
    earliest_start_minute: int = Field(default=0, ge=0, le=10080)
    latest_finish_minute: Optional[int] = Field(default=None, ge=1, le=10080)
    priority: int = Field(default=0, ge=-1000, le=1000)
    resource_demands: Dict[str, int] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_task(self):
        if (
            self.latest_finish_minute is not None
            and self.latest_finish_minute <= self.earliest_start_minute
        ):
            raise ValueError("latest_finish_minute must be after earliest_start_minute")
        invalid = [
            resource_id
            for resource_id, demand in self.resource_demands.items()
            if not resource_id.strip() or demand < 1
        ]
        if invalid:
            raise ValueError("resource demands must use non-empty IDs and positive integers")
        normalized_dependencies = [value.strip() for value in self.dependencies]
        if any(not value for value in normalized_dependencies):
            raise ValueError("dependency IDs cannot be blank")
        if len(normalized_dependencies) != len(set(normalized_dependencies)):
            raise ValueError("dependency IDs must be unique per task")
        if self.task_id in normalized_dependencies:
            raise ValueError("a task cannot depend on itself")
        self.dependencies = normalized_dependencies
        return self


class PreparationScheduleRequest(BaseModel):
    horizon_minutes: int = Field(default=24 * 60, ge=1, le=10080)
    granularity_minutes: int = Field(default=5, ge=1, le=60)
    resources: List[PreparationResource] = Field(default_factory=list, max_length=200)
    tasks: List[PreparationTask] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_request(self):
        resource_ids = [resource.resource_id for resource in self.resources]
        task_ids = [task.task_id for task in self.tasks]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("resource_id values must be unique")
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id values must be unique")
        task_id_set = set(task_ids)
        for resource in self.resources:
            if resource.available_from_minute >= self.horizon_minutes:
                raise ValueError(
                    f"resource {resource.resource_id} starts outside the scheduling horizon"
                )
        for task in self.tasks:
            if task.earliest_start_minute >= self.horizon_minutes:
                raise ValueError(
                    f"task {task.task_id} starts outside the scheduling horizon"
                )
            unknown = sorted(set(task.dependencies) - task_id_set)
            if unknown:
                raise ValueError(
                    f"task {task.task_id} references unknown dependencies: {', '.join(unknown)}"
                )

        graph = {task.task_id: tuple(task.dependencies) for task in self.tasks}
        state: Dict[str, int] = {}
        trail: List[str] = []

        def visit(task_id: str) -> None:
            marker = state.get(task_id, 0)
            if marker == 2:
                return
            if marker == 1:
                start = trail.index(task_id)
                cycle = trail[start:] + [task_id]
                raise ValueError("preparation dependency cycle: " + " -> ".join(cycle))
            state[task_id] = 1
            trail.append(task_id)
            for dependency in graph[task_id]:
                visit(dependency)
            trail.pop()
            state[task_id] = 2

        for task_id in sorted(graph):
            visit(task_id)
        return self


class ScheduledPreparationTask(BaseModel):
    task_id: str
    start_minute: int
    finish_minute: int
    duration_minutes: int
    priority: int
    resource_demands: Dict[str, int]
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnscheduledPreparationTask(BaseModel):
    task_id: str
    reason_code: str
    message: str
    missing_resources: List[str] = Field(default_factory=list)
    blocked_by: List[str] = Field(default_factory=list)
    capacity_violations: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PreparationScheduleResponse(BaseModel):
    method: str = "deterministic_dependency_aware_resource_scheduler_v2"
    deterministic: bool = True
    horizon_minutes: int
    granularity_minutes: int
    scheduled: List[ScheduledPreparationTask]
    unscheduled: List[UnscheduledPreparationTask]
    resource_utilization: Dict[str, float]
    resource_peak_usage: Dict[str, int]
    makespan_minutes: int
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
