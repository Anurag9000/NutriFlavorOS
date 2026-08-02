"""Authenticated preparation-resource and reviewed-evidence APIs."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import DBUser, get_db
from backend.domain.preparation import (
    PreparationScheduleRequest,
    PreparationScheduleResponse,
)
from backend.domain.preparation_evidence import (
    BuildPreparationTasksRequest,
    BuildPreparationTasksResponse,
    RecipePreparationProfileView,
)
from backend.domain.preparation_pipeline import (
    CompileAndScheduleRequest,
    CompileAndScheduleResponse,
)
from backend.domain.preparation_repair import (
    PreparationScheduleRepairRequest,
    PreparationScheduleRepairResult,
)
from backend.engines.prep_resource_scheduler import build_preparation_schedule
from backend.engines.prep_schedule_repair import (
    PreparationRepairError,
    repair_preparation_schedule,
)
from backend.services.preparation_evidence_service import (
    build_tasks_from_profiles,
    get_profile,
    list_profiles,
)
from backend.services.preparation_pipeline_service import compile_and_schedule
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/preparation", tags=["preparation"])


@router.post("/schedule", response_model=PreparationScheduleResponse)
def schedule_preparation(
    payload: PreparationScheduleRequest,
    _: DBUser = Depends(get_current_user),
) -> PreparationScheduleResponse:
    """Schedule only explicitly declared preparation work and capacities."""

    return build_preparation_schedule(payload)


@router.post(
    "/schedule/repair",
    response_model=PreparationScheduleRepairResult,
)
def repair_preparation(
    payload: PreparationScheduleRepairRequest,
    _: DBUser = Depends(get_current_user),
) -> PreparationScheduleRepairResult:
    """Return a deterministic advisory repair without accepting or persisting it."""

    try:
        return repair_preparation_schedule(payload)
    except PreparationRepairError as exc:
        raise HTTPException(status_code=409, detail=exc.as_dict()) from exc


@router.get("/profiles", response_model=List[RecipePreparationProfileView])
def preparation_profiles(
    reviewed_only: bool = Query(default=True),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: DBUser = Depends(get_current_user),
) -> List[RecipePreparationProfileView]:
    """List provenance-bearing recipe preparation evidence."""

    return list_profiles(
        db,
        reviewed_only=reviewed_only,
        active_only=active_only,
    )


@router.get(
    "/recipes/{recipe_id}/profile",
    response_model=RecipePreparationProfileView,
)
def recipe_preparation_profile(
    recipe_id: str,
    reviewed_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: DBUser = Depends(get_current_user),
) -> RecipePreparationProfileView:
    """Return one recipe's explicit preparation evidence profile."""

    return get_profile(db, recipe_id, reviewed_only=reviewed_only)


@router.post("/build-tasks", response_model=BuildPreparationTasksResponse)
def compile_preparation_tasks(
    payload: BuildPreparationTasksRequest,
    db: Session = Depends(get_db),
    _: DBUser = Depends(get_current_user),
) -> BuildPreparationTasksResponse:
    """Compile reviewed recipe profiles into namespaced scheduling tasks."""

    return build_tasks_from_profiles(db, payload)


@router.post(
    "/compile-and-schedule",
    response_model=CompileAndScheduleResponse,
)
def compile_and_schedule_preparation(
    payload: CompileAndScheduleRequest,
    db: Session = Depends(get_db),
    _: DBUser = Depends(get_current_user),
) -> CompileAndScheduleResponse:
    """Compile evidence and fail closed unless partial scheduling is explicit."""

    return compile_and_schedule(db, payload)
