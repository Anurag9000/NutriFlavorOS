"""Integrated preparation evidence compilation and deterministic scheduling."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.domain.preparation import PreparationScheduleRequest
from backend.domain.preparation_evidence import BuildPreparationTasksRequest
from backend.domain.preparation_pipeline import (
    CompileAndScheduleRequest,
    CompileAndScheduleResponse,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.services.preparation_evidence_service import build_tasks_from_profiles


def compile_and_schedule(
    db: Session,
    payload: CompileAndScheduleRequest,
) -> CompileAndScheduleResponse:
    """Compile reviewed evidence and schedule only when the policy permits it.

    By default, any unresolved occurrence blocks scheduling. Callers must set
    `allow_partial=true` explicitly to schedule the covered subset. The response
    always preserves unresolved evidence and profile-version provenance.
    """

    compilation = build_tasks_from_profiles(
        db,
        BuildPreparationTasksRequest(
            occurrences=payload.occurrences,
            duration_policy=payload.duration_policy,
            reviewed_only=payload.reviewed_only,
        ),
    )
    has_unresolved = bool(compilation.unresolved)
    if has_unresolved and not payload.allow_partial:
        return CompileAndScheduleResponse(
            compilation=compilation,
            schedule=None,
            partial=False,
            execution_status="blocked_unresolved",
        )
    if not compilation.tasks:
        return CompileAndScheduleResponse(
            compilation=compilation,
            schedule=None,
            partial=has_unresolved,
            execution_status="no_compilable_tasks",
        )

    schedule = build_preparation_schedule(
        PreparationScheduleRequest(
            horizon_minutes=payload.horizon_minutes,
            granularity_minutes=payload.granularity_minutes,
            resources=payload.resources,
            tasks=compilation.tasks,
        )
    )
    schedule.diagnostics.update(
        {
            "evidence_pipeline": "reviewed_profile_compilation_v1",
            "profile_versions": compilation.profile_versions,
            "unresolved_occurrence_count": len(compilation.unresolved),
            "partial_schedule": has_unresolved,
            "duration_policy": compilation.duration_policy.value,
            "reviewed_only": payload.reviewed_only,
        }
    )
    return CompileAndScheduleResponse(
        compilation=compilation,
        schedule=schedule,
        partial=has_unresolved,
        execution_status="scheduled",
    )
